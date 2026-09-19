"""Synthetic canonical-entry tests; never run the Phase 14 validation dataset."""
import pandas as pd
import pytest
from research.phase15.trend_pullback import TrendPullback
from research.phase15.opening_range_breakout import OpeningRangeBreakout
from research.phase15.vwap_mean_reversion import VWAPMeanReversion


def frame(rows, start='2026-09-01 09:15'):
    defaults=dict(open=100., high=110., low=90., close=104., volume=200.,
                  EMA20=105., EMA50=100., RSI=50., VWAP=103., ATR=2., VolumeSMA=100.)
    stamps=pd.date_range(start, periods=len(rows), freq='5min', tz='Asia/Kolkata')
    return pd.DataFrame([dict(defaults, datetime=stamp, **row) for stamp,row in zip(stamps,rows)])


def trend(side='BUY'):
    if side=='BUY': return frame([dict(EMA50=98.),dict(EMA50=99.),dict(EMA50=100.)])
    return frame([dict(EMA20=95.,EMA50=x,close=96.,VWAP=97.) for x in (102.,101.,100.)])


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_e_mirrored_entry_and_once_per_episode(side):
    df=trend(side)
    strategy=TrendPullback()
    assert strategy.get_signal(df)==side
    assert strategy.get_signal(df)=='HOLD'


@pytest.mark.parametrize('change',[
    dict(EMA20=100.), dict(close=106.), dict(close=100.), dict(RSI=49.99),
    dict(VWAP=104.01), dict(EMA50=98.), dict(RSI=float('nan')),
])
def test_e_requires_every_buy_condition(change):
    df=trend()
    for k,v in change.items(): df.loc[2,k]=v
    assert TrendPullback().get_signal(df)=='HOLD'


def test_e_slope_uses_three_points_not_monotonic_filter():
    df=trend()
    df.loc[1,'EMA50']=110.
    assert TrendPullback().get_signal(df)=='BUY'


def test_e_reset_hidden_between_runner_evaluations():
    df=frame([dict(EMA50=x) for x in (98.,99.,100.,101.,102.)])
    df.loc[3,'close']=106.
    strategy=TrendPullback()
    assert strategy.get_signal(df.iloc[:3])=='BUY'
    assert strategy.get_signal(df)=='BUY'
    assert [e['episode'] for e in strategy.events]==[1,2]


def test_e_does_not_reset_merely_at_new_session():
    df=trend()
    extra=frame([dict(EMA50=101.)],start='2026-09-02 09:15')
    strategy=TrendPullback()
    assert strategy.get_signal(df)=='BUY'
    assert strategy.get_signal(pd.concat([df,extra],ignore_index=True))=='HOLD'


def opening(side='BUY'):
    changes=dict(close=111.,VWAP=105.,RSI=55.) if side=='BUY' else dict(close=89.,VWAP=95.,RSI=45.)
    return frame([{}, {}, {}, changes])


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_f_complete_range_and_one_direction_attempt(side):
    df=opening(side)
    strategy=OpeningRangeBreakout()
    assert strategy.get_signal(df.iloc[:3])=='HOLD'
    assert strategy.get_signal(df)==side
    assert strategy.get_signal(df)=='HOLD'
    assert strategy.events[0]['or_high']==110.
    assert strategy.events[0]['or_low']==90.


@pytest.mark.parametrize('change',[dict(close=110.),dict(VWAP=111.),dict(RSI=54.99),dict(volume=100.)])
def test_f_strict_breakout_vwap_volume_and_rsi(change):
    df=opening()
    for k,v in change.items(): df.loc[3,k]=v
    assert OpeningRangeBreakout().get_signal(df)=='HOLD'


def test_f_missing_opening_bar_never_forms_range():
    df=opening().drop(index=1).reset_index(drop=True)
    assert OpeningRangeBreakout().get_signal(df)=='HOLD'


def test_f_session_reset_and_independent_direction_budget():
    strategy=OpeningRangeBreakout()
    df=opening()
    assert strategy.get_signal(df)=='BUY'
    extra=frame([dict(close=89.,VWAP=95.,RSI=45.)],start='2026-09-01 09:35')
    df=pd.concat([df,extra],ignore_index=True)
    assert strategy.get_signal(df)=='SELL'
    next_day=opening()
    next_day.datetime+=pd.Timedelta(days=1)
    assert strategy.get_signal(pd.concat([df,next_day],ignore_index=True))=='BUY'


def test_f_no_lookahead_opening_range_uses_only_three_bars():
    df=opening()
    df.loc[3,'high']=999.
    strategy=OpeningRangeBreakout()
    assert strategy.get_signal(df)=='BUY'
    assert strategy.events[0]['or_high']==110.


def excursion(side='BUY'):
    change=dict(close=97.,VWAP=100.,EMA20=99.,RSI=35.) if side=='BUY' else dict(close=103.,VWAP=100.,EMA20=101.,RSI=65.)
    return frame([change])


@pytest.mark.parametrize('side',['BUY','SELL'])
def test_g_mirrored_once_per_excursion(side):
    df=excursion(side)
    strategy=VWAPMeanReversion()
    assert strategy.get_signal(df)==side
    assert strategy.get_signal(df)=='HOLD'


