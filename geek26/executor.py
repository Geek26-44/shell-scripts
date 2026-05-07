#!/usr/bin/env python3
"""Geek26 Bot v3.2 — Executor. 18 command handlers with timeouts and fuzzy matching."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import (
    CMD_TIMEOUT_DOWNLOAD, CMD_TIMEOUT_FAST, CMD_TIMEOUT_SEARCH,
    BotSettings,
)
from brain import CommandParser, CommandType, ParsedCommand


class CommandExecutor:
    """Execute parsed commands safely."""

    def __init__(self, settings: BotSettings, logger, memory=None) -> None:
        self.s = settings
        self.log = logger
        self.memory = memory
        self.obsidian = settings.obsidian_vault
        self.github = settings.github_dir
        self.downloads = settings.downloads

        # Feature 4: file/photo to send back to Telegram after a command.
        # Tuple of (path_str, kind, caption) where kind ∈ {"photo", "document"}.
        # Set by handlers, consumed (and cleared) by bot.py after execute().
        self.last_file: Optional[Tuple[str, str, str]] = None

        # Level 2: undo target. Path of the most recent OBSIDIAN_WRITE so
        # CANCEL can actually delete it. Cleared after a successful undo.
        self.last_obsidian_path: Optional[Path] = None

        self.handlers = {
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
            CommandType.SCREENSHOT: self._handle_screenshot,
            CommandType.KEEP_AWAKE: self._handle_keep_awake,
            CommandType.DISK_USAGE: self._handle_disk_usage,
            CommandType.MEMORY_STATUS: self._handle_memory_status,
            CommandType.SHOW_PROCESSES: self._handle_show_processes,
            CommandType.ESCALATE: self._handle_escalate,
            # Feature 2: contextual commands
            CommandType.REPEAT: self._handle_repeat,
            CommandType.CANCEL: self._handle_cancel,
            CommandType.WEB_SEARCH: self._handle_web_search,
            CommandType.CHAIN: self._handle_chain,
            CommandType.REMIND: self._handle_remind,
        }

        self.restartable = {
            "ollama": ["brew", "services", "restart", "ollama"],
            "postgres": ["brew", "services", "restart", "postgresql"],
            "postgresql": ["brew", "services", "restart", "postgresql"],
        }

    def execute(self, command: ParsedCommand, user_id: int) -> Tuple[bool, str]:
        handler = self.handlers.get(command.type)
        if not handler:
            return False, "❓ Неизвестная команда"

        # Reset per-call attachment slot. Handlers that produce a file
        # (e.g. SCREENSHOT, OBSIDIAN_READ) populate self.last_file.
        self.last_file = None

        t0 = __import__("time").time()
        try:
            ok, msg = handler(command.params)
        except subprocess.TimeoutExpired:
            ok, msg = False, "⏱️ Команда превысила таймаут"
        except Exception as e:
            ok, msg = False, f"❌ {e}"
        duration = __import__("time").time() - t0

        if self.memory:
            self.memory.save_command(
                command.raw_text, command.type.value,
                json.dumps(command.params, ensure_ascii=False),
                ok, duration,
            )

        return ok, msg

    # ── Helpers ──

    def _run(self, cmd: List[str], timeout: int = CMD_TIMEOUT_FAST,
             input_text: Optional[str] = None) -> Tuple[bool, str]:
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, input=input_text,
            )
            if r.returncode == 0:
                return True, r.stdout.strip() or "✅ Выполнено"
            return False, r.stderr.strip() or f"❌ Exit code {r.returncode}"
        except subprocess.TimeoutExpired:
            raise
        except Exception as e:
            return False, f"❌ {e}"

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    # ── Handlers ──

    def _handle_open_url(self, p: Dict) -> Tuple[bool, str]:
        url = p.get("url", "")
        if not url:
            return False, "❌ URL не указан"
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        ok, _ = self._run(["open", url])
        return (True, f"✅ Открыл: {url}") if ok else (False, "❌ Не удалось открыть")

    def _handle_refresh_page(self, p: Dict) -> Tuple[bool, str]:
        script = 'tell application "System Events" to keystroke "r" using {command down}'
        ok, _ = self._run(["osascript", "-e", script], timeout=CMD_TIMEOUT_FAST)
        return (True, "✅ Cmd+R отправлен") if ok else (False, "❌ Ошибка")

    def _handle_download(self, p: Dict) -> Tuple[bool, str]:
        url = p.get("url", "")
        if not url:
            return False, "❌ URL не указан"
        fname = url.split("/")[-1] or "download"
        fpath = self.downloads / fname
        ok, _ = self._run(["curl", "-L", "-o", str(fpath), url], timeout=CMD_TIMEOUT_DOWNLOAD)
        if ok and fpath.exists():
            size = fpath.stat().st_size
            return True, f"✅ Скачал: {fname} ({self._format_size(size)})"
        return False, "❌ Не удалось скачать"

    def _handle_clipboard(self, p: Dict) -> Tuple[bool, str]:
        text = p.get("text", "")
        if not text:
            return False, "❌ Текст не указан"
        ok, _ = self._run(["pbcopy"], timeout=CMD_TIMEOUT_FAST, input_text=text)
        preview = text[:50] + "..." if len(text) > 50 else text
        return (True, f"✅ Скопировано: {preview}") if ok else (False, "❌ Ошибка")

    def _handle_obsidian_write(self, p: Dict) -> Tuple[bool, str]:
        text = p.get("text", "")
        if not text:
            return False, "❌ Текст не указан"
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        fname = f"geek26_{ts}.md"
        inbox = self.obsidian / "Inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        fpath = inbox / fname
        title = text.split(".")[0][:50] if "." in text else text[:50]
        content = f"---\ncreated: {datetime.now().isoformat()}\nsource: geek26-bot\n---\n\n# {title}\n\n{text}\n"
        fpath.write_text(content, encoding="utf-8")
        # Level 2: remember this file so CANCEL can undo (delete) it.
        self.last_obsidian_path = fpath
        return True, f"✅ Заметка: {fname}"

    def _handle_obsidian_search(self, p: Dict) -> Tuple[bool, str]:
        query = p.get("query", "")
        if not query:
            return False, "❌ Запрос не указан"
        try:
            ok, out = self._run(
                ["/opt/homebrew/bin/rg", "-i", "--max-count", "5", "--files-with-matches",
                 query, str(self.obsidian)], timeout=CMD_TIMEOUT_SEARCH)
        except Exception:
            ok, out = self._run(["find", str(self.obsidian), "-name", f"*{query}*.md"],
                                 timeout=CMD_TIMEOUT_SEARCH)
        if ok and out:
            files = [Path(f).relative_to(self.obsidian).name for f in out.strip().split("\n")[:5]]
            return True, f"🔍 Найдено по '{query}':\n" + "\n".join(f"• {f}" for f in files)
        return True, f"🔍 Ничего не найдено по '{query}'"

    def _handle_obsidian_read(self, p: Dict) -> Tuple[bool, str]:
        name = p.get("name", "")
        if not name:
            return False, "❌ Название не указано"
        ok, out = self._run(
            ["/opt/homebrew/bin/rg", "-i", "--files-with-matches", "-g", f"*{name}*.md",
             str(self.obsidian)], timeout=CMD_TIMEOUT_SEARCH)
        if ok and out:
            fpath = Path(out.strip().split("\n")[0])
            full = fpath.read_text(encoding="utf-8")
            content = full[:2000]
            if len(full) > 2000:
                content += "\n\n... (обрезано)"
            # Feature 4: attach .md as a Telegram document so user has the full file
            if fpath.suffix.lower() == ".md" and fpath.exists():
                self.last_file = (str(fpath), "document", f"📝 {fpath.name}")
            return True, f"📝 {fpath.name}:\n\n{content}"
        return False, f"❌ Заметка '{name}' не найдена"

    def _handle_git_log(self, p: Dict) -> Tuple[bool, str]:
        repo = p.get("repo", "shell-scripts")
        rpath = self.github / repo
        if not rpath.exists():
            return False, f"❌ Репозиторий {repo} не найден"
        ok, out = self._run(["git", "-C", str(rpath), "log", "--oneline", "--graph", "-10"],
                             timeout=CMD_TIMEOUT_FAST)
        return (True, f"📋 {repo} коммиты:\n```\n{out}\n```") if ok else (False, out)

    def _handle_git_status(self, p: Dict) -> Tuple[bool, str]:
        repo = p.get("repo", "shell-scripts")
        rpath = self.github / repo
        if not rpath.exists():
            return False, f"❌ Репо {repo} не найден"
        ok, out = self._run(["git", "-C", str(rpath), "status", "--short"],
                             timeout=CMD_TIMEOUT_FAST)
        if ok:
            return (True, f"✅ {repo}: чисто") if not out else (True, f"📊 {repo}:\n```\n{out}\n```")
        return False, out

    def _handle_open_repo(self, p: Dict) -> Tuple[bool, str]:
        repo = p.get("repo", "")
        if not repo:
            return False, "❌ Репозиторий не указан"
        if "/" not in repo:
            repo = f"Geek26-44/{repo}"
        url = f"https://github.com/{repo}"
        ok, _ = self._run(["open", url])
        return (True, f"✅ Открыл: {url}") if ok else (False, "❌ Ошибка")

    def _handle_graphify_query(self, p: Dict) -> Tuple[bool, str]:
        query = p.get("query", "")
        if not query:
            return False, "❌ Запрос не указан"
        ok, out = self._run(["graphify", "query", query], timeout=CMD_TIMEOUT_SEARCH)
        if ok and out:
            return True, f"🔮 Graphify:\n{out[:1000]}"
        return False, "❌ Graphify не ответил"

    def _handle_graphify_path(self, p: Dict) -> Tuple[bool, str]:
        n1 = p.get("node1", "")
        n2 = p.get("node2", "")
        if not n1 or not n2:
            return False, "❌ Укажи оба узла"
        ok, out = self._run(["graphify", "path", n1, n2], timeout=CMD_TIMEOUT_SEARCH)
        if ok and out:
            return True, f"🔗 {n1} → {n2}:\n{out[:1000]}"
        return False, f"❌ Путь не найден. Попробуй: graphify query \"{n1}\""

    def _handle_check_services(self, p: Dict) -> Tuple[bool, str]:
        services = [
            ("Ollama", "http://localhost:11434/api/ps"),
            ("Finance Dashboard", "http://localhost:3000"),
            ("Geek Dashboard", "http://localhost:8080"),
        ]
        results = []
        for name, url in services:
            try:
                r = requests.get(url, timeout=5)
                results.append(f"✅ {name} ({r.status_code})")
            except Exception:
                results.append(f"❌ {name}")
        # Also check disk
        disk = shutil.disk_usage("/")
        disk_pct = (disk.used / disk.total) * 100
        disk_free = self._format_size(disk.free)
        results.append(f"💾 Диск: {disk_pct:.0f}% занято, {disk_free} свободно")
        return True, "🏥 Статус:\n" + "\n".join(results)

    def _handle_restart_service(self, p: Dict) -> Tuple[bool, str]:
        svc = p.get("service", "").lower()
        if svc not in self.restartable:
            return False, f"❌ '{svc}' не в whitelist. Доступно: {', '.join(self.restartable)}"
        ok, out = self._run(self.restartable[svc], timeout=30)
        return (True, f"♻️ Перезапустил {svc}") if ok else (False, f"❌ {out}")

    def _handle_screenshot(self, p: Dict) -> Tuple[bool, str]:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fpath = self.downloads / f"screenshot_{ts}.png"
        ok, _ = self._run(["screencapture", "-x", str(fpath)], timeout=10)
        if ok and fpath.exists():
            caption = f"📸 Скриншот {ts}"
            # Feature 4: send the actual image back to Telegram
            self.last_file = (str(fpath), "photo", caption)
            return True, f"📸 Скриншот: {fpath.name} ({self._format_size(fpath.stat().st_size)})"
        return False, "❌ Не удалось сделать скриншот"

    def _handle_keep_awake(self, p: Dict) -> Tuple[bool, str]:
        script = "~/github/shell-scripts/keep-awake.sh"
        ok, _ = self._run(["bash", os.path.expanduser(script)], timeout=CMD_TIMEOUT_FAST)
        return (True, "☕ Mac не уснёт") if ok else (False, "❌ Ошибка (скрипт не найден?)")

    def _handle_disk_usage(self, p: Dict) -> Tuple[bool, str]:
        disk = shutil.disk_usage("/")
        total = self._format_size(disk.total)
        used = self._format_size(disk.used)
        free = self._format_size(disk.free)
        pct = (disk.used / disk.total) * 100
        # Top dirs
        ok, out = self._run(["du", "-sh", str(Path.home() / "github"), str(Path.home() / "Documents"),
                             str(Path.home() / "Downloads"), str(Path.home() / ".ollama")],
                            timeout=15)
        details = f"\n{out}" if ok else ""
        return True, f"💾 Диск:\n  Всего: {total}\n  Занято: {used} ({pct:.0f}%)\n  Свободно: {free}{details}"

    def _handle_memory_status(self, p: Dict) -> Tuple[bool, str]:
        ok, out = self._run(["vm_stat"], timeout=CMD_TIMEOUT_FAST)
        if ok:
            # Parse key lines
            lines = out.split("\n")
            parsed = []
            for line in lines:
                if any(k in line for k in ["Pages free", "Pages active", "Pages inactive", "Pages wired"]):
                    parsed.append(line.strip())
            return True, "🧠 Память:\n" + "\n".join(parsed[:6])
        # Fallback
        ok2, out2 = self._run(["sysctl", "-n", "hw.memsize"], timeout=5)
        if ok2:
            total_gb = int(out2.strip()) / (1024**3)
            return True, f"🧠 RAM: {total_gb:.1f} GB"
        return False, "❌ Не удалось получить информацию о памяти"

    def _handle_show_processes(self, p: Dict) -> Tuple[bool, str]:
        ok, out = self._run(["ps", "aux", "-r"], timeout=CMD_TIMEOUT_FAST)
        if ok:
            lines = out.strip().split("\n")[:11]  # header + top 10
            return True, "⚙️ Топ процессов:\n```\n" + "\n".join(lines) + "\n```"
        return False, "❌ Ошибка"

    def _handle_escalate(self, p: Dict) -> Tuple[bool, str]:
        task = p.get("task", "")
        ok, _ = self._run(
            ["openclaw", "system", "event", "--text", f"Geek26 escalation: {task}", "--mode", "now"],
            timeout=10,
        )
        if ok:
            return True, "🚀 Эскалировано к Geek (OpenClaw)."
        return True, "📋 Слишком сложно для меня. Напиши Geek через OpenClaw."

    def _handle_web_search(self, p: Dict) -> Tuple[bool, str]:
        query = p.get("query", "").strip()
        if not query:
            return False, "❌ Запрос не указан"
        try:
            r = subprocess.run(
                ["gemini", "-p", query],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            return False, "❌ Gemini CLI не найден"
        if r.returncode != 0:
            return False, (r.stderr.strip() or f"❌ Gemini exit code {r.returncode}")[:2000]
        out = (r.stdout or "").strip()
        return True, f"🌐 Web Search:\n{out[:2000] if out else 'Пустой ответ'}"

    def _handle_chain(self, p: Dict) -> Tuple[bool, str]:
        steps = [str(s).strip() for s in p.get("steps", []) if str(s).strip()][:3]
        if len(steps) < 2:
            return False, "❌ Цепочка должна содержать минимум 2 шага"

        parser = CommandParser(self.memory)
        prev_ok = True
        prev_msg = ""
        results = []
        overall_ok = True

        for idx, step in enumerate(steps, start=1):
            if idx > 1 and self._chain_step_should_skip(step, prev_msg):
                results.append(f"{idx}. ⏭️ Пропустил: условие не сработало")
                continue

            cmd = parser.parse(step)
            if cmd.type == CommandType.CHAIN:
                return False, "❌ Вложенные цепочки не поддерживаются"
            cmd.params["chain_context"] = prev_msg

            if cmd.type == CommandType.RESTART_SERVICE and not cmd.params.get("service"):
                svc = self._infer_failed_service(prev_msg)
                if svc:
                    cmd.params["service"] = svc

            handler = self.handlers.get(cmd.type)
            if not handler or cmd.type == CommandType.NONE:
                prev_ok, prev_msg = False, f"❓ Не понял шаг: {step}"
            else:
                try:
                    prev_ok, prev_msg = handler(cmd.params)
                except subprocess.TimeoutExpired:
                    prev_ok, prev_msg = False, "⏱️ Шаг превысил таймаут"
                except Exception as e:
                    prev_ok, prev_msg = False, f"❌ Шаг: {e}"

            overall_ok = overall_ok and prev_ok
            marker = "✅" if prev_ok else "❌"
            results.append(f"{idx}. {marker} {cmd.type.value}: {prev_msg[:600]}")

        return overall_ok, "🔗 Цепочка:\n" + "\n".join(results)

    def _chain_step_should_skip(self, step: str, prev_msg: str) -> bool:
        lower = step.lower()
        conditional = any(word in lower for word in ["если", "if", "упало", "failed", "down"])
        if not conditional:
            return False
        bad_markers = ["❌", "not responding", "unhealthy", "failed", "down"]
        return not any(marker.lower() in prev_msg.lower() for marker in bad_markers)

    def _infer_failed_service(self, prev_msg: str) -> str:
        for line in prev_msg.splitlines():
            lower = line.lower()
            if "❌" not in lower:
                continue
            for svc in ("ollama", "postgres", "postgresql"):
                if svc in lower:
                    return "postgres" if svc == "postgresql" else svc
        return ""

    def _handle_remind(self, p: Dict) -> Tuple[bool, str]:
        if not self.memory:
            return False, "❌ SQLite недоступен"
        chat_id = p.get("chat_id")
        text = p.get("text", "").strip()
        trigger_at = p.get("trigger_at", "").strip()
        if not chat_id:
            return False, "❌ chat_id не указан"
        if not text:
            return False, "❌ Текст напоминания не указан"
        if not trigger_at:
            return False, "❌ Не понял время. Пример: напомни через 2 часа купить молоко"
        reminder_id = self.memory.add_reminder(int(chat_id), text, trigger_at)
        return True, f"⏰ Напомню: {text}\nID: {reminder_id}\nКогда: {trigger_at}"

    # ── Feature 2: contextual commands ──

    def _handle_repeat(self, p: Dict) -> Tuple[bool, str]:
        """
        Re-run the previous successful command.
        bot.py passes it as params['prev_command'] (a ParsedCommand instance).
        """
        prev = p.get("prev_command")
        if prev is None:
            return False, "❓ Нечего повторять"

        # Don't recurse REPEAT/CANCEL on themselves
        if prev.type in (CommandType.REPEAT, CommandType.CANCEL):
            return False, "❌ Нельзя повторять REPEAT/CANCEL"

        handler = self.handlers.get(prev.type)
        if not handler:
            return False, f"❓ Не могу повторить {prev.type.value}"

        try:
            ok, msg = handler(prev.params)
        except subprocess.TimeoutExpired:
            return False, "⏱️ Повтор превысил таймаут"
        except Exception as e:
            return False, f"❌ Повтор: {e}"

        prefix = "🔁 Повтор: "
        return ok, prefix + msg

    def _handle_cancel(self, p: Dict) -> Tuple[bool, str]:
        """
        Best-effort undo.

        Real rollback is implemented for:
          - OBSIDIAN_WRITE — delete the just-created note (if path still tracked
            and the file is inside the Obsidian Inbox, for safety).

        For everything else we report that rollback isn't possible.
        bot.py separately handles clearing any pending confirmation, so we
        only see CANCEL here when there's no pending confirm.
        """
        prev = p.get("prev_command")
        if prev is None:
            return True, "❓ Нечего отменять"

        # Real undo for OBSIDIAN_WRITE
        if prev.type == CommandType.OBSIDIAN_WRITE and self.last_obsidian_path is not None:
            target = self.last_obsidian_path
            inbox = (self.obsidian / "Inbox").resolve()
            try:
                resolved = target.resolve()
            except Exception:
                resolved = target
            # Safety: only delete files inside Obsidian/Inbox
            try:
                resolved.relative_to(inbox)
            except ValueError:
                self.last_obsidian_path = None
                return False, f"❌ Откат заблокирован: файл вне Inbox"

            if resolved.exists() and resolved.is_file():
                try:
                    resolved.unlink()
                    self.last_obsidian_path = None
                    return True, f"↩️ Удалил заметку: {resolved.name}"
                except Exception as e:
                    return False, f"❌ Не удалось удалить заметку: {e}"
            self.last_obsidian_path = None
            return True, f"↩️ Заметка уже удалена: {target.name}"

        return True, (
            f"⚠️ Откат '{prev.type.value}' не поддерживается. "
            "Для большинства команд откат невозможен."
        )
