"""Versioned Phase28A-R input-calendar repair; public daily data only."""
from __future__ import annotations
import argparse
import collections
import copy
import csv
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import requests
from research import phase28a_daily as a

META = a.ROOT / 'research/metadata/phase28ar'
OLD_META = a.ROOT / 'research/metadata/phase28a'
OLD_RAW_HASH = 'b96b6681664c08d70408e9274c0e188b9ad82fbaaac32149a8aa4e7ecd9da7e5'
DEFECTS = {'2024-01-22', '2024-05-20'}
SCHEMA_ID = 'NSE_PUBLIC_STKEQ_DAILY_PHASE28AR_V1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def preserve():
    snapshot = a.load(META / 'preservation_before.json')
    require(a.git('branch', '--show-current') == 'main' and a.git('rev-parse', 'HEAD') == a.HEAD, 'Git baseline changed')
    for path, digest in snapshot['files'].items():
        require(a.sha((a.ROOT / path).read_bytes()) == digest, 'preserved file changed: ' + path)
    require(not a.git('diff', '--name-only') and not a.git('diff', '--cached', '--name-only'), 'tracked or staged changes')
    allowed = ['research/metadata/phase28a/', 'research/metadata/phase28ar/', 'research/phase28a_daily.py',
               'research/phase28ar_daily.py', 'tests/test_phase28a_daily.py', 'tests/test_phase28ar_daily.py']
    for line in a.git('status', '--porcelain=v1', '--untracked-files=all').splitlines():
        require(line.startswith('?? ') and any(line[3:] == p or (p.endswith('/') and line[3:].startswith(p)) for p in allowed),
                'unexpected workspace change: ' + line)
    for path in (a.RAW / 'probe.zip', a.DERIVED / 'probe.csv'):
        require(subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=a.ROOT).returncode == 0, 'missing bulk ignore rule')
    require(not a.git('ls-files', '--', str(a.RAW), str(a.DERIVED)), 'tracked bulk data')
    return snapshot


def window(days):
    return dict(first=days[0], last=days[-1], count=len(days), dates=days,
                list_hash=a.sha(a.canonical(days)))


def is_normal(row):
    return row['normal'] and row['session_type'] == 'NORMAL' and row['status'] == 'TRADING'


def recompute(original, evidence):
    """Pure date/classification operation; never reads security or return data."""
    require(set(evidence['holidays']) == DEFECTS, 'unsupported calendar correction')
    corrected = copy.deepcopy(original)
    by_day = {r['date']: r for r in corrected['rows']}
    require(len(by_day) == len(corrected['rows']), 'duplicate calendar dates')
    changes = []
    for day in sorted(DEFECTS):
        proof = evidence['holidays'][day]
        require(proof['classification'] == 'HOLIDAY' and proof['market'] == 'NSE Capital Market equities', 'equity holiday not proven')
        old = copy.deepcopy(by_day[day])
        require(is_normal(old), 'unexpected original defect classification')
        new = by_day[day]
        new.update(status='NON_TRADING', session_type='HOLIDAY', normal=False, open=None, close=None,
                   expected_5m_research=0, source=[proof['reference']], notes='Phase28A-R authoritative equity trading-holiday correction')
        new['30m'] = dict(complete=0, residual=0)
        new['60m'] = dict(complete=0, residual=0)
        changes.append(dict(date=day, before=old, after=copy.deepcopy(new)))
    eligible = sorted(d for d, r in by_day.items() if d < a.SEL and is_normal(r))
    extension = evidence['extension_calendar']
    cursor = date.fromisoformat(min(by_day))
    extra = []
    while len(eligible) < 252:
        cursor -= timedelta(days=1)
        day = cursor.isoformat()
        require(extension['supported_first'] <= day <= extension['supported_last'], 'extension exceeds authoritative calendar scope')
        require(day not in corrected['special_sessions'], 'extension special session unresolved')
        row = copy.deepcopy(original['rows'][0])
        row.update(date=day, source=[extension['reference'], 'Phase27 standard weekday market timing'],
                   notes='Phase28A-R minimal backwards extension; annual calendar and weekday convention')
        if cursor.weekday() >= 5 or day in extension['september_holidays']:
            row.update(status='NON_TRADING', session_type='WEEKEND' if cursor.weekday() >= 5 else 'HOLIDAY',
                       normal=False, open=None, close=None, expected_5m_research=0)
            row['30m'] = row['60m'] = dict(complete=0, residual=0)
        by_day[day] = row
        extra.append(copy.deepcopy(row))
        if is_normal(row):
            eligible.append(day)
    eligible.sort()
    corrected['rows'] = [by_day[d] for d in sorted(by_day)]
    corrected['coverage']['first'] = min(by_day)
    corrected['history'] = window(eligible[-252:])
    corrected['liquidity'] = window(eligible[-60:])
    corrected.update(schema='phase28ar-calendar-v1', parent_calendar_sha256=a.CAL,
                     amendment='Authoritative input correctness repair only; no research outcome used')
    require(corrected['selection'] == original['selection'] and corrected['selection']['date'] == a.SEL, 'selection changed')
    for key in ('T_NEW', 'stages', 'normal_grid', 'special_sessions'):
        require(corrected[key] == original[key], key + ' changed')
    comparison = dict(old_history=original['history'], corrected_history=corrected['history'],
                      old_liquidity=original['liquidity'], corrected_liquidity=corrected['liquidity'],
                      removed_dates=sorted(set(original['history']['dates']) - set(corrected['history']['dates'])),
                      added_dates=sorted(set(corrected['history']['dates']) - set(original['history']['dates'])),
                      liquidity_changed=original['liquidity'] != corrected['liquidity'],
                      classification_changes=changes, extension_rows=sorted(extra, key=lambda r:r['date']),
                      research_outcomes_used=False)
    return corrected, comparison


