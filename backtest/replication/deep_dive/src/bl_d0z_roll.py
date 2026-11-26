"""D0 roll-out and 'other' buy-backs (plan reports/D0_OPEN_ROLL_PLAN.md, Part R).
R0 label audit (roll-out chance level), R-H1 sale-clock features, R-H2 decayed-lot / age features, R-H3 two-stage product, tolerance outcome (reported separately).
LOCO + forward + within-cycle-label placebo of the SAME set. Run with OMP_NUM_THREADS=1.
Outputs bl_d0z_audit.csv, bl_d0z_roll_auc.csv, bl_d0z_roll_gate.csv, bl_d0z_roll_gain.csv, bl_summary_d0z1.json"""
import sys, json, warnings, time; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from multiprocessing import Pool
R = {}; CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); B = pd.read_pickle(f'{OUT}/bl_d0w_panel.pkl.gz').reset_index(drop=True); Pn = pd.read_pickle(f'{OUT}/bl_d0b_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); D = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz')
key = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; D['cid'] = [key.get((a, b), -1) for a, b in zip(D.und, D.expiry)]
# ---------- R0 label audit: share of in-scope buy-back lots followed by a same-right body sale within 60 s, real vs sale times shifted +-10 min
Xs = X[~X.type.astype(str).str.startswith(('1', '2'))].copy(); Xs['t'] = Xs.type.astype(str).str.slice(0, 1).astype(int); S = D[D.klass == 'body sell'][['cid', 'cp', 'tod']]; sale = {k: np.sort(v.tod.values) for k, v in S.groupby(['cid', 'cp'])}
def followed(row_t, c, cp, shift=0.0):
    a = sale.get((c, cp));
    if a is None: return False
    i = np.searchsorted(a + shift, row_t, 'left'); return i < len(a) and a[i] + shift <= row_t + 60
Xs['fol'] = [followed(t, c, cp) for t, c, cp in zip(Xs.tod, Xs.cid, Xs.cp)]; chance = np.mean([[followed(t, c, cp, sh) for t, c, cp in zip(Xs.tod, Xs.cid, Xs.cp)] for sh in (-600, 600, -900, 900)], axis=0); Xs['chance'] = chance
aud = Xs.groupby('t').agg(lots=('lid', 'size'), followed_real=('fol', 'mean'), followed_chance=('chance', 'mean')).reset_index(); aud['excess'] = aud.followed_real - aud.followed_chance; aud.round(4).to_csv(f'{OUT}/bl_d0z_audit.csv', index=False)
Xs['hr'] = pd.cut(Xs.tod, [0, 36000, 45000, 52000, 54600]); ah = Xs.groupby(['hr']).agg(real=('fol', 'mean'), chance=('chance', 'mean')).reset_index(); R['audit_by_hour'] = {str(r.hr): [float(r.real), float(r.chance)] for r in ah.itertuples()}
R['audit_roll_followed_real'] = float(Xs[Xs.t == 6].fol.mean()); R['audit_all_followed_real'] = float(Xs.fol.mean()); R['audit_all_followed_chance'] = float(Xs.chance.mean())
# ---------- extra features: decayed lots and age (lot panel, bars to j-1), sale-clock arrays
Pn = Pn.sort_values(['lid', 'j']).reset_index(drop=True); g = Pn.groupby('lid'); Pn['px_prev'] = g.px.shift(1); jp_ = g.j.shift(1); Pn.loc[jp_ != Pn.j - 1, 'px_prev'] = np.nan; Pn['px_prev'] = Pn.px_prev.fillna(Pn.entry); Pn['rp'] = Pn.px_prev / Pn.entry
Pn['first_j'] = g.j.transform('min'); Pn['age'] = np.where(Pn.origin == 'D0', Pn.j - Pn.first_j, np.nan)
for t in (0.5, 0.3, 0.2): Pn[f'le{int(t*10)}'] = (Pn.rp <= t).astype(int)
A = Pn.groupby(['cid', 'j', 'cp']).agg(n_le05=('le5', 'sum'), n_le03=('le3', 'sum'), n_le02=('le2', 'sum'), min_rp=('rp', 'min'), age_max=('age', 'max'), age_min=('age', 'min'), age_mean=('age', 'mean')).reset_index()
B = B.merge(A, on=['cid', 'j', 'cp'], how='left'); B['share_le05'] = B.n_le05 / B.n_open; B['to_1510'] = 354 - B.j; B['y_sell'] = (B.sell_all_lots > 0).astype(float)
B = B.sort_values(['cid', 'cp', 'j']).reset_index(drop=True)
for nm in ('y_roll_out', 'y_other_bb'): B[nm + '_tol'] = ((B[nm] > 0) | (B.groupby(['cid', 'cp'])[nm].shift(-1).fillna(0) > 0)).astype(float)
B['y_sale_next'] = ((B.y_sell > 0) | (B.groupby(['cid', 'cp']).y_sell.shift(-1).fillna(0) > 0)).astype(float)
cids = np.sort(B.cid.unique()); CID = B.cid.values; J = B.j.values.astype(int); GRP = (B.und.astype(str) + '|' + B.version.astype(str) + '|' + B.cp.astype(str)).values
def arrays(col, smooth):
    out = {}
    for gname in np.unique(GRP):
        m = GRP == gname; cc = np.unique(CID[m]); a = np.full((len(cc), 380), np.nan)
        for n, c in enumerate(cc): mm = m & (CID == c); a[n, J[mm]] = B[col].values[mm]
        if smooth:
            sm = a.copy()
            for d in (-1, 1): sm = np.fmax(sm, np.roll(a, d, axis=1))
            a = sm
        out[gname] = (cc, a)
    return out
