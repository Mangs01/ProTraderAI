# Locked development workflow

These permanent rules govern ProTraderAI X continuity. Records preserve context;
they do not grant new implementation or operational authority.

- Develop offline first. No broker, network or API activity; no paid AI calls.
- Do not access secrets or `.env` files, import `config.settings`, or execute `main.py`.
- No live trading. File-backed paper trading requires future qualification and
  explicit authorization. Never activate durable Journal storage under this workflow.
- Frozen contracts cannot change without a separately approved change process.
  Preserve codec, schema, hash identity, accounting and ABI boundaries.
- Preserve unrelated untracked files, including research evidence. Do not read
  research metadata contents during continuity work.
- Every phase follows: Plan -> Small implementation batch -> Independent read-only
  audit -> Remediation -> Explicit approval -> Selective commit -> Verification.
- No automatic staging, commit or push. No broad `git add`. Obtain explicit
  approval for the exact reviewed files and action; verify the staged filenames
  and staged diff before a separately authorized commit.
- Static tests, mocks and header review do not establish Windows qualification.
- Historical implementation approval never authorizes a new action. Ask before
  implementing, staging, committing or pushing unless that exact action is already
  explicitly authorized in the current task.

Authoritative boundaries include `docs/offline/durable-journal-contract.md`,
`docs/offline/windows-b1-native-inspection.md`,
`paper/offline/native/journal_storage_windows_inspect.h`, and the pinned
`ai_research/contracts/responses-v1/CONTRACT.md`. Read applicable repository
instructions and the relevant contracts before each phase. Historical command
examples and acquisition procedures are not permission to execute them.

On resumption, verify branch, full HEAD, all untracked paths and staged filenames.
Resolve unexpected differences before work. Use an exact file allowlist. Record
evidence sources, limitations, blocked gates and acceptance status honestly.
