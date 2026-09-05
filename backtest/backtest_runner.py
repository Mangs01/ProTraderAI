import pandas as pd
from loguru import logger

from backtest.backtest_engine import BacktestEngine
from config.settings import (
    ATR_PERIOD,
    BACKTEST_SLIPPAGE_BPS,
    EMA_FAST_PERIOD,
    EMA_SLOW_PERIOD,
    FIVE_MINUTE_BAR_MINUTES,
    INCOMPLETE_SESSION_POLICY,
    INTERVAL,
    INTRADAY_INTERVALS,
    MAX_DAILY_LOSS,
    MAX_TRADE_PER_DAY,
    NSE_FINAL_BAR_START,
    NSE_LAST_ENTRY_CUTOFF,
    NSE_SESSION_END,
    NSE_SESSION_START,
    PAPER_BALANCE,
    RISK_PER_TRADE,
    TRADING_TIMEZONE,
    RSI_PERIOD,
    VOLUME_SMA_PERIOD,
)
from core.indicators import Indicators
from strategy.strategy_manager import StrategyManager
from utils.time_utils import (
    expected_bar_times,
    normalize_timestamp_series,
    parse_session_time,
    validate_five_minute_sessions,
)
from utils.session_policy import FiveMinuteSessionPolicy


class BacktestRunner:

    def __init__(
        self,
        df,
        interval=INTERVAL,
        trading_timezone=TRADING_TIMEZONE,
        session_start=NSE_SESSION_START,
        session_end=NSE_SESSION_END,
        final_bar_start=NSE_FINAL_BAR_START,
        last_entry_cutoff=NSE_LAST_ENTRY_CUTOFF,
        slippage_bps=BACKTEST_SLIPPAGE_BPS,
        cas_eligible=False,
        session_policy=None,
    ):
        self.df = df.copy()
        self.interval = interval
        self.trading_timezone = trading_timezone
        self.intraday = interval in INTRADAY_INTERVALS
        self.session_start = parse_session_time(session_start)
        self.session_end = parse_session_time(session_end)
        self.final_bar_start = parse_session_time(final_bar_start)
        self.last_entry_cutoff = parse_session_time(last_entry_cutoff)
        self.session_policy = session_policy or FiveMinuteSessionPolicy(
            cas_eligible=cas_eligible,
            session_start=self.session_start,
            legacy_final_bar_start=self.final_bar_start,
            legacy_entry_cutoff=self.last_entry_cutoff,
        )
        self.cas_auxiliary_data = self.df.iloc[0:0].copy()
        self.pending_entry = None
        self.strategy = StrategyManager()
        self.engine = BacktestEngine(
            initial_capital=PAPER_BALANCE,
            risk_per_trade=RISK_PER_TRADE,
            reward_ratio=2.0,
            max_daily_loss=MAX_DAILY_LOSS,
            max_trades_per_day=MAX_TRADE_PER_DAY,
            slippage_bps=slippage_bps,
        )

    def prepare_data(self):
        if "datetime" not in self.df.columns:
            raise ValueError("Backtest data must contain datetime")
        try:
            self.df["datetime"] = normalize_timestamp_series(
                self.df["datetime"], self.trading_timezone
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Backtest data contains invalid datetime values"
            ) from exc

        if self.df["datetime"].isna().any():
            raise ValueError(
                "Backtest data contains invalid datetime values"
            )

        duplicates = self.df["datetime"].duplicated(keep=False)
        if duplicates.any():
            values = self.df.loc[
                duplicates, "datetime"
            ].astype(str).unique()
            raise ValueError(
                "Backtest data contains duplicate timestamps: "
                + ", ".join(values[:5])
            )

        self.df = self.df.sort_values(
            "datetime", kind="mergesort"
        ).reset_index(drop=True)

        if self.intraday:
            self._validate_intraday_sessions()

    def _validate_intraday_sessions(self):
        if self.interval == "FIVE_MINUTE":
            validate_five_minute_sessions(
                self.df,
                session_start=self.session_start.isoformat(),
                session_end=self.session_end.isoformat(),
                final_bar_start=self.final_bar_start.isoformat(),
                interval_minutes=FIVE_MINUTE_BAR_MINUTES,
                session_policy=self.session_policy,
            )
            auxiliary_mask = self.df.apply(
                lambda row: row["datetime"].time() in set(
                    self.session_policy.auxiliary_bar_times(
                        row["datetime"].date()
                    )
                ),
                axis=1,
            )
            self.cas_auxiliary_data = self.df.loc[auxiliary_mask].copy()
            self.df = self.df.loc[~auxiliary_mask].reset_index(drop=True)
            return

        candle_times = self.df["datetime"].dt.time
        outside_session = (
            (candle_times < self.session_start)
            | (candle_times > self.final_bar_start)
        )
        if outside_session.any():
            invalid = self.df.loc[
                outside_session, "datetime"
            ].astype(str).tolist()
            raise ValueError(
                "Intraday data contains candles outside the regular "
                f"NSE bar-start session: {', '.join(invalid[:5])}"
            )
    def prepare_indicators(self):
        self.df["EMA20"] = Indicators.ema(
            self.df, EMA_FAST_PERIOD
        )
        self.df["EMA50"] = Indicators.ema(
            self.df, EMA_SLOW_PERIOD
        )
        self.df["RSI"] = Indicators.rsi(self.df, RSI_PERIOD)
        self.df["VWAP"] = Indicators.vwap(
            self.df, session_reset=self.intraday
        )
        self.df["VolumeSMA"] = Indicators.volume_sma(
            self.df, VOLUME_SMA_PERIOD
        )
        self.df["ATR"] = Indicators.atr(self.df, ATR_PERIOD)
        required = self.strategy.required_indicators() + ("ATR",)
        self.df["INDICATOR_READY"] = Indicators.readiness(
            self.df, required
        )
        logger.success("Backtest Indicators Prepared")

    def _pending_can_execute(self, candle_index, timestamp):

        pending = self.pending_entry
        if pending is None:
            return False
        if candle_index != pending["signal_index"] + 1:
            return False
        if not self.intraday:
            return True
        return (
            timestamp.date() == pending["signal_timestamp"].date()
            and timestamp.time()
            <= self.session_policy.final_allowed_entry_bar(timestamp.date())
            and timestamp.time() in set(
                self.session_policy.expected_bar_times(timestamp.date())
            )
            and timestamp.time()
            != self.session_policy.final_regular_bar_start(timestamp.date())
        )

    def run(self):
        self.prepare_data()
        self.prepare_indicators()
        self.pending_entry = None
        buy_signals = sell_signals = hold_signals = 0
        trading_dates = self.df["datetime"].dt.date
        last_date = None

        for i in range(len(self.df)):
            candle = self.df.iloc[i]
            timestamp = candle["datetime"]
            current_date = trading_dates.iat[i]
            if last_date is None or current_date != last_date:
                if (
                    self.intraday
                    and self.pending_entry is not None
                    and self.pending_entry["signal_timestamp"].date()
                    != current_date
                ):
                    self.pending_entry = None
                if self.intraday and self.engine.position is not None:
                    raise RuntimeError(
                        "Intraday position survived into a new trading date"
                    )
                last_date = current_date
                self.engine.reset_daily_risk()
                logger.info(f"NEW TRADING DAY | {current_date}")

            if self.pending_entry is not None:
                pending = self.pending_entry
                can_execute = self._pending_can_execute(i, timestamp)
                self.pending_entry = None
                if can_execute and self.engine.position is None:
                    self.engine.execute_entry(
                        side=pending["side"],
                        raw_entry_price=float(candle["open"]),
                        atr=pending["atr"],
                        candle_index=i,
                        entry_timestamp=timestamp,
                        signal_index=pending["signal_index"],
                        signal_timestamp=pending["signal_timestamp"],
                    )

            self.engine.check_exit(
                open_price=float(candle["open"]),
                high=float(candle["high"]),
                low=float(candle["low"]),
                candle_index=i,
                exit_timestamp=timestamp,
            )

            if (
                self.intraday
                and timestamp.time()
                == self.session_policy.final_regular_bar_start(current_date)
            ):
                self.pending_entry = None
                if self.engine.position is not None:
                    self.engine.close_end_of_session(
                        exit_price=float(candle["close"]),
                        candle_index=i,
                        exit_timestamp=timestamp,
                    )
                continue

            if self.engine.position is not None:
                continue
            if not self.engine.can_open_trade():
                continue
            if (
                self.intraday
                and timestamp.time()
                > self.session_policy.final_allowed_signal_bar(current_date)
            ):
                continue

            if (
                "INDICATOR_READY" in self.df.columns
                and not bool(candle["INDICATOR_READY"])
            ):
                continue

            signal = self.strategy.get_signal(self.df.iloc[:i + 1])
            if signal == "BUY":
                buy_signals += 1
            elif signal == "SELL":
                sell_signals += 1
            else:
                hold_signals += 1

            if signal in ("BUY", "SELL"):
                self.pending_entry = {
                    "side": signal,
                    "atr": float(candle["ATR"]),
                    "signal_index": i,
                    "signal_timestamp": timestamp,
                }

        # A signal on the final bar has no executable next bar.
        self.pending_entry = None

        if self.engine.position is not None:
            if self.intraday:
                raise RuntimeError(
                    "Intraday backtest ended with an open position"
                )
            self.engine.close_open_position(
                exit_price=float(self.df.iloc[-1]["close"]),
                candle_index=len(self.df) - 1,
                exit_timestamp=self.df.iloc[-1]["datetime"],
            )

        logger.info("========================================")
        logger.info(f"BUY Signals  : {buy_signals}")
        logger.info(f"SELL Signals : {sell_signals}")
        logger.info(f"HOLD Signals : {hold_signals}")
        logger.info("========================================")
        return self.engine.summary()
