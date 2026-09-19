# Phase 17 — Preregistered breakout-retest hypothesis

**H classification: REJECT.** Exactly one canonical full-dataset H execution. No tuning or comparator reruns.

## Safety, integrity and preregistration

Exact dataset SHA256 `fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6`; metadata SHA256 `e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67`. Published9,309 / regular9,294 / excluded CAS15 / sessions125 / LEGACY98 / CAS27 / policy v2. All previous source/artifact hashes preserved; production and engine unchanged. Preregistered at 2026-09-10T06:50:13.657073+00:00. Source hashes are in JSON.

**name:** H - OPENING RANGE BREAKOUT -> RETEST -> CONTINUATION

**opening_range:** Exactly completed regular 09:15,09:20,09:25 bars; high=max(high), low=min(low); all three required.

**BUY:** At/after09:30 completed close>OR_HIGH arms. A strictly later completed low<=OR_HIGH and close>OR_HIGH qualifies. First eligible qualifying candle emits BUY; direction DONE for session.

**SELL:** At/after09:30 completed close<OR_LOW arms. A strictly later completed high>=OR_LOW and close<OR_LOW qualifies. First eligible qualifying candle emits SELL; direction DONE for session.

**no_filters:** No RSI/EMA/VWAP/volume filters, tolerances, breakout-distance limits, body thresholds or retest-duration limits. ATR14 is used only by unchanged execution readiness/sizing/stop/target.

**skipped_bars:** Existing harness semantics: process completed regular skipped bars causally for state; record qualifying skipped retests without emission or backfill. Remain armed until first eligible qualifying retest emits. Entry gates are unchanged. Skipped reasons are reported as HARNESS_SKIPPED (position/risk/readiness not individually inferred).

**cutoff:** State expires after existing final allowed signal bar (LEGACY15:05, CAS15:00). First subsequent qualifying retest may be recorded as CUTOFF diagnostic only; no new breakout after expiry. Final tail consumed with emission disabled.

**funnel:** Initial breakout at most once per direction/session before cutoff. Qualifying retests/conversion count distinct armed breakouts with any later qualifying candle (including skipped/cutoff); all candidate candles separately counted. No-qualifying includes no retest through final regular candle. Cutoff-blocked counts distinct breakouts with late candidate. First-retest delays and emitted-retest delays are distinguished.

**execution:** Unchanged runner/engine: completed N signal, physical regular N+1 open, signal ATR, adverse5bps each leg, stop1.5ATR,target2ATR, gaps first, range STOP wins, sole _close_position, no overlap/overnight.

**classification:** Zero violations first. N<30 INSUFFICIENT SAMPLE; gross<=0 REJECT. Candidate requires gross>0,net>0,PF>=1,DD<30%,>=10 trades and gross>0 in each half and each policy regime, >=10 trades on both sides with both sides gross-positive, no Phase15 concentration flag. Otherwise positive gross RESEARCH FURTHER. These conservative research gates are frozen before results.

**comparison_limit:** F has RSI/VWAP/volume entry filters while H deliberately has none. F-vs-H compares complete hypotheses, not an isolated causal effect of retesting. Same dataset informed H: never held-out or production-ready.

The existing global test guard blocks network. Regression tests deliberately contain caught network-denial probes, fake historical transport/auth calls and broker __new__ stubs; these are not external service actions. H process blocks network/DNS/process and broker/live/SmartAPI imports before project imports. No real HistoricalClient, AngelOneBroker, LiveFeed, authentication, account/profile/order activity. Network attempts=0.

## Breakout → retest funnel

| Metric | BUY | SELL |
| --- | --- | --- |
| sessions_with_opening_range | 125 | 125 |
| sessions_with_initial_breakout | 71 | 84 |
| breakout_events | 71 | 84 |
| qualifying_retests | 53 | 76 |
| breakouts_with_no_qualifying_retest | 18 | 8 |
| retests_blocked_by_cutoff | 0 | 1 |
| retests_with_skipped_candidates | 0 | 1 |
| all_qualifying_candidate_candles | 53 | 78 |
| signals_emitted | 53 | 74 |
| signals_entered | 53 | 74 |
| retest_conversion_pct | 74.6479 | 90.4762 |
| entry_conversion_pct | 74.6479 | 88.0952 |

