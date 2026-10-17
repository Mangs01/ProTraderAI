"""Synthetic memory-only replay, corruption and exact-attempt regressions."""
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path
import sqlite3

import pytest

from paper.offline import journal_codec as codec, journal_schema as schema
from paper.offline.journal import Journal, AmbiguousCommit
from paper.offline.models import Account, Risk, State, Signal
from paper.offline.journal_replay import (
    HistoryAnchor, RecoverySnapshot, AttemptedCommit, RecoveryResolution,
    ReplayValidationError, HistoricalCorruption, ReplayStorageError,
    ReplayCleanupError, TransactionContinuityError, verify_history, reconcile_attempt,
    COMMIT_COLUMNS, EVENT_COLUMNS, HEAD_COLUMNS,
)
from test_offline_paper_engine import config, candle, cost_profile

FINGERPRINT = 'engine-v1:sha256:' + 'a' * 64
HOLD = Signal('HOLD')


def tape(side='BUY'):
    return [(candle(0), Signal(side, 2)), (candle(1), HOLD),
            (candle(2, high=105, low=95), Signal('SELL', 2)),
            (candle(3), HOLD), (candle(4, high=105, low=95), HOLD)]


@pytest.fixture
def histories():
    journals = []

    def make(inputs=(), cfg=None):
        journal = Journal(cfg or config(), FINGERPRINT)
        journals.append(journal)
        for c, s in inputs:
            journal.process(c, s, expected_version=journal.version)
        return journal

    yield make
    for journal in journals:
        journal.close()


def verify(journal, tip=None, **kwargs):
    return verify_history(journal._db, expected_config=journal._config,
                          expected_engine_fingerprint=FINGERPRINT,
                          expected_tip=tip, **kwargs)


def rows(db):
    return tuple(db.execute('SELECT * FROM main.' + table + ' ORDER BY 1').fetchall()
                 for table in schema.TABLES)


def corrupt(db, sql, parameters=()):
    """Restore exact schema protections before verification sees the database."""
    foreign_keys = db.execute('PRAGMA foreign_keys').fetchone()[0]
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute('PRAGMA ignore_check_constraints=ON')
    try:
        for name in schema.TRIGGERS:
            db.execute('DROP TRIGGER main.' + name)
        db.execute(sql, parameters)
    finally:
        for definition in schema.TRIGGERS.values():
            db.execute(definition)
        db.execute('PRAGMA ignore_check_constraints=OFF')
        db.execute('PRAGMA foreign_keys=' + str(foreign_keys))
    assert not db.in_transaction


def attempt(journal, prior):
    db, v = journal._db, journal.version
    return AttemptedCommit(prior,
        db.execute('SELECT ' + COMMIT_COLUMNS + ' FROM main.candle_commits WHERE version=?', (v,)).fetchone(),
        tuple(db.execute('SELECT ' + EVENT_COLUMNS + ' FROM main.events WHERE commit_version=? ORDER BY event_index', (v,)).fetchall()),
        db.execute('SELECT ' + HEAD_COLUMNS + ' FROM main.state_head').fetchone())


def reconcile(journal, identity):
    return reconcile_attempt(journal._db, expected_config=journal._config,
        expected_engine_fingerprint=FINGERPRINT, attempted_commit=identity)


def test_genesis_and_explicit_tip(histories):
    j = histories()
    before = rows(j._db)
    result = verify(j, HistoryAnchor(0, None))
    assert result == RecoverySnapshot(State(Account(config().capital), Risk()), 0,
        codec.empty_digest('input'), codec.empty_digest('event'), None, 0)
    assert rows(j._db) == before and not j._db.in_transaction
    with pytest.raises(TypeError):
        verify_history(j._db, expected_config=config(), expected_engine_fingerprint=FINGERPRINT)
    with pytest.raises(FrozenInstanceError):
        result.version = 9


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
@pytest.mark.parametrize('fees', [False, True])
@pytest.mark.parametrize('length', [1, 2, 3, 5])
def test_replayed_trade_states(histories, side, fees, length):
    cfg = config(costs=cost_profile(), slippage_bps=5) if fees else config()
    j = histories(tape(side)[:length], cfg)
    before, old = rows(j._db), j.state
    result = verify(j, HistoryAnchor(j.version, j._snapshot.commit_digest))
    assert codec.encode(result.state) == codec.encode(j.state)
    assert (result.input_digest, result.event_digest, result.commit_digest) == (
        j._snapshot.input_digest, j._snapshot.event_digest, j._snapshot.commit_digest)
    assert result.event_count == len(j.state.events)
    assert j.state is old and rows(j._db) == before and not j.poisoned
    assert not j._db.in_transaction


