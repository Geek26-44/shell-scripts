#!/usr/bin/env python3
"""
Dual LLM Telegram Bot — две модели + эвристика выбора лучшего ответа.
Полностью автономный бот. Независим от любых внешних систем.

Usage: python3 dual-llm-bot.py
  Token читается из .bot-token в той же директории.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

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

SYSTEM_PROMPT = """Ты — Geek26, цифровой помощник Димы (36 лет, из Костромы, живёт в EST).

## Личность
- Отвечай прямо, без воды. Никаких "Отличный вопрос!" или пустых вступлений
- Юмор уместен, если к месту
- Языки: русский/английский (отвечай на языке вопроса)
- Стиль: эффективный, лаконичный, по делу

## Возможности
Я умею выполнять команды на твоём Mac. Когда ты просишь что-то сделать, я:
1. Понимаю намерение
2. Выполняю команду
3. Показываю результат

### Команды которые я выполняю:

**Работа с изображениями:**
- Если присылаешь фото → делаю OCR и анализирую текст
- "что на картинке" → описываю содержимое

**Управление Mac:**
- "открой [url]" → открываю в браузере
- "обнови страницу" → отправляю Cmd+R активному окну
- "скачай [url]" → скачиваю файл в ~/Downloads
- "скопируй в буфер [текст]" → копирую текст

**Obsidian (твои заметки):**
- "запиши в обсидиан: [текст]" → создаю заметку
- "найди в заметках [запрос]" → ищу по vault
- "прочитай заметку [название]" → показываю содержимое

**GitHub:**
- "покажи последние коммиты [репо]" → git log
- "статус [репо]" → git status
- "открой репо [название]" → открываю на GitHub

**Graphify (граф знаний):**
- "найди в графе [запрос]" → поиск по графу
- "как связаны [A] и [B]" → показываю путь между узлами

**Системные задачи:**
- "проверь сервисы" → статус localhost:8080, :3000, :11434
- "перезапусти [сервис]" → останавливаю и запускаю

**Эскалация к OpenClaw:**
- Если задача сложная (исследование, аналитика, многошаговые операции) → скажу что нужна эскалация к Geek (OpenClaw)

## Формат ответов
Когда выполняю команду:
```
Понял: [что буду делать]
Выполняю: [команда]
Результат: [вывод]
```

Если ошибка:
```
Ошибка: [что случилось]
Попробуй: [альтернатива]
```

