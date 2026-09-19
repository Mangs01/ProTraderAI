"""G: fixed one-ATR VWAP stretch, RSI 35/65, one signal per excursion."""
from research.phase15.common import PrefixState

class VWAPMeanReversion(PrefixState):
    def __init__(self):
        super().__init__()
        self.day = None
        self.low = float('inf')
        self.high = float('-inf')
        self.used = {'BUY': False, 'SELL': False}

    def required_indicators(self):
        return ('ATR', 'VWAP', 'RSI', 'EMA20')

    def get_signal(self, df):
        for row in self.unseen(df):
            day = row.datetime.date()
            if day != self.day:
                self.day = day
                self.low, self.high = float('inf'), float('-inf')
                self.used = {'BUY': False, 'SELL': False}
            self.low = min(self.low, float(row.low))
            self.high = max(self.high, float(row.high))
            if self.finite(row, ('close', 'VWAP')):
                if row.close >= row.VWAP:
                    self.used['BUY'] = False
                if row.close <= row.VWAP:
                    self.used['SELL'] = False
        row = next(df.iloc[-1:].itertuples(index=False))
        if not self.finite(row, self.required_indicators()+('close',)) or row.ATR <= 0:
            return 'HOLD'
        buy = (row.close < row.VWAP-row.ATR and row.RSI <= 35 and row.close < row.EMA20
               and row.close > self.low-0.25*row.ATR)
        sell = (row.close > row.VWAP+row.ATR and row.RSI >= 65 and row.close > row.EMA20
                and row.close < self.high+0.25*row.ATR)
        for side, qualifies in (('BUY', buy), ('SELL', sell)):
            if qualifies and not self.used[side]:
                self.used[side] = True
                return self.emit(side, row, session_low=self.low, session_high=self.high)
        return 'HOLD'