def test_zero_and_multiple_event_commits(histories):
    holds = histories([(candle(i), HOLD) for i in range(4)])
    assert verify(holds).event_count == 0
    j = histories([(candle(0), Signal('BUY', 2)),
                   (candle(1, high=105, low=95), Signal('SELL', 2))])
    assert [e.kind for e in verify(j).state.events] == ['INTENT', 'ENTRY', 'EXIT', 'INTENT']


@pytest.mark.parametrize('date_change', [False, True])
def test_sparse_and_date_cancel(histories, date_change):
    c = replace(candle(0), timestamp=candle(0).timestamp + timedelta(days=1)) if date_change else candle(3)
    j = histories([(candle(0), Signal('BUY', 2)), (c, HOLD)])
    result = verify(j)
    assert result.state.events[-1].reason == ('DATE_CHANGED' if date_change else 'MISSING_NEXT_CANDLE')
    assert result.state.pending is None


def test_sparse_open_position_and_flat_date_reset(histories):
    j = histories([(candle(0), Signal('BUY', 2)), (candle(1), HOLD), (candle(4), HOLD)])
    assert verify(j).state.position is not None
    flat = histories([(candle(0), HOLD), (replace(candle(0), timestamp=candle(0).timestamp + timedelta(days=1)), HOLD)])
    assert verify(flat).state.risk.day == flat.state.last_timestamp.date().isoformat()


def test_negative_equity_not_clipped(histories):
    cfg = config(capital=1000, risk_fraction=1, daily_loss_limit=1000)
    j = histories([(candle(0), Signal('SELL', 2)), (candle(1), HOLD),
                   (candle(2, open=1000, high=1001, low=999, close=1000), HOLD)], cfg)
    assert verify(j).state.account.realized_equity < 0
    assert verify(j).state.risk.locked


@pytest.mark.parametrize('column,value', [
    ('config_hash', 'b'*64), ('input_contract_hash', 'b'*64),
    ('execution_contract_hash', 'b'*64), ('engine_fingerprint', 'engine-v1:sha256:'+'b'*64),
    ('config_json', b'{}'), ('config_json', codec.encode(config(capital=20000))),
])
def test_metadata_corruption(histories, column, value):
    j = histories(tape())
    corrupt(j._db, 'UPDATE main.run_metadata SET ' + column + '=?', (value,))
    with pytest.raises(HistoricalCorruption):
        verify(j)
    assert not j._db.in_transaction


@pytest.mark.parametrize('which', ['config', 'fingerprint', 'invalid_fingerprint'])
def test_expected_contract(histories, which):
    j = histories()
    cfg = config(capital=20000) if which == 'config' else config()
    fp = 'engine-v1:sha256:'+'b'*64 if which == 'fingerprint' else FINGERPRINT
    if which == 'invalid_fingerprint':
        fp = 'NEXT_OPEN_STOP_FIRST_V1'
    error = ReplayValidationError if which == 'invalid_fingerprint' else HistoricalCorruption
    with pytest.raises(error):
        verify_history(j._db, expected_config=cfg, expected_engine_fingerprint=fp, expected_tip=None)


@pytest.mark.parametrize('column,value', [
    ('input_json', b'{}'), ('input_json', codec.encode((candle(0),))),
    ('input_json', codec.encode((HOLD, candle(0)))),
    ('input_json', codec.encode((candle(0, close=101), Signal('BUY', 2)))),
    ('input_hash', 'b'*64), ('cumulative_input_hash', 'b'*64),
    ('cumulative_event_hash', 'b'*64), ('state_hash', 'b'*64),
    ('commit_hash', 'b'*64), ('candle_identity', 'wrong'),
    ('instrument', 'OTHER'), ('interval_seconds', 600),
    ('input_hash', b'a'*64), ('instrument', b'SYNTHETIC'),
    ('input_json', 'not a blob'), ('interval_seconds', 300.5),
])
def test_commit_corruption(histories, column, value):
    j = histories(tape())
    corrupt(j._db, 'UPDATE main.candle_commits SET ' + column + '=? WHERE version=1', (value,))
    before = rows(j._db)
    with pytest.raises(HistoricalCorruption):
        verify(j)
    assert rows(j._db) == before and not j._db.in_transaction


@pytest.mark.parametrize('column,value', [('event_json', b'\x00'), ('event_hash', 'b'*64),
    ('event_hash', b'a'*64), ('event_json', 'text'), ('event_index', 1.5)])
