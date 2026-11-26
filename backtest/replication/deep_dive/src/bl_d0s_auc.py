"""D0 chunk 1, T5 (plan reports/D0_SELLS_PLAN.md + addendum 1c): one ranking number for D0 selling.
Cells: active cycle (before the real stop) x minute 1..374 x right; positive = a body sale in the cell. Leave-one-cycle-out gradient boosting.
A same-minute market + decoded rules (OOF timetable waves from the other half, breakout machine, fresh extremes, moves, ATM premium lows, ladder with resets at timetable waves, clock);
B = A with market lagged one minute; C = A + real buy-back history from earlier minutes and the real short book at the end of the previous minute (teacher-forced);
C0 = C + same-minute buy-backs (teacher-forced, same-minute: measures the coupling, not a causal trigger).
Common-cause check: AUC of the same-minute other-right buy-back lots for solo-sale cells inside quintiles of the same-minute favourable spot move.
Outputs bl_d0s_auc.csv, bl_d0s_auc_type.csv, bl_d0s_auc_cc.csv, bl_d0s_auc_pred.pkl.gz, bl_summary_d0s4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
src = open('bl_d0s_tt.py').read(); exec(src[:src.index('WALL = waves(D0C)')])
WF = pd.read_pickle(f'{OUT}/bl_d0s_waves_fold.pkl.gz'); rows = []
for i in D0C:
    d = M[i]; h, l, c, st = d['h'], d['l'], d['c'], d['step']; js = int(min((STOP[i] - 33300) // 60, 375)); r = CY.iloc[i]
    w = WF[i % 2]; w = w[(w.und == r.und) & (w.version == r.version)]; wv = np.zeros(400); np.add.at(wv, ((w.t.values - 33300) // 60).astype(int), w.lots.values)
    fi = np.zeros((400, 2)); dep = np.zeros(400)
    for j, s in fires(d): fi[j, 0 if s > 0 else 1] += 1
    K = d['K']; ki = d['ki']; op = d['op']; atmk = [int(K[np.argmin(np.abs(K - c[max(j - 1, 0)]))]) for j in range(375)]
    s_ = S[S.cid == i]; b_ = B[B.cid == i]
    for cp in ('CE', 'PE'):
        sg = -1 if cp == 'CE' else 1                                # favourable spot direction for a short of this right
        sold = np.zeros(400); np.add.at(sold, np.clip(s_[s_.cp == cp].j.values, 0, 399), s_[s_.cp == cp].lots.values)
        labj = {}
        for lab in ('grid_pair', 'offgrid_pair', 'solo'): x = np.zeros(400); g = s_[(s_.cp == cp) & (s_.lab == lab)]; np.add.at(x, np.clip(g.j.values, 0, 399), g.lots.values); labj[lab] = x
        bs = np.zeros(400); np.add.at(bs, np.clip(b_[b_.cp == cp].j.values, 0, 399), b_[b_.cp == cp].lots.values); bo = np.zeros(400); o_ = 'PE' if cp == 'CE' else 'CE'; np.add.at(bo, np.clip(b_[b_.cp == o_].j.values, 0, 399), b_[b_.cp == o_].lots.values)
        pcl = op[(cp, 'close')]; plo = op[(cp, 'low')]
        # book: short lots on this right from the real carried book + D0 body orders up to the end of the previous minute
        z1 = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & (O.cp == cp)]; carry = -((z1.side == 'Buy') * 2 - 1).mul(z1.lots).sum() if len(z1) else 0
        net = np.cumsum(sold - bs); book = carry + np.concatenate([[0], net[:-1]])
        for j in range(1, min(js, 375)):
            def mk(jj):
                f = {}
                for n in (5, 15, 30, 60):
                    a0 = max(jj - n, 0)
                    f[f'fav_ext{n}'] = float((l[jj] < l[a0:jj].min()) if cp == 'CE' else (h[jj] > h[a0:jj].max())) if jj > 0 else 0.0
                    f[f'adv_ext{n}'] = float((h[jj] > h[a0:jj].max()) if cp == 'CE' else (l[jj] < l[a0:jj].min())) if jj > 0 else 0.0
                for n in (1, 5, 15): f[f'fav_mv{n}'] = sg * (c[jj] - c[max(jj - n, 0)]) / st
                f['fav_intrabar'] = ((c[max(jj - 1, 0)] - l[jj]) if cp == 'CE' else (h[jj] - c[max(jj - 1, 0)])) / st
                x = pcl[ki[atmk[jj]]] if atmk[jj] in ki else None
                for n in (5, 15):
                    f[f'atm_prem_low{n}'] = float(plo[ki[atmk[jj]], jj] < np.nanmin(plo[ki[atmk[jj]], max(jj - n, 0):jj])) if (x is not None and jj > 0) else 0.0
                return f
            f = mk(j); fl = mk(j - 1)
            row = dict(cid=i, j=j, cp=cp, y=int(sold[j] > 0), **{k: labj[k][j] > 0 for k in labj}, wave=wv[j], wave_pm1=wv[max(j - 1, 0)] + wv[j + 1], fire=fi[j].sum(), fire_side=fi[j, 0 if cp == 'PE' else 1], moh=(j + 15) % 60, j_=j,
                       bb_same_prev5=bs[max(j - 5, 0):j].sum(), bb_oth_prev5=bo[max(j - 5, 0):j].sum(), bb_same_prev1=bs[j - 1], bb_oth_prev1=bo[j - 1], book=book[j], bb_same_now=bs[j], bb_oth_now=bo[j])
            row.update({f'A_{k}': v for k, v in f.items()}); row.update({f'B_{k}': v for k, v in fl.items()}); rows.append(row)
X = pd.DataFrame(rows); X['cpn'] = (X.cp == 'CE').astype(int)
base = ['wave', 'wave_pm1', 'fire', 'fire_side', 'moh', 'j_', 'cpn']; mA = [k for k in X if k.startswith('A_')]; mB = [k for k in X if k.startswith('B_')]; hist_ = ['bb_same_prev5', 'bb_oth_prev5', 'bb_same_prev1', 'bb_oth_prev1', 'book']
VAR = {'A same-minute market + rules': base + mA, 'B causal (market lagged 1 min)': base + mB, 'C A + real buy-back history (earlier minutes) + book': base + mA + hist_, 'C0 C + same-minute buy-backs (teacher-forced)': base + mA + hist_ + ['bb_same_now', 'bb_oth_now'], 'timetable + clock only': base[:2] + ['moh', 'j_', 'cpn']}
rng = np.random.default_rng(11); P = {}; out = []
def bauc(y, p, cid, reps=500):
    u = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in u}; bs = []
    for _ in range(reps):
        k = np.concatenate([idx[c] for c in rng.choice(u, len(u))]);
        if y[k].min() != y[k].max(): bs.append(roc_auc_score(y[k], p[k]))
    return np.percentile(bs, 2.5), np.percentile(bs, 97.5)
for nm, cols in VAR.items():
    p = np.zeros(len(X))
    for i in D0C:
        tr = X.cid != i
        if not (~tr).any(): continue
        m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=31, random_state=0).fit(X.loc[tr, cols], X.loc[tr, 'y']); p[~tr.values] = m.predict_proba(X.loc[~tr, cols])[:, 1]
    P[nm] = p; y = X.y.values; a = roc_auc_score(y, p); lo, hi = bauc(y, p, X.cid.values)
    nt = X.wave.values + X.wave_pm1.values == 0; a2 = roc_auc_score(y[nt], p[nt]); out.append(dict(variant=nm, AUC=a, ci_lo=lo, ci_hi=hi, AUC_no_wave_minutes=a2, cells=len(X), positives=int(y.sum())))
T = pd.DataFrame(out); T.to_csv(f'{OUT}/bl_d0s_auc.csv', index=False); print(T.round(3).to_string(index=False))
ty = []
for lab in ('grid_pair', 'offgrid_pair', 'solo'):
    k = (X[lab].values) | (X.y.values == 0); yy = X[lab].values[k].astype(int); d_ = dict(sell_label=lab, cells_with_sale=int(yy.sum()))
    for nm in VAR: d_[nm] = roc_auc_score(yy, P[nm][k])
    ty.append(d_)
TY = pd.DataFrame(ty); TY.to_csv(f'{OUT}/bl_d0s_auc_type.csv', index=False); print(TY.round(3).to_string(index=False))
# common-cause check: other-right same-minute buy-back lots as a score for solo cells, inside quintiles of the favourable intrabar + 1-min move
k = X.solo.values | (X.y.values == 0); Z = X[k].copy(); Z['ys'] = Z.solo.astype(int); Z['mv'] = Z.A_fav_mv1 + Z.A_fav_intrabar; Z['q'] = pd.qcut(Z.mv.rank(method='first'), 5, labels=False); cc = []
for q, g in Z.groupby('q'):
    cc.append(dict(quintile=int(q), mv_lo=g.mv.min(), mv_hi=g.mv.max(), cells=len(g), solo_rate=g.ys.mean(), AUC_bb_other_now=roc_auc_score(g.ys, g.bb_oth_now) if g.ys.nunique() == 2 else np.nan, AUC_bb_other_prev5=roc_auc_score(g.ys, g.bb_oth_prev5) if g.ys.nunique() == 2 else np.nan))
CC = pd.DataFrame(cc); CC.to_csv(f'{OUT}/bl_d0s_auc_cc.csv', index=False); print(CC.round(3).to_string(index=False))
pd.to_pickle(dict(X=X[['cid', 'j', 'cp', 'y', 'grid_pair', 'offgrid_pair', 'solo']], P=P), f'{OUT}/bl_d0s_auc_pred.pkl.gz')
rec('d0s4', dict(auc={r.variant: round(r.AUC, 4) for r in T.itertuples()}, auc_ci={r.variant: [round(r.ci_lo, 4), round(r.ci_hi, 4)] for r in T.itertuples()}, auc_no_wave={r.variant: round(r.AUC_no_wave_minutes, 4) for r in T.itertuples()}, cells=int(len(X)), positives=int(X.y.sum()),
                  by_type=TY.set_index('sell_label').round(4).to_dict('index'), cc=CC.round(4).to_dict('records')))
