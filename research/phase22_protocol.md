# Phase 22 — Economic hypothesis and clean multi-instrument research protocol

Protocol SHA256: `7a7454e22f9984a8cc36be1b4cc7a9477aa79094c11e605f7474b98d3fb9b67c`

This is preregistration only: no acquisition, strategy, signal, backtest, or network/API activity.

## Decision

Saved Phases 12, 13, 14B, 15, 16, 17, 20B, and 21 show A/D/E/F/G/H/I all gross- and net-negative with PF below one. Gross edge was absent; costs were secondary; side asymmetry was inconsistent; entry selection and weak follow-through were primary; no independent exit defect was established. Evidence against FIVE_MINUTE is moderate and both SBIN histories are exposed.

Four mechanisms were assessed: slower directional persistence; volatility compression-to-expansion; cross-sectional relative strength; and market-relative persistence. The canonical JSON records mechanism, persistence, falsification, frequency, costs, applicability, post-hoc risk, complexity, data, and A–I relation for each.

Selected question:

> Does directional movement measured over a meaningful slower intraday interval across a preregistered universe of liquid NSE cash equities contain sufficiently persistent forward directional information to produce positive aggregate gross expectancy and survive realistic execution friction?

The proposed mechanism is gradual information incorporation and split institutional order flow. Non-positive forward gross expectancy, absent breadth, or material reversal across both horizons falsifies it. No profitability is predicted.

## Frozen protocol

THIRTY_MINUTE and SIXTY_MINUTE are co-primary fixed conditions, not a sweep. The primary result gives each 50% weight and equal instrument weight; both must be gross-positive. Formal condition tests use Holm correction.

Select 20–24 (target 24) point-in-time NIFTY 100 cash equities by trailing 60-session median traded value on the last session before Stage A, with 95% of 252 sessions, 252-session listing history, valid actions/identity, and at most four per sector. Exclude suspended, trade-to-trade, SME, sub-INR-20, ambiguous, incomplete, or unadjustable names. Use point-in-time membership, keep later removals through valid history, and never replace retrospectively. SBIN is allowed only if objectively selected, equally weighted, and never decisive. Required fixed context is NIFTY 50 plus the official selection-date sector index.

Deterministically hash-partition identities before prices: 16 visible and 8 withheld at N=24 (at least 7 withheld otherwise). Stage A is the earliest adjacent 12 months, visible identities only. Sealed Stage B is the next 6 months, all identities, one canonical run. Sealed Stage C is the next 6 months, all identities, opened only after unchanged B passes all gates, one run. The blocks anchor mechanically to the latest completed regular session available at acquisition. Design-based sample minima are **TO BE FROZEN BEFORE DATA ACQUISITION** without returns.

Budget: one mechanism and at most two total operational formulations. Only nonsemantic fixes, necessary normalization, and A-only selection between those two may change. No sweeps, combinations, exit optimization, post-result side/session/instrument deletion, timeframe selection, or context rescue.

Freeze adverse 5 bps/leg (or larger justified before acquisition), full NSE charges, 1% position risk, 2% aggregate risk, 2% daily-loss latch, three trades/day, no overnight, and next-physical-bar-open execution after a completed signal. Never loosen economics.

Primary metric: equal-condition, equal-instrument gross expectancy/trade in initial-risk units after slippage and before charges. Secondary: net P&L/expectancy, PF, drawdown, count, cost drag, instrument breadth, and chronology.

Stage B requires zero correctness/provenance violations and a pre-acquisition design-based sample minimum. Signal gates: pooled, both timeframe, visible, and withheld gross expectancy >0; at least 60% of traded instruments and the median instrument gross-positive; at least two of three chronological blocks positive with no block above 60% of positive gross P&L; every leave-one-out estimate positive; no instrument above 25%, and no trade/session above 10%, of positive gross P&L. Deployability additionally requires positive net P&L/expectancy, PF ≥1.10, drawdown ≤20%, and friction ≤50% of pre-friction positive expectancy. Every gate must pass for C.

Use 95% CIs and a hierarchical moving-block bootstrap of contiguous days within instruments, with block length frozen on A; no IID trade bootstrap. Report equal-instrument, leave-one-out, cluster-robust, and three-block results.

Validate timezone, grid, duplicates, missing bars, special/CAS sessions, corporate actions, identity/token mapping, metadata/data hashes, and deterministic reload. Unknown partial sessions fail closed.

The registry records dataset ID, instruments, timeframe, period, SHA256, acquisition date, role, first-read time, spec hash, canonical run count, and status. Once read, never relabel pristine. Both SBIN FIVE_MINUTE March–September 2026 and September 2025–March 2026 are EXPOSED/DEVELOPMENT.

Before held-out, stop and repair using synthetic/development evidence while keeping sealed if semantics remain unchanged. After held-out, never silently patch/rerun; record contamination, assess interpretability, and require fresh data for material change.

Stop for absent mechanism or broad Stage A edge, Stage B gross failure, concentration/post-hoc dependence, broad horizon failure, drawdown/friction breach, correctness/provenance failure, exhausted budget, or deployability failure.

All Phase 22 protocol items are complete: Phase 23 is **READY for offline acquisition-readiness planning only**, not automatic acquisition. Its objective is to freeze independent point-in-time metadata sources, exchange calendar, design-based sample thresholds, manifests, and sealing controls, then require explicit approval before acquisition.

Production, engine, A–I, economics/session components, broker/history/live, environment, datasets, and Phase 19/20/20A/20B/21 artifacts remain unchanged. New strategies: 0. Backtests: 0. Acquisitions: 0. Network/API: 0.