| Side | Delay | Available N | Median bars | Mean bars |
| --- | --- | --- | --- | --- |
| BUY | breakout_to_first_retest_bars | 53 | 2.0000 | 5.7547 |
| BUY | breakout_to_emitted_retest_bars | 53 | 2.0000 | 5.7547 |
| BUY | breakout_to_entry_bars | 53 | 3.0000 | 6.7547 |
| SELL | breakout_to_first_retest_bars | 76 | 4.0000 | 9.2105 |
| SELL | breakout_to_emitted_retest_bars | 74 | 4.0000 | 9.2973 |
| SELL | breakout_to_entry_bars | 74 | 5.0000 | 10.2973 |

Qualifying retests above count distinct breakouts, not repeated candidate candles. Cutoff/skipped categories can overlap and are not additive. Every emitted signal entered; no direction rearms after emission. Late tail records are diagnostic only.

## Full-period H metrics

| Metric | H |
| --- | --- |
| total_trades | 127 |
| winning_trades | 50 |
| losing_trades | 77 |
| breakeven_trades | 0 |
| win_rate | 39.3700 |
| gross_profit | 46028.4800 |
| gross_loss | 68872.5400 |
| gross_net_pnl | -22844.0700 |
| total_charges | 16944.1000 |
| net_pnl | -39788.1700 |
| final_capital | 60211.8300 |
| profit_factor | 0.6700 |
| average_gross_trade | -179.8746 |
| average_net_trade | -313.2927 |
| average_net_win | 785.2792 |
| average_net_loss_signed | -1026.6511 |
| max_drawdown | 39788.1700 |
| max_drawdown_percent | 39.7900 |
| equity_points | 128 |
| buy_signals | 53 |
| sell_signals | 74 |
| hold_evaluations | 7133 |
| buy_trades | 53 |
| sell_trades | 74 |
| stop_count | 74 |
| target_count | 47 |
| eod_count | 6 |
| end_of_backtest_count | 0 |
| charges_per_trade | 133.4181 |
| charges_over_absolute_gross_percent | 74.1729 |
| daily_loss_lock_trigger_count | 6 |
| max_trade_per_day_trigger_count | 0 |
| minimum_stop_exposure_percent | 1.1442 |
| average_stop_exposure_percent | 1.3178 |
| maximum_stop_exposure_percent | 1.5594 |
| quantity_min | 102 |
| quantity_max | 473 |

Engine summaries may be rounded; precise full-period trade sums and PF appear in JSON H.precise and comparison tables. Gross includes slipped fills and excludes explicit charges. PF uses positive gross trade pnl / absolute negative gross trade pnl; winners/losers use net pnl. Side results are attribution on carried sizing, not independently sized side runs; isolated side DD omitted.

## BUY / SELL

| Group | N | Wins | Losses | Win % | Gross INR | Charges INR | Net INR | PF | Avg gross INR | Avg net INR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BUY | 53 | 15 | 38 | 28.3019 | -21455.4867 | 6726.0006 | -28181.4874 | 0.3828 | -404.8205 | -531.7262 |
| SELL | 74 | 35 | 39 | 47.2973 | -1388.5824 | 10218.0998 | -11606.6822 | 0.9593 | -18.7646 | -156.8471 |

## Exits

| Group | N | Wins | Losses | Win % | Gross INR | Charges INR | Net INR | PF | Avg gross INR | Avg net INR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STOP_LOSS | 74 | 0 | 74 | 0.0000 | -68741.5993 | 9703.7054 | -78445.3048 | 0.0000 | -928.9405 | -1060.0717 |
| TARGET | 47 | 47 | 0 | 100.0000 | 45159.8300 | 6376.7304 | 38783.0996 | NA | 960.8474 | 825.1723 |
| END_OF_SESSION | 6 | 3 | 3 | 50.0000 | 737.7002 | 863.6646 | -125.9644 | 6.6336 | 122.9500 | -20.9941 |
| END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NA | NA | 0 |

