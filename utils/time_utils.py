from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import (
    FIVE_MINUTE_BAR_MINUTES,
    NSE_FINAL_BAR_START,
    NSE_SESSION_END,
    NSE_SESSION_START,
    TRADING_TIMEZONE,
)
from utils.session_policy import FiveMinuteSessionPolicy, SessionRegime


def normalize_timestamp(value, timezone_name):
    """Convert aware values to the trading timezone; naive means local time."""
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("Timestamp is null")
    timezone = ZoneInfo(timezone_name)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(
            timezone, ambiguous="raise", nonexistent="raise"
        )
    return timestamp.tz_convert(timezone)


def normalize_timestamp_series(series, timezone_name):
    normalized = []
    for value in series:
        normalized.append(normalize_timestamp(value, timezone_name))
    return pd.Series(normalized, index=series.index)


def parse_session_time(value):
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid session time: {value}") from exc


def expected_bar_times(session_start, final_bar_start, interval_minutes):
    start = pd.Timestamp.combine(pd.Timestamp("2000-01-01"), session_start)
    end = pd.Timestamp.combine(pd.Timestamp("2000-01-01"), final_bar_start)
    return tuple(
        timestamp.time()
        for timestamp in pd.date_range(
            start, end, freq=f"{interval_minutes}min"
        )
    )


def summarize_five_minute_sessions(
    df, source_chunks=None, session_start=NSE_SESSION_START,
    final_bar_start=NSE_FINAL_BAR_START,
    interval_minutes=FIVE_MINUTE_BAR_MINUTES,
    session_policy=None,
):
    """Return serializable evidence for every represented trading date."""
    if "datetime" not in df.columns or df.empty:
        return []
    start = parse_session_time(session_start)
    final = parse_session_time(final_bar_start)
    summaries = []
    for trading_date, group in df.groupby(df["datetime"].dt.date, sort=True):
        timestamps = group["datetime"]
        unique_times = set(timestamps.dt.time)
        if session_policy is None:
            expected = set(expected_bar_times(start, final, interval_minutes))
            auxiliary = set()
            regime = SessionRegime.LEGACY_REGULAR
        else:
            expected = set(session_policy.expected_bar_times(trading_date))
            auxiliary = set(session_policy.auxiliary_bar_times(trading_date))
            regime = session_policy.regime_for(trading_date)
        regular_rows = group[timestamps.dt.time.isin(expected)]
        auxiliary_rows = group[timestamps.dt.time.isin(auxiliary)]
        chunks = set()
        if source_chunks is not None:
            for index in group.index:
                chunks.update(source_chunks.get(index, ()))
        summaries.append({
            "date": str(trading_date),
            "row_count": int(len(group)),
            "first_timestamp": str(timestamps.min()),
            "last_timestamp": str(timestamps.max()),
            "unique_bar_count": int(timestamps.nunique()),
            "duplicate_count": int(len(group) - timestamps.nunique()),
            "session_regime": regime.value,
            "expected_regular_bar_count": len(expected),
            "regular_row_count": int(len(regular_rows)),
            "regular_unique_bar_count": int(regular_rows["datetime"].nunique()),
            "auxiliary_cas_bar_starts": sorted(
                value.strftime("%H:%M")
                for value in set(auxiliary_rows["datetime"].dt.time)
            ),
            "missing_expected_bar_starts": [
                value.strftime("%H:%M") for value in sorted(expected - unique_times)
            ],
            "unexpected_bar_starts": [
                value.strftime("%H:%M")
                for value in sorted(unique_times - expected - auxiliary)
            ],
            "has_09_15": time(9, 15) in unique_times,
            "has_15_25": time(15, 25) in unique_times,
            "has_15_30": time(15, 30) in unique_times,
            "source_chunks": sorted(chunks),
        })
    return summaries


def five_minute_validation_error(summary, expected_count):
    missing = summary["missing_expected_bar_starts"] or ["none"]
    extra = summary["unexpected_bar_starts"] or ["none"]
    return (
        f"Invalid FIVE_MINUTE session | Date: {summary['date']} | "
        f"Expected: {expected_count} | Actual: {summary['row_count']} | "
        f"Unique: {summary['unique_bar_count']} | "
        f"Duplicates: {summary['duplicate_count']} | "
        f"Missing: {', '.join(missing)} | Extra: {', '.join(extra)} | "
        f"First: {summary['first_timestamp']} | Last: {summary['last_timestamp']} | "
        f"Source chunks: {summary['source_chunks'] or 'unknown'}"
    )


def completed_session_range(
    now=None,
    lookback_days=30,
    timezone_name=TRADING_TIMEZONE,
    session_start=NSE_SESSION_START,
    session_end=NSE_SESSION_END,
):
    """Return a completed intraday request range in the trading timezone.

    No exchange holiday calendar is assumed. Before the normal close, the
    candidate end date is yesterday; after close it is today. The downloader
    and strict session validator establish which candidate dates actually
    traded.
    """
    if now is None:
        now = pd.Timestamp.now(tz=timezone_name)
    current = normalize_timestamp(now, timezone_name)
    start_time = parse_session_time(session_start)
    end_time = parse_session_time(session_end)
    end_date = current.date()
    if current.time() < end_time:
        end_date = end_date - timedelta(days=1)
    while end_date.weekday() >= 5:
        end_date = end_date - timedelta(days=1)
    end = pd.Timestamp.combine(pd.Timestamp(end_date), end_time)
    end = end.tz_localize(ZoneInfo(timezone_name))
    start_date = end_date - timedelta(days=int(lookback_days))
    start = pd.Timestamp.combine(pd.Timestamp(start_date), start_time)
    start = start.tz_localize(ZoneInfo(timezone_name))
    if start > end:
        raise ValueError("Completed session range is invalid")
    return start, end


def validate_five_minute_sessions(
    df,
    session_start=NSE_SESSION_START,
    session_end=NSE_SESSION_END,
    final_bar_start=NSE_FINAL_BAR_START,
    interval_minutes=FIVE_MINUTE_BAR_MINUTES,
    session_policy=None,
):
    """Validate ordinary represented sessions without synthesizing candles."""
    if "datetime" not in df.columns or df.empty:
        raise ValueError("FIVE_MINUTE data requires datetime rows")
    start = parse_session_time(session_start)
    end = parse_session_time(session_end)
    final = parse_session_time(final_bar_start)
    policy = session_policy or FiveMinuteSessionPolicy(
        cas_eligible=False,
        session_start=start,
        legacy_final_bar_start=final,
        interval_minutes=interval_minutes,
    )
    for summary in summarize_five_minute_sessions(
        df, session_start=session_start, final_bar_start=final_bar_start,
        interval_minutes=interval_minutes, session_policy=policy,
    ):
        expected_count = summary["expected_regular_bar_count"]
        if (summary["regular_row_count"] != expected_count
                or summary["regular_unique_bar_count"] != expected_count
                or summary["duplicate_count"]
                or summary["missing_expected_bar_starts"]
                or summary["unexpected_bar_starts"]):
            raise ValueError(five_minute_validation_error(summary, expected_count))
    return df
