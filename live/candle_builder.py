from datetime import datetime
from loguru import logger


class CandleBuilder:

    def __init__(self):

        self.current_candle = None

        self.completed_candles = []

    def update(self, ltp):

        now = datetime.now()

        minute = now.replace(second=0, microsecond=0)

        # First Candle
        if self.current_candle is None:

            self.current_candle = {

                "time": minute,

                "open": ltp,

                "high": ltp,

                "low": ltp,

                "close": ltp

            }

            return None

        # Same Minute
        if minute == self.current_candle["time"]:

            self.current_candle["high"] = max(
                self.current_candle["high"],
                ltp
            )

            self.current_candle["low"] = min(
                self.current_candle["low"],
                ltp
            )

            self.current_candle["close"] = ltp

            return None

        # New Minute

        finished = self.current_candle.copy()

        self.completed_candles.append(finished)

        logger.success(f"New Candle : {finished}")

        self.current_candle = {

            "time": minute,

            "open": ltp,

            "high": ltp,

            "low": ltp,

            "close": ltp

        }

        return finished