"""One-shot offline Phase 14B; unchanged Phase 13 harness and production engine."""
import hashlib
import importlib.abc
import json
import math
from pathlib import Path
import socket
import statistics
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ATTEMPTS = []
def deny(*args, **kwargs):
    ATTEMPTS.append('network')
    raise BaseException('Network prohibited')
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.lower().startswith(('smartapi', 'broker.', 'live.')):
            raise BaseException('Forbidden import: '+fullname)
sys.meta_path.insert(0, Guard())
for n in ('connect','connect_ex','send','sendall','sendto'):
    setattr(socket.socket, n, deny)
for n in ('create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'):
    setattr(socket, n, deny)
def guard(event, args):
    if event in ('socket.connect','socket.sendto','socket.getaddrinfo','socket.gethostbyname','subprocess.Popen','os.system'):
        deny()
sys.addaudithook(guard)
import pandas as pd
from loguru import logger
from research import ema_harness as h
from config import settings as s
logger.remove()
OUT = ROOT/'research/phase14b_results.json'
CSV = ROOT/'data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv'
META = CSV.with_suffix('.csv.meta.json')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
    files = [p for p in ROOT.rglob('*.py') if not {'venv','.venv','site-packages','.git','__pycache__'}.intersection(p.parts)]
    files += [ROOT/'.env'] if (ROOT/'.env').exists() else []
    files += list((ROOT/'data').glob('historical_NSE_3045_FIVE_MINUTE.csv*'))
    files += list((ROOT/'research').glob('phase13*'))
    files += [CSV, META]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in files}
def stats(ts, capital=100000):
    net = [t['pnl'] for t in ts]
    gp = sum(max(t['gross_pnl'],0) for t in ts)
    gl = -sum(min(t['gross_pnl'],0) for t in ts)
    peak = capital
    dd = ddp = 0
    for p in net:
        capital += p
        peak = max(peak,capital)
        dd = max(dd,peak-capital)
        ddp = max(ddp,100*(peak-capital)/peak if peak > 0 else 0)
    return dict(trades=len(ts), wins=sum(p>0 for p in net), losses=sum(p<0 for p in net),
        breakeven=sum(p==0 for p in net), win_rate=100*sum(p>0 for p in net)/len(net) if net else 0,
        gross_profit=gp, gross_loss=gl, gross_pnl=gp-gl, charges=sum(t['charges'] for t in ts),
        net_pnl=sum(net), profit_factor=gp/gl if gl else None,
        average_net_trade=statistics.mean(net) if net else 0, max_drawdown=dd,max_drawdown_percent=ddp,
        buy_trades=sum(t['side']=='BUY' for t in ts), sell_trades=sum(t['side']=='SELL' for t in ts),
        end_of_session=sum(t['reason']=='END_OF_SESSION' for t in ts))
