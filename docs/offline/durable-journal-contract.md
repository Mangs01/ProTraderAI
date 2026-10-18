# Durable journal safety contract — TS-2C2-D2a

Status: normative design specification; no durable runtime behavior is implemented by this document.
Baseline: ProTraderAI X, main, 89c2f483f74d481732b1b4a12486a84a8921b060.

MUST, MUST NOT, and REQUIRED define acceptance requirements. Proposed APIs and exception types below are specifications, not claims about the current implementation. Operational use remains prohibited until the release gates pass.

## 1. Supported scope and guarantees

The first durable environment consists of one trusted Journal process, one privately owned SQLite connection, and one database on a qualified local Windows filesystem. Callbacks MUST be transaction-neutral. Application code MUST NOT access or manipulate the private connection, SQL hooks, transaction markers, or snapshot fields. Imports MUST perform no storage I/O. There is no broker, network, credential, strategy-selection, or trading integration in this feature.

Within this boundary the implementation MUST provide atomic candle transactions, conditional durable COMMIT, deterministic full-history restart verification, exact trusted-tip validation, persistent history integrity checks, and publication last. Processing, recovery, and close MUST be serialized; same-thread reentrancy MUST be rejected.

SQLite durability depends on the qualified runtime/VFS, filesystem, operating system, and device honoring locking and synchronization requests. No absolute power-loss guarantee is made for unqualified hardware. Unkeyed hashes detect inconsistency; they do not authenticate inputs or writers.

Excluded guarantees: resistance to malicious privileged writers; arbitrary Python monkeypatching; direct private SQL; marker forgery; transaction replacement within trusted setup/rearming or pending COMMIT/ROLLBACK; cross-system atomic anchor updates; receipt delivery exactly once; automatic retries; automatic migration or repair; network storage; WAL; concurrent Journal owners. Permissions and ownership locks reduce accidental interference but do not turn the database into an authenticated ledger.

## 2. Proposed public API and errors

The existing `Journal(config, engine_fingerprint)` MUST remain memory-only with its current behavior and rejection of storage selection. Its behavior MUST NOT depend on filesystem state.

Proposed class factories:

- `Journal.fresh(path, config, engine_fingerprint)`
- `Journal.resume(path, config, engine_fingerprint, *, expected_tip)`

Both factories return a ready Journal only after all required verification succeeds. No partially initialized coordinator may escape. No caller-supplied connection, SQLite URI, alternate mode, inferred fallback, or storage-option dictionary is accepted. Additional keyword arguments are rejected by the signatures.

Type, value, and lexical path validation MUST finish before target access; filesystem-dependent identity and path-policy checks follow under the ownership protocol: `config` must have exact type Config and pass existing canonical validation; the fingerprint must have exact type str and match `engine-v1:sha256:` followed by exactly 64 lowercase hexadecimal characters; path must have exact type str and satisfy section 7. No environment-variable expansion, home expansion, or current-directory resolution is performed. `expected_tip` must have exact type HistoryAnchor, never None: version is an exact nonnegative int, not bool; hash is None exactly at version zero and otherwise exactly 64 lowercase hexadecimal characters. The caller MUST supply an independently trusted anchor bound to the intended journal. The caller's claimed fingerprint is not independently authenticated by this API.

Proposed error surface, all new names requiring implementation in later phases:

| Condition | Required exception |
| --- | --- |
| Invalid config, fingerprint, path syntax/type, or explicit anchor value | existing ContractMismatch |
| Missing required keyword / unsupported arguments | Python TypeError |
| FRESH target exists | proposed JournalAlreadyExists(JournalError) |
| RESUME target missing | proposed JournalNotFound(JournalError) |
| Ownership unavailable within timeout | proposed JournalOwnershipError(JournalError) |
| Unsupported storage, identity or effective configuration | existing ContractMismatch |
| OS/open/permission/I/O failure before write-outcome uncertainty | proposed JournalStorageError(JournalError) |
| Invalid expected replay arguments | existing ReplayValidationError |
| Historical/schema/metadata/accounting/hash/anchor mismatch during replay | existing HistoricalCorruption |
| Replay storage, transaction continuity or cleanup failure | existing ReplayStorageError or its existing subclasses |
| COMMIT or post-COMMIT verification outcome uncertain | existing AmbiguousCommit |
| Later processing on poisoned/closed instance or reentrancy | existing JournalPoisoned / JournalClosed / JournalReentrant |

