"""Synthetic memory-only coordinator acceptance and fault-injection tests."""
import sqlite3
from dataclasses import replace
from datetime import timedelta, timezone

import pytest

from paper.offline import journal_codec as codec, journal_schema as schema
from paper.offline.engine import PaperEngine
from paper.offline.journal import (Journal, Receipt, ContractMismatch, InputConflict,
    StaleVersion, InvalidInput, TransactionFailure, AmbiguousCommit,
    JournalPoisoned, JournalClosed, JournalReentrant)
from paper.offline.models import Signal
from test_offline_paper_engine import config, candle, cost_profile

FINGERPRINT = 'engine-v1:sha256:' + 'a' * 64


class FaultHarness:
    """White-box transaction hooks; production never accepts this as storage."""
    def __init__(self, journal):
        self._connection = journal._db
        self.journal = journal
        journal._execute = self.execute
        journal._commit = self.commit
        journal._rollback = self.rollback

    def __getattr__(self, name):
        return getattr(self._connection, name)

    fault = None
    journal = None
    observed = None

    def execute(self, sql, parameters=()):
        fault = self.fault
        if fault and sql.startswith(fault):
            self.fault = None
            raise sqlite3.OperationalError('injected ' + fault)
        if fault == 'second_event' and sql.startswith('INSERT INTO main.events') and parameters[2] == 1:
            self.fault = None
            raise sqlite3.OperationalError('second event')
        cursor = self._connection.execute(sql, parameters)
        if fault == 'after_head' and sql.startswith(('INSERT INTO main.state_head', 'UPDATE main.state_head')):
            self.fault = None
            raise sqlite3.OperationalError('after head')
        if fault == 'cas' and sql.startswith('UPDATE main.state_head'):
            class Miss:
                rowcount = 0
            self.fault = None
            return Miss()
        return cursor

    def commit(self):
        if self.journal is not None:
            self.observed = (self.journal.state, self.journal.version, self.in_transaction)
        if self.fault == 'commit_rollback':
            self.fault = None
            self._connection.rollback()
            return
        if self.fault == 'commit_noop':
            self.fault = None
            return
        if self.fault == 'commit_before':
            self.fault = None
            raise sqlite3.OperationalError('COMMIT not applied')
        self._connection.commit()
        if self.fault == 'commit_after':
            self.fault = None
            raise sqlite3.OperationalError('COMMIT applied but acknowledgement lost')

    def rollback(self):
        if self.fault == 'rollback_noop':
            self.fault = None
            return
        if self.fault == 'rollback':
            self.fault = None
            raise sqlite3.OperationalError('rollback failed')
        return self._connection.rollback()


@pytest.fixture
def setup():
    journal = Journal(config(), FINGERPRINT)
    db = FaultHarness(journal)
    yield db, journal
    journal.close()
    db.close()


def apply(journal, c, s):
    return journal.process(c, s, expected_version=journal.version)


def rows(db):
    return tuple(tuple(db.execute('SELECT * FROM main.' + name).fetchall()) for name in schema.TABLES)


def verify(db, journal):
    """Independently fold stored rows and compare every persisted contract."""
    schema.validate_schema(db._connection)
    inputs, events, parent = codec.empty_digest('input'), codec.empty_digest('event'), None
    event_count = 0
    for commit in db.execute('SELECT * FROM main.candle_commits ORDER BY version'):
        v, run, pv, instrument, interval, identity, wire, ih, ci, ce, sh, ch = commit
        c, s = codec.decode(wire, tuple)
        assert run == 1 and pv == (v - 1 or None)
        assert (instrument, interval, identity) == (config().instrument, config().interval_seconds, c.timestamp.isoformat(timespec='microseconds'))
        assert ih == codec.input_hash(c, s)
        inputs = codec.cumulative_digest('input', inputs, ih, count=v)
        for index, row in enumerate(db.execute('SELECT * FROM main.events WHERE commit_version=? ORDER BY event_index', (v,))):
            sequence, version, event_index, payload, eh = row
            event_count += 1
            event = codec.decode(payload)
            assert sequence == event.sequence == event_count
            assert event_index == index and version == v
            assert event == journal.state.events[event_count - 1]
            assert codec.event_hash(event) == eh
            events = codec.cumulative_digest('event', events, eh, count=event_count)
        assert (ci, ce) == (inputs, events)
        assert ch == codec.commit_hash(parent, v, ci, ce, sh,
            codec.execution_policy_hash(config(), FINGERPRINT),
            processed_input_count=v, event_count=event_count)
        parent = ch
    if journal.version:
        head = db.execute('SELECT * FROM main.state_head').fetchone()
        assert head == (1, journal.version, codec.encode(journal.state), codec.state_hash(journal.state))


