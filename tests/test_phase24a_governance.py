from datetime import date,datetime,timedelta,timezone
import json,math
import pytest
from research.governance.core import *

H="a"*64
REQ=["dataset_id","role","exposure_status","canonical_run_count","dataset_content_hash","period_start","period_end","instrument_cohort","phase22_protocol_hash","phase23_protocol_hash"]
def manifest(role="STAGE_B_SEALED",state="SEALED"):
 return {"dataset_id":"D","role":role,"exposure_status":state,"canonical_run_count":0,"dataset_content_hash":H,"period_start":"2025-01-01","period_end":"2025-06-30","instrument_cohort":["I1"],"phase22_protocol_hash":P22,"phase23_protocol_hash":P23}
def auth(role="STAGE_B_SEALED"):
 return {"dataset_id":"D","dataset_role":role,"phase22_protocol_hash":P22,"phase23_protocol_hash":P23,"dataset_content_hash":H,"strategy_spec_hash":"b"*64,"authorization_purpose":"canonical evaluation","authorization_timestamp":"2026-01-01T00:00:00Z","expected_canonical_run_count":0}

def test_canonical_hash_order_and_rejects_non_json():
 assert canonical_bytes({"b":1,"a":2})==canonical_bytes({"a":2,"b":1})
 assert content_hash({"b":1,"a":2})==content_hash({"a":2,"b":1})
 with pytest.raises(GovernanceError):canonical_bytes({"x":float("nan")})
 with pytest.raises(GovernanceError):canonical_bytes({"x":object()})

def test_protocol_and_manifest_fail_closed():
 validate_manifest(manifest(),REQ)
 for key in ("phase22_protocol_hash","phase23_protocol_hash"):
  m=manifest();m[key]=H
  with pytest.raises(GovernanceError):validate_manifest(m,REQ)
 m=manifest();m.pop("dataset_id")
 with pytest.raises(GovernanceError):validate_manifest(m,REQ)
 m=manifest();m["period_start"]="2026-01-01"
 with pytest.raises(GovernanceError):validate_manifest(m,REQ)
 m=manifest();m["instrument_cohort"]=["X","X"]
 with pytest.raises(GovernanceError):validate_manifest(m,REQ)

def test_transitions_and_no_reseal():
 assert transition("STAGE_B_SEALED","PRISTINE","SEALED")=="SEALED"
 assert transition("STAGE_B_SEALED","SEALED","OPEN_AUTHORIZED")=="OPEN_AUTHORIZED"
 assert transition("STAGE_B_SEALED","OPEN_AUTHORIZED","EXPOSED")=="EXPOSED"
 with pytest.raises(GovernanceError):transition("STAGE_B_SEALED","EXPOSED","SEALED")

def test_authorization_and_sealed_read():
 m=manifest();assert read_permitted(m)[0] is False
 assert read_permitted(m,auth())==(True,"PERMITTED")
 a=auth();a["dataset_id"]="wrong";assert read_permitted(m,a)[0] is False
 a=auth();a["dataset_content_hash"]="c"*64;assert read_permitted(m,a)[0] is False
 assert read_permitted(None,auth())[0] is False
 a_m=manifest("STAGE_A_DEVELOPMENT","OPEN_AUTHORIZED")
 assert read_permitted(a_m)[0] is True

def test_exposure_does_not_increment_run():
 m=expose(manifest(),auth(),"2026-01-01T00:00:00Z")
 assert m["exposure_status"]=="EXPOSED" and m["canonical_run_count"]==0
 assert m["prior_sealed_metadata"]["exposure_status"]=="SEALED" and m["strategy_spec_hash"]=="b"*64

def test_run_lock_atomic_second_and_interrupted(tmp_path):
 p=tmp_path/"lock.json";m=manifest()
 assert begin_run(p,m,auth())["canonical_run_count"]==1
 with pytest.raises(GovernanceError):begin_run(p,m,auth())
 assert complete_run(p)["status"]=="COMPLETE"
 with pytest.raises(GovernanceError):begin_run(p,m,auth())
 q=tmp_path/"bad.json";q.write_text('{"status":"INTERRUPTED","canonical_run_count":1}')
 with pytest.raises(GovernanceError):complete_run(q)