Preserve existing process errors, including StaleVersion, InputConflict, InvalidInput, TransactionFailure, and poisoning semantics. Preserve diagnostic exception chaining without exposing credentials. Resource acquisition errors MUST NOT be misreported as historical corruption. Cancellation and other BaseException outcomes MUST still receive safe cleanup and MUST NOT yield a usable coordinator.

A factory failure MUST preserve the reserved database and prohibit application-directed artifact cleanup as defined in section 4, and return no object. SQLite-owned rollback/recovery cleanup remains permitted; byte-for-byte sidecar preservation is not promised. An uncertain initialization COMMIT MUST raise AmbiguousCommit, close the private connection where possible, and require subsequent explicit RESUME with an appropriate trusted anchor; it MUST NOT retry initialization. If closure cannot be established, ownership MUST NOT be voluntarily released while the connection might still be active; terminate or retain a fail-closed resource owner under the D2b cleanup design. This cleanup mechanism is a D2b acceptance requirement.

## 3. SQLite configuration and validation

| Requirement | Scope and timing |
| --- | --- |
| Explicit `BEGIN IMMEDIATE` | Every candle write transaction and atomic initialization transaction; no implicit driver transaction management |
| `isolation_level=None` | Connection-local explicit transaction policy; preserve current supported Python behavior |
| `journal_mode=DELETE` | Effective pager journal policy; establish on newly reserved FRESH storage, inspect/require on RESUME without conversion |
| `synchronous=EXTRA` | Connection-local; explicitly set outside transactions on every open and read back before application writes; native recovery sequencing is qualified under section 5 |
| `foreign_keys=ON` | Connection-local; set outside transactions and verify on every connection |
| `temp_store=MEMORY` | Connection-local; establish before application verification/processing and require thereafter; early native recovery follows section 5; no unexpected TEMP objects |
| UTF-8 | Persistent database encoding; establish before FRESH schema creation, validate only on RESUME |
| application_id / user_version / metadata | Persistent identity; write atomically during FRESH, validate only on RESUME |
| busy timeout | Explicit 5,000 ms SQLite busy timeout, read back; ownership acquisition also has a 5,000 ms budget |
| ATTACH / DETACH | Denied throughout connection lifetime, including memory attachments |
| row/text factories | Default tuple rows and str text as required by current replay |

The timeout is a bounded contention policy, not a promise that every filesystem I/O or SQL operation completes within five seconds. The implementation MUST NOT layer unbounded application retries on either timeout.

Persistent versus connection-local classification matters: journal modes have mode-specific persistence behavior; DELETE must be verified on every open, and a successful readback does not prove how a prior connection was configured. A stored WAL indication must be rejected, and no current mode is proof of historical synchronization settings. Every owned connection MUST be configured and validated. RESUME may change connection-local settings but MUST NOT issue journal-mode conversion, encoding changes, identity changes, DDL, VACUUM, initialization, or migration. Physical writes needed for SQLite's native crash recovery are the limited exception described in section 5.

Reject WAL, MEMORY, OFF, TRUNCATE, PERSIST, unsafe synchronization, attachments, unexpected TEMP objects, unsupported factories, and unsupported database identity. No silent setting fallback. File-backed verification MUST receive a trusted storage contract from the owned connection layer; merely removing existing memory checks is not sufficient. Do not expose a generic supplied-connection route. The initial durable environment requires qualified effective SQLite-level exclusive locking in addition to the application lease, as specified in section 7. Setting or reading back locking_mode=EXCLUSIVE alone proves neither actual lock acquisition nor lifetime ownership.

Schema compatibility is exact: schema version 2, current application ID, metadata version, required tables/triggers and their definitions, foreign-key validity, and integrity_check success. No schema-version bump is authorized here. Storage-policy changes do not change codec/hash identity. If later implementation needs new persistent schema objects, stop and obtain separate schema approval.

## 4. FRESH state machine and initialization crashes

