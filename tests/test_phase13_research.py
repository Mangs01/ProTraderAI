from datetime import time

import pandas as pd

from backtest.backtest_runner import BacktestRunner
from research.ema_variants import (
    EMACrossoverRSIStrategy,
    EMACrossoverStrategy,
    EMARegimeLockStrategy,
)
from strategy.ema_strategy import EMAStrategy


def indicators(ema20, ema50, rsi=50):
    return pd.DataFrame({"EMA20": ema20, "EMA50": ema50, "RSI": rsi})


def test_true_bullish_crossover_emits_one_buy_without_repeating():
    strategy = EMACrossoverStrategy()
    assert strategy.get_signal(indicators([99, 101], [100, 100])) == "BUY"
    assert strategy.get_signal(
        indicators([99, 101, 102], [100, 100, 100])
    ) == "HOLD"


def test_true_bearish_crossover_emits_one_sell_without_repeating():
    strategy = EMACrossoverStrategy()
    assert strategy.get_signal(indicators([101, 99], [100, 100])) == "SELL"
    assert strategy.get_signal(
        indicators([101, 99, 98], [100, 100, 100])
    ) == "HOLD"


def test_crossover_rsi_requires_confirmation_on_event_candle():
    strategy = EMACrossoverRSIStrategy()
    assert strategy.get_signal(
        indicators([99, 101], [100, 100], [50, 60])
    ) == "HOLD"
    assert strategy.get_signal(
        indicators([99, 101], [100, 100], [50, 61])
    ) == "BUY"
    assert strategy.get_signal(
        indicators([101, 99], [100, 100], [50, 40])
    ) == "HOLD"
    assert strategy.get_signal(
        indicators([101, 99], [100, 100], [50, 39])
    ) == "SELL"


def test_regime_lock_prevents_repeat_and_resets():
    strategy = EMARegimeLockStrategy()
    assert strategy.get_signal(indicators([101], [100], [70])) == "BUY"
    assert strategy.get_signal(
        indicators([101, 102], [100, 100], [70, 70])
    ) == "HOLD"
    assert strategy.get_signal(
        indicators([101, 102, 99], [100, 100, 100], [70, 70, 30])
    ) == "SELL"
    assert strategy.get_signal(
        indicators([101, 102, 99, 98], [100] * 4, [70, 70, 30, 30])
    ) == "HOLD"
    assert strategy.get_signal(
        indicators([101, 102, 99, 98, 101], [100] * 5,
                   [70, 70, 30, 30, 70])
    ) == "BUY"


def test_regime_lock_detects_reset_hidden_between_evaluations():
    strategy = EMARegimeLockStrategy()
    assert strategy.get_signal(indicators([101], [100], [70])) == "BUY"
    assert strategy.get_signal(
        indicators([101, 99, 101], [100, 100, 100], [70, 30, 70])
    ) == "BUY"


def test_research_variants_do_not_modify_production_ema_behavior():
    frame = indicators([110] * 50, [100] * 50, [70] * 50)
    before = EMAStrategy.signal(frame)
    EMACrossoverStrategy().get_signal(frame)
    EMACrossoverRSIStrategy().get_signal(frame)
    EMARegimeLockStrategy().get_signal(frame)
    assert before == EMAStrategy.signal(frame) == "BUY"


class EventAt:
    def required_indicators(self):
        return ("EMA20", "EMA50", "RSI")

    def get_signal(self, df):
        return (
            "BUY"
            if df.iloc[-1]["datetime"].time() == time(15, 0)
            else "HOLD"
        )


def cas_session(day):
    stamps = pd.date_range(
        f"{day} 09:15", f"{day} 15:10", freq="5min", tz="Asia/Kolkata"
    )
    return pd.DataFrame({
        "datetime": stamps,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1000.0,
        "EMA20": 101.0,
        "EMA50": 100.0,
        "RSI": 70.0,
        "ATR": 100.0,
        "INDICATOR_READY": True,
    })


def test_research_strategy_uses_same_next_bar_and_cas_cutoff_model():
    runner = BacktestRunner(
        cas_session("2026-09-01"),
        interval="FIVE_MINUTE",
        cas_eligible=True,
    )
    runner.prepare_indicators = lambda: None
    runner.strategy = EventAt()
    runner.run()
    trade = runner.engine.trades[0]
    assert trade["signal_timestamp"].time() == time(15, 0)
    assert trade["entry_timestamp"].time() == time(15, 5)
    assert trade["reason"] == "END_OF_SESSION"


def test_research_pending_entry_never_crosses_session():
    runner = BacktestRunner(
        cas_session("2026-09-01"),
        interval="FIVE_MINUTE",
        cas_eligible=True,
    )
    runner.pending_entry = {
        "side": "BUY",
        "atr": 10.0,
        "signal_index": 71,
        "signal_timestamp": pd.Timestamp("2026-09-01 15:10+05:30"),
    }
    assert runner._pending_can_execute(
        72, pd.Timestamp("2026-09-02 09:15+05:30")
    ) is False