def test_genesis_and_zero_event_holds(setup):
    db, j = setup
    assert j.version == 0 and not j.state.processed
    assert db.execute('SELECT COUNT(*) FROM main.run_metadata').fetchone() == (1,)
    assert db.execute('SELECT COUNT(*) FROM main.state_head').fetchone() == (0,)
    for i in range(3):
        receipt = apply(j, candle(i), Signal('HOLD'))
        assert receipt.status == 'APPLIED' and receipt.version == i + 1
        assert receipt.state is j.state
    assert db.execute('SELECT COUNT(*) FROM main.events').fetchone() == (0,)
    verify(db, j)


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
@pytest.mark.parametrize('multiple', [False, True])
def test_execution_and_marking_parity(setup, side, multiple):
    db, j = setup
    engine = PaperEngine(config())
    tape = [(candle(0), Signal(side, 2)),
            (candle(1, high=105, low=95) if multiple else candle(1), Signal(side, 2) if multiple else Signal('HOLD')),
            (candle(2, high=102, close=101), Signal('HOLD')),
            (candle(3, high=110, low=90), Signal('HOLD'))]
    for c, s in tape:
        prior = j.state
        receipt = apply(j, c, s)
        assert receipt.state == engine.process(c, s)
        if not multiple and c == tape[2][0]:
            assert j.state.events == prior.events
            assert j.state.account != prior.account
        verify(db, j)
    if multiple:
        assert [e.kind for e in j.state.events[1:4]] == ['ENTRY', 'EXIT', 'INTENT']


@pytest.mark.parametrize('side', ['BUY', 'SELL'])
def test_costs_and_slippage_parity(side):
    cfg = config(costs=cost_profile(), slippage_bps=5)
    j = Journal(cfg, FINGERPRINT)
    db = FaultHarness(j)
    engine = PaperEngine(cfg)
    try:
        for c, s in [(candle(0), Signal(side, 2)), (candle(1), Signal('HOLD')),
                     (candle(2, high=102, close=101), Signal('HOLD')),
                     (candle(3, open=90, high=110, low=89), Signal('HOLD'))]:
            assert apply(j, c, s).state == engine.process(c, s)
    finally:
        j.close()
        db.close()


@pytest.mark.parametrize('index', [0, 2])
def test_duplicate_old_and_latest_and_stale(setup, index):
    db, j = setup
    for i in range(3):
        apply(j, candle(i), Signal('HOLD'))
    before, state = rows(db), j.state
    receipt = apply(j, candle(index), Signal('HOLD'))
    assert receipt == Receipt('ALREADY_PROCESSED', 3, index + 1, state, receipt.commit_hash)
    assert rows(db) == before and j.state is state
    with pytest.raises(StaleVersion):
        j.process(candle(index), Signal('HOLD'), expected_version=2)
    assert rows(db) == before and j.state is state