Order: validate arguments; validate protected parent and path policy; acquire target reservation ownership; atomically create the target with exclusive Windows creation semantics; bind the created file identity; open the private SQLite connection without allowing a missing target to be recreated; configure storage; initialize; verify; publish.

An existence check followed by ordinary SQLite create-if-missing is forbidden. FRESH rejects every existing target, including zero-byte files, directories, invalid SQLite files, damaged journals, and incompatible databases. Parent directories MUST already exist and MUST NOT be created by the durable API. Unexplained SQLite sidecars at the target namespace MUST cause refusal before reservation and MUST be checked again under ownership before creation; application code MUST NOT delete existing evidence. A leftover rollback journal is not by itself proof of corruption; SQLite must validate recovery state under the qualified opening procedure. FRESH still refuses unexplained pre-existing sidecars instead of claiming them as its own.

Schema DDL, application_id, user_version, and the single metadata row MUST commit in one explicit transaction. Genesis has no candle commits, no events, no state_head row, State(Account(config.capital), Risk()), version zero, empty cumulative digests, and a null commit digest. The current schema helper's separate schema commit followed by metadata insertion is NOT sufficient for durable FRESH. The future implementation must preserve its existing memory callers while providing atomic durable initialization.

Before returning, verify exact schema, metadata, effective storage settings, SQLite integrity, complete genesis replay, and HistoryAnchor(0, None). Publication and object availability occur last.

| Initialization crash boundary | Permitted result and next action |
| --- | --- |
| Before ownership or exclusive creation | No new database from this operation |
| During exclusive reservation / before SQLite initialization | Target may be absent or an incomplete reserved file; never assume usable genesis |
| During connection configuration, before initialization BEGIN | Empty/incomplete SQLite artifact possible; RESUME rejects absent application identity/metadata |
| During schema/metadata transaction | No committed application initialization; SQLite may leave a recovery journal; RESUME rejects incomplete identity |
| During initialization COMMIT | Either incomplete/uninitialized storage or complete genesis after SQLite recovery |
| After COMMIT, before verification/publication/return | Complete genesis may exist even though FRESH did not return success |
| During failed-factory cleanup | Preserve the reservation/database without manual artifact cleanup; permit SQLite-owned rollback cleanup; close connection before voluntary ownership release |

Application code MUST NOT manually delete, truncate, rename, or repair the database or SQLite recovery artifacts as failure cleanup. In particular, a failed FRESH reservation or incomplete database MUST NOT be automatically deleted and recreated. SQLite-owned rollback-journal creation, deletion, truncation, and recovery cleanup are permitted as part of normal transactional operation, including rollback during connection close; this does not authorize switching away from DELETE journal mode. Artifact preservation does not mean byte-for-byte preservation of transient sidecars after native recovery. For forensic preservation, use a separately designed and qualified acquisition workflow before opening for recovery. FRESH MUST NOT retry creation or manually clean sidecars. Any future operator-directed disposal is outside these APIs. Existing valid genesis must be opened through explicit RESUME, never by rerunning FRESH. A trusted genesis record must be provisioned independently; the universal zero anchor is not journal identity.

## 5. RESUME algorithm

1. Validate all supplied arguments, including the mandatory independently supplied expected_tip, and trusted journal binding.
2. Validate the existing protected local target, acquire lifetime ownership, and verify Windows file identity before database operations.
3. Open existing-only using the D2b-qualified opening/recovery procedure below: never create a missing file, including if it disappears in a race. Refuse unsupported persistent storage settings without conversion.
4. Permit necessary native hot rollback-journal recovery only under the qualified assumptions below while the application lease and path/file protection are held. Establish and verify the required connection-local settings and actual SQLite exclusive lock before historical replay/publication. Do not assume that lock acquisition or inspection can precede all recovery writes.
5. Establish a guarded stable read transaction with the existing bounded continuity semantics. No caller transaction is allowed.
6. Validate UTF-8, application identity, exact schema and metadata, foreign keys and integrity, expected configuration, fingerprint, and derived input/execution contracts.
7. Replay every input from genesis using the existing transition authority. Check contiguous versions and parent links, input identities, canonical bytes, event order/index/sequence, processed counts, all accounting, cumulative digests, state hashes, and commit-chain hashes.
8. Require exact final state_head bytes and hash, then construct and independently revalidate RecoverySnapshot and its counts/digests.
9. Require `HistoryAnchor(snapshot.version, snapshot.commit_digest) == expected_tip`. An anchor is not merely a lower bound or trusted prefix.
10. Successfully finish the verifier-owned read transaction, establish no active transaction remains, and perform final required identity/storage checks under lifetime ownership.
11. Publish the verified snapshot as the last operation that makes the coordinator usable. Retain ownership until close.

