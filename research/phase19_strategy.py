"""I — VWAP reclaim with trend alignment; preregistration only."""
import math
from research.phase15.common import PrefixState

class VWAPReclaimTrendAlignment(PrefixState):
    """Causal symmetric deviation -> later VWAP reclaim state machine."""
    def __init__(self):
        super().__init__()
        self.day = None
        self.states = {'BUY':'WAIT_DEVIATION','SELL':'WAIT_DEVIATION'}
        self.deviation_indices = {'BUY':None,'SELL':None}
        self.deviations = []
        self.current_signal_timestamp = None
    def required_indicators(self):
        return ('EMA20','EMA50','RSI','ATR','VWAP')
    @staticmethod
    def _finite(row, columns):
        try:
            return all(hasattr(row,c) and math.isfinite(float(getattr(row,c))) for c in columns)
        except (TypeError, ValueError, OverflowError):
            return False
    def get_signal(self, df):
        if len(df) < self._seen:
            raise ValueError('Strategy requires monotonically growing history')
        start=self._seen; self._seen=len(df); signal='HOLD'
        self.current_signal_timestamp = None
        for index in range(start,len(df)):
            # Catch up state/events, but only the final row may signal to callers.
            signal = 'HOLD'
            self.current_signal_timestamp = None
            row=df.iloc[index]; day=row.datetime.date()
            if day != self.day:
                self.day=day; self.states={'BUY':'WAIT_DEVIATION','SELL':'WAIT_DEVIATION'}; self.deviation_indices={'BUY':None,'SELL':None}
            previous=df.iloc[index-1] if index else None
            for side in ('BUY','SELL'):
                state=self.states[side]
                if state=='DONE': continue
                if state=='WAIT_DEVIATION':
                    needed=('close','VWAP','RSI')
                    if not self._finite(row,needed): continue
                    deviation=(float(row.close)<float(row.VWAP) and float(row.RSI)<45) if side=='BUY' else (float(row.close)>float(row.VWAP) and float(row.RSI)>55)
                    if deviation:
                        self.states[side]='WAIT_RECLAIM'; self.deviation_indices[side]=index
                        self.deviations.append({'side':side,'index':index,'timestamp':row.datetime,'close':float(row.close),'vwap':float(row.VWAP),'rsi':float(row.RSI)})
                    continue
                if state=='WAIT_RECLAIM':
                    if previous is None or not self._finite(row,('close','VWAP','RSI','EMA20','EMA50')) or not self._finite(previous,('EMA20',)):
                        continue
                    reclaim=(float(row.close)>float(row.VWAP) and float(row.EMA20)>float(row.EMA50) and float(row.EMA20)>float(previous.EMA20) and float(row.RSI)>=50) if side=='BUY' else (float(row.close)<float(row.VWAP) and float(row.EMA20)<float(row.EMA50) and float(row.EMA20)<float(previous.EMA20) and float(row.RSI)<=50)
                    if reclaim and index>self.deviation_indices[side]:
                        self.states[side]='DONE'; signal=side
                        self.current_signal_timestamp = row.datetime
                        self.emit(side,row,deviation_index=self.deviation_indices[side],deviation_timestamp=df.iloc[self.deviation_indices[side]].datetime)
        if signal != 'HOLD':
            if (self.current_signal_timestamp != df.iloc[-1].datetime
                    or self.events[-1]['timestamp'] != self.current_signal_timestamp
                    or self.events[-1]['signal'] != signal):
                raise RuntimeError('Strategy I signal origin must match current evaluation bar')
        return signal