# Phase 13A infrastructure tests. Progression tests stub every experiment;
# only the production control is executed against the frozen cache.
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from research import ema_harness as harness


class AlwaysHold:
    def required_indicators(self):
        return ("EMA20", "EMA50")

    def get_signal(self, df):
        return "HOLD"


def test_zero_trade_research_contract():
    result = harness.run_variant(cas_session("2026-09-01"), AlwaysHold)
    zero_keys = (
        "total_trades", "winning_trades", "losing_trades", "breakeven_trades",
        "win_rate", "gross_profit", "gross_loss", "gross_net_pnl",
        "total_charges", "net_pnl", "profit_factor", "max_drawdown",
        "max_drawdown_percent", "average_win", "average_loss",
        "buy_trades", "sell_trades", "average_net_trade", "median_trade",
        "largest_winner", "largest_loser", "target_count", "stop_count",
        "eod_count", "longest_winning_streak", "longest_losing_streak",
        "charges_per_trade", "charges_over_turnover_percent", "gross_turnover",
        "buy_signals", "sell_signals", "pending_entries", "pending_cancelled",
        "average_stop_exposure_percent", "maximum_stop_exposure_percent",
    )
    assert {key: result[key] for key in zero_keys} == dict.fromkeys(zero_keys, 0)
    assert result["final_capital"] == 100000
    assert result["equity_curve"] == [100000]
    assert result["equity_points"] == 1
    assert result["trades"] == []
    assert result["hold_evaluations"] > 0


def stub_experiments(monkeypatch, baseline):
    monkeypatch.setattr(harness.pd, "read_csv", lambda _: object())
    run = Mock(side_effect=[baseline, {}, {}, {}])
    monkeypatch.setattr(harness, "run_variant", run)
    return run


def test_matching_baseline_allows_stubbed_progression(monkeypatch):
    run = stub_experiments(monkeypatch, dict(harness.FROZEN_BASELINE))
    result = harness.run_all()
    assert list(result) == ["A_STATE", "B_CROSS", "C_CROSS_RSI", "D_REGIME_LOCK"]
    assert [call.args[1] for call in run.call_args_list] == [
        harness.StrategyManager, harness.EMACrossoverStrategy,
        harness.EMACrossoverRSIStrategy, harness.EMARegimeLockStrategy,
    ]


@pytest.mark.parametrize("metric", list(harness.FROZEN_BASELINE))
def test_each_baseline_mismatch_blocks_all_variants(monkeypatch, metric):
    baseline = dict(harness.FROZEN_BASELINE)
    expected = baseline[metric]
    baseline[metric] += 1
    run = stub_experiments(monkeypatch, baseline)
    with pytest.raises(harness.BaselineMismatchError) as error:
        harness.run_all()
    run.assert_called_once()
    assert run.call_args.args[1] is harness.StrategyManager
    assert error.value.mismatches == {metric: (expected, baseline[metric])}
    assert f"{metric}: expected {expected!r}, actual {baseline[metric]!r}" in str(error.value)


@pytest.mark.parametrize("actual", [None, float("nan"), float("inf"), "-35043.92", True])
def test_invalid_baseline_value_blocks_progression(monkeypatch, actual):
    baseline = dict(harness.FROZEN_BASELINE)
    baseline["net_pnl"] = actual
    run = stub_experiments(monkeypatch, baseline)
    with pytest.raises(harness.BaselineMismatchError):
        harness.run_all()
    run.assert_called_once()


def test_missing_and_multiple_mismatches_reported():
    baseline = dict(harness.FROZEN_BASELINE)
    del baseline["total_trades"]
    baseline["net_pnl"] = 0
    with pytest.raises(harness.BaselineMismatchError) as error:
        harness.validate_baseline(baseline)
    assert error.value.mismatches == {
        "total_trades": (67, None), "net_pnl": (-35043.92, 0),
    }


def test_baseline_tolerance_is_absolute_and_counts_are_exact():
    baseline = dict(harness.FROZEN_BASELINE)
    baseline["net_pnl"] += 0.004
    harness.validate_baseline(baseline)
    baseline["net_pnl"] += 0.002
    with pytest.raises(harness.BaselineMismatchError):
        harness.validate_baseline(baseline)
    baseline = dict(harness.FROZEN_BASELINE)
    baseline["total_trades"] += 0.001
    with pytest.raises(harness.BaselineMismatchError):
        harness.validate_baseline(baseline)


def test_frozen_production_baseline_reproduces():
    cache = Path(__file__).resolve().parents[1] / "data/historical_NSE_3045_FIVE_MINUTE.csv"
    metadata = json.loads(cache.with_suffix(".csv.meta.json").read_text())
    assert hashlib.sha256(cache.read_bytes()).hexdigest() == metadata["csv_sha256"]
    result = harness.run_variant(pd.read_csv(cache), harness.StrategyManager)
    harness.validate_baseline(result)
    assert result["buy_signals"] == 25
    assert result["sell_signals"] == 42
    assert result["hold_evaluations"] == 354