def test_stage_c_predecessor():
 m=manifest("STAGE_C_SEALED");a=auth("STAGE_C_SEALED")
 assert not read_permitted(m,a)[0]
 p={"canonical_run_complete":True,"continuation_passed":True,"strategy_spec_hash":"b"*64,"phase22_protocol_hash":P22,"phase23_protocol_hash":P23}
 assert read_permitted(m,a,p)[0]
 p["continuation_passed"]=False;assert not read_permitted(m,a,p)[0]

def test_file_hash_verification(tmp_path):
 p=tmp_path/"x";p.write_bytes(b"x");verify_hashes({str(p):file_sha256(p)})
 with pytest.raises(GovernanceError):verify_hashes({str(p):H})

@pytest.mark.parametrize("n,counts",list(SPLITS.items()))
def test_split_deterministic(n,counts):
 ids=[f"ID{i:02}" for i in range(n)];a,b=split_identities(ids);c,d=split_identities(list(reversed(ids)))
 assert (a,b)==(c,d) and (len(a),len(b))==counts and set(a).isdisjoint(b)
 with pytest.raises(GovernanceError):split_identities(ids[:-1]+[ids[0]])

def test_periods_leap_and_month_end():
 T=date(2024,2,29);s=[date(2022,2,28)+timedelta(days=i) for i in range((T-date(2022,2,28)).days+1)]
 p=periods(T,s)
 assert p["A"][0]==date(2022,2,28) and p["B"][0]==date(2023,2,28) and p["C"][0]==date(2023,8,29) and p["C"][1]==T
 T2=date(2025,3,31);s2=[date(2023,3,31)+timedelta(days=i) for i in range((T2-date(2023,3,31)).days+1)]
 assert periods(T2,s2)["B"][0]==date(2024,3,31)

def candidates(n=30):
 out=[]
 for i in range(n):
  out.append({"member":True,"series":"EQ","history_sessions":252,"identity_clear":True,"unresolved_action":False,"traded_values":[1000-i]*60,"isin":f"ISIN{i:02}","symbol":f"S{i:02}","sector":f"SEC{i//4}","permanent_identity":f"I{i:02}"})
 return out

def test_universe_selection_exact_shortfall_sector_ties_and_ineligible():
 assert len(select_universe(candidates()))==24
 c=candidates(23);assert len(select_universe(c))==23
 with pytest.raises(GovernanceError):select_universe(candidates(19))
 c=candidates();c[0]["sector"]="ONE";c[1]["sector"]="ONE";c[2]["sector"]="ONE";c[3]["sector"]="ONE";c[4]["sector"]="ONE"
 assert "I04" not in select_universe(c)
 tie=candidates();tie[0]["traded_values"]=tie[1]["traded_values"];assert select_universe(tie).index("I00")<select_universe(tie).index("I01")
 for key,value in (("traded_values",[1]*59),("identity_clear",False),("series","BE"),("history_sessions",251),("unresolved_action",True)):
  c=candidates(24);c[0][key]=value
  selected=select_universe(c);assert len(selected)==23 and "I00" not in selected

def bars(count,start,eligible=True):
 return [{"timestamp":start+timedelta(minutes=5*i),"open":i,"high":i+2,"low":i-1,"close":i+1,"volume":10,"research_eligible":eligible} for i in range(count)]

def test_30_60_aggregation_terminal_residual():
 o=datetime(2026,1,2,9,15);r=bars(75,o)
 b30,x30=aggregate(r,6,o);b60,x60=aggregate(r,12,o)
 assert len(b30)==12 and len(x30)==3 and len(b60)==6 and len(x60)==3
 assert b30[0]["open"]==0 and b30[0]["high"]==7 and b30[0]["low"]==-1 and b30[0]["close"]==6 and b30[0]["volume"]==60

def test_special_session_and_cas_exclusion():
 o=datetime(2025,10,21,13,45);r=bars(12,o)
 full,res=aggregate(r,12,o);assert len(full)==1 and not res
 short=bars(9,o);full,res=aggregate(short,6,o);assert len(full)==1 and len(res)==3
 r=bars(12,o);r[5]["research_eligible"]=False
 full,res=aggregate(r,6,o);assert len(full)==1 and len(res)==5

