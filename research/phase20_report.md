# Phase 20 ? blocked before held-out exposure

Precheck: 430 passed, 0 failed, 0 skipped. Compilation: 91 Python files passed. git diff --check passed.

Phase 19 specification hash and recorded held-out path/hashes passed verification. Expected and recalculated specification hash: `97a972931ee6213fa946869ef1a394ac3606273f6f9c39a9962b7c2ac91c0b62`.

## Confirmed source/interface defect

BacktestRunner.run skips strategy calls while a position is open or execution eligibility checks fail. Strategy I processes all unseen bars on its next call and returns a prior reclaim signal even when the current bar does not reclaim. The runner assigns the returned signal to the current bar and enters on its successor.

Synthetic evidence: bar 0 (09:15) deviates; bar 1 (09:20) reclaims; bar 2 (09:25) has close equal to VWAP. Calling on the first-bar prefix returns HOLD. Calling next on all three bars returns BUY with an event timestamp of 09:20. The runner would label it 09:25 and enter at bar 3 instead of physical bar 2. This violates the frozen signal/entry contract. The test used synthetic stdlib row objects matching the strategy's dataframe access interface; no historical prices.

Per the explicit source-defect stop rule, no source was patched and no canonical run was executed. Canonical run count: 0. Run lock not acquired. Held-out files were not opened, parsed or hashed; integrity/session/overlap checks were not reached. All historical performance, funnel, side, exit, half, Muhurat, concentration, cost and trade audit metrics are unavailable. No economic classification is assigned. BLOCKED is a workflow status.

External network attempts and all forbidden API counts: 0. An initial overbroad audit guard blocked local socket.gethostname during pandas import; no external communication occurred. The subsequent synthetic confirmation avoided pandas entirely.

Production, engine, indicators, risk, charges, slippage, sizing, policy, Phase 18A registry, broker/live feed, Phase 19 artifacts and held-out files were not modified. No staging, commit or push. No trades CSV created.

A separately authorized correctness review is required. The held-out dataset remains unexposed by this attempt.
