from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from backtest.backtest_engine import BacktestEngine
from backtest.backtest_runner import BacktestRunner

INITIAL = 100_000


def make_engine(**kw):
    args = dict(initial_capital=INITIAL, risk_per_trade=1.0,
                max_daily_loss=2_000, max_trades_per_day=5, slippage_bps=0)
    args.update(kw)
    return BacktestEngine(**args)


def open_trade(e, side="BUY", index=0, stamp="2026-09-01 09:15+05:30"):
    e.open_trade(side, 100.0, 90.0 if side == "BUY" else 110.0,
                 120.0 if side == "BUY" else 80.0, index,
                 pd.Timestamp(stamp))


def assert_invariants(e):
    assert len(e.equity_curve) == len(e.trades) + 1
    assert e.capital == pytest.approx(
        e.initial_capital + sum(t["pnl"] for t in e.trades))
    assert e.equity_curve[-1] == pytest.approx(e.capital)


@pytest.mark.parametrize("side,price,gross", [
    ("BUY", 110.0, 1_000.0), ("SELL", 90.0, 1_000.0)])
def test_buy_and_sell_accounting(side, price, gross):
    e = make_engine()
    open_trade(e, side)
    qty = e.position["quantity"]
    charges = e.calculate_charges(100.0, price, qty, side)["total_charges"]
    e.close_open_position(price, 1)
    trade = e.trades[0]
    assert trade["gross_pnl"] == pytest.approx(gross)
    assert trade["charges"] == pytest.approx(charges)
    assert trade["pnl"] == pytest.approx(gross - charges)
    assert e.capital == pytest.approx(INITIAL + gross - charges)
    assert e.equity_curve == pytest.approx([INITIAL, e.capital])
    assert_invariants(e)


@pytest.mark.parametrize("high,low,reason,price", [
    (105.0, 89.0, "STOP_LOSS", 90.0),
    (121.0, 95.0, "TARGET", 120.0)])
def test_stop_and_target_use_central_close(high, low, reason, price):
    e = make_engine()
    open_trade(e)
    with patch.object(e, "_close_position", wraps=e._close_position) as spy:
        e.check_exit(high, low, 1)
    spy.assert_called_once()
    assert spy.call_args.kwargs["reason"] == reason
    assert spy.call_args.kwargs["exit_price"] == price
    assert e.trades[0]["reason"] == reason
    assert_invariants(e)


def test_end_of_backtest_closes_once_and_updates_all_accounting():
    e = make_engine()
    open_trade(e)
    qty = e.position["quantity"]
    net = -500.0 - e.calculate_charges(100.0, 95.0, qty, "BUY")["total_charges"]
    e.close_open_position(95.0, 1)
    assert len(e.trades) == 1
    assert e.trades[0]["reason"] == "END_OF_BACKTEST"
    assert e.capital == pytest.approx(INITIAL + net)
    assert e.daily_pnl == pytest.approx(net)
    assert e.equity_curve == pytest.approx([INITIAL, INITIAL + net])
    assert e.peak_capital == INITIAL
    assert e.max_drawdown == pytest.approx(-net)
    assert e.max_drawdown_percent == pytest.approx(-net / INITIAL * 100)
    snapshot = (e.capital, e.daily_pnl, list(e.equity_curve), list(e.trades))
    e.close_open_position(50.0, 2)
    assert (e.capital, e.daily_pnl, e.equity_curve, e.trades) == snapshot
    assert_invariants(e)


def test_max_trades_blocks_more_same_date_entries():
    e = make_engine(max_trades_per_day=2)
    for i, minute in enumerate((15, 25)):
        open_trade(e, index=i * 2, stamp=f"2026-09-01 09:{minute}+05:30")
        e.close_open_position(101.0, i * 2 + 1)
    open_trade(e, index=4, stamp="2026-09-01 09:35+05:30")
    assert (e.daily_trade_count, len(e.trades), e.position) == (2, 2, None)
    assert e.can_open_trade() is False
    assert_invariants(e)


