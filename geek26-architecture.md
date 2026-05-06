# Geek26 Telegram Bot v2 Architecture

## System Prompt

```python
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
```

## Command Parser Architecture

```python
import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

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
    confidence: float  # 0.0 to 1.0
    raw_text: str

class CommandParser:
    """LLM-assisted + regex command parser for 9B models"""

    def __init__(self):
        # Regex patterns for high-confidence matching
        self.patterns = {
            CommandType.OPEN_URL: [
                (r'открой\s+(https?://[^\s]+)', {'url': 1}),
                (r'open\s+(https?://[^\s]+)', {'url': 1}),
                (r'перейди на\s+(https?://[^\s]+)', {'url': 1}),
                (r'go to\s+(https?://[^\s]+)', {'url': 1}),
            ],
            CommandType.REFRESH_PAGE: [
                (r'обнови\s+страницу', {}),
                (r'refresh\s+page', {}),
                (r'перезагрузи\s+страницу', {}),
                (r'reload\s+page', {}),
            ],
            CommandType.DOWNLOAD: [
                (r'скачай\s+(https?://[^\s]+)', {'url': 1}),
                (r'download\s+(https?://[^\s]+)', {'url': 1}),
                (r'загрузи\s+(https?://[^\s]+)', {'url': 1}),
            ],
            CommandType.CLIPBOARD: [
                (r'скопируй в буфер[:：]?\s*(.+)', {'text': 1}),
                (r'copy to clipboard[:：]?\s*(.+)', {'text': 1}),
                (r'в буфер[:：]?\s*(.+)', {'text': 1}),
            ],
            CommandType.OBSIDIAN_WRITE: [
                (r'запиши в обсидиан[:：]?\s*(.+)', {'text': 1}),
                (r'write to obsidian[:：]?\s*(.+)', {'text': 1}),
                (r'добавь в заметки[:：]?\s*(.+)', {'text': 1}),
                (r'создай заметку[:：]?\s*(.+)', {'text': 1}),
            ],
            CommandType.OBSIDIAN_SEARCH: [
                (r'найди в заметках\s+(.+)', {'query': 1}),
                (r'search notes for\s+(.+)', {'query': 1}),
                (r'поиск в обсидиане?\s+(.+)', {'query': 1}),
            ],
            CommandType.OBSIDIAN_READ: [
                (r'прочитай заметку\s+(.+)', {'name': 1}),
                (r'read note\s+(.+)', {'name': 1}),
                (r'покажи заметку\s+(.+)', {'name': 1}),
            ],
            CommandType.GIT_LOG: [
                (r'покажи\s+(?:последние\s+)?коммиты\s*(?:в\s+)?([^\s]+)?', {'repo': 1}),
                (r'git log\s*(?:for\s+)?([^\s]+)?', {'repo': 1}),
                (r'коммиты\s+([^\s]+)', {'repo': 1}),
            ],
            CommandType.GIT_STATUS: [
                (r'статус\s+(?:проекта\s+)?([^\s]+)', {'repo': 1}),
                (r'git status\s*(?:for\s+)?([^\s]+)?', {'repo': 1}),
                (r'что изменилось в\s+([^\s]+)', {'repo': 1}),
            ],
            CommandType.OPEN_REPO: [
                (r'открой репо(?:зиторий)?\s+([^\s]+)', {'repo': 1}),
                (r'open repo(?:sitory)?\s+([^\s]+)', {'repo': 1}),
            ],
            CommandType.GRAPHIFY_QUERY: [
                (r'(?:найди|поиск)\s+в\s+графе\s+(.+)', {'query': 1}),
                (r'graphify query\s+(.+)', {'query': 1}),
                (r'граф[:：]\s*(.+)', {'query': 1}),
            ],
            CommandType.GRAPHIFY_PATH: [
                (r'(?:как\s+)?связаны?\s+(.+?)\s+и\s+(.+)', {'node1': 1, 'node2': 2}),
                (r'путь между\s+(.+?)\s+и\s+(.+)', {'node1': 1, 'node2': 2}),
                (r'связь\s+(.+?)\s+(?:и|с)\s+(.+)', {'node1': 1, 'node2': 2}),
            ],
            CommandType.CHECK_SERVICES: [
                (r'проверь\s+сервисы', {}),
                (r'check\s+services', {}),
                (r'статус\s+сервисов', {}),
            ],
            CommandType.RESTART_SERVICE: [
                (r'перезапусти\s+(.+)', {'service': 1}),
                (r'restart\s+(.+)', {'service': 1}),
                (r'рестарт\s+(.+)', {'service': 1}),
            ],
        }

        # Keywords for escalation detection
        self.escalation_keywords = [
            'сложн', 'анализ', 'исследова', 'разбер', 'изуч',
            'complex', 'analyze', 'research', 'investigate',
            'многошаг', 'multi-step', 'глубок', 'deep',
            'план', 'стратег', 'архитектур'
        ]

    def parse(self, text: str, llm_hint: Optional[str] = None) -> ParsedCommand:
        """
        Parse command from text.
        llm_hint: optional LLM interpretation of intent
        """
        text_lower = text.lower().strip()

        # First, check regex patterns
        for cmd_type, patterns in self.patterns.items():
            for pattern, param_map in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    params = {}
                    for param_name, group_idx in param_map.items():
                        if group_idx <= len(match.groups()):
                            value = match.group(group_idx)
                            if value:
                                params[param_name] = value.strip()

                    return ParsedCommand(
                        type=cmd_type,
                        params=params,
                        confidence=0.9,  # High confidence for regex match
                        raw_text=text
                    )

        # Check for escalation
        if any(kw in text_lower for kw in self.escalation_keywords):
            return ParsedCommand(
                type=CommandType.ESCALATE,
                params={'task': text},
                confidence=0.7,
                raw_text=text
            )

        # If LLM provided a hint, try to parse it
        if llm_hint:
            return self._parse_llm_hint(llm_hint, text)

        return ParsedCommand(
            type=CommandType.NONE,
            params={},
            confidence=0.0,
            raw_text=text
        )

    def _parse_llm_hint(self, hint: str, original_text: str) -> ParsedCommand:
        """Parse LLM's interpretation of command intent"""
        hint_lower = hint.lower()

        # Simple keyword matching for LLM hints
        if 'open' in hint_lower and 'url' in hint_lower:
            # Extract URL from original text
            url_match = re.search(r'https?://[^\s]+', original_text)
            if url_match:
                return ParsedCommand(
                    type=CommandType.OPEN_URL,
                    params={'url': url_match.group(0)},
                    confidence=0.6,
                    raw_text=original_text
                )

        # Add more LLM hint parsing as needed

        return ParsedCommand(
            type=CommandType.NONE,
            params={},
            confidence=0.0,
            raw_text=original_text
        )
```

