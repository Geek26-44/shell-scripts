#!/usr/bin/env python3
"""Geek26 Bot v3 — Config. Все настройки в одном месте."""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass, field

# === PATHS ===
SCRIPT_DIR = Path(__file__).resolve().parent
SHELL_SCRIPTS = SCRIPT_DIR.parent
TOKEN_FILE = SHELL_SCRIPTS / ".bot-token"
LOG_DIR = SHELL_SCRIPTS / "logs"
DB_FILE = SCRIPT_DIR / "geek26.db"

HOME = Path.home()
OBSIDIAN_VAULT = HOME / "Documents" / "Obsidian-Vault"
GITHUB_DIR = HOME / "github"
DOWNLOADS = HOME / "Downloads"

# === TOKEN ===
try:
    with open(TOKEN_FILE) as f:
        BOT_TOKEN = f.read().strip()
except FileNotFoundError:
    print(f"Token file not found: {TOKEN_FILE}")
    sys.exit(1)

# === NETWORK ===
ALLOWED_USER = 170285780
TELEGRAM_URL = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"
OLLAMA_CHAT = "http://localhost:11434/api/chat"
OLLAMA_GEN = "http://localhost:11434/api/generate"
POLL_TIMEOUT = 30       # Telegram long polling
REQUEST_TIMEOUT = 60    # Must be > POLL_TIMEOUT

# === MODELS ===
MODELS = {
    "qwen3.5:9b": {"emoji": "🟣", "short": "Qwen 3.5 9B", "ctx": 4096, "timeout": 120},
    "gemma4:e4b": {"emoji": "🔵", "short": "Gemma 4 E4B", "ctx": 4096, "timeout": 120},
}

# === CONTEXT ===
CONTEXT_SIZE = 20           # сообщений в памяти
CONTEXT_LOAD_ON_START = 20  # загрузить из SQLite при старте
MAX_COMMANDS_PER_MIN = 10   # защита от спама

# === RETRY ===
LLM_RETRIES = 3
LLM_BACKOFF = [2, 5, 10]   # секунды между попытками

# === WATCHDOG ===
WATCHDOG_INTERVAL = 60      # каждые N итераций
MAX_CONSECUTIVE_ERRORS = 10 # после → self-restart
DISK_WARNING_PCT = 95

# === EXECUTOR TIMEOUTS ===
CMD_TIMEOUT_FAST = 10    # open, clipboard
CMD_TIMEOUT_SEARCH = 30  # obsidian, git, graphify
CMD_TIMEOUT_DOWNLOAD = 120

# === SYSTEM PROMPT ===
SYSTEM_PROMPT = """Ты — Geek26, цифровой помощник Димы (36 лет, из Костромы, живёт в EST).

## Личность
- Отвечай прямо, без воды. Никаких "Отличный вопрос!" или пустых вступлений
- Юмор уместен, если к месту
- Языки: русский/английский (отвечай на языке вопроса)
- Стиль: эффективный, лаконичный, по делу
- Если не уверен что понял команду — переспрашивай
- Если команда не из твоего списка — говорю что не умею, предлагаю альтернативу
- Никогда не придумываю команды которых нет

## Возможности
Я умею выполнять команды на твоём Mac. Когда ты просишь что-то сделать, я:
1. Понимаю намерение
2. Выполняю команду
3. Показываю результат

### Команды которые я выполняю:

**Работа с изображениями:**
- Если присылаешь фото → делаю OCR и анализирую текст

**Управление Mac:**
- "открой [url]" → открываю в браузере
- "обнови страницу" → отправляю Cmd+R
- "скачай [url]" → скачиваю в ~/Downloads
- "скопируй в буфер [текст]" → копирую текст

**Obsidian (заметки):**
- "запиши в обсидиан [текст]" → создаю заметку
- "найди в заметках [запрос]" → ищу по vault
- "прочитай заметку [название]" → показываю содержимое

**GitHub:**
- "покажи коммиты [репо]" → git log
- "статус [репо]" → git status
- "открой репо [название]" → открываю на GitHub

**Graphify (граф знаний):**
- "найди в графе [запрос]" → поиск по графу
- "как связаны [A] и [B]" → путь между узлами

**Системные:**
- "проверь сервисы" → статус Ollama, Dashboard, API
- "перезапусти [сервис]" → рестарт (с подтверждением)

**Сложные задачи:**
- Если задача сложная (анализ, ресёрч, стратегия) → скажу что нужна эскалация к Geek

## Формат ответов
Команда:
```
Понял: [что делаю]
Результат: [вывод]
```
Ошибка:
```
Не получилось: [что случилось]
Попробуй: [альтернатива]
```

## Безопасность
- Команды только для user_id=170285780
- rm → trash
- sudo → спрашиваю подтверждение
- Внешние действия → спрашиваю подтверждение"""


@dataclass
class BotSettings:
    """Runtime settings, loaded once at startup."""
    token: str = BOT_TOKEN
    allowed_user: int = ALLOWED_USER
    obsidian_vault: Path = OBSIDIAN_VAULT
    github_dir: Path = GITHUB_DIR
    downloads: Path = DOWNLOADS
    db_file: Path = DB_FILE
    log_dir: Path = LOG_DIR


def setup_logging(name: str = "geek26") -> logging.Logger:
    """Configure rotating file + stdout logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(LOG_DIR / "geek26-bot.log", maxBytes=2_000_000, backupCount=3)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)

    return log
