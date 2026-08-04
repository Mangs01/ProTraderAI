from loguru import logger


class EMAStrategy:

    @staticmethod
    def signal(df):

        if len(df) < 50:
            logger.warning("Not enough candle data")
            return "HOLD"

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        ema20 = latest["EMA20"]
        ema50 = latest["EMA50"]
        rsi = latest["RSI"]

        prev_ema20 = previous["EMA20"]
        prev_ema50 = previous["EMA50"]

        close = latest["close"]

        # EMA Gap
        ema_gap = abs(ema20 - ema50)

        logger.info(
            f"Close={close:.2f} | EMA20={ema20:.2f} | EMA50={ema50:.2f} | RSI={rsi:.2f}"
        )

        # Ignore weak trend
        if ema_gap < 0.20:
            logger.info("Weak Trend")
            return "HOLD"

        # BUY
        if (
            ema20 > ema50
            and prev_ema20 >= prev_ema50
            and rsi >= 55
        ):

            logger.success("BUY SIGNAL")
            return "BUY"

        # SELL
        if (
            ema20 < ema50
            and prev_ema20 <= prev_ema50
            and rsi <= 45
        ):

            logger.warning("SELL SIGNAL")
            return "SELL"

        logger.info("NO TRADE")

        return "HOLD"