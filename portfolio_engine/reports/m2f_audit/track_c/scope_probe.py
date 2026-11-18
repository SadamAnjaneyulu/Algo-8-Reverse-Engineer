"""Scope probes [RAW][IMPL]: who opened the episodes that are closed by s_ (stops) / num / v_; are wing items 1 instrument per parent; distributions quoted by the report."""
import json, collections, load_raw, ref_wing_body as R
F = load_raw.load(); A = R.analyse(F); I = A['items']; out = {}
inv = collections.defaultdict(int); ep = collections.defaultdict(int); epmods = collections.defaultdict(collections.Counter); cp_ep = {}
for f in sorted(F, key=lambda f: (f['ts'], f['row'])):
    i = f['inst']; cur = inv[i]; q = f['qty']; s = f['sgn']
    if cur != 0 and (cur > 0) != (s > 0):
        cp_ep[f['row']] = (i, ep[i]); c = min(q, abs(cur))
        if q - c > 0: ep[i] += 1; epmods[(i, ep[i])][f['tag']] += q - c
    else:
        if cur == 0: ep[i] += 1
        epmods[(i, ep[i])][f['tag']] += q
    inv[i] = cur + s * q
o = collections.defaultdict(int)
for p in A['portions']:
    if p['kind'] != 'CLOSE': continue
    f = p['fill']; d = p['dir']; mods = epmods[cp_ep[f['row']]]
    if d == -1 and f['tag'] == 's_': o['short_episodes_closed_by_s_|opened_only_by_num' if set(mods) == {'num'} else 'short_episodes_closed_by_s_|opened_by_other_or_mixed'] += p['qty']
    if d == 1 and f['tag'] == 'num': o['long_episodes_closed_by_num|opened_only_by_h_' if set(mods) == {'h_'} else 'long_episodes_closed_by_num|other'] += p['qty']
    if d == 1 and f['tag'] == 'v_': o['long_episodes_closed_by_v_|opened_by_' + ('+'.join(sorted(mods)))] += p['qty']
    if d == 1 and f['tag'] == 's_': o['long_episodes_closed_by_s_|opened_by_' + ('+'.join(sorted(mods)))] += p['qty']
out['closing_exclusion_by_episode_origin'] = dict(o)
wp = collections.Counter(k[2] for k in I if k[0] == 'OPENING' and k[1] == 'WING'); out['opening_wing_parents'] = len(wp); out['opening_wing_items'] = sum(wp.values()); out['wing_parents_with_multiple_instruments'] = sum(1 for v in wp.values() if v > 1)
bp = collections.Counter(k[2] for k in I if k[0] == 'OPENING' and k[1] == 'BODY'); out['opening_body_parents'] = len(bp); out['body_parents_multi_instr'] = sum(1 for v in bp.values() if v > 1)
def q(xs, f): xs = sorted(xs); return xs[min(len(xs) - 1, int(f * (len(xs) - 1) + .5))]
S = json.load(open('../../m2d_data/m2d_summary.json'))['coverage']; chk = {}
for lv in ('OPENING', 'CLOSING'):
    for m in ('W1', 'W1_S60'):
        L = [l for l in A['links'][m] if l['level'] == lv]; wl = collections.Counter(l['wing'] for l in L); bl = collections.Counter(l['body'] for l in L)
        mine = dict(candidates_per_wing=[min(wl.values()), q(wl.values(), .1), q(wl.values(), .5), q(wl.values(), .9), max(wl.values())], wings_per_body=[min(bl.values()), q(bl.values(), .1), q(bl.values(), .5), q(bl.values(), .9), max(bl.values())], abs_dt=[min(abs(l['dt_s']) for l in L), q([abs(l['dt_s']) for l in L], .1), q([abs(l['dt_s']) for l in L], .5), q([abs(l['dt_s']) for l in L], .9), max(abs(l['dt_s']) for l in L)],
                    otm=[min(l['otm'] for l in L), q([l['otm'] for l in L], .1), q([l['otm'] for l in L], .5), q([l['otm'] for l in L], .9), max(l['otm'] for l in L)], qty_ratio=[min(l['qty_ratio'] for l in L), q([l['qty_ratio'] for l in L], .1), q([l['qty_ratio'] for l in L], .5), q([l['qty_ratio'] for l in L], .9), max(l['qty_ratio'] for l in L)])
        e = S[f'{lv}|{m}']; ok = {}
        for k, v in mine.items():
            ev = {'abs_dt': e['abs_dt_s'], 'otm': e['otm_distance']}.get(k) or e[k]; ev = [ev[x] for x in ('min', 'p10', 'median', 'p90', 'max')]; ok[k] = all(abs(a - b) < 1e-6 for a, b in zip(ev, v))
        chk[f'{lv}|{m}'] = ok
out['distribution_equal_to_committed_summary'] = chk
json.dump(out, open('scope_probe_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
