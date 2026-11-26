"""P1-3B / P1-3C teacher-forced evaluations (reports/PHASE1_GATE3BC_PLAN.md). No engine run."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S
OUT = bl_common.OUT; OPEN_S = 33300; REAL = S.REAL.copy(); REAL['cyc'] = REAL.und + '|' + REAL.expiry; cyc_ix = {f'{r.und}|{r.expiry}': i for i, r in enumerate(S.CY.itertuples())}; PREP = {c: S.prep(i) for c, i in cyc_ix.items()}
def snap(K, x): return float(K[np.argmin(np.abs(K - x))])
# ----------------------------------------------------------------------------------------- 3b
rows = []
for cyc, i in cyc_ix.items():
    d = PREP[cyc]; K = d['K']; ki = d['ki']; op = d['op']; close = S.OH[tuple(cyc.split('|'))].close.values; R = REAL[REAL.cyc == cyc].sort_values('row')
    wings = {}; shorts = {}
    for r in R.itertuples():
        key = (r.cp, float(r.strike)); n = int(r.lots)
        if r.role == 'open_long' and r.module != 'v_': wings.setdefault(key, []).extend([int(r.t_first)] * n)
        elif r.role == 'open_short': shorts[key] = shorts.get(key, 0) + n
        elif r.role == 'cover_short': shorts[key] = max(shorts.get(key, 0) - n, 0)
        elif r.role == 'close_long' and r.module == 'h_':
            held = {k: v for k, v in wings.items() if k[0] == r.cp and len(v) > 0}
            if len(held) >= 2 and key in held:
                j = int((r.t_first - OPEN_S) // 60); jp = min(max(j - 1, 0), len(close) - 1); atm = snap(K, close[jp]); prem = lambda k: float(op[(r.cp, 'close')][ki[int(k[1])], jp]) if int(k[1]) in ki else 0.0; ks = list(held)      # a strike outside the downloaded chain is the outermost and cheapest by construction: premium 0 (limit, counted)
                pick = {'W1': max(ks, key=lambda k: (abs(k[1] - atm), k[1])), 'W2': min(ks, key=lambda k: (prem(k), k[1])), 'W3': max(ks, key=lambda k: (max(held[k]), k[1])), 'W4': min(ks, key=lambda k: (min(held[k]), k[1])), 'W5': min(ks, key=lambda k: (abs(k[1] - atm), k[1])), 'W6': max(ks, key=lambda k: (len(held[k]), k[1]))}
                rec = dict(cyc=cyc, row=int(r.row), n_held=len(ks), chance=1 / len(ks), real=key[1], outside_chain=any(int(k[1]) not in ki for k in ks)); rec.update({w: (p[1] == key[1]) for w, p in pick.items()}); rows.append(rec)
        if r.role == 'close_long':
            ks = key
            for _ in range(n):
                if wings.get(ks): wings[ks].pop(0)
D = pd.DataFrame(rows); W = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6']; res = dict(wing_sells_total=int(((REAL.role == 'close_long') & (REAL.module == 'h_')).sum()), with_two_or_more_held=int(len(D)), chance=float(D.chance.mean()))
res['orders_with_a_candidate_outside_the_chain'] = int(D.outside_chain.sum()); res['rules'] = {w: float(D[w].mean()) for w in W}; cyc_l = sorted(D.cyc.unique()); per = {c: D[D.cyc == c] for c in cyc_l}; rng = np.random.default_rng(3); sup = {}
for w in W[1:]:
    f = lambda sel: np.concatenate([per[c][w].values for c in sel]).mean() - np.concatenate([per[c]['W1'].values for c in sel]).mean(); bs = [f(list(rng.choice(cyc_l, len(cyc_l)))) for _ in range(4000)]; ge = int(sum(per[c][w].mean() >= per[c]['W1'].mean() for c in cyc_l)); d0 = f(cyc_l)
    sup[w] = dict(diff=float(d0), ci95=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], cycles_ge_W1=ge, supported=bool(d0 >= 0.05 and np.quantile(bs, .025) > 0 and ge >= 20))
res['vs_W1'] = sup
# ----------------------------------------------------------------------------------------- 3c
L = REAL[(REAL.module == 'v_') & (REAL.role == 'open_long')]; rows = []
for cyc, z in L.groupby('cyc'):
    t0 = int(z.t_first.min()); R = REAL[REAL.cyc == cyc].sort_values('row'); sh = {'CE': {}, 'PE': {}}; wl = {'CE': 0, 'PE': 0}
    for r in R[R.t_first < t0].itertuples():
        if r.role == 'open_short': sh[r.cp][r.strike] = sh[r.cp].get(r.strike, 0) + int(r.lots)
        elif r.role == 'cover_short': sh[r.cp][r.strike] = max(sh[r.cp].get(r.strike, 0) - int(r.lots), 0)
        elif r.role == 'open_long' and r.module != 'v_': wl[r.cp] += int(r.lots)
        elif r.role == 'close_long': wl[r.cp] = max(wl[r.cp] - int(r.lots), 0)
    S_ = {c: sum(v.values()) for c, v in sh.items()}; heavy = 'CE' if S_['CE'] > S_['PE'] else 'PE'; light = 'PE' if heavy == 'CE' else 'CE'; by_side = z.groupby('cp').lots.sum().to_dict()
    rows.append(dict(cyc=cyc, und=cyc.split('|')[0], total=int(z.lots.sum()), real_side=max(by_side, key=by_side.get), pred_side=heavy, only_one_side=len(by_side) == 1, S_heavy=S_[heavy], S_light=S_[light], S_total=S_['CE'] + S_['PE'], t0=t0))
Lm = pd.DataFrame(rows); res['lump'] = dict(cycles_with_lump=int(len(Lm)), side_agreement=float((Lm.real_side == Lm.pred_side).mean()), orders=int(len(L)), lots=int(L.lots.sum()))
feats = {'M1': 'S_heavy', 'M2': None, 'M3': 'S_total', 'M4': None}; Lm['M2f'] = Lm.S_heavy - Lm.S_light
def fit_pred(train, test, m):
    out = []
    for und in test.und.unique():
        tr = train[train.und == und]; te = test[test.und == und]
        if m == 'M4': a = tr.total.median(); p = np.full(len(te), a)
        else: x = {'M1': tr.S_heavy, 'M2': tr.M2f, 'M3': tr.S_total}[m].values.astype(float); y = tr.total.values.astype(float); a = np.median(y[x > 0] / x[x > 0]) if (x > 0).any() else 0.0; xt = {'M1': te.S_heavy, 'M2': te.M2f, 'M3': te.S_total}[m].values.astype(float); p = a * xt
        out.append(pd.Series(p, index=te.index))
    return pd.concat(out).reindex(test.index)
err = {}; pred = {}
for m in ('M1', 'M2', 'M3', 'M4'):
    ps = pd.Series(index=Lm.index, dtype=float)
    for c in Lm.cyc: ps[Lm.index[Lm.cyc == c][0]] = fit_pred(Lm[Lm.cyc != c], Lm[Lm.cyc == c], m).iloc[0]
    pred[m] = ps; err[m] = (ps - Lm.total).abs()
res['lump']['loco_MAE_lots'] = {m: float(e.mean()) for m, e in err.items()}; res['lump']['loco_median_rel_err'] = {m: float((err[m] / Lm.total).median()) for m in err}; res['lump']['real_mean_lots'] = float(Lm.total.mean())
cl = list(Lm.cyc); rng = np.random.default_rng(9); sup = {}
for m in ('M2', 'M3', 'M4'):
    dif = (err[m] - err['M1']).values; bs = [dif[rng.integers(0, len(dif), len(dif))].mean() for _ in range(4000)]; rel = float(dif.mean() / err['M1'].mean()); better = int((err[m] < err['M1']).sum())
    sup[m] = dict(mae_rel_change_vs_M1=rel, ci95_of_mean_diff=[float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], cycles_better=better, supported=bool(rel <= -0.20 and np.quantile(bs, .975) < 0 and better >= 20))
res['lump']['vs_M1'] = sup
json.dump(res, open(f'{OUT}/phase1/3BC.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
