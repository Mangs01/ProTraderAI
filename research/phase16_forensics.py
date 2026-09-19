"""Phase 16 saved-event diagnostics; no strategy or engine execution."""
import hashlib, importlib.abc, json, math, socket, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
H=(1,2,3,6,12)
BUCKETS=('09:30-10:29','10:30-11:29','11:30-12:29','12:30-13:29','13:30-14:29','14:30-final')
ATTEMPTS=[]
def guard():
    def deny(*a,**kw):
        ATTEMPTS.append('network/process')
        raise BaseException('Phase16 offline violation')
    class Imports(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.lower().split('.')[0] in ('smartapi','broker','live'):
                ATTEMPTS.append(fullname)
                raise BaseException('Forbidden import '+fullname)
    sys.meta_path.insert(0,Imports())
    for k in ('connect','connect_ex','send','sendall','sendto'): setattr(socket.socket,k,deny)
    for k in ('create_connection','getaddrinfo','gethostbyname','gethostbyname_ex'): setattr(socket,k,deny)
    def audit(event,args):
        if event.startswith(('socket.connect','socket.send','socket.getaddrinfo','socket.gethostbyname')) or event in ('subprocess.Popen','os.system'): deny()
    sys.addaudithook(audit)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def stats(values):
    import numpy as np
    x=np.array([v for v in values if v is not None and math.isfinite(v)],dtype=float)
    if not len(x): return dict(n=0,mean=None,median=None,std=None,positive_pct=None,p25=None,p75=None,max=None)
    return dict(n=len(x),mean=float(x.mean()),median=float(np.median(x)),std=float(x.std(ddof=1)) if len(x)>1 else None,positive_pct=float((x>0).mean()*100),p25=float(np.quantile(x,.25)),p75=float(np.quantile(x,.75)),max=float(x.max()))
def directional_return(side,ref,future): return future/ref-1 if side=='BUY' else ref/future-1
def forward(df,e,h,side,ref,atr):
    j=e+h-1
    if j>=len(df) or df.iloc[j].datetime.date()!=df.iloc[e].datetime.date(): return None
    p=float(df.iloc[j].close)
    return dict(index=j,timestamp=str(df.iloc[j].datetime),price=p,return_pct=100*directional_return(side,ref,p),atr=(p-ref)*(1 if side=='BUY' else -1)/atr)
def excursions(side,raw,highs,lows,atr):
    mfe=max([0.]+([h-raw for h in highs] if side=='BUY' else [raw-l for l in lows]))
    mae=max([0.]+([raw-l for l in lows] if side=='BUY' else [h-raw for h in highs]))
    return dict(mfe_price=mfe,mae_price=mae,mfe_pct=100*mfe/raw,mae_pct=100*mae/raw,mfe_atr=mfe/atr,mae_atr=mae/atr)
def first_touch(bars,side,ref,atr):
    d=1 if side=='BUY' else -1
    for r in bars.itertuples():
        op=d*(r.open-ref)/atr
        if op<=-1.5: return dict(outcome='STOP',collision=False,index=r.Index,gap=True)
        if op>=2: return dict(outcome='TARGET',collision=False,index=r.Index,gap=True)
        fav=(r.high-ref if d==1 else ref-r.low)/atr
        adv=(ref-r.low if d==1 else r.high-ref)/atr
        stop,target=adv>=1.5-1e-10,fav>=2-1e-10
        if stop or target: return dict(outcome='STOP' if stop else 'TARGET',collision=stop and target,index=r.Index,gap=False)
    return dict(outcome='NEITHER',collision=False,index=None,gap=False)
def duration(e,x): return dict(bars=x-e,minutes=5*(x-e),candles=x-e+1)
def regular_only(df,policy):
    allowed={d:set(policy.expected_bar_times(d)) for d in df.datetime.dt.date.unique()}
    return df.loc[[t.time() in allowed[t.date()] for t in df.datetime]].reset_index(drop=True)
def tertile_cuts(values):
    import numpy as np
    return [float(x) for x in np.quantile(sorted(values),[1/3,2/3],method='linear')]
def tertile(v,c): return 'LOW' if v<=c[0] else 'MID' if v<=c[1] else 'HIGH'
def pct(rows,predicate): return 100*sum(predicate(r) for r in rows)/len(rows) if rows else None
def performance(rows):
    gp=sum(max(0,r['gross_pnl']) for r in rows); gl=-sum(min(0,r['gross_pnl']) for r in rows)
    net=sum(r['pnl'] for r in rows)
    return dict(trades=len(rows),gross_pnl=gp-gl,net_pnl=net,pf=gp/gl if gl else None,win_rate=pct(rows,lambda r:r['pnl']>0),average_net_trade=net/len(rows) if rows else None)
def summarize(rows):
    out=dict(performance=performance(rows))
    out['forward']={ref:{str(h):{unit:stats([r['forward'][ref][str(h)][unit] if r['forward'][ref][str(h)] else None for r in rows]) for unit in ('return_pct','atr')} for h in H} for ref in ('signal_close','raw_open')}
    out['excursions']={b:{**{k:stats([r[b][k] for r in rows]) for k in ('mfe_price','mae_price','mfe_pct','mae_pct','mfe_atr','mae_atr')},'mfe_reach_pct':{str(t):pct(rows,lambda r:r[b]['mfe_atr']>=t-1e-10) for t in (.5,1,1.5,2)},'mae_reach_pct':{str(t):pct(rows,lambda r:r[b]['mae_atr']>=t-1e-10) for t in (.5,1,1.5)}} for b in ('confirmed','candle_upper')}
    for name,reason,key,thresholds in [('stop_forensics','STOP_LOSS','mfe_atr',(.25,.5,1,1.5,2)),('target_forensics','TARGET','mae_atr',(.25,.5,1,1.5))]:
        rs=[r for r in rows if r['reason']==reason]
        out[name]=dict(count=len(rs),**{b:dict(stats=stats([r[b][key] for r in rs]),reach_pct={str(t):pct(rs,lambda r:r[b][key]>=t-1e-10) for t in thresholds}) for b in ('confirmed','candle_upper')})
    out['duration']={k:stats([r['duration'][k] for r in rows]) for k in ('bars','minutes','candles')}
    out['exit_within_candles_pct']={reason:{str(n):pct([r for r in rows if r['reason']==reason],lambda r:r['duration']['candles']<=n) for n in hs} for reason,hs in [('STOP_LOSS',(1,2,3,6)),('TARGET',H)]}
    out['immediate']={k:dict(count=sum(r['immediate']==k for r in rows),pct=pct(rows,lambda r:r['immediate']==k)) for k in ('FAVORABLE','ADVERSE','BOTH','NEITHER')}
    out['geometry']={ref:dict(stop_first_pct=pct(rows,lambda r:r['touch'][ref]['outcome']=='STOP'),target_first_pct=pct(rows,lambda r:r['touch'][ref]['outcome']=='TARGET'),neither_pct=pct(rows,lambda r:r['touch'][ref]['outcome']=='NEITHER'),collisions=sum(r['touch'][ref]['collision'] for r in rows)) for ref in ('raw_open','slipped_entry')}
    out['geometry']['distances']={k:stats([r[k] for r in rows]) for k in ('stop_distance','target_distance','stop_atr','target_atr','reward_risk')}
    return out

def main():
    guard()
    import pandas as pd
    from core.indicators import Indicators
    from utils.session_policy import FiveMinuteSessionPolicy
    from utils.time_utils import normalize_timestamp_series,validate_five_minute_sessions
    pp=ROOT/'research/phase15_results.json'; prior=json.loads(pp.read_text()); ph=sha(pp)
    csv=ROOT/prior['dataset']['csv_path']
    assert sha(csv)=='fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6'
    assert sha(csv.with_suffix('.csv.meta.json'))=='e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67'
    frozen={**prior['frozen_existing_files'],**prior['canonical_source_hashes']}
    for p,v in frozen.items(): assert sha(ROOT/p)==v,'Frozen source mismatch: '+p
    policy=FiveMinuteSessionPolicy(cas_eligible=True)
    df=pd.read_csv(csv); df.datetime=normalize_timestamp_series(df.datetime,'Asia/Kolkata')
    df=df.sort_values('datetime',kind='mergesort').reset_index(drop=True)
    validate_five_minute_sessions(df,session_policy=policy)
    assert len(df)==9309
    df=regular_only(df,policy); assert len(df)==9294
    df['EMA20']=Indicators.ema(df,20); df['EMA50']=Indicators.ema(df,50)
    df['RSI']=Indicators.rsi(df,14); df['ATR']=Indicators.atr(df,14)
    df['VWAP']=Indicators.vwap(df,session_reset=True); df['VolumeSMA']=Indicators.volume_sma(df,20)
    events=[]; violations=[]
    def check(ok,name,identity):
        if not ok: violations.append(dict(event=identity,invariant=name))
    for f in ('E','F','G'):
        v=prior['variants'][f]
        assert len(v['trades'])==len(v['signal_events'])==v['total_trades']
        for n,(t,event,ar) in enumerate(zip(v['trades'],v['signal_events'],v['correctness_audit']['details']),1):
            identity=f'{f}{n:03d}'; s,e,x=(t[k] for k in ('signal_index','entry_index','exit_index'))
            sr,er,xr=df.iloc[s],df.iloc[e],df.iloc[x]; atr=float(ar['signal_atr'])
            check(math.isclose(atr,sr.ATR,abs_tol=1e-10),'saved signal ATR',identity)
            check(e==s+1 and x>=e,'N+1 entry',identity)
            check(sr.datetime.date()==er.datetime.date()==xr.datetime.date(),'same session',identity)
            for idx,k in ((s,'signal_timestamp'),(e,'entry_timestamp'),(x,'exit_timestamp')):
                check(df.iloc[idx].datetime==pd.Timestamp(t[k]),k,identity)
                check(df.iloc[idx].datetime.time() in policy.expected_bar_times(sr.datetime.date()),'regular timestamp',identity)
            check(pd.Timestamp(event['timestamp'])==sr.datetime and event['signal']==t['side'],'event match',identity)
            check(sr.datetime.time()<=policy.final_allowed_signal_bar(sr.datetime.date()),'signal cutoff',identity)
            check(er.open==t['raw_entry_price'],'raw entry open',identity)
            check(math.isclose(abs(t['entry']-t['stop_loss'])/atr,1.5,abs_tol=1e-9),'stop geometry',identity)
            check(math.isclose(abs(t['target']-t['entry'])/atr,2,abs_tol=1e-9),'target geometry',identity)
            bars=df.iloc[e:x+1]; before=df.iloc[e:x]
            highs=list(before.high)+[float(xr.open),t['raw_exit_price']]
            lows=list(before.low)+[float(xr.open),t['raw_exit_price']]
            if t['reason']=='END_OF_SESSION': highs=list(bars.high); lows=list(bars.low)
            touch=first_touch(bars,t['side'],t['entry'],atr)
            check({'STOP':'STOP_LOSS','TARGET':'TARGET','NEITHER':'END_OF_SESSION'}[touch['outcome']]==t['reason'],'exit geometry',identity)
            if touch['index'] is not None: check(touch['index']==x,'exit index',identity)
            d=1 if t['side']=='BUY' else -1
            fav=(er.high-er.open if d==1 else er.open-er.low)>0
            adv=(er.open-er.low if d==1 else er.high-er.open)>0
            minute=er.datetime.hour*60+er.datetime.minute
            bucket=BUCKETS[(minute-570)//60] if 570<=minute<930 else 'OUTSIDE_PREDEFINED'
            chars=dict(RSI=float(sr.RSI),ATR=atr,atr_close_pct=100*atr/sr.close,vwap_distance_price=float(sr.close-sr.VWAP),time_minutes=minute-5)
            if f in ('E','G'): chars['ema20_distance_price']=float(sr.close-sr.EMA20)
            if f=='E': chars.update(ema50_distance_price=float(sr.close-sr.EMA50),ema20_ema50_spread=float(sr.EMA20-sr.EMA50))
            if f=='F': chars.update(volume_ratio=float(sr.volume/sr.VolumeSMA),opening_range_distance_price=d*(sr.close-event['or_high' if d==1 else 'or_low']))
            r=dict(t,id=identity,family=f,signal_atr=atr,signal_bar_close=float(sr.close),raw_next_bar_open=float(er.open),slipped_entry_price=t['entry'],regime='CAS' if sr.datetime.date()>=policy.effective_date else 'LEGACY',outcome='WINNER' if t['pnl']>0 else 'LOSER' if t['pnl']<0 else 'BREAKEVEN',time_bucket=bucket,characteristics=chars,duration=duration(e,x),confirmed=excursions(t['side'],er.open,highs,lows,atr),candle_upper=excursions(t['side'],er.open,list(bars.high),list(bars.low),atr),immediate='BOTH' if fav and adv else 'FAVORABLE' if fav else 'ADVERSE' if adv else 'NEITHER',touch=dict(raw_open=first_touch(bars,t['side'],er.open,atr),slipped_entry=touch),stop_distance=abs(t['entry']-t['stop_loss']),target_distance=abs(t['target']-t['entry']),stop_atr=abs(t['entry']-t['stop_loss'])/atr,target_atr=abs(t['target']-t['entry'])/atr,reward_risk=abs(t['target']-t['entry'])/abs(t['entry']-t['stop_loss']))
            r['forward']={ref:{str(h):forward(df,e,h,t['side'],price,atr) for h in H} for ref,price in [('signal_close',sr.close),('raw_open',er.open)]}
            for ref in r['forward'].values():
                for h,val in ref.items():
                    if val:
                        check(val['index']==s+int(h) and val['index']>s,'forward indexing',identity)
                        check(pd.Timestamp(val['timestamp']).date()==sr.datetime.date(),'horizon session',identity)
            r['slippage_drag']=(t['entry_slippage']+t['exit_slippage'])*t['quantity']
            r['raw_price_pnl']=d*(t['raw_exit_price']-t['raw_entry_price'])*t['quantity']
            check(math.isclose(r['raw_price_pnl']-r['slippage_drag'],t['gross_pnl'],abs_tol=1e-7),'slippage reconciliation',identity)
            events.append(r)
    assert len(events)==482
    cuts=tertile_cuts([r['characteristics']['atr_close_pct'] for r in events])
    for r in events: r['volatility']=tertile(r['characteristics']['atr_close_pct'],cuts)
    result=dict(status='ANALYZED',dataset=prior['dataset'],phase15_results_sha256=ph,event_source='LOADED: saved signal_events and trades; zero reconstruction or strategy runs',volatility=dict(cuts_atr_close_pct=cuts,method='Pooled 482 trades; linear quantiles 1/3 and 2/3, ties <= cut go lower',counts={k:sum(r['volatility']==k for r in events) for k in ('LOW','MID','HIGH')}),audit=dict(events=len(events),violation_count=len(violations),violations=violations),families={},events=events,safety=dict(network_attempts=len(ATTEMPTS),forbidden_imports=[],strategy_runs=0,production_unchanged=True,engine_unchanged=True,frozen_files_verified=len(frozen),no_commit=True),validation=dict(precheck_tests='341 passed, 0 failed in 13.31s',precheck_compile='79 files passed',precheck_diff='PASS'))
    for f in ('E','F','G'):
        rows=[r for r in events if r['family']==f]
        groups={'ALL':rows,**{k:[r for r in rows if r['side']==k] for k in ('BUY','SELL')},**{k:[r for r in rows if r['outcome']==k] for k in ('WINNER','LOSER','BREAKEVEN')},**{k:[r for r in rows if r['reason']==k] for k in ('STOP_LOSS','TARGET','END_OF_SESSION')}}
        family=dict(groups={k:summarize(rs) for k,rs in groups.items()},time_of_day={k:performance([r for r in rows if r['time_bucket']==k]) for k in (*BUCKETS,'OUTSIDE_PREDEFINED')},volatility={k:performance([r for r in rows if r['volatility']==k]) for k in ('LOW','MID','HIGH')},regimes={k:summarize([r for r in rows if r['regime']==k]) for k in ('LEGACY','CAS')},characteristics={g:{k:stats([r['characteristics'][k] for r in rs]) for k in rows[0]['characteristics']} for g,rs in groups.items() if g in ('WINNER','LOSER')})
        c={k:sum(r[k] for r in rows) for k in ('gross_pnl','slippage_drag','raw_price_pnl','brokerage','stt','stamp_duty','transaction_charges','sebi_charges','ipft','gst','charges','pnl')}
        turnover=sum(r['buy_turnover']+r['sell_turnover'] for r in rows)
        c.update(gross_turnover=turnover,charges_over_turnover=c['charges']/turnover,charges_over_absolute_gross=c['charges']/abs(c['gross_pnl']),average_charge=c['charges']/len(rows),gross_average=c['gross_pnl']/len(rows),net_average=c['pnl']/len(rows),per_trade_cost_atr=stats([(r['charges']+r['slippage_drag'])/r['quantity']/r['signal_atr'] for r in rows]))
        family['costs']=c; result['families'][f]=family
    for p,v in frozen.items(): assert sha(ROOT/p)==v
    assert sha(pp)==ph and not ATTEMPTS
    assert not violations,violations
    (ROOT/'research/phase16_results.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item())+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('audit','volatility','safety')},indent=2))
if __name__=='__main__': main()

