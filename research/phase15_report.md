# Phase 15 - Controlled new-strategy family research

Canonical E/F/G evaluated once each, offline, on the Phase 14 validation history. A/D are loaded from Phase 14B records; no full-validation A/D reruns. No optimization or production changes.

## Outcome

**E: REJECT / GROSS NEGATIVE**. 92 trades; gross P&L INR -21,985.07; net P&L INR -35,768.31; gross PF 0.58; realized max DD 39.02%.

**F: REJECT / GROSS NEGATIVE**. 142 trades; gross P&L INR -29,636.88; net P&L INR -48,672.63; gross PF 0.61; realized max DD 51.68%.

**G: REJECT / GROSS NEGATIVE**. 248 trades; gross P&L INR -53,290.47; net P&L INR -79,818.21; gross PF 0.48; realized max DD 80.15%.

## Dataset integrity and preservation

Dataset: `data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv`. Metadata: same filename plus `.meta.json`.

Dataset SHA256: `fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6`

Metadata SHA256: `e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67`

Exact hash gate passed. Published rows 9,309; regular strategy/execution rows 9,294; CAS auxiliary rows 15; represented sessions 125 (98 legacy x 75 bars, 27 CAS x 72 bars); session-policy version 2. The unchanged validator accepted all represented sessions with no duplicates, missing required bars or unexpected timestamps. This is represented-session validation, not an external exchange-calendar completeness claim.

The existing runner strips auxiliary rows before indicator preparation. All signal, entry, stop/target and EOD timestamps were checked against the regular-session policy. No CAS auxiliary prices were used. Original-file hashes and new canonical source hashes were frozen before execution and verified afterward; manifests are in JSON. Phase 13 and Phase 14 outputs and the Phase 12 cache remain unchanged.

## Exact canonical definitions

### E - TREND PULLBACK

BUY: EMA20 > EMA50; (EMA50[N] - EMA50[N-2]) / 2 > 0; all latest 3 values ready; close <= EMA20; close > EMA50; RSI >= 50; close >= session VWAP; once per pullback episode.

SELL: EMA20 < EMA50; (EMA50[N] - EMA50[N-2]) / 2 < 0; all latest 3 values ready; close >= EMA20; close < EMA50; RSI <= 50; close <= session VWAP; once per pullback episode.

State and timing: BUY episode starts at close <= EMA20 in bullish EMA regime; after signal rearm only at close > EMA20, then next pullback. Mirror for SELL. No session reset; skipped regular bars update state. No signal is backfilled on skipped bars.

### F - OPENING RANGE BREAKOUT

High/low extrema of exactly the completed 09:15, 09:20, 09:25 regular bars; all three required.

BUY: close > OR_HIGH; close > session VWAP; RSI >= 55; volume > VolumeSMA20; one BUY attempt/session.

SELL: close < OR_LOW; close < session VWAP; RSI <= 45; volume > VolumeSMA20; one SELL attempt/session.

State and timing: Earliest eligible bar start 09:30, completed at 09:35; execution next physical 09:35 bar open. Direction budget consumed on signal (one attempt); runner guards ensure every emitted validation signal enters. If any F signal fails to enter, stop for review. Budgets reset each session.

### G - VWAP MEAN REVERSION

BUY: close < session VWAP - 1.0 * ATR14; RSI <= 35; close < EMA20; close > session low - 0.25 * ATR14; one BUY signal/excursion.

SELL: close > session VWAP + 1.0 * ATR14; RSI >= 65; close > EMA20; close < session high + 0.25 * ATR14; one SELL signal/excursion.

State and timing: BUY rearms only at close >= VWAP, SELL only at close <= VWAP; reset both at session start. Extrema use all completed regular bars so far including current. Skipped bars update extrema and resets without backfilled signals.

Definition limitation: The supplied extreme filter is nonbinding for valid OHLC and positive ATR; preserved literally, without an added continuation filter.

