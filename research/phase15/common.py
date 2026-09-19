"""Causal state processing of every completed regular bar in a runner prefix."""
import math

class PrefixState:
    def __init__(self):
        self._seen = 0
        self.events = []

    def unseen(self, df):
        if len(df) < self._seen:
            raise ValueError('Strategy requires monotonically growing history')
        start = self._seen
        self._seen = len(df)
        return df.iloc[start:].itertuples(index=False)

    @staticmethod
    def finite(row, columns):
        return all(hasattr(row, c) and math.isfinite(float(getattr(row, c))) for c in columns)

    def emit(self, signal, row, **evidence):
        self.events.append(dict(signal=signal, timestamp=row.datetime, **evidence))
        return signal