def make_plan(calendar, original):
    plan = copy.deepcopy(original)
    hist, liq = calendar['history']['dates'], calendar['liquidity']['dates']
    requests = []
    for day in hist + [a.SEL]:
        fmt = 'LEGACY' if day <= '2024-07-05' else 'UDIFF'
        purposes = (['history'] if day in hist else ['selection_universe']) + (['liquidity'] if day in liq else [])
        request = dict(date=day, format=fmt, filename=a.filename(day, fmt), purposes=purposes)
        request['url'] = a.source_url(request)
        request['raw'] = (a.RAW / request['filename']).relative_to(a.ROOT).as_posix()
        requests.append(request)
    plan.update(schema='phase28ar-bhavcopy-plan-v1', parent_plan_sha256=a.load(a.ROOT / 'research/phase27_bhavcopy_acquisition_plan.json')['plan_sha256'],
                calendar_sha256=a.sha(a.canonical(calendar)), requests=requests, count=len(requests), executed=False)
    enforce(calendar, plan)
    return plan


def enforce(calendar, plan, index=None):
    rows = {r['date']:r for r in calendar['rows']}
    require(len(rows) == len(calendar['rows']), 'duplicate calendar rows')
    normals = sorted(d for d, r in rows.items() if d < a.SEL and is_normal(r))
    history, liquidity = calendar['history']['dates'], calendar['liquidity']['dates']
    require(len(history) == 252 and history == normals[-252:], 'history is not exactly 252 preceding NORMAL sessions')
    require(len(liquidity) == 60 and liquidity == normals[-60:], 'liquidity is not exactly 60 preceding NORMAL sessions')
    for label in ['history', 'liquidity']:
        require(calendar[label] == window(calendar[label]['dates']), 'window binding mismatch')
    days = [r['date'] for r in plan['requests']]
    require(days == history + [a.SEL] and len(set(days)) == 253 and plan['count'] == 253, 'corrected plan not exact')
    require(not DEFECTS.intersection(days), 'holiday acquisition target')
    require(plan['calendar_sha256'] == a.sha(a.canonical(calendar)), 'plan/calendar binding mismatch')
    for request in plan['requests']:
        day = request['date']
        require(is_normal(rows[day]) and date.fromisoformat(day).weekday() < 5, 'non-NORMAL/weekend target')
        require(request['format'] == ('LEGACY' if day <= '2024-07-05' else 'UDIFF'), 'format boundary changed')
        require(request['url'] == a.source_url(request), 'source URL mismatch')
    if index is not None:
        require([r['date'] for r in index] == days, 'incomplete or duplicate required coverage')
        require(len({r['sha256'] for r in index}) == 253, 'duplicate raw file hashes')


