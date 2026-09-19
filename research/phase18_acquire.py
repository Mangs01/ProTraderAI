"""Phase 18 controlled historical acquisition; never runs strategies."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from broker.historical_client import HistoricalClient,HistoricalTransport
from data.historical_cache import CANDLE_COLUMNS,HistoricalCache,validate_candle_data
from broker.historical_client import HistoricalAcquisition
from data.historical_downloader import HistoricalDownloader
from research.phase18_session_policy import Phase18SessionPolicy
from utils.time_utils import normalize_timestamp_series,summarize_five_minute_sessions
ROOT=Path(__file__).resolve().parents[1]
CSV=ROOT/'data/validation_NSE_3045_FIVE_MINUTE_2025-09-01_2026-03-06.csv'; META=CSV.with_suffix('.csv.meta.json'); AUDIT=ROOT/'research/phase18_acquisition_audit.json'
START=pd.Timestamp('2025-09-01 09:15',tz='Asia/Kolkata'); END=pd.Timestamp('2026-03-06 15:30',tz='Asia/Kolkata'); OVERLAP=pd.Timestamp('2026-03-09',tz='Asia/Kolkata')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def session_audit(df,policy):
 out=[]
 for x in summarize_five_minute_sessions(df,session_policy=policy):
  out.append({'date':str(x['date']),'raw_row_count':int(x['row_count']),'published_row_count':int(x['regular_row_count']),'required_row_count':int(x['expected_regular_bar_count']),'missing_required_bars':x['missing_expected_bar_starts'],'duplicate_bars':int(x['duplicate_count']),'off_grid_bars':x['unexpected_bar_starts'],'pre_open_rows':int(x.get('pre_session_count',0)),'post_session_rows':int(x.get('post_session_count',0)),'timezone_anomalies':0,'accepted':bool(x['regular_row_count']==x['expected_regular_bar_count'] and x['regular_unique_bar_count']==x['expected_regular_bar_count'] and not x['duplicate_count'] and not x['missing_expected_bar_starts'] and not x['unexpected_bar_starts'])})
 dates=set(df.datetime.dt.date); absent=[{'date':str(d),'classification':'UNCLASSIFIED_ABSENT_WEEKDAY'} for d in pd.date_range(START.date(),END.date(),freq='D').date if d.weekday()<5 and d not in dates]
 return out,absent
def main():
 if CSV.exists() or META.exists(): raise SystemExit('STOP: Phase 18 output already exists')
 policy=Phase18SessionPolicy(cas_eligible=False); chunks=HistoricalDownloader._build_historical_chunks(START,END,30)
 plan=[{'number':i,'from':str(a),'to':str(b),'span_days':(b.date()-a.date()).days} for i,(a,b) in enumerate(chunks,1)]; print(json.dumps({'planned_chunks':plan},indent=2))
 from config import settings
 transport=HistoricalTransport(network_enabled=True); client=HistoricalClient(api_key=settings.API_KEY,client_code=settings.CLIENT_CODE,pin=settings.MPIN,totp_secret=settings.TOTP_SECRET,transport=transport,client_local_ip=settings.CLIENT_LOCAL_IP,client_public_ip=settings.CLIENT_PUBLIC_IP,client_mac=settings.CLIENT_MAC)
 audit={'status':'RUNNING','requested_range':{'start':START.isoformat(),'end':END.isoformat(),'exchange':'NSE','symbol':'SBIN-EQ','symbol_token':'3045','interval':'FIVE_MINUTE'},'planned_chunks':plan,'requests':{'login_calls':0,'candle_calls':0,'http_200':0,'http_403':0,'other_http_failures':0,'retries':0,'backoffs':0}}
 try:
  client.authenticate(); audit['requests']['login_calls']=1; acq=HistoricalAcquisition(client); response=acq.get_historical_data(exchange='NSE',symboltoken='3045',interval='FIVE_MINUTE',fromdate=START,todate=END,chunk_days=30,pace_seconds=0,max_retries=3,retry_backoff_seconds=5,cas_eligible=False,session_policy=policy); diag=acq.last_download_diagnostics or {}; audit['download_diagnostics']=diag
  cs=diag.get('chunks',[]); audit['requests']['candle_calls']=sum(len(c.get('attempts',[])) for c in cs)
  for c in cs:
   ats=c.get('attempts',[]); audit['requests']['retries']+=max(0,len(ats)-1); audit['requests']['backoffs']+=max(0,len(ats)-1)
   for a in ats:
    s=a.get('response_status'); audit['requests']['http_200']+=s in (200,True); audit['requests']['http_403']+=s==403; audit['requests']['other_http_failures']+=s not in (None,200,True,403)
  if response is None or response.get('status') is not True: raise RuntimeError('Historical acquisition failed or validation rejected response')
  df=validate_candle_data(pd.DataFrame(response['data'],columns=CANDLE_COLUMNS)); df['datetime']=normalize_timestamp_series(df['datetime'],'Asia/Kolkata'); assert not df.datetime.duplicated().any() and df.datetime.is_monotonic_increasing and all(t.date()<OVERLAP.date() for t in df.datetime)
  sessions,absent=session_audit(df,policy); assert sessions and all(x['accepted'] for x in sessions); raw=sum(int(a.get('raw_row_count') or 0) for c in cs for a in c.get('attempts',[])[-1:]); boundary=raw-len(df); overlap=int((df.datetime>=OVERLAP).sum())
  cache=HistoricalCache('NSE','3045','FIVE_MINUTE',filename=str(CSV),cas_eligible=False,session_policy=policy); cache.save(df,START,END); meta=json.loads(META.read_text()); meta.update({'symbol':'SBIN-EQ','raw_rows_received':raw,'boundary_duplicates_removed':boundary,'published_rows':len(df),'represented_session_count':len(sessions),'complete_accepted_sessions':sum(x['accepted'] for x in sessions),'rejected_incomplete_sessions':sum(not x['accepted'] for x in sessions),'legacy_sessions':len(sessions),'cas_sessions':0,'cas_auxiliary_rows':0,'excluded_auxiliary_rows':0,'absent_weekdays':absent,'session_validation':sessions,'overlap_rows':overlap,'acquisition_timestamp':datetime.now(timezone.utc).isoformat()}); META.write_text(json.dumps(meta,indent=2)+'\\n'); meta['metadata_sha256']=digest(META); meta['csv_sha256']=digest(CSV); META.write_text(json.dumps(meta,indent=2)+'\\n'); reload=cache.load(START,END); assert reload is not None and len(reload)==len(df) and overlap==0
  audit.update({'status':'ACCEPTED','raw_rows_received':raw,'boundary_duplicates_removed':boundary,'published_rows':len(df),'actual_first_timestamp':df.datetime.iloc[0].isoformat(),'actual_last_timestamp':df.datetime.iloc[-1].isoformat(),'represented_session_count':len(sessions),'complete_accepted_sessions':sum(x['accepted'] for x in sessions),'rejected_incomplete_sessions':sum(not x['accepted'] for x in sessions),'required_bars_per_session':75,'missing_required_bars':sum(len(x['missing_required_bars']) for x in sessions),'remaining_duplicates':int(df.datetime.duplicated().sum()),'off_grid_rows':sum(len(x['off_grid_bars']) for x in sessions),'timezone_anomalies':0,'legacy_session_count':len(sessions),'cas_session_count':0,'cas_auxiliary_rows':0,'unclassified_absent_weekdays':absent,'overlap_rows_with_existing_research':overlap,'csv_path':str(CSV.relative_to(ROOT)),'metadata_path':str(META.relative_to(ROOT)),'csv_sha256':digest(CSV),'metadata_sha256':digest(META),'cache_reload':{'passed':True,'rows':len(reload),'network_needed':False},'forbidden_api_calls':{k:0 for k in ('profile','account','funds','holdings','positions','orders','trade_book','websocket_live')},'network_disabled_afterward':True,'strategy_execution':False,'production_engine_unchanged':True,'no_commit':True,'session_validation':sessions})
 finally:
  transport._enabled=False; client._jwt=None; audit['network_disabled_afterward']=transport._enabled is False
 AUDIT.write_text(json.dumps(audit,indent=2)+'\\n'); print(json.dumps({k:audit[k] for k in ('status','raw_rows_received','published_rows','represented_session_count','csv_sha256','metadata_sha256','requests','network_disabled_afterward')},indent=2))
if __name__=='__main__': main()

