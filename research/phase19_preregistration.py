"""Strategy I definition and artifact writing only; no evaluation entry point."""
import hashlib
import json
from pathlib import Path
from research.phase19_strategy import VWAPReclaimTrendAlignment

STRATEGY_SPEC = {
    'phase': 19,
    'strategy_id': 'I',
    'strategy_name': 'VWAP RECLAIM WITH TREND ALIGNMENT',
    'research_status': 'PREREGISTERED; DEFINITION + FREEZE ONLY; NOT EVALUATED',
    'economic_hypothesis': 'Price first deviates from session VWAP, then later reclaims VWAP while the intraday EMA trend is aligned.',
    'sequence': ['DEVIATION', 'STRICTLY LATER RECLAIM', 'NEXT-PHYSICAL-BAR ENTRY'],
    'buy': {
        'deviation': ['close < session VWAP', 'RSI14 < 45'],
        'reclaim': ['close > session VWAP', 'EMA20 > EMA50', 'EMA20[N] > EMA20[N-1]', 'RSI14 >= 50']},
    'sell': {
        'deviation': ['close > session VWAP', 'RSI14 > 55'],
        'reclaim': ['close < session VWAP', 'EMA20 < EMA50', 'EMA20[N] < EMA20[N-1]', 'RSI14 <= 50']},
    'state_machine': {
        'initial': 'WAIT_DEVIATION', 'deviation_transition': 'WAIT_RECLAIM; no signal; EMA trend not required',
        'reclaim_transition': 'First strictly later completed regular bar satisfying ALL reclaim conditions emits direction and sets DONE',
        'same_bar_prohibited': True, 'session_reset': 'Both directions reset to WAIT_DEVIATION each session; no overnight state',
        'max_signals_per_direction_per_session': 1, 'directions_may_coexist': True,
        'fail_closed': 'Missing, nonnumeric or nonfinite current or prior values needed by a rule => HOLD / no signal; preserve pending state. Missing prior EMA20 cannot reclaim.',
        'input_contract': 'Monotonically growing prefix of completed regular bars only; caller applies unchanged session policy; never supply future bars'},
    'indicators': {
        'required': ['EMA20', 'EMA50', 'RSI14', 'ATR14', 'session VWAP'],
        'implementation': 'core/indicators.py: Indicators.ema/rsi/atr/vwap(session_reset=True)',
        'warm_up': 'Unchanged: EMA min_periods=period, RSI rolling(14), ATR rolling(14), VWAP cumulative close*volume / cumulative volume by session date',
        'column_mapping': {'RSI14': 'RSI', 'ATR14': 'ATR', 'session VWAP': 'VWAP'},
        'atr_role': 'Existing execution readiness and stop/target sizing; not an additional deviation/reclaim predicate'},
    'execution': {
        'phase': 20, 'signal': 'Completed regular bar N', 'entry': 'Physical regular bar N+1 open',
        'reference': 'backtest/backtest_engine.py; backtest/backtest_runner.py',
        'no_lookahead': True, 'no_overlapping_positions': True, 'no_overnight_position': True,
        'entry_cutoff': 'unchanged', 'CAS_and_special_sessions': 'unchanged',
        'stop_atr_multiple': 1.5, 'target_atr_multiple': 2.0,
        'entry_slippage_bps_adverse': 5, 'exit_slippage_bps_adverse': 5,
        'risk': 'Existing 1% research risk model and sizing; unchanged',
        'charges': 'Existing NSE intraday charge model used by backtest/backtest_engine.py; unchanged',
        'daily_loss_lock': 'unchanged', 'max_trades_per_day': 'unchanged', 'gap_handling': 'unchanged',
        'same_bar_stop_target_collision': 'STOP wins', 'END_OF_SESSION': 'existing policy unchanged'},
    'session_policy': {
        'reference': 'research/phase18_session_policy.py: Phase18SessionPolicy; utils/session_policy.py',
        'modification_permitted': False,
        'special_session': {'date': '2025-10-21', 'classification': 'SPECIAL_MUHURAT', 'market': '13:45–14:45', 'required_five_minute_starts': '13:45–14:40', 'required_count': 12}},
    'held_out': {
        'dataset_path': 'data/validation_NSE_3045_FIVE_MINUTE_2025-09-01_2026-03-06.csv',
        'csv_sha256': 'ade5eb291d420577878ada5e6ebf63dd109206deed5939745cde768a2efea16a',
        'metadata_sha256': 'cafa32c5b4c33734091047bda870df30ef97319280a0765f76551b93e4ebd884',
        'provenance': 'Supplied Phase 18A constants only; neither file opened, parsed or hashed by preregistration'},
    'phase20_evaluation_gates': {
        'classifications': ['REJECT', 'INSUFFICIENT SAMPLE', 'RESEARCH FURTHER', 'CANDIDATE FOR SECOND HELD-OUT VALIDATION'],
        'candidate_requires_all': ['correctness violations = 0', 'trades >= 75', 'gross net P&L > 0', 'net P&L > 0', 'PF >= 1.10', 'max DD <= 25%', 'both chronological halves gross-positive', 'at least one chronological half net-positive and the other not severely negative', 'no single trade >20% gross profit contribution', 'no single session >25% net profit contribution', 'not wholly dependent on BUY-only or SELL-only behavior', 'no session-policy/cutoff leakage'],
        'sample_rule': 'If trades < 75, maximum classification INSUFFICIENT SAMPLE even if profitable; no loosened rerun',
        'gross_failure_rule': 'Canonical gross net P&L <= 0 => REJECT unless a correctness defect makes the result uninterpretable; explicit fees are not the primary explanation of gross failure',
        'precedence': 'Correctness defect makes results uninterpretable: RESEARCH FURTHER with no candidate claim; otherwise gross failure REJECT; otherwise trades <75 INSUFFICIENT SAMPLE; otherwise all gates pass CANDIDATE FOR SECOND HELD-OUT VALIDATION; otherwise RESEARCH FURTHER',
        'qualitative_gates': 'Preserved verbatim; no invented numeric definition of severely negative or side dependence. An unestablished gate cannot be counted as passed.',
        'side_asymmetry': 'Symmetric frozen strategy; side statistics diagnostic only. No BUY-only, SELL-only or side-specific thresholds',
        'single_run': 'Exactly one canonical first-exposure evaluation on this reserved dataset; no variants, threshold alternatives or post-result change and rerun. Identical deterministic reproduction only for correctness, not another candidate. Altered strategy is a new hypothesis requiring different unexposed data'},
    'selection_contamination_disclosure': [
        'Prior March–September 2026 research informed the broad research direction',
        'Strategy I rules were frozen before opening Phase 18 price data',
        'Phase 18 Sep2025–Mar2026 price observations did not influence Strategy I parameter/rule choice',
        'Phase 20 is intended as first exposure to this reserved dataset; this is not universal out-of-sample proof'],
    'structural_distinction': 'Independent symmetric session state machines requiring deviation then a later VWAP reclaim with EMA alignment; not rejected A/D/E/F/G/H',
    'phase19_prohibitions': ['held-out file access', 'network', 'historical signals/trades/backtest', 'performance evaluation', 'production or engine or session-policy changes'],
}


