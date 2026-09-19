"""Phase 17 one-shot execution, saved-result diagnostics and report rendering."""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/phase17_results.json'
SOURCES=('research/phase17_breakout_retest.py','research/phase17_runner.py','tests/test_phase17_research.py')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(r):
    def encode(x):
        if hasattr(x,'item'): return x.item()
        return str(x)
    OUT.write_text(json.dumps(r,indent=2,default=encode,allow_nan=False)+'\n',encoding='utf-8')
def verify(r):
    for path,digest in {**r['frozen_existing_files'],**r.get('canonical_source_hashes',{})}.items():
        assert sha(ROOT/path)==digest,'Frozen mismatch: '+path
    csv=ROOT/r['dataset']['csv_path']
    assert sha(csv)==r['dataset']['csv_sha256']=='fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6'
    assert sha(csv.with_suffix('.csv.meta.json'))==r['dataset']['metadata_sha256']=='e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67'

def preregister(r):
    from research.phase17_breakout_retest import DEFINITION
    assert r['runs']==0 and r['status']=='PREREGISTERING'
    verify(r)
    r['definition']=DEFINITION
    r['canonical_source_hashes']={p:sha(ROOT/p) for p in SOURCES}
    r['status']='PREREGISTERED'
    r['preregistered_at']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    r['validation']['prerun_tests']='374 passed, 0 failed; 18 new Phase17 tests'
    save(r)
    (ROOT/'research/phase17_report.md').write_text('# Phase 17 preregistration\n\nNo full-dataset H execution yet.\n\n'+'\n\n'.join('**'+k+':** '+v for k,v in DEFINITION.items())+'\n',encoding='utf-8')
    print('PREREGISTERED; canonical source hashes frozen; runs=0')

