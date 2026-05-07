from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from geek26.bot import Geek26Bot, TelegramClient, Watchdog, WatchdogError, run_bot_once, send_long
from geek26.brain import BrainStore, OllamaBrain
from geek26.config import BotSettings
from geek26.executor import CommandExecutor, CommandParser, CommandType, ParsedCommand, SafetyValidator


class DummyResponse:
    def __init__(self, ok: bool = True, payload=None, status_code: int = 200, content: bytes = b""):
        self.ok = ok
        self._payload = payload or {}
        self.status_code = status_code
        self.content = content

    def json(self):
        return self._payload


class Geek26Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = BotSettings(script_dir=Path(self.tmp.name))
        self.logger = logging.getLogger(f"test-geek26-{id(self)}")
        self.logger.handlers = []
        self.logger.addHandler(logging.NullHandler())
        self.store = BrainStore(self.settings.db_file)
        self.addCleanup(self.store.close)

    def make_bot(self):
        return Geek26Bot(self.settings, self.logger, store=self.store)

    def test_01_parser_open_url(self):
        parser = CommandParser()
        parsed = parser.parse("открой https://example.com")
        self.assertEqual(parsed.type, CommandType.OPEN_URL)
        self.assertEqual(parsed.params["url"], "https://example.com")

    def test_02_parser_graphify_path(self):
        parser = CommandParser()
        parsed = parser.parse("как связаны alpha и beta")
        self.assertEqual(parsed.type, CommandType.GRAPHIFY_PATH)
        self.assertEqual(parsed.params, {"node1": "alpha", "node2": "beta"})

    def test_03_parser_escalation_keyword(self):
        parser = CommandParser()
        parsed = parser.parse("сделай глубокий анализ архитектуры")
        self.assertEqual(parsed.type, CommandType.ESCALATE)
        self.assertGreater(parsed.confidence, 0.5)

    def test_04_parser_llm_hint_download(self):
        parser = CommandParser()
        parsed = parser.parse("please grab https://example.com/file.zip", llm_hint="download")
        self.assertEqual(parsed.type, CommandType.DOWNLOAD)
        self.assertEqual(parsed.params["url"], "https://example.com/file.zip")

    def test_05_safety_blocks_unauthorized_user(self):
        validator = SafetyValidator(allowed_user_id=7)
        ok, error = validator.validate_command(ParsedCommand(CommandType.OPEN_URL, {}, 1.0, "x"), user_id=9)
        self.assertFalse(ok)
        self.assertEqual(error, "Unauthorized user")

    def test_06_safety_blocks_shortener_url(self):
        validator = SafetyValidator(allowed_user_id=7)
        command = ParsedCommand(CommandType.DOWNLOAD, {"url": "https://bit.ly/demo"}, 1.0, "x")
        ok, error = validator.validate_command(command, user_id=7)
        self.assertFalse(ok)
        self.assertEqual(error, "Suspicious URL")

    def test_07_safety_requires_confirmation_for_restart(self):
        validator = SafetyValidator(allowed_user_id=7)
        command = ParsedCommand(CommandType.RESTART_SERVICE, {"service": "ollama"}, 1.0, "x")
        self.assertTrue(validator.needs_confirmation(command))

    def test_08_store_persists_recent_chat(self):
        self.store.add_chat_message(55, "user", "hello")
        self.store.add_chat_message(55, "assistant", "world")
        self.assertEqual(self.store.recent_chat(55, 10), [("user", "hello"), ("assistant", "world")])

    def test_09_store_records_command_audit(self):
        self.store.add_command_audit(1, 2, "open_url", "open", "open x", True, "ok")
        rows = self.store.list_command_audit()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["command_type"], "open_url")

    def test_10_brain_heuristic_prefers_russian_response(self):
        question = "объясни архитектуру проекта"
        ru_answer = "1. Архитектура проекта состоит из модулей, потому что это упрощает поддержку."
        en_answer = "Short answer."
        self.assertGreater(OllamaBrain.heuristic_score(question, ru_answer), OllamaBrain.heuristic_score(question, en_answer))

    def test_11_brain_pick_best_prefers_qwen_on_small_delta(self):
        brain = OllamaBrain(self.settings, store=self.store)
        results = {
            "qwen3.5:9b": ("Это полезный ответ про архитектуру проекта.", "10 tok/s"),
            "gemma4:e4b": ("Это полезный ответ про архитектуру проекта и детали.", "11 tok/s"),
        }
        model, _, _ = brain.pick_best("архитектура проекта", results)
        self.assertEqual(model, "qwen3.5:9b")
        brain.close()

    def test_12_executor_open_url_success(self):
        executor = CommandExecutor(self.settings, self.logger, store=self.store)
        with patch.object(executor, "_run_shell", return_value=(True, "ok")) as run_shell:
            ok, output = executor.execute(
                ParsedCommand(CommandType.OPEN_URL, {"url": "https://example.com"}, 1.0, "x"),
                self.settings.allowed_user,
                chat_id=3,
            )
        run_shell.assert_called_once()
        self.assertTrue(ok)
        self.assertIn("https://example.com", output)
        self.assertEqual(len(self.store.list_command_audit()), 1)

    def test_13_executor_restart_service_whitelist_rejects_unknown(self):
        executor = CommandExecutor(self.settings, self.logger, store=self.store)
        ok, output = executor.execute(
            ParsedCommand(CommandType.RESTART_SERVICE, {"service": "nginx"}, 1.0, "x"),
            self.settings.allowed_user,
        )
        self.assertFalse(ok)
        self.assertIn("whitelist", output)

    def test_14_executor_obsidian_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp_home:
            with patch("pathlib.Path.home", return_value=Path(tmp_home)):
                executor = CommandExecutor(self.settings, self.logger, store=self.store)
                ok, output = executor.execute(
                    ParsedCommand(CommandType.OBSIDIAN_WRITE, {"text": "тестовая заметка"}, 1.0, "x"),
                    self.settings.allowed_user,
                )
                inbox = Path(tmp_home) / "Documents" / "Obsidian-Vault" / "Inbox"
                files = list(inbox.glob("geek26_*.md"))
        self.assertTrue(ok)
        self.assertEqual(len(files), 1)
        self.assertIn("Создал заметку", output)

    def test_15_bot_confirmation_flow_yes_executes(self):
        bot = self.make_bot()
        with patch.object(bot, "_execute_and_format", return_value="done"):
            response = bot.process_message("перезапусти ollama", self.settings.allowed_user, 11)
            done = bot.process_message("да", self.settings.allowed_user, 11)
        self.assertIn("Нужно подтверждение", response)
        self.assertEqual(done, "done")
        bot.close()

    def test_16_bot_uses_brain_for_regular_chat(self):
        bot = self.make_bot()
        with patch.object(bot.brain, "process_chat", return_value="chat-result") as process_chat:
            reply = bot.process_message("привет", self.settings.allowed_user, 13)
        process_chat.assert_called_once_with(13, "привет")
        self.assertEqual(reply, "chat-result")
        bot.close()

    def test_17_send_long_splits_messages(self):
        client = MagicMock()
        send_long(client, 99, "a" * 9000)
        self.assertEqual(client.call.call_count, 3)

    def test_18_telegram_client_timeout_logic(self):
        session = MagicMock()
        session.post.return_value = DummyResponse(payload={"ok": True})
        client = TelegramClient("TOKEN", self.settings, session=session)
        client.call("getUpdates", timeout=30, offset=1)
        _, kwargs = session.post.call_args
        self.assertEqual(kwargs["timeout"], 60)

    def test_19_watchdog_raises_on_idle(self):
        times = iter([0, 10])
        watchdog = Watchdog(idle_limit=5, failure_limit=3, clock=lambda: next(times))
        with self.assertRaises(WatchdogError):
            watchdog.check()

    def test_20_run_bot_once_processes_update(self):
        bot = self.make_bot()
        tg_client = MagicMock()
        tg_client.call.side_effect = [
            {
                "result": [
                    {
                        "update_id": 10,
                        "message": {
                            "chat": {"id": 77},
                            "from": {"id": self.settings.allowed_user},
                            "text": "привет",
                        },
                    }
                ]
            },
            {"ok": True},
            {"ok": True},
        ]
        watchdog = Watchdog(idle_limit=30, failure_limit=3, clock=lambda: 0)
        with patch.object(bot, "process_message", return_value="reply") as process_message:
            offset = run_bot_once(self.settings, self.logger, tg_client, bot, watchdog, 0)
        self.assertEqual(offset, 11)
        process_message.assert_called_once_with("привет", self.settings.allowed_user, 77)
        bot.close()


if __name__ == "__main__":
    unittest.main()
