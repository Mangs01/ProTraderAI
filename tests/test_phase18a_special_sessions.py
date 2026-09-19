import json
from datetime import date
import pandas as pd
import pytest
from data.historical_cache import CANDLE_COLUMNS, HistoricalCache
from utils.time_utils import summarize_five_minute_sessions, validate_five_minute_sessions
from research.phase18_session_policy import Phase18SessionPolicy

POLICY=Phase18SessionPolicy(cas_eligible=True)
def bars(day,start,count):
    ts=pd.date_range(f'{day} {start}',periods=count,freq='5min',tz='Asia/Kolkata')
    return pd.DataFrame({'datetime':ts,'open':100.,'high':101.,'low':99.,'close':100.,'volume':1.})

def test_exact_muhurat_grid_accepted_and_deterministic():
    df=bars('2025-10-21','13:45',12)
    s=summarize_five_minute_sessions(df,session_policy=POLICY)[0]
    assert POLICY.regime_for(date(2025,10,21)).value=='SPECIAL_MUHURAT'
    assert POLICY.expected_bar_times(date(2025,10,21))==tuple(pd.date_range('2000-01-01 13:45','2000-01-01 14:40',freq='5min').time)
    assert s['expected_regular_bar_count']==12 and not s['missing_expected_bar_starts'] and validate_five_minute_sessions(df,session_policy=POLICY) is df

def test_missing_any_muhurat_bar_rejected():
    df=bars('2025-10-21','13:45',12).drop(index=4)
    with pytest.raises(ValueError): validate_five_minute_sessions(df,session_policy=POLICY)

def test_duplicate_muhurat_bar_rejected():
    df=bars('2025-10-21','13:45',12); df=pd.concat([df,df.iloc[[3]]],ignore_index=True)
    with pytest.raises(ValueError): validate_five_minute_sessions(df,session_policy=POLICY)

def test_off_grid_and_preopen_rejected():
    df=bars('2025-10-21','13:45',12); df.loc[0,'datetime']=pd.Timestamp('2025-10-21 13:47',tz='Asia/Kolkata')
    with pytest.raises(ValueError): validate_five_minute_sessions(df,session_policy=POLICY)
    df=bars('2025-10-21','13:45',12); df=pd.concat([pd.DataFrame([{'datetime':pd.Timestamp('2025-10-21 09:15',tz='Asia/Kolkata'),'open':100.,'high':101.,'low':99.,'close':100.,'volume':1.}]),df],ignore_index=True)
    with pytest.raises(ValueError): validate_five_minute_sessions(df,session_policy=POLICY)

def test_1445_not_required_but_postclose_row_rejected():
    df=bars('2025-10-21','13:45',12); validate_five_minute_sessions(df,session_policy=POLICY)
    extra=pd.DataFrame([{'datetime':pd.Timestamp('2025-10-21 14:45',tz='Asia/Kolkata'),'open':100.,'high':101.,'low':99.,'close':100.,'volume':1.}])
    with pytest.raises(ValueError): validate_five_minute_sessions(pd.concat([df,extra],ignore_index=True),session_policy=POLICY)

def test_arbitrary_12bar_legacy_and_normal_legacy_require_75():
    with pytest.raises(ValueError): validate_five_minute_sessions(bars('2025-10-20','09:15',12),session_policy=POLICY)
    validate_five_minute_sessions(bars('2025-10-20','09:15',75),session_policy=POLICY)

def test_cas_unchanged_and_special_exact_lookup_no_network():
    cas=bars('2026-09-01','09:15',72)
    assert POLICY.regime_for(date(2026,9,1)).value=='CAS_ELIGIBLE'
    validate_five_minute_sessions(cas,session_policy=POLICY)
    assert POLICY.special_session(date(2025,10,20)) is None

def test_policy_metadata_records_registry_and_rejects_old_semantics():
    metadata=POLICY.metadata()
    assert metadata['version']==2 and 'special_sessions' in metadata
    assert metadata['special_sessions']['2025-10-21']['classification']=='SPECIAL_MUHURAT'
    old=dict(metadata); old.pop('special_sessions')
    assert old != metadata

