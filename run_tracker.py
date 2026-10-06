#!/usr/bin/env python3
"""JW U.S. Congregation Tracker v3.3
Reads the collector's data/snapshot.json, classifies U.S. records conservatively,
archives a dated U.S. snapshot, compares it to the prior snapshot, and writes
summary/event files consumed by the dashboard.
"""
import json, math, re, os, shutil
from pathlib import Path
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; SNAP=DATA/'snapshots'; EVENTS=DATA/'events'
RAW=DATA/'snapshot.json'
SNAP.mkdir(parents=True,exist_ok=True); EVENTS.mkdir(parents=True,exist_ok=True)

ENGLISH='bafaf6d8-1e69-47c2-abcb-b3bdfc28eebe'
SPANISH='2cadddaf-80d5-472d-b6d9-48cd4dd17a5b'
STATE_CODES='AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split()
STATE_NAMES=['Alabama','Alaska','Arizona','Arkansas','California','Colorado','Connecticut','Delaware','Florida','Georgia','Hawaii','Idaho','Illinois','Indiana','Iowa','Kansas','Kentucky','Louisiana','Maine','Maryland','Massachusetts','Michigan','Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada','New Hampshire','New Jersey','New Mexico','New York','North Carolina','North Dakota','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina','South Dakota','Tennessee','Texas','Utah','Vermont','Virginia','Washington','West Virginia','Wisconsin','Wyoming','District of Columbia']

MEX_ABBR_RE=re.compile(r'(?:(?:,|\s)B\.C\.S\.?|(?:,|\s)B\.C\.?|(?:,|\s)Son\.?|(?:,|\s)Chih\.?|(?:,|\s)Sin\.?|(?:,\s|\s)Jal\.?|(?:,\s|\s)Nay\.?|(?:,\s|\s)Dgo\.?|(?:,\s|\s)Coah\.?|(?:,\s|\s)Tamps\.?|(?:,\s|\s)N\.L\.?|(?:,\s|\s)Gto\.?|(?:,\s|\s)Qro\.?|(?:,\s|\s)Q\.R\.?|(?:,\s|\s)Yuc\.?|(?:,\s|\s)Oax\.?|(?:,\s|\s)Pue\.?|(?:,\s|\s)Ver\.?|(?:,\s|\s)Gro\.?|(?:,\s|\s)Mich\.?|(?:,\s|\s)Mor\.?|(?:,\s|\s)Tlax\.?|(?:,\s|\s)Hgo\.?|(?:,\s|\s)Chis\.?|(?:,\s|\s)Tab\.?|(?:,\s|\s)Camp\.?|(?:,\s|\s)Zac\.?|(?:,\s|\s)Ags\.?|(?:,\s|\s)Col\.?|(?:,\s|\s)S\.L\.P\.?)',re.I)

CAN_POST=re.compile(r'\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b',re.I)
CAN_PROV=re.compile(r'\b(?:ON|QC|NB|NS|PE|NL|MB|SK|AB|BC|YT|NT|NU|ONTARIO|QUEBEC|NEW BRUNSWICK|NOVA SCOTIA|PRINCE EDWARD ISLAND|NEWFOUNDLAND|MANITOBA|SASKATCHEWAN|ALBERTA|BRITISH COLUMBIA|YUKON|NORTHWEST TERRITORIES|NUNAVUT)\b',re.I)
US_STATE_RE=re.compile(r'\b(?:'+ '|'.join(STATE_CODES) + r')\b',re.I)
US_NAME_RE=re.compile(r'\b(?:'+'|'.join(STATE_NAMES)+r')\b',re.I)
ZIP_RE=re.compile(r'\b\d{5}(?:-\d{4})?\b')

def text(r): return ' '.join(str(r.get(k) or '') for k in ('name','address','city','state'))
def foreign_country(r):
    t=text(r).upper()
    if '(BHS)' in t or 'BAHAMAS' in t: return 'Bahamas'
    if CAN_POST.search(t) or (CAN_PROV.search(t) and not ZIP_RE.search(t)): return 'Canada'
    # Mexican abbreviations are strong evidence when they occur in the address/name;
    # do not use full names like Sonora or California because U.S. place names can match them.
    if MEX_ABBR_RE.search(t): return 'Mexico'
    return None

