# Phase 14B — Offline longer-history A vs D validation

Both frozen variants are **REJECT** on this dataset. D reduces losses and drawdown materially, but remains unprofitable before and after charges. No production-readiness designation is made.

## Integrity and execution scope

Dataset SHA256: `fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6`

Metadata SHA256: `e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67`

Input: `data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv` and its `.meta.json`. Both supplied hashes match exactly. Independently validated 9,309 published rows, 9,294 regular rows, 15 CAS auxiliary rows, 125 represented sessions, policy version 2, 98 legacy sessions x 75 regular bars, and 27 CAS sessions x 72 regular bars. The unchanged session validator accepted every represented session. No missing required bars, duplicates or off-grid/session anomalies. This verifies represented sessions; it does not establish external exchange-calendar coverage.

A = existing StrategyManager / frozen EMA production behavior. D = existing EMARegimeLockStrategy. Each was executed exactly once through the existing `run_variant`; B/C and `run_all` were not executed. The required regression suite separately reproduces the Phase 12 control and uses mocked research progression tests. Neither regression run repeats the Phase 14B comparison.

All 15 CAS auxiliary rows were removed by the existing runner before indicators, signals, execution and EOD processing. Both captured runner frames contained 9,294 rows. No indicators or EOD prices came from auxiliary rows.

## Full-period metrics

Amounts are INR. PF uses gross P&L, consistent with Phase 13. Wins/losses and averages use net P&L. Average loss below is a positive magnitude. Drawdown uses realized closed-trade equity, not intrabar mark-to-market.

| Metric | A | D |
|---|---:|---:|
| BUY signals | 241 | 66 |
| SELL signals | 243 | 64 |
| HOLD evaluations | 2241 | 6843 |
| Trades | 484 | 130 |
| Winners | 174 | 50 |
| Losers | 310 | 80 |
| Win rate % | 35.95 | 38.46 |
| Gross profit | 84,039.01 | 47,506.66 |
| Gross loss magnitude | 137,147.85 | 72,613.78 |
| Gross net P&L | -53,108.84 | -25,107.12 |
| Charges | 42,517.88 | 17,820.84 |
| Net P&L | -95,626.73 | -42,927.96 |
| Final capital | 4,373.27 | 57,072.04 |
| Gross PF | 0.61 | 0.65 |
| Net PF (supplement) | 0.42 | 0.49 |
| Average net trade | -197.58 | -330.22 |
| Average net win | 393.41 | 813.15 |
| Average net loss magnitude | 529.29 | 1,044.82 |
| Max DD INR | 99,213.47 | 47,104.28 |
| Max DD % | 95.78 | 45.22 |
| Equity points | 485 | 131 |
| BUY trades | 241 | 66 |
| SELL trades | 243 | 64 |
| STOP exits | 290 | 76 |
| TARGET exits | 166 | 46 |
| END_OF_SESSION exits | 28 | 8 |
| END_OF_BACKTEST exits | 0 | 0 |
| Average charges/trade | 87.85 | 137.08 |
| Charges / absolute gross result % | 80.06 | 70.98 |
| Daily loss-lock sessions | 25 | 16 |
| Max-trade-limit sessions | 56 | 0 |
| Minimum modeled stop exposure % | 1.13 | 1.14 |
| Average modeled stop exposure % | 1.49 | 1.33 |
| Maximum modeled stop exposure % | 2.50 | 1.72 |
| Quantity minimum | 12 | 64 |
| Quantity maximum | 365 | 516 |
| Trades/session | 3.87 | 1.04 |
| Active sessions | 125 | 88 |
| Occupied bars | 5224 | 1592 |
| Occupied regular bars % | 56.21 | 17.13 |
| Pending cancellations | 0 | 0 |

Signal counts describe actual strategy evaluations after the runner gates, not every regular bar. Daily trigger counts count sessions reaching each limit; repeated blocked-bar messages are not additional triggers. Both limits may trigger in a single session.

## A versus D and regime-lock effect

| Delta (D minus A unless marked reduction) | Value |
|---|---:|
| total_trades | -354 |
| buy_trades | -175 |
| sell_trades | -179 |
| gross_net_pnl | 28,001.72 |
| net_pnl | 52,698.77 |
| max_drawdown_percent | -50.56 |
| occupied_bar_percent | -39.08 |
| trades_per_session | -2.83 |
| trade_reduction_percent | 73.14 |
| charges_reduction_percent | 58.09 |
| repeated_same_regime_entries_removed | 357 |

A contains 357 repeat entries beyond the first entry in each entered EMA regime; D contains zero. A enters 127 distinct regimes and D enters 130. Thus 357 repeat entries are removed while net trade count falls by 354; the different holding and risk-lock paths allow different regime participation. This is a descriptive comparison, not a same-trade causal P&L attribution.