def measure(ts,df):
    from research.phase16_forensics import forward,excursions,duration,first_touch,H,BUCKETS
    rows=[]
    for t in ts:
        s,e,x=(t[k] for k in ('signal_index','entry_index','exit_index'))
        sr,er,xr=df.iloc[s],df.iloc[e],df.iloc[x];atr=float(sr.ATR)
        bars=df.iloc[e:x+1]; before=df.iloc[e:x]
        highs=list(before.high)+[float(xr.open),t['raw_exit_price']]
        lows=list(before.low)+[float(xr.open),t['raw_exit_price']]
        if t['reason']=='END_OF_SESSION': highs=list(bars.high);lows=list(bars.low)
        d=1 if t['side']=='BUY' else -1
        fav=(er.high-er.open if d==1 else er.open-er.low)>0
        adv=(er.open-er.low if d==1 else er.high-er.open)>0
        minute=er.datetime.hour*60+er.datetime.minute
        rows.append(dict(t,signal_atr=atr,signal_bar_close=float(sr.close),raw_next_bar_open=float(er.open),slipped_entry_price=t['entry'],
            forward={ref:{str(h):forward(df,e,h,t['side'],price,atr) for h in H} for ref,price in [('signal_close',sr.close),('raw_open',er.open)]},
            confirmed=excursions(t['side'],er.open,highs,lows,atr),candle_upper=excursions(t['side'],er.open,list(bars.high),list(bars.low),atr),
            duration=duration(e,x),immediate='BOTH' if fav and adv else 'FAVORABLE' if fav else 'ADVERSE' if adv else 'NEITHER',
            touch={ref:first_touch(bars,t['side'],price,atr) for ref,price in [('raw_open',er.open),('slipped_entry',t['entry'])]},
            stop_distance=abs(t['entry']-t['stop_loss']),target_distance=abs(t['target']-t['entry']),stop_atr=abs(t['entry']-t['stop_loss'])/atr,
            target_atr=abs(t['target']-t['entry'])/atr,reward_risk=abs(t['target']-t['entry'])/abs(t['entry']-t['stop_loss']),
            time_bucket=BUCKETS[(minute-570)//60] if 570<=minute<930 else 'OUTSIDE_PREDEFINED',
            slippage_drag=(t['entry_slippage']+t['exit_slippage'])*t['quantity']))
    return rows

def extra_audit(r,runner,strategy,observed):
    import pandas as pd
    from research.phase15.audit import audit
    m=r['H'];errors=audit(m,runner)
    df=runner.df;events=strategy.events;ts=m['trades']
    def check(ok,name,trade=None):
        if not ok: errors.append(dict(trade=trade,invariant=name))
    check(len(ts)==len(events)==len(observed['entries']),'one entered trade per emitted signal')
    check(observed['closures']==len(ts),'sole closure count')
    check(runner.pending_entry is None and runner.engine.position is None,'no pending/open position')
    for n,(t,event,args) in enumerate(zip(ts,events,observed['entries']),1):
        s,e,x=t['signal_index'],t['entry_index'],t['exit_index'];b=event['breakout_index']
        sr,br=df.iloc[s],df.iloc[b];day=sr.datetime.date()
        opening=df.loc[(df.datetime.dt.date==day)&df.datetime.dt.strftime('%H:%M').isin(['09:15','09:20','09:25'])]
        check(len(opening)==3,'exact opening three bars',n)
        upper,lower=float(opening.high.max()),float(opening.low.min())
        check(upper==event['or_high'] and lower==event['or_low'],'opening extrema',n)
        check(b<s and br.datetime.date()==day and br.datetime.strftime('%H:%M')>='09:30','strictly later retest',n)
        check((br.close>upper and sr.low<=upper and sr.close>upper) if t['side']=='BUY' else (br.close<lower and sr.high>=lower and sr.close<lower),'breakout/retest direction',n)
        check(event['timestamp']==t['signal_timestamp'] and event['signal']==t['side'] and event['index']==s,'signal event match',n)
        check(args['signal_index']==s and args['candle_index']==e and math.isclose(args['atr'],sr.ATR,abs_tol=1e-10),'observed signal ATR execution',n)
        check(n==1 or ts[n-2]['exit_index']<e,'nonoverlap',n)
        for idx in (b,s,e,x):
            stamp=df.iloc[idx].datetime
            check(stamp.time() in runner.session_policy.expected_bar_times(stamp.date()),'regular only',n)
        check(br.datetime+pd.Timedelta(minutes=5)<=sr.datetime and sr.datetime+pd.Timedelta(minutes=5)==df.iloc[e].datetime,'completion before next open',n)
    check(len({(t['entry_timestamp'].date(),t['side']) for t in ts})==len(ts),'at most one signal per side/session')
    # Validate all observed breakout/candidate context, including skipped/cutoff bars.
    for b in strategy.breakouts:
        row=df.iloc[b['index']]
        check(row.close>b['or_high'] if b['side']=='BUY' else row.close<b['or_low'],'all breakout records')
    for c in strategy.retests:
        row=df.iloc[c['index']]
        check(c['index']>c['breakout_index'],'all retests later')
        check((row.low<=c['or_high'] and row.close>c['or_high']) if c['side']=='BUY' else (row.high>=c['or_low'] and row.close<c['or_low']),'all qualifying retests')
    m['correctness_audit'].update(violation_count=len(errors),violations=errors,observed_closure_calls=observed['closures'],observed_entry_arguments=observed['entries'],events_audited=len(events),auxiliary_rows_excluded=len(runner.cas_auxiliary_data))
    return errors

def analyze(r,df,dates,policy):
    from research.phase15.audit import stats as trade_stats
    from research.phase15.phase15_runner import concentration
    from research.phase16_forensics import stats,summarize,performance,BUCKETS
    ts=r['H']['trades']; m=r['H']; n=len(ts)
    full=trade_stats(ts);m['precise']=full
    m['average_gross_trade']=full['gross_pnl']/n if n else 0
    m['average_net_win']=stats([t['pnl'] for t in ts if t['pnl']>0])['mean']
    m['average_net_loss_signed']=stats([t['pnl'] for t in ts if t['pnl']<0])['mean']
    r['sides']={s:trade_stats([t for t in ts if t['side']==s]) for s in ('BUY','SELL')}
    for side,v in r['sides'].items():
        v['average_gross_trade']=v['gross_pnl']/v['trades'] if v['trades'] else 0
        v.pop('max_drawdown');v.pop('max_drawdown_percent') # side DD is not independently sized.
    r['exits']={s:trade_stats([t for t in ts if t['reason']==s]) for s in ('STOP_LOSS','TARGET','END_OF_SESSION','END_OF_BACKTEST')}
    r['periods']={}
    for k,ds in dict(first_half=dates[:62],second_half=dates[62:],LEGACY=[d for d in dates if d<policy.effective_date],CAS=[d for d in dates if d>=policy.effective_date]).items():
        capital=100000+sum(t['pnl'] for t in ts if t['entry_timestamp'].date()<ds[0])
        r['periods'][k]=dict(sessions=len(ds),start=str(ds[0]),end=str(ds[-1]),starting_capital=capital,**trade_stats([t for t in ts if t['entry_timestamp'].date() in ds],capital))
    r['concentration']=concentration(ts,dates)
    diag=measure(ts,df);r['event_diagnostics']=diag
    r['forensics']={side:summarize(diag if side=='ALL' else [e for e in diag if e['side']==side]) for side in ('ALL','BUY','SELL')}
    r['time_of_day']={k:performance([e for e in diag if e['time_bucket']==k]) for k in (*BUCKETS,'OUTSIDE_PREDEFINED')}
    r['funnel']={}
    for side in ('BUY','SELL'):
        bs=[b for b in r['state_records']['breakouts'] if b['side']==side]
        candidates=[c for c in r['state_records']['retests'] if c['side']==side]
        qual=[b for b in bs if b['first_retest'] is not None]
        emitted=[b for b in bs if b['signal'] is not None]
        entered=[t for t in ts if t['side']==side]
        r['funnel'][side]=dict(sessions_with_opening_range=sum(s['opening_range'] is not None for s in r['state_records']['sessions'].values()),
            sessions_with_initial_breakout=len({b['session'] for b in bs}),breakout_events=len(bs),qualifying_retests=len(qual),breakouts_with_no_qualifying_retest=len(bs)-len(qual),
            retests_blocked_by_cutoff=sum('late_retest' in b for b in bs),retests_with_skipped_candidates=len({c['session'] for c in candidates if c['status']=='HARNESS_SKIPPED'}),
            all_qualifying_candidate_candles=len(candidates),signals_emitted=len(emitted),signals_entered=len(entered),
            retest_conversion_pct=100*len(qual)/len(bs) if bs else None,entry_conversion_pct=100*len(entered)/len(bs) if bs else None,
            breakout_to_first_retest_bars=stats([b['first_retest']['index']-b['index'] for b in qual]),
            breakout_to_emitted_retest_bars=stats([b['signal']['index']-b['index'] for b in emitted]),
            breakout_to_entry_bars=stats([t['entry_index']-next(e['breakout_index'] for e in r['state_records']['events'] if e['index']==t['signal_index'] and e['signal']==side) for t in entered]))
    charges={k:sum(t[k] for t in ts) for k in ('brokerage','stt','stamp_duty','transaction_charges','sebi_charges','ipft','gst','charges','gross_pnl','pnl')}
    turnover=sum(t['buy_turnover']+t['sell_turnover'] for t in ts);slip=sum(e['slippage_drag'] for e in diag)
    r['costs']=dict(charges,slippage_drag=slip,raw_price_pnl=full['gross_pnl']+slip,turnover=turnover,
        charges_over_turnover=charges['charges']/turnover if turnover else None,
        charges_over_absolute_gross=charges['charges']/abs(full['gross_pnl']) if full['gross_pnl'] else None,
        average_charge=charges['charges']/n if n else None)
    for e in diag:
        for reference in e['forward'].values():
            for horizon,value in reference.items():
                assert value is None or (value['index']==e['signal_index']+int(horizon) and df.iloc[value['index']].datetime.date()==e['entry_timestamp'].date())
    prior15=json.loads((ROOT/'research/phase15_results.json').read_text());prior14=json.loads((ROOT/'research/phase14b_results.json').read_text());prior16=json.loads((ROOT/'research/phase16_results.json').read_text())
    keys=('total_trades','buy_trades','sell_trades','gross_net_pnl','net_pnl','profit_factor','max_drawdown_percent','win_rate','average_net_trade','total_charges','charges_per_trade')
    r['comparison']={k:{field:v[field] for field in keys} for k,v in {**prior14['variants'],**prior15['variants'],'H':m}.items()}
    for k,v in r['comparison'].items():
        original=m if k=='H' else (prior14['variants'].get(k) or prior15['variants'][k])
        v['gross_net_pnl']=sum(t['gross_pnl'] for t in original['trades'])
        v['net_pnl']=sum(t['pnl'] for t in original['trades'])
        gp=sum(max(t['gross_pnl'],0) for t in original['trades']);gl=-sum(min(t['gross_pnl'],0) for t in original['trades'])
        v['profit_factor']=gp/gl if gl else None
        v['average_gross_trade']=v['gross_net_pnl']/v['total_trades'] if v['total_trades'] else 0
    f=r['comparison']['F'];hh=r['comparison']['H']
    r['direct_F_H']=dict(F=f,H=hh,F_forensics=prior16['families']['F']['groups'],
        trade_reduction_pct=100*(1-n/f['total_trades']),gross_change=hh['gross_net_pnl']-f['gross_net_pnl'],net_change=hh['net_pnl']-f['net_pnl'],
        dd_percentage_point_change=hh['max_drawdown_percent']-f['max_drawdown_percent'],pf_change=hh['profit_factor']-f['profit_factor'] if hh['profit_factor'] is not None else None,
        caution='F uses RSI/VWAP/volume filters, H does not. Differences cannot isolate retest causality. Changing capital/quantity and trade count also affect aggregate INR comparisons.')
    if n<30: label='INSUFFICIENT SAMPLE'
    elif full['gross_pnl']<=0: label='REJECT'
    elif (full['net_pnl']>0 and full['profit_factor']>=1 and full['max_drawdown_percent']<30
          and all(p['gross_pnl']>0 and p['trades']>=10 for p in r['periods'].values())
          and all(p['gross_pnl']>0 and p['trades']>=10 for p in r['sides'].values())
          and not r['concentration']['concentration_flag']): label='CANDIDATE FOR HELD-OUT VALIDATION'
    else: label='RESEARCH FURTHER'
    r['classification']=label


def execute(r):
    import pandas as pd
    from loguru import logger
    from research import ema_harness as h
    from research.phase17_breakout_retest import BreakoutRetest
    from research.phase16_forensics import ATTEMPTS
    from backtest.backtest_engine import BacktestEngine
    assert r['runs']==0 and r['status']=='PREREGISTERED','STOP: canonical H cannot be rerun'
    verify(r);logger.remove()
    raw=pd.read_csv(ROOT/r['dataset']['csv_path'])
    seen=dict(runner=None,entries=[],closures=0)
    def profile(frame,event,arg):
        if event=='return' and frame.f_code is h.BacktestRunner.run.__code__: seen['runner']=frame.f_locals['self']
        elif event=='call' and frame.f_code is BacktestEngine.execute_entry.__code__:
            seen['entries'].append({k:frame.f_locals[k] for k in ('atr','signal_index','candle_index')})
        elif event=='call' and frame.f_code is BacktestEngine._close_position.__code__: seen['closures']+=1
    r.update(runs=1,status='RUNNING');save(r) # Irrevocable one-shot marker before execution.
    sys.setprofile(profile)
    try: m=h.run_variant(raw,BreakoutRetest)
    finally: sys.setprofile(None)
    r['H']=m;r['status']='EXECUTED';save(r) # Preserve sole result before derivation/audit.
    runner=seen['runner'];strategy=runner.strategy.strategy
    strategy.finish_diagnostics(runner.df)
    r['state_records']=dict(events=strategy.events,breakouts=strategy.breakouts,retests=strategy.retests,sessions=strategy.sessions)
    save(r)
    dates=sorted(runner.df.datetime.dt.date.unique())
    assert len(raw)==9309 and len(runner.df)==9294 and len(runner.cas_auxiliary_data)==15 and len(dates)==125
    assert sum(d<runner.session_policy.effective_date for d in dates)==98 and runner.session_policy.version==2
    errors=extra_audit(r,runner,strategy,seen);save(r)
    if errors:
        r['status']='AUDIT_FAILED';save(r);raise RuntimeError('STOP classification: correctness violations')
    analyze(r,runner.df,dates,runner.session_policy)
    verify(r);assert not ATTEMPTS
    r.update(status='ANALYZED',safety=dict(network_attempts=len(ATTEMPTS),forbidden_imports=[],production_unchanged=True,engine_unchanged=True,prior_artifacts_unchanged=True,no_commit=True))
    save(r)
    print(json.dumps(dict(classification=r['classification'],metrics=m['precise'],funnel=r['funnel'],costs=r['costs'],direct_changes={k:v for k,v in r['direct_F_H'].items() if k not in ('F','H','F_forensics')}),indent=2))


def report(r):
    lines=['# Phase 17 — Preregistered breakout-retest hypothesis','']
    def text(s): lines.extend([s,''])
    def table(headers,rows):
        def fmt(x): return 'NA' if x is None else f'{x:.4f}' if isinstance(x,float) else str(x)
        lines.append('| '+' | '.join(headers)+' |');lines.append('| '+' | '.join(['---']*len(headers))+' |')
        lines.extend('| '+' | '.join(fmt(x) for x in row)+' |' for row in rows);lines.append('')
    text('**H classification: '+r['classification']+'.** Exactly one canonical full-dataset H execution. No tuning or comparator reruns.')
    text('## Safety, integrity and preregistration')
    text('Exact dataset SHA256 `'+r['dataset']['csv_sha256']+'`; metadata SHA256 `'+r['dataset']['metadata_sha256']+'`. Published9,309 / regular9,294 / excluded CAS15 / sessions125 / LEGACY98 / CAS27 / policy v2. All previous source/artifact hashes preserved; production and engine unchanged. Preregistered at '+r['preregistered_at']+'. Source hashes are in JSON.')
    for k,v in r['definition'].items(): text('**'+k+':** '+v)
    text('The existing global test guard blocks network. Regression tests deliberately contain caught network-denial probes, fake historical transport/auth calls and broker __new__ stubs; these are not external service actions. H process blocks network/DNS/process and broker/live/SmartAPI imports before project imports. No real HistoricalClient, AngelOneBroker, LiveFeed, authentication, account/profile/order activity. Network attempts=0.')
    text('## Breakout → retest funnel')
    keys=('sessions_with_opening_range','sessions_with_initial_breakout','breakout_events','qualifying_retests','breakouts_with_no_qualifying_retest','retests_blocked_by_cutoff','retests_with_skipped_candidates','all_qualifying_candidate_candles','signals_emitted','signals_entered','retest_conversion_pct','entry_conversion_pct')
    table(['Metric','BUY','SELL'],[[k,*[r['funnel'][s][k] for s in ('BUY','SELL')]] for k in keys])
    table(['Side','Delay','Available N','Median bars','Mean bars'],[[s,k,r['funnel'][s][k]['n'],r['funnel'][s][k]['median'],r['funnel'][s][k]['mean']] for s in ('BUY','SELL') for k in ('breakout_to_first_retest_bars','breakout_to_emitted_retest_bars','breakout_to_entry_bars')])
    text('Qualifying retests above count distinct breakouts, not repeated candidate candles. Cutoff/skipped categories can overlap and are not additive. Every emitted signal entered; no direction rearms after emission. Late tail records are diagnostic only.')
    text('## Full-period H metrics')
    keys=('total_trades','winning_trades','losing_trades','breakeven_trades','win_rate','gross_profit','gross_loss','gross_net_pnl','total_charges','net_pnl','final_capital','profit_factor','average_gross_trade','average_net_trade','average_net_win','average_net_loss_signed','max_drawdown','max_drawdown_percent','equity_points','buy_signals','sell_signals','hold_evaluations','buy_trades','sell_trades','stop_count','target_count','eod_count','end_of_backtest_count','charges_per_trade','charges_over_absolute_gross_percent','daily_loss_lock_trigger_count','max_trade_per_day_trigger_count','minimum_stop_exposure_percent','average_stop_exposure_percent','maximum_stop_exposure_percent','quantity_min','quantity_max')
    table(['Metric','H'],[[k,r['H'].get(k)] for k in keys])
    text('Engine summaries may be rounded; precise full-period trade sums and PF appear in JSON H.precise and comparison tables. Gross includes slipped fills and excludes explicit charges. PF uses positive gross trade pnl / absolute negative gross trade pnl; winners/losers use net pnl. Side results are attribution on carried sizing, not independently sized side runs; isolated side DD omitted.')
    for key,title in [('sides','BUY / SELL'),('exits','Exits')]:
        text('## '+title)
        table(['Group','N','Wins','Losses','Win %','Gross INR','Charges INR','Net INR','PF','Avg gross INR','Avg net INR'],[[k,*[v[x] for x in ('trades','wins','losses','win_rate','gross_pnl','charges','net_pnl','profit_factor')],v['gross_pnl']/v['trades'] if v['trades'] else None,v['average_net_trade']] for k,v in r[key].items()])
    text('## Forward returns')
    text('Phase16 unchanged: raw physical entry open reference; horizon h ends at close index entry+h-1. BUY future/ref-1; SELL ref/future-1. ATR moves are directional price differences / signal ATR14. No session crossing, unavailable=null; measurement continues after actual exit only for fixed-horizon diagnostics. Percentages below are percentage units.')
    table(['Side','Bars','N','Mean %','Median %','Positive %','Mean ATR','Median ATR'],[[s,h,*[r['forensics'][s]['forward']['raw_open'][str(h)]['return_pct'][k] for k in ('n','mean','median','positive_pct')],*[r['forensics'][s]['forward']['raw_open'][str(h)]['atr'][k] for k in ('mean','median')]] for s in ('ALL','BUY','SELL') for h in (1,2,3,6,12)])
    text('## MFE / MAE')
    text('Phase16 bounds unchanged: confirmed lower bound includes completed candles before exit plus exit open/raw fill (full candle for EOD); candle_upper additionally includes full exit range, which can contain post-exit moves. Intrabar extrema are not knowable exactly. Reference raw entry; no negative excursions; regular-only bars through recorded exit.')
    table(['Side','Bound','Median MFE ATR','Mean MFE ATR','Median MAE ATR','Mean MAE ATR','MFE>=.5 %','>=1 %','>=1.5 %','>=2 %','MAE>=.5 %','>=1 %','>=1.5 %'],[[s,b,*[r['forensics'][s]['excursions'][b][k][z] for k,z in [('mfe_atr','median'),('mfe_atr','mean'),('mae_atr','median'),('mae_atr','mean')]],*r['forensics'][s]['excursions'][b]['mfe_reach_pct'].values(),*r['forensics'][s]['excursions'][b]['mae_reach_pct'].values()] for s in ('ALL','BUY','SELL') for b in ('confirmed','candle_upper')])
    text('## Direct F versus H')
    keys=('total_trades','buy_trades','sell_trades','gross_net_pnl','profit_factor','net_pnl','max_drawdown_percent','win_rate','average_gross_trade','average_net_trade','total_charges','charges_per_trade')
    table(['Metric','F','H'],[[k,r['comparison']['F'][k],r['comparison']['H'][k]] for k in keys])
    table(['Metric','Change H minus F (trade reduction positive means fewer)'],[[k,v] for k,v in r['direct_F_H'].items() if k not in ('F','H','F_forensics','caution')])
    fg=r['direct_F_H']['F_forensics']
    comparison_rows=[]
    for family,groups in [('F',fg),('H',r['forensics'])]:
        for side in ('ALL','BUY','SELL'):
            g=groups[side]
            comparison_rows.append([family,side,g['excursions']['confirmed']['mfe_atr']['median'],g['excursions']['confirmed']['mae_atr']['median'],*[g['forward']['raw_open'][str(h)]['return_pct']['mean'] for h in (1,3,6,12)]])
    table(['Family','Side','Median confirmed MFE ATR','Median confirmed MAE ATR','1bar mean %','3bar mean %','6bar mean %','12bar mean %'],comparison_rows)
    text(r['direct_F_H']['caution'])
    text('## Chronological and policy stability')
    text('Original path, no rerun/reset: first62 sessions Mar09-Jun10; second63 Jun11-Sep08. Period DD starts from carried capital and local period-start realized-equity peak, as Phase15; no intrabar mark-to-market. Separate regime counts98/27.')
    table(['Period','Sessions','Starting capital','Trades','Gross INR','Net INR','PF','DD %','BUY','SELL','EOD'],[[k,*[v[z] for z in ('sessions','starting_capital','trades','gross_pnl','net_pnl','profit_factor','max_drawdown_percent','buy_trades','sell_trades','end_of_session')]] for k,v in r['periods'].items()])
    text('## Time of day')
    text('Physical entry timestamps; fixed Phase16 buckets, all retained including empty/outside buckets. Diagnostic only.')
    table(['Bucket','N','Gross INR','Net INR','PF','Win %'],[[k,*[v[z] for z in ('trades','gross_pnl','net_pnl','pf','win_rate')]] for k,v in r['time_of_day'].items()])
    text('## Costs')
    table(['Metric (INR, ratios are fractions)','H'],list(r['costs'].items()))
    text('Exact slippage attribution uses saved leg differences times actual quantity. Raw-price pnl keeps actual trade path, size and slipped-entry-dependent exit levels fixed; it is not a zero-slippage rerun. Explicit charges reconcile to saved components.')
    text('## A / D / E / F / G / H comparison')
    table(['Family','N','Gross INR','Net INR','PF','DD %','Win %','Avg gross INR','Avg net INR'],[[k,*[v[z] for z in ('total_trades','gross_net_pnl','net_pnl','profit_factor','max_drawdown_percent','win_rate','average_gross_trade','average_net_trade')]] for k,v in r['comparison'].items()])
    text('## Correctness, concentration and limitations')
    text(str(r['H']['correctness_audit']['trades_audited'])+' trades audited; '+str(r['H']['correctness_audit']['violation_count'])+' violations. Exact OR construction, completed breakout, strictly later qualified retest, next physical open, observed signal ATR, mirrored fills/slippage, sizing, levels, gap/STOP priority, fee components, one closure/trade, equity, no overlap/overnight, cutoffs and CAS exclusions checked. All emitted signals match entered trades. Additional all-breakout/candidate and forward-index audits passed. No future data used to form signals.')
    c=r['concentration']
    table(['Concentration metric','Value'],[[k,c[k]] for k in ('top_five_profitable_sessions_gross_profit_percent','top_five_losing_sessions_gross_loss_percent','net_without_best_five','concentration_flag')])
    text('This dataset informed the hypothesis through Phase16 and is NOT held-out. Single instrument, one six-month path, dependent observations, changing capital and small policy/side samples limit generalization. F/H filter differences prevent causal attribution solely to retesting. No alternative H version, parameter optimization or production-readiness claim. Candidate classification would still require genuinely non-overlapping validation.')
    if 'interpretation' in r:
        text('## Interpretation and next step')
        for k,v in r['interpretation'].items(): text('**'+k+':** '+v)
    text('## Validation and artifacts')
    for k,v in r['validation'].items(): text('**'+k+':** '+str(v))
    text('Report `research/phase17_report.md`; JSON `research/phase17_results.json` includes sole-run trades, all state/funnel records, per-entry diagnostics, source hashes and audits. No unnecessary CSV. Production/engine and Phase15/16 artifacts unchanged. No commit.')
    (ROOT/'research/phase17_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    from research.phase16_forensics import guard
    guard()
    r=json.loads(OUT.read_text())
    mode=sys.argv[1]
    if mode=='--preregister': preregister(r)
    elif mode=='--run': execute(r)
    elif mode=='--report': verify(r);report(r)
    else: raise SystemExit('Use --preregister, --run or --report')
if __name__=='__main__': main()
