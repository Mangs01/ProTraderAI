"""Offline Phase28B deterministic selection; no acquisition or execution APIs."""
import collections
import csv
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import json
import socket
import subprocess
from research import phase28a_daily as a, phase28ar_daily as ar

META = a.ROOT / 'research/metadata/phase28b'
EXPECTED = dict(protocol=a.P26, history='8f1dc540ca00251314b4beb75bb782cdc8c20cd2cee3433ac2d78b393d5a777a', liquidity=a.LIQ,
    raw_manifest='89c8bae354f14b3a24238b37ff30c1874fecb9be2190ae64451d8be2d7750978',
    derived='5154d2652a58f880adae93908cd125cd43dc8020d862a14aa0bb53a59a5eb09c')
require = ar.require

def check_hash(actual, expected, label):
    require(actual == expected, label + ' hash mismatch')

def baseline():
    require(a.git('branch', '--show-current') == 'main' and a.git('rev-parse', 'HEAD') == a.HEAD, 'Git baseline mismatch')
    require(not a.git('diff', '--name-only') and not a.git('diff', '--cached', '--name-only'), 'tracked/staged changes')

def snapshot():
    paths = set(a.git('ls-files', 'research').splitlines())
    for directory in (a.META, ar.META):
        paths.update(p.relative_to(a.ROOT).as_posix() for p in directory.rglob('*') if p.is_file())
    paths.update(['research/phase28a_daily.py', 'research/phase28ar_daily.py', 'tests/test_phase28a_daily.py', 'tests/test_phase28ar_daily.py'])
    return {p: ar.file_hash(a.ROOT / p) for p in sorted(paths)}

