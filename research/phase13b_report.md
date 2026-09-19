# Phase 13B controlled strategy results

Exploratory results only: one instrument, 23 sessions, 2026-08-05 through 2026-09-04. No parameter search or production promotion.

The mandatory run_all() baseline gate passed all 14 frozen metrics. A/B/C/D ran once each for this experiment. The required pytest suite also executes its existing A baseline regression; no B/C/D research reruns occurred.

Dataset: NSE SBIN-EQ, token 3045, FIVE_MINUTE; 1,666 raw rows, 1,656 accepted rows, 10 CAS auxiliary rows. Continuous session 09:15?15:10; latest signal 15:00, latest entry 15:05, EOD 15:10. CSV hash matches metadata; both file hashes were unchanged after execution.

All runs use the existing runner/engine, capital 100,000 INR, risk 1%, daily loss limit 2,000 INR, five trades/day, next physical candle open, signal-bar ATR, 5 bps adverse slippage per leg, 1.5 ATR stop, 2 ATR target, existing charges, open-gap precedence and STOP-first intrabar ambiguity handling.

Monetary values below are INR. Winners/losers and trade statistics use net P&L. Gross P&L is after modeled slippage and before charges. Gross loss and average loser are shown as positive loss magnitudes. Profit factor uses gross profit/gross loss. Monetary components are independently rounded, so a one-paise display difference is possible.

## Fair comparison

| Metric | A State | B Cross | C Cross+RSI | D RegimeLock |
|---|---:|---:|---:|---:|
| Trades | 67 | 22 | 14 | 22 |
| Win rate % | 31.34 | 31.82 | 28.57 | 40.91 |
| Gross net P&L | -24,487.52 | -9,713.45 | -7,247.15 | -5,796.56 |
| Charges | 10,556.40 | 3,848.45 | 2,336.58 | 3,960.83 |
| Net P&L | -35,043.92 | -13,561.90 | -9,583.73 | -9,757.39 |
| Final capital | 64,956.08 | 86,438.10 | 90,416.27 | 90,242.61 |
| Profit factor | 0.43 | 0.42 | 0.36 | 0.61 |
| Max DD % | 36.10 | 15.05 | 11.07 | 12.68 |
| BUY trades | 25 | 11 | 6 | 9 |
| SELL trades | 42 | 11 | 8 | 13 |
| STOP exits | 42 | 15 | 10 | 13 |
| TARGET exits | 19 | 6 | 3 | 7 |
| EOD exits | 6 | 1 | 1 | 2 |
| Average charges/trade | 157.56 | 174.93 | 166.90 | 180.04 |

## Additional metrics

| Metric | A State | B Cross | C Cross+RSI | D RegimeLock |
|---|---:|---:|---:|---:|
| Winners | 21 | 7 | 4 | 9 |
| Losers | 46 | 15 | 10 | 13 |
| Gross profit | 18,747.97 | 7,151.91 | 4,142.25 | 9,174.80 |
| Gross loss | 43,235.49 | 16,865.37 | 11,389.40 | 14,971.36 |
| Equity points | 68 | 23 | 15 | 23 |
| Average net trade | -523.04 | -616.45 | -684.55 | -443.52 |
| Average winner | 735.10 | 855.30 | 891.76 | 848.12 |
| Average loser magnitude | 1,097.41 | 1,303.27 | 1,315.08 | 1,337.73 |
| Median net trade | -1,011.70 | -1,242.09 | -1,259.19 | -1,243.29 |
| Largest winner | 969.62 | 1,050.72 | 1,050.72 | 1,055.87 |
| Largest loser | -1,467.63 | -1,640.69 | -1,640.69 | -1,652.02 |
| Longest winning streak | 4 | 2 | 1 | 2 |
| Longest losing streak | 6 | 7 | 4 | 5 |
| Average holding bars | 11.96 | 14.05 | 18.00 | 14.68 |
| Median holding bars | 7.00 | 6.00 | 8.50 | 6.50 |
| Gross turnover | 41,693,590.93 | 15,845,674.28 | 9,450,487.66 | 16,476,728.47 |
| Charges/gross turnover % | 0.02532 | 0.02429 | 0.02472 | 0.02404 |
| Charges/absolute gross P&L % | 43.11 | 39.62 | 32.24 | 68.33 |

Holding bars count bars touched, including entry and exit bars: exit_index - entry_index + 1. A same-entry-bar exit therefore counts as one holding bar. This is distinct from prohibited entry on the signal candle.

## Signal frequency

| Metric | A State | B Cross | C Cross+RSI | D RegimeLock |
|---|---:|---:|---:|---:|
| BUY signals | 25 | 11 | 6 | 9 |
| SELL signals | 42 | 11 | 8 | 13 |
| HOLD evaluations | 354 | 1083 | 1275 | 1110 |
| Pending created | 67 | 22 | 14 | 22 |
| Pending cancelled | 0 | 0 | 0 | 0 |
| Completed trades | 67 | 22 | 14 | 22 |
| Repeated same-regime entries | 45 | 0 | 0 | 0 |

Counts reflect evaluations permitted by runner position, risk, readiness and cutoff gates, not every candle. Every emitted BUY/SELL creates a pending entry in this runner. Each recorded signal became a completed trade; cancellations were zero. All B/C trade signals satisfied the actual previous/current EMA crossover; C also satisfied current RSI. No B/C repeat or D same-regime re-entry was found.

## BUY versus SELL

