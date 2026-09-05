import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from utils.time_utils import (
    normalize_timestamp_series,
    validate_five_minute_sessions,
)
from utils.session_policy import FiveMinuteSessionPolicy


CANDLE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]


def normalized_timestamp(value):
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("Historical timestamp is invalid")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp


def validate_candle_data(data):
    """Return normalized candle data or raise ValueError."""
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        try:
            df = pd.DataFrame(data, columns=CANDLE_COLUMNS)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid historical candle structure") from exc

    if list(df.columns) != CANDLE_COLUMNS or df.empty:
        raise ValueError("Historical data must contain the expected OHLCV schema")

    try:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("Historical data contains invalid timestamps") from exc
    if df["datetime"].isna().any():
        raise ValueError("Historical data contains null timestamps")

    for column in NUMERIC_COLUMNS:
        try:
            df[column] = pd.to_numeric(df[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Historical data contains non-numeric {column} values"
            ) from exc
    if df[NUMERIC_COLUMNS].isna().any().any():
        raise ValueError("Historical data contains null OHLCV values")
    if not np.isfinite(df[NUMERIC_COLUMNS].to_numpy(dtype=float)).all():
        raise ValueError("Historical data contains non-finite OHLCV values")
    if (df["volume"] < 0).any():
        raise ValueError("Historical data contains negative volume")
    if (
        (df["high"] < df[["open", "low", "close"]].max(axis=1)).any()
        or (df["low"] > df[["open", "high", "close"]].min(axis=1)).any()
    ):
        raise ValueError("Historical data contains inconsistent OHLC values")

    return df.sort_values("datetime", kind="mergesort").reset_index(drop=True)


class HistoricalCache:
    def __init__(
        self,
        exchange,
        symboltoken,
        interval,
        cache_dir="data",
        filename=None,
        cas_eligible=False,
        session_policy=None,
    ):
        self.exchange = str(exchange)
        self.symboltoken = str(symboltoken)
        self.interval = str(interval)
        self.session_policy = session_policy or FiveMinuteSessionPolicy(
            cas_eligible=cas_eligible
        )

        if filename is None:
            parts = (
                self._safe_component(self.exchange),
                self._safe_component(self.symboltoken),
                self._safe_component(self.interval),
            )
            filename = Path(cache_dir) / f"historical_{'_'.join(parts)}.csv"

        self.filename = str(filename)
        self.metadata_filename = f"{self.filename}.meta.json"
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_component(value):
        component = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip())
        component = component.strip("._-")
        if not component:
            raise ValueError("Cache identity contains an empty component")
        return component

    @staticmethod
    def _timestamp(value):
        return normalized_timestamp(value)

    @staticmethod
    def _digest(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _weekday_count(start_date, end_date, inclusive):
        if start_date >= end_date:
            return 0
        return len(pd.bdate_range(start_date, end_date, inclusive=inclusive))

    @classmethod
    def _validate_intraday_coverage(
        cls, actual_first, actual_last, requested_start, requested_end,
        session_policy=None,
    ):
        actual_first = cls._timestamp(actual_first)
        actual_last = cls._timestamp(actual_last)
        requested_start = cls._timestamp(requested_start)
        requested_end = cls._timestamp(requested_end)
        if actual_first.date() > requested_start.date():
            missing = cls._weekday_count(
                requested_start.date(), actual_first.date(), "left"
            )
            if missing:
                raise ValueError(
                    "FIVE_MINUTE cache is missing a boundary trading session"
                )
        elif actual_first.date() == requested_start.date() and actual_first.time() > time(9, 15):
            raise ValueError("FIVE_MINUTE cache starts after session open")
        if actual_last.date() < requested_end.date():
            missing = cls._weekday_count(
                actual_last.date(), requested_end.date(), "right"
            )
            if missing:
                raise ValueError(
                    "FIVE_MINUTE cache ends before a boundary trading session"
                )
        elif actual_last.date() == requested_end.date() and actual_last.time() < (
            session_policy or FiveMinuteSessionPolicy()
        ).final_regular_bar_start(actual_last.date()):
            raise ValueError("FIVE_MINUTE cache is missing the final session bar")
    def save(self, data, requested_start, requested_end):
        df = validate_candle_data(data)
        if self.interval == "FIVE_MINUTE":
            df["datetime"] = normalize_timestamp_series(
                df["datetime"], "Asia/Kolkata"
            )
            validate_five_minute_sessions(
                df, session_policy=self.session_policy
            )
        if df["datetime"].duplicated().any():
            raise ValueError("Historical cache data contains duplicate timestamps")

        requested_start = self._timestamp(requested_start)
        requested_end = self._timestamp(requested_end)
        if requested_start > requested_end:
            raise ValueError("Requested cache range is invalid")

        first_timestamp = df["datetime"].iloc[0]
        last_timestamp = df["datetime"].iloc[-1]
        coverage_tolerance = (pd.Timedelta(days=7) if self.interval == "ONE_DAY" else pd.Timedelta(0))
        if self.interval == "FIVE_MINUTE":
            self._validate_intraday_coverage(
                first_timestamp, last_timestamp, requested_start, requested_end,
                self.session_policy,
            )
        if self.interval == "ONE_DAY" and (
            self._timestamp(first_timestamp)
            > requested_start + coverage_tolerance
            or self._timestamp(last_timestamp)
            < requested_end - coverage_tolerance
        ):
            raise ValueError("Historical data does not cover the requested range")

        directory = Path(self.filename).parent
        csv_temp = metadata_temp = csv_backup = metadata_backup = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv.tmp", dir=directory,
                delete=False, newline="", encoding="utf-8"
            ) as handle:
                csv_temp = handle.name
                df.to_csv(handle, index=False)
                handle.flush()
                os.fsync(handle.fileno())

            written = pd.read_csv(csv_temp)
            validate_candle_data(written)
            csv_hash = self._digest(csv_temp)

            metadata = {
                "version": (
                    self.session_policy.version
                    if self.interval == "FIVE_MINUTE" else 1
                ),
                "exchange": self.exchange,
                "symbol_token": self.symboltoken,
                "interval": self.interval,
                "requested_start": requested_start.isoformat(),
                "requested_end": requested_end.isoformat(),
                "actual_first_timestamp": first_timestamp.isoformat(),
                "actual_last_timestamp": last_timestamp.isoformat(),
                "columns": CANDLE_COLUMNS,
                "row_count": len(df),
                "csv_sha256": csv_hash,
            }
            if self.interval == "FIVE_MINUTE":
                metadata["session_policy"] = self.session_policy.metadata()
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json.tmp", dir=directory,
                delete=False, encoding="utf-8"
            ) as handle:
                metadata_temp = handle.name
                json.dump(metadata, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())

            if os.path.exists(self.filename):
                with tempfile.NamedTemporaryFile(
                    suffix=".csv.bak", dir=directory, delete=False
                ) as handle:
                    csv_backup = handle.name
                shutil.copy2(self.filename, csv_backup)
            if os.path.exists(self.metadata_filename):
                with tempfile.NamedTemporaryFile(
                    suffix=".json.bak", dir=directory, delete=False
                ) as handle:
                    metadata_backup = handle.name
                shutil.copy2(self.metadata_filename, metadata_backup)

            try:
                os.replace(csv_temp, self.filename)
                csv_temp = None
                os.replace(metadata_temp, self.metadata_filename)
                metadata_temp = None
            except OSError:
                if csv_backup is not None:
                    os.replace(csv_backup, self.filename)
                    csv_backup = None
                elif os.path.exists(self.filename):
                    os.unlink(self.filename)
                if metadata_backup is not None:
                    os.replace(metadata_backup, self.metadata_filename)
                    metadata_backup = None
                elif os.path.exists(self.metadata_filename):
                    os.unlink(self.metadata_filename)
                raise
        finally:
            for path in (
                csv_temp, metadata_temp, csv_backup, metadata_backup
            ):
                if path and os.path.exists(path):
                    os.unlink(path)
        logger.success(
            f"Historical Data Cached : {len(df)} candles | "
            f"{self.exchange}/{self.symboltoken}/{self.interval}"
        )

    def load(self, requested_start, requested_end):
        if not os.path.exists(self.filename) or not os.path.exists(
            self.metadata_filename
        ):
            logger.warning("Historical cache or metadata not found")
            return None

        try:
            with open(self.metadata_filename, encoding="utf-8") as handle:
                metadata = json.load(handle)

            expected_identity = {
                "exchange": self.exchange,
                "symbol_token": self.symboltoken,
                "interval": self.interval,
            }
            if any(metadata.get(key) != value
                   for key, value in expected_identity.items()):
                raise ValueError("Historical cache identity mismatch")
            if metadata.get("columns") != CANDLE_COLUMNS:
                raise ValueError("Historical cache schema metadata mismatch")
            if self.interval == "FIVE_MINUTE" and (
                metadata.get("version") != self.session_policy.version
                or metadata.get("session_policy")
                != self.session_policy.metadata()
            ):
                raise ValueError("Historical cache session policy mismatch")
            if metadata.get("csv_sha256") != self._digest(self.filename):
                raise ValueError("Historical cache checksum mismatch")

            cached_start = self._timestamp(metadata["requested_start"])
            cached_end = self._timestamp(metadata["requested_end"])
            requested_start = self._timestamp(requested_start)
            requested_end = self._timestamp(requested_end)
            if cached_start > requested_start or cached_end < requested_end:
                logger.warning("Historical cache does not cover requested range")
                return None

            df = validate_candle_data(pd.read_csv(self.filename))
            if df["datetime"].duplicated().any():
                raise ValueError("Historical cache contains duplicate timestamps")
            if len(df) != metadata.get("row_count"):
                raise ValueError("Historical cache row count mismatch")

            actual_first = self._timestamp(metadata["actual_first_timestamp"])
            actual_last = self._timestamp(metadata["actual_last_timestamp"])
            if (self._timestamp(df["datetime"].iloc[0]) != actual_first
                    or self._timestamp(df["datetime"].iloc[-1]) != actual_last):
                raise ValueError("Historical cache timestamp metadata mismatch")
            if self.interval == "FIVE_MINUTE":
                df["datetime"] = normalize_timestamp_series(
                    df["datetime"], "Asia/Kolkata"
                )
                validate_five_minute_sessions(
                    df, session_policy=self.session_policy
                )
                self._validate_intraday_coverage(
                    actual_first, actual_last, requested_start, requested_end,
                    self.session_policy,
                )
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Historical cache rejected: {exc}")
            return None

        logger.success(
            f"Historical Cache Loaded : {len(df)} candles | "
            f"{self.exchange}/{self.symboltoken}/{self.interval}"
        )
        return df
