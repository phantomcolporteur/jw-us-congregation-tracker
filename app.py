import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title='JW U.S. Congregation Tracker', layout='wide')
st.title('JW U.S. Congregation Tracker')
st.caption('Historical snapshots of the public JW.org meeting-finder data. A change is a data observation, not proof of a congregation dissolution or merger.')

snap=Path('data/snapshot.json'); diff=Path('data/diff.json')
if not snap.exists():
    st.info('No snapshot yet. Run: python tracker/collector.py')
    st.stop()
s=json.loads(snap.read_text()); rows=s.get('records',[])
df=pd.DataFrame(rows)
col1,col2,col3,col4=st.columns(4)
col1.metric('Observed congregations',len(df))
col2.metric('States observed',df['state'].nunique() if 'state' in df else 0)
col3.metric('Languages observed',df['language'].nunique() if 'language' in df else 0)
col4.metric('Captured',s.get('captured_at','')[:10])

if diff.exists():
    d=json.loads(diff.read_text())
    a,b,c=st.columns(3); a.metric('New since prior snapshot',len(d.get('added',[]))); b.metric('Missing since prior snapshot',len(d.get('removed',[]))); c.metric('Changed records',len(d.get('changed',[])))

st.subheader('By state')
if 'state' in df:
    st.dataframe(df.groupby('state').size().sort_values(ascending=False).rename('congregations').to_frame(),use_container_width=True)

st.subheader('By language')
if 'language' in df:
    st.dataframe(df.groupby('language').size().sort_values(ascending=False).rename('congregations').to_frame(),use_container_width=True)

st.subheader('Records')
cols=[c for c in ['name','language','city','state','latitude','longitude','address','source_id'] if c in df.columns]
st.dataframe(df[cols].sort_values(['state','city','name'],na_position='last'),use_container_width=True,hide_index=True)
