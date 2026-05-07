#!/usr/bin/env python3
"""Geek26 Bot v3 — Main loop with watchdog and graceful shutdown."""

from __future__ import annotations

import html
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from typing import Optional, Tuple

from config import (
    ALLOWED_USER, BOT_TOKEN, MAX_COMMANDS_PER_MIN, MODELS,
    POLL_TIMEOUT, REQUEST_TIMEOUT,
    TELEGRAM_URL, TELEGRAM_FILE_URL, WATCHDOG_INTERVAL, MAX_CONSECUTIVE_ERRORS,
    DISK_WARNING_PCT, BotSettings, setup_logging, SHELL_SCRIPTS, OLLAMA_CHAT,
)
from brain import (
    CommandParser, SafetyValidator, OllamaBrain, Memory,
    CommandType, ParsedCommand,
)
from executor import CommandExecutor

# Hard limits (Telegram caps message text at 4096; user text capped to keep
# Ollama context healthy at num_ctx=4096).
TG_MAX_LEN = 4000
USER_TEXT_MAX_LEN = 6000

# Pending-confirmation TTL — abandon stale prompts after this many seconds.
PENDING_CONFIRM_TTL = 60

# Background-task timer for facts pruning (every Nth iteration).
FACTS_PRUNE_INTERVAL_ITERS = WATCHDOG_INTERVAL * 30  # ≈ once per ~hour
FACTS_PRUNE_DAYS = 90

# ──────────────────────────────────────────────
# TELEGRAM API
# ──────────────────────────────────────────────

# Network-level retries for transient Telegram failures (5xx, timeouts).
# Long-polling getUpdates is excluded from retry — the main loop already
# handles that via its own backoff path.
TG_RETRY_ATTEMPTS = 3
TG_RETRY_BACKOFF = [1, 3, 6]


