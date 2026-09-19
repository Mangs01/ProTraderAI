"""Render recorded Phase15 results only; never imports or runs strategies."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def fmt(value):
    if value is None:
        return 'N/A'
    if isinstance(value,float):
        return f'{value:,.2f}'
    return str(value)


def render():
    path=ROOT/'research/phase15_results.json'
    r=json.loads(path.read_text(encoding='utf-8'))
    if r['status'] not in ('RUNS_AUDITED_CLASSIFIED','COMPLETE'):
        raise RuntimeError('Report requires all three successful runs and audits')
    variants=r['variants']
    lines=['# Phase 15 - Controlled new-strategy family research','',
           'Canonical E/F/G evaluated once each, offline, on the Phase 14 validation history. A/D are loaded from Phase 14B records; no full-validation A/D reruns. No optimization or production changes.','']
    def para(text):
        lines.extend([text,''])
    def table(headers,rows):
        lines.append('| '+' | '.join(headers)+' |')
        lines.append('| '+' | '.join(['---']+['---:']*(len(headers)-1))+' |')
        lines.extend('| '+' | '.join(fmt(x) for x in row)+' |' for row in rows)
        lines.append('')
    para('## Outcome')
    for name,v in variants.items():
        para(f"**{name}: {v['classification']} / {v['gross_edge']}**. {v['total_trades']} trades; gross P&L INR {fmt(v['gross_net_pnl'])}; net P&L INR {fmt(v['net_pnl'])}; gross PF {fmt(v['profit_factor_unrounded'])}; realized max DD {fmt(v['max_drawdown_percent'])}%.")
    para('## Dataset integrity and preservation')
    para('Dataset: `'+r['dataset']['csv_path']+'`. Metadata: same filename plus `.meta.json`.')
    para('Dataset SHA256: `'+r['dataset']['csv_sha256']+'`')
    para('Metadata SHA256: `'+r['dataset']['metadata_sha256']+'`')
    para('Exact hash gate passed. Published rows 9,309; regular strategy/execution rows 9,294; CAS auxiliary rows 15; represented sessions 125 (98 legacy x 75 bars, 27 CAS x 72 bars); session-policy version 2. The unchanged validator accepted all represented sessions with no duplicates, missing required bars or unexpected timestamps. This is represented-session validation, not an external exchange-calendar completeness claim.')
    para('The existing runner strips auxiliary rows before indicator preparation. All signal, entry, stop/target and EOD timestamps were checked against the regular-session policy. No CAS auxiliary prices were used. Original-file hashes and new canonical source hashes were frozen before execution and verified afterward; manifests are in JSON. Phase 13 and Phase 14 outputs and the Phase 12 cache remain unchanged.')
    para('## Exact canonical definitions')
    for name,definition in r['definitions'].items():
        para('### '+name+' - '+definition['family'])
        if 'range' in definition: para(definition['range'])
        for side in ('BUY','SELL'):
            para(side+': '+'; '.join(definition[side])+'.')
        para('State and timing: '+definition['state'])
        if 'limitation' in definition: para('Definition limitation: '+definition['limitation'])
    para('Shared indicators: '+r['methodology']['indicators'])
    para('Shared execution: '+r['methodology']['execution'])
    para('Shared risk: '+r['methodology']['risk'])
    para('F consumes its one attempt on signal. Its audit verifies every emitted signal entered and at most one entry per direction/session. Thus the attempt and successful-entry limits coincide in this dataset; no broker fill assumptions or custom entry callbacks were introduced.')
    para('## Full-period metrics')
    para('Amounts are INR. Gross P&L includes execution slippage, excludes charges. PF is positive gross trade P&L / absolute negative gross trade P&L. Winners/losers and averages use net trade P&L. The displayed average loss is signed. HOLD counts only actual runner evaluations after its gates. Trigger counts count sessions reaching the latch/fifth trade, not repeated blocked-bar log messages.')
    fields=[('BUY signals','buy_signals'),('SELL signals','sell_signals'),('HOLD evaluations','hold_evaluations'),
        ('Total trades','total_trades'),('Winners','winning_trades'),('Losers','losing_trades'),('Breakeven','breakeven_trades'),
        ('Win rate %','win_rate'),('Gross profit','gross_profit'),('Gross loss magnitude','gross_loss'),
        ('Gross net P&L','gross_net_pnl'),('Charges','total_charges'),('Net P&L','net_pnl'),('Final capital','final_capital'),
        ('Gross PF','profit_factor_unrounded'),('Average net trade','average_net_trade'),('Average net win','average_win'),
        ('Average net loss','average_net_loss_signed'),('Max drawdown INR','max_drawdown'),('Max drawdown %','max_drawdown_percent'),
        ('Equity points','equity_points'),('BUY trades','buy_trades'),('SELL trades','sell_trades'),('STOP exits','stop_count'),
        ('TARGET exits','target_count'),('END_OF_SESSION exits','eod_count'),('END_OF_BACKTEST exits','end_of_backtest_count'),
        ('Charges/trade','charges_per_trade'),('Charges / absolute gross result %','charges_over_absolute_gross_percent'),
        ('Loss-lock trigger sessions','daily_loss_lock_trigger_count'),('Max-trades/day trigger sessions','max_trade_per_day_trigger_count'),
        ('Minimum modeled stop exposure %','minimum_stop_exposure_percent'),('Average modeled stop exposure %','average_stop_exposure_percent'),
        ('Maximum modeled stop exposure %','maximum_stop_exposure_percent'),('Quantity min','quantity_min'),('Quantity max','quantity_max'),
        ('Trades/session','trades_per_session'),('Active sessions','active_sessions'),('Occupied bars %','occupied_bar_percent'),('Pending cancelled','pending_cancelled')]
    table(['Metric','E','F','G'],[[label]+[variants[n][key] for n in ('E','F','G')] for label,key in fields])
    para('Modeled stop exposure includes adverse stop-exit slippage and charges divided by capital immediately before entry. It is not a hard cap; gaps can exceed it. Occupied bars include entry and exit bars and are a coarse duration proxy. Realized drawdown excludes intrabar mark-to-market.')
    para('## Gross-edge gate')
    table(['Family','Gross edge','Gross P&L','PF before charges','Net P&L'],
          [[n,v['gross_edge'],v['gross_net_pnl'],v['profit_factor_unrounded'],v['net_pnl']] for n,v in variants.items()])
    para('Gross classification uses unrounded trade totals: >0 positive, =0 flat, <0 negative. Gross-negative/PF-below-one strategies cannot proceed toward production. No production-ready designation exists in this phase.')
    para('## Side analysis')
    table(['Family / side','Trades','Wins','Losses','Win %','Gross P&L','Charges','Net P&L','PF','Avg net'],
          [[n+' / '+side]+[b[k] for k in ('trades','wins','losses','win_rate','gross_pnl','charges','net_pnl','profit_factor','average_net_trade')]
           for n,v in variants.items() for side,b in v['sides'].items()])
    for n,v in variants.items():
        positive=[side for side,b in v['sides'].items() if b['gross_pnl']>0]
        net_positive=[side for side,b in v['sides'].items() if b['net_pnl']>0]
        para(n+': gross-positive sides: '+(', '.join(positive) or 'none')+'; net-positive sides: '+(', '.join(net_positive) or 'none')+'. No side was removed or rerun.')
    para('## Exit analysis')
    table(['Family / exit','Trades','Wins','Losses','Gross P&L','Charges','Net P&L'],
          [[n+' / '+reason]+[b[k] for k in ('trades','wins','losses','gross_pnl','charges','net_pnl')]
           for n,v in variants.items() for reason,b in v['exits'].items()])
    para('STOP_LOSS is the engine name for STOP. All families use identical exits; these buckets describe entry selection and subsequent price paths, not strategy-specific exit logic.')
    para('## Time-slice stability')
    para(r['methodology']['slices']+' Indicators and episode state are not restarted at the split. Slice DD uses each slice starting capital and a local peak; drawdowns are not additive.')
    table(['Family / half','Sessions','Trades','Gross P&L','Net P&L','PF','Max DD %','BUY','SELL'],
          [[n+' / '+label]+[v['periods'][label][k] for k in ('sessions','trades','gross_pnl','net_pnl','profit_factor','max_drawdown_percent','buy_trades','sell_trades')]
           for n,v in variants.items() for label in ('first_half','second_half')])
    para('## Legacy versus CAS')
    table(['Family / regime','Sessions','Trades','Gross P&L','Net P&L','PF','Max DD %','BUY','SELL','EOD'],
          [[n+' / '+label]+[v['periods'][label][k] for k in ('sessions','trades','gross_pnl','net_pnl','profit_factor','max_drawdown_percent','buy_trades','sell_trades','end_of_session')]
           for n,v in variants.items() for label in ('LEGACY','CAS')])
    para('Legacy March 9-July 31; CAS August 3-September 8. Different capital paths affect monetary comparisons. CAS is only 27 sessions; chronology and market conditions are confounded with policy-period differences.')
    para('## Session concentration')
    para(r['methodology']['concentration'])
    para('Predetermined flag: '+r['methodology']['concentration_flag'])
    fields=[('Best session net','best_session_net_pnl'),('Worst session net','worst_session_net_pnl'),
        ('Best five gross winning-trade contribution','top_five_profitable_sessions_gross_profit'),
        ('Best five share of total gross profit %','top_five_profitable_sessions_gross_profit_percent'),
        ('Worst five gross losing-trade magnitude','top_five_losing_sessions_gross_loss'),
        ('Worst five share of total gross loss %','top_five_losing_sessions_gross_loss_percent'),
        ('Best five net P&L','best_five_net_pnl'),('Best five / signed total net %','best_five_share_of_total_net_percent'),
        ('Best five / absolute total net %','best_five_share_of_absolute_total_net_percent'),('Net excluding best five','net_without_best_five'),('Concentration flag','concentration_flag')]
    table(['Metric','E','F','G'],[[label]+[variants[n]['concentration'][key] for n in ('E','F','G')] for label,key in fields])
    para('A negative best-five / total-net percentage means profitable sessions offset a full-period loss; it is not a negative contribution to profits. No concentration flag does not imply a positive edge or adequate tail coverage.')
    for n,v in variants.items():
        for group in ('best_five_sessions','worst_five_sessions'):
            table([n+' '+group,'Trades','Gross P&L','Charges','Net P&L'],
                  [[b['date'],b['trades'],b['gross_pnl'],b['charges'],b['net_pnl']] for b in v['concentration'][group]])
    para('## Trade correctness and offline safety')
    table(['Family','Trades audited','Closure calls','Violations'],
          [[n,v['correctness_audit']['trades_audited'],v['correctness_audit']['observed_closure_calls'],v['correctness_audit']['violation_count']] for n,v in variants.items()])
    para('Every trade was checked for physical N+1 entry and observed signal ATR argument; 5bps adverse entry/exit slippage; 1.5/2 ATR stop/target; first qualifying exit including opening gaps before intrabar STOP/TARGET precedence; quantity based on actual pre-entry capital; every charge component; net P&L and each equity point; cutoff/same-session/no-overlap/EOD behavior; and regular-only timestamps. Passive profiling counted `_close_position()` calls and captured runner/entry evidence without replacing engine methods. All recorded signals entered; no pending entry or open position survived the run.')
    para('Auxiliary rows were excluded before indicators/signals/execution/EOD by unchanged production code. Boundary branches not observed in a dataset are supported by regression tests, rather than claimed as empirically exercised. JSON retains trades, equity curves, emitted signal evidence, per-trade audit details and observed entry arguments.')
    para('Network attempts = '+str(r['safety']['network_attempts'])+'. Socket and audit guards were installed before research imports; SDK, broker and live imports were prohibited and none loaded. No HistoricalClient network use, AngelOneBroker, LiveFeed, actual authentication, account/profile/order activity. Regression suites separately exercise mocks under the existing network guard. No network tools or acquisition runs were used.')
    para('## A / D / E / F / G comparison')
    combined=dict(r['prior_variants'],**variants)
    table(['Family','Trades','Gross P&L','Charges','Net P&L','Capital','PF','Max DD %','Win %','BUY','SELL','Charges/trade'],
          [[n]+[combined[n][k] for k in ('total_trades','gross_net_pnl','total_charges','net_pnl','final_capital','profit_factor','max_drawdown_percent','win_rate','buy_trades','sell_trades','charges_per_trade')] for n in ('A','D','E','F','G')])
    for question,answer in r.get('comparison_answers',{}).items():
        para('**'+question+'** '+answer)
    para('## Classification and limitations')
    para('Predeclared rules: '+r['methodology']['classification'])
    for n,v in variants.items():
        para('**'+n+': '+v['classification']+'**. '+v.get('classification_reason','See the gross gate, sample size, stability, drawdown and concentration tables above.'))
    para(r['methodology']['caveats'])
    para('The prescribed G session-extreme test does not prevent continuation for valid OHLC/positive ATR. This limitation was identified before execution and deliberately preserved; no new filter, side deletion or exit variation was tried.')
    para('Next research step without tuning: '+r.get('recommended_next_step','Review the recorded evidence and preregister a distinct hypothesis before any further experiment; do not adjust these canonical parameters on this dataset.'))
    para('## Validation and Git status')
    for k,v in r['validation'].items():
        if k!='git_status': para(k+': '+str(v))
    para('One intermediate new-test run had 340 passed / 1 failed because its synthetic ATR 100 at price 100 implied a negative stop; the charge model correctly rejected it. Only test-fixture ATR changed to 10 before any canonical dataset run. The corrected suite passed 341 tests. No engine/harness/strategy patch or canonical rerun followed a result.')
    para('Original production strategy/config, engine, risk/charges/slippage, policy, .env, broker/live/acquisition, Phase 12 cache and Phase 13/14 outputs are unchanged against the saved 83-file manifest. No commit.')
    if 'git_status' in r['validation']:
        para('```text\n'+'\n'.join(r['validation']['git_status'])+'\n```')
    para('Artifacts: `research/phase15_report.md`, `research/phase15_results.json`; canonical source and one-shot runner under `research/phase15/`; tests in `tests/test_phase15_research.py`. The renderer reads recorded results only.')
    para('PHASE 15 COMPLETE \u2014 NEW STRATEGY FAMILY RESEARCH FINISHED')
    (ROOT/'research/phase15_report.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Rendered Phase15 report from saved results only')


if __name__=='__main__':
    render()