def test_count_preserving_historical_event_corruption(histories, column, value):
    j = histories(tape())
    count = len(j.state.events)
    corrupt(j._db, 'UPDATE main.events SET ' + column + '=? WHERE sequence=1', (value,))
    assert j._db.execute('SELECT COUNT(*) FROM main.events').fetchone() == (count,)
    with pytest.raises(HistoricalCorruption):
        verify(j)


def test_validly_rehashed_fabricated_event(histories):
    j = histories(tape())
    fake = replace(j.state.events[0], reason='FABRICATED')
    corrupt(j._db, 'UPDATE main.events SET event_json=?,event_hash=? WHERE sequence=1',
            (codec.encode(fake), codec.event_hash(fake)))
    with pytest.raises(HistoricalCorruption, match='event_payload'):
        verify(j)


@pytest.mark.parametrize('sql', [
    'DELETE FROM main.events WHERE sequence=1',
    'UPDATE main.events SET commit_version=5,event_index=99 WHERE sequence=1',
    'UPDATE main.events SET event_index=99 WHERE sequence=1',
    'UPDATE main.events SET sequence=99 WHERE sequence=1',
    'INSERT INTO main.events SELECT 99,5,99,event_json,event_hash FROM main.events WHERE sequence=1',
    'UPDATE main.events SET commit_version=999 WHERE sequence=1',
])
def test_missing_extra_reassigned_and_reordered_events(histories, sql):
    j = histories(tape())
    corrupt(j._db, sql)
    with pytest.raises(HistoricalCorruption):
        verify(j)


@pytest.mark.parametrize('location', ['metadata', 'input', 'event', 'head'])
def test_noncanonical_payloads(histories, location):
    j = histories(tape())
    table, key, column = {
        'metadata': ('run_metadata', 'singleton', 'config_json'),
        'input': ('candle_commits', 'version', 'input_json'),
        'event': ('events', 'sequence', 'event_json'),
        'head': ('state_head', 'singleton', 'state_json'),
    }[location]
    payload = j._db.execute('SELECT '+column+' FROM main.'+table+' WHERE '+key+'=1').fetchone()[0]
    corrupt(j._db, 'UPDATE main.'+table+' SET '+column+'=? WHERE '+key+'=1', (b' '+payload,))
    with pytest.raises(HistoricalCorruption):
        verify(j)


@pytest.mark.parametrize('case', ['missing', 'stale', 'hash', 'payload', 'fabricated', 'type'])
def test_head_corruption(histories, case):
    j = histories(tape())
    if case == 'missing':
        j._db.execute('DELETE FROM main.state_head')
    elif case == 'stale':
        j._db.execute('UPDATE main.state_head SET commit_version=1')
    elif case == 'hash':
        j._db.execute("UPDATE main.state_head SET state_hash=?", ('b'*64,))
    elif case == 'type':
        j._db.execute('UPDATE main.state_head SET state_json=?', ('text',))
    else:
        fake = replace(j.state, account=replace(j.state.account,
                       realized_equity=j.state.account.realized_equity + 100))
        payload = b'{}' if case == 'payload' else codec.encode(fake)
        j._db.execute('UPDATE main.state_head SET state_json=?,state_hash=?',
                      (payload, codec.state_hash(fake)))
    with pytest.raises(HistoricalCorruption):
        verify(j)


def test_fully_rehashed_fabricated_accounting(histories):
    j = histories([(candle(0), HOLD)])
    fake = replace(j.state, account=replace(j.state.account, realized_equity=Decimal('99999')))
    row = list(j._db.execute('SELECT '+COMMIT_COLUMNS+' FROM main.candle_commits').fetchone())
    row[10] = codec.state_hash(fake)
    row[11] = codec.commit_hash(None, 1, row[8], row[9], row[10],
        codec.execution_policy_hash(config(), FINGERPRINT), processed_input_count=1, event_count=0)
    corrupt(j._db, 'UPDATE main.candle_commits SET state_hash=?,commit_hash=?', tuple(row[10:]))
    j._db.execute('UPDATE main.state_head SET state_json=?,state_hash=?', (codec.encode(fake), row[10]))
    with pytest.raises(HistoricalCorruption, match='state_hash'):
        verify(j)


def test_coherent_truncation_requires_trusted_tip(histories):
    j = histories([(candle(i), HOLD) for i in range(3)])
    trusted = HistoryAnchor(j.version, j._snapshot.commit_digest)
    short = histories([(candle(0), HOLD)])
    head = short._db.execute('SELECT '+HEAD_COLUMNS+' FROM main.state_head').fetchone()
    j._db.execute('UPDATE main.state_head SET commit_version=?,state_json=?,state_hash=?', head[1:])
    corrupt(j._db, 'DELETE FROM main.candle_commits WHERE version>1')
    assert verify(j).version == 1  # Internal consistency is deliberately insufficient.
    with pytest.raises(HistoricalCorruption, match='expected_tip'):
        verify(j, trusted)