No application-level initializer, migration, repair, row synthesis, truncation, reset, recreation, strategy action, or input retry is allowed. SQLite-owned rollback/recovery cleanup remains permitted under section 4. Missing/empty/non-SQLite/incompatible storage fails closed. Necessary SQLite hot-journal recovery is transaction recovery, not permission for application repair. Never manually remove a hot journal. If native recovery cannot establish a valid view, fail without a snapshot. Preserving bytes before native recovery requires a separate qualified forensic procedure, not this API.

A database newer than expected_tip MUST fail even if complete replay succeeds. A crash after a valid COMMIT but before external anchor update can therefore cause an intentional availability failure. It is not proof of corruption. No silent acceptance of a newer tip, downgrade to unanchored verification, or fallback to FRESH is permitted.

### RESUME opening and native recovery qualification (M2)

This is a dependency contract, not a claimed universal PRAGMA execution order. Before database SQL, install the explicit driver transaction policy, bounded busy handler/timeout through a qualified connection API, default factories, and ATTACH/DETACH authorizer as early as the supported API permits. These are connection/driver controls, not persistent database edits. The runtime's connection-open path may itself inspect storage; D2b MUST determine that behavior rather than assume opening is inert. The application lease and protected path/identity binding must already cover opening and recovery.

Request foreign_keys=ON, temp_store=MEMORY, synchronous=EXTRA, and the exclusive locking policy at the earliest qualified points outside application transactions. Foreign-key enforcement is per-connection and must be verified before schema/history checks; it does not validate existing rows or govern SQLite's physical rollback recovery. Read back the busy timeout and all effective settings before replay/publication and before accepting application writes. Synchronization must be verified as EXTRA before any application write transaction. Applying or reading a PRAGMA is not universally guaranteed to be content-free: synchronous, locking, journal-mode, encoding, schema and integrity inspections can require pager/header/schema access depending on the runtime/VFS. D2b must identify the actual first access and recovery-triggering operation.

Persistent encoding, application_id, user_version, schema and metadata MUST be inspected, never changed on RESUME. Inspect journal_mode without assigning a new mode; reject WAL or any unsupported effective mode. A read, schema/PRAGMA inspection, read-transaction start, or lock-acquisition attempt may encounter a hot journal and cause SQLite to obtain recovery locks, restore pages, synchronize storage, and clean recovery artifacts. Such native writes may precede successful setting readback or acquisition of the final retained exclusive lock. They are allowed only under the qualified runtime/VFS/storage assumptions, not as a claim that EXTRA or exclusive locking was already established. Byte-for-byte nonmodification during crash recovery cannot be promised.

D2b MUST document and empirically qualify the precise opening sequence for each supported runtime/VFS, including settings requested/effective at each possible recovery point, actual native recovery synchronization assumptions, lock transitions, and file-identity protection. If necessary recovery precedes verification of some settings, its safety requires explicit evidence for that native recovery path under the named Windows storage assumptions; later readback cannot retroactively prove the settings used. If an adequate recovery path cannot be established, that environment remains unsupported and release-blocked. Fail closed without publication or application writes on unknown ordering, failed recovery, setting mismatch, identity change, or inability to acquire/retain the real exclusive lock. Cleanup follows section 4 and may itself invoke SQLite-owned rollback behavior.

Qualification MUST open a genuine hot rollback journal produced by an interrupted process on a disposable local test database, demonstrate the recovered pre-transaction history and integrity, and exercise recovery interruption, contention and I/O failures. A fabricated filename, ordinary leftover cold journal, or Python exception alone does not establish this gate. These are future D2b tests, not database creation authorized by this documentation task. No immutable=1, nolock mode, or other bypass may suppress required locking/recovery. No mode conversion, initialization, application repair, or migration is permitted.

## 6. Trusted anchor lifecycle

