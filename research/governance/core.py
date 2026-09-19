from __future__ import annotations
import calendar, hashlib, json, math, os
from datetime import date, datetime
from pathlib import Path
from statistics import median

P22="7a7454e22f9984a8cc36be1b4cc7a9477aa79094c11e605f7474b98d3fb9b67c"
P23="8ffc9f659cae347c1233ee5e09b7a5adc9b863425bb6dd3022587270f325fde3"
ROLES={"STAGE_A_DEVELOPMENT","STAGE_B_SEALED","STAGE_C_SEALED"}
STATES={"PRISTINE","SEALED","OPEN_AUTHORIZED","EXPOSED","CONTAMINATED","INVALID"}
SPLITS={20:(13,7),21:(14,7),22:(15,7),23:(15,8),24:(16,8)}
class GovernanceError(ValueError): pass

def canonical_bytes(v):
    try:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
    except (TypeError,ValueError) as e:raise GovernanceError(f"not canonical JSON: {e}") from e
def content_hash(v):return hashlib.sha256(canonical_bytes(v)).hexdigest()
def file_sha256(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sha(v):return isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v)
def protocols(o):
    if o.get("phase22_protocol_hash")!=P22 or o.get("phase23_protocol_hash")!=P23:raise GovernanceError("protocol mismatch")
def verify_hashes(items):
    for p,h in items.items():
        if not sha(h) or not Path(p).is_file() or file_sha256(p)!=h:raise GovernanceError(f"hash mismatch: {p}")

def validate_manifest(m,required):
    missing=[x for x in required if x not in m]
    if missing:raise GovernanceError(f"missing fields: {missing}")
    protocols(m)
    if m["role"] not in ROLES or m["exposure_status"] not in STATES:raise GovernanceError("invalid role/state")
    if m["role"]!="STAGE_A_DEVELOPMENT" and m["exposure_status"] not in {"SEALED","OPEN_AUTHORIZED","EXPOSED","CONTAMINATED","INVALID"}:raise GovernanceError("held-out not sealed")
    if type(m["canonical_run_count"]) is not int or m["canonical_run_count"] not in (0,1):raise GovernanceError("bad run count")
    if not sha(m["dataset_content_hash"]):raise GovernanceError("bad dataset hash")
    if date.fromisoformat(m["period_start"])>date.fromisoformat(m["period_end"]):raise GovernanceError("period order")
    ids=m["instrument_cohort"]
    if len(ids)!=len(set(ids)):raise GovernanceError("duplicate identity")

TRANS={
"STAGE_A_DEVELOPMENT":{("PRISTINE","OPEN_AUTHORIZED"),("OPEN_AUTHORIZED","EXPOSED")},
"STAGE_B_SEALED":{("PRISTINE","SEALED"),("SEALED","OPEN_AUTHORIZED"),("OPEN_AUTHORIZED","EXPOSED")},
"STAGE_C_SEALED":{("PRISTINE","SEALED"),("SEALED","OPEN_AUTHORIZED"),("OPEN_AUTHORIZED","EXPOSED")}}
def transition(role,old,new):
    if role not in TRANS or old not in STATES or new not in STATES or (old,new) not in TRANS[role]:raise GovernanceError("invalid transition")
    return new

AUTH={"dataset_id","dataset_role","phase22_protocol_hash","phase23_protocol_hash","dataset_content_hash","strategy_spec_hash","authorization_purpose","authorization_timestamp","expected_canonical_run_count"}
def validate_auth(a,m):
    if AUTH-set(a):raise GovernanceError("incomplete authorization")
    protocols(a)
    if (a["dataset_id"],a["dataset_role"],a["dataset_content_hash"])!=(m["dataset_id"],m["role"],m["dataset_content_hash"]):raise GovernanceError("authorization mismatch")
    if not sha(a["strategy_spec_hash"]) or a["expected_canonical_run_count"]!=m["canonical_run_count"]:raise GovernanceError("spec/run mismatch")
    d=datetime.fromisoformat(a["authorization_timestamp"].replace("Z","+00:00"))
    if d.tzinfo is None or not a["authorization_purpose"]:raise GovernanceError("authorization metadata")

def read_permitted(m,a=None,predecessor=None):
    try:
        if m is None:raise GovernanceError("missing manifest")
        protocols(m); role,state=m.get("role"),m.get("exposure_status")
        if role not in ROLES or state not in STATES:raise GovernanceError("unknown role/state")
        if role=="STAGE_A_DEVELOPMENT":
            if state not in {"OPEN_AUTHORIZED","EXPOSED"}:raise GovernanceError("A unreadable")
        else:
            if state not in {"SEALED","AUTHORIZED","EXPOSED"} or a is None:raise GovernanceError("authorization required")
            validate_auth(a,m)
            if role=="STAGE_C_SEALED":
                if not predecessor or not predecessor.get("canonical_run_complete") or not predecessor.get("continuation_passed"):raise GovernanceError("predecessor failed")
                if predecessor.get("strategy_spec_hash")!=a["strategy_spec_hash"]:raise GovernanceError("spec changed")
                protocols(predecessor)
        return True,"PERMITTED"
    except (GovernanceError,KeyError,TypeError,ValueError) as e:return False,str(e)

