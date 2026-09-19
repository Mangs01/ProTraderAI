# Phase 20 ? Strategy I first held-out evaluation

**Classification: REJECT. Canonical runs: 1. Correctness violations: 0.**

Strategy I loses before explicit charges: gross net P&L ??48,363.91, explicit charges ?22,253.79, net P&L ??70,617.70. Final capital ?29,382.30 from ?100,000. No variant, side-only run, tuning or reproduction occurred.

## Integrity and preregistration

Expected and actual Phase 19 specification SHA256: `97a972931ee6213fa946869ef1a394ac3606273f6f9c39a9962b7c2ac91c0b62`.

Expected and actual CSV SHA256: `ade5eb291d420577878ada5e6ebf63dd109206deed5939745cde768a2efea16a`.

Expected and actual metadata SHA256: `cafa32c5b4c33734091047bda870df30ef97319280a0765f76551b93e4ebd884`.

9,612 rows; 129 complete sessions: 128 normal legacy and one Muhurat (2025-10-21). CAS, missing bars, duplicates, off-grid/timezone anomalies, incomplete/rejected sessions and prior-dataset timestamp overlap: all 0. First exposure was authorized after precheck/spec gates passed. Exclusive run lock remains COMPLETE with count 1.

## Full-period metrics

| Metric | Value |
| --- | --- |
| trades | 156 |
| wins | 44 |
| losses | 112 |
| breakeven | 0 |
| win_rate | 28.21 |
| gross_profit | 27,064.14 |
| gross_loss | 75,428.05 |
| gross_pnl | -48,363.91 |
| charges | 22,253.79 |
| net_pnl | -70,617.70 |
| profit_factor | 0.36 |
| average_net_trade | -452.68 |
| max_drawdown | 70,875.68 |
| max_drawdown_percent | 70.88 |
| buy_trades | 80 |
| sell_trades | 76 |
| end_of_session | 10 |
| average_gross_trade | -310.03 |
| average_net_win | 481.47 |
| average_net_loss | -819.66 |
| final_capital | 29,382.30 |
| equity_points | 157 |
| turnover | 83,965,102.02 |
| average_charge_per_trade | 142.65 |
| charges_over_turnover_percent | 0.03 |
| charges_over_absolute_gross_percent | 46.01 |
| quantity_min | 51 |
| quantity_max | 1048 |
| risk_exposure_min_percent | 1.23 |
| risk_exposure_mean_percent | 1.48 |
| risk_exposure_max_percent | 1.85 |
| daily_loss_lock_trigger_sessions | 8 |
| max_trades_trigger_sessions | 0 |
| BUY_signals | 83 |
| SELL_signals | 77 |
| HOLD_evaluations | 9452 |

## Deviation ? reclaim ? entry funnel

| Metric | BUY | SELL |
| --- | --- | --- |
| valid_warmup_sessions | 129 | 129 |
| deviations | 119 | 123 |
| deviations_later_reclaimed | 83 | 77 |
| deviations_never_reclaimed | 36 | 46 |
| reclaim_events | 83 | 77 |
| emitted_signals | 83 | 77 |
| cutoff_blocked_signals | 1 | 1 |
| position_blocked_signals | 3 | 0 |
| risk_blocked_signals | 0 | 0 |
| actual_entries | 80 | 76 |
| reclaim_conversion_percent | 69.75 | 62.60 |
| entry_conversion_percent | 96.39 | 98.70 |
| deviation_to_entry_conversion_percent | 67.23 | 61.79 |
| median_deviation_reclaim_bars | 14 | 20 |
| median_deviation_reclaim_minutes | 70 | 100 |
| median_deviation_entry_bars | 14.00 | 21.00 |
| median_deviation_entry_minutes | 70.00 | 105.00 |

Blocker counts overlap; they must not be summed as mutually exclusive reasons. Conversion denominators and lag subsets are identified in the results notes.

## Side diagnostics ? original trade path only

| Metric | BUY | SELL |
| --- | --- | --- |
| trades | 80 | 76 |
| wins | 25 | 19 |
| losses | 55 | 57 |
| win_rate | 31.25 | 25.00 |
| gross_pnl | -17,874.31 | -30,489.60 |
| charges | 11,007.07 | 11,246.72 |
| net_pnl | -28,881.38 | -41,736.33 |
| profit_factor | 0.48 | 0.26 |
| average_gross_trade | -223.43 | -401.18 |
| average_net_trade | -361.02 | -549.16 |

## Exit diagnostics

| Exit | Count | Wins | Losses | Gross ? | Charges ? | Net ? |
| --- | --- | --- | --- | --- | --- | --- |
| STOP | 103 | 0 | 103 | -73,528.37 | 15,148.20 | -88,676.57 |
| TARGET | 43 | 43 | 0 | 26,653.11 | 5,650.45 | 21,002.66 |
| END_OF_SESSION | 10 | 1 | 9 | -1,488.65 | 1,455.14 | -2,943.79 |
| END_OF_BACKTEST | 0 | 0 | 0 | 0 | 0 | 0 |