HistoryAnchor retains its existing exact-tip semantics and representation. Anchors MUST come from independent trusted storage, not from the database being verified or a replaceable copy in the same protection boundary. The trusted record MUST bind the anchor to the intended journal identifier, configuration/execution contract and controlled storage identity. Path text alone and HistoryAnchor(0, None) do not establish that identity. The API does not authenticate the provider: selecting and validating the external record remains a required integration responsibility.

The existing schema and hash chain contain no unique per-journal nonce. Two journals with identical configuration, engine and input history can have identical anchors. The trusted provider must define external identity/provisioning and lookup; no database schema change or claim of cryptographically unique run identity is made here.

Freshness must be explicit. A trusted anchor protects only the history it records. An attacker or accidental restore can replace both the database and an inadequately protected anchor with older matching copies. Local proximity does not provide independence; backup and rollback policy must cover both protection domains.

Ordering is conceptually database COMMIT, persistence verification, and external anchor update. These operations are NOT one atomic transaction. Never advance the trusted anchor based only on a candidate or an uncertain COMMIT. There is a window where the database contains H+1 and trusted storage still records H. Receipt/anchor acknowledgement ordering, provider update atomicity, and provider crash recovery are unresolved release blockers. A Journal receipt alone MUST NOT be described as proof that an external anchor was persisted.

Stale-anchor policy: RESUME refuses without publication and preserves evidence. A separate explicitly authorized reconciliation procedure must verify full history and compare it with independently trusted request/receipt/operational evidence before authorizing a new anchor. Internal consistency alone cannot authorize advancement. If such evidence is unavailable, the journal remains unavailable. No automatic re-anchoring, anchor rollback, database rollback, or unanchored operational RESUME is allowed. The provider and reconciliation protocol MUST be specified and qualified before operational release; this document does not pretend they exist.

## 7. Lifetime ownership and Windows paths

Path policy: exact str, absolute drive-qualified local Windows file path, no NUL, no URI syntax, no environment expansion, and no implicit normalization that changes the selected target. Reject UNC/network mappings, drive-relative forms, device/extended-device namespaces, alternate data streams, wildcard syntax, reserved device components, and trailing-dot/space aliases. Case-insensitive aliases must resolve to one ownership identity. The qualification must establish that the drive is genuinely local, not assume it from a drive letter.

For the first release, reject junctions, symbolic links, other reparse points in the target or parent chain, and existing targets with multiple hard links. The protected directory policy MUST prevent untrusted path-component replacement while owned. Use Windows volume/file identity from qualified handle-based checks, not only normalized strings. FRESH needs namespace reservation before a target file identity exists; RESUME needs ownership of the existing identity. The lock mechanism MUST cover both and prevent alias-based concurrent access.

One OS-backed cross-process ownership lease MUST span reservation/open, SQLite recovery, verification, processing, and closure. A second cooperating owner fails within the ownership timeout. Python locks, lock-file existence, stale PID text, and per-transaction SQLite locking alone do not meet this requirement. Lock files, if used, are synchronization artifacts, not databases or trusted anchors; their existence does not prove ownership. A held lease must not be stolen merely because a PID appears stale.

Acquisition order: protected namespace/path validation; ownership reservation; exclusive creation or existing-target binding; file-identity verification; SQLite open; verification; publication. Recheck identity when binding the SQLite connection and before publication; refuse replacement, disappearance, or unsupported aliasing. Maintain the protected-directory/identity guarantees for the whole lifetime. Closing order: stop accepting operations; serialize with active operation; close SQLite without committing new work; release identity handles and ownership only after closure is established. Idempotent close MUST retain the last published state and MUST NOT claim success before resource closure.

Process termination releases kernel-held locks according to the qualified Windows mechanism, but does not authorize deletion of files or imply a clean database. The next owner must perform normal recovery. Permission, sharing-violation and disk-full failures must be surfaced without fallback location, implicit retries, reduced durability, or application-directed artifact cleanup. Normal SQLite-owned rollback/recovery cleanup remains permitted under section 4. Directory permissions must allow SQLite rollback-journal lifecycle operations as well as main-file access. Antivirus and backup interference must fail boundedly where contention controls apply; arbitrary OS I/O latency is not bounded by busy_timeout.

