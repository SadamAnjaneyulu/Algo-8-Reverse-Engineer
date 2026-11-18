"""Item (5): recompute cycle-level W1/W1_S60/W3 coverage of the two frozen cycles from RAW and compare ALL fields with m2e_data/<cycle>/coverage.json['wing_body_coverage_cycle_level']. [RAW][IMPL]
Two recomputations: (a) full-ledger replay filtered to the cycle, (b) replay on the cycle-only fills (what the engine does)."""
import json, collections, load_raw, ref_wing_body as R
REPO = '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2e_data/'
F = load_raw.load()
def dist(xs):
    xs = sorted(xs)
    if not xs: return dict(n=0)
    q = lambda f: xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
    return dict(n=len(xs), min=xs[0], p10=q(.1), median=q(.5), p90=q(.9), max=xs[-1])
def cov(A, level, method, cyc):
    I = {k: i for k, i in A['items'].items() if (i.inst[0], i.inst[1]) == cyc}
    W = [i for i in I.values() if i.level == level and i.role == 'WING']; B = [i for i in I.values() if i.level == level and i.role == 'BODY']
    L = [l for l in A['links'][method] if l['level'] == level and (l['wing'][3][0], l['wing'][3][1]) == cyc]
    wl = collections.Counter(l['wing'] for l in L); bl = collections.Counter(l['body'] for l in L); wu = sum(i.qty for i in W); bu = sum(i.qty for i in B)
    r = dict(level=level, method=method, wing_items=len(W), body_items=len(B), wing_units=wu, body_units=bu, wing_items_with_candidate=len(wl), wing_items_unique_candidate=sum(1 for v in wl.values() if v == 1), wing_items_multiple_candidates=sum(1 for v in wl.values() if v > 1), wing_items_no_candidate=len(W) - len(wl),
             wing_units_with_candidate=sum(I[k].qty for k in wl), wing_units_unmatched=wu - sum(I[k].qty for k in wl), body_items_with_wing_candidate=len(bl), body_items_without_wing=len(B) - len(bl), body_units_with_wing_candidate=sum(I[k].qty for k in bl), body_units_without_wing=bu - sum(I[k].qty for k in bl), links=len(L),
             candidates_per_wing=dist(list(wl.values())), wings_per_body=dist(list(bl.values())), qty_ratio=dist([l['qty_ratio'] for l in L]), dt_s=dist([l['dt_s'] for l in L]), abs_dt_s=dist([abs(l['dt_s']) for l in L]), otm_distance=dist([l['otm'] for l in L]), px_ratio=dist([l['px_ratio'] for l in L]),
             nearest_tied_links=(sum(l['tied'] for l in L) if method != 'W3' else 'NA'))
    if method == 'W3':
        # per-cycle queue residual: recompute groups within this cycle
        g = collections.defaultdict(lambda: [0, 0])
        for i in W + B: g[i.grp + (i.session,)][0 if i.role == 'WING' else 1] += i.qty
        rw = sum(max(0, v[0] - v[1]) for v in g.values()); rb = sum(max(0, v[1] - v[0]) for v in g.values())
        r['wing_units_unmatched'] = rw; r['body_units_without_wing'] = rb; r['wing_units_with_candidate'] = wu - rw; r['body_units_with_wing_candidate'] = bu - rb
    return r
out = {}
for cyc_name, cyc in (('NIFTY_2026-06-30', ('NIFTY', '2026-06-30')), ('SENSEX_2026-07-16', ('SENSEX', '2026-07-16'))):
    committed = json.load(open(REPO + cyc_name + '/coverage.json'))['wing_body_coverage_cycle_level']
    Afull = R.analyse(F); Acyc = R.analyse([f for f in F if (f['inst'][0], f['inst'][1]) == cyc]); res = {}
    for name, A in (('full_filtered', Afull), ('cycle_only_replay', Acyc)):
        diffs = []; n = 0
        for key, c in committed.items():
            lv, m = key.split('|'); mine = cov(A, lv, m, cyc)
            for f, v in c.items():
                n += 1
                if f == 'nearest_tied_links' and v == 'NA' and mine[f] == 'NA': continue
                if mine[f] != v and not (isinstance(v, dict) and all(abs(float(mine[f].get(k, 0)) - float(v.get(k, 0))) < 1e-5 for k in set(v) | set(mine[f]))): diffs.append((key, f, v, mine[f]))
        res[name] = dict(fields_compared=n, diffs=diffs[:10], n_diffs=len(diffs))
    # also: total headline for cycle
    res['cycle_keys'] = sorted(committed)
    out[cyc_name] = res
json.dump(out, open('cycle_compare_result.json', 'w'), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
