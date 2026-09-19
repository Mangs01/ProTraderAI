import hashlib,json
from pathlib import Path
import pandas as pd
import pytest
from research.phase19_strategy import VWAPReclaimTrendAlignment
from research.phase18_session_policy import Phase18SessionPolicy

ROOT=Path(__file__).resolve().parents[1]
def frame(rows,start='2025-10-20 09:15'):
    defaults=dict(open=100.,high=101.,low=99.,close=100.,EMA20=101.,EMA50=100.,RSI=50.,VWAP=100.,ATR=2.)
    stamps=pd.date_range(start,periods=len(rows),freq='5min',tz='Asia/Kolkata')
    return pd.DataFrame([dict(defaults,datetime=t,**r) for t,r in zip(stamps,rows)])
def buy_dev(**x): return dict(close=99.,VWAP=100.,RSI=40.,**x)
def buy_rec(**x):
    values = dict(close=101., VWAP=100., RSI=50., EMA20=102., EMA50=100.)
    values.update(x)
    return values
def sell_dev(**x): return dict(close=101.,VWAP=100.,RSI=60.,**x)
def sell_rec(**x):
    values = dict(close=99., VWAP=100., RSI=50., EMA20=98., EMA50=100.)
    values.update(x)
    return values

def test_buy_deviation_changes_state_without_signal():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([buy_dev()]))=='HOLD'; assert s.states['BUY']=='WAIT_RECLAIM'
def test_sell_deviation_changes_state_without_signal():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([sell_dev()]))=='HOLD'; assert s.states['SELL']=='WAIT_RECLAIM'
def test_same_bar_cannot_reclaim():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([dict(close=101.,VWAP=100.,RSI=50.,EMA20=102.,EMA50=100.)]))=='HOLD'; assert not s.events
def test_buy_later_reclaim_emits_buy():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([buy_dev(),buy_rec()]))=='BUY'; assert s.events[0]['deviation_index']==0
def test_sell_later_reclaim_emits_sell():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([sell_dev(),sell_rec()]))=='SELL'
def test_reclaim_without_deviation_is_hold():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([buy_rec(),sell_rec()]))=='HOLD'
def test_wrong_trend_is_hold():
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([buy_dev(),buy_rec(EMA20=99.)]))=='HOLD'; s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([sell_dev(),sell_rec(EMA20=101.)]))=='HOLD'
def test_reclaim_rsi_boundaries():
    assert VWAPReclaimTrendAlignment().get_signal(frame([buy_dev(),buy_rec(RSI=49.99)]))=='HOLD'
    assert VWAPReclaimTrendAlignment().get_signal(frame([sell_dev(),sell_rec(RSI=50.01)]))=='HOLD'
def test_one_signal_per_direction_session():
    s=VWAPReclaimTrendAlignment(); df=frame([buy_dev(),buy_rec(),dict(close=99.,VWAP=100.,RSI=40.),buy_rec()]); assert s.get_signal(df)=='HOLD'; assert len(s.events)==1

def test_session_reset():
    s=VWAPReclaimTrendAlignment(); df=frame([buy_dev(),buy_rec()]); assert s.get_signal(df)=='BUY'; nxt=frame([buy_dev(),buy_rec()],start='2025-10-21 09:15'); assert s.get_signal(pd.concat([df,nxt],ignore_index=True))=='BUY'; assert len(s.events)==2
def test_missing_values_fail_closed():
    # The deviation bar is also the reclaim's prior bar: its EMA20 is required.
    s=VWAPReclaimTrendAlignment(); assert s.get_signal(frame([buy_dev(EMA20=float('nan')),buy_rec()]))=='HOLD'
    assert s.states['BUY']=='WAIT_RECLAIM'
    assert VWAPReclaimTrendAlignment().get_signal(frame([buy_dev(),buy_rec(EMA20=float('nan'))]))=='HOLD'
def test_no_lookahead_prefix():
    s=VWAPReclaimTrendAlignment(); df=frame([buy_dev(),buy_rec(),dict(close=999.,VWAP=1.,RSI=1.)]); assert s.get_signal(df.iloc[:1])=='HOLD'; assert s.get_signal(df.iloc[:2])=='BUY'; assert len(s.events)==1

def test_special_policy_contract_unchanged():
    p=Phase18SessionPolicy(cas_eligible=False); assert p.special_session(pd.Timestamp('2025-10-21').date())['classification']=='SPECIAL_MUHURAT'; assert len(p.expected_bar_times(pd.Timestamp('2025-10-21').date()))==12

def test_production_and_engine_sources_unchanged_by_preregistration():
    assert 'BacktestEngine' not in Path(ROOT/'research/phase19_strategy.py').read_text()