## Chronological halves ? carried capital, no rerun

| Half | Dates | Sessions | Trades | Gross ? | Net ? | PF | Max DD % | BUY | SELL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIRST_HALF | 2025-09-01 to 2025-12-02 | 64 | 77 | -32,366.19 | -45,883.31 | 0.34 | 47.20 | 39 | 38 |
| SECOND_HALF | 2025-12-03 to 2026-03-06 | 65 | 79 | -15,997.72 | -24,734.39 | 0.39 | 46.75 | 41 | 38 |

## Muhurat diagnostic

2025-10-21: state active; one SELL deviation at 13:45 and one BUY deviation at 14:40. No reclaims, emitted signals, entries or exits; gross/net P&L ?0. All 12 registered starts were included. Existing floating-point VWAP comparison is preserved, as detailed in results notes.

## Concentration and cost attribution

| Metric | Value |
| --- | --- |
| largest_winning_trade_gross | 1,095.45 |
| gross_profit_share_percent | 4.05 |
| largest_profitable_session | 2025-10-30 |
| largest_session_net | 1,296.76 |
| net_profit_share_percent | NOT ESTABLISHED / N/A |
| trade_gate | PASS |
| session_gate | NOT ESTABLISHED |

Net-profit concentration is NOT ESTABLISHED because total net P&L is negative.

| Metric | Value |
| --- | --- |
| gross_net_strategy_result | -48,363.91 |
| explicit_charges | 22,253.79 |
| net_result | -70,617.70 |
| turnover | 83,965,102.02 |
| exact_captured_leg_slippage_drag | 41,982.55 |
| raw_price_pnl_same_trade_path | -6,381.36 |
| limitation | Exact raw-versus-fill leg drag at actual quantities; not a zero-slippage strategy comparator. No rerun. |
| interpretation | Loses before explicit charges |

## Correctness and acceptance

Audited all 9,612 current-row evaluations, 160 signals and 156 trades; exactly 156 sole accounting closures and 157 equity points. Correctness, lookahead and session/cutoff violations: 0. Captured entries, fills, ATR, sizing, levels, gaps, STOP priority, charges, daily risk and final capital reconcile. Existing causal indicators and current-row-only strategy prefixes were used.

| Gate | Result |
| --- | --- |
| correctness_violations_zero | PASS |
| trades_at_least_75 | PASS |
| gross_positive | FAIL |
| net_positive | FAIL |
| PF_at_least_1_10 | FAIL |
| max_DD_at_most_25_percent | FAIL |
| both_halves_gross_positive | FAIL |
| other_half_not_severely_negative | NOT ESTABLISHED |
| not_wholly_dependent_on_one_side | NOT ESTABLISHED |
| single_trade_concentration | PASS |
| single_session_concentration | NOT ESTABLISHED |
| no_session_cutoff_leakage | PASS |

Both halves are gross- and net-negative; neither provides a positive half. Both BUY and SELL are gross- and net-negative. Qualitative candidate gates therefore cannot be established; no post-hoc numeric threshold is assigned. With 156 trades, sample size passes, but the frozen gross-failure rule independently requires REJECT. Fees are not the primary explanation.

## Preservation, validation and limitations

Precheck: 439 passed / 0 failed / 0 skipped; 91 files compiled; diff check PASS. Final: 439 passed / 0 failed / 0 skipped; 92 files compiled; diff check PASS. Frozen spec and saved capture reconciliation PASS.

External network attempts: 0. Login, historical candles, profile, account, funds, holdings, positions, orders, trade-book and websocket/live calls: all 0.

Production, BacktestEngine, economics, indicators, session policy, Phase 18A registry, broker/transport/live sources, .env and Phase 19 artifacts unchanged. Original blocked Phase 20 and Phase 20A artifacts preserved. No post-result source changes. Existing Git modifications/untracked work remain; no staging, commit, push, clean or revert.

One instrument, one held-out period, finite sample, no cross-instrument or second independent validation; regime dependence remains possible. Broad research direction was informed by prior research. This is not universal out-of-sample proof or production readiness. The dataset is now exposed. Reject this frozen hypothesis; any changed hypothesis requires new unexposed data.

Artifacts: phase20_canonical_results.json, phase20_canonical_trades.csv, phase20_canonical_capture.json, phase20_canonical_bars.csv, phase20_canonical_integrity.json and phase20_canonical_run.lock.json.

Execution capture: Every completed regular bar advances Strategy I once. Existing pending-next-bar eligibility, engine entry/exit/risk order and policy are retained. Blocked signals are diagnostic only and never executed late.
