"""D0 chunk 2, B5 (plan reports/D0_BUYBACKS_PLAN.md): one ranking number for D0 body buy-backs.
Cells: cycle x minute (1 .. 15:09 / before the stop) x right; positive = a body buy-back lot in scope in the cell. Leave-one-cycle-out gradient boosting.
A market + book features from the real book (open lots' highest ratio on the minute high, counts above 1.3/1.5/1.7/2.0, lowest premium held, lots <= 0.1 / 0.25 of entry, other-right highest ratio,
adverse spot moves and fresh extremes, premium speed, clock); B = the same with completed bars (previous close ratios, market lagged one minute); clock only.
AUC overall and by group (that group's cells vs no-buy-back cells), cycle-bootstrap CIs. Outputs bl_d0b_auc.csv, bl_d0b_auc_type.csv, bl_d0b_auc_pred.pkl.gz, bl_summary_d0b3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
src = open('bl_d0b_mach.py').read(); exec(src[:src.index('JJ = np.arange(375)')])
SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); rows = []
for i in D0C:
    d = C[i]; r = CY.iloc[i]; o = SP[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values; st = ref.STEP[r.und]; je = d['je']; xs = XS[XS.cid == i]
    lab = {(cp, g): set(xs[(xs.cp == cp) & (xs.grp == g)].j) for cp in ('CE', 'PE') for g in ('loss', 'mid-profit', 'deep-profit')}
    for j in range(1, je + 1):
        al = (d['j0'] <= j) & (d['jx'] >= j)
        for ci, cp in ((0, 'CE'), (1, 'PE')):
            m = al & (d['cp'] == ci); mo = al & (d['cp'] != ci); sg = 1 if cp == 'CE' else -1
            def bk(R_, Lo_):
                x = R_[m, j] if m.any() else np.array([0.0]); lo_ = Lo_[m, j] if m.any() else np.array([9.0]); xo = R_[mo, j] if mo.any() else np.array([0.0])
                return dict(n=int(m.sum()), rmax=x.max(), r13=(x >= 1.3).sum(), r15=(x >= 1.5).sum(), r17=(x >= 1.7).sum(), r20=(x >= 2.0).sum(), rmean=x.mean(), lo10=(lo_ <= 0.1).sum(), lo25=(lo_ <= 0.25).sum(), lomin=lo_.min(), ormax=xo.max(), on=int(mo.sum()))
            def mk(jj):
                f = {f'adv_mv{n}': sg * (c[jj] - c[max(jj - n, 0)]) / st for n in (1, 3, 5, 15)}
                for n in (5, 15, 30): f[f'adv_ext{n}'] = 0.0 if jj < 1 else (float(h[jj] > h[max(jj - n, 0):jj].max()) if cp == 'CE' else float(l[jj] < l[max(jj - n, 0):jj].min()))
                f['adv_intrabar'] = ((h[jj] - c[max(jj - 1, 0)]) if cp == 'CE' else (c[max(jj - 1, 0)] - l[jj])) / st; return f
            A_ = bk(d['H'], d['Lo']); B_ = bk(d['Cp'], np.concatenate([d['Lo'][:, :1], d['Lo'][:, :-1]], axis=1)); fa = mk(j); fb = mk(j - 1)
            y = {g: j in lab[(cp, g)] for g in ('loss', 'mid-profit', 'deep-profit')}
            row = dict(cid=i, j=j, cp=cp, cpn=ci, y=int(any(y.values())), **{f'y_{g}': v for g, v in y.items()}, blk=j % 15, j_=j, moh=(j + 15) % 60)
            row.update({f'A_{k}': v for k, v in {**A_, **fa}.items()}); row.update({f'B_{k}': v for k, v in {**B_, **fb}.items()}); rows.append(row)
X = pd.DataFrame(rows); base = ['blk', 'j_', 'moh', 'cpn']
VAR = {'A same-minute market + book': base + [k for k in X if k.startswith('A_')], 'B completed bars (causal)': base + [k for k in X if k.startswith('B_')], 'clock only': base,
       'A book ratios only (no market)': base + [f'A_{k}' for k in ('n', 'rmax', 'r13', 'r15', 'r17', 'r20', 'rmean', 'lo10', 'lo25', 'lomin', 'ormax', 'on')]}
rng = np.random.default_rng(3); P = {}; out = []
def bauc(y, p, cid, reps=500):
    u = np.unique(cid); idx = {c_: np.where(cid == c_)[0] for c_ in u}; bs = []
    for _ in range(reps):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))])
        if y[k].min() != y[k].max(): bs.append(roc_auc_score(y[k], p[k]))
    return np.percentile(bs, 2.5), np.percentile(bs, 97.5)
for nm, cols in VAR.items():
    p = np.zeros(len(X))
    for i in D0C:
        tr = (X.cid != i).values
        if tr.all(): continue
        mdl = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=31, random_state=0).fit(X.loc[tr, cols], X.y[tr]); p[~tr] = mdl.predict_proba(X.loc[~tr, cols])[:, 1]
    P[nm] = p; y = X.y.values; lo, hi = bauc(y, p, X.cid.values); out.append(dict(variant=nm, AUC=roc_auc_score(y, p), ci_lo=lo, ci_hi=hi, cells=len(X), positives=int(y.sum())))
T = pd.DataFrame(out); T.to_csv(f'{OUT}/bl_d0b_auc.csv', index=False); print(T.round(3).to_string(index=False)); ty = []
for g in ('loss', 'mid-profit', 'deep-profit'):
    k = X[f'y_{g}'].values | (X.y.values == 0); yy = X[f'y_{g}'].values[k].astype(int); dd = dict(group=g, cells_with_buyback=int(yy.sum()))
    for nm in VAR: dd[nm] = roc_auc_score(yy, P[nm][k])
    ty.append(dd)
TY = pd.DataFrame(ty); TY.to_csv(f'{OUT}/bl_d0b_auc_type.csv', index=False); print(TY.round(3).to_string(index=False))
pd.to_pickle(dict(X=X[['cid', 'j', 'cp', 'y', 'y_loss', 'y_mid-profit', 'y_deep-profit']], P=P), f'{OUT}/bl_d0b_auc_pred.pkl.gz')
rec('d0b3', dict(auc={r.variant: round(r.AUC, 4) for r in T.itertuples()}, ci={r.variant: [round(r.ci_lo, 4), round(r.ci_hi, 4)] for r in T.itertuples()}, by_group=TY.set_index('group').round(4).to_dict('index'), cells=int(len(X)), positives=int(X.y.sum())))