Shared indicators: Unchanged production indicator implementations: EMA20/50, rolling RSI14, rolling ATR14, VolumeSMA20, cumulative close-times-volume / volume session VWAP. Rolling indicators continue across sessions; VWAP resets each session.

Shared execution: Unchanged BacktestRunner and BacktestEngine: completed N signal, physical N+1 open, signal ATR, stop 1.5 ATR, target 2 ATR, adverse 5bps each leg, gaps before range, intrabar STOP wins, sole closure _close_position, EOD/no overnight.

Shared risk: Initial INR 100000, 1% capital distance-to-stop sizing, INR 2000 daily loss latch, max five trades/session, unchanged charges/cutoffs/session policy v2.

F consumes its one attempt on signal. Its audit verifies every emitted signal entered and at most one entry per direction/session. Thus the attempt and successful-entry limits coincide in this dataset; no broker fill assumptions or custom entry callbacks were introduced.

## Full-period metrics

Amounts are INR. Gross P&L includes execution slippage, excludes charges. PF is positive gross trade P&L / absolute negative gross trade P&L. Winners/losers and averages use net trade P&L. The displayed average loss is signed. HOLD counts only actual runner evaluations after its gates. Trigger counts count sessions reaching the latch/fifth trade, not repeated blocked-bar log messages.

| Metric | E | F | G |
| --- | ---: | ---: | ---: |
| BUY signals | 44 | 66 | 135 |
| SELL signals | 48 | 76 | 113 |
| HOLD evaluations | 7895 | 7279 | 6105 |
| Total trades | 92 | 142 | 248 |
| Winners | 33 | 53 | 78 |
| Losers | 59 | 89 | 170 |
| Breakeven | 0 | 0 | 0 |
| Win rate % | 35.87 | 37.32 | 31.45 |
| Gross profit | 30,195.95 | 46,817.02 | 48,501.25 |
| Gross loss magnitude | 52,181.02 | 76,453.90 | 101,791.72 |
| Gross net P&L | -21,985.07 | -29,636.88 | -53,290.47 |
| Charges | 13,783.24 | 19,035.75 | 26,527.74 |
| Net P&L | -35,768.31 | -48,672.63 | -79,818.21 |
| Final capital | 64,231.69 | 51,327.37 | 20,181.79 |
| Gross PF | 0.58 | 0.61 | 0.48 |
| Average net trade | -388.79 | -342.76 | -321.85 |
| Average net win | 763.78 | 747.34 | 515.66 |
| Average net loss | -1,033.44 | -991.93 | -706.12 |
| Max drawdown INR | 41,097.11 | 53,872.02 | 81,489.01 |
| Max drawdown % | 39.02 | 51.68 | 80.15 |
| Equity points | 93 | 143 | 249 |
| BUY trades | 44 | 66 | 135 |
| SELL trades | 48 | 76 | 113 |
| STOP exits | 52 | 84 | 162 |
| TARGET exits | 31 | 50 | 77 |
| END_OF_SESSION exits | 9 | 8 | 9 |
| END_OF_BACKTEST exits | 0 | 0 | 0 |
| Charges/trade | 149.82 | 134.05 | 106.97 |
| Charges / absolute gross result % | 62.69 | 64.23 | 49.78 |
| Loss-lock trigger sessions | 6 | 6 | 9 |
| Max-trades/day trigger sessions | 0 | 0 | 2 |
| Minimum modeled stop exposure % | 1.19 | 1.14 | 1.14 |
| Average modeled stop exposure % | 1.37 | 1.34 | 1.40 |
| Maximum modeled stop exposure % | 1.65 | 1.68 | 1.84 |
| Quantity min | 159 | 108 | 24 |
| Quantity max | 506 | 490 | 386 |
| Trades/session | 0.74 | 1.14 | 1.98 |
| Active sessions | 65 | 115 | 125 |
| Occupied bars % | 9.25 | 15.82 | 27.44 |
| Pending cancelled | 0 | 0 | 0 |

