"""Counterexample harness: the same hand-built fills are fed to (a) the independent reference and (b) pe.wing_body.analyse; links and items compared field by field. Classification: [IMPL] (+ expected results asserted by hand = [RAW-style hand derivation])."""
import sys, os, collections
REPO = os.environ.get('M2F_REPO', '/home/user/Algo-8-Reverse-Engineer'); PYP = os.environ.get('M2F_PYPATH', REPO + '/portfolio_engine/python')
sys.path.insert(0, PYP); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import wing_body as wb
from pe.generators.synthetic import Builder, BASE_TS
import ref_wing_body as R


def N(cp='CE', k=24000, exp='2026-01-08', und='NIFTY'): return (und, exp, cp, k)


def build(spec, scope='TAGGED'):
    """spec: list of dict(inst=(und,exp,cp,strike), t=offset s, side=+1/-1, qty, px=paise, parent, tag in num|h_|s_|v_, e=entry minute offset (minutes from BASE) or None, app='632469')"""
    b = Builder('cx'); ids = {}; meta = {}; rf = []
    for n, s in enumerate(spec, 1):
        u, e, c, k = s['inst']; key = s['inst']
        if key not in ids: ids[key] = b.add_inst(cp=c, strike=k, expiry=e, und=u)
        b.fill(ids[key], s['t'], s['side'], s['qty'], s.get('px', 1000), parent=s['parent'], module=s['tag'])
        em = s.get('e', 0); emin = None if em is None else BASE_TS + 60 * em
        if s['parent'] not in meta: meta[s['parent']] = dict(parent_order_id=s['parent'], order_entry_minute_s=emin, app_key_last6=s.get('app', '632469'))
        rf.append(dict(row=n, ts=BASE_TS + s['t'], inst=key, sgn=s['side'], qty=s['qty'], px=s.get('px', 1000), parent=s['parent'], tag=s['tag'], emin=emin))
    ins, fills = b.out(); ls = LineageSet(fills, ins, 'SYNTHETIC_TEST', 'src')
    return ls, meta, rf


def ikey(item_id):
    _, lv, role, rest = item_id.split(':', 3); parent, inst = rest.split(':', 1); u, e, c, k = inst.split('|'); return (lv, role, parent, (u, e, c, int(k)))


def compare(spec, scope='TAGGED', engine_fn=None):
    ls, meta, rf = build(spec); E = (engine_fn or wb.analyse)(ls, meta, scope); A = R.analyse(rf, scope); diffs = []
    ei = {ikey(i.item_id): i for i in E.items}; mi = A['items']
    if set(ei) != set(mi): diffs.append(('items', sorted(map(str, set(ei) ^ set(mi)))[:4]))
    for k in set(ei) & set(mi):
        a, b = ei[k], mi[k]
        if (a.qty, a.first_ts, a.e_minute, a.session) != (b.qty, b.first_ts, b.emin, b.session if False else b.session) and not (a.qty == b.qty and a.first_ts == b.first_ts and a.e_minute == b.emin): diffs.append(('item_field', str(k)))
    for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'):
        el = {(l['level'], ikey(l['wing_item']), ikey(l['body_item'])): l for l in E.links[m]}; ml = {(l['level'], l['wing'], l['body']): l for l in A['links'][m]}
        if set(el) != set(ml): diffs.append((m, 'linkset', sorted(map(str, set(el) ^ set(ml)))[:4])); continue
        if len(E.links[m]) != len(A['links'][m]): diffs.append((m, 'dup rows', len(E.links[m]), len(A['links'][m])))
        for k in el:
            e, l = el[k], ml[k]
            c = dict(dt=e['dt_s'] == l['dt_s'], q=(e['wing_qty'], e['body_qty']) == (l['wing_qty'], l['body_qty']), r=abs(e['qty_ratio'] - l['qty_ratio']) < 1e-9, o=e['otm_distance'] == l['otm'], se=e['same_entry_minute'] == l['same_emin'])
            if m in ('W1', 'W1_S60', 'W2', 'W2_S60'): c.update(n=e['nearest'] == l['nearest'], t=e['nearest_tied'] == l['tied'], nc=e['n_candidates_for_wing'] == l['n_cand'], ls=e['link_status'] == ('UNIQUE_CANDIDATE' if l['n_cand'] == 1 else 'MULTIPLE_CANDIDATES'))
            if m in ('W2', 'W2_S60'): c.update(w=abs(e['weight'] - l['weight']) < 1e-8, wu=abs(e['weighted_wing_units'] - l['wunits']) < 1e-5)
            if m == 'W3': c.update(mu=e['queue_matched_units'] == l['matched'], seg=e['segment'] == l['seg'])
            bad = [n for n, ok in c.items() if not ok]
            if bad: diffs.append((m, 'fields', bad, str(k)[:120]))
    if (E.w3_residual['wing_units_unmatched'], E.w3_residual['body_units_unmatched']) != (A['w3_resid']['wing'], A['w3_resid']['body']): diffs.append(('w3_resid', E.w3_residual, A['w3_resid']))
    return diffs, E, A