D reduces BUY trades by 175 (72.61%) and SELL trades by 179 (73.66%). Gross loss improves by INR 28,001.72 and net loss by INR 52,698.77. Max drawdown falls by 50.56 percentage points. Occupied-bar share falls from 56.21% to 17.13%; trades/session fall from 3.872 to 1.040. D retains more capital, so its later quantities and average monetary trade loss are larger despite identical sizing logic.

## BUY versus SELL

| Variant / side | Trades | Wins | Losses | Win % | Gross P&L | Charges | Net P&L | Gross PF | Avg net trade |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A / BUY | 241 | 79 | 162 | 32.78 | -31,689.02 | 20,796.46 | -52,485.48 | 0.55 | -217.78 |
| A / SELL | 243 | 95 | 148 | 39.09 | -21,419.83 | 21,721.42 | -43,141.25 | 0.68 | -177.54 |
| D / BUY | 66 | 23 | 43 | 34.85 | -16,693.91 | 8,728.66 | -25,422.57 | 0.57 | -385.19 |
| D / SELL | 64 | 27 | 37 | 42.19 | -8,413.21 | 9,092.18 | -17,505.39 | 0.75 | -273.52 |

The previously weak BUY side remains weak: it has lower win rate, lower PF, and more negative average net trade than SELL for both variants. SELL is also unprofitable; these results do not justify a side-filter change.

## Exit analysis

| Variant / exit | Trades | Wins | Losses | Gross P&L | Charges | Net P&L |
|---|---:|---:|---:|---:|---:|---:|
| A / STOP_LOSS | 290 | 0 | 290 | -135,546.59 | 25,533.86 | -161,080.45 |
| A / TARGET | 166 | 166 | 0 | 81,777.51 | 14,784.14 | 66,993.37 |
| A / END_OF_SESSION | 28 | 8 | 20 | 660.24 | 2,199.88 | -1,539.64 |
| A / END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 |
| D / STOP_LOSS | 76 | 0 | 76 | -71,852.56 | 10,453.42 | -82,305.98 |
| D / TARGET | 46 | 46 | 0 | 45,583.65 | 6,309.09 | 39,274.56 |
| D / END_OF_SESSION | 8 | 4 | 4 | 1,161.79 | 1,058.33 | 103.46 |
| D / END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 |

STOP_LOSS is the engine label for STOP. Stops dominate losses in both variants. D reduces stop exits from 290 to 76 and targets from 166 to 46. EOD net P&L changes from -1,539.64 over 28 exits to +103.46 over only eight exits; that small positive D bucket does not establish stable EOD profitability. Exit code is shared and unchanged. No END_OF_BACKTEST closures or overnight positions occurred.

## Chronological stability and legacy/CAS

The predetermined split is the first 62 represented sessions (March 9-June 10) and remaining 63 (June 11-September 8). Legacy is March 9-July 31; CAS is August 3-September 8. These are attributed trades from the full runs, with actual carried capital, unchanged indicator/regime history, and a local equity peak reset at each subperiod start. No subperiod runs occurred. Monetary comparisons reflect different capital paths; slice drawdowns are not additive.

| Variant / period | Sessions | Trades | Net P&L | Gross PF | Max DD % | BUY | SELL | EOD exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A / first_half | 62 | 212 | -59,660.45 | 0.64 | 61.06 | 107 | 105 | 7 |
| A / second_half | 63 | 272 | -35,966.27 | 0.54 | 89.16 | 134 | 138 | 21 |
| A / LEGACY | 98 | 371 | -84,862.36 | 0.62 | 85.48 | 190 | 181 | 19 |
| A / CAS | 27 | 113 | -10,764.37 | 0.50 | 71.78 | 51 | 62 | 9 |
| D / first_half | 62 | 64 | -16,926.08 | 0.78 | 20.26 | 34 | 30 | 3 |
| D / second_half | 63 | 66 | -26,001.88 | 0.51 | 31.30 | 32 | 34 | 5 |
| D / LEGACY | 98 | 103 | -31,668.43 | 0.70 | 34.98 | 54 | 49 | 7 |
| D / CAS | 27 | 27 | -11,259.53 | 0.46 | 16.75 | 12 | 15 | 1 |

Both variants lose in every reported period. D deteriorates from first-half PF 0.78 to second-half PF 0.51 and from legacy PF 0.70 to CAS PF 0.46. D CAS net loss exceeds A CAS net loss despite far fewer trades, in part because D enters CAS with much more remaining capital. CAS has only 27 sessions and D only 27 trades; this is weak evidence for separating policy-period effects from market conditions.

## Risk, costs and limitations

