from datetime import date, time
from unittest.mock import patch

import pandas as pd
import pytest

from backtest.backtest_engine import BacktestEngine
from backtest.backtest_runner import BacktestRunner


class SignalOnce:
    def __init__(self, side):
        self.side = side
        self.calls = 0

    def get_signal(self, _df):
        self.calls += 1
        return self.side if self.calls == 1 else "HOLD"


def runner_frame(rows):
    return pd.DataFrame([
        dict(datetime=stamp, open=open_, high=high, low=low,
             close=close, volume=1000, ATR=atr)
        for stamp, open_, high, low, close, atr in rows
    ])


def daily_runner(side):
    df = runner_frame([
        ("2026-09-01", 90, 151, 89, 150, 10),
        ("2026-09-02", 100, 101, 99, 100, 10),
        ("2026-09-03", 100, 101, 99, 100, 10),
    ])
    runner = BacktestRunner(df, interval="ONE_DAY")
    runner.prepare_indicators = lambda: None
    runner.strategy = SignalOnce(side)
    return runner


@pytest.mark.parametrize("side, expected_fill", [
    ("BUY", 100.05),
    ("SELL", 99.95),
])
def test_signal_executes_at_next_bar_open_with_adverse_slippage(side, expected_fill):
    runner = daily_runner(side)
    runner.run()
    trade = runner.engine.trades[0]
    assert trade["signal_index"] == 0
    assert trade["entry_index"] == 1
    assert trade["raw_entry_price"] == 100.0
    assert trade["entry"] == pytest.approx(expected_fill)
    assert trade["entry"] != 150.0


def test_pending_entry_at_dataset_end_is_cancelled():
    runner = BacktestRunner(
        runner_frame([("2026-09-01", 100, 101, 99, 100, 10)]),
        interval="ONE_DAY",
    )
    runner.prepare_indicators = lambda: None
    runner.strategy = SignalOnce("BUY")
    result = runner.run()
    assert result["total_trades"] == 0
    assert runner.engine.position is None
    assert runner.pending_entry is None


def complete_session(day="2026-09-01"):
    stamps = pd.date_range(
        f"{day} 09:15", f"{day} 15:25", freq="5min", tz="Asia/Kolkata"
    )
    return pd.DataFrame({
        "datetime": stamps,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1000.0,
        "ATR": 100.0,
    })


class SignalAt:
    def __init__(self, at):
        self.at = at

    def get_signal(self, df):
        return "BUY" if df.iloc[-1]["datetime"].time() == self.at else "HOLD"


def intraday_runner(strategy, **kwargs):
    runner = BacktestRunner(
        complete_session(), interval="FIVE_MINUTE", **kwargs
    )
    runner.prepare_indicators = lambda: None
    runner.strategy = strategy
    return runner


def test_pending_entry_is_cancelled_when_next_bar_reaches_cutoff():
    runner = intraday_runner(SignalAt(time(15, 10)))
    runner.run()
    assert runner.engine.trades == []
    assert runner.engine.position is None
    assert runner.pending_entry is None


def test_pending_entry_never_executes_on_forced_exit_bar():
    runner = intraday_runner(
        SignalAt(time(15, 20)), last_entry_cutoff="15:30"
    )
    runner.run()
    assert runner.engine.trades == []
    assert runner.pending_entry is None


def test_intraday_pending_entry_cannot_cross_trading_date():
    runner = intraday_runner(SignalAt(time(9, 15)))
    runner.pending_entry = {
        "side": "BUY",
        "atr": 10.0,
        "signal_index": 74,
        "signal_timestamp": pd.Timestamp("2026-09-01 15:25+05:30"),
    }
    assert runner._pending_can_execute(
        75, pd.Timestamp("2026-09-02 09:15+05:30")
    ) is False


def test_entry_slippage_applied_once_and_levels_use_actual_fill():
    engine = BacktestEngine(slippage_bps=5)
    engine.execute_entry("BUY", 100.0, 10.0, 1)
    assert engine.position["raw_entry_price"] == 100.0
    assert engine.position["entry"] == pytest.approx(100.05)
    assert engine.position["entry_slippage"] == pytest.approx(0.05)
    assert engine.position["stop_loss"] == pytest.approx(85.05)
    assert engine.position["target"] == pytest.approx(120.05)


