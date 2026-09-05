from datetime import date, time
import json
from unittest.mock import patch

import pandas as pd
import pytest

from backtest.backtest_runner import BacktestRunner
from data.historical_cache import HistoricalCache
from utils.session_policy import (
    FiveMinuteSessionPolicy,
    SessionRegime,
    cas_eligibility_from_instrument,
)
from utils.time_utils import (
    completed_session_range,
    summarize_five_minute_sessions,
    validate_five_minute_sessions,
)


POLICY = FiveMinuteSessionPolicy(cas_eligible=True)


def session(day, final="15:10", auxiliary=()):
    stamps = list(pd.date_range(
        f"{day} 09:15", f"{day} {final}", freq="5min",
        tz="Asia/Kolkata",
    ))
    stamps.extend(pd.Timestamp(f"{day} {value}", tz="Asia/Kolkata")
                  for value in auxiliary)
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
        self.calls = []

    def get_signal(self, df):
        stamp = df.iloc[-1]["datetime"]
        self.calls.append(stamp)
        return "BUY" if stamp.time() == self.at else "HOLD"


def runner(df, strategy=None):
    value = BacktestRunner(df, interval="FIVE_MINUTE", cas_eligible=True)
    value.prepare_indicators = lambda: None
    if strategy is not None:
        value.strategy = strategy
    return value


def test_policy_boundary_and_programmatic_counts():
    assert POLICY.regime_for(date(2026, 8, 2)) is SessionRegime.LEGACY_REGULAR
    assert POLICY.regime_for(date(2026, 8, 3)) is SessionRegime.CAS_ELIGIBLE
    assert len(POLICY.expected_bar_times(date(2026, 8, 2))) == 75
    expected = POLICY.expected_bar_times(date(2026, 8, 3))
    assert expected[0] == time(9, 15)
    assert expected[-1] == time(15, 10)
    assert len(expected) == (
        (15 * 60 + 10 - (9 * 60 + 15)) // POLICY.interval_minutes + 1
    )
    assert len(expected) == 72


def test_legacy_and_non_cas_sessions_remain_75_bars():
    legacy = session("2026-07-31", final="15:25")
    non_cas = session("2026-09-01", final="15:25")
    validate_five_minute_sessions(legacy, session_policy=POLICY)
    validate_five_minute_sessions(
        non_cas, session_policy=FiveMinuteSessionPolicy(cas_eligible=False)
    )
    with pytest.raises(ValueError, match="Missing: 12:00"):
        validate_five_minute_sessions(
            legacy[legacy["datetime"].dt.time != time(12)],
            session_policy=POLICY,
        )


def test_cas_complete_and_optional_1525_are_classified_not_required():
    complete = session("2026-08-03")
    assert validate_five_minute_sessions(complete, session_policy=POLICY) is complete
    with_aux = session("2026-08-03", auxiliary=("15:25",))
    validate_five_minute_sessions(with_aux, session_policy=POLICY)
    summary = summarize_five_minute_sessions(
        with_aux, session_policy=POLICY
    )[0]
    assert summary["regular_row_count"] == 72
    assert summary["expected_regular_bar_count"] == 72
    assert summary["auxiliary_cas_bar_starts"] == ["15:25"]
    assert summary["unexpected_bar_starts"] == []


@pytest.mark.parametrize("missing", [time(12), time(15, 10)])
def test_cas_missing_required_regular_bar_rejects(missing):
    df = session("2026-08-03")
    df = df[df["datetime"].dt.time != missing]
    with pytest.raises(ValueError, match=f"Missing: {missing.strftime('%H:%M')}"):
        validate_five_minute_sessions(df, session_policy=POLICY)


def test_cas_duplicate_and_unexplained_off_session_reject():
    df = session("2026-08-03")
    with pytest.raises(ValueError, match="Duplicates: 1"):
        validate_five_minute_sessions(
            pd.concat([df, df.iloc[[10]]]), session_policy=POLICY
        )
    bad = pd.concat([df, session("2026-08-03").iloc[[0]].assign(
        datetime=pd.Timestamp("2026-08-03 15:30", tz="Asia/Kolkata")
    )])
    with pytest.raises(ValueError, match="Extra: 15:30"):
        validate_five_minute_sessions(bad, session_policy=POLICY)


