"""Deterministic offline harness for the frozen Phase 12 dataset."""

import math
import statistics
from types import MappingProxyType

import pandas as pd

from backtest.backtest_runner import BacktestRunner
from research.ema_variants import (
    CountingStrategy,
    EMACrossoverRSIStrategy,
    EMACrossoverStrategy,
    EMARegimeLockStrategy,
)
from strategy.strategy_manager import StrategyManager


VARIANTS = {
    "A_STATE": StrategyManager,
    "B_CROSS": EMACrossoverStrategy,
    "C_CROSS_RSI": EMACrossoverRSIStrategy,
    "D_REGIME_LOCK": EMARegimeLockStrategy,
}


FROZEN_BASELINE = MappingProxyType({
    "total_trades": 67,
    "winning_trades": 21,
    "losing_trades": 46,
    "win_rate": 31.34,
    "gross_profit": 18747.97,
    "gross_loss": 43235.49,
    "gross_net_pnl": -24487.52,
    "total_charges": 10556.40,
    "net_pnl": -35043.92,
    "final_capital": 64956.08,
    "profit_factor": 0.43,
    "max_drawdown": 36704.03,
    "max_drawdown_percent": 36.10,
    "equity_points": 68,
})


class BaselineMismatchError(RuntimeError):
    """The control failed to reproduce; research must not proceed."""

    def __init__(self, mismatches):
        self.mismatches = mismatches
        details = "; ".join(
            f"{key}: expected {expected!r}, actual {actual!r}"
            for key, (expected, actual) in mismatches.items()
        )
        super().__init__(f"Research baseline reproduction failed: {details}")


def validate_baseline(result):
    """Require exact counts; tolerate 0.005 for two-decimal summary values."""
    mismatches = {}
    for key, expected in FROZEN_BASELINE.items():
        actual = result.get(key)
        numeric = isinstance(actual, (int, float)) and not isinstance(actual, bool)
        matches = numeric and math.isfinite(actual) and (
            actual == expected if isinstance(expected, int)
            else math.isclose(actual, expected, rel_tol=0, abs_tol=0.005)
        )
        if not matches:
            mismatches[key] = (expected, actual)
    if mismatches:
        raise BaselineMismatchError(mismatches)


def _normalize_summary(summary, engine):
    """Complete the research contract without changing engine accounting."""
    result = dict(summary)
    if result["total_trades"] == 0:
        result.update(
            total_charges=0.0,
            gross_net_pnl=0.0,
            max_drawdown=0.0,
            max_drawdown_percent=0.0,
        )
    result["equity_curve"] = list(engine.equity_curve)
    result["equity_points"] = len(engine.equity_curve)
    return result


def _streaks(values):
    best_win = best_loss = win = loss = 0
    for value in values:
        win = win + 1 if value > 0 else 0
        loss = loss + 1 if value < 0 else 0
        best_win, best_loss = max(best_win, win), max(best_loss, loss)
    return best_win, best_loss


def _modeled_stop_exposure(engine, trades):
    capital = engine.initial_capital
    exposures = []
    for trade in trades:
        stop_fill = engine.apply_slippage(
            trade["stop_loss"],
            "SELL" if trade["side"] == "BUY" else "BUY",
        )
        gross = (
            (stop_fill - trade["entry"])
            if trade["side"] == "BUY"
            else (trade["entry"] - stop_fill)
        ) * trade["quantity"]
        charges = engine.calculate_charges(
            trade["entry"], stop_fill, trade["quantity"], trade["side"]
        )["total_charges"]
        exposures.append((-(gross - charges) / capital) * 100)
        capital += trade["pnl"]
    return exposures


def run_variant(data, strategy_factory):
    strategy = CountingStrategy(strategy_factory())
    runner = BacktestRunner(data, interval="FIVE_MINUTE", cas_eligible=True)
    runner.strategy = strategy
    summary = _normalize_summary(runner.run(), runner.engine)
    trades = runner.engine.trades
    pnls = [trade["pnl"] for trade in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    win_streak, loss_streak = _streaks(pnls)
    turnover = sum(
        trade["buy_turnover"] + trade["sell_turnover"] for trade in trades
    )
    exposures = _modeled_stop_exposure(runner.engine, trades)
    signals = strategy.counts.buy + strategy.counts.sell
    return {
        **summary,
        "buy_trades": sum(t["side"] == "BUY" for t in trades),
        "sell_trades": sum(t["side"] == "SELL" for t in trades),
        "average_net_trade": statistics.mean(pnls) if pnls else 0,
        "median_trade": statistics.median(pnls) if pnls else 0,
        "largest_winner": max(wins) if wins else 0,
        "largest_loser": min(losses) if losses else 0,
        "target_count": sum(t["reason"] == "TARGET" for t in trades),
        "stop_count": sum(t["reason"] == "STOP_LOSS" for t in trades),
        "eod_count": sum(t["reason"] == "END_OF_SESSION" for t in trades),
        "longest_winning_streak": win_streak,
        "longest_losing_streak": loss_streak,
        "charges_per_trade": (
            summary["total_charges"] / len(trades) if trades else 0
        ),
        "charges_over_turnover_percent": (
            summary["total_charges"] / turnover * 100 if turnover else 0
        ),
        "gross_turnover": turnover,
        "buy_signals": strategy.counts.buy,
        "sell_signals": strategy.counts.sell,
        "hold_evaluations": strategy.counts.hold,
        "pending_entries": signals,
        "pending_cancelled": signals - len(trades),
        "average_stop_exposure_percent": (
            statistics.mean(exposures) if exposures else 0
        ),
        "maximum_stop_exposure_percent": max(exposures) if exposures else 0,
        "trades": trades,
    }


def run_all(cache_path="data/historical_NSE_3045_FIVE_MINUTE.csv"):
    data = pd.read_csv(cache_path)
    # Explicit production control first: no registry ordering or skip flag.
    baseline = run_variant(data, StrategyManager)
    validate_baseline(baseline)
    results = {"A_STATE": baseline}
    for name in ("B_CROSS", "C_CROSS_RSI", "D_REGIME_LOCK"):
        results[name] = run_variant(data, VARIANTS[name])
    return results