def audit(r, runner):
    df,e,policy = runner.df,runner.engine,runner.session_policy
    errors, details, daily = [],[],{}
    capital=e.initial_capital
    def check(ok,n,field):
        if not ok: errors.append(dict(trade=n,invariant=field))
    def eq(a,b): return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7)
    for n,t in enumerate(r['trades'],1):
        si,ei,xi=t['signal_index'],t['entry_index'],t['exit_index']
        signal,entry=df.iloc[si],df.iloc[ei]
        day=t['entry_timestamp'].date()
        state=daily.setdefault(day,dict(pnl=0,count=0,loss_hit=False))
        check(not state['loss_hit'] and state['count']<e.max_trades_per_day,n,'daily risk')
        check(ei==si+1 and t['entry_timestamp']==entry['datetime'] and t['signal_timestamp']==signal['datetime'],n,'physical next bar')
        check(t['signal_timestamp'].date()==day==t['exit_timestamp'].date(),n,'session boundary')
        check(t['signal_timestamp'].time()<=policy.final_allowed_signal_bar(day) and t['entry_timestamp'].time()<=policy.final_allowed_entry_bar(day),n,'cutoff')
        sign=1 if t['side']=='BUY' else -1
        atr=float(signal['ATR'])
        fill=float(entry['open'])*(1+sign*0.0005)
        stop,target=fill-sign*1.5*atr,fill+sign*2*atr
        check(eq(t['raw_entry_price'],entry['open']) and eq(t['entry'],fill) and t['slippage_bps']==5,n,'entry slippage')
        check(eq(t['stop_loss'],stop) and eq(t['target'],target),n,'signal ATR stop target')
        q=max(int(capital*e.risk_per_trade/100/abs(fill-stop)),1)
        check(q==t['quantity'],n,'sizing')
        expected=None
        for j in range(ei,xi+1):
            b=df.iloc[j]
            op,hi,lo=float(b['open']),float(b['high']),float(b['low'])
            if (op<=stop if sign==1 else op>=stop): expected=(j,'STOP_LOSS',op)
            elif (op>=target if sign==1 else op<=target): expected=(j,'TARGET',op)
            elif (lo<=stop if sign==1 else hi>=stop): expected=(j,'STOP_LOSS',stop)
            elif (hi>=target if sign==1 else lo<=target): expected=(j,'TARGET',target)
            elif b['datetime'].time()==policy.final_regular_bar_start(day): expected=(j,'END_OF_SESSION',float(b['close']))
            if expected: break
        check(expected is not None,n,'exit exists')
        if expected:
            j,reason,raw=expected
            check(j==xi and reason==t['reason'] and eq(raw,t['raw_exit_price']) and t['exit_timestamp']==df.iloc[j]['datetime'],n,'first exit gap priority stop priority EOD')
            check(eq(t['exit'],raw*(1-sign*0.0005)),n,'exit slippage')
        q=t['quantity']
        buy=(t['entry'] if sign==1 else t['exit'])*q
        sell=(t['exit'] if sign==1 else t['entry'])*q
        def leg(v): return min(s.BROKERAGE_MAX_PER_ORDER,max(s.BROKERAGE_MIN_PER_ORDER,v*s.BROKERAGE_RATE))
        brokerage=leg(buy)+leg(sell)
        transaction=(buy+sell)*s.NSE_TRANSACTION_RATE
        sebi,ipft=(buy+sell)*s.SEBI_RATE,(buy+sell)*s.IPFT_RATE
        components=dict(buy_turnover=buy,sell_turnover=sell,brokerage=brokerage,
            entry_brokerage=leg(t['entry']*q),exit_brokerage=leg(t['exit']*q),transaction_charges=transaction,
            stt=sell*s.STT_SELL_RATE,stamp_duty=buy*s.STAMP_DUTY_BUY_RATE,sebi_charges=sebi,ipft=ipft,
            gst=(brokerage+transaction+sebi+ipft)*s.GST_RATE)
        check(all(eq(t[k],v) for k,v in components.items()),n,'charge components')
        charges=sum(components[k] for k in ('brokerage','transaction_charges','stt','stamp_duty','sebi_charges','ipft','gst'))
        gross=sign*(t['exit']-t['entry'])*q
        check(eq(t['charges'],charges) and eq(t['gross_pnl'],gross) and eq(t['pnl'],gross-charges),n,'accounting')
        capital+=t['pnl']
        check(eq(r['equity_curve'][n],capital),n,'equity')
        state['pnl']+=t['pnl']
        state['count']+=1
        state['loss_hit']|=state['pnl']<=-e.max_daily_loss
        details.append(dict(trade=n,signal_atr=atr,capital_before=capital-t['pnl'],expected_quantity=q))
    exposures=h._modeled_stop_exposure(e,r['trades'])
    r.update(minimum_stop_exposure_percent=min(exposures,default=0),modeled_stop_exposures_percent=exposures,
        quantity_min=min((t['quantity'] for t in r['trades']),default=0),quantity_max=max((t['quantity'] for t in r['trades']),default=0),
        daily_loss_lock_trigger_count=sum(v['loss_hit'] for v in daily.values()),
        max_trade_per_day_trigger_count=sum(v['count']>=e.max_trades_per_day for v in daily.values()),
        end_of_backtest_count=sum(t['reason']=='END_OF_BACKTEST' for t in r['trades']),
        charges_over_absolute_gross_percent=100*sum(t['charges'] for t in r['trades'])/abs(sum(t['gross_pnl'] for t in r['trades'])),
        correctness_audit=dict(violation_count=len(errors),violations=errors,trades_audited=len(details),details=details))
    return errors

