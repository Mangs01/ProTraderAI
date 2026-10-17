"""Version 2 canonical wire format and hashes; pure, offline, no storage.

Decimals use coefficient/exponent text, removing trailing zeros and signed zero.
Timestamps preserve local wall time and the exact offset (not zone names/fold).
Cumulative digests fold one item at a time in supplied order, starting at None.
Engine fingerprints must be versioned content identities supplied by the caller;
a policy name is deliberately insufficient evidence of engine compatibility.
Malformed wire values and non-scalar Unicode strings raise ValueError. Text is
preserved exactly: no Unicode normalization or surrogate replacement occurs.
"""
import hashlib
import json
import re
from dataclasses import fields
from datetime import datetime, timedelta, timezone, date
from decimal import (Decimal, localcontext, Context, MAX_EMAX, MIN_EMIN,
                     ROUND_HALF_UP, InvalidOperation, DivisionByZero, Overflow)
from typing import get_type_hints, get_origin, get_args

from .config import Config, Costs
from .models import Candle, Signal, State, Account, Risk, Position, Intent, Event

VERSION = 2
DECIMAL_CONTEXT = Context(prec=80, rounding=ROUND_HALF_UP, Emin=MIN_EMIN,
                          Emax=MAX_EMAX, capitals=1, clamp=0, flags=[],
                          traps=[InvalidOperation, DivisionByZero, Overflow])


def validate_engine_fingerprint(value):
    """Caller assertion, not authentication. Only engine contract v1 is supported."""
    if type(value) is not str or not re.fullmatch(r'engine-v1:sha256:[0-9a-f]{64}', value):
        raise ValueError('Supported versioned engine content fingerprint required')
    return value
RECORDS = {c.__name__: c for c in
           (Config, Costs, Candle, Signal, State, Account, Risk, Position, Intent, Event)}


def decimal_text(value):
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError('Finite Decimal required')
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return '0'
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return ('-' if sign else '') + ''.join(map(str, digits)) + 'e' + str(exponent)


def _matches(value, hint):
    if get_origin(hint) is not None:
        return any(_matches(value, part) for part in get_args(hint))
    return type(value) is hint


def _validate(value):
    for f, hint in get_type_hints(type(value)).items():
        if not _matches(getattr(value, f), hint):
            raise ValueError('Incorrect field type: ' + f)
    if any(type(getattr(value, f.name)) is Decimal and not getattr(value, f.name).is_finite() for f in fields(value)):
        raise ValueError('Finite financial values required')
    if isinstance(value, (Position, Intent)) and value.side not in ('BUY', 'SELL'):
        raise ValueError('Invalid side')
    # Local invariants only. Historical accounting, replay and configuration-
    # dependent reconciliation belong to the future journal/recovery layer.
    if isinstance(value, Account) and (value.reserved < 0 or value.projected_charges < 0):
        raise ValueError('Negative reserve/charges')
    if isinstance(value, Intent) and value.atr <= 0:
        raise ValueError('Invalid pending ATR')
    if isinstance(value, Position):
        if value.quantity <= 0 or min(value.entry, value.raw_entry, value.stop, value.target, value.reserve) <= 0:
            raise ValueError('Invalid position values')
        if not (value.stop < value.entry < value.target if value.side == 'BUY' else value.target < value.entry < value.stop):
            raise ValueError('Invalid protective levels')
    if isinstance(value, Risk):
        if value.entries < 0 or value.closed_losses < 0:
            raise ValueError('Invalid risk values')
        if value.day is not None and date.fromisoformat(value.day).isoformat() != value.day:
            raise ValueError('Invalid risk day')
    if isinstance(value, Event):
        if value.sequence < 1 or not all(type(p) is tuple and len(p) == 2 and type(p[0]) is str for p in value.fields):
            raise ValueError('Invalid event fields/sequence')
        if len({p[0] for p in value.fields}) != len(value.fields):
            raise ValueError('Duplicate event field')
    if isinstance(value, State):
        if not all(type(p) is tuple and len(p) == 2 and type(p[0]) is Candle and type(p[1]) is Signal for p in value.processed):
            raise ValueError('Invalid processed inputs')
        if not all(type(e) is Event for e in value.events):
            raise ValueError('Invalid events')
        if any(e.sequence != i for i, e in enumerate(value.events, 1)):
            raise ValueError('Invalid event ordering')
        if value.utc_offset is not None and not -timedelta(days=1) < value.utc_offset < timedelta(days=1):
            raise ValueError('Invalid UTC offset')
        stamps = [p[0].timestamp for p in value.processed]
        if not stamps:
            if (value.last_timestamp is not None or value.utc_offset is not None or value.events
                    or value.position is not None or value.pending is not None or value.risk.day is not None
                    or value.account.reserved != 0 or value.account.unrealized_pnl != 0
                    or value.account.projected_charges != 0):
                raise ValueError('Inconsistent initial state')
        else:
            if value.last_timestamp is None or value.utc_offset is None:
                raise ValueError('Missing state timestamp identity')
            if any(t.utcoffset() != value.utc_offset for t in stamps + [value.last_timestamp]):
                raise ValueError('Inconsistent timestamp offsets')
            if value.last_timestamp != stamps[-1] or any(a >= b for a, b in zip(stamps, stamps[1:])):
                raise ValueError('Inconsistent processed ordering/head')
            if value.risk.day != stamps[-1].date().isoformat():
                raise ValueError('Inconsistent risk day')
            for event in value.events:
                if event.timestamp.utcoffset() != value.utc_offset or event.timestamp not in stamps:
                    raise ValueError('Event timestamp outside inputs')
            if any(a.timestamp > b.timestamp for a, b in zip(value.events, value.events[1:])):
                raise ValueError('Nonchronological events')
        if value.position is not None and value.pending is not None:
            raise ValueError('Position and pending intent coexist')
        if value.position is None:
            if any(v != 0 for v in (value.account.reserved, value.account.unrealized_pnl, value.account.projected_charges)):
                raise ValueError('Flat account has open-position values')
        else:
            p = value.position
            if (value.account.reserved != p.reserve or value.risk.entries < 1
                    or p.entry_timestamp.utcoffset() != value.utc_offset or p.entry_timestamp not in stamps
                    or p.entry_timestamp.date().isoformat() != value.risk.day):
                raise ValueError('Inconsistent position state')
        if value.pending is not None:
            p = value.pending
            if (p.signal_timestamp != value.last_timestamp or p.signal_timestamp.utcoffset() != value.utc_offset
                    or value.processed[-1][1].side != p.side or value.processed[-1][1].atr != p.atr):
                raise ValueError('Inconsistent pending state')