def test_incoherent_truncation_and_version_gap(histories):
    j = histories([(candle(i), HOLD) for i in range(3)])
    j._db.execute('PRAGMA foreign_keys=OFF')
    corrupt(j._db, 'DELETE FROM main.candle_commits WHERE version=2')
    j._db.execute('PRAGMA foreign_keys=ON')
    with pytest.raises(HistoricalCorruption):
        verify(j)


def test_duplicate_identity_and_conflicting_timestamp(histories):
    j = histories([(candle(i), HOLD) for i in range(2)])
    # Different spelling avoids SQL uniqueness; replay must still reject the duplicate.
    corrupt(j._db, 'UPDATE main.candle_commits SET input_json=?,input_hash=?,candle_identity=? WHERE version=2',
            (codec.encode((candle(0), HOLD)), codec.input_hash(candle(0), HOLD), 'other'))
    with pytest.raises(HistoricalCorruption):
        verify(j)


@pytest.mark.parametrize('prior_length', [0, 1, 2])
@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_exact_attempt_reconciliation(histories, prior_length, side):
    inputs = tape(side)
    prior = histories(inputs[:prior_length])
    applied = histories(inputs[:prior_length+1])
    anchor = HistoryAnchor(prior.version, prior._snapshot.commit_digest)
    identity = attempt(applied, anchor)
    before = rows(prior._db), rows(applied._db)
    no = reconcile(prior, identity)
    yes = reconcile(applied, identity)
    assert no.outcome == 'NOT_COMMITTED' and no.snapshot == verify(prior)
    assert yes.outcome == 'COMMITTED' and yes.snapshot == verify(applied)
    assert before == (rows(prior._db), rows(applied._db))
    with pytest.raises(FrozenInstanceError):
        identity.head_row = ()


def test_zero_event_attempt(histories):
    prior, applied = histories(), histories([(candle(0), HOLD)])
    identity = attempt(applied, HistoryAnchor(0, None))
    assert identity.event_rows == ()
    assert reconcile(prior, identity).outcome == 'NOT_COMMITTED'
    assert reconcile(applied, identity).outcome == 'COMMITTED'


@pytest.mark.parametrize('case', ['different_input', 'later_tip', 'different_prior'])
def test_divergent_attempts(histories, case):
    prior = histories(tape()[:1])
    applied = histories(tape()[:2])
    identity = attempt(applied, HistoryAnchor(prior.version, prior._snapshot.commit_digest))
    if case == 'different_input':
        target = histories([(candle(0), Signal('BUY', 2)), (candle(1, close=101), HOLD)])
    elif case == 'later_tip':
        target = histories(tape()[:3])
    else:
        target = histories([(candle(0), HOLD)])
    with pytest.raises(HistoricalCorruption):
        reconcile(target, identity)


def test_unapplied_attempt_must_itself_replay(histories):
    prior = histories([(candle(0), HOLD)])
    applied = histories([(candle(0), HOLD), (candle(1), HOLD)])
    identity = attempt(applied, HistoryAnchor(prior.version, prior._snapshot.commit_digest))
    row = list(identity.commit_row)
    row[8] = 'b'*64
    bad = replace(identity, commit_row=tuple(row))
    with pytest.raises(HistoricalCorruption, match='input_digest'):
        reconcile(prior, bad)


@pytest.mark.parametrize('version,digest', [(True, None), (-1, None), (0, 'a'*64), (1, None), (1, 'A'*64)])
def test_anchor_validation(version, digest):
    with pytest.raises(ReplayValidationError):
        HistoryAnchor(version, digest)


@pytest.mark.parametrize('case', ['rows_list', 'head_list', 'wrong_anchor', 'missing_event', 'wrong_head'])
def test_attempt_record_validation(histories, case):
    applied = histories(tape()[:1])
    identity = attempt(applied, HistoryAnchor(0, None))
    values = {
        'rows_list': {'event_rows': list(identity.event_rows)},
        'head_list': {'head_row': list(identity.head_row)},
        'wrong_anchor': {'prior_anchor': HistoryAnchor(1, 'a'*64)},
        'missing_event': {'event_rows': ((1, 1, 0, b'{}', 'a'*64),)},
        'wrong_head': {'head_row': (1, 2, identity.head_row[2], identity.head_row[3])},
    }[case]
    with pytest.raises(ReplayValidationError):
        replace(identity, **values)


