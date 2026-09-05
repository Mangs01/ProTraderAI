from dataclasses import dataclass
from datetime import date, time, timedelta
from enum import Enum

import pandas as pd

from config.settings import (
    FIVE_MINUTE_BAR_MINUTES,
    FIVE_MINUTE_SESSION_POLICY_VERSION,
    NSE_CAS_CONTINUOUS_FINAL_BAR_START,
    NSE_CAS_EFFECTIVE_DATE,
    NSE_CAS_ENTRY_CUTOFF,
    NSE_CAS_PERIOD_BAR_STARTS,
    NSE_FINAL_BAR_START,
    NSE_LAST_ENTRY_CUTOFF,
    NSE_SESSION_START,
)


class SessionRegime(str, Enum):
    LEGACY_REGULAR = "LEGACY_REGULAR"
    CAS_ELIGIBLE = "CAS_ELIGIBLE"


def _parse_time(value):
    return value if isinstance(value, time) else time.fromisoformat(value)


def _parse_date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


@dataclass(frozen=True)
class FiveMinuteSessionPolicy:
    """Date-aware NSE cash FIVE_MINUTE session semantics."""

    cas_eligible: bool = False
    effective_date: date = _parse_date(NSE_CAS_EFFECTIVE_DATE)
    session_start: time = _parse_time(NSE_SESSION_START)
    legacy_final_bar_start: time = _parse_time(NSE_FINAL_BAR_START)
    legacy_entry_cutoff: time = _parse_time(NSE_LAST_ENTRY_CUTOFF)
    cas_continuous_final_bar_start: time = _parse_time(
        NSE_CAS_CONTINUOUS_FINAL_BAR_START
    )
    cas_entry_cutoff: time = _parse_time(NSE_CAS_ENTRY_CUTOFF)
    cas_period_bar_starts: tuple = tuple(
        _parse_time(value) for value in NSE_CAS_PERIOD_BAR_STARTS
    )
    interval_minutes: int = FIVE_MINUTE_BAR_MINUTES
    version: int = FIVE_MINUTE_SESSION_POLICY_VERSION

    def regime_for(self, trading_date):
        if self.cas_eligible and _parse_date(trading_date) >= self.effective_date:
            return SessionRegime.CAS_ELIGIBLE
        return SessionRegime.LEGACY_REGULAR

    def final_regular_bar_start(self, trading_date):
        if self.regime_for(trading_date) is SessionRegime.CAS_ELIGIBLE:
            return self.cas_continuous_final_bar_start
        return self.legacy_final_bar_start

    def entry_cutoff(self, trading_date):
        if self.regime_for(trading_date) is SessionRegime.CAS_ELIGIBLE:
            return self.cas_entry_cutoff
        return self.legacy_entry_cutoff

    def expected_bar_times(self, trading_date):
        anchor = pd.Timestamp("2000-01-01")
        start = pd.Timestamp.combine(anchor, self.session_start)
        final = pd.Timestamp.combine(anchor, self.final_regular_bar_start(trading_date))
        return tuple(
            stamp.time()
            for stamp in pd.date_range(start, final, freq=f"{self.interval_minutes}min")
        )

    def auxiliary_bar_times(self, trading_date):
        if self.regime_for(trading_date) is SessionRegime.CAS_ELIGIBLE:
            return self.cas_period_bar_starts
        return ()

    def final_allowed_entry_bar(self, trading_date):
        cutoff_bound = pd.Timestamp.combine(
            pd.Timestamp("2000-01-01"), self.entry_cutoff(trading_date)
        ) - timedelta(minutes=self.interval_minutes)
        eod_bound = pd.Timestamp.combine(
            pd.Timestamp("2000-01-01"),
            self.final_regular_bar_start(trading_date),
        ) - timedelta(minutes=self.interval_minutes)
        return min(cutoff_bound, eod_bound).time()

    def final_allowed_signal_bar(self, trading_date):
        anchor = pd.Timestamp.combine(
            pd.Timestamp("2000-01-01"), self.final_allowed_entry_bar(trading_date)
        )
        return (anchor - timedelta(minutes=self.interval_minutes)).time()

    def metadata(self):
        return {
            "version": self.version,
            "cas_eligible": self.cas_eligible,
            "cas_effective_date": self.effective_date.isoformat(),
            "legacy_final_bar_start": self.legacy_final_bar_start.isoformat(),
            "cas_continuous_final_bar_start": (
                self.cas_continuous_final_bar_start.isoformat()
            ),
            "interval_minutes": self.interval_minutes,
        }


def cas_eligibility_from_instrument(record):
    """Read SmartAPI's field without guessing from a symbol or token."""
    value = record.get("is_cas_enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    raise ValueError("Instrument master lacks a valid is_cas_enabled value")