def build():
    preserve()
    evidence = a.load(META / 'evidence.json')
    for proof in list(evidence['holidays'].values()) + [evidence['extension_calendar']]:
        require(a.sha((a.ROOT / proof['local_path']).read_bytes()) == proof['sha256'], 'evidence hash mismatch')
    original = a.load(a.ROOT / 'research/phase27_calendar_manifest.json')['calendar']
    readiness = a.load(a.ROOT / 'research/phase27_acquisition_readiness.json')['readiness']
    require(a.sha(a.canonical(original)) == a.CAL and a.sha(a.canonical(readiness)) == a.P27, 'original canonical hash mismatch')
    require(a.sha(a.canonical(a.load(a.ROOT / 'research/phase26_new_cycle_protocol.json')['canonical_protocol'])) == a.P26, 'protocol mismatch')
    calendar, comparison = recompute(original, evidence)
    plan = make_plan(calendar, a.load(a.ROOT / 'research/phase27_bhavcopy_acquisition_plan.json')['plan'])
    cal_hash, plan_hash = a.sha(a.canonical(calendar)), a.sha(a.canonical(plan))
    amended = copy.deepcopy(readiness)
    amended.update(schema='phase28ar-readiness-v1', parent_readiness_sha256=a.P27)
    for name in ['history', 'liquidity']:
        amended[name].update(first=calendar[name]['first'], last=calendar[name]['last'], count=calendar[name]['count'], hash=calendar[name]['list_hash'])
    amended['bindings'].update(calendar_hash=cal_hash, bhavcopy_plan_hash=plan_hash)
    amended['authorization']['Phase28A_R'] = 'Explicitly authorized calendar defect repair and daily-only acquisition resume'
    # Original nested acquisition/contamination/sealing rules and stage boundaries are retained.
    amendment = dict(schema='phase28ar-amendment-v1', original_protocol_sha256=a.P26,
        original_readiness_sha256=a.P27, original_calendar_sha256=a.CAL,
        corrected_calendar_sha256=cal_hash, corrected_plan_sha256=plan_hash,
        corrected_readiness_sha256=a.sha(a.canonical(amended)), evidence_sha256=a.sha(a.canonical(evidence)),
        original_blocked_raw_hash_manifest=OLD_RAW_HASH,
        reason='Two authoritative equity trading holidays were incorrectly NORMAL; restore 252 preceding NORMAL observations without changing research rules',
        comparison=comparison, no_research_outcomes_used=True,
        unchanged=['Phase26 protocol', 'selection session', 'T_NEW', 'Stage A/B/C boundaries', '60/252 rules', 'universe', 'eligibility/ranking', 'contamination', 'economics', 'special-session treatment'])
    # Full calendar is compact JSON metadata, not a market-data payload.
    a.atomic(META / 'calendar_v1.json', a.canonical(dict(calendar_sha256=cal_hash, calendar=calendar)) + b'\n', immutable=True)
    for name, value in [('plan_v1', dict(plan_sha256=plan_hash, plan=plan)),
                        ('readiness_v1', dict(readiness_sha256=amendment['corrected_readiness_sha256'], readiness=amended)),
                        ('amendment_v1', amendment)]:
        a.atomic(META / (name + '.json'), a.canonical(value) + b'\n', immutable=True)
    return calendar, plan, amendment


def raw_manifest(index):
    return a.sha(a.canonical([dict(date=r['date'], sha256=r['sha256']) for r in index]))


def verified_rows(entry, request, schema, raw_root=None):
    raw_root = a.RAW if raw_root is None else raw_root
    require(entry['date'] == request['date'] and entry['filename'] == request['filename'], 'raw identity mismatch')
    require(entry['url'] == a.source_url(request) and entry['http_status'] == 200 and entry['acquired_utc'], 'official provenance missing')
    payload = (raw_root / request['filename']).read_bytes()
    require(a.sha(payload) == entry['sha256'] and len(payload) == entry['bytes'], 'raw hash/length mismatch')
    rows, stats = a.validate(payload, request, schema)
    require(stats == entry['validation'], 'stored validation mismatch')
    return rows


