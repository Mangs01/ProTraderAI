from datetime import time
import json

import pandas as pd
import pytest

from backtest.backtest_runner import BacktestRunner
from config.settings import (
    NSE_FINAL_BAR_START,
    NSE_SESSION_START,
)
from core.indicators import Indicators
from data.historical_cache import HistoricalCache
from utils.time_utils import completed_session_range


def session(day, offset=0.0):
    stamps = pd.date_range(
        f"{day} 09:15", f"{day} 15:25", freq="5min", tz="Asia/Kolkata"
    )
    close = [100.0 + offset + min(i, 50) for i in range(len(stamps))]
    return pd.DataFrame({
        "datetime": stamps,
        "open": close,
        "high": [value + 100 for value in close],
        "low": [value - 100 for value in close],
        "close": close,
        "volume": [1000.0 + i for i in range(len(stamps))],
    })


def test_completed_range_before_market_uses_previous_date():
    start, end = completed_session_range("2026-09-05 08:00+05:30")
    assert start == pd.Timestamp("2026-08-05 09:15+05:30")
    assert end == pd.Timestamp("2026-09-04 15:30+05:30")


def test_completed_range_during_market_uses_previous_date():
    start, end = completed_session_range("2026-09-05 12:00+05:30")
    assert start.time() == time(9, 15)
    assert end == pd.Timestamp("2026-09-04 15:30+05:30")


def test_completed_range_after_close_skips_saturday():
    _, end = completed_session_range("2026-09-05 16:00+05:30")
    assert end == pd.Timestamp("2026-09-04 15:30+05:30")


def test_completed_range_converts_utc_and_skips_saturday():
    _, end = completed_session_range("2026-09-05 10:00+00:00")
    assert end == pd.Timestamp("2026-09-04 15:30+05:30")


def test_completed_range_has_30_calendar_day_lookback_and_fixed_times():
    start, end = completed_session_range(
        "2026-09-05 16:00+05:30", lookback_days=30
    )
    assert (end.date() - start.date()).days == 30
    assert start.time() == time(9, 15)
    assert end.time() == time(15, 30)


def test_real_indicators_and_runner_complete_one_five_minute_session():
    df = session("2026-09-01")
    runner = BacktestRunner(df, interval="FIVE_MINUTE")
    result = runner.run()
    assert len(runner.df) == 75
    assert runner.df["INDICATOR_READY"].iloc[:49].eq(False).all()
    assert runner.df["INDICATOR_READY"].iloc[49]
    assert result["total_trades"] == 1
    trade = runner.engine.trades[0]
    assert trade["signal_index"] == 49
    assert trade["entry_index"] == 50
    assert trade["entry_timestamp"].time() == time(13, 25)
    assert trade["reason"] == "END_OF_SESSION"
    assert trade["raw_entry_price"] == pytest.approx(150.0)
    assert trade["entry"] == pytest.approx(150.075)
    assert trade["exit_timestamp"].time() == time(15, 25)
    assert len(runner.engine.equity_curve) == 2
    assert runner.engine.daily_pnl == pytest.approx(trade["pnl"])


def test_real_two_session_flow_resets_risk_and_vwap_without_overnight():
    df = pd.concat([session("2026-09-01"), session("2026-09-02", offset=10.0)], ignore_index=True)
    runner = BacktestRunner(df, interval="FIVE_MINUTE")
    result = runner.run()
    assert len(runner.df) == 150
    assert len(runner.engine.trades) == 2
    assert all(trade["reason"] == "END_OF_SESSION" for trade in runner.engine.trades)
    assert all(
        trade["entry_timestamp"].date() == trade["exit_timestamp"].date()
        for trade in runner.engine.trades
    )
    assert runner.engine.position is None
    assert runner.engine.daily_trade_count == 1
    assert runner.df.loc[0, "VWAP"] != runner.df.loc[75, "VWAP"]
    assert result["total_trades"] == 2


def test_five_minute_cache_accepts_complete_session(tmp_path):
    value = HistoricalCache("NSE", "3045", "FIVE_MINUTE", cache_dir=tmp_path)
    rows = session("2026-09-01").values.tolist()
    value.save(rows, "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30")
    loaded = value.load(
        "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30"
    )
    assert loaded is not None and len(loaded) == 75


def test_five_minute_cache_rejects_boundary_short_actual_data(tmp_path):
    value = HistoricalCache("NSE", "3045", "FIVE_MINUTE", cache_dir=tmp_path)
    rows = session("2026-09-01").values.tolist()
    value.save(rows, "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30")
    metadata_path = value.metadata_filename
    metadata = json.loads(open(metadata_path, encoding="utf-8").read())
    metadata["requested_end"] = "2026-09-03T15:30:00"
    open(metadata_path, "w", encoding="utf-8").write(json.dumps(metadata))
    assert value.load(
        "2026-09-01 09:15+05:30", "2026-09-03 15:30+05:30"
    ) is None


def test_five_minute_incomplete_session_is_not_published(tmp_path):
    value = HistoricalCache("NSE", "3045", "FIVE_MINUTE", cache_dir=tmp_path)
    rows = session("2026-09-01").iloc[:-1].values.tolist()
    with pytest.raises(ValueError, match=r"Invalid FIVE_MINUTE.*Missing: 15:25"):
        value.save(rows, "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30")
    assert not value.filename or not pd.io.common.file_exists(value.filename)
