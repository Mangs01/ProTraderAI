"""Authorized Phase28A daily bhavcopies only. No cohort selection or evaluation."""
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import zipfile
import requests

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / 'research/metadata/phase28a'
RAW = ROOT / 'research/data/new_cycle_001/raw/bhavcopy'
DERIVED = ROOT / 'research/data/new_cycle_001/derived'
HEAD = '7ff8b3e227f1507424aa6611e7cb62120a5a76a6'
P26 = '2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa'
P27 = '9f3903d1e82f0e5d1cc3fd0d9f727ef66b1c367717ccc6b60addd74bcfa88815'
CAL = '13274fbe46c6df033b93537feda34532ccced0670c9153ccd135fba6b3084c72'
HIST = '9fe2580d123522ad6b8993236407967a060fe720b28dd7a9464636d88cefe734'
LIQ = '386e2c19593c40e81f271f776a0134089476596eff471aab782c1cc6b47c6398'
SEL = '2024-09-17'
MONTHS = 'JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split()
FIELDS = ['session_date','isin','symbol','series','instrument_type','traded_value','source_format','source_sha256','source_reference']

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def atomic(path, payload, immutable=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    if immutable and path.exists():
        if path.read_bytes()!=payload:
            raise ValueError('immutable file differs')
        return
    temp=path.with_name(path.name+'.partial')
    created=False
    try:
        with temp.open('xb') as stream:
            created=True
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable and path.exists():
            raise ValueError('immutable destination appeared')
        os.replace(temp,path)
    finally:
        if created and temp.exists():
            temp.unlink()

def save(path,value):
    atomic(path,json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False).encode('utf-8')+b'\n')

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def filename(day,fmt):
    d=date.fromisoformat(day)
    if fmt=='LEGACY':
        return f'cm{d.day:02d}{MONTHS[d.month-1]}{d.year}bhav.csv.zip'
    if fmt=='UDIFF':
        return f'BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip'
    raise ValueError('unknown format')

def source_url(req):
    d=date.fromisoformat(req['date'])
    if req['filename']!=filename(req['date'],req['format']):
        raise ValueError('filename mismatch')
    prefix=f'content/historical/EQUITIES/{d.year}/{MONTHS[d.month-1]}/' if req['format']=='LEGACY' else 'content/cm/'
    return 'https://nsearchives.nseindia.com/'+prefix+req['filename']

def enforce_sessions(c,p):
    history,liquidity=c['history']['dates'],c['liquidity']['dates']
    days=[r['date'] for r in p['requests']]
    if len(history)!=252 or sha(canonical(history))!=HIST:
        raise ValueError('history manifest mismatch')
    if len(liquidity)!=60 or sha(canonical(liquidity))!=LIQ or liquidity!=history[-60:]:
        raise ValueError('liquidity manifest mismatch')
    if days!=history+[SEL] or len(set(days))!=253 or p['count']!=253:
        raise ValueError('exact planned-session mismatch')
    rows={r['date']:r for r in c['rows']}
    if len(rows)!=len(c['rows']):
        raise ValueError('duplicate calendar dates')
    for day in days:
        r=rows[day]
        if r['session_type']!='NORMAL' or not r['normal'] or r['status']!='TRADING':
            raise ValueError('non-NORMAL date '+day)
    if c['selection']['date']!=SEL or c['selection']['classification']!='NORMAL':
        raise ValueError('selection mismatch')
    for req in p['requests']:
        if req['format']!=('LEGACY' if req['date']<='2024-07-05' else 'UDIFF'):
            raise ValueError('format boundary mismatch')
        source_url(req)

