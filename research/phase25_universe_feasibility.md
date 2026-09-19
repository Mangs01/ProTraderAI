# Phase 25 — New Research-Cycle Universe Feasibility

## Decision

**NEW PUBLIC-DATA UNIVERSE FEASIBLE**

This conclusion is narrow: a new cycle can define its point-in-time frame as every unique STK/EQ identity in the official final NSE bhavcopy for a mechanically selected normal session. It does not prove a broader universe of every legally listed but nontrading or suspended security.

The old cycle remains: **BLOCKED — HISTORICAL INDEX MEMBERSHIP NOT PUBLICLY PROVEN**.

## Official evidence

On 2024-09-16 the official UDiFF file has 2,899 rows; the feasibility filter has 1,845 STK/EQ rows, 1,845 unique ISINs, no duplicate ISINs, and no zero-turnover row. The 2024-09-13 file has 1,836 such identities. An official 2023-09-15 legacy bhavcopy was also recovered, proving public archive continuity across the 2024 UDiFF schema change.

| Requirement | Finding |
|---|---|
| Historical security master | Proven for traded-EQ frame; partially proven for broader all-listed frame |
| EQ series | Proven from dated official fields |
| ISIN/identity | Feasible with effective-dated mappings; fail closed on ambiguity |
| Listing/history | Feasible via frozen prior-session observations; literal listing dates need corroboration |
| Delisting/suspension | Official records exist; historical files retain later exits |
| Symbol/action continuity | Official reports exist; retrospective use is identity-only |
| Daily turnover | Proven through TOTTRDVAL / TtlTrfVal |
| Price-volume fallback | Feasible but unnecessary while turnover is available |
| Calendar | Feasible through official holiday/special-session circulars |
| Historical sectors | Not proven from reviewed public evidence |

## Survivorship and look-ahead

A dated-bhavcopy seed avoids current-master substitution: later-delisted, renamed, merged, or exited names remain represented when they traded historically. Nontrading/suspended names are excluded by the explicit ex-ante frame. Covering all listed securities would require a dated all-listed master and remains unproven.

Later corporate-action information may resolve identity only; it may not exclude a security because of its later outcome. A current-active-master workflow fails feasibility.

## Candidate definitions

1. A: dated official STK/EQ frame, frozen minimum history, median official daily traded value, deterministic top N.
2. B: A plus a preregistered observation/traded-value floor.
3. C: dated official all-listed EQ master including nontrading securities. Conditional because the dated archive was not proven.

They were compared only on reconstructibility, bias, complexity, burden, auditability, and paid-data dependence. A/B need no paid data established here. C is conditional.

## Sector and cohort constraints

A public point-in-time sector snapshot was not established, so the old sector cap cannot carry forward. A new protocol must prove dated official sectors or preregister another objective, public diversification treatment; Phase 25 does not choose it.

A 20–30 instrument cohort remains reasonable. Nothing here supports changing 24, but the later protocol must justify and freeze the count. Previously used SBIN periods remain **EXPOSED**.

## New-protocol requirements

Freeze before acquisition: structural hypothesis; universe, selection-date, identity and liquidity rules; cohort size; diversification; timeframes; Stage A/B/C chronology; visible/withheld design; economics; primary metric; continuation/rejection gates; statistical plan; exposure registry; defect handling; and stop rules.

## Counters and network

- Official file GET attempts: 14 (13 successful; one obsolete URL returned 404)
- Official searches: 5 batches / 20 queries
- Candle API calls / intraday rows: 0 / 0
- Strategies / executions / backtests / optimizations: 0 / 0 / 0 / 0
- SmartAPI logins or account/order/live calls: 0
- Final cohorts or acquisition manifests: 0

## Preserved hashes

- Phase22: 7a7454e22f9984a8cc36be1b4cc7a9477aa79094c11e605f7474b98d3fb9b67c
- Phase23: 8ffc9f659cae347c1233ee5e09b7a5adc9b863425bb6dd3022587270f325fde3
- Phase24B: 3517be7107241a68255d394f68c5996e99add8974d60e86b4d0c8dcbe0a5fd74

## Official source hashes

- research/metadata/phase25/raw/nse_all_reports.html — a33ab5d7a013ec2082c4cedd1cdf64d75f1d3524a1370dcd110f96821b4af679
- research/metadata/phase25/raw/nse_bhavcopy_20240916.zip — c0ee951905d113af74f36e3bb95f6777f3463b9e593760038a9f05c783131742
- research/metadata/phase25/raw/nse_master_specification.pdf — a1e45b6de312ebf05298fac8a1c4fbe337b8339b7eb110ac75705925bd05487e
- research/metadata/phase25/raw/nse_data_sharing_policy.pdf — e56b39137f84f7b1835537d9c277abe1e06e99a1ad01d2d47c16933da38b26de
- research/metadata/phase25/raw/nse_series_legend.html — 4a9306dbb2e759403f8ab32bac8aa789f22da736560427c82a5fe573ca779656
- research/metadata/phase25/raw/nse_bhavcopy_20240913.zip — 3f487c9b93a5cd050099ed77b6d089bd8fe32f5413da11f3f152d737627c4d0c
- research/metadata/phase25/raw/nse_bhavcopy_20230915.zip — 3421fe70169cc0bbd18d67d815308fdf836b5139778856dabf79b73610e27328
- research/metadata/phase25/raw/nse_securities_available.html — 39f49d67f8963eace16c8c76e664b3b8bd5924fcc174d375fb0c9e9c386d1625
- research/metadata/phase25/raw/nse_delisting.html — 88454804d875f36fe56d7b1920440e7d7e0b158165a33344abba359404b5c774
- research/metadata/phase25/raw/nse_listing_compliance.html — 26da0e5ae69c46cc2119fac2d3b2763ec5c77e52be33c8051887f7891bd66783
- research/metadata/phase25/raw/nse_industry_classification.html — 7c9b1c9d5c4e5a9b38b64ad2e621c44cac2b0d098ac50fb2d41cf379d6b85b8b
- research/metadata/phase25/raw/nse_historical_reports.html — f13a2d38d7d4ebd0d5d85f3860a660cdd2f4f161ff0a16822a1842dd3de471fb
- research/metadata/phase25/raw/nse_calendar_2024.pdf — 7157229ba94c179d280dd0d732da56d0992c482e862fac72d9d3879626c77c8a

## Validation

Precheck: 465 passed; 97 Python files compiled; git diff --check passed.

Final validation: 465 tests passed; 98 Python files compiled; git diff --check passed; all 49 snapshotted old-cycle artifacts were unchanged. The pre-existing dirty/untracked workspace was preserved.

## Recommendation

Draft and preregister a wholly new protocol using A or B after resolving diversification. Candle acquisition remains unauthorized.

