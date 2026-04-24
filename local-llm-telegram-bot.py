#!/usr/bin/env python3
"""
Local LLM Telegram Bot — direct Ollama → Telegram, no OpenClaw overhead.
Usage: python3 local-llm-telegram-bot.py <model> <bot_token>
Example: python3 local-llm-telegram-bot.py qwen2.5:14b 123456:ABC-DEF
"""

import sys, json, requests, time, os, subprocess

OLLAMA_URL = "http://localhost:11434/api/generate"
SHELL_SCRIPTS = "/Users/geek2026/github/shell-scripts"
SHELL_SCRIPTS = "/Users/geek2026/github/shell-scripts"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:14b"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else None

if not TOKEN:
    print("Usage: python3 local-llm-telegram-bot.py <model> <bot_token>")
    sys.exit(1)

OFFSET = 0
MODEL_SHORT = MODEL.split(":")[0].capitalize()

def tg(method, **kwargs):
    url = TELEGRAM_URL.format(token=TOKEN, method=method)
    r = requests.post(url, json=kwargs, timeout=30)
    return r.json()

def ollama(prompt, timeout=120):
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": 4096}
        }, timeout=timeout)
        if r.ok:
            return r.json().get("response", "⚠️ Empty response").strip()
        return f"⚠️ Ollama error: {r.status_code}"
    except requests.exceptions.Timeout:
        return "⏱️ Таймаут — модель не успела ответить (120с)"
    except Exception as e:
        return f"⚠️ Error: {e}"

def get_name(msg):
    """Extract sender name from message."""
    f = msg.get("from", {})
    return f.get("first_name", f.get("username", "User"))

print(f"🤖 {MODEL_SHORT} bot started (model: {MODEL})")
sys.stdout.flush()

while True:
    try:
        updates = tg("getUpdates", offset=OFFSET, timeout=30)
        for update in updates.get("result", []):
            OFFSET = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            
            if text == "/start" or text == "/help":
                tg("sendMessage", chat_id=chat_id, text=f"🤖 {MODEL_SHORT} (local)\nПиши — отвечу.\nФото → распознаю текст.\nГолос → расшифрую.")
                continue
            if text.startswith("/"):
                continue
            
            # === Handle voice/audio ===
            voice = msg.get("voice") or msg.get("audio")
            if voice:
                file_id = voice.get("file_id")
                try:
                    file_info = tg("getFile", file_id=file_id)
                    file_path = file_info["result"]["file_path"]
                    dl_url = TELEGRAM_FILE_URL.format(token=TOKEN, path=file_path)
                    local_audio = f"/tmp/voice_{int(time.time())}.ogg"
                    r = requests.get(dl_url, timeout=30)
                    with open(local_audio, "wb") as f:
                        f.write(r.content)
                    tg("sendChatAction", chat_id=chat_id, action="typing")
                    result = subprocess.run(
                        [f"{SHELL_SCRIPTS}/transcribe.sh", local_audio],
                        capture_output=True, text=True, timeout=120
                    )
                    transcription = result.stdout.strip()
                    if transcription:
                        tg("sendMessage", chat_id=chat_id, text=f"📝 Расшифровка:\n{transcription[:4000]}")
                    else:
                        tg("sendMessage", chat_id=chat_id, text="⚠️ Не удалось распознать")
                    os.remove(local_audio)
                except Exception as e:
                    tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка аудио: {e}")
                continue
            
            # === Handle photo ===
            photos = msg.get("photo")
            if photos:
                file_id = photos[-1]["file_id"]
                try:
                    file_info = tg("getFile", file_id=file_id)
                    file_path = file_info["result"]["file_path"]
                    dl_url = TELEGRAM_FILE_URL.format(token=TOKEN, path=file_path)
                    local_img = f"/tmp/photo_{int(time.time())}.jpg"
                    r = requests.get(dl_url, timeout=30)
                    with open(local_img, "wb") as f:
                        f.write(r.content)
                    tg("sendChatAction", chat_id=chat_id, action="typing")
                    result = subprocess.run(
                        [f"{SHELL_SCRIPTS}/ocr.sh", local_img],
                        capture_output=True, text=True, timeout=180
                    )
                    ocr_text = result.stdout.strip()
                    if ocr_text:
                        tg("sendMessage", chat_id=chat_id, text=f"📄 Текст:\n{ocr_text[:4000]}")
                    else:
                        tg("sendMessage", chat_id=chat_id, text="⚠️ Не удалось распознать")
                    os.remove(local_img)
                except Exception as e:
                    tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка: {e}")
                continue
            
            # === Text message ===
            if not text:
                continue
            
            # Typing indicator
            tg("sendChatAction", chat_id=chat_id, action="typing")
            
            # Generate response
            name = get_name(msg)
            response = ollama(f"{name}: {text}")
            
            # Send (split if too long)
            if len(response) > 4096:
                for i in range(0, len(response), 4096):
                    tg("sendMessage", chat_id=chat_id, text=response[i:i+4096])
            else:
                tg("sendMessage", chat_id=chat_id, text=response)
                
    except KeyboardInterrupt:
        print("\nStopped.")
        break
    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(5)