Modeled stop exposure includes adverse stop-exit slippage and charges divided by capital immediately before entry. It is not a hard cap; gaps can exceed it. Occupied bars include entry and exit bars and are a coarse duration proxy. Realized drawdown excludes intrabar mark-to-market.

## Gross-edge gate

| Family | Gross edge | Gross P&L | PF before charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| E | GROSS NEGATIVE | -21,985.07 | 0.58 | -35,768.31 |
| F | GROSS NEGATIVE | -29,636.88 | 0.61 | -48,672.63 |
| G | GROSS NEGATIVE | -53,290.47 | 0.48 | -79,818.21 |

Gross classification uses unrounded trade totals: >0 positive, =0 flat, <0 negative. Gross-negative/PF-below-one strategies cannot proceed toward production. No production-ready designation exists in this phase.

## Side analysis

| Family / side | Trades | Wins | Losses | Win % | Gross P&L | Charges | Net P&L | PF | Avg net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E / BUY | 44 | 15 | 29 | 34.09 | -11,718.02 | 6,343.78 | -18,061.80 | 0.54 | -410.50 |
| E / SELL | 48 | 18 | 30 | 37.50 | -10,267.04 | 7,439.46 | -17,706.50 | 0.61 | -368.89 |
| F / BUY | 66 | 18 | 48 | 27.27 | -25,570.39 | 8,365.72 | -33,936.11 | 0.38 | -514.18 |
| F / SELL | 76 | 35 | 41 | 46.05 | -4,066.49 | 10,670.03 | -14,736.51 | 0.88 | -193.90 |
| G / BUY | 135 | 38 | 97 | 28.15 | -33,039.99 | 14,401.26 | -47,441.25 | 0.43 | -351.42 |
| G / SELL | 113 | 40 | 73 | 35.40 | -20,250.48 | 12,126.48 | -32,376.96 | 0.54 | -286.52 |

E: gross-positive sides: none; net-positive sides: none. No side was removed or rerun.

F: gross-positive sides: none; net-positive sides: none. No side was removed or rerun.

G: gross-positive sides: none; net-positive sides: none. No side was removed or rerun.

## Exit analysis

| Family / exit | Trades | Wins | Losses | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E / STOP_LOSS | 52 | 0 | 52 | -50,542.30 | 7,830.53 | -58,372.83 |
| E / TARGET | 31 | 31 | 0 | 28,999.01 | 4,694.71 | 24,304.30 |
| E / END_OF_SESSION | 9 | 2 | 7 | -441.78 | 1,258.00 | -1,699.78 |
| E / END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 |
| F / STOP_LOSS | 84 | 0 | 84 | -74,983.16 | 11,100.44 | -86,083.59 |
| F / TARGET | 50 | 50 | 0 | 46,270.46 | 6,875.93 | 39,394.53 |
| F / END_OF_SESSION | 8 | 3 | 5 | -924.18 | 1,059.39 | -1,983.56 |
| F / END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 |
| G / STOP_LOSS | 162 | 0 | 162 | -101,145.55 | 17,674.28 | -118,819.83 |
| G / TARGET | 77 | 77 | 0 | 48,229.01 | 8,020.89 | 40,208.12 |
| G / END_OF_SESSION | 9 | 1 | 8 | -373.93 | 832.57 | -1,206.50 |
| G / END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 |

STOP_LOSS is the engine name for STOP. All families use identical exits; these buckets describe entry selection and subsequent price paths, not strategy-specific exit logic.

## Time-slice stability

Same Phase14B attribution: 62 sessions Mar09-Jun10; 63 Jun11-Sep08; no reruns or resets. Actual carried capital, local realized-equity peak at slice start. Legacy 98 / CAS 27. Indicators and episode state are not restarted at the split. Slice DD uses each slice starting capital and a local peak; drawdowns are not additive.

