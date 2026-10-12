"""Offline Phase28A tests; preserved official evidence is read-only."""
import collections
import copy
import csv
import io
import zipfile
from pathlib import Path
import pytest
from research import phase28a_daily as m

SCHEMA=m.load(m.ROOT/'research/phase26_schema_mapping.json')['schema']

def req(day='2024-09-16',fmt='UDIFF'):
    return dict(date=day,format=fmt,filename=m.filename(day,fmt))

def sample(day='20240916'):
    return (m.ROOT/f'research/metadata/phase25/raw/nse_bhavcopy_{day}.zip').read_bytes()

def edited(payload,change):
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        name=z.namelist()[0]
        rows=list(csv.reader(io.StringIO(z.read(name).decode('utf-8-sig'))))
    change(rows)
    out=io.StringIO(newline='')
    csv.writer(out,lineterminator='\n').writerows(rows)
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(name,out.getvalue())
    return result.getvalue()

@pytest.mark.parametrize('day,fmt,count',[('20230915','LEGACY',1699),('20240913','UDIFF',1836),('20240916','UDIFF',1845)])
def test_official_schema_mapping_and_provenance(day,fmt,count):
    request=req(day[:4]+'-'+day[4:6]+'-'+day[6:],fmt)
    payload=sample(day)
    rows,stats=m.validate(payload,request,SCHEMA)
    assert len(rows)==count==stats['unique_isins']
    assert stats['duplicate_isins']==0
    assert {r['instrument_type'] for r in rows}=={'STK'}
    assert {r['series'] for r in rows}=={'EQ'}
    assert {r['source_sha256'] for r in rows}=={m.sha(payload)}
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        original=list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))
    source={r['ISIN']:r for r in original if r.get('SctySrs',r.get('SERIES'))=='EQ'}
    field='TOTTRDVAL' if fmt=='LEGACY' else 'TtlTrfVal'
    assert all(m.Decimal(r['traded_value'])==m.Decimal(source[r['isin']][field]) for r in rows)

@pytest.mark.parametrize('payload',[b'<html>error</html>',b'{"error":"denied"}',b'PK\x03\x04bad',b''])
def test_malformed_html_error_rejection(payload):
    with pytest.raises(m.ValidationError):
        m.validate(payload,req(),SCHEMA)

@pytest.mark.parametrize('kind',['date','bizdate','value','isin','missing_value','column','duplicate'])
def test_fail_closed_rows(kind):
    def change(rows):
        headers=rows[0]
        row=next(r for r in rows[1:] if r[headers.index('SctySrs')]=='EQ')
        if kind=='duplicate':
            rows.append(row[:])
        elif kind=='column':
            row.pop()
        else:
            field,value={'date':('TradDt','2024-09-13'),'bizdate':('BizDt','2024-09-13'),'value':('TtlTrfVal','NaN'),'isin':('ISIN',''),'missing_value':('TtlTrfVal','')}[kind]
            row[headers.index(field)]=value
    with pytest.raises(m.ValidationError):
        m.validate(edited(sample(),change),req(),SCHEMA)

def test_non_stk_eq_filtered():
    def change(rows):
        h=rows[0]
        row=next(r for r in rows[1:] if r[h.index('SctySrs')]=='EQ')
        row[h.index('FinInstrmTp')]='FUT'
    rows,stats=m.validate(edited(sample(),change),req(),SCHEMA)
    assert len(rows)==1844
    assert stats['source_rows']==2899

def test_duplicate_isin_different_symbol_rejected():
    def change(rows):
        h=rows[0]
        row=next(r[:] for r in rows[1:] if r[h.index('SctySrs')]=='EQ')
        row[h.index('TckrSymb')]='DIFFERENT'
        rows.append(row)
    with pytest.raises(m.ValidationError,match='duplicate'):
        m.validate(edited(sample(),change),req(),SCHEMA)