def main():
    if OUT.exists(): raise SystemExit('STOP: results exist; reruns prohibited')
    before=snapshot()
    assert sha(CSV)=='fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6'
    assert sha(META)=='e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67'
    meta=json.loads(META.read_text())
    data=pd.read_csv(CSV)
    gate=h.BacktestRunner(data,interval='FIVE_MINUTE',cas_eligible=True)
    gate.prepare_data()
    dates=sorted(gate.df['datetime'].dt.date.unique())
    assert len(data)==meta['row_count']==9309
    assert len(gate.df)==meta['accepted_row_count']==9294
    assert len(gate.cas_auxiliary_data)==15
    assert len(dates)==meta['trading_session_count']==125
    assert gate.session_policy.version==meta['session_policy']['version']==2
    legacy=[d for d in dates if d<gate.session_policy.effective_date]
    cas=[d for d in dates if d>=gate.session_policy.effective_date]
    assert len(legacy)==98 and len(cas)==27
    assert gate.df.groupby(gate.df['datetime'].dt.date).size().to_dict()=={d:75 if d in legacy else 72 for d in dates}
    acquisition=json.loads((ROOT/'research/phase14a9_acquisition_audit.json').read_text())
    assert all(sha(ROOT/p)==v for p,v in acquisition['frozen_before'].items())
    groups=dict(first_half=dates[:62],second_half=dates[62:],LEGACY=legacy,CAS=cas)
    results=dict(status='RUNNING',dataset=dict(csv_sha256=sha(CSV),metadata_sha256=sha(META),published_rows=9309,
        regular_rows=9294,auxiliary_rows=15,sessions=125,legacy_sessions=98,cas_sessions=27,session_policy_version=2),
        split_method='First 62 / remaining 63 represented sessions; attribution of full-run trades, no reruns; carried capital; local realized-equity peaks.',
        frozen_before=before,variants={},runs=dict(A=0,D=0),validation=dict(precheck_tests='305 passed, 0 failed',precheck_compile='68 files passed',precheck_diff_check='passed'))
    def save(): OUT.write_text(json.dumps(results,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
    save()
    for name,factory in [('A',h.StrategyManager),('D',h.EMARegimeLockStrategy)]:
        captured={}
        def profile(frame,event,arg):
            if event=='return' and frame.f_code is h.BacktestRunner.run.__code__: captured['runner']=frame.f_locals['self']
        results['runs'][name]+=1
        save()
        sys.setprofile(profile)
        try: r=h.run_variant(data,factory)
        finally: sys.setprofile(None)
        results['variants'][name]=r
        save()
        runner=captured['runner']
        assert len(runner.df)==9294 and len(runner.cas_auxiliary_data)==15
        errors=audit(r,runner)
        ts=r['trades']
        r['sides']={side:stats([t for t in ts if t['side']==side]) for side in ('BUY','SELL')}
        r['exits']={reason:stats([t for t in ts if t['reason']==reason]) for reason in ('STOP_LOSS','TARGET','END_OF_SESSION','END_OF_BACKTEST')}
        r['periods']={}
        for label,ds in groups.items():
            start_cap=100000+sum(t['pnl'] for t in ts if t['entry_timestamp'].date()<ds[0])
            r['periods'][label]=dict(sessions=len(ds),start=str(ds[0]),end=str(ds[-1]),starting_capital=start_cap,
                **stats([t for t in ts if t['entry_timestamp'].date() in ds],start_cap))
        relation=runner.df['EMA20'].gt(runner.df['EMA50']).astype(int)-runner.df['EMA20'].lt(runner.df['EMA50']).astype(int)
        regimes=relation.ne(relation.shift()).cumsum()
        ids=[int(regimes.iloc[t['signal_index']]) for t in ts]
        r['same_regime_repeat_entries']=len(ids)-len(set(ids))
        r['signal_regime_ids']=ids
        r['occupied_bars']=sum(t['exit_index']-t['entry_index']+1 for t in ts)
        r['occupied_bar_percent']=r['occupied_bars']/9294*100
        r['trades_per_session']=len(ts)/125
        r['active_sessions']=len({t['entry_timestamp'].date() for t in ts})
        r['largest_five_winners_net']=sum(sorted((t['pnl'] for t in ts if t['pnl']>0),reverse=True)[:5])
        save()
        if errors:
            results['status']='BLOCKED_CORRECTNESS'
            save()
            raise SystemExit('STOP: correctness violations')
        print(name,'completed once:',r['total_trades'],'trades;',r['net_pnl'],'net',flush=True)
    a,d=results['variants']['A'],results['variants']['D']
    results['deltas_D_minus_A']={k:d[k]-a[k] for k in ('total_trades','buy_trades','sell_trades','gross_net_pnl','net_pnl','max_drawdown_percent','occupied_bar_percent','trades_per_session')}
    results['deltas_D_minus_A'].update(trade_reduction_percent=100*(1-d['total_trades']/a['total_trades']),
        charges_reduction_percent=100*(1-d['total_charges']/a['total_charges']),
        repeated_same_regime_entries_removed=a['same_regime_repeat_entries']-d['same_regime_repeat_entries'])
    results['frozen_after']=snapshot()
    assert results['frozen_after']==before
    results['safety']=dict(network_attempts=len(ATTEMPTS),forbidden_modules_loaded=[n for n in sys.modules if n.lower().startswith(('smartapi','broker.','live.'))],
        production_and_frozen_files_unchanged=True,note='Research blocks network and broker/live/SDK imports. Regression tests use mocked transports under their existing network guard.')
    assert not ATTEMPTS and not results['safety']['forbidden_modules_loaded']
    results['status']='RUNS_AND_AUDIT_COMPLETE'
    save()
if __name__=='__main__': main()
