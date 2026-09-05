from unittest.mock import Mock

import pandas as pd
import pytest

from broker.angelone import AngelOneBroker
from data.historical_cache import HistoricalCache


def candle(timestamp, close=100.0):
    return [timestamp, close - 1, close + 1, close - 2, close, 1_000]


def cache(tmp_path, token="3045", interval="ONE_DAY"):
    return HistoricalCache("NSE", token, interval, cache_dir=tmp_path)


def test_cache_identity_differs_by_interval_and_symbol(tmp_path):
    daily = cache(tmp_path, interval="ONE_DAY")
    intraday = cache(tmp_path, interval="FIVE_MINUTE")
    other_symbol = cache(tmp_path, token="9999")
    assert daily.filename.endswith("historical_NSE_3045_ONE_DAY.csv")
    assert len({daily.filename, intraday.filename, other_symbol.filename}) == 3


def test_cache_identity_components_are_safely_sanitized(tmp_path):
    value = HistoricalCache("N/SE", "../3045", "ONE DAY", cache_dir=tmp_path)
    assert value.filename.endswith("historical_N_SE_3045_ONE_DAY.csv")
    assert ".." not in value.filename.rsplit("\\", 1)[-1]


def test_valid_cache_coverage_is_accepted(tmp_path):
    value = cache(tmp_path)
    rows = [candle("2026-01-02T00:00:00+05:30"),
            candle("2026-01-05T00:00:00+05:30")]
    value.save(rows, "2026-01-01", "2026-01-06")
    loaded = value.load("2026-01-02", "2026-01-05")
    assert loaded is not None
    assert len(loaded) == 2
    assert list(loaded.columns) == [
        "datetime", "open", "high", "low", "close", "volume"]


def test_insufficient_or_stale_cache_coverage_is_rejected(tmp_path):
    value = cache(tmp_path)
    value.save([candle("2026-01-03")], "2026-01-01", "2026-01-05")
    assert value.load("2025-12-31", "2026-01-05") is None
    assert value.load("2026-01-01", "2026-01-06") is None


def test_materially_incomplete_data_cannot_claim_full_coverage(tmp_path):
    value = cache(tmp_path)
    with pytest.raises(ValueError, match="does not cover"):
        value.save([candle("2026-01-15")], "2026-01-01", "2026-01-31")

def test_malformed_or_tampered_cache_is_rejected(tmp_path):
    value = cache(tmp_path)
    value.save([candle("2026-01-03")], "2026-01-01", "2026-01-05")
    with open(value.filename, "a", encoding="utf-8") as handle:
        handle.write("malformed\n")
    assert value.load("2026-01-01", "2026-01-05") is None


def test_atomic_failure_never_appears_as_valid_cache(tmp_path, monkeypatch):
    value = cache(tmp_path)
    value.save([candle("2026-01-03", 100)], "2026-01-01", "2026-01-05")
    import data.historical_cache as module
    real_replace = module.os.replace
    calls = 0

    def fail_metadata_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated interrupted metadata publish")
        return real_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_metadata_replace)
    with pytest.raises(OSError):
        value.save([candle("2026-01-04", 101)], "2026-01-01", "2026-01-05")
    loaded = value.load("2026-01-01", "2026-01-05")
    assert loaded is not None
    assert loaded.iloc[0]["close"] == pytest.approx(100.0)
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob("*.bak"))


def fake_broker(responses):
    broker = AngelOneBroker.__new__(AngelOneBroker)
    broker.api = Mock()
    broker.api.getCandleData.side_effect = responses
    return broker


def download(broker, **overrides):
    args = dict(
        exchange="NSE", symboltoken="3045", interval="FIVE_MINUTE",
        fromdate="2026-01-01 09:15", todate="2026-01-03 09:15",
        chunk_days=1, pace_seconds=0, max_retries=2,
        retry_backoff_seconds=0, sleep_fn=Mock(),
    )
    args.update(overrides)
    return broker.get_historical_data(**args)


