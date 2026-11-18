"""Re-derive headline numbers from RAW via own replay [RAW][IMPL]; compare to committed m2d_summary.json and report text claims."""
import json, collections
import load_raw, ref_wing_body as R
F = load_raw.load(); A = R.analyse(F); I = A['items']; P = A['portions']; out = {}
S = json.load(open('/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2d_data/m2d_summary.json'))
out['replay_units'] = dict(open_portions=sum(1 for p in P if p['kind'] == 'OPEN'), open_units=sum(p['qty'] for p in P if p['kind'] == 'OPEN'), close_portions=sum(1 for p in P if p['kind'] == 'CLOSE'), close_units=sum(p['qty'] for p in P if p['kind'] == 'CLOSE'), fills=len(F), fill_units=sum(f['qty'] for f in F))
def cov(level, method):
    W = [i for i in I.values() if i.level == level and i.role == 'WING']; B = [i for i in I.values() if i.level == level and i.role == 'BODY']; L = A['links'][method]; L = [l for l in L if l['level'] == level]
    wl = collections.Counter(l['wing'] for l in L); bl = collections.Counter(l['body'] for l in L); wu = sum(i.qty for i in W); bu = sum(i.qty for i in B)
    r = dict(wing_items=len(W), body_items=len(B), wing_units=wu, body_units=bu, wing_with=len(wl), wing_unique=sum(1 for v in wl.values() if v == 1), wing_multi=sum(1 for v in wl.values() if v > 1), wing_none=len(W) - len(wl),
             wing_units_unmatched=wu - sum(I[k].qty for k in wl), body_with=len(bl), body_without=len(B) - len(bl), body_units_without=bu - sum(I[k].qty for k in bl), links=len(L))
    return r
out['coverage'] = {f'{lv}|{m}': cov(lv, m) for lv in ('OPENING', 'CLOSING') for m in ('W1', 'W1_S60')}
out['W3_resid'] = A['w3_resid']
w3 = A['links']['W3']; ww = set(l['wing'] for l in w3); out['W3_wings_with_segment'] = len(ww); out['W3_links'] = len(w3)
# group level
g = collections.defaultdict(lambda: [0, 0])
for i in I.values():
    g[i.grp + (i.emin,)][0 if i.role == 'WING' else 1] += i.qty
res = {}
for lv in ('OPENING', 'CLOSING'):
    gs = [v for k, v in g.items() if k[0] == lv]; both = [v for v in gs if v[0] and v[1]]; ex = [v for v in both if v[0] == v[1]]
    res[lv] = dict(groups=len(gs), both=len(both), wing_only=sum(1 for v in gs if v[0] and not v[1]), body_only=sum(1 for v in gs if v[1] and not v[0]), wing_units_wing_only=sum(v[0] for v in gs if v[0] and not v[1]), body_units_body_only=sum(v[1] for v in gs if v[1] and not v[0]),
                   exact_share_both=len(ex) / len(both), exact_share_all=len(ex) / len(gs), wing_units_in_exact=sum(v[0] for v in ex) / sum(v[0] for v in gs), lt1=sum(1 for v in both if v[0] < v[1]) / len(both), gt1=sum(1 for v in both if v[0] > v[1]) / len(both))
out['group_level'] = res
# exclusions (tagged scope) by tag
ex = collections.defaultdict(int)
for p in P:
    f = p['fill']; d = p['dir']; ok = (d == 1 and f['tag'] == 'h_') or (d == -1 and f['tag'] == 'num')
    if not ok: ex[(('OPENING' if p['kind'] == 'OPEN' else 'CLOSING'), 'LONG' if d == 1 else 'SHORT', f['tag'])] += p['qty']
out['exclusions'] = {'|'.join(k): v for k, v in sorted(ex.items())}
out['exclusion_totals'] = dict(closing=sum(v for k, v in ex.items() if k[0] == 'CLOSING'), opening=sum(v for k, v in ex.items() if k[0] == 'OPENING'))
# closing wing origin: opening modules of the episode being closed. Need episode id => replay episodes
inv = collections.defaultdict(int); ep = collections.defaultdict(int); epmods = collections.defaultdict(set); cp_ep = {}
for f in sorted(F, key=lambda f: (f['ts'], f['row'])):
    i = f['inst']; cur = inv[i]; q = f['qty']; s = f['sgn']
    if cur != 0 and (cur > 0) != (s > 0):
        cp_ep[f['row']] = (i, ep[i]); c = min(q, abs(cur))
        if q - c > 0: ep[i] += 1; epmods[(i, ep[i])].add(f['tag'])
    else:
        if cur == 0: ep[i] += 1
        epmods[(i, ep[i])].add(f['tag'])
    inv[i] = cur + s * q
    if inv[i] == 0 and False: pass
# note: ep increments when opening from flat (cur==0) -- ensure consistent with closing to flat then reopen
o = collections.defaultdict(int)
for p in P:
    if p['kind'] != 'CLOSE': continue
    f = p['fill']
    if not (p['dir'] == 1 and f['tag'] == 'h_'): continue
    mods = epmods[cp_ep[f['row']]]; o['opened_only_by_h_' if mods == {'h_'} else ('opened_by_mixed_modules' if 'h_' in mods else 'opened_without_h_')] += p['qty']
out['closing_wing_origin'] = dict(o)
# app key shares (wing opening)
wa = collections.defaultdict(lambda: [0, 0]); app = {f['parent']: f['app'] for f in F}
for i in I.values():
    if i.level == 'OPENING' and i.role == 'WING': wa[app[i.parent]][0] += 1; wa[app[i.parent]][1] += i.qty
out['wing_app_key'] = dict(wa); tot = sum(v[1] for v in wa.values()); out['second_key_unit_share'] = sum(v[1] for k, v in wa.items() if k != '632469') / tot; out['second_key_item_share'] = sum(v[0] for k, v in wa.items() if k != '632469') / sum(v[0] for v in wa.values())
# app key across all fills
ak = collections.Counter(); akp = collections.defaultdict(set)
for f in F: ak[(f['tag'], f['app'])] += 1
out['app_key_by_tag_rows'] = {f'{a}|{b}': v for (a, b), v in sorted(ak.items())}
# stop-closed bodies not in short-body: closing portions closing a SHORT episode with tag s_
sb = collections.defaultdict(int); seed = collections.defaultdict(int)
for p in P:
    f = p['fill']
    if p['kind'] == 'CLOSE' and p['dir'] == -1 and f['tag'] == 's_': sb['stop_closed_short_units'] += p['qty']
    if p['kind'] == 'OPEN' and p['dir'] == 1 and f['tag'] == 'num': seed['long_num_open_units'] += p['qty']
out['stop_closed_short_units'] = dict(sb); out['long_num_open_units'] = dict(seed)
json.dump(out, open('headline_result.json', 'w'), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
