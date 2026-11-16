"""Item 7: compare my regenerated file inventory with the committed reports/r1c_dual_scenario/file_inventory.json (class counts and per-path classes + hashes), and
check the hybrid's real inventory_series.tsv against the flag sidecar (item 1b, on the actual output files)."""
import json, sys, os, csv, collections
mine = json.load(open(sys.argv[1])); repo = json.load(open(sys.argv[2])); base_out, hyb_out = sys.argv[3], sys.argv[4]


def summ(j):
    keys = [k for k in j if isinstance(j[k], dict)]
    return {k: (j[k] if len(json.dumps(j[k])) < 800 else '...') for k in j if k not in ('files',)}


print('top-level keys mine', list(mine)); print('top-level keys repo', list(repo))
for k in ('delivered_files', 'control_files_produced', 'scenario_files_produced', 'TOTAL_UNIVERSE'):
    print(k, mine.get(k), repo.get(k))
for k in mine:
    if k in repo and isinstance(mine[k], dict) and len(json.dumps(mine[k])) < 1500: print(k, 'equal' if mine[k] == repo[k] else ('DIFF', mine[k], repo[k]))


def cls(j):
    out = {}
    for side in ('control', 'scenario'):
        v = j.get(side) or j.get('comparisons', {}).get(side)
        if isinstance(v, dict):
            for p, e in (v.get('paths') or v.get('files') or {}).items(): out[(side, p)] = e if not isinstance(e, dict) else e.get('class')
    return out


a, b = cls(mine), cls(repo); print('per-path classes mine', len(a), 'repo', len(b), 'differing', sum(1 for k in set(a) | set(b) if a.get(k) != b.get(k)))
# 1b on real output: last fill of each second in hybrid inventory_series; compare cum columns with baseline at the same second
cy = 'SENSEX_2026-07-16'


def read(base, name):
    with open(os.path.join(base, 'reports', 'm2e_data', cy, name)) as fh: return list(csv.DictReader(fh, delimiter='\t'))


B = read(base_out, 'inventory_series.tsv'); H = read(hyb_out, 'inventory_series.tsv'); Fg = read(hyb_out, 'inventory_series_intra_second_flags.tsv')
flag = {r['fill_id']: r['aggregate_state_after_fill'] for r in Fg}


def second_end(rows):
    out = {}
    for r in rows: out[r['ts_utc_s']] = r
    return out


be, he = second_end(B), second_end(H); cols = [c for c in B[0] if c.startswith('cum_') or c in ('short_CE', 'short_PE', 'long_CE', 'long_PE', 'gross_total', 'net_total')]
diff = collections.Counter(); rows_flagged_invariant_but_differ = 0
for ts, r in he.items():
    d = [c for c in cols if r[c] != be[ts][c]]
    for c in d: diff[c] += 1
    if d and flag[r['fill_id']] == 'SECOND_END_ORDER_INVARIANT': rows_flagged_invariant_but_differ += 1
print('SENSEX cycle: second-end rows (last fill of a second) whose columns differ baseline vs hybrid, by column:', dict(diff))
print('of those, rows that the sidecar labels SECOND_END_ORDER_INVARIANT or SINGLE_FILL_SECOND:', rows_flagged_invariant_but_differ)
cy = 'NIFTY_2026-06-30'; B = read(base_out, 'inventory_series.tsv'); H = read(hyb_out, 'inventory_series.tsv'); Fg = read(hyb_out, 'inventory_series_intra_second_flags.tsv'); flag = {r['fill_id']: r['aggregate_state_after_fill'] for r in Fg}
be, he = second_end(B), second_end(H); diff = collections.Counter(); n = 0
for ts, r in he.items():
    d = [c for c in cols if r[c] != be[ts][c]]
    for c in d: diff[c] += 1
    if d and flag[r['fill_id']] in ('SECOND_END_ORDER_INVARIANT', 'SINGLE_FILL_SECOND'): n += 1
print('NIFTY cycle:', dict(diff), 'flagged invariant but differ:', n)
