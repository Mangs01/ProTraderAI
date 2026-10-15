"""Synthetic-only acceptance tests for the isolated in-memory paper engine."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext, ROUND_HALF_UP
import subprocess
import sys
from pathlib import Path

import pytest

from paper.offline.config import Config, Costs, validate_config
from paper.offline.models import Candle, Signal
from paper.offline.engine import PaperEngine
from paper.offline.execution import charges, fill, levels

D = Decimal
START = datetime(2026, 1, 5, 9, 15, tzinfo=timezone(timedelta(hours=5, minutes=30)))

def settings(**updates):
    result = dict(mode="PAPER", capital="10000", risk_fraction="0.01",
                  daily_trade_limit=5, daily_loss_limit="500", maximum_notional="10000",
                  slippage_bps="0", instrument="SYNTHETIC", interval_seconds=300,
                  execution_policy="NEXT_OPEN_STOP_FIRST_V1",
                  costs=dict(version="PAPER_COST_V1", brokerage_rate="0", brokerage_min="0",
                             brokerage_max="0", transaction_rate="0", stt_sell_rate="0",
                             stamp_buy_rate="0", sebi_rate="0", ipft_rate="0", gst_rate="0"))
    result.update(updates)
    return result

def config(**updates):
    return validate_config(settings(**updates))

def candle(i, open=100, high=101, low=99, close=100, volume=1000):
    return Candle(START + timedelta(minutes=5 * i), open, high, low, close, volume)

def entered(side="BUY", **updates):
    engine = PaperEngine(config(**updates))
    engine.process(candle(0, open=90, high=101, low=89, close=100), Signal(side, 2))
    engine.process(candle(1), Signal("HOLD"))
    assert engine.state.position is not None
    return engine

def exits(engine):
    return [e for e in engine.state.events if e.kind == "EXIT"]

def rejection(engine):
    return [e.reason for e in engine.state.events if e.kind == "REJECT"]

@pytest.mark.parametrize("key", list(settings()))
def test_every_configuration_key_is_required(key):
    values = settings()
    del values[key]
    with pytest.raises(ValueError):
        validate_config(values)

@pytest.mark.parametrize("updates", [
    {"mode": "LIVE"}, {"mode": None}, {"execution_policy": "OTHER"},
    {"extra": 1}, {"capital": "NaN"}, {"capital": "Infinity"},
    {"capital": 0}, {"capital": True}, {"capital": "0.001"},
    {"risk_fraction": 0}, {"risk_fraction": 1.1}, {"risk_fraction": float("nan")},
    {"daily_trade_limit": 0}, {"daily_trade_limit": 1.5}, {"daily_trade_limit": True},
    {"daily_loss_limit": -1}, {"maximum_notional": 0},
    {"slippage_bps": -1}, {"slippage_bps": 10000},
    {"interval_seconds": 0}, {"interval_seconds": 86401}, {"instrument": " "},
])
def test_configuration_fails_closed(updates):
    with pytest.raises(ValueError):
        config(**updates)

@pytest.mark.parametrize("change", ["missing", "extra", "negative", "version", "bounds", "nonfinite"])
def test_strict_cost_configuration(change):
    values = settings()
    costs = values["costs"]
    if change == "missing":
        del costs["gst_rate"]
    elif change == "extra":
        costs["unknown"] = 0
    elif change == "negative":
        costs["stt_sell_rate"] = -1
    elif change == "version":
        costs["version"] = "CURRENT_LIVE"
    elif change == "bounds":
        costs["brokerage_min"] = 1
    else:
        costs["gst_rate"] = "Infinity"
    with pytest.raises(ValueError):
        validate_config(values)

@pytest.mark.parametrize("side,expected", [("BUY", D("33")), ("SELL", D("-33"))])
def test_next_open_hold_account_and_immutable_state(side, expected):
    engine = entered(side)
    p = engine.state.position
    assert p.entry == 100 and p.quantity == 33
    assert p.reserve == 3300
    snapshot = engine.state
    state = engine.process(candle(2, high=102, low=99, close=101), Signal("HOLD"))
    assert state.position == p
    assert state.account.realized_equity == 10000
    assert state.account.available_cash == 6700
    assert state.account.unrealized_pnl == expected
    assert state.account.marked_equity == 10000 + expected
    assert snapshot.account.unrealized_pnl == 0
    with pytest.raises(FrozenInstanceError):
        state.position.quantity = 1
    assert state.risk.entries == 1

@pytest.mark.parametrize("side,open_,high,low,reason,price", [
    ("BUY", 100, 101, 97, "STOP", 97),
    ("BUY", 100, 104, 99, "TARGET", 104),
    ("SELL", 100, 103, 99, "STOP", 103),
    ("SELL", 100, 101, 96, "TARGET", 96),
    ("BUY", 90, 101, 89, "STOP_GAP", 90),
    ("BUY", 110, 111, 90, "TARGET_GAP", 110),
    ("SELL", 110, 111, 99, "STOP_GAP", 110),
    ("SELL", 90, 111, 89, "TARGET_GAP", 90),
    ("BUY", 100, 104, 97, "STOP", 97),
    ("SELL", 100, 103, 96, "STOP", 103),
])
def test_exit_precedence_and_exact_touches(side, open_, high, low, reason, price):
    engine = entered(side)
    p = engine.state.position
    state = engine.process(candle(2, open_, high, low, open_), Signal("HOLD"))
    event = exits(engine)[0]
    data = dict(event.fields)
    gross = (D(price) - p.entry) * p.quantity * (1 if side == "BUY" else -1)
    assert event.reason == reason
    assert data["raw_price"] == data["fill_price"] == price
    assert data["gross_pnl"] == data["net_pnl"] == gross
    assert state.position is None and state.account.reserved == 0
    assert state.account.available_cash == state.account.realized_equity == 10000 + gross
    assert state.account.net_closed_pnl == state.risk.daily_net == gross
    assert state.risk.closed_losses == max(0, -gross)
    prior = state
    engine.process(candle(2, open_, high, low, open_), Signal("HOLD"))
    assert engine.state is prior
    engine.process(candle(3), Signal("HOLD"))
    assert len(exits(engine)) == 1

@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_entry_candle_can_hit_stop(side):
    engine = PaperEngine(config())
    engine.process(candle(0), Signal(side, 2))
    engine.process(candle(1, high=105, low=95), Signal("HOLD"))
    assert len(exits(engine)) == 1 and exits(engine)[0].reason == "STOP"
    assert engine.state.risk.entries == 1 and engine.state.position is None

@pytest.mark.parametrize("side,entry,raw_exit,exit_fill", [
    ("BUY", D("100.05"), 90, D("89.955")),
    ("SELL", D("99.95"), 110, D("110.055")),
])
def test_adverse_slippage_applied_once(side, entry, raw_exit, exit_fill):
    engine = entered(side, slippage_bps=5)
    p = engine.state.position
    assert p.entry == entry
    engine.process(candle(2, raw_exit, max(111, raw_exit), min(89, raw_exit), raw_exit), Signal("HOLD"))
    data = dict(exits(engine)[0].fields)
    assert data["raw_price"] == raw_exit and data["fill_price"] == exit_fill
    assert data["gross_pnl"] == ((exit_fill - entry) * p.quantity * (1 if side == "BUY" else -1)).quantize(D("0.01"), rounding=ROUND_HALF_UP)

def test_hold_never_creates_or_closes_position():
    engine = PaperEngine(config())
    engine.process(candle(0), Signal("HOLD"))
    assert engine.state.position is None and engine.state.pending is None
    assert not engine.state.events

@pytest.mark.parametrize("atr", [None, 0, -1, D("0.00000001"), 100])
def test_invalid_atr_or_protective_levels_rejected(atr):
    engine = PaperEngine(config())
    engine.process(candle(0), Signal("BUY", atr))
    engine.process(candle(1), Signal("HOLD"))
    assert engine.state.position is None
    assert any(reason in ("INVALID_ATR", "INVALID_PROTECTIVE_LEVELS") for reason in rejection(engine))
    assert engine.state.account.realized_equity == 10000 and engine.state.risk.entries == 0

@pytest.mark.parametrize("updates,reason", [
    ({"risk_fraction": "0.00001"}, "ZERO_QUANTITY_RISK"),
    ({"capital": "99"}, "INSUFFICIENT_CASH"),
    ({"maximum_notional": "99"}, "NOTIONAL_LIMIT"),
])
def test_zero_quantity_cash_notional_rejections(updates, reason):
    engine = PaperEngine(config(**updates))
    account = engine.state.account
    engine.process(candle(0), Signal("BUY", 2))
    risk = engine.state.risk
    engine.process(candle(1), Signal("HOLD"))
    assert reason in rejection(engine)
    assert engine.state.account == account and engine.state.risk == risk

def test_cash_and_notional_caps_reduce_quantity():
    assert entered(maximum_notional=550).state.position.quantity == 5
    assert entered(capital=1000, risk_fraction=1).state.position.quantity == 10

def cost_profile():
    values = settings()["costs"]
    values.update(brokerage_rate="0.001", brokerage_min="5", brokerage_max="20",
                  transaction_rate="0.000030699", stt_sell_rate="0.00025",
                  stamp_buy_rate="0.00003", sebi_rate="0.000001",
                  ipft_rate="0.000000001", gst_rate="0.18")
    return values

@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_directional_charges_reconcile_once(side):
    cfg = config(costs=cost_profile())
    engine = entered(side, costs=cost_profile())
    p = engine.state.position
    assert p.quantity < 33
    assert p.reserve > p.entry * p.quantity
    stopfill = fill(p.stop, "SELL" if side == "BUY" else "BUY", cfg)
    stopfees = dict(charges(p.entry, stopfill, p.quantity, side, cfg.costs))["total"]
    assert abs(p.entry - stopfill) * p.quantity + stopfees <= cfg.capital * cfg.risk_fraction
    engine.process(candle(2, 110, 111, 89, 110), Signal("HOLD"))
    event = dict(exits(engine)[0].fields)
    components = dict(event["charges"])
    assert components["total"] == sum(v for k, v in components.items() if k != "total")
    assert event["net_pnl"] == event["gross_pnl"] - components["total"]
    assert engine.state.account.realized_equity == cfg.capital + event["net_pnl"]
    assert engine.state.account.net_closed_pnl == event["net_pnl"]
    expected_sell = D("110") if side == "BUY" else p.entry
    expected_buy = p.entry if side == "BUY" else D("110")
    assert components["stt"] == (expected_sell * p.quantity * cfg.costs.stt_sell_rate).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    assert components["stamp"] == (expected_buy * p.quantity * cfg.costs.stamp_buy_rate).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    engine.process(candle(3), Signal("HOLD"))
    assert engine.state.account.realized_equity == cfg.capital + event["net_pnl"]

@pytest.mark.parametrize("turnover,expected", [(1, 5), (10000, 10), (100000, 20)])
def test_brokerage_floor_percentage_cap(turnover, expected):
    fees = dict(charges(turnover, turnover, 1, "BUY", config(costs=cost_profile()).costs))
    assert fees["entry_brokerage"] == fees["exit_brokerage"] == expected
    taxable = sum(fees[k] for k in ("entry_brokerage", "exit_brokerage", "transaction", "sebi", "ipft"))
    assert fees["gst"] == (taxable * D("0.18")).quantize(D("0.01"), rounding=ROUND_HALF_UP)

def test_cost_reserve_blocks_apparently_affordable_one_share():
    engine = PaperEngine(config(capital=100, risk_fraction=1, costs=cost_profile()))
    engine.process(candle(0), Signal("BUY", 2))
    engine.process(candle(1), Signal("HOLD"))
    assert "INSUFFICIENT_CASH" in rejection(engine)
    assert engine.state.account.available_cash == 100

def test_daily_trade_limit_counts_fills_not_attempts():
    engine = entered(daily_trade_limit=1)
    engine.process(candle(2, high=104), Signal("BUY", 2))
    assert "DAILY_TRADE_LIMIT" in rejection(engine)
    assert engine.state.risk.entries == 1 and engine.state.pending is None

def test_loss_lock_gap_can_exceed_modeled_limit():
    engine = entered(daily_loss_limit=20)
    assert engine.state.position.quantity == 6
    engine.process(candle(2, 90, 91, 89, 90), Signal("BUY", 2))
    assert engine.state.risk.closed_losses == 60
    assert engine.state.risk.locked and "DAILY_LOSS_LIMIT" in rejection(engine)

def test_wins_do_not_cancel_cumulative_loss_and_next_day_resets_flat():
    engine = entered(daily_loss_limit=100)
    engine.process(candle(2, low=97), Signal("BUY", 2))
    assert engine.state.risk.closed_losses == 99
    engine.process(candle(3), Signal("HOLD"))
    assert engine.state.position is None  # remaining budget cannot fund one share
    assert "ZERO_QUANTITY_RISK" in rejection(engine)
    tomorrow = Candle(START + timedelta(days=1), 100, 101, 99, 100, 1000)
    engine.process(tomorrow, Signal("HOLD"))
    assert engine.state.risk.entries == 0 and engine.state.risk.closed_losses == 0

def test_profitable_trade_preserves_cumulative_closed_losses():
    engine = entered(daily_loss_limit=500)
    engine.process(candle(2, low=97), Signal("BUY", 2))
    losses = engine.state.risk.closed_losses
    engine.process(candle(3), Signal("HOLD"))
    engine.process(candle(4, high=104), Signal("HOLD"))
    assert engine.state.risk.daily_net > 0
    assert engine.state.risk.closed_losses == losses

def test_duplicate_signals_and_conflicting_candles():
    engine = PaperEngine(config())
    c, s = candle(0), Signal("BUY", 2)
    prior = engine.process(c, s)
    assert engine.process(c, s) is prior
    assert len(prior.events) == 1
    with pytest.raises(ValueError):
        engine.process(c, Signal("SELL", 2))
    with pytest.raises(ValueError):
        engine.process(candle(0, close=101), s)
    assert engine.state is prior
    engine.process(candle(1), Signal("BUY", 2))
    assert engine.state.risk.entries == 1 and "POSITION_OPEN" in rejection(engine)

def test_missing_next_candle_cancels_instead_of_delayed_fill():
    engine = PaperEngine(config())
    engine.process(candle(0), Signal("BUY", 2))
    engine.process(candle(2), Signal("HOLD"))
    assert engine.state.position is None
    assert any(e.reason == "MISSING_NEXT_CANDLE" for e in engine.state.events)

def test_open_position_date_change_fails_without_mutation():
    engine = entered()
    prior = engine.state
    with pytest.raises(ValueError):
        engine.process(Candle(START + timedelta(days=1), 100, 101, 99, 100, 1), Signal("HOLD"))
    assert engine.state is prior

@pytest.mark.parametrize("stamp", ["2026-01-05", None, datetime(2026, 1, 5)])
def test_invalid_timestamp(stamp):
    with pytest.raises(ValueError):
        Candle(stamp, 100, 101, 99, 100, 1)

@pytest.mark.parametrize("name,value", [
    ("open", 102), ("close", 98), ("low", 102), ("high", 98),
    ("open", 0), ("volume", -1), ("high", "NaN"), ("low", float("inf")),
    ("close", "-Infinity"), ("volume", True),
])
def test_invalid_ohlcv(name, value):
    values = dict(timestamp=START, open=100, high=101, low=99, close=100, volume=1)
    values[name] = value
    with pytest.raises(ValueError):
        Candle(**values)

def test_out_of_order_and_timezone_change_fail_closed():
    engine = entered()
    prior = engine.state
    with pytest.raises(ValueError):
        engine.process(candle(-1), Signal("HOLD"))
    with pytest.raises(ValueError):
        engine.process(Candle((START + timedelta(minutes=10)).astimezone(timezone.utc), 100, 101, 99, 100, 1), Signal("HOLD"))
    assert engine.state is prior

@pytest.mark.parametrize("side,atr", [("WAIT", 2), ("BUY", "NaN"), ("SELL", "Infinity")])
def test_invalid_signals(side, atr):
    with pytest.raises(ValueError):
        Signal(side, atr)

def test_decimal_execution_independent_of_ambient_precision():
    outputs = []
    for precision in (6, 28):
        with localcontext() as ctx:
            ctx.prec = precision
            engine = entered(costs=cost_profile(), slippage_bps=5)
            engine.process(candle(2, 90, 101, 89, 90), Signal("HOLD"))
            outputs.append(engine.state)
    assert outputs[0] == outputs[1]

def test_fresh_process_import_and_broker_isolation():
    root = str(Path(__file__).resolve().parents[1])
    code = '''
import sys, builtins, io, os, socket, importlib.abc
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import dataclass
sys.path.insert(0, ROOT)
attempts = []
def deny(*args, **kwargs):
    attempts.append("io_or_credential_or_order")
    raise AssertionError("Forbidden application access")
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"broker", "SmartApi", "smartapi", "dotenv", "config", "backtest", "research", "ai_research", "requests", "urllib", "live", "data", "execution", "strategy"}:
            attempts.append(fullname)
            raise AssertionError("Forbidden import: " + fullname)
sys.meta_path.insert(0, Guard())
original_import = builtins.__import__
def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name.split(".")[0] in {"broker", "SmartApi", "smartapi", "dotenv", "config", "backtest", "research", "ai_research", "live", "data", "execution", "strategy"}:
        attempts.append(name)
        raise AssertionError("Forbidden import: " + name)
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = guarded_import
class ForbiddenEnvironment(dict):
    def __getitem__(self, key): return deny()
    def get(self, *a): return deny()
    def __iter__(self): return deny()
os.environ = ForbiddenEnvironment()
os.getenv = deny
builtins.open = deny
io.open = deny
os.mkdir = deny
os.makedirs = deny
socket.create_connection = deny
socket.getaddrinfo = deny
socket.socket.connect = deny
socket.socket.connect_ex = deny
socket.socket.send = deny
socket.socket.sendall = deny
# Inert SDK stand-ins ensure any order-method call is observable without
# importing the real SDK, credentials, or broker wrappers.
import types
sdk = types.ModuleType("SmartApi")
class TrapBroker:
    def __init__(self, *a, **k): deny()
    login = place_order = modify_order = cancel_order = deny
    placeOrder = modifyOrder = cancelOrder = deny
sdk.SmartConnect = TrapBroker
sys.modules["SmartApi"] = sdk
from paper.offline.config import validate_config
from paper.offline.models import Candle, Signal
from paper.offline.engine import PaperEngine
from paper.offline.execution import charges
values = VALUES
engine = PaperEngine(validate_config(values))
start = datetime(2026, 1, 5, 9, 15, tzinfo=timezone.utc)
engine.process(Candle(start, 100, 101, 99, 100, 1), Signal("BUY", 2))
engine.process(Candle(start + timedelta(minutes=5), 100, 105, 95, 100, 1), Signal("HOLD"))
assert engine.state.position is None
assert any(e.kind == "EXIT" for e in engine.state.events)
assert attempts == [], attempts
assert not any(name.split(".")[0] in {"broker", "backtest", "research", "ai_research", "dotenv", "config", "strategy"} for name in sys.modules)
print("ISOLATION_OK: zero application IO, credential, network, broker imports/order calls")
'''.replace("ROOT", repr(root)).replace("VALUES", repr(settings()))
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ISOLATION_OK" in result.stdout

@pytest.mark.parametrize("side,atr", [("BUY", 0), ("SELL", -2), ("OTHER", 2), ("BUY", "NaN")])
def test_protective_level_helper_rejects_invalid_side_or_distance(side, atr):
    with pytest.raises(ValueError):
        levels(D("100"), atr, side)

def test_entry_revalidated_using_actual_next_open_not_signal_close():
    engine = PaperEngine(config(maximum_notional=150))
    engine.process(candle(0), Signal("BUY", 2))
    engine.process(candle(1, 200, 201, 199, 200), Signal("HOLD"))
    assert "NOTIONAL_LIMIT" in rejection(engine)
    assert engine.state.account.realized_equity == 10000
    assert engine.state.account.reserved == 0 and engine.state.risk.entries == 0

@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_intrabar_target_slippage_once(side):
    engine = entered(side, slippage_bps=5)
    position = engine.state.position
    engine.process(candle(2, 100, 105 if side == "BUY" else 101,
                          99 if side == "BUY" else 95, 100), Signal("HOLD"))
    event = exits(engine)[0]
    fields = dict(event.fields)
    assert event.reason == "TARGET"
    assert fields["raw_price"] == position.target
    assert fields["fill_price"] == fill(position.target, "SELL" if side == "BUY" else "BUY", config(slippage_bps=5))

def test_missing_next_date_cancels_intent_without_fill():
    engine = PaperEngine(config())
    engine.process(candle(0), Signal("BUY", 2))
    engine.process(Candle(START + timedelta(days=1), 100, 101, 99, 100, 1), Signal("HOLD"))
    assert engine.state.pending is None and engine.state.position is None
    assert any(e.reason == "DATE_CHANGED" for e in engine.state.events)

def test_fresh_replay_produces_identical_events_and_account():
    engines = [PaperEngine(config(costs=cost_profile(), slippage_bps=5)) for _ in range(2)]
    tape = [(candle(0), Signal("BUY", 2)),
            (candle(1), Signal("HOLD")),
            (candle(2, high=105), Signal("SELL", 2)),
            (candle(3), Signal("HOLD")),
            (candle(4, low=95), Signal("HOLD"))]
    for engine in engines:
        for c, s in tape:
            engine.process(c, s)
    assert engines[0].state == engines[1].state
    assert len(exits(engines[0])) == 2
    assert [e.sequence for e in engines[0].state.events] == list(range(1, len(engines[0].state.events) + 1))
    nets = sum(dict(e.fields)["net_pnl"] for e in exits(engines[0]))
    assert engines[0].state.account.realized_equity == 10000 + nets

def test_account_properties_use_fixed_decimal_context():
    engine = entered(costs=cost_profile())
    engine.process(candle(2, close=101, high=102), Signal("HOLD"))
    a = engine.state.account
    expected = (a.available_cash, a.marked_equity)
    with localcontext() as ctx:
        ctx.prec = 3
        assert (a.available_cash, a.marked_equity) == expected

def test_invalid_process_types_do_not_mutate():
    engine = PaperEngine(config())
    prior = engine.state
    with pytest.raises(ValueError):
        engine.process("candle", Signal("HOLD"))
    with pytest.raises(ValueError):
        engine.process(candle(0), "BUY")
    assert engine.state is prior

@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_loss_exceeding_equity_is_not_clipped_and_blocks_entries(side):
    engine = entered(side, capital=1000, risk_fraction=1, daily_loss_limit=10000)
    gap = 1 if side == "BUY" else 1000
    engine.process(candle(2, gap, max(gap, 100), min(gap, 100), gap), Signal("BUY", 2))
    if side == "SELL":
        assert engine.state.account.realized_equity < 0 and engine.state.risk.locked
        assert "DAILY_LOSS_LIMIT" in rejection(engine)
    assert engine.state.account.reserved == 0

def test_noninterval_timestamp_fails_closed():
    engine = entered()
    prior = engine.state
    c = Candle(START + timedelta(minutes=10, seconds=1), 100, 101, 99, 100, 1)
    with pytest.raises(ValueError):
        engine.process(c, Signal("HOLD"))
    assert engine.state is prior


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("with_costs", [False, True])
@pytest.mark.parametrize("close", [D("100"), D("101.123456")])
def test_marked_equity_matches_hypothetical_executable_liquidation(side, with_costs, close):
    from paper.offline.execution import liquidation
    from paper.offline.models import Account

    cfg = config(slippage_bps=5, **({"costs": cost_profile()} if with_costs else {}))
    engine = entered(side, slippage_bps=5,
                     **({"costs": cost_profile()} if with_costs else {}))
    prior = engine.state
    position = prior.position
    state = engine.process(candle(2, high=102, close=close), Signal("HOLD"))
    # Independent hypothetical transaction: one adverse exit fill and one set
    # of round-trip charges. Entry fill already includes entry slippage.
    direction = D("1") if side == "BUY" else D("-1")
    exit_fill = (close * (1 - direction * D("0.0005"))).quantize(
        D("0.000001"), rounding=ROUND_HALF_UP)
    gross = ((exit_fill - position.entry) * position.quantity * direction).quantize(
        D("0.01"), rounding=ROUND_HALF_UP)
    fees = dict(charges(position.entry, exit_fill, position.quantity, side, cfg.costs))["total"]
    expected_equity = prior.account.realized_equity + gross - fees
    quoted_fill, quoted_gross, quoted_charges, quoted_net = liquidation(position, close, cfg)
    assert (quoted_fill, quoted_gross, dict(quoted_charges)["total"]) == (exit_fill, gross, fees)
    hypothetical_closed_account = Account(
        prior.account.realized_equity + quoted_net,
        net_closed_pnl=prior.account.net_closed_pnl + quoted_net)
    assert state.account.marked_equity == hypothetical_closed_account.realized_equity
    assert state.account.marked_equity == expected_equity
    assert state.account.unrealized_pnl == gross
    assert state.account.projected_charges == fees
    assert state.account.realized_equity == prior.account.realized_equity
    assert state.account.net_closed_pnl == prior.account.net_closed_pnl == 0
    assert state.account.reserved == prior.account.reserved == position.reserve
    assert state.account.available_cash == prior.account.available_cash
    assert state.position == position and state.risk == prior.risk
    assert state.events == prior.events and not exits(engine)
    assert engine.process(candle(2, high=102, close=close), Signal("HOLD")) is state
    if not with_costs and close == 100:
        assert position.quantity == 32
        assert expected_equity == D("9996.80")
        old_mark = prior.account.realized_equity + (
            (close - position.entry) * position.quantity * direction).quantize(D("0.01"))
        assert old_mark == D("9998.40")


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_marking_and_actual_closure_share_liquidation_accounting(side):
    from paper.offline.execution import liquidation

    engine = entered(side, slippage_bps=5, costs=cost_profile())
    before = engine.state
    position = before.position
    # A hypothetical liquidation quote must produce the same net equity as
    # a subsequent actual simulated gap closure at that raw price.
    raw_exit = D("90") if side == "BUY" else D("110")
    exit_fill, gross, breakdown, net = liquidation(position, raw_exit, engine._config)
    state = engine.process(candle(2, raw_exit, max(111, raw_exit), min(89, raw_exit), raw_exit),
                           Signal("HOLD"))
    fields = dict(exits(engine)[0].fields)
    assert fields["fill_price"] == exit_fill
    assert fields["gross_pnl"] == gross
    assert fields["charges"] == breakdown and fields["net_pnl"] == net
    assert state.account.realized_equity == before.account.realized_equity + net
    assert state.account.reserved == 0 and state.account.projected_charges == 0
    assert state.account.marked_equity == state.account.realized_equity


@pytest.mark.parametrize("index", [0, 1])
def test_equivalent_instant_with_different_offset_rejects_before_duplicate(index):
    engine = entered()
    prior = engine.state
    original, signal = prior.processed[index]
    converted = Candle(original.timestamp.astimezone(timezone.utc), original.open,
                       original.high, original.low, original.close, original.volume)
    assert converted == original  # datetime equality alone loses offset identity.
    with pytest.raises(ValueError, match="Timezone offset changed"):
        engine.process(converted, signal)
    assert engine.state is prior and engine.state.events is prior.events
    assert engine.process(original, signal) is prior
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        engine.process(original, Signal("SELL", 2))
    assert engine.state is prior
    following = engine.process(candle(2), Signal("HOLD"))
    assert following.last_timestamp == candle(2).timestamp
    assert following.position == prior.position


def test_first_candle_anchors_interval_grid_without_session_origin():
    engine = PaperEngine(config())
    start = START + timedelta(seconds=1, microseconds=123)
    first = Candle(start, 100, 101, 99, 100, 1)
    state = engine.process(first, Signal("HOLD"))
    assert engine.process(first, Signal("HOLD")) is state
    second = Candle(start + timedelta(seconds=300), 100, 101, 99, 100, 1)
    state = engine.process(second, Signal("HOLD"))
    misaligned = Candle(start + timedelta(seconds=601), 100, 101, 99, 100, 1)
    with pytest.raises(ValueError, match="interval grid"):
        engine.process(misaligned, Signal("HOLD"))
    assert engine.state is state


@pytest.mark.parametrize("multiple", [2, 3, 12])
def test_missing_expected_candle_cancels_pending_and_preserves_account(multiple):
    engine = PaperEngine(config())
    prior = engine.process(candle(0), Signal("BUY", 2))
    state = engine.process(candle(multiple), Signal("HOLD"))
    assert state.pending is None and state.position is None
    assert state.account == prior.account and state.risk == prior.risk
    added = state.events[len(prior.events):]
    assert len(added) == 1
    assert (added[0].kind, added[0].reason) == ("CANCEL", "MISSING_NEXT_CANDLE")


def test_integer_multiple_source_interval_cannot_be_authenticated_from_timestamps():
    # A ten-minute source and a five-minute source with every other candle
    # missing produce identical timestamps. Both are accepted as sparse input;
    # neither may execute an intent after skipping its expected next candle.
    engine = PaperEngine(config())
    for index in (0, 2, 4, 6):
        engine.process(candle(index), Signal("BUY", 2))
    assert engine.state.position is None and engine.state.risk.entries == 0
    assert len([e for e in engine.state.events if e.reason == "MISSING_NEXT_CANDLE"]) == 3
    assert engine.state.pending.signal_timestamp == candle(6).timestamp


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_valid_sparse_input_monitors_existing_position_without_inventing_bars(side):
    engine = entered(side)
    prior = engine.state
    state = engine.process(candle(4), Signal("HOLD"))
    assert state.position == prior.position and state.events == prior.events
    assert len(state.processed) == len(prior.processed) + 1
    assert state.last_timestamp == candle(4).timestamp
    state = engine.process(candle(6, high=104 if side == "BUY" else 101,
                                  low=99 if side == "BUY" else 96), Signal("HOLD"))
    assert state.position is None
    assert len(exits(engine)) == 1 and exits(engine)[0].reason == "TARGET"