def test_optional_cas_bar_never_reaches_strategy_or_execution():
    strategy = SignalAt(time(15, 25))
    value = runner(session("2026-09-01", auxiliary=("15:25",)), strategy)
    value.run()
    assert len(value.cas_auxiliary_data) == 1
    assert all(stamp.time() != time(15, 25) for stamp in strategy.calls)
    assert value.engine.trades == []


@pytest.mark.parametrize("signal_time,trades,entry_time", [
    (time(15, 0), 1, time(15, 5)),
    (time(15, 5), 0, None),
])
def test_cas_final_signal_and_entry_cutoff(signal_time, trades, entry_time):
    value = runner(session("2026-09-01"), SignalAt(signal_time))
    value.run()
    assert len(value.engine.trades) == trades
    if trades:
        assert value.engine.trades[0]["entry_timestamp"].time() == entry_time
    assert POLICY.final_allowed_signal_bar(date(2026, 9, 1)) == time(15, 0)
    assert POLICY.final_allowed_entry_bar(date(2026, 9, 1)) == time(15, 5)


def test_cas_eod_uses_1510_close_once_and_never_carries():
    df = session("2026-09-01", auxiliary=("15:25",))
    df.loc[df["datetime"].dt.time == time(15, 10), "close"] = 107.0
    df.loc[df["datetime"].dt.time == time(15, 25), "close"] = 999.0
    value = runner(df, SignalAt(time(9, 15)))
    with patch.object(
        value.engine, "_close_position", wraps=value.engine._close_position
    ) as close_spy:
        value.run()
    close_spy.assert_called_once()
    trade = value.engine.trades[0]
    assert trade["reason"] == "END_OF_SESSION"
    assert trade["exit_timestamp"].time() == time(15, 10)
    assert trade["raw_exit_price"] == 107.0
    assert trade["exit"] == pytest.approx(106.9465)
    assert value.engine.position is None
    assert len(value.engine.equity_curve) == 2


def test_cas_cache_policy_metadata_and_old_metadata_rejection(tmp_path):
    value = HistoricalCache(
        "NSE", "3045", "FIVE_MINUTE", cache_dir=tmp_path,
        cas_eligible=True,
    )
    rows = session("2026-09-01").drop(columns=["ATR"]).values.tolist()
    value.save(rows, "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30")
    assert value.load(
        "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30"
    ) is not None
    with open(value.metadata_filename, encoding="utf-8") as handle:
        metadata = json.load(handle)
    assert metadata["version"] == POLICY.version
    assert metadata["session_policy"] == POLICY.metadata()
    metadata["version"] = 1
    metadata.pop("session_policy")
    with open(value.metadata_filename, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle)
    assert value.load(
        "2026-09-01 09:15+05:30", "2026-09-01 15:30+05:30"
    ) is None


@pytest.mark.parametrize("now,expected", [
    ("2026-09-04 16:00+05:30", "2026-09-04"),
    ("2026-09-05 16:00+05:30", "2026-09-04"),
    ("2026-09-06 16:00+05:30", "2026-09-04"),
    ("2026-09-07 12:00+05:30", "2026-09-04"),
    ("2026-09-07 16:00+05:30", "2026-09-07"),
])
def test_completed_range_weekend_bounds(now, expected):
    _, end = completed_session_range(now)
    assert str(end.date()) == expected


@pytest.mark.parametrize("raw,expected", [
    (True, True), ("true", True), ("0", False), (0, False),
])
def test_instrument_master_cas_field_resolution(raw, expected):
    assert cas_eligibility_from_instrument(
        {"symbol": "ANY-EQ", "is_cas_enabled": raw}
    ) is expected


def test_instrument_master_missing_cas_field_is_not_inferred():
    with pytest.raises(ValueError, match="is_cas_enabled"):
        cas_eligibility_from_instrument({"symbol": "SBIN-EQ"})
