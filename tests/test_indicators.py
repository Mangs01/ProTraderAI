import numpy as np
import pandas as pd
import pytest

from backtest.backtest_runner import BacktestRunner
from core.indicators import Indicators
from strategy.ema_strategy import EMAStrategy
from strategy.strategy_manager import StrategyManager
from utils.time_utils import normalize_timestamp_series


def market_frame(count=60, start="2026-01-01", freq="D"):
    close = pd.Series(np.arange(100.0, 100.0 + count))
    return pd.DataFrame({
        "datetime": pd.date_range(start, periods=count, freq=freq),
        "open": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": np.arange(1000.0, 1000.0 + count),
    })


def test_ema20_requires_twenty_raw_bars():
    values = Indicators.ema(market_frame(20), 20)
    assert values.iloc[:19].isna().all()
    assert pd.notna(values.iloc[19])


def test_ema50_requires_fifty_raw_bars():
    values = Indicators.ema(market_frame(50), 50)
    assert values.iloc[:49].isna().all()
    assert pd.notna(values.iloc[49])


def strategy_frame(count):
    df = market_frame(count)
    df["EMA20"] = 110.0
    df["EMA50"] = 100.0
    df["RSI"] = 70.0
    return df


def test_ema_strategy_blocks_signal_before_fifty_raw_bars():
    assert EMAStrategy.signal(strategy_frame(49)) == "HOLD"


def test_ema_strategy_preserves_buy_rule_after_readiness():
    assert EMAStrategy.signal(strategy_frame(50)) == "BUY"


def test_rsi_readiness_uses_existing_fourteen_period_formula():
    df = market_frame(14)
    df["close"] = [100, 101, 100, 102, 101, 103, 102,
                   104, 103, 105, 104, 106, 105, 107]
    values = Indicators.rsi(df, 14)
    assert values.iloc[:13].isna().all()
    assert pd.notna(values.iloc[13])


def test_atr_requires_fourteen_bars():
    values = Indicators.atr(market_frame(14), 14)
    assert values.iloc[:13].isna().all()
    assert pd.notna(values.iloc[13])


def test_volume_sma_requires_twenty_bars():
    values = Indicators.volume_sma(market_frame(20), 20)
    assert values.iloc[:19].isna().all()
    assert pd.notna(values.iloc[19])


def test_intraday_vwap_resets_each_trading_date():
    df = pd.DataFrame({
        "datetime": pd.to_datetime([
            "2026-09-01 09:15+05:30",
            "2026-09-01 09:20+05:30",
            "2026-09-02 09:15+05:30",
            "2026-09-02 09:20+05:30",
        ]),
        "close": [10.0, 20.0, 100.0, 200.0],
        "volume": [1.0, 3.0, 2.0, 2.0],
    })
    result = Indicators.vwap(df, session_reset=True)
    assert result.tolist() == pytest.approx([10.0, 17.5, 100.0, 150.0])


def test_vwap_groups_mixed_aware_timestamps_by_normalized_ist_date():
    df = pd.DataFrame({
        "datetime": [
            "2026-09-01 18:35:00+00:00",  # 00:05 IST on Sep 2
            "2026-09-02 00:10:00+05:30",
            "2026-09-02 18:40:00+00:00",  # 00:10 IST on Sep 3
        ],
        "close": [10.0, 30.0, 100.0],
        "volume": [1.0, 1.0, 1.0],
    })
    df["datetime"] = normalize_timestamp_series(
        df["datetime"], "Asia/Kolkata"
    )
    result = Indicators.vwap(df, session_reset=True)
    assert result.tolist() == pytest.approx([10.0, 20.0, 100.0])


def test_one_day_vwap_remains_continuous_and_accepts_midnight():
    df = pd.DataFrame({
        "datetime": pd.to_datetime([
            "2026-09-01 00:00", "2026-09-02 00:00"
        ]),
        "close": [10.0, 30.0],
        "volume": [1.0, 1.0],
    })
    assert Indicators.vwap(df).tolist() == pytest.approx([10.0, 20.0])


class BuyOnFirstEvaluation:
    def __init__(self):
        self.lengths = []

    def required_indicators(self):
        return ("EMA20", "EMA50", "RSI")

    def get_signal(self, df):
        self.lengths.append(len(df))
        return "BUY" if len(self.lengths) == 1 else "HOLD"


def test_runner_first_signal_evaluation_uses_fifty_raw_bars():
    runner = BacktestRunner(market_frame(60), interval="ONE_DAY")
    strategy = BuyOnFirstEvaluation()
    runner.strategy = strategy
    runner.run()
    assert strategy.lengths[0] == 50
    assert runner.engine.trades[0]["signal_index"] == 49
    assert runner.engine.trades[0]["entry_index"] == 50


def test_runner_readiness_requires_atr_but_not_vwap_or_volume_sma():
    df = market_frame(50)
    df["volume"] = 0.0
    runner = BacktestRunner(df, interval="ONE_DAY")
    runner.prepare_data()
    runner.prepare_indicators()
    last = runner.df.iloc[-1]
    assert pd.isna(last["VWAP"])
    assert last["VolumeSMA"] == 0.0
    assert bool(last["INDICATOR_READY"]) is True
    assert runner.df["INDICATOR_READY"].iloc[:49].eq(False).all()


def test_active_ema_strategy_declares_only_consumed_indicators():
    assert StrategyManager().required_indicators() == (
        "EMA20", "EMA50", "RSI"
    )

def test_execution_readiness_blocks_missing_atr_only():
    df = pd.DataFrame({
        "EMA20": [110.0],
        "EMA50": [100.0],
        "RSI": [70.0],
        "ATR": [np.nan],
        "VWAP": [np.nan],
        "VolumeSMA": [np.nan],
    })
    required = StrategyManager().required_indicators() + ("ATR",)
    assert bool(Indicators.readiness(df, required).iloc[0]) is False
    df.loc[0, "ATR"] = 2.0
    assert bool(Indicators.readiness(df, required).iloc[0]) is True
