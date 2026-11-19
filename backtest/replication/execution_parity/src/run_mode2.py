"""MODE 2 (fully simulated): the reconstructed engine (R1 / R2 rules) generates its own events on the same market data; compare with the original on the 35 live cycles.
All numbers are IN-SAMPLE (rules were read from these cycles). Outputs -> outputs/mode2_*.csv"""
import os, sys, json
import numpy as np, pandas as pd
import ref, compare as C
sys.path.insert(0, ref.REPL)
import runner, data, sim
from bt import cycles as Cy
F = ref.load_fills(); O = ref.orders(F); O['j'] = O.j.clip(0, 374); O['day'] = O.dayno
cyc = pd.read_csv(ref.CYCLES); cl = Cy.cycle_list(); d0l = sim.d0_median_ladder(); LOTU = ref.LOT
# ---------------------------------------------------------------- simulate
sim_ev = []; sim_meta = []
for r in cyc.itertuples():
    m = cl[(cl.und == r.und) & (cl.expiry == r.expiry)].iloc[0]; c = data.load_cycle(r.und, r.expiry, m.d1, m.d0)
    for v in ('R1', 'R2'):
        lp = runner.build(c, r.und, v, d0l).run(); e = runner.events(lp); e['variant'] = v; e['und'] = r.und; e['expiry'] = r.expiry; sim_ev.append(e)
        sim_meta.append(dict(variant=v, und=r.und, expiry=r.expiry, stopped=lp.stopped is not None, stop_day=None if lp.stopped is None else lp.stopped[0], stop_j=None if lp.stopped is None else lp.stopped[1], open_at_end=len(lp.state.lots), no_market=len(lp.no_market)))
SE = pd.concat(sim_ev, ignore_index=True); SE['cp'] = SE.right; SE['lots'] = 1; SE['day'] = SE.d; SE.to_csv(f'{ref.OUT}/mode2_sim_events.csv.gz', index=False); pd.DataFrame(sim_meta).to_csv(f'{ref.OUT}/mode2_sim_meta.csv', index=False)
# ---------------------------------------------------------------- event agreement
have = {(r.und, r.expiry): (r.has_d1, r.has_d0, r.carry_in_known) for r in cyc.itertuples()}
O['has_d1'] = [have[(u, e)][0] for u, e in zip(O.und, O.expiry)]; O['has_d0'] = [have[(u, e)][1] for u, e in zip(O.und, O.expiry)]
def sub(S, v, role, side, tag_in=None, day=None, cyc_flag=None):
    x = S[(S.variant == v) & (S.role == role) & (S.side == side)]
    if tag_in is not None: x = x[x.tag.isin(tag_in)]
    if day is not None: x = x[x.d == day]
    return x
def act(mod, side, day, sched=None):
    x = O[(O.module == mod) & (O.side == side) & (O.dayno == day) & (O['has_d1' if day == 0 else 'has_d0'])]
    if sched is True: x = x[((x.j - 1) % 15) < 3]
    if sched is False: x = x[((x.j - 1) % 15) >= 3]
    return x
