"""Settings from .env (copy .env.example to .env)."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _map(raw: str) -> dict[str, str]:
    # "GOLD=XAUUSD.pro,US30=DJ30" -> {"GOLD": "XAUUSD.pro", "US30": "DJ30"}
    return dict(pair.split("=", 1) for pair in raw.split(",") if "=" in pair)


@dataclass
class Settings:
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    source_chat_id: int = int(os.getenv("SOURCE_CHAT_ID", "0"))   # your signal channel
    admin_chat_id: int = int(os.getenv("ADMIN_CHAT_ID", "0"))     # where receipts and commands go
    risk_pct: float = float(os.getenv("RISK_PCT", "0.5"))
    max_open_trades: int = int(os.getenv("MAX_OPEN_TRADES", "5"))
    split_tps: bool = os.getenv("SPLIT_TPS", "true").lower() == "true"
    symbol_suffix: str = os.getenv("SYMBOL_SUFFIX", "")
    symbol_map: dict[str, str] = field(default_factory=lambda: _map(os.getenv("SYMBOL_MAP", "")))
    magic: int = int(os.getenv("MAGIC", "880088"))
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"

    def broker_symbol(self, symbol: str) -> str:
        return self.symbol_map.get(symbol, symbol + self.symbol_suffix)
