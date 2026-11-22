"""D0 chunk 5 scoring (plan reports/D0_FREE_RUN_PLAN.md). Lot-level one-to-one matching per cycle x class x right (same minute, then +-1; nearest strike breaks ties), F1 / precision / recall /
F1 strike-exact / F1 within one strike step, per class and overall (modelled classes), null = simulated orders shifted +15 min. Splits from bl_d0_fr.py (OOF halves pooled, forward A, forward B).
AUC: any-activity cells (cycle x minute x right, real modelled-class order in the cell); (1) raw simulator activity score; (2) gradient boosting on simulator activity + market + clock,
trained on the split's training cycles simulated with the training parameters, scored on its test cycles.
Outputs bl_d0_fr_score.csv, bl_d0_fr_class.csv, bl_d0_fr_auc.csv, bl_summary_d0fr.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
import bl_d0_fr as F
CY = F.CY; O = F.O; SPT = F.SPT; RES = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz'); PAR = json.load(open(f'{OUT}/bl_d0_fr_params.json')); R = {}
CLS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('v_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'body_long', ('num', 'close_long'): 'body_long'}
NMOD = ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'body_long', 'stop']; REAL = {}; NOTM = {}
for i in F.D0C:
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)].copy(); z['cls'] = ['stop' if m == 's_' else CLS.get((m, ro), 'not_modelled') for m, ro in zip(z.module, z.role)]; z['j'] = ((z.tod - 33300) // 60).clip(0, 389).astype(int)
    REAL[i] = z; NOTM[i] = int(z[z.cls == 'not_modelled'].lots.sum())
def match(rj, rk, sj, sk, tol=1):
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
expand = lambda df: (np.repeat(df.j.values, df.lots.values).astype(int), np.repeat(df.strike.values, df.lots.values).astype(float))
def score(sims, cids, shift=0):
    rows = {c: dict(real=0, sim=0, tp=0, exact=0, within1=0) for c in NMOD}
    for i in cids:
        st = ref.STEP[CY.iloc[i].und]; s = sims[i]
        for c in NMOD:
            for cp in ('CE', 'PE'):
                rj, rk = expand(REAL[i][(REAL[i].cls == c) & (REAL[i].cp == cp)]); g = s[(s.cls == c) & (s.cp == cp)]; sj, sk = expand(g); sj = sj + shift
                rows[c]['real'] += len(rj); rows[c]['sim'] += len(sj)
                if len(rj) and len(sj): dk = match(rj, rk, sj, sk); rows[c]['tp'] += len(dk); rows[c]['exact'] += int((dk == 0).sum()); rows[c]['within1'] += int((dk <= st + 1e-6).sum())
    f1 = lambda tp, a, b: 2 * tp / max(a + b, 1); out = []
    for c, d in rows.items(): out.append(dict(cls=c, real_lots=d['real'], sim_lots=d['sim'], matched=d['tp'], precision=d['tp'] / max(d['sim'], 1), recall=d['tp'] / max(d['real'], 1), F1=f1(d['tp'], d['sim'], d['real']), F1_strict=f1(d['exact'], d['sim'], d['real']), F1_within1=f1(d['within1'], d['sim'], d['real'])))
    T = pd.DataFrame(out); t = T.sum(numeric_only=True)
    ov = dict(real_lots=int(t.real_lots), sim_lots=int(t.sim_lots), precision=t.matched / t.sim_lots, recall=t.matched / t.real_lots, F1=2 * t.matched / (t.sim_lots + t.real_lots), F1_strict=2 * T.F1_strict.mul(T.sim_lots + T.real_lots).sum() / 2 / (t.sim_lots + t.real_lots),
              F1_within1=T.F1_within1.mul(T.sim_lots + T.real_lots).sum() / (t.sim_lots + t.real_lots), not_modelled_lots=int(sum(NOTM[i] for i in cids)))
    return T, ov
SETS = {'OOF (cycle halves)': ({**RES['OOF half 0 test'], **RES['OOF half 1 test']}, F.D0C), 'forward A (same version, later cycles)': (RES['forward A (same version, later cycles)'], PAR['forward A (same version, later cycles)']['test']),
        'forward B (train V1, test V2)': (RES['forward B (train V1, test V2)'], PAR['forward B (train V1, test V2)']['test'])}
ovs = []; cls_rows = []
for nm, (sims, cids) in SETS.items():
    T, ov = score(sims, cids); _, nl = score(sims, cids, 15); ovs.append(dict(split=nm, cycles=len(cids), **ov, null_shift15_F1=nl['F1'])); cls_rows.append(T.assign(split=nm)); print(nm, {k: round(v, 3) if isinstance(v, float) else v for k, v in ov.items()}, 'null', round(nl['F1'], 3))
OV = pd.DataFrame(ovs); CL = pd.concat(cls_rows, ignore_index=True); OV.to_csv(f'{OUT}/bl_d0_fr_score.csv', index=False); CL.to_csv(f'{OUT}/bl_d0_fr_class.csv', index=False); print(CL[CL.split.str.startswith('OOF')].round(3).to_string(index=False))
# ---------------- stop agreement (cycle level; post-hoc diagnostic)
sa_ = []
for nm, (sims, cids) in SETS.items():
    for i in cids:
        rs = REAL[i][REAL[i].cls == 'stop']; ss = sims[i][sims[i].cls == 'stop']; sa_.append(dict(split=nm, cid=i, real_stop_j=int(rs.j.min()) if len(rs) else None, sim_stop_j=int(ss.j.min()) if len(ss) else None))
SA = pd.DataFrame(sa_); SA['agree'] = [('both' if (a == a and a is not None) and (b == b and b is not None) else ('real only' if (a == a and a is not None) else ('sim only' if (b == b and b is not None) else 'neither'))) for a, b in zip(SA.real_stop_j, SA.sim_stop_j)]
SA['dj'] = SA.sim_stop_j - SA.real_stop_j; SA.to_csv(f'{OUT}/bl_d0_fr_stops.csv', index=False); R_stop = SA.groupby(['split', 'agree']).size().unstack(fill_value=0); print(R_stop.to_string()); print('timing |dj| <= 1 among both:', SA[SA.agree == 'both'].groupby('split').dj.apply(lambda d: float((d.abs() <= 1).mean())).to_dict())
# ---------------- AUC
def cells(i, s):
    r = CY.iloc[i]; sp = SPT[(r.und, r.expiry)]; h, l, c = sp.high.values, sp.low.values, sp.close.values; st = ref.STEP[r.und]; z = REAL[i]; z = z[z.cls != 'not_modelled']
    ya = {}
    for q in z.itertuples(): ya[(q.cp, min(q.j, 374))] = 1
    sa = {}
    for q in s.itertuples(): sa[(q.cls, q.cp, q.j)] = sa.get((q.cls, q.cp, q.j), 0) + q.lots
    rows = []
    for j in range(375):
        for cp in ('CE', 'PE'):
            d = dict(cid=i, j=j, cp=cp, cpn=int(cp == 'CE'), y=ya.get((cp, j), 0), j_=j, moh=(j + 15) % 60, blk=j % 15)
            tot = 0; tot1 = 0
            for k in NMOD:
                v = sa.get((k, cp, j), 0); d[f's_{k}'] = v; d[f's1_{k}'] = sa.get((k, cp, j - 1), 0) + sa.get((k, cp, j + 1), 0); tot += v; tot1 += d[f's1_{k}']
            d['sim_score'] = tot + 0.5 * tot1
            for n in (1, 5, 15): d[f'mv{n}'] = (c[j] - c[max(j - n, 0)]) / st
            d['rng'] = (h[j] - l[j]) / st; d['newhi15'] = float(j > 0 and h[j] > h[max(j - 15, 0):j].max()); d['newlo15'] = float(j > 0 and l[j] < l[max(j - 15, 0):j].min()); d['newhi60'] = float(j > 0 and h[j] > h[max(j - 60, 0):j].max()); d['newlo60'] = float(j > 0 and l[j] < l[max(j - 60, 0):j].min())
            rows.append(d)
    return rows
au = []; rng = np.random.default_rng(17)
for nm, key_tests in (('OOF (cycle halves)', ['OOF half 0 test', 'OOF half 1 test']), ('forward A (same version, later cycles)', ['forward A (same version, later cycles)']), ('forward B (train V1, test V2)', ['forward B (train V1, test V2)'])):
    ys = []; ps = []; pr = []; cid_all = []
    for key in key_tests:
        tr, te = PAR[key]['train'], PAR[key]['test']; vm = {'V2': 'V1', 'V1': 'V1'} if key.startswith('forward B') else {'V1': 'V1', 'V2': 'V2'}; P = F.fit(tr, te, vm)
        Xtr = pd.DataFrame([x for i in tr for x in cells(i, F.sim(i, P))]); Xte = pd.DataFrame([x for i in te for x in cells(i, RES[key][i])])
        cols = [k for k in Xtr.columns if k not in ('cid', 'j', 'cp', 'y')]; m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, min_samples_leaf=20, random_state=0).fit(Xtr[cols], Xtr.y)
        ys.append(Xte.y.values); ps.append(m.predict_proba(Xte[cols])[:, 1]); pr.append(Xte.sim_score.values); cid_all.append(Xte.cid.values)
    y = np.concatenate(ys); p = np.concatenate(ps); s_ = np.concatenate(pr); cc = np.concatenate(cid_all); u = np.unique(cc); idx = {c_: np.where(cc == c_)[0] for c_ in u}; bs = []
    for _ in range(300): k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); bs.append(roc_auc_score(y[k], p[k]))
    au.append(dict(split=nm, AUC_model=roc_auc_score(y, p), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5), AUC_raw_simulator=roc_auc_score(y, s_), cells=len(y), positives=int(y.sum()))); print(au[-1])
AU = pd.DataFrame(au); AU.to_csv(f'{OUT}/bl_d0_fr_auc.csv', index=False)
rec('d0fr', dict(overall=OV.round(4).to_dict('records'), auc=AU.round(4).to_dict('records'), stops={f'{a}|{b}': int(v) for (a, b), v in R_stop.stack().items()}, stop_timing_pm1=SA[SA.agree == 'both'].groupby('split').dj.apply(lambda d: float((d.abs() <= 1).mean())).to_dict()))
