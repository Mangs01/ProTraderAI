"""Offline tests for the versioned Phase28A-R calendar input repair."""
import copy
from pathlib import Path
import pytest
from research import phase28a_daily as a
from research import phase28ar_daily as r

@pytest.fixture
def inputs():
    original=a.load(a.ROOT/'research/phase27_calendar_manifest.json')['calendar']
    evidence=a.load(r.META/'evidence.json')
    corrected,changes=r.recompute(original,evidence)
    plan=r.make_plan(corrected,a.load(a.ROOT/'research/phase27_bhavcopy_acquisition_plan.json')['plan'])
    return original,evidence,corrected,changes,plan


def test_authoritative_holiday_exclusion_and_only_two_changes(inputs):
    original,evidence,corrected,changes,plan=inputs
    before={x['date']:x for x in original['rows']}
    after={x['date']:x for x in corrected['rows']}
    assert {d for d in before if before[d]!=after[d]}==r.DEFECTS
    for day in r.DEFECTS:
        assert after[day]['session_type']=='HOLIDAY'
        assert after[day]['status']=='NON_TRADING' and not after[day]['normal']
        assert day not in corrected['history']['dates']
        assert all(q['date']!=day for q in plan['requests'])
    assert corrected['special_sessions']==original['special_sessions']
    assert evidence['holidays']['2024-01-22']['reference'].startswith('NSE/SURV/60342')
    assert 'not inferred from bank/settlement' in evidence['holidays']['2024-01-22']['evidence_basis']


def test_deterministic_252_and_exact_replacements(inputs):
    original,evidence,c,changes,plan=inputs
    assert r.recompute(original,evidence)==(c,changes)
    assert changes['removed_dates']==['2024-01-22','2024-05-20']
    assert changes['added_dates']==['2023-09-05','2023-09-06']
    assert c['history']['count']==252
    assert c['history']['first']=='2023-09-05' and c['history']['last']=='2024-09-16'
    assert c['history']['dates']==['2023-09-05','2023-09-06']+[d for d in original['history']['dates'] if d not in r.DEFECTS]
    assert c['liquidity']==original['liquidity'] and not changes['liquidity_changed']
    assert c['liquidity']['list_hash']==a.LIQ
    for key in ['selection','T_NEW','stages','normal_grid','special_sessions']:
        assert c[key]==original[key]
    assert len(plan['requests'])==len({q['date'] for q in plan['requests']})==253
    assert sum(q['date']==a.SEL for q in plan['requests'])==1
    r.enforce(c,plan)


@pytest.mark.parametrize('kind',['missing','duplicate','holiday','bad_binding','250'])
def test_corrected_plan_exactness_rejections(inputs,kind):
    _,_,c,_,p=copy.deepcopy(inputs)
    if kind=='missing': p['requests'].pop()
    if kind=='duplicate': p['requests'][1]=p['requests'][0]
    if kind=='holiday': p['requests'][0]['date']='2024-01-22'
    if kind=='bad_binding': p['calendar_sha256']='bad'
    if kind=='250': c['history']=r.window(c['history']['dates'][2:])
    with pytest.raises(ValueError): r.enforce(c,p)


def test_original_phase26_27_and_blocked_audit_unchanged():
    before=a.load(r.META/'preservation_before.json')['files']
    for path,digest in before.items():
        assert a.sha((a.ROOT/path).read_bytes())==digest,path
    assert a.load(r.OLD_META/'result.json')['status']=='BLOCKED'
    assert a.load(r.OLD_META/'result.json')['raw_hash_manifest_sha256']==r.OLD_RAW_HASH


def test_reuse_reads_valid_official_bytes_without_network(tmp_path):
    day='2024-09-16'
    req=dict(date=day,format='UDIFF',filename=a.filename(day,'UDIFF'))
    data=(a.ROOT/'research/metadata/phase25/raw/nse_bhavcopy_20240916.zip').read_bytes()
    schema=a.load(a.ROOT/'research/phase26_schema_mapping.json')['schema']
    rows,stats=a.validate(data,req,schema)
    entry=dict(date=day,filename=req['filename'],url=a.source_url(req),http_status=200,acquired_utc='2026-09-20T00:00:00Z',sha256=a.sha(data),bytes=len(data),validation=stats)
    path=tmp_path/req['filename']
    path.write_bytes(data)
    assert r.verified_rows(entry,req,schema,tmp_path)==rows
    path.write_bytes(data+b'tampered')
    with pytest.raises(ValueError,match='hash/length'):
        r.verified_rows(entry,req,schema,tmp_path)


def test_download_only_mechanical_additions(inputs):
    _,_,_,changes,p=inputs
    existing=[dict(date=q['date']) for q in p['requests'] if q['date'] not in changes['added_dates']]
    assert len(existing)==251
    todo=r.new_only(p,existing,changes['added_dates'])
    assert [q['date'] for q in todo]==['2023-09-05','2023-09-06']
    with pytest.raises(ValueError,match='no redownload authorized'):
        r.new_only(p,existing[:-1],changes['added_dates'])
    assert r.new_only(p,[dict(date=q['date']) for q in p['requests']],changes['added_dates'])==[]


def fake_index(plan):
    return [dict(date=q['date'],sha256=a.sha(q['date'].encode())) for q in plan['requests']]


def test_derived_layer_requires_complete_coverage(inputs,tmp_path):
    _,_,c,_,p=inputs
    dest=tmp_path/'must_not_exist'
    with pytest.raises(ValueError,match='coverage'):
        r.write_layer(c,p,fake_index(p)[:-1],{},dest)
    assert not dest.exists()


def test_no_synthetic_holiday_rows_or_forward_fill(inputs,tmp_path,monkeypatch):
    _,_,c,_,p=inputs
    monkeypatch.setattr(a,'ROOT',tmp_path)
    monkeypatch.setattr(r,'META',tmp_path/'metadata')
    absent=p['requests'][0]['date']
    def rows(entry,req,schema):
        # One identity is observed on every date except the first, never filled.
        row=dict(zip(a.FIELDS,[req['date'],'INE062A01020','SBIN','EQ','STK','10.00',req['format'],entry['sha256'],'raw/reference']))
        result=[row]
        if req['date']!=absent:
            result.append(dict(row,isin='INE002A01018',symbol='RELIANCE'))
        return result
    monkeypatch.setattr(r,'verified_rows',rows)
    dest=tmp_path/'derived'
    result=r.write_layer(c,p,fake_index(p),{},dest)
    data=list(a.csv.DictReader((dest/'daily_stk_eq_phase28ar_v1.csv').open(encoding='utf-8',newline='')))
    assert len(data)==505==result['rows']
    assert result['unique_sessions']==253 and result['unique_isins']==2
    assert not r.DEFECTS.intersection(row['session_date'] for row in data)
    assert sum(row['isin']=='INE002A01018' for row in data)==252
    assert result['complete_252_observations']==1
    assert result['synthetic_rows']==result['forward_fills']==result['cohort_selections']==0
    assert r.write_layer(c,p,fake_index(p),{},dest)==result


def test_out_of_scope_extension_or_unproven_holiday_blocks(inputs):
    original,evidence,_,_,_=inputs
    bad=copy.deepcopy(evidence)
    bad['holidays']['2024-01-22']['market']='Bank settlement'
    with pytest.raises(ValueError,match='equity holiday not proven'):
        r.recompute(original,bad)
    bad=copy.deepcopy(evidence)
    bad['extension_calendar']['supported_first']='2023-09-06'
    with pytest.raises(ValueError,match='exceeds authoritative'):
        r.recompute(original,bad)