def test_no_cross_session_and_gap_excluded():
 o=datetime(2026,1,2,9,15);r=bars(6,o);r[-1]["timestamp"]+=timedelta(days=1)
 with pytest.raises(GovernanceError):aggregate(r,6,o)
 r=bars(6,o);r[2]["timestamp"]+=timedelta(minutes=5)
 full,res=aggregate(r,6,o);assert not full and len(res)==6

def test_sample_gate_boundaries_and_reasons():
 blocks=[{"trades":60,"coverage":.9}]*3
 assert sample_gate(240,{"THIRTY_MINUTE":120,"SIXTY_MINUTE":120},24,16,8,(20,13,7),blocks)==[]
 r=sample_gate(239,{"THIRTY_MINUTE":119,"SIXTY_MINUTE":120},24,16,8,(19,12,6),[{"trades":59,"coverage":.89}]*3)
 assert {"total","THIRTY_MINUTE","overall","visible","withheld"}.issubset(r)

def test_breadth_condition_cross_sectional():
 vals={f"I{i}":1 for i in range(20)}
 assert breadth(vals,24)==[]
 vals["I0"]=100;assert "concentration" in breadth(vals,24)
 assert conditions(.1,.2,{"a":.1,"b":.2},{"c":.1,"d":.2})==[]
 assert {"60m","withheld_mean","withheld_median"}.issubset(conditions(.1,-.1,{"a":.1},{"b":-.1}))

def test_chronology_boundary_and_zero():
 assert chronology([{"trades":60,"gross_pnl":60},{"trades":60,"gross_pnl":40},{"trades":60,"gross_pnl":-1}])==[]
 assert "concentration" in chronology([{"trades":60,"gross_pnl":61},{"trades":60,"gross_pnl":39},{"trades":60,"gross_pnl":-1}])
 assert "concentration" in chronology([{"trades":60,"gross_pnl":0}]*3)

def test_friction_and_concentration_boundaries():
 t=[{"charges":25,"slippage":25,"gross_pnl":75}]
 assert friction(t)==(True,.5)
 assert friction([{"charges":1,"slippage":1,"gross_pnl":-3}])==(False,None)
 assert concentration([10]*10,.1)==(True,.1)
 assert concentration([25,25,25,25],.25)==(True,.25)
 assert concentration([0,0],.25)==(False,None)

def test_pf_dd_boundaries_undefined():
 assert pf_dd(110,100,20)==[]
 assert "pf" in pf_dd(109.99,100,20)
 assert "dd" in pf_dd(110,100,20.01)
 assert "pf" in pf_dd(1,0,1)

def test_primary_metric_and_zero_trade():
 ts=[{"condition":"THIRTY_MINUTE","identity":"A","gross_pnl":10,"initial_risk":10},{"condition":"THIRTY_MINUTE","identity":"B","gross_pnl":30,"initial_risk":10},{"condition":"SIXTY_MINUTE","identity":"A","gross_pnl":20,"initial_risk":10}]
 r=primary(ts,["A","B","C"])
 assert r["conditions"]["THIRTY_MINUTE"]["expectancy"]==2 and r["conditions"]["SIXTY_MINUTE"]["expectancy"]==2 and r["overall"]==2 and r["zero_trade"]==["C"]

def test_bootstrap_config_only():
 validate_bootstrap(BOOTSTRAP)
 with pytest.raises(GovernanceError):validate_bootstrap({**BOOTSTRAP,"seed":1})

def request(i="I",raw="raw",meta="meta"):
 return {"permanent_identity":i,"symbol":"S","token":"1","series":"EQ","source_interval":"FIVE_MINUTE","requested_start":"2025-01-01","requested_end":"2025-02-01","chunk_policy":"sessions","session_policy_binding":"hash","retry_policy":"3","rate_limit_policy":"sequential","raw_destination":raw,"metadata_destination":meta}
def test_acquisition_request_validator_negative_paths():
 validate_requests([request()])
 for change in ({"source_interval":"DAY"},{"requested_start":"2026-01-01"},{"raw_destination":"same","metadata_destination":"same"},{"symbol":"/order"}):
  r=request();r.update(change)
  with pytest.raises((GovernanceError,ValueError)):validate_requests([r])
 with pytest.raises(GovernanceError):validate_requests([request(),request()])