## Forward returns

Phase16 unchanged: raw physical entry open reference; horizon h ends at close index entry+h-1. BUY future/ref-1; SELL ref/future-1. ATR moves are directional price differences / signal ATR14. No session crossing, unavailable=null; measurement continues after actual exit only for fixed-horizon diagnostics. Percentages below are percentage units.

| Side | Bars | N | Mean % | Median % | Positive % | Mean ATR | Median ATR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 127 | 0.0101 | 0.0049 | 51.1811 | 0.0627 | 0.0267 |
| ALL | 2 | 127 | 0.0107 | 0.0000 | 49.6063 | 0.0616 | 0.0000 |
| ALL | 3 | 127 | 0.0130 | 0.0181 | 54.3307 | 0.0631 | 0.0662 |
| ALL | 6 | 127 | 0.0135 | 0.0000 | 49.6063 | 0.1035 | 0.0000 |
| ALL | 12 | 118 | -0.0355 | 0.0240 | 51.6949 | -0.1431 | 0.1005 |
| BUY | 1 | 53 | -0.0028 | -0.0092 | 47.1698 | 0.0524 | -0.0266 |
| BUY | 2 | 53 | -0.0334 | -0.0676 | 33.9623 | -0.0997 | -0.2016 |
| BUY | 3 | 53 | -0.0437 | -0.0544 | 41.5094 | -0.1352 | -0.2857 |
| BUY | 6 | 53 | -0.0537 | -0.1317 | 30.1887 | -0.1317 | -0.5911 |
| BUY | 12 | 50 | -0.0804 | -0.1194 | 38.0000 | -0.2644 | -0.5247 |
| SELL | 1 | 74 | 0.0193 | 0.0148 | 54.0541 | 0.0700 | 0.0555 |
| SELL | 2 | 74 | 0.0423 | 0.0427 | 60.8108 | 0.1772 | 0.1963 |
| SELL | 3 | 74 | 0.0537 | 0.0378 | 63.5135 | 0.2051 | 0.1752 |
| SELL | 6 | 74 | 0.0617 | 0.0428 | 63.5135 | 0.2719 | 0.2157 |
| SELL | 12 | 68 | -0.0025 | 0.0834 | 61.7647 | -0.0538 | 0.3164 |

## MFE / MAE

Phase16 bounds unchanged: confirmed lower bound includes completed candles before exit plus exit open/raw fill (full candle for EOD); candle_upper additionally includes full exit range, which can contain post-exit moves. Intrabar extrema are not knowable exactly. Reference raw entry; no negative excursions; regular-only bars through recorded exit.

| Side | Bound | Median MFE ATR | Mean MFE ATR | Median MAE ATR | Mean MAE ATR | MFE>=.5 % | >=1 % | >=1.5 % | >=2 % | MAE>=.5 % | >=1 % | >=1.5 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | confirmed | 1.5500 | 1.3282 | 1.2073 | 0.9534 | 68.5039 | 58.2677 | 50.3937 | 41.7323 | 80.3150 | 61.4173 | 0.0000 |
| ALL | candle_upper | 1.5500 | 1.5169 | 1.3298 | 1.1359 | 70.0787 | 59.0551 | 50.3937 | 41.7323 | 80.3150 | 61.4173 | 28.3465 |
| BUY | confirmed | 0.8191 | 1.0929 | 1.2480 | 1.0794 | 56.6038 | 47.1698 | 41.5094 | 28.3019 | 90.5660 | 73.5849 | 0.0000 |
| BUY | candle_upper | 0.9142 | 1.3055 | 1.3681 | 1.2878 | 56.6038 | 49.0566 | 41.5094 | 28.3019 | 90.5660 | 73.5849 | 32.0755 |
| SELL | confirmed | 2.0851 | 1.4968 | 1.0895 | 0.8632 | 77.0270 | 66.2162 | 56.7568 | 51.3514 | 72.9730 | 52.7027 | 0.0000 |
| SELL | candle_upper | 2.0851 | 1.6683 | 1.1899 | 1.0271 | 79.7297 | 66.2162 | 56.7568 | 51.3514 | 72.9730 | 52.7027 | 25.6757 |

