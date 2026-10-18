"""Private-memory atomic journal with anchored in-place recovery.

Journal(config, engine_fingerprint) owns one literal :memory: connection and
closes it on close(). The former supplied-connection API is unsupported.
Private _execute/_commit/_rollback methods are fault-injection seams for tests;
they cannot select or replace storage through the public constructor. Private
attributes and Python module monkeypatching are trusted-code boundaries.
Historical count-preserving corruption detection remains deferred to replay.
"""
import sqlite3
from dataclasses import dataclass
from threading import Lock, local
from contextlib import contextmanager

from . import journal_codec as codec, journal_schema as schema
from .config import Config
from .models import Account, Risk, State, Candle, Signal
from .engine import transition
from .journal_replay import (AttemptedCommit, HistoryAnchor, RecoverySnapshot,
                             RecoveryResolution, verify_history, reconcile_attempt)


class JournalError(Exception):
    """Base coordinator failure."""


class JournalReentrant(JournalError):
    pass


class JournalClosed(JournalError):
    pass


class JournalPoisoned(JournalError):
    pass


class ContractMismatch(JournalError):
    pass


class StaleVersion(JournalError):
    pass


class InputConflict(JournalError):
    pass


class InvalidInput(JournalError):
    pass


class TransactionFailure(JournalError):
    pass


class AmbiguousCommit(JournalPoisoned):
    pass


@dataclass(frozen=True)
class Receipt:
    """Current committed head plus the version accepting this input.

    commit_hash identifies the current head, including on duplicate receipts.
    """
    status: str
    version: int
    input_version: int
    state: State
    commit_hash: str | None


@dataclass(frozen=True)
class _Snapshot:
    state: State
    version: int
    input_digest: str
    event_digest: str
    commit_digest: str | None


def _memory(connection):
    if not isinstance(connection, sqlite3.Connection):
        raise ContractMismatch("Explicit sqlite3.Connection required")
    databases = connection.execute("PRAGMA database_list").fetchall()
    if (not databases or databases[0] != (0, 'main', '')
            or any(row != (1, 'temp', '') for row in databases[1:])):
        raise ContractMismatch("Only an unattached private in-memory database is supported")
    # File databases have a path; temporary databases may also have an empty path,
    # but do not report MEMORY journal mode.
    if connection.execute("PRAGMA main.journal_mode").fetchone() != ('memory',):
        raise ContractMismatch("Only in-memory SQLite is supported")
    if connection.execute("SELECT name FROM temp.sqlite_master").fetchall():
        raise ContractMismatch("Unexpected TEMP objects")