def test_exact_session_enforcement():
    c=m.load(m.ROOT/'research/phase27_calendar_manifest.json')['calendar']
    p=m.load(m.ROOT/'research/phase27_bhavcopy_acquisition_plan.json')['plan']
    m.enforce_sessions(c,p)
    for change in ['drop','duplicate','shift','special']:
        cc,pp=copy.deepcopy(c),copy.deepcopy(p)
        if change=='drop': pp['requests'].pop()
        if change=='duplicate': pp['requests'][-1]=pp['requests'][0]
        if change=='shift': pp['requests'][0]['date']='2023-09-08'
        if change=='special': cc['rows'][0]['normal']=False
        with pytest.raises(ValueError): m.enforce_sessions(cc,pp)

def test_atomic_immutable_and_failure(tmp_path,monkeypatch):
    p=tmp_path/'raw.zip'
    m.atomic(p,b'original',True)
    m.atomic(p,b'original',True)
    with pytest.raises(ValueError): m.atomic(p,b'changed',True)
    assert p.read_bytes()==b'original'
    q=tmp_path/'new.zip'
    def fail(*args): raise OSError('simulated interruption')
    monkeypatch.setattr(m.os,'replace',fail)
    with pytest.raises(OSError): m.atomic(q,b'body')
    assert not q.exists() and not q.with_name(q.name+'.partial').exists()

class Response:
    def __init__(self,payload,status=200):
        self.payload=payload
        self.status_code=status
        self.headers={'Content-Length':str(len(payload))}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,size): yield self.payload

class Session:
    def __init__(self,responses): self.responses=iter(responses)
    def get(self,url,**kwargs):
        assert url.startswith('https://nsearchives.nseindia.com/')
        assert kwargs['allow_redirects'] is False
        return next(self.responses)

def test_acquisition_retry_raw_hash(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'RAW',tmp_path)
    # validate source references against the actual repository root via a wrapper.
    original=m.validate
    def validate(payload,request,schema):
        monkeypatch.setattr(m,'RAW',m.ROOT/'research/data/new_cycle_001/raw/bhavcopy')
        result=original(payload,request,schema)
        monkeypatch.setattr(m,'RAW',tmp_path)
        return result
    monkeypatch.setattr(m,'validate',validate)
    counters,events=collections.Counter(),[]
    result,rows=m.acquire(req(),SCHEMA,Session([Response(b'error',503),Response(sample())]),counters,events,sleep=lambda _:None)
    assert counters['official_file_requests']==2 and counters['retries']==1
    assert counters['successes']==1 and counters['non_200_responses']==1
    assert (tmp_path/req()['filename']).read_bytes()==sample()
    assert result['sha256']==m.sha(sample()) and result['http_status']==200
    assert rows and len(events)==2

def test_acquisition_rejects_partial_payload(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'RAW',tmp_path)
    responses=[Response(sample()) for _ in range(3)]
    for r in responses: r.headers['Content-Length']='1'
    counters,events=collections.Counter(),[]
    result,rows=m.acquire(req(),SCHEMA,Session(responses),counters,events,sleep=lambda _:None)
    assert rows is None and counters['failures']==1
    assert counters['malformed_payloads']==3 and counters['retries']==2
    assert not list(tmp_path.iterdir())

def test_retry_after_bounded():
    assert m.retry_delay('10',2)==10
    assert m.retry_delay('3600',2) is None
    assert m.retry_delay(None,5)==5

def test_wrong_member_and_header_rejected():
    payload=io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z: z.writestr('wrong.csv','hello')
    with pytest.raises(m.ValidationError): m.validate(payload.getvalue(),req(),SCHEMA)
    with pytest.raises(m.ValidationError):
        m.validate(edited(sample(),lambda rows: rows[0].__setitem__(rows[0].index('TtlTrfVal'),'WRONG')),req(),SCHEMA)

def test_existing_acquisition_cannot_silently_restart(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'META',tmp_path)
    (tmp_path/'session_index.json').write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError,match='requires review'):
        m.run()

def test_offline_rebuild_rejects_missing_sessions(tmp_path,monkeypatch):
    c=m.load(m.ROOT/'research/phase27_calendar_manifest.json')['calendar']
    p=m.load(m.ROOT/'research/phase27_bhavcopy_acquisition_plan.json')['plan']
    monkeypatch.setattr(m,'META',tmp_path)
    monkeypatch.setattr(m,'precheck',lambda:(c,p,SCHEMA,{}))
    (tmp_path/'session_index.json').write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError,match='exact planned coverage'):
        m.validate_local()