| Family / half | Sessions | Trades | Gross P&L | Net P&L | PF | Max DD % | BUY | SELL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E / first_half | 62 | 48 | -14,385.25 | -21,430.49 | 0.54 | 25.41 | 21 | 27 |
| E / second_half | 63 | 44 | -7,599.82 | -14,337.82 | 0.64 | 18.25 | 23 | 21 |
| F / first_half | 62 | 72 | -12,260.80 | -22,103.96 | 0.71 | 25.27 | 31 | 41 |
| F / second_half | 63 | 70 | -17,376.08 | -26,568.67 | 0.49 | 35.34 | 35 | 35 |
| G / first_half | 62 | 119 | -33,884.88 | -48,780.33 | 0.50 | 49.62 | 64 | 55 |
| G / second_half | 63 | 129 | -19,405.59 | -31,037.88 | 0.42 | 60.60 | 71 | 58 |

## Legacy versus CAS

| Family / regime | Sessions | Trades | Gross P&L | Net P&L | PF | Max DD % | BUY | SELL | EOD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E / LEGACY | 98 | 74 | -20,947.27 | -31,938.89 | 0.54 | 35.38 | 37 | 37 | 6 |
| E / CAS | 27 | 18 | -1,037.79 | -3,829.42 | 0.85 | 6.25 | 7 | 11 | 3 |
| F / LEGACY | 98 | 112 | -22,267.95 | -37,459.98 | 0.65 | 40.01 | 51 | 61 | 6 |
| F / CAS | 27 | 30 | -7,368.92 | -11,212.65 | 0.44 | 20.28 | 15 | 15 | 2 |
| G / LEGACY | 98 | 193 | -49,699.79 | -71,791.25 | 0.46 | 72.25 | 106 | 87 | 7 |
| G / CAS | 27 | 55 | -3,590.68 | -8,026.96 | 0.62 | 28.46 | 29 | 26 | 2 |

Legacy March 9-July 31; CAS August 3-September 8. Different capital paths affect monetary comparisons. CAS is only 27 sessions; chronology and market conditions are confounded with policy-period differences.

## Session concentration

Rank profitable sessions by positive session net and losing sessions by most negative session net. Report gross winning-trade contributions in best five / full gross profit; absolute gross losing-trade contributions in worst five / full gross loss. Also provide netted session gross contributions and denominators. Best-five net / total net is signed; absolute denominator share and net excluding best five are also reported. Zero denominators => null.

Predetermined flag: Flag if top-five gross-profit share > 50%, top-five gross-loss share > 50%, or positive full net becomes nonpositive excluding best five sessions.

| Metric | E | F | G |
| --- | ---: | ---: | ---: |
| Best session net | 2,057.76 | 1,159.58 | 2,024.34 |
| Worst session net | -2,516.44 | -2,663.29 | -2,470.07 |
| Best five gross winning-trade contribution | 7,580.81 | 6,077.77 | 10,813.47 |
| Best five share of total gross profit % | 25.11 | 12.98 | 22.30 |
| Worst five gross losing-trade magnitude | 10,615.19 | 10,555.15 | 10,376.51 |
| Worst five share of total gross loss % | 20.34 | 13.81 | 10.19 |
| Best five net P&L | 6,490.75 | 5,485.96 | 8,179.21 |
| Best five / signed total net % | -18.15 | -11.27 | -10.25 |
| Best five / absolute total net % | 18.15 | 11.27 | 10.25 |
| Net excluding best five | -42,259.05 | -54,158.58 | -87,997.42 |
| Concentration flag | False | False | False |

A negative best-five / total-net percentage means profitable sessions offset a full-period loss; it is not a negative contribution to profits. No concentration flag does not imply a positive edge or adequate tail coverage.

