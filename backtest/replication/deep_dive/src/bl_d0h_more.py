"""D0 chunk 3: addendum 3b (post-hoc) + H6 rules + H8 (plan reports/D0_HEDGE_PLAN.md).
3b-T1 v_ sell waves vs the excess L - S before them (all modules, D-1 carried position); share of v_ sell lots made while L > S. 3b-T2 wing strike reference refit out-of-fold:
X% of ATM premium / fixed premium / fixed steps OTM / X% of the last body short's premium on that right. H6 lump-sale rules (fixed clock, sell when L > S, end of body activity)
scored on lots at +-1 minute vs +30-min shifted predictions. H8 hedge AUC (h_ buys, h_ sells): leave-one-cycle-out gradient boosting on gap + same-minute body lots + clock (teacher-forced),
and a causal variant (gap and body lots of the previous minute).
Outputs bl_d0h_vwaves.csv, bl_d0h_h2b.csv, bl_d0h_h6.csv, bl_d0h_auc.csv, bl_summary_d0h2.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); R = {}; rng = np.random.default_rng(21)
D0C = [i for i, r in enumerate(CY.itertuples()) if ((O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)).any()]
NJ = 400
def hist(js, w=None):
    a = np.zeros(NJ, int); np.add.at(a, np.clip(np.asarray(js, int), 0, NJ - 1), 1 if w is None else np.asarray(w, int)); return a
def mt(a, p):
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); n = int(m.sum()); a -= m; p -= m
    for j in range(NJ):
        if a[j] == 0: continue
        for jj in (j - 1, j + 1):
            if 0 <= jj < NJ and a[j] and p[jj]: x = min(a[j], p[jj]); a[j] -= x; p[jj] -= x; n += x
    return n
VW = []; LUMP = {}; RULE2 = {}; CELLS = []; LASTBODY = {}; STOPT = {}
for i in D0C:
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry)].copy(); z['ts'] = np.where(z.dayno == 0, z.t_dec.fillna(z.te), z.t_dec.fillna(z.tod)); z['sg'] = np.where(z.side.str.lower() == 'buy', 1, -1)
    pos = {}; lump0 = {'CE': 0, 'PE': 0}
    for q in z[z.dayno == 0].itertuples():
        k = (q.cp, int(q.strike)); pos[k] = pos.get(k, 0) + q.sg * q.lots
        if q.module == 'v_': lump0[q.cp] += q.sg * q.lots
    LUMP[i] = {cp: max(v, 0) for cp, v in lump0.items()}
    def SL(cp): return -sum(v for (c2, _), v in pos.items() if c2 == cp and v < 0), sum(v for (c2, _), v in pos.items() if c2 == cp and v > 0)
    z1 = z[z.dayno == 1].sort_values(['ts', 'row']); rows = list(z1.itertuples()); n = len(rows); k_ = 0; left = dict(LUMP[i]); pr2 = {'CE': [], 'PE': []}
    body = z1[(z1.module == 'num') & z1.role.isin(['open_short', 'cover_short'])]; LASTBODY[i] = int((body.tod.max() - 33300) // 60) if len(body) else 0
    st_ = z1[z1.module == 's_']; STOPT[i] = int((st_.tod.min() - 33300) // 60) if len(st_) else None
    hb = {(cp, j): [0, 0] for cp in ('CE', 'PE') for j in range(NJ)}; gap_start = {}; bodyl = {}
    jprev = -1
    while k_ < n:
        q = rows[k_]; j = int(min(max((q.tod - 33300) // 60, 0), NJ - 1))
        while jprev < j:
            jprev += 1
            for cp in ('CE', 'PE'): s, l = SL(cp); gap_start[(cp, jprev)] = s - l
        if q.module in ('v_', 'h_') and q.role == 'close_long':
            grp = [q]; m = k_ + 1
            while m < n and rows[m].module == q.module and rows[m].cp == q.cp and rows[m].ts - q.ts <= 0.05 and rows[m].role == 'close_long': grp.append(rows[m]); m += 1
            s, l = SL(q.cp); lots = sum(g.lots for g in grp); VW.append(dict(cid=i, module=q.module, cp=q.cp, j=j, lots=lots, excess=l - s))
            for g in grp: kk = (g.cp, int(g.strike)); pos[kk] = pos.get(kk, 0) + g.sg * g.lots
            if q.module == 'h_':
                for g in grp: hb[(g.cp, int(min(max((g.tod - 33300) // 60, 0), NJ - 1)))][1] += g.lots
            k_ = m; continue
        kk = (q.cp, int(q.strike)); pos[kk] = pos.get(kk, 0) + q.sg * q.lots
        if q.module == 'h_' and q.role == 'open_long': hb[(q.cp, j)][0] += q.lots
        if q.module == 'num' and q.role in ('open_short', 'cover_short'): bodyl[(q.cp, j, q.role)] = bodyl.get((q.cp, j, q.role), 0) + q.lots
        if q.module != 'v_':
            s, l = SL(q.cp)
            if l - s > 0 and left[q.cp] > 0: x = min(l - s, left[q.cp]); left[q.cp] -= x; pr2[q.cp] += [j] * x
        k_ += 1
    RULE2[i] = pr2
    for j in range(1, 375):
        for cp in ('CE', 'PE'):
            CELLS.append(dict(cid=i, j=j, cp=cp, cpn=int(cp == 'CE'), y_buy=int(hb[(cp, j)][0] > 0), y_sell=int(hb[(cp, j)][1] > 0), gap=gap_start.get((cp, j), 0), gap_prev=gap_start.get((cp, j - 1), 0), sells_now=bodyl.get((cp, j, 'open_short'), 0),
                              bb_now=bodyl.get((cp, j, 'cover_short'), 0), sells_prev=bodyl.get((cp, j - 1, 'open_short'), 0), bb_prev=bodyl.get((cp, j - 1, 'cover_short'), 0), j_=j, moh=(j + 15) % 60))
V = pd.DataFrame(VW); V.to_csv(f'{OUT}/bl_d0h_vwaves.csv', index=False)
R['3b_T1'] = {m: dict(waves=int(len(g)), lots=int(g.lots.sum()), equals_excess=float((g.lots == g.excess).mean()), le_excess=float((g.lots <= g.excess).mean()), lots_while_L_gt_S=float(g[g.excess > 0].lots.sum() / g.lots.sum())) for m, g in V.groupby('module')}
# ---------------- 3b-T2 wing strike references
BY = pd.read_csv(f'{OUT}/bl_d0h_buys.csv'); lastsell = []
for q in BY.itertuples():
    r = CY.iloc[q.cid]; s = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 'num') & (O.role == 'open_short') & (O.cp == q.cp) & (O.tod < 33300 + 60 * (q.j + 1))]
    lastsell.append(float(s.sort_values('tod').px_avg.iloc[-1]) if len(s) else np.nan)
BY['last_sell_px'] = lastsell
def pick(q, kind, x):
    r = CY.iloc[q.cid]; op = OPT[(r.und, r.expiry)]; pr = op[(q.cp, 'close')][:, q.j - 1]; K = op['K']; st = ref.STEP[r.und]; otm = (K - q.spot) * (1 if q.cp == 'CE' else -1) > 0; ok = otm & np.isfinite(pr)
    if not ok.any(): return np.nan
    if kind == 'pct_atm': tgt = x * q.atm_px; return K[ok][np.argmin(np.abs(pr[ok] - tgt))] if tgt == tgt else np.nan
    if kind == 'fixed_rs': return K[ok][np.argmin(np.abs(pr[ok] - x))]
    if kind == 'steps': kk = q.spot + (1 if q.cp == 'CE' else -1) * x * st; return K[np.argmin(np.abs(K - kk))]
    if kind == 'pct_sold': tgt = x * q.last_sell_px; return K[ok][np.argmin(np.abs(pr[ok] - tgt))] if tgt == tgt else np.nan
GR = {'pct_atm': [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.075, 0.10], 'fixed_rs': [0.5, 1, 1.5, 2, 3, 4, 5], 'steps': [5, 8, 10, 12, 15, 20, 25], 'pct_sold': [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.075, 0.1]}
CACHE = {(kd, x): np.array([pick(q, kd, x) for q in BY.itertuples()]) for kd in GR for x in GR[kd]}
ex = lambda kd, x, m: float(np.nanmean((CACHE[(kd, x)][m] == BY.strike.values[m]).astype(float)[~np.isnan(CACHE[(kd, x)][m])]))
h2b = []
for kd in GR:
    hit = []; ch = []
    for h in (0, 1):
        tr = (BY.cid % 2 != h).values; te = ~tr; bx = max(GR[kd], key=lambda x: ex(kd, x, tr)); ch.append(bx); hit.append((ex(kd, bx, te), te.sum()))
    h2b.append(dict(reference=kd, chosen=' / '.join(map(str, ch)), exact_oof=sum(a * b for a, b in hit) / sum(b for _, b in hit)))
H2B = pd.DataFrame(h2b); H2B.to_csv(f'{OUT}/bl_d0h_h2b.csv', index=False); print(H2B.round(3).to_string(index=False))
# ---------------- H6 lump-sale rules
LP = pd.read_csv(f'{OUT}/bl_d0h_lump.csv'); h6 = []
def sc(pred, shift=0):
    tp = ns = nr = 0; per = []
    for i in D0C:
        x = [0, 0, 0]
        for cp in ('CE', 'PE'):
            a = hist(LP[(LP.cid == i) & (LP.cp == cp)].j, LP[(LP.cid == i) & (LP.cp == cp)].lots); p = hist(np.asarray(pred[i][cp], int) + shift) if len(pred[i][cp]) else np.zeros(NJ, int); x[0] += mt(a, p); x[1] += int(p.sum()); x[2] += int(a.sum())
        per.append(x)
    a = np.array(per); return 2 * a[:, 0].sum() / max(a[:, 1].sum() + a[:, 2].sum(), 1), a[:, 0].sum() / max(a[:, 1].sum(), 1), a[:, 0].sum() / max(a[:, 2].sum(), 1), int(a[:, 1].sum()), int(a[:, 2].sum())
pred_clock = {}
for h in (0, 1):
    tr = [i for i in D0C if i % 2 != h]; fs = LP[LP.cid.isin(tr)].groupby('cid').j.min(); jm = int(fs.median()) if len(fs) else 0
    for i in [i for i in D0C if i % 2 == h]: pred_clock[i] = {cp: [jm] * LUMP[i][cp] for cp in ('CE', 'PE')}
pred_end = {i: {cp: [min(LASTBODY[i], STOPT[i] if STOPT[i] is not None else 999)] * LUMP[i][cp] for cp in ('CE', 'PE')} for i in D0C}
for nm, pr in (('fixed clock (training median first-sale minute), all lump lots', pred_clock), ('sell when L > S on that right (event-level, real book)', RULE2), ('all lump lots at the end of body activity / the stop', pred_end)):
    f, p, rc, ns, nr = sc(pr); fn = sc(pr, 30)[0]; h6.append(dict(rule=nm, F1=f, precision=p, recall=rc, sim_lots=ns, real_lots=nr, null_shift30_F1=fn))
H6 = pd.DataFrame(h6); H6.to_csv(f'{OUT}/bl_d0h_h6.csv', index=False); print(H6.round(3).to_string(index=False)); R['lump_carried_lots'] = int(sum(sum(v.values()) for v in LUMP.values()))
# ---------------- H8 AUC
X = pd.DataFrame(CELLS); au = []
for y in ('y_buy', 'y_sell'):
    for nm, cols in (('teacher-forced: gap at minute start + same-minute body lots + clock', ['gap', 'sells_now', 'bb_now', 'j_', 'moh', 'cpn']), ('causal: gap and body lots of the previous minute + clock', ['gap_prev', 'sells_prev', 'bb_prev', 'j_', 'moh', 'cpn']), ('clock only', ['j_', 'moh', 'cpn'])):
        p = np.zeros(len(X))
        for i in D0C:
            tr = (X.cid != i).values; mdl = HistGradientBoostingClassifier(max_iter=150, random_state=0).fit(X.loc[tr, cols], X.loc[tr, y]); p[~tr] = mdl.predict_proba(X.loc[~tr, cols])[:, 1]
        u = X.cid.unique(); idx = {c_: np.where(X.cid.values == c_)[0] for c_ in u}; bs = []
        for _ in range(300):
            k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); bs.append(roc_auc_score(X[y].values[k], p[k]))
        au.append(dict(target='h_ buy' if y == 'y_buy' else 'h_ sell', variant=nm, AUC=roc_auc_score(X[y], p), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5), cells=len(X), positives=int(X[y].sum())))
AU = pd.DataFrame(au); AU.to_csv(f'{OUT}/bl_d0h_auc.csv', index=False); print(AU.round(3).to_string(index=False))
R['H2b'] = H2B.round(4).to_dict('records'); R['H6'] = H6.round(4).to_dict('records'); R['H8'] = AU.round(4).to_dict('records'); rec('d0h2', R); print(R['3b_T1'])