The exact Windows locking/handle/sharing mechanism, Python-to-SQLite file binding, alias-resistant reservation, and cleanup on failed close are UNRESOLVED D2b BLOCKERS. D2b cannot pass by choosing a normalized-path mutex without demonstrating the identity and race requirements. If these cannot be achieved within the selected SQLite integration, revise the design before implementation proceeds.

### External-connection boundary (M1)

Three cases are distinct. A second cooperating Journal process MUST be rejected by the lifetime application lease. A separate ordinary SQLite connection that ignores that lease is not prevented by the lease alone. A malicious/privileged writer, raw-file modification, or deliberate locking bypass is not prevented by either lease or SQLite locks and remains outside the supported threat model.

The smallest supported durable contract requires both the application lease and qualified effective SQLite-level exclusive locking. The owner MUST actually acquire the SQLite exclusive lock before replay/publication and retain its exclusion across idle periods, transaction boundaries, in-process recovery, and until connection closure. Selecting or reading back PRAGMA locking_mode=EXCLUSIVE is not evidence of acquisition. The D2b-qualified acquisition path must not initialize or change application rows on RESUME; native recovery may precede the final retained lock as described in section 5. An already-active external reader/writer may prevent acquisition, in which case opening fails boundedly without a usable Journal. Do not silently fall back to cooperative-only operation.

While that real lock is held, independent ordinary connections using the qualified SQLite/VFS locking protocol must be unable to complete database reads or writes. Merely opening a connection is not necessarily blocked. Before the retained exclusive lock is acquired, the lease provides no exclusion against connections ignoring it; the recovery/locking qualification and protected environment must account for that acquisition window. Raw writes, lock-bypassing VFS/options, same-process private connection manipulation, unsupported aliases/filesystems, and malicious privileged modification are unsupported bypass cases. If exclusion of ordinary SQLite access or the recovery acquisition window cannot be qualified, the environment is release-blocked: undetected historical edits between verification and publication/processing remain a risk, and runtime current-head checks cannot substitute for full replay.

D2b MUST test a real retained lock, a second cooperating Journal owner, and an independent plain SQLite process attempting both reads and writes while the owner is active, including idle and post-transaction periods. Also test external connections existing before owner acquisition and access after closure/process termination. Record SQLite primary/extended BUSY and LOCKED results separately from OS sharing/permission errors, successful connection-open versus SQL access, immediate refusal versus busy-handler timeout, and measured bounded acquisition behavior. BUSY and LOCKED need not both occur or share timeout behavior; no assumption that the busy handler waits/retries every lock error is allowed. Assert no usable owner on failed acquisition and no successful external SQL access during qualified exclusion. Characterize unsupported bypass cases as exclusions, never as proof of safety. D2b acceptance and operational release are blocked until these results and the native recovery sequence are qualified. These mechanisms do not provide malicious tamper resistance.

## 8. Candle crash consistency and acknowledgement

Let H be the last committed head and H+1 the proposed candle transaction. Expectations assume supported storage and the B3-C2 trust boundary; out-of-contract private transaction interference is not covered.

| Crash point | Expected state after SQLite recovery | Restart requirement |
| --- | --- | --- |
| Before BEGIN | H; no changes for this input | Full verification and exact anchor; no inferred input retry |
| During BEGIN/SAVEPOINT setup or rearming | H; no committed candle writes | Native recovery, then full verification; markers are not durable evidence |
| During commit/event/head writes | H | Entire uncommitted suffix rolls back; reject any partial committed history |
| During CAS | H | Head and associated commit/events must remain atomic |
| Before COMMIT, including after AttemptedCommit capture | H | In-memory attempt is lost on termination |
| During COMMIT | H or complete H+1 | Determine actual committed history; never infer from call progress |
| After successful COMMIT | H+1 under qualified durability assumptions | Replay even if acknowledgement was never delivered |
| During post-COMMIT verification / before snapshot publication | H+1 | Reconstruct independently; reject stale exact anchor |
| During snapshot publication or receipt delivery | H+1 | Caller receipt delivery remains unknown |
| During close | Last complete committed head; uncommitted transaction rolls back | Normal restart verification; close is not a commit boundary |

