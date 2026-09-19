"""F: completed 09:15/09:20/09:25 opening range; one attempt/side/session."""
from datetime import time
from research.phase15.common import PrefixState

class OpeningRangeBreakout(PrefixState):
    def __init__(self):
        super().__init__()
        self.day = None
        self.opening = {}
        self.used = set()

    def required_indicators(self):
        return ('RSI', 'VWAP', 'VolumeSMA')

    def get_signal(self, df):
        opening_times = {time(9, 15), time(9, 20), time(9, 25)}
        for row in self.unseen(df):
            day = row.datetime.date()
            if day != self.day:
                self.day, self.opening, self.used = day, {}, set()
            if row.datetime.time() in opening_times:
                self.opening[row.datetime.time()] = (float(row.high), float(row.low))
        row = next(df.iloc[-1:].itertuples(index=False))
        if row.datetime.time() < time(9, 30) or set(self.opening) != opening_times:
            return 'HOLD'
        if not self.finite(row, self.required_indicators()+('close', 'volume')):
            return 'HOLD'
        upper = max(v[0] for v in self.opening.values())
        lower = min(v[1] for v in self.opening.values())
        buy = row.close > upper and row.close > row.VWAP and row.RSI >= 55
        sell = row.close < lower and row.close < row.VWAP and row.RSI <= 45
        for side, qualifies in (('BUY', buy), ('SELL', sell)):
            if qualifies and row.volume > row.VolumeSMA and side not in self.used:
                self.used.add(side)
                return self.emit(side, row, or_high=upper, or_low=lower)
        return 'HOLD'
