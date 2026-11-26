"""Validation of the standalone package d1_strategy/algo8_d1.py against (1) the research simulator bl_fr_sim.py on identical parameters and (2) the real D-1 ledger.
Parameters are fitted on all 32 cycles (in-sample): this checks that the clean code reproduces the research simulator, not out-of-sample accuracy (see D1_FORWARD.md: 0.63 on unseen cycles).
Outputs bl_d1pkg_equivalence.csv, bl_d1pkg_scores.csv, bl_summary_d1pkg.json"""
import sys, warnings, json; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_fr_sim as S
import algo8_d1 as A
CY, REAL = S.CY, S.REAL
CLASS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'opening_wings', ('v_', 'open_long'): 'lump'}
REAL['cls'] = [CLASS.get((m, r_), 'not_modelled') for m, r_ in zip(REAL.module, REAL.role)]; REAL.loc[(REAL.cls == 'opening_wings') & (REAL.j > 2), 'cls'] = 'not_modelled'
NMOD = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'opening_wings', 'lump']; TOL = {c: 1 for c in NMOD}; TOL['lump'] = 3
lots_of = lambda df: df.loc[df.index.repeat(df.lots.astype(int))]
RL = {}
for i, r in enumerate(CY.itertuples()):
    z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry)]
    for (cls, cp), g in z.groupby(['cls', 'cp']): g = lots_of(g); RL[(i, cls, cp)] = (g.j.values.astype(int), g.strike.values.astype(float))
def match(rj, rk, sj, sk, tol):
    bucket = {}
    for n, j in enumerate(sj): bucket.setdefault(int(j), []).append(n)
    used = np.zeros(len(sj), bool); done = np.zeros(len(rj), bool); dk = []
    for ps in range(tol + 1):
        for a in range(len(rj)):
            if done[a]: continue
            best = None
            for jj in ({rj[a]} if ps == 0 else {rj[a] - ps, rj[a] + ps}):
                for n in bucket.get(int(jj), []):
                    if used[n]: continue
                    d = abs(sk[n] - rk[a])
                    if best is None or d < best[0]: best = (d, n)
            if best: used[best[1]] = True; done[a] = True; dk.append(best[0])
    return np.array(dk)
def score(orders, cids):
    rows = {c: dict(real=0, sim=0, tp=0, exact=0, within1=0) for c in NMOD + ['not_modelled']}
    for i in cids:
        o = orders[i]; ol = lots_of(o) if len(o) else o; st = ref.STEP[CY.iloc[i].und]
        for cls in NMOD + ['not_modelled']:
            for cp in ('CE', 'PE'):
                rj, rk = RL.get((i, cls, cp), (np.array([], int), np.array([], float))); rows[cls]['real'] += len(rj)
                if cls == 'not_modelled' or not len(ol): continue
                g = ol[(ol.cls == cls) & (ol.cp == cp)]; rows[cls]['sim'] += len(g)
                if len(rj) and len(g):
                    dk = match(rj, rk, g.j.values.astype(int), g.strike.values.astype(float), TOL[cls]); rows[cls]['tp'] += len(dk); rows[cls]['exact'] += int((dk == 0).sum()); rows[cls]['within1'] += int((dk <= st).sum())
    return rows
