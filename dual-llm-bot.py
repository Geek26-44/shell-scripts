#!/usr/bin/env python3
"""
Dual LLM Telegram Bot — две модели + эвристика выбора лучшего ответа.
Полностью независим от OpenClaw.

Usage: python3 dual-llm-bot.py <bot_token>

Ответы:
  1️⃣ qwen3.5:9b
  2️⃣ gemma4:e4b
  🏆 Эвристика: лучший ответ + почему
"""

import sys, json, requests, time, os, subprocess, threading, re
from concurrent.futures import ThreadPoolExecutor, as_completed

# === CONFIG ===
TOKEN = sys.argv[1] if len(sys.argv) > 1 else None
if not TOKEN:
    print("Usage: python3 dual-llm-bot.py <bot_token>")
    sys.exit(1)

ALLOWED_USER = 170285780
OLLAMA_URL = "http://localhost:11434/api/generate"
SHELL_SCRIPTS = "/Users/geek2026/github/shell-scripts"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"

MODELS = {
    "qwen3.5:9b": {"emoji": "🟣", "short": "Qwen 3.5 9B", "ctx": 4096, "timeout": 300},
    "gemma4:e4b": {"emoji": "🔵", "short": "Gemma 4 E4B", "ctx": 4096, "timeout": 300},
}

OFFSET = 0

def tg(method, **kwargs):
    url = TELEGRAM_URL.format(token=TOKEN, method=method)
    r = requests.post(url, json=kwargs, timeout=30)
    return r.json()

def ollama_single(model, prompt, ctx=4096, timeout=300, retries=3):
    """Query one model with retry logic. Returns (model_name, response, speed_info)."""
    for attempt in range(retries):
        try:
            # Unload previous model to free RAM
            try:
                requests.post(OLLAMA_URL, json={"model": model, "keep_alive": "0s"}, timeout=5)
            except:
                pass
            time.sleep(1)
            
            r = requests.post(OLLAMA_URL, json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": ctx}
            }, timeout=timeout)
            if r.ok:
                data = r.json()
                resp = data.get("response", "").strip()
                if resp:
                    ec = data.get("eval_count", 0)
                    el = data.get("eval_duration", 0)
                    speed = f"{ec/(el/1e9):.1f} tok/s" if el > 0 else "? tok/s"
                    return (model, resp, speed)
                # Empty response = model loading, retry
                print(f"  {model}: empty response (attempt {attempt+1}), retrying...")
                sys.stdout.flush()
                time.sleep(10)
                continue
            return (model, f"⚠️ Ollama error: {r.status_code}", "error")
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            print(f"  {model}: connection error (attempt {attempt+1}): {e}")
            sys.stdout.flush()
            time.sleep(15)
        except requests.exceptions.Timeout:
            return (model, "⏱️ Таймаут", "timeout")
        except Exception as e:
            print(f"  {model}: error (attempt {attempt+1}): {e}")
            sys.stdout.flush()
            time.sleep(10)
    return (model, f"⚠️ Не удалось получить ответ после {retries} попыток", "error")

def query_both_models(prompt):
    """Query models SEQUENTIALLY — 16GB RAM can't fit both at once."""
    results = {}
    for model, cfg in MODELS.items():
        model_name, resp, speed = ollama_single(model, prompt, cfg["ctx"], cfg["timeout"])
        results[model_name] = (resp, speed)
    return results

def heuristic_score(question, answer):
    """
    Score an answer 0-100 based on heuristic criteria.
    Higher = better.
    """
    if not answer or answer.startswith("⚠️") or answer.startswith("⏱️"):
        return 0
    
    score = 50  # baseline
    
    # Length: too short is bad (<50 chars), too long is slightly penalized
    length = len(answer)
    if length < 30:
        score -= 30
    elif length < 100:
        score -= 10
    elif 200 <= length <= 2000:
        score += 10
    elif length > 3000:
        score -= 5  # slightly penalize rambling
    
    # Structure bonuses
    if "```" in answer or "\n    " in answer:
        score += 5  # has code examples
    if re.search(r'\d+\.', answer):
        score += 5  # has numbered list
    if re.search(r'[-•]\s', answer):
        score += 3  # has bullet points
    if "**" in answer or "__" in answer:
        score += 3  # has bold emphasis
    
    # Relevance: check if key words from question appear in answer
    q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
    a_words = set(re.findall(r'\b\w{4,}\b', answer.lower()))
    overlap = len(q_words & a_words)
    if overlap > 0:
        score += min(overlap * 3, 15)
    
    # Russian text bonus (if question is in Russian)
    if re.search(r'[а-яА-Я]', question):
        if re.search(r'[а-яА-Я]', answer):
            score += 10
        else:
            score -= 15  # answered in wrong language
    
    # Confidence markers
    confidence_phrases = ["например", "example", "в частности", "specifically", 
                          "потому что", "because", "следовательно", "therefore"]
    for phrase in confidence_phrases:
        if phrase in answer.lower():
            score += 2
    
    # Hedge phrases (uncertainty) — slight penalty
    hedge_phrases = ["не уверен", "not sure", "возможно", "maybe", "я думаю"]
    for phrase in hedge_phrases:
        if phrase in answer.lower():
            score -= 2
    
    return max(0, min(100, score))

