"""Frozen value records. All timestamps must carry a timezone."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from .config import number, PRECISION

ZERO = Decimal("0")

@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self):
        if not isinstance(self.timestamp, datetime) or self.timestamp.utcoffset() is None:
            raise ValueError("Timezone-aware datetime required")
        for name in ("open", "high", "low", "close", "volume"):
            value = number(getattr(self, name))
            object.__setattr__(self, name, value)
            if value < 0 or (name != "volume" and value == 0):
                raise ValueError("Invalid OHLCV range")
        if not self.low <= self.open <= self.high or not self.low <= self.close <= self.high:
            raise ValueError("Invalid OHLC bounds")

@dataclass(frozen=True)
class Signal:
    side: str
    atr: Decimal | None = None

    def __post_init__(self):
        if self.side not in ("BUY", "SELL", "HOLD"):
            raise ValueError("Unsupported signal")
        if self.atr is not None:
            object.__setattr__(self, "atr", number(self.atr))

@dataclass(frozen=True)
class Intent:
    side: str
    atr: Decimal
    signal_timestamp: datetime
    signal_id: str

@dataclass(frozen=True)
class Position:
    side: str
    quantity: int
    entry: Decimal
    raw_entry: Decimal
    stop: Decimal
    target: Decimal
    reserve: Decimal
    entry_timestamp: datetime
    signal_id: str

@dataclass(frozen=True)
class Account:
    realized_equity: Decimal
    reserved: Decimal = ZERO
    unrealized_pnl: Decimal = ZERO
    projected_charges: Decimal = ZERO
    net_closed_pnl: Decimal = ZERO

    @property
    def available_cash(self):
        with localcontext() as ctx:
            ctx.prec = PRECISION
            ctx.rounding = "ROUND_HALF_UP"
            return self.realized_equity - self.reserved

    @property
    def marked_equity(self):
        with localcontext() as ctx:
            ctx.prec = PRECISION
            ctx.rounding = "ROUND_HALF_UP"
            return self.realized_equity + self.unrealized_pnl - self.projected_charges

@dataclass(frozen=True)
class Risk:
    day: str | None = None
    entries: int = 0
    closed_losses: Decimal = ZERO
    daily_net: Decimal = ZERO
    locked: bool = False

@dataclass(frozen=True)
class Event:
    sequence: int
    timestamp: datetime
    kind: str
    reason: str
    fields: tuple

@dataclass(frozen=True)
class State:
    account: Account
    risk: Risk
    position: Position | None = None
    pending: Intent | None = None
    processed: tuple = ()
    events: tuple = ()
    last_timestamp: datetime | None = None
    utc_offset: timedelta | None = None