def tg(method: str, **kwargs):
    """
    Call a Telegram API method.

    For non-polling calls, retry on transient errors (Timeout, 5xx). For
    long-polling getUpdates, we keep the original semantics — a single
    attempt — so the main loop's backoff path stays in charge.
    """
    url = TELEGRAM_URL.format(token=BOT_TOKEN, method=method)
    poll_timeout = kwargs.get("timeout", 0)
    conn_timeout = max(REQUEST_TIMEOUT, poll_timeout + 15)
    is_polling = method == "getUpdates" and poll_timeout > 0

    if is_polling:
        r = requests.post(url, json=kwargs, timeout=conn_timeout)
        return r.json()

    last_exc: Optional[Exception] = None
    for attempt in range(TG_RETRY_ATTEMPTS):
        try:
            r = requests.post(url, json=kwargs, timeout=conn_timeout)
            # Retry only on server-side errors; let the caller see 4xx as-is.
            if 500 <= r.status_code < 600 and attempt < TG_RETRY_ATTEMPTS - 1:
                time.sleep(TG_RETRY_BACKOFF[attempt])
                continue
            return r.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if attempt < TG_RETRY_ATTEMPTS - 1:
                time.sleep(TG_RETRY_BACKOFF[attempt])
                continue
            # Final attempt failed — return a synthetic error payload so
            # callers can keep going without raising.
            return {"ok": False, "error": str(last_exc)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": str(last_exc) if last_exc else "unknown"}


# Inline-code/code-block markdown → Telegram HTML.
_BACKTICK_BLOCK_RE = re.compile(r"```([\s\S]*?)```")
_BACKTICK_INLINE_RE = re.compile(r"`([^`\n]+)`")


def _to_html(text: str) -> str:
    """
    Convert plaintext-with-backticks (what the LLM tends to emit) into safe
    Telegram HTML so triple-backtick blocks render as <pre> and single
    backticks render as <code>. Other characters are HTML-escaped.
    """
    if not text:
        return ""
    safe = html.escape(text, quote=False)
    safe = _BACKTICK_BLOCK_RE.sub(lambda m: f"<pre>{m.group(1)}</pre>", safe)
    safe = _BACKTICK_INLINE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", safe)
    return safe


def send_message(chat_id: int, text: str, parse_mode: Optional[str] = "HTML") -> bool:
    """
    Send a message, splitting if too long. Defaults to HTML rendering with
    fallback to plain text on Telegram's 400 (e.g. malformed HTML).
    """
    if not text:
        return False

    def _post(chunk: str, mode: Optional[str]) -> bool:
        body = _to_html(chunk) if mode == "HTML" else chunk
        kwargs = {"chat_id": chat_id, "text": body}
        if mode:
            kwargs["parse_mode"] = mode
        r = tg("sendMessage", **kwargs)
        if r.get("ok"):
            return True
        # Fall back: drop parse_mode and resend the raw chunk.
        if mode:
            r2 = tg("sendMessage", chat_id=chat_id, text=chunk)
            return r2.get("ok", False)
        return False

    if len(text) <= TG_MAX_LEN:
        return _post(text, parse_mode)

    ok = True
    for i in range(0, len(text), TG_MAX_LEN):
        chunk = text[i:i + TG_MAX_LEN]
        ok = _post(chunk, parse_mode) and ok
        time.sleep(0.5)
    return ok


def send_message_result(chat_id: int, text: str,
                        parse_mode: Optional[str] = "HTML") -> Optional[int]:
    """Send one Telegram message and return message_id. Long messages fall back to send_message()."""
    if not text:
        return None
    if len(text) > TG_MAX_LEN:
        last_id = None
        for i in range(0, len(text), TG_MAX_LEN):
            last_id = send_message_result(chat_id, text[i:i + TG_MAX_LEN], parse_mode=parse_mode)
            time.sleep(0.5)
        return last_id
    body = _to_html(text) if parse_mode == "HTML" else text
    kwargs = {"chat_id": chat_id, "text": body}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    r = tg("sendMessage", **kwargs)
    if r.get("ok"):
        return r.get("result", {}).get("message_id")
    if parse_mode:
        r2 = tg("sendMessage", chat_id=chat_id, text=text)
        if r2.get("ok"):
            return r2.get("result", {}).get("message_id")
    return None


def edit_message(chat_id: int, message_id: int, text: str,
                 parse_mode: Optional[str] = "HTML") -> bool:
    """
    Edit a previously-sent Telegram message in place (≤4096 chars).
    Used by the streaming path to update the '🤔 Думаю...' placeholder
    with partial / final assistant text. Falls back to plain text if HTML
    is rejected.
    """
    text = text[:4096]
    body = _to_html(text) if parse_mode == "HTML" else text
    kwargs = {"chat_id": chat_id, "message_id": message_id, "text": body}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    try:
        r = tg("editMessageText", **kwargs)
        if r.get("ok"):
            return True
        # Common Telegram quirk: 400 "message is not modified" when content
        # didn't actually change — treat as success so we don't churn edits.
        desc = (r.get("description") or "").lower()
        if "not modified" in desc:
            return True
        if parse_mode:
            r2 = tg("editMessageText",
                    chat_id=chat_id, message_id=message_id, text=text)
            return r2.get("ok", False)
        return False
    except Exception:
        return False
    except Exception:
        return False


def edit_message_reply_markup(chat_id: int, message_id: int, reply_markup: dict) -> bool:
    try:
        r = tg(
            "editMessageReplyMarkup",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
        return r.get("ok", False)
    except Exception:
        return False


def answer_callback(callback_id: str, text: str = "") -> None:
    try:
        kwargs = {"callback_query_id": callback_id}
        if text:
            kwargs["text"] = text
        tg("answerCallbackQuery", **kwargs)
    except Exception:
        pass


def send_file(chat_id: int, file_path: str, caption: str = "") -> bool:
    """
    Feature 4: upload a document (any file) back to the user via multipart.
    Returns True on success.
    """
    fp = Path(file_path)
    if not fp.exists() or not fp.is_file():
        return False
    url = TELEGRAM_URL.format(token=BOT_TOKEN, method="sendDocument")
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]
    try:
        with open(fp, "rb") as f:
            r = requests.post(
                url,
                data=data,
                files={"document": (fp.name, f)},
                timeout=120,
            )
        return r.json().get("ok", False)
    except Exception:
        return False


def send_photo(chat_id: int, file_path: str, caption: str = "") -> bool:
    """
    Feature 4: upload a photo via multipart (proper Telegram photo, not a file).
    Returns True on success.
    """
    fp = Path(file_path)
    if not fp.exists() or not fp.is_file():
        return False
    url = TELEGRAM_URL.format(token=BOT_TOKEN, method="sendPhoto")
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]
    try:
        with open(fp, "rb") as f:
            r = requests.post(
                url,
                data=data,
                files={"photo": (fp.name, f)},
                timeout=120,
            )
        return r.json().get("ok", False)
    except Exception:
        return False


_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _sanitize_local_name(file_path: str) -> str:
    """
    Build a safe filename for /tmp from a Telegram-supplied file_path. The
    server-supplied path is trusted, but hardening here costs nothing —
    keep only [a-zA-Z0-9._-], cap length, and forbid leading dots.
    """
    flat = file_path.replace("/", "_").replace("\\", "_")
    safe = _SAFE_FILENAME_RE.sub("_", flat).strip("._")[:120] or "file"
    return safe


def download_file(file_path: str) -> Optional[str]:
    """
    Download a Telegram-hosted file to /tmp using a sanitized name.
    Returns the local path or None on failure.
    """
    url = TELEGRAM_FILE_URL.format(token=BOT_TOKEN, path=file_path)
    local = f"/tmp/geek26_{_sanitize_local_name(file_path)}"
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(local, "wb") as f:
            f.write(r.content)
        return local
    except Exception:
        return None


# ──────────────────────────────────────────────
# BOT
# ──────────────────────────────────────────────

