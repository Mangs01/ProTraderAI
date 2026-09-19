# Phase 20A ? Strategy I current-bar interface repaired

Precheck: 430 passed, 0 failed, 0 skipped; 91 Python files compiled; git diff --check passed.

Before editing, BUY and SELL synthetic sequences reproduced the defect: deviation at 09:15, reclaim at 09:20, non-reclaim close equal to VWAP at 09:25. A prefix ending 09:25 returned BUY/SELL with the historical event timestamp 09:20.

Root cause: the evaluator processes only unseen rows, not full-history rescanning. Its local signal variable retained the last emitted signal across subsequent rows. The runner consumes that string as the current bar signal without consulting historical event timestamps. This is a state catch-up/current-result interface mismatch.

Only research/phase19_strategy.py and tests/test_phase19_preregistration.py were edited. This report and phase20a_results.json are new. The evaluator now resets its public signal and current_signal_timestamp for each unseen row. Historical events and DONE states remain intact. A non-HOLD return checks that its exposed origin, final prefix timestamp and last event agree, otherwise raises RuntimeError. No runner or engine change was needed: historical signals no longer cross the evaluator boundary as current signals. Missed historical signals are neither executed late nor backfilled.

After repair, both standalone mirrors return HOLD at 09:25, current_signal_timestamp is None, and the historical reclaim remains at 09:20. Sequential-prefix return timestamps exactly match one-pass chronological event timestamps across BUY/SELL and session resets. Regression coverage includes fresh and skipped prefixes, repeated calls, close == VWAP, current-bar timestamps and a deliberately corrupted timestamp that fails loudly. Existing tests retain same-bar prohibition, fail-closed missing values/prior EMA20, one signal per direction/session, session resets and no future dependency. One old test expectation was changed from historical BUY to current HOLD while retaining its single-event assertion.

Expected, before and after strategy_spec SHA256:
`97a972931ee6213fa946869ef1a394ac3606273f6f9c39a9962b7c2ac91c0b62`

Hash gate PASS. Preserved-file hash checks PASS: production, engine, economics, indicators, Phase 18A policy/registry, broker/live sources, Phase 19 preregistration and blocked Phase 20 artifacts are unchanged. Held-out files were never opened or hashed.

Final pytest: 439 passed, 0 failed, 0 skipped. Synthetic standalone evaluations: 2 before and 2 after, plus regression tests. Audited external network attempts: 0. Held-out CSV reads: 0. Held-out metadata reads: 0. Historical Strategy I evaluations: 0. Canonical Phase 20 runs before repair: 0; during repair: 0. No authentication or forbidden API activity.

Ready to restart Phase 20 subject to its integrity gates and single-run lock. First exposure remains intact. No staging, commit, push, clean or unrelated revert.