@pytest.mark.parametrize('change', ['open', 'high', 'low', 'close', 'volume', 'signal', 'atr', 'offset'])
def test_conflicting_inputs(setup, change):
    db, j = setup
    c, s = candle(0), Signal('BUY', 2)
    apply(j, c, s)
    if change == 'signal':
        s = Signal('SELL', 2)
    elif change == 'atr':
        s = Signal('BUY', 3)
    elif change == 'offset':
        c = replace(c, timestamp=c.timestamp.astimezone(timezone.utc))
    else:
        values = {'open': 101, 'high': 102, 'low': 98, 'close': 101, 'volume': 2}
        c = replace(c, **{change: values[change]})
    before, old = rows(db), j.state
    with pytest.raises(InputConflict):
        apply(j, c, s)
    assert rows(db) == before and j.state is old


@pytest.mark.parametrize('version', [-1, 0, 2, True, None])
def test_stale_new_input(setup, version):
    db, j = setup
    apply(j, candle(0), Signal('HOLD'))
    before, old = rows(db), j.state
    with pytest.raises(StaleVersion):
        j.process(candle(1), Signal('HOLD'), expected_version=version)
    assert rows(db) == before and j.state is old


@pytest.mark.parametrize('case', ['chronology', 'grid', 'open_date', 'type'])
def test_invalid_transition_is_atomic(setup, case):
    db, j = setup
    apply(j, candle(0), Signal('BUY', 2))
    apply(j, candle(1), Signal('HOLD'))
    c = {'chronology': candle(-1), 'grid': replace(candle(2), timestamp=candle(2).timestamp + timedelta(seconds=1)),
         'open_date': replace(candle(2), timestamp=candle(2).timestamp + timedelta(days=1)), 'type': None}[case]
    before, old = rows(db), j.state
    with pytest.raises(InvalidInput):
        apply(j, c, Signal('HOLD'))
    assert rows(db) == before and j.state is old


@pytest.mark.parametrize('next_day', [False, True])
def test_pending_gap_and_date_cancel(setup, next_day):
    db, j = setup
    apply(j, candle(0), Signal('BUY', 2))
    c = replace(candle(0), timestamp=candle(0).timestamp + timedelta(days=1)) if next_day else candle(2)
    apply(j, c, Signal('HOLD'))
    assert j.state.pending is None and j.state.position is None
    assert j.state.events[-1].reason == ('DATE_CHANGED' if next_day else 'MISSING_NEXT_CANDLE')
    verify(db, j)


@pytest.mark.parametrize('fault', ['INSERT INTO main.candle_commits', 'INSERT INTO main.events', 'INSERT INTO main.state_head', 'after_head'])
@pytest.mark.parametrize('existing', [False, True])
def test_sql_failures_rollback_entire_transaction(setup, fault, existing):
    db, j = setup
    if existing:
        apply(j, candle(0), Signal('HOLD'))
    before, old, version = rows(db), j.state, j.version
    db.fault = 'UPDATE main.state_head' if existing and fault == 'INSERT INTO main.state_head' else fault
    with pytest.raises(TransactionFailure):
        apply(j, candle(version), Signal('BUY', 2))
    assert j.state is old and j.version == version and rows(db) == before
    assert not db.in_transaction and not j.poisoned
    assert apply(j, candle(version), Signal('BUY', 2)).status == 'APPLIED'


def test_cas_miss_rolls_back(setup):
    db, j = setup
    apply(j, candle(0), Signal('HOLD'))
    before, old = rows(db), j.state
    db.fault = 'cas'
    with pytest.raises(ContractMismatch, match='compare-and-swap'):
        apply(j, candle(1), Signal('BUY', 2))
    assert rows(db) == before and j.state is old


@pytest.mark.parametrize('fault,committed', [('commit_before', False), ('commit_after', True), ('commit_noop', False), ('commit_rollback', False)])
def test_ambiguous_commit_poisoning(setup, fault, committed):
    db, j = setup
    before, old = rows(db), j.state
    db.fault = fault
    with pytest.raises(AmbiguousCommit):
        apply(j, candle(0), Signal('BUY', 2))
    assert j.poisoned and j.state is old and j.version == 0
    assert (rows(db) != before) == committed
    assert db.execute('SELECT COUNT(*) FROM main.candle_commits').fetchone() == (int(committed),)
    assert db.execute('SELECT COUNT(*) FROM main.events').fetchone() == (int(committed),)
    with pytest.raises(JournalPoisoned):
        apply(j, candle(0), Signal('BUY', 2))


