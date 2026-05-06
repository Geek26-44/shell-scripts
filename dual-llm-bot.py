#!/usr/bin/env python3
"""
Dual LLM Telegram Bot — две модели + эвристика выбора лучшего ответа.
Полностью автономный бот. Независим от любых внешних систем.

Usage: python3 dual-llm-bot.py
  Token читается из .bot-token в той же директории.
"""

import sys, json, requests, time, os, subprocess, re, logging
from logging.handlers import RotatingFileHandler
from collections import deque

# === PATHS ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, ".bot-token")
LOG_FILE = os.path.join(SCRIPT_DIR, "logs", "dual-llm-bot.log")

# === TOKEN ===
try:
    with open(TOKEN_FILE) as f:
        TOKEN = f.read().strip()
except FileNotFoundError:
    print(f"Token file not found: {TOKEN_FILE}")
    sys.exit(1)

# === CONFIG ===
ALLOWED_USER = 170285780
OLLAMA_CHAT = "http://localhost:11434/api/chat"
OLLAMA_GEN = "http://localhost:11434/api/generate"
SHELL_SCRIPTS = SCRIPT_DIR
TELEGRAM_URL = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"

SYSTEM_PROMPT = "Ты — полезный AI-ассистент. Отвечай чётко, по делу, на языке вопроса. Кратко но полно."

MODELS = {
    "qwen3.5:9b": {"emoji": "🟣", "short": "Qwen 3.5 9B", "ctx": 4096, "timeout": 300},
    "gemma4:e4b": {"emoji": "🔵", "short": "Gemma 4 E4B", "ctx": 4096, "timeout": 300},
}

# === CONTEXT ===
CONTEXT_SIZE = 10  # последних сообщений в контексте
chat_history = deque(maxlen=CONTEXT_SIZE)

# === LOGGING ===
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log = logging.getLogger("dual-bot")
log.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3)
handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
log.addHandler(handler)
# Also to stdout
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
log.addHandler(sh)

# === HELPERS ===
def tg(method, **kwargs):
    url = TELEGRAM_URL.format(token=TOKEN, method=method)
    r = requests.post(url, json=kwargs, timeout=30)
    return r.json()

def unload_model(model):
    try:
        requests.post(OLLAMA_GEN, json={"model": model, "keep_alive": "0s", "stream": False}, timeout=10)
    except:
        pass

def check_ollama():
    """Quick healthcheck — is Ollama alive?"""
    try:
        r = requests.get("http://localhost:11434/api/ps", timeout=5)
        return r.ok
    except:
        return False

def ollama_chat(model, messages, ctx=4096, timeout=300, retries=3):
    """Query model via chat API. Returns (model, response, speed_info)."""
    for attempt in range(retries):
        try:
            r = requests.post(OLLAMA_CHAT, json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_ctx": ctx},
                "think": False
            }, timeout=timeout)
            if r.ok:
                data = r.json()
                msg = data.get("message", {}).get("content", "").strip()
                if msg:
                    ec = data.get("eval_count", 0)
                    el = data.get("eval_duration", 0)
                    speed = f"{ec/(el/1e9):.1f} tok/s" if el > 0 else "? tok/s"
                    return (model, msg, speed)
                log.info(f"  {model}: empty (attempt {attempt+1}), retrying...")
                time.sleep(8)
                continue
            return (model, f"⚠️ Ollama error: {r.status_code}", "error")
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
            log.info(f"  {model}: connection error (attempt {attempt+1})")
            time.sleep(12)
        except requests.exceptions.Timeout:
            return (model, "⏱️ Таймаут", "timeout")
        except Exception as e:
            log.info(f"  {model}: error (attempt {attempt+1}): {e}")
            time.sleep(8)
    return (model, f"⚠️ Не удалось получить ответ после {retries} попыток", "error")

def query_both_models(prompt):
    """Query models SEQUENTIALLY — 16GB RAM can't fit both."""
    results = {}
    model_list = list(MODELS.items())

    # Build messages with context
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in chat_history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    for i, (model, cfg) in enumerate(model_list):
        log.info(f"  Querying {model}...")
        model_name, resp, speed = ollama_chat(model, messages, cfg["ctx"], cfg["timeout"])
        results[model_name] = (resp, speed)
        log.info(f"  {model}: {speed}, {len(resp)} chars")
        if i < len(model_list) - 1:
            unload_model(model)
            time.sleep(2)
    return results

def heuristic_score(question, answer):
    """Score 0-100. Higher = better."""
    if not answer or answer.startswith("⚠️") or answer.startswith("⏱️"):
        return 0

    score = 50

    length = len(answer)
    if length < 30: score -= 30
    elif length < 100: score -= 10
    elif 200 <= length <= 2000: score += 10
    elif length > 3000: score -= 5

    if "```" in answer or "\n    " in answer: score += 5
    if re.search(r'\d+\.', answer): score += 5
    if re.search(r'[-•]\s', answer): score += 3
    if "**" in answer or "__" in answer: score += 3

    q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
    a_words = set(re.findall(r'\b\w{4,}\b', answer.lower()))
    overlap = len(q_words & a_words)
    if overlap > 0: score += min(overlap * 3, 15)

    if re.search(r'[а-яА-Я]', question):
        if re.search(r'[а-яА-Я]', answer): score += 10
        else: score -= 15

    for p in ["например", "потому что", "because", "следовательно"]:
        if p in answer.lower(): score += 2
    for p in ["не уверен", "возможно", "maybe"]:
        if p in answer.lower(): score -= 2

    return max(0, min(100, score))