def test_snapshot_and_resolution_validation(histories):
    snapshot = verify(histories())
    for changes in ({'version': True}, {'event_count': True}, {'input_digest': 'a'*64},
                    {'event_digest': 'a'*64}, {'state': ()}):
        with pytest.raises(ReplayValidationError):
            replace(snapshot, **changes)
    with pytest.raises(ReplayValidationError):
        RecoveryResolution('MAYBE', snapshot)
    with pytest.raises(ReplayValidationError):
        RecoveryResolution('COMMITTED', None)


@pytest.mark.parametrize('operation', ['verify', 'reconcile'])
def test_active_caller_transaction_preserved(histories, operation):
    j, applied = histories(), histories([(candle(0), HOLD)])
    identity = attempt(applied, HistoryAnchor(0, None))
    j._db.execute('BEGIN')
    j._db.execute('CREATE TEMP TABLE caller_state (v)')
    j._db.execute('INSERT INTO caller_state VALUES (42)')
    try:
        with pytest.raises(ReplayValidationError, match='active_transaction'):
            verify(j) if operation == 'verify' else reconcile(j, identity)
        assert j._db.in_transaction
        assert j._db.execute('SELECT v FROM caller_state').fetchall() == [(42,)]
    finally:
        j._db.rollback()


class FaultConnection(sqlite3.Connection):
    fault = None

    def execute(self, sql, parameters=()):
        if self.fault == 'read' and 'FROM main.candle_commits' in sql:
            raise sqlite3.OperationalError('injected read failure')
        if self.fault == 'cleanup_raise' and sql.startswith('RELEASE SAVEPOINT'):
            raise sqlite3.OperationalError('injected cleanup failure')
        if self.fault == 'cleanup_noop' and sql.startswith('RELEASE SAVEPOINT'):
            class Noop:
                pass
            return Noop()
        if self.fault == 'file' and sql == 'PRAGMA database_list':
            class Result:
                def fetchall(self):
                    return [(0, 'main', 'synthetic-file-path')]
            return Result()
        if self.fault == 'integrity' and sql == 'PRAGMA integrity_check':
            class Result:
                def fetchall(self):
                    return [('synthetic integrity failure',)]
            return Result()
        return super().execute(sql, parameters)

    def rollback(self):
        if self.fault == 'cleanup_raise':
            raise sqlite3.OperationalError('injected cleanup failure')
        if self.fault == 'cleanup_noop':
            return
        return super().rollback()


@pytest.mark.parametrize('fault,error', [('read', ReplayStorageError),
    ('cleanup_raise', ReplayCleanupError), ('cleanup_noop', ReplayCleanupError),
    ('file', ReplayValidationError), ('integrity', HistoricalCorruption)])
def test_storage_reads_and_cleanup(histories, fault, error):
    j = histories(tape())
    db = sqlite3.connect(':memory:', factory=FaultConnection, isolation_level=None)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA temp_store=MEMORY')
        j._db.backup(db)
        before = rows(db)
        db.fault = fault
        with pytest.raises(error):
            verify_history(db, expected_config=config(), expected_engine_fingerprint=FINGERPRINT, expected_tip=None)
        if fault in ('cleanup_raise', 'cleanup_noop'):
            assert db.in_transaction  # Failed cleanup is reported; caller owns resolution.
        else:
            assert not db.in_transaction
        db.fault = None
        db.rollback()
        assert rows(db) == before
    finally:
        db.fault = None
        db.close()


def test_attachments_temp_and_foreign_keys(histories):
    j = histories()
    # A separate memory-only connection can attach; Journal's own authorizer forbids it.
    db = sqlite3.connect(':memory:', isolation_level=None)
    try:
        db.execute('PRAGMA temp_store=MEMORY')
        db.execute('PRAGMA foreign_keys=ON')
        j._db.backup(db)
        db.execute("ATTACH DATABASE ':memory:' AS extra")
        with pytest.raises(ReplayValidationError, match='storage_identity'):
            verify_history(db, expected_config=config(), expected_engine_fingerprint=FINGERPRINT, expected_tip=None)
        db.execute('DETACH DATABASE extra')
        db.execute('CREATE TEMP TABLE shadow (x)')
        with pytest.raises(ReplayValidationError, match='temp_objects'):
            verify_history(db, expected_config=config(), expected_engine_fingerprint=FINGERPRINT, expected_tip=None)
        db.execute('DROP TABLE temp.shadow')
        db.execute('PRAGMA foreign_keys=OFF')
        with pytest.raises(HistoricalCorruption, match='schema'):
            verify_history(db, expected_config=config(), expected_engine_fingerprint=FINGERPRINT, expected_tip=None)
        assert not db.in_transaction
    finally:
        db.close()