def test_no_publication_before_commit(setup):
    db, j = setup
    old = j.state
    apply(j, candle(0), Signal('BUY', 2))
    assert db.observed == (old, 0, True)
    assert j.state is not old and j.version == 1


@pytest.mark.parametrize('mismatch', ['head_hash', 'head_payload', 'head_missing', 'tip', 'metadata', 'foreign_keys'])
def test_head_and_contract_refusal(setup, mismatch):
    db, j = setup
    apply(j, candle(0), Signal('HOLD'))
    if mismatch == 'head_hash':
        db.execute("UPDATE main.state_head SET state_hash='wrong'")
    elif mismatch == 'head_payload':
        db.execute("UPDATE main.state_head SET state_json=X'00'")
    elif mismatch == 'head_missing':
        db.execute('DELETE FROM main.state_head')
    elif mismatch == 'tip':
        db.execute("INSERT INTO main.candle_commits SELECT 2,1,1,instrument,interval_seconds,'other',input_json,input_hash,cumulative_input_hash,cumulative_event_hash,state_hash,'other' FROM main.candle_commits")
    elif mismatch == 'metadata':
        db.execute('DROP TRIGGER run_metadata_no_update')
        db.execute("UPDATE main.run_metadata SET config_hash='wrong'")
        db.execute(schema.TRIGGERS['run_metadata_no_update'])
    else:
        db.execute('PRAGMA foreign_keys=OFF')
    db.commit()
    before, old = rows(db), j.state
    with pytest.raises(ContractMismatch):
        apply(j, candle(1), Signal('HOLD'))
    assert rows(db) == before and j.state is old


def test_ownership_close_and_no_resume(setup):
    db, j = setup
    other = Journal(config(), FINGERPRINT)
    try:
        apply(j, candle(0), Signal('HOLD'))
        assert other.version == 0
        assert other._db is not j._db
        with pytest.raises(TypeError):
            Journal(db, config(), FINGERPRINT)
        j.close()
        assert j.closed
        with pytest.raises(JournalClosed):
            apply(j, candle(1), Signal('HOLD'))
        with pytest.raises(sqlite3.ProgrammingError):
            db.execute('SELECT COUNT(*) FROM main.candle_commits')
    finally:
        other.close()


@pytest.mark.parametrize('bad', [None, ':memory:', 'file:memory?mode=memory', 1])
def test_no_automatic_connection_creation(bad):
    with pytest.raises(TypeError):
        Journal(bad, config(), FINGERPRINT)


def test_reject_temp_and_attached_memory(setup):
    db, j = setup
    with pytest.raises(sqlite3.DatabaseError, match='authorized'):
        db.execute("ATTACH DATABASE ':memory:' AS extra")
    assert not any(row[1] == 'extra' for row in db.execute('PRAGMA database_list'))
    assert apply(j, candle(0), Signal('HOLD')).status == 'APPLIED'