| E best_five_sessions | Trades | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| 2026-03-11 | 2 | 2,393.38 | 335.62 | 2,057.76 |
| 2026-06-17 | 2 | 1,681.49 | 332.48 | 1,349.01 |
| 2026-03-09 | 1 | 1,206.82 | 134.61 | 1,072.21 |
| 2026-03-10 | 1 | 1,209.03 | 143.90 | 1,065.13 |
| 2026-05-04 | 1 | 1,090.10 | 143.46 | 946.64 |

| E worst_five_sessions | Trades | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| 2026-03-16 | 2 | -2,272.63 | 243.81 | -2,516.44 |
| 2026-04-07 | 2 | -2,137.38 | 278.91 | -2,416.29 |
| 2026-05-11 | 2 | -2,090.48 | 316.85 | -2,407.33 |
| 2026-03-24 | 2 | -2,143.86 | 241.50 | -2,385.37 |
| 2026-05-19 | 2 | -1,970.83 | 310.63 | -2,281.46 |

| F best_five_sessions | Trades | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| 2026-03-13 | 1 | 1,268.06 | 108.48 | 1,159.58 |
| 2026-03-17 | 1 | 1,270.24 | 120.78 | 1,149.46 |
| 2026-03-12 | 1 | 1,212.99 | 140.63 | 1,072.36 |
| 2026-03-30 | 1 | 1,170.58 | 113.58 | 1,057.00 |
| 2026-04-20 | 1 | 1,155.90 | 108.34 | 1,047.55 |

| F worst_five_sessions | Trades | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| 2026-03-18 | 2 | -2,360.90 | 302.39 | -2,663.29 |
| 2026-05-08 | 2 | -2,112.16 | 279.58 | -2,391.75 |
| 2026-03-23 | 2 | -2,117.90 | 209.47 | -2,327.36 |
| 2026-06-10 | 2 | -1,924.17 | 332.86 | -2,257.03 |
| 2026-04-06 | 2 | -2,040.02 | 207.84 | -2,247.86 |

| G best_five_sessions | Trades | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| 2026-03-10 | 2 | 2,335.47 | 311.13 | 2,024.34 |
| 2026-03-18 | 2 | 2,235.84 | 279.06 | 1,956.78 |
| 2026-04-08 | 2 | 2,130.48 | 240.72 | 1,889.76 |
| 2026-06-08 | 3 | 1,888.30 | 285.05 | 1,603.25 |
| 2026-03-19 | 3 | 1,144.52 | 439.45 | 705.07 |

| G worst_five_sessions | Trades | Gross P&L | Charges | Net P&L |
| --- | ---: | ---: | ---: | ---: |
| 2026-03-13 | 2 | -2,216.96 | 253.11 | -2,470.07 |
| 2026-03-16 | 2 | -2,135.08 | 234.48 | -2,369.55 |
| 2026-03-17 | 2 | -2,108.01 | 242.56 | -2,350.57 |
| 2026-03-24 | 2 | -2,028.00 | 206.05 | -2,234.05 |
| 2026-04-23 | 2 | -1,888.46 | 308.60 | -2,197.06 |

## Trade correctness and offline safety

| Family | Trades audited | Closure calls | Violations |
| --- | ---: | ---: | ---: |
| E | 92 | 92 | 0 |
| F | 142 | 142 | 0 |
| G | 248 | 248 | 0 |

Every trade was checked for physical N+1 entry and observed signal ATR argument; 5bps adverse entry/exit slippage; 1.5/2 ATR stop/target; first qualifying exit including opening gaps before intrabar STOP/TARGET precedence; quantity based on actual pre-entry capital; every charge component; net P&L and each equity point; cutoff/same-session/no-overlap/EOD behavior; and regular-only timestamps. Passive profiling counted `_close_position()` calls and captured runner/entry evidence without replacing engine methods. All recorded signals entered; no pending entry or open position survived the run.

Auxiliary rows were excluded before indicators/signals/execution/EOD by unchanged production code. Boundary branches not observed in a dataset are supported by regression tests, rather than claimed as empirically exercised. JSON retains trades, equity curves, emitted signal evidence, per-trade audit details and observed entry arguments.