@pytest.mark.parametrize('change',[dict(close=98.),dict(RSI=35.01),dict(EMA20=97.),dict(ATR=0.)])
def test_g_requires_strict_stretch_rsi_ema_and_positive_atr(change):
    df=excursion()
    for k,v in change.items(): df.loc[0,k]=v
    assert VWAPMeanReversion().get_signal(df)=='HOLD'


def test_g_reset_requires_vwap_touch_even_if_stretch_temporarily_ends():
    strategy=VWAPMeanReversion()
    df=excursion()
    assert strategy.get_signal(df)=='BUY'
    for close in (99.,97.):
        nxt=excursion()
        nxt['datetime']=df.iloc[-1].datetime+pd.Timedelta(minutes=5)
        nxt['close']=close
        df=pd.concat([df,nxt],ignore_index=True)
    assert strategy.get_signal(df)=='HOLD'
    for close in (100.,97.):
        nxt=excursion()
        nxt['datetime']=df.iloc[-1].datetime+pd.Timedelta(minutes=5)
        nxt['close']=close
        df=pd.concat([df,nxt],ignore_index=True)
    assert strategy.get_signal(df)=='BUY'


def test_g_session_extremes_and_budget_reset():
    strategy=VWAPMeanReversion()
    df=excursion()
    assert strategy.get_signal(df)=='BUY'
    nxt=excursion()
    nxt.datetime+=pd.Timedelta(days=1)
    nxt['low']=96.
    assert strategy.get_signal(pd.concat([df,nxt],ignore_index=True))=='BUY'
    assert strategy.events[-1]['session_low']==96.


def test_g_supplied_extreme_filter_is_nonbinding_for_valid_positive_atr():
    df=excursion()
    df.loc[0,'low']=df.loc[0,'close']
    assert VWAPMeanReversion().get_signal(df)=='BUY'


@pytest.mark.parametrize('factory',[TrendPullback,OpeningRangeBreakout,VWAPMeanReversion])
def test_strategy_rejects_rewound_history(factory):
    strategy=factory()
    df=frame([{}, {}, {}, {}])
    strategy.get_signal(df)
    with pytest.raises(ValueError,match='monotonically'):
        strategy.get_signal(df.iloc[:2])

from backtest.backtest_runner import BacktestRunner
from research import ema_harness as harness
from research.phase15.audit import audit, stats
from research.phase15.phase15_runner import concentration


def test_audit_detects_corrupted_charge_and_preserves_cas_eod():
    stamps=pd.date_range('2026-09-01 09:15','2026-09-01 15:25',freq='5min',tz='Asia/Kolkata')
    df=pd.DataFrame(dict(datetime=stamps,open=100.,high=101.,low=99.,close=100.,volume=1000.,
                        EMA20=101.,EMA50=100.,RSI=70.,VWAP=100.,ATR=10.,INDICATOR_READY=True))
    df.loc[df.datetime.dt.hour.eq(15)&df.datetime.dt.minute.ge(15),'close']=999999.
    class Event:
        def required_indicators(self): return ('EMA20','EMA50','RSI')
        def get_signal(self,history): return 'BUY' if history.iloc[-1].datetime.strftime('%H:%M')=='15:00' else 'HOLD'
    runner=BacktestRunner(df,interval='FIVE_MINUTE',cas_eligible=True)
    runner.strategy=Event()
    runner.prepare_indicators=lambda:None
    r=harness._normalize_summary(runner.run(),runner.engine)
    r['trades']=runner.engine.trades
    assert len(runner.df)==72 and len(runner.cas_auxiliary_data)==3
    assert audit(r,runner)==[]
    assert r['trades'][0]['entry_timestamp'].strftime('%H:%M')=='15:05'
    assert r['trades'][0]['reason']=='END_OF_SESSION'
    assert r['trades'][0]['raw_exit_price']==100.
    r['trades'][0]['charges']+=1
    assert any(x['invariant']=='accounting' for x in audit(r,runner))


def test_zero_trade_statistics_and_concentration_are_defined():
    assert stats([])['profit_factor'] is None
    c=concentration([], [pd.Timestamp('2026-09-01').date()])
    assert c['best_session_net_pnl']==0
    assert c['best_five_share_of_total_net_percent'] is None
    assert c['concentration_flag'] is False


def test_concentration_signed_net_share_and_denominators():
    dates=[pd.Timestamp('2026-09-01').date(),pd.Timestamp('2026-09-02').date()]
    ts=[dict(entry_timestamp=pd.Timestamp('2026-09-01'),pnl=90.,gross_pnl=100.,charges=10.),
        dict(entry_timestamp=pd.Timestamp('2026-09-02'),pnl=-210.,gross_pnl=-200.,charges=10.)]
    c=concentration(ts,dates)
    assert c['best_five_share_of_total_net_percent']==-75.
    assert c['top_five_profitable_sessions_gross_profit_percent']==100.
    assert c['top_five_losing_sessions_gross_loss_percent']==100.
    assert c['net_without_best_five']==-210.