SQLite supplies atomic transaction recovery and configured durability. The application must ensure the transaction contains the correct commit row, ordered full event suffix, and head/CAS update; it must verify deterministic accounting, canonical identity, complete history, and anchors. Atomic wrong data is still wrong data.

A successful APPLIED receipt follows COMMIT, persistence verification, and snapshot publication. An ALREADY_PROCESSED receipt follows verified duplicate identity and checked rollback, with no new COMMIT or version advance. It does not establish caller receipt delivery or external anchor durability. A COMMIT/post-verification exception poisons the live instance without publishing the candidate. There is no automatic retry. An unacknowledged committed input remains committed; explicit resubmission must retain current duplicate/conflict/expected-version semantics rather than being silently rebased.

Shutdown MUST serialize with writes/recovery. It MUST NOT liquidate positions, cancel persisted pending intent, advance a candle, flush an uncommitted candidate by COMMIT, repair uncertainty, or manually delete/truncate/rename recovery artifacts. SQLite-owned rollback and recovery cleanup, including journal deletion or truncation during normal close/rollback, is permitted under section 4; never manually delete a hot rollback journal. A leftover journal alone is not evidence of corruption. Failure to close must be reported and remain fail-closed.

## 9. Compatibility, replay, and in-process recovery

Preserve canonical codec version 2 byte-for-byte, schema version 2 unless separately approved, hash domains and chain identity, event ordering, one input per commit, CAS semantics, exact historical replay, accounting, and engine behavior. Pending intents and open paper positions are reconstructed exactly, not adjusted to wall-clock time. Do not change strategy or execution accounting.

Retain existing AttemptedCommit capture before COMMIT and exact in-process reconciliation of only the prior history or exact attempted successor. The object is process memory: it DOES NOT survive process termination. Restart with committed database history can reconstruct a verified tip but cannot establish the existence of an uncommitted lost request, lost caller acknowledgement, or absent external evidence. Persisting an intent ledger is not authorized; an intent stored inside the candle transaction cannot prove an attempt that rolled back.

Preserve current recover() semantics, including retained-head anchoring, exact attempt reconciliation, independent full re-verification, snapshot revalidation, no automatic retry, poisoning on uncertainty, and publication/poison clearing last. Mandatory expected_tip applies to restart resume(); it does not silently change the existing memory recover() API.

B3-C2 bounded continuity remains unchanged: unique nested write markers are RELEASEd and rearmed without destructive ROLLBACK TO; replay uses its existing guarded read-savepoint behavior. Setup/rearming and pending COMMIT/ROLLBACK are trusted transaction-control boundaries. Continuity markers are evidence, not authentication. Never blindly roll back replacement transactions or retry a failed rollback. Routine current-head checks are not a substitute for full restart replay; count-preserving historical corruption remains detectable through replay.

## 10. Backup, restore, and operational limits

Supported backup requires SQLite's supported backup facility under serialized ownership, or a separately qualified quiescent procedure with proven closed connections and consistent sidecar handling. Live raw main-file copying is NOT supported. Do not expose the private connection to backup callers or introduce a second Journal owner. No backup API is implemented or authorized by this specification.

A backup must be paired with independently protected identity and anchor evidence at its verified tip. Validate the backup's complete replay and anchor before treating it as recoverable. Never discard a hot rollback journal manually or classify a leftover journal as corrupt solely by its presence. SQLite-owned cleanup under the qualified procedure is permitted; byte-for-byte forensic preservation requires acquisition before opening for recovery. No WAL sidecar policy is implied by this DELETE-only contract.

Restore requires an explicit operator-selected offline destination and authorization. Never automatically replace the active database or roll anchors backward to accommodate an older backup. After restore, require normal RESUME verification and exact trusted-anchor equality. A valid older backup is unavailable under a newer exact anchor until an explicitly reviewed recovery policy resolves that discrepancy. Preserve originals and failed evidence; no automatic restoration is supported.

Operational release requires a named Windows version, Python/SQLite version and VFS, supported local filesystem and storage-device class, qualified synchronization and locking behavior, permissions model, and power-loss assumptions. NTFS or any other filesystem is not declared qualified merely by being local. Process termination tests do not demonstrate hardware power-loss durability. Antivirus/sharing violations, journal recovery, disk-full and I/O error behavior need qualification.