def precheck():
    baseline()
    preserved = snapshot()
    for path, digest in a.load(ar.META / 'preservation_before.json')['files'].items():
        check_hash(ar.file_hash(a.ROOT / path), digest, 'preserved ' + path)
    recorded = a.load(ar.META / 'preservation_before.json')['files'].copy()
    def collect_sources(value):
        if isinstance(value, dict):
            if 'local_path' in value and 'sha256' in value:
                recorded[value['local_path']] = value['sha256']
            for item in value.values(): collect_sources(item)
        elif isinstance(value, list):
            for item in value: collect_sources(item)
    collect_sources(a.load(a.ROOT / 'research/phase27_calendar_manifest.json'))
    # Recorded original source bytes take precedence over Git's newline filters.
    for path in a.git('ls-files', 'research/*phase27*', 'research/metadata/phase27').splitlines():
        if path in recorded:
            check_hash(ar.file_hash(a.ROOT / path), recorded[path], 'original Phase27 ' + path)
        else:
            raw = subprocess.check_output(['git', 'cat-file', '--filters', a.HEAD + ':' + path], cwd=a.ROOT)
            require((a.ROOT / path).read_bytes() == raw, 'Phase27 checkout bytes changed: ' + path)
    protocol = a.load(a.ROOT / 'research/phase26_new_cycle_protocol.json')['canonical_protocol']
    check_hash(a.sha(a.canonical(protocol)), a.P26, 'protocol')
    original = a.load(a.ROOT / 'research/phase27_calendar_manifest.json')['calendar']
    check_hash(a.sha(a.canonical(original)), a.CAL, 'original calendar')
    readiness = a.load(a.ROOT / 'research/phase27_acquisition_readiness.json')['readiness']
    check_hash(a.sha(a.canonical(readiness)), a.P27, 'original readiness')
    evidence = a.load(ar.META / 'evidence.json')
    for proof in list(evidence['holidays'].values()) + [evidence['extension_calendar']]:
        check_hash(ar.file_hash(a.ROOT / proof['local_path']), proof['sha256'], 'calendar evidence')
    calendar, comparison = ar.recompute(original, evidence)
    stored = a.load(ar.META / 'calendar_v1.json')
    require(calendar == stored['calendar'], 'calendar reconstruction mismatch')
    check_hash(a.sha(a.canonical(calendar)), stored['calendar_sha256'], 'corrected calendar')
    plan = ar.make_plan(calendar, a.load(a.ROOT / 'research/phase27_bhavcopy_acquisition_plan.json')['plan'])
    pw = a.load(ar.META / 'plan_v1.json')
    require(plan == pw['plan'], 'plan reconstruction mismatch')
    check_hash(a.sha(a.canonical(plan)), pw['plan_sha256'], 'corrected plan')
    amendment = a.load(ar.META / 'amendment_v1.json')
    require(amendment['comparison'] == comparison, 'amendment mismatch')
    for key, value in [('original_protocol_sha256', a.P26), ('original_readiness_sha256', a.P27), ('original_calendar_sha256', a.CAL),
        ('corrected_calendar_sha256', stored['calendar_sha256']), ('corrected_plan_sha256', pw['plan_sha256']), ('evidence_sha256', a.sha(a.canonical(evidence)))]:
        check_hash(amendment[key], value, key)
    rw = a.load(ar.META / 'readiness_v1.json')
    check_hash(a.sha(a.canonical(rw['readiness'])), rw['readiness_sha256'], 'amended readiness')
    check_hash(rw['readiness_sha256'], amendment['corrected_readiness_sha256'], 'readiness binding')
    index = a.load(ar.META / 'session_index.json')
    ar.enforce(calendar, plan, index)
    result = a.load(ar.META / 'result.json')
    require(result['status'] == 'COMPLETE', 'Phase28A-R incomplete')
    path = a.ROOT / result['derived']['path']
    verified = dict(protocol=a.sha(a.canonical(protocol)), history=calendar['history']['list_hash'], liquidity=calendar['liquidity']['list_hash'],
        raw_manifest=ar.raw_manifest(index), derived=ar.file_hash(path))
    for key, digest in EXPECTED.items():
        check_hash(verified[key], digest, key)
    schema = a.load(a.ROOT / 'research/phase26_schema_mapping.json')['schema']
    require(schema == protocol['schema'], 'schema differs from protocol')
    rebuilt = hashlib.sha256()
    header = io.StringIO(newline='')
    csv.writer(header, lineterminator='\n').writerow(a.FIELDS)
    rebuilt.update(header.getvalue().encode('utf-8'))
    rows = []
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == a.FIELDS, 'derived columns changed')
        for request, entry in zip(plan['requests'], index):
            batch = ar.verified_rows(entry, request, schema)
            text = io.StringIO(newline='')
            csv.DictWriter(text, fieldnames=a.FIELDS, lineterminator='\n').writerows(batch)
            rebuilt.update(text.getvalue().encode('utf-8'))
            for row in batch:
                require(next(reader, None) == row, 'raw/derived row mismatch')
            rows.extend(batch)
        require(next(reader, None) is None, 'extra derived rows')
    check_hash(rebuilt.hexdigest(), EXPECTED['derived'], 'raw reconstruction')
    require(len(rows) == 463553 and len({r['session_date'] for r in rows}) == 253 and len({r['isin'] for r in rows}) == 2292, 'derived counts')
    require(sum(r['date'] == a.SEL for r in index) == 1, 'selection session multiplicity')
    stats = next(r['validation'] for r in index if r['date'] == a.SEL)
    for key, count in dict(source_rows=2867, stk_eq_rows=1838, unique_isins=1838, duplicate_isins=0,
        invalid_missing_isins=0, zero_traded_values=0, missing_traded_values=0, duplicate_source_rows=0).items():
        require(stats[key] == count, 'selection universe ' + key)
    require(snapshot() == preserved, 'historical evidence changed')
    return rows, calendar, protocol, dict(status='PASS', starting_head=a.HEAD, verified_input_hashes=verified,
        selection_statistics=stats, derived_rows=len(rows), derived_sessions=253, derived_isins=2292, history_sessions=252, liquidity_sessions=60,
        corrected_calendar_sha256=stored['calendar_sha256'], amendment_sha256=a.sha(a.canonical(amendment)),
        raw_files_revalidated=253, historical_file_hashes=preserved)

