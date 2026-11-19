"""Behavioural fidelity of Algo 8 decision engine v1 on the 35 live cycles (IN-SAMPLE: parameters were extracted from these cycles). Same comparison engine and pre-registered classes as Mode 2.
Outputs -> outputs/v1_parity_*.csv ; compares with the earlier R1/R2 results in outputs/mode2_*.csv"""
import sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import ref, compare as C, algo8_v1 as V
sys.path.insert(0, ref.REPL)
import data
from bt import cycles as Cy
F = ref.load_fills(); O = ref.orders(F); O['j'] = O.j.clip(0, 374); O['day'] = O.dayno; cyc = pd.read_csv(ref.CYCLES); cl = Cy.cycle_list(); ev_all = []; meta = []
for r in cyc.itertuples():
    m = cl[(cl.und == r.und) & (cl.expiry == r.expiry)].iloc[0]; c = data.load_cycle(r.und, r.expiry, m.d1, m.d0); lp = V.build(c, r.und).run(); e = V.events(lp); e['und'] = r.und; e['expiry'] = r.expiry; ev_all.append(e)
    meta.append(dict(und=r.und, expiry=r.expiry, **V.result(lp, c, r.und)))
SE = pd.concat(ev_all, ignore_index=True); SE['cp'] = SE.right; SE['lots'] = 1; SE['day'] = SE.d; pd.DataFrame(meta).to_csv(f'{ref.OUT}/v1_parity_cycles.csv', index=False)
ok1 = {(r.und, r.expiry) for r in cyc.itertuples() if r.has_d1}; ok0 = {(r.und, r.expiry) for r in cyc.itertuples() if r.has_d0}
def act(mod, side, day, sched=None):
    x = O[(O.module == mod) & (O.side == side) & (O.dayno == day)]; x = x[[(u, e) in (ok1 if day == 0 else ok0) for u, e in zip(x.und, x.expiry)]]
    if sched is True: x = x[(((x.j - 1) % 15) < 3) & (((x.j - 1) // 15) < 17) & (x.j >= 1)]
    return x
def sim(role, side, day, tags=None):
    x = SE[(SE.role == role) & (SE.side == side) & (SE.d == day)]
    if tags: x = x[x.tag.isin(tags)]
    return x
CATS = [('D-1 body entries (17 ladder slots, first 3 min)', sim('body', -1, 0, ['ENTRY']), act('num', 'Sell', 0, True), 1), ('D-1 body entries (all original D-1 body sells)', sim('body', -1, 0, ['ENTRY']), act('num', 'Sell', 0), 1), ('D-1 wing entries', sim('wing', 1, 0, ['ENTRY']), act('h_', 'Buy', 0), 1),
        ('D-1 body buy-backs', sim('body', 1, 0), act('num', 'Buy', 0), 2), ('D0 body entries', sim('body', -1, 1, ['ENTRY']), act('num', 'Sell', 1), 1), ('D0 body buy-backs', sim('body', 1, 1), act('num', 'Buy', 1), 2), ('D0 wing sells', sim('wing', -1, 1), act('h_', 'Sell', 1), 2), ('D0 wing entries', sim('wing', 1, 1, ['ENTRY']), act('h_', 'Buy', 1), 1)]
rows = []
for name, s, a, tol in CATS:
    ok = ok1 if name.startswith('D-1') else ok0; s = s[[(u, e) in ok for u, e in zip(s.und, s.expiry)]]; s = s[['und', 'expiry', 'cp', 'strike', 'lots', 'j', 'day']]; a = a[['und', 'expiry', 'cp', 'strike', 'lots', 'j', 'day']]
    for sm in ('any', 'same'):
        o = C.agree_with_null(s, a, tol, sm, ndraw=30); rows.append(dict(category=name, strike_mode=sm, tol_min=tol, **{k: o[k] for k in ('matched', 'n_sim', 'n_act', 'P', 'R', 'null_P', 'lift_P')}, cls=C.classify(o)))
A_ = pd.DataFrame(rows); A_.to_csv(f'{ref.OUT}/v1_parity_event_agreement.csv', index=False)
inv = []
for r in cyc[cyc.carry_in_known].itertuples():
    ka, Ma = ref.inventory_minute_grid(F, (r.und, r.expiry)); e = SE[(SE.und == r.und) & (SE.expiry == r.expiry)].copy(); e['sl'] = e.side; ks, Ms = C.path_from_events(e); res = C.inventory_compare(ka, Ma[:, :750], ks, Ms)
    a374, s374 = res['A'][:, 374], res['S'][:, 374]; inv.append(dict(und=r.und, expiry=r.expiry, active=res['active'], exact=res['exact'], nmae=res['nmae'], short_end_d1_actual=float(-a374[a374 < 0].sum()), short_end_d1_sim=float(-s374[s374 < 0].sum())))
I = pd.DataFrame(inv); I.to_csv(f'{ref.OUT}/v1_parity_inventory.csv', index=False)
pd.set_option('display.width', 250); print(A_[A_.strike_mode == 'any'].round(3).to_string(index=False)); print('inventory exact share mean', I.exact.mean().round(3), 'nmae median', I.nmae.median().round(3), 'overnight shorts actual/sim', I.short_end_d1_actual.mean().round(1), I.short_end_d1_sim.mean().round(1))
M = pd.DataFrame(meta); print('cycle stops', int(M.cycle_stop.sum()), 'of', len(M), '(actual 12 of 35); mean orders per cycle', M.n_orders.mean().round(0), '; original mean orders per cycle', round(len(O) / 35))
