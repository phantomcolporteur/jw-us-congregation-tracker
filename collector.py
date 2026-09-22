#!/usr/bin/env python3
import argparse,json,os,time
from datetime import datetime,timezone
from pathlib import Path
import requests
API_URL=os.getenv('JW_API_URL','https://apps.jw.org/api/public/meeting-search/weekly-meetings')
MEETING_UI='https://apps.jw.org/ui/E/meeting-search.html#/weekly-meetings'
BBOX=(-124.8,24.3,-66.9,49.4)
HEADERS={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36','Accept':'application/json, text/plain, */*','Referer':MEETING_UI,'Origin':'https://apps.jw.org','X-Requested-With':'XMLHttpRequest'}
def grid(step=1.0):
 a,b,c,d=BBOX; lat=b
 while lat<=d+1e-9:
  lon=a
  while lon<=c+1e-9:
   yield round(lat,4),round(lon,4); lon+=step
  lat+=step
def first(x,keys):
 if isinstance(x,dict):
  for k in keys:
   if k in x and x[k] not in (None,''): return x[k]
def walk(x):
 if isinstance(x,dict):
  if {str(k).lower() for k in x}&{'congregationname','congregation_name','meetingname','congregation','congregationid'}: yield x
  for v in x.values(): yield from walk(v)
 elif isinstance(x,list):
  for v in x: yield from walk(v)
def norm(r):
 cid=first(r,['congregationId','congregationID','id','congregation_id'])
 return {'source_id':str(cid) if cid is not None else None,'name':first(r,['congregationName','congregation_name','meetingName','name']),'language':first(r,['languageName','language','languageDescription','searchLanguageName']),'language_code':first(r,['languageCode','language_code','searchLanguageCode']),'latitude':first(r,['latitude','lat']),'longitude':first(r,['longitude','lon','lng']),'city':first(r,['city','locality','town']),'state':first(r,['state','stateName','province']),'address':first(r,['address','meetingAddress','locationAddress']),'source_record':r}
def key(x):
 if x.get('source_id'): return 'id:'+str(x['source_id'])
 return 'fallback:'+'|'.join(str(x.get(k) or '').strip().lower() for k in ['name','language','latitude','longitude','city','state'])
def session():
 s=requests.Session(); s.headers.update(HEADERS); return s
def request_point(s,lat,lon):
 p={'includeSuggestions':'true','latitude':lat,'longitude':lon,'searchLanguageCode':'E'}; last=None
 for n in range(1,4):
  try:
   r=s.get(API_URL,params=p,timeout=30)
   if r.status_code>=400: raise RuntimeError(f'HTTP {r.status_code}; response={r.text[:500]!r}')
   try:return r.json()
   except ValueError: raise RuntimeError(f'HTTP {r.status_code}; response was not JSON: {r.text[:500]!r}')
  except Exception as e:
   last=e
   if n<3: time.sleep(n*1.5)
 raise last
def probe():
 print('Testing JW.org meeting-finder connection...',flush=True)
 payload=request_point(session(),39.7392,-104.9903)
 rec=[norm(x) for x in walk(payload) if norm(x).get('name')]
 print(f'Probe succeeded: {len(rec)} meeting records returned.',flush=True)
 if not rec: raise RuntimeError('JW.org responded but no meeting records were found in the probe response.')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--step',type=float,default=float(os.getenv('GRID_STEP','1.0'))); ap.add_argument('--delay',type=float,default=float(os.getenv('REQUEST_DELAY','0.35'))); ap.add_argument('--max-points',type=int); ap.add_argument('--out',default='data/snapshot.json'); args=ap.parse_args()
 probe(); points=list(grid(args.step)); points=points[:args.max_points] if args.max_points else points; s=session(); out={}; errors=[]
 for i,(lat,lon) in enumerate(points,1):
  try:
   for raw in walk(request_point(s,lat,lon)):
    item=norm(raw)
    if item.get('name'): out[key(item)]=item
  except Exception as e: errors.append({'lat':lat,'lon':lon,'error':repr(e)})
  if i%25==0 or i==len(points): print(f'{i}/{len(points)} points; {len(out)} records; {len(errors)} errors',flush=True)
  time.sleep(args.delay)
 rate=len(errors)/len(points) if points else 1
 if len(out)<100 or rate>0.20:
  raise SystemExit(f'\nCOLLECTION REJECTED AS INVALID.\nRequests: {len(points)}\nRecords: {len(out)}\nErrors: {len(errors)} ({rate:.1%})\nSample errors: {json.dumps(errors[:5],indent=2)}\n\nNo snapshot was written because the result is not trustworthy.')
 now=datetime.now(timezone.utc).isoformat(); snap={'captured_at':now,'source':API_URL,'record_count':len(out),'request_count':len(points),'error_count':len(errors),'records':list(out.values()),'errors':errors}; p=Path(args.out); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'captured_at':now,'records':len(out),'errors':len(errors),'out':str(p)},indent=2))
if __name__=='__main__': main()
