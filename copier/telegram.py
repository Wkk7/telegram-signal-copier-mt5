"""Minimal Telegram Bot API client (long polling, no extra libraries)."""
import logging

import requests

log = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str):
        if not token:
            raise ValueError("TELEGRAM_TOKEN is missing in .env")
        self.base = f"https://api.telegram.org/bot{token}"
        self.offset = None

    def updates(self, timeout: int = 30) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": '["message","channel_post"]'}
        if self.offset is not None:
            params["offset"] = self.offset
        r = requests.get(f"{self.base}/getUpdates", params=params, timeout=timeout + 10)
        r.raise_for_status()
        result = r.json().get("result", [])
        if result:
            self.offset = result[-1]["update_id"] + 1
        return result

    def send(self, chat_id: int, text: str) -> None:
        if not chat_id:
            return
        try:
            requests.post(f"{self.base}/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=10)
        except requests.RequestException as exc:
            log.warning("sendMessage failed: %s", exc)