class Geek26Bot:
    def __init__(self) -> None:
        self.settings = BotSettings()
        self.log = setup_logging()
        self.memory = Memory(self.settings.db_file)
        self.parser = CommandParser(self.memory)
        self.safety = SafetyValidator()
        self.brain = OllamaBrain(self.memory, self.log)
        self.executor = CommandExecutor(self.settings, self.log, self.memory)

        self.offset = 0
        self.iteration = 0
        self.consecutive_errors = 0
        # chat_id -> (ParsedCommand, expires_at_epoch)
        self.pending_confirm: dict = {}
        # chat_id -> experience_id awaiting a textual correction after 👎.
        self.pending_corrections: dict = {}
        # Filled by process_message(show_thinking=False) when caller must send
        # the LLM response itself and then attach feedback buttons.
        self._pending_llm_feedback: Optional[dict] = None
        self.current_topic: Optional[str] = None
        # Feature 2: last successful (non-REPEAT/CANCEL) command, for "повтори"/"отмени"
        self.last_command: Optional[ParsedCommand] = None
        self.running = True

        # Per-chat sliding window of recent message timestamps for rate limiting.
        # chat_id -> deque[float epoch seconds]
        self._rate_window: dict = {}

        # Load context from SQLite
        self.brain.load_context(ALLOWED_USER)

        # Level 2: recover the most recent successful command so "повтори"
        # works across restarts.
        self._restore_last_command()

        # Level 2: warm both models in the background so the first chat
        # doesn't pay a 10-15s cold-start penalty.
        try:
            import threading as _t
            _t.Thread(target=self.brain.warm_models, daemon=True,
                      name="warm-models").start()
        except Exception as e:
            self.log.warning("warm_models thread failed: %s", e)

        # Graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _restore_last_command(self) -> None:
        """Reconstruct last_command from the most recent successful audit row."""
        try:
            row = self.memory.get_last_successful_command()
            if not row:
                return
            raw_text, type_str, params_json = row
            try:
                cmd_type = CommandType(type_str)
            except ValueError:
                return
            try:
                params = json.loads(params_json) if params_json else {}
            except (TypeError, json.JSONDecodeError):
                params = {}
            self.last_command = ParsedCommand(cmd_type, params, 1.0, raw_text or "")
            self.log.info("Restored last_command: %s", cmd_type.value)
        except Exception as e:
            self.log.warning("_restore_last_command: %s", e)

    def _rate_limit_ok(self, chat_id: int) -> bool:
        """
        Sliding-window rate limit: at most MAX_COMMANDS_PER_MIN within the
        last 60 seconds per chat. Returns False if the chat is over its
        budget. Uses self._rate_window as a per-chat deque of timestamps.
        """
        now = time.time()
        win = self._rate_window.setdefault(chat_id, deque())
        cutoff = now - 60.0
        while win and win[0] < cutoff:
            win.popleft()
        if len(win) >= MAX_COMMANDS_PER_MIN:
            return False
        win.append(now)
        return True

    def _handle_signal(self, signum, frame):
        self.log.info("Received signal %s — shutting down gracefully", signum)
        self.running = False

    # ── Message Processing ──

    def process_message(self, text: str, user_id: int, chat_id: int,
                        show_thinking: bool = True) -> str:
        """
        Route message: command → executor, else → chat.

        show_thinking=True (default) makes the chat branch send a '🤔 Думаю...'
        placeholder, then stream the LLM reply into it via editMessageText.
        Disable in batch mode where the caller wraps replies.
        """
        text = text.strip()
        if not text:
            return ""

        # Truncate huge user input — keeps Ollama context healthy and
        # protects against accidental log dumps.
        if len(text) > USER_TEXT_MAX_LEN:
            text = text[:USER_TEXT_MAX_LEN] + "\n[…обрезано]"

        pending_exp = self.pending_corrections.pop(chat_id, None)
        if pending_exp is not None:
            learned = self._save_feedback_correction(pending_exp, text)
            if learned:
                keyword, cmd_type = learned
                return f"Запомнил correction. Паттерн: {keyword} → {cmd_type}"
            return "Запомнил correction."

        correction = self._parse_inline_correction(text)
        if correction:
            exp = self.memory.get_last_negative_experience(chat_id)
            if exp:
                learned = self._save_feedback_correction(int(exp["id"]), correction)
                if learned:
                    keyword, cmd_type = learned
                    return f"Запомнил correction. Паттерн: {keyword} → {cmd_type}"
                return "Запомнил correction."

        # ── Slash commands ─────────────────────────────────────────────
        if text.lower() == "/clear":
            self.brain.chat_history.clear()
            self.memory.clear_context(chat_id)
            return "🧹 Контекст очищен"

        if text.lower() == "/stats":
            return self._get_stats()

        if text.lower() == "/daily":
            return self._get_daily()

        if text.lower() == "/help":
            return self._get_help()

        if text.lower().startswith("/remember "):
            parts = text[10:].strip().split(None, 1)
            if len(parts) == 2:
                self.memory.save_fact(parts[0], parts[1])
                return f"🧠 Запомнил: {parts[0]}"
            return "Использование: /remember <тема> <содержание>"

        if text.lower() == "/facts":
            facts = self.memory.get_all_facts()
            if not facts:
                return "🧠 Пока ничего не запомнил"
            lines = [f"• {topic}: {content[:60]}" for topic, content in facts]
            return "🧠 Знаю:\n" + "\n".join(lines)

        if text.lower().startswith("/forget"):
            arg = text[7:].strip()
            if not arg:
                return "Использование: /forget <тема>  (или /forget all)"
            if arg.lower() == "all":
                rows = self.memory.get_all_facts()
                count = 0
                for topic, _ in rows:
                    count += self.memory.delete_fact(topic)
                return f"🗑 Забыл всё: {count} фактов"
            n = self.memory.delete_fact(arg)
            return f"🗑 Забыл '{arg}': {n} запис(ь/и)" if n else f"❓ Не нашёл '{arg}'"

        if text.lower() == "/last":
            if self.last_command is None:
                return "📭 Нет предыдущей команды"
            return (f"📌 Последняя команда: {self.last_command.type.value}\n"
                    f"params: {self.last_command.params}\n"
                    f"raw: {self.last_command.raw_text[:200]}")

        # ── Pending confirmation (with TTL) ────────────────────────────
        pc = self.pending_confirm.get(chat_id)
        if pc is not None:
            cmd, expires = pc
            if time.time() > expires:
                # Stale — quietly drop and treat the message as a fresh one
                self.pending_confirm.pop(chat_id, None)
            else:
                self.pending_confirm.pop(chat_id, None)
                if text.lower() in ("да", "yes", "y", "ок", "ok"):
                    ok, msg = self.executor.execute(cmd, user_id)
                    prefix = "♻️ Подтверждено — "
                    if ok:
                        self.last_command = cmd
                    self._maybe_send_attachment(chat_id)
                    return prefix + msg
                else:
                    return "❌ Отменено"

        # Parse command
        command = self.parser.parse(text)

        # ── Feature 2: contextual commands ──────────────────────────────
        if command.type == CommandType.REPEAT and command.confidence > 0.5:
            if self.last_command is None:
                return "❓ Нечего повторять. Сначала выполни какую-нибудь команду."
            repeat_cmd = ParsedCommand(
                CommandType.REPEAT,
                {"prev_command": self.last_command},
                command.confidence,
                text,
            )
            ok, msg = self.executor.execute(repeat_cmd, user_id)
            result = msg
            self.memory.save_message(chat_id, "user", text)
            self.memory.save_message(chat_id, "assistant", result)
            self._maybe_summarize_memory(chat_id)
            self._maybe_send_attachment(chat_id)
            return result

        if command.type == CommandType.CANCEL and command.confidence > 0.5:
            if chat_id in self.pending_confirm:
                self.pending_confirm.pop(chat_id)
                return "❌ Подтверждение отменено"
            cancel_cmd = ParsedCommand(
                CommandType.CANCEL,
                {"prev_command": self.last_command},
                command.confidence,
                text,
            )
            ok, msg = self.executor.execute(cancel_cmd, user_id)
            # If undo deleted the source command, clear last_command so a
            # subsequent "повтори" doesn't re-execute something undone.
            if ok and self.last_command is not None and \
               self.last_command.type == CommandType.OBSIDIAN_WRITE:
                self.last_command = None
            return msg

        if command.type.value != "none" and command.confidence > 0.5:
            ok, err = self.safety.validate(command, user_id)
            if not ok:
                return f"⛔ {err}"

            if command.type == CommandType.REMIND:
                command.params["chat_id"] = chat_id

            if self.safety.needs_confirmation(command):
                # Set TTL'd pending confirmation
                self.pending_confirm[chat_id] = (command, time.time() + PENDING_CONFIRM_TTL)
                desc = command.type.value.replace("_", " ")
                return (f"⚠️ Подтверди: {desc} {command.params}\n"
                        f"Ответь 'да' или 'нет'. (через {PENDING_CONFIRM_TTL}с истечёт)")

            ok, msg = self.executor.execute(command, user_id)
            prefix = "✅ " if ok else ""
            result = f"Понял: {command.type.value.replace('_', ' ')}\n{prefix}{msg}"

            if ok:
                self.last_command = command
                shortcut = self.memory.detect_recurring(
                    command.raw_text,
                    command.type.value,
                    json.dumps(command.params, ensure_ascii=False),
                )
                if shortcut:
                    result += f"\n\nХочешь shortcut? {shortcut}"

            self._maybe_send_attachment(chat_id)

            self.memory.save_message(chat_id, "user", text)
            self.memory.save_message(chat_id, "assistant", result)
            self._maybe_summarize_memory(chat_id)
            return result

        # ── Regular chat (with streaming) ──────────────────────────────
        self._maybe_record_topic(text)
        self.memory.save_message(chat_id, "user", text)

        thinking_msg_id: Optional[int] = None
        if show_thinking:
            try:
                resp = tg("sendMessage", chat_id=chat_id, text="🤔 Думаю...")
                if resp.get("ok"):
                    thinking_msg_id = resp.get("result", {}).get("message_id")
            except Exception as e:
                self.log.warning("thinking placeholder failed: %s", e)
                thinking_msg_id = None

        if thinking_msg_id is not None:
            # Stream tokens into the placeholder, throttling edits to ~1/sec
            # (Telegram caps editMessageText at roughly that rate per chat).
            last_edit = [time.time()]

            def on_chunk(full_text: str) -> None:
                # Don't edit on every token — Telegram will rate-limit us.
                now = time.time()
                if now - last_edit[0] < 1.2:
                    return
                if len(full_text.strip()) < 20:
                    return
                view = full_text[-3900:] if len(full_text) > 3900 else full_text
                if edit_message(chat_id, thinking_msg_id, view + " ▌"):
                    last_edit[0] = now

            result = self.brain.process_chat_streaming(text, on_chunk=on_chunk)
            self.memory.save_message(chat_id, "assistant", result)
            self._maybe_summarize_memory(chat_id)

            # Final edit: drop the cursor, render the full reply.
            if result and len(result) <= TG_MAX_LEN:
                if edit_message(chat_id, thinking_msg_id, result):
                    self._save_llm_experience(chat_id, text, result, thinking_msg_id)
                    return ""
            # Long reply or final-edit failed → drop placeholder, send normally
            try:
                tg("deleteMessage", chat_id=chat_id, message_id=thinking_msg_id)
            except Exception:
                pass
            self._pending_llm_feedback = {
                "chat_id": chat_id,
                "user_text": text,
                "bot_response": result,
                "model": self.brain.last_model or "",
            }
            return result

        # No placeholder available (batch mode) — fall through to non-streaming
        result = self.brain.process_chat(text)
        self.memory.save_message(chat_id, "assistant", result)
        self._maybe_summarize_memory(chat_id)
        self._pending_llm_feedback = {
            "chat_id": chat_id,
            "user_text": text,
            "bot_response": result,
            "model": self.brain.last_model or "",
        }
        return result

    def send_proactive_message(self, chat_id: int, text: str) -> bool:
        """Send a bot-initiated Telegram message outside a user request."""
        try:
            return send_message(chat_id, text)
        except Exception as e:
            self.log.warning("send_proactive_message failed: %s", e)
            return False

    def _maybe_summarize_memory(self, chat_id: int) -> None:
        try:
            self.brain.summarize_history_if_needed(chat_id)
        except Exception as e:
            self.log.warning("summarize_history_if_needed: %s", e)

    def _maybe_send_attachment(self, chat_id: int) -> None:
        """
        Feature 4: if the most recent executor handler attached a file
        (e.g. SCREENSHOT photo, OBSIDIAN_READ .md), upload it now and clear.
        """
        info = getattr(self.executor, "last_file", None)
        if not info:
            return
        # Clear first so we never double-send
        self.executor.last_file = None
        try:
            fpath, kind, caption = info
        except (TypeError, ValueError):
            return
        try:
            if kind == "photo":
                send_photo(chat_id, fpath, caption=caption)
            elif kind == "document":
                send_file(chat_id, fpath, caption=caption)
        except Exception as e:
            self.log.warning("send attachment failed: %s", e)

    def _feedback_markup(self, message_id: int) -> dict:
        return {
            "inline_keyboard": [[
                {"text": "👍", "callback_data": f"fb:ok:{message_id}"},
                {"text": "👎", "callback_data": f"fb:bad:{message_id}"},
            ]]
        }

    def _save_llm_experience(self, chat_id: int, user_text: str,
                             bot_response: str, message_id: int,
                             model: Optional[str] = None) -> None:
        try:
            self.memory.save_experience(
                chat_id,
                user_text,
                bot_response,
                model if model is not None else (self.brain.last_model or ""),
                "none",
                telegram_message_id=message_id,
            )
            edit_message_reply_markup(chat_id, message_id, self._feedback_markup(message_id))
        except Exception as e:
            self.log.warning("save LLM experience failed: %s", e)

    def _send_with_pending_feedback(self, chat_id: int, text: str) -> bool:
        payload = self._pending_llm_feedback
        self._pending_llm_feedback = None
        if not payload or payload.get("chat_id") != chat_id:
            return send_message(chat_id, text)
        message_id = send_message_result(chat_id, text)
        if not message_id:
            return False
        self._save_llm_experience(
            chat_id,
            payload.get("user_text", ""),
            payload.get("bot_response", text),
            message_id,
            payload.get("model", ""),
        )
        return True

    def _parse_inline_correction(self, text: str) -> Optional[str]:
        match = re.search(
            r'^\s*(?:нет|не\s+так)[,:\s]+(?:я\s+имел(?:а)?\s+в\s+виду|надо)\s+(.+)$',
            text,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    def _save_feedback_correction(self, exp_id: int, correction: str) -> Optional[Tuple[str, str]]:
        exp = self.memory.get_experience(exp_id)
        self.memory.update_experience_feedback(exp_id, "negative", correction)
        if not exp:
            return None
        try:
            learned = self.brain.learn_from_correction(
                str(exp.get("user_text") or ""),
                correction,
                parser=self.parser,
            )
            model = str(exp.get("model") or "")
            if model:
                command_type = self.brain.router.classify(str(exp.get("user_text") or ""))
                self.memory.update_model_score(model, command_type, -20.0)
            return learned
        except Exception as e:
            self.log.warning("feedback correction learning failed: %s", e)
            return None

    def _maybe_record_topic(self, text: str) -> None:
        try:
            topic = self.brain.extract_topic(text)
            if not topic or topic == self.current_topic:
                return
            previous = self.current_topic
            self.current_topic = topic
            content = f"Мы говорили про {topic}"
            if previous:
                content = f"Перешли от темы {previous} к теме {topic}"
            self.memory.save_fact(f"conversation:{topic}", content)
        except Exception as e:
            self.log.warning("topic extraction failed: %s", e)

    def handle_callback(self, callback_query: dict) -> None:
        callback_id = callback_query.get("id", "")
        user_id = callback_query.get("from", {}).get("id")
        if user_id != ALLOWED_USER:
            answer_callback(callback_id, "Unauthorized")
            return

        data = callback_query.get("data", "")
        msg = callback_query.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        if not data.startswith("fb:") or not chat_id:
            answer_callback(callback_id)
            return

        parts = data.split(":", 2)
        if len(parts) != 3:
            answer_callback(callback_id)
            return
        action, raw_msg_id = parts[1], parts[2]
        try:
            message_id = int(raw_msg_id)
        except ValueError:
            answer_callback(callback_id)
            return

        exp = self.memory.get_experience_by_message_id(message_id)
        if not exp:
            answer_callback(callback_id, "Не нашёл experience")
            return

        exp_id = int(exp["id"])
        model = str(exp.get("model") or "")
        command_type = self.brain.router.classify(str(exp.get("user_text") or ""))
        if action == "ok":
            self.memory.update_experience_feedback(exp_id, "positive")
            if model:
                self.memory.update_model_score(model, command_type, 20.0)
            answer_callback(callback_id, "Запомнил 👍")
        elif action == "bad":
            self.memory.update_experience_feedback(exp_id, "negative")
            if model:
                self.memory.update_model_score(model, command_type, -20.0)
            self.pending_corrections[chat_id] = exp_id
            answer_callback(callback_id, "Запомнил 👎")
            send_message(chat_id, "Что не так?")
        else:
            answer_callback(callback_id)

    def _get_help(self) -> str:
        return """🤖 Geek26 Bot v3.2

Команды:
• открой [url] — открыть в браузере
• обнови страницу — Cmd+R
• скачай [url] — скачать файл
• скопируй в буфер: [текст]
• запиши в обсидиан: [текст]
• найди в заметках [запрос]
• покажи коммиты [репо]
• статус [репо]
• проверь сервисы
• найди в интернете [запрос]
• напомни через 2 часа [текст]
• проверь сервисы и если что-то упало — рестартни
• место на диске
• покажи процессы
• скриншот
• не усыплять мак

Бот-команды:
/help — эта справка
/stats — статистика
/daily — ежедневный дайджест
/clear — очистить контекст
/remember <тема> <текст> — запомнить факт
/facts — что я знаю

Для сложных задач просто напиши — эскалирую к Geek."""

    def _get_stats(self) -> str:
        cmds = self.memory.get_recent_commands(10)
        if not cmds:
            return "📊 Нет данных"
        success = sum(1 for c in cmds if c["success"])
        total = len(cmds)
        return (f"📊 Статистика:\n"
                f"  Команд: {total} (✅ {success}, ❌ {total - success})\n"
                f"  Контекст: {len(self.brain.chat_history)}/{self.brain.chat_history.maxlen}\n"
                f"  SQLite: {'✅' if self.memory.is_healthy() else '❌'}")

    def _get_daily(self) -> str:
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        cmds = self.memory.get_commands_since(since, limit=100)
        total = len(cmds)
        success = sum(1 for c in cmds if c["success"])

        ok_services, services = self.executor._handle_check_services({})
        ok_disk, disk = self.executor._handle_disk_usage({})

        command_lines = []
        for c in cmds[:10]:
            status = "✅" if c["success"] else "❌"
            command_lines.append(f"{status} {c['type']}: {str(c['text'])[:80]}")
        if not command_lines:
            command_lines.append("Команд не было")

        return (
            "☀️ Daily Digest\n"
            f"Период: последние 24 часа\n\n"
            f"📌 Команды: {total} (✅ {success}, ❌ {total - success})\n"
            + "\n".join(command_lines)
            + "\n\n"
            + (services if ok_services else f"❌ Статус сервисов: {services}")
            + "\n\n"
            + (disk if ok_disk else f"❌ Диск: {disk}")
        )

    # ── Media ──

    def handle_photo(self, file_path: str, chat_id: int) -> str:
        """OCR on photo. Result is also saved into chat_history for continuity."""
        local = download_file(file_path)
        if not local:
            return "❌ Не удалось скачать фото"
        script = SHELL_SCRIPTS / "ocr.sh"
        if not script.exists():
            return "❌ OCR скрипт не найден"
        try:
            import subprocess
            r = subprocess.run(
                ["bash", str(script), local],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0 and r.stdout.strip():
                ocr_text = r.stdout.strip()[:2000]
                # Feed into chat history so subsequent messages have context
                self._record_modal_input("photo", ocr_text, chat_id)
                analysis = self._analyze_photo_text(ocr_text)
                return f"📷 OCR:\n{ocr_text}" + (f"\n\n{analysis}" if analysis else "")
            return "❌ OCR не распознал текст"
        except Exception as e:
            return f"❌ OCR ошибка: {e}"

    def _analyze_photo_text(self, ocr_text: str) -> str:
        suggestions = []
        url_match = re.search(r'https?://[^\s]+', ocr_text)
        if url_match:
            suggestions.append(f"• URL найден: можно открыть {url_match.group(0)}")

        if re.search(r'\b(error|exception|traceback|failed|ошибка|исключение)\b', ocr_text, re.IGNORECASE):
            suggestions.append("• Похоже на ошибку: можно эскалировать к Geek")

        parsed = self.parser.parse(ocr_text)
        if parsed.type != CommandType.NONE and parsed.confidence > 0.5:
            suggestions.append(f"• Похоже на команду: можно выполнить {parsed.type.value}")

        llm_note = self._photo_llm_analysis(ocr_text)
        if llm_note:
            suggestions.append(f"• Gemma: {llm_note[:700]}")

        return "🔎 Анализ:\n" + "\n".join(suggestions) if suggestions else ""

    def _photo_llm_analysis(self, ocr_text: str) -> str:
        model = "gemma4:e4b"
        if model not in MODELS:
            return ""
        messages = [
            {"role": "system", "content": "Коротко проанализируй OCR текст. Если есть URL, ошибка или команда для бота, предложи одно действие. Без выполнения."},
            {"role": "user", "content": ocr_text[:2000]},
        ]
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": "5m",
            "think": False,
            "options": {"num_ctx": 2048},
        }
        try:
            r = requests.post(OLLAMA_CHAT, json=payload, timeout=15)
            data = r.json()
            return data.get("message", {}).get("content", "").strip()
        except requests.Timeout:
            self.log.info("photo LLM analysis timeout")
            return ""
        except Exception as e:
            self.log.warning("photo LLM analysis failed: %s", e)
            return ""

    def handle_voice(self, file_path: str, chat_id: int) -> str:
        """Transcribe voice. Result is also saved into chat_history for continuity."""
        local = download_file(file_path)
        if not local:
            return "❌ Не удалось скачать голосовое"
        script = SHELL_SCRIPTS / "transcribe.sh"
        if not script.exists():
            return "❌ Transcribe скрипт не найден"
        try:
            import subprocess
            r = subprocess.run(
                ["bash", str(script), local],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode == 0 and r.stdout.strip():
                txt = r.stdout.strip()[:2000]
                self._record_modal_input("voice", txt, chat_id)
                return f"🎤 Транскрипция:\n{txt}"
            return "❌ Не удалось распознать"
        except Exception as e:
            return f"❌ Ошибка транскрипции: {e}"

    def _record_modal_input(self, kind: str, content: str, chat_id: int) -> None:
        """
        Push voice / photo content into chat_history + persistent SQLite
        message log so a follow-up question like "что я сказал?" can see it.
        """
        try:
            tag = f"[{kind}]"
            user_line = f"{tag} {content}"
            self.brain.chat_history.append(("user", user_line))
            self.memory.save_message(chat_id, "user", user_line)
            self._maybe_summarize_memory(chat_id)
        except Exception as e:
            self.log.warning("record_modal_input: %s", e)

    # ── Watchdog ──

    def watchdog_check(self) -> None:
        """Periodic health check."""
        # Ollama
        ollama_ok = self.brain.check_ollama()
        if not ollama_ok:
            self.log.warning("⚠️ Ollama not responding!")
            try:
                r = subprocess.run(
                    ["brew", "services", "restart", "ollama"],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    self.log.info("Watchdog restarted Ollama via brew")
                else:
                    self.log.warning("Watchdog Ollama restart failed: %s", (r.stderr or r.stdout).strip())
            except Exception as e:
                self.log.warning("Watchdog Ollama restart error: %s", e)

        # SQLite
        db_ok = self.memory.is_healthy()
        if not db_ok:
            self.log.error("❌ SQLite unhealthy!")

        # Disk
        disk = shutil.disk_usage("/")
        disk_pct = (disk.used / disk.total) * 100
        disk_threshold = min(DISK_WARNING_PCT, 90)
        if disk_pct > disk_threshold:
            self.log.warning("⚠️ Disk %.1f%% full!", disk_pct)
            self.send_proactive_message(
                ALLOWED_USER,
                f"⚠️ Диск заполнен на {disk_pct:.1f}% ({self.executor._format_size(disk.free)} свободно)",
            )

        self._send_due_reminders()

        self.log.info("Watchdog: Ollama=%s DB=%s Disk=%.1f%%", ollama_ok, db_ok, disk_pct)

    def _send_due_reminders(self) -> None:
        now_iso = datetime.now().isoformat()
        try:
            due = self.memory.get_due_reminders(now_iso)
        except Exception as e:
            self.log.warning("get_due_reminders failed: %s", e)
            return
        for reminder_id, chat_id, text, trigger_at in due:
            if self.send_proactive_message(chat_id, f"⏰ Напоминание:\n{text}"):
                try:
                    self.memory.mark_reminder_sent(reminder_id)
                except Exception as e:
                    self.log.warning("mark_reminder_sent(%s): %s", reminder_id, e)

    # ── Main Loop ──

    def run(self) -> None:
        self.log.info("🤖 Geek26 Bot v3 started")
        self.log.info("   Models: %s", ", ".join(MODELS.keys()))
        self.log.info("   DB: %s", self.settings.db_file)
        self.log.info("   Watchdog: every %d iterations", WATCHDOG_INTERVAL)

        while self.running:
            try:
                updates = tg("getUpdates", offset=self.offset, timeout=POLL_TIMEOUT)

                if not updates.get("ok"):
                    self.log.error("getUpdates failed: %s", updates.get("description", "unknown"))
                    self.consecutive_errors += 1
                    self._check_error_limit()
                    continue

                self.consecutive_errors = 0
                self.iteration += 1

                # Watchdog
                if self.iteration % WATCHDOG_INTERVAL == 0:
                    self.watchdog_check()

                for update in updates.get("result", []):
                    self.offset = update["update_id"] + 1
                    self._handle_update(update)

            except requests.Timeout:
                # Normal — long polling timeout
                self.consecutive_errors = 0
                continue
            except Exception as e:
                self.consecutive_errors += 1
                self.log.error("Loop error: %s", e)
                self._check_error_limit()
                time.sleep(5)

        self.log.info("🛑 Geek26 Bot stopped cleanly")

    def _split_batch(self, text: str) -> list:
        """Split numbered list into individual items. Returns list."""
        text = text.strip()

        # Pattern: numbered items like "1. text" or "1) text" or "1. текст"
        lines = text.split('\n')
        items = []
        current = None
        numbered_re = re.compile(r'^\s*\d+[.)\]]\s*')

        for line in lines:
            if numbered_re.match(line):
                if current is not None:
                    items.append(current)
                # Strip number prefix
                current = numbered_re.sub('', line).strip()
            else:
                if current is not None:
                    current += ' ' + line.strip()
                elif line.strip():
                    # Non-numbered line before any numbers = not a batch
                    return [text]

        if current is not None:
            items.append(current)

        # Only treat as batch if 2+ items found
        return items if len(items) >= 2 else [text]

    def _check_error_limit(self) -> None:
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            self.log.critical("💀 %d consecutive errors — self-restarting", self.consecutive_errors)
            sys.exit(1)

    def _handle_update(self, update: dict) -> None:
        if update.get("callback_query"):
            self.handle_callback(update["callback_query"])
            return

        msg = update.get("message", {})
        if not msg:
            return

        chat_id = msg.get("chat", {}).get("id")
        user_id = msg.get("from", {}).get("id")
        text = msg.get("text", "")

        if user_id != ALLOWED_USER:
            return

        # Photo
        if msg.get("photo"):
            photos = msg["photo"]
            file_id = photos[-1]["file_id"]  # largest
            file_info = tg("getFile", file_id=file_id)
            if file_info.get("ok"):
                reply = self.handle_photo(file_info["result"]["file_path"], chat_id)
                send_message(chat_id, reply)
            return

        # Voice
        if msg.get("voice"):
            file_id = msg["voice"]["file_id"]
            file_info = tg("getFile", file_id=file_id)
            if file_info.get("ok"):
                reply = self.handle_voice(file_info["result"]["file_path"], chat_id)
                send_message(chat_id, reply)
            return

        if not text:
            return

        self.log.info("Q: %s", text[:100])

        # Check if message is a batch (numbered list)
        items = self._split_batch(text)
        if len(items) > 1:
            self.log.info("Batch detected: %d items", len(items))
            send_message(chat_id, f"📋 Получил {len(items)} задач. Обрабатываю по очереди...")
            for i, item in enumerate(items):
                self.log.info("Batch [%d/%d]: %s", i+1, len(items), item[:60])
                # show_thinking=False — batch items are wrapped with [N/M] header,
                # so we want the full reply returned (not edited in place)
                reply = self.process_message(item.strip(), user_id, chat_id, show_thinking=False)
                if reply:
                    self._send_with_pending_feedback(
                        chat_id,
                        f"**[{i+1}/{len(items)}]** {item.strip()[:40]}\n{'─'*30}\n{reply}",
                    )
                time.sleep(1)  # small pause between items
            send_message(chat_id, f"✅ Все {len(items)} задач обработано.")
        else:
            reply = self.process_message(text, user_id, chat_id)
            if reply:
                self._send_with_pending_feedback(chat_id, reply)


if __name__ == "__main__":
    bot = Geek26Bot()
    bot.run()
