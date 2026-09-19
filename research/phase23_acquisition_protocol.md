# Phase 23 — Offline acquisition-readiness and data-sealing preregistration

PHASE22_PROTOCOL_SHA256: `7a7454e22f9984a8cc36be1b4cc7a9477aa79094c11e605f7474b98d3fb9b67c`

PHASE23_PROTOCOL_SHA256: `8ffc9f659cae347c1233ee5e09b7a5adc9b863425bb6dd3022587270f325fde3`

This phase is offline planning only. Network attempts, API calls, acquisitions, strategies, and backtests are all zero. The canonical JSON is controlling.

## Acquisition sources and universe

Future authorized work must prefer official index-provider/NSE point-in-time constituent, security-master, daily-turnover, calendar/circular, corporate-action, and index-identity records. Broker-primary records are fallbacks only when reconciled and effectively dated. Required fields, date semantics, and fail-closed behavior are frozen per category in JSON; no unverified URLs are asserted.

Selection date is the last valid trading session before Stage A. Only facts known by its close qualify. Candidates are point-in-time NIFTY 100 EQ securities with 252 prior normal sessions, exact 60-session liquidity coverage, unambiguous permanent identity/ISIN/symbol/token, requestable A–C history, and resolved material actions.

Liquidity is the median official daily traded value over exactly 60 normal sessions strictly before selection. Special sessions are excluded and the window walks backward. Missing observations fail eligibility. A uniformly applied price-volume approximation is allowed only if official turnover is unavailable. Ranking ties resolve by ascending ISIN then normalized symbol.

Rank descending, apply a maximum four names per fixed selection-date sector, and accept the first 24. Continue down rank when capped. Deterministic 20–23 shortfalls are accepted; below 20 blocks research. Selected identities remain in cohort after exit, suspension, delisting, symbol change, or merger; absent observations are explicit EVENT_UNAVAILABLE records, never replacements or zero returns.

## Actions, calendar, and bars

Raw execution-valid OHLCV stays unadjusted and immutable. Identity links and analytical adjustment factors are separate. Splits, bonuses, rights/distributions, symbol changes, and mergers/demergers require authoritative effective-dated classification. No adjusted/raw mixing; unresolved material actions fail closed.

The calendar manifest records date, session type, open/close, expected 5/30/60-minute grids, special-session reference, CAS status, and notes. No weekday inference; unknown partial sessions fail closed.

Acquire canonical FIVE_MINUTE candles later and aggregate from the authoritative session open. OHLC is first/max/min/last and volume sums. Six complete source bars form 30m; twelve form 60m; never cross sessions. A normal 09:15–15:30 session is 375 minutes: 12 full 30m or 6 full 60m bars plus a 15-minute terminal residual. The residual remains in raw/QC records as TERMINAL_PARTIAL but is excluded from both research conditions—never padded, merged, extended, or fabricated. Special/CAS sessions use their authoritative grids and the same completeness rule.

NIFTY 50 and selection-date sector indices use permanent identity/effective mapping, canonical 5m source, identical derived grids, hashes, and aligned sessions. Required context gaps fail the aligned date closed.

## Periods, identity split, and sample gates

Let T be the latest completed normal session permitted by separate acquisition authorization. Boundaries are T−24, T−12, and T−6 calendar months. Each start is the first valid session on/after its boundary; each end is the last valid session before the next boundary, with C ending T. Selection date is the preceding valid session.

Withheld assignment sorts SHA256(Phase23 hash + ":" + permanent identity). Visible/withheld counts are 13/7, 14/7, 15/7, 15/8, and 16/8 for cohorts 20–24.

Stage B minimums: 240 trades overall; 120 per condition; participation of at least ceil(80% of cohort), ceil(80% of visible), and ceil(80% of withheld); three predetermined equal-session blocks with at least 60 trades and 90% scheduled-session admission each. Failure is INSUFFICIENT_SAMPLE.

Both timeframe expectancies, both group expectancies and medians, and the pooled primary metric must be positive. At least ceil(60% of participating instruments) must be gross-positive and median instrument expectancy positive. At least two chronological thirds must be positive, with no block above 60% of positive block P&L.

Friction equals charges plus absolute modeled slippage divided by summed positive pre-friction trade P&L; denominator ≤0 fails, and ratio must be ≤0.50. Positive gross contributions define concentration denominators; a zero denominator fails. Single trade/session/instrument limits are 10%/10%/25%. Aggregate PF remains ≥1.10 and realized portfolio drawdown ≤20%; instrument/condition values are diagnostic.

Trade R is gross P&L after slippage and before charges divided by frozen initial risk. Average within instrument, then equally across participating instruments within condition, then 50/50 across conditions. Zero-trade and valid-event-absent identities remain participation/accountability records and are never imputed.

## Statistical, manifest, and sealing rules

Use 10,000 hierarchical moving-block bootstrap replications with seed 230023: resample identities within visible/withheld strata, then contiguous day blocks, retaining all same-day trades. Stage A selects block length as the first lag with absolute daily-R autocorrelation below .10 for two lags, clamped to 5–20 days, then freezes it. Report 95% percentile intervals. Holm at two-sided .05 covers only the 30m and 60m mean-versus-zero tests. Trades are never treated IID.

Stage manifests contain role, cohort/context, periods, calendars/actions/identity hashes, raw/derived hashes, timestamps, both protocol hashes, spec hash, run count, and exposure. Acquisition requests specify identity/token/series, source interval, dates, chunks, session/retry/rate rules, and destinations. Phase 23 sends none.

Future workflow: acquire immutable raw data; validate; derive deterministically; hash everything; register roles; expose A; keep B/C sealed; on authorized held-out first read record timestamp and bind spec hash; atomically change canonical run count 0→1; deny repeats and never restore pristine status.

A research governance guard—not broker/history modification—checks role/state, explicit authorization artifact, hashes, predecessor gates, and run lock. It fails closed.

## Phase 24 gate

All acquisition-readiness rules are frozen and there are no inference-critical TODOs. Phase 24 is READY only for the recommended scope: implement synthetic-tested governance manifests/guards and, after a separate explicit authorization naming sources/date/network scope, acquire authoritative metadata first. Completion of Phase 23 does not authorize any acquisition, candle request, strategy, or backtest.
