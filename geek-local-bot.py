#!/usr/bin/env python3
"""
Geek Local Bot — Telegram bot with Gemma 9B + system command execution
Direct local LLM with ability to run commands on Mac
"""

import json
import logging
import subprocess
import urllib.request
import urllib.error
import time

# === CONFIG ===
BOT_TOKEN = "8293339092:AAEbV9-19j0qHv8ZmRU8yIG7EgoVMp-CeZk"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:9b"
ALLOWED_USER = 170285780
MAX_HISTORY = 20
TIMEOUT = 120  # seconds for commands

SYSTEM_PROMPT = """Ты — Geek Local, AI-ассистент с прямым доступом к Mac.
Работаешь на модели Gemma 9B. Отвечай на русском.

У тебя есть доступ к командной строке Mac. Когда пользователь просит что-то сделать:
1. Определи какую команду нужно выполнить
2. Ответь в формате: EXEC: <команда>
3. После выполнения команды — объясни результат

Доступные инструменты на Mac:
- mouse.sh click/double/right/move/type/key/hotkey/scroll — управление мышкой и клавиатурой
- screenshot.sh — скриншот экрана
- open <app> — открыть приложение
- safari-ui.sh — автоматизация Safari
- whisperkit-cli transcribe — транскрипция аудио
- ollama — управление моделями
- Любые shell команды (ls, cat, grep, curl и т.д.)

Примеры:
Пользователь: "Открой Safari" → EXEC: open -a Safari
Пользователь: "Кликни на 500 300" → EXEC: bash /Users/geek2026/.openclaw/workspace/scripts/mouse.sh click 500 300
Пользователь: "Скриншот" → EXEC: screencapture /tmp/screenshot.png && echo "done"
Пользователь: "Какой сегодня день" → EXEC: date

⚠️ Правила безопасности:
- НЕ выполнять rm -rf или деструктивные команды без подтверждения
- НЕ выполнять команды с sudo
- НЕ отправлять данные наружу (curl/wget на внешние серверы)
- Если не уверен — спроси пользователя
"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("geek-local-bot")

SCRIPTS_DIR = "/Users/geek2026/.openclaw/workspace/scripts"

# === STATE ===
conversations = {}

def api(method, data=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    if data:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def exec_command(cmd):
    """Execute shell command safely"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=TIMEOUT, cwd="/Users/geek2026"
        )
        output = result.stdout.strip()
        error = result.stderr.strip()
        if result.returncode != 0 and error:
            return f"❌ Ошибка (code {result.returncode}):\n{error[:1000]}"
        return output[:2000] if output else "✅ Выполнено (нет вывода)"
    except subprocess.TimeoutExpired:
        return "⏱️ Таймаут — команда выполнялась слишком долго"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def ollama_chat(messages):
    data = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2048}
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
        return result.get("message", {}).get("content", "⚠️ Нет ответа")

def send_message(chat_id, text):
    # Telegram limit is 4096 chars
    for i in range(0, len(text), 4000):
        chunk = text[i:i+4000]
        try:
            api("sendMessage", {"chat_id": chat_id, "text": chunk})
        except Exception as e:
            log.error(f"Send error: {e}")
            try:
                api("sendMessage", {"chat_id": chat_id, "text": chunk[:1000]})
            except:
                pass

def process_message(text, user_id):
    """Process user message through Gemma and execute commands"""
    if user_id not in conversations:
        conversations[user_id] = []

    history = conversations[user_id]
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-MAX_HISTORY:]

    # Get response from Ollama
    response = ollama_chat(messages)

    # Check for EXEC: commands
    exec_results = []
    final_response = response

    for line in response.split('\n'):
        line_stripped = line.strip()
        if line_stripped.upper().startswith("EXEC:"):
            cmd = line_stripped[5:].strip()
            if cmd:
                log.info(f"Executing: {cmd}")
                result = exec_command(cmd)
                exec_results.append(f"📤 Команда: `{cmd}`\n📥 Результат:\n{result}")

                # Feed result back to model for explanation
                history.append({"role": "assistant", "content": response})
                followup_msgs = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Выполнил: {cmd}\nРезультат:\n{result}\nОбъясни результат кратко на русском."}
                ]
                followup = ollama_chat(followup_msgs)
                final_response = followup
                break  # One command at a time for safety

    # If no EXEC found, just return the response
    if exec_results:
        output = "\n\n".join(exec_results) + f"\n\n💬 {final_response}"
    else:
        output = final_response

    history.append({"role": "assistant", "content": final_response})

    # Trim
    if len(history) > MAX_HISTORY * 2:
        conversations[user_id] = history[-MAX_HISTORY:]

    return output

def process_update(update):
    msg = update.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg.get("text", "")

    if user_id != ALLOWED_USER:
        send_message(chat_id, "⛔ Доступ запрещён")
        return

    if text == "/start":
        send_message(chat_id,
            "🤖 Geek Local Bot v2\n"
            "Модель: Gemma 9B (локально)\n\n"
            "Умею:\n"
            "• Отвечать на вопросы\n"
            "• Выполнять команды на Mac\n"
            "• Управлять мышкой/клавиатурой\n"
            "• Делать скриншоты\n"
            "• Открывать приложения\n\n"
            "Просто попроси — сделаю.")
        return

    if text == "/clear":
        conversations.pop(user_id, None)
        send_message(chat_id, "🗑️ История очищена")
        return

    if text == "/status":
        try:
            with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
                models = json.loads(r.read())
                model_list = "\n".join(f"  • {m['name']}" for m in models.get("models", []))
            send_message(chat_id, f"✅ Ollada работает\nМодели:\n{model_list}")
        except:
            send_message(chat_id, "❌ Ollama не отвечает")
        return

    if not text:
        return

    send_message(chat_id, "⏳ Думаю...")

    try:
        output = process_message(text, user_id)
        send_message(chat_id, output)
        log.info(f"OK: {text[:50]}...")
    except Exception as e:
        log.error(f"Error: {e}")
        send_message(chat_id, f"❌ Ошибка: {str(e)[:200]}")

def main():
    log.info("Starting Geek Local Bot v2 (Gemma 9B + exec)...")

    try:
        api("deleteWebhook")
    except:
        pass

    last_update_id = 0

    while True:
        try:
            result = api("getUpdates", {
                "offset": last_update_id + 1,
                "timeout": 30,
                "allowed_updates": ["message"]
            })

            for update in result.get("result", []):
                last_update_id = update["update_id"]
                process_update(update)

        except urllib.error.URLError:
            log.error("Network error, retrying...")
            time.sleep(5)
        except Exception as e:
            log.error(f"Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
