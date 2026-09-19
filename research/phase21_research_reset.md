# Phase 21  Research program reset and evidence synthesis

## Decision and evidence boundary

**Recommend Option E: pause strategy development until a stronger structural economic hypothesis is defined and preregistered. Do not create Strategy J.**

Seven SBIN FIVE_MINUTE families have been evaluated. Every family is negative before explicit charges, every full-sample BUY and SELL bucket is negative, every chronological half is negative, and realized drawdown is at least 39.02%. Strategy I failed its held-out period with gross P&L **-48,363.91** before **22,253.79** of charges. Continued rule generation on the same instrument/timeframe would compound high research-overfitting risk.

Only saved Phase 12, 13, 14B, 15, 16, 17, 19, 20, 20A and 20B artifacts were used. No strategy execution, signal generation, backtest, optimization, side-only test or new-data access occurred.

- **MarchSeptember 2026:** 125 represented research/validation sessions; A/D/E/F/G/H and Phase 16. H was selection-contaminated.
- **September 2025March 2026:** 129 represented Phase 18 held-out sessions; exposed by I's sole Phase 20 evaluation and audited in Phase 20B.

## Master comparison

Amounts are INR. Gross includes saved slippage and excludes charges. Halves are attribution, not reruns. AH and I are not pooled.

| Strategy | Family | Dataset/role | Trades W/L | Win % | Gross | Charges | Net | PF | DD % | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| A | EMA/RSI state | MarSep 2026 research | 484 174/310 | 35.95 | -53,108.84 | 42,517.88 | -95,626.73 | .6100 | 95.78 | REJECT |
| D | Regime lock | MarSep 2026 research | 130 50/80 | 38.46 | -25,107.12 | 17,820.84 | -42,927.96 | .6500 | 45.22 | REJECT |
| E | Trend pullback | MarSep 2026 development | 92 33/59 | 35.87 | -21,985.07 | 13,783.24 | -35,768.31 | .5800 | 39.02 | REJECT |
| F | Opening-range breakout | MarSep 2026 development | 142 53/89 | 37.32 | -29,636.88 | 19,035.75 | -48,672.63 | .6100 | 51.68 | REJECT |
| G | VWAP mean reversion | MarSep 2026 development | 248 78/170 | 31.45 | -53,290.47 | 26,527.74 | -79,818.21 | .4800 | 80.15 | REJECT |
| H | Breakout-retest | MarSep 2026 contaminated development | 127 50/77 | 39.37 | -22,844.07 | 16,944.10 | -39,788.17 | .6683 | 39.79 | REJECT |
| I | VWAP reclaim + trend | Sep 2025Mar 2026 held-out | 156 44/112 | 28.21 | -48,363.91 | 22,253.79 | -70,617.70 | .3588 | 70.88 | REJECT; VALIDATED |

| Strategy | BUY trades; gross/net | SELL trades; gross/net | First-half gross/net | Second-half gross/net |
|---|---:|---:|---:|---:|
| A | 241; -31,689.02/-52,485.48 | 243; -21,419.83/-43,141.25 | -36,305.33/-59,660.45 | -16,803.52/-35,966.27 |
| D | 66; -16,693.91/-25,422.57 | 64; -8,413.21/-17,505.39 | -8,299.63/-16,926.08 | -16,807.49/-26,001.88 |
| E | 44; -11,718.02/-18,061.80 | 48; -10,267.04/-17,706.50 | -14,385.25/-21,430.49 | -7,599.82/-14,337.82 |
| F | 66; -25,570.39/-33,936.11 | 76; -4,066.49/-14,736.51 | -12,260.80/-22,103.96 | -17,376.08/-26,568.67 |
| G | 135; -33,039.99/-47,441.25 | 113; -20,250.48/-32,376.96 | -33,884.88/-48,780.33 | -19,405.59/-31,037.88 |
| H | 53; -21,455.49/-28,181.49 | 74; -1,388.58/-11,606.68 | -12,615.87/-22,276.22 | -10,228.19/-17,511.95 |
| I | 80; -17,874.31/-28,881.38 | 76; -30,489.60/-41,736.33 | -32,366.19/-45,883.31 | -15,997.72/-24,734.39 |

## Recurring failure modes

