# Phase 18A / Phase 18 ? Non-overlapping historical dataset

## Acceptance

The authoritative exact-date Muhurat extension validated the observed 2025-10-21 13:45?14:40 session as SPECIAL_MUHURAT with 12 bars. The resumed acquisition completed and the dataset is accepted for future held-out research. No strategy was imported or run.

Root cause: Phase 18 originally failed closed because the normal legacy validator assumed every pre-CAS represented session used 09:15?15:25 / 75 bars. The assumption was false for the officially registered NSE/CMTR/70319, Circular 124/2025 Muhurat session. Unknown partial sessions still fail closed.

Policy version remains 2; the research policy metadata now carries the exact special-session registry, so older metadata without that registry is rejected by deterministic metadata equality.

Requested range: 2025-09-01T09:15:00+05:30 through 2026-03-06T15:30:00+05:30. Planned chunks: 7. Authentication calls: 1. Candle calls: 8, with 7 successful API responses, one bounded retry, zero observed 403 responses.

Published rows: 9612; raw rows: 9616; boundary duplicates removed: 4. Actual coverage: 2025-09-01T09:15:00+05:30 through 2026-03-06T15:25:00+05:30. Sessions: 129 total (128 normal legacy, 1 special, 0 CAS). Rejected/incomplete sessions: 0. Missing bars: 0. Remaining duplicates: 0. Off-grid rows: 0. Timezone anomalies: 0. Overlap with the March?September research dataset: 0.

Unclassified absent weekdays: 7 (2025-10-02, 2025-10-22, 2025-11-05, 2025-12-25, 2026-01-15, 2026-01-26, 2026-03-03).

CSV: `data/validation_NSE_3045_FIVE_MINUTE_2025-09-01_2026-03-06.csv`
Metadata: `data/validation_NSE_3045_FIVE_MINUTE_2025-09-01_2026-03-06.csv.meta.json`
Audit: `research/phase18_acquisition_audit.json`
CSV SHA256: `ade5eb291d420577878ada5e6ebf63dd109206deed5939745cde768a2efea16a`
Metadata SHA256: `cafa32c5b4c33734091047bda870df30ef97319280a0765f76551b93e4ebd884`

Cache reload passed hash, schema, coverage, normal/special session validation, and byte-equivalent dataset comparison without network. Network was disabled after acquisition. Profile/account/funds/holdings/positions/orders/trade-book/websocket calls were all zero. Production strategy and engine accounting were unchanged. No commit, push, or git add was performed.
