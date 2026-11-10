"""Turns free-text Telegram signals into structured orders.

Understands the formats most channels use, for example:

    BUY EURUSD @ 1.0850  SL 1.0820  TP 1.0880 TP2 1.0910
    XAUUSD SELL NOW 2350 / SL: 2360 / TP1: 2340 / TP2: 2330
    Gold buy limit 2330-2328, stop loss 2320, take profit 2345
    EUR/USD long entry 1,0850 sl 1,0820 tp 1,0900
    CLOSE GBPUSD
"""
import re
from dataclasses import dataclass, field

ALIASES = {
    "GOLD": "XAUUSD", "SILVER": "XAGUSD", "OIL": "USOIL", "WTI": "USOIL", "BRENT": "UKOIL",
    "DOW": "US30", "DJ30": "US30", "NASDAQ": "US100", "NAS100": "US100", "NQ": "US100",
    "SPX": "US500", "SP500": "US500", "DAX": "GER40", "DE40": "GER40",
    "BTC": "BTCUSD", "BITCOIN": "BTCUSD", "ETH": "ETHUSD",
}
CURRENCIES = {"EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "XAU", "XAG", "BTC", "ETH"}
OTHER_SYMBOLS = {"US30", "US100", "US500", "GER40", "UK100", "JP225", "USOIL", "UKOIL"}

NUM = r"(\d+(?:[.,]\d+)?)"
SEP = r"\s*(?:[:=@]|AT)?\s*"
# "TP", "TP1", "TP 2:", "T/P", "TAKE PROFIT 3:" - an index digit counts only when glued to the
# label or followed by ":" / "=", so "TP 190.50" is read as 190.50 and not as TP1 + 90.50
TP_LABEL = r"(?:\bTP|T/P|TAKE\s*PROFIT)(?:\d|\s*\d(?=\s*[:=@]))?"


@dataclass
class Signal:
    side: str                      # "buy" | "sell"
    symbol: str
    order_type: str = "market"     # "market" | "limit" | "stop"
    entry: float | None = None
    sl: float | None = None
    tps: list[float] = field(default_factory=list)


@dataclass
class Close:
    symbol: str


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _find_symbol(text: str) -> str | None:
    compact = text.replace("/", "")
    for token in re.findall(r"[A-Z0-9]{2,7}", compact):
        if token in ALIASES:
            return ALIASES[token]
        if token in OTHER_SYMBOLS:
            return token
        if len(token) == 6 and token[:3] in CURRENCIES and token[3:] in CURRENCIES:
            return token
    return None


def parse(message: str) -> Signal | Close | None:
    """Return a Signal, a Close instruction, or None when the text is not a trade."""
    text = message.upper()

    close = re.search(r"\bCLOSE\b", text)
    side_m = re.search(r"\b(BUY|SELL|LONG|SHORT)\b", text)
    symbol = _find_symbol(text)
    if close and symbol and not side_m:
        return Close(symbol)
    if not side_m or not symbol:
        return None
    side = "buy" if side_m.group(1) in ("BUY", "LONG") else "sell"

    order_type = "market"
    kind = re.search(r"\b(?:BUY|SELL|LONG|SHORT)\s+(LIMIT|STOP)\b", text)
    if kind:
        order_type = kind.group(1).lower()

    sl_m = re.search(r"(?:\bSL\b|S/L|STOP\s*LOSS|STOPLOSS)" + SEP + NUM, text)
    if not sl_m:
        return None  # never copy a trade without a stop loss
    sl = _num(sl_m.group(1))

    tps = [_num(v) for v in re.findall(TP_LABEL + SEP + NUM, text)]

    # entry: after @ / AT / ENTRY / PRICE / NOW, or the first number after the side or order type
    entry = None
    em = (re.search(r"(?:@|\bAT\b|\bENTRY\b|\bPRICE\b|\bNOW\b)\s*:?\s*" + NUM, text)
          or re.search(r"\b(?:BUY|SELL|LONG|SHORT)(?:\s+(?:LIMIT|STOP))?\s+(?:[A-Z/]{3,7}\s+)?" + NUM, text))
    if em:
        entry = _num(em.group(1))

    signal = Signal(side, symbol, order_type, entry, sl, tps)
    return signal if is_consistent(signal) else None


def is_consistent(s: Signal) -> bool:
    """Reject signals whose numbers contradict the direction (usually typos)."""
    up = s.side == "buy"
    ref = s.entry
    if ref is None:
        ref = s.tps[0] if s.tps else None
        if ref is None:
            return True
        return s.sl < ref if up else s.sl > ref
    if (up and s.sl >= ref) or (not up and s.sl <= ref):
        return False
    return all((tp > ref) if up else (tp < ref) for tp in s.tps)
