"""Research-only EMA signal variants; production strategy is unchanged."""

from dataclasses import dataclass


REQUIRED_EMA = ("EMA20", "EMA50")


def _ready(df, columns):
    if len(df) < 2:
        return False
    current = df.iloc[-1]
    previous = df.iloc[-2]
    return all(
        column in df.columns
        and current[column] == current[column]
        and previous[column] == previous[column]
        for column in columns
    )


class EMACrossoverStrategy:
    """Emit only on an EMA20/EMA50 relationship transition."""

    def required_indicators(self):
        return REQUIRED_EMA

    def get_signal(self, df):
        if not _ready(df, REQUIRED_EMA):
            return "HOLD"
        previous, current = df.iloc[-2], df.iloc[-1]
        if (
            previous["EMA20"] <= previous["EMA50"]
            and current["EMA20"] > current["EMA50"]
        ):
            return "BUY"
        if (
            previous["EMA20"] >= previous["EMA50"]
            and current["EMA20"] < current["EMA50"]
        ):
            return "SELL"
        return "HOLD"


class EMACrossoverRSIStrategy(EMACrossoverStrategy):
    """EMA crossover event confirmed by RSI on that event candle."""

    def required_indicators(self):
        return REQUIRED_EMA + ("RSI",)

    def get_signal(self, df):
        if not _ready(df, self.required_indicators()):
            return "HOLD"
        event = super().get_signal(df)
        rsi = df.iloc[-1]["RSI"]
        if event == "BUY" and rsi > 60:
            return "BUY"
        if event == "SELL" and rsi < 40:
            return "SELL"
        return "HOLD"


class EMARegimeLockStrategy:
    """State conditions with at most one signal per EMA direction regime."""

    def __init__(self):
        self._used_regime = None

    def required_indicators(self):
        return REQUIRED_EMA + ("RSI",)

    def get_signal(self, df):
        current = df.iloc[-1]
        if any(
            column not in df.columns or current[column] != current[column]
            for column in self.required_indicators()
        ):
            return "HOLD"
        relationship = (
            "BUY" if current["EMA20"] > current["EMA50"]
            else "SELL" if current["EMA20"] < current["EMA50"]
            else "FLAT"
        )
        relationship_series = df["EMA20"].gt(df["EMA50"]).map(
            {True: "BUY", False: "SELL"}
        )
        relationship_series[df["EMA20"].eq(df["EMA50"])] = "FLAT"
        regime_start = len(df) - 1
        while (
            regime_start > 0
            and relationship_series.iloc[regime_start - 1] == relationship
        ):
            regime_start -= 1
        regime = (relationship, regime_start)
        qualifies = (
            relationship == "BUY" and current["RSI"] > 60
            or relationship == "SELL" and current["RSI"] < 40
        )
        if qualifies and self._used_regime != regime:
            self._used_regime = regime
            return relationship
        return "HOLD"


@dataclass
class SignalCounts:
    buy: int = 0
    sell: int = 0
    hold: int = 0


class CountingStrategy:
    """Transparent counter around any runner-compatible strategy."""

    def __init__(self, strategy):
        self.strategy = strategy
        self.counts = SignalCounts()

    def required_indicators(self):
        return self.strategy.required_indicators()

    def get_signal(self, df):
        signal = self.strategy.get_signal(df)
        if signal == "BUY":
            self.counts.buy += 1
        elif signal == "SELL":
            self.counts.sell += 1
        else:
            self.counts.hold += 1
        return signal