def exact_median(values):
    require(len(values) == 60, 'median requires exactly 60 observations')
    values = [Decimal(v) for v in values]
    require(all(v.is_finite() and v >= 0 for v in values), 'invalid traded value')
    values.sort()
    with localcontext() as ctx:
        ctx.prec = max(50, max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + 5)
        return (values[29] + values[30]) / Decimal(2)

def identity_review(rows, symbol_isins, symbol_sessions):
    ordered = sorted(rows, key=lambda r: r['session_date'])
    segments = []
    for row in ordered:
        if not segments or segments[-1]['symbol'] != row['symbol']:
            segments.append(dict(symbol=row['symbol'], first_observed=row['session_date'], last_observed=row['session_date'],
                observations=0, first_source_sha256=row['source_sha256']))
        segments[-1]['last_observed'] = row['session_date']
        segments[-1]['observations'] += 1
    collisions = {s: sorted(symbol_isins[s]) for s in sorted({r['symbol'] for r in rows}) if len(symbol_isins[s]) > 1}
    # Reused symbols are diagnostic only. Dated distinct ISIN records stay separate.
    overlapping = sorted({r['symbol'] for r in rows if len(symbol_sessions[(r['symbol'], r['session_date'])]) > 1})
    return dict(isin=ordered[0]['isin'], observed_symbol_history=segments, symbol_other_isins=collisions,
        material_ambiguities=overlapping,
        collision_resolution='Concurrent same-symbol different-ISIN STK/EQ mapping unresolved' if overlapping else 'Dated ISIN identities kept separate; no splice or inferred replacement',
        identity_continuity_status='UNRESOLVED_SYMBOL_ISIN_MAPPING' if overlapping else 'RESOLVED_OFFICIAL_SAME_ISIN_ROWS',
        corporate_action_review_status='UNRESOLVED_IDENTITY_LIQUIDITY_COMPARABILITY' if overlapping else 'NO_MATERIAL_AMBIGUITY_IN_FROZEN_IDENTITY_RECORD')

def evaluate(rows, history, liquidity, selection=a.SEL):
    require(len(history) == len(set(history)) == 252, 'history window length')
    require(len(liquidity) == len(set(liquidity)) == 60 and liquidity == history[-60:], 'liquidity window length')
    require(history == sorted(history) and history[-1] < selection, 'history chronology')
    days = set(history + [selection])
    by_isin = collections.defaultdict(dict)
    symbol_isins = collections.defaultdict(set)
    symbol_sessions = collections.defaultdict(set)
    for row in rows:
        require(row['session_date'] in days, 'out-of-window row; future data forbidden')
        require(row['instrument_type'] == 'STK' and row['series'] == 'EQ', 'non-STK/EQ row')
        require(a.valid_isin(row['isin']), 'invalid ISIN')
        require(row['session_date'] not in by_isin[row['isin']], 'duplicate ISIN/session')
        by_isin[row['isin']][row['session_date']] = row
        symbol_isins[row['symbol']].add(row['isin'])
        symbol_sessions[(row['symbol'], row['session_date'])].add(row['isin'])
    audit, identities, ranking = [], [], []
    for isin, observations in sorted(by_isin.items()):
        if selection not in observations:
            continue
        current = observations[selection]
        mh = [d for d in history if d not in observations]
        ml = [d for d in liquidity if d not in observations]
        invalid = []
        for day in liquidity:
            if day in observations:
                try:
                    value = Decimal(observations[day]['traded_value'])
                    if not value.is_finite() or value < 0:
                        invalid.append(day)
                except (InvalidOperation, ValueError):
                    invalid.append(day)
        review = identity_review(list(observations.values()), symbol_isins, symbol_sessions)
        identities.append(review)
        reasons = []
        if mh: reasons.append('MISSING_REQUIRED_252_HISTORY')
        if ml: reasons.append('MISSING_REQUIRED_60_LIQUIDITY')
        if invalid: reasons.append('INVALID_CANONICAL_TRADED_VALUE')
        if review['material_ambiguities']: reasons.append('UNRESOLVED_MATERIAL_SYMBOL_ISIN_CONTINUITY')
        median = None if ml or invalid else format(exact_median([observations[d]['traded_value'] for d in liquidity]), 'f')
        record = dict(isin=isin, symbol=current['symbol'], series=current['series'], instrument_type='STK',
            history_observation_count=252-len(mh), liquidity_observation_count=60-len(ml), median_60_session_traded_value=median,
            eligible=not reasons, exclusion_reasons=reasons, missing_history_sessions=mh, missing_liquidity_sessions=ml,
            invalid_liquidity_sessions=invalid, identity_continuity_status=review['identity_continuity_status'],
            corporate_action_review_status=review['corporate_action_review_status'], source_reference=current['source_reference'], source_sha256=current['source_sha256'])
        audit.append(record)
        if not reasons:
            ranking.append({k: v for k, v in record.items() if k not in ('missing_history_sessions', 'missing_liquidity_sessions', 'invalid_liquidity_sessions')})
    ranking.sort(key=ranking_key)
    for rank, record in enumerate(ranking, 1): record['rank'] = rank
    return audit, identities, ranking

