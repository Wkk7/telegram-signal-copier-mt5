"""Copies signals from YOUR Telegram channel to YOUR MetaTrader 5 account.

    python run_copier.py

1. Create a bot with @BotFather, add it as ADMIN of your signal channel.
2. Put the token and chat ids in .env (DRY_RUN=true first!).
3. Commands in the admin chat: /status  /pause  /resume
"""
import logging
import time

import requests

from copier.config import Settings
from copier.parser import Close, Signal, parse
from copier.telegram import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("copier")


class Copier:
    def __init__(self, cfg: Settings, bot: TelegramBot, broker=None):
        self.cfg, self.bot, self.broker = cfg, bot, broker
        self.paused = False

    def notify(self, text: str) -> None:
        log.info(text.replace("\n", " | "))
        self.bot.send(self.cfg.admin_chat_id, text)

    def handle_signal(self, text: str) -> None:
        action = parse(text)
        if action is None:
            return
        if self.paused:
            self.notify(f"Paused - ignored: {text[:80]}")
            return
        prefix = "[DRY RUN] " if self.cfg.dry_run else ""

        if isinstance(action, Close):
            symbol = self.cfg.broker_symbol(action.symbol)
            closed = 0 if self.cfg.dry_run else self.broker.close_symbol(symbol)
            self.notify(f"{prefix}CLOSE {symbol}: {closed} position(s) closed")
            return

        assert isinstance(action, Signal)
        symbol = self.cfg.broker_symbol(action.symbol)
        summary = (f"{prefix}{action.side.upper()} {action.order_type} {symbol} entry {action.entry or 'market'} "
                   f"SL {action.sl} TP {', '.join(map(str, action.tps)) or '-'}")
        if self.cfg.dry_run:
            self.notify(summary)
            return
        if len(self.broker.my_positions()) >= self.cfg.max_open_trades:
            self.notify(f"Max open trades reached - skipped:\n{summary}")
            return
        try:
            receipts = self.broker.place(action, symbol, self.cfg.risk_pct, self.cfg.split_tps)
            self.notify(summary + "\n" + "\n".join(receipts))
        except RuntimeError as exc:
            self.notify(f"Not copied: {exc}\n{summary}")

    def handle_command(self, text: str) -> None:
        cmd = text.strip().split()[0].lower()
        if cmd == "/pause":
            self.paused = True
            self.notify("Copier paused")
        elif cmd == "/resume":
            self.paused = False
            self.notify("Copier resumed")
        elif cmd == "/status":
            if self.broker is None:
                self.notify(f"Dry run - paused: {self.paused}")
                return
            acc = self.broker.account()
            self.notify(f"Balance {acc.balance:.2f} {acc.currency} | equity {acc.equity:.2f} | "
                        f"open trades {len(self.broker.my_positions())} | paused: {self.paused}")

    def process(self, update: dict) -> None:
        post = update.get("channel_post")
        if post and post.get("chat", {}).get("id") == self.cfg.source_chat_id:
            self.handle_signal(post.get("text") or post.get("caption") or "")
            return
        msg = update.get("message")
        if msg and msg.get("chat", {}).get("id") == self.cfg.admin_chat_id and (msg.get("text") or "").startswith("/"):
            self.handle_command(msg["text"])


def main() -> None:
    cfg = Settings()
    bot = TelegramBot(cfg.telegram_token)
    broker = None
    if not cfg.dry_run:
        from copier.mt5_client import MT5  # needs the MT5 terminal running
        broker = MT5(cfg.magic)
    copier = Copier(cfg, bot, broker)
    copier.notify(f"Signal copier started (dry run: {cfg.dry_run}, risk {cfg.risk_pct}% per signal)")
    while True:
        try:
            for update in bot.updates():
                copier.process(update)
        except requests.RequestException as exc:
            log.warning("Telegram connection problem: %s - retrying", exc)
            time.sleep(5)
        except KeyboardInterrupt:
            log.info("Stopped by user")
            break


if __name__ == "__main__":
    main()
