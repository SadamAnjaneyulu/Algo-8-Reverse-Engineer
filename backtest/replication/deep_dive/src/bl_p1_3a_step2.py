"""P1-3A Step 2: teacher-forced stop mechanisms K1-K5 (and K6 latency) on the real position at (contract, minute) level (plan sections 4 and Addendum 1). No engine change."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S, bl_tfe as T
from d1_algo.book import Book
OUT = bl_common.OUT; OPEN_S = 33300; LR = pd.read_csv(f'{OUT}/bodysell/ledger_real.csv'); MODULE = {(r.cyc, int(r.row)): r.inferred_module for r in LR.itertuples()}
REAL = S.REAL.copy(); REAL['cyc'] = REAL.und + '|' + REAL.expiry; cyc_ix = {f'{r.und}|{r.expiry}': i for i, r in enumerate(S.CY.itertuples())}; PREP = {c: S.prep(i) for c, i in cyc_ix.items()}
RGRID = [1.4, 1.5, 1.6, 1.7, 1.8]; CGRID = [1.2, 1.3, 1.4, 1.5]
def minute_states(cyc):
    """yield per minute j: lots held at the START of minute j: list of dict(cp, strike, entry, emin, module, key)"""
    R = REAL[REAL.cyc == cyc].sort_values('row'); book = Book(); mod_of = {}; out = {}; rows = list(R.itertuples()); ptr = 0
    for j in range(0, 375):
        t0 = OPEN_S + 60 * j
        while ptr < len(rows) and rows[ptr].t_first < t0:
            r = rows[ptr]; T.apply_real(book, dict(t=int(r.t_first), row=int(r.row), cp=r.cp, strike=float(r.strike), side=r.side, lots=int(r.lots), role=r.role, module=r.module, px=float(r.px_avg)))
            if r.role == 'open_short' and r.module == 'num':
                for l in book.shorts[(r.cp, float(r.strike))][-int(r.lots):]: l.role = MODULE.get((cyc, int(r.row)), 'solo')
            ptr += 1
        out[j] = [dict(cp=cp, strike=k, entry=l.entry_price, emin=l.minute, module=l.role) for (cp, k), v in book.shorts.items() for l in v]
    return out
rows = []
for cyc, i in cyc_ix.items():
    d = PREP[cyc]; ki = d['ki']; op = d['op']; st = minute_states(cyc); R = REAL[(REAL.cyc == cyc) & (REAL.module == 'num') & (REAL.role == 'cover_short')]
    real_bb = {}
    for r in R.itertuples(): j = int((r.t_first - OPEN_S) // 60); real_bb[(r.cp, float(r.strike), j)] = real_bb.get((r.cp, float(r.strike), j), 0) + int(r.lots)
    for j, lots in st.items():
        for l in lots:
            if l['emin'] >= j or l['entry'] <= 0: continue
            a = ki[int(l['strike'])]; jb = min(j, 374); l['rh'] = float(op[(l['cp'], 'high')][a, jb] / l['entry']); l['rc'] = float(op[(l['cp'], 'close')][a, max(j - 1, 0)] / l['entry'])
        els = [l for l in lots if 'rh' in l]
        for (cp, k), g in pd.DataFrame(els).groupby(['cp', 'strike']) if els else []:
            rows.append(dict(cyc=cyc, j=j, cp=cp, strike=k, n=len(g), rh=sorted(g.rh.tolist(), reverse=True), rc=g.rc.tolist(), mods=g.module.tolist(), rh_by_mod=g.rh.tolist(), ids=list(zip(g.entry.tolist(), g.emin.tolist())), real=real_bb.get((cp, k, j), 0)))
E_ = pd.DataFrame(rows); E_['key'] = list(zip(E_.cyc, E_.j, E_.cp, E_.strike))
# real buy-backs on contracts with no eligible lot at the start of the minute (held only after entry in the same minute or no lot): count as unreachable
tot_real = int(REAL[(REAL.module == 'num') & (REAL.role == 'cover_short')].lots.sum()); reach = int(E_.real.sum())
def lot_mask(r, mech, p):
    rh, rc = np.array(r.rh_by_mod), np.array(r.rc)
    if mech in ('K1',): return rh >= 1.6
    if mech == 'K2': return rh >= p
    if mech == 'K3': return rc >= 1.6
    raise ValueError(mech)
def run_first(df, mask_fn):
    """each lot counted once per mechanism, at the first minute it satisfies the mask (lot id = cycle, contract, entry price, entry minute)"""
    seen = set(); out = []
    for r in df.itertuples():
        m = mask_fn(r); new = 0
        for ok, lid in zip(m, r.ids):
            key = (r.cyc, r.cp, r.strike, lid)
            if ok and key not in seen: seen.add(key); new += 1
        out.append(new)
    return np.array(out)
def pred(df, mech, p): return run_first(df, lambda r: lot_mask(r, mech, p))
def f1(pr, re): tp = np.minimum(pr, re).sum(); P_ = tp / max(pr.sum(), 1); R_ = tp / max(re.sum(), 1); return float(2 * P_ * R_ / (P_ + R_)) if (P_ + R_) else 0.0, float(P_), float(R_)
re_ = E_.real.values; res = dict(real_lots_total=tot_real, real_lots_on_contract_minutes_with_an_eligible_lot=reach, events=int(len(E_)))
res['K1'] = dict(zip(['F1', 'P', 'R'], f1(pred(E_, 'K1', None), re_)))
# K2: constant ratio, LOCO
cycs = sorted(E_.cyc.unique()); sc = {p: pred(E_, 'K2', p) for p in RGRID}; chosen = []; tp = pp = rp = 0.0
for c in cycs:
    m = (E_.cyc != c).values; best = max(RGRID, key=lambda p: f1(sc[p][m], re_[m])[0]); chosen.append(best); mc = ~m; tp += np.minimum(sc[best][mc], re_[mc]).sum(); pp += sc[best][mc].sum(); rp += re_[mc].sum()
Pn = tp / max(pp, 1); Rn = tp / max(rp, 1); res['K2'] = dict(grid={str(p): dict(zip(['F1', 'P', 'R'], f1(sc[p], re_))) for p in RGRID}, loco_chosen={str(k): int(v) for k, v in pd.Series(chosen).value_counts().items()}, loco_F1=float(2 * Pn * Rn / (Pn + Rn)))
res['K3'] = dict(zip(['F1', 'P', 'R'], f1(pred(E_, 'K3', None), re_)))
# K4: module-specific ratio, LOCO over a 2D grid (scheduled_clock vs others)
def pred_mod(df, ps, po):
    def mk(r): rh = np.array(r.rh_by_mod); sched = np.array([m == 'scheduled_clock' for m in r.mods]); return ((rh >= ps) & sched) | ((rh >= po) & ~sched)
    return run_first(df, mk)
grid2 = [(a, b) for a in RGRID for b in RGRID]; sc2 = {g: pred_mod(E_, *g) for g in grid2}; ch2 = []; tp = pp = rp = 0.0
for c in cycs:
    m = (E_.cyc != c).values; best = max(grid2, key=lambda g: f1(sc2[g][m], re_[m])[0]); ch2.append(best); mc = ~m; tp += np.minimum(sc2[best][mc], re_[mc]).sum(); pp += sc2[best][mc].sum(); rp += re_[mc].sum()
Pn = tp / max(pp, 1); Rn = tp / max(rp, 1); res['K4'] = dict(loco_chosen={str(k): int(v) for k, v in pd.Series(ch2).value_counts().items()}, loco_F1=float(2 * Pn * Rn / (Pn + Rn)), best_in_sample=max(((g, f1(sc2[g], re_)[0]) for g in grid2), key=lambda x: x[1]))
# K5: cluster closing: if any lot on the right (cp) in the same minute reaches 1.6, all lots of that right with ratio >= cluster ratio are bought back
k1m = {}                                                                                           # per (cyc, j, cp): did any lot of that right reach 1.6 in that minute (any lot, counted or not)
for r in E_.itertuples(): k1m[(r.cyc, r.j, r.cp)] = k1m.get((r.cyc, r.j, r.cp), False) or bool((np.array(r.rh_by_mod) >= 1.6).any())
def pred_k5(df, cr): return run_first(df, lambda r: (np.array(r.rh_by_mod) >= (cr if k1m[(r.cyc, r.j, r.cp)] else 1.6)))
sc5 = {c: pred_k5(E_, c) for c in CGRID}; ch5 = []; tp = pp = rp = 0.0
for c in cycs:
    m = (E_.cyc != c).values; best = max(CGRID, key=lambda x: f1(sc5[x][m], re_[m])[0]); ch5.append(best); mc = ~m; tp += np.minimum(sc5[best][mc], re_[mc]).sum(); pp += sc5[best][mc].sum(); rp += re_[mc].sum()
Pn = tp / max(pp, 1); Rn = tp / max(rp, 1); res['K5'] = dict(grid={str(c): dict(zip(['F1', 'P', 'R'], f1(sc5[c], re_))) for c in CGRID}, loco_chosen={str(k): int(v) for k, v in pd.Series(ch5).value_counts().items()}, loco_F1=float(2 * Pn * Rn / (Pn + Rn)))
# cluster bootstrap of the best mechanism vs K1 (by cycle)
def per_cycle_f1(pr): return {c: f1(pr[(E_.cyc == c).values], re_[(E_.cyc == c).values])[0] for c in cycs}
k1 = pred(E_, 'K1', None); rng = np.random.default_rng(5); cand = {'K2@LOCO-modal': sc[int(pd.Series(chosen).mode()[0])] if False else sc[pd.Series(chosen).mode()[0]], 'K3': pred(E_, 'K3', None), 'K5@LOCO-modal': sc5[pd.Series(ch5).mode()[0]]}
def boot(pr):
    d = []
    for _ in range(2000):
        pick = rng.choice(cycs, len(cycs)); m = np.concatenate([np.where((E_.cyc == c).values)[0] for c in pick]); d.append(f1(pr[m], re_[m])[0] - f1(k1[m], re_[m])[0])
    pc1 = per_cycle_f1(k1); pcx = per_cycle_f1(pr); return dict(diff=f1(pr, re_)[0] - f1(k1, re_)[0], ci95=[float(np.quantile(d, .025)), float(np.quantile(d, .975))], cycles_ge_K1=int(sum(pcx[c] >= pc1[c] for c in cycs)))
res['vs_K1'] = {k: boot(v) for k, v in cand.items()}
json.dump(res, open(f'{OUT}/phase1/3A_step2.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