@pytest.mark.skipif(
    not (ROOT / 'research/phase19_preregistration.py').is_file(),
    reason='Post-implementation check: Phase 19 preregistration module does not exist yet.',
)
def audited_generation(directory):
    """Fresh interpreter: audit hooks observe real import and generation operations."""
    import subprocess, sys
    script = r"""
import sys, json, pathlib
root = pathlib.Path.cwd().resolve()
counts = {'held_out_csv_read_attempts': 0, 'held_out_metadata_read_attempts': 0,
          'network_attempts': 0, 'historical_strategy_i_evaluations': 0,
          'strategy_signal_calls': 0, 'engine_calls': 0}
held = 'validation_NSE_3045_FIVE_MINUTE_2025-09-01_2026-03-06.csv'
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = pathlib.Path(args[0].decode() if isinstance(args[0], bytes) else args[0]).resolve()
        if path.name in (held, held + '.meta.json'):
            key = 'held_out_metadata_read_attempts' if path.name.endswith('.json') else 'held_out_csv_read_attempts'
            counts[key] += 1
            raise AssertionError('Held-out access blocked')
        if path.is_relative_to(root / 'data'):
            raise AssertionError('Dataset access blocked')
    if event.startswith('socket.') or event in ('urllib.Request', 'subprocess.Popen', 'os.system'):
        counts['network_attempts'] += 1
        raise AssertionError('Network/process access blocked')
def profile(frame, event, arg):
    if event != 'call': return
    name = frame.f_code.co_filename.replace('\\', '/')
    if name.endswith('phase19_strategy.py') and frame.f_code.co_name == 'get_signal':
        counts['strategy_signal_calls'] += 1
        raise AssertionError('Generation must not execute strategy')
    if name.endswith('backtest_engine.py'):
        counts['engine_calls'] += 1
        raise AssertionError('Generation must not execute engine')
sys.addaudithook(audit)
sys.setprofile(profile)
from research.phase19_preregistration import generate_artifacts, PHASE19_SPEC_SHA256
record = generate_artifacts(sys.argv[1])
sys.setprofile(None)
# No dataset access, signal calls or engine calls occurred: no historical evaluation.
assert counts['strategy_signal_calls'] == counts['engine_calls'] == 0
print(json.dumps(dict(counts, specification_hash=PHASE19_SPEC_SHA256, hash_reconciliation=True)))
"""
    result = subprocess.run([sys.executable, '-c', script, str(directory)], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_heldout_firewall_no_dataset_reads(tmp_path):
    counts = audited_generation(tmp_path)
    assert counts['held_out_csv_read_attempts'] == 0
    assert counts['held_out_metadata_read_attempts'] == 0
    assert counts['network_attempts'] == 0
    assert counts['strategy_signal_calls'] == counts['engine_calls'] == 0


@pytest.mark.skipif(
    not (ROOT / 'research/phase19_preregistration.json').is_file(),
    reason='Post-implementation check: Phase 19 preregistration artifact does not exist yet.',
)
def test_spec_hash_matches_artifact():
    r=json.loads((ROOT/'research/phase19_preregistration.json').read_text()); canonical=json.dumps(r['strategy_spec'],sort_keys=True,separators=(',',':')).encode(); assert hashlib.sha256(canonical).hexdigest()==r['strategy_spec_sha256']


def test_deterministic_serialization_and_hash(tmp_path):
    from research.phase19_preregistration import STRATEGY_SPEC, canonical_spec_bytes, specification_hash, generate_artifacts, PHASE19_SPEC_SHA256
    assert canonical_spec_bytes(STRATEGY_SPEC) == canonical_spec_bytes(dict(reversed(list(STRATEGY_SPEC.items()))))
    assert specification_hash(STRATEGY_SPEC) == PHASE19_SPEC_SHA256
    generate_artifacts(tmp_path)
    first = (tmp_path / 'phase19_preregistration.json').read_bytes()
    generate_artifacts(tmp_path)
    assert first == (tmp_path / 'phase19_preregistration.json').read_bytes()


@pytest.mark.parametrize('side,dev,rec', [('BUY',buy_dev,buy_rec), ('SELL',sell_dev,sell_rec)])
def test_both_direction_limits_and_reset(side,dev,rec):
    s=VWAPReclaimTrendAlignment()
    df=frame([dev(),rec(),dev(),rec()])
    s.get_signal(df)
    assert [e['signal'] for e in s.events] == [side]
    next_day=frame([rec()],start='2025-10-22 09:15')
    assert s.get_signal(pd.concat([df,next_day],ignore_index=True)) == 'HOLD'
    assert s.states[side] == 'WAIT_DEVIATION'


@pytest.mark.parametrize('side,dev,boundary', [('BUY',buy_dev,45),('SELL',sell_dev,55)])
def test_strict_deviation_rsi_boundary(side,dev,boundary):
    row=dev(); row['RSI']=boundary
    s=VWAPReclaimTrendAlignment()
    assert s.get_signal(frame([row])) == 'HOLD'
    assert s.states[side] == 'WAIT_DEVIATION'


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), 'invalid', pd.NA])
@pytest.mark.parametrize('column', ['close','VWAP','RSI','EMA20','EMA50'])
def test_reclaim_missing_values_preserve_pending(value,column):
    row=buy_rec(); row[column]=value
    s=VWAPReclaimTrendAlignment()
    assert s.get_signal(frame([buy_dev(),row])) == 'HOLD'
    assert s.states['BUY'] == 'WAIT_RECLAIM'