ARR = {'ck_any': (arrays('y_any_bb', True), 0), 'ck_burst': (arrays('y_burst', True), 0), 'ck_sell_0': (arrays('y_sell', False), 0), 'ck_sell_p1': (arrays('y_sell', False), 1), 'ck_sell_m1': (arrays('y_sell', False), -1)}
CKN = list(ARR)
def clocks(ref):
    """ref: set of reference cycles. A row of cycle d excludes d itself."""
    out = {k: np.full(len(B), np.nan) for k in CKN}
    for k, (A_, d) in ARR.items():
        for gname, (cc, mat) in A_.items():
            m = np.where(GRP == gname)[0]; keep = np.isin(cc, list(ref)); S_ = np.nansum(mat[keep], axis=0); N_ = np.sum(~np.isnan(mat[keep]), axis=0); ci = np.searchsorted(cc, CID[m]); col = np.clip(J[m] + d, 0, 379); own = mat[ci, col]; ownv = ~np.isnan(own) & np.isin(CID[m], list(ref))
            num = S_[col] - np.where(ownv, own, 0); den = N_[col] - ownv.astype(int); out[k][m] = np.where(den > 0, num / np.maximum(den, 1), np.nan)
    return pd.DataFrame(out)
FAM = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j', 'gap_fav', 'carried_own', 'carried_other'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other', 'phx_prem_low_15', 'phx_prem_low_30', 'phx_prem_low_60', 'phx_prem_low_day'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'])
LS = ['n_open', 'n_itm1', 'n_itm2', 'n_itm3', 'n_itm5', 'n_itm8', 'max_itm', 'mean_itm', 'min_itm', 'loss_lakh', 'coll_lakh', 'loss_pct', 'n_r12', 'n_r14', 'max_ratio_prev', 'mean_ratio_prev', 'carried_share', 'share_itm2', 'share_r14']
SC = ['ck_sell_0', 'ck_sell_p1', 'ck_sell_m1']; AGE = ['n_le05', 'n_le03', 'n_le02', 'min_rp', 'age_max', 'age_min', 'age_mean', 'share_le05', 'to_1510']; REF = sum(FAM.values(), []) + LS + ['ck_any', 'ck_burst']
SETS = {'REF (ALL of D0_BURST_LONG)': REF, 'REF + sale clock': REF + SC, 'REF + decayed/age': REF + AGE, 'REF + sale clock + decayed/age': REF + SC + AGE}
OUTC = {'y_roll_out': 'roll-out', 'y_other_bb': 'other', 'y_roll_out_tol': 'roll-out (this or next minute)', 'y_other_bb_tol': 'other (this or next minute)', 'y_sale_next': 'same-right sale this or next minute'}
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
CKF = {}
def matrix(cols, fold):
    ck = [c for c in cols if c in CKN]; base = [c for c in cols if c not in CKN]; Xm = B[base].values.astype(float)
    return np.hstack([Xm, CKF[fold][ck].values.astype(float)]) if ck else Xm
