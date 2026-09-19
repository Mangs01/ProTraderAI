"""Phase 15 local audit, derived from the frozen Phase 14B methodology."""
import math
from research import ema_harness as h
from config import settings as s
import statistics

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
        charges_over_absolute_gross_percent=(100*sum(t['charges'] for t in r['trades'])/abs(sum(t['gross_pnl'] for t in r['trades'])) if sum(t['gross_pnl'] for t in r['trades']) else None),
        correctness_audit=dict(violation_count=len(errors),violations=errors,trades_audited=len(details),details=details))
    return errors