def canonical_spec_bytes(spec):
    return json.dumps(spec, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def specification_hash(spec):
    return hashlib.sha256(canonical_spec_bytes(spec)).hexdigest()


PHASE19_SPEC_SHA256 = specification_hash(STRATEGY_SPEC)


def generate_artifacts(directory=None):
    """Write only preregistration documents, then reload JSON to reconcile hash."""
    directory = Path(directory) if directory is not None else Path(__file__).parent
    record = {'strategy_spec': STRATEGY_SPEC, 'strategy_spec_sha256': PHASE19_SPEC_SHA256,
              'PHASE19_SPEC_SHA256': PHASE19_SPEC_SHA256}
    destination = directory / 'phase19_preregistration.json'
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    reloaded = json.loads(destination.read_text(encoding='utf-8'))
    if specification_hash(reloaded['strategy_spec']) != reloaded['strategy_spec_sha256']:
        raise ValueError('Preregistration hash reconciliation failed')
    markdown = '# Phase 19 — Strategy I preregistration\n\nDefinition + freeze only. No historical evaluation.\n\n'
    markdown += 'PHASE19_SPEC_SHA256: `' + PHASE19_SPEC_SHA256 + '`\n\n'
    markdown += 'The complete frozen specification follows. Held-out hashes are supplied constants, not recomputed.\n\n```json\n'
    markdown += json.dumps(STRATEGY_SPEC, indent=2, ensure_ascii=False) + '\n```\n'
    (directory / 'phase19_preregistration.md').write_text(markdown, encoding='utf-8')
    return record


if __name__ == '__main__':
    generate_artifacts()