def auc(y, p):
    r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def task(a):
    out, sname, kind, c = a; y = B[out].values.copy(); te = np.isin(CID, c if isinstance(c, list) else [c]); tr = ~te
    if kind == 'placebo':
        rng = np.random.default_rng(int(c) + 1)
        for cc in cids: m = np.where(CID == cc)[0]; y[m] = rng.permutation(y[m])
    Xm = matrix(SETS[sname], 'fw' if kind == 'forward' else c); m = mk(); m.fit(Xm[tr], y[tr]); return (out, sname, kind, c), np.where(te)[0], m.predict_proba(Xm[te])[:, 1]
if __name__ == '__main__':
    t0 = time.time(); ver = B.groupby('cid').version.first(); exp_ = B.groupby('cid').expiry.first(); fw_tr = []; fw_te = []
    for v in ver.unique(): cv = sorted([c for c in cids if ver[c] == v], key=lambda c: exp_[c]); n = int(np.ceil(len(cv) * 2 / 3)); fw_tr += cv[:n]; fw_te += cv[n:]
    CKF.update({int(c): clocks(set(cids) - {c}) for c in cids}); CKF['fw'] = clocks(set(fw_tr)); print('clocks', round(time.time() - t0), flush=True)
    sets_for = lambda o: SETS if o != 'y_sale_next' else {k: v for k, v in SETS.items() if k in ('REF + sale clock',)}
    jobs = [(o, s, 'loco', int(c)) for o in OUTC for s in sets_for(o) for c in cids] + [(o, s, 'forward', fw_te) for o in OUTC for s in sets_for(o)]
    with Pool(4) as pool: res = list(pool.imap_unordered(task, jobs, chunksize=4))
    print('fits', len(res), round(time.time() - t0), flush=True); P = {}
    for (o, s, k, c), idx, p in res: P.setdefault((o, s, k), np.full(len(B), np.nan))[idx] = p
    rng = np.random.default_rng(3); idxc = {c: np.where(CID == c)[0] for c in cids}; rows = []
    def ci(y, p, nb=300):
        bs = []
        for _ in range(nb):
            ii = np.concatenate([idxc[c] for c in rng.choice(cids, len(cids))]); yy = y[ii]
            if 0 < yy.sum() < len(yy): bs.append(auc(yy, p[ii]))
        return float(np.quantile(bs, .025)), float(np.quantile(bs, .975))
    for o, nm in OUTC.items():
        y = B[o].values
        for s in sets_for(o):
            p = P[(o, s, 'loco')]; lo, hi = ci(y, p); tm = np.isin(CID, fw_te); pf = P[(o, s, 'forward')]
            wc = [auc(y[idxc[c]], p[idxc[c]]) for c in cids if 0 < y[idxc[c]].sum() < len(idxc[c])]
            rows.append(dict(outcome=nm, set=s, auc_loco=auc(y, p), lo=lo, hi=hi, within_cycle=float(np.mean(wc)), forward_auc=auc(y[tm], pf[tm]) if 0 < y[tm].sum() < tm.sum() else np.nan, positives=int(y.sum()), cells=len(y)))
    AU = pd.DataFrame(rows)
    # R-H3: two-stage product
    Pb = pd.read_pickle(f'{OUT}/bl_d0w_burst_pred.pkl.gz'); Bo = pd.read_pickle(f'{OUT}/bl_d0w_panel.pkl.gz').reset_index(drop=True)
    pb = pd.Series(Pb[('y_any_bb', 'ALL (E + lot state + clock)', 'loco')], index=pd.MultiIndex.from_arrays([Bo.cid, Bo.cp, Bo.j])); pb = pb[~pb.index.duplicated()]
    ps = pd.Series(P[('y_sale_next', 'REF + sale clock', 'loco')], index=pd.MultiIndex.from_arrays([B.cid, B.cp, B.j]))
    prod = pb.reindex(ps.index).values * ps.values; ok = np.isfinite(prod)
    for o in ('y_roll_out', 'y_other_bb'):
        y = B[o].values; lo, hi = ci(y[ok], prod[ok]) if False else (np.nan, np.nan); rows.append(dict(outcome=OUTC[o], set='two-stage product P(buy-back) x P(sale next)', auc_loco=auc(y[ok], prod[ok]), lo=lo, hi=hi, within_cycle=np.nan, forward_auc=np.nan, positives=int(y[ok].sum()), cells=int(ok.sum())))
    AU = pd.DataFrame(rows); AU.round(4).to_csv(f'{OUT}/bl_d0z_roll_auc.csv', index=False)
    # placebo of the best set (same set) for the two gate outcomes + the paired gain over REF
    G = []; gain = []
    for o in ('y_roll_out', 'y_other_bb'):
        nm = OUTC[o]; z = AU[(AU.outcome == nm) & AU.set.isin(SETS)].set_index('set'); best = z.auc_loco.idxmax(); jobs2 = [(o, best, 'placebo', int(c)) for c in cids]
        with Pool(4) as pool: r2 = list(pool.imap_unordered(task, jobs2, chunksize=4))
        pp = np.full(len(B), np.nan)
        for (_, _, _, c), idx, p in r2: pp[idx] = p
        y = B[o].values; a = z.loc[best]; pla = auc(y, pp)
        ref_p = P[(o, 'REF (ALL of D0_BURST_LONG)', 'loco')]; bp = P[(o, best, 'loco')]; d = auc(y, bp) - auc(y, ref_p); bs = []
        for _ in range(300):
            ii = np.concatenate([idxc[c] for c in rng.choice(cids, len(cids))]); yy = y[ii]
            if 0 < yy.sum() < len(yy): bs.append(auc(yy, bp[ii]) - auc(yy, ref_p[ii]))
        ok_ = a.auc_loco >= 0.85 and a.lo > 0.82 and a.forward_auc >= 0.80 and pla < 0.65
        G.append(dict(outcome=nm, best_set=best, auc=a.auc_loco, lo=a.lo, hi=a.hi, forward=a.forward_auc, within_cycle=a.within_cycle, placebo=pla, ref_auc=z.loc['REF (ALL of D0_BURST_LONG)'].auc_loco, gate='met' if ok_ else 'not met'))
        gain.append(dict(outcome=nm, best_set=best, gain_over_REF=d, lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975))))
    pd.DataFrame(G).round(4).to_csv(f'{OUT}/bl_d0z_roll_gate.csv', index=False); pd.DataFrame(gain).round(4).to_csv(f'{OUT}/bl_d0z_roll_gain.csv', index=False); rec('d0z1', R)
    pd.to_pickle(P, f'{OUT}/bl_d0z_roll_pred.pkl.gz'); print('done', round(time.time() - t0)); pd.set_option('display.width', 250); print(aud.round(3).to_string()); print(json.dumps(R, indent=1)[:1500]); print(pd.DataFrame(G).round(3).to_string()); print(pd.DataFrame(gain).round(4).to_string()); print(AU.round(3).to_string())