def classify_us(r, prior_us_ids):
    f=foreign_country(r)
    if f: return False, f, 'explicit_foreign_marker'
    name=str(r.get('name') or '')
    if '(USA)' in name.upper(): return True, 'US', 'name_marked_USA'
    # A U.S. state + U.S. ZIP is useful supporting evidence, but never overrides foreign markers.
    t=text(r)
    if ZIP_RE.search(t) and (US_STATE_RE.search(t) or US_NAME_RE.search(t)):
        return True, 'US', 'us_state_plus_zip'
    if r.get('source_id') in prior_us_ids:
        return True, 'US', 'known_us_congregation'
    return False, 'Uncertain', 'insufficient_country_evidence'

def load_raw():
    if not RAW.exists(): raise SystemExit('Missing data/snapshot.json. Run the collector first.')
    return json.loads(RAW.read_text(encoding='utf-8'))

def prior_files(): return sorted(SNAP.glob('*.json'))
def load_latest():
    fs=prior_files()
    return json.loads(fs[-1].read_text(encoding='utf-8')) if fs else None

def hav(a,b):
    if a is None or b is None: return None
    try: lat1,lon1=float(a.get('latitude')),float(a.get('longitude')); lat2,lon2=float(b.get('latitude')),float(b.get('longitude'))
    except: return None
    p=math.pi/180; x=(lat2-lat1)*p; y=(lon2-lon1)*p
    h=math.sin(x/2)**2+math.cos(lat1*p)*math.cos(lat2*p)*math.sin(y/2)**2
    return 3958.7613*2*math.asin(math.sqrt(min(1,h)))

def normname(s): return re.sub(r'[^a-z0-9]+',' ',str(s or '').lower()).strip()
def sim(a,b): return SequenceMatcher(None,normname(a),normname(b)).ratio()
def lang(r): return r.get('language_code') or r.get('language') or ''

def grid_key(r, step=0.5):
    try: return (int(float(r['latitude'])/step), int(float(r['longitude'])/step))
    except: return None

def match_relocations(old,new):
    pairs=[]; used=set(); grid={}
    for j,n in enumerate(new):
        k=grid_key(n)
        if k: grid.setdefault(k,[]).append(j)
    for o in old:
        k=grid_key(o)
        if not k: continue
        cand=[]
        ol=lang(o)
        for di in (-1,0,1):
            for dj in (-1,0,1):
                for j in grid.get((k[0]+di,k[1]+dj),[]):
                    if j in used: continue
                    n=new[j]
                    if ol and lang(n) and ol!=lang(n): continue
                    d=hav(o,n)
                    if d is None or d>50: continue
                    s=sim(o.get('name'),n.get('name'))
                    if s>=0.35 or d<=5:
                        score=(1 if d<=30 else 0)+(s*2)-(d/100)
                        cand.append((score,j,d,s))
        if cand:
            _,j,d,s=max(cand); used.add(j); pairs.append((o,new[j],d,s))
    return pairs

def local_count_map(recs, step=0.5):
    grid={}
    for r in recs:
        k=grid_key(r,step)
        if k: grid.setdefault(k,[]).append(r)
    out={}
    for r in recs:
        k=grid_key(r,step)
        if not k: continue
        c=0
        for di in (-1,0,1):
            for dj in (-1,0,1):
                for x in grid.get((k[0]+di,k[1]+dj),[]):
                    d=hav(r,x)
                    if d is not None and d<=30: c+=1
        out[r['source_id']]=c
    return out

