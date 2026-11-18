"""Stage 1: inventory of the committed dataset and reconciliation of file names against the manifests (checkpoint, status, calendars, reports)."""
import csv, io, json, re, sys, collections
from .gitsrc import GitSource


def run(commit, out_dir):
    g = GitSource(commit); t = g.tree(); R = dict(commit=g.commit, files=len(t), bytes=sum(z for _, z in t.values()))
    by = collections.defaultdict(lambda: [0, 0])
    for p, (s, z) in t.items():
        k = re.sub(r'exp\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}', 'D', p); by[k][0] += 1; by[k][1] += z
    R['by_pattern'] = {k: dict(files=v[0], bytes=v[1]) for k, v in sorted(by.items())}
    ck = list(csv.reader(io.StringIO(g.text('manifests/checkpoint.csv'))))
    R['checkpoint_rows'] = len(ck); plan = collections.defaultdict(set); spot = collections.defaultdict(set); fut = collections.defaultdict(set); opts = collections.Counter(); dup = 0; seen = set(); width = collections.Counter(len(r) for r in ck)
    for r in ck:
        tup = tuple(r)
        if tup in seen: dup += 1
        seen.add(tup)
        if r[1] == 'option': plan[r[0]].add((r[2], r[3])); opts[(r[0], r[2], r[3])] += 1
        elif r[1] == 'spot': spot[r[0]].add(r[2])
        elif r[1] == 'futures': fut[r[0]].add(r[2])
        else: R.setdefault('unknown_checkpoint_kinds', []).append(r)
    R['checkpoint_row_widths'] = dict(width); R['checkpoint_duplicate_rows'] = dup
    files_opt = {i: set() for i in ('nifty', 'sensex')}; files_spot = {i: set() for i in ('nifty', 'sensex')}; files_fut = {i: set() for i in ('nifty', 'sensex')}
    for p in t:
        m = re.match(r'normalized/(nifty|sensex)/options/exp(\S{10})_(\S{10})\.csv', p)
        if m: files_opt[m[1]].add((m[2], m[3]))
        m = re.match(r'normalized/(nifty|sensex)/underlying/spot/(\S{10})\.csv', p)
        if m: files_spot[m[1]].add(m[2])
        m = re.match(r'normalized/(nifty|sensex)/underlying/futures/(\S{10})\.csv', p)
        if m: files_fut[m[1]].add(m[2])
    R['manifest_vs_files'] = {}
    for i in ('nifty', 'sensex'):
        R['manifest_vs_files'][i] = dict(
            option_sessions_in_checkpoint=len(plan[i]), option_session_files=len(files_opt[i]), sessions_in_checkpoint_without_file=sorted(plan[i] - files_opt[i])[:10], files_not_in_checkpoint=sorted(files_opt[i] - plan[i])[:10],
            contracts_in_checkpoint=sum(opts[k] for k in opts if k[0] == i), contracts_per_session=dict(collections.Counter(sum(1 for k in opts if k[0] == i and (k[1], k[2]) == s) for s in plan[i])),
            spot_days_in_checkpoint=len(spot[i]), spot_files=len(files_spot[i]), spot_missing_files=sorted(spot[i] - files_spot[i])[:10], spot_extra_files=sorted(files_spot[i] - spot[i])[:10],
            futures_days_in_checkpoint=len(fut[i]), futures_files=len(files_fut[i]), futures_missing_files=sorted(fut[i] - files_fut[i])[:10])
    R['download_status'] = json.loads(g.text('manifests/download_status.json'))
    for i in ('nifty', 'sensex'):
        rows = list(csv.DictReader(io.StringIO(g.text(f'metadata/expiry_calendar/expiry_calendar_{i}.csv')))); R[f'calendar_{i}'] = dict(rows=len(rows), found=sum(1 for r in rows if r['expiry']), not_found=sum(1 for r in rows if not r['expiry']), first=rows[0]['week'], last=rows[-1]['week'], weekdays=dict(collections.Counter(r['weekday'] for r in rows)))
    json.dump(R, open(f'{out_dir}/inventory.json', 'w'), indent=1, default=str); return R


if __name__ == '__main__':
    r = run(sys.argv[1], sys.argv[2]); print(json.dumps({k: v for k, v in r.items() if k != 'by_pattern'}, indent=1, default=str)[:5000])
