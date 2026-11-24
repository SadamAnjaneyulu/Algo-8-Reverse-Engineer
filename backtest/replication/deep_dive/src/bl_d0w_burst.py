"""D0 burst buy-backs and the open buy-back types (plan reports/D0_BURST_LONG_PLAN.md, Part 1).
Cell outcomes: any buy-back, burst (>= 5 lots), stop-loss, take-profit, partner, roll-out, burst member, other. Feature sets: E (existing families), E+LS (lot state: ITM depth, side loss, lots at risk), E+CK (learned clock), ALL, base+ITM only.
LOCO + forward + within-cycle-label placebo; same-minute-information variant reported separately (not for the gate). Lot-level: which open lots a burst takes.
Run with OMP_NUM_THREADS=1. Outputs bl_d0w_burst_auc.csv, bl_d0w_burst_gate.csv, bl_d0w_burst_lots.csv, bl_d0w_burst_size.csv, bl_d0w_burst_pred.pkl.gz, bl_summary_d0w2.json"""
import sys, json, warnings, time; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from multiprocessing import Pool
B = pd.read_pickle(f'{OUT}/bl_d0w_panel.pkl.gz').reset_index(drop=True); R = {}
FAM = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j', 'gap_fav', 'carried_own', 'carried_other'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other', 'phx_prem_low_15', 'phx_prem_low_30', 'phx_prem_low_60', 'phx_prem_low_day'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'])
LS = ['n_open', 'n_itm1', 'n_itm2', 'n_itm3', 'n_itm5', 'n_itm8', 'max_itm', 'mean_itm', 'min_itm', 'loss_lakh', 'coll_lakh', 'loss_pct', 'n_r12', 'n_r14', 'max_ratio_prev', 'mean_ratio_prev', 'carried_share', 'share_itm2', 'share_r14']
ITM = ['n_itm1', 'n_itm2', 'n_itm3', 'n_itm5', 'n_itm8', 'max_itm', 'mean_itm', 'min_itm', 'share_itm2']
SAME = ['bb_own_same_min', 'bb_other_same_min', 'sl_other_same_min']
E_ = sum(FAM.values(), []); CKN = ['ck_any', 'ck_burst']
OUTC = {'y_any_bb': 'any buy-back', 'y_burst': 'burst (>= 5 lots)', 'y_stop_loss': 'stop-loss', 'y_take_profit': 'take-profit', 'y_partner': 'partner', 'y_roll_out': 'roll-out', 'y_burst_member': 'burst member', 'y_other_bb': 'other'}
SETS = {'E existing families': E_, 'E + lot state': E_ + LS, 'E + clock': E_ + CKN, 'ALL (E + lot state + clock)': E_ + LS + CKN, 'base + ITM depth only': FAM['base'] + ITM}
cids = np.sort(B.cid.unique()); CID = B.cid.values; GRP = (B.und.astype(str) + '|' + B.version.astype(str) + '|' + B.cp.astype(str)).values; J = B.j.values.astype(int)
# ---------- learned clock: share of the other training cycles of the same underlying x version x right with a buy-back (any / burst) in this minute +-1
def build_arrays(col):
    A = {}
    for g in np.unique(GRP):
        m = GRP == g; cc = np.unique(CID[m]); a = np.full((len(cc), 377), np.nan)
        for n, c in enumerate(cc):
            mm = m & (CID == c); a[n, J[mm]] = B[col].values[mm]
        sm = a.copy()
        for d in (-1, 1): sh = np.roll(a, d, axis=1); sm = np.fmax(sm, sh)                      # +-1 minute (NaN-safe max)
        A[g] = (cc, sm)
    return A
CKA = {'ck_any': build_arrays('y_any_bb'), 'ck_burst': build_arrays('y_burst')}
def clock_cols(excl):
    """clock features for a fold: reference cycles = all but `excl`; a row of cycle d excludes d as well"""
    out = {k: np.full(len(B), np.nan) for k in CKN}
    for k, A in CKA.items():
        for g, (cc, sm) in A.items():
            m = np.where(GRP == g)[0]; keep = cc != excl; S = np.nansum(sm[keep], axis=0); N = np.sum(~np.isnan(sm[keep]), axis=0)
            ci = np.searchsorted(cc, CID[m]); own = sm[ci, J[m]]; ownv = ~np.isnan(own) & (CID[m] != excl)
            num = S[J[m]] - np.where(ownv, own, 0); den = N[J[m]] - ownv.astype(int); out[k][m] = np.where(den > 0, num / np.maximum(den, 1), np.nan)
    return np.column_stack([out[k] for k in CKN])
CKF = {int(c): clock_cols(c) for c in cids}; CKF['all'] = clock_cols(-1)
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def matrix(cols, fold):
    base = [c for c in cols if c not in CKN]; X = B[base].values.astype(float); X = np.hstack([X, CKF[fold]]) if any(c in CKN for c in cols) else X; return X
