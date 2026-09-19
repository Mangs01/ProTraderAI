import hashlib,json
from pathlib import Path
import pandas as pd
import pytest
from research.phase17_breakout_retest import BreakoutRetest
from research.phase15.opening_range_breakout import OpeningRangeBreakout
from backtest.backtest_runner import BacktestRunner


def frame(rows,start='2026-09-01 09:15'):
    stamps=pd.date_range(start,periods=len(rows),freq='5min',tz='Asia/Kolkata')
    base=dict(open=100.,high=110.,low=90.,close=100.,volume=200.,RSI=60.,VWAP=100.,VolumeSMA=100.,ATR=10.,INDICATOR_READY=True)
    return pd.DataFrame([dict(base,datetime=t,**r) for t,r in zip(stamps,rows)])

def setup(side='BUY'):
    return frame([{}, {}, {}, dict(close=111.,high=112.,low=109.) if side=='BUY' else dict(close=89.,low=88.,high=91.)])

@pytest.mark.parametrize('side',['BUY','SELL'])
def test_breakout_alone_and_same_bar_retest_forbidden(side):
    h=BreakoutRetest(); df=setup(side)
    assert h.get_signal(df)=='HOLD' and len(h.breakouts)==1 and not h.retests
    assert h.states[side]=='WAIT_RETEST'

@pytest.mark.parametrize('side',['BUY','SELL'])
def test_later_retest_and_once_per_side(side):
    h=BreakoutRetest(); df=setup(side);h.get_signal(df)
    row=dict(close=111.,high=113.,low=110.) if side=='BUY' else dict(close=89.,low=87.,high=90.)
    df=pd.concat([df,frame([row],start='2026-09-01 09:35')],ignore_index=True)
    assert h.get_signal(df)==side
    assert h.events[0]['breakout_index']<h.events[0]['index']
    assert h.get_signal(df)=='HOLD' and h.states[side]=='DONE'
    df=pd.concat([df,frame([row],start='2026-09-01 09:40')],ignore_index=True)
    assert h.get_signal(df)=='HOLD'

def test_opening_range_exact_three_completed_bars():
    h=BreakoutRetest(); df=setup(); df.loc[0,'high']=115
    df.loc[3,['high','close']]=[999,116]
    h.get_signal(df)
    assert h.breakouts[0]['or_high']==115 and h.breakouts[0]['or_low']==90
    assert [b['timestamp'].strftime('%H:%M') for b in h.sessions['2026-09-01']['opening_range']['bars']]==['09:15','09:20','09:25']

def test_missing_range_bar_never_arms():
    h=BreakoutRetest(); df=setup().drop(index=1).reset_index(drop=True)
    assert h.get_signal(df)=='HOLD' and not h.breakouts

def test_inside_range_does_not_invalidate_and_no_retest_no_signal():
    h=BreakoutRetest(); df=setup();h.get_signal(df)
    for clock,change in [('09:35',dict(close=100.)),('09:40',dict(close=112.,low=111.,high=113.))]:
        df=pd.concat([df,frame([change],start='2026-09-01 '+clock)],ignore_index=True)
        assert h.get_signal(df)=='HOLD'
        assert h.states['BUY']=='WAIT_RETEST'
    assert not h.retests

def test_session_reset_and_independent_directions():
    h=BreakoutRetest(); df=setup(); h.get_signal(df)
    df=pd.concat([df,frame([dict(close=89.)],start='2026-09-01 09:35')],ignore_index=True)
    h.get_signal(df)
    assert h.states==dict(BUY='WAIT_RETEST',SELL='WAIT_RETEST')
    nxt=setup();nxt.datetime+=pd.Timedelta(days=1)
    assert h.get_signal(pd.concat([df,nxt],ignore_index=True))=='HOLD'
    assert h.states['SELL']=='WAIT_BREAKOUT' and h.states['BUY']=='WAIT_RETEST'

def test_skipped_retest_remains_armed_no_backfill():
    h=BreakoutRetest(); df=setup(); h.get_signal(df)
    df=pd.concat([df,frame([dict(close=111.),dict(close=112.,low=111.,high=113.)],start='2026-09-01 09:35')],ignore_index=True)
    assert h.get_signal(df)=='HOLD'
    assert h.retests[0]['status']=='HARNESS_SKIPPED' and h.states['BUY']=='WAIT_RETEST'
    df=pd.concat([df,frame([dict(close=111.)],start='2026-09-01 09:45')],ignore_index=True)
    assert h.get_signal(df)=='BUY'

@pytest.mark.parametrize('day,clock,expected',[('2026-03-09','15:05','BUY'),('2026-03-09','15:10','HOLD'),('2026-09-01','15:00','BUY'),('2026-09-01','15:05','HOLD')])
def test_existing_cutoffs(day,clock,expected):
    h=BreakoutRetest();df=setup();df.datetime+=pd.Timestamp(day)-pd.Timestamp('2026-09-01');h.get_signal(df)
    df=pd.concat([df,frame([dict(close=111.)],start=day+' '+clock)],ignore_index=True)
    assert h.get_signal(df)==expected
    if expected=='HOLD': assert h.retests[-1]['status']=='CUTOFF'

def test_cas_auxiliary_cannot_retest_or_signal():
    h=BreakoutRetest();df=setup();h.get_signal(df)
    df=pd.concat([df,frame([dict(close=111.,high=999999.)],start='2026-09-01 15:15')],ignore_index=True)
    assert h.get_signal(df)=='HOLD' and not h.retests

def test_no_lookahead_future_change_and_history_rewind():
    df=setup();h=BreakoutRetest();h.get_signal(df)
    df=pd.concat([df,frame([dict(close=111.),dict(close=999999.)],start='2026-09-01 09:35')],ignore_index=True)
    assert h.get_signal(df.iloc[:5])=='BUY'
    with pytest.raises(ValueError): h.get_signal(df.iloc[:4])

def test_next_physical_bar_execution_and_cas_eod():
    stamps=pd.date_range('2026-09-01 09:15','2026-09-01 15:25',freq='5min',tz='Asia/Kolkata')
    df=frame([{} for _ in stamps]);df.loc[3,'close']=111.;df.loc[4,'close']=111.
    df.loc[5:,'open']=111.;df.loc[5:,'high']=112.;df.loc[5:,'low']=109.;df.loc[5:,'close']=111.
    df.loc[72:,'close']=999999.
    runner=BacktestRunner(df,interval='FIVE_MINUTE',cas_eligible=True);runner.strategy=BreakoutRetest()
    runner.prepare_indicators=lambda:None
    runner.run(); t=runner.engine.trades[0]
    assert len(runner.engine.trades)==1 and t['signal_index']==4 and t['entry_index']==5
    assert t['raw_entry_price']==111. and t['entry']==pytest.approx(111*1.0005)
    assert t['reason']=='END_OF_SESSION' and t['raw_exit_price']==111.
    assert len(runner.df)==72 and len(runner.cas_auxiliary_data)==3

def test_f_behavior_unchanged():
    f=OpeningRangeBreakout();h=BreakoutRetest();df=setup()
    assert f.get_signal(df)=='BUY' and h.get_signal(df)=='HOLD'

def test_frozen_production_engine_and_prior_artifacts():
    root=Path(__file__).resolve().parents[1]
    r=json.loads((root/'research/phase17_results.json').read_text())
    for path,digest in r['frozen_existing_files'].items():
        assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,path
