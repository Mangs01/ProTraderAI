import time

import pandas as pd
from loguru import logger
from utils.time_utils import (
    five_minute_validation_error,
    normalize_timestamp_series,
    summarize_five_minute_sessions,
    validate_five_minute_sessions,
)

from data.historical_cache import (
    CANDLE_COLUMNS,
    HistoricalCache,
    normalized_timestamp,
    validate_candle_data,
)
from utils.session_policy import FiveMinuteSessionPolicy


class HistoricalDownloader:
    """Shared candle download/validation only; no authentication or trading."""

    @staticmethod
    def _build_historical_chunks(start, end, chunk_days):
        """Build inclusive chunks bounded by calendar-date distance.

        Adjacent chunks intentionally share one timestamp. Aggregation removes
        only that cross-chunk boundary duplicate.
        """
        chunks = []
        chunk_start = start
        while chunk_start <= end:
            if (end.date() - chunk_start.date()).days <= chunk_days:
                chunk_end = end
            else:
                chunk_end = chunk_start + pd.Timedelta(days=chunk_days)
            chunks.append((chunk_start, chunk_end))
            if chunk_end == end:
                break
            chunk_start = chunk_end
        return chunks

    @staticmethod
    def _raw_response_metadata(response):
        metadata = {
            "response_status": None,
            "api_message": None,
            "error_code": None,
            "data_exists": False,
            "raw_row_count": None,
            "first_raw_candle_timestamp": None,
            "last_raw_candle_timestamp": None,
        }
        if not isinstance(response, dict):
            return metadata
        rows = response.get("data")
        metadata.update({
            "response_status": response.get("status"),
            "api_message": response.get("message"),
            "error_code": response.get("errorcode"),
            "data_exists": rows is not None,
            "raw_row_count": len(rows) if isinstance(rows, list) else None,
        })
        if isinstance(rows, list) and rows:
            if isinstance(rows[0], (list, tuple)) and rows[0]:
                metadata["first_raw_candle_timestamp"] = str(rows[0][0])
            if isinstance(rows[-1], (list, tuple)) and rows[-1]:
                metadata["last_raw_candle_timestamp"] = str(rows[-1][0])
        return metadata

    def get_historical_data(
        self,
        exchange,
        symboltoken,
        interval,
        fromdate,
        todate,
        chunk_days=None,
        pace_seconds=0.0,
        max_retries=3,
        retry_backoff_seconds=5.0,
        sleep_fn=time.sleep,
        cas_eligible=False,
        session_policy=None,
    ):
        policy = session_policy or FiveMinuteSessionPolicy(
            cas_eligible=cas_eligible
        )
        self.last_download_diagnostics = {
            "interval": interval,
            "requested_fromdate": str(fromdate),
            "requested_todate": str(todate),
            "chunks": [],
            "dates": [],
            "validation_error": None,
        }
        start = pd.Timestamp(fromdate)
        end = pd.Timestamp(todate)
        if pd.isna(start) or pd.isna(end) or start > end:
            logger.error("Invalid historical data date range")
            return None
        if chunk_days is None:
            chunk_days = 90 if interval == "FIVE_MINUTE" else 2000
        if chunk_days <= 0 or max_retries <= 0:
            logger.error("Invalid historical download configuration")
            return None

        chunks = self._build_historical_chunks(start, end, chunk_days)

        combined = []
        for chunk_index, (chunk_start, chunk_end) in enumerate(chunks):
            params = {
                "exchange": exchange,
                "symboltoken": symboltoken,
                "interval": interval,
                "fromdate": chunk_start.strftime("%Y-%m-%d %H:%M"),
                "todate": chunk_end.strftime("%Y-%m-%d %H:%M"),
            }
            chunk_data = None
            chunk_audit = {
                "chunk_number": chunk_index + 1,
                "requested_fromdate": params["fromdate"],
                "requested_todate": params["todate"],
                "attempts": [],
            }
            self.last_download_diagnostics["chunks"].append(chunk_audit)
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(
                        f"Downloading Candle Data | Chunk "
                        f"{chunk_index + 1}/{len(chunks)} | "
                        f"Attempt {attempt}/{max_retries}"
                    )
                    response = self.api.getCandleData(params)
                    response_audit = self._raw_response_metadata(response)
                    response_audit["attempt"] = attempt
                    chunk_audit["attempts"].append(response_audit)
                    logger.info(f"Historical response audit: {chunk_audit}")
                    if not isinstance(response, dict):
                        raise ValueError("Historical API returned malformed response")
                    if response.get("status") is not True:
                        raise ValueError(
                            "Historical API failure: "
                            f"{response.get('message') or response.get('errorcode')}"
                        )
                    rows = response.get("data")
                    if not isinstance(rows, list) or not rows:
                        raise ValueError("Historical API returned unusable data")
                    chunk_data = validate_candle_data(rows)
                    chunk_data["_source_chunk"] = chunk_index + 1
                    break
                except Exception as exc:
                    if (not chunk_audit["attempts"]
                            or chunk_audit["attempts"][-1]["attempt"] != attempt):
                        chunk_audit["attempts"].append({
                            "attempt": attempt,
                            **self._raw_response_metadata(None),
                        })
                    chunk_audit["attempts"][-1]["exception"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
                    logger.error(
                        f"Historical chunk failed "
                        f"(Attempt {attempt}/{max_retries}): {exc}"
                    )
                    if attempt < max_retries:
                        sleep_fn(retry_backoff_seconds * attempt)

            if chunk_data is None:
                logger.error(
                    f"Historical download aborted at chunk "
                    f"{chunk_index + 1}/{len(chunks)}"
                )
                return None

            combined.append(chunk_data)
            if chunk_index < len(chunks) - 1 and pace_seconds > 0:
                sleep_fn(pace_seconds)

        try:
            result = pd.concat(combined, ignore_index=True)
            result["datetime"] = pd.to_datetime(result["datetime"], errors="raise")
            drop_indexes = []
            duplicate_rows = result[result["datetime"].duplicated(keep=False)]
            for _, group in duplicate_rows.groupby("datetime"):
                if len(group) == group["_source_chunk"].nunique():
                    drop_indexes.extend(group.index[:-1])
            result = result.drop(index=drop_indexes).sort_values(
                "datetime", kind="mergesort"
            ).reset_index(drop=True)
            source_chunks = {
                index: [int(chunk)]
                for index, chunk in result["_source_chunk"].items()
            }
            result = validate_candle_data(result[CANDLE_COLUMNS])
            if interval == "FIVE_MINUTE":
                result["datetime"] = normalize_timestamp_series(
                    result["datetime"], "Asia/Kolkata"
                )
                summaries = summarize_five_minute_sessions(
                    result, source_chunks=source_chunks,
                    session_policy=policy,
                )
                self.last_download_diagnostics["dates"] = summaries
                logger.info(f"FIVE_MINUTE response summaries: {summaries}")
                try:
                    validate_five_minute_sessions(
                        result, session_policy=policy
                    )
                except ValueError:
                    raise
                HistoricalCache._validate_intraday_coverage(
                    result["datetime"].iloc[0], result["datetime"].iloc[-1],
                    start, end, policy
                )
            coverage_tolerance = pd.Timedelta(days=7)
            if interval == "ONE_DAY" and (
                normalized_timestamp(result["datetime"].iloc[0])
                > start + coverage_tolerance
                or normalized_timestamp(result["datetime"].iloc[-1])
                < end - coverage_tolerance
            ):
                raise ValueError(
                    "Combined historical data has incomplete coverage"
                )
        except (TypeError, ValueError) as exc:
            self.last_download_diagnostics["validation_error"] = str(exc)
            logger.error(f"Historical aggregation failed: {exc}")
            return None

        logger.success(
            f"Historical Data Loaded Successfully : {len(result)} candles"
        )
        return {
            "status": True,
            "message": "SUCCESS",
            "data": result[CANDLE_COLUMNS].values.tolist(),
        }

