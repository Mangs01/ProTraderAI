"""Render the saved Phase 16 measurements; no simulation."""
import json
from pathlib import Path
from research.phase16_forensics import ROOT, H, stats, performance, guard

METHOD = {
 'universe':'All 482 canonical emitted entries, E=92 F=142 G=248; every saved signal executed. No filtering, strategy generation, tuning or engine calls.',
 'source':'Phase15 signal_events, trades and correctness_audit.details.signal_atr loaded. Existing causal Indicators functions reconstruct signal context only, after regular-bar filtering.',
 'reference':'Signal N is a completed candle labelled by its start. Execution at physical N+1 open equals signal completion time. A references signal close; B references raw N+1 open. Slipped fill retained separately.',
 'forward':'H=1,2,3,6,12 uses close at entry_index+H-1 = signal_index+H. The entry candle is the first completed future candle. Continue measurement after actual exit, never after regular session ends; unavailable = null. Approximate elapsed horizons 5/10/15/30/60 minutes.',
 'direction':'BUY=future/reference-1; SELL=reference/future-1. Percent tables multiply by 100. ATR moves use (future-reference)/signal_ATR for BUY and (reference-future)/signal_ATR for SELL; this is price-linear, unlike reciprocal SELL percentage.',
 'statistics':'Sample standard deviation ddof=1; linear quantiles; zero return is not positive. Null for unavailable statistics or undefined PF (no gross losses). N always reports actual availability. Net pnl >0 winner, <0 loser; all zero/breakeven groups retained in JSON.',
 'excursions':'Raw entry reference; zero floor. Confirmed lower bound uses all entry-to-pre-exit candles plus exit open and recorded raw exit. EOD includes full final candle. Upper bound additionally uses entire exit-candle high/low, which may occur after fill. Exact pre-exit extrema and ordering are unknowable from OHLC; bounds replace invented precision. In gap exits, confirmed is exact; upper deliberately remains a loose candle bound.',
 'geometry':'Actual levels are around SLIPPED entry: stop 1.5 ATR and target 2 ATR, RR=4/3. Raw-reference threshold diagnostic is separately labelled and censored at actual exit; it is not an alternative backtest. Gap precedes range; STOP wins unresolved same-bar collisions. Full exit-candle raw-threshold probabilities are candle proxies; confirmed-path probabilities and unresolved counts are also provided.',
 'duration':'bars = exit_index-entry_index; minutes = bar-start timestamp difference = bars*5, not precise fill elapsed time. Executable candles = bars+1, so same-entry-candle exit=1 candle, 0 bar-start minutes. Within-N probabilities use candles<=N (within N*5 minutes upper bound). Intrabar actual duration lies between reported minutes and minutes+5; gap exit is at lower bound; EOD at upper bound.',
 'immediate':'Entry candle high/low vs raw entry: favorable/adverse/BOTH/neither. BOTH asserts no sequence. Next-bar close return equals raw-open 1-bar diagnostic, independent of exit.',
 'characteristics':'Only family-used frozen fields: RSI, ATR, ATR/close%, VWAP distance, signal clock minute; E additionally EMA20/50 distances and spread; F Volume/VolumeSMA20 and side-relative OR boundary distance; G EMA20 distance. Distances price units, ATR/close percent, time minutes since midnight; no new indicators. Winner/loser comparison is descriptive, with side splits in JSON.',
 'time_buckets':'Buckets use physical entry time, final bucket ends at regime entry limit. Six entries predate 09:30 (E4, G2); retained in OUTSIDE_PREDEFINED rather than discarded or misassigned. Exact signal cutoffs LEGACY 15:05, CAS 15:00; corresponding entry limits 15:10 and 15:05.',
 'volatility':'Pooled complete 482-trade sample; one linear quantile computation at 1/3 and 2/3; <= lower LOW, <= upper MID, else HIGH. Labels are post-hoc and never signal inputs.',
 'cost':'All saved charges used at full precision. Gross pnl includes slippage and excludes explicit fees. Raw-price pnl minus quantity*(entry_slippage+exit_slippage) equals saved gross. Raw-price pnl holds actual fills/exit levels/quantity/path fixed: not a zero-slippage strategy counterfactual. Ratios use saved fill turnover and absolute saved gross.',
 'safety':'Diagnostic process blocks socket/DNS/process calls and broker/live/SmartAPI imports before project imports. Zero attempts. Regression suite separately has intentional caught network-denial probes and fake historical transport/auth tests; zero external network activity, not zero synthetic test invocations.'
}
LIMITATIONS=[
 'Single instrument and 125 represented sessions; non-independent, overlapping forward windows and many descriptive comparisons. Positive sample means are not established directional alpha or tradability.',
 'Exit-conditioned excursions are censored and subject to exit-bar sequence ambiguity. Target-trade small MAE is also a consequence of stop selection; it cannot justify a different stop.',
 'Horizon availability changes near session end; 12-bar groups differ from 1-bar groups. No overnight carrying or imputation.',
 'Actual intrabar timestamps are unavailable. Duration minutes are bar-start differences with a five-minute interval, not exact fill times.',
 'CAS is only 27 sessions and occurs later chronologically; capital/quantity also decline. Regime pnl differences are not causal effects.',
 'Costs dominate the accounting bridge but gross after slippage is already negative. Positive raw-price accounting for E/F does not establish a profitable no-slippage strategy because actual exit levels and trade selection depended on slipped entries.',
 'No optimized thresholds, alternative rules or versions tested; every bad bucket and losing observation remains included.'
]
CONCLUSIONS={
 'shared_failure':'Weak directional expectancy relative to execution friction; frequent modest favorable excursions are not sustained into sufficient realized reward.',
 'directional_alpha':'Positive descriptive means exist, most clearly F SELL (all five means positive; 12-bar 67.61% positive). F BUY has negative means/medians at every horizon. G both-side means are negative at every horizon. E changes sign. No independent or economically sufficient alpha established.',
 'stops':'Confirmed >=0.5 ATR before STOP: E59.62%, F51.19%, G51.23%; >=1 ATR only 30.77%,27.38%,29.01%. Within first candle: 3.85%,10.71%,20.37%. Many modest reversals, not predominantly immediate failures; substantial reversals are a minority.',
 'targets':'Actual target rates 33.70%,35.21%,31.05%; median confirmed MFE 1.41,1.47,1.08 ATR. Targets are not impossible, but target reach is insufficient. Censoring and weak forward means prevent concluding target/stop geometry is the root cause.',
 'costs':'Costs are a primary arithmetic contributor, not a small secondary effect: combined slippage+fees about 0.83,0.76,0.86 ATR/trade. Explicit fees are an additional loss after negative saved gross. Foundational entry edge is weak; COST_DRAG_DOMINANT is not assigned solely from fixed-path raw-price accounting.',
 'buy_sell':'BUY is worse in realized gross PF and average net trade for all three. SELL remains net-negative. Forward SELL superiority is not consistent: G SELL mean directional returns are worse than BUY at all horizons; E mixed. F has strongest direction-specific descriptive contrast.',
 'time':'Losses concentrate differently: E12:30-13:29 ~48.7% of net loss; F first two buckets ~82.3%; G11:30-13:29 ~49.6%. Sparse positive E/F buckets do not show a shared time-of-day remedy or causal explanation.',
 'volatility':'All nine family-by-tertile groups are gross and net negative. G LOW is particularly weak, but no common profitable regime or large-share causal explanation is established.',
 'cas':'E/G CAS per-trade losses and PF improve; F worsens. All six legacy/CAS gross and net results remain negative. Small and chronological/confounded samples; no common material structural improvement established.'
}
CLASS={
 'E':dict(label='MIXED_FAILURE',evidence='Weak/sign-changing forward edge plus reversal after modest initial movement and material costs. >=0.5 ATR before stop 59.62%, >=1.5 only21.15%; raw-open mean ATR at 3/6/12 bars 0.029/-0.093/0.176 vs 0.828 ATR average costs. No geometry mismatch demonstrated.'),
 'F':dict(label='MIXED_FAILURE',evidence='Direction contrast (BUY wrong-direction descriptively; SELL small positive means), pooled weak entry edge, and material costs. SELL12-bar mean0.252 ATR vs pooled average cost0.758 ATR. Both realized sides negative; no direction removal or tuning.'),
 'G':dict(label='ENTRY_EDGE_WEAK',evidence='Both sides negative mean returns at every horizon; pooled ATR means -0.039,-0.067,-0.061,-0.162,-0.186. Medians/frequencies are mixed, so systematic wrong direction is not claimed. Costs amplify already negative raw-price accounting; modest stop reversals coexist.')
}
DECISION=dict(code='A',direction='NEW ENTRY HYPOTHESIS REQUIRED',evidence='Across families the fixed-horizon directional magnitudes are weak relative to measured friction; G lacks mean edge and E is unstable. F SELL is a descriptive pocket but insufficient to choose direction removal or exit redesign. No robust positive pre-exit expectancy supports prioritizing stop/target research.',future_hypotheses=['A future preregistered entry hypothesis must demonstrate directional magnitude relative to unchanged execution costs on independent data.','F direction asymmetry and modest pre-stop favorable movement may be recorded as observations for that future protocol; no rule, parameter or filter is proposed.'])

