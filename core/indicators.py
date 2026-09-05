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
            adjust=False,
            min_periods=period
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

    @staticmethod
    def vwap(df, session_reset=False):

        price_volume = df["close"] * df["volume"]

        if session_reset:
            if "datetime" not in df.columns:
                raise ValueError(
                    "Session VWAP requires a datetime column"
                )
            trading_date = df["datetime"].dt.date
            cumulative_volume = df["volume"].groupby(
                trading_date
            ).cumsum()
            cumulative_price_volume = price_volume.groupby(
                trading_date
            ).cumsum()
        else:
            cumulative_volume = df["volume"].cumsum()
            cumulative_price_volume = price_volume.cumsum()

        return cumulative_price_volume / cumulative_volume

    @staticmethod
    def readiness(df, required_columns):

        missing = [
            column for column in required_columns
            if column not in df.columns
        ]
        if missing:
            raise ValueError(
                "Missing required indicators: " + ", ".join(missing)
            )

        return df[list(required_columns)].notna().all(axis=1)

    @staticmethod
    def volume_sma(df, period=20):

        return df["volume"].rolling(period).mean()

    @staticmethod
    def atr(df, period=14):

        high_low = df["high"] - df["low"]

        high_close = (df["high"] - df["close"].shift()).abs()

        low_close = (df["low"] - df["close"].shift()).abs()

        tr = high_low.combine(high_close, max).combine(low_close, max)

        return tr.rolling(period).mean()