The existing full-history State and replay repeatedly process growing input/event collections. A measured maximum supported history/input/event size, startup time, memory use and disk-space policy MUST be established before release. Do not add snapshots, pruning, compaction or altered hash semantics to evade this gate.

## 11. Implementation acceptance gates

All gates require offline operation, unchanged canonical vectors and trading accounting, and preservation of the existing 641-test offline baseline. That count is inherited from D1/user evidence, not a test result established by this documentation task. D2a authorizes no runtime implementation. Later tasks must provide their own file allowlists and write authorization.

### D2b — Connection and ownership foundation

Specify and test the actual Windows ownership/reservation mechanism, handle/file identity binding, alias and replacement-race rejection, existing-only opening, exclusive FRESH reservation, configuration readback, 5,000 ms contention policies, cleanup and failed-close behavior. Require independent-process contention and process-termination tests, forbidden path cases, hard-link/reparse policy, missing/existing/permission failures, and no import-time I/O. Require the M1 independent plain-SQLite read/write tests with actual retained exclusive-lock evidence and BUSY/LOCKED/timeout/bypass characterization. Require the M2 genuine hot-journal opening test, documented runtime/VFS ordering and early-recovery durability assumptions, and fail-closed cases. Require the M3 distinction between prohibited manual artifact cleanup and permitted SQLite-owned rollback/recovery cleanup, including failed FRESH and close paths. No usable durable Journal may be exposed by this gate alone. Unresolved Windows mechanism, ordinary-writer exclusion, or native-recovery sequencing blocks D2b acceptance.

### D3 — Atomic FRESH

Require one atomic schema/identity/metadata transaction, unchanged memory initialization behavior, genesis verification and publication last. Test every initialization matrix boundary, concurrent FRESH, pre-existing empty/damaged targets, unexplained sidecars, disk-full/COMMIT uncertainty, and preserved reservation/database artifacts without manual cleanup; permit qualified SQLite-owned sidecar lifecycle changes. No unsafe helper reuse that commits schema separately. D2b must have passed first.

### D4 — Verified RESUME

Require existing-only opening, no initializer/migration, mandatory exact trusted anchor, qualified hot-journal recovery, full replay and fingerprint/config checks, cleanup and publication last. Test missing/incompatible/corrupt histories, coherent truncation, valid divergent/rehashed histories, stale anchor with a valid newer tip, failed replay cleanup, duplicate receipts and continuation parity, and SQLite-owned cleanup without application repair or immutable/locking bypass. No unanchored fallback. D2b and D3 must have passed first; provider integration may remain unavailable in synthetic tests but remains a release blocker.

### D5 — Crash and restart qualification

Use real independent-process reopen tests across all listed creation, write, COMMIT, publication and shutdown boundaries. Include zero-event and multi-event transactions, CAS miss, lost acknowledgement, contention, antivirus-like sharing failures, permission/disk-full/I/O faults, and hot-journal recovery. Injected Python exceptions and process kills do not substitute for required VFS/storage durability qualification. Assert exact resulting history, anchor behavior, and no partial publication. Crash tests must accompany D3/D4; D5 systematically qualifies the complete matrix.

### D6 — Independent correctness and security audit

Independently review contract compliance, callback trust exclusions, schema/codec/hash compatibility, ownership races and replacement/rollback threats, anchor provisioning/update/reconciliation, backup/restore, durability evidence, and measured history limits. Review source and tests; do not mistake coherent replay for authenticity. Critical findings block release; remediation returns to the owning implementation gate.

### Operational release blockers

The external trusted-anchor provider, independent journal binding/provisioning, anchor update/acknowledgement/reconciliation protocol, exact Windows ownership/file-binding mechanism, supported filesystem/runtime/storage qualification, retained SQLite exclusive-lock exclusion of ordinary external connections, native hot-journal opening/recovery ordering, and durability evidence are unresolved. Maximum history-size qualification and a validated backup/restore procedure are also mandatory release gates. No operational durable use is authorized until these are closed and D2b through D6 pass. Failure of any gate must disable durable entry points without deleting, migrating, downgrading, or restoring existing database artifacts. Memory-only operation remains available under its unchanged contract.
