"""Stage 7: compare the broad dataset with the earlier exact-contract Breeze files (data/breeze/..., different downloader and run time) on every overlapping contract-day and index day.
Both come from the same vendor: agreement shows the two pipelines handle the vendor data identically, it is NOT independent proof that the vendor data are correct."""
import io, json, re, sys, collections
import numpy as np, pandas as pd
from .gitsrc import GitSource

COLS = ['open', 'high', 'low', 'close', 'volume', 'open_interest']


def run(commit, out):
    g = GitSource(commit); gl = GitSource(commit, prefix='data/breeze'); lt = gl.tree()
    broad_sessions = {(m[1], m[2], m[3]) for p in g.tree() for m in [re.match(r'normalized/(nifty|sensex)/options/exp(\S{10})_(\S{10})\.csv', p)] if m}
    legacy = collections.defaultdict(list)
    for p in lt:
        m = re.match(r'normalized/options/(NIFTY|SENSEX)/(\S{10})/(\d+)(CE|PE)/(\S{10})\.\w+\.csv', p)
        if m: legacy[(m[1].lower(), m[2], m[5])].append((int(m[3]), m[4], p))
    res = []; cache = {}
    for (idx, exp, day), items in sorted(legacy.items()):
        if (idx, exp, day) not in broad_sessions: res.append(dict(index=idx, expiry=exp, day=day, legacy_contracts=len(items), in_broad=False)); continue
        b = pd.read_csv(io.BytesIO(g.read(f'normalized/{idx}/options/exp{exp}_{day}.csv'))); b['key'] = list(zip(b.strike.astype(int), b.right)); grp = {k: d for k, d in b.groupby('key')}
        for strike, right, p in items:
            L = pd.read_csv(io.BytesIO(gl.read(p))); L['m'] = L.timestamp_ist.str.slice(11, 16); B = grp.get((strike, right))
            r = dict(index=idx, expiry=exp, day=day, strike=strike, right=right, in_broad=True, legacy_rows=len(L), broad_rows=0 if B is None else len(B))
            if B is not None:
                B = B.assign(m=B.datetime.str.slice(11, 16)); M = L.merge(B, on='m', suffixes=('_l', '_b'), how='outer', indicator=True)
                both = M[M._merge == 'both']; r['legacy_only_minutes'] = int((M._merge == 'left_only').sum()); r['broad_only_minutes'] = int((M._merge == 'right_only').sum()); r['both_minutes'] = len(both)
                for c in COLS: r['mismatch_' + c] = int(((both[c + '_l'] != both[c + '_b']) & ~(both[c + '_l'].isna() & both[c + '_b'].isna())).sum())
            res.append(r)
    pd.DataFrame(res).to_csv(f'{out}/legacy_option_crosscheck.csv', index=False)
    # index vs spot
    ires = []
    for p in lt:
        m = re.match(r'normalized/indices/(NIFTY|SENSEX)/(\S{10})\.\w+\.csv', p)
        if not m: continue
        idx, day = m[1].lower(), m[2]; rel = f'normalized/{idx}/underlying/spot/{day}.csv'
        if rel not in g.tree(): continue
        L = pd.read_csv(io.BytesIO(gl.read(p))); L['m'] = L.timestamp_ist.str.slice(11, 16); B = pd.read_csv(io.BytesIO(g.read(rel))); B['m'] = B.datetime.str.slice(11, 16)
        M = L.merge(B, on='m', suffixes=('_l', '_b'), how='outer', indicator=True); both = M[M._merge == 'both']
        r = dict(index=idx, day=day, legacy_rows=len(L), broad_rows=len(B), legacy_only=int((M._merge == 'left_only').sum()), broad_only=int((M._merge == 'right_only').sum()), both=len(both))
        for c in ('open', 'high', 'low', 'close'): r['mismatch_' + c] = int((both[c + '_l'] != both[c + '_b']).sum()); r['maxdiff_' + c] = float((both[c + '_l'] - both[c + '_b']).abs().max()) if len(both) else None
        ires.append(r)
    pd.DataFrame(ires).to_csv(f'{out}/legacy_index_crosscheck.csv', index=False)
    o = pd.DataFrame(res); i = pd.DataFrame(ires); s = dict(legacy_contract_days=int(o.legacy_rows.notna().sum()), overlapping_sessions=int(o[o.in_broad].groupby(['index', 'expiry', 'day']).ngroups), legacy_sessions_not_in_broad=int(o[~o.in_broad].groupby(['index', 'expiry', 'day']).ngroups))
    ov = o[o.in_broad & o.broad_rows.notna()]
    s.update(contract_days_compared=len(ov), legacy_contract_days_absent_in_broad=int((ov.broad_rows == 0).sum()), contract_days_with_any_mismatch=int((ov[[c for c in ov.columns if c.startswith('mismatch_')]].sum(axis=1) > 0).sum()), minutes_legacy_only=int(ov.legacy_only_minutes.sum()), minutes_broad_only=int(ov.broad_only_minutes.sum()), minutes_both=int(ov.both_minutes.sum()),
             field_mismatches={c: int(ov[c].sum()) for c in ov.columns if c.startswith('mismatch_')}, index_days_compared=len(i), index_days_with_mismatch=int((i[[c for c in i.columns if c.startswith('mismatch_')]].sum(axis=1) > 0).sum()), index_minutes_legacy_only=int(i.legacy_only.sum()), index_minutes_broad_only=int(i.broad_only.sum()))
    json.dump(s, open(f'{out}/legacy_crosscheck_summary.json', 'w'), indent=1); return s


if __name__ == '__main__': print(json.dumps(run(sys.argv[1], sys.argv[2]), indent=1))
