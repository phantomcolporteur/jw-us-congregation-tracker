import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; SRC=ROOT/'data'/'snapshot.json'; OUT=ROOT/'data'/'snapshots'
def main():
 if not SRC.exists(): raise SystemExit(f'No {SRC} found. The collector must succeed first.')
 p=json.loads(SRC.read_text(encoding='utf-8'))
 if p.get('record_count',0)<100: raise SystemExit('Snapshot rejected: fewer than 100 records.')
 if p.get('error_count',0)>p.get('request_count',1)*.20: raise SystemExit('Snapshot rejected: more than 20% of requests failed.')
 captured=p.get('captured_at') or datetime.now(timezone.utc).isoformat(); dt=datetime.fromisoformat(captured.replace('Z','+00:00')); p['date']=dt.strftime('%Y-%m-%d'); OUT.mkdir(parents=True,exist_ok=True); target=OUT/f"{dt.strftime('%Y-%m-%dT%H-%M-%SZ')}.json"; target.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8'); print(f'Archived snapshot: {target}')
if __name__=='__main__': main()
