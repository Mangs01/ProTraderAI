"""H: preregistered symmetric opening-range breakout, later retest, continuation."""
from datetime import time, timedelta
from research.phase15.common import PrefixState
from utils.session_policy import FiveMinuteSessionPolicy

DEFINITION = {
    'name': 'H - OPENING RANGE BREAKOUT -> RETEST -> CONTINUATION',
    'opening_range': 'Exactly completed regular 09:15,09:20,09:25 bars; high=max(high), low=min(low); all three required.',
    'BUY': 'At/after09:30 completed close>OR_HIGH arms. A strictly later completed low<=OR_HIGH and close>OR_HIGH qualifies. First eligible qualifying candle emits BUY; direction DONE for session.',
    'SELL': 'At/after09:30 completed close<OR_LOW arms. A strictly later completed high>=OR_LOW and close<OR_LOW qualifies. First eligible qualifying candle emits SELL; direction DONE for session.',
    'no_filters': 'No RSI/EMA/VWAP/volume filters, tolerances, breakout-distance limits, body thresholds or retest-duration limits. ATR14 is used only by unchanged execution readiness/sizing/stop/target.',
    'skipped_bars': 'Existing harness semantics: process completed regular skipped bars causally for state; record qualifying skipped retests without emission or backfill. Remain armed until first eligible qualifying retest emits. Entry gates are unchanged. Skipped reasons are reported as HARNESS_SKIPPED (position/risk/readiness not individually inferred).',
    'cutoff': 'State expires after existing final allowed signal bar (LEGACY15:05, CAS15:00). First subsequent qualifying retest may be recorded as CUTOFF diagnostic only; no new breakout after expiry. Final tail consumed with emission disabled.',
    'funnel': 'Initial breakout at most once per direction/session before cutoff. Qualifying retests/conversion count distinct armed breakouts with any later qualifying candle (including skipped/cutoff); all candidate candles separately counted. No-qualifying includes no retest through final regular candle. Cutoff-blocked counts distinct breakouts with late candidate. First-retest delays and emitted-retest delays are distinguished.',
    'execution': 'Unchanged runner/engine: completed N signal, physical regular N+1 open, signal ATR, adverse5bps each leg, stop1.5ATR,target2ATR, gaps first, range STOP wins, sole _close_position, no overlap/overnight.',
    'classification': 'Zero violations first. N<30 INSUFFICIENT SAMPLE; gross<=0 REJECT. Candidate requires gross>0,net>0,PF>=1,DD<30%,>=10 trades and gross>0 in each half and each policy regime, >=10 trades on both sides with both sides gross-positive, no Phase15 concentration flag. Otherwise positive gross RESEARCH FURTHER. These conservative research gates are frozen before results.',
    'comparison_limit': 'F has RSI/VWAP/volume entry filters while H deliberately has none. F-vs-H compares complete hypotheses, not an isolated causal effect of retesting. Same dataset informed H: never held-out or production-ready.'
}

class BreakoutRetest(PrefixState):
    def __init__(self):
        super().__init__()
        self.policy = FiveMinuteSessionPolicy(cas_eligible=True)
        self.day = None
        self.sessions = {}
        self.breakouts = []
        self.retests = []
        self.states = {}
        self.active = {}
        self.opening = {}
        self._times = {}

    def required_indicators(self):
        return ()

    def _advance(self, df, emit_current):
        start = self._seen
        output = 'HOLD'
        for index,row in enumerate(self.unseen(df),start):
            day,clock = row.datetime.date(),row.datetime.time()
            allowed = self._times.setdefault(day,set(self.policy.expected_bar_times(day)))
            if clock not in allowed:
                continue
            if day != self.day:
                self.day,self.opening = day,{}
                self.states = dict(BUY='WAIT_BREAKOUT',SELL='WAIT_BREAKOUT')
                self.active = {}
                self.sessions[str(day)] = dict(opening_range=None)
            if clock in (time(9,15),time(9,20),time(9,25)):
                self.opening[clock] = dict(index=index,timestamp=row.datetime,high=float(row.high),low=float(row.low))
            if len(self.opening) != 3 or clock < time(9,30):
                continue
            upper = max(x['high'] for x in self.opening.values())
            lower = min(x['low'] for x in self.opening.values())
            self.sessions[str(day)]['opening_range'] = dict(high=upper,low=lower,bars=list(self.opening.values()))
            late = clock > self.policy.final_allowed_signal_bar(day)
            eligible = emit_current and index == len(df)-1 and not late
            for side in ('BUY','SELL'):
                state = self.states[side]
                beyond = row.close > upper if side=='BUY' else row.close < lower
                touch = row.low <= upper if side=='BUY' else row.high >= lower
                if state == 'WAIT_BREAKOUT':
                    if late:
                        self.states[side] = 'EXPIRED'
                    elif beyond:
                        record = dict(side=side,session=str(day),index=index,timestamp=row.datetime,
                                      completed_at=row.datetime+timedelta(minutes=5),
                                      or_high=upper,or_low=lower,first_retest=None,signal=None)
                        self.breakouts.append(record)
                        self.active[side] = record
                        self.states[side] = 'WAIT_RETEST'
                    continue  # A breakout candle can never retest itself.
                if state == 'DONE' or side not in self.active:
                    continue
                record = self.active[side]
                if late:
                    self.states[side] = 'EXPIRED'
                if not (beyond and touch and index > record['index']):
                    continue
                # Only first late candidate is needed; it can never emit.
                if late and record.get('late_retest') is not None:
                    continue
                candidate = dict(side=side,session=str(day),index=index,timestamp=row.datetime,
                                 completed_at=row.datetime+timedelta(minutes=5),
                                 breakout_index=record['index'],or_high=upper,or_low=lower,
                                 status='CUTOFF' if late else 'SIGNAL' if eligible else 'HARNESS_SKIPPED')
                self.retests.append(candidate)
                if record['first_retest'] is None:
                    record['first_retest'] = candidate
                if late:
                    record['late_retest'] = candidate
                if eligible:
                    record['signal'] = candidate
                    self.states[side] = 'DONE'
                    output = self.emit(side,row,index=index,breakout_index=record['index'],
                                       breakout_timestamp=record['timestamp'],or_high=upper,or_low=lower)
        return output

    def get_signal(self, df):
        return self._advance(df,True)

    def finish_diagnostics(self, df):
        """Consume runner-skipped tail with no emission; never rerun the strategy."""
        return self._advance(df,False)