@pytest.mark.parametrize('fingerprint', ['', 'NEXT_OPEN_STOP_FIRST_V1', 'engine-v2:sha256:' + 'a'*64])
def test_invalid_fingerprint_does_not_initialize(fingerprint, monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('database creation before config validation')
    monkeypatch.setattr(sqlite3, 'connect', deny)
    with pytest.raises(ContractMismatch):
        Journal(config(), fingerprint)


def test_active_caller_transaction_preserved(setup):
    db, j = setup
    db.execute('BEGIN')
    with pytest.raises(ContractMismatch, match='caller transaction'):
        apply(j, candle(0), Signal('HOLD'))
    assert db.in_transaction
    db.rollback()


def test_rollback_failure_poisoning(setup):
    db, j = setup
    db.fault = 'rollback'
    with pytest.raises(JournalPoisoned):
        j.process(candle(0), Signal('HOLD'), expected_version=5)
    assert j.poisoned
    with pytest.raises(JournalPoisoned):
        apply(j, candle(0), Signal('HOLD'))
    db.rollback()


def test_import_and_processing_isolation():
    import subprocess
    import sys
    from pathlib import Path
    script = r'''
import sys, builtins, io, os, socket, sqlite3, dataclasses, threading, typing, json, hashlib
from datetime import datetime, timezone
from decimal import Decimal
sys.path.insert(0, ROOT)
real_import = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name.split('.')[0] in {'main','config','dotenv','broker','SmartApi','backtest','research','requests','urllib'}:
        raise AssertionError(name)
    return real_import(name, globals, locals, fromlist, level)
builtins.__import__ = guarded
def deny(*a, **k): raise AssertionError('forbidden I/O or credentials')
builtins.open = io.open = os.getenv = socket.socket = deny
class ForbiddenEnvironment(dict):
    def __getitem__(self, key): return deny()
    def get(self, *a): return deny()
    def __iter__(self): return deny()
os.environ = ForbiddenEnvironment()
connect = sqlite3.connect
sqlite3.connect = deny
from paper.offline.journal import Journal
from paper.offline.config import Config, Costs
from paper.offline.models import Candle, Signal
cfg = Config('PAPER',Decimal('10000'),Decimal('.01'),5,Decimal('500'),Decimal('10000'),Decimal('0'),Costs('PAPER_COST_V1', *([Decimal('0')]*9)),'SYNTHETIC',300,'NEXT_OPEN_STOP_FIRST_V1')
def private_connect(target, **kwargs):
    assert target == ':memory:' and 'uri' not in kwargs and 'factory' not in kwargs
    return connect(target, **kwargs)
sqlite3.connect = private_connect
j = Journal(cfg,'engine-v1:sha256:'+'a'*64)
j.process(Candle(datetime(2026,1,5,tzinfo=timezone.utc),100,101,99,100,1),Signal('HOLD'),expected_version=0)
assert j.version == 1
j.close()
'''.replace('ROOT', repr(str(Path(__file__).resolve().parents[1])))
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_partial_multiple_event_insert_rolls_back(setup):
    db, j = setup
    apply(j, candle(0), Signal('BUY', 2))
    before, old = rows(db), j.state
    db.fault = 'second_event'
    with pytest.raises(TransactionFailure, match='second event'):
        apply(j, candle(1, high=105, low=95), Signal('SELL', 2))
    assert rows(db) == before and j.state is old and j.version == 1
    assert not db.in_transaction
    receipt = apply(j, candle(1, high=105, low=95), Signal('SELL', 2))
    assert [e.kind for e in receipt.state.events[1:]] == ['ENTRY', 'EXIT', 'INTENT']
    verify(db, j)


def test_concurrent_stale_call_cannot_rebase():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    j = Journal(config(), FINGERPRINT)
    db = FaultHarness(j)
    barrier = Barrier(2)
    def process():
        barrier.wait(timeout=5)
        try:
            return j.process(candle(0), Signal('HOLD'), expected_version=0).status
        except StaleVersion:
            return 'STALE'
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process) for _ in range(2)]
            assert sorted(f.result(timeout=10) for f in futures) == ['APPLIED', 'STALE']
        assert j.version == 1
        verify(db, j)
    finally:
        j.close()
        db.close()