| Mode | Class | Saved evidence |
|---|---|---|
| Negative gross expectancy | **COMMON** | All AI gross results negative; PF .3588.6683. |
| Win rate versus 1.5/2 ATR | **COMMON** | Reference break-even excluding EOD/costs is 42.86%; observed 28.21%39.37%. |
| Stop frequency | **COMMON** | Stops/targets: A 290/166, D 76/46, E 52/31, F 84/50, G 162/77, H 74/47, I 103/43. |
| Weak follow-through | **COMMON** | Phase 16: E sign-changing, pooled F weak, G negative-mean all horizons; H 1/2/3/6/12-bar ATR means .063/.062/.063/.103/-.143. |
| Favorable move then reversal | **COMMON** | E/F/G stopped trades reaching .5 ATR: 59.62%/51.19%/51.23%; 1 ATR only 30.77%/27.38%/29.01%. |
| Fee/slippage drag | **COMMON** | E/F/G friction about .83/.76/.86 ATR/trade; every family already gross-negative. |
| Side asymmetry | **STRATEGY-SPECIFIC** | BUY weaker AH; I reverses ordering. Both sides always lose. |
| Regime instability | **COMMON** | All E/F/G volatility tertiles and AH legacy/CAS slices negative; I failed another period. |
| Chronological instability | **COMMON** | All first/second halves gross- and net-negative. |
| Repeated entries | **STRATEGY-SPECIFIC** | A had 357 repeats and 3.87 trades/session; D removed them but lost gross. |
| Insufficient sample | **NOT ESTABLISHED** | Full samples 92484; subgroup sparsity cannot explain broad failure. |
| Large drawdown | **COMMON** | Every DD 39.02%. |
| Session-policy effects | **NOT ESTABLISHED** | CAS only 27 confounded sessions; I Muhurat had no trades. |

## Cost, side, and entry-edge conclusions

**Underlying gross directional edge was generally absent; costs were material but secondary.** Gross P&L was A -53,108.84; D -25,107.12; E -21,985.07; F -29,636.88; G -53,290.47; H -22,844.07; I -48,363.91. I then incurred 22,253.79 in charges. Phase 16/H fixed-path raw-price bridges are not zero-slippage strategy reruns and do not overturn universal canonical gross failure.

**BUY/SELL: WEAK/INCONSISTENT.** SELL was descriptively better for AH, but lost gross and net. Held-out I reversed the ordering: BUY PF .4812 versus SELL PF .2559. Phase 16 found G SELL forward means worse than BUY and E mixed. No side-only recommendation is supported.

**Entry edge: C  both, with entry timing/selection primary and exit-geometry causality not established.** Short-horizon returns were weak/unstable relative to .76.86 ATR friction. G was negative at every horizon; E changed sign; pooled F was weak. H improved some 16-bar measures but was negative at 12 bars and gross-negative. Roughly half of stopped E/F/G trades first moved .5 ATR favorably, but only 27%31% reached 1 ATR. Target rates were 33.70%/35.21%/31.05%, with median confirmed MFE 1.41/1.47/1.08 ATR. Target-trade MAE exists, but exit-conditioned censoring and unknown intrabar order prevent isolating geometry.

## Timeframe and instrument

**Evidence for timeframe change: MODERATE.** Weak 560 minute persistence, reversals, stop dominance and large friction relative to excursion fit a noisy microstructure-sensitive horizon. A traded 3.87 times/session and occupied 56.21% of bars. Yet lower-frequency D/E/H also failed and no alternate timeframe was tested. A slower timeframe is a research dimension, not a demonstrated fix.

SBIN-only work cannot distinguish general hypothesis failure from SBIN-specific behavior and has no cross-sectional replication. Repeated adaptation after side/time/regime/excursion inspection makes SBIN increasingly contaminated. **Future empirical work must require multiple instruments selected by a precommitted rule.**

## Dataset exposure and overfitting

| Dataset | Period | Exposed by | Pristine for a new influenced hypothesis? |
|---|---|---|---|
| SBIN FIVE_MINUTE research/validation | MarSep 2026 | A/D/E/F/G/H and Phase 16 | **No** |
| SBIN FIVE_MINUTE Phase 18 held-out | Sep 2025Mar 2026 | I Phase 20 and Phase 20B | **No** |

