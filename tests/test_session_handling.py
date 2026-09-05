from datetime import date, time
from unittest.mock import patch

import pandas as pd
import pytest

from backtest.backtest_runner import BacktestRunner


def complete_session(day="2026-09-01", tz="Asia/Kolkata"):
    stamps = pd.date_range(
        f"{day} 09:15", f"{day} 15:25", freq="5min", tz=tz
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


def make_runner(df, strategy=None):
    runner = BacktestRunner(df, interval="FIVE_MINUTE")
    runner.prepare_indicators = lambda: None
    if strategy is not None:
        runner.strategy = strategy
    return runner


class SignalAt:
    def __init__(self, at, side="BUY", on_date=None):
        self.at = at
        self.side = side
        self.on_date = on_date
        self.calls = []

    def get_signal(self, df):
        stamp = df.iloc[-1]["datetime"]
        self.calls.append(stamp)
        if stamp.time() == self.at and (
            self.on_date is None or stamp.date() == self.on_date
        ):
            return self.side
        return "HOLD"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026-09-01 09:15:00+05:30", "2026-09-01 09:15:00+05:30"),
        ("2026-09-01 03:45:00+00:00", "2026-09-01 09:15:00+05:30"),
        ("2026-09-01 09:15:00", "2026-09-01 09:15:00+05:30"),
    ],
)
def test_timestamp_policy_normalizes_to_ist(raw, expected):
    runner = BacktestRunner(pd.DataFrame({"datetime": [raw]}), interval="ONE_DAY")
    runner.prepare_data()
    assert runner.df.iloc[0]["datetime"] == pd.Timestamp(expected)
    assert str(runner.df.iloc[0]["datetime"].tzinfo) == "Asia/Kolkata"


def test_mixed_aware_and_naive_timestamps_are_deterministic():
    runner = BacktestRunner(
        pd.DataFrame({"datetime": [
            "2026-09-01 10:00:00+05:30",
            "2026-09-01 03:45:00+00:00",
            "2026-09-01 09:30:00",
        ]}),
        interval="ONE_DAY",
    )
    runner.prepare_data()
    assert list(runner.df["datetime"].dt.strftime("%H:%M")) == [
        "09:15", "09:30", "10:00"
    ]
    assert all(str(value.tzinfo) == "Asia/Kolkata" for value in runner.df["datetime"])


def test_one_day_midnight_candles_are_not_session_filtered():
    runner = BacktestRunner(
        pd.DataFrame({"datetime": ["2026-09-02 00:00", "2026-09-01 00:00"]}),
        interval="ONE_DAY",
    )
    runner.prepare_data()
    assert list(runner.df["datetime"].dt.hour) == [0, 0]
    assert runner.df["datetime"].is_monotonic_increasing


def test_complete_session_accepts_open_mid_and_final_bar():
    runner = make_runner(complete_session())
    runner.prepare_data()
    times = set(runner.df["datetime"].dt.time)
    assert {time(9, 15), time(12, 0), time(15, 25)} <= times
    assert len(runner.df) == 75


@pytest.mark.parametrize("stamp", ["2026-09-01 09:10+05:30", "2026-09-01 15:30+05:30"])
def test_intraday_session_rejects_preopen_and_postclose(stamp):
    extra = complete_session().iloc[[0]].copy()
    extra["datetime"] = pd.to_datetime([stamp])
    runner = make_runner(pd.concat([complete_session(), extra], ignore_index=True))
    with pytest.raises(ValueError, match=f"Extra: {pd.Timestamp(stamp).strftime('%H:%M')}"):
        runner.prepare_data()


@pytest.mark.parametrize("entry_time, expected_trades", [
    (time(15, 5), 1),
    (time(15, 10), 0),
    (time(15, 15), 0),
    (time(15, 20), 0),
    (time(15, 25), 0),
])
def test_last_entry_cutoff_is_exclusive(entry_time, expected_trades):
    strategy = SignalAt(entry_time)
    runner = make_runner(complete_session(), strategy)
    runner.run()
    assert len(runner.engine.trades) == expected_trades
    if expected_trades:
        assert runner.engine.trades[0]["reason"] == "END_OF_SESSION"
    if entry_time == time(15, 25):
        assert all(stamp.time() != time(15, 25) for stamp in strategy.calls)


@pytest.mark.parametrize("side, final_close", [("BUY", 105.0), ("SELL", 95.0)])
def test_end_of_session_uses_centralized_accounting_once(side, final_close):
    df = complete_session()
    df.loc[df.index[-1], "close"] = final_close
    runner = make_runner(df, SignalAt(time(9, 15), side))
    with patch.object(
        runner.engine, "_close_position", wraps=runner.engine._close_position
    ) as close_spy:
        runner.run()
    close_spy.assert_called_once()
    assert close_spy.call_args.kwargs["reason"] == "END_OF_SESSION"
    trade = runner.engine.trades[0]
    assert trade["reason"] == "END_OF_SESSION"
    assert trade["exit_timestamp"].time() == time(15, 25)
    assert runner.engine.daily_pnl == pytest.approx(trade["pnl"])
    assert len(runner.engine.equity_curve) == 2
    snapshot = (
        runner.engine.capital,
        runner.engine.daily_pnl,
        list(runner.engine.equity_curve),
        list(runner.engine.trades),
    )
    runner.engine.close_end_of_session(50.0, 999, pd.Timestamp("2026-09-01 15:25+05:30"))
    assert snapshot == (
        runner.engine.capital,
        runner.engine.daily_pnl,
        runner.engine.equity_curve,
        runner.engine.trades,
    )


def test_no_overnight_position_and_reset_occurs_only_while_flat():
    df = pd.concat([
        complete_session("2026-09-01"),
        complete_session("2026-09-02"),
    ], ignore_index=True)
    runner = make_runner(df, SignalAt(time(10, 0), "BUY", date(2026, 9, 1)))
    positions_at_reset = []
    original_reset = runner.engine.reset_daily_risk

    def observed_reset():
        positions_at_reset.append(runner.engine.position)
        original_reset()

    runner.engine.reset_daily_risk = observed_reset
    runner.run()
    trade = runner.engine.trades[0]
    assert positions_at_reset == [None, None]
    assert trade["entry_timestamp"].date() == date(2026, 9, 1)
    assert trade["exit_timestamp"].date() == date(2026, 9, 1)
    assert runner.engine.position is None


@pytest.mark.parametrize("missing_time", [time(12, 0), time(15, 25)])
def test_incomplete_session_is_rejected_instead_of_using_early_eod(missing_time):
    df = complete_session()
    df = df[df["datetime"].dt.time != missing_time].reset_index(drop=True)
    runner = make_runner(df)
    with pytest.raises(ValueError, match=f"Missing: {missing_time.strftime('%H:%M')}"):
        runner.prepare_data()