"""Explicit, immutable configuration; no environment or file configuration."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

PRECISION = 40
MONEY = Decimal("0.01")
PRICE = Decimal("0.000001")

def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("Expected a finite decimal number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal number") from exc
    if not result.is_finite() or result.copy_abs() > Decimal("1e15"):
        raise ValueError("Non-finite or out-of-range number")
    return result

def rounded(value, quantum=MONEY):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_UP
        return value.quantize(quantum, rounding=ROUND_HALF_UP)

def strict_keys(values, expected):
    if not isinstance(values, dict) or set(values) != set(expected):
        raise ValueError("Missing or unknown configuration keys")

@dataclass(frozen=True)
class Costs:
    version: str
    brokerage_rate: Decimal
    brokerage_min: Decimal
    brokerage_max: Decimal
    transaction_rate: Decimal
    stt_sell_rate: Decimal
    stamp_buy_rate: Decimal
    sebi_rate: Decimal
    ipft_rate: Decimal
    gst_rate: Decimal

    def __post_init__(self):
        if self.version != "PAPER_COST_V1":
            raise ValueError("Unsupported cost version")
        for name in self.__dataclass_fields__:
            if name == "version":
                continue
            value = number(getattr(self, name))
            object.__setattr__(self, name, value)
            if value < 0 or ("rate" in name and value > 1):
                raise ValueError("Invalid cost range")
        if self.brokerage_min > self.brokerage_max:
            raise ValueError("Invalid brokerage bounds")

@dataclass(frozen=True)
class Config:
    mode: str
    capital: Decimal
    risk_fraction: Decimal
    daily_trade_limit: int
    daily_loss_limit: Decimal
    maximum_notional: Decimal
    slippage_bps: Decimal
    costs: Costs
    instrument: str
    interval_seconds: int
    execution_policy: str

    def __post_init__(self):
        if self.mode != "PAPER" or self.execution_policy != "NEXT_OPEN_STOP_FIRST_V1":
            raise ValueError("Explicit supported PAPER mode/policy required")
        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise ValueError("Instrument required")
        if self.instrument != self.instrument.strip():
            raise ValueError("Ambiguous instrument identity")
        for name in ("daily_trade_limit", "interval_seconds"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError("Positive integer required")
        if self.interval_seconds > 86400:
            raise ValueError("Interval out of range")
        for name in ("capital", "risk_fraction", "daily_loss_limit", "maximum_notional", "slippage_bps"):
            value = number(getattr(self, name))
            object.__setattr__(self, name, value)
            if value < 0 or (name != "slippage_bps" and value == 0):
                raise ValueError("Invalid configuration range")
        if self.risk_fraction > 1 or self.slippage_bps >= 10000:
            raise ValueError("Invalid risk/slippage")
        if not isinstance(self.costs, Costs):
            raise ValueError("Explicit Costs required")
        if rounded(self.capital) != self.capital or rounded(self.daily_loss_limit) != self.daily_loss_limit:
            raise ValueError("Capital/loss limit must be exact cents")

def validate_config(values):
    strict_keys(values, Config.__dataclass_fields__)
    copied = dict(values)
    strict_keys(copied["costs"], Costs.__dataclass_fields__)
    copied["costs"] = Costs(**dict(copied["costs"]))
    return Config(**copied)
