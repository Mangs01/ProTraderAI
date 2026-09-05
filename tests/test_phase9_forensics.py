from unittest.mock import Mock

import pandas as pd
import pytest

from broker.angelone import AngelOneBroker
from data.historical_cache import HistoricalCache
from utils.time_utils import (
    summarize_five_minute_sessions,
    validate_five_minute_sessions,
)


def candle(timestamp):
    return [timestamp, 100.0, 101.0, 99.0, 100.0, 1000]


def session_rows(day="2026-08-06"):
    return [
        candle(stamp.isoformat())
        for stamp in pd.date_range(
            f"{day} 09:15", f"{day} 15:25", freq="5min",
            tz="Asia/Kolkata",
        )
    ]


def frame(rows):
    return pd.DataFrame(
        rows, columns=["datetime", "open", "high", "low", "close", "volume"]
    ).assign(datetime=lambda value: pd.to_datetime(value["datetime"]))


@pytest.mark.parametrize(
    "start,end,days,expected",
    [
        ("2026-08-06 09:15", "2026-08-20 15:30", 30, 1),
        ("2026-08-06 09:15", "2026-09-05 15:30", 30, 1),
        ("2026-08-06 09:15", "2026-09-06 09:16", 30, 2),
        ("2026-01-01 09:15", "2026-04-05 15:30", 30, 4),
        ("2026-08-06 15:30", "2026-09-05 09:15", 30, 1),
    ],
)
def test_calendar_day_chunk_boundaries(start, end, days, expected):
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    chunks = AngelOneBroker._build_historical_chunks(start, end, days)
    assert len(chunks) == expected
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    assert all(
        (chunk_end.date() - chunk_start.date()).days <= days
        for chunk_start, chunk_end in chunks
    )
    assert all(
        chunks[index][1] == chunks[index + 1][0]
        for index in range(len(chunks) - 1)
    )


def fake_broker(response):
    broker = AngelOneBroker.__new__(AngelOneBroker)
    broker.api = Mock()
    broker.api.getCandleData.return_value = response
    return broker


def download(broker):
    return broker.get_historical_data(
        exchange="NSE", symboltoken="3045", interval="FIVE_MINUTE",
        fromdate="2026-08-06 09:15", todate="2026-08-06 15:30",
        chunk_days=30, pace_seconds=0, max_retries=1,
        retry_backoff_seconds=0, sleep_fn=Mock(),
    )


def test_safe_raw_response_audit_survives_malformed_rows():
    response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "AB123",
        "data": [["2026-08-06T09:15:00+05:30"], ["broken"]],
    }
    broker = fake_broker(response)
    assert download(broker) is None
    attempt = broker.last_download_diagnostics["chunks"][0]["attempts"][0]
    assert attempt == {
        "attempt": 1,
        "response_status": True,
        "api_message": "SUCCESS",
        "error_code": "AB123",
        "data_exists": True,
        "raw_row_count": 2,
        "first_raw_candle_timestamp": "2026-08-06T09:15:00+05:30",
        "last_raw_candle_timestamp": "broken",
        "exception": "ValueError: Invalid historical candle structure",
    }
    assert "token" not in str(broker.last_download_diagnostics).lower()


def assert_invalid_summary(rows, missing, extra, duplicates=0):
    value = frame(rows)
    summary = summarize_five_minute_sessions(value)[0]
    assert summary["missing_expected_bar_starts"] == missing
    assert summary["unexpected_bar_starts"] == extra
    assert summary["duplicate_count"] == duplicates
    with pytest.raises(ValueError):
        validate_five_minute_sessions(value)
    return summary


def test_known_73_bar_anomaly_is_diagnosed_and_not_published(tmp_path):
    rows = [
        row for row in session_rows()
        if pd.Timestamp(row[0]).strftime("%H:%M") not in {"15:15", "15:20"}
    ]
    broker = fake_broker({"status": True, "message": "SUCCESS", "data": rows})
    assert download(broker) is None

    summary = broker.last_download_diagnostics["dates"][0]
    assert summary["date"] == "2026-08-06"
    assert summary["row_count"] == 73
    assert summary["unique_bar_count"] == 73
    assert summary["duplicate_count"] == 0
    assert summary["missing_expected_bar_starts"] == ["15:15", "15:20"]
    assert summary["unexpected_bar_starts"] == []
    assert summary["has_09_15"] is True
    assert summary["has_15_25"] is True
    assert summary["has_15_30"] is False
    error = broker.last_download_diagnostics["validation_error"]
    assert "Date: 2026-08-06" in error
    assert "Expected: 75" in error
    assert "Actual: 73" in error
    assert "Missing: 15:15, 15:20" in error
    assert "Extra: none" in error

    cache = HistoricalCache("NSE", "3045", "FIVE_MINUTE", cache_dir=tmp_path)
    assert not pd.io.common.file_exists(cache.filename)


def test_complete_75_bar_summary_and_validation():
    value = frame(session_rows())
    summary = summarize_five_minute_sessions(value)[0]
    assert summary["row_count"] == summary["unique_bar_count"] == 75
    assert summary["missing_expected_bar_starts"] == []
    assert summary["unexpected_bar_starts"] == []
    assert validate_five_minute_sessions(value) is value


def test_missing_final_15_25_is_diagnosed():
    assert_invalid_summary(session_rows()[:-1], ["15:25"], [])


def test_unexpected_15_30_is_diagnosed():
    assert_invalid_summary(
        session_rows() + [candle("2026-08-06T15:30:00+05:30")], [], ["15:30"]
    )


def test_duplicate_timestamp_is_diagnosed():
    rows = session_rows()
    assert_invalid_summary(rows + [rows[10]], [], [], duplicates=1)


def test_one_missing_middle_bar_is_diagnosed():
    rows = [
        row for row in session_rows()
        if pd.Timestamp(row[0]).strftime("%H:%M") != "12:00"
    ]
    assert_invalid_summary(rows, ["12:00"], [])


def test_off_session_timestamp_is_diagnosed():
    assert_invalid_summary(
        session_rows() + [candle("2026-08-06T09:10:00+05:30")], [], ["09:10"]
    )
