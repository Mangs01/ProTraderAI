PHASE 28B COMPLETE ? POINT-IN-TIME COHORT DETERMINISTICALLY FROZEN

Cycle: NSE_PUBLIC_STKEQ_24_CYCLE_001. Selection session: 2024-09-17. Starting and ending branch: main. Starting and ending HEAD: 7ff8b3e227f1507424aa6611e7cb62120a5a76a6.

All prechecks passed. The corrected history contains exactly 252 preceding NORMAL sessions, 2023-09-05 through 2024-09-16. Liquidity contains exactly the final 60 of those sessions, 2024-06-21 through 2024-09-16. Selection occurs once in the 253-entry session index. All 253 immutable raw files were independently SHA256/provenance/schema validated and compared row-for-row to the existing daily layer, without rewriting raw or derived evidence. The rebuilt CSV digest matches the frozen 463,553-row, 253-session, 2,292-ISIN layer.

Verified input bindings:

| Input | SHA256 |
|---|---|
| derived | 5154d2652a58f880adae93908cd125cd43dc8020d862a14aa0bb53a59a5eb09c |
| history | 8f1dc540ca00251314b4beb75bb782cdc8c20cd2cee3433ac2d78b393d5a777a |
| liquidity | 386e2c19593c40e81f271f776a0134089476596eff471aab782c1cc6b47c6398 |
| protocol | 2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa |
| raw_manifest | 89c8bae354f14b3a24238b37ff30c1874fecb9be2190ae64451d8be2d7750978 |
| Original Phase27 calendar | 13274fbe46c6df033b93537feda34532ccced0670c9153ccd135fba6b3084c72 |
| Original Phase27 readiness | 9f3903d1e82f0e5d1cc3fd0d9f727ef66b1c367717ccc6b60addd74bcfa88815 |
| Corrected calendar | 84dac81bd15f1814891c73d897bf4728fdcdbdd30e2e68c24c7486d49018a125 |
| Phase28A-R amendment canonical JSON | d06ec621922513f9b96dfea6a2a32582b1ae3f272a31d32304fd282daeb642d5 |
| Selection FINAL bhavcopy | e637a4aeb1120ef0336be3dbb61fbb8fa2639916782ac913cb2012d8c8b99967 |

Original Phase27 evidence matches its recorded source/preservation hashes and baseline checkout bytes. Git autocrlf makes some Git LF blobs differ from the original working-tree source bytes; the recorded original source hashes are verified directly. No evidence was normalized or rewritten. Precheck records the historical file snapshot; all recorded hashes still match after testing.

Universe and eligibility:

- Official selection source rows: 2,867; STK/EQ rows and unique valid STK/EQ ISINs: 1,838. Duplicate/invalid ISINs, duplicate source rows, zero or missing selection traded values: 0.
- Eligible: 1,300. Excluded: 538. All 538 lack one or more required history observations; 150 of these also lack one or more required liquidity observations. Exclusion reason counts overlap. Invalid canonical liquidity values: 0; unresolved material identity exclusions: 0.
- History and liquidity observations are matched by ISIN and exact frozen session dates. No imputation, forward fill, special-session substitution, identity splice, sector filter, discretionary override, or additional liquidity floor was applied.
- All 1,300 eligible identities are ranked by descending exact-decimal median official traded value, then ascending ISIN and selection-date symbol. The first 24 are selected; replacement is forbidden. eligibility_audit.json records every candidate, missing dates, counts, reasons, and available median, including excluded candidates with high raw liquidity.

Ordered frozen cohort (official daily traded-value units are INR; exact 60-session medians are not rounded). Every row is STK/EQ with 252 history and 60 liquidity observations:

| Rank | ISIN | Selection symbol | Median 60-session traded value | Stratum |
|---:|---|---|---:|---|
| 1 | INE040A01034 | HDFCBANK | 29875806190.525 | VISIBLE |
| 2 | INE090A01021 | ICICIBANK | 15386197084.05 | VISIBLE |
| 3 | INE002A01018 | RELIANCE | 15067030304.95 | WITHHELD |
| 4 | INE249Z01012 | MAZDOCK | 11829358205.90 | WITHHELD |
| 5 | INE062A01020 | SBIN | 11779712654.775 | VISIBLE |
| 6 | INE009A01021 | INFY | 10959655348.20 | VISIBLE |
| 7 | INE758T01015 | ZOMATO | 10807483030.45 | VISIBLE |
| 8 | INE155A01022 | TATAMOTORS | 10690070189.025 | VISIBLE |
| 9 | INE415G01027 | RVNL | 9887187818.325 | WITHHELD |
| 10 | INE238A01034 | AXISBANK | 9258953592.55 | WITHHELD |
| 11 | INE397D01024 | BHARTIARTL | 8560220879.20 | WITHHELD |
| 12 | INE467B01029 | TCS | 8407240953.225 | WITHHELD |
| 13 | INE669E01016 | IDEA | 7761650372.65 | WITHHELD |
| 14 | INE018A01030 | LT | 7669566373.625 | VISIBLE |
| 15 | INE263A01024 | BEL | 7625934076.825 | VISIBLE |
| 16 | INE237A01028 | KOTAKBANK | 7612137373.25 | WITHHELD |
| 17 | INE213A01029 | ONGC | 6703097692.375 | VISIBLE |
| 18 | INE020B01018 | RECLTD | 6465459663.775 | VISIBLE |
| 19 | INE101A01026 | M&M | 6396577042.375 | VISIBLE |
| 20 | INE296A01024 | BAJFINANCE | 6363232849.975 | VISIBLE |
| 21 | INE205A01025 | VEDL | 6133609505.775 | VISIBLE |
| 22 | INE154A01025 | ITC | 6098864112.325 | VISIBLE |
| 23 | INE733E01010 | NTPC | 5972142870.40 | VISIBLE |
| 24 | INE081A01020 | TATASTEEL | 5861630029.59 | VISIBLE |

