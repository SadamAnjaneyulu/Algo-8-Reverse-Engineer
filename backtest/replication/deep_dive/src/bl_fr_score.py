"""Free-running D-1 reconstruction vs the real ledger (plan reports/D1_FREE_RUN_PLAN.md): out-of-fold parameters (two cycle halves), lot matching, class and overall scores, book scores.
Outputs bl_fr_classes.csv, bl_fr_overall.csv, bl_fr_cycles.csv, bl_fr_book.csv, bl_fr_carry.csv, bl_fr_params.csv, bl_fr_orders.pkl.gz, bl_summary_fr1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_fr_sim as S
CY, REAL = S.CY, S.REAL; F = pd.read_csv(f'{OUT}/bl_sd_reactlots.csv'); LP = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); R = {}
CLASS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'opening_wings', ('v_', 'open_long'): 'lump'}
REAL['cls'] = [CLASS.get((m, r_), 'not_modelled') for m, r_ in zip(REAL.module, REAL.role)]
# opening wings = body-stream longs at j <= 2; the later body longs (15:15 flatten rebuy) are not modelled
REAL.loc[(REAL.cls == 'opening_wings') & (REAL.j > 2), 'cls'] = 'not_modelled'
NMOD = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'opening_wings', 'lump']; TOL = {c: 1 for c in NMOD}; TOL['lump'] = 3
def lots_of(df):                                    # one row per lot
    return df.loc[df.index.repeat(df.lots.astype(int))]
RL = {}                                             # real lots by (cid, cls, cp)
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
def score(orders, cids, step_of):
    rows = {}
    for cls in NMOD + ['not_modelled']: rows[cls] = dict(real=0, sim=0, tp=0, exact=0, within1=0)
    for i in cids:
        o = orders[i]; ol = lots_of(o) if len(o) else o
        for cls in NMOD + ['not_modelled']:
            for cp in ('CE', 'PE'):
                rj, rk = RL.get((i, cls, cp), (np.array([], int), np.array([], float))); rows[cls]['real'] += len(rj)
                if cls == 'not_modelled' or not len(ol): continue
                g = ol[(ol.cls == cls) & (ol.cp == cp)]; rows[cls]['sim'] += len(g)
                if len(rj) and len(g):
                    dk = match(rj, rk, g.j.values.astype(int), g.strike.values.astype(float), TOL[cls]); rows[cls]['tp'] += len(dk); rows[cls]['exact'] += int((dk == 0).sum()); rows[cls]['within1'] += int((dk <= step_of(i)).sum())
    return rows
step_of = lambda i: ref.STEP[CY.iloc[i].und]
def f1(tp, sim, real): return 2 * tp / max(sim + real, 1)
# ---------------- parameter fitting (per fold)
def fit_params(tr):
    f = F[F.cid.isin(tr)]; b, a = np.polyfit(f.depth.clip(-0.5, 3), f.extra_fav, 1)
    lm = LP[(LP.main == 1) & LP.cid.isin(tr)]; ratio = {u: float((g.lots / g.S_h).median()) for u, g in lm.groupby('und')}
    cyr = CY.assign(regime=CY.d1.map(S.regime)); lj = {}
    for rg in ('r1', 'r2', 'r3'):
        ids_ = [i for i in range(len(CY)) if cyr.regime.iloc[i] == rg]; m = LP[(LP.main == 1) & LP.cid.isin(ids_)]; mt = m[m.cid.isin(tr)]
        lj[rg] = int(np.median(((mt if len(mt) else m).t - 33300) // 60))
    oo = {}
    for u in ('NIFTY', 'SENSEX'):
        for v in ('V1', 'V2'):
            ids_ = [i for i in tr if CY.iloc[i].und == u and CY.iloc[i].version == v]; offs = []
            for i in ids_:
                r = CY.iloc[i]; z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry) & (REAL.cls == 'opening_wings')]; c0 = S.OH[(r.und, r.expiry)].close.values[0]
                offs += list(((z.strike - c0) / ref.STEP[u] * np.where(z.cp == 'CE', 1, -1)).values)
            oo[(u, v)] = float(np.median(offs)) if offs else np.nan
    for k, v in oo.items():
        if v != v: oo[k] = float(np.nanmedian([x for kk, x in oo.items() if kk[0] == k[0]]))
    return dict(a=float(a), b=float(b), k=0.025, lump_z=2.2, lump_ratio=ratio, lump_t=lj, open_off=oo)
def run(cids, P, mode, late=False): return {i: S.sim_cycle(i, P, mode, late) for i in cids}
OO = lambda d: {i: t[0] for i, t in d.items()}
ids = list(range(len(CY))); OUTALL = {}; PARAMS = []; FULL = {}
def fit_and_score(mode, late=False):
    allorders = {}; chosen = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P['tp'] = 0.4; P['theta'] = 1.6
        if mode == 'free':
            best = None
            for tp in (0.25, 0.4, 0.5, 0.75, 1.0, 1.5):
                P['tp'] = tp; rr = score(OO(run(tr, P, 'free')), tr, step_of)['body_sell']; v = f1(rr['tp'], rr['sim'], rr['real'])
                if best is None or v > best[0]: best = (v, tp)
            P['tp'] = best[1]; best = None
            for th in (1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.0):
                P['theta'] = th; rr = score(OO(run(tr, P, 'free')), tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
                if best is None or v > best[0]: best = (v, th)
            P['theta'] = best[1]
        chosen.append(dict(fold=h_, tp=P.get('tp'), theta=P.get('theta'), a=round(P['a'], 3), b=round(P['b'], 3), lump_ratio=str({k: round(v, 3) for k, v in P['lump_ratio'].items()}), lump_t=str(P['lump_t']), open_off=str({f'{u}/{v}': round(x, 1) for (u, v), x in P['open_off'].items()})))
        allorders.update(run(te, P, mode, late))
    return allorders, chosen
def table(orders, label):
    rows = score(orders, ids, step_of); out = []
    for cls in NMOD + ['not_modelled']:
        d = rows[cls]; p = d['tp'] / d['sim'] if d['sim'] else np.nan; rc = d['tp'] / d['real'] if d['real'] else np.nan
        out.append(dict(variant=label, cls=cls, real_lots=d['real'], sim_lots=d['sim'], matched=d['tp'], precision=p, recall=rc, F1=f1(d['tp'], d['sim'], d['real']), F1_strict=f1(d['exact'], d['sim'], d['real']), F1_within1=f1(d['within1'], d['sim'], d['real']), strike_exact_of_matched=d['exact'] / d['tp'] if d['tp'] else np.nan, within1_of_matched=d['within1'] / d['tp'] if d['tp'] else np.nan))
    T = pd.DataFrame(out); tot = {k: int(T[k].sum()) for k in ('real_lots', 'sim_lots', 'matched')}; ex = sum(rows[c]['exact'] for c in NMOD); w1 = sum(rows[c]['within1'] for c in NMOD)
    ov = dict(variant=label, real_lots=tot['real_lots'], sim_lots=tot['sim_lots'], matched=tot['matched'], precision=tot['matched'] / tot['sim_lots'], recall=tot['matched'] / tot['real_lots'], F1=f1(tot['matched'], tot['sim_lots'], tot['real_lots']), F1_strict=f1(ex, tot['sim_lots'], tot['real_lots']), F1_within1=f1(w1, tot['sim_lots'], tot['real_lots']),
              F1_modelled_classes_only=f1(tot['matched'], tot['sim_lots'], int(T[T.cls != 'not_modelled'].real_lots.sum())), real_lots_modelled=int(T[T.cls != 'not_modelled'].real_lots.sum()))
    return T, ov
CLS_ROWS = []; OV = []
for label, mode, late in (('FR free-running (primary)', 'free', False), ('FR + late R3 (post-hoc)', 'free', True), ('TF-hedge (hedge on real body)', 'tf_hedge', False)):
    full, chosen = fit_and_score(mode, late); orders = OO(full); OUTALL[label] = orders; FULL[label] = full; T, ov = table(orders, label); CLS_ROWS.append(T); OV.append(ov); PARAMS += [dict(variant=label, **c) for c in chosen]; print(label); print(T.round(3).to_string(index=False)); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in ov.items()})
CL = pd.concat(CLS_ROWS); CL.round(4).to_csv(f'{OUT}/bl_fr_classes.csv', index=False); OVd = pd.DataFrame(OV); OVd.round(4).to_csv(f'{OUT}/bl_fr_overall.csv', index=False); pd.DataFrame(PARAMS).to_csv(f'{OUT}/bl_fr_params.csv', index=False); pd.to_pickle(OUTALL, f'{OUT}/bl_fr_orders.pkl.gz')
# per-cycle F1 (primary)
pc = []
for i in ids:
    rr = score({i: OUTALL['FR free-running (primary)'][i]}, [i], step_of); tp = sum(v['tp'] for v in rr.values()); sm = sum(v['sim'] for v in rr.values()); rl = sum(v['real'] for v in rr.values()); pc.append(dict(cid=i, und=CY.iloc[i].und, real_lots=rl, sim_lots=sm, matched=tp, F1=f1(tp, sm, rl)))
PC = pd.DataFrame(pc); PC.round(4).to_csv(f'{OUT}/bl_fr_cycles.csv', index=False); print(PC.F1.describe().round(3).to_dict())
R['overall'] = OVd.round(4).to_dict('records'); R['classes'] = CL.round(4).to_dict('records'); R['per_cycle_F1'] = PC.F1.describe().round(4).to_dict(); rec('fr1', R)

# ---------------- book scores: short/long lots through the day and the carried book (primary and TF-hedge variants)
real_net = {}; real_snap = []; SNAPJ = [60, 120, 180, 240, 300, 360, 374]
for i, r in enumerate(CY.itertuples()):
    z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry)].sort_values(['te', 'row']); sg = np.where(z.side == 'Buy', 1, -1) * z.lots.values; net = {}
    for cp_, k_, v_, jj in zip(z.cp.values, z.strike.values.astype(int), sg, z.j.values): net[(cp_, k_, jj)] = v_
    cum = {}; zz = list(zip(z.cp.values, z.strike.values.astype(int), sg, z.j.values)); p_ = 0
    for sj in SNAPJ:
        while p_ < len(zz) and zz[p_][3] <= sj: cum[(zz[p_][0], zz[p_][1])] = cum.get((zz[p_][0], zz[p_][1]), 0) + zz[p_][2]; p_ += 1
        for cp in ('CE', 'PE'): real_snap.append(dict(cid=i, j=sj, cp=cp, S_real=-sum(v for (c2, _), v in cum.items() if c2 == cp and v < 0), L_real=sum(v for (c2, _), v in cum.items() if c2 == cp and v > 0)))
    while p_ < len(zz): cum[(zz[p_][0], zz[p_][1])] = cum.get((zz[p_][0], zz[p_][1]), 0) + zz[p_][2]; p_ += 1
    real_net[i] = {k: v for k, v in cum.items() if v != 0}
RS = pd.DataFrame(real_snap); BK = []; CARRY = []
for label in ('FR free-running (primary)', 'TF-hedge (hedge on real body)'):
    sn = pd.concat([t[1] for t in FULL[label].values()]); sm = []
    for r_ in sn.itertuples():
        for cp in ('CE', 'PE'): sm.append(dict(cid=r_.cid, j=r_.j, cp=cp, S_sim=getattr(r_, f'S_{cp}'), L_sim=getattr(r_, f'L_{cp}')))
    M = pd.DataFrame(sm).merge(RS, on=['cid', 'j', 'cp'])
    for j, g in list(M.groupby('j')) + [('all hours', M)]:
        for lab, a, b in (('short lots S', 'S_sim', 'S_real'), ('long lots L', 'L_sim', 'L_real')):
            BK.append(dict(variant=label, j=j, quantity=lab, MAE_lots=float((g[a] - g[b]).abs().mean()), mean_real=float(g[b].mean()), mean_sim=float(g[a].mean()), corr=float(np.corrcoef(g[a], g[b])[0, 1]) if g[b].std() > 0 and g[a].std() > 0 else np.nan, median_abs_err_pct=float(((g[a] - g[b]).abs() / g[b].clip(lower=1)).median() * 100)))
    # carried book: contract-level overlap
    for i in ids:
        sim = FULL[label][i][2]; rl = real_net[i]
        sh = sum(min(-v, -sim.get(k, 0)) for k, v in rl.items() if v < 0 and sim.get(k, 0) < 0); lg = sum(min(v, sim.get(k, 0)) for k, v in rl.items() if v > 0 and sim.get(k, 0) > 0)
        rS = -sum(v for v in rl.values() if v < 0); rL = sum(v for v in rl.values() if v > 0); sS = -sum(v for v in sim.values() if v < 0); sL = sum(v for v in sim.values() if v > 0)
        CARRY.append(dict(variant=label, cid=i, real_S=rS, real_L=rL, sim_S=sS, sim_L=sL, shared_short=sh, shared_long=lg))
BKd = pd.DataFrame(BK); BKd.round(4).to_csv(f'{OUT}/bl_fr_book.csv', index=False); CAd = pd.DataFrame(CARRY); CAd.round(4).to_csv(f'{OUT}/bl_fr_carry.csv', index=False)
for label, g in CAd.groupby('variant'):
    R[f'carry_{label}'] = dict(short_overlap=float(g.shared_short.sum() / g.real_S.sum()), long_overlap=float(g.shared_long.sum() / g.real_L.sum()), S_mae=float((g.sim_S - g.real_S).abs().mean()), L_mae=float((g.sim_L - g.real_L).abs().mean()), S_corr=float(np.corrcoef(g.sim_S, g.real_S)[0, 1]), L_corr=float(np.corrcoef(g.sim_L, g.real_L)[0, 1]), real_S_mean=float(g.real_S.mean()), real_L_mean=float(g.real_L.mean()), sim_S_mean=float(g.sim_S.mean()), sim_L_mean=float(g.sim_L.mean()))
    print(label, {k: round(v, 3) for k, v in R[f'carry_{label}'].items()})
print(BKd[BKd.j == 'all hours'].round(3).to_string(index=False)); R['book'] = BKd.round(4).to_dict('records'); rec('fr1', R)