def test_file_storage_rejection_without_opening_a_file(monkeypatch):
    real_connect = sqlite3.connect
    calls = []
    def private_connect(target, **kwargs):
        calls.append((target, kwargs))
        assert target == ':memory:' and 'uri' not in kwargs and 'factory' not in kwargs
        return real_connect(target, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', private_connect)
    j = Journal(config(), FINGERPRINT)
    try:
        assert calls == [(':memory:', dict(isolation_level=None, check_same_thread=False))]
        with pytest.raises(TypeError):
            Journal(config(), FINGERPRINT, connection='forbidden-file.sqlite')
        assert len(calls) == 1
    finally:
        j.close()


def test_runtime_temporary_storage_change_refused(setup):
    db, j = setup
    db.execute('PRAGMA temp_store=FILE')
    old, before = j.state, rows(db)
    with pytest.raises(ContractMismatch, match='Temporary storage'):
        apply(j, candle(0), Signal('HOLD'))
    assert j.state is old and rows(db) == before


def test_broken_candidate_prefix_refused(setup, monkeypatch):
    import paper.offline.journal as module
    db, j = setup
    apply(j, candle(0), Signal('HOLD'))
    old, before = j.state, rows(db)
    monkeypatch.setattr(module, 'transition', lambda *args: old)
    with pytest.raises(ContractMismatch, match='prefix'):
        apply(j, candle(1), Signal('HOLD'))
    assert j.state is old and rows(db) == before


def test_autocommit_noop_mode_refused_without_initialization():
    with pytest.raises(TypeError):
        Journal(config(), FINGERPRINT, autocommit=True)


@pytest.mark.parametrize('table', ['candle_commits', 'events', 'state_head'])
@pytest.mark.parametrize('existing', [False, True])
def test_runtime_temp_shadowing_refused(setup, table, existing):
    db, j = setup
    if existing:
        apply(j, candle(0), Signal('HOLD'))
    db.execute('CREATE TEMP TABLE ' + table + ' AS SELECT * FROM main.' + table)
    before, old, version = rows(db), j.state, j.version
    with pytest.raises(ContractMismatch, match='TEMP'):
        apply(j, candle(version), Signal('BUY', 2))
    assert rows(db) == before and j.state is old and j.version == version
    assert not db.in_transaction


@pytest.mark.parametrize('operation', ['process', 'close'])
def test_sqlite_callback_reentrancy_rejects_promptly(operation):
    # A child process gives a hard timeout and is killed/reaped on a regression;
    # no worker threads survive a failing deadlock test.
    import subprocess
    import sys
    from pathlib import Path
    script = r'''
import sys
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)
from test_offline_paper_engine import config, candle
from paper.offline.journal import Journal, JournalReentrant
from paper.offline.models import Signal
j = Journal(config(), 'engine-v1:sha256:' + 'a'*64)
seen = []
def callback(sql):
    if sql == 'BEGIN IMMEDIATE':
        try:
            if OPERATION == 'close':
                j.close()
            else:
                j.process(candle(0), Signal('HOLD'), expected_version=0)
        except JournalReentrant:
            seen.append('rejected')
j._db.set_trace_callback(callback)
try:
    receipt = j.process(candle(0), Signal('HOLD'), expected_version=0)
    assert seen == ['rejected']
    assert receipt.status == 'APPLIED' and j.version == 1 and not j.closed
finally:
    j._db.set_trace_callback(None)
    j.close()
'''.replace('ROOT', repr(str(Path(__file__).resolve().parents[1]))).replace('TESTS', repr(str(Path(__file__).resolve().parent))).replace('OPERATION', repr(operation))
    result = subprocess.run([sys.executable, '-I', '-B', '-c', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


def test_shared_uri_has_no_alias_and_cannot_be_supplied(setup):
    db, j = setup
    external = sqlite3.connect('file::memory:?cache=shared', uri=True)
    try:
        apply(j, candle(0), Signal('BUY', 2))
        assert external.execute('SELECT name FROM main.sqlite_master').fetchall() == []
        with pytest.raises(TypeError):
            Journal(config(), FINGERPRINT, connection=external)
        assert external is not j._db
        external.execute('CREATE TABLE run_metadata (value TEXT)')
        external.execute("INSERT INTO run_metadata VALUES ('external mutation')")
        external.commit()
        assert apply(j, candle(1), Signal('HOLD')).status == 'APPLIED'
        verify(db, j)
    finally:
        external.close()


@pytest.mark.parametrize('target', [':memory:', 'file::memory:?cache=shared', 'forbidden.sqlite'])
def test_public_api_rejects_storage_selection(target):
    # These strings are never passed to sqlite3.connect.
    with pytest.raises(TypeError):
        Journal(config(), FINGERPRINT, connection=target)
    with pytest.raises(TypeError):
        Journal(config(), FINGERPRINT, factory=lambda: target)


def test_silent_rollback_after_partial_insert_poisons(setup, monkeypatch):
    db, j = setup
    old = j.state
    db.fault = 'INSERT INTO main.events'
    monkeypatch.setattr(j, '_rollback', lambda: None)
    with pytest.raises(JournalPoisoned, match='postconditions'):
        apply(j, candle(0), Signal('BUY', 2))
    assert j.poisoned and j.state is old and j.version == 0
    assert db.in_transaction
    with pytest.raises(JournalPoisoned):
        apply(j, candle(0), Signal('BUY', 2))
    j.close()  # Owned connection closure discards the uncommitted partial rows.
    assert j.closed


def test_duplicate_rollback_noop_poisons(setup):
    db, j = setup
    apply(j, candle(0), Signal('HOLD'))
    old = j.state
    db.fault = 'rollback_noop'
    with pytest.raises(JournalPoisoned):
        apply(j, candle(0), Signal('HOLD'))
    assert j.poisoned and j.state is old


def test_publication_waits_for_persistence_verification(setup, monkeypatch):
    db, j = setup
    old = j.state
    original = j._verify_commit
    observed = []
    def verify_commit(*args):
        observed.append((j.state is old, j.version, db.in_transaction,
                         db.execute('SELECT COUNT(*) FROM main.candle_commits').fetchone()[0]))
        return original(*args)
    monkeypatch.setattr(j, '_verify_commit', verify_commit)
    apply(j, candle(0), Signal('BUY', 2))
    assert observed == [(True, 0, False, 1)]
    assert j.version == 1 and j.state is not old


def test_postcommit_verification_error_poisons_without_publication(setup, monkeypatch):
    db, j = setup
    old = j.state
    def fail(*args):
        raise sqlite3.OperationalError('verification read failed')
    monkeypatch.setattr(j, '_verify_commit', fail)
    with pytest.raises(AmbiguousCommit):
        apply(j, candle(0), Signal('BUY', 2))
    assert j.poisoned and j.state is old and j.version == 0
    assert db.execute('SELECT COUNT(*) FROM main.candle_commits').fetchone() == (1,)


def test_current_event_suffix_verified_after_commit(setup, monkeypatch):
    db, j = setup
    old = j.state
    def commit_and_corrupt():
        db.commit()
        db.execute('DROP TRIGGER main.events_no_update')
        db.execute("UPDATE main.events SET event_json=X'00'")
        db.execute(schema.TRIGGERS['events_no_update'])
    monkeypatch.setattr(j, '_commit', commit_and_corrupt)
    with pytest.raises(AmbiguousCommit):
        apply(j, candle(0), Signal('BUY', 2))
    assert j.poisoned and j.state is old and j.version == 0


def test_count_preserving_historical_event_corruption_remains_deferred(setup):
    db, j = setup
    apply(j, candle(0), Signal('BUY', 2))
    db.execute('DROP TRIGGER main.events_no_update')
    db.execute("UPDATE main.events SET event_json=X'00',event_hash='bad' WHERE sequence=1")
    db.execute(schema.TRIGGERS['events_no_update'])
    # This intentionally documents B2's boundary. Only this transaction's new
    # suffix is checked; historical replay/corruption reconciliation is B3.
    assert apply(j, candle(1), Signal('HOLD')).status == 'APPLIED'
    assert db.execute('SELECT event_json FROM main.events WHERE sequence=1').fetchone() == (b'\x00',)