rows = []
CATS = [  # name, sim selector, actual selector, tolerance (min), tag
    ('D-1 body entries (all original D-1 body sells)', lambda S, v: sub(S, v, 'body', -1, ['ENTRY'], 0), lambda: act('num', 'Sell', 0), 1),
    ('D-1 body entries (original sells inside the 17 scheduled windows only)', lambda S, v: sub(S, v, 'body', -1, ['ENTRY'], 0), lambda: act('num', 'Sell', 0, True), 1),
    ('D-1 wing entries (h_ Buy)', lambda S, v: sub(S, v, 'wing', 1, ['ENTRY'], 0), lambda: act('h_', 'Buy', 0), 1),
    ('D-1 body buy-backs', lambda S, v: sub(S, v, 'body', 1, None, 0), lambda: act('num', 'Buy', 0), 2),
    ('D-1 wing sells (h_ Sell)', lambda S, v: sub(S, v, 'wing', -1, None, 0), lambda: act('h_', 'Sell', 0), 2),
    ('D0 body entries (num Sell)', lambda S, v: sub(S, v, 'body', -1, ['ENTRY'], 1), lambda: act('num', 'Sell', 1), 1),
    ('D0 body buy-backs', lambda S, v: sub(S, v, 'body', 1, None, 1), lambda: act('num', 'Buy', 1), 2),
    ('D0 wing sells (h_ Sell)', lambda S, v: sub(S, v, 'wing', -1, None, 1), lambda: act('h_', 'Sell', 1), 2),
]
for v in ('R1', 'R2'):
    S = SE
    for name, fs, fa, tol in CATS:
        s = fs(S, v)[['und', 'expiry', 'cp', 'strike', 'lots', 'j', 'day']].copy(); a = fa()[['und', 'expiry', 'cp', 'strike', 'lots', 'j', 'day']].copy()
        # restrict the simulation to the cycles that have the original session
        keep = set(zip(a.und, a.expiry)) | set(); dkey = 'has_d1' if 'D-1' in name else 'has_d0'
        ok = {(r.und, r.expiry) for r in cyc.itertuples() if (r.has_d1 if 'D-1' in name else r.has_d0)}; s = s.loc[np.array([(u, e) in ok for u, e in zip(s.und, s.expiry)], dtype=bool)]
        for strike in ('any', 'same'):
            for t in sorted({0, 1, 2, 5, tol}):
                pass
                o = C.agree_with_null(s, a, t, strike, ndraw=40) if t == tol else C.agree(s, a, t, strike)
                if t != tol: o.update(null_P=np.nan, null_R=np.nan, lift_P=np.nan, lift_R=np.nan)
                rows.append(dict(variant=v, category=name, strike_mode=strike, tol_min=t, primary=(t == tol), cls=C.classify(o) if t == tol else '', **{k: o[k] for k in ('matched', 'n_sim', 'n_act', 'P', 'R', 'null_P', 'null_R', 'lift_P', 'lift_R')}))
A = pd.DataFrame(rows); A.to_csv(f'{ref.OUT}/mode2_event_agreement.csv', index=False)
# ---------------------------------------------------------------- inventory path (30 complete cycles)
inv = []; per_t = []
for r in cyc[cyc.carry_in_known].itertuples():
    keys_a, Ma = ref.inventory_minute_grid(F, (r.und, r.expiry))
    Ma = np.concatenate([Ma[:, :375], Ma[:, 385:385 + 375]], axis=1) if Ma.shape[1] >= 385 + 375 else Ma
    for v in ('R1', 'R2'):
        e = SE[(SE.variant == v) & (SE.und == r.und) & (SE.expiry == r.expiry)].copy(); e['sl'] = e.side
        keys_s, Ms = C.path_from_events(e) if len(e) else ([], np.zeros((0, 750)))
        res = C.inventory_compare(keys_a, Ma[:, :750] if Ma.shape[1] >= 750 else Ma, keys_s, Ms)
        inv.append(dict(variant=v, und=r.und, expiry=r.expiry, **{k: res[k] for k in ('active', 'exact', 'mae', 'nmae', 'mean_abs_actual')}))
        if res['active']:
            Aa, Ss = res['A'], res['S']; T = Aa.shape[1]
            for b0 in range(0, T, 75):
                msk = ((Aa[:, b0:b0 + 75] != 0) | (Ss[:, b0:b0 + 75] != 0))
                if msk.sum(): per_t.append(dict(variant=v, und=r.und, expiry=r.expiry, bin=b0 // 75, active=int(msk.sum()), abs_diff_sum=float(np.abs(Aa[:, b0:b0 + 75] - Ss[:, b0:b0 + 75])[msk].sum()), abs_actual_sum=float(np.abs(Aa[:, b0:b0 + 75])[msk].sum())))
I = pd.DataFrame(inv); I.to_csv(f'{ref.OUT}/mode2_inventory_by_cycle.csv', index=False); pd.DataFrame(per_t).to_csv(f'{ref.OUT}/mode2_inventory_by_time.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70)
print(A[A.primary & (A.variant == 'R1')][['category', 'strike_mode', 'tol_min', 'n_sim', 'n_act', 'matched', 'P', 'R', 'lift_P', 'lift_R', 'cls']].round(3).to_string(index=False))
print(I.groupby('variant').apply(lambda d: pd.Series(dict(cycles=len(d), exact_share_mean=d.exact.mean(), nmae_median=d.nmae.median(), nmae_mean=d.nmae.mean()))).round(3))
