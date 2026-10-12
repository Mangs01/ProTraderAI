PHASE 28A-R COMPLETE ? CALENDAR DEFECT REPAIRED AND DAILY DATA VALIDATED

Authoritative defect evidence was verified from official NSE sources. January 22, 2024 is proven non-NORMAL for NSE equity trading by the NSE Surveillance circular NSE/SURV/60342, which explicitly cites NSE/CMTR/60338 as the revised trading holiday. May 20, 2024 is proven non-NORMAL by NSE Capital Market circular NSE/CMTR/61518, which explicitly declares the trading holiday for Parliamentary Elections in Mumbai. The source PDFs, SHA256 values, render review, and failed direct CMTR60338 retrieval attempts are recorded in evidence.json and evidence_requests.json.

Original frozen artifacts were not edited. Phase26 protocol SHA256 remains 2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa; original Phase27 readiness remains 9f3903d1e82f0e5d1cc3fd0d9f727ef66b1c367717ccc6b60addd74bcfa88815; original Phase27 calendar remains 13274fbe46c6df033b93537feda34532ccced0670c9153ccd135fba6b3084c72. The original blocked Phase28A raw manifest remains b96b6681664c08d70408e9274c0e188b9ad82fbaaac32149a8aa4e7ecd9da7e5.

Calendar repair was deterministic and outcome-blind:
- old history: 2023-09-07 through 2024-09-16, 252 sessions, hash 9fe2580d123522ad6b8993236407967a060fe720b28dd7a9464636d88cefe734
- corrected history: 2023-09-05 through 2024-09-16, 252 sessions, hash 8f1dc540ca00251314b4beb75bb782cdc8c20cd2cee3433ac2d78b393d5a777a
- removed from NORMAL history: 2024-01-22, 2024-05-20
- added NORMAL sessions: 2023-09-05, 2023-09-06
- old and corrected liquidity: 2024-06-21 through 2024-09-16, 60 sessions, hash 386e2c19593c40e81f271f776a0134089476596eff471aab782c1cc6b47c6398; unchanged
- selection remains 2024-09-17 NORMAL; T_NEW and Stage A/B/C boundaries unchanged

Acquisition reused 251 existing raw files after independent SHA/provenance/schema validation. It downloaded 2 additional files using 2 official requests, with zero retries, failures, non-200 responses, malformed payloads, or schema failures. Corrected coverage is history 252/252, liquidity 60/60, and selection 1/1. The corrected raw hash manifest is 89c8bae354f14b3a24238b37ff30c1874fecb9be2190ae64451d8be2d7750978.

Derived layer: 463553 rows, 253 sessions, 2292 unique ISINs, schema NSE_PUBLIC_STKEQ_DAILY_PHASE28AR_V1, hash 5154d2652a58f880adae93908cd125cd43dc8020d862a14aa0bb53a59a5eb09c. Selection validation frame contains 1838 rows. There are no synthetic rows or forward fills. Identity/action anomalies remain unresolved for Phase28B: 65 ISIN symbol groups and 77 symbol ISIN groups. No ranking or cohort selection occurred.

Verification rebuilt the layer offline from all 253 immutable raw files: PASS, hash 5154d2652a58f880adae93908cd125cd43dc8020d862a14aa0bb53a59a5eb09c, network requests 0.

Tests: 499 passed; 3 failures are the already documented historical Phase16 byte-preservation mismatch and are unchanged. All Phase28A-R tests passed. No new unrelated failures occurred. Python compilation passed.

Git status is untracked Phase28A/Phase28A-R source, tests, and small metadata only; no tracked or staged changes. Bulk raw and derived paths remain ignored and untracked. Nothing was staged, committed, or pushed.

No cohort selection, SmartAPI, Angel One, candle/intraday acquisition, strategy, backtest, Stage B/C exposure, live feed, or order operation occurred. No credentials or .env files were read or changed.

Amendment artifacts: evidence.json, calendar_v1.json, plan_v1.json, readiness_v1.json, amendment_v1.json, preservation_before.json, reuse_audit.json, request_audit.json, session_index.json, result.json, identity_anomalies.json, reproducibility_audit.json, and this report. The original Phase28A blocked audit remains preserved under research/metadata/phase28a/.