def auc(y, p):
    r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def task(a):
    out, sname, kind, c = a; cols = SETS[sname]; y = B[out].values; te = np.isin(CID, c if isinstance(c, list) else [c]); tr = ~te
    if kind == 'placebo':
        rng = np.random.default_rng(int(c) + 1); y = y.copy()
        for cc in cids:
            m = np.where(CID == cc)[0]; y[m] = rng.permutation(y[m])
    X = matrix(cols, c if kind != 'forward' else 'all');
    if kind == 'forward': X = matrix(cols, 'all')
    m = mk(); m.fit(X[tr], y[tr]); return (out, sname, kind, c), np.where(te)[0], m.predict_proba(X[te])[:, 1]
if __name__ == '__main__':
    t0 = time.time(); ver = B.groupby('cid').version.first(); exp_ = B.groupby('cid').expiry.first(); fw_tr = []; fw_te = []
    for v in ver.unique():
        cv = sorted([c for c in cids if ver[c] == v], key=lambda c: exp_[c]); n = int(np.ceil(len(cv) * 2 / 3)); fw_tr += cv[:n]; fw_te += cv[n:]
    jobs = [(o, s, 'loco', int(c)) for o in OUTC for s in SETS for c in cids] + [(o, s, 'forward', fw_te) for o in OUTC for s in SETS] + [(o, 'ALL (E + lot state + clock)', 'placebo', int(c)) for o in OUTC for c in cids]
    CKFW = None
    # forward clock: reference cycles = forward-train cycles only
    def clock_cols_set(refset):
        out = {k: np.full(len(B), np.nan) for k in CKN}
        for k, A in CKA.items():
            for g, (cc, sm) in A.items():
                m = np.where(GRP == g)[0]; keep = np.isin(cc, refset); S = np.nansum(sm[keep], axis=0); N = np.sum(~np.isnan(sm[keep]), axis=0); ci = np.searchsorted(cc, CID[m]); own = sm[ci, J[m]]; ownv = ~np.isnan(own) & np.isin(CID[m], refset)
                num = S[J[m]] - np.where(ownv, own, 0); den = N[J[m]] - ownv.astype(int); out[k][m] = np.where(den > 0, num / np.maximum(den, 1), np.nan)
        return np.column_stack([out[k] for k in CKN])
    CKF['all'] = clock_cols_set(fw_tr)                                   # forward: the clock is learned on the forward-train cycles only
    def run(jobs_):
        with Pool(4) as pool: return list(pool.imap_unordered(task, jobs_, chunksize=4))
    res = run(jobs); print('fits', len(res), round(time.time() - t0), flush=True)
    P = {}
    for (o, s, k, c), idx, p in res:
        P.setdefault((o, s, k), np.full(len(B), np.nan))[idx] = p
    pd.to_pickle(P, f'{OUT}/bl_d0w_burst_pred.pkl.gz')
    rows = []; rng = np.random.default_rng(3); idxc = {c: np.where(CID == c)[0] for c in cids}
    for o in OUTC:
        y = B[o].values
        for s in SETS:
            p = P[(o, s, 'loco')]; a = auc(y, p); bs = []
            for _ in range(300):
                ii = np.concatenate([idxc[c] for c in rng.choice(cids, len(cids))]); yy = y[ii]
                if 0 < yy.sum() < len(yy): bs.append(auc(yy, p[ii]))
            wc = [auc(y[idxc[c]], p[idxc[c]]) for c in cids if 0 < y[idxc[c]].sum() < len(idxc[c])]
            pf = P[(o, s, 'forward')]; tm = np.isin(CID, fw_te); af = auc(y[tm], pf[tm]) if 0 < y[tm].sum() < tm.sum() else np.nan
            pp = P.get((o, s, 'placebo')); ap = auc(y, pp) if pp is not None else np.nan
            rows.append(dict(outcome=OUTC[o], set=s, auc_loco=a, lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975)), within_cycle=float(np.mean(wc)), forward_auc=af, placebo_auc=ap, cells=len(y), positives=int(y.sum())))
    AU = pd.DataFrame(rows); AU.round(4).to_csv(f'{OUT}/bl_d0w_burst_auc.csv', index=False)
    G = []
    for o, nm in OUTC.items():
        z = AU[AU.outcome == nm].set_index('set'); best = z.auc_loco.drop('base + ITM depth only').idxmax(); a = z.loc[best]; ok = a.auc_loco >= 0.85 and a.lo > 0.82 and a.forward_auc >= 0.80 and (np.isnan(a.placebo_auc) or a.placebo_auc < 0.65)
        G.append(dict(outcome=nm, best_set=best, auc=a.auc_loco, lo=a.lo, forward=a.forward_auc, placebo=a.placebo_auc, within_cycle=a.within_cycle, E_auc=z.loc['E existing families'].auc_loco, gain_over_E=a.auc_loco - z.loc['E existing families'].auc_loco, gate='met' if ok else 'not met'))
    pd.DataFrame(G).round(4).to_csv(f'{OUT}/bl_d0w_burst_gate.csv', index=False)
    print('done', round(time.time() - t0)); pd.set_option('display.width', 250); print(pd.DataFrame(G).round(3).to_string()); print(AU.round(3).to_string())
