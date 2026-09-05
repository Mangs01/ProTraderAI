from loguru import logger

from config.settings import EMA_SLOW_PERIOD


class EMAStrategy:

    REQUIRED_INDICATORS = ("EMA20", "EMA50", "RSI")

    @staticmethod
    def signal(df):

        if len(df) < EMA_SLOW_PERIOD:

            logger.warning("Not enough candle data")

            return "HOLD"

        latest = df.iloc[-1]

        if any(
            indicator not in df.columns
            or latest[indicator] != latest[indicator]
            for indicator in EMAStrategy.REQUIRED_INDICATORS
        ):
            logger.warning("EMA strategy indicators are not ready")
            return "HOLD"

        ema20 = latest["EMA20"]
        ema50 = latest["EMA50"]
        rsi = latest["RSI"]

        logger.info(
            f"EMA20={ema20:.2f} | "
            f"EMA50={ema50:.2f} | "
            f"RSI={rsi:.2f}"
        )

        # BUY
        if ema20 > ema50 and rsi > 60:

            logger.success("BUY SIGNAL")

            return "BUY"

        # SELL
        if ema20 < ema50 and rsi < 40:

            logger.warning("SELL SIGNAL")

            return "SELL"

        logger.info("NO TRADE")

        return "HOLD"