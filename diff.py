import argparse, csv, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data'/'snapshots'
CHANGES=ROOT/'data'/'changes.csv'

FIELDS=['name','language','language_code','latitude','longitude','city','state','address']

def key(x):
    if x.get('source_id'): return 'id:' + str(x['source_id'])
    return 'fallback:' + '|'.join(str(x.get(k) or '').strip().lower() for k in ['name','language','latitude','longitude','city','state'])

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def compare(old,new):
    a={key(x):x for x in old.get('records',[])}
    b={key(x):x for x in new.get('records',[])}
    rows=[]
    for k in sorted(b.keys()-a.keys()):
        x=b[k]; rows.append({'change_type':'NEW','old_name':'','new_name':x.get('name',''),'old_state':'','new_state':x.get('state',''),'confidence':'high'})
    for k in sorted(a.keys()-b.keys()):
        x=a[k]; rows.append({'change_type':'NO_LONGER_OBSERVED','old_name':x.get('name',''),'new_name':'','old_state':x.get('state',''),'new_state':'','confidence':'medium'})
    for k in a.keys() & b.keys():
        aa,bb=a[k],b[k]
        delta={f:(aa.get(f),bb.get(f)) for f in FIELDS if aa.get(f)!=bb.get(f)}
        if not delta: continue
        name_changed=aa.get('name')!=bb.get('name')
        location_changed=any(aa.get(f)!=bb.get(f) for f in ['latitude','longitude','address','city','state'])
        if name_changed and location_changed: typ='POSSIBLE_RENAME_OR_MOVE'
        elif name_changed: typ='POSSIBLE_RENAME'
        elif location_changed: typ='POSSIBLE_MOVE'
        elif aa.get('language')!=bb.get('language') or aa.get('language_code')!=bb.get('language_code'): typ='LANGUAGE_CHANGED'
        else: typ='OTHER_CHANGE'
        rows.append({'change_type':typ,'old_name':aa.get('name',''),'new_name':bb.get('name',''),'old_state':aa.get('state',''),'new_state':bb.get('state',''),'confidence':'medium'})
    return rows

def main():
    files=sorted(SNAP.glob('*.json'))
    if not files: raise SystemExit('No snapshots exist yet.')
    if len(files)<2:
        print('First snapshot saved; no previous snapshot to compare.')
        return
    old,new=load(files[-2]),load(files[-1])
    rows=compare(old,new)
    CHANGES.parent.mkdir(parents=True,exist_ok=True)
    existing=[]
    if CHANGES.exists():
        with CHANGES.open(encoding='utf-8',newline='') as f: existing=list(csv.DictReader(f))
    fieldnames=['from_date','to_date','change_type','old_name','new_name','old_state','new_state','confidence']
    from_date=old.get('date',''); to_date=new.get('date','')
    for r in rows:
        r['from_date']=from_date; r['to_date']=to_date
    # Keep one copy of each snapshot-pair event if workflow is rerun.
    existing=[r for r in existing if not (r.get('from_date')==from_date and r.get('to_date')==to_date)]
    with CHANGES.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader(); w.writerows(existing+rows)
    print(f'Compared {from_date} -> {to_date}: {len(rows)} changes')

if __name__=='__main__': main()
