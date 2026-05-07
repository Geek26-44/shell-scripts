#!/usr/bin/env python3
"""Geek26 Bot v3.2 — Smart Brain. RAG + memory recall + adaptive routing + more commands."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from config import (
    ALLOWED_USER, CMD_TIMEOUT_SEARCH, CONTEXT_LOAD_ON_START, CONTEXT_SIZE,
    DB_FILE, LLM_BACKOFF, LLM_RETRIES, MODELS, OLLAMA_CHAT, OLLAMA_GEN,
    BotSettings, OBSIDIAN_VAULT, SHELL_SCRIPTS,
)

# ──────────────────────────────────────────────
# COMMAND TYPES & PARSING
# ──────────────────────────────────────────────

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
    SCREENSHOT = "screenshot"
    KEEP_AWAKE = "keep_awake"
    DISK_USAGE = "disk_usage"
    MEMORY_STATUS = "memory_status"
    SHOW_PROCESSES = "show_processes"
    ESCALATE = "escalate"
    REPEAT = "repeat"
    CANCEL = "cancel"
    WEB_SEARCH = "web_search"
    CHAIN = "chain"
    REMIND = "remind"
    NONE = "none"


@dataclass
class ParsedCommand:
    type: CommandType
    params: Dict[str, Any]
    confidence: float
    raw_text: str


class CommandParser:
    """Regex + keyword hybrid parser with pattern learning."""

    def __init__(self, memory: Optional["Memory"] = None) -> None:
        self.memory = memory
        self.patterns: Dict[CommandType, List[Tuple[str, Dict[str, int]]]] = {
            CommandType.OPEN_URL: [
                (r'открой\s+(https?://[^\s]+)', {"url": 1}),
                (r'open\s+(https?://[^\s]+)', {"url": 1}),
                (r'перейди\s+(?:на\s+)?(https?://[^\s]+)', {"url": 1}),
                (r'go\s+to\s+(https?://[^\s]+)', {"url": 1}),
            ],
            CommandType.REFRESH_PAGE: [
                (r'обнови\s+страницу', {}),
                (r'refresh\s+page', {}),
                (r'перезагрузи\s+страницу', {}),
                (r'reload\s+page', {}),
            ],
            CommandType.DOWNLOAD: [
                (r'скачай\s+(https?://[^\s]+)', {"url": 1}),
                (r'download\s+(https?://[^\s]+)', {"url": 1}),
                (r'загрузи\s+(https?://[^\s]+)', {"url": 1}),
            ],
            CommandType.CLIPBOARD: [
                (r'скопируй\s+в\s+буфер[:：]?\s*(.+)', {"text": 1}),
                (r'copy\s+(?:to\s+)?clipboard[:：]?\s*(.+)', {"text": 1}),
                (r'в\s+буфер[:：]?\s*(.+)', {"text": 1}),
            ],
            CommandType.OBSIDIAN_WRITE: [
                (r'запиши\s+в\s+обсидиан[:：]?\s*(.+)', {"text": 1}),
                (r'создай\s+заметку[:：]?\s*(.+)', {"text": 1}),
                (r'добавь\s+в\s+заметки[:：]?\s*(.+)', {"text": 1}),
                (r'write\s+(?:to\s+)?obsidian[:：]?\s*(.+)', {"text": 1}),
            ],
            CommandType.OBSIDIAN_SEARCH: [
                (r'найди\s+в\s+заметках\s+(.+)', {"query": 1}),
                (r'поиск\s+в\s+обсидиан(?:е)?\s+(.+)', {"query": 1}),
                (r'search\s+notes\s+(?:for\s+)?(.+)', {"query": 1}),
                (r'поищи\s+(?:в\s+заметках\s+)?(.+)', {"query": 1}),
            ],
            CommandType.OBSIDIAN_READ: [
                (r'прочитай\s+заметку\s+(.+)', {"name": 1}),
                (r'покажи\s+заметку\s+(.+)', {"name": 1}),
                (r'read\s+note\s+(.+)', {"name": 1}),
            ],
            CommandType.GIT_LOG: [
                (r'покажи\s+(?:последние\s+)?коммиты\s+(?:в\s+)?([^\s]+)?', {"repo": 1}),
                (r'коммиты\s+([^\s]+)', {"repo": 1}),
                (r'git\s+log\s*(?:for\s+)?([^\s]+)?', {"repo": 1}),
            ],
            CommandType.GIT_STATUS: [
                (r'статус\s+(?:проекта\s+)?([^\s]+)', {"repo": 1}),
                (r'что\s+изменилось\s+в\s+([^\s]+)', {"repo": 1}),
                (r'git\s+status\s*(?:for\s+)?([^\s]+)?', {"repo": 1}),
            ],
            CommandType.OPEN_REPO: [
                (r'открой\s+репо(?:зиторий)?\s+([^\s]+)', {"repo": 1}),
                (r'open\s+repo(?:sitory)?\s+([^\s]+)', {"repo": 1}),
            ],
            CommandType.GRAPHIFY_QUERY: [
                (r'(?:найди|поиск)\s+в\s+графе?\s+(.+)', {"query": 1}),
                (r'graphify\s+query\s+(.+)', {"query": 1}),
                (r'граф[:：]\s*(.+)', {"query": 1}),
            ],
            CommandType.GRAPHIFY_PATH: [
                (r'(?:как\s+)?связаны?\s+(.+?)\s+и\s+(.+)', {"node1": 1, "node2": 2}),
                (r'путь\s+(?:между\s+)?(.+?)\s+(?:и|с)\s+(.+)', {"node1": 1, "node2": 2}),
                (r'связь\s+(.+?)\s+(?:и|с)\s+(.+)', {"node1": 1, "node2": 2}),
            ],
            CommandType.CHECK_SERVICES: [
                (r'проверь\s+сервисы', {}),
                (r'check\s+services', {}),
                (r'статус\s+сервисов', {}),
                (r'здоровье\s+системы', {}),
            ],
            CommandType.RESTART_SERVICE: [
                (r'перезапусти\s+(.+)', {"service": 1}),
                (r'restart\s+(.+)', {"service": 1}),
                (r'рестарт\s+(.+)', {"service": 1}),
            ],
            CommandType.SCREENSHOT: [
                (r'сделай\s+скриншот', {}),
                (r'screenshot', {}),
                (r'скрин\s+(?:экрана)?', {}),
                (r'сфоткай\s+экран', {}),
            ],
            CommandType.KEEP_AWAKE: [
                (r'не\s+усыпляй\s+мак', {}),
                (r'keep\s+awake', {}),
                (r'бодрствуй', {}),
                (r'не\s+спи', {}),
            ],
            CommandType.DISK_USAGE: [
                (r'сколько\s+места\s+(?:на\s+диске)?', {}),
                (r'disk\s+usage', {}),
                (r'свободно\s+место', {}),
                (r'место\s+на\s+диске', {}),
            ],
            CommandType.MEMORY_STATUS: [
                (r'память\s+(?:системы)?', {}),
                (r'ram\s+usage', {}),
                (r'сколько\s+памяти', {}),
                (r'memory\s+status', {}),
            ],
            CommandType.SHOW_PROCESSES: [
                (r'покажи\s+процессы', {}),
                (r'top\s+processes', {}),
                (r'что\s+жрёт\s+(?:ресурсы\s+)?', {}),
                (r'кто\s+жрёт\s+память', {}),
            ],
            CommandType.REPEAT: [
                (r'^\s*повтори\s*(?:ещё\s+раз)?\s*$', {}),
                (r'^\s*ещё\s+раз\s*$', {}),
                (r'^\s*сделай\s+ещё(?:\s+раз)?\s*$', {}),
                (r'^\s*repeat\s*$', {}),
                (r'^\s*again\s*$', {}),
                (r'^\s*do\s+(?:it\s+)?again\s*$', {}),
            ],
            CommandType.CANCEL: [
                (r'^\s*отмени(?:\s+это|\s+последнее)?\s*$', {}),
                (r'^\s*отмена\s*$', {}),
                (r'^\s*откати\s*$', {}),
                (r'^\s*cancel\s*$', {}),
                (r'^\s*undo\s*$', {}),
            ],
            CommandType.WEB_SEARCH: [
                (r'найди\s+в\s+интернете\s+(.+)', {"query": 1}),
                (r'гугли\s+(.+)', {"query": 1}),
                (r'найди\s+онлайн\s+(.+)', {"query": 1}),
                (r'search\s+web\s+(.+)', {"query": 1}),
            ],
            CommandType.REMIND: [
                (r'напомни\s+(.+)', {"text": 1}),
                (r'remind\s+me\s+(.+)', {"text": 1}),
            ],
        }

        self.keywords: Dict[CommandType, List[str]] = {
            CommandType.OPEN_URL: ["открой", "open", "перейди", "зайди на"],
            CommandType.REFRESH_PAGE: ["обнови страницу", "refresh", "reload"],
            CommandType.DOWNLOAD: ["скачай", "download", "загрузи", "качни"],
            CommandType.CLIPBOARD: ["в буфер", "скопируй", "clipboard", "copy"],
            CommandType.OBSIDIAN_WRITE: ["запиши в обсидиан", "создай заметку", "в заметки"],
            CommandType.OBSIDIAN_SEARCH: ["найди в заметках", "поиск в обсидиан", "поищи"],
            CommandType.OBSIDIAN_READ: ["прочитай заметку", "покажи заметку"],
            CommandType.GIT_LOG: ["коммиты", "commits", "git log"],
            CommandType.GIT_STATUS: ["статус проекта", "git status", "что изменилось"],
            CommandType.OPEN_REPO: ["открой репо", "open repo"],
            CommandType.GRAPHIFY_QUERY: ["в графе", "graphify query", "поиск по графу"],
            CommandType.GRAPHIFY_PATH: ["как связаны", "путь между", "связь между"],
            CommandType.CHECK_SERVICES: ["проверь сервисы", "check services", "статус сервисов"],
            CommandType.RESTART_SERVICE: ["перезапусти", "restart", "рестарт"],
            CommandType.SCREENSHOT: ["скриншот", "screenshot", "скрин", "сфоткай"],
            CommandType.KEEP_AWAKE: ["не усыпляй", "keep awake", "бодрствуй", "не спи"],
            CommandType.DISK_USAGE: ["место на диске", "disk usage", "сколько места", "свободно место"],
            CommandType.MEMORY_STATUS: ["память системы", "ram", "сколько памяти"],
            CommandType.SHOW_PROCESSES: ["покажи процессы", "top processes", "жрёт память"],
            CommandType.ESCALATE: [
                "анализ", "проанализируй", "исследуй", "исследование",
                "разберись", "разобрать", "изучи", "глубок", "ресёрч",
                "research", "analyze", "investigate", "стратег", "архитектур",
                "многошаг", "multi-step", "сложн", "complex",
                "спланируй", "план ", "оптимизир",
            ],
            CommandType.REPEAT: ["повтори", "ещё раз", "сделай ещё", "repeat", "again"],
            CommandType.CANCEL: ["отмени", "отмена", "откати", "cancel", "undo"],
            CommandType.WEB_SEARCH: ["найди в интернете", "search web", "гугли", "найди онлайн"],
            CommandType.REMIND: ["напомни", "remind me"],
        }

        self._load_patterns()

    def _load_patterns(self) -> None:
        if not self.memory:
            return
        for keyword, cmd_type_str in self.memory.get_patterns():
            try:
                cmd_type = CommandType(cmd_type_str)
                if cmd_type not in self.keywords:
                    self.keywords[cmd_type] = []
                if keyword not in self.keywords[cmd_type]:
                    self.keywords[cmd_type].append(keyword)
            except ValueError:
                pass

    def learn_pattern(self, keyword: str, cmd_type: CommandType) -> None:
        if cmd_type not in self.keywords:
            self.keywords[cmd_type] = []
        if keyword not in self.keywords[cmd_type]:
            self.keywords[cmd_type].append(keyword)
            if self.memory:
                self.memory.save_pattern(keyword, cmd_type.value)

    def parse(self, text: str, llm_hint: Optional[str] = None) -> ParsedCommand:
        text_lower = text.lower().strip()

        chain_steps = self._parse_chain_steps(text)
        if chain_steps:
            return ParsedCommand(CommandType.CHAIN, {"steps": chain_steps}, 0.85, text)

        for cmd_type, patterns in self.patterns.items():
            for pattern, param_map in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    params = {}
                    for pname, gidx in param_map.items():
                        val = match.group(gidx) if gidx <= len(match.groups()) else None
                        if val:
                            params[pname] = val.strip()
                    if cmd_type == CommandType.REMIND:
                        params = self._extract_reminder_params(text)
                    return ParsedCommand(cmd_type, params, 0.9, text)

        for cmd_type, kws in self.keywords.items():
            for kw in kws:
                if kw in text_lower:
                    params = self._extract_params(cmd_type, text)
                    return ParsedCommand(cmd_type, params, 0.7, text)

        if llm_hint:
            return self._parse_llm_hint(llm_hint, text)

        return ParsedCommand(CommandType.NONE, {}, 0.0, text)

    def _extract_params(self, cmd_type: CommandType, text: str) -> Dict[str, Any]:
        url_match = re.search(r'https?://[^\s]+', text)
        params: Dict[str, Any] = {}

        if cmd_type in (CommandType.OPEN_URL, CommandType.DOWNLOAD) and url_match:
            params["url"] = url_match.group(0)
        elif cmd_type == CommandType.WEB_SEARCH:
            lower = text.lower()
            for kw in self.keywords.get(cmd_type, []):
                if kw in lower:
                    idx = lower.index(kw) + len(kw)
                    params["query"] = text[idx:].strip(" :—-")
                    break
            if "query" not in params:
                params["query"] = text.strip()
        elif cmd_type == CommandType.REMIND:
            params.update(self._extract_reminder_params(text))
        elif cmd_type == CommandType.ESCALATE:
            params["task"] = text
        elif cmd_type == CommandType.RESTART_SERVICE:
            for svc in ["ollama", "postgres", "redis", "nginx"]:
                if svc in text.lower():
                    params["service"] = svc
                    break
        elif cmd_type in (CommandType.GIT_LOG, CommandType.GIT_STATUS, CommandType.OPEN_REPO):
            for repo_name in ["shell-scripts", "Finance", "11-steps"]:
                if repo_name.lower() in text.lower():
                    params["repo"] = repo_name
                    break
        elif cmd_type == CommandType.GRAPHIFY_QUERY:
            for kw in self.keywords.get(cmd_type, []):
                if kw in text.lower():
                    idx = text.lower().index(kw) + len(kw)
                    params["query"] = text[idx:].strip()
                    break
        elif cmd_type == CommandType.GRAPHIFY_PATH:
            match = re.search(r'(.+?)\s+(?:и|с|and)\s+(.+)', text)
            if match:
                params["node1"] = match.group(1).strip()
                params["node2"] = match.group(2).strip()

        return params

    def _parse_chain_steps(self, text: str) -> List[str]:
        parts = re.split(r'\s+(?:и\s+если|и\s+тогда|а\s+потом|then|and\s+then)\s+', text, flags=re.IGNORECASE)
        steps = [p.strip(" .;") for p in parts if p.strip(" .;")]
        if len(steps) < 2:
            return []
        return steps[:3]

    def _extract_reminder_params(self, text: str) -> Dict[str, Any]:
        raw = re.sub(r'^\s*(напомни|remind\s+me)\s*', '', text, flags=re.IGNORECASE).strip()
        lower = raw.lower()
        params: Dict[str, Any] = {"text": raw}

        tomorrow = re.search(r'завтра\s+в\s+(\d{1,2})(?::(\d{2}))?\s*(?:утра|am)?', lower)
        if tomorrow:
            hour = int(tomorrow.group(1))
            minute = int(tomorrow.group(2) or 0)
            if "pm" in lower and hour < 12:
                hour += 12
            trigger = (datetime.now() + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            reminder_text = (raw[:tomorrow.start()] + raw[tomorrow.end():]).strip(" ,.-")
            params.update({"text": reminder_text or raw, "trigger_at": trigger.isoformat()})
            return params

        rel = re.search(
            r'через\s+(\d+)\s*(мин(?:ут[уы]?)?|час(?:а|ов)?|д(?:ень|ня|ней)|дн(?:я|ей)?)\s*(.*)',
            lower,
            flags=re.IGNORECASE,
        )
        if rel:
            amount = int(rel.group(1))
            unit = rel.group(2)
            if unit.startswith("мин"):
                delta = timedelta(minutes=amount)
            elif unit.startswith("час"):
                delta = timedelta(hours=amount)
            else:
                delta = timedelta(days=amount)
            params.update({
                "text": raw[rel.end(2):].strip(" ,.-") or raw,
                "trigger_at": (datetime.now() + delta).isoformat(),
            })
        return params

    def _parse_llm_hint(self, hint: str, original: str) -> ParsedCommand:
        hint_lower = hint.lower()
        if "open" in hint_lower and "url" in hint_lower:
            url_match = re.search(r'https?://[^\s]+', original)
            if url_match:
                return ParsedCommand(CommandType.OPEN_URL, {"url": url_match.group(0)}, 0.5, original)
        if "download" in hint_lower:
            url_match = re.search(r'https?://[^\s]+', original)
            if url_match:
                return ParsedCommand(CommandType.DOWNLOAD, {"url": url_match.group(0)}, 0.5, original)
        return ParsedCommand(CommandType.NONE, {}, 0.0, original)


# ──────────────────────────────────────────────
# SAFETY
# ──────────────────────────────────────────────

class SafetyValidator:
    def __init__(self, allowed_user: int = ALLOWED_USER) -> None:
        self.allowed_user = allowed_user
        self.confirm_required_cmds = [CommandType.RESTART_SERVICE]

    def validate(self, command: ParsedCommand, user_id: int) -> Tuple[bool, Optional[str]]:
        if user_id != self.allowed_user:
            return False, "⛔ Unauthorized"
        return True, None

    def needs_confirmation(self, command: ParsedCommand) -> bool:
        return command.type in self.confirm_required_cmds


# ──────────────────────────────────────────────
# SQLITE PERSISTENCE
# ──────────────────────────────────────────────

class Memory:
    """SQLite-backed persistent memory."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT,
                command_type TEXT,
                params TEXT,
                success INTEGER,
                duration REAL,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE,
                command_type TEXT
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE,
                content TEXT,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                text TEXT,
                trigger_at TEXT,
                sent INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id);
            CREATE INDEX IF NOT EXISTS idx_facts_topic ON facts(topic);
            CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(sent, trigger_at);
        """)
        self._conn.commit()

    def save_message(self, chat_id: int, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, datetime.now().isoformat()),
        )
        self._conn.commit()

    def load_context(self, chat_id: int, limit: int = CONTEXT_LOAD_ON_START) -> List[Tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return list(reversed(rows))

    def clear_context(self, chat_id: int) -> None:
        self._conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        self._conn.commit()

    def save_command(self, raw_text: str, cmd_type: str, params: str,
                     success: bool, duration: float) -> None:
        self._conn.execute(
            "INSERT INTO commands (raw_text, command_type, params, success, duration, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (raw_text, cmd_type, params, int(success), duration, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_recent_commands(self, limit: int = 20) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT raw_text, command_type, success, duration FROM commands ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"text": r[0], "type": r[1], "success": bool(r[2]), "duration": r[3]} for r in rows]

    def get_commands_since(self, since_iso: str, limit: int = 100) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT raw_text, command_type, success, duration, timestamp FROM commands "
            "WHERE timestamp >= ? ORDER BY id DESC LIMIT ?",
            (since_iso, limit),
        ).fetchall()
        return [
            {"text": r[0], "type": r[1], "success": bool(r[2]), "duration": r[3], "timestamp": r[4]}
            for r in rows
        ]

    def save_pattern(self, keyword: str, cmd_type: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO patterns (keyword, command_type) VALUES (?, ?)",
            (keyword, cmd_type),
        )
        self._conn.commit()

    def get_patterns(self) -> List[Tuple[str, str]]:
        return self._conn.execute("SELECT keyword, command_type FROM patterns").fetchall()

    def save_fact(self, topic: str, content: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO facts (topic, content, timestamp) VALUES (?, ?, ?)",
            (topic, content, datetime.now().isoformat()),
        )
        self._conn.commit()

    def search_facts(self, query: str, limit: int = 5) -> List[str]:
        words = query.lower().split()[:5]
        if not words:
            return []
        conditions = " OR ".join(["topic LIKE ? OR content LIKE ?"] * len(words))
        params = []
        for w in words:
            params.extend([f"%{w}%", f"%{w}%"])
        rows = self._conn.execute(
            f"SELECT content FROM facts WHERE {conditions} LIMIT ?",
            params + [limit],
        ).fetchall()
        return [r[0] for r in rows]

    def get_all_facts(self) -> List[Tuple[str, str]]:
        return self._conn.execute("SELECT topic, content FROM facts").fetchall()

    def delete_fact(self, topic: str) -> int:
        """Remove fact(s) by topic. Returns count deleted. Topic is matched case-insensitively."""
        cur = self._conn.execute(
            "DELETE FROM facts WHERE LOWER(topic) = LOWER(?)", (topic,)
        )
        self._conn.commit()
        return cur.rowcount

    def add_reminder(self, chat_id: int, text: str, trigger_at: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO reminders (chat_id, text, trigger_at, sent) VALUES (?, ?, ?, 0)",
            (chat_id, text, trigger_at),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_due_reminders(self, now_iso: str) -> List[Tuple[int, int, str, str]]:
        return self._conn.execute(
            "SELECT id, chat_id, text, trigger_at FROM reminders "
            "WHERE sent = 0 AND trigger_at <= ? ORDER BY trigger_at ASC",
            (now_iso,),
        ).fetchall()

    def mark_reminder_sent(self, reminder_id: int) -> None:
        self._conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
        self._conn.commit()

    def prune_old_facts(self, days: int = 90) -> int:
        """Delete facts whose timestamp is older than `days` days. Returns count deleted."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cur = self._conn.execute(
            "DELETE FROM facts WHERE timestamp IS NOT NULL AND timestamp < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cur.rowcount

    def get_last_successful_command(self) -> Optional[Tuple[str, str, str]]:
        """
        Return (raw_text, command_type, params_json) of the most recent
        successful, non-meta command. Used to recover last_command after restart.
        """
        row = self._conn.execute(
            "SELECT raw_text, command_type, params FROM commands "
            "WHERE success = 1 AND command_type NOT IN ('repeat', 'cancel', 'none') "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row

    def is_healthy(self) -> bool:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False


# ──────────────────────────────────────────────
# RAG-LITE: Obsidian search for context
# ──────────────────────────────────────────────

class ObsidianRAG:
    """Lightweight RAG: search Obsidian vault + extract relevant excerpts."""

    def __init__(self, vault_path: Path, logger) -> None:
        self.vault = vault_path
        self.log = logger
        self.rg = "/opt/homebrew/bin/rg"

    def search(self, query: str, max_results: int = 3) -> List[str]:
        if not self.vault.exists():
            return []

        # Extract key terms (skip stop words)
        stop = {"и", "в", "на", "с", "что", "как", "это", "не", "но", "а", "о", "от", "до", "по",
                "the", "a", "an", "is", "are", "was", "how", "what", "why", "do", "does"}
        words = [w for w in query.lower().split() if w not in stop and len(w) > 2]
        if not words:
            return []

        try:
            # Search with multiple terms for better results
            search_term = "|".join(words[:4])
            r = subprocess.run(
                [self.rg, "-i", "--max-count", "3", "-A", "8",
                 "--sort-path", search_term, str(self.vault),
                 "--glob", "*.md", "--no-filename", "--no-line-number"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0 or not r.stdout.strip():
                return []

            # Split into chunks, clean up
            chunks = []
            for block in r.stdout.split("--\n"):
                text = block.strip()[:600]
                if text and len(text) > 30:
                    # Clean up ragged newlines
                    text = re.sub(r'\n{3,}', '\n\n', text)
                    chunks.append(text)

            return chunks[:max_results]
        except subprocess.TimeoutExpired:
            self.log.warning("RAG search timeout")
            return []
        except Exception as e:
            self.log.warning("RAG error: %s", e)
            return []

    def read_note(self, name: str) -> Optional[str]:
        """Read a specific note by fuzzy name match."""
        try:
            r = subprocess.run(
                [self.rg, "-i", "--files-with-matches", "-g", f"*{name}*.md",
                 str(self.vault)],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                fpath = Path(r.stdout.strip().split("\n")[0])
                content = fpath.read_text(encoding="utf-8")[:3000]
                return content
        except Exception:
            pass
        return None


# ──────────────────────────────────────────────
# SMART SYSTEM PROMPT BUILDER
# ──────────────────────────────────────────────

def build_system_prompt(
    rag_context: Optional[str] = None,
    recent_commands: Optional[List[Dict]] = None,
    facts: Optional[List[str]] = None,
    memory_recall: Optional[str] = None,
) -> str:
    """Dynamic system prompt with context injection."""

    prompt = """Ты — Geek26, цифровой помощник Димы. Второе я в цифровом мире.

## Личность
- Говори прямо, без воды и "Отличный вопрос!"
- Отвечай на языке вопроса (русский/английский)
- Юмор уместен, но по делу
- Не знаешь — скажи прямо. Не придумывай.
- Команда не из списка — предложи что МОЖЕШЬ

## О Диме
- 36 лет, из Костромы, живёт в EST timezone
- Работает с Mac mini M4 только мышкой (БЕЗ клавиатуры)
- Ценит: приватность, чёткость, скорость
- Ненавидит: воду, долгие вступления, "я ИИ"

## Твои модели
- Qwen 3.5 9B — умная, для сложных ответов
- Gemma 4 E4B — быстрая, для простых
- Обе локальные (Ollama), работают без интернета

## Что ты умеешь (команды)
**Mac:** открой URL, обнови страницу, скачай файл, скопируй в буфер, скриншот
**Obsidian:** запиши заметку, найди в заметках, прочитай заметку
**GitHub:** покажи коммиты, статус, открой репо
**Graphify:** поиск по графу знаний, связи между сущностями
**Система:** проверь сервисы, перезапусти, место на диске, память, процессы, не усыплять мак
**Медиа:** OCR на фото, транскрипция голосовых
**Сложные задачи:** эскалируй к Geek (OpenClaw)

## Формат ответов
- Коротко и по делу
- Результат сразу
- Ошибка → что случилось + альтернатива
- Для объяснений: структурируй (списки, абзацы)"""

    if memory_recall:
        prompt += f"\n\n## Ранее в разговоре (память)\n{memory_recall}"

    if facts:
        prompt += "\n\n## То что я знаю\n" + "\n".join(f"- {f}" for f in facts[:5])

    if rag_context:
        prompt += f"\n\n## Контекст из Obsidian\n{rag_context}"

    if recent_commands:
        lines = []
        for cmd in recent_commands[-5:]:
            status = "✅" if cmd["success"] else "❌"
            lines.append(f"- {status} {cmd['text'][:60]}")
        if lines:
            prompt += "\n\n## Недавние команды\n" + "\n".join(lines)

    return prompt


# ──────────────────────────────────────────────
# QUERY COMPLEXITY ROUTER
# ──────────────────────────────────────────────

class ComplexityRouter:
    TRIVIAL = [
        r'^(привет|здарова|йо|хай|hi|hello|hey|ок|окей|спасибо|thanks|да|нет|\+|\-|ok|👍|👌)$',
        r'^(как\s+дела|что\s+нового|как\s+ты|how\s+are|what\'?s\s+up)',
        r'^(пока|bye|давай|до\s+свидания|увидимся)',
        r'^/\w+$',
    ]

    COMPLEX = [
        r'(?:объясни|explain|расскажи.*про|tell\s+me\s+about|как\s+работает|how\s+does)',
        r'(?:почему|why|зачем|в\s+чём\s+разница|difference)',
        r'(?:сравни|compare|vs|против|versus)',
        r'(?:предложи|suggest|посоветуй|recommend|идея|idea)',
        r'(?:что\s+ты\s+думаешь|what\s+do\s+you\s+think|мнение|opinion)',
        r'(?:помоги|help\s+me|подскажи.*как|how\s+to|как\s+настроить)',
        r'(?:оцени|assess|rate|рейтинг|ranking|за\s+и\s+против|pros\s+and\s+cons)',
        r'(?:подробнее|more\s+details|детальн|elaborate)',
        r'(?:лучший|best|worst|худший|топ\s+\d)',
    ]

    def classify(self, text: str) -> str:
        text_lower = text.lower().strip()
        for pattern in self.TRIVIAL:
            if re.search(pattern, text_lower):
                return "trivial"
        for pattern in self.COMPLEX:
            if re.search(pattern, text_lower):
                return "complex"
        if len(text.split()) > 8:
            return "complex"
        return "simple"


# ──────────────────────────────────────────────
# LLM BRAIN (v3.2)
# ──────────────────────────────────────────────

class OllamaBrain:
    """Smart brain: adaptive routing + RAG + memory recall + facts."""

    def __init__(self, memory: Memory, logger) -> None:
        self.memory = memory
        self.log = logger
        self.chat_history: deque = deque(maxlen=CONTEXT_SIZE)
        self.rag = ObsidianRAG(OBSIDIAN_VAULT, logger)
        self.router = ComplexityRouter()
        self.model_stats: Dict[str, Dict] = {
            name: {"wins": 0, "total": 0}
            for name in MODELS
        }

    def load_context(self, chat_id: int) -> None:
        rows = self.memory.load_context(chat_id)
        for role, content in rows:
            self.chat_history.append((role, content))
        self.log.info("Loaded %d messages from SQLite", len(rows))

    def check_ollama(self) -> bool:
        try:
            r = requests.get("http://localhost:11434/api/ps", timeout=5)
            return r.ok
        except Exception:
            return False

    def unload_model(self, model: str) -> None:
        """Keep models warm for 5 minutes."""
        try:
            requests.post(OLLAMA_GEN, json={"model": model, "keep_alive": "5m", "stream": False}, timeout=10)
        except Exception:
            pass

    def ollama_chat(self, model: str, messages: List[Dict], timeout: int = 120) -> Optional[str]:
        for attempt in range(LLM_RETRIES):
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": "5m",
                    "options": {"num_ctx": 4096},
                }
                if "qwen" in model.lower():
                    payload["think"] = False

                r = requests.post(OLLAMA_CHAT, json=payload, timeout=timeout)
                data = r.json()
                return data.get("message", {}).get("content", "").strip()
            except requests.Timeout:
                self.log.warning("Model %s timeout (%d/%d)", model, attempt + 1, LLM_RETRIES)
            except Exception as e:
                self.log.warning("Model %s error (%d/%d): %s", model, attempt + 1, LLM_RETRIES, e)
            if attempt < LLM_RETRIES - 1:
                time.sleep(LLM_BACKOFF[attempt] if attempt < len(LLM_BACKOFF) else 10)
        return None

    def summarize_history_if_needed(self, chat_id: int) -> bool:
        """
        Compact long in-memory chat history into a short hidden summary.
        Returns True when compaction happened.
        """
        if len(self.chat_history) <= 15:
            return False

        recent = list(self.chat_history)[-10:]
        transcript = "\n".join(f"{role}: {content[:500]}" for role, content in recent)
        messages = [
            {"role": "system", "content": "Сделай краткое резюме диалога для памяти бота. Только факты, решения, открытые вопросы."},
            {"role": "user", "content": transcript},
        ]
        model = "gemma4:e4b" if "gemma4:e4b" in MODELS else list(MODELS.keys())[0]
        summary = self.ollama_chat(model, messages, timeout=15)
        self.unload_model(model)
        if not summary:
            return False

        summary = summary[:1500]
        try:
            self.memory.save_fact("summary", summary)
        except Exception as e:
            self.log.warning("save summary fact failed: %s", e)

        self.chat_history.clear()
        self.chat_history.append(("system", f"[summary] {summary}"))
        try:
            self.memory.clear_context(chat_id)
            self.memory.save_message(chat_id, "system", f"[summary] {summary}")
        except Exception as e:
            self.log.warning("persist summary context failed: %s", e)
        self.log.info("Compacted chat_history into summary (%d chars)", len(summary))
        return True

    def ollama_chat_stream(self, model: str, messages: List[Dict],
                           on_chunk: Optional[Callable[[str], None]] = None,
                           timeout: int = 120) -> Optional[str]:
        """
        Streaming variant. Single attempt (no retry — caller may retry whole flow).
        on_chunk(full_text_so_far) is called as new tokens arrive. Returns
        the complete text when done, or None on hard failure.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "5m",
            "options": {"num_ctx": 4096},
        }
        if "qwen" in model.lower():
            payload["think"] = False

        full = ""
        try:
            r = requests.post(OLLAMA_CHAT, json=payload, stream=True, timeout=timeout)
            for raw in r.iter_lines():
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    full += chunk
                    if on_chunk is not None:
                        try:
                            on_chunk(full)
                        except Exception as e:
                            self.log.warning("on_chunk callback error: %s", e)
                if data.get("done"):
                    break
            return full.strip() or None
        except requests.Timeout:
            self.log.warning("Stream %s timeout", model)
            return full.strip() if full else None
        except Exception as e:
            self.log.warning("Stream %s error: %s", model, e)
            return full.strip() if full else None

    def warm_models(self) -> None:
        """
        Best-effort: send a tiny dummy request to each model so Ollama loads
        them into VRAM. Runs synchronously but each call has a short timeout.
        Called once at bot startup to avoid 10-15s cold-start on first message.
        """
        for model in MODELS:
            try:
                requests.post(
                    OLLAMA_GEN,
                    json={"model": model, "prompt": "ok", "stream": False, "keep_alive": "5m"},
                    timeout=20,
                )
                self.log.info("Warmed: %s", MODELS[model]["short"])
            except Exception as e:
                self.log.info("Warm %s skipped: %s", model, e)

    def _build_messages(self, user_text: str, complexity: str) -> List[Dict]:
        rag_context = None
        recent_cmds = None
        facts = None
        memory_recall = None

        if complexity in ("complex", "simple"):
            # RAG from Obsidian
            rag_chunks = self.rag.search(user_text, max_results=3)
            if rag_chunks:
                rag_context = "\n\n".join(rag_chunks)

            # Facts from DB
            facts = self.memory.search_facts(user_text, limit=3)

            recent_cmds = self.memory.get_recent_commands(5)

        # Memory recall: last few messages for continuity
        if len(self.chat_history) > 2:
            last_msgs = list(self.chat_history)[-4:]
            recall_lines = [f"{'👤' if r == 'user' else '🤖'}: {c[:80]}" for r, c in last_msgs]
            memory_recall = "\n".join(recall_lines)

        system = build_system_prompt(rag_context, recent_cmds, facts, memory_recall)

        messages = [{"role": "system", "content": system}]
        for role, content in self.chat_history:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})
        return messages

    def query_single(self, model: str, user_text: str, complexity: str) -> Tuple[Optional[str], float]:
        messages = self._build_messages(user_text, complexity)
        t0 = time.time()
        resp = self.ollama_chat(model, messages, timeout=MODELS[model]["timeout"])
        elapsed = time.time() - t0
        self.unload_model(model)

        if resp:
            speed = len(resp) / elapsed if elapsed > 0 else 0
            self.log.info("  %s: %.1f tok/s, %d chars", MODELS[model]["short"], speed, len(resp))
            return resp, speed
        return None, 0

    def query_both(self, user_text: str, complexity: str) -> Tuple[str, str, str]:
        results = {}
        for model_name, cfg in MODELS.items():
            resp, speed = self.query_single(model_name, user_text, complexity)
            if resp:
                results[model_name] = (resp, speed)
            else:
                results[model_name] = ("⏱️ Таймаут", 0)
                self.log.info("  %s: FAILED", cfg["short"])

        valid = {k: v for k, v in results.items() if v[1] > 0}
        if not valid:
            return "", "⚠️ Обе модели недоступны.", ""

        best_name = max(valid, key=lambda k: self._score(user_text, valid[k][0], valid[k][1], k))
        best_resp = valid[best_name][0]

        for mn in valid:
            self.model_stats[mn]["total"] += 1
        self.model_stats[best_name]["wins"] += 1

        details_parts = []
        for mn, (resp, spd) in results.items():
            sc = self._score(user_text, resp, spd, mn) if spd > 0 else 0
            details_parts.append(f"{MODELS[mn]['emoji']} {MODELS[mn]['short']}: {sc}/100 ({spd:.0f} tok/s)")
        details = "\n".join(details_parts)

        return best_name, best_resp, details

    def _score(self, question: str, answer: str, speed: float, model: str) -> float:
        if not answer or answer.startswith("⏱️"):
            return 0
        score = 25.0
        length = len(answer)
        if 30 < length < 2000:
            score += 25
        elif 2000 <= length < 4000:
            score += 15
        elif length > 0:
            score += 5
        if speed > 25:
            score += 15
        elif speed > 15:
            score += 10
        elif speed > 5:
            score += 5
        q_words = set(question.lower().split()) - {"и", "в", "на", "с", "что", "как", "the", "a", "is"}
        a_words = set(answer.lower().split())
        if q_words:
            overlap = len(q_words & a_words) / len(q_words)
            score += overlap * 25
        if any(m in answer for m in ["•", "-", "1.", "2.", "*"]):
            score += 5
        if "```" in answer or "`" in answer:
            score += 5
        stats = self.model_stats.get(model, {})
        if stats.get("total", 0) > 3:
            win_rate = stats["wins"] / stats["total"]
            if win_rate > 0.6:
                score += 5
        return min(100, score)

    def process_chat(self, text: str) -> str:
        complexity = self.router.classify(text)
        self.log.info("Complexity: %s | '%s'", complexity, text[:60])

        if complexity == "trivial":
            # Fast path: try fastest model first, fallback to second
            for model_name in MODELS:
                resp, speed = self.query_single(model_name, text, "trivial")
                if resp:
                    self.chat_history.append(("user", text))
                    self.chat_history.append(("assistant", resp))
                    # Feature 3: auto-extract facts (gated + async)
                    self._maybe_auto_save_facts_async(resp, complexity)
                    return resp
            return "⚠️ Модели недоступны. Попробуй через минуту."

        best_name, best_resp, details = self.query_both(text, complexity)
        if not best_resp or best_resp.startswith("⚠️"):
            return best_resp

        self.chat_history.append(("user", text))
        self.chat_history.append(("assistant", best_resp))

        # Feature 3: auto-extract facts from the assistant's response
        self._maybe_auto_save_facts_async(best_resp, complexity)

        if complexity == "complex":
            cfg = MODELS[best_name]
            return f"🏆 {cfg['short']}\n{details}\n{'─' * 30}\n\n{best_resp}"

        return best_resp

    def process_chat_streaming(self, text: str,
                               on_chunk: Optional[Callable[[str], None]] = None) -> str:
        """
        Like process_chat but uses ollama streaming so the caller can update
        the Telegram message as tokens arrive. No model comparison — picks
        gemma for trivial, qwen for everything else.
        """
        complexity = self.router.classify(text)
        self.log.info("Complexity (stream): %s | '%s'", complexity, text[:60])

        # Pick a single model — gemma for trivial / fast, qwen for thoughtful.
        if complexity == "trivial":
            preferred = "gemma4:e4b"
        else:
            preferred = "qwen3.5:9b"
        model_name = preferred if preferred in MODELS else list(MODELS.keys())[0]

        messages = self._build_messages(text, complexity)
        t0 = time.time()
        full = self.ollama_chat_stream(
            model_name, messages, on_chunk=on_chunk,
            timeout=MODELS[model_name]["timeout"],
        )
        elapsed = time.time() - t0
        self.unload_model(model_name)

        if not full:
            return "⚠️ Модель недоступна. Попробуй через минуту."

        speed = len(full) / elapsed if elapsed > 0 else 0
        self.log.info("Stream done: %s, %.1fs, %d chars (~%.0f tok/s)",
                      MODELS[model_name]["short"], elapsed, len(full), speed)

        self.chat_history.append(("user", text))
        self.chat_history.append(("assistant", full))

        # Feature 3: auto-extract facts (gated + async)
        self._maybe_auto_save_facts_async(full, complexity)

        return full

    def get_llm_hint(self, text: str) -> Optional[str]:
        messages = [
            {"role": "system", "content": "Classify: reply ONE word. open_url, download, obsidian, git, graphify, system, or chat."},
            {"role": "user", "content": text},
        ]
        fastest = list(MODELS.keys())[0]
        result = self.ollama_chat(fastest, messages, timeout=30)
        self.unload_model(fastest)
        return result

    # ── Feature 3: Auto-fact extraction ──

    def extract_facts(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract important facts from text using fast model (gemma4:e4b).
        Single attempt, hard 15s timeout. Returns list of (topic, content) tuples.
        Format expected from LLM: 'topic: content', one per line, or 'none'.
        """
        if not text or len(text.strip()) < 30:
            return []

        # Pick the fastest model — prefer gemma if available
        fast_model = "gemma4:e4b" if "gemma4:e4b" in MODELS else list(MODELS.keys())[0]

        prompt = (
            "Извлеки ВАЖНЫЕ факты из текста ниже в формате 'topic: content'. "
            "Один факт на строку. Только: имена, даты, числа, предпочтения, "
            "решения. Без воды, без объяснений. Если фактов нет — ответь 'none'.\n\n"
            f"Текст:\n{text[:1500]}"
        )
        messages = [
            {"role": "system", "content": "Ты извлекаешь факты. Отвечай кратко, по формату."},
            {"role": "user", "content": prompt},
        ]

        # Direct POST without retries — best-effort, skip on timeout
        try:
            payload = {
                "model": fast_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "5m",
                "options": {"num_ctx": 2048},
            }
            if "qwen" in fast_model.lower():
                payload["think"] = False

            r = requests.post(OLLAMA_CHAT, json=payload, timeout=15)
            data = r.json()
            resp = data.get("message", {}).get("content", "").strip()
        except requests.Timeout:
            self.log.info("extract_facts: timeout, skipping")
            return []
        except Exception as e:
            self.log.warning("extract_facts: %s", e)
            return []

        if not resp:
            return []
        # Common "no facts" markers
        first_word = resp.lower().split(None, 1)[0] if resp.split() else ""
        if first_word in ("none", "нет", "—", "-"):
            return []

        facts: List[Tuple[str, str]] = []
        for raw_line in resp.split("\n"):
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            # Strip bullet/number prefixes
            line = re.sub(r'^[\-\*•\d\.\)\]]+\s*', '', line)
            topic, _, content = line.partition(":")
            topic = topic.strip().strip('"\'`*_').lower()[:100]
            content = content.strip().strip('"\'`*_')[:500]
            if not topic or not content:
                continue
            if topic in ("none", "нет", "facts", "factы", "topic"):
                continue
            facts.append((topic, content))
            if len(facts) >= 5:
                break
        return facts

    def _auto_save_facts(self, response_text: str) -> None:
        """Best-effort: extract facts from response and persist them."""
        try:
            facts = self.extract_facts(response_text)
            if not facts:
                return
            for topic, content in facts:
                try:
                    self.memory.save_fact(topic, content)
                except Exception as e:
                    self.log.warning("save_fact failed (%s): %s", topic, e)
            self.log.info("Auto-saved %d fact(s) from response", len(facts))
        except Exception as e:
            self.log.warning("auto_save_facts: %s", e)

    def _maybe_auto_save_facts_async(self, response_text: str, complexity: str) -> None:
        """
        Gate + async wrapper for fact extraction:
        - Skip on trivial responses or short text (<100 chars) — avoids LLM
          calls on greetings like "привет" / "спасибо".
        - Run in a daemon thread so the user sees the reply immediately and
          fact extraction happens in the background.
        """
        if not response_text or len(response_text.strip()) < 100:
            return
        if complexity == "trivial":
            return
        try:
            t = threading.Thread(
                target=self._auto_save_facts,
                args=(response_text,),
                daemon=True,
                name="auto-save-facts",
            )
            t.start()
        except Exception as e:
            # Fallback: run inline if threading fails for some reason
            self.log.warning("Threaded fact extraction failed (%s); running sync", e)
            self._auto_save_facts(response_text)