## Executor Module

```python
import subprocess
import os
import time
import requests
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import json
from datetime import datetime

class CommandExecutor:
    """Execute parsed commands safely"""

    def __init__(self, allowed_user_id: int = 170285780):
        self.allowed_user_id = allowed_user_id
        self.home = Path.home()
        self.obsidian_vault = self.home / "Documents" / "Obsidian-Vault"
        self.downloads = self.home / "Downloads"
        self.github = self.home / "github"
        self.shell_scripts = self.github / "shell-scripts"

    def execute(self, command: ParsedCommand, user_id: int) -> Tuple[bool, str]:
        """
        Execute command and return (success, result_text)
        """
        # Safety check
        if user_id != self.allowed_user_id:
            return False, "⛔ Unauthorized user"

        # Log execution attempt
        self._log_execution(command)

        # Route to appropriate handler
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
            return False, f"❌ Ошибка: {str(e)}"

    def _log_execution(self, command: ParsedCommand):
        """Log command execution for audit"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'command_type': command.type.value,
            'params': command.params,
            'raw_text': command.raw_text
        }
        # In production, write to proper log file
        print(f"[EXEC] {json.dumps(log_entry)}")

    def _run_shell(self, cmd: list, timeout: int = 120) -> Tuple[bool, str]:
        """Run shell command safely"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            if result.returncode == 0:
                return True, result.stdout.strip() or "✅ Выполнено"
            else:
                return False, f"❌ Ошибка: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            raise

    def _handle_open_url(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Open URL in default browser"""
        url = params.get('url')
        if not url:
            return False, "❌ URL не указан"

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        success, output = self._run_shell(['open', url])
        if success:
            return True, f"✅ Открыл: {url}"
        return success, output

    def _handle_refresh_page(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Send Cmd+R to active window"""
        applescript = '''
        tell application "System Events"
            keystroke "r" using {command down}
        end tell
        '''
        success, output = self._run_shell(['osascript', '-e', applescript], timeout=10)
        if success:
            return True, "✅ Отправил Cmd+R"
        return success, output

    def _handle_download(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Download file to ~/Downloads"""
        url = params.get('url')
        if not url:
            return False, "❌ URL не указан"

        filename = url.split('/')[-1] or 'download'
        filepath = self.downloads / filename

        # Use curl for download
        success, output = self._run_shell([
            'curl', '-L', '-o', str(filepath), url
        ], timeout=300)

        if success and filepath.exists():
            size = filepath.stat().st_size
            return True, f"✅ Скачал: {filename} ({self._format_size(size)})"
        return False, "❌ Не удалось скачать файл"

    def _handle_clipboard(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Copy text to clipboard"""
        text = params.get('text', '')
        if not text:
            return False, "❌ Текст не указан"

        # Use pbcopy on macOS
        try:
            subprocess.run(['pbcopy'], input=text, text=True, check=True)
            preview = text[:50] + "..." if len(text) > 50 else text
            return True, f"✅ Скопировано: {preview}"
        except Exception as e:
            return False, f"❌ Ошибка копирования: {e}"

    def _handle_obsidian_write(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Write note to Obsidian vault"""
        text = params.get('text', '')
        if not text:
            return False, "❌ Текст не указан"

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"geek26_{timestamp}.md"
        filepath = self.obsidian_vault / "Inbox" / filename

        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Write note with metadata
        content = f"""---
created: {datetime.now().isoformat()}
source: geek26-bot
---

# {text.split('.')[0] if '.' in text else text[:50]}

{text}
"""

        filepath.write_text(content, encoding='utf-8')
        return True, f"✅ Создал заметку: {filename}"

    def _handle_obsidian_search(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Search in Obsidian vault"""
        query = params.get('query', '')
        if not query:
            return False, "❌ Запрос не указан"

        # Use ripgrep for fast search
        success, output = self._run_shell([
            'rg', '-i', '--max-count', '5', '--files-with-matches',
            query, str(self.obsidian_vault)
        ], timeout=30)

        if success and output:
            files = output.strip().split('\n')[:5]
            results = []
            for f in files:
                rel_path = Path(f).relative_to(self.obsidian_vault)
                results.append(f"• {rel_path}")

            return True, f"🔍 Найдено по '{query}':\n" + "\n".join(results)

        return True, f"❌ Ничего не найдено по запросу: {query}"

    def _handle_obsidian_read(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Read specific note from Obsidian"""
        name = params.get('name', '')
        if not name:
            return False, "❌ Название заметки не указано"

        # Search for note file
        success, output = self._run_shell([
            'find', str(self.obsidian_vault), '-name', f"*{name}*.md",
            '-type', 'f', '-print', '-quit'
        ], timeout=10)

        if success and output:
            filepath = Path(output.strip())
            content = filepath.read_text(encoding='utf-8')
            # Limit output
            if len(content) > 2000:
                content = content[:2000] + "\n\n... (обрезано)"

            return True, f"📝 {filepath.name}:\n\n{content}"

        return False, f"❌ Заметка '{name}' не найдена"

    def _handle_git_log(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Show git commits"""
        repo = params.get('repo', 'shell-scripts')
        repo_path = self.github / repo

        if not repo_path.exists():
            return False, f"❌ Репозиторий {repo} не найден"

        success, output = self._run_shell([
            'git', '-C', str(repo_path), 'log',
            '--oneline', '--graph', '-10'
        ], timeout=10)

        if success:
            return True, f"📋 Последние коммиты {repo}:\n```\n{output}\n```"
        return success, output

    def _handle_git_status(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Show git status"""
        repo = params.get('repo', 'shell-scripts')
        repo_path = self.github / repo

        if not repo_path.exists():
            return False, f"❌ Репозиторий {repo} не найден"

        success, output = self._run_shell([
            'git', '-C', str(repo_path), 'status', '--short'
        ], timeout=10)

        if success:
            if output:
                return True, f"📊 Статус {repo}:\n```\n{output}\n```"
            else:
                return True, f"✅ {repo}: чисто, нет изменений"
        return success, output

    def _handle_open_repo(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Open GitHub repository"""
        repo = params.get('repo', '')
        if not repo:
            return False, "❌ Репозиторий не указан"

        # Assume it's user's repo if no owner specified
        if '/' not in repo:
            repo = f"geek2026/{repo}"

        url = f"https://github.com/{repo}"
        return self._handle_open_url({'url': url})

    def _handle_graphify_query(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Query Graphify knowledge graph"""
        query = params.get('query', '')
        if not query:
            return False, "❌ Запрос не указан"

        success, output = self._run_shell([
            'graphify', 'query', query
        ], timeout=30)

        if success:
            return True, f"🔮 Graphify результаты:\n{output}"
        return success, output

    def _handle_graphify_path(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Find path between nodes in Graphify"""
        node1 = params.get('node1', '')
        node2 = params.get('node2', '')

        if not node1 or not node2:
            return False, "❌ Укажи оба узла"

        success, output = self._run_shell([
            'graphify', 'path', node1, node2
        ], timeout=30)

        if success:
            return True, f"🔗 Путь {node1} → {node2}:\n{output}"
        return success, output

    def _handle_check_services(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Check health of local services"""
        services = [
            ("Ollama", "http://localhost:11434/api/ps"),
            ("Web App", "http://localhost:3000/health"),
            ("API", "http://localhost:8080/health")
        ]

        results = []
        for name, url in services:
            try:
                r = requests.get(url, timeout=5)
                status = "✅" if r.ok else f"⚠️ {r.status_code}"
            except:
                status = "❌ Не отвечает"
            results.append(f"{name}: {status}")

        return True, "🏥 Статус сервисов:\n" + "\n".join(results)

    def _handle_restart_service(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Restart a service (with safety checks)"""
        service = params.get('service', '')
        if not service:
            return False, "❌ Сервис не указан"

        # Whitelist of restartable services
        allowed_services = {
            'ollama': 'brew services restart ollama',
            'postgres': 'brew services restart postgresql',
            'redis': 'brew services restart redis',
        }

        if service.lower() not in allowed_services:
            return False, f"❌ Сервис '{service}' не в whitelist"

        cmd = allowed_services[service.lower()]
        success, output = self._run_shell(cmd.split(), timeout=30)

        if success:
            return True, f"♻️ Перезапустил {service}"
        return success, output

    def _handle_escalate(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Escalate to OpenClaw"""
        task = params.get('task', '')

        # Send event to OpenClaw
        success, output = self._run_shell([
            'openclaw', 'system', 'event',
            '--text', f"Escalated from Geek26: {task}",
            '--mode', 'now'
        ], timeout=10)

        if success:
            return True, "🚀 Эскалировано к Geek (OpenClaw). Он займётся этой задачей."
        return False, "❌ Не удалось эскалировать к OpenClaw"

    def _format_size(self, size: int) -> str:
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"
```

