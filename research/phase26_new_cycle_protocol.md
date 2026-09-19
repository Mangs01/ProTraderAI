# Phase 26 — New Public-Data Research Cycle Preregistration

## Freeze

Cycle ID: **NSE_PUBLIC_STKEQ_24_CYCLE_001**

PHASE26_PROTOCOL_SHA256: **2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa**

Hash definition: SHA-256 over only the canonical_protocol object serialized as UTF-8 JSON with lexicographically sorted keys, comma/colon separators without whitespace, and Unicode preserved. The wrapper and hash field are excluded.

The old cycle remains **BLOCKED — HISTORICAL INDEX MEMBERSHIP NOT PUBLICLY PROVEN**.

## Protocol summary

Hypothesis: **SLOWER-TIMESCALE DIRECTIONAL PERSISTENCE** caused by gradual information incorporation and institutionally split order flow. It is falsified by failure to find a broadly positive implementable Stage-A formulation or by failure of any required Stage-B signal, timeframe, withheld, breadth, economic, concentration, or chronology gate. No exact entry or indicator rules are introduced.

Universe: the **traded STK/EQ selection-session universe**—unique ISINs in the official FINAL bhavcopy for the last authoritative NORMAL session strictly before Stage A. This is not all listed NSE equity; nontrading/suspended names are outside by definition.

History: 252 preceding NORMAL-session observations, without imputation. Liquidity: median official traded value over exactly 60 preceding NORMAL sessions. Legacy TOTTRDVAL and UDiFF TtlTrfVal are one canonical measure. No extra floor or close-times-volume fallback.

Selection: deterministic eligibility, descending liquidity, ISIN then symbol tie-break, exactly 24. Fewer than 24 blocks. No replacement or performance input. Sector is not a selection rule; concentration, breadth, equal-instrument expectancy, and leave-one-out sensitivity are mandatory reports.

Timeframes: co-primary 30m and 60m derived from session-open-anchored FIVE_MINUTE bars. A normal session yields 12 or 6 complete bars plus a 15-minute QC residual that is never researched, padded, merged, or fabricated. Special sessions are manifest-driven and CAS auxiliary rows excluded.

Chronology: future T_NEW is the latest fully completed NORMAL session before the authorized acquisition-readiness start date. A mechanical 24-month window is divided 12/6/6 calendar months and resolved to authoritative sessions.

Contamination: if SBIN is selected it remains in the 24-name cohort and deterministic split, but overlapping exposed Stage B/C observations are excluded from pristine inference, bootstrap inputs, participation denominators, and gates, with no replacement. Insufficient pristine sample fails its gate.

Split: SHA256(protocol hash + colon + ISIN), sorted by digest then ISIN; first 16 DEVELOPMENT_VISIBLE and final 8 CROSS_SECTIONAL_WITHHELD.

Development budget: one mechanism and at most two operational formulations. No threshold sweeps, timeframe winner, indicator mining, repeated stop/target tuning, loser removal, or post-outcome filters.

Economics: preserved complete charges and adverse slippage, 1% position risk, 2% portfolio risk, 2% daily latch, no overnight, completed-bar signals, next-eligible-bar execution, and **maximum 3 opened trades per day portfolio-wide**.

Primary metric: trade gross R to per-instrument mean, equal-instrument condition mean, then equal 30m/60m mean. Zero-trade instruments affect participation only. Secondary metrics are limited to the frozen compact list in JSON.

Stage B gates remain: 240 total and 120 per timeframe; 80% overall/visible/withheld participation; three blocks with 60 trades each; 90% session coverage; every pooled/timeframe/visible/withheld/median expectancy above zero; 60% positive participants; PF at least 1.10; drawdown at most 20%; positive net; bounded friction; 10% trade/session and 25% instrument concentration; at least two positive blocks with no one positive block above 60%.

Statistics: 10,000 hierarchical moving-block bootstrap replications, seed 230023, 95% percentile intervals, identity resampling within split strata, contiguous day blocks, Holm correction for both timeframes, and no IID trade bootstrap.

Governance: new dataset bindings and locks; Stage B/C sealed; one canonical run. Pre-heldout correctness repairs use synthetic/Stage-A evidence and full revalidation. Post-access changes record contamination and cannot silently rerun.

Phase 27 is **READY for acquisition-readiness/freeze work only**. Candle acquisition remains unauthorized. Inference-critical TODOs: zero.

Phase 26 counters: network requests, external metadata reads, bhavcopy downloads, cohort selections, candle calls/rows, strategy implementations/executions, signals, backtests, optimizations, and SmartAPI calls are all **0**.