def expose(m,a,timestamp,predecessor=None):
    ok,why=read_permitted(m,a,predecessor)
    if not ok:raise GovernanceError(why)
    out=dict(m)
    if out["exposure_status"]!="EXPOSED":
        out["prior_sealed_metadata"]={"exposure_status":out["exposure_status"],"first_read_timestamp":out.get("first_read_timestamp")}
        out.update(exposure_status="EXPOSED",first_read_timestamp=timestamp,strategy_spec_hash=a["strategy_spec_hash"])
    return out

def begin_run(path,m,a,predecessor=None):
    ok,why=read_permitted(m,a,predecessor)
    if not ok:raise GovernanceError(why)
    p=Path(path)
    if p.exists() or m["canonical_run_count"]!=0:raise GovernanceError("run unavailable")
    s={"status":"IN_PROGRESS","canonical_run_count":1,"dataset_id":m["dataset_id"],"strategy_spec_hash":a["strategy_spec_hash"]}
    try:
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        with os.fdopen(fd,"wb") as f:f.write(canonical_bytes(s));f.flush();os.fsync(f.fileno())
    except FileExistsError as e:raise GovernanceError("lock exists") from e
    return s
def complete_run(path):
    p=Path(path);s=json.loads(p.read_text())
    if s.get("status")!="IN_PROGRESS" or s.get("canonical_run_count")!=1:raise GovernanceError("interrupted/invalid lock")
    s["status"]="COMPLETE";q=p.with_suffix(p.suffix+".tmp");q.write_bytes(canonical_bytes(s));os.replace(q,p);return s

def split_identities(ids):
    if len(ids) not in SPLITS or len(ids)!=len(set(ids)):raise GovernanceError("20-24 unique identities required")
    o=sorted(ids,key=lambda x:hashlib.sha256(f"{P23}:{x}".encode()).hexdigest());n=SPLITS[len(ids)][0]
    return o[:n],o[n:]

def shift(d,n):
    y,m=divmod(d.year*12+d.month-1+n,12);return date(y,m+1,min(d.day,calendar.monthrange(y,m+1)[1]))
def periods(T,sessions):
    s=sorted(set(sessions))
    if T not in s:raise GovernanceError("terminal absent")
    first=lambda x:next((d for d in s if d>=x),None);last=lambda x:next((d for d in reversed(s) if d<x),None)
    d0,d1,d2=shift(T,-24),shift(T,-12),shift(T,-6);out={"A":(first(d0),last(d1)),"B":(first(d1),last(d2)),"C":(first(d2),T)}
    if any(None in x or x[0]>x[1] for x in out.values()):raise GovernanceError("boundary absent")
    return out

def select_universe(cs):
    e=[]
    for c in cs:
        v=c.get("traded_values",[])
        if c.get("member") and c.get("series")=="EQ" and c.get("history_sessions",0)>=252 and c.get("identity_clear") and not c.get("unresolved_action") and len(v)==60 and all(type(x) in (int,float) and x>=0 for x in v):
            e.append((float(median(v)),c["isin"],c["symbol"],c["sector"],c["permanent_identity"]))
    e.sort(key=lambda x:(-x[0],x[1],x[2]));out=[];sectors={}
    for _,_,_,sec,i in e:
        if sectors.get(sec,0)>=4:continue
        out.append(i);sectors[sec]=sectors.get(sec,0)+1
        if len(out)==24:break
    if len(out)<20:raise GovernanceError("fewer than 20")
    return out