## Safety Layer

```python
class SafetyValidator:
    """Validate commands for safety before execution"""

    def __init__(self, allowed_user_id: int = 170285780):
        self.allowed_user_id = allowed_user_id

        # Dangerous patterns
        self.dangerous_patterns = [
            r'\brm\s+-rf',
            r'\bsudo\s+rm',
            r'\b>\s*/dev/s',  # Overwriting devices
            r'\bdd\s+if=',    # Disk operations
            r'\bmkfs\.',      # Format operations
            r':(){ :|:& };:', # Fork bomb
        ]

        # Commands requiring confirmation
        self.confirm_required = [
            'sudo',
            'reboot',
            'shutdown',
            'kill -9',
            'systemctl stop',
            'brew uninstall',
        ]

        # Safe command whitelist (for shell execution)
        self.safe_commands = {
            'ls', 'pwd', 'echo', 'cat', 'grep', 'find', 'head', 'tail',
            'git', 'curl', 'open', 'osascript', 'pbcopy', 'pbpaste',
            'rg', 'fd', 'graphify', 'openclaw', 'trash',
            'brew', 'npm', 'python3', 'node',
        }

    def validate_command(self, command: ParsedCommand, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Validate command for safety.
        Returns (is_safe, error_message)
        """
        # User check
        if user_id != self.allowed_user_id:
            return False, "Unauthorized user"

        # Check command type specific rules
        if command.type == CommandType.DOWNLOAD:
            url = command.params.get('url', '')
            if not self._validate_url(url):
                return False, "Suspicious URL"

        # For shell-based commands, check patterns
        if hasattr(command, 'shell_cmd'):
            shell_cmd = command.shell_cmd

            # Check dangerous patterns
            for pattern in self.dangerous_patterns:
                if re.search(pattern, shell_cmd, re.IGNORECASE):
                    return False, f"Dangerous command pattern: {pattern}"

            # Check if confirmation needed
            for confirm_cmd in self.confirm_required:
                if confirm_cmd in shell_cmd.lower():
                    return False, f"Command requires confirmation: {confirm_cmd}"

        return True, None

    def _validate_url(self, url: str) -> bool:
        """Validate URL for safety"""
        if not url:
            return False

        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return False

        # Check against known malicious patterns
        malicious_patterns = [
            r'bit\.ly',
            r'tinyurl',
            r'goo\.gl',
            r'ow\.ly',
            # Add more as needed
        ]

        for pattern in malicious_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False

        return True

    def needs_confirmation(self, command: ParsedCommand) -> bool:
        """Check if command needs user confirmation"""
        # External actions
        if command.type in [CommandType.RESTART_SERVICE]:
            return True

        # Commands with side effects
        if command.type == CommandType.OBSIDIAN_WRITE:
            # Large text might need confirmation
            text = command.params.get('text', '')
            if len(text) > 1000:
                return True

        return False
```