def test_chunk_aggregation_deduplicates_boundary_and_sorts():
    broker = fake_broker([
        {"status": True, "data": [
            candle("2026-01-02 09:15", 102),
            candle("2026-01-01 09:15", 100)]},
        {"status": True, "data": [
            candle("2026-01-03 09:15", 103),
            candle("2026-01-02 09:15", 202)]},
    ])
    result = download(broker, interval="ONE_DAY")
    assert result is not None
    timestamps = [pd.Timestamp(row[0]) for row in result["data"]]
    assert timestamps == sorted(timestamps)
    assert len(timestamps) == len(set(timestamps)) == 3
    boundary = next(row for row in result["data"]
                    if pd.Timestamp(row[0]) == pd.Timestamp("2026-01-02 09:15"))
    assert boundary[4] == 202
    assert broker.api.getCandleData.call_count == 2


def test_successful_chunks_are_paced_between_requests():
    sleeper = Mock()
    broker = fake_broker([
        {"status": True, "data": [candle("2026-01-01 09:15")]},
        {"status": True, "data": [candle("2026-01-03 09:15")]},
    ])
    result = download(broker, interval="ONE_DAY", pace_seconds=0.25, sleep_fn=sleeper)
    assert result is not None
    sleeper.assert_called_once_with(0.25)


def test_failed_middle_chunk_prevents_partial_success_or_cache(tmp_path):
    broker = fake_broker([
        {"status": True, "data": [candle("2026-01-01 09:15")]},
        {"status": False, "message": "rate limited", "data": None},
        {"status": False, "message": "rate limited", "data": None},
    ])
    result = download(broker)
    value = cache(tmp_path, interval="FIVE_MINUTE")
    if result is not None:
        value.save(result["data"], "2026-01-01 09:15", "2026-01-03 09:15")
    assert result is None
    assert not tmp_path.iterdir().__next__() if any(tmp_path.iterdir()) else True
    assert not pd.io.common.file_exists(value.filename)


def test_api_status_false_retries_then_returns_none():
    broker = fake_broker([
        {"status": False, "message": "bad request", "data": None},
        {"status": False, "message": "bad request", "data": None},
    ])
    assert download(
        broker, todate="2026-01-01 10:15", chunk_days=90
    ) is None
    assert broker.api.getCandleData.call_count == 2


def test_transport_retry_exhaustion_returns_none_cleanly():
    broker = fake_broker([RuntimeError("offline failure"),
                          RuntimeError("offline failure")])
    assert download(
        broker, todate="2026-01-01 10:15", chunk_days=90
    ) is None
    assert broker.api.getCandleData.call_count == 2


@pytest.mark.parametrize("response", [
    None, "not-a-dict", {}, {"data": [candle("2026-01-01 09:15")]},
    {"status": True, "data": []},
    {"status": True, "data": [["bad"]]},
])
def test_malformed_api_response_is_rejected(response):
    broker = fake_broker([response])
    assert download(
        broker, todate="2026-01-01 10:15", chunk_days=90, max_retries=1
    ) is None

def complete_five_minute_rows(day="2026-01-02"):
    return [
        candle(timestamp.isoformat(), 100.0)
        for timestamp in pd.date_range(
            f"{day} 09:15", f"{day} 15:25", freq="5min",
            tz="Asia/Kolkata",
        )
    ]


def test_downloader_rejects_incomplete_five_minute_session_before_publish(tmp_path):
    rows = complete_five_minute_rows()[:-1]
    broker = fake_broker([{"status": True, "data": rows}])
    result = download(
        broker,
        fromdate="2026-01-02 09:15",
        todate="2026-01-02 15:30",
        chunk_days=30,
        max_retries=1,
    )
    assert result is None
    value = cache(tmp_path, interval="FIVE_MINUTE")
    assert not pd.io.common.file_exists(value.filename)


def test_historical_ohlcv_invariants_are_enforced(tmp_path):
    rows = complete_five_minute_rows()
    rows[10][2] = rows[10][4] - 1
    value = cache(tmp_path, interval="FIVE_MINUTE")
    with pytest.raises(ValueError, match="inconsistent OHLC"):
        value.save(
            rows,
            "2026-01-02 09:15+05:30",
            "2026-01-02 15:30+05:30",
        )
    assert not pd.io.common.file_exists(value.filename)