def pick_best(question, results):
    """
    Pick the best response using heuristic scoring.
    Returns (best_model, best_response, details).
    """
    scores = {}
    details_lines = []
    
    for model, (response, speed) in results.items():
        score = heuristic_score(question, response)
        cfg = MODELS[model]
        scores[model] = score
        details_lines.append(f"{cfg['emoji']} {cfg['short']}: {score}/100 ({speed})")
    
    best_model = max(scores, key=scores.get)
    best_response = results[best_model][0]
    
    # If scores are equal (within 5 pts), prefer qwen3.5 (smarter model)
    sorted_models = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_models) >= 2 and sorted_models[0][1] - sorted_models[1][1] < 5:
        if "qwen3.5" in scores:
            best_model = "qwen3.5:9b"
            best_response = results[best_model][0]
    
    details = "\n".join(details_lines)
    return best_model, best_response, details

def send_long(chat_id, text, prefix=""):
    """Send message, splitting if >4096 chars."""
    full = f"{prefix}{text}" if prefix else text
    if len(full) > 4096:
        for i in range(0, len(full), 4096):
            tg("sendMessage", chat_id=chat_id, text=full[i:i+4096])
    else:
        tg("sendMessage", chat_id=chat_id, text=full)

def process_media(msg, chat_id):
    """Handle voice/audio/photo. Returns transcription/OCR text or None."""
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
            os.remove(local_audio)
            if transcription:
                return transcription
            return None
        except Exception as e:
            tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка аудио: {e}")
            return None
    
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
            os.remove(local_img)
            if ocr_text:
                return f"[На изображении]: {ocr_text}"
            return None
        except Exception as e:
            tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка: {e}")
            return None
    
    return None

print("🤖 Dual LLM Bot started")
print(f"   Models: {', '.join(MODELS.keys())}")
print(f"   Mode: dual + heuristic")
sys.stdout.flush()

while True:
    try:
        updates = tg("getUpdates", offset=OFFSET, timeout=30)
        for update in updates.get("result", []):
            OFFSET = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "")
            sender = msg.get("from", {}).get("id", 0)
            
            # Auth check
            if sender != ALLOWED_USER:
                continue
            
            if text == "/start" or text == "/help":
                tg("sendMessage", chat_id=chat_id, text=(
                    "🤖 Dual LLM Bot\n"
                    "Две модели отвечают параллельно, затем эвристика выбирает лучший ответ.\n\n"
                    f"Модели: {', '.join(MODELS.keys())}\n"
                    "Фото → OCR, Голос → транскрипция\n"
                    "/mode — переключить режим (dual/single)"
                ))
                continue
            
            if text == "/mode":
                tg("sendMessage", chat_id=chat_id, text="Режим: dual (обе модели + эвристика)")
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
            
            # === DUAL MODE: query both models ===
            tg("sendChatAction", chat_id=chat_id, action="typing")
            
            # Send both in parallel
            results = query_both_models(prompt)
            
            # Send each model's response as separate message
            for model, cfg in MODELS.items():
                if model in results:
                    response, speed = results[model]
                    header = f"{cfg['emoji']} {cfg['short']} ({speed}):\n\n"
                    send_long(chat_id, response, prefix=header)
            
            # Heuristic: pick best
            best_model, best_response, details = pick_best(prompt, results)
            best_cfg = MODELS[best_model]
            
            verdict = (
                f"🏆 Эвристика: {best_cfg['short']}\n\n"
                f"📊 Оценки:\n{details}\n\n"
                f"{'─' * 30}\n\n"
                f"{best_response}"
            )
            send_long(chat_id, verdict)
                
    except KeyboardInterrupt:
        print("\nStopped.")
        break
    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(5)