## Integration with Bot

```python
# Modified dual-llm-bot.py integration

class Geek26Bot:
    """Enhanced bot with command execution"""

    def __init__(self):
        self.parser = CommandParser()
        self.executor = CommandExecutor()
        self.validator = SafetyValidator()

        # Update system prompt
        self.system_prompt = SYSTEM_PROMPT  # From above

    def process_message(self, text: str, user_id: int, chat_id: int) -> str:
        """Process message with command detection"""

        # First, try to parse as command
        command = self.parser.parse(text)

        if command.type != CommandType.NONE and command.confidence > 0.5:
            # Validate safety
            is_safe, error = self.validator.validate_command(command, user_id)
            if not is_safe:
                return f"⛔ Безопасность: {error}"

            # Check if needs confirmation
            if self.validator.needs_confirmation(command):
                # Store pending command and ask for confirmation
                self.pending_commands[chat_id] = command
                return self._format_confirmation_request(command)

            # Execute command
            return self._execute_and_format(command, user_id)

        # Not a command, process as regular chat
        return self._process_chat(text)

    def _execute_and_format(self, command: ParsedCommand, user_id: int) -> str:
        """Execute command and format response"""
        # Show what we understood
        understanding = self._format_understanding(command)

        # Execute
        success, result = self.executor.execute(command, user_id)

        # Format response
        if success:
            return f"Понял: {understanding}\n{result}"
        else:
            return f"Понял: {understanding}\n{result}\nПопробуй: {self._suggest_alternative(command)}"

    def _format_understanding(self, command: ParsedCommand) -> str:
        """Format what bot understood from command"""
        formats = {
            CommandType.OPEN_URL: "открываю {url}",
            CommandType.OBSIDIAN_WRITE: "записываю в Obsidian",
            CommandType.GIT_LOG: "показываю коммиты {repo}",
            # ... etc
        }

        template = formats.get(command.type, "выполняю команду")
        return template.format(**command.params)

    def _suggest_alternative(self, command: ParsedCommand) -> str:
        """Suggest alternative when command fails"""
        suggestions = {
            CommandType.OPEN_URL: "проверь URL",
            CommandType.OBSIDIAN_SEARCH: "попробуй другие ключевые слова",
            CommandType.GIT_LOG: "убедись что репозиторий существует",
            # ... etc
        }

        return suggestions.get(command.type, "проверь синтаксис команды")
```

