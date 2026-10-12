"""Focused Phase28B contract tests; synthetic identities and frozen local audits."""
import copy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import pytest
from research import phase28b_selection as b

HISTORY = [(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(252)]
LIQUIDITY = HISTORY[-60:]

def isin(number):
    prefix = 'INE' + f'{number:03d}' + 'A0100'
    return next(prefix + str(i) for i in range(10) if b.a.valid_isin(prefix + str(i)))

def rows(number=0, symbol='TEST', value='1'):
    return [dict(session_date=d, isin=isin(number), symbol=symbol, instrument_type='STK', series='EQ',
        traded_value=value, source_sha256='synthetic', source_reference='synthetic') for d in HISTORY + [b.a.SEL]]

def evaluate(data):
    return b.evaluate(data, HISTORY, LIQUIDITY)

def test_selection_universe_reproduced_from_corrected_rows():
    result = b.a.load(b.ar.META / 'result.json')
    path = b.a.ROOT / result['derived']['path']
    if not path.exists(): pytest.skip('local frozen bulk data unavailable')
    with path.open(encoding='utf-8', newline='') as stream:
        import csv
        selected = [r for r in csv.DictReader(stream) if r['session_date'] == b.a.SEL]
    assert len(selected) == len({r['isin'] for r in selected}) == 1838
    assert all(r['instrument_type']=='STK' and r['series']=='EQ' and b.a.valid_isin(r['isin']) for r in selected)
    assert all(Decimal(r['traded_value']) > 0 for r in selected)
    assert b.a.load(b.META/'precheck.json')['selection_statistics']['source_rows'] == 2867

def test_exact_history_and_no_forward_fill():
    data = rows()
    assert evaluate(data)[0][0]['eligible']
    data.pop(0)
    record = evaluate(data)[0][0]
    assert record['history_observation_count'] == 251
    assert record['missing_history_sessions'] == [HISTORY[0]]
    assert record['exclusion_reasons'] == ['MISSING_REQUIRED_252_HISTORY']
    assert len(data) == 252

def test_exact_liquidity():
    data = [r for r in rows() if r['session_date'] != LIQUIDITY[5]]
    record = evaluate(data)[0][0]
    assert record['liquidity_observation_count'] == 59
    assert 'MISSING_REQUIRED_60_LIQUIDITY' in record['exclusion_reasons']
    assert record['median_60_session_traded_value'] is None

@pytest.mark.parametrize('values', [['1']*59, ['1']*61, ['NaN']*60, ['Infinity']*60, ['-1']*60])
def test_median_invalid_inputs(values):
    with pytest.raises(ValueError): b.exact_median(values)

def test_exact_decimal_even_median():
    assert b.exact_median(['0.1']*30 + ['0.2']*30) == Decimal('0.15')
    assert b.exact_median([str(i) for i in range(60)]) == Decimal('29.5')

@pytest.mark.parametrize('bad', ['', 'NaN', 'Infinity', '-1'])
def test_invalid_liquidity_excludes(bad):
    data = rows()
    data[-2]['traded_value'] = bad
    assert 'INVALID_CANONICAL_TRADED_VALUE' in evaluate(data)[0][0]['exclusion_reasons']

def test_ranking_and_ties():
    candidates = [dict(isin='B',symbol='Z',median_60_session_traded_value='10'),
        dict(isin='A',symbol='Z',median_60_session_traded_value='10'),
        dict(isin='A',symbol='A',median_60_session_traded_value='10'),
        dict(isin='Z',symbol='A',median_60_session_traded_value='11')]
    assert [(r['isin'],r['symbol']) for r in sorted(candidates,key=b.ranking_key)] == [('Z','A'),('A','A'),('A','Z'),('B','Z')]

def test_stable_isin_rename_preserves_identity():
    data = rows()
    for r in data[100:]: r['symbol']='RENAMED'
    audit, identity, ranking = evaluate(data)
    assert audit[0]['eligible'] and len(ranking) == 1
    assert [s['symbol'] for s in identity[0]['observed_symbol_history']] == ['TEST','RENAMED']
    assert identity[0]['observed_symbol_history'][1]['first_observed'] == HISTORY[100]

def test_different_isins_never_spliced_even_when_symbol_reused():
    data = rows(0)[:100] + rows(1)[100:]
    audit, identities, ranking = evaluate(data)
    assert len(audit) == 1 and audit[0]['history_observation_count'] == 152
    assert audit[0]['exclusion_reasons'] == ['MISSING_REQUIRED_252_HISTORY']
    assert identities[0]['symbol_other_isins'] and not identities[0]['material_ambiguities']
    assert ranking == []

def test_concurrent_identity_ambiguity_fails_closed():
    audit, _, ranking = evaluate(rows(0) + rows(1))
    assert not ranking
    assert all('UNRESOLVED_MATERIAL_SYMBOL_ISIN_CONTINUITY' in r['exclusion_reasons'] for r in audit)

def test_duplicate_isin_observation_fails():
    with pytest.raises(ValueError,match='duplicate'): evaluate(rows() + rows()[:1])

def test_future_observations_forbidden():
    data = rows()
    data.append(dict(data[0], session_date='2026-01-01'))
    with pytest.raises(ValueError,match='future'): evaluate(data)

def test_selection_requires_current_presence():
    assert evaluate(rows()[:-1]) == ([], [], [])

def test_exact_24_no_replacement_and_repeatability():
    data = [row for i in range(25) for row in rows(i, 'TEST'+str(i), str(100-i))]
    ranking = evaluate(data)[2]
    selected = b.select(ranking)
    assert len(selected) == 24 and selected[-1]['isin'] == isin(23)
    assert selected == b.select(evaluate(list(reversed(data)))[2])
    with pytest.raises(ValueError): b.select(ranking[:23])
    # No later-availability input exists: frozen chosen identities persist.
    unavailable_later = {isin(0)}
    assert selected[0]['isin'] in unavailable_later
    assert isin(24) not in {r['isin'] for r in selected}

def test_deterministic_16_8_split():
    cohort = [dict(isin=isin(i),rank=i+1) for i in range(24)]
    split = b.split(cohort)
    expected = sorted(cohort,key=lambda r: (hashlib.sha256((b.a.P26+':'+r['isin']).encode()).hexdigest(),r['isin']))
    assert [r['isin'] for r in split] == [r['isin'] for r in expected]
    assert [r['stratum'] for r in split] == ['VISIBLE']*16+['WITHHELD']*8
    assert b.split(list(reversed(cohort))) == split

def test_contamination_has_no_selection_input():
    data = rows()
    for r in data: r.update(isin='INE062A01020',symbol='SBIN')
    assert evaluate(data)[0][0]['eligible']
    assert evaluate(data)[2][0]['symbol'] == 'SBIN'

def test_input_hash_mismatch_fails_closed():
    with pytest.raises(ValueError,match='hash mismatch'): b.check_hash('wrong',b.EXPECTED['derived'],'derived')

def test_failed_precheck_cannot_select(monkeypatch):
    def fail(): raise ValueError('input hash mismatch')
    def forbidden(*args): pytest.fail('selection reached after failed precheck')
    monkeypatch.setattr(b,'precheck',fail)
    monkeypatch.setattr(b,'outputs',forbidden)
    # Avoid changing process-wide sockets in this isolated control-flow test.
    monkeypatch.setattr(b.socket.socket,'connect',b.socket.socket.connect)
    monkeypatch.setattr(b.socket,'create_connection',b.socket.create_connection)
    with pytest.raises(ValueError,match='hash mismatch'): b.run()

def test_frozen_hash_and_repeatability_audit():
    manifest=b.a.load(b.META/'cohort_selection_manifest.json')
    repeat=b.a.load(b.META/'repeatability_audit.json')
    assert b.a.sha(b.a.canonical(manifest['canonical_binding'])) == manifest['phase28b_selection_sha256'] == repeat['phase28b_selection_sha256']
    assert repeat['status']=='PASS'
    assert len(manifest['cohort'])==24
    assert b.a.load(b.META/'future_intraday_request_manifest.json')['requests']==[]


def test_decimal_ranking_preserves_arbitrary_precision():
    high = dict(isin='Z',symbol='Z',median_60_session_traded_value='10000000000000000000000000000.02')
    low = dict(isin='A',symbol='A',median_60_session_traded_value='10000000000000000000000000000.01')
    assert sorted([low,high],key=b.ranking_key) == [high,low]
    assert b.exact_median([high['median_60_session_traded_value']]*30+[low['median_60_session_traded_value']]*30) == Decimal('10000000000000000000000000000.015')
