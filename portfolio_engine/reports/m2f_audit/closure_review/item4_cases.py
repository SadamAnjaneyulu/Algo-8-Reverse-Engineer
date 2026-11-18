"""Item 4: (i) re-derive the D-1 concentration statement from the delivered case records, with my own timestamp -> IST -> session logic, using the raw CSV for the start time of each selected episode's
instrument's first fill of that episode (episode start = first fill of the episode per episodes.tsv; I cross-check episodes.tsv first_ts against the raw rows). (ii) which inputs does case selection read?"""
import csv, json, os, datetime as dt, collections, re
import rawload as R
PE = os.path.join(R.REPO, 'portfolio_engine'); res = {}
rows = R.load(); byrow = {r['row']: r for r in rows}
prof = [];
for cy, expiry in (('NIFTY_2026-06-30', '2026-06-30'), ('SENSEX_2026-07-16', '2026-07-16')):
    d = os.path.join(PE, 'reports', 'm2e_data', cy)
    cs = json.load(open(os.path.join(d, 'case_studies.json'))); eps = {r['episode_id']: r for r in csv.DictReader(open(os.path.join(d, 'episodes.tsv')), delimiter='\t')}
    fills = {r['fill_id']: r for r in csv.DictReader(open(os.path.join(d, 'fills.tsv')), delimiter='\t')}
    ev = [r for r in csv.DictReader(open(os.path.join(d, 'lifecycle_events.tsv')), delimiter='\t')]
    sessions = sorted({R.ist_day(r['ts']) for r in rows if r['expiry'] == expiry and r['und'] == cy.split('_')[0]})
    exp_day = (dt.date.fromisoformat(expiry) - dt.date(1970, 1, 1)).days
    for name, rec in cs['records'].items():
        if rec['status'] != 'AVAILABLE': res.setdefault(cy, {})[name] = 'UNAVAILABLE'; continue
        eid = rec['position_id']; e = eps[eid]
        # my own start time: first raw fill (by row) of the episode's first lifecycle event
        first_fill = next(x['fill_id'] for x in ev if x['episode_id'] == eid); row = int(first_fill[1:]); ts = byrow[row]['ts']
        assert str(ts) == e['first_ts_utc_s'], (eid, ts, e['first_ts_utc_s'])
        day = R.ist_day(ts); prior = [s for s in sessions if s < exp_day]
        label = 'D0' if day == exp_day else f'D-{len(prior) - prior.index(day)}'
        hh = dt.datetime.fromtimestamp(ts + 19800, dt.timezone.utc).strftime('%H:%M:%S')
        prof.append((cy, name, eid, label, hh)); res.setdefault(cy, {})[name] = dict(position=eid, d_label=label, ist=hh)
c = collections.Counter(p[3] for p in prof); h = collections.Counter(p[4][:2] for p in prof)
res['summary'] = dict(n=len(prof), by_d_label=dict(c), by_ist_hour=dict(h), distinct_positions=len({(p[0], p[2]) for p in prof}))
print(res['summary']); [print(p) for p in prof]
# claim text in the report
md = open(os.path.join(PE, 'reports', 'M2E_POSITION_CASE_STUDIES.md')).read(); m = re.search(r'### 1\.1.*?\n\n(.*?)\n', md, re.S); print(m.group(1)[:700] if m else 'no 1.1 paragraph')
# (ii) inputs read by pe/cases.select
src = open(os.path.join(PE, 'python', 'pe', 'cases.py')).read(); sel = src[src.index('def select'):src.index('def record')]
cols = sorted(set(re.findall(r"\[\'([a-z_0-9]+)\'\]", sel))); res['columns_read_by_select'] = cols; print('columns read by select():', cols)
json.dump(res, open('item4_cases_result.json', 'w'), indent=1)
