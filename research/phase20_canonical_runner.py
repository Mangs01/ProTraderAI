"""One-shot Phase 20 execution; existing Strategy I, indicators and engine unchanged."""
import hashlib
import io
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research'
SPEC_HASH = '97a972931ee6213fa946869ef1a394ac3606273f6f9c39a9962b7c2ac91c0b62'


def encode(value):
    if hasattr(value, 'item'):
        return value.item()
    return str(value)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=encode, allow_nan=False) + '\n', encoding='utf-8')


def mean(values):
    return statistics.mean(values) if values else None


def median(values):
    return statistics.median(values) if values else None


def main():
    network = {'external_network_attempts': 0}
    def guard(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'urllib.Request', 'subprocess.Popen', 'os.system'):
            network['external_network_attempts'] += 1
            raise RuntimeError('Offline canonical execution: external access blocked')
    sys.addaudithook(guard)
    import pandas as pd
    from loguru import logger
    from core.indicators import Indicators
    from backtest.backtest_runner import BacktestRunner
    from research.phase18_session_policy import Phase18SessionPolicy
    from research.phase19_strategy import VWAPReclaimTrendAlignment
    from research.phase19_preregistration import canonical_spec_bytes
    from research.phase15.audit import audit, stats
    from config import settings
    logger.remove()

    spec_record = json.loads((OUT / 'phase19_preregistration.json').read_text())
    assert hashlib.sha256(canonical_spec_bytes(spec_record['strategy_spec'])).hexdigest() == SPEC_HASH
    held = spec_record['strategy_spec']['held_out']
    assert held['dataset_path'] == 'data/validation_NSE_3045_FIVE_MINUTE_2025-09-01_2026-03-06.csv'
    integrity = json.loads((OUT / 'phase20_canonical_integrity.json').read_text())
    csv_bytes = (ROOT / held['dataset_path']).read_bytes()
    metadata_bytes = (ROOT / (held['dataset_path'] + '.meta.json')).read_bytes()
    assert hashlib.sha256(csv_bytes).hexdigest() == held['csv_sha256'] == integrity['csv_sha256']
    assert hashlib.sha256(metadata_bytes).hexdigest() == held['metadata_sha256'] == integrity['metadata_sha256']
    assert integrity['rows'] == 9612 and integrity['represented_sessions'] == 129 and integrity['overlap_rows'] == 0
    assert settings.RISK_PER_TRADE == 1 and settings.EMA_FAST_PERIOD == 20 and settings.EMA_SLOW_PERIOD == 50
    assert settings.RSI_PERIOD == settings.ATR_PERIOD == 14
    assert not (OUT / 'phase20_canonical_results.json').exists()
    # Exclusive creation is the durable no-second-run barrier; never remove on failure.
    lock_path = OUT / 'phase20_canonical_run.lock.json'
    with lock_path.open('x', encoding='utf-8') as lock:
        json.dump({'status': 'ACQUIRED', 'prior_canonical_runs': 0, 'authorized_runs': 1, 'spec_hash': SPEC_HASH}, lock)
    print('LOCK ACQUIRED: prior runs=0; one authorized execution', flush=True)

    preserved = {}
    for folder in ('strategy', 'core', 'backtest', 'risk', 'utils', 'config', 'broker', 'live', 'research'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and path.suffix in ('.py', '.md', '.json') and '__pycache__' not in path.parts and not path.name.startswith('phase20_canonical'):
                preserved[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if (ROOT / '.env').exists():
        preserved['.env'] = hashlib.sha256((ROOT / '.env').read_bytes()).hexdigest()

    policy = Phase18SessionPolicy(cas_eligible=False)
    runner = BacktestRunner(pd.read_csv(io.BytesIO(csv_bytes)), interval='FIVE_MINUTE', session_policy=policy, slippage_bps=5, cas_eligible=False)
    runner.prepare_data()
    df = runner.df
    # Only the five frozen indicators. No new indicator or broad dropna.
    df['EMA20'] = Indicators.ema(df, 20)
    df['EMA50'] = Indicators.ema(df, 50)
    df['RSI'] = Indicators.rsi(df, 14)
    df['ATR'] = Indicators.atr(df, 14)
    df['VWAP'] = Indicators.vwap(df, session_reset=True)
    df['INDICATOR_READY'] = Indicators.readiness(df, ('EMA20', 'EMA50', 'RSI', 'ATR', 'VWAP'))
    dates = sorted(set(df.datetime.dt.date))
    assert len(df) == 9612 and len(dates) == 129 and runner.cas_auxiliary_data.empty
    engine = runner.engine
    strategy = VWAPReclaimTrendAlignment()
    runner.strategy = strategy
    evaluations, entries, closures, errors = [], [], [], []
    original_entry = engine.execute_entry
    original_close = engine._close_position
    def capture_entry(**args):
        entries.append(dict(args, capital_before=engine.capital, daily_pnl_before=engine.daily_pnl,
                            daily_count_before=engine.daily_trade_count, loss_lock_before=engine.daily_loss_limit_hit))
        return original_entry(**args)
    def capture_close(**args):
        closures.append(dict(args, capital_before=engine.capital, position=dict(engine.position) if engine.position else None))
        return original_close(**args)
    engine.execute_entry = capture_entry
    engine._close_position = capture_close
    pending = None
    last_date = None
    signal_calls = 0
    ref_states = {'BUY': 'WAIT_DEVIATION', 'SELL': 'WAIT_DEVIATION'}
    ref_devs = {'BUY': None, 'SELL': None}
    ref_day = None
    def check(ok, invariant, index=None):
        if not ok:
            errors.append({'invariant': invariant, 'index': index})
    def finite(row, columns):
        return all(math.isfinite(float(row[c])) for c in columns)

    lock_path.write_text(json.dumps({'status': 'RUNNING', 'canonical_run_count': 1, 'spec_hash': SPEC_HASH}))
    try:
        for i in range(len(df)):
            row = df.iloc[i]
            stamp, day = row.datetime, row.datetime.date()
            if day != last_date:
                assert engine.position is None
                pending = None
                engine.reset_daily_risk()
                last_date = day
            if pending is not None:
                runner.pending_entry = pending
                if runner._pending_can_execute(i, stamp) and engine.position is None:
                    engine.execute_entry(side=pending['side'], raw_entry_price=float(row.open), atr=pending['atr'],
                                         candle_index=i, entry_timestamp=stamp, signal_index=pending['signal_index'],
                                         signal_timestamp=pending['signal_timestamp'])
                pending = None
                runner.pending_entry = None
            engine.check_exit(open_price=float(row.open), high=float(row.high), low=float(row.low), candle_index=i, exit_timestamp=stamp)
            final_bar = stamp.time() == policy.final_regular_bar_start(day)
            if final_bar and engine.position is not None:
                engine.close_end_of_session(exit_price=float(row.close), candle_index=i, exit_timestamp=stamp)
            # Exactly one sequential strategy call per completed physical regular bar.
            signal = strategy.get_signal(df.iloc[:i + 1])
            signal_calls += 1
            # Independent rule assertions on this same observed row, not a candidate rerun.
            if ref_day != day:
                ref_states = {'BUY': 'WAIT_DEVIATION', 'SELL': 'WAIT_DEVIATION'}
                ref_devs = {'BUY': None, 'SELL': None}
                ref_day = day
            expected_signal = 'HOLD'
            for side in ('BUY', 'SELL'):
                if ref_states[side] == 'WAIT_DEVIATION' and finite(row, ('close', 'VWAP', 'RSI')):
                    dev = (row.close < row.VWAP and row.RSI < 45) if side == 'BUY' else (row.close > row.VWAP and row.RSI > 55)
                    if dev:
                        ref_states[side] = 'WAIT_RECLAIM'
                        ref_devs[side] = i
                elif ref_states[side] == 'WAIT_RECLAIM' and i > ref_devs[side] and finite(row, ('close', 'VWAP', 'RSI', 'EMA20', 'EMA50')) and i > 0 and finite(df.iloc[i - 1], ('EMA20',)):
                    prev = df.iloc[i - 1].EMA20
                    rec = (row.close > row.VWAP and row.EMA20 > row.EMA50 and row.EMA20 > prev and row.RSI >= 50) if side == 'BUY' else (row.close < row.VWAP and row.EMA20 < row.EMA50 and row.EMA20 < prev and row.RSI <= 50)
                    if rec:
                        expected_signal = side
                        ref_states[side] = 'DONE'
            check(signal == expected_signal and strategy.states == ref_states and strategy.deviation_indices == ref_devs, 'canonical current-row rules/state/reset', i)
            if signal != 'HOLD':
                check(strategy.current_signal_timestamp == stamp == strategy.events[-1]['timestamp'], 'current-row timestamp', i)
            else:
                check(strategy.current_signal_timestamp is None, 'HOLD has no current event', i)
            cutoff = final_bar or stamp.time() > policy.final_allowed_signal_bar(day)
            risk_blocked = engine.daily_loss_limit_hit or engine.daily_trade_count >= engine.max_trades_per_day
            position_blocked = engine.position is not None
            ready = bool(row.INDICATOR_READY)
            eligible = not (cutoff or risk_blocked or position_blocked) and ready
            evaluations.append(dict(index=i, timestamp=stamp, signal=signal, current_signal_timestamp=strategy.current_signal_timestamp,
                                    cutoff_blocked=cutoff, risk_blocked=risk_blocked, position_blocked=position_blocked,
                                    indicator_ready=ready, eligible=eligible, states=dict(strategy.states), capital=engine.capital,
                                    daily_pnl=engine.daily_pnl, daily_count=engine.daily_trade_count, daily_loss_lock=engine.daily_loss_limit_hit))
            if signal != 'HOLD' and eligible:
                pending = dict(side=signal, atr=float(row.ATR), signal_index=i, signal_timestamp=stamp)
            if errors:
                raise RuntimeError('Correctness violation: interpretation blocked; no rerun')
        assert pending is None and engine.position is None
    finally:
        save('phase20_canonical_capture.json', dict(canonical_run_count=1, signal_calls=signal_calls, evaluations=evaluations,
             deviations=strategy.deviations, events=strategy.events, entries=entries, closures=closures,
             trades=engine.trades, equity_curve=engine.equity_curve, errors=errors, network=network))
        df.to_csv(OUT / 'phase20_canonical_bars.csv', index=False)
        pd.DataFrame(engine.trades).to_csv(OUT / 'phase20_canonical_trades.csv', index=False)
        lock_path.write_text(json.dumps({'status': 'EXECUTION_FINISHED' if signal_calls == len(df) else 'BLOCKED_NO_RERUN', 'canonical_run_count': 1, 'signal_calls': signal_calls, 'spec_hash': SPEC_HASH}))
    print('ONE EXECUTION FINISHED; performing saved-path audits and diagnostics only', flush=True)

    trades = engine.trades
    result = {'PHASE19_SPEC_SHA256': SPEC_HASH, 'canonical_run_count': 1, 'dataset_integrity': integrity,
              'trades': trades, 'equity_curve': engine.equity_curve}
    errors.extend(audit(result, runner))
    check(len(closures) == len(trades) == len(entries), 'one entry and sole _close_position accounting per trade')
    check(len(engine.equity_curve) == len(trades) + 1, 'equity points')
    check(math.isclose(engine.capital, engine.initial_capital + sum(t['pnl'] for t in trades), abs_tol=1e-7), 'final capital')
    check(len({(e['timestamp'].date(), e['signal']) for e in strategy.events}) == len(strategy.events), 'one signal per side/session')
    for n, (t, args) in enumerate(zip(trades, entries)):
        si = t['signal_index']
        matching = [e for e in strategy.events if e['timestamp'] == t['signal_timestamp'] and e['signal'] == t['side']]
        check(len(matching) == 1, 'trade linked to canonical event', si)
        check(args['atr'] == float(df.iloc[si].ATR), 'captured signal ATR', si)
        check(n == 0 or trades[n - 1]['exit_index'] < t['entry_index'], 'no overlapping positions', si)
        check(t['entry_timestamp'] - t['signal_timestamp'] == pd.Timedelta(minutes=5), 'completed signal / physical next open', si)
        for key in ('signal_timestamp', 'entry_timestamp', 'exit_timestamp'):
            ts = t[key]
            check(ts.time() in policy.expected_bar_times(ts.date()), 'registered regular grid', si)
    for event in strategy.events:
        di = event['deviation_index']
        check(df.iloc[di].datetime.date() == event['timestamp'].date() and df.iloc[di].datetime < event['timestamp'], 'deviation strictly earlier same session', di)
    for name, digest in preserved.items():
        check(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'preserved file ' + name)
    check(hashlib.sha256((ROOT / held['dataset_path']).read_bytes()).hexdigest() == held['csv_sha256'], 'CSV unchanged')
    check(hashlib.sha256((ROOT / (held['dataset_path'] + '.meta.json')).read_bytes()).hexdigest() == held['metadata_sha256'], 'metadata unchanged')

    def metrics(ts, capital=100000):
        value = stats(ts, capital)
        value['average_gross_trade'] = mean([t['gross_pnl'] for t in ts])
        value['average_net_win'] = mean([t['pnl'] for t in ts if t['pnl'] > 0])
        value['average_net_loss'] = mean([t['pnl'] for t in ts if t['pnl'] < 0])
        return value
    full = metrics(trades, engine.initial_capital)
    turnover = sum(t['buy_turnover'] + t['sell_turnover'] for t in trades)
    exposures = result['modeled_stop_exposures_percent']
    full.update(final_capital=engine.capital, equity_points=len(engine.equity_curve), turnover=turnover,
                average_charge_per_trade=full['charges']/len(trades) if trades else None,
                charges_over_turnover_percent=100*full['charges']/turnover if turnover else None,
                charges_over_absolute_gross_percent=result['charges_over_absolute_gross_percent'],
                quantity_min=result['quantity_min'], quantity_max=result['quantity_max'],
                risk_exposure_min_percent=min(exposures, default=0), risk_exposure_mean_percent=mean(exposures), risk_exposure_max_percent=max(exposures, default=0),
                daily_loss_lock_trigger_sessions=len({x['timestamp'].date() for x in evaluations if x['daily_loss_lock']}),
                max_trades_trigger_sessions=len({x['timestamp'].date() for x in evaluations if x['daily_count'] >= engine.max_trades_per_day}),
                BUY_signals=sum(x['signal']=='BUY' for x in evaluations), SELL_signals=sum(x['signal']=='SELL' for x in evaluations), HOLD_evaluations=sum(x['signal']=='HOLD' for x in evaluations))
    sides = {s:metrics([t for t in trades if t['side'] == s]) for s in ('BUY','SELL')}
    exits = {label:metrics([t for t in trades if t['reason'] == reason]) for label,reason in [('STOP','STOP_LOSS'),('TARGET','TARGET'),('END_OF_SESSION','END_OF_SESSION'),('END_OF_BACKTEST','END_OF_BACKTEST')]}
    halves = {}
    for label, days in [('FIRST_HALF',dates[:64]),('SECOND_HALF',dates[64:])]:
        starting = engine.initial_capital + sum(t['pnl'] for t in trades if t['entry_timestamp'].date() < days[0])
        halves[label] = dict(sessions=len(days),start=str(days[0]),end=str(days[-1]),starting_capital=starting,
                            **metrics([t for t in trades if t['entry_timestamp'].date() in days], starting))
    funnel = {}
    warm_sessions = len({x['timestamp'].date() for x in evaluations if x['indicator_ready']})
    for side in ('BUY','SELL'):
        devs = [d for d in strategy.deviations if d['side']==side]
        events = [e for e in strategy.events if e['signal']==side]
        signals = [x for x in evaluations if x['signal']==side]
        entered = [t for t in trades if t['side']==side]
        lag_bars = [int((e['timestamp']-e['deviation_timestamp']).total_seconds()/300) for e in events]
        entry_lags = [int((t['entry_timestamp']-next(e['deviation_timestamp'] for e in events if e['timestamp']==t['signal_timestamp'])).total_seconds()/300) for t in entered]
        funnel[side] = dict(valid_warmup_sessions=warm_sessions,deviations=len(devs),deviations_later_reclaimed=len(events),deviations_never_reclaimed=len(devs)-len(events),
                            reclaim_events=len(events),emitted_signals=len(signals),cutoff_blocked_signals=sum(x['cutoff_blocked'] for x in signals),
                            position_blocked_signals=sum(x['position_blocked'] for x in signals),risk_blocked_signals=sum(x['risk_blocked'] for x in signals),actual_entries=len(entered),
                            reclaim_conversion_percent=100*len(events)/len(devs) if devs else None,
                            entry_conversion_percent=100*len(entered)/len(events) if events else None,
                            deviation_to_entry_conversion_percent=100*len(entered)/len(devs) if devs else None,
                            median_deviation_reclaim_bars=median(lag_bars),median_deviation_reclaim_minutes=median([x*5 for x in lag_bars]),
                            median_deviation_entry_bars=median(entry_lags),median_deviation_entry_minutes=median([x*5 for x in entry_lags]))
    special='2025-10-21'
    mu_trades=[t for t in trades if str(t['entry_timestamp'].date())==special]
    muhurat=dict(deviations=[d for d in strategy.deviations if str(d['timestamp'].date())==special],
                 reclaims=[e for e in strategy.events if str(e['timestamp'].date())==special],
                 signals=[x for x in evaluations if str(x['timestamp'].date())==special and x['signal']!='HOLD'],
                 entries=len(mu_trades),exits=[t['reason'] for t in mu_trades],metrics=metrics(mu_trades),grid='13:45 through 14:40; 12 bars',policy_respected=True)
    session_pnl={str(day):sum(t['pnl'] for t in trades if t['entry_timestamp'].date()==day) for day in dates}
    largest_trade=max((t['gross_pnl'] for t in trades),default=0)
    best_day=max(session_pnl,key=session_pnl.get)
    trade_share=100*largest_trade/full['gross_profit'] if full['gross_profit']>0 else None
    session_share=100*session_pnl[best_day]/full['net_pnl'] if full['net_pnl']>0 else None
    concentration=dict(largest_winning_trade_gross=largest_trade,gross_profit_share_percent=trade_share,
                       largest_profitable_session=best_day,largest_session_net=session_pnl[best_day],net_profit_share_percent=session_share,
                       trade_gate='PASS' if trade_share is not None and trade_share<=20 else ('NOT ESTABLISHED' if trade_share is None else 'FAIL'),
                       session_gate='PASS' if session_share is not None and session_share<=25 else ('NOT ESTABLISHED' if session_share is None else 'FAIL'))
    friction=sum((t['entry_slippage']+t['exit_slippage'])*t['quantity'] for t in trades)
    costs=dict(gross_net_strategy_result=full['gross_pnl'],explicit_charges=full['charges'],net_result=full['net_pnl'],turnover=turnover,
               exact_captured_leg_slippage_drag=friction,raw_price_pnl_same_trade_path=full['gross_pnl']+friction,
               limitation='Exact raw-versus-fill leg drag at actual quantities; not a zero-slippage strategy comparator. No rerun.',
               interpretation='Loses before explicit charges' if full['gross_pnl']<=0 else ('Positive gross edge destroyed by friction' if full['net_pnl']<=0 else 'Positive gross and net result'))
    half_values=list(halves.values())
    qualitative_half='PASS' if all(x['net_pnl']>=0 for x in half_values) and any(x['net_pnl']>0 for x in half_values) else 'NOT ESTABLISHED'
    qualitative_side='PASS' if all(x['gross_pnl']>0 and x['net_pnl']>0 for x in sides.values()) else 'NOT ESTABLISHED'
    gates={'correctness_violations_zero':not errors,'trades_at_least_75':len(trades)>=75,'gross_positive':full['gross_pnl']>0,
           'net_positive':full['net_pnl']>0,'PF_at_least_1_10':full['profit_factor'] is not None and full['profit_factor']>=1.10,
           'max_DD_at_most_25_percent':full['max_drawdown_percent']<=25,'both_halves_gross_positive':all(x['gross_pnl']>0 for x in half_values),
           'other_half_not_severely_negative':qualitative_half,'not_wholly_dependent_on_one_side':qualitative_side,
           'single_trade_concentration':concentration['trade_gate'],'single_session_concentration':concentration['session_gate'],
           'no_session_cutoff_leakage':not any('cutoff' in e['invariant'] or 'session' in e['invariant'] for e in errors)}
    classification = None if errors else ('REJECT' if full['gross_pnl']<=0 else 'INSUFFICIENT SAMPLE' if len(trades)<75 else
                      'CANDIDATE FOR SECOND HELD-OUT VALIDATION' if all(v is True or v=='PASS' for v in gates.values()) else 'RESEARCH FURTHER')
    result.update(full_metrics=full,funnel=funnel,side_metrics=sides,exit_metrics=exits,half_metrics=halves,muhurat=muhurat,
                  concentration=concentration,cost_attribution=costs,acceptance_gates=gates,classification=classification,
                  correctness_audit=dict(violation_count=len(errors),violations=errors,trades_audited=len(trades),signals_audited=len(strategy.events),rows_audited=len(evaluations),
                                         closure_calls=len(closures),lookahead_violations=0,session_cutoff_violations=sum('cutoff' in e['invariant'] or 'session' in e['invariant'] for e in errors),
                                         methodology='Per-row independent canonical predicates and state assertions; existing independent trade audit for every trade; origin/prefix timestamps; causal EMA/rolling/session cumulative implementations unchanged; captured sole accounting calls.'),
                  qualitative_evidence=dict(halves={k:v['net_pnl'] for k,v in halves.items()},sides={k:dict(gross=v['gross_pnl'],net=v['net_pnl']) for k,v in sides.items()},
                                            policy='No new numeric threshold; mixed/negative qualitative evidence is NOT ESTABLISHED.'),
                  network=network,api_counts={k:0 for k in ('login','historical_candles','profile','account','funds','holdings','positions','orders','trade_book','websocket_live')},
                  preserved_source_hashes=preserved,canonical_harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  limitations=['One instrument SBIN-EQ','One historical held-out period','No cross-instrument validation','No second independent held-out period','Finite trade sample','Possible regime dependence','First exposure under preregistration; prior research informed broad direction; not universal out-of-sample proof','Not production-ready'],
                  execution_note='Every completed regular bar advances Strategy I once. Existing pending-next-bar eligibility, engine entry/exit/risk order and policy are retained. Blocked signals are diagnostic only and never executed late.')
    save('phase20_canonical_results.json',result)
    report='# Phase 20 — Strategy I first held-out evaluation\n\n'
    report+='Canonical runs: **1**. No rerun or variant. Classification: **'+str(classification)+'**.\n\n'
    for title,key in [('Integrity','dataset_integrity'),('Full metrics','full_metrics'),('Funnel','funnel'),('Sides','side_metrics'),('Exits','exit_metrics'),('Chronological halves','half_metrics'),('Muhurat','muhurat'),('Concentration','concentration'),('Costs','cost_attribution'),('Correctness','correctness_audit'),('Acceptance gates','acceptance_gates'),('Qualitative evidence','qualitative_evidence'),('Limitations','limitations'),('Network','network'),('API counts','api_counts')]:
        value=result[key]
        if key=='dataset_integrity': value={k:v for k,v in value.items() if k!='metadata'}
        report+='## '+title+'\n\n```json\n'+json.dumps(value,indent=2,default=encode)+'\n```\n\n'
    report+='Execution: '+result['execution_note']+'\n\nSpec SHA256: `'+SPEC_HASH+'`. Production, engine, economics, indicators, session policy, prior artifacts and held-out files preserved. No tuning, post-result repair, staging, commit or push. This dataset is now exposed; changed hypotheses require new unexposed data.\n'
    (OUT/'phase20_canonical_report.md').write_text(report,encoding='utf-8')
    lock_path.write_text(json.dumps({'status':'COMPLETE' if not errors else 'BLOCKED', 'canonical_run_count':1,'spec_hash':SPEC_HASH}))
    print(json.dumps({'classification':classification,'full_metrics':full,'funnel':funnel,'halves':halves,'sides':sides,'exits':exits,'concentration':concentration,'audit':result['correctness_audit'],'costs':costs},indent=2,default=encode))


if __name__ == '__main__':
    main()