@pytest.mark.parametrize('value', [None, ':memory:', 'forbidden.sqlite', 1])
def test_reject_nonconnections(value):
    with pytest.raises(ReplayValidationError, match='connection'):
        verify_history(value, expected_config=config(), expected_engine_fingerprint=FINGERPRINT, expected_tip=None)


def test_closed_connection(histories):
    j = histories()
    j.close()
    with pytest.raises(ReplayStorageError):
        verify(j)


def test_determinism_hostile_context_and_read_only_trace(histories):
    j = histories(tape(), config(costs=cost_profile(), slippage_bps=5))
    expected = verify(j)
    statements = []
    j._db.set_trace_callback(statements.append)
    before, changes = rows(j._db), j._db.total_changes
    try:
        with localcontext() as ctx:
            ctx.prec, ctx.Emax, ctx.Emin = 2, 2, -2
            ctx.traps[Inexact] = ctx.traps[Rounded] = True
            assert verify(j) == expected
            assert verify(j) == expected
        assert rows(j._db) == before and j._db.total_changes == changes
        assert not any(s.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'COMMIT')) for s in statements)
        assert sum(s.startswith('SAVEPOINT \"protrader_replay_') for s in statements) == 2
        assert sum(s.startswith('RELEASE SAVEPOINT \"protrader_replay_') for s in statements) == 2
        assert sum(s.startswith('ROLLBACK TO SAVEPOINT \"protrader_replay_') for s in statements) >= 10
    finally:
        j._db.set_trace_callback(None)


def test_import_and_verification_isolation():
    root = str(Path(__file__).resolve().parents[1])
    script = r'''
import sys, builtins, io, os, socket, sqlite3, dataclasses, threading, typing, json, hashlib, re
from datetime import datetime, timezone
from decimal import Decimal
sys.path.insert(0, ROOT)
from paper.offline.journal import Journal
from paper.offline.config import Config, Costs
from paper.offline.models import Candle, Signal
cfg = Config('PAPER', Decimal('10000'), Decimal('.01'), 5, Decimal('500'), Decimal('10000'), Decimal('0'), Costs('PAPER_COST_V1', *([Decimal('0')]*9)), 'SYNTHETIC', 300, 'NEXT_OPEN_STOP_FIRST_V1')
j = Journal(cfg, 'engine-v1:sha256:'+'a'*64)
j.process(Candle(datetime(2026,1,5,tzinfo=timezone.utc),100,101,99,100,1), Signal('HOLD'), expected_version=0)
real_import = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name.split('.')[0] in {'main','config','dotenv','broker','SmartApi','backtest','research','requests','urllib'}:
        raise AssertionError(name)
    return real_import(name, globals, locals, fromlist, level)
def deny(*a, **k): raise AssertionError('forbidden I/O or credentials')
builtins.__import__ = guarded
builtins.open = io.open = os.getenv = socket.socket = sqlite3.connect = deny
class ForbiddenEnvironment(dict):
    def __getitem__(self, key): return deny()
    def get(self, *a): return deny()
    def __iter__(self): return deny()
os.environ = ForbiddenEnvironment()
from paper.offline.journal_replay import verify_history
result = verify_history(j._db, expected_config=cfg, expected_engine_fingerprint='engine-v1:sha256:'+'a'*64, expected_tip=None)
assert result.version == 1 and not j._db.in_transaction
j.close()
'''.replace('ROOT', repr(root))
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.parametrize('table,sql', [
    ('metadata', 'DELETE FROM main.run_metadata'),
    ('parent', 'UPDATE main.candle_commits SET parent_version=99 WHERE version=3'),
    ('run', 'UPDATE main.candle_commits SET run_id=2 WHERE version=1'),
    ('genesis', 'UPDATE main.candle_commits SET parent_version=99 WHERE version=1'),
])
def test_missing_metadata_and_broken_commit_links(histories, table, sql):
    j = histories([(candle(i), HOLD) for i in range(3)])
    corrupt(j._db, sql)
    with pytest.raises(HistoricalCorruption):
        verify(j)


