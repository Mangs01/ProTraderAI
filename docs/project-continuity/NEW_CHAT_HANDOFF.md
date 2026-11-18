# New chat startup guide

Continuity documents are project records, not substitutes for verifying actual
repository state. A newer plan or uncommitted file is not an accepted checkpoint.

1. Read all four files under `docs/project-continuity/`: `LOCKED_WORKFLOW.md`,
   `PROJECT_HISTORY.md`, `CURRENT_CHECKPOINT.md`, and this `NEW_CHAT_HANDOFF.md`.
2. Read applicable repository instructions. Verify actual state with read-only
   `git branch --show-current`, `git rev-parse HEAD`,
   `git status --short --untracked-files=all`, and `git diff --cached --name-only`.
   Inspect the checkpoint script source and its parser contract; do not run it
   when the known Git LFS fail-closed policy prevents safe execution.
   Resolve unexpected differences before proceeding; do not reset or clean them.
3. Read authoritative frozen contracts: `docs/offline/durable-journal-contract.md`,
   `docs/offline/windows-b1-native-inspection.md`,
   `paper/offline/native/journal_storage_windows_inspect.h`, and, where relevant,
   `ai_research/contracts/responses-v1/CONTRACT.md`. Read relevant committed
   documentation; historical commands are not execution authorization.
4. Identify active phase, blocked work and exact authorized allowlist.
   Historical Accepted-Checkpoint remains PC-1 at
   55b0fd34b45f2a4b144f8c44d9ce71f101143332. PC-1 audit/runtime PASS and
   PC-1-SYNC independent audit PASS are operator-reported historical evidence.
   Latest operator-verified local/GitHub main HEAD is
   afa6c1304c3de28ec0a9862d91899f699a64d5bc (afa6c13).
   C2.1 Batch 1 source-only work is explicitly accepted, committed and pushed.
   Native Windows qualification remains pending; the entire C2.1 is not complete.
   No automatic continuation is authorized; further implementation needs new
   explicit authorization. Operator-provided evidence records subsequent
   PC-1-FINAL completion: independent read-only audit PASS, documentation commit
   and GitHub push completed, local/GitHub main verified at
   b2a1eb506ca5e0c9022d6673fe6b460ee1f2c5fa. This earlier milestone does not
   change historical PC-1 metadata; C2.1 Batch 1 remains the latest documented
   technical foundation. See PROJECT_HISTORY.md for chronological reconciliation.
5. Distinguish historical plans and approvals from current authorization. Ask
   before implementing, staging, committing or pushing; an explicit current task
   may authorize its exact action without another redundant question.
6. Preserve untracked research and inspection work. Do not read research metadata
   contents, secrets or `.env` files. Never import `config.settings` or run `main.py`.
7. Never activate trading or durable storage. No broker/network/API activity or
   paid AI calls. Static checks do not establish Windows qualification.
8. Continue from the latest independently accepted checkpoint supported by
   evidence. If acceptance cannot be established, report the uncertainty and seek
   direction. Do not promote this draft into an accepted checkpoint yourself.

## Copyable opening message