def pick_best(question, results):
    scores = {}
    details = []
    for model, (response, speed) in results.items():
        s = heuristic_score(question, response)
        scores[model] = s
        cfg = MODELS[model]
        details.append(f"{cfg['emoji']} {cfg['short']}: {s}/100 ({speed})")

    best_model = max(scores, key=scores.get)
    sorted_m = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_m) >= 2 and sorted_m[0][1] - sorted_m[1][1] < 5:
        if "qwen3.5" in scores:
            best_model = "qwen3.5:9b"

    return best_model, results[best_model][0], "\n".join(details)

def send_long(chat_id, text):
    """Send, splitting at 4096 chars."""
    for i in range(0, len(text), 4096):
        tg("sendMessage", chat_id=chat_id, text=text[i:i+4096])

def process_media(msg, chat_id):
    """Handle voice/photo. Returns text or None."""
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        try:
            file_info = tg("getFile", file_id=voice["file_id"])
            dl_url = TELEGRAM_FILE_URL.format(token=TOKEN, path=file_info["result"]["file_path"])
            local = f"/tmp/voice_{int(time.time())}.ogg"
            with open(local, "wb") as f:
                f.write(requests.get(dl_url, timeout=30).content)
            tg("sendChatAction", chat_id=chat_id, action="typing")
            result = subprocess.run([f"{SHELL_SCRIPTS}/transcribe.sh", local],
                                    capture_output=True, text=True, timeout=120)
            os.remove(local)
            return result.stdout.strip() or None
        except Exception as e:
            tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка аудио: {e}")
            return None

    photos = msg.get("photo")
    if photos:
        try:
            file_info = tg("getFile", file_id=photos[-1]["file_id"])
            dl_url = TELEGRAM_FILE_URL.format(token=TOKEN, path=file_info["result"]["file_path"])
            local = f"/tmp/photo_{int(time.time())}.jpg"
            with open(local, "wb") as f:
                f.write(requests.get(dl_url, timeout=30).content)
            tg("sendChatAction", chat_id=chat_id, action="typing")
            result = subprocess.run([f"{SHELL_SCRIPTS}/ocr.sh", local],
                                    capture_output=True, text=True, timeout=180)
            os.remove(local)
            ocr = result.stdout.strip()
            return f"[На изображении]: {ocr}" if ocr else None
        except Exception as e:
            tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка: {e}")
            return None
    return None

# === MAIN ===
OFFSET = 0
log.info("🤖 Dual LLM Bot started")
log.info(f"   Models: {', '.join(MODELS.keys())}")
log.info(f"   API: chat (think=false) | Context: {CONTEXT_SIZE} messages")
log.info(f"   Mode: compact (best answer + scores)")

while True:
    try:
        updates = tg("getUpdates", offset=OFFSET, timeout=30)
        for update in updates.get("result", []):
            OFFSET = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            sender = msg.get("from", {}).get("id", 0)

            if sender != ALLOWED_USER:
                continue

            # Commands
            if text == "/start" or text == "/help":
                tg("sendMessage", chat_id=chat_id, text=(
                    "🤖 Dual LLM Bot\n"
                    "Две модели отвечают, эвристика выбирает лучший.\n\n"
                    f"Модели: {', '.join(MODELS.keys())}\n"
                    "Фото → OCR | Голос → транскрипция\n"
                    "/clear — очистить контекст\n"
                    "/verbose — показать оба ответа"
                ))
                continue

            if text == "/clear":
                chat_history.clear()
                tg("sendMessage", chat_id=chat_id, text="🗑 Контекст очищен")
                continue

            if text == "/verbose":
                tg("sendMessage", chat_id=chat_id, text=(
                    "Режим: compact (только лучший ответ)\n"
                    "Скоро будет переключатель 🔄"
                ))
                continue

            if text.startswith("/"):
                continue

            # Build prompt
            media_text = process_media(msg, chat_id)
            if media_text and not text:
                prompt = media_text
            elif media_text:
                prompt = f"{media_text}\n\n{text}"
            else:
                prompt = text

            if not prompt:
                continue

            # Healthcheck
            if not check_ollama():
                tg("sendMessage", chat_id=chat_id, text="⚠️ Ollama не отвечает. Подожди минуту.")
                continue

            log.info(f"Q: {prompt[:80]}")
            tg("sendChatAction", chat_id=chat_id, action="typing")

            results = query_both_models(prompt)
            best_model, best_response, details = pick_best(prompt, results)
            best_cfg = MODELS[best_model]

            # Save to context
            chat_history.append(("user", prompt))
            chat_history.append(("assistant", best_response))

            # Compact format: best answer + scores
            reply = f"🏆 {best_cfg['short']}\n{details}\n{'─'*30}\n\n{best_response}"
            send_long(chat_id, reply)

    except KeyboardInterrupt:
        log.info("Stopped.")
        break
    except Exception as e:
        log.error(f"Loop error: {e}")
        time.sleep(5)
