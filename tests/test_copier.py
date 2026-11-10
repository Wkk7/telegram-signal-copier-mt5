import unittest

from copier.config import Settings
from run_copier import Copier


class FakeBot:
    def __init__(self):
        self.sent = []

    def send(self, chat_id, text):
        self.sent.append(text)


def make(dry_run=True):
    cfg = Settings()
    cfg.source_chat_id, cfg.admin_chat_id, cfg.dry_run = -100123, 42, dry_run
    cfg.symbol_suffix, cfg.symbol_map = ".pro", {"XAUUSD": "GOLD"}
    bot = FakeBot()
    return Copier(cfg, bot), bot


def post(chat_id, text):
    return {"channel_post": {"chat": {"id": chat_id}, "text": text}}


class CopierTest(unittest.TestCase):
    def test_copies_only_from_source_channel(self):
        copier, bot = make()
        copier.process(post(-100999, "BUY EURUSD 1.0850 SL 1.0820 TP 1.0900"))
        self.assertEqual(bot.sent, [])
        copier.process(post(-100123, "BUY EURUSD 1.0850 SL 1.0820 TP 1.0900"))
        self.assertIn("BUY market EURUSD.pro", bot.sent[0])

    def test_symbol_map_wins_over_suffix(self):
        copier, bot = make()
        copier.process(post(-100123, "Gold sell 2350 sl 2360 tp 2340"))
        self.assertIn("GOLD", bot.sent[0])

    def test_pause_and_resume_from_admin_chat(self):
        copier, bot = make()
        copier.process({"message": {"chat": {"id": 42}, "text": "/pause"}})
        copier.process(post(-100123, "BUY EURUSD 1.0850 SL 1.0820 TP 1.0900"))
        self.assertTrue(bot.sent[-1].startswith("Paused"))
        copier.process({"message": {"chat": {"id": 42}, "text": "/resume"}})
        self.assertFalse(copier.paused)

    def test_commands_from_strangers_are_ignored(self):
        copier, bot = make()
        copier.process({"message": {"chat": {"id": 7}, "text": "/pause"}})
        self.assertFalse(copier.paused)


if __name__ == "__main__":
    unittest.main()
