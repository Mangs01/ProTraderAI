"""Explicit SQLite foundation only. Import performs no I/O.

Call initialization outside a transaction; foreign-key enforcement is required
on every connection. No journal processing or recovery is provided here.
Only UTF-8 database encoding is supported. Initialization verifies the effective
encoding before any changes; it never migrates or re-encodes a supplied database.
"""
import sqlite3

SCHEMA_VERSION = 2
APPLICATION_ID = 0x50544149
TABLES = {
    'run_metadata': '''CREATE TABLE run_metadata (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        schema_version INTEGER NOT NULL CHECK(schema_version = 2),
        config_json BLOB NOT NULL, config_hash TEXT NOT NULL,
        input_contract_hash TEXT NOT NULL, execution_contract_hash TEXT NOT NULL,
        engine_fingerprint TEXT NOT NULL CHECK(typeof(engine_fingerprint) = 'text'
          AND length(engine_fingerprint) = 81
          AND instr(engine_fingerprint, char(0)) = 0
          AND substr(engine_fingerprint, 1, 17) = 'engine-v1:sha256:'
          AND substr(engine_fingerprint, 18) NOT GLOB '*[^0-9a-f]*')
    )''',
    'candle_commits': '''CREATE TABLE candle_commits (
        version INTEGER PRIMARY KEY CHECK(typeof(version) = 'integer' AND version >= 1),
        run_id INTEGER NOT NULL DEFAULT 1 CHECK(run_id = 1) REFERENCES run_metadata(singleton),
        parent_version INTEGER UNIQUE REFERENCES candle_commits(version),
        instrument TEXT NOT NULL, interval_seconds INTEGER NOT NULL CHECK(interval_seconds > 0),
        candle_identity TEXT NOT NULL, input_json BLOB NOT NULL,
        input_hash TEXT NOT NULL, cumulative_input_hash TEXT NOT NULL,
        cumulative_event_hash TEXT NOT NULL, state_hash TEXT NOT NULL,
        commit_hash TEXT NOT NULL UNIQUE,
        CHECK((version = 1 AND parent_version IS NULL) OR
              (version > 1 AND parent_version IS NOT NULL AND parent_version = version - 1)),
        UNIQUE(instrument, interval_seconds, candle_identity)
    )''',
    'state_head': '''CREATE TABLE state_head (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1) REFERENCES run_metadata(singleton),
        commit_version INTEGER NOT NULL UNIQUE REFERENCES candle_commits(version),
        state_json BLOB NOT NULL, state_hash TEXT NOT NULL,
        CHECK(commit_version >= 1)
    )''',
    'events': '''CREATE TABLE events (
        sequence INTEGER PRIMARY KEY CHECK(typeof(sequence) = 'integer' AND sequence >= 1),
        commit_version INTEGER NOT NULL REFERENCES candle_commits(version),
        event_index INTEGER NOT NULL CHECK(typeof(event_index) = 'integer' AND event_index >= 0),
        event_json BLOB NOT NULL, event_hash TEXT NOT NULL,
        UNIQUE(commit_version, event_index)
    )''',
}

TRIGGERS = {
    'events_order': '''CREATE TRIGGER events_order BEFORE INSERT ON events BEGIN
        SELECT CASE WHEN NEW.sequence != COALESCE((SELECT MAX(sequence) FROM events), 0) + 1
          OR NEW.event_index != (SELECT COUNT(*) FROM events WHERE commit_version = NEW.commit_version)
          OR NEW.commit_version < COALESCE((SELECT MAX(commit_version) FROM events), NEW.commit_version)
          THEN RAISE(ABORT, 'event order') END;
    END''',
}

# Immutable rows cannot be changed by UPDATE/DELETE or INSERT OR REPLACE,
# including when SQLite recursive_triggers is disabled (its usual default).
for _table, _key in (('run_metadata', 'singleton'), ('candle_commits', 'version'), ('events', 'sequence')):
    for _operation in ('UPDATE', 'DELETE'):
        _name = _table + '_no_' + _operation.lower()
        TRIGGERS[_name] = (f'CREATE TRIGGER {_name} BEFORE {_operation} ON {_table} BEGIN '
                           "SELECT RAISE(ABORT, 'immutable journal row'); END")
    _name = _table + '_no_replace'
    TRIGGERS[_name] = (f'CREATE TRIGGER {_name} BEFORE INSERT ON {_table} '
                       f'WHEN EXISTS (SELECT 1 FROM {_table} WHERE {_key} = NEW.{_key}) BEGIN '
                       "SELECT RAISE(ABORT, 'immutable journal identity'); END")
TRIGGERS['commits_no_unique_replace'] = '''CREATE TRIGGER commits_no_unique_replace
    BEFORE INSERT ON candle_commits WHEN EXISTS (
      SELECT 1 FROM candle_commits WHERE commit_hash = NEW.commit_hash
      OR parent_version = NEW.parent_version
      OR (instrument = NEW.instrument AND interval_seconds = NEW.interval_seconds
          AND candle_identity = NEW.candle_identity)) BEGIN
    SELECT RAISE(ABORT, 'immutable commit identity'); END'''


def _connection(connection):
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError('Explicit sqlite3 connection required')


def _encoding(connection):
    if connection.execute('PRAGMA main.encoding').fetchone()[0] != 'UTF-8':
        raise ValueError('Journal requires UTF-8 database encoding')


def _normalize(sql):
    # Exact comparison preserves whitespace inside SQL literals as well.
    return sql.strip().rstrip(';')


def _objects(connection):
    # SQLite reserves the literal sqlite_ prefix. LIKE's underscore wildcard
    # would also hide user objects such as sqliteXhidden.
    return [(kind, name, sql) for kind, name, sql in connection.execute('SELECT type, name, sql FROM sqlite_master')
            if not name.startswith('sqlite_')]


def validate_schema(connection):
    """Reject version, application, definition, FK and integrity mismatches."""
    _connection(connection)
    _encoding(connection)
    if connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
        raise ValueError('Wrong application ID')
    if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        raise ValueError('Unsupported schema version')
    if connection.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
        raise ValueError('Foreign keys must be enabled')
    actual = {(kind, name): _normalize(sql) for kind, name, sql in _objects(connection)}
    expected = {('table', k): _normalize(v) for k, v in TABLES.items()}
    expected.update({('trigger', k): _normalize(v) for k, v in TRIGGERS.items()})
    if actual != expected:
        raise ValueError('Schema definition mismatch')
    if connection.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Foreign key violation')
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('Integrity failure')


def initialize_schema(connection):
    """Initialize an empty supplied database, or strictly validate an existing one.

Never commits an existing caller transaction. Failure rolls back all DDL.
"""
    _connection(connection)
    _encoding(connection)
    if connection.in_transaction:
        raise ValueError('Initialization requires no active transaction')
    connection.execute('PRAGMA foreign_keys = ON')
    if _objects(connection):
        validate_schema(connection)
        return
    if connection.execute('PRAGMA user_version').fetchone()[0] or connection.execute('PRAGMA application_id').fetchone()[0]:
        raise ValueError('Refusing nonempty database identity')
    connection.execute('BEGIN')
    try:
        for sql in (*TABLES.values(), *TRIGGERS.values()):
            connection.execute(sql)
        connection.execute('PRAGMA application_id = ' + str(APPLICATION_ID))
        connection.execute('PRAGMA user_version = ' + str(SCHEMA_VERSION))
        validate_schema(connection)
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