Network attempts = 0. Socket and audit guards were installed before research imports; SDK, broker and live imports were prohibited and none loaded. No HistoricalClient network use, AngelOneBroker, LiveFeed, actual authentication, account/profile/order activity. Regression suites separately exercise mocks under the existing network guard. No network tools or acquisition runs were used.

## A / D / E / F / G comparison

| Family | Trades | Gross P&L | Charges | Net P&L | Capital | PF | Max DD % | Win % | BUY | SELL | Charges/trade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 484 | -53,108.84 | 42,517.88 | -95,626.73 | 4,373.27 | 0.61 | 95.78 | 35.95 | 241 | 243 | 87.85 |
| D | 130 | -25,107.12 | 17,820.84 | -42,927.96 | 57,072.04 | 0.65 | 45.22 | 38.46 | 66 | 64 | 137.08 |
| E | 92 | -21,985.07 | 13,783.24 | -35,768.31 | 64,231.69 | 0.58 | 39.02 | 35.87 | 44 | 48 | 149.82 |
| F | 142 | -29,636.88 | 19,035.75 | -48,672.63 | 51,327.37 | 0.61 | 51.68 | 37.32 | 66 | 76 | 134.05 |
| G | 248 | -53,290.47 | 26,527.74 | -79,818.21 | 20,181.79 | 0.48 | 80.15 | 31.45 | 135 | 113 | 106.97 |

**Did any new family become gross-positive?** No. E -21,985.07; F -29,636.88; G -53,290.47 INR gross net P&L.

**Did any new family become net-positive?** No. E -35,768.31; F -48,672.63; G -79,818.21 INR after charges.

**Did any achieve PF >= 1?** No. Gross PF E 0.58, F 0.61, G 0.48.

**Did any reduce DD without eliminating almost all trades?** All three have lower DD than A with non-trivial samples (92/142/248 trades over 65/115/125 active sessions). E alone improves on D: 39.02% versus 45.22%, with 92 versus 130 trades. Reduced frequency and different capital paths confound causal attribution; none demonstrates profitable entry edge. F DD 51.68% and G DD 80.15% remain severe.

**Is performance stable across both halves?** There is no stable profitability: every family is gross- and net-negative in both halves. E gross PF improves 0.54 to 0.64; F deteriorates 0.71 to 0.49; G deteriorates 0.50 to 0.42.

**Is performance stable across legacy and CAS?** Every family is gross- and net-negative in both regimes. E CAS has only 18 trades, F 30, G 55; apparent regime differences are not evidence of an edge or a causal policy effect.

**Is profitability dependent on one side only?** No profitable side exists. Both sides are gross- and net-negative in every family. BUY is weaker than SELL by PF, win rate and average net trade for E/F/G. No side was removed.

**Is the result overly concentrated?** No family triggers the predeclared concentration rule. Best five profitable sessions contribute 25.11% / 12.98% / 22.30% of gross winning-trade profits; worst five contribute 20.34% / 13.81% / 10.19% of gross losses for E/F/G. This does not mitigate broad negative expectancy or limited tail coverage.

## Classification and limitations

Predeclared rules: Zero correctness violations required before any classification. Fewer than 30 trades => INSUFFICIENT SAMPLE. Gross <= 0 with PF < 1 => REJECT. Candidate requires positive gross and net, PF >= 1, at least 30 trades, DD < 30%, both halves and both policy periods gross-positive with >=10 trades each, and no concentration flag. Other gross-positive cases => RESEARCH FURTHER. No production-ready class.

**E: REJECT**. 92 trades provide a non-trivial sample, but full-period gross P&L is negative, gross PF is below one, and both BUY/SELL, both chronological halves and both policy periods are gross- and net-negative. Realized drawdown is 39.02%. No predefined concentration flag is triggered; rejection reflects broad negative results rather than one isolated session. This canonical definition does not qualify for held-out-candidate status.