def ranking_key(row):
    return (Decimal(row['median_60_session_traded_value']).copy_negate(), row['isin'], row['symbol'])

def select(ranking):
    require(len(ranking) >= 24, 'fewer than 24 eligible identities')
    return ranking[:24]

def split(cohort, protocol_hash=a.P26):
    require(len(cohort) == 24 and len({r['isin'] for r in cohort}) == 24, 'cohort must contain 24 unique identities')
    ordered = sorted([dict(isin=r['isin'], cohort_rank=r['rank'], split_hash=a.sha((protocol_hash + ':' + r['isin']).encode('utf-8'))) for r in cohort], key=lambda r: (r['split_hash'], r['isin']))
    for i, row in enumerate(ordered): row['stratum'] = 'VISIBLE' if i < 16 else 'WITHHELD'
    return ordered

def outputs(rows, calendar, protocol, preflight):
    audit, identities, ranking = evaluate(rows, calendar['history']['dates'], calendar['liquidity']['dates'])
    require(len(audit) == 1838, 'universe count mismatch')
    cohort = select(ranking)
    assignments = split(cohort)
    contamination = dict(policy=protocol['contamination'], SBIN_isin='INE062A01020', SBIN_selected=any(r['isin']=='INE062A01020' for r in cohort),
        prior_exposed_periods=[['2025-09-01', '2026-03-06'], ['2026-03-09', '2026-09-08']], effect_on_selection='NONE; no removal or replacement',
        participation='Retain cohort/split/logistics accounting; exposed overlapping Stage B/C observations excluded from pristine inference, bootstrap inputs, participation denominators and gates')
    binding = dict(schema='PHASE28B_SELECTION_FREEZE_V1', cycle_id=protocol['cycle_id'], phase26_protocol_sha256=a.P26,
        corrected_input_hashes=preflight['verified_input_hashes'], corrected_calendar_sha256=preflight['corrected_calendar_sha256'], amendment_sha256=preflight['amendment_sha256'],
        selection_session=dict(date=a.SEL, final=True, instrument_type='STK', series='EQ', identity='ISIN', source_sha256=cohort[0]['source_sha256']),
        eligibility_rule_identity=dict(protocol_sha256=a.P26, history=protocol['history'], liquidity=protocol['liquidity'], eligibility=protocol['eligibility'],
            identity_review='Official effective observed same-ISIN history; no different-ISIN merge; unresolved symbol/ISIN mapping fails closed'),
        ranking_identity=['exact Decimal 60-session median descending', 'ISIN ascending', 'selection symbol ascending'],
        selected_ordered_isins=[r['isin'] for r in cohort], visible_withheld_assignments=assignments, contamination=contamination,
        eligibility_audit_sha256=a.sha(a.canonical(audit)), identity_audit_sha256=a.sha(a.canonical(identities)), liquidity_ranking_sha256=a.sha(a.canonical(ranking)))
    digest = a.sha(a.canonical(binding))
    return dict(cohort_selection_manifest=dict(status='FROZEN', canonicalization='UTF-8 JSON sorted keys, comma/colon separators, ensure_ascii=false; canonical_binding only', phase28b_selection_sha256=digest, canonical_binding=binding, cohort=cohort),
        eligibility_audit=dict(raw_universe_count=len(audit), eligible_count=len(ranking), excluded_count=len(audit)-len(ranking), exclusion_counts=dict(collections.Counter(reason for r in audit for reason in r['exclusion_reasons'])), counts_overlap=True, candidates=audit),
        liquidity_ranking=dict(ranking=ranking, replacement_allowed=False),
        identity_continuity_audit=dict(review=identities, different_isin_merges=0, source='All 253 verified FINAL bhavcopies; per-row provenance in frozen derived layer', no_future_identity_or_performance_used=True,
            review_scope='Official STK/EQ identities through selection; no claim that all corporate actions are absent. Official cash turnover is not adjusted price. Same-ISIN rename dates are observed NORMAL-session boundaries, not inferred legal dates.'),
        visible_withheld_split=dict(algorithm=protocol['split']['algorithm'], visible=16, withheld=8, assignments=assignments),
        future_intraday_request_manifest=dict(status='PLAN_ONLY_NOT_AUTHORIZED', executed=False, phase28b_selection_sha256=digest, interval='FIVE_MINUTE', requests=[],
            cohort=[dict(isin=r['isin'], selection_symbol=r['symbol'], stratum=next(x['stratum'] for x in assignments if x['isin']==r['isin'])) for r in cohort], stages=calendar['stages'], corrected_calendar_sha256=preflight['corrected_calendar_sha256'],
            required_before_execution=['Separate explicit acquisition authorization', 'Effective-dated authoritative ISIN/symbol/provider-token mapping', 'Corporate-action and provider coverage validation without replacement', 'Deterministic provider-limit-aware nonoverlapping chunks; bounded logged retry', 'Immutable stage/ISIN storage, hashes, roles, withheld development sealing', 'Frozen contamination exclusions'], contamination=contamination, candle_requests=0, broker_requests=0))