def test_realized_daily_losses_accumulate_and_lock_entries():
    e = make_engine(max_daily_loss=1_500)
    for i, minute in enumerate((0, 10)):
        open_trade(e, index=i * 2, stamp=f"2026-09-01 10:{minute:02d}+05:30")
        e.check_exit(100.0, 90.0, i * 2 + 1)
    expected = sum(t["pnl"] for t in e.trades)
    assert len(e.trades) == 2 and expected <= -e.max_daily_loss
    assert e.daily_pnl == pytest.approx(expected)
    assert e.daily_loss_limit_hit is True
    assert e.can_open_trade() is False
    open_trade(e, index=4, stamp="2026-09-01 10:20+05:30")
    assert e.position is None and e.daily_trade_count == 2
    assert_invariants(e)


def test_daily_reset_clears_count_pnl_and_loss_lock():
    e = make_engine(max_daily_loss=500, max_trades_per_day=1)
    open_trade(e)
    e.check_exit(100.0, 90.0, 1)
    assert e.daily_trade_count == 1 and e.daily_pnl < -500
    assert e.daily_loss_limit_hit is True and e.can_open_trade() is False
    e.reset_daily_risk()
    assert (e.daily_trade_count, e.daily_pnl, e.daily_loss_limit_hit) == (0, 0.0, False)
    assert e.can_open_trade() is True and len(e.trades) == 1
    assert_invariants(e)


class BuyThenHold:
    def __init__(self):
        self.calls = 0

    def get_signal(self, _df):
        self.calls += 1
        return "BUY" if self.calls == 1 else "HOLD"


def test_one_day_pending_signal_executes_next_date_without_overnight_position():
    # Current behavior lock: a later phase will replace overnight carry with
    # mandatory END_OF_SESSION closure.
    df = pd.DataFrame([
        dict(datetime="2026-09-01 15:25+05:30", open=100, high=101,
             low=99, close=100, volume=1000, ATR=10),
        dict(datetime="2026-09-02 09:15+05:30", open=101, high=105,
             low=95, close=102, volume=1000, ATR=10)])
    runner = BacktestRunner(df, interval="ONE_DAY")
    runner.prepare_indicators = lambda: None
    runner.strategy = BuyThenHold()
    runner.run()
    trade = runner.engine.trades[0]
    assert len(runner.engine.trades) == 1
    assert trade["signal_timestamp"].date() == date(2026, 9, 1)
    assert trade["entry_timestamp"].date() == date(2026, 9, 2)
    assert trade["exit_timestamp"].date() == date(2026, 9, 2)
    assert trade["reason"] == "END_OF_BACKTEST"
    assert runner.engine.daily_trade_count == 1
    assert runner.engine.daily_pnl == pytest.approx(trade["pnl"])
    assert_invariants(runner.engine)


def test_multiple_closes_preserve_accounting_invariants():
    e = make_engine()
    for i, (side, price) in enumerate((("BUY", 110), ("SELL", 92), ("BUY", 95))):
        open_trade(e, side, i * 2)
        prior = e.daily_pnl
        e.close_open_position(price, i * 2 + 1)
        assert e.daily_pnl == pytest.approx(prior + e.trades[-1]["pnl"])
    assert e.daily_pnl == pytest.approx(sum(t["pnl"] for t in e.trades))
    assert_invariants(e)


def frame(timestamps):
    n = len(timestamps)
    return pd.DataFrame(dict(datetime=timestamps, open=[100] * n,
        high=[101] * n, low=[99] * n, close=[100] * n, volume=[1000] * n))


@pytest.mark.parametrize("bad", ["not-a-timestamp", None, pd.NaT])
def test_prepare_data_rejects_invalid_and_null_timestamps(bad):
    runner = BacktestRunner(frame([bad]))
    with pytest.raises(ValueError, match="invalid datetime"):
        runner.prepare_data()


def test_prepare_data_rejects_duplicate_timestamps():
    stamp = "2026-09-01 09:15+05:30"
    runner = BacktestRunner(frame([stamp, stamp]))
    with pytest.raises(ValueError, match="duplicate timestamps"):
        runner.prepare_data()


def test_prepare_data_sorts_valid_timestamps_oldest_first():
    runner = BacktestRunner(frame(["2026-09-01 09:25+05:30",
                                   "2026-09-01 09:15+05:30",
                                   "2026-09-01 09:20+05:30"]),
                            interval="ONE_DAY")
    runner.prepare_data()
    assert runner.df["datetime"].is_monotonic_increasing

