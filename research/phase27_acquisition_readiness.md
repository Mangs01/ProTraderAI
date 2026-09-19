# Phase 27 — Acquisition Readiness and Date Sealing

Cycle: **NSE_PUBLIC_STKEQ_24_CYCLE_001**
Phase26: **2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa**
PHASE27_READINESS_SHA256: **9f3903d1e82f0e5d1cc3fd0d9f727ef66b1c367717ccc6b60addd74bcfa88815**

The hash is SHA-256 over only the readiness object serialized as canonical UTF-8 JSON with sorted keys and compact separators.

## Frozen dates

- Start: 2026-09-18T11:55:03.3197372+05:30
- T_NEW: 2026-09-17, NORMAL
- Stage A: 2024-09-18 through 2025-09-17
- Stage B: 2025-09-18 through 2026-03-17
- Stage C: 2026-03-18 through 2026-09-17
- Selection: 2024-09-17, NORMAL
- Liquidity: 60 NORMAL sessions, 2024-06-21 through 2024-09-16, hash 386e2c19593c40e81f271f776a0134089476596eff471aab782c1cc6b47c6398
- History: 252 preceding NORMAL sessions excluding selection, 2023-09-07 through 2024-09-16, hash 9fe2580d123522ad6b8993236407967a060fe720b28dd7a9464636d88cefe734
- Calendar hash: 13274fbe46c6df033b93537feda34532ccced0670c9153ccd135fba6b3084c72

The stages are contiguous without overlap. Special sessions are explicit. Pre-CAS normal sessions have 75 five-minute slots, 12 complete 30m and 6 complete 60m bars plus a 15-minute QC residual. From 2026-08-03, validated CAS semantics retain 72 continuous research slots through 15:15; CAS auxiliary rows are excluded, preserving 12 and 6 complete bars.

## Exposure

SBIN exposure overlaps Stage A 2025-09-01..2025-09-17, Stage B 2025-09-18..2026-03-17, and Stage C 2026-03-18..2026-09-08. If selected, it remains in the cohort/split but is excluded from pristine inference for affected held-out stages and is not replaced.

The denominator is all 24 identities. Pristine minima are 20 overall, 13 visible and 7 withheld. Contaminated identities remain denominator nonparticipants, contribute no trades or expectancy, and receive no artificial zero profitability.

## Plans and authorization

The unexecuted bhavcopy plan has 253 dates: 252 history dates plus selection; liquidity dates are a subset. Legacy TOTTRDVAL and UDiFF TtlTrfVal map to official total daily traded value. Missing or ambiguous inputs fail closed.

The cohort template has zero candidates/rankings. The candle template has zero requests. Stage A ends DEVELOPMENT_READABLE after validation/registration; Stage B/C end SEALED. Physical presence is not read permission.

Phase28A is READY only for separate authorization of official daily/bhavcopy acquisition and validation. Phase28B selection and Phase28C FIVE_MINUTE acquisition remain unauthorized.

Network: calendar GET attempts 7 (5 HTTP successes); session circular GET attempts 9 (8 successes); discovery searches 9 batches/29 queries. Bhavcopy, price/turnover, SmartAPI, candle and account/order/live calls are zero. Cohort selection, rankings, strategies, signals, backtests and optimizations are zero.