f1 = lambda tp, sim, real: 2 * tp / max(sim + real, 1)
# ---- parameters fitted on all cycles (same procedure as bl_fr_score.fit_params)
F = pd.read_csv(f'{OUT}/bl_sd_reactlots.csv'); LP = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); ids = list(range(len(CY)))
b_, a_ = np.polyfit(F.depth.clip(-0.5, 3), F.extra_fav, 1); lm = LP[(LP.main == 1)]; ratio = {u: float((g.lots / g.S_h).median()) for u, g in lm.groupby('und')}
cyr = CY.assign(regime=CY.d1.map(S.regime)); lj = {rg: int(np.median(((LP[(LP.main == 1) & LP.cid.isin([i for i in ids if cyr.regime.iloc[i] == rg])].t - 33300) // 60))) for rg in ('r1', 'r2', 'r3')}
oo = {}
for u in ('NIFTY', 'SENSEX'):
    for v in ('V1', 'V2'):
        offs = []
        for i in [i for i in ids if CY.iloc[i].und == u and CY.iloc[i].version == v]:
            r = CY.iloc[i]; z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry) & (REAL.cls == 'opening_wings')]; c0 = S.OH[(r.und, r.expiry)].close.values[0]
            offs += list(((z.strike - c0) / ref.STEP[u] * np.where(z.cp == 'CE', 1, -1)).values)
        oo[(u, v)] = float(np.median(offs))
P = dict(a=float(a_), b=float(b_), k=0.025, lump_z=2.2, lump_ratio=ratio, lump_t=lj, open_off=oo, tp=0.4, theta=1.5)
print('fitted on all cycles', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
def pkg_orders(i, stop_price, stop_ratio, exact):
    r = CY.iloc[i]; d = S.prep(i); cfg = A.config_for(r.und, r.d1); cfg.stop_price = stop_price; cfg.stop_ratio = stop_ratio
    if exact: cfg.extra_a, cfg.extra_b, cfg.lump_ratio, cfg.lump_minute, cfg.opening_wing_offset_steps = P['a'], P['b'], ratio[r.und], lj[S.regime(r.d1)], oo[(r.und, r.version)]
    chain = A.OptionChain(d['K'], {k: v for k, v in d['op'].items() if isinstance(k, tuple)}); o = S.OH[(r.und, r.expiry)]
    res = A.D1Strategy(cfg).run(o.open.values, o.high.values, o.low.values, o.close.values, chain)
    m = {'scheduled_straddle': 'body_sell', 'breakout_straddle': 'body_sell', 'breakout_extra': 'body_sell', 'ladder_solo': 'body_sell', 'stop_buyback': 'body_buyback', 'protective_wing_buy': 'wing_buy', 'protective_wing_sell': 'wing_sell', 'opening_wing_buy': 'opening_wings', 'overnight_lump': 'lump'}
    return pd.DataFrame([dict(cid=i, cls=m[x.role], cp=x.right, j=x.minute, strike=x.strike, lots=x.lots, step=cfg.strike_step) for x in res.orders]), res
# ---- (1) equivalence with the research simulator (same parameters: prev-close stop at 1.5x)
eq = []; RES = {}; PKG = {}
for i in ids:
    ro = S.sim_cycle(i, P, 'free')[0]; po, _ = pkg_orders(i, 'prev_close', 1.5, True)
    key = lambda df: sorted((c_, p_, int(j_), float(k_)) for c_, p_, j_, k_, n_ in zip(df.cls, df.cp, df.j, df.strike, df.lots) for _ in range(int(n_))) if len(df) else []          # one entry per lot
    a_k, b_k = key(ro), key(po); eq.append(dict(cid=i, research_rows=len(a_k), package_rows=len(b_k), identical=a_k == b_k, only_research=len(set(a_k) - set(b_k)), only_package=len(set(b_k) - set(a_k))))
    RES[i] = ro; PKG[i] = po
EQ = pd.DataFrame(eq); EQ.to_csv(f'{OUT}/bl_d1pkg_equivalence.csv', index=False); print('identical cycles', int(EQ.identical.sum()), 'of', len(EQ)); print(EQ[~EQ.identical].to_string(index=False))
# ---- (2) scores vs the real ledger
rows = []; R = dict(identical_cycles=int(EQ.identical.sum()), cycles=len(EQ))
variants = {'research simulator (prev-close stop 1.5x)': RES, 'package, same parameters (prev-close stop 1.5x)': PKG}
hi = {i: pkg_orders(i, 'high', 1.6, True)[0] for i in ids}; variants['package, intrabar stop 1.6x (minute high)'] = hi
dflt = {i: pkg_orders(i, 'high', 1.6, False)[0] for i in ids}; variants['package defaults as shipped (rounded constants, stop 1.6x on minute high)'] = dflt
for nm, od in variants.items():
    sc = score(od, ids); tp = sum(sc[c]['tp'] for c in NMOD); sm = sum(sc[c]['sim'] for c in NMOD); rl = sum(sc[c]['real'] for c in sc); ex = sum(sc[c]['exact'] for c in NMOD); w1 = sum(sc[c]['within1'] for c in NMOD)
    rows.append(dict(variant=nm, cls='ALL', real_lots=rl, sim_lots=sm, matched=tp, precision=tp / sm, recall=tp / rl, F1=f1(tp, sm, rl), F1_strike_within_one=f1(w1, sm, rl), F1_exact_strike=f1(ex, sm, rl)))
    for c in NMOD: d = sc[c]; rows.append(dict(variant=nm, cls=c, real_lots=d['real'], sim_lots=d['sim'], matched=d['tp'], precision=d['tp'] / max(d['sim'], 1), recall=d['tp'] / max(d['real'], 1), F1=f1(d['tp'], d['sim'], d['real']), F1_strike_within_one=f1(d['within1'], d['sim'], d['real']), F1_exact_strike=f1(d['exact'], d['sim'], d['real'])))
SC = pd.DataFrame(rows); SC.round(4).to_csv(f'{OUT}/bl_d1pkg_scores.csv', index=False); print(SC[SC.cls == 'ALL'].round(3).to_string(index=False)); print(SC[SC.variant.str.startswith('package defaults')].round(3).to_string(index=False))
R['scores_all'] = SC[SC.cls == 'ALL'].round(4).to_dict('records'); R['scores_defaults_by_class'] = SC[SC.variant.str.startswith('package defaults')].round(4).to_dict('records'); rec('d1pkg', R)