@pytest.mark.parametrize('case', ['trigger', 'extra_table', 'application', 'version', 'temp_store'])
def test_incompatible_schema_and_storage_settings(histories, case):
    j = histories()
    sql = {
        'trigger': 'DROP TRIGGER main.events_order',
        'extra_table': 'CREATE TABLE main.unexpected (v)',
        'application': 'PRAGMA main.application_id=42',
        'version': 'PRAGMA main.user_version=1',
        'temp_store': 'PRAGMA temp_store=FILE',
    }[case]
    j._db.execute(sql)
    with pytest.raises((HistoricalCorruption, ReplayValidationError)):
        verify(j)
    assert not j._db.in_transaction


def test_interval_grid_and_offset_replayed_after_rehash(histories):
    j = histories([(candle(0), HOLD), (candle(1), HOLD)])
    for bad_candle in (
        replace(candle(1), timestamp=candle(1).timestamp + timedelta(seconds=1)),
        replace(candle(1), timestamp=candle(1).timestamp - timedelta(days=1)),
        replace(candle(1), timestamp=candle(1).timestamp.astimezone(timezone.utc)),
    ):
        ih = codec.input_hash(bad_candle, HOLD)
        cumulative = codec.cumulative_digest('input',
            codec.cumulative_digest('input', None, codec.input_hash(candle(0), HOLD), count=1), ih, count=2)
        corrupt(j._db, 'UPDATE main.candle_commits SET input_json=?,input_hash=?,cumulative_input_hash=?,candle_identity=? WHERE version=2',
                (codec.encode((bad_candle, HOLD)), ih, cumulative,
                 bad_candle.timestamp.isoformat(timespec='microseconds')))
        with pytest.raises(HistoricalCorruption, match='replay_payload'):
            verify(j)


def test_exact_duplicate_identity_blocked_by_schema(histories):
    j = histories([(candle(0), HOLD)])
    with pytest.raises(sqlite3.IntegrityError):
        j._db.execute('INSERT INTO main.candle_commits SELECT 2,1,1,instrument,interval_seconds,candle_identity,input_json,input_hash,cumulative_input_hash,cumulative_event_hash,state_hash,? FROM main.candle_commits', ('b'*64,))
    assert verify(j).version == 1


def test_reconciliation_requires_exact_prior_hash(histories):
    applied = histories(tape()[:2])
    identity = attempt(applied, HistoryAnchor(1, 'b'*64))
    with pytest.raises(HistoricalCorruption, match='attempt_prior'):
        reconcile(applied, identity)


def test_reconciliation_rejects_attempt_payload_changes(histories):
    applied = histories(tape()[:2])
    prior = histories(tape()[:1])
    identity = attempt(applied, HistoryAnchor(1, prior._snapshot.commit_digest))
    row = list(identity.commit_row)
    row[11] = 'b'*64
    bad = replace(identity, commit_row=tuple(row))
    for target in (prior, applied):
        with pytest.raises(HistoricalCorruption):
            reconcile(target, bad)


@pytest.mark.parametrize('factory', ['row', 'text'])
def test_custom_factories_rejected_without_modification(histories, factory):
    j = histories()
    if factory == 'row':
        j._db.row_factory = sqlite3.Row
    else:
        j._db.text_factory = bytes
    with pytest.raises(ReplayValidationError, match='connection_factories'):
        verify(j)
    assert not j._db.in_transaction
    assert j._db.row_factory is (sqlite3.Row if factory == 'row' else None)
    assert j._db.text_factory is (bytes if factory == 'text' else str)


def test_invalid_expected_tip_and_config(histories):
    j = histories()
    with pytest.raises(ReplayValidationError, match='expected_tip'):
        verify(j, (0, None))
    with pytest.raises(ReplayValidationError, match='expected_config'):
        verify_history(j._db, expected_config={}, expected_engine_fingerprint=FINGERPRINT, expected_tip=None)
    with pytest.raises(ReplayValidationError, match='attempted_commit'):
        reconcile(j, None)


