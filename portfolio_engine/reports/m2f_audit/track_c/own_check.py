"""Independent comparison of a (possibly mutated) pe.wing_body mirror against the track-C reference.  usage: M2F_PYPATH=<mirror>/python python3 own_check.py out.json
Real ledger (engine loaded from the mirror, pe other modules untouched) + 18 synthetic counterexample scenarios + 150 fuzz scenarios.  Output: per-component differences.  An exception is reported as CRASH (not counted as a kill)."""
import sys, os, json, pickle, collections, traceback, random
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
PYP = os.environ['M2F_PYPATH']; REPO = '/home/user/Algo-8-Reverse-Engineer'; SC = '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_c/'
sys.path.insert(0, PYP)
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import wing_body as wb
from pe.generators import historical as H
import ref_wing_body as R, load_raw
import cx_harness as X
out = dict(real={}, synthetic={}, fuzz={}, crash=None)
def real():
    pk = SC + 'ref_cache.pkl'
    if os.path.exists(pk): A, F = pickle.load(open(pk, 'rb'))
    else: F = load_raw.load(); A = R.analyse(F); pickle.dump((A, F), open(pk, 'wb'))
    ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); meta = {r['parent_order_id']: r for r in H.generate_parents(REPO, ls.roles)}
    E = wb.analyse(ls, meta, 'TAGGED'); res = {}
    ei = {X.ikey(i.item_id): i for i in E.items}; mi = A['items']; res['items_keyset_equal'] = set(ei) == set(mi)
    res['item_field_diffs'] = sum(1 for k in set(ei) & set(mi) if not (ei[k].qty == mi[k].qty and ei[k].first_ts == mi[k].first_ts and ei[k].e_minute == mi[k].emin and abs(ei[k].avg_px - mi[k].pxsum / mi[k].qty) < 1e-6 and ei[k].session == mi[k].session - 0 or False) and not (ei[k].qty == mi[k].qty and ei[k].first_ts == mi[k].first_ts and ei[k].e_minute == mi[k].emin and abs(ei[k].avg_px - mi[k].pxsum / mi[k].qty) < 1e-6 and ei[k].session == __import__('datetime').date.fromordinal(719163 + mi[k].session).isoformat()))
    for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'):
        el = collections.defaultdict(list)
        for l in E.links[m]: el[(l['level'], X.ikey(l['wing_item']), X.ikey(l['body_item']))].append(l)
        ml = {(l['level'], l['wing'], l['body']): l for l in A['links'][m]}; d = dict(rows_engine=len(E.links[m]), rows_ref=len(ml), dup_keys=sum(1 for v in el.values() if len(v) > 1), only_engine=len(set(el) - set(ml)), only_ref=len(set(ml) - set(el)), field=collections.Counter())
        for k in set(el) & set(ml):
            e = el[k][0]; l = ml[k]
            c = dict(dt=e['dt_s'] == l['dt_s'], q=(e['wing_qty'], e['body_qty']) == (l['wing_qty'], l['body_qty']), r=abs(e['qty_ratio'] - l['qty_ratio']) < 1e-9, o=e['otm_distance'] == l['otm'], px=abs(e['px_ratio'] - l['px_ratio']) < 1e-6, se=e['same_entry_minute'] == l['same_emin'], sess=e['session'] == __import__('datetime').date.fromordinal(719163 + A['items'][l['wing']].session).isoformat(), wts=e['wing_first_ts'] == A['items'][l['wing']].first_ts)
            if m != 'W3': c.update(n=e['nearest'] == l['nearest'], t=e['nearest_tied'] == l['tied'], nc=e['n_candidates_for_wing'] == l['n_cand'], ls=e['link_status'] == ('UNIQUE_CANDIDATE' if l['n_cand'] == 1 else 'MULTIPLE_CANDIDATES'), ip=e['in_primary_candidate_set'] == (1 if m in ('W1', 'W2') else l['same_emin']))
            if m in ('W2', 'W2_S60'): c.update(w=abs(e['weight'] - l['weight']) < 1e-8, wu=abs(e['weighted_wing_units'] - l['wunits']) < 1e-5)
            if m == 'W3': c.update(mu=e['queue_matched_units'] == l['matched'], seg=e['segment'] == l['seg'], w=abs(e['weight'] - l['weight']) < 1e-8)
            for n, ok in c.items():
                if not ok: d['field'][n] += 1
        d['field'] = dict(d['field']); res[m] = d
    res['w3_resid'] = (E.w3_residual['wing_units_unmatched'], E.w3_residual['body_units_unmatched']) == (A['w3_resid']['wing'], A['w3_resid']['body'])
    # coverage
    cov_diffs = []
    I = mi
    for lv in ('OPENING', 'CLOSING'):
        for m in ('W1', 'W1_S60') + (('W3',) if lv == 'OPENING' else ()):
            c = wb.coverage(E, lv, m); W_ = [i for i in I.values() if i.level == lv and i.role == 'WING']; B_ = [i for i in I.values() if i.level == lv and i.role == 'BODY']; L = [l for l in A['links'][m] if l['level'] == lv]
            wl = collections.Counter(l['wing'] for l in L); bl = collections.Counter(l['body'] for l in L); wu = sum(i.qty for i in W_); bu = sum(i.qty for i in B_)
            mine = dict(wing_items=len(W_), body_items=len(B_), wing_units=wu, body_units=bu, wing_items_with_candidate=len(wl), wing_items_unique_candidate=sum(1 for v in wl.values() if v == 1), wing_items_multiple_candidates=sum(1 for v in wl.values() if v > 1), wing_items_no_candidate=len(W_) - len(wl), wing_units_unmatched=wu - sum(I[k].qty for k in wl),
                        body_items_with_wing_candidate=len(bl), body_items_without_wing=len(B_) - len(bl), body_units_without_wing=bu - sum(I[k].qty for k in bl), links=len(L))
            if m == 'W3': mine['wing_units_unmatched'] = A['w3_resid']['wing']; mine['body_units_without_wing'] = A['w3_resid']['body']
            for k, v in mine.items():
                if c[k] != v: cov_diffs.append((lv, m, k, c[k], v))
    res['coverage_diffs'] = cov_diffs
    # scope exclusions (own)
    ex = collections.defaultdict(int)
    for p in A['portions']:
        f = p['fill']; d = p['dir']
        if not ((d == 1 and f['tag'] == 'h_') or (d == -1 and f['tag'] == 'num')): ex[('OPENING' if p['kind'] == 'OPEN' else 'CLOSING_of_' + ('LONG' if d == 1 else 'SHORT') + '_episode', ('LONG' if d == 1 else 'SHORT') if p['kind'] == 'OPEN' else 'closing_module', f['tag'])] += p['qty']
    mex = {f'{a}|{b}|{c}': v for (a, b, c), v in sorted(ex.items())}; res['scope_exclusions_equal'] = wb.scope_exclusions(ls) == mex
    # group-level ratios
    g = collections.defaultdict(lambda: [0, 0])
    for i in I.values(): g[i.grp + (i.emin,)][0 if i.role == 'WING' else 1] += i.qty
    G = wb.group_level_ratios(E); gd = []
    for lv in ('OPENING', 'CLOSING'):
        gs = [v for k, v in g.items() if k[0] == lv]; both = [v for v in gs if v[0] and v[1]]; exx = [v for v in both if v[0] == v[1]]
        mine = dict(groups_total=len(gs), groups_with_both=len(both), groups_wing_only=sum(1 for v in gs if v[0] and not v[1]), groups_body_only=sum(1 for v in gs if v[1] and not v[0]), share_exactly_1_of_groups_with_both=len(exx) / len(both))
        for k, v in mine.items():
            if G[lv][k] is None or abs(G[lv][k] - v) > 1e-9: gd.append((lv, k, G[lv][k], v))
    res['group_ratio_diffs'] = gd
    # direction scope
    return res
