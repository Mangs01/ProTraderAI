import pandas as pd
import pytest
from research.phase16_forensics import (directional_return,forward,excursions,first_touch,duration,regular_only,tertile_cuts,tertile)
from utils.session_policy import FiveMinuteSessionPolicy

def frame(rows,start='2026-09-01 09:30'):
    stamps=pd.date_range(start,periods=len(rows),freq='5min',tz='Asia/Kolkata')
    return pd.DataFrame([dict(datetime=t,open=100.,high=101.,low=99.,close=100.,**r) for t,r in zip(stamps,rows)])

@pytest.mark.parametrize('side,expected',[('BUY',.1),('SELL',100/110-1)])
def test_direction(side,expected):
    assert directional_return(side,100,110)==pytest.approx(expected)

def test_session_boundary_truncation():
    df=frame([{},{}],start='2026-09-01 15:10')
    df.loc[1,'datetime']=pd.Timestamp('2026-09-02 09:15',tz='Asia/Kolkata')
    assert forward(df,0,2,'BUY',100,2) is None
    assert forward(df,0,1,'BUY',100,2)['index']==0

@pytest.mark.parametrize('side,mfe,mae',[('BUY',6,3),('SELL',3,6)])
def test_excursions_direction_and_atr(side,mfe,mae):
    r=excursions(side,100,[104,106],[98,97],2)
    assert r['mfe_price']==mfe and r['mae_price']==mae
    assert r['mfe_atr']==mfe/2 and r['mae_atr']==mae/2
    assert r['mfe_pct']==mfe and r['mae_pct']==mae

@pytest.mark.parametrize('side',['BUY','SELL'])
def test_same_bar_stop_wins(side):
    df=frame([{}]); df.loc[0,['high','low']]=[105,95]
    r=first_touch(df,side,100,2)
    assert r['outcome']=='STOP' and r['collision']

def test_gap_target_precedes_later_range():
    df=frame([{}]); df.loc[0,['open','high','low']]=[105,106,90]
    r=first_touch(df,'BUY',100,2)
    assert r['outcome']=='TARGET' and r['gap'] and not r['collision']

def test_time_to_exit_same_bar_and_later():
    assert duration(8,8)==dict(bars=0,minutes=0,candles=1)
    assert duration(8,11)==dict(bars=3,minutes=15,candles=4)

def test_cas_auxiliary_exclusion():
    df=frame([{}, {}, {}, {}, {}, {}, {}],start='2026-09-01 15:10')
    r=regular_only(df,FiveMinuteSessionPolicy(cas_eligible=True))
    assert list(r.datetime.dt.strftime('%H:%M'))==['15:10']

def test_tertiles_determinism_and_ties():
    values=[.1,.1,.2,.3,.4,.5,.6,.7,.7]
    cuts=tertile_cuts(values)
    assert cuts==tertile_cuts(list(reversed(values)))
    assert tertile(cuts[0],cuts)=='LOW' and tertile(cuts[1],cuts)=='MID'
    assert sum(tertile(v,cuts) in ('LOW','MID','HIGH') for v in values)==len(values)

def test_no_lookahead_horizon_indexing():
    df=frame([{}, {}, {}, {}]); df['close']=[90,102,106,999]
    assert forward(df,1,1,'BUY',100,2)['price']==102
    assert forward(df,1,2,'BUY',100,2)['atr']==3
    df.loc[3,'close']=-999
    assert forward(df,1,2,'BUY',100,2)['price']==106
    assert forward(df,1,12,'BUY',100,2) is None

def test_signal_reference_and_raw_reference_differ():
    df=frame([{}]); df.loc[0,'close']=102
    assert forward(df,0,1,'BUY',99,2)['atr']==1.5
    assert forward(df,0,1,'BUY',100,2)['atr']==1

def test_causal_indicator_context_is_prefix_invariant():
    from core.indicators import Indicators
    df=frame([{} for _ in range(80)])
    df['close']=[100+(i%7)*.2+i*.01 for i in range(80)]
    df['high']=df.close+1; df['low']=df.close-1;df['volume']=100
    for calculate in (lambda d:Indicators.ema(d,20),lambda d:Indicators.ema(d,50),Indicators.atr,Indicators.rsi,lambda d:Indicators.vwap(d,session_reset=True),Indicators.volume_sma):
        full=calculate(df)
        assert full.iloc[59]==pytest.approx(calculate(df.iloc[:60]).iloc[-1])
        altered=df.copy(); altered.loc[60:,['high','low','close','volume']]=999999
        assert calculate(altered).iloc[59]==pytest.approx(full.iloc[59])

def test_saved_universe_integrity_and_accounting():
    import json
    from research.phase16_forensics import ROOT
    r=json.loads((ROOT/'research/phase16_results.json').read_text())
    assert len(r['events'])==482 and r['audit']['violation_count']==0
    for f,n in [('E',92),('F',142),('G',248)]:
        v=r['families'][f]; assert v['groups']['ALL']['performance']['trades']==n
        assert sum(x['trades'] for x in v['time_of_day'].values())==n
        assert sum(x['trades'] for x in v['volatility'].values())==n
        c=v['costs']
        assert c['raw_price_pnl']-c['slippage_drag']==pytest.approx(c['gross_pnl'])
        assert c['gross_pnl']-c['charges']==pytest.approx(c['pnl'])
        assert sum(c[k] for k in ('brokerage','stt','stamp_duty','transaction_charges','sebi_charges','ipft','gst'))==pytest.approx(c['charges'])
    for e in r['events']:
        assert e['entry_index']==e['signal_index']+1
        assert e['confirmed']['mfe_atr']<=e['candle_upper']['mfe_atr']+1e-9
        assert e['confirmed']['mae_atr']<=e['candle_upper']['mae_atr']+1e-9
        for ref in e['forward'].values():
            for h,v in ref.items():
                if v:
                    assert v['index']==e['signal_index']+int(h)
                    assert pd.Timestamp(v['timestamp']).date()==pd.Timestamp(e['signal_timestamp']).date()
