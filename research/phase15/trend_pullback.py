"""E: fixed trend pullback, with one signal per deterministic episode."""
from research.phase15.common import PrefixState

class TrendPullback(PrefixState):
    def __init__(self):
        super().__init__()
        self.used = {'BUY': False, 'SELL': False}
        self.episode = {'BUY': 0, 'SELL': 0}
        self.in_pullback = {'BUY': False, 'SELL': False}

    def required_indicators(self):
        return ('EMA20', 'EMA50', 'RSI', 'VWAP')

    def get_signal(self, df):
        for row in self.unseen(df):
            if not self.finite(row, ('close', 'EMA20', 'EMA50')):
                continue
            # Only an actual close back across EMA20 resets a consumed episode.
            if row.close > row.EMA20:
                self.used['BUY'] = False
                self.in_pullback['BUY'] = False
            if row.close < row.EMA20:
                self.used['SELL'] = False
                self.in_pullback['SELL'] = False
            for side, enters in (
                ('BUY', row.EMA20 > row.EMA50 and row.close <= row.EMA20),
                ('SELL', row.EMA20 < row.EMA50 and row.close >= row.EMA20),
            ):
                if enters and not self.in_pullback[side]:
                    self.episode[side] += 1
                    self.in_pullback[side] = True
        if len(df) < 3:
            return 'HOLD'
        row = next(df.iloc[-1:].itertuples(index=False))
        if not self.finite(row, self.required_indicators()+('close',)):
            return 'HOLD'
        slopes = df['EMA50'].iloc[-3:]
        if slopes.isna().any():
            return 'HOLD'
        slope = (float(slopes.iloc[-1])-float(slopes.iloc[0]))/2
        buy = (row.EMA20 > row.EMA50 and slope > 0 and row.close <= row.EMA20
               and row.close > row.EMA50 and row.RSI >= 50 and row.close >= row.VWAP)
        sell = (row.EMA20 < row.EMA50 and slope < 0 and row.close >= row.EMA20
                and row.close < row.EMA50 and row.RSI <= 50 and row.close <= row.VWAP)
        for side, qualifies in (('BUY', buy), ('SELL', sell)):
            if qualifies and not self.used[side]:
                self.used[side] = True
                return self.emit(side, row, episode=self.episode[side], ema50_slope=slope)
        return 'HOLD'
