# New chat startup guide

Continuity documents are project records, not substitutes for verifying actual
repository state. A newer plan or uncommitted file is not an accepted checkpoint.

1. Read all four files under `docs/project-continuity/`: `LOCKED_WORKFLOW.md`,
   `PROJECT_HISTORY.md`, `CURRENT_CHECKPOINT.md`, and this `NEW_CHAT_HANDOFF.md`.
2. Read applicable repository instructions. Verify actual state with read-only
   `git branch --show-current`, `git rev-parse HEAD`,
   `git status --short --untracked-files=all`, and `git diff --cached --name-only`.
   Optionally run the reviewed `tools/offline/New-ProjectCheckpoint.ps1` locally.
   Resolve unexpected differences before proceeding; do not reset or clean them.
3. Read authoritative frozen contracts: `docs/offline/durable-journal-contract.md`,
   `docs/offline/windows-b1-native-inspection.md`,
   `paper/offline/native/journal_storage_windows_inspect.h`, and, where relevant,
   `ai_research/contracts/responses-v1/CONTRACT.md`. Read relevant committed
   documentation; historical commands are not execution authorization.
4. Identify active phase, blocked work and exact authorized file allowlist.
   PC-1 is administrative; C2.1 is paused, not completed. PC-1 source audit PASS and local checkpoint runtime verification PASS are
   operator-reported. Accepted PC-1 local commit is
   48d5eed5c5954ab843a8f82ebc5c9db4063c8a9a. PC-1-SYNC awaits independent acceptance.
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
Expected branch is main; accepted historical PC-1 local commit is
48d5eed5c5954ab843a8f82ebc5c9db4063c8a9a. Validate checkpoint metadata.
PC-1-SYNC awaits independent acceptance. GitHub backup is unverified.
Identify active phase, blocked gates and evidence of independent acceptance.
PC-1 creation was authorized historically; it grants no new write authority.
C2 planning was PARTIAL; C2.1 remains paused unless separately authorized.
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
explicit authorization and evidence. GitHub backup remains unverified.
Native Windows qualification is not established. C2.1 is paused. File-backed
paper trading, durable storage integration and live trading remain BLOCKED.
