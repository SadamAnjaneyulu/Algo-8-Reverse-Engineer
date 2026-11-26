"""N3: from predictors to a rule (reports/D0_CTRIG_PLAN.md). Depth-3 trees, leave-one-cycle-out; threshold picked on the training cycles; cell-level F1 with +-1 minute tolerance.
phx_* features and the two hand rules were added after N2 (post-hoc). Outputs bl_d0n_n3.csv, bl_d0n_n3_tree.txt, bl_summary_d0n4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.tree import DecisionTreeClassifier as DT, export_text
PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz').sort_values(['cid', 'cp', 'j']).reset_index(drop=True); rng = np.random.default_rng(101); R = {}
spot = ['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60']
prem = ['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'phx_prem_low_15', 'phx_prem_low_30', 'phx_prem_low_60', 'phx_prem_low_day']
book = ['n_own', 'n_other', 'share_own', 'expo_share_own', 'mark_own', 'mark_other', 'mtm_lakh', 'sell_own_5', 'sell_own_15', 'since_sale_own']
bbf = ['bb_other_1', 'bb_other_5', 'sl_other_1', 'sl_other_5', 'since_bb_other']; base = ['min_in_15', 'min_in_5', 'hour', 'is_ce', 'und_nifty', 'v2']
SETS = {'tree: spot + time': base + spot, 'tree: premium + time': base + prem, 'tree: spot + premium + time': base + spot + prem, 'tree: all market/book': base + spot + prem + book, 'tree: all + past buy-backs': base + spot + prem + book + bbf}
def tol(flag, y, cp_cid, tolerance=True):
    """cell-level hits with +-1 minute tolerance, per (cid, cp) series (PN is sorted by cid, cp, j)"""
    tp_p = 0; fp = 0; rec_hit = 0; npos = 0; nflag = 0
    for _, ix in cp_cid.items():
        f = flag[ix].astype(bool); a = y[ix].astype(bool); fa = (f | np.r_[f[1:], False] | np.r_[False, f[:-1]]) if tolerance else f; aa = (a | np.r_[a[1:], False] | np.r_[False, a[:-1]]) if tolerance else a
        tp_p += int((f & aa).sum()); nflag += int(f.sum()); rec_hit += int((a & fa).sum()); npos += int(a.sum())
    pr = tp_p / max(nflag, 1); rc = rec_hit / max(npos, 1); return pr, rc, 2 * pr * rc / max(pr + rc, 1e-9), nflag
GRP = {k: np.where((PN.cid.values == k[0]) & (PN.cp.values == k[1]))[0] for k in PN.groupby(['cid', 'cp']).groups}
yv = PN.y.values
def run(cols, perm=False, rule=None):
    flag = np.zeros(len(PN), bool); Xm = PN[cols].values.copy() if cols else None
    if perm:
        for c_ in PN.cid.unique():
            m = np.where(PN.cid.values == c_)[0]; Xm[m] = Xm[rng.permutation(m)]
    if rule is not None: return rule
    Xm = np.nan_to_num(Xm, nan=-9.0)
    for c_ in PN.cid.unique():
        te = PN.cid.values == c_; t = DT(max_depth=3, min_samples_leaf=100, random_state=0).fit(Xm[~te], yv[~te]); ptr = t.predict_proba(Xm[~te])[:, 1]; pte = t.predict_proba(Xm[te])[:, 1]
        best = (-1, 0.5)
        for th in np.arange(0.15, 0.65, 0.05):
            fl = np.zeros(len(PN), bool); fl[np.where(~te)[0]] = ptr >= th; sub = {k: v for k, v in GRP.items() if k[0] != c_}; f1 = tol(fl, yv, sub, False)[2]          # post-hoc correction: threshold chosen on exact-cell F1 (the +-1 minute metric has a high floor)
            if f1 > best[0]: best = (f1, th)
        flag[np.where(te)[0]] = pte >= best[1]
    return flag
def boot_f1(flag, nb=200, tolerance=True):
    cids = PN.cid.unique(); out = []
    for _ in range(nb):
        k = rng.choice(cids, len(cids)); sub = {}; 
        for n_, c_ in enumerate(k):
            for kk, v in GRP.items():
                if kk[0] == c_: sub[(n_, kk[1])] = v
        out.append(tol(flag, yv, sub, tolerance)[2])
    return np.percentile(out, [2.5, 97.5])
rows = []
for nm, cols in SETS.items():
    fl = run(cols); pr, rc, f1, nf = tol(fl, yv, GRP); ci = boot_f1(fl); fp = run(cols, perm=True); prp, rcp, f1p, _ = tol(fp, yv, GRP); pe, re_, fe, _ = tol(fl, yv, GRP, False); cie = boot_f1(fl, 200, False); pep, rep_, fep, _ = tol(fp, yv, GRP, False)
    rows.append(dict(rule=nm, exact_precision=pe, exact_recall=re_, exact_F1=fe, exact_F1_lo=cie[0], exact_F1_hi=cie[1], exact_placebo_F1=fep, exact_ratio_vs_placebo=fe / max(fep, 1e-9), tol_F1=f1, tol_placebo_F1=f1p, flagged_cells=nf)); print(rows[-1])
for nm, f in (('hand rule (post-hoc): ATM premium at its day low (close at j-1)', PN.phx_prem_low_day.values > 0), ('hand rule (post-hoc): ATM premium at 60-min low', PN.phx_prem_low_60.values > 0), ('hand rule (post-hoc, uses bar j): ATM premium makes new day low in minute j', PN.phx_prem_newlow_c.values > 0), ('hand rule (post-hoc): day low OR spot fresh 60-min extreme', (PN.phx_prem_low_day.values > 0) | (PN.fresh_60.values > 0))):
    pr, rc, f1, nf = tol(f, yv, GRP); pe, re_, fe, _ = tol(f, yv, GRP, False); cie = boot_f1(f, 200, False); rows.append(dict(rule=nm, exact_precision=pe, exact_recall=re_, exact_F1=fe, exact_F1_lo=cie[0], exact_F1_hi=cie[1], exact_placebo_F1=np.nan, exact_ratio_vs_placebo=np.nan, tol_F1=f1, tol_placebo_F1=np.nan, flagged_cells=nf)); print(rows[-1])
pa, ra, fa_, na = tol(np.ones(len(PN), bool), yv, GRP); pae, rae, fae, _ = tol(np.ones(len(PN), bool), yv, GRP, False); R['flag_all'] = dict(tol_F1=fa_, exact_F1=fae, exact_precision=pae, base_rate=float(yv.mean()))
N3 = pd.DataFrame(rows); N3.to_csv(f'{OUT}/bl_d0n_n3.csv', index=False)
cols = base + spot + prem + book; t = DT(max_depth=3, min_samples_leaf=100, random_state=0).fit(np.nan_to_num(PN[cols].values, nan=-9.0), yv); open(f'{OUT}/bl_d0n_n3_tree.txt', 'w').write(export_text(t, feature_names=cols)); print(export_text(t, feature_names=cols))
R['n3'] = N3.round(4).to_dict('records'); rec('d0n4', R)