```text
Resume ProTraderAI X at D:\Projects\ProTraderAI in OFFLINE mode.
Read all four docs/project-continuity documents and applicable repository
instructions first. Verify branch, full HEAD, full untracked Git status and staged
filenames read-only, then read the frozen durable and C1 ABI contracts.
Expected branch is main. Historical Accepted-Checkpoint remains PC-1:
55b0fd34b45f2a4b144f8c44d9ce71f101143332.
Latest operator-verified local/GitHub main HEAD is
afa6c1304c3de28ec0a9862d91899f699a64d5bc (afa6c13).
Fresh local Git verification is mandatory before any repository action.
C2.1 Batch 1 source-only work is explicitly accepted, committed and pushed.
Independent source re-audit PASS is operator-reported; H1/M1/M2 FIXED;
15 Python source-only checks PASS; 19 native scenarios NOT compiled or executed.
L1 LOW and I1 INFORMATIONAL remain tracked. Native Windows qualification pending.
PC-1-FINAL subsequently completed per operator evidence; see startup guidance
and PROJECT_HISTORY.md. Historical PC-1 metadata remains unchanged.
No checkpoint promotion follows.
Further C2.1 implementation requires new explicit authorization.
Uploaded Project Sources may lag local repository documentation; reconcile them.
Identify current scope, blocked gates and acceptance evidence before acting.
Do not implement, stage, commit or push without explicit current authorization
and an exact file allowlist. Preserve unrelated untracked files. Do not read
research metadata contents, secrets or .env; do not import config.settings or run
main.py. No network, paid AI, brokers, trading or durable storage activation.
Report verified state and the exact next authorized step before making changes.
```

## Checkpoint reconciliation

Accepted historical checkpoints do not authorize new development. The script
reports AT_ACCEPTED_CHECKPOINT (0 when the workspace baseline also matches),
DESCENDANT_REVIEW_REQUIRED (2), BEHIND_ACCEPTED_CHECKPOINT (1), or DIVERGED (1).
Workspace/path discrepancies return 2; Git inspection failures override review
results with 1. Invalid metadata, wrong/detached branch, missing commit or
incomplete history fail with 1. Never interpret exit 2 as implementation authority
or automatically promote a descendant. Acceptance metadata requires separately
explicit authorization and evidence. The fixed Remote-Backup field remains
unverified for parser compatibility; current GitHub evidence is recorded separately.
Native Windows qualification is not established. Further C2.1 implementation requires new explicit authorization. File-backed
paper trading, durable storage integration and live trading remain BLOCKED.

## Backup evidence and Project Source refresh

Historically, the operator verified local and GitHub main HEAD at
`55b0fd34b45f2a4b144f8c44d9ce71f101143332` for
`https://github.com/Mangs01/ProTraderAI.git`. No network re-verification was
performed in PC-1-FINAL. Continuity acceptance grants no trading authorization.
The private ZIP is `D:\ProTraderAI-Backups\ProTraderAI-20261101-182354-534.zip`
(63.38 MB; 1118 files), with SHA-256
`74C3C9F9CDA9396940E1C49BAB1AC12743AB1169379112BF14EB495A7E34EFFB`.
The matching checksum file has the ZIP path plus `.sha256`. Operator reports
required files PASS, `.env` excluded PASS, ZIP readable PASS and checksum verified.
Complete disaster-recovery restoration was NOT tested. Untracked files are not
included in the GitHub push but are represented in the offline ZIP subject to
the operator-verified inventory; do not infer an independently inspected inventory.

Read all four Project Source continuity documents at every new-chat startup.
Verify fresh Git HEAD/status and staged filenames before repository modifications.
Uploaded Project Sources may lag local repository documentation. Refresh manually
after acceptance; local edits do not update uploads. Reconcile stale records with
fresh local Git before any repository action.
Latest GitHub evidence is operator-reported for
https://github.com/Mangs01/ProTraderAI.git at
afa6c1304c3de28ec0a9862d91899f699a64d5bc. Reported push: fast-forward
b2a1eb5 to afa6c13 using force-capable --force-with-lease; no remote history
rewrite is asserted. No network re-verification occurred in this batch.

Preserve all 11 protected untracked paths listed in CURRENT_CHECKPOINT.md and
the checkpoint script, without reading research metadata contents.
Offline-first restrictions remain: no broker, network/API trading or paid AI calls,
live trading, file-backed paper trading activation or durable Journal storage
activation. No frozen contract/ABI changes, secret access, native Windows
qualification claim, or checkpoint promotion without separate approval.
Documentation acceptance grants no operational authorization. This batch permits
only three continuity Markdown edits; no automatic staging, commit or push,
checkpoint-script execution, tests, native binaries or trading code.
