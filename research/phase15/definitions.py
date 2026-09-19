"""Predetermined definitions and reporting conventions, fixed before execution."""
DEFINITIONS = {
    'E': {
        'family': 'TREND PULLBACK',
        'BUY': ['EMA20 > EMA50', '(EMA50[N] - EMA50[N-2]) / 2 > 0; all latest 3 values ready',
                'close <= EMA20', 'close > EMA50', 'RSI >= 50', 'close >= session VWAP', 'once per pullback episode'],
        'SELL': ['EMA20 < EMA50', '(EMA50[N] - EMA50[N-2]) / 2 < 0; all latest 3 values ready',
                 'close >= EMA20', 'close < EMA50', 'RSI <= 50', 'close <= session VWAP', 'once per pullback episode'],
        'state': 'BUY episode starts at close <= EMA20 in bullish EMA regime; after signal rearm only at close > EMA20, then next pullback. Mirror for SELL. No session reset; skipped regular bars update state. No signal is backfilled on skipped bars.',
    },
    'F': {
        'family': 'OPENING RANGE BREAKOUT',
        'range': 'High/low extrema of exactly the completed 09:15, 09:20, 09:25 regular bars; all three required.',
        'BUY': ['close > OR_HIGH', 'close > session VWAP', 'RSI >= 55', 'volume > VolumeSMA20', 'one BUY attempt/session'],
        'SELL': ['close < OR_LOW', 'close < session VWAP', 'RSI <= 45', 'volume > VolumeSMA20', 'one SELL attempt/session'],
        'state': 'Earliest eligible bar start 09:30, completed at 09:35; execution next physical 09:35 bar open. Direction budget consumed on signal (one attempt); runner guards ensure every emitted validation signal enters. If any F signal fails to enter, stop for review. Budgets reset each session.',
    },
    'G': {
        'family': 'VWAP MEAN REVERSION',
        'BUY': ['close < session VWAP - 1.0 * ATR14', 'RSI <= 35', 'close < EMA20', 'close > session low - 0.25 * ATR14', 'one BUY signal/excursion'],
        'SELL': ['close > session VWAP + 1.0 * ATR14', 'RSI >= 65', 'close > EMA20', 'close < session high + 0.25 * ATR14', 'one SELL signal/excursion'],
        'state': 'BUY rearms only at close >= VWAP, SELL only at close <= VWAP; reset both at session start. Extrema use all completed regular bars so far including current. Skipped bars update extrema and resets without backfilled signals.',
        'limitation': 'The supplied extreme filter is nonbinding for valid OHLC and positive ATR; preserved literally, without an added continuation filter.',
    },
}
METHOD = {
    'indicators': 'Unchanged production indicator implementations: EMA20/50, rolling RSI14, rolling ATR14, VolumeSMA20, cumulative close-times-volume / volume session VWAP. Rolling indicators continue across sessions; VWAP resets each session.',
    'execution': 'Unchanged BacktestRunner and BacktestEngine: completed N signal, physical N+1 open, signal ATR, stop 1.5 ATR, target 2 ATR, adverse 5bps each leg, gaps before range, intrabar STOP wins, sole closure _close_position, EOD/no overnight.',
    'risk': 'Initial INR 100000, 1% capital distance-to-stop sizing, INR 2000 daily loss latch, max five trades/session, unchanged charges/cutoffs/session policy v2.',
    'slices': 'Same Phase14B attribution: 62 sessions Mar09-Jun10; 63 Jun11-Sep08; no reruns or resets. Actual carried capital, local realized-equity peak at slice start. Legacy 98 / CAS 27.',
    'concentration': 'Rank profitable sessions by positive session net and losing sessions by most negative session net. Report gross winning-trade contributions in best five / full gross profit; absolute gross losing-trade contributions in worst five / full gross loss. Also provide netted session gross contributions and denominators. Best-five net / total net is signed; absolute denominator share and net excluding best five are also reported. Zero denominators => null.',
    'concentration_flag': 'Flag if top-five gross-profit share > 50%, top-five gross-loss share > 50%, or positive full net becomes nonpositive excluding best five sessions.',
    'classification': 'Zero correctness violations required before any classification. Fewer than 30 trades => INSUFFICIENT SAMPLE. Gross <= 0 with PF < 1 => REJECT. Candidate requires positive gross and net, PF >= 1, at least 30 trades, DD < 30%, both halves and both policy periods gross-positive with >=10 trades each, and no concentration flag. Other gross-positive cases => RESEARCH FURTHER. No production-ready class.',
    'caveats': 'No parameter search. One instrument and one in-sample history, limited tails and CAS coverage. Realized-equity DD excludes intrabar mark-to-market. Side buckets are attribution, not separately sized strategy runs.',
}
