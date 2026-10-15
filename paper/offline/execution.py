"""Pure fills and directional charge calculations; no broker-shaped payloads."""
from decimal import Decimal, localcontext
from .config import PRICE, PRECISION, rounded, number

def fill(raw, side, config):
    raw = number(raw)
    if raw <= 0 or side not in ("BUY", "SELL"):
        raise ValueError("Invalid fill inputs")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = "ROUND_HALF_UP"
        result = rounded(raw * (1 + (1 if side == "BUY" else -1) * config.slippage_bps / 10000), PRICE)
        if result <= 0:
            raise ValueError("Nonpositive slipped fill")
        return result

def charges(entry, exit_price, quantity, side, costs):
    if side not in ("BUY", "SELL") or type(quantity) is not int or quantity <= 0:
        raise ValueError("Invalid charge side/quantity")
    entry, exit_price = number(entry), number(exit_price)
    if min(entry, exit_price) <= 0:
        raise ValueError("Positive charge prices required")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = "ROUND_HALF_UP"
        e, x = entry * quantity, exit_price * quantity
        buy, sell = (e, x) if side == "BUY" else (x, e)
        def brokerage(turnover):
            return rounded(min(costs.brokerage_max, max(costs.brokerage_min, turnover * costs.brokerage_rate)))
        components = {
            "entry_brokerage": brokerage(e),
            "exit_brokerage": brokerage(x),
            "transaction": rounded((e + x) * costs.transaction_rate),
            "stt": rounded(sell * costs.stt_sell_rate),
            "stamp": rounded(buy * costs.stamp_buy_rate),
            "sebi": rounded((e + x) * costs.sebi_rate),
            "ipft": rounded((e + x) * costs.ipft_rate),
        }
        components["gst"] = rounded(sum(components[k] for k in ("entry_brokerage", "exit_brokerage", "transaction", "sebi", "ipft")) * costs.gst_rate)
        components["total"] = sum(components.values())
        return tuple(sorted(components.items()))

def liquidation(position, raw_exit, config):
    """Pure executable liquidation estimate, shared by marking and closure."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = "ROUND_HALF_UP"
        side = "SELL" if position.side == "BUY" else "BUY"
        exit_fill = fill(raw_exit, side, config)
        breakdown = charges(position.entry, exit_fill, position.quantity, position.side, config.costs)
        gross = rounded((exit_fill - position.entry) * position.quantity * (1 if position.side == "BUY" else -1))
        return exit_fill, gross, breakdown, gross - dict(breakdown)["total"]


def levels(entry, atr, side):
    entry, atr = number(entry), number(atr)
    if side not in ("BUY", "SELL") or entry <= 0 or atr <= 0:
        raise ValueError("INVALID_PROTECTIVE_LEVELS")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = "ROUND_HALF_UP"
        sign = 1 if side == "BUY" else -1
        stop = rounded(entry - sign * Decimal("1.5") * atr, PRICE)
        target = rounded(entry + sign * Decimal("2") * atr, PRICE)
        if min(stop, target) <= 0 or (side == "BUY" and not stop < entry < target) or (side == "SELL" and not target < entry < stop):
            raise ValueError("INVALID_PROTECTIVE_LEVELS")
        return stop, target

def exit_quote(position, candle):
    p, c = position, candle
    if p.side == "BUY":
        if c.open <= p.stop:
            return c.open, "STOP_GAP"
        if c.open >= p.target:
            return c.open, "TARGET_GAP"
        if c.low <= p.stop:
            return p.stop, "STOP"
        if c.high >= p.target:
            return p.target, "TARGET"
    else:
        if c.open >= p.stop:
            return c.open, "STOP_GAP"
        if c.open <= p.target:
            return c.open, "TARGET_GAP"
        if c.high >= p.stop:
            return p.stop, "STOP"
        if c.low <= p.target:
            return p.target, "TARGET"
    return None