def precheck():
    if git('branch','--show-current')!='main' or git('rev-parse','HEAD')!=HEAD:
        raise ValueError('Git baseline mismatch')
    allowed=['research/phase28a_daily.py','tests/test_phase28a_daily.py','research/metadata/phase28a/']
    for line in git('status','--porcelain=v1','--untracked-files=all').splitlines():
        if not line.startswith('?? ') or not any(line[3:]==a or (a.endswith('/') and line[3:].startswith(a)) for a in allowed):
            raise ValueError('unexpected working-tree change '+line)
    p26=load(ROOT/'research/phase26_new_cycle_protocol.json')
    p27=load(ROOT/'research/phase27_acquisition_readiness.json')
    if sha(canonical(p26['canonical_protocol']))!=P26 or sha(canonical(p27['readiness']))!=P27:
        raise ValueError('protocol/readiness mismatch')
    b=p27['readiness']['bindings']
    specs=[('phase27_calendar_manifest','calendar',CAL),('phase27_bhavcopy_acquisition_plan','plan',b['bhavcopy_plan_hash']),('phase27_cohort_selection_template','template',b['cohort_template_hash']),('phase27_candle_acquisition_template','template',b['candle_template_hash']),('phase27_access_registry','access',b['access_hash']),('phase27_exposure_overlap','exposure',b['exposure_hash'])]
    objects={}
    files=['research/phase26_new_cycle_protocol.json','research/phase27_acquisition_readiness.json','research/phase26_schema_mapping.json','research/phase26_exposure_registry.json']
    for name,key,expected in specs:
        path='research/'+name+'.json'
        obj=load(ROOT/path)[key]
        if sha(canonical(obj))!=expected:
            raise ValueError(name+' hash mismatch')
        objects[key]=obj
        files.append(path)
    schema=load(ROOT/files[2])['schema']
    if sha((ROOT/files[2]).read_bytes())!=b['schema_file_hash'] or schema!=p26['canonical_protocol']['schema']:
        raise ValueError('schema mismatch')
    if load(ROOT/files[3])['phase26_protocol_sha256']!=P26:
        raise ValueError('exposure binding mismatch')
    enforce_sessions(objects['calendar'],objects['plan'])
    for path in [RAW/'probe.zip',DERIVED/'probe.csv']:
        if subprocess.run(['git','check-ignore','-q',str(path)],cwd=ROOT).returncode:
            raise ValueError('missing ignore rule')
    if git('ls-files','--',str(RAW),str(DERIVED)):
        raise ValueError('bulk files tracked')
    audit=dict(status='PASS',branch='main',starting_head=HEAD,initial_working_tree_clean=True,
        initial_clean_evidence='Read-only git status before Phase28A file creation returned no entries',
        protocol_sha256=P26,readiness_sha256=P27,calendar_sha256=CAL,history_sha256=HIST,liquidity_sha256=LIQ,
        frozen_file_sha256={p:sha((ROOT/p).read_bytes()) for p in files},planned_dates=253,selection_occurrences=1,
        duplicate_dates=0,all_normal=True,bulk_paths_ignored=True,credentials_required=False,
        public_source='https://www.nseindia.com/all-reports',transport='HTTPS public archive; no credentials/cookies/login; redirects disabled; trust_env=False',
        storage_override='User-authorized local-only bulk paths; no frozen plan mutation')
    return objects['calendar'],objects['plan'],schema,audit

class ValidationError(ValueError):
    def __init__(self,category,reason):
        super().__init__(reason)
        self.category=category