def synth():
    exec(open(os.path.join(HERE, 'cx_scenarios.py')).read().split('res = {}')[0], globals())
    bad = []
    for name, spec in S.items():
        for scope in ('TAGGED', 'DIRECTION'):
            d, E, A = X.compare(spec, scope)
            if d: bad.append((name, scope, str(d[0])[:150]))
    rnd = random.Random(77); fz = []
    for it in range(150):
        insts = [X.N(cp, 24000 + 100 * k) for cp in ('CE', 'PE') for k in range(3)] + [X.N('CE', 24000, '2026-01-15')]; spec = []
        for j in range(rnd.randint(3, 14)):
            tag = rnd.choice(('h_', 'num', 'h_', 'num', 's_', 'v_')); side = rnd.choice((1, -1)); par = f'P{rnd.randint(0, 9)}'
            spec.append(dict(inst=rnd.choice(insts), t=rnd.choice((0, 1, 2, 30, 59, 60, 61, 62, 119, 120, IDAY - 5, IDAY + 5)) + rnd.randint(0, 3), side=side, qty=65 * rnd.randint(1, 4), parent=par + ('_' + tag), tag=tag, e=rnd.choice((0, 0, 1, 2, None))))
        seen = {}
        for s in spec: seen.setdefault(s['parent'], (s['tag'], s['e'])); s['tag'], s['e'] = seen[s['parent']]
        for scope in ('TAGGED', 'DIRECTION'):
            d, E, A = X.compare(spec, scope)
            if d: fz.append((it, scope, str(d[0])[:120]))
    return dict(scenarios_with_diffs=bad, fuzz_with_diffs=len(fz), fuzz_examples=fz[:3])
try:
    out['synthetic'] = synth()
except Exception as e: out['crash'] = 'synthetic: ' + repr(e)[:300]
try:
    out['real'] = real()
except Exception as e: out['crash'] = (out['crash'] or '') + ' real: ' + repr(e)[:300] + traceback.format_exc()[-500:]
def verdict(o):
    r = o['real']; s = o['synthetic']; reasons = []
    if o['crash']: return 'CRASH', [o['crash'][:200]]
    if not r.get('items_keyset_equal') or r.get('item_field_diffs'): reasons.append('items')
    for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'):
        d = r[m]
        if d['rows_engine'] != d['rows_ref'] or d['dup_keys'] or d['only_engine'] or d['only_ref'] or d['field']: reasons.append(f'links:{m}')
    for k in ('w3_resid', 'scope_exclusions_equal'):
        if not r[k]: reasons.append(k)
    if r['coverage_diffs']: reasons.append('coverage')
    if r['group_ratio_diffs']: reasons.append('group_ratio')
    if s['scenarios_with_diffs'] or s['fuzz_with_diffs']: reasons.append('synthetic/fuzz')
    return ('KILLED' if reasons else 'SURVIVED'), reasons
v, why = verdict(out); out['verdict'] = v; out['reasons'] = why
json.dump(out, open(sys.argv[1], 'w'), indent=1, default=str); print(v, why)