**F: REJECT**. 142 trades provide a non-trivial sample, but full-period gross P&L is negative, gross PF is below one, and both BUY/SELL, both chronological halves and both policy periods are gross- and net-negative. Realized drawdown is 51.68%. No predefined concentration flag is triggered; rejection reflects broad negative results rather than one isolated session. This canonical definition does not qualify for held-out-candidate status.

**G: REJECT**. 248 trades provide a non-trivial sample, but full-period gross P&L is negative, gross PF is below one, and both BUY/SELL, both chronological halves and both policy periods are gross- and net-negative. Realized drawdown is 80.15%. No predefined concentration flag is triggered; rejection reflects broad negative results rather than one isolated session. This canonical definition does not qualify for held-out-candidate status.

No parameter search. One instrument and one in-sample history, limited tails and CAS coverage. Realized-equity DD excludes intrabar mark-to-market. Side buckets are attribution, not separately sized strategy runs.

The prescribed G session-extreme test does not prevent continuation for valid OHLC/positive ATR. This limitation was identified before execution and deliberately preserved; no new filter, side deletion or exit variation was tried.

Next research step without tuning: Preregister a research-only diagnostic of the saved entry events using fixed forward-return horizons, MAE/MFE and slippage/charge attribution, with no parameter search, side removal, exit changes or additional backtest variants. Use it to understand the common failure mechanism and require a distinct economic hypothesis before proposing another canonical experiment; none of E/F/G should advance as a held-out candidate.

## Validation and Git status

precheck_tests: 305 passed, 0 failed (10.46s)

precheck_compile: 69 files passed

precheck_diff_check: PASS

pre_execution_new_tests: 341 passed, 0 failed (22.60s); 36 new tests

intermediate_fixture_failure: 340 passed, 1 failed: synthetic ATR 100 at price 100 caused negative modeled stop; only test fixture changed to ATR 10 before canonical runs. Existing engine correctly rejected negative charge input.

final_tests: 341 passed, 0 failed (9.87s)

final_compile: 79 Python files passed; excludes venv, .venv, site-packages and .git; in-memory compilation

final_diff_check: PASS

source_freeze: All 83 pre-existing file hashes and all canonical pre-run source hashes match after final tests

artifact_reconciliation: PASS: all side/exit/half/policy buckets reconcile to the single full-run trade logs and net P&L

no_commit: True

One intermediate new-test run had 340 passed / 1 failed because its synthetic ATR 100 at price 100 implied a negative stop; the charge model correctly rejected it. Only test-fixture ATR changed to 10 before any canonical dataset run. The corrected suite passed 341 tests. No engine/harness/strategy patch or canonical rerun followed a result.

Original production strategy/config, engine, risk/charges/slippage, policy, .env, broker/live/acquisition, Phase 12 cache and Phase 13/14 outputs are unchanged against the saved 83-file manifest. No commit.

```text
 M broker/angelone.py
 M config/settings.py
 M live/live_feed.py
?? broker/HISTORICAL_SAFETY.md
?? broker/historical_client.py
?? data/historical_NSE_3045_FIVE_MINUTE.csv
?? data/historical_NSE_3045_FIVE_MINUTE.csv.meta.json
?? data/historical_downloader.py
?? data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv
?? data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv.meta.json
?? research/
?? tests/conftest.py
?? tests/test_phase13_research.py
?? tests/test_phase14a1_isolation.py
?? tests/test_phase14a2_identity.py
?? tests/test_phase14a5_contract.py
?? tests/test_phase14a6_diagnostics.py
?? tests/test_phase15_research.py
```

Artifacts: `research/phase15_report.md`, `research/phase15_results.json`; canonical source and one-shot runner under `research/phase15/`; tests in `tests/test_phase15_research.py`. The renderer reads recorded results only.

PHASE 15 COMPLETE — NEW STRATEGY FAMILY RESEARCH FINISHED
