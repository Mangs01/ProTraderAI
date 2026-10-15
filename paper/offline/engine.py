"""Single-authority in-memory transitions. No persistence or session liquidation."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
from .config import Config, PRECISION, rounded
from .models import Account, Candle, Event, Intent, Position, Risk, Signal, State
from .execution import charges, exit_quote, fill, levels, liquidation

class PaperEngine:
    def __init__(self, config):
        if not isinstance(config, Config):
            raise ValueError("Validated explicit configuration required")
        self._config = config
        self._state = State(Account(config.capital), Risk())

    @property
    def state(self):
        return self._state

    def process(self, candle, signal):
        if not isinstance(candle, Candle) or not isinstance(signal, Signal):
            raise ValueError("Validated candle and injected signal required")
        with localcontext() as ctx:
            ctx.prec = PRECISION
            ctx.rounding = "ROUND_HALF_UP"
            result = self._advance(candle, signal)
        self._state = result
        return result

    def _advance(self, c, signal):
        cfg, old = self._config, self._state
        # Aware datetime equality compares instants, so validate fixed-offset
        # identity before accepting an otherwise identical replay.
        if old.utc_offset is not None and c.timestamp.utcoffset() != old.utc_offset:
            raise ValueError("Timezone offset changed")
        for previous, previous_signal in old.processed:
            if previous.timestamp == c.timestamp:
                if previous == c and previous_signal == signal:
                    return old
                raise ValueError("Conflicting duplicate candle/signal")
        if old.last_timestamp is not None and c.timestamp <= old.last_timestamp:
            raise ValueError("Nonchronological candle")
        # The first candle anchors the grid; no session origin is supplied.
        # Integer-multiple gaps are permitted. Timestamps alone cannot distinguish
        # missing candles from a different source interval; pending fills still
        # require the immediately expected next candle below.
        if old.last_timestamp is not None and (c.timestamp - old.last_timestamp) % timedelta(seconds=cfg.interval_seconds):
            raise ValueError("Candle not on declared interval grid")
        a, r, p, pending = old.account, old.risk, old.position, old.pending
        events = list(old.events)
        def emit(kind, reason, **fields):
            events.append(Event(len(events) + 1, c.timestamp, kind, reason, tuple(sorted(fields.items()))))
        day = c.timestamp.date().isoformat()
        if r.day != day:
            if p is not None:
                raise ValueError("Open position cannot cross date; no liquidation implemented")
            if pending is not None:
                emit("CANCEL", "DATE_CHANGED", signal_id=pending.signal_id)
            pending = None
            r = Risk(day)
        if pending is not None:
            intent, pending = pending, None
            if c.timestamp != intent.signal_timestamp + timedelta(seconds=cfg.interval_seconds):
                emit("CANCEL", "MISSING_NEXT_CANDLE", signal_id=intent.signal_id)
            else:
                reason = None
                if r.locked:
                    reason = "DAILY_LOSS_LIMIT"
                elif r.entries >= cfg.daily_trade_limit:
                    reason = "DAILY_TRADE_LIMIT"
                entry = fill(c.open, intent.side, cfg)
                try:
                    stop, target = levels(entry, intent.atr, intent.side)
                except ValueError:
                    reason = reason or "INVALID_PROTECTIVE_LEVELS"
                if reason is None:
                    closing_side = "SELL" if intent.side == "BUY" else "BUY"
                    stop_fill = fill(stop, closing_side, cfg)
                    per_share = abs(entry - stop_fill)
                    risk_budget = min(a.realized_equity * cfg.risk_fraction, cfg.daily_loss_limit - r.closed_losses)
                    # Reserve full entry notional plus round-trip costs evaluated
                    # at the larger protective price. This is a bounded scenario,
                    # never a guarantee against arbitrary opening gaps.
                    reserve_price = max(entry, stop_fill, fill(target, closing_side, cfg))
                    cap = min(int(cfg.maximum_notional / entry), max(0, int(a.available_cash / entry)), max(0, int(risk_budget / per_share)))
                    def metrics(q):
                        fees = dict(charges(entry, stop_fill, q, intent.side, cfg.costs))["total"]
                        cost_reserve = dict(charges(entry, reserve_price, q, intent.side, cfg.costs))["total"]
                        return rounded(per_share * q) + fees, entry * q + cost_reserve
                    lo, hi = 0, cap
                    while lo < hi:
                        mid = (lo + hi + 1) // 2
                        loss, reserve = metrics(mid)
                        if loss <= risk_budget and reserve <= a.available_cash:
                            lo = mid
                        else:
                            hi = mid - 1
                    if lo == 0:
                        one_loss, one_reserve = metrics(1)
                        if entry > cfg.maximum_notional:
                            reason = "NOTIONAL_LIMIT"
                        elif one_reserve > a.available_cash:
                            reason = "INSUFFICIENT_CASH"
                        else:
                            reason = "ZERO_QUANTITY_RISK"
                    else:
                        _, reserve = metrics(lo)
                        p = Position(intent.side, lo, entry, c.open, stop, target, reserve, c.timestamp, intent.signal_id)
                        a = replace(a, reserved=reserve)
                        r = replace(r, entries=r.entries + 1)
                        emit("ENTRY", "NEXT_OPEN", side=p.side, quantity=lo, raw_price=c.open, fill_price=entry, stop=stop, target=target, reserve=reserve, signal_id=intent.signal_id)
                if reason is not None:
                    emit("REJECT", reason, signal_id=intent.signal_id)
        if p is not None:
            quote = exit_quote(p, c)
            if quote is not None:
                raw, reason = quote
                exit_fill, gross, breakdown, net = liquidation(p, raw, cfg)
                a = Account(a.realized_equity + net, net_closed_pnl=a.net_closed_pnl + net)
                losses = r.closed_losses + max(Decimal("0"), -net)
                r = replace(r, closed_losses=losses, daily_net=r.daily_net + net, locked=losses >= cfg.daily_loss_limit or a.realized_equity <= 0)
                emit("EXIT", reason, side=p.side, quantity=p.quantity, raw_price=raw, fill_price=exit_fill, entry=p.entry, gross_pnl=gross, charges=breakdown, net_pnl=net, realized_equity=a.realized_equity, signal_id=p.signal_id)
                p = None
            else:
                # Mark estimated executable liquidation equity. The shared
                # quote includes one adverse exit fill and full round-trip
                # charges; reserves are cash constraints, not extra losses.
                _, gross, breakdown, _ = liquidation(p, c.close, cfg)
                projected = dict(breakdown)["total"]
                a = replace(a, unrealized_pnl=gross, projected_charges=projected)
        # Injection is interpreted only at completion, after execution/monitoring.
        if signal.side != "HOLD":
            signal_id = f"{cfg.instrument}|{cfg.interval_seconds}|{c.timestamp.isoformat()}|{signal.side}"
            reason = None
            if signal.atr is None or signal.atr <= 0:
                reason = "INVALID_ATR"
            elif p is not None:
                reason = "POSITION_OPEN"
            elif r.locked:
                reason = "DAILY_LOSS_LIMIT"
            elif r.entries >= cfg.daily_trade_limit:
                reason = "DAILY_TRADE_LIMIT"
            if reason:
                emit("REJECT", reason, signal_id=signal_id)
            else:
                pending = Intent(signal.side, signal.atr, c.timestamp, signal_id)
                emit("INTENT", "SIGNAL_CLOSE", side=signal.side, atr=signal.atr, signal_id=signal_id)
        return State(a, r, p, pending, old.processed + ((c, signal),), tuple(events), c.timestamp, c.timestamp.utcoffset())
