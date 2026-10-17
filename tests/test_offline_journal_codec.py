"""Synthetic offline codec and schema acceptance tests."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from dataclasses import replace, fields, is_dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest

from paper.offline import journal_codec as c
from paper.offline import journal_schema as s
from paper.offline.config import Costs, Config
from paper.offline.models import Account, Risk, State, Candle, Signal, Event, Position, Intent
from paper.offline.engine import PaperEngine

D = Decimal
STAMP = datetime(2026, 1, 5, 9, 15, 1, 123456,
                 tzinfo=timezone(timedelta(hours=5, minutes=30, microseconds=123)))


def config():
    costs = Costs('PAPER_COST_V1', *([D('0')] * 9))
    return Config('PAPER', D('10000'), D('.01'), 5, D('500'), D('10000'),
                  D('0'), costs, 'SYNTHETIC', 300, 'NEXT_OPEN_STOP_FIRST_V1')


def candle(stamp=STAMP):
    return Candle(stamp, D('100'), D('101'), D('99'), D('100'), D('1'))


@pytest.mark.parametrize('text,expected', [('1.2300', '123e-2'), ('-0.00', '0'),
    ('0E+999', '0'), ('1000', '1e3'), ('-12345678901234567890.1200', '-1234567890123456789012e-2')])
def test_decimal_canonicalization(text, expected):
    with localcontext() as ctx:
        ctx.prec = 2
        assert c.decimal_text(D(text)) == expected
        assert c.decode(c.encode(D(text))) == D(text)
    assert c.encode(D('1.00')) == c.encode(D('1'))
    assert c.encode(D('-0')) == c.encode(D('0'))


def test_large_negative_aggregates_and_low_precision():
    account = Account(D('-999999999999999999999999999999999999999999.99'),
                      D('9999999999999999999999999999999999999999999'))
    expected = c.encode(account)
    with localcontext() as ctx:
        ctx.prec = 1
        assert c.encode(c.decode(expected)) == expected
        assert c.decode(expected) == account
        assert c.decode(c.encode(config())) == config()


def test_timestamp_identity():
    result = c.decode(c.encode(candle()))
    assert result.timestamp.isoformat() == STAMP.isoformat()
    assert result.timestamp.microsecond == 123456
    assert result.timestamp.astimezone(timezone.utc) == STAMP.astimezone(timezone.utc)
    assert c.encode(STAMP) != c.encode(STAMP.astimezone(timezone.utc))


def test_nested_fields_and_all_records_roundtrip():
    event = Event(1, STAMP, 'EXIT', 'SYNTHETIC',
                  (('charges', (('gst', D('.12300')), ('total', D('100000000000000000000')))),
                   ('misc', (None, True, 7, 'α', STAMP, timedelta(microseconds=-3)))))
    position = Position('BUY', 1, D('100'), D('100'), D('97'), D('104'), D('100'), STAMP, 'synthetic')
    intent = Intent('BUY', D('2'), STAMP, 'synthetic')
    state = State(Account(D('-10')), Risk(day=STAMP.date().isoformat()), None, intent,
                  ((candle(), Signal('BUY', D('2'))),), (event,), STAMP, STAMP.utcoffset())
    for record in (config(), config().costs, candle(), Signal('HOLD'), state,
                   state.account, state.risk, position, intent, event):
        wire = c.encode(record)
        assert c.decode(wire, type(record)) == record
        assert c.encode(c.decode(wire)) == wire
    assert c.encode(event.fields) != c.encode(tuple(reversed(event.fields)))


def test_real_engine_state_roundtrip():
    engine = PaperEngine(config())
    for i, signal in enumerate((Signal('BUY', D('2')), Signal('HOLD'), Signal('SELL', D('2')))):
        engine.process(candle(STAMP + timedelta(seconds=300*i)), signal)
        assert c.decode(c.encode(engine.state)) == engine.state


@pytest.mark.parametrize('value', [1.5, float('nan'), float('inf'), D('NaN'), D('Infinity'),
    datetime(2026, 1, 1), [], {}, Account(1), Risk(entries=True),
    Event(True, STAMP, 'X', '', ()), Event(1, STAMP, 'X', '', (('x', 1), ('x', 2))),
    State(Account(D('1')), Risk(), events=(Event(2, STAMP, 'X', '', ()), Event(1, STAMP, 'X', '', ())))])
def test_invalid_encode(value):
    with pytest.raises(ValueError):
        c.encode(value)


@pytest.mark.parametrize('payload', [b'', b'[]', b'{}', b'\xff', b'{',
    b'{"version":1,"version":1,"value":null}',
    b'{"version":true,"value":null}', b'{"version":3,"value":null}',
    b'{"version":1,"value":NaN}', b'{"version":1,"value":Infinity}',
    b'{"version":1,"value":1.2}', b'{"version":1,"value":{"decimal":"NaN"}}',
    b'{"version":1,"value":{"decimal":"1.00"}}',
    b'{"version":1,"value":{"datetime":"2026-01-01T00:00:00.000000"}}',
    b'{"version":1,"value":{"tuple":[],"tuple":[]}}',
    b'{"version":1,"value":{"record":"Unknown","fields":{}}}',
    b'{"version":1,"value":null,"extra":0}'])
def test_invalid_json(payload):
    with pytest.raises(ValueError):
        c.decode(payload.replace(b'"version":1', b'"version":2'))


@pytest.mark.parametrize('change', ['missing', 'unknown', 'type'])
def test_strict_record_fields(change):
    raw = json.loads(c.encode(Account(D('1'))))
    fields = raw['value']['fields']
    if change == 'missing':
        del fields['reserved']
    elif change == 'unknown':
        fields['extra'] = None
    else:
        fields['realized_equity'] = '1'
    with pytest.raises(ValueError):
        c.decode(json.dumps(raw).encode())


def test_hash_contracts():
    cfg = config()
    fingerprint = 'engine-v1:sha256:' + 'a'*64
    hashes = [c.configuration_hash(cfg), c.input_contract_hash(cfg),
              c.execution_policy_hash(cfg, fingerprint), c.input_hash(candle(), Signal('HOLD')),
              c.event_hash(Event(1, STAMP, 'X', '', ())), c.state_hash(State(Account(D('1')), Risk()))]
    assert len(set(hashes)) == len(hashes)
    assert c.configuration_hash(cfg) == c.configuration_hash(c.decode(c.encode(cfg)))
    assert c.execution_policy_hash(cfg, fingerprint) != c.execution_policy_hash(cfg, 'engine-v1:sha256:' + 'b'*64)
    assert c.digest('a', cfg) != c.digest('b', cfg)
    assert c.input_hash(candle(), Signal('HOLD')) != c.input_hash(candle(STAMP.astimezone(timezone.utc)), Signal('HOLD'))
    a, b = hashes[:2]
    assert c.cumulative_digest('input', None, a, count=1) == c.cumulative_digest('input', c.empty_digest('input'), a, count=1)
    assert c.cumulative_digest('input', None, a, count=1) != c.cumulative_digest('event', None, a, count=1)
    assert c.cumulative_digest('input', c.cumulative_digest('input', None, a, count=1), b, count=2) != c.cumulative_digest('input', c.cumulative_digest('input', None, b, count=1), a, count=2)
    args = (1, a, b, a, b)
    assert c.commit_hash(None, *args, processed_input_count=1, event_count=1) != c.commit_hash(a, 2, a, b, a, b, processed_input_count=2, event_count=1)
    with pytest.raises(ValueError):
        c.execution_policy_hash(cfg, cfg.execution_policy)
    with pytest.raises(ValueError):
        c.commit_hash(None, True, a, b, a, b, processed_input_count=1, event_count=1)


def database():
    db = sqlite3.connect(':memory:')
    s.initialize_schema(db)
    return db


def seed(db):
    db.execute('INSERT INTO run_metadata VALUES (1,2,?,?,?,?,?)',
               (b'{}', 'a', 'b', 'c', 'engine-v1:sha256:' + 'a'*64))
    db.execute('INSERT INTO candle_commits VALUES (1,1,NULL,?,?,?,?,?,?,?,?,?)',
               ('SYNTHETIC', 300, 'instant-1', b'{}', 'a', 'b', 'c', 'd', 'e'))


def test_schema_idempotent_and_versions():
    with database() as db:
        s.initialize_schema(db)
        s.validate_schema(db)
        assert db.execute('PRAGMA application_id').fetchone()[0] == s.APPLICATION_ID
        db.execute('PRAGMA user_version=3')
        with pytest.raises(ValueError):
            s.validate_schema(db)
        with pytest.raises(ValueError):
            s.initialize_schema(db)


def test_schema_definitions_and_foreign_keys():
    with database() as db:
        db.execute('DROP TRIGGER events_order')
        with pytest.raises(ValueError):
            s.validate_schema(db)
    with database() as db:
        db.execute('PRAGMA foreign_keys=OFF')
        with pytest.raises(ValueError):
            s.validate_schema(db)
    with database() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO state_head VALUES (1,1,X'00','a')")


def test_schema_constraints():
    with database() as db:
        seed(db)
        db.execute("INSERT INTO state_head VALUES (1,1,X'00','d')")
        db.execute("INSERT INTO events VALUES (1,1,0,X'00','a')")
        for sql in ["INSERT INTO events VALUES (3,1,1,X'00','a')",
                    "INSERT INTO events VALUES (2,1,0,X'00','a')",
                    "INSERT INTO events VALUES (2,99,0,X'00','a')",
                    "INSERT INTO state_head VALUES (2,1,X'00','d')",
                    "INSERT INTO state_head VALUES (1,1,X'00','d')",
                    "INSERT INTO candle_commits SELECT 2,run_id,1,instrument,interval_seconds,candle_identity,input_json,input_hash,cumulative_input_hash,cumulative_event_hash,state_hash,'other' FROM candle_commits",
                    "INSERT INTO candle_commits SELECT 3,run_id,1,instrument,interval_seconds,'other',input_json,input_hash,cumulative_input_hash,cumulative_event_hash,state_hash,'other' FROM candle_commits"]:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
        db.execute("INSERT INTO events VALUES (2,1,1,X'00','b')")
        s.validate_schema(db)


def test_import_isolation():
    code = '''
import sys, builtins, io, os, socket, sqlite3, json, hashlib, typing, dataclasses
from datetime import datetime, timedelta
from decimal import Decimal
sys.path.insert(0, ROOT)
def deny(*a, **k): raise AssertionError('import-time IO')
real_import = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if level == 0 and name.split('.')[0] in {'broker','SmartApi','config','main','backtest','research','dotenv'}:
        raise AssertionError(name)
    return real_import(name, globals, locals, fromlist, level)
builtins.__import__ = guarded
builtins.open = io.open = os.getenv = sqlite3.connect = socket.socket = deny
import paper.offline.journal_codec
import paper.offline.journal_schema
'''.replace('ROOT', repr(str(Path(__file__).resolve().parents[1])))
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def unchecked_wire(record):
    """Build invalid record payloads without calling codec record validation."""
    def pack(value):
        if is_dataclass(value):
            return {'record': type(value).__name__, 'fields': {f.name: pack(getattr(value, f.name)) for f in fields(value)}}
        if type(value) is tuple:
            return {'tuple': [pack(v) for v in value]}
        return json.loads(c.encode(value))['value']
    return json.dumps({'version': 2, 'value': pack(record)}).encode()


def valid_state():
    engine = PaperEngine(config())
    return engine.process(candle(), Signal('BUY', D('2')))


def valid_position():
    return Position('BUY', 1, D('100'), D('100'), D('97'), D('104'), D('100'), STAMP, 'synthetic')


@pytest.mark.parametrize('record', [Account(D('-1'), reserved=D('-1')),
    Account(D('1'), projected_charges=D('-1')), Risk(closed_losses=D('-1')),
    Risk(day='20260105'), Intent('BUY', D('-1'), STAMP, 'synthetic'),
    Intent('BUY', D('0'), STAMP, 'synthetic'),
    *[replace(valid_position(), **{name: value}) for name, value in
      [('entry', D('-1')), ('raw_entry', D('0')), ('stop', D('0')), ('target', D('99')),
       ('stop', D('101')), ('quantity', 0), ('quantity', True), ('reserve', D('-1')), ('reserve', D('0'))]]])
def test_invalid_financial_records_both_directions(record):
    with pytest.raises(ValueError):
        c.encode(record)
    with pytest.raises(ValueError):
        c.decode(unchecked_wire(record))


@pytest.mark.parametrize('change', [
    {'events': (Event(2, STAMP, 'X', '', ()),)},
    {'events': (Event(1, STAMP, 'X', '', ()), Event(3, STAMP, 'X', '', ()))},
    {'events': (Event(1, STAMP, 'X', '', ()), Event(1, STAMP, 'X', '', ()))},
    {'utc_offset': timedelta(days=3)}, {'utc_offset': timedelta(days=-1)},
    {'last_timestamp': None}, {'last_timestamp': STAMP + timedelta(seconds=1)},
    {'risk': Risk(day='2026-01-06')}, {'processed': ()},
    {'processed': ((candle(), Signal('BUY', D('2'))),)*2},
    {'account': Account(D('1'), reserved=D('1'))},
    {'pending': Intent('SELL', D('2'), STAMP, 'synthetic')},
    {'position': valid_position()},
    {'events': (Event(1, STAMP + timedelta(seconds=1), 'X', '', ()),)}])
def test_local_state_inconsistency(change):
    record = replace(valid_state(), **change)
    with pytest.raises(ValueError):
        c.encode(record)
    with pytest.raises(ValueError):
        c.decode(unchecked_wire(record))


def test_negative_equity_and_zero_values_remain_valid():
    record = State(Account(D('-100000000000000000000.01'), net_closed_pnl=D('-5')), Risk(daily_net=D('-5')))
    assert c.decode(c.encode(record)) == record
    assert c.decode(c.encode(Signal('BUY', D('0')))) == Signal('BUY', D('0'))
    for side, gap in [('BUY', 1), ('SELL', 1000)]:
        engine = PaperEngine(config())
        engine.process(candle(), Signal(side, D('2')))
        engine.process(candle(STAMP + timedelta(seconds=300)), Signal('HOLD'))
        close = Candle(STAMP + timedelta(seconds=600), D(gap), D(max(gap, 100)), D(min(gap, 100)), D(gap), D('1'))
        state = engine.process(close, Signal('HOLD'))
        assert c.decode(c.encode(state)) == state
        if side == 'SELL':
            assert state.account.realized_equity < 0


def test_hostile_decimal_context():
    from decimal import ROUND_DOWN
    values = (config(), valid_state(), Account(D('-1e200'), D('1e300')),
              D('1e-1000'), D('-0'), D('123456789012345678901.2345'))
    baseline = [c.encode(v) for v in values]
    with localcontext() as ctx:
        ctx.prec = 1
        ctx.Emax = 2
        ctx.Emin = -2
        ctx.rounding = ROUND_DOWN
        ctx.clamp = 1
        for signal in ctx.traps:
            ctx.traps[signal] = True
        for value, wire in zip(values, baseline):
            assert c.encode(value) == wire
            assert c.decode(wire) == value
        with pytest.raises(ValueError):
            c.decode(b'{"version":2,"value":{"decimal":"garbage"}}')


@pytest.mark.parametrize('offset', [123, -123, 0, 86399999999, -86399999999, 19800000123, -19800000123])
def test_offset_microseconds_exact(offset):
    stamp = STAMP.replace(tzinfo=timezone(timedelta(microseconds=offset)))
    wire = c.encode(stamp)
    expected = ('{"value":{"datetime":"2026-01-05T09:15:01.123456","offset_us":' + str(offset) + '},"version":2}').encode()
    assert wire == expected
    restored = c.decode(wire)
    assert restored.utcoffset() == timedelta(microseconds=offset)
    assert restored.replace(tzinfo=None) == stamp.replace(tzinfo=None)
    assert restored.astimezone(timezone.utc) == stamp.astimezone(timezone.utc)


@pytest.mark.parametrize('tag', [
    {'datetime': '2026-01-01T00:00:00.000000', 'offset_us': 86400000000},
    {'datetime': '2026-01-01T00:00:00.000000', 'offset_us': -86400000000},
    {'datetime': '2026-01-01T00:00:00.000000', 'offset_us': True},
    {'datetime': '2026-01-01T00:00:00.000000', 'offset_us': 1.2},
    {'datetime': '2026-01-01T00:00:00.000000+00:00', 'offset_us': 0},
    {'datetime': '2026-01-01T00:00:00.000000+99:00', 'offset_us': 0},
    {'datetime': '20260101T00:00:00', 'offset_us': 0},
    {'datetime': '2026-01-01T00:00:00.000000'},
    {'datetime': '2026-01-01T00:00:00.000000', 'offset_us': 0, 'extra': 0}])
def test_malformed_timestamp_tags(tag):
    with pytest.raises(ValueError):
        c.decode(json.dumps({'version': 2, 'value': tag}).encode())


@pytest.mark.parametrize('sql', [
    'CREATE TABLE sqliteXhidden (x)', 'CREATE TABLE sqliteZsimilar (x)',
    'CREATE TABLE extra (x)', 'CREATE VIEW sqliteXview AS SELECT 1',
    'CREATE INDEX sqliteXindex ON events(event_hash)',
    'CREATE TRIGGER sqliteXtrigger AFTER INSERT ON events BEGIN SELECT 1; END',
    'ALTER TABLE events ADD COLUMN extra TEXT', 'DROP TRIGGER events_no_update',
    'DROP TABLE state_head'])
def test_schema_object_regressions(sql):
    with database() as db:
        db.execute(sql)
        with pytest.raises(ValueError):
            s.validate_schema(db)
        with pytest.raises(ValueError):
            s.initialize_schema(db)


def test_schema_altered_trigger_and_internal_objects():
    with database() as db:
        db.execute('ANALYZE')  # SQLite's own sqlite_stat1 is legitimate.
        s.validate_schema(db)
        db.execute('DROP TRIGGER events_no_update')
        db.execute('CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT 1; END')
        with pytest.raises(ValueError):
            s.validate_schema(db)
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE sqliteXhidden (x)')
        with pytest.raises(ValueError):
            s.initialize_schema(db)
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [('sqliteXhidden',)]


@pytest.mark.parametrize('table', ['events', 'candle_commits', 'run_metadata'])
@pytest.mark.parametrize('operation', ['UPDATE', 'DELETE', 'REPLACE'])
def test_immutable_rows(table, operation):
    with database() as db:
        seed(db)
        db.execute("INSERT INTO events VALUES (1,1,0,X'00','a')")
        before = db.execute('SELECT * FROM ' + table).fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            if operation == 'UPDATE':
                key = 'sequence' if table == 'events' else 'version' if table == 'candle_commits' else 'singleton'
                db.execute(f'UPDATE {table} SET {key} = {key}')
            elif operation == 'DELETE':
                db.execute('DELETE FROM ' + table)
            else:
                db.execute(f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}')
        assert db.execute('SELECT * FROM ' + table).fetchall() == before
        s.validate_schema(db)


def test_zero_event_commits_and_head_update():
    with database() as db:
        seed(db)
        db.execute("INSERT INTO candle_commits SELECT 2,1,1,instrument,interval_seconds,'instant-2',input_json,input_hash,cumulative_input_hash,cumulative_event_hash,state_hash,'second' FROM candle_commits WHERE version=1")
        db.execute("INSERT INTO state_head VALUES (1,1,X'00','d')")
        db.execute('UPDATE state_head SET commit_version=2')
        assert db.execute('SELECT COUNT(*) FROM events').fetchone() == (0,)
        s.validate_schema(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT OR REPLACE INTO candle_commits SELECT 3,1,2,instrument,interval_seconds,'instant-3',input_json,input_hash,cumulative_input_hash,cumulative_event_hash,state_hash,'e' FROM candle_commits WHERE version=1")


@pytest.mark.parametrize('fingerprint', [None, '', 'engine-v1garbage:sha256:x',
    'engine-v2:sha256:' + 'a'*64, 'engine-v01:sha256:' + 'a'*64,
    'engine-v1:sha256:' + 'A'*64, 'engine-v1:sha256:' + 'a'*63,
    'engine-v1:sha256:' + 'a'*65, 'engine-v1:sha256:' + 'a'*63+'g',
    'engine-v1:sha256:' + 'a'*64+'\x00hidden'])
def test_fingerprint_contract_matches_sql(fingerprint):
    with pytest.raises(ValueError):
        c.execution_policy_hash(config(), fingerprint)
    with database() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO run_metadata VALUES (1,2,?,?,?,?,?)', (b'{}','a','b','c',fingerprint))


@pytest.mark.parametrize('previous,version,count,events', [(None,2,2,0), ('a'*64,1,1,0),
    (None,True,1,0), (None,1,0,0), (None,1,True,0), (None,1,1,-1), (None,1,1,True)])
def test_commit_genesis_and_counts(previous, version, count, events):
    with pytest.raises(ValueError):
        c.commit_hash(previous, version, 'a'*64, c.empty_digest('event'), 'b'*64, 'c'*64,
                      processed_input_count=count, event_count=events)


def test_hash_counts_and_legacy_rejection():
    args = (None, 1, 'a'*64, 'b'*64, 'c'*64, 'd'*64)
    first = c.commit_hash(*args, processed_input_count=1, event_count=1)
    assert first != c.commit_hash(*args, processed_input_count=1, event_count=2)
    with pytest.raises(TypeError):
        c.commit_hash(*args)
    with pytest.raises(ValueError):
        c.decode(b'{"version":1,"value":null}')
    for previous, count in [(None,2), ('a'*64,1), (None,True), (None,0)]:
        with pytest.raises(ValueError):
            c.cumulative_digest('input', previous, 'b'*64, count=count)


def test_fixed_canonical_and_hash_vectors():
    # Values computed independently with JSON primitives and hashlib, without
    # importing the codec. Literal bytes pin separators, tags and field order.
    wire = b'{"value":{"tuple":[{"decimal":"123e-2"},"synthetic"]},"version":2}'
    assert c.encode((D('1.2300'), 'synthetic')) == wire
    assert c.decode(wire) == (D('1.23'), 'synthetic')
    assert c.digest('vector', (D('1.23'), 'synthetic')) == '4b8bd4a6a4b60bc5e325833ecc8469767b3061832a22e657cc7653044da16538'
    ei = '79d914db5b6ccdad971c131522a38bf947ac9ade131d7df29a6a5d6a81e34abc'
    ee = '02965de9f9a2215d056e31232f558a2f8c93b807d4739167a7d87589f8168ef5'
    ci = 'fafa2110475ae46dc69242e64e88712615de60f464b0aadcfd324799f306e307'
    assert c.empty_digest('input') == ei
    assert c.empty_digest('event') == ee
    assert c.cumulative_digest('input', None, 'a'*64, count=1) == ci
    assert c.commit_hash(None, 1, ci, ee, 'b'*64, 'c'*64,
                         processed_input_count=1, event_count=0) == 'b9dd894a1902bcc1c9fdc2c96ee5a55a5927595be42f08a5e4c19a81661a01b3'


@pytest.mark.parametrize('name', list(s.TRIGGERS))
def test_all_protection_triggers_required(name):
    with database() as db:
        db.execute('DROP TRIGGER ' + name)
        with pytest.raises(ValueError):
            s.validate_schema(db)


def test_schema_namespaces_do_not_hide_objects():
    with database() as db:
        db.execute('CREATE TABLE events_no_update (x)')
        with pytest.raises(ValueError):
            s.validate_schema(db)


def test_initialization_transaction_and_identity_guards():
    with sqlite3.connect(':memory:') as db:
        db.execute('PRAGMA user_version=1')
        with pytest.raises(ValueError):
            s.initialize_schema(db)
        assert db.execute('SELECT name FROM sqlite_master').fetchall() == []
    with sqlite3.connect(':memory:') as db:
        db.execute('PRAGMA application_id=123')
        with pytest.raises(ValueError):
            s.initialize_schema(db)
    with database() as db:
        seed(db)
        with pytest.raises(ValueError):
            s.initialize_schema(db)
        assert db.in_transaction


def test_existing_position_and_pending_consistency():
    engine = PaperEngine(config())
    engine.process(candle(), Signal('BUY', D('2')))
    state = engine.process(candle(STAMP + timedelta(seconds=300)), Signal('HOLD'))
    assert c.decode(c.encode(state)) == state
    for bad in [replace(state, account=replace(state.account, reserved=D('0'))),
                replace(state, risk=replace(state.risk, entries=0)),
                replace(state, position=replace(state.position, entry_timestamp=STAMP + timedelta(seconds=1)))]:
        with pytest.raises(ValueError):
            c.decode(unchecked_wire(bad))


def test_invalid_empty_hash_count_combinations():
    for inputs, events, count in [(c.empty_digest('input'), c.empty_digest('event'), 0),
                                   ('a'*64, c.empty_digest('event'), 1),
                                   ('a'*64, 'b'*64, 0)]:
        with pytest.raises(ValueError):
            c.commit_hash(None, 1, inputs, events, 'c'*64, 'd'*64,
                          processed_input_count=1, event_count=count)


@pytest.mark.parametrize('bad', ['\ud800', '\udfff', 'prefix\ud800suffix', '\udc00\ud800'])
@pytest.mark.parametrize('location', ['reason', 'kind', 'field_key', 'nested_value'])
def test_surrogates_reject_in_event_strings(bad, location):
    values = dict(sequence=1, timestamp=STAMP, kind='EXIT', reason='synthetic', fields=())
    raw = json.loads(c.encode(Event(**values)))
    if location in ('kind', 'reason'):
        values[location] = bad
        raw['value']['fields'][location] = bad
    elif location == 'field_key':
        values['fields'] = ((bad, D('1')),)
        raw['value']['fields']['fields'] = {'tuple': [{'tuple': [bad, {'decimal': '1e0'}]}]}
    else:
        values['fields'] = (('nested', (('text', (bad,)),)),)
        raw['value']['fields']['fields'] = {'tuple': [{'tuple': ['nested', {'tuple': [
            {'tuple': ['text', {'tuple': [bad]}]}]}]}]}
    # ensure_ascii emits escaped surrogates as bytes, without lossy replacement.
    payload = json.dumps(raw, ensure_ascii=True).encode('ascii')
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.decode(payload)
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.encode(Event(**values))
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.event_hash(Event(**values))


@pytest.mark.parametrize('bad', ['\ud800', '\udc00'])
def test_surrogates_reject_scalar_config_and_json_keys(bad):
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.decode(json.dumps({'version': 2, 'value': bad}).encode('ascii'))
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.encode(bad)
    raw = json.loads(c.encode(config()))
    raw['value']['fields']['instrument'] = bad
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.decode(json.dumps(raw).encode('ascii'))
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.encode(replace(config(), instrument=bad))
    with pytest.raises(ValueError, match='Unicode surrogate'):
        c.decode(json.dumps({'version': 2, 'value': None, bad: 0}).encode('ascii'))


@pytest.mark.parametrize('text', ['caf\u00e9', '\u03b1\u0915', '\U0001f680', '\U00010000\U0010ffff', 'e\u0301'])
def test_valid_unicode_decode_encode_hash_roundtrip(text):
    event = Event(1, STAMP, 'SYNTHETIC', text, ((text, ('nested', text)),))
    canonical = c.encode(event)
    # JSON surrogate-pair escapes for supplementary characters decode to the
    # original Unicode scalar, and canonical output uses its unchanged UTF-8.
    escaped = json.dumps(json.loads(canonical), ensure_ascii=True).encode('ascii')
    restored = c.decode(escaped, Event)
    assert restored == event
    assert restored.reason == text
    assert c.encode(restored) == canonical
    assert c.event_hash(restored) == c.event_hash(event)
    expected = ('{"value":' + json.dumps(text, ensure_ascii=False) + ',"version":2}').encode('utf-8')
    assert c.encode(text) == expected
    assert c.decode(expected) == text


def test_unicode_text_is_not_normalized():
    assert c.encode('\u00e9') != c.encode('e\u0301')
    assert c.decode(b'{"version":2,"value":"\\ud83d\\ude80"}') == '\U0001f680'


def test_explicit_utf8_initialization_and_fingerprint():
    with sqlite3.connect(':memory:') as db:
        db.execute("PRAGMA encoding='UTF-8'")
        s.initialize_schema(db)
        assert db.execute('PRAGMA main.encoding').fetchone() == ('UTF-8',)
        fingerprint = 'engine-v1:sha256:' + '0123456789abcdef'*4
        assert c.validate_engine_fingerprint(fingerprint) == fingerprint
        db.execute('INSERT INTO run_metadata VALUES (1,2,?,?,?,?,?)', (b'{}','a','b','c',fingerprint))
        s.validate_schema(db)
        assert db.execute('SELECT engine_fingerprint FROM run_metadata').fetchone() == (fingerprint,)


@pytest.mark.parametrize('encoding', ['UTF-16le', 'UTF-16be'])
@pytest.mark.parametrize('preexisting', [False, True])
def test_utf16_rejected_without_partial_initialization(encoding, preexisting):
    with sqlite3.connect(':memory:') as db:
        db.execute("PRAGMA encoding='" + encoding + "'")
        if preexisting:
            db.execute('CREATE TABLE sentinel (value TEXT)')
            db.execute("INSERT INTO sentinel VALUES ('preserved')")
            db.commit()
        before = db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        identity = (db.execute('PRAGMA application_id').fetchone(), db.execute('PRAGMA user_version').fetchone())
        foreign_keys = db.execute('PRAGMA foreign_keys').fetchone()
        for operation in (s.initialize_schema, s.validate_schema):
            with pytest.raises(ValueError, match='UTF-8 database encoding'):
                operation(db)
            assert db.execute('PRAGMA main.encoding').fetchone() == (encoding,)
            assert db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name').fetchall() == before
            assert (db.execute('PRAGMA application_id').fetchone(), db.execute('PRAGMA user_version').fetchone()) == identity
            assert db.execute('PRAGMA foreign_keys').fetchone() == foreign_keys
            assert not db.in_transaction
        if preexisting:
            assert db.execute('SELECT value FROM sentinel').fetchall() == [('preserved',)]


@pytest.mark.parametrize('fingerprint', ['engine-v1:sha256:' + 'a'*64+'\x00',
    'engine-v1:sha256:' + 'a'*30+'\x00'+'a'*34,
    'engine-v1:sha256:' + 'a'*63+'\u00e9'])
def test_character_level_fingerprint_rejection(fingerprint):
    with pytest.raises(ValueError):
        c.validate_engine_fingerprint(fingerprint)
    with database() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('INSERT INTO run_metadata VALUES (1,2,?,?,?,?,?)', (b'{}','a','b','c',fingerprint))
