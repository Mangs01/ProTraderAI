# Project history

Evidence: local Git history inspected at `bf928cefb5e2439482971cefd9d317f9eae4d2d6`,
the committed contracts listed below, and the operator's PC-1 continuity brief.
Commit subjects establish landed scope, not independent runtime qualification.
No tests were rerun to reconstruct this history.

| Order | Milestone | Evidence and status |
| --- | --- | --- |
| 1 | Offline AI assistant | `bf8edff`: offline assistant with Responses safety hardening committed; live readiness remains blocked. See `ai_research/README.md` and pinned Responses contract. |
| 2 | TS-1 development: in-memory paper engine | `95b60c1`: isolated offline paper engine committed. TS phase naming follows the operator brief; the commit establishes the engine milestone. |
| 3 | TS-2 development: SQLite journal codec/schema and coordinator | `d8da46a`: codec and schema; `623c5fe`: in-memory atomic paper journal committed. SQLite schema availability is not durable activation. |
| 4 | Replay, recovery and bounded-write continuity | `5d3407c`: historical replay verifier; `a138dd3`: verified in-memory recovery; `89c2f48`: write transaction continuity committed. Memory-only boundary retained. |
| 5 | Durable readiness assessment | Historical D1 assessment referenced by the durable contract; durable readiness blocked. No separate assessment commit or new test result is asserted here. |
| 6 | Frozen durable contract | `589c37f`: TS-2C2-D2a contract committed. Proposed FRESH/RESUME APIs and D2b-D6 gates remain specifications; operational storage unqualified. |
| 7 | Windows lexical validation Batch A | `1016de2`: offline Windows storage path validation committed. Lexical validation does not qualify filesystem identity, ownership or durability. |
| 8 | B1 Python inspection audit failure | Operator brief reports failure. Existing untracked Python inspection and test files are preserved, not accepted or qualified. No audit artifact contents were inspected in PC-1. |
| 9 | Native ABI Option C design | Declaration/design alternative recorded in the C1 native contract; acquisition, loader and qualification remain future work. Option C selection history follows the operator brief. |
| 10 | C1 declaration/documentation | `bf928ce`: native ABI header and design committed. Operator reports independent declaration-level review; no native implementation or DLL qualification follows from that review. |
| 11 | C2 planning | Operator reports verdict **PARTIAL**. C2.1 source implementation paused, not completed; no implementation authorization transfers to a resumed session. |
| 12 | PC-1 continuity foundation | Initial administrative foundation was pending audit when recorded. Subsequently locally committed and accepted at `48d5eed5c5954ab843a8f82ebc5c9db4063c8a9a`. Operator reports PC-1 source audit PASS and local checkpoint runtime verification PASS. GitHub backup unverified. |
| 13 | PC-1-SYNC checkpoint consistency | Explicit accepted-checkpoint metadata and read-only local ancestry classification implemented; pending independent acceptance. No automatic acceptance of descendants; historical acceptance grants no new development authority. |

Primary storage references: `docs/offline/durable-journal-contract.md`,
`docs/offline/windows-b1-native-inspection.md` and
`paper/offline/native/journal_storage_windows_inspect.h`.
Research metadata contents, secrets and `.env` files were excluded from inspection.

PC-1 acceptance evidence is operator-reported, not a new independent audit by this
implementation. GitHub backup is unverified. C2.1 remains paused; native Windows
qualification is not established. File-backed paper trading, durable storage
integration and live trading remain BLOCKED. Locked workflow remains in force.