Neither dataset may be treated as pristine held-out data for modified I or a new influenced hypothesis. Original data files are unchanged.

**Overfitting risk: HIGH.** Seven families were examined on one instrument; later hypotheses followed earlier failures; side, time, regime, chronology, forward-return, MFE/MAE, reversal and cost diagnostics were repeatedly inspected. The 2026 set was reused, H was selected after Phase 16, and the former held-out set is now exposed. No formal multiple-testing p-value is claimed.

## Decision matrix

| Option | Merit | Overfitting risk | Complexity | Data need | Supported? |
|---|---|---|---|---|---|
| A: more SBIN 5m rules | Low | Very high | Low | New pristine data but same narrow domain | **No** |
| B: SBIN slower timeframe | Moderate | High | Moderate | New development + two chronological held-outs | **Partial**; SBIN-only problem remains |
| C: frozen hypothesis across NSE basket | High | Moderate | High | Rule-selected multi-instrument panel + two held-outs | **Conditional yes**, after mechanism definition |
| D: change timeframe and universe | High | Moderate if preregistered | Very high | New slower multi-instrument panel + two held-outs | **Conditional**; hypothesis first |
| E: pause and define economic hypothesis | Very high | Lowest | Moderate | No acquisition until protocol freeze | **Yes  recommended** |

No option carries a performance prediction.

## Clean future-data protocol

**Development:** after preregistration, acquire multiple liquid NSE instruments using objective liquidity, listing-history, continuity and data-quality rules fixed before price inspection. Freeze timeframe rationale, sampling, session/corporate-action treatment, missing-data policy, minimum history, partition lengths and exclusions. Use the earliest chronological block for development only.

**First held-out:** a strictly later, non-overlapping panel block using the same frozen universe rule/timeframe. Seal until specification, code hashes, integrity and gates pass. Exactly one canonical run; exposure permanently ends held-out status.

**Second held-out:** a further strictly later, non-overlapping sealed block. Open only if the unchanged hypothesis passes all first-held-out gates. Exactly one confirmation run, with no intervening changes.

- Multiple instruments and chronological separation are mandatory.
- Freeze deterministic period durations/order before acquisition; never choose convenient dates after viewing prices.
- Track hashes, acquisition metadata, first-open time, role, every strategy/diagnostic exposure and pristine/exposed state.
- Preregister rationale, mechanism, timeframe/universe rules, entry/exit/risk/cost assumptions, metrics, sample and decision gates, diagnostics, code hash and defect handling.
- **One-run rule:** one canonical execution per hypothesis per held-out stage. A source/data/integrity defect blocks classification; repair requires documented preregistration and genuinely unexposed validation data.

## Stop conditions

1. Stop before acquisition if no falsifiable structural mechanism can be stated independently of AI diagnostics.
2. Stop a frozen hypothesis on negative gross expectancy at a held-out gate; do not rescue it with exposed side/time/regime/exit/risk/cost changes.
3. Stop the directional-persistence line if it fails across required multi-instrument development and first held-out panels.
4. Stop rather than iterate if failure persists at the preregistered slower timeframe across multiple instruments.
5. Stop if post-hoc subgroup selection dominates or provenance cannot prove validation was pristine.
6. Do not create a named strategy because one descriptive pocket looks favorable or implementation is easy.

## Selected direction and Phase 22

Choose **Option E**. If work resumes, the broad question is: **Does slower-timescale directional persistence across a rule-selected basket of liquid NSE instruments survive realistic costs?** Phase 21 defines no entry rule or threshold.

**Recommended Phase 22 objective:** economic-hypothesis and protocol preregistration onlystate a falsifiable structural rationale, objective universe rule, slower-timeframe rationale, partition rules, gates, exposure-registry schema and stop rules. Acquire no data and execute no strategy.

## Preservation

Phase 21 creates only this report and \`phase21_research_reset.json\`. Production strategy, BacktestEngine, risk/charge/slippage/sizing/indicators/session policy, broker/history/live components, \`.env\`, data and Phase 19/20/20A/20B artifacts remain unchanged. New strategies: **0**. Backtests: **0**. Network/API activity: **0**. No staging, commit or push.