def build_events(prev,cur):
    po={r['source_id']:r for r in prev['records']}; co={r['source_id']:r for r in cur['records']}
    added=[co[k] for k in co.keys()-po.keys()]; gone=[po[k] for k in po.keys()-co.keys()]
    common=[(po[k],co[k]) for k in po.keys()&co.keys()]
    events=[]
    for o,n in common:
        if normname(o.get('name'))!=normname(n.get('name')): events.append({'type':'name_change','severity':'notable','source_id':n['source_id'],'before':o.get('name'),'after':n.get('name')})
        if lang(o)!=lang(n): events.append({'type':'language_change','severity':'notable','source_id':n['source_id'],'before_language':lang(o),'after_language':lang(n),'name':n.get('name')})
        d=hav(o,n)
        if d is not None and d>=1:
            sev='major' if d>=15 else 'notable'
            events.append({'type':'location_change','severity':sev,'source_id':n['source_id'],'name':n.get('name'),'miles':round(d,1),'before_address':o.get('address'),'after_address':n.get('address')})
    pairs=match_relocations(gone,added)
    paired_old={p[0]['source_id'] for p in pairs}; paired_new={p[1]['source_id'] for p in pairs}
    for o,n,d,s in pairs:
        events.append({'type':'likely_relocation','severity':'major' if d>=15 else 'notable','old_source_id':o['source_id'],'new_source_id':n['source_id'],'name_before':o.get('name'),'name_after':n.get('name'),'miles':round(d,1),'name_similarity':round(s,2),'before_address':o.get('address'),'after_address':n.get('address')})
    for r in added:
        if r['source_id'] not in paired_new:
            l=lang(r); kind='new_language_congregation' if l not in (ENGLISH,SPANISH,'') else 'new_congregation'
            events.append({'type':kind,'severity':'major' if kind=='new_language_congregation' else 'notable','source_id':r['source_id'],'name':r.get('name'),'language':l,'address':r.get('address'),'latitude':r.get('latitude'),'longitude':r.get('longitude')})
    for r in gone:
        if r['source_id'] not in paired_old:
            events.append({'type':'no_longer_observed','severity':'notable','source_id':r['source_id'],'name':r.get('name'),'language':lang(r),'address':r.get('address'),'latitude':r.get('latitude'),'longitude':r.get('longitude')})
    # language at an existing physical location
    oldloc={}
    newloc={}
    for r in prev['records']: oldloc.setdefault(r.get('location_id'),set()).add(lang(r))
    for r in cur['records']: newloc.setdefault(r.get('location_id'),set()).add(lang(r))
    for lid,langs in newloc.items():
        for l in langs-oldloc.get(lid,set()):
            if l not in (ENGLISH,SPANISH,''):
                rs=[r for r in cur['records'] if r.get('location_id')==lid and lang(r)==l]
                if rs: events.append({'type':'new_language_at_existing_location','severity':'major','location_id':lid,'language':l,'name':rs[0].get('name'),'address':rs[0].get('address')})
    return events

def main():
    raw=load_raw()
    previous=load_latest()
    prior_ids=set(r['source_id'] for r in previous['records']) if previous else set()
    us=[]; country_counts={}
    for r in raw['records']:
        ok,c,reason=classify_us(r,prior_ids)
        country_counts[c]=country_counts.get(c,0)+1
        if ok: us.append(r)
    date=raw['captured_at'][:10]
    cur={'captured_at':raw['captured_at'],'source':raw.get('source'),'collector_version':'3.3','record_count':len(us),'records':us}
    path=SNAP/(date+'.json')
    if path.exists(): path=SNAP/(date+'-'+raw['captured_at'][11:19].replace(':','')+'.json')
    path.write_text(json.dumps(cur,ensure_ascii=False,indent=2),encoding='utf-8')
    events=[]
    if previous: events=build_events(previous,cur)
    # simple local-area anomaly score using centers from current and previous; only emit top centers
    local=[]
    if previous:
        cm=local_count_map(cur['records']); pm=local_count_map(previous['records'])
        for r in cur['records']:
            cc=cm.get(r['source_id'],0)
            pc=pm.get(r['source_id'],0)
            delta=cc-pc; pct=(delta/pc*100) if pc else 100 if cc else 0
            if abs(delta)>=3 or abs(pct)>=10:
                local.append({'type':'major_local_change','severity':'major','source_id':r['source_id'],'name':r.get('name'),'latitude':r.get('latitude'),'longitude':r.get('longitude'),'current_count':cc,'previous_count':pc,'delta':delta,'percent_change':round(pct,1)})
        local.sort(key=lambda x:(abs(x['delta']),abs(x['percent_change'])),reverse=True)
        # dedupe nearby centers so one event represents a local cluster
        kept=[]
        for e in local:
            if all(hav(e,k)>15 for k in kept): kept.append(e)
            if len(kept)>=25: break
        events.extend(kept)
    latest={'from':previous['captured_at'] if previous else None,'to':cur['captured_at'],'events':events,'counts':{}}
    from collections import Counter
    latest['counts']=dict(Counter(e['type'] for e in events))
    (EVENTS/'latest.json').write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding='utf-8')
    (DATA/'current_us.json').write_text(json.dumps(cur,ensure_ascii=False),encoding='utf-8')
    summary={'captured_at':cur['captured_at'],'us_congregations':len(us),'raw_records':len(raw['records']),'country_counts':country_counts,'previous_us_congregations':len(previous['records']) if previous else None,'event_counts':latest['counts'],'events_total':len(events)}
    (DATA/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
