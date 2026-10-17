"""Standalone, read-only verification of existing in-memory journal history.

The caller must exclusively own the connection throughout each call. No paths,
connections, schema initialization, repairs or coordinator publication occur.
An unanchored result proves internal consistency, not completeness or writer
identity. Fingerprints and attempted identities are independently trusted caller
assertions. Arbitrary Python monkeypatching is outside the trust boundary.
"""
import re
import sqlite3
from dataclasses import dataclass
from decimal import localcontext
from itertools import count

from . import journal_codec as codec, journal_schema as schema
from .config import Config
from .engine import transition
from .models import Account, Risk, State, Candle, Signal, Event


class ReplayError(Exception):
    """Structured failure; code is stable, detail is diagnostic only."""
    def __init__(self, code, detail='', *, version=None, sequence=None):
        self.code, self.version, self.sequence = code, version, sequence
        super().__init__(code + (': ' + detail if detail else ''))


class ReplayValidationError(ReplayError):
    """Invalid arguments or unsupported connection contract."""


class HistoricalCorruption(ReplayError):
    """Stored history is malformed, incompatible or inconsistent with replay."""


class ReplayStorageError(ReplayError):
    """SQLite could not establish a verification result."""


class ReplayCleanupError(ReplayStorageError):
    """The verifier could not establish closure of its own transaction."""


class TransactionContinuityError(ReplayStorageError):
    """The verifier-owned SQLite transaction ended or was replaced."""


def _require(ok, code, *, version=None, sequence=None):
    if not ok:
        raise HistoricalCorruption(code, version=version, sequence=sequence)


