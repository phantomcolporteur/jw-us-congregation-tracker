import json,csv,html
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; SNAP=DATA/'snapshots'; DOCS=ROOT/'docs'; DOCS.mkdir(exist_ok=True)
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def e(x): return html.escape(str(x if x is not None else ''))
def main():
 ps=sorted(SNAP.glob('*.json'))
 if not ps:return
 latest=load(ps[-1]); recs=latest.get('records',[]); states=Counter(r.get('state') or 'Unknown' for r in recs); langs=Counter(r.get('language') or 'Unknown' for r in recs)
 rows=[]; cp=DATA/'changes.csv'
 if cp.exists():
  with cp.open(encoding='utf-8') as f: rows=list(csv.DictReader(f))
 recent=rows[-100:][::-1]; counts=Counter(x['change_type'] for x in rows if x.get('to_date')==latest.get('date'))
 sr=''.join(f'<tr><td>{e(s)}</td><td>{n}</td></tr>' for s,n in states.most_common()); lr=''.join(f'<tr><td>{e(s)}</td><td>{n}</td></tr>' for s,n in langs.most_common(40))
 cr=''.join(f'<tr><td>{e(x.get("change_type"))}</td><td>{e(x.get("old_name"))}</td><td>{e(x.get("new_name"))}</td><td>{e(x.get("old_state") or x.get("new_state"))}</td><td>{e(x.get("confidence"))}</td></tr>' for x in recent)
 hist=''.join(f'<tr><td>{p.stem}</td><td>{len(load(p).get("records",[])):,}</td><td>{len(load(p).get("errors",[]))}</td></tr>' for p in ps[-20:][::-1])
 css='body{font-family:system-ui;margin:0;background:#f5f7fb;color:#172033}main{max-width:1200px;margin:auto;padding:30px}.muted{color:#667085}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:20px 0}.card,section{background:white;border:1px solid #e4e7ec;border-radius:14px;padding:18px;box-shadow:0 2px 8px #0001}.num{font-size:30px;font-weight:750}.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #eee;text-align:left;font-size:14px}.green{color:#067647}.red{color:#b42318}.blue{color:#175cd3}@media(max-width:800px){.cols{grid-template-columns:1fr}}'
 body=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>JW U.S. Congregation Tracker</title><style>{css}</style></head><body><main><h1>🇺🇸 JW U.S. Congregation Tracker</h1><p class="muted">Latest snapshot: {e(latest.get('date'))} · Source: JW.org public meeting finder</p><div class="grid"><div class="card"><div class="muted">Observed congregations</div><div class="num">{len(recs):,}</div></div><div class="card"><div class="muted">Languages</div><div class="num">{len(langs)}</div></div><div class="card"><div class="muted">Collection requests</div><div class="num">{latest.get('request_count',0):,}</div></div></div><section><h2>Latest changes</h2><div class="grid"><div class="card"><div>New</div><div class="num green">{counts.get('NEW',0)}</div></div><div class="card"><div>No longer observed</div><div class="num red">{counts.get('NO_LONGER_OBSERVED',0)}</div></div><div class="card"><div>Possible rename/move</div><div class="num blue">{counts.get('POSSIBLE_RENAME_OR_MOVE',0)}</div></div></div><p class="muted">"No longer observed" is deliberately not treated as proof of closure.</p></section><div class="cols"><section><h2>By state</h2><table><tr><th>State</th><th>Observed</th></tr>{sr}</table></section><section><h2>By language</h2><table><tr><th>Language</th><th>Observed</th></tr>{lr}</table></section></div><section><h2>Recent detected changes</h2><table><tr><th>Type</th><th>Previous</th><th>Current</th><th>State</th><th>Confidence</th></tr>{cr or '<tr><td colspan="5">A second snapshot is needed.</td></tr>'}</table></section><section><h2>Snapshot history</h2><table><tr><th>Date</th><th>Records</th><th>Errors</th></tr>{hist}</table></section></main></body></html>'''
 (DOCS/'index.html').write_text(body,encoding='utf-8')
if __name__=='__main__':main()