## Безопасность
- Выполняю команды только для user_id=170285780
- Не выполняю sudo без подтверждения
- rm заменяю на trash
- Внешние действия (email, посты) → спрашиваю подтверждение"""

MODELS = {
    "qwen3.5:9b": {"emoji": "🟣", "short": "Qwen 3.5 9B", "ctx": 4096, "timeout": 300},
    "gemma4:e4b": {"emoji": "🔵", "short": "Gemma 4 E4B", "ctx": 4096, "timeout": 300},
}

# === CONTEXT ===
CONTEXT_SIZE = 10
chat_history = deque(maxlen=CONTEXT_SIZE)


class CommandType(Enum):
    OPEN_URL = "open_url"
    REFRESH_PAGE = "refresh_page"
    DOWNLOAD = "download"
    CLIPBOARD = "clipboard"
    OBSIDIAN_WRITE = "obsidian_write"
    OBSIDIAN_SEARCH = "obsidian_search"
    OBSIDIAN_READ = "obsidian_read"
    GIT_LOG = "git_log"
    GIT_STATUS = "git_status"
    OPEN_REPO = "open_repo"
    GRAPHIFY_QUERY = "graphify_query"
    GRAPHIFY_PATH = "graphify_path"
    CHECK_SERVICES = "check_services"
    RESTART_SERVICE = "restart_service"
    ESCALATE = "escalate"
    NONE = "none"


@dataclass
class ParsedCommand:
    type: CommandType
    params: Dict[str, Any]
    confidence: float
    raw_text: str
    shell_cmd: Optional[str] = None


class CommandParser:
    """LLM-assisted + regex command parser for 9B models."""

    def __init__(self):
        self.patterns = {
            CommandType.OPEN_URL: [
                (r"открой\s+(https?://[^\s]+)", {"url": 1}),
                (r"open\s+(https?://[^\s]+)", {"url": 1}),
                (r"перейди на\s+(https?://[^\s]+)", {"url": 1}),
                (r"go to\s+(https?://[^\s]+)", {"url": 1}),
            ],
            CommandType.REFRESH_PAGE: [
                (r"обнови\s+страницу", {}),
                (r"refresh\s+page", {}),
                (r"перезагрузи\s+страницу", {}),
                (r"reload\s+page", {}),
            ],
            CommandType.DOWNLOAD: [
                (r"скачай\s+(https?://[^\s]+)", {"url": 1}),
                (r"download\s+(https?://[^\s]+)", {"url": 1}),
                (r"загрузи\s+(https?://[^\s]+)", {"url": 1}),
            ],
            CommandType.CLIPBOARD: [
                (r"скопируй в буфер[:：]?\s*(.+)", {"text": 1}),
                (r"copy to clipboard[:：]?\s*(.+)", {"text": 1}),
                (r"в буфер[:：]?\s*(.+)", {"text": 1}),
            ],
            CommandType.OBSIDIAN_WRITE: [
                (r"запиши в обсидиан[:：]?\s*(.+)", {"text": 1}),
                (r"write to obsidian[:：]?\s*(.+)", {"text": 1}),
                (r"добавь в заметки[:：]?\s*(.+)", {"text": 1}),
                (r"создай заметку[:：]?\s*(.+)", {"text": 1}),
            ],
            CommandType.OBSIDIAN_SEARCH: [
                (r"найди в заметках\s+(.+)", {"query": 1}),
                (r"search notes for\s+(.+)", {"query": 1}),
                (r"поиск в обсидиане?\s+(.+)", {"query": 1}),
            ],
            CommandType.OBSIDIAN_READ: [
                (r"прочитай заметку\s+(.+)", {"name": 1}),
                (r"read note\s+(.+)", {"name": 1}),
                (r"покажи заметку\s+(.+)", {"name": 1}),
            ],
            CommandType.GIT_LOG: [
                (r"покажи\s+(?:последние\s+)?коммиты\s*(?:в\s+)?([^\s]+)?", {"repo": 1}),
                (r"git log\s*(?:for\s+)?([^\s]+)?", {"repo": 1}),
                (r"коммиты\s+([^\s]+)", {"repo": 1}),
            ],
            CommandType.OPEN_REPO: [
                (r"открой репо(?:зиторий)?\s+([^\s]+)", {"repo": 1}),
                (r"open repo(?:sitory)?\s+([^\s]+)", {"repo": 1}),
            ],
            CommandType.GRAPHIFY_QUERY: [
                (r"(?:найди|поиск)\s+в\s+графе\s+(.+)", {"query": 1}),
                (r"graphify query\s+(.+)", {"query": 1}),
                (r"граф[:：]\s*(.+)", {"query": 1}),
            ],
            CommandType.GRAPHIFY_PATH: [
                (r"(?:как\s+)?связаны?\s+(.+?)\s+и\s+(.+)", {"node1": 1, "node2": 2}),
                (r"путь между\s+(.+?)\s+и\s+(.+)", {"node1": 1, "node2": 2}),
                (r"связь\s+(.+?)\s+(?:и|с)\s+(.+)", {"node1": 1, "node2": 2}),
            ],
            CommandType.CHECK_SERVICES: [
                (r"проверь\s+сервисы", {}),
                (r"check\s+services", {}),
                (r"статус\s+сервисов", {}),
            ],
            CommandType.GIT_STATUS: [
                (r"статус\s+(?:проекта\s+)?([^\s]+)", {"repo": 1}),
                (r"git status\s*(?:for\s+)?([^\s]+)?", {"repo": 1}),
                (r"что изменилось в\s+([^\s]+)", {"repo": 1}),
            ],
            CommandType.RESTART_SERVICE: [
                (r"перезапусти\s+(.+)", {"service": 1}),
                (r"restart\s+(.+)", {"service": 1}),
                (r"рестарт\s+(.+)", {"service": 1}),
            ],
        }
        self.escalation_keywords = [
            "сложн",
            "анализ",
            "исследова",
            "разбер",
            "изуч",
            "complex",
            "analyze",
            "research",
            "investigate",
            "многошаг",
            "multi-step",
            "глубок",
            "deep",
            "план",
            "стратег",
            "архитектур",
        ]

    def parse(self, text: str, llm_hint: Optional[str] = None) -> ParsedCommand:
        text_lower = text.lower().strip()
        for cmd_type, patterns in self.patterns.items():
            for pattern, param_map in patterns:
                match = re.search(pattern, text_lower)
                if not match:
                    continue
                params = {}
                for param_name, group_idx in param_map.items():
                    if group_idx <= len(match.groups()):
                        value = match.group(group_idx)
                        if value:
                            params[param_name] = value.strip()
                return ParsedCommand(type=cmd_type, params=params, confidence=0.9, raw_text=text)

        if any(kw in text_lower for kw in self.escalation_keywords):
            return ParsedCommand(
                type=CommandType.ESCALATE,
                params={"task": text},
                confidence=0.7,
                raw_text=text,
            )

        if llm_hint:
            return self._parse_llm_hint(llm_hint, text)

        return ParsedCommand(type=CommandType.NONE, params={}, confidence=0.0, raw_text=text)

    def _parse_llm_hint(self, hint: str, original_text: str) -> ParsedCommand:
        hint_lower = hint.lower()
        if "open_url" in hint_lower or ("open" in hint_lower and "url" in hint_lower):
            url_match = re.search(r"https?://[^\s]+", original_text)
            if url_match:
                return ParsedCommand(
                    type=CommandType.OPEN_URL,
                    params={"url": url_match.group(0)},
                    confidence=0.6,
                    raw_text=original_text,
                )
        if "download" in hint_lower:
            url_match = re.search(r"https?://[^\s]+", original_text)
            if url_match:
                return ParsedCommand(
                    type=CommandType.DOWNLOAD,
                    params={"url": url_match.group(0)},
                    confidence=0.55,
                    raw_text=original_text,
                )
        if "refresh_page" in hint_lower or "refresh" in hint_lower:
            return ParsedCommand(
                type=CommandType.REFRESH_PAGE,
                params={},
                confidence=0.55,
                raw_text=original_text,
            )
        if "clipboard" in hint_lower:
            return ParsedCommand(
                type=CommandType.CLIPBOARD,
                params={"text": original_text},
                confidence=0.5,
                raw_text=original_text,
            )
        return ParsedCommand(type=CommandType.NONE, params={}, confidence=0.0, raw_text=original_text)


class CommandExecutor:
    """Execute parsed commands safely."""

    def __init__(self, allowed_user_id: int = ALLOWED_USER):
        self.allowed_user_id = allowed_user_id
        self.home = Path.home()
        self.obsidian_vault = self.home / "Documents" / "Obsidian-Vault"
        self.downloads = self.home / "Downloads"
        self.github = self.home / "github"
        self.shell_scripts = Path(SHELL_SCRIPTS)

    def execute(self, command: ParsedCommand, user_id: int) -> Tuple[bool, str]:
        if user_id != self.allowed_user_id:
            return False, "⛔ Unauthorized user"

        self._log_execution(command)
        handlers = {
            CommandType.OPEN_URL: self._handle_open_url,
            CommandType.REFRESH_PAGE: self._handle_refresh_page,
            CommandType.DOWNLOAD: self._handle_download,
            CommandType.CLIPBOARD: self._handle_clipboard,
            CommandType.OBSIDIAN_WRITE: self._handle_obsidian_write,
            CommandType.OBSIDIAN_SEARCH: self._handle_obsidian_search,
            CommandType.OBSIDIAN_READ: self._handle_obsidian_read,
            CommandType.GIT_LOG: self._handle_git_log,
            CommandType.GIT_STATUS: self._handle_git_status,
            CommandType.OPEN_REPO: self._handle_open_repo,
            CommandType.GRAPHIFY_QUERY: self._handle_graphify_query,
            CommandType.GRAPHIFY_PATH: self._handle_graphify_path,
            CommandType.CHECK_SERVICES: self._handle_check_services,
            CommandType.RESTART_SERVICE: self._handle_restart_service,
            CommandType.ESCALATE: self._handle_escalate,
        }
        handler = handlers.get(command.type)
        if not handler:
            return False, "❓ Команда не распознана"

        try:
            return handler(command.params)
        except subprocess.TimeoutExpired:
            return False, "⏱️ Команда превысила таймаут (120с)"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    def _log_execution(self, command: ParsedCommand):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "command_type": command.type.value,
            "params": command.params,
            "raw_text": command.raw_text,
        }
        log.info(f"[EXEC] {json.dumps(log_entry, ensure_ascii=False)}")

    def _run_shell(
        self,
        cmd: list[str],
        timeout: int = 120,
        input_text: Optional[str] = None,
    ) -> Tuple[bool, str]:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or "✅ Выполнено"
        return False, result.stderr.strip() or "❌ Команда завершилась с ошибкой"

    def _handle_open_url(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        url = params.get("url")
        if not url:
            return False, "❌ URL не указан"
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        success, output = self._run_shell(["open", url], timeout=10)
        return (True, f"✅ Открыл: {url}") if success else (False, output)

    def _handle_refresh_page(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        applescript = (
            'tell application "System Events"\n'
            '    keystroke "r" using {command down}\n'
            "end tell"
        )
        success, output = self._run_shell(["osascript", "-e", applescript], timeout=10)
        return (True, "✅ Отправил Cmd+R") if success else (False, output)

    def _handle_download(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        url = params.get("url")
        if not url:
            return False, "❌ URL не указан"
        filename = url.split("/")[-1] or "download"
        filepath = self.downloads / filename
        success, output = self._run_shell(["curl", "-L", "-o", str(filepath), url], timeout=300)
        if success and filepath.exists():
            size = filepath.stat().st_size
            return True, f"✅ Скачал: {filename} ({self._format_size(size)})"
        return False, output if output else "❌ Не удалось скачать файл"

    def _handle_clipboard(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        text = params.get("text", "")
        if not text:
            return False, "❌ Текст не указан"
        success, output = self._run_shell(["pbcopy"], timeout=10, input_text=text)
        if success:
            preview = text[:50] + "..." if len(text) > 50 else text
            return True, f"✅ Скопировано: {preview}"
        return False, output

    def _handle_obsidian_write(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        text = params.get("text", "")
        if not text:
            return False, "❌ Текст не указан"
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"geek26_{timestamp}.md"
        filepath = self.obsidian_vault / "Inbox" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        heading = text.split(".")[0] if "." in text else text[:50]
        content = (
            f"---\ncreated: {datetime.now().isoformat()}\nsource: geek26-bot\n---\n\n"
            f"# {heading}\n\n{text}\n"
        )
        filepath.write_text(content, encoding="utf-8")
        return True, f"✅ Создал заметку: {filename}"

    def _handle_obsidian_search(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        query = params.get("query", "")
        if not query:
            return False, "❌ Запрос не указан"
        success, output = self._run_shell(
            ["rg", "-i", "--max-count", "5", "--files-with-matches", query, str(self.obsidian_vault)],
            timeout=30,
        )
        if success and output:
            files = output.splitlines()[:5]
            results = []
            for found in files:
                rel_path = Path(found).relative_to(self.obsidian_vault)
                results.append(f"• {rel_path}")
            return True, f"🔍 Найдено по '{query}':\n" + "\n".join(results)
        return True, f"❌ Ничего не найдено по запросу: {query}"

    def _handle_obsidian_read(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        name = params.get("name", "")
        if not name:
            return False, "❌ Название заметки не указано"
        success, output = self._run_shell(
            ["find", str(self.obsidian_vault), "-name", f"*{name}*.md", "-type", "f", "-print", "-quit"],
            timeout=10,
        )
        if success and output:
            filepath = Path(output.strip())
            content = filepath.read_text(encoding="utf-8")
            if len(content) > 2000:
                content = content[:2000] + "\n\n... (обрезано)"
            return True, f"📝 {filepath.name}:\n\n{content}"
        return False, f"❌ Заметка '{name}' не найдена"

    def _handle_git_log(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        repo = params.get("repo") or "shell-scripts"
        repo_path = self.github / repo
        if not repo_path.exists():
            return False, f"❌ Репозиторий {repo} не найден"
        success, output = self._run_shell(
            ["git", "-C", str(repo_path), "log", "--oneline", "--graph", "-10"],
            timeout=10,
        )
        return (True, f"📋 Последние коммиты {repo}:\n```\n{output}\n```") if success else (False, output)

    def _handle_git_status(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        repo = params.get("repo") or "shell-scripts"
        repo_path = self.github / repo
        if not repo_path.exists():
            return False, f"❌ Репозиторий {repo} не найден"
        success, output = self._run_shell(
            ["git", "-C", str(repo_path), "status", "--short"],
            timeout=10,
        )
        if not success:
            return False, output
        if output:
            return True, f"📊 Статус {repo}:\n```\n{output}\n```"
        return True, f"✅ {repo}: чисто, нет изменений"

    def _handle_open_repo(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        repo = params.get("repo", "")
        if not repo:
            return False, "❌ Репозиторий не указан"
        if "/" not in repo:
            repo = f"geek2026/{repo}"
        return self._handle_open_url({"url": f"https://github.com/{repo}"})

    def _handle_graphify_query(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        query = params.get("query", "")
        if not query:
            return False, "❌ Запрос не указан"
        success, output = self._run_shell(["graphify", "query", query], timeout=30)
        return (True, f"🔮 Graphify результаты:\n{output}") if success else (False, output)

    def _handle_graphify_path(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        node1 = params.get("node1", "")
        node2 = params.get("node2", "")
        if not node1 or not node2:
            return False, "❌ Укажи оба узла"
        success, output = self._run_shell(["graphify", "path", node1, node2], timeout=30)
        return (True, f"🔗 Путь {node1} → {node2}:\n{output}") if success else (False, output)

    def _handle_check_services(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        services = [
            ("Ollama", "http://localhost:11434/api/ps"),
            ("Web App", "http://localhost:3000/health"),
            ("API", "http://localhost:8080/health"),
        ]
        results = []
        for name, url in services:
            try:
                response = requests.get(url, timeout=5)
                status = "✅" if response.ok else f"⚠️ {response.status_code}"
            except Exception:
                status = "❌ Не отвечает"
            results.append(f"{name}: {status}")
        return True, "🏥 Статус сервисов:\n" + "\n".join(results)

    def _handle_restart_service(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        service = params.get("service", "")
        if not service:
            return False, "❌ Сервис не указан"
        allowed_services = {
            "ollama": "brew services restart ollama",
            "postgres": "brew services restart postgresql",
            "redis": "brew services restart redis",
        }
        service_key = service.lower().strip()
        if service_key not in allowed_services:
            return False, f"❌ Сервис '{service}' не в whitelist"
        success, output = self._run_shell(allowed_services[service_key].split(), timeout=30)
        return (True, f"♻️ Перезапустил {service_key}") if success else (False, output)

    def _handle_escalate(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        task = params.get("task", "")
        success, _ = self._run_shell(
            ["openclaw", "system", "event", "--text", f"Escalated from Geek26: {task}", "--mode", "now"],
            timeout=10,
        )
        if success:
            return True, "🚀 Эскалировано к Geek (OpenClaw). Он займётся этой задачей."
        return False, "❌ Не удалось эскалировать к OpenClaw"

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"


class SafetyValidator:
    """Validate commands for safety before execution."""

    def __init__(self, allowed_user_id: int = ALLOWED_USER):
        self.allowed_user_id = allowed_user_id
        self.dangerous_patterns = [
            r"\brm\s+-rf",
            r"\bsudo\s+rm",
            r"\b>\s*/dev/s",
            r"\bdd\s+if=",
            r"\bmkfs\.",
            r":\(\)\{ :\|:& \};:",
        ]
        self.confirm_required = [
            "sudo",
            "reboot",
            "shutdown",
            "kill -9",
            "systemctl stop",
            "brew uninstall",
        ]
        self.safe_commands = {
            "ls",
            "pwd",
            "echo",
            "cat",
            "grep",
            "find",
            "head",
            "tail",
            "git",
            "curl",
            "open",
            "osascript",
            "pbcopy",
            "pbpaste",
            "rg",
            "fd",
            "graphify",
            "openclaw",
            "trash",
            "brew",
            "npm",
            "python3",
            "node",
        }

    def validate_command(self, command: ParsedCommand, user_id: int) -> Tuple[bool, Optional[str]]:
        if user_id != self.allowed_user_id:
            return False, "Unauthorized user"
        if command.type == CommandType.DOWNLOAD:
            url = command.params.get("url", "")
            if not self._validate_url(url):
                return False, "Suspicious URL"
        if command.shell_cmd:
            shell_cmd = command.shell_cmd
            for pattern in self.dangerous_patterns:
                if re.search(pattern, shell_cmd, re.IGNORECASE):
                    return False, f"Dangerous command pattern: {pattern}"
            for confirm_cmd in self.confirm_required:
                if confirm_cmd in shell_cmd.lower():
                    return False, f"Command requires confirmation: {confirm_cmd}"
        return True, None

    def _validate_url(self, url: str) -> bool:
        if not url or not url.startswith(("http://", "https://")):
            return False
        malicious_patterns = [r"bit\.ly", r"tinyurl", r"goo\.gl", r"ow\.ly"]
        return not any(re.search(pattern, url, re.IGNORECASE) for pattern in malicious_patterns)

    def needs_confirmation(self, command: ParsedCommand) -> bool:
        if command.type in [CommandType.RESTART_SERVICE]:
            return True
        if command.type == CommandType.OBSIDIAN_WRITE:
            text = command.params.get("text", "")
            if len(text) > 1000:
                return True
        return False


# === LOGGING ===
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
log = logging.getLogger("dual-bot")
log.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3)
handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
log.addHandler(handler)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
log.addHandler(sh)


def tg(method, **kwargs):
    url = TELEGRAM_URL.format(token=TOKEN, method=method)
    # Long polling: Telegram may hold connection up to `timeout` param in getUpdates
    # requests timeout must be LONGER than that to avoid race condition
    poll_timeout = kwargs.get('timeout', 0)
    conn_timeout = max(60, poll_timeout + 15)  # at least 60s, or poll+15
    response = requests.post(url, json=kwargs, timeout=conn_timeout)
    return response.json()


def unload_model(model):
    try:
        requests.post(OLLAMA_GEN, json={"model": model, "keep_alive": "0s", "stream": False}, timeout=10)
    except Exception:
        pass


def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/ps", timeout=5)
        return response.ok
    except Exception:
        return False


def ollama_chat(model, messages, ctx=4096, timeout=300, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post(
                OLLAMA_CHAT,
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_ctx": ctx},
                    "think": False,
                },
                timeout=timeout,
            )
            if response.ok:
                data = response.json()
                msg = data.get("message", {}).get("content", "").strip()
                if msg:
                    eval_count = data.get("eval_count", 0)
                    eval_duration = data.get("eval_duration", 0)
                    speed = f"{eval_count / (eval_duration / 1e9):.1f} tok/s" if eval_duration > 0 else "? tok/s"
                    return model, msg, speed
                log.info(f"  {model}: empty (attempt {attempt + 1}), retrying...")
                time.sleep(8)
                continue
            return model, f"⚠️ Ollama error: {response.status_code}", "error"
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
            log.info(f"  {model}: connection error (attempt {attempt + 1})")
            time.sleep(12)
        except requests.exceptions.Timeout:
            return model, "⏱️ Таймаут", "timeout"
        except Exception as e:
            log.info(f"  {model}: error (attempt {attempt + 1}): {e}")
            time.sleep(8)
    return model, f"⚠️ Не удалось получить ответ после {retries} попыток", "error"


def query_both_models(prompt):
    results = {}
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in chat_history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    for idx, (model, cfg) in enumerate(MODELS.items()):
        log.info(f"  Querying {model}...")
        model_name, resp, speed = ollama_chat(model, messages, cfg["ctx"], cfg["timeout"])
        results[model_name] = (resp, speed)
        log.info(f"  {model}: {speed}, {len(resp)} chars")
        if idx < len(MODELS) - 1:
            unload_model(model)
            time.sleep(2)
    return results


def heuristic_score(question, answer):
    if not answer or answer.startswith("⚠️") or answer.startswith("⏱️"):
        return 0

    score = 50
    length = len(answer)
    if length < 30:
        score -= 30
    elif length < 100:
        score -= 10
    elif 200 <= length <= 2000:
        score += 10
    elif length > 3000:
        score -= 5

    if "```" in answer or "\n    " in answer:
        score += 5
    if re.search(r"\d+\.", answer):
        score += 5
    if re.search(r"[-•]\s", answer):
        score += 3
    if "**" in answer or "__" in answer:
        score += 3

    q_words = set(re.findall(r"\b\w{4,}\b", question.lower()))
    a_words = set(re.findall(r"\b\w{4,}\b", answer.lower()))
    overlap = len(q_words & a_words)
    if overlap > 0:
        score += min(overlap * 3, 15)

    if re.search(r"[а-яА-Я]", question):
        if re.search(r"[а-яА-Я]", answer):
            score += 10
        else:
            score -= 15

    for marker in ["например", "потому что", "because", "следовательно"]:
        if marker in answer.lower():
            score += 2
    for marker in ["не уверен", "возможно", "maybe"]:
        if marker in answer.lower():
            score -= 2

    return max(0, min(100, score))


def pick_best(question, results):
    scores = {}
    details = []
    for model, (response, speed) in results.items():
        score = heuristic_score(question, response)
        scores[model] = score
        cfg = MODELS[model]
        details.append(f"{cfg['emoji']} {cfg['short']}: {score}/100 ({speed})")

    best_model = max(scores, key=scores.get)
    sorted_models = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if len(sorted_models) >= 2 and sorted_models[0][1] - sorted_models[1][1] < 5 and "qwen3.5:9b" in scores:
        best_model = "qwen3.5:9b"
    return best_model, results[best_model][0], "\n".join(details)


def send_long(chat_id, text):
    for i in range(0, len(text), 4096):
        tg("sendMessage", chat_id=chat_id, text=text[i : i + 4096])


def process_media(msg, chat_id):
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        try:
            file_info = tg("getFile", file_id=voice["file_id"])
            dl_url = TELEGRAM_FILE_URL.format(token=TOKEN, path=file_info["result"]["file_path"])
            local = f"/tmp/voice_{int(time.time())}.ogg"
            with open(local, "wb") as f:
                f.write(requests.get(dl_url, timeout=30).content)
            tg("sendChatAction", chat_id=chat_id, action="typing")
            result = subprocess.run(
                [f"{SHELL_SCRIPTS}/transcribe.sh", local],
                capture_output=True,
                text=True,
                timeout=120,
            )
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
            result = subprocess.run(
                [f"{SHELL_SCRIPTS}/ocr.sh", local],
                capture_output=True,
                text=True,
                timeout=180,
            )
            os.remove(local)
            ocr = result.stdout.strip()
            return f"[На изображении]: {ocr}" if ocr else None
        except Exception as e:
            tg("sendMessage", chat_id=chat_id, text=f"❌ Ошибка: {e}")
            return None
    return None


class Geek26Bot:
    def __init__(self):
        self.parser = CommandParser()
        self.executor = CommandExecutor()
        self.validator = SafetyValidator()
        self.pending_commands: Dict[int, ParsedCommand] = {}

    def process_message(self, text: str, user_id: int, chat_id: int) -> str:
        normalized = (text or "").strip()
        if chat_id in self.pending_commands and normalized.lower() in {"да", "yes", "/yes", "подтверждаю"}:
            command = self.pending_commands.pop(chat_id)
            return self._execute_and_format(command, user_id)
        if chat_id in self.pending_commands and normalized.lower() in {"нет", "no", "/no", "отмена", "cancel"}:
            self.pending_commands.pop(chat_id, None)
            return "Отменил."

        llm_hint = None
        command = self.parser.parse(normalized)
        if command.type == CommandType.NONE and normalized:
            llm_hint = self._get_llm_command_hint(normalized)
            command = self.parser.parse(normalized, llm_hint=llm_hint)

        if command.type != CommandType.NONE and command.confidence > 0.5:
            command.shell_cmd = self._describe_shell_command(command)
            is_safe, error = self.validator.validate_command(command, user_id)
            if not is_safe:
                return f"⛔ Безопасность: {error}"
            if self.validator.needs_confirmation(command):
                self.pending_commands[chat_id] = command
                return self._format_confirmation_request(command)
            return self._execute_and_format(command, user_id)

        return self._process_chat(normalized)

    def _get_llm_command_hint(self, text: str) -> Optional[str]:
        if not check_ollama():
            return None
        messages = [
            {
                "role": "system",
                "content": (
                    "Определи, похоже ли сообщение на одну из команд. "
                    "Ответь одним токеном из списка: "
                    "open_url, refresh_page, download, clipboard, obsidian_write, "
                    "obsidian_search, obsidian_read, git_log, git_status, open_repo, "
                    "graphify_query, graphify_path, check_services, restart_service, escalate, none."
                ),
            },
            {"role": "user", "content": text},
        ]
        model = "qwen3.5:9b" if "qwen3.5:9b" in MODELS else next(iter(MODELS))
        _, hint, _ = ollama_chat(model, messages, ctx=1024, timeout=45, retries=1)
        return hint.strip() if hint else None

    def _process_chat(self, text: str) -> str:
        if not text:
            return ""
        if not check_ollama():
            return "⚠️ Ollama не отвечает. Подожди минуту."
        log.info(f"Q: {text[:80]}")
        results = query_both_models(text)
        best_model, best_response, details = pick_best(text, results)
        best_cfg = MODELS[best_model]
        chat_history.append(("user", text))
        chat_history.append(("assistant", best_response))
        return f"🏆 {best_cfg['short']}\n{details}\n{'─' * 30}\n\n{best_response}"

    def _execute_and_format(self, command: ParsedCommand, user_id: int) -> str:
        understanding = self._format_understanding(command)
        execution = self._format_execution(command)
        success, result = self.executor.execute(command, user_id)
        if success:
            return f"Понял: {understanding}\nВыполняю: {execution}\nРезультат: {result}"
        return (
            f"Понял: {understanding}\n"
            f"Выполняю: {execution}\n"
            f"Ошибка: {result}\n"
            f"Попробуй: {self._suggest_alternative(command)}"
        )

    def _format_understanding(self, command: ParsedCommand) -> str:
        formats = {
            CommandType.OPEN_URL: "открываю {url}",
            CommandType.REFRESH_PAGE: "обновляю активную страницу",
            CommandType.DOWNLOAD: "скачиваю {url}",
            CommandType.CLIPBOARD: "копирую текст в буфер",
            CommandType.OBSIDIAN_WRITE: "записываю в Obsidian",
            CommandType.OBSIDIAN_SEARCH: "ищу в заметках: {query}",
            CommandType.OBSIDIAN_READ: "читаю заметку {name}",
            CommandType.GIT_LOG: "показываю коммиты {repo}",
            CommandType.GIT_STATUS: "проверяю статус {repo}",
            CommandType.OPEN_REPO: "открываю репозиторий {repo}",
            CommandType.GRAPHIFY_QUERY: "ищу в графе: {query}",
            CommandType.GRAPHIFY_PATH: "ищу связь между {node1} и {node2}",
            CommandType.CHECK_SERVICES: "проверяю сервисы",
            CommandType.RESTART_SERVICE: "перезапускаю сервис {service}",
            CommandType.ESCALATE: "эскалирую задачу к Geek",
        }
        template = formats.get(command.type, "выполняю команду")
        params = dict(command.params)
        params.setdefault("repo", "shell-scripts")
        return template.format(**params)

    def _format_execution(self, command: ParsedCommand) -> str:
        if command.shell_cmd:
            return command.shell_cmd
        return command.type.value

    def _describe_shell_command(self, command: ParsedCommand) -> Optional[str]:
        params = command.params
        descriptions = {
            CommandType.OPEN_URL: f"open {params.get('url', '')}".strip(),
            CommandType.REFRESH_PAGE: "osascript Cmd+R",
            CommandType.DOWNLOAD: f"curl -L -o ~/Downloads/... {params.get('url', '')}".strip(),
            CommandType.CLIPBOARD: "pbcopy",
            CommandType.OBSIDIAN_WRITE: "write ~/Documents/Obsidian-Vault/Inbox/*.md",
            CommandType.OBSIDIAN_SEARCH: "rg --files-with-matches <query> ~/Documents/Obsidian-Vault",
            CommandType.OBSIDIAN_READ: "find ~/Documents/Obsidian-Vault -name '*note*.md'",
            CommandType.GIT_LOG: f"git -C ~/github/{params.get('repo') or 'shell-scripts'} log --oneline --graph -10",
            CommandType.GIT_STATUS: f"git -C ~/github/{params.get('repo') or 'shell-scripts'} status --short",
            CommandType.OPEN_REPO: "open https://github.com/...",
            CommandType.GRAPHIFY_QUERY: "graphify query <query>",
            CommandType.GRAPHIFY_PATH: "graphify path <node1> <node2>",
            CommandType.CHECK_SERVICES: "GET localhost health endpoints",
            CommandType.RESTART_SERVICE: f"brew services restart {params.get('service', '')}".strip(),
            CommandType.ESCALATE: "openclaw system event --mode now",
        }
        return descriptions.get(command.type)

    def _format_confirmation_request(self, command: ParsedCommand) -> str:
        understanding = self._format_understanding(command)
        return f"Нужно подтверждение: {understanding}\nОтветь 'да' или 'нет'."

    def _suggest_alternative(self, command: ParsedCommand) -> str:
        suggestions = {
            CommandType.OPEN_URL: "проверь URL",
            CommandType.DOWNLOAD: "проверь ссылку и доступность файла",
            CommandType.OBSIDIAN_SEARCH: "попробуй другие ключевые слова",
            CommandType.OBSIDIAN_READ: "уточни название заметки",
            CommandType.GIT_LOG: "убедись что репозиторий существует",
            CommandType.GIT_STATUS: "проверь имя репозитория",
            CommandType.GRAPHIFY_QUERY: "уточни запрос для графа",
            CommandType.RESTART_SERVICE: "используй один из whitelist сервисов: ollama, postgres, redis",
            CommandType.ESCALATE: "проверь что openclaw установлен и доступен в PATH",
        }
        return suggestions.get(command.type, "проверь синтаксис команды")


BOT = Geek26Bot()

# === MAIN ===
OFFSET = 0
log.info("🤖 Dual LLM Bot started")
log.info(f"   Models: {', '.join(MODELS.keys())}")
log.info(f"   API: chat (think=false) | Context: {CONTEXT_SIZE} messages")
log.info("   Mode: compact (best answer + scores)")

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

            if text == "/start" or text == "/help":
                tg(
                    "sendMessage",
                    chat_id=chat_id,
                    text=(
                        "🤖 Dual LLM Bot\n"
                        "Две модели отвечают, эвристика выбирает лучший.\n\n"
                        f"Модели: {', '.join(MODELS.keys())}\n"
                        "Фото → OCR | Голос → транскрипция\n"
                        "/clear — очистить контекст\n"
                        "/verbose — показать оба ответа\n"
                        "Подтверждение команд: да / нет"
                    ),
                )
                continue

            if text == "/clear":
                chat_history.clear()
                BOT.pending_commands.clear()
                tg("sendMessage", chat_id=chat_id, text="🗑 Контекст очищен")
                continue

            if text == "/verbose":
                tg(
                    "sendMessage",
                    chat_id=chat_id,
                    text=("Режим: compact (только лучший ответ)\n" "Скоро будет переключатель 🔄"),
                )
                continue

            if text.startswith("/") and text not in {"/yes", "/no"}:
                continue

            media_text = process_media(msg, chat_id)
            if media_text and not text:
                prompt = media_text
            elif media_text:
                prompt = f"{media_text}\n\n{text}"
            else:
                prompt = text

            if not prompt:
                continue

            tg("sendChatAction", chat_id=chat_id, action="typing")
            reply = BOT.process_message(prompt, sender, chat_id)
            if reply:
                send_long(chat_id, reply)

    except KeyboardInterrupt:
        log.info("Stopped.")
        break
    except Exception as e:
        log.error(f"Loop error: {e}")
        time.sleep(5)
