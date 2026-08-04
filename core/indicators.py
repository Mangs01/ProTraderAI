import pandas as pd


class Indicators:

    @staticmethod
    def prepare_dataframe(candles):

        df = pd.DataFrame(
            candles,
            columns=[
                "datetime",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        )

        df["datetime"] = pd.to_datetime(df["datetime"])

        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        return df


    @staticmethod
    def ema(df, period):

        return df["close"].ewm(
            span=period,
            adjust=False
        ).mean()


    @staticmethod
    def rsi(df, period=14):

        delta = df["close"].diff()

        gain = delta.where(delta > 0, 0)

        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(period).mean()

        avg_loss = loss.rolling(period).mean()

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return rsi