Frozen sizing risks 1% of current realized capital against entry-to-stop distance before exit slippage and charges. Stops are 1.5 x signal ATR and targets 2 x signal ATR; entry and exit slippage are adverse 5 bps. Daily loss limit is INR 2,000 and max trades/day is five. EMA 20/50, RSI 14 with >60 BUY / <40 SELL, ATR 14, session policy version 2 and all other production settings remain unchanged. D changes only signal eligibility via the existing regime lock, not exits or sizing.

Modeled all-in stop exposure is 1.13/1.49/2.50% min/mean/max for A and 1.14/1.33/1.72% for D. This includes adverse stop-fill slippage and charges, but is not a guaranteed loss cap because gaps can exceed it. A capital erosion makes minimum brokerage a larger fraction of equity; neither nominal 1% sizing nor the daily loss latch guarantees a hard all-in loss ceiling. The audit found no implementation violation.

D reduces total charges by 58.09%, less than the 73.14% trade reduction. Its average charges/trade rise from 87.85 to 137.08 because quantities and capital paths differ. Charges add 80.06% to A absolute gross loss and 70.98% to D absolute gross loss. Both are already unprofitable before charges; removing cost drag would not establish an edge.

Only one instrument and 125 represented sessions are covered, with serially dependent trades and limited tail coverage. The dataset overlaps the earlier short sample and is not a clean held-out sample. Realized-equity drawdown understates possible intrabar stress; occupied bars are a coarse frequency/exposure proxy, not notional leverage. No additional instruments, configurations, parameter searches or optimized splits were used.

| Tail / concentration diagnostic | A | D |
|---|---:|---:|
| Largest net winner | 1,129.79 | 1,169.92 |
| Largest net loser | -1,390.73 | -1,365.47 |
| Longest losing streak | 10 | 7 |
| Top five winners share of all net wins % | 8.06 | 14.23 |
| Worst session net P&L | -3,063.31 | -2,738.09 |
| Best session net P&L | 3,752.80 | 2,137.92 |

## Correctness and offline audit

All 484 A trades and all 130 D trades passed independent source-bar checks for physical N+1 entry, signal-bar ATR, entry/exit slippage, first valid exit, gap precedence, STOP-before-TARGET intrabar precedence, EOD price/reason, session/cutoff boundaries, quantity sizing, every charge component, net P&L and each realized equity point. Recorded fill/slippage aliases reconcile and positions never overlap. **Correctness violations: 0.**

The captured unchanged runners excluded auxiliary rows before indicators; no pending entries remained and all emitted entries executed (zero cancellations in this dataset). Boundary-cancellation branches are protected by regression tests rather than claimed as empirically exercised here. Source inspection confirms `_close_position()` remains the sole accounting closure path. No engine or existing harness patches were made.

Research network attempts = **0**. Process-level socket guards and audit hooks were installed before research imports. SmartAPI, broker and live module imports were forbidden and none loaded; therefore no HistoricalClient use, AngelOneBroker instantiation, LiveFeed, authentication, API, order, account or profile action occurred in the research process. Regression tests exercise mocked acquisition/authentication/forbidden-action cases under their existing offline network guard; they do not make real broker calls. No network tool was used.

## Classification

**A: REJECT.** 484 trades show negative gross expectancy, 95.78% realized drawdown and losses across both sides and all slices.

**D: REJECT.** The longer 130-trade sample improves precision over Phase 13B (22 trades), but shows -42,927.96 net P&L, gross PF 0.65, 45.22% realized drawdown and persistent negative results across sides, halves and policy periods. Frequency reduction is useful descriptive evidence but does not support held-out-candidate status for this frozen definition. Limited CAS/tail coverage does not overturn the observed broad losses. Neither variant is production-ready.

## Validation and preservation

Precheck: **305 passed, 0 failed** (13.40s); 68 Python files compiled; `git diff --check` passed. Final: **305 passed, 0 failed** (8.12s); 69 Python files compiled in memory excluding venv, .venv, site-packages and .git; `git diff --check` passed. No commit.

All existing Python sources, .env, Phase 12 cache and metadata, Phase 13 outputs, and validation inputs match the before/after SHA256 manifest recorded in JSON, including after the final tests. Existing tracked modifications to broker/angelone.py, config/settings.py and live/live_feed.py predate this work and were preserved.

Artifacts: `research/phase14b_report.md`, `research/phase14b_results.json`; supporting one-shot orchestration: `research/phase14b_validation.py`. JSON contains complete trade records, equity curves, per-trade audit evidence, exposure values, slices, and file manifests. The script refuses to run when results already exist.

Git status (pre-existing entries preserved; research/ now also contains Phase 14B artifacts):

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
```

PHASE 14B COMPLETE — LONGER-HISTORY A-vs-D VALIDATION FINISHED