class Journal:
    """Explicit initialization on an empty private in-memory connection only."""

    def __init__(self, config, engine_fingerprint):
        self._lock = Lock()
        self._local = local()
        self._closed = False
        self._poisoned = False
        self._pending_attempt: AttemptedCommit | None = None
        if type(config) is not Config:
            raise ContractMismatch("Validated Config required")
        self._config = config
        try:
            self._metadata = (1, schema.SCHEMA_VERSION, codec.encode(config),
                              codec.configuration_hash(config), codec.input_contract_hash(config),
                              codec.execution_policy_hash(config, engine_fingerprint), engine_fingerprint)
        except ValueError as exc:
            raise ContractMismatch(str(exc)) from exc
        self._snapshot = _Snapshot(State(Account(config.capital), Risk()), 0,
                                   codec.empty_digest('input'), codec.empty_digest('event'), None)
        # Storage identity comes from this literal call, not from PRAGMA inference.
        self._db = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        try:
            self._db.execute("PRAGMA temp_store=MEMORY")
            schema.initialize_schema(self._db)
            self._db.set_authorizer(self._authorize)
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute("INSERT INTO main.run_metadata VALUES (?,?,?,?,?,?,?)", self._metadata)
            try:
                self._commit()
                if self._db.in_transaction:
                    raise TransactionFailure("Metadata COMMIT did not end transaction")
                self._verify(self._snapshot)
            except BaseException as exc:
                self._poisoned = True
                raise AmbiguousCommit("Metadata persistence not established") from exc
        except BaseException:
            self._db.close()
            self._closed = True
            raise

    @staticmethod
    def _authorize(action, arg1, arg2, database, source):
        # No ATTACH, even memory attachments. Storage is fixed for this lifetime.
        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    @contextmanager
    def _operation(self):
        if getattr(self._local, 'active', False):
            raise JournalReentrant("Reentrant coordinator operation")
        with self._lock:
            self._local.active = True
            try:
                yield
            finally:
                self._local.active = False

    def _execute(self, sql, parameters=()):
        return self._db.execute(sql, parameters)

    def _commit(self):
        self._db.commit()

    def _rollback(self):
        self._db.rollback()

    def _rollback_checked(self, old, verified):
        try:
            self._rollback()
            if self._db.in_transaction:
                raise TransactionFailure("ROLLBACK did not end transaction")
            if verified:
                self._verify(old)
        except BaseException as exc:
            self._poisoned = True
            raise JournalPoisoned("Rollback postconditions failed") from exc

    def _verify_commit(self, snapshot, commit_row, event_rows):
        # Reads bypass the injectable write/transaction hooks. This validates the
        # just-written transaction, not historical replay or full corruption.
        self._verify(snapshot)
        actual = self._db.execute("SELECT * FROM main.candle_commits WHERE version=?",
                                  (snapshot.version,)).fetchone()
        if actual != commit_row:
            raise ContractMismatch("Persisted commit identity mismatch")
        actual = self._db.execute("SELECT * FROM main.events WHERE commit_version=? ORDER BY event_index",
                                  (snapshot.version,)).fetchall()
        if actual != event_rows:
            raise ContractMismatch("Persisted event suffix mismatch")

    @property
    def state(self):
        return self._snapshot.state

    @property
    def version(self):
        return self._snapshot.version

    @property
    def poisoned(self):
        return self._poisoned

    @property
    def closed(self):
        return self._closed

    def close(self):
        with self._operation():
            if not self._closed:
                self._db.close()
                self._closed = True

    def _verify(self, old):
        _memory(self._db)
        if self._db.execute("PRAGMA temp_store").fetchone() != (2,):
            raise ContractMismatch("Temporary storage must remain in memory")
        try:
            schema.validate_schema(self._db)
        except ValueError as exc:
            raise ContractMismatch(str(exc)) from exc
        if self._db.execute("SELECT * FROM main.run_metadata").fetchall() != [self._metadata]:
            raise ContractMismatch("Run metadata mismatch")
        heads = self._db.execute("SELECT * FROM main.state_head").fetchall()
        expected = [] if old.version == 0 else [(1, old.version, codec.encode(old.state), codec.state_hash(old.state))]
        if heads != expected:
            raise ContractMismatch("Committed head mismatch")
        count, tip = self._db.execute("SELECT COUNT(*), MAX(version) FROM main.candle_commits").fetchone()
        if count != old.version or tip != (old.version or None):
            raise ContractMismatch("Commit tip mismatch")
        if self._db.execute("SELECT COUNT(*) FROM main.events").fetchone()[0] != len(old.state.events):
            raise ContractMismatch("Event count mismatch")
        if old.version:
            row = self._db.execute("SELECT cumulative_input_hash,cumulative_event_hash,state_hash,commit_hash FROM main.candle_commits WHERE version=?", (old.version,)).fetchone()
            if row != (old.input_digest, old.event_digest, codec.state_hash(old.state), old.commit_digest):
                raise ContractMismatch("Commit digest mismatch")

    def recover(self, *, expected_tip=None):
        """Replay and publish only the retained head or exact attempted outcome.

        An optional HistoryAnchor further constrains the resolved tip. Returns
        the verified RecoverySnapshot; never retries an interrupted input.
        """
        with self._operation():
            if self._closed:
                raise JournalClosed("Coordinator closed")
            try:
                if self._db.in_transaction:
                    raise ContractMismatch("Active caller transaction")
                if expected_tip is not None and type(expected_tip) is not HistoryAnchor:
                    raise ContractMismatch("HistoryAnchor required")
                old = self._snapshot
                options = dict(expected_config=self._config,
                               expected_engine_fingerprint=self._metadata[6])
                attempt = self._pending_attempt
                if attempt is None:
                    anchor = HistoryAnchor(old.version, old.commit_digest)
                    resolved = None
                else:
                    resolution = reconcile_attempt(self._db, attempted_commit=attempt, **options)
                    if (type(resolution) is not RecoveryResolution or
                            resolution.outcome not in ('COMMITTED', 'NOT_COMMITTED')):
                        raise ContractMismatch("Exact recovery resolution required")
                    resolved = resolution.snapshot
                    anchor = (HistoryAnchor(attempt.commit_row[0], attempt.commit_row[11])
                              if resolution.outcome == 'COMMITTED' else attempt.prior_anchor)
                verified = verify_history(self._db, expected_tip=anchor, **options)
                if type(verified) is not RecoverySnapshot:
                    raise ContractMismatch("RecoverySnapshot required")
                # Revalidate all snapshot accounting before conversion/publication.
                checked = RecoverySnapshot(verified.state, verified.version, verified.input_digest,
                                           verified.event_digest, verified.commit_digest,
                                           verified.event_count)
                if (HistoryAnchor(checked.version, checked.commit_digest) != anchor or
                        (expected_tip is not None and expected_tip != anchor) or
                        (resolved is not None and (resolved != checked or
                         codec.encode(resolved.state) != codec.encode(checked.state)))):
                    raise ContractMismatch("Recovery results disagree")
                snapshot = _Snapshot(checked.state, checked.version, checked.input_digest,
                                     checked.event_digest, checked.commit_digest)
                if attempt is None and (snapshot != old or
                        codec.encode(snapshot.state) != codec.encode(old.state)):
                    raise ContractMismatch("Recovery differs from published snapshot")
                if self._db.in_transaction:
                    raise TransactionFailure("Recovery left an active transaction")
                self._snapshot = snapshot
                self._pending_attempt = None
                self._poisoned = False
                return checked
            except BaseException:
                self._poisoned = True
                raise

    def process(self, candle, signal, *, expected_version):
        with self._operation():
            if self._closed:
                raise JournalClosed("Coordinator closed")
            if self._poisoned:
                raise JournalPoisoned("Coordinator poisoned; recovery required")
            db, old = self._db, self._snapshot
            began = False
            committing = False
            verified = False
            try:
                if db.in_transaction:
                    raise ContractMismatch("Active caller transaction")
                self._execute("BEGIN IMMEDIATE")
                began = True
                self._verify(old)
                verified = True
                if type(candle) is not Candle or type(signal) is not Signal:
                    raise InvalidInput("Candle and Signal required")
                if old.state.utc_offset is not None and candle.timestamp.utcoffset() != old.state.utc_offset:
                    raise InputConflict("Timezone offset changed")
                identity = candle.timestamp.isoformat(timespec='microseconds')
                payload = codec.encode((candle, signal))
                ih = codec.input_hash(candle, signal)
                duplicate = self._execute("SELECT version,input_json,input_hash FROM main.candle_commits WHERE instrument=? AND interval_seconds=? AND candle_identity=?",
                                       (self._config.instrument, self._config.interval_seconds, identity)).fetchone()
                if duplicate and duplicate[1:] != (payload, ih):
                    raise InputConflict("Conflicting duplicate candle/signal")
                if type(expected_version) is not int or expected_version != old.version:
                    raise StaleVersion("Expected version does not match committed version")
                if duplicate:
                    receipt = Receipt('ALREADY_PROCESSED', old.version, duplicate[0], old.state, old.commit_digest)
                    self._rollback_checked(old, verified)
                    return receipt
                try:
                    candidate = transition(self._config, old.state, candle, signal)
                except ValueError as exc:
                    raise InvalidInput(str(exc)) from exc
                n, e = len(old.state.processed), len(old.state.events)
                if (candidate.processed != old.state.processed + ((candle, signal),)
                        or candidate.events[:e] != old.state.events):
                    raise ContractMismatch("Transition history prefix changed")
                suffix = candidate.events[e:]
                version = old.version + 1
                if n + 1 != version:
                    raise ContractMismatch("Processed count/version mismatch")
                state_json = codec.encode(candidate)
                sh = codec.state_hash(candidate)
                inputs = codec.cumulative_digest('input', old.input_digest, ih, count=version)
                events = old.event_digest
                rows = []
                for index, event in enumerate(suffix):
                    if event.sequence != e + index + 1:
                        raise ContractMismatch("Event sequence mismatch")
                    eh = codec.event_hash(event)
                    events = codec.cumulative_digest('event', events, eh, count=event.sequence)
                    rows.append((event.sequence, version, index, codec.encode(event), eh))
                ch = codec.commit_hash(old.commit_digest, version, inputs, events, sh, self._metadata[5],
                                       processed_input_count=version, event_count=len(candidate.events))
                snapshot = _Snapshot(candidate, version, inputs, events, ch)
                receipt = Receipt('APPLIED', version, version, candidate, ch)
                commit_row = (version, 1, old.version or None, self._config.instrument,
                              self._config.interval_seconds, identity, payload, ih, inputs, events, sh, ch)
                self._execute("INSERT INTO main.candle_commits VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", commit_row)
                for row in rows:
                    self._execute("INSERT INTO main.events VALUES (?,?,?,?,?)", row)
                if old.version:
                    cursor = self._execute("UPDATE main.state_head SET commit_version=?,state_json=?,state_hash=? WHERE singleton=1 AND commit_version=? AND state_hash=?",
                                        (version, state_json, sh, old.version, codec.state_hash(old.state)))
                else:
                    cursor = self._execute("INSERT INTO main.state_head VALUES (1,?,?,?)", (version, state_json, sh))
                if cursor.rowcount != 1:
                    raise ContractMismatch("State head compare-and-swap failed")
                self._pending_attempt = AttemptedCommit(
                    HistoryAnchor(old.version, old.commit_digest), commit_row,
                    tuple(rows), (1, version, state_json, sh))
                committing = True
                self._commit()
                if db.in_transaction:
                    raise TransactionFailure("COMMIT did not end transaction")
                self._verify_commit(snapshot, commit_row, rows)
                if db.in_transaction:
                    raise TransactionFailure("Persistence verification opened a transaction")
                self._snapshot = snapshot
                self._pending_attempt = None
                return receipt
            except BaseException as exc:
                if committing:
                    self._poisoned = True
                    # Never infer success or retry after a COMMIT exception.
                    try:
                        if db.in_transaction:
                            self._rollback_checked(old, False)
                    except BaseException:
                        pass
                    raise AmbiguousCommit("COMMIT/publication outcome uncertain") from exc
                if began and not self._poisoned:
                    self._rollback_checked(old, verified)
                if isinstance(exc, JournalError):
                    raise
                if isinstance(exc, ValueError):
                    raise InvalidInput(str(exc)) from exc
                if isinstance(exc, sqlite3.Error):
                    raise TransactionFailure(str(exc)) from exc
                raise
