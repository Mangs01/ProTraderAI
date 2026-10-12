PHASE 28A BLOCKED ? OFFICIAL DAILY DATA ACQUISITION OR VALIDATION REQUIRES REVIEW

The exact frozen plan cannot be completed. Official archive requests for 2024-01-22 and 2024-05-20 each returned HTTP 404 on all three attempts. Both dates are classified NORMAL in the unchanged frozen calendar. Official notices corroborate a calendar conflict. No session was added, removed, shifted, or substituted.

- January 22: [NSE Clearing circular CMPT60343](https://nsearchives.nseindia.com/content/circulars/CMPT60343.pdf) addresses the public holiday and references NSE/CMTR/60338. Direct web access to CMTR60338 failed; no unofficial copy was used.
- May 20: [NSE capital-market circular CMTR61518](https://nsearchives.nseindia.com/content/circulars/CMTR61518.pdf) explicitly declares the trading holiday for parliamentary elections.

Further calendar/protocol review requires separate authorization. Phase28A does not repair or reseal the frozen inputs.

| Check | Result |
|---|---|
| Prechecks | PASS against frozen inputs; subsequent official evidence conflicts with two NORMAL classifications |
| Branch / starting and ending HEAD | main / 7ff8b3e227f1507424aa6611e7cb62120a5a76a6 |
| Initial working tree | Clean, verified before Phase28A work |
| Phase26 canonical SHA256 | 2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa ? matched |
| Phase27 readiness SHA256 | 9f3903d1e82f0e5d1cc3fd0d9f727ef66b1c367717ccc6b60addd74bcfa88815 ? matched |
| Calendar SHA256 | 13274fbe46c6df033b93537feda34532ccced0670c9153ccd135fba6b3084c72 ? matched |
| History manifest SHA256 | 9fe2580d123522ad6b8993236407967a060fe720b28dd7a9464636d88cefe734 ? matched |
| Liquidity manifest SHA256 | 386e2c19593c40e81f271f776a0134089476596eff471aab782c1cc6b47c6398 ? matched |
| Acquisition start UTC | 2026-09-20T03:47:42.290876+00:00 |
| Acquisition end UTC | 2026-09-20T03:54:57.856367+00:00 |
| Planned / acquired unique dates | 253 / 251 |
| Official bhavcopy requests / successes | 257 / 251 |
| Retries / failed attempts / failed dates | 4 / 6 / 2 |
| Non-200 / malformed / schema failures | 6 / 0 / 0 |
| Raw files / SHA256-verified files | 251 / 251; all revalidated offline |
| Raw aggregate manifest SHA256 | b96b6681664c08d70408e9274c0e188b9ad82fbaaac32149a8aa4e7ecd9da7e5 |
| Raw manifest definition | SHA256 of canonical JSON ordered date/sha256 pairs from session_index.json |
| Validated format counts | 201 legacy / 50 UDiFF (planned 203 / 50) |
| Selection date / format | 2024-09-17 / UDiFF |
| Selection source / STK-EQ rows | 2,867 / 1,838 |
| Selection unique / duplicate / invalid-missing ISINs | 1,838 / 0 / 0 |
| Selection zero / missing traded values | 0 / 0 |
| History coverage | 250 / 252 sessions; complete 252-observation checks unavailable |
| Liquidity coverage | 60 / 60 sessions; no median/ranking computed |
| Validated STK/EQ rows across acquired files | 460,174 |
| Missing sessions | 2024-01-22; 2024-05-20; HTTP 404 after three attempts each |
| Duplicate dates / raw hashes / partial files | 0 / 0 / 0 |
| Identity anomalies | 65 ISINs with multiple symbols; 76 symbols with multiple ISINs, unresolved |
| Corporate-action review | Not completed; no identity continuity inferred or retrospectively replaced |
| Derived daily layer | Not created because exact coverage failed; 0 persisted rows, hash unavailable |
| Selection universe frame | Validated in memory only; no final cohort selected |
| Tests | python -m pytest -q: 486 passed, 3 known historical preservation failures; 24 Phase28A tests passed; no new failures |
| Compile | PASS for new module and tests |
| Git | Only new Phase28A source, tests, and small metadata are untracked; no tracked/staged changes |
| Bulk policy | Raw and derived paths remain ignored; no bulk file tracked; .gitignore unchanged |
| Preservation | Phase26/27 and all tracked historical files unchanged |

The three preservation failures are the already documented Phase16 byte mismatch, listed in verification.json. No repair, normalization, or expectation change was attempted.

Network accounting separates 257 canonical bhavcopy requests from metadata web operations: 4 opens and 3 search queries in 2 search batches. Per-request URLs, timestamps, HTTP results and hashes are in request_audit.json and session_index.json. Source interpretation is documented in source_review.json. Official [NSE reports](https://www.nseindia.com/all-reports) confirms the July 8, 2024 UDiFF transition. Legacy TOTTRDVAL and UDiFF TtlTrfVal are used exactly as frozen. Other legacy series are not inferred to be STK.

No SmartAPI, Angel One login, candle/intraday acquisition, strategy research, market-data backtest, live-feed, order, cohort ranking/selection, or Stage B/C strategy evaluation occurred. The explicitly requested offline regression suite was the only execution of existing test code. No credentials or .env were read or changed; no secrets were printed. No staging, commit, push, destructive Git action, or git gc occurred.

Files: precheck.json; request_audit.json; session_index.json; result.json; validation_audit.json; identity_anomalies.json; source_review.json; verification.json. Bulk raw bytes remain local-only under research/data/new_cycle_001/raw/bhavcopy/. Identity anomaly lists are observations across the acquired subset, not eligibility decisions.