## Example Dialogs

### 1. Screenshot OCR
```
User: [sends photo]
Bot: Понял: анализирую изображение
Выполняю: ~/github/shell-scripts/ocr.sh /tmp/photo_12345.jpg
Результат: На изображении текст: "Error: Connection refused at line 42"
```

### 2. Open URL
```
User: открой https://github.com/geek2026/openclaw
Bot: Понял: открываю https://github.com/geek2026/openclaw
✅ Открыл: https://github.com/geek2026/openclaw
```

### 3. Obsidian Note Creation
```
User: запиши в обсидиан: встреча с командой в 15:00, обсудить архитектуру нового сервиса
Bot: Понял: записываю в Obsidian
✅ Создал заметку: geek26_2024-01-15_14-30.md
```

### 4. Git Status Check
```
User: статус openclaw
Bot: Понял: показываю статус openclaw
📊 Статус openclaw:
```
M  src/app.py
M  tests/test_app.py
?? docs/new-feature.md
```
```

### 5. Service Health Check
```
User: проверь сервисы
Bot: Понял: проверяю статус сервисов
🏥 Статус сервисов:
Ollama: ✅
Web App: ❌ Не отвечает
API: ✅
```

### 6. Complex Task Escalation
```
User: проанализируй архитектуру проекта и предложи оптимизации
Bot: Понял: задача требует глубокого анализа
🚀 Эскалировано к Geek (OpenClaw). Он займётся этой задачей.
```

### 7. Graphify Query
```
User: найди в графе quantum computing
Bot: Понял: ищу в графе знаний
🔮 Graphify результаты:
- Quantum Computing → связано с → Cryptography (вес: 0.8)
- Quantum Computing → связано с → Machine Learning (вес: 0.6)
- Quantum Computing → упоминается в → Research Paper 2024
```

### 8. Error Handling
```
User: открой репо my-secret-project
Bot: Понял: открываю репозиторий my-secret-project
❌ Репозиторий my-secret-project не найден
Попробуй: убедись что репозиторий существует
```

## Deployment Notes

1. **Update System Prompt**: Replace the generic prompt in dual-llm-bot.py line 35
2. **Add Command Parser**: Insert before the main loop
3. **Integrate Executor**: Add command detection in message processing
4. **Test Safety**: Verify all dangerous commands are blocked
5. **Add Logging**: Ensure all executions are logged for audit
6. **Monitor Performance**: 9B models might need prompt engineering for better command detection

## Future Enhancements

1. **Learning**: Track successful commands and improve parsing
2. **Aliases**: User-defined command shortcuts
3. **Batch Operations**: Execute multiple commands in sequence
4. **Scheduling**: Delayed command execution
5. **Notifications**: Alert user when long-running commands complete