def _text(value):
    """Python strings must contain Unicode scalar values, including astral ones."""
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError('Unpaired Unicode surrogate')
    return value


def _pack(value):
    if type(value) is str:
        return _text(value)
    if value is None or type(value) in (int, bool):
        return value
    if type(value) is Decimal:
        return {'decimal': decimal_text(value)}
    if type(value) is datetime:
        if value.utcoffset() is None:
            raise ValueError('Aware timestamp required')
        offset = value.utcoffset()
        return {'datetime': value.replace(tzinfo=None).isoformat(timespec='microseconds'),
                'offset_us': (offset.days * 86400 + offset.seconds) * 1000000 + offset.microseconds}
    if type(value) is timedelta:
        return {'timedelta': (value.days * 86400 + value.seconds) * 1000000 + value.microseconds}
    if type(value) is tuple:
        return {'tuple': [_pack(v) for v in value]}
    if type(value) in RECORDS.values():
        _validate(value)
        return {'record': type(value).__name__, 'fields': {f.name: _pack(getattr(value, f.name)) for f in fields(value)}}
    raise ValueError('Unsupported value type')


def _unpack(value):
    if type(value) is str:
        return _text(value)
    if value is None or type(value) in (int, bool):
        return value
    if type(value) is not dict:
        raise ValueError('Invalid wire value')
    if set(value) == {'decimal'} and type(value['decimal']) is str:
        result = Decimal(value['decimal'])
        if decimal_text(result) != value['decimal']:
            raise ValueError('Noncanonical decimal')
        return result
    if (set(value) == {'datetime', 'offset_us'} and type(value['datetime']) is str
            and type(value['offset_us']) is int):
        result = datetime.fromisoformat(value['datetime'])
        if result.tzinfo is not None or result.isoformat(timespec='microseconds') != value['datetime']:
            raise ValueError('Invalid timestamp')
        return result.replace(tzinfo=timezone(timedelta(microseconds=value['offset_us'])))
    if set(value) == {'timedelta'} and type(value['timedelta']) is int:
        return timedelta(microseconds=value['timedelta'])
    if set(value) == {'tuple'} and type(value['tuple']) is list:
        return tuple(_unpack(v) for v in value['tuple'])
    if set(value) == {'record', 'fields'} and type(value['record']) is str and value['record'] in RECORDS:
        cls = RECORDS[value['record']]
        raw = value['fields']
        if type(raw) is not dict or set(raw) != {f.name for f in fields(cls)}:
            raise ValueError('Missing or unknown record fields')
        kwargs = {k: _unpack(v) for k, v in raw.items()}
        if any(not _matches(kwargs[k], h) for k, h in get_type_hints(cls).items()):
            raise ValueError('Incorrect record field type')
        with localcontext(DECIMAL_CONTEXT):
            result = cls(**kwargs)
        _validate(result)
        return result
    raise ValueError('Unknown wire tag/fields')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def encode(value):
    """Canonical UTF-8 bytes. Validate constructor contracts on encoding too."""
    with localcontext(DECIMAL_CONTEXT):
        packed = _pack(value)
        _unpack(packed)
        return _json({'version': VERSION, 'value': packed})


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _text(key)
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def decode(payload, expected_type=None):
    try:
        if type(payload) is not bytes:
            raise ValueError('UTF-8 bytes required')
        raw = json.loads(payload.decode('utf-8'), object_pairs_hook=_pairs,
                         parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        if type(raw) is not dict or set(raw) != {'version', 'value'} or type(raw['version']) is not int or raw['version'] != VERSION:
            raise ValueError('Unsupported envelope/version')
        with localcontext(DECIMAL_CONTEXT):
            result = _unpack(raw['value'])
        if expected_type is not None and type(result) is not expected_type:
            raise ValueError('Unexpected record type')
        return result
    except (TypeError, OverflowError, UnicodeError, ArithmeticError) as exc:
        raise ValueError('Invalid journal payload') from exc


def digest(domain, value):
    if type(domain) is not str or not domain:
        raise ValueError('Explicit domain required')
    return hashlib.sha256(encode(('ProTraderAI/journal/v2', domain, value))).hexdigest()


def _typed(domain, value, cls):
    if type(value) is not cls:
        raise ValueError('Incorrect hash input')
    return digest(domain, value)


def configuration_hash(config):
    return _typed('configuration', config, Config)


def input_contract_hash(config):
    if type(config) is not Config:
        raise ValueError('Config required')
    return digest('input-contract', (config.instrument, config.interval_seconds, 'aware-fixed-offset/microseconds/ohlcv/v1'))


def execution_policy_hash(config, engine_fingerprint):
    if type(config) is not Config:
        raise ValueError('Config required')
    validate_engine_fingerprint(engine_fingerprint)
    return digest('execution-policy', (configuration_hash(config), config.execution_policy, engine_fingerprint))


def input_hash(candle, signal):
    if type(candle) is not Candle or type(signal) is not Signal:
        raise ValueError('Candle and Signal required')
    return digest('candle-signal', (candle, signal))


def event_hash(event):
    return _typed('event', event, Event)


def state_hash(state):
    if type(state) is not State:
        raise ValueError('State required')
    return digest('state', (VERSION, len(state.processed), len(state.events), state))


def _hash(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('SHA-256 hex required')
    return value


def cumulative_digest(kind, previous, item_hash, *, count):
    """None seeds an empty sequence; count is the resulting sequence length.

Use empty_digest(kind) for an empty sequence and fold its result thereafter.
No sorting, deduplication or implicit reset occurs.
"""
    if kind not in ('input', 'event') or type(count) is not int or count < 1:
        raise ValueError('Invalid cumulative domain')
    if (count == 1 and previous not in (None, empty_digest(kind))) or (count > 1 and (previous is None or previous == empty_digest(kind))):
        raise ValueError('Invalid cumulative predecessor/count')
    return digest('cumulative-' + kind, (VERSION, count, empty_digest(kind) if previous is None else _hash(previous), _hash(item_hash)))


def empty_digest(kind):
    if kind not in ('input', 'event'):
        raise ValueError('Invalid cumulative domain')
    return digest('empty-' + kind, ())


def commit_hash(previous, version, input_digest, event_digest, state_digest, contract_digest, *, processed_input_count, event_count):
    """One candle per commit: genesis is version/count 1 with null parent.

    Cumulative event count may be zero. Caller verifies that the predecessor's
    version/counts and digests match history; hashes are not authentication.
"""
    if type(version) is not int or version < 1:
        raise ValueError('Positive commit version required')
    if (previous is None) != (version == 1):
        raise ValueError('Genesis alone requires null predecessor')
    if (type(processed_input_count) is not int or processed_input_count != version
            or type(event_count) is not int or event_count < 0):
        raise ValueError('One input per commit; nonnegative event count required')
    if (event_count == 0) != (event_digest == empty_digest('event')):
        raise ValueError('Invalid empty event digest/count')
    if input_digest == empty_digest('input'):
        raise ValueError('A commit must include an input')
    return digest('commit-chain', (VERSION, None if previous is None else _hash(previous), version,
                                 processed_input_count, event_count,
                                 *map(_hash, (input_digest, event_digest, state_digest, contract_digest))))