def _hash(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _valid(ok, code):
    if not ok:
        raise ReplayValidationError(code)


@dataclass(frozen=True)
class HistoryAnchor:
    version: int
    commit_hash: str | None

    def __post_init__(self):
        _valid(type(self.version) is int and self.version >= 0, 'anchor_version')
        _valid(self.commit_hash is None if self.version == 0 else _hash(self.commit_hash),
               'anchor_hash')


@dataclass(frozen=True)
class RecoverySnapshot:
    state: State
    version: int
    input_digest: str
    event_digest: str
    commit_digest: str | None
    event_count: int

    def __post_init__(self):
        _valid(type(self.state) is State, 'snapshot_state')
        HistoryAnchor(self.version, self.commit_digest)
        _valid(type(self.event_count) is int and self.event_count >= 0, 'snapshot_count')
        _valid(_hash(self.input_digest) and _hash(self.event_digest), 'snapshot_digest')
        try:
            codec.encode(self.state)
        except ValueError as exc:
            raise ReplayValidationError('snapshot_state', str(exc)) from exc
        _valid(len(self.state.processed) == self.version and
               len(self.state.events) == self.event_count, 'snapshot_counts')
        _valid((self.version == 0) == (self.input_digest == codec.empty_digest('input')),
               'snapshot_input_digest')
        _valid((self.event_count == 0) == (self.event_digest == codec.empty_digest('event')),
               'snapshot_event_digest')
        inputs, events = codec.empty_digest('input'), codec.empty_digest('event')
        for count, (candle, signal) in enumerate(self.state.processed, 1):
            inputs = codec.cumulative_digest('input', inputs, codec.input_hash(candle, signal), count=count)
        for event in self.state.events:
            events = codec.cumulative_digest('event', events, codec.event_hash(event), count=event.sequence)
        _valid((inputs, events) == (self.input_digest, self.event_digest), 'snapshot_digests')
        if self.version == 0:
            _valid(codec.encode(self.state) == codec.encode(State(Account(self.state.account.realized_equity), Risk())),
                   'snapshot_genesis')


COMMIT_COLUMNS = ('version,run_id,parent_version,instrument,interval_seconds,'
                  'candle_identity,input_json,input_hash,cumulative_input_hash,'
                  'cumulative_event_hash,state_hash,commit_hash')
EVENT_COLUMNS = 'sequence,commit_version,event_index,event_json,event_hash'
HEAD_COLUMNS = 'singleton,commit_version,state_json,state_hash'


def _commit_shape(row):
    return (type(row) is tuple and len(row) == 12 and
            all(type(row[i]) is int for i in (0, 1, 4)) and
            (row[2] is None or type(row[2]) is int) and
            all(type(row[i]) is str for i in (3, 5)) and type(row[6]) is bytes and
            all(_hash(row[i]) for i in range(7, 12)))


def _event_shape(row):
    return (type(row) is tuple and len(row) == 5 and
            all(type(row[i]) is int for i in (0, 1, 2)) and
            type(row[3]) is bytes and _hash(row[4]))


def _head_shape(row):
    return (type(row) is tuple and len(row) == 4 and
            type(row[0]) is int and type(row[1]) is int and
            type(row[2]) is bytes and _hash(row[3]))


def _canonical(payload, cls):
    value = codec.decode(payload, cls)
    if codec.encode(value) != payload:
        raise ValueError('Noncanonical stored payload')
    return value


@dataclass(frozen=True)
class AttemptedCommit:
    prior_anchor: HistoryAnchor
    commit_row: tuple
    event_rows: tuple
    head_row: tuple

    def __post_init__(self):
        _valid(type(self.prior_anchor) is HistoryAnchor, 'attempt_anchor')
        _valid(_commit_shape(self.commit_row), 'attempt_commit_row')
        _valid(type(self.event_rows) is tuple and all(_event_shape(r) for r in self.event_rows),
               'attempt_event_rows')
        _valid(_head_shape(self.head_row), 'attempt_head_row')
        r, h = self.commit_row, self.head_row
        _valid(r[0] == self.prior_anchor.version + 1 and r[1] == 1 and
               r[2] == (self.prior_anchor.version or None) and r[4] > 0, 'attempt_links')
        _valid(h[:2] == (1, r[0]) and h[3] == r[10], 'attempt_head')
        try:
            pair = _canonical(r[6], tuple)
            _valid(len(pair) == 2 and type(pair[0]) is Candle and type(pair[1]) is Signal,
                   'attempt_input')
            _valid(r[5] == pair[0].timestamp.isoformat(timespec='microseconds') and
                   r[7] == codec.input_hash(*pair), 'attempt_input_identity')
            state = _canonical(h[2], State)
            _valid(len(state.processed) == r[0] and codec.state_hash(state) == r[10], 'attempt_state')
            _valid(codec.encode(state.processed[-1]) == r[6], 'attempt_state_input')
            start = len(state.events) - len(self.event_rows)
            _valid(start >= 0, 'attempt_event_count')
            for index, row in enumerate(self.event_rows):
                event = _canonical(row[3], Event)
                _valid(row[:3] == (start + index + 1, r[0], index) and
                       event.sequence == row[0] and codec.event_hash(event) == row[4] and
                       codec.encode(state.events[start + index]) == row[3], 'attempt_event')
        except ValueError as exc:
            raise ReplayValidationError('attempt_payload', str(exc)) from exc


@dataclass(frozen=True)
class RecoveryResolution:
    outcome: str
    snapshot: RecoverySnapshot

    def __post_init__(self):
        _valid(type(self.outcome) is str and self.outcome in ('COMMITTED', 'NOT_COMMITTED'),
               'resolution_outcome')
        _valid(type(self.snapshot) is RecoverySnapshot, 'resolution_snapshot')


def _advance(config, contract, state, version, inputs, events, parent, row, event_rows):
    v = version + 1
    _require(_commit_shape(row), 'commit_types', version=v)
    _require(row[:3] == (v, 1, version or None), 'commit_links', version=v)
    _require(row[3:5] == (config.instrument, config.interval_seconds), 'input_contract', version=v)
    try:
        pair = _canonical(row[6], tuple)
        _require(len(pair) == 2 and type(pair[0]) is Candle and type(pair[1]) is Signal,
                 'input_shape', version=v)
        candle, signal = pair
        _require(row[5] == candle.timestamp.isoformat(timespec='microseconds'), 'candle_identity', version=v)
        ih = codec.input_hash(candle, signal)
        _require(ih == row[7], 'input_hash', version=v)
        inputs = codec.cumulative_digest('input', inputs, ih, count=v)
        _require(inputs == row[8], 'input_digest', version=v)
        candidate = transition(config, state, candle, signal)
        e = len(state.events)
        _require(len(candidate.processed) == v and
                 codec.encode(candidate.processed) == codec.encode(state.processed + (pair,)),
                 'processed_prefix', version=v)
        _require(codec.encode(candidate.events[:e]) == codec.encode(state.events), 'event_prefix', version=v)
        suffix = candidate.events[e:]
        _require(len(event_rows) == len(suffix), 'event_count', version=v)
        for index, (event, stored) in enumerate(zip(suffix, event_rows)):
            sequence = e + index + 1
            _require(_event_shape(stored), 'event_types', version=v, sequence=sequence)
            _require(stored[:3] == (sequence, v, index) and event.sequence == sequence,
                     'event_order', version=v, sequence=sequence)
            _canonical(stored[3], Event)
            _require(stored[3] == codec.encode(event), 'event_payload', version=v, sequence=sequence)
            eh = codec.event_hash(event)
            _require(stored[4] == eh, 'event_hash', version=v, sequence=sequence)
            events = codec.cumulative_digest('event', events, eh, count=sequence)
        _require(events == row[9], 'event_digest', version=v)
        sh = codec.state_hash(candidate)
        _require(sh == row[10], 'state_hash', version=v)
        ch = codec.commit_hash(parent, v, inputs, events, sh, contract,
                               processed_input_count=v, event_count=len(candidate.events))
        _require(ch == row[11], 'commit_hash', version=v)
        return candidate, v, inputs, events, ch
    except (ValueError, ArithmeticError, TypeError, OverflowError) as exc:
        raise HistoricalCorruption('replay_payload', str(exc), version=v) from exc


def _head(heads, state, version):
    if not version:
        _require(heads == [], 'genesis_head')
        return
    _require(len(heads) == 1 and _head_shape(heads[0]), 'head_shape')
    try:
        _canonical(heads[0][2], State)
    except (ValueError, ArithmeticError) as exc:
        raise HistoricalCorruption('head_payload', str(exc), version=version) from exc
    _require(heads[0] == (1, version, codec.encode(state), codec.state_hash(state)),
             'head_mismatch', version=version)


_SAVEPOINT_IDS = count(1)


class _ReadGuard:
    """A savepoint marker distinguishes our transaction from a replacement.

    An outermost SAVEPOINT starts a deferred SQLite transaction. ROLLBACK TO
    both checks that this savepoint still belongs to the active transaction and
    leaves it in place. Releasing the outermost savepoint ends the transaction.
    """
    def __init__(self, connection):
        self.connection = connection
        self.name = 'protrader_replay_' + str(next(_SAVEPOINT_IDS))
        self.active = False

    def start(self):
        self.connection.execute('SAVEPOINT "' + self.name + '"')
        self.active = True
        if not self.connection.in_transaction:
            self.active = False
            raise TransactionContinuityError('transaction_start')
        self.check()

    def check(self):
        if not self.active or not self.connection.in_transaction:
            self.active = False
            raise TransactionContinuityError('transaction_interrupted')
        try:
            self.connection.execute('ROLLBACK TO SAVEPOINT "' + self.name + '"')
        except sqlite3.Error as exc:
            self.active = False
            raise TransactionContinuityError('transaction_replaced', str(exc)) from exc
        if not self.connection.in_transaction:
            self.active = False
            raise TransactionContinuityError('transaction_interrupted')

    def finish(self):
        self.check()
        try:
            self.connection.execute('RELEASE SAVEPOINT "' + self.name + '"')
        except sqlite3.Error as exc:
            self.active = False
            raise ReplayCleanupError('cleanup', str(exc)) from exc
        self.active = False
        if self.connection.in_transaction:
            raise ReplayCleanupError('cleanup', 'Savepoint was nested in another transaction')

    def cleanup(self):
        if not self.active:
            return
        try:
            self.check()
            self.connection.execute('RELEASE SAVEPOINT "' + self.name + '"')
            self.active = False
            if self.connection.in_transaction:
                raise RuntimeError('Verifier savepoint did not end its transaction')
        except BaseException as exc:
            self.active = False
            raise ReplayCleanupError('cleanup', str(exc)) from exc


def _fetchall(db, guard, sql, parameters=()):
    rows = db.execute(sql, parameters).fetchall()
    guard.check()
    return rows


def _scan(db, config, fingerprint, attempt, guard):
    databases = db.execute('PRAGMA database_list').fetchall()
    guard.check()
    _valid(bool(databases) and databases[0] == (0, 'main', '') and
           all(r == (1, 'temp', '') for r in databases[1:]), 'storage_identity')
    mode = db.execute('PRAGMA main.journal_mode').fetchone()
    guard.check()
    _valid(mode == ('memory',), 'storage_mode')
    temp_store = db.execute('PRAGMA temp_store').fetchone()
    guard.check()
    _valid(temp_store == (2,), 'temporary_storage')
    temp_objects = _fetchall(db, guard, 'SELECT name FROM temp.sqlite_master ORDER BY name')
    _valid(not temp_objects, 'temp_objects')
    try:
        schema.validate_schema(db)
    except ValueError as exc:
        raise HistoricalCorruption('schema', str(exc)) from exc
    guard.check()
    metadata = _fetchall(db, guard, 'SELECT singleton,schema_version,config_json,config_hash,'
                          'input_contract_hash,execution_contract_hash,engine_fingerprint '
                          'FROM main.run_metadata ORDER BY singleton')
    contract = codec.execution_policy_hash(config, fingerprint)
    expected = (1, schema.SCHEMA_VERSION, codec.encode(config), codec.configuration_hash(config),
                codec.input_contract_hash(config), contract, fingerprint)
    _require(len(metadata) == 1 and all(type(a) is type(b) for a, b in zip(metadata[0], expected)),
             'metadata_types')
    try:
        _canonical(metadata[0][2], Config)
    except ValueError as exc:
        raise HistoricalCorruption('metadata_payload', str(exc)) from exc
    _require(metadata == [expected], 'metadata_contract')
    guard.check()
    state = State(Account(config.capital), Risk())
    accumulator = (state, 0, codec.empty_digest('input'), codec.empty_digest('event'), None)
    commits = _fetchall(db, guard, 'SELECT ' + COMMIT_COLUMNS +
                        ' FROM main.candle_commits ORDER BY version')
    all_events = _fetchall(db, guard, 'SELECT ' + EVENT_COLUMNS +
                           ' FROM main.events ORDER BY sequence')
    offset, last_events = 0, []
    prior_seen = attempt is None or attempt.prior_anchor == HistoryAnchor(0, None)
    for row in commits:
        end = offset
        while end < len(all_events) and all_events[end][1] == row[0]:
            end += 1
        last_events = all_events[offset:end]
        accumulator = _advance(config, contract, *accumulator, row, last_events)
        offset = end
        if attempt is not None and accumulator[1] == attempt.prior_anchor.version:
            _require(accumulator[4] == attempt.prior_anchor.commit_hash, 'attempt_prior')
            prior_seen = True
    _require(offset == len(all_events), 'unconsumed_events')
    state, version, inputs, events, parent = accumulator
    heads = _fetchall(db, guard, 'SELECT ' + HEAD_COLUMNS +
                      ' FROM main.state_head ORDER BY singleton')
    _head(heads, state, version)
    guard.check()
    snapshot = RecoverySnapshot(state, version, inputs, events, parent, len(state.events))
    if attempt is None:
        return snapshot
    _require(prior_seen, 'attempt_prior')
    if HistoryAnchor(version, parent) == attempt.prior_anchor:
        candidate = _advance(config, contract, *accumulator, attempt.commit_row, attempt.event_rows)
        _head([attempt.head_row], candidate[0], candidate[1])
        guard.check()
        return RecoveryResolution('NOT_COMMITTED', snapshot)
    _require(version == attempt.commit_row[0] and commits[-1] == attempt.commit_row and
             tuple(last_events) == attempt.event_rows and heads == [attempt.head_row], 'attempt_identity')
    guard.check()
    return RecoveryResolution('COMMITTED', snapshot)


def _run(connection, config, fingerprint, tip, attempt):
    _valid(isinstance(connection, sqlite3.Connection), 'connection')
    _valid(type(config) is Config, 'expected_config')
    _valid(tip is None or type(tip) is HistoryAnchor, 'expected_tip')
    _valid(attempt is None or type(attempt) is AttemptedCommit, 'attempted_commit')
    try:
        codec.encode(config)
        codec.validate_engine_fingerprint(fingerprint)
    except ValueError as exc:
        raise ReplayValidationError('expected_contract', str(exc)) from exc
    guard = None
    try:
        _valid(not connection.in_transaction, 'active_transaction')
        _valid(connection.row_factory is None and connection.text_factory is str, 'connection_factories')
        # SAVEPOINT starts an outermost deferred read transaction. Keeping this
        # marker lets us detect rollback followed by BEGIN, which in_transaction
        # alone cannot distinguish. Releasing it ends exactly our transaction.
        guard = _ReadGuard(connection)
        guard.start()
        with localcontext(codec.DECIMAL_CONTEXT):
            result = _scan(connection, config, fingerprint, attempt, guard)
        if tip is not None:
            _require(HistoryAnchor(result.version, result.commit_digest) == tip, 'expected_tip')
        guard.check()
        guard.finish()
        return result
    except BaseException as exc:
        if guard is not None and guard.active:
            try:
                guard.cleanup()
            except BaseException as cleanup:
                raise ReplayCleanupError('cleanup', str(cleanup)) from exc
        if isinstance(exc, sqlite3.Error):
            raise ReplayStorageError('sqlite', str(exc)) from exc
        raise


def verify_history(connection, *, expected_config, expected_engine_fingerprint, expected_tip):
    """Verify one exclusively owned database view, optionally bound to an exact tip.

    expected_tip=None cannot detect coherent truncation or valid replacement
    history. Default SQLite row/text factories and temp_store=MEMORY are required.
    Failure never returns a partial snapshot. No connection settings are changed.
    """
    return _run(connection, expected_config, expected_engine_fingerprint, expected_tip, None)


def reconcile_attempt(connection, *, expected_config, expected_engine_fingerprint, attempted_commit):
    """Resolve only an exact prior history or exact attempted successor.

    Active transactions are rejected, never resolved. Caller-captured identity
    must precede COMMIT; no input retry or Journal publication occurs here.
    """
    _valid(type(attempted_commit) is AttemptedCommit, 'attempted_commit')
    return _run(connection, expected_config, expected_engine_fingerprint, None, attempted_commit)