def reuse_old(plan, schema):
    old = a.load(OLD_META / 'session_index.json')
    require(len(old) == 251 and raw_manifest(old) == OLD_RAW_HASH, 'original raw manifest identity changed')
    targets = {r['date']: r for r in plan['requests']}
    require(len({r['date'] for r in old}) == len(old), 'duplicate original index')
    events = a.load(OLD_META / 'request_audit.json')['attempts']
    successes = {e['date']:e for e in events if e['result'] == 'SUCCESS'}
    reused = []
    for number, entry in enumerate(old, 1):
        require(entry['date'] in targets, 'original success outside corrected plan')
        event = successes[entry['date']]
        require(event['url'] == entry['url'] and event['sha256'] == entry['sha256'] and event['http_status'] == 200, 'original acquisition audit mismatch')
        verified_rows(entry, targets[entry['date']], schema)
        item = copy.deepcopy(entry)
        item['reuse'] = 'Verified original Phase28A HTTP/hash audit and immutable local bytes; no request'
        reused.append(item)
        if number % 50 == 0:
            print(json.dumps(dict(reused_validated=number)), flush=True)
    return reused


def new_only(plan, existing, authorized_dates):
    required = {r['date']:r for r in plan['requests']}
    have = {r['date'] for r in existing}
    require(len(have) == len(existing) and have <= set(required), 'unexpected/duplicate reuse dates')
    todo = sorted(set(required) - have)
    require(set(todo) <= set(authorized_dates), 'missing non-replacement raw file; no redownload authorized')
    return [required[d] for d in todo]