def no_network(*args, **kwargs):
    raise RuntimeError('Phase28B is offline; network prohibited')

def run():
    socket.socket.connect = no_network
    socket.create_connection = no_network
    rows, calendar, protocol, preflight = precheck()
    products = outputs(rows, calendar, protocol, preflight)
    repeated = outputs(list(reversed(rows)), calendar, protocol, preflight)
    require(a.canonical(products) == a.canonical(repeated), 'repeatability failed')
    require(snapshot() == preflight['historical_file_hashes'], 'historical evidence changed')
    baseline()
    for name, value in products.items(): a.atomic(META / (name + '.json'), a.canonical(value) + b'\n', immutable=True)
    a.atomic(META / 'precheck.json', a.canonical(preflight) + b'\n', immutable=True)
    a.atomic(META / 'repeatability_audit.json', a.canonical(dict(status='PASS', method='Full selection recomputed with reversed input order; all products byte identical', phase28b_selection_sha256=products['cohort_selection_manifest']['phase28b_selection_sha256'], network_requests=0, broker_requests=0, candle_requests=0)) + b'\n', immutable=True)
    print(json.dumps(dict(freeze=products['cohort_selection_manifest']['phase28b_selection_sha256'], eligible=products['eligibility_audit']['eligible_count'], exclusions=products['eligibility_audit']['exclusion_counts'], cohort=[(r['rank'],r['isin'],r['symbol'],r['median_60_session_traded_value']) for r in products['cohort_selection_manifest']['cohort']]), indent=2))

if __name__ == '__main__':
    run()