## Direct F versus H

| Metric | F | H |
| --- | --- | --- |
| total_trades | 142 | 127 |
| buy_trades | 66 | 53 |
| sell_trades | 76 | 74 |
| gross_net_pnl | -29636.8787 | -22844.0691 |
| profit_factor | 0.6124 | 0.6683 |
| net_pnl | -48672.6276 | -39788.1696 |
| max_drawdown_percent | 51.6800 | 39.7900 |
| win_rate | 37.3200 | 39.3700 |
| average_gross_trade | -208.7104 | -179.8746 |
| average_net_trade | -342.7650 | -313.2927 |
| total_charges | 19035.7500 | 16944.1000 |
| charges_per_trade | 134.0546 | 133.4181 |

| Metric | Change H minus F (trade reduction positive means fewer) |
| --- | --- |
| trade_reduction_pct | 10.5634 |
| gross_change | 6792.8095 |
| net_change | 8884.4580 |
| dd_percentage_point_change | -11.8900 |
| pf_change | 0.0560 |

| Family | Side | Median confirmed MFE ATR | Median confirmed MAE ATR | 1bar mean % | 3bar mean % | 6bar mean % | 12bar mean % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F | ALL | 1.4712 | 1.1981 | -0.0060 | 0.0038 | 0.0001 | 0.0199 |
| F | BUY | 0.8698 | 1.2418 | -0.0322 | -0.0336 | -0.0316 | -0.0224 |
| F | SELL | 1.8279 | 1.0929 | 0.0167 | 0.0363 | 0.0268 | 0.0569 |
| H | ALL | 1.5500 | 1.2073 | 0.0101 | 0.0130 | 0.0135 | -0.0355 |
| H | BUY | 0.8191 | 1.2480 | -0.0028 | -0.0437 | -0.0537 | -0.0804 |
| H | SELL | 2.0851 | 1.0895 | 0.0193 | 0.0537 | 0.0617 | -0.0025 |

F uses RSI/VWAP/volume filters, H does not. Differences cannot isolate retest causality. Changing capital/quantity and trade count also affect aggregate INR comparisons.

## Chronological and policy stability

Original path, no rerun/reset: first62 sessions Mar09-Jun10; second63 Jun11-Sep08. Period DD starts from carried capital and local period-start realized-equity peak, as Phase15; no intrabar mark-to-market. Separate regime counts98/27.

| Period | Sessions | Starting capital | Trades | Gross INR | Net INR | PF | DD % | BUY | SELL | EOD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_half | 62 | 100000 | 71 | -12615.8745 | -22276.2172 | 0.7009 | 22.2762 | 30 | 41 | 3 |
| second_half | 63 | 77723.7828 | 56 | -10228.1946 | -17511.9523 | 0.6169 | 22.5310 | 23 | 33 | 3 |
| LEGACY | 98 | 100000 | 104 | -16116.1779 | -30057.7974 | 0.7187 | 31.3321 | 43 | 61 | 4 |
| CAS | 27 | 69942.2026 | 23 | -6727.8912 | -9730.3721 | 0.4191 | 13.9120 | 10 | 13 | 2 |

## Time of day

Physical entry timestamps; fixed Phase16 buckets, all retained including empty/outside buckets. Diagnostic only.