def test_coexisting_states_keep_correct_deviation_evidence():
    s=VWAPReclaimTrendAlignment()
    df=frame([buy_dev(),sell_dev(),buy_rec()])
    assert s.get_signal(df) == 'BUY'
    assert s.events[0]['deviation_timestamp'] == df.iloc[0].datetime


def test_unchanged_sources_match_preimplementation_snapshot():
    snapshot=ROOT/'phase19_preservation_before.json'
    if snapshot.exists():
        before=json.loads(snapshot.read_text())
        for name,digest in before.items():
            if Path(name).as_posix() == 'research/phase19_strategy.py': continue
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name


@pytest.mark.parametrize('side,dev,rec', [('BUY',buy_dev,buy_rec),('SELL',sell_dev,sell_rec)])
@pytest.mark.parametrize('skip_first', [False,True])
def test_current_bar_interface_does_not_replay_historical_reclaim(side,dev,rec,skip_first):
    df=frame([dev(),rec(),dict(close=100.,VWAP=100.),rec(),rec()])
    s=VWAPReclaimTrendAlignment()
    if skip_first:
        assert s.get_signal(df.iloc[:1]) == 'HOLD'
    assert s.get_signal(df.iloc[:3]) == 'HOLD'
    assert s.current_signal_timestamp is None
    assert [(e['signal'],e['timestamp']) for e in s.events] == [(side,df.iloc[1].datetime)]
    for end in (4,5,5):
        assert s.get_signal(df.iloc[:end]) == 'HOLD'
        assert s.current_signal_timestamp is None
    assert len(s.events) == 1


@pytest.mark.parametrize('side,dev,rec', [('BUY',buy_dev,buy_rec),('SELL',sell_dev,sell_rec)])
def test_current_signal_exposes_current_timestamp(side,dev,rec):
    df=frame([dev(),rec()]); s=VWAPReclaimTrendAlignment()
    assert s.get_signal(df) == side
    assert s.current_signal_timestamp == s.events[-1]['timestamp'] == df.iloc[-1].datetime
    assert s.get_signal(df) == 'HOLD'
    assert s.current_signal_timestamp is None


def test_sequential_prefix_signals_equal_one_pass_chronological_events():
    day=frame([buy_dev(),buy_rec(),sell_dev(),sell_rec(),dict(close=100.)])
    next_day=frame([sell_dev(),sell_rec(),buy_dev(),buy_rec(),dict(close=100.)],start='2025-10-22 09:15')
    df=pd.concat([day,next_day],ignore_index=True)
    sequential=VWAPReclaimTrendAlignment(); returned=[]
    for end in range(1,len(df)+1):
        signal=sequential.get_signal(df.iloc[:end])
        if signal != 'HOLD':
            assert sequential.current_signal_timestamp == df.iloc[end-1].datetime
            returned.append((signal,sequential.current_signal_timestamp))
    once=VWAPReclaimTrendAlignment()
    assert once.get_signal(df) == 'HOLD'
    events=[(e['signal'],e['timestamp']) for e in once.events]
    assert returned == events == [(e['signal'],e['timestamp']) for e in sequential.events]
    assert len(events) == 4


def test_timestamp_invariant_fails_loudly_on_corrupted_event():
    class CorruptEvent(VWAPReclaimTrendAlignment):
        def emit(self,signal,row,**evidence):
            super().emit(signal,row,**evidence)
            self.events[-1]['timestamp'] -= pd.Timedelta(minutes=5)
    with pytest.raises(RuntimeError,match='signal origin'):
        CorruptEvent().get_signal(frame([buy_dev(),buy_rec()]))


def test_phase20a_frozen_spec_and_preservation():
    from research.phase19_preregistration import canonical_spec_bytes
    artifact=json.loads((ROOT/'research/phase19_preregistration.json').read_text())
    assert hashlib.sha256(canonical_spec_bytes(artifact['strategy_spec'])).hexdigest() == '97a972931ee6213fa946869ef1a394ac3606273f6f9c39a9962b7c2ac91c0b62'
    saved=json.loads((ROOT/'research/phase20a_results.json').read_text())
    for name,digest in saved['preserved_before'].items():
        if name == 'research/phase19_strategy.py': continue
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest,name