def write_layer(calendar, plan, index, schema, destination=None):
    """Coverage gate runs before creating any derived file or directory."""
    enforce(calendar, plan, index)
    destination = a.DERIVED if destination is None else destination
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / 'daily_stk_eq_phase28ar_v1.csv'
    temp = target.with_suffix('.csv.partial')
    symbols, identities = collections.defaultdict(set), collections.defaultdict(set)
    history, liquidity = collections.Counter(), collections.Counter()
    total, selection_rows = 0, []
    try:
        with temp.open('x', encoding='utf-8', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=a.FIELDS, lineterminator='\n')
            writer.writeheader()
            for request, entry in zip(plan['requests'], index):
                rows = verified_rows(entry, request, schema)
                require(all(r['session_date'] == request['date'] and r['session_date'] not in DEFECTS for r in rows), 'cross-date/holiday derived rows')
                require(len({r['isin'] for r in rows}) == len(rows), 'duplicate derived identity')
                writer.writerows(rows)
                total += len(rows)
                for row in rows:
                    isin, symbol = row['isin'], row['symbol']
                    symbols[isin].add(symbol)
                    identities[symbol].add(isin)
                    history[isin] += int(request['date'] in calendar['history']['dates'])
                    liquidity[isin] += int(request['date'] in calendar['liquidity']['dates'])
                if request['date'] == a.SEL:
                    selection_rows = rows
            out.flush()
            os.fsync(out.fileno())
        digest = file_hash(temp)
        if target.exists():
            require(file_hash(target) == digest, 'existing derived content differs')
            temp.unlink()
        else:
            os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()
    selection_payload = a.csv_bytes(selection_rows)
    a.atomic(destination / 'selection_universe_phase28ar_v1.csv', selection_payload, immutable=True)
    anomalies = dict(same_isin_multiple_symbols={k:sorted(v) for k,v in sorted(symbols.items()) if len(v)>1},
        same_symbol_multiple_isins={k:sorted(v) for k,v in sorted(identities.items()) if len(v)>1},
        resolution='UNRESOLVED; Phase28B must assess authoritative continuity/action evidence; no eligibility decision, merging or replacement',
        corporate_action_review_complete=False)
    a.save(META / 'identity_anomalies.json', anomalies)
    return dict(schema=SCHEMA_ID, canonical_mapping='NSE_BHAVCOPY_CANONICAL_V1', fields=a.FIELDS,
        path=target.relative_to(a.ROOT).as_posix(), rows=total, unique_sessions=len(index), unique_isins=len(symbols), sha256=digest,
        encoding='UTF-8 without BOM', serialization='CSV LF; header order as fields; session ascending, then ISIN/symbol ascending; exact base-10 decimal; no imputation',
        selection_frame_rows=len(selection_rows), selection_frame_sha256=a.sha(selection_payload),
        complete_252_observations=sum(history[r['isin']] == 252 for r in selection_rows),
        complete_60_observations=sum(liquidity[r['isin']] == 60 for r in selection_rows),
        selection_history_counts=dict(sorted(collections.Counter(history[r['isin']] for r in selection_rows).items())),
        selection_liquidity_counts=dict(sorted(collections.Counter(liquidity[r['isin']] for r in selection_rows).items())),
        symbol_change_groups=len(anomalies['same_isin_multiple_symbols']), isin_change_groups=len(anomalies['same_symbol_multiple_isins']),
        synthetic_rows=0, forward_fills=0, rankings=0, cohort_selections=0)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run():
    require(not (META / 'result.json').exists(), 'Phase28A-R result already exists; use --verify, never redownload')
    calendar, plan, amendment = build()
    schema = a.load(a.ROOT / 'research/phase26_schema_mapping.json')['schema']
    start = a.utc()
    reused = reuse_old(plan, schema)
    todo = new_only(plan, reused, amendment['comparison']['added_dates'])
    require({r['date'] for r in todo} == set(amendment['comparison']['added_dates']), 'new acquisitions differ from mechanical additions')
    for request in todo:
        require(not (a.RAW / request['filename']).exists(), 'unindexed replacement raw already present; review provenance before resuming')
    a.save(META / 'reuse_audit.json', dict(reused_files=len(reused), original_hash_manifest=OLD_RAW_HASH,
        network_requests=0, verified_dates=[r['date'] for r in reused], hashes_verified=True, official_success_audit_verified=True))
    counters = collections.Counter({k:0 for k in ['official_file_requests','successes','retries','failures','failed_attempts','non_200_responses','malformed_payloads','schema_failures','http_failures']})
    attempts, added, missing = [], [], []
    with requests.Session() as session:
        session.trust_env = False
        for request in todo:
            result, rows = a.acquire(request, schema, session, counters, attempts)
            if rows is None:
                missing.append(result)
            else:
                result['reuse'] = 'New Phase28A-R mechanically required session'
                added.append(result)
            a.save(META / 'request_audit.json', dict(counters=counters, attempts=attempts))
            a.save(META / 'session_index.json', sorted(reused + added, key=lambda r:r['date']))
            print(json.dumps(dict(new_date=request['date'], valid=rows is not None)), flush=True)
            time.sleep(1)
    index = sorted(reused + added, key=lambda r:r['date'])
    result = dict(status='BLOCKED' if missing else 'DATA_VALIDATED_TESTS_PENDING', started_utc=start, acquisition_end_utc=a.utc(),
        reused_raw_files=len(reused), newly_downloaded_files=len(added), counters=counters, missing=missing,
        corrected_raw_hash_manifest=raw_manifest(index), original_blocked_raw_hash_manifest=OLD_RAW_HASH,
        coverage=dict(history=sum(r['date'] in calendar['history']['dates'] for r in index), liquidity=sum(r['date'] in calendar['liquidity']['dates'] for r in index), selection=sum(r['date']==a.SEL for r in index)),
        schema_counts=dict(collections.Counter(r['validation']['schema'] for r in index)),
        selection_statistics=next(r['validation'] for r in index if r['date']==a.SEL),
        derived=None, cohort_selection=False, SmartAPI_calls=0, candle_calls=0, strategy_calls=0, backtests=0, orders=0, Stage_B_C_exposure=False)
    a.save(META / 'result.json', result)
    if not missing:
        print('Exact corrected coverage established; deriving daily layer', flush=True)
        result['derived'] = write_layer(calendar, plan, index, schema)
        preserve()
        result['completed_validation_utc'] = a.utc()
        a.save(META / 'result.json', result)
    print(json.dumps(result, indent=2))


def verify():
    calendar, plan, amendment = build()
    index = a.load(META / 'session_index.json')
    result = a.load(META / 'result.json')
    require(raw_manifest(index) == result['corrected_raw_hash_manifest'], 'corrected raw manifest changed')
    schema = a.load(a.ROOT / 'research/phase26_schema_mapping.json')['schema']
    derived = write_layer(calendar, plan, index, schema)
    # JSON persistence converts Counter keys to strings; compare semantically.
    require(json.loads(json.dumps(derived, sort_keys=True)) == json.loads(json.dumps(result['derived'], sort_keys=True)), 'derived reproducibility failed')
    preserve()
    audit = dict(status='PASS', files_revalidated=len(index), derived_sha256=derived['sha256'],
        derived_rows=derived['rows'], network_requests=0, preserved_originals=True)
    a.save(META / 'reproducibility_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--acquire', action='store_true')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.acquire:
        run()
    elif args.verify:
        verify()
    else:
        print(json.dumps(build()[2], indent=2))