| Bucket | N | Gross INR | Net INR | PF | Win % |
| --- | --- | --- | --- | --- | --- |
| 09:30-10:29 | 44 | -14175.4615 | -19039.2505 | 0.4688 | 31.8182 |
| 10:30-11:29 | 38 | -10391.9016 | -15737.6161 | 0.5344 | 34.2105 |
| 11:30-12:29 | 14 | 5668.3910 | 3579.2757 | 2.4103 | 71.4286 |
| 12:30-13:29 | 11 | -1753.0868 | -3399.9152 | 0.6979 | 36.3636 |
| 13:30-14:29 | 11 | 798.1977 | -816.6852 | 1.1698 | 54.5455 |
| 14:30-final | 9 | -2990.2080 | -4373.9782 | 0.4403 | 33.3333 |
| OUTSIDE_PREDEFINED | 0 | 0 | 0 | NA | NA |

## Costs

| Metric (INR, ratios are fractions) | H |
| --- | --- |
| brokerage | 5080.0000 |
| stt | 7714.0574 |
| stamp_duty | 926.3722 |
| transaction_charges | 1895.2121 |
| sebi_charges | 61.7353 |
| ipft | 0.0617 |
| gst | 1266.6616 |
| charges | 16944.1004 |
| gross_pnl | -22844.0691 |
| pnl | -39788.1696 |
| slippage_drag | 30867.6537 |
| raw_price_pnl | 8023.5846 |
| turnover | 61735303.4792 |
| charges_over_turnover | 0.0003 |
| charges_over_absolute_gross | 0.7417 |
| average_charge | 133.4181 |

Exact slippage attribution uses saved leg differences times actual quantity. Raw-price pnl keeps actual trade path, size and slipped-entry-dependent exit levels fixed; it is not a zero-slippage rerun. Explicit charges reconcile to saved components.

## A / D / E / F / G / H comparison

| Family | N | Gross INR | Net INR | PF | DD % | Win % | Avg gross INR | Avg net INR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 484 | -53108.8424 | -95626.7255 | 0.6128 | 95.7800 | 35.9500 | -109.7290 | -197.5759 |
| D | 130 | -25107.1199 | -42927.9606 | 0.6542 | 45.2200 | 38.4600 | -193.1317 | -330.2151 |
| E | 92 | -21985.0678 | -35768.3083 | 0.5787 | 39.0200 | 35.8700 | -238.9681 | -388.7860 |
| F | 142 | -29636.8787 | -48672.6276 | 0.6124 | 51.6800 | 37.3200 | -208.7104 | -342.7650 |
| G | 248 | -53290.4684 | -79818.2109 | 0.4765 | 80.1500 | 31.4500 | -214.8809 | -321.8476 |
| H | 127 | -22844.0691 | -39788.1696 | 0.6683 | 39.7900 | 39.3700 | -179.8746 | -313.2927 |

## Correctness, concentration and limitations

127 trades audited; 0 violations. Exact OR construction, completed breakout, strictly later qualified retest, next physical open, observed signal ATR, mirrored fills/slippage, sizing, levels, gap/STOP priority, fee components, one closure/trade, equity, no overlap/overnight, cutoffs and CAS exclusions checked. All emitted signals match entered trades. Additional all-breakout/candidate and forward-index audits passed. No future data used to form signals.

| Concentration metric | Value |
| --- | --- |
| top_five_profitable_sessions_gross_profit_percent | 13.1691 |
| top_five_losing_sessions_gross_loss_percent | 14.9447 |
| net_without_best_five | -45162.3531 |
| concentration_flag | False |

This dataset informed the hypothesis through Phase16 and is NOT held-out. Single instrument, one six-month path, dependent observations, changing capital and small policy/side samples limit generalization. F/H filter differences prevent causal attribution solely to retesting. No alternative H version, parameter optimization or production-readiness claim. Candidate classification would still require genuinely non-overlapping validation.

## Interpretation and next step

**H classification:** REJECT: 127 trades is non-trivial, but gross -INR22,844.07 and PF0.6683 fail the economic gate. Both sides, both chronological halves, and both policy regimes are gross/net negative. No correctness violation or concentration flag.