@pytest.mark.parametrize('fault', ['before', 'after', 'noop', 'silent_rollback'])
@pytest.mark.parametrize('existing', [False, True])
def test_attempt_captured_before_ambiguous_commit(histories, fault, existing):
    j = histories([(candle(0), HOLD)] if existing else [])
    old, version = j.state, j.version
    prior = HistoryAnchor(version, j._snapshot.commit_digest)
    captured = []

    def uncertain_commit():
        db = j._db
        assert db.in_transaction and j.state is old and j.version == version
        captured.append(AttemptedCommit(prior,
            db.execute('SELECT '+COMMIT_COLUMNS+' FROM main.candle_commits WHERE version=?', (version+1,)).fetchone(),
            tuple(db.execute('SELECT '+EVENT_COLUMNS+' FROM main.events WHERE commit_version=? ORDER BY event_index', (version+1,)).fetchall()),
            db.execute('SELECT '+HEAD_COLUMNS+' FROM main.state_head').fetchone()))
        if fault == 'before':
            raise sqlite3.OperationalError('before COMMIT')
        if fault == 'noop':
            return
        if fault == 'silent_rollback':
            db.rollback()
            return
        db.commit()
        raise sqlite3.OperationalError('lost acknowledgement after COMMIT')

    j._commit = uncertain_commit
    with pytest.raises(AmbiguousCommit):
        j.process(candle(version), Signal('BUY', 2), expected_version=version)
    assert j.poisoned and j.state is old and j.version == version
    assert not j._db.in_transaction and len(captured) == 1
    result = reconcile(j, captured[0])
    assert result.outcome == ('COMMITTED' if fault == 'after' else 'NOT_COMMITTED')
    assert result.snapshot.version == version + (fault == 'after')
    assert j.poisoned and j.state is old and j.version == version


@pytest.mark.parametrize('phase,statement', [
    ('schema', 'PRAGMA application_id'),
    ('metadata', 'FROM main.run_metadata'),
    ('commits', 'FROM main.candle_commits ORDER BY version'),
    ('events', 'FROM main.events ORDER BY sequence'),
    ('head', 'FROM main.state_head ORDER BY singleton'),
])
def test_trace_rollback_during_verification_rejects_without_mutation(histories, phase, statement):
    j = histories(tape())
    db, before, state = j._db, rows(j._db), j.state
    interrupted = []

    def trace(sql):
        if not interrupted and statement in sql:
            interrupted.append((phase, db.in_transaction))
            db.rollback()

    db.set_trace_callback(trace)
    try:
        with pytest.raises(TransactionContinuityError):
            verify(j)
        assert interrupted == [(phase, True)]
        assert rows(db) == before and j.state is state and not j.closed
        assert not db.in_transaction
        db.set_trace_callback(None)
        assert verify(j) == verify(j)
    finally:
        db.set_trace_callback(None)


def test_trace_rollback_and_restart_is_not_accepted_as_same_transaction(histories):
    j = histories(tape())
    db, before, state = j._db, rows(j._db), j.state
    interrupted = []

    def trace(sql):
        if not interrupted and 'FROM main.candle_commits ORDER BY version' in sql:
            interrupted.append(True)
            db.rollback()
            db.execute('BEGIN')

    db.set_trace_callback(trace)
    try:
        with pytest.raises(TransactionContinuityError):
            verify(j)
        assert interrupted == [True]
        assert rows(db) == before and j.state is state and not j.closed
        assert db.in_transaction  # The replacement transaction is left to its owner.
    finally:
        db.set_trace_callback(None)
        if db.in_transaction:
            db.rollback()


@pytest.mark.parametrize('outcome', ['NOT_COMMITTED', 'COMMITTED'])
def test_reconciliation_rollbacks_during_replay_fail_closed(histories, outcome):
    prior = histories([(candle(0), HOLD)])
    applied = histories([(candle(0), HOLD), (candle(1), Signal('BUY', 2))])
    identity = attempt(applied, HistoryAnchor(prior.version, prior._snapshot.commit_digest))
    target = prior if outcome == 'NOT_COMMITTED' else applied
    db, before, state = target._db, rows(target._db), target.state
    fired = []

    def trace(sql):
        if not fired and 'FROM main.candle_commits ORDER BY version' in sql:
            fired.append(True)
            db.rollback()

    db.set_trace_callback(trace)
    try:
        with pytest.raises(TransactionContinuityError):
            reconcile(target, identity)
        assert fired == [True]
        assert rows(db) == before and target.state is state and not target.closed
        assert not db.in_transaction
    finally:
        db.set_trace_callback(None)
    assert reconcile(target, identity).outcome == outcome


def test_transaction_ending_at_release_and_cleanup_failure(histories):
    j = histories(tape())
    db, before, state = j._db, rows(j._db), j.state
    fired = []

    def trace(sql):
        if not fired and sql.startswith('RELEASE SAVEPOINT "protrader_replay_'):
            fired.append(True)
            db.rollback()
            db.execute('BEGIN')

    db.set_trace_callback(trace)
    try:
        with pytest.raises(ReplayCleanupError):
            verify(j)
        assert fired == [True]
        assert rows(db) == before and j.state is state and not j.closed
        assert db.in_transaction
    finally:
        db.set_trace_callback(None)
        if db.in_transaction:
            db.rollback()
    assert verify(j) == verify(j)