The split uses SHA256(UTF-8 protocol_sha256 + colon + ISIN), sorting by digest then ISIN; the first 16 are VISIBLE and last 8 WITHHELD. visible_withheld_split.json records every digest and cohort rank. No manual balancing or future returns were used.

Identity and corporate-action findings:

The historical diagnostic contains 65 multi-symbol ISIN groups and 77 multi-ISIN symbol groups. Among the 1,838 selection candidates, 53 have observed same-ISIN symbol changes and 66 touch symbols used by another ISIN. These diagnostics did not automatically exclude candidates. 0 candidates have unresolved concurrent same-symbol/different-ISIN STK/EQ mappings. Selected candidates with observed symbol changes: none.

Each candidate was reviewed against the dated official FINAL bhavcopy records. Stable ISIN symbol changes retain their identity and observed first/last NORMAL-session symbol history with source hashes. Different ISINs remain separate, including time-disjoint symbol reuse; their observations are never combined to satisfy history. This resolves the reported identity anomalies for the frozen daily-window eligibility test. The audit describes observed trading-session boundaries, not invented legal effective dates.

No material identity or official cash-turnover comparability ambiguity remains in the records for the eligible candidates. This is not a claim that no corporate actions occurred: official cash traded value is used without price adjustment. Later provider-token mapping and post-selection corporate actions require acquisition-time validation under the already frozen cohort, without replacing identities. No current instrument master, future constituents, future identity changes, or later performance were used for selection.

SBIN: rank 5, ISIN INE062A01020, VISIBLE. It remains in the cohort and split/logistics accounting. Prior exposures remain 2025-09-01 through 2026-03-06 and 2026-03-09 through 2026-09-08. Overlapping exposed Stage B/C observations cannot enter pristine inference, bootstrap inputs, pristine participation denominators or gates. Only registry-proven non-overlap may be pristine. No contamination-driven selection change occurred.

Phase28B selection freeze SHA256: 5f676f6fe9e4d1fd752bb8d9d94aecf78f38740817ea1b59cd1581e3d952b7e5

Canonicalization: UTF-8 JSON, lexicographically sorted object keys, comma/colon separators without whitespace, ensure_ascii=false; hash canonical_binding only. The binding contains Phase26 identity, corrected input/calendar/amendment hashes, selection source, eligibility/ranking identities, ordered 24 ISINs, exact split assignments, contamination annotations, and eligibility/identity/ranking audit hashes. This is the binding for later intraday acquisition.

Repeatability: PASS. Reversing all input rows and recomputing produces byte-identical selection products. A second complete offline invocation revalidated all 253 raw files and matched the immutable artifacts and freeze hash. All audit and split bindings were rechecked.

Validation:

- python -m pytest -q: 526 passed; 3 failed. All 27 new Phase28B tests passed. No new unrelated failures.
- The three unchanged known failures concern historical research/phase16_forensics.py bytes: actual 5aea877cb2c0a9bfd93bcba8a04aa6929b6f0fc370a41cc1bae4dcd8321d14e8 versus frozen expected 8e1fd099e98f61caaeed0a1710415f7b89574039c24a92a20c0dec3ebe712d8e. Expected hashes were not changed.
- Failure tests: tests/test_phase17_research.py::test_frozen_production_engine_and_prior_artifacts; tests/test_phase19_preregistration.py::test_unchanged_sources_match_preimplementation_snapshot; tests/test_phase19_preregistration.py::test_phase20a_frozen_spec_and_preservation.
- Python compilation: PASS for all 103 repository Python sources.
- Full pytest output is preserved in pytest_output.txt. verification.json records source/test hashes and checks.

Operations: network requests 0; SmartAPI logins/calls 0; broker requests 0; candle requests 0; new intraday rows 0; research strategy executions 0; research backtests 0; orders/live-feed operations 0; Stage B/C market-data reads 0. No credentials or .env files were read. No strategy development or market-data evaluation occurred; pytest ran the existing synthetic/unit regression suite.

future_intraday_request_manifest.json is PLAN ONLY, executed=false, with zero requests. It binds the fixed cohort, strata, frozen stage boundaries, contamination policy, and later authorization/mapping/storage requirements. No intraday acquisition is authorized or performed.

Final Git status:

```
?? research/metadata/phase28a/
?? research/metadata/phase28ar/
?? research/metadata/phase28b/
?? research/phase28a_daily.py
?? research/phase28ar_daily.py
?? research/phase28b_selection.py
?? tests/test_phase28a_daily.py
?? tests/test_phase28ar_daily.py
?? tests/test_phase28b_selection.py
```

There are no tracked modifications or staged changes. Existing Phase28A/28A-R untracked files remain preserved; new files are limited to the Phase28B selector, tests, and small metadata artifacts. Original Phase13?28A-R evidence and raw bhavcopy bytes remain unchanged. Nothing was staged, committed, or pushed.

Artifacts: cohort_selection_manifest.json, eligibility_audit.json, liquidity_ranking.json, identity_continuity_audit.json, visible_withheld_split.json, future_intraday_request_manifest.json, precheck.json, repeatability_audit.json, verification.json, pytest_output.txt, report.md.

PHASE 28B COMPLETE ? POINT-IN-TIME COHORT DETERMINISTICALLY FROZEN