**Did retesting improve entry quality or merely reduce frequency?:** Some descriptive improvement beyond frequency: F->H PF0.6124->0.6683, average gross -208.71->-179.87 INR, average net -342.76->-313.29 INR, median confirmed MFE1.4712->1.5500 ATR, pooled1/3/6-bar mean returns improve. But pooled12-bar mean falls from+0.01994% to-0.03552%; median MAE slightly worsens1.1981->1.2073 ATR. Thus short-horizon quality improves modestly, not enough for a positive symmetric economic edge. Filter differences, composition and carried sizing prevent attributing this causally to retest alone.

**Forward evidence:** H pooled1/2/3/6/12-bar mean ATR =0.06266/0.06164/0.06313/0.10347/-0.14305. BUY percentage means are negative at every horizon; SELL is positive through6 bars but negative at12. Positive one-bar BUY ATR mean with negative percent mean reflects different volatility normalization, not a direction-convention error.

**Direction evidence:** BUY53 trades,15 wins, gross -21,455.49 INR, net -28,181.49, PF0.3828. SELL74 trades,35 wins, gross -1,388.58, net -11,606.68, PF0.9593. SELL is better but insufficient; both directions retained and no SELL-only version evaluated.

**Stability:** First/second half gross -12,615.87/-10,228.19 INR and net -22,276.22/-17,511.95. LEGACY/CAS gross -16,116.18/-6,727.89 and net -30,057.80/-9,730.37. No positive chronological or policy slice supports continuation under the frozen gate.

**Time of day:** First two entry buckets account for about87.4% of total net loss. The11:30-12:29 bucket is positive (+3,579.28 INR,14 trades); retained descriptively with every losing bucket. No time filter proposed.

**Costs A or B:** A under the canonical gross convention: H loses before explicit charges. Exact fixed-path raw-price accounting +8,023.58 INR less slippage30,867.65 equals gross -22,844.07; explicit charges16,944.10 deepen net to-39,788.17. This is not a positive canonical gross edge destroyed only by fees, nor a zero-slippage backtest. Charges/turnover0.02744637%; charges/absolute gross74.1729%; average fee133.42 INR.

**Skipped-bar interpretation:** The preregistered unchanged-harness semantics were retained. One SELL breakout had skipped qualifying candidates and never emitted; another had a cutoff-blocked retest. No breakout with a skipped first retest later entered in this sample, so consuming versus retaining that missed direction would not change saved H entries here.

**Selection contamination:** H was proposed after Phase16 on this same dataset. All results are exploratory and selection-contaminated; no held-out or production-ready claim. Positive subgroups are not validated alternatives.

**Recommended next step without tuning:** Archive canonical H as rejected. Do not adjust H, remove a side, or filter time buckets. Any further strategy work requires a separately preregistered new economic entry hypothesis and genuinely non-overlapping validation data; this result does not justify tuning H.

**Input path:** data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv

## Validation and artifacts

**precheck_tests:** 356 passed, 0 failed in 12.98s

**precheck_compile:** 82 files passed

**precheck_diff:** PASS

**prerun_tests:** 374 passed, 0 failed; 18 new Phase17 tests

**final_tests:** 374 passed, 0 failed in9.45s; 18 new Phase17 tests

**final_compile:** PASS:85 project Python files; venv/.venv/site-packages/.git excluded

**final_diff_check:** PASS

**final_git_status:** Pre-existing tracked modifications broker/angelone.py, config/settings.py, live/live_feed.py retained; previous untracked files retained. Phase17 adds research/phase17_breakout_retest.py, research/phase17_runner.py, research/phase17_report.md, research/phase17_results.json, tests/test_phase17_research.py. research/ appears as an untracked directory.

**final_preservation:** PASS:101 existing file hashes and3 canonical Phase17 source hashes match; sole-run trade/state/diagnostic hashes unchanged; runs=1; no commit

Report `research/phase17_report.md`; JSON `research/phase17_results.json` includes sole-run trades, all state/funnel records, per-entry diagnostics, source hashes and audits. No unnecessary CSV. Production/engine and Phase15/16 artifacts unchanged. No commit.