def main():
 guard()
 from research.phase16_forensics import first_touch,excursions
 import pandas as pd
 from utils.session_policy import FiveMinuteSessionPolicy
 from utils.time_utils import normalize_timestamp_series
 from research.phase16_forensics import regular_only
 p=ROOT/'research/phase16_results.json'; r=json.loads(p.read_text())
 r.update(methodology=METHOD,limitations=LIMITATIONS,common_failure=CONCLUSIONS,decision=DECISION)
 df=pd.read_csv(ROOT/r['dataset']['csv_path']);df.datetime=normalize_timestamp_series(df.datetime,'Asia/Kolkata');df=regular_only(df,FiveMinuteSessionPolicy(cas_eligible=True))
 for e in r['events']:
  i,x=e['entry_index'],e['exit_index']; b=df.iloc[i:x+1].copy()
  if e['reason']!='END_OF_SESSION':
   b.loc[x,'high']=max(float(b.loc[x,'open']),e['raw_exit_price'])
   b.loc[x,'low']=min(float(b.loc[x,'open']),e['raw_exit_price'])
  e['touch']['raw_confirmed']=first_touch(b,e['side'],e['raw_next_bar_open'],e['signal_atr'])
 for f,v in r['families'].items():
  v['classification']=CLASS[f]
  rows=[e for e in r['events'] if e['family']==f]
  v['raw_threshold_confirmed']={k:sum(e['touch']['raw_confirmed']['outcome']==k for e in rows) for k in ('STOP','TARGET','NEITHER')}
  v['characteristics_by_side']={side:{outcome:{k:stats([e['characteristics'][k] for e in rows if e['side']==side and e['outcome']==outcome]) for k in rows[0]['characteristics']} for outcome in ('WINNER','LOSER')} for side in ('BUY','SELL')}
 r['audit']['raw_threshold_exit_censoring']='Confirmed-path counts distinguished from full exit-candle proxies; no post-exit range asserted as pre-exit fact.'
 p.write_text(json.dumps(r,indent=2,allow_nan=False,default=lambda x:x.item())+'\n',encoding='utf-8')
 lines=['# Phase 16 — Entry edge forensics','', '**Decision: A — NEW ENTRY HYPOTHESIS REQUIRED.** Diagnostic only; no tuning, strategy rerun, production or engine changes.','']
 def text(s): lines.extend([s,''])
 def table(headers,rows):
  def fmt(x): return 'NA' if x is None else f'{x:.4f}' if isinstance(x,float) else str(x)
  lines.append('| '+' | '.join(headers)+' |');lines.append('| '+' | '.join(['---']*len(headers))+' |')
  lines.extend('| '+' | '.join(fmt(x) for x in row)+' |' for row in rows);lines.append('')
 text('## Integrity, event source and methodology')
 text(f"Dataset `{r['dataset']['csv_path']}`; SHA256 `{r['dataset']['csv_sha256']}`. Metadata SHA256 `{r['dataset']['metadata_sha256']}`. Phase15 JSON SHA256 `{r['phase15_results_sha256']}`. Both exact requested hashes verified; 9,309 rows, 9,294 regular, 15 CAS auxiliary excluded, 125 sessions (98 LEGACY / 27 CAS). 92 frozen file hashes verified before and after diagnostics.")
 text(r['event_source'])
 for k,val in METHOD.items(): text(f'**{k}:** {val}')
 text('## Samples and saved outcomes')
 table(['Family','Side/group','N','Gross INR','Net INR','Gross PF','Net win %'],[[f,k,*[g['performance'][m] for m in ('trades','gross_pnl','net_pnl','pf','win_rate')]] for f,v in r['families'].items() for k,g in v['groups'].items()])
 text('## Fixed forward returns and ATR units')
 text('All statistics use every available observation. Both reference prices shown. Signal-close forward measurement is not an executable fill assumption. Std is sample standard deviation. Full winner/loser and exit-conditioned horizon tables are in JSON, alongside all event records.')
 for f,v in r['families'].items():
  for ref in ('signal_close','raw_open'):
   text(f'### {f}: {ref}')
   table(['Side','H','N','Mean %','Median %','Std %','Positive %','p25 %','p75 %','Mean ATR','Median ATR','p25 ATR','p75 ATR'],[[side,h,*[v['groups'][side]['forward'][ref][str(h)]['return_pct'][k] for k in ('n','mean','median','std','positive_pct','p25','p75')],*[v['groups'][side]['forward'][ref][str(h)]['atr'][k] for k in ('mean','median','p25','p75')]] for side in ('ALL','BUY','SELL') for h in H])
 text('## MFE / MAE bounds before recorded exit')
 text('Confirmed is a lower bound, candle_upper is a loose upper bound. Neither should be represented as exact intrabar extrema. All price/percentage/ATR distributions are retained in JSON.')
 for bound in ('confirmed','candle_upper'):
  text(f'### {bound}')
  table(['Family','Side','Mean MFE ATR','Median MFE ATR','Mean MAE ATR','Median MAE ATR','MFE>=.5 %','>=1 %','>=1.5 %','>=2 %','MAE>=.5 %','>=1 %','>=1.5 %'],[[f,side,*[v['groups'][side]['excursions'][bound][k][s] for k,s in [('mfe_atr','mean'),('mfe_atr','median'),('mae_atr','mean'),('mae_atr','median')]],*v['groups'][side]['excursions'][bound]['mfe_reach_pct'].values(),*v['groups'][side]['excursions'][bound]['mae_reach_pct'].values()] for f,v in r['families'].items() for side in ('ALL','BUY','SELL')])
 for name,title,thresholds in [('stop_forensics','STOP favorable excursion',('.25','.5','1','1.5','2')),('target_forensics','TARGET adverse excursion',('.25','.5','1','1.5'))]:
  text('## '+title)
  table(['Family','Side','Bound','N','Mean ATR','Median ATR',*[f'>={t} ATR %' for t in thresholds]],[[f,side,b,v['groups'][side][name]['count'],v['groups'][side][name][b]['stats']['mean'],v['groups'][side][name][b]['stats']['median'],*v['groups'][side][name][b]['reach_pct'].values()] for f,v in r['families'].items() for side in ('ALL','BUY','SELL') for b in ('confirmed','candle_upper')])
 text('## Time to outcome')
 for unit in ('bars','minutes'):
  text('### '+unit+' (bar-start convention)')
  table(['Family','Group','N','Mean','Median','p25','p75','Max'],[[f,k,*[v['groups'][k]['duration'][unit][s] for s in ('n','mean','median','p25','p75','max')]] for f,v in r['families'].items() for k in ('ALL','STOP_LOSS','TARGET','END_OF_SESSION','BUY','SELL')])
 table(['Family','Exit','Within1 candle %','Within2 %','Within3 %','Within6 %','Within12 %'],[[f,reason,*[v['groups']['ALL']['exit_within_candles_pct'][reason].get(str(h)) for h in H]] for f,v in r['families'].items() for reason in ('STOP_LOSS','TARGET')])
 text('## Immediate entry-candle quality')
 table(['Family','Side','Favorable N/%','Adverse N/%','BOTH N/%','Neither N/%','Next close mean %','Next close median %'],[[f,side,*[str(v['groups'][side]['immediate'][k]['count'])+'/'+str(round(v['groups'][side]['immediate'][k]['pct'],2)) for k in ('FAVORABLE','ADVERSE','BOTH','NEITHER')],*[v['groups'][side]['forward']['raw_open']['1']['return_pct'][k] for k in ('mean','median')]] for f,v in r['families'].items() for side in ('BUY','SELL')])
 text('## Stop versus target geometry')
 table(['Family','Mean stop price','Mean target price','Mean stop ATR','Mean target ATR','Mean RR'],[[f,*[v['groups']['ALL']['geometry']['distances'][k]['mean'] for k in ('stop_distance','target_distance','stop_atr','target_atr','reward_risk')]] for f,v in r['families'].items()])
 table(['Family','Reference','P target first %','P stop first %','Neither/censored %','Ambiguous collisions'],[[f,ref,*[v['groups']['ALL']['geometry'][ref][k] for k in ('target_first_pct','stop_first_pct','neither_pct','collisions')]] for f,v in r['families'].items() for ref in ('slipped_entry','raw_open')])
 text('Slipped-entry rows reproduce actual engine thresholds and exits. Raw-open rows above are full exit-candle proxies and can include post-exit range; do not interpret them as exact pre-exit probabilities. The conservative confirmed-path counts below establish reaches using prior candles and known exit open/fill only. NEITHER is censored/unresolved, not proof a threshold would never be hit. No path is extended beyond recorded exit.')
 table(['Family','N','Confirmed target-first N / %','Confirmed stop-first N / %','Unresolved/neither N / %'],[[f,len([e for e in r['events'] if e['family']==f]),*[str(v['raw_threshold_confirmed'][k])+' / '+str(round(100*v['raw_threshold_confirmed'][k]/v['groups']['ALL']['performance']['trades'],4)) for k in ('TARGET','STOP','NEITHER')]] for f,v in r['families'].items()])
 text('## Cost attribution')
 keys=('raw_price_pnl','slippage_drag','gross_pnl','brokerage','stt','stamp_duty','transaction_charges','sebi_charges','ipft','gst','charges','pnl','gross_turnover','charges_over_turnover','charges_over_absolute_gross','average_charge','gross_average','net_average')
 table(['Metric (INR unless ratio)','E','F','G'],[[k,*[r['families'][f]['costs'][k] for f in ('E','F','G')]] for k in keys])
 table(['Family','Mean combined cost ATR','Median combined cost ATR'],[[f,v['costs']['per_trade_cost_atr']['mean'],v['costs']['per_trade_cost_atr']['median']] for f,v in r['families'].items()])
 text('Cost ratios above are fractions, not percentages. Slippage attribution is exact on saved fixed trades; no alternative execution assumptions or strategy reruns. Raw-price pnl is not a zero-slippage backtest.')
 text('## Entry edge before exits')
 table(['Family','Side','Positive mean H','Positive median H','Positive-frequency >50% H','All horizon means positive?'],[[f,side,','.join(str(h) for h in H if v['groups'][side]['forward']['raw_open'][str(h)]['return_pct']['mean']>0) or 'none',','.join(str(h) for h in H if v['groups'][side]['forward']['raw_open'][str(h)]['return_pct']['median']>0) or 'none',','.join(str(h) for h in H if v['groups'][side]['forward']['raw_open'][str(h)]['return_pct']['positive_pct']>50) or 'none',all(v['groups'][side]['forward']['raw_open'][str(h)]['return_pct']['mean']>0 for h in H)] for f,v in r['families'].items() for side in ('BUY','SELL')])
 text(CONCLUSIONS['directional_alpha']+' Positive magnitudes are small relative to measured actual round-trip costs; forward horizons are descriptive, not new exit rules or tradable strategies. ATR means can differ in sign from percent means due to volatility weighting.')
 text('## Winner versus loser signal characteristics')
 table(['Family','Outcome','Field','N','Mean','Median','p25','p75'],[[f,outcome,field,*[s[k] for k in ('n','mean','median','p25','p75')]] for f,v in r['families'].items() for outcome,cs in v['characteristics'].items() for field,s in cs.items()])
 text('Winners versus losers have median signal ATR E 2.057/1.911, F 2.186/2.221, G 2.291/2.038. E median signal times are 12:50/13:20; F 11:30/11:00; G 10:50/11:32:30. F/G pooled RSI differences strongly mix BUY and SELL, so they do not establish an RSI effect. These are outcome-conditioned descriptions, not threshold discovery. Side-specific descriptive distributions are also in JSON to expose direction mixing; no indicator or value is proposed as a filter.')
 for key,title in [('time_of_day','Time of day'),('volatility','Volatility tertiles')]:
  text('## '+title)
  if key=='volatility': text(str(r['volatility']))
  table(['Family','Bucket','N','Gross INR','Net INR','Gross PF','Win %','Avg net INR'],[[f,k,*[s[m] for m in ('trades','gross_pnl','net_pnl','pf','win_rate','average_net_trade')]] for f,v in r['families'].items() for k,s in v[key].items()])
  text(CONCLUSIONS['time' if key=='time_of_day' else 'volatility'])
 text('## LEGACY / CAS')
 table(['Family','Regime','N','3bar N','3bar mean %','3bar median %','6bar N','6bar mean %','6bar median %','Median MFE ATR lower','Median MAE ATR lower','STOP %','TARGET %','Gross INR','Net INR'],[[f,k,g['performance']['trades'],*[g['forward']['raw_open'][h]['return_pct'][s] for h in ('3','6') for s in ('n','mean','median')],g['excursions']['confirmed']['mfe_atr']['median'],g['excursions']['confirmed']['mae_atr']['median'],g['geometry']['slipped_entry']['stop_first_pct'],g['geometry']['slipped_entry']['target_first_pct'],g['performance']['gross_pnl'],g['performance']['net_pnl']] for f,v in r['families'].items() for k,g in v['regimes'].items()])
 text(CONCLUSIONS['cas'])
 text('## Failure classifications')
 for f,v in CLASS.items(): text(f"**{f}: {v['label']}.** {v['evidence']}")
 text('## Cross-family common failure')
 for k,v in CONCLUSIONS.items(): text(f'**{k}:** {v}')
 text('## Correctness, leakage and safety audit')
 text('482/482 saved events audited; 0 violations. Signal/event timestamps, physical N+1 open, same session, horizon indexing, signal ATR against unchanged causal ATR14, regular timestamps, cutoffs, no CAS auxiliary input, mirrored direction, saved exit/index reproduction and slippage reconciliation passed. Future bars are used only in measurements; no signal is regenerated or mutated. Existing frozen sources and Phase15 JSON retained. Research network attempts=0; no SmartAPI/broker/live imports, HistoricalClient activity, AngelOneBroker instantiation or real auth/account/profile/order calls. Regression probes/stubs are separately documented in methodology.')
 text('## Limitations and future hypotheses')
 for s in LIMITATIONS: text('- '+s)
 for s in DECISION['future_hypotheses']: text('- '+s)
 text('## Validation and artifacts')
 text('Baseline: 341 passed, 0 failed; 79 Python files compiled; diff check PASS. Final regression: 356 passed, 0 failed in 10.66s (15 new Phase16 tests). Compile: all 82 project Python files PASS, excluding venv/.venv/site-packages/.git. Final git diff --check PASS. All 92 frozen source files and canonical Phase15 JSON remain unchanged. No commit.')
 text('Git status retains pre-existing modifications to broker/angelone.py, config/settings.py and live/live_feed.py, and pre-existing untracked broker/data/research/tests files. Phase16 adds only its two research modules, report, JSON, and tests/test_phase16_forensics.py. The untracked research directory appears as a single Git status entry. No production or engine modifications were made during Phase16.')
 text('Report: `research/phase16_report.md`. JSON: `research/phase16_results.json`, including all 482 event diagnostics and all outcome/side distributions. No duplicate CSV created. Research code: `research/phase16_forensics.py` and `research/phase16_report_builder.py`; tests: `tests/test_phase16_forensics.py`. No commit.')
 text('## Phase 17 decision')
 text('**A — NEW ENTRY HYPOTHESIS REQUIRED.** '+DECISION['evidence'])
 (ROOT/'research/phase16_report.md').write_text('\n'.join(lines),encoding='utf-8')
 print('Report rendered; events preserved; no strategy execution.')
if __name__=='__main__': main()

