"""MetaTrader 5 side: lot size from risk %, market / pending orders, closing."""
import math

import MetaTrader5 as mt5

from .parser import Signal


def lot_size(balance: float, risk_pct: float, sl_distance: float, info) -> float:
    """Lots so that the stop loss costs `risk_pct` % of balance (rounded DOWN to the lot step)."""
    if sl_distance <= 0 or info.trade_tick_value <= 0:
        return 0.0
    loss_per_lot = sl_distance / info.trade_tick_size * info.trade_tick_value
    lots = math.floor(balance * risk_pct / 100 / loss_per_lot / info.volume_step) * info.volume_step
    return 0.0 if lots < info.volume_min else round(min(lots, info.volume_max), 8)


class MT5:
    def __init__(self, magic: int):
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        self.magic = magic

    def account(self):
        return mt5.account_info()

    def my_positions(self, symbol: str | None = None) -> list:
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        return [p for p in (positions or []) if p.magic == self.magic]

    def place(self, signal: Signal, symbol: str, risk_pct: float, split_tps: bool) -> list[str]:
        """Open the trade(s) for a signal. Returns one receipt line per order."""
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Symbol {symbol} not found at this broker (check SYMBOL_SUFFIX / SYMBOL_MAP)")
        info, tick = mt5.symbol_info(symbol), mt5.symbol_info_tick(symbol)
        buy = signal.side == "buy"
        market_price = tick.ask if buy else tick.bid
        price = market_price if signal.order_type == "market" or signal.entry is None else signal.entry

        total = lot_size(self.account().balance, risk_pct, abs(price - signal.sl), info)
        if total == 0:
            raise RuntimeError("Position size below the minimum lot - signal skipped")
        targets = signal.tps if (split_tps and len(signal.tps) > 1) else signal.tps[:1] or [0.0]
        per_order = math.floor(total / len(targets) / info.volume_step) * info.volume_step
        if per_order < info.volume_min:  # too small to split without adding risk: one order, first TP
            targets, per_order = targets[:1], total

        action, order_type = mt5.TRADE_ACTION_DEAL, (mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL)
        if signal.order_type == "limit":
            action, order_type = mt5.TRADE_ACTION_PENDING, (mt5.ORDER_TYPE_BUY_LIMIT if buy else mt5.ORDER_TYPE_SELL_LIMIT)
        elif signal.order_type == "stop":
            action, order_type = mt5.TRADE_ACTION_PENDING, (mt5.ORDER_TYPE_BUY_STOP if buy else mt5.ORDER_TYPE_SELL_STOP)

        receipts = []
        for i, tp in enumerate(targets, 1):
            request = {
                "action": action, "symbol": symbol, "volume": round(per_order, 8), "type": order_type,
                "price": round(price, info.digits), "sl": round(signal.sl, info.digits),
                "tp": round(tp, info.digits), "deviation": 30, "magic": self.magic,
                "comment": f"copier TP{i}", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                receipts.append(f"TP{i}: REJECTED {getattr(result, 'retcode', '')} {getattr(result, 'comment', mt5.last_error())}")
            else:
                receipts.append(f"TP{i}: {signal.side.upper()} {per_order:g} lots {symbol} @ {result.price or price} "
                                f"SL {signal.sl} TP {tp or '-'}")
        return receipts

    def close_symbol(self, symbol: str) -> int:
        closed = 0
        for p in self.my_positions(symbol):
            tick = mt5.symbol_info_tick(symbol)
            is_buy = p.type == mt5.POSITION_TYPE_BUY
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": p.volume, "position": p.ticket,
                "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
                "price": tick.bid if is_buy else tick.ask, "deviation": 30, "magic": self.magic,
                "comment": "copier close", "type_filling": mt5.ORDER_FILLING_IOC,
            })
            closed += int(result is not None and result.retcode == mt5.TRADE_RETCODE_DONE)
        return closed