def valid_isin(value):
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]',value):
        return False
    digits=''.join(str(ord(c)-55) if c.isalpha() else c for c in value)
    return sum((int(c)*2)//10+(int(c)*2)%10 if i%2 else int(c) for i,c in enumerate(reversed(digits)))%10==0

def validate(payload,req,schema):
    def fail(reason,category='schema_failures'):
        raise ValidationError(category,reason)
    if not payload.startswith(b'PK\x03\x04'):
        fail('HTML/error or non-ZIP payload','malformed_payloads')
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            if z.namelist()!=[req['filename'][:-4]]:
                fail('unexpected ZIP members','malformed_payloads')
            info=z.infolist()[0]
            if info.file_size>25000000 or info.flag_bits&1:
                fail('oversized/encrypted ZIP','malformed_payloads')
            if z.testzip() is not None:
                fail('ZIP CRC error','malformed_payloads')
            text=z.read(info).decode('utf-8-sig')
    except (zipfile.BadZipFile,UnicodeError,RuntimeError,EOFError) as exc:
        fail(type(exc).__name__,'malformed_payloads')
    reader=csv.reader(io.StringIO(text,newline=''),strict=True)
    try:
        headers=next(reader)
    except (StopIteration,csv.Error):
        fail('empty/malformed CSV')
    fmt=req['format']
    mapping=schema[fmt.lower()]
    required={v for k,v in mapping.items() if k!='instrument_type' or fmt=='UDIFF'}
    if not required.issubset(headers) or len(headers)!=len(set(headers)):
        fail('missing/duplicate authoritative headers')
    if fmt=='UDIFF' and not {'BizDt','Sgmt','Src'}.issubset(headers):
        fail('missing exchange/date fields')
    stats=dict(source_rows=0,stk_eq_rows=0,unique_isins=0,duplicate_isins=0,invalid_missing_isins=0,zero_traded_values=0,missing_traded_values=0,duplicate_source_rows=0,schema=fmt)
    rows,seen,isins,issues=[],set(),collections.Counter(),[]
    digest=sha(payload)
    try:
        for line,values in enumerate(reader,2):
            stats['source_rows']+=1
            if len(values)!=len(headers):
                fail(f'row {line}: malformed column count')
            if tuple(values) in seen:
                stats['duplicate_source_rows']+=1
            seen.add(tuple(values))
            row=dict(zip(headers,values))
            if row.get('',''):
                fail(f'row {line}: unexpected trailing data')
            actual=row[mapping['trade_date']].strip()
            if fmt=='LEGACY':
                parts=actual.split('-')
                try:
                    actual=date(int(parts[2]),MONTHS.index(parts[1])+1,int(parts[0])).isoformat()
                except (ValueError,IndexError):
                    fail(f'row {line}: invalid date')
            elif row['BizDt']!=req['date'] or row['Sgmt']!='CM' or row['Src']!='NSE':
                fail(f'row {line}: wrong business date/segment/source')
            if actual!=req['date']:
                fail(f'row {line}: cross-date contamination')
            series,symbol,isin=(row[mapping[k]].strip() for k in ['series','symbol','isin'])
            # Official CM legacy archive + official EQ series legend establish
            # the cash-equity instrument family. Non-EQ legacy types are not inferred.
            kind=row['FinInstrmTp'].strip() if fmt=='UDIFF' else ('STK' if series=='EQ' else 'LEGACY_OTHER')
            if not series or not symbol or not kind:
                fail(f'row {line}: missing identity/type/series')
            if kind!='STK' or series!='EQ':
                continue
            stats['stk_eq_rows']+=1
            isins[isin]+=1
            if not valid_isin(isin):
                stats['invalid_missing_isins']+=1
                issues.append(f'row {line}: invalid/missing ISIN')
            raw_value=row[mapping['total_traded_value']].strip()
            if not raw_value:
                stats['missing_traded_values']+=1
                issues.append(f'row {line}: missing traded value')
                continue
            try:
                value=Decimal(raw_value)
                if not value.is_finite() or value<0:
                    raise InvalidOperation
            except InvalidOperation:
                fail(f'row {line}: invalid traded value')
            stats['zero_traded_values']+=int(value==0)
            rows.append(dict(zip(FIELDS,[req['date'],isin,symbol,series,kind,format(value,'f'),fmt,digest,(RAW/req['filename']).relative_to(ROOT).as_posix()])))
    except csv.Error:
        fail('malformed CSV syntax')
    stats['unique_isins']=len(isins)
    stats['duplicate_isins']=sum(n>1 for n in isins.values())
    if not rows or issues or stats['duplicate_isins'] or stats['duplicate_source_rows']:
        fail('invalid/duplicate rows: '+json.dumps(stats)+'; '+'; '.join(issues[:5]))
    return sorted(rows,key=lambda r:(r['isin'],r['symbol'])),stats

def retry_delay(header,minimum):
    if not header:
        return minimum
    try:
        delay=max(0,int(header))
    except ValueError:
        try:
            delay=max(0,(parsedate_to_datetime(header)-datetime.now(timezone.utc)).total_seconds())
        except (ValueError,TypeError):
            return minimum
    return None if delay>60 else max(minimum,delay)

def acquire(req,schema,session,counters,attempts,sleep=time.sleep):
    url=source_url(req)
    for attempt in range(1,4):
        counters['retries']+=int(attempt>1)
        counters['official_file_requests']+=1
        event=dict(date=req['date'],url=url,attempt=attempt,started_utc=utc(),http_status=None)
        delay_header=None
        try:
            with session.get(url,timeout=(15,45),allow_redirects=False,stream=True,headers={'User-Agent':'Mozilla/5.0','Accept':'application/zip','Accept-Encoding':'identity'}) as response:
                event['http_status']=response.status_code
                delay_header=response.headers.get('Retry-After')
                if response.status_code!=200:
                    counters['non_200_responses']+=1
                    raise ValidationError('http_failures','HTTP '+str(response.status_code))
                if response.headers.get('Content-Encoding','identity').lower() not in ('','identity'):
                    raise ValidationError('malformed_payloads','unexpected transport encoding')
                chunks,size=[],0
                for chunk in response.iter_content(65536):
                    size+=len(chunk)
                    if size>10000000:
                        raise ValidationError('malformed_payloads','oversized payload')
                    chunks.append(chunk)
                payload=b''.join(chunks)
                length=response.headers.get('Content-Length')
                if length is not None and int(length)!=len(payload):
                    raise ValidationError('malformed_payloads','incomplete HTTP body')
                rows,stats=validate(payload,req,schema)
                atomic(RAW/req['filename'],payload,immutable=True)
                event.update(result='SUCCESS',ended_utc=utc(),sha256=sha(payload),bytes=len(payload))
                attempts.append(event)
                counters['successes']+=1
                return dict(date=req['date'],filename=req['filename'],url=url,acquired_utc=event['ended_utc'],http_status=200,sha256=sha(payload),bytes=len(payload),validation=stats),rows
        except (requests.RequestException,ValidationError,OSError,ValueError) as exc:
            counters['failed_attempts']+=1
            if isinstance(exc,ValidationError):
                counters[exc.category]+=1
            event.update(result='FAILED',ended_utc=utc(),reason=str(exc) if isinstance(exc,ValidationError) else type(exc).__name__)
            attempts.append(event)
        if attempt<3:
            delay=retry_delay(delay_header,(2,5)[attempt-1])
            if delay is None:
                break
            sleep(delay)
    counters['failures']+=1
    return dict(date=req['date'],url=url,reason=attempts[-1]['reason']),None

def csv_bytes(rows):
    out=io.StringIO(newline='')
    writer=csv.DictWriter(out,fieldnames=FIELDS,lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode('utf-8')

def derive(records,c):
    payload=csv_bytes(r for day in sorted(records) for r in records[day])
    atomic(DERIVED/'daily_stk_eq.csv',payload)
    selection=records[SEL]
    atomic(DERIVED/'selection_universe_validation_only.csv',csv_bytes(selection))
    hist,liq=collections.Counter(),collections.Counter()
    symbols,identities=collections.defaultdict(set),collections.defaultdict(set)
    for day,rows in records.items():
        for r in rows:
            hist[r['isin']]+=int(day in c['history']['dates'])
            liq[r['isin']]+=int(day in c['liquidity']['dates'])
            symbols[r['isin']].add(r['symbol'])
            identities[r['symbol']].add(r['isin'])
    anomalies=dict(same_isin_multiple_symbols={k:sorted(v) for k,v in sorted(symbols.items()) if len(v)>1},same_symbol_multiple_isins={k:sorted(v) for k,v in sorted(identities.items()) if len(v)>1},resolution='UNRESOLVED; Phase28B authoritative continuity/action evidence required; no eligibility determination',corporate_action_review_complete=False)
    save(META/'identity_anomalies.json',anomalies)
    return dict(path=(DERIVED/'daily_stk_eq.csv').relative_to(ROOT).as_posix(),rows=sum(map(len,records.values())),sha256=sha(payload),selection_frame_rows=len(selection),history_sessions=252,liquidity_sessions=60,selection_history_observation_counts=dict(sorted(collections.Counter(hist[r['isin']] for r in selection).items())),selection_liquidity_observation_counts=dict(sorted(collections.Counter(liq[r['isin']] for r in selection).items())),complete_252_observations=sum(hist[r['isin']]==252 for r in selection),complete_60_observations=sum(liq[r['isin']]==60 for r in selection),symbol_change_groups=len(anomalies['same_isin_multiple_symbols']),isin_change_groups=len(anomalies['same_symbol_multiple_isins']),imputed_rows=0,rankings=0,cohort_selections=0)

def run():
    if (META/'session_index.json').exists():
        raise ValueError('Existing acquisition requires review; use offline validation, never silently restart')
    c,p,schema,prechecks=precheck()
    save(META/'precheck.json',prechecks)
    counters=collections.Counter({k:0 for k in ['official_file_requests','successes','retries','failures','failed_attempts','non_200_responses','malformed_payloads','schema_failures','http_failures','SmartAPI_calls','Angel_One_logins','candle_calls','strategy_calls','backtests','orders']})
    start,attempts,index,missing,records=utc(),[],[],[],{}
    with requests.Session() as session:
        session.trust_env=False
        for number,req in enumerate(p['requests'],1):
            result,rows=acquire(req,schema,session,counters,attempts)
            if rows is None:
                missing.append(result)
            else:
                index.append(result)
                records[req['date']]=rows
            save(META/'request_audit.json',dict(counters=counters,attempts=attempts))
            save(META/'session_index.json',index)
            print(json.dumps(dict(progress=number,date=req['date'],valid=rows is not None,successes=len(index),failures=len(missing))),flush=True)
            if number<len(p['requests']):
                time.sleep(1)
    end=utc()
    derived=derive(records,c) if not missing else None
    unchanged=all(sha((ROOT/path).read_bytes())==digest for path,digest in prechecks['frozen_file_sha256'].items())
    report=dict(status='DATA_VALIDATED_TESTS_PENDING' if not missing and unchanged else 'BLOCKED',acquisition_start_utc=start,acquisition_end_utc=end,precheck='PASS',planned_dates=253,successful_unique_dates=len(index),raw_file_count=len(list(RAW.glob('*.zip'))),raw_hash_manifest_sha256=sha(canonical([dict(date=r['date'],sha256=r['sha256']) for r in index])),raw_hash_manifest_rule='SHA256 canonical JSON ordered date/sha256 pairs from session_index.json',counters=counters,missing_dates=missing,duplicate_planned_dates=0,duplicate_raw_hashes=[h for h,n in collections.Counter(r['sha256'] for r in index).items() if n>1],schema_counts=dict(collections.Counter(r['validation']['schema'] for r in index)),selection_statistics=next((r['validation'] for r in index if r['date']==SEL),None),validated_history_sessions=sum(r['date'] in c['history']['dates'] for r in index),derived=derived,frozen_artifacts_unchanged=unchanged,metadata_web_open_calls=2,metadata_web_urls=['https://www.nseindia.com/all-reports','https://www.nseindia.com/resources/exchange-communication-circulars'],final_cohort_selected=False,Stage_B_C_strategy_exposure=False)
    save(META/'result.json',report)
    print(json.dumps(report,indent=2))

def validate_local():
    """Rebuild solely from indexed immutable raw bytes, without network access."""
    c,p,schema,checks=precheck()
    index=load(META/'session_index.json')
    if [r['date'] for r in index]!=[r['date'] for r in p['requests']]:
        raise ValueError('local index lacks exact planned coverage')
    expected={r['filename'] for r in p['requests']}
    if {x.name for x in RAW.glob('*.zip')}!=expected:
        raise ValueError('local raw file set differs from plan')
    records={}
    for req,entry in zip(p['requests'],index):
        payload=(RAW/req['filename']).read_bytes()
        if entry['url']!=source_url(req) or entry['http_status']!=200 or entry['sha256']!=sha(payload) or entry['bytes']!=len(payload):
            raise ValueError('local raw provenance mismatch '+req['date'])
        rows,stats=validate(payload,req,schema)
        if stats!=entry['validation']:
            raise ValueError('local validation differs '+req['date'])
        records[req['date']]=rows
    before=sha((DERIVED/'daily_stk_eq.csv').read_bytes())
    derived=derive(records,c)
    if before!=derived['sha256']:
        raise ValueError('derived reproducibility mismatch')
    result=dict(status='PASS',network_requests=0,raw_files_revalidated=len(index),derived_sha256=before,derived_rows=derived['rows'])
    save(META/'reproducibility_audit.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--acquire',action='store_true')
    group.add_argument('--validate-local',action='store_true')
    args=parser.parse_args()
    if args.acquire:
        run()
    elif args.validate_local:
        validate_local()
    else:
        print(json.dumps(precheck()[3],indent=2))