| Variant/side | Count | Win rate % | Gross P&L | Charges | Net P&L |
|---|---:|---:|---:|---:|---:|
| A_STATE/BUY | 25 | 16.00 | -16,107.47 | 3,632.20 | -19,739.66 |
| A_STATE/SELL | 42 | 40.48 | -8,380.05 | 6,924.20 | -15,304.26 |
| B_CROSS/BUY | 11 | 9.09 | -9,966.60 | 1,843.43 | -11,810.03 |
| B_CROSS/SELL | 11 | 54.55 | 253.14 | 2,005.02 | -1,751.88 |
| C_CROSS_RSI/BUY | 6 | 0.00 | -6,631.43 | 902.78 | -7,534.21 |
| C_CROSS_RSI/SELL | 8 | 50.00 | -615.72 | 1,433.80 | -2,049.52 |
| D_REGIME_LOCK/BUY | 9 | 22.22 | -5,955.27 | 1,582.47 | -7,537.73 |
| D_REGIME_LOCK/SELL | 13 | 53.85 | 158.71 | 2,378.36 | -2,219.66 |

All four overall results fall in cost category A: strategy loses before costs. B and D SELL subsets fall in category B: small positive gross results become negative after charges. BUY remains the weaker direction across all variants. Lower total charges reflect fewer trades; charges per trade increase relative to A.

## Drawdown and risk

| Metric | A State | B Cross | C Cross+RSI | D RegimeLock |
|---|---:|---:|---:|---:|
| Max drawdown INR | 36,704.03 | 15,178.32 | 11,157.81 | 12,874.49 |
| Max drawdown % | 36.10 | 15.05 | 11.07 | 12.68 |
| Average modeled stop exposure % | 1.3878 | 1.3789 | 1.3502 | 1.3853 |
| Maximum modeled stop exposure % | 1.7108 | 1.6993 | 1.6993 | 1.6992 |
| Daily loss-lock triggers | 14 | 5 | 1 | 4 |
| Max-trade-limit triggers | 3 | 0 | 0 | 0 |

Drawdown uses the existing realized, closed-trade equity curve, not intratrade mark-to-market. Stop exposure is modeled from the entry fill to the slipped stop fill plus round-trip charges, divided by pre-trade capital. The stop is anchored to the slipped entry; entry slippage is not added twice. This diagnostic excludes gap overshoot and is not a maximum possible loss. Trigger counts are distinct daily threshold activations reconstructed from chronological trades, not repeated blocked evaluations.

## Change from A

| Metric | B Cross | C Cross+RSI | D RegimeLock |
|---|---:|---:|---:|
| Trade reduction % | 67.16 | 79.10 | 67.16 |
| Charges reduction % | 63.54 | 77.87 | 62.48 |
| Gross P&L change INR | 14,774.07 | 17,240.37 | 18,690.96 |
| Net P&L change INR | 21,482.02 | 25,460.19 | 25,286.53 |
| Max DD change INR | -21,525.71 | -25,546.22 | -23,829.54 |
| Max DD change percentage points | -21.05 | -25.03 | -23.42 |
| BUY count change | -14.00 | -19.00 | -16.00 |
| SELL count change | -31.00 | -34.00 | -29.00 |

D traded the same 22 direction/regime identifiers as A, once each. A contained 45 additional entries in those regimes: 16 BUY and 29 SELL. D eliminated all 45 repeat entries (67 to 22 trades). This quantifies the lockout effect; P&L differences are path-dependent because capital, timing and risk locks can change, so they cannot be attributed solely to removing 45 unchanged trades.

## Interpretation

- A: REJECT. Repeated entry design produces 45 repeats, negative gross P&L, high total charges and 36.10% drawdown in this sample. Retain it as the frozen reference.
- B: INSUFFICIENT SAMPLE. The event rule removes repeats, but only 22 trades remain; gross profit factor is 0.42 and average net loss/trade is worse than A. Balanced direction counts conceal severe BUY weakness.
- C: INSUFFICIENT SAMPLE. Only 14 trades (six BUY, all losses); gross profit factor 0.36 and worse average net trade than A. Lower aggregate loss and drawdown do not establish improved trade quality.
- D: RESEARCH FURTHER. The structural question has evidence: 45 repeats disappear, gross loss and drawdown decline, profit factor rises to 0.61, and average net trade improves. Gross/net P&L remain negative, SELL gross gains are consumed by charges, and 22 trades are insufficient for promotion.

Only 23 sessions from one instrument and a single contiguous period are represented. Trades within regimes/days are dependent; 67 trades are not 67 independent observations. Direction subsets range from six to 42 trades. There is no held-out period, market-regime replication, reliable tail-loss estimate, or evidence of persistence across instruments. Lower drawdown partly reflects fewer opportunities/exposure. These are exploratory structural findings only.

## Correctness and validation

No correctness issue found in the recorded runs. All 125 trades were checked for next-bar entries, timestamp/index alignment, session/cutoff compliance, no overlapping positions/duplicate close, signal-bar ATR stops/targets, unchanged sizing, charge/net reconciliation, crossover/state eligibility and daily risk limits. Exit-bar scanning confirmed first eligible exit, open-gap precedence, STOP-first ambiguity, adverse exit slippage and EOD behavior. Source inspection confirmed causal indicators and prefix-only signal input.

177 tests passed, zero failed. No tests or Python source changed. Compilation and final Git checks are reported in the final response. New artifacts only: research/phase13b_results.json and research/phase13b_report.md. No network, API, websocket, order activity, production changes, parameter changes, cache changes, or commit.

PHASE 13B COMPLETE ? CONTROLLED A/B/C/D RESULTS READY FOR REVIEW
