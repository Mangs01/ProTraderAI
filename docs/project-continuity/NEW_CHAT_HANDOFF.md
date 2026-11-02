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
4. Identify active phase, blocked work and exact authorized file allowlist.
   PC-1 is administrative; C2.1 is paused, not completed. PC-1 source audit PASS and local checkpoint runtime verification PASS are
   operator-reported. Latest operator-accepted continuity commit is
   55b0fd34b45f2a4b144f8c44d9ce71f101143332. PC-1-SYNC independent audit PASS (H1, H2 and M1 closed) is operator-reported;
   PC-1-FINAL documentation synchronization is in progress, not audited, committed or pushed.
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
Expected branch is main; latest operator-accepted continuity commit is
55b0fd34b45f2a4b144f8c44d9ce71f101143332. Validate checkpoint metadata.
PC-1-SYNC independent audit PASS (H1, H2 and M1 closed) is operator-reported;
PC-1-FINAL documentation synchronization is in progress, not audited, committed
or pushed. GitHub push/remote HEAD verification PASS is operator-reported.
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
explicit authorization and evidence. The fixed Remote-Backup field remains
unverified for parser compatibility; current GitHub evidence is recorded separately.
Native Windows qualification is not established. C2.1 is paused. File-backed
paper trading, durable storage integration and live trading remain BLOCKED.

## Backup evidence and Project Source refresh

The operator verified local and GitHub main HEAD at
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
After PC-1-FINAL independent audit and explicit final acceptance, ChatGPT Project
Source uploads must be refreshed manually; local edits do not update uploads.
Until refreshed, compare uploaded records with the repository and resolve stale
records before acting. This batch authorizes only the three continuity Markdown
updates, no staging, commit, push, checkpoint-script execution or trading work.