@pytest.mark.parametrize("side,open_,expected_reason,expected_raw,expected_fill", [
    ("BUY", 80.0, "STOP_LOSS", 80.0, 79.96),
    ("BUY", 130.0, "TARGET", 130.0, 129.935),
    ("SELL", 120.0, "STOP_LOSS", 120.0, 120.06),
    ("SELL", 70.0, "TARGET", 70.0, 70.035),
])
def test_gap_exit_uses_open_then_adverse_slippage(
    side, open_, expected_reason, expected_raw, expected_fill
):
    engine = BacktestEngine(slippage_bps=5)
    engine.open_trade(
        side, 100.0, 90.0 if side == "BUY" else 110.0,
        120.0 if side == "BUY" else 80.0, 0
    )
    engine.check_exit(
        high=max(open_, 100.0), low=min(open_, 100.0), candle_index=1,
        open_price=open_
    )
    trade = engine.trades[0]
    assert trade["reason"] == expected_reason
    assert trade["raw_exit_price"] == expected_raw
    assert trade["exit"] == pytest.approx(expected_fill)


@pytest.mark.parametrize("side,high,low,reason,raw,fill", [
    ("BUY", 105.0, 89.0, "STOP_LOSS", 90.0, 89.955),
    ("BUY", 121.0, 95.0, "TARGET", 120.0, 119.94),
    ("SELL", 111.0, 95.0, "STOP_LOSS", 110.0, 110.055),
    ("SELL", 105.0, 79.0, "TARGET", 80.0, 80.04),
])
def test_normal_intrabar_exit_policy(side, high, low, reason, raw, fill):
    engine = BacktestEngine(slippage_bps=5)
    engine.open_trade(
        side, 100.0, 90.0 if side == "BUY" else 110.0,
        120.0 if side == "BUY" else 80.0, 0
    )
    engine.check_exit(high, low, 1, open_price=100.0)
    trade = engine.trades[0]
    assert trade["reason"] == reason
    assert trade["raw_exit_price"] == raw
    assert trade["exit"] == pytest.approx(fill)


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_ambiguous_intrabar_candle_uses_stop_first(side):
    engine = BacktestEngine(slippage_bps=5)
    engine.open_trade(
        side, 100.0, 90.0 if side == "BUY" else 110.0,
        120.0 if side == "BUY" else 80.0, 0
    )
    engine.check_exit(121.0, 79.0, 1, open_price=100.0)
    assert engine.trades[0]["reason"] == "STOP_LOSS"
    assert engine.trades[0]["raw_exit_price"] == (
        90.0 if side == "BUY" else 110.0
    )


@pytest.mark.parametrize("side,method,raw,expected", [
    ("BUY", "close_end_of_session", 100.0, 99.95),
    ("SELL", "close_end_of_session", 100.0, 100.05),
    ("BUY", "close_open_position", 100.0, 99.95),
    ("SELL", "close_open_position", 100.0, 100.05),
])
def test_market_closures_apply_one_adverse_exit_slippage(side, method, raw, expected):
    engine = BacktestEngine(slippage_bps=5)
    engine.open_trade(
        side, 100.0, 90.0 if side == "BUY" else 110.0,
        120.0 if side == "BUY" else 80.0, 0
    )
    with patch.object(engine, "_close_position", wraps=engine._close_position) as spy:
        getattr(engine, method)(raw, 1)
    spy.assert_called_once()
    trade = engine.trades[0]
    assert trade["raw_exit_price"] == raw
    assert trade["exit"] == pytest.approx(expected)
    assert trade["exit_slippage"] == pytest.approx(0.05)


def test_central_accounting_and_audit_fields_update_once():
    engine = BacktestEngine(slippage_bps=5)
    engine.execute_entry(
        "BUY", 100.0, 10.0, 1,
        pd.Timestamp("2026-09-01 09:20+05:30"),
        0, pd.Timestamp("2026-09-01 09:15+05:30")
    )
    qty = engine.position["quantity"]
    with patch.object(engine, "_close_position", wraps=engine._close_position) as spy:
        engine.check_exit(101.0, 80.0, 2, open_price=80.0)
    spy.assert_called_once()
    trade = engine.trades[0]
    expected_gross = (trade["exit"] - trade["entry"]) * qty
    expected_charges = engine.calculate_charges(
        trade["entry"], trade["exit"], qty, "BUY"
    )["total_charges"]
    assert trade["gross_pnl"] == pytest.approx(expected_gross)
    assert trade["charges"] == pytest.approx(expected_charges)
    assert trade["pnl"] == pytest.approx(expected_gross - expected_charges)
    assert engine.capital == pytest.approx(engine.initial_capital + trade["pnl"])
    assert engine.daily_pnl == pytest.approx(trade["pnl"])
    assert engine.equity_curve == pytest.approx([engine.initial_capital, engine.capital])
    snapshot = (engine.capital, engine.daily_pnl, list(engine.equity_curve), list(engine.trades))
    engine.close_open_position(1.0, 3)
    assert snapshot == (engine.capital, engine.daily_pnl, engine.equity_curve, engine.trades)