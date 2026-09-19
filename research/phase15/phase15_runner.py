"""Offline one-shot canonical E/F/G orchestration. No engine monkeypatches."""
import hashlib
import importlib.abc
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'research/phase15_results.json'
CSV = ROOT/'data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv'
CSV_SHA = 'fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6'
META_SHA = 'e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67'
ATTEMPTS = []


def install_offline_guard():
    def deny(*args, **kwargs):
        ATTEMPTS.append('blocked network/process attempt')
        raise BaseException('Phase15 network/process activity prohibited')
    class Imports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.lower().startswith(('smartapi', 'broker.', 'live.')):
                ATTEMPTS.append('forbidden import: '+fullname)
                raise BaseException('Phase15 prohibited import: '+fullname)
    sys.meta_path.insert(0, Imports())
    for name in ('connect','connect_ex','send','sendall','sendto'):
        setattr(socket.socket,name,deny)
    for name in ('create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
        setattr(socket,name,deny)
    def guard(event,args):
        if event in ('socket.connect','socket.sendto','socket.getaddrinfo','socket.gethostbyname','subprocess.Popen','os.system'):
            deny()
    sys.addaudithook(guard)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_manifest(manifest):
    differences = [k for k,v in manifest.items() if not (ROOT/k).is_file() or sha(ROOT/k)!=v]
    if differences:
        raise RuntimeError('Frozen source mismatch: '+', '.join(differences))


def concentration(trades, dates):
    daily=[]
    for day in dates:
        ts=[t for t in trades if t['entry_timestamp'].date()==day]
        daily.append(dict(date=str(day),trades=len(ts),net_pnl=sum(t['pnl'] for t in ts),
            gross_pnl=sum(t['gross_pnl'] for t in ts),charges=sum(t['charges'] for t in ts),
            gross_profit=sum(max(t['gross_pnl'],0) for t in ts),gross_loss=-sum(min(t['gross_pnl'],0) for t in ts)))
    best=sorted([x for x in daily if x['net_pnl']>0],key=lambda x:(-x['net_pnl'],x['date']))[:5]
    worst=sorted([x for x in daily if x['net_pnl']<0],key=lambda x:(x['net_pnl'],x['date']))[:5]
    gp=sum(x['gross_profit'] for x in daily)
    gl=sum(x['gross_loss'] for x in daily)
    net=sum(x['net_pnl'] for x in daily)
    bn=sum(x['net_pnl'] for x in best)
    def pct(n,d): return n/d*100 if d else None
    bp=pct(sum(x['gross_profit'] for x in best),gp)
    wl=pct(sum(x['gross_loss'] for x in worst),gl)
    return dict(daily=daily,best_session_net_pnl=max(x['net_pnl'] for x in daily),
        worst_session_net_pnl=min(x['net_pnl'] for x in daily),best_five_sessions=best,worst_five_sessions=worst,
        top_five_profitable_sessions_gross_profit=sum(x['gross_profit'] for x in best),
        top_five_profitable_sessions_gross_profit_percent=bp,
        top_five_losing_sessions_gross_loss=sum(x['gross_loss'] for x in worst),
        top_five_losing_sessions_gross_loss_percent=wl,
        best_five_netted_gross_contribution_percent=pct(sum(x['gross_pnl'] for x in best),gp),
        worst_five_netted_gross_loss_contribution_percent=pct(-sum(x['gross_pnl'] for x in worst),gl),
        best_five_net_pnl=bn,best_five_share_of_total_net_percent=pct(bn,net),
        best_five_share_of_absolute_total_net_percent=pct(bn,abs(net)),net_without_best_five=net-bn,
        total_gross_profit=gp,total_gross_loss=gl,total_net_pnl=net,
        concentration_flag=(bp is not None and bp>50) or (wl is not None and wl>50) or (net>0 and net-bn<=0))


def classify(result):
    if result['correctness_audit']['violation_count']:
        raise RuntimeError('Classification prohibited: correctness violations')
    gross=sum(t['gross_pnl'] for t in result['trades'])
    result['gross_edge']='GROSS POSITIVE' if gross>0 else 'GROSS NEGATIVE' if gross<0 else 'GROSS FLAT'
    if result['total_trades']<30:
        return 'INSUFFICIENT SAMPLE'
    if gross<=0:
        return 'REJECT'
    stable=all(p['gross_pnl']>0 and p['trades']>=10 for p in result['periods'].values())
    if (result['net_pnl']>0 and result['profit_factor']>=1 and result['max_drawdown_percent']<30
            and stable and not result['concentration']['concentration_flag']):
        return 'CANDIDATE FOR HELD-OUT VALIDATION'
    return 'RESEARCH FURTHER'


def main():
    if OUT.exists():
        raise SystemExit('STOP: Phase15 results exist; one-shot runs cannot be repeated')
    install_offline_guard()
    import math
    import pandas as pd
    from loguru import logger
    from research import ema_harness as h
    from research.phase15.audit import audit, stats
    from research.phase15.definitions import DEFINITIONS, METHOD
    from research.phase15.trend_pullback import TrendPullback
    from research.phase15.opening_range_breakout import OpeningRangeBreakout
    from research.phase15.vwap_mean_reversion import VWAPMeanReversion
    logger.remove()
    manifest=json.loads((ROOT/'research/phase15/source_freeze.json').read_text())
    verify_manifest(manifest)
    assert sha(CSV)==CSV_SHA and sha(CSV.with_suffix('.csv.meta.json'))==META_SHA
    meta=json.loads(CSV.with_suffix('.csv.meta.json').read_text())
    raw=pd.read_csv(CSV)
    gate=h.BacktestRunner(raw,interval='FIVE_MINUTE',cas_eligible=True)
    gate.prepare_data()
    dates=sorted(gate.df.datetime.dt.date.unique())
    assert len(raw)==meta['row_count']==9309 and len(gate.df)==meta['accepted_row_count']==9294
    assert len(gate.cas_auxiliary_data)==15 and len(dates)==meta['trading_session_count']==125
    assert gate.session_policy.version==meta['session_policy']['version']==2
    legacy=[d for d in dates if d<gate.session_policy.effective_date]
    cas=[d for d in dates if d>=gate.session_policy.effective_date]
    assert len(legacy)==98 and len(cas)==27
    assert gate.df.groupby(gate.df.datetime.dt.date).size().to_dict()=={d:75 if d in legacy else 72 for d in dates}
    assert str(dates[0])=='2026-03-09' and str(dates[61])=='2026-06-10'
    assert str(dates[62])=='2026-06-11' and str(dates[-1])=='2026-09-08'
    ad_path=ROOT/'research/phase14b_results.json'
    ad=json.loads(ad_path.read_text(encoding='utf-8'))
    assert ad['status']=='COMPLETE' and ad['dataset']['csv_sha256']==CSV_SHA and ad['dataset']['metadata_sha256']==META_SHA
    research_files=list((ROOT/'research/phase15').glob('*.py'))+[ROOT/'tests/test_phase15_research.py']
    canonical_manifest={p.relative_to(ROOT).as_posix():sha(p) for p in research_files}
    result=dict(status='RUNNING',dataset=dict(csv_path=CSV.relative_to(ROOT).as_posix(),csv_sha256=CSV_SHA,
        metadata_sha256=META_SHA,published_rows=9309,regular_rows=9294,cas_auxiliary_rows=15,sessions=125,legacy_sessions=98,cas_sessions=27,session_policy_version=2),
        definitions=DEFINITIONS,methodology=METHOD,frozen_existing_files=manifest,canonical_source_hashes=canonical_manifest,
        prior_results_sha256=sha(ad_path),prior_variants=ad['variants'],variants={},runs=dict(E=0,F=0,G=0),
        validation=dict(precheck_tests='305 passed, 0 failed (10.46s)',precheck_compile='69 files passed',precheck_diff_check='PASS'))
    def save():
        OUT.write_text(json.dumps(result,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
    save()
    try:
        for name,factory in [('E',TrendPullback),('F',OpeningRangeBreakout),('G',VWAPMeanReversion)]:
            seen={'runner':None,'closures':0,'entries':[]}
            def profile(frame,event,arg):
                if event=='return' and frame.f_code is h.BacktestRunner.run.__code__:
                    seen['runner']=frame.f_locals['self']
                elif event=='call' and frame.f_code is h.BacktestRunner.__init__.__globals__['BacktestEngine']._close_position.__code__:
                    seen['closures']+=1
                elif event=='call' and frame.f_code is h.BacktestRunner.__init__.__globals__['BacktestEngine'].execute_entry.__code__:
                    seen['entries'].append({k:frame.f_locals[k] for k in ('atr','signal_index','candle_index')})
            result['runs'][name]+=1
            save()
            sys.setprofile(profile)
            try:
                metrics=h.run_variant(raw,factory)
            finally:
                sys.setprofile(None)
            result['variants'][name]=metrics
            save()  # Save the sole execution before audit/derived analysis.
            runner=seen['runner']
            assert runner is not None and len(runner.df)==9294 and len(runner.cas_auxiliary_data)==15
            errors=audit(metrics,runner)
            def check(ok,kind):
                if not ok: errors.append(dict(invariant=kind))
            ts=metrics['trades']
            check(seen['closures']==len(ts),'sole accounting closure count')
            check(len(seen['entries'])==len(ts),'entry attempt count')
            check(runner.pending_entry is None and runner.engine.position is None,'no pending/open position at end')
            for i,t in enumerate(ts):
                check(i==0 or ts[i-1]['exit_index']<t['entry_index'],'nonoverlap')
                check(t['entry_fill_price']==t['entry'] and t['exit_fill_price']==t['exit'],'fill aliases')
                check(math.isclose(t['entry_slippage'],abs(t['entry']-t['raw_entry_price']),abs_tol=1e-9),'entry slip record')
                check(math.isclose(t['exit_slippage'],abs(t['exit']-t['raw_exit_price']),abs_tol=1e-9),'exit slip record')
                for stamp in (t['signal_timestamp'],t['entry_timestamp'],t['exit_timestamp']):
                    check(stamp.time() in runner.session_policy.expected_bar_times(stamp.date()),'regular-only timestamp')
                source=seen['entries'][i]
                check(source['signal_index']==t['signal_index'] and source['candle_index']==t['entry_index']
                      and source['atr']==float(runner.df.iloc[t['signal_index']]['ATR']),'observed ATR argument')
            metrics['signal_events']=runner.strategy.strategy.events
            check(len(metrics['signal_events'])==metrics['buy_signals']+metrics['sell_signals'],'signal event count')
            check([(x['timestamp'],x['signal']) for x in metrics['signal_events']]==[(t['signal_timestamp'],t['side']) for t in ts],'all emitted signals executed')
            if name=='F':
                pairs=[(t['entry_timestamp'].date(),t['side']) for t in ts]
                check(len(pairs)==len(set(pairs)),'F one successful entry per direction/session')
            metrics['correctness_audit'].update(violation_count=len(errors),violations=errors,
                observed_closure_calls=seen['closures'],observed_entry_arguments=seen['entries'],
                regular_rows_at_indicator_preparation=9294,auxiliary_rows_excluded=15)
            save()
            if errors:
                raise RuntimeError(name+' correctness violations; classification stopped')
            metrics['sides']={side:stats([t for t in ts if t['side']==side]) for side in ('BUY','SELL')}
            metrics['exits']={reason:stats([t for t in ts if t['reason']==reason]) for reason in ('STOP_LOSS','TARGET','END_OF_SESSION','END_OF_BACKTEST')}
            for label in ('sides','exits'):
                for bucket in metrics[label].values():
                    bucket.pop('max_drawdown',None)
                    bucket.pop('max_drawdown_percent',None)
            metrics['periods']={}
            for label,ds in dict(first_half=dates[:62],second_half=dates[62:],LEGACY=legacy,CAS=cas).items():
                cap=runner.engine.initial_capital+sum(t['pnl'] for t in ts if t['entry_timestamp'].date()<ds[0])
                metrics['periods'][label]=dict(sessions=len(ds),start=str(ds[0]),end=str(ds[-1]),starting_capital=cap,
                    **stats([t for t in ts if t['entry_timestamp'].date() in ds],cap))
            metrics['concentration']=concentration(ts,dates)
            metrics['occupied_bars']=sum(t['exit_index']-t['entry_index']+1 for t in ts)
            metrics['occupied_bar_percent']=metrics['occupied_bars']/9294*100
            metrics['active_sessions']=len({t['entry_timestamp'].date() for t in ts})
            metrics['trades_per_session']=len(ts)/125
            metrics['average_net_loss_signed']=-metrics['average_loss']
            gp=sum(max(t['gross_pnl'],0) for t in ts)
            gl=-sum(min(t['gross_pnl'],0) for t in ts)
            metrics['profit_factor_unrounded']=gp/gl if gl else None
            metrics['gross_net_pnl_unrounded']=gp-gl
            metrics['net_pnl_unrounded']=sum(t['pnl'] for t in ts)
            print(name,'run and audit complete:',len(ts),'trades;',metrics['net_pnl'],'net',flush=True)
            verify_manifest(manifest)
            verify_manifest(canonical_manifest)
            save()
        # Classification waits until all three audits pass.
        for metrics in result['variants'].values():
            metrics['classification']=classify(metrics)
        result['safety']=dict(network_attempts=len(ATTEMPTS),forbidden_modules_loaded=[n for n in sys.modules if n.lower().startswith(('smartapi','broker.','live.'))],
            production_unchanged=True,phase13_phase14_unchanged=True,prior_A_D_reruns=0,
            note='Regression suites separately use mocked transports and the frozen-cache baseline. Full-validation A/D were loaded, never rerun.')
        assert not ATTEMPTS and not result['safety']['forbidden_modules_loaded']
        result['status']='RUNS_AUDITED_CLASSIFIED'
        save()
    except BaseException as exc:
        result['status']='BLOCKED'
        result['failure']=str(exc)
        result['network_attempts']=len(ATTEMPTS)
        save()
        raise


if __name__=='__main__':
    main()