def aggregate(rows,size,session_open):
    if size not in (6,12):raise GovernanceError("size")
    groups={}
    for r in sorted((x for x in rows if x.get("research_eligible") is True),key=lambda x:x["timestamp"]):
        if r["timestamp"].date()!=session_open.date():raise GovernanceError("cross session")
        n=int((r["timestamp"]-session_open).total_seconds()//300)
        if n<0:raise GovernanceError("before open")
        groups.setdefault(n//size,[]).append(r)
    full=[];res=[]
    for idx,g in sorted(groups.items()):
        expected=[session_open.timestamp()+300*(idx*size+j) for j in range(size)]
        if len(g)==size and [x["timestamp"].timestamp() for x in g]==expected:
            full.append({"timestamp":g[0]["timestamp"],"open":g[0]["open"],"high":max(x["high"] for x in g),"low":min(x["low"] for x in g),"close":g[-1]["close"],"volume":sum(x["volume"] for x in g)})
        else:res.extend(g)
    return full,res

def sample_gate(total,by,n,nv,nw,part,blocks):
    r=[]
    if total<240:r+=["total"]
    for c in ("THIRTY_MINUTE","SIXTY_MINUTE"):
        if by.get(c,0)<120:r+=[c]
    for name,x,b in zip(("overall","visible","withheld"),part,(n,nv,nw)):
        if x<math.ceil(.8*b):r+=[name]
    for i,b in enumerate(blocks):
        if b.get("trades",0)<60:r+=[f"block{i}_trades"]
        if b.get("coverage",0)<.9:r+=[f"block{i}_coverage"]
    return r
def breadth(values,n):
    r=[];v=list(values.values())
    if len(v)<math.ceil(.8*n):r+=["participation"]
    if not v or sum(x>0 for x in v)<math.ceil(.6*len(v)):r+=["positive"]
    if not v or median(v)<=0:r+=["median"]
    p=[max(x,0) for x in v];d=sum(p)
    if d<=0 or max(p,default=0)/d>.25:r+=["concentration"]
    return r
def conditions(c30,c60,vis,held):
    r=[]
    if c30<=0:r+=["30m"]
    if c60<=0:r+=["60m"]
    if (c30+c60)/2<=0:r+=["pooled"]
    for name,g in (("visible",vis),("withheld",held)):
        v=list(g.values())
        if not v or sum(v)/len(v)<=0:r+=[name+"_mean"]
        if not v or median(v)<=0:r+=[name+"_median"]
    return r
def chronology(bs):
    if len(bs)!=3:return ["count"]
    r=[]
    if any(b["trades"]<60 for b in bs):r+=["trades"]
    p=[b["gross_pnl"] for b in bs]
    if sum(x>0 for x in p)<2:r+=["positive"]
    q=[max(x,0) for x in p];d=sum(q)
    if d<=0 or max(q)/d>.6:r+=["concentration"]
    return r
def friction(ts):
    n=sum(t["charges"]+abs(t["slippage"]) for t in ts);d=sum(max(t["gross_pnl"]+abs(t["slippage"]),0) for t in ts)
    return (False,None) if d<=0 else (n/d<=.5,n/d)
def concentration(values,limit):
    p=[max(x,0) for x in values];d=sum(p)
    return (False,None) if d<=0 else (max(p)/d<=limit,max(p)/d)
def pf_dd(gp,gl,dd):
    r=[]
    if gl<=0 or gp/gl<1.10:r+=["pf"]
    if dd>20:r+=["dd"]
    return r
def primary(ts,cohort):
    out={}
    for c in ("THIRTY_MINUTE","SIXTY_MINUTE"):
        ins={}
        for i in cohort:
            v=[t["gross_pnl"]/t["initial_risk"] for t in ts if t["condition"]==c and t["identity"]==i]
            if v:ins[i]=sum(v)/len(v)
        out[c]={"instruments":ins,"expectancy":sum(ins.values())/len(ins) if ins else None}
    vals=[x["expectancy"] for x in out.values() if x["expectancy"] is not None]
    return {"conditions":out,"overall":sum(vals)/2 if len(vals)==2 else None,"zero_trade":[i for i in cohort if not any(t["identity"]==i for t in ts)]}

BOOTSTRAP={"replications":10000,"seed":230023,"confidence":.95,"interval":"percentile","hierarchy":["identity within visible/withheld strata","contiguous trading-day blocks"],"holm_tests":2}
def validate_bootstrap(c):
    if dict(c)!=BOOTSTRAP:raise GovernanceError("bootstrap mismatch")
REQUEST={"permanent_identity","symbol","token","series","source_interval","requested_start","requested_end","chunk_policy","session_policy_binding","retry_policy","rate_limit_policy","raw_destination","metadata_destination"}
def validate_requests(rs):
    ids=set();paths=set()
    for r in rs:
        if REQUEST-set(r):raise GovernanceError("missing request field")
        if not r["permanent_identity"] or r["permanent_identity"] in ids:raise GovernanceError("duplicate identity")
        ids.add(r["permanent_identity"])
        if r["source_interval"]!="FIVE_MINUTE" or r["series"]!="EQ":raise GovernanceError("unsupported")
        if date.fromisoformat(r["requested_start"])>date.fromisoformat(r["requested_end"]):raise GovernanceError("reversed")
        if any(x in str(r).lower() for x in ("/order","placeorder","live/order")):raise GovernanceError("endpoint")
        for k in ("raw_destination","metadata_destination"):
            if r[k] in paths:raise GovernanceError("path collision")
            paths.add(r[k])

