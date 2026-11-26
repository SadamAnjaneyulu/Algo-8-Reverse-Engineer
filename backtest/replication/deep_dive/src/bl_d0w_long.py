"""D0 body-stream longs (plan reports/D0_BURST_LONG_PLAN.md, Part 2).
L1 strike rule (premium target P*, fraction of ATM premium, fixed OTM steps; fitted on training cycles, leave-one-cycle-out, +15 min placebo), L2 opening lot count against book quantities,
L3/L4 buy and sell presence in a minute cell (E existing families, + book of longs and shorts, + state of the held longs), L5 clearance rule (which longs are sold at 15:14).
Run with OMP_NUM_THREADS=1. Outputs bl_d0w_long_strike.csv, bl_d0w_long_open.csv, bl_d0w_long_auc.csv, bl_d0w_long_gate.csv, bl_d0w_long_clear.csv, bl_d0w_longstate.pkl.gz, bl_summary_d0w3.json"""
import sys, json, warnings, time; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from multiprocessing import Pool
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); TL = pd.read_pickle(f'{OUT}/bl_d0u_timeline.pkl.gz'); R = {}
key = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; O = pd.read_pickle(f'{OUT}/bl_all_orders.pkl.gz'); O['cid'] = [key.get((a, b), -1) for a, b in zip(O.und, O.expiry)]; O = O[O.cid >= 0]
B = pd.read_pickle(f'{OUT}/bl_d0w_panel.pkl.gz').reset_index(drop=True); STEP = {i: ref.STEP[CY.und[i]] for i in range(len(CY))}
cl = {i: SPT[(CY.und[i], CY.expiry[i])].close.values for i in range(len(CY)) if (CY.und[i], CY.expiry[i]) in SPT}; op_ = {i: OPT[(CY.und[i], CY.expiry[i])] for i in range(len(CY)) if (CY.und[i], CY.expiry[i]) in OPT}
# ---------- L1 strike rule on every body-stream long buy order of D0
Db = O[(O.dayno == 1) & (O.module == 'num') & (O.role == 'open_long')].copy(); Db['jm'] = ((Db.tod - 33300) // 60).astype(int); rows = []
GRID_P = np.arange(0.5, 6.01, 0.25); GRID_F = np.arange(0.005, 0.0601, 0.0025); GRID_K = np.arange(1, 41)
def otm_set(c, cp, j):
    j = int(min(max(j, 0), 375)); op = op_[c]; K = op['K']; jj = min(max(j - 1, 0), 374); pr = op[(cp, 'close')][:, jj] if j >= 1 else op[(cp, 'open')][:, 0]; spv = cl[c][jj] if j >= 1 else SPT[(CY.und[c], CY.expiry[c])].open.values[0]
    off = (K - spv) / STEP[c] * (1 if cp == 'CE' else -1); ok = (off > 0) & np.isfinite(pr) & (pr > 0); a = float(op[(cp, 'close')][np.argmin(np.abs(K - spv)), jj]) if j >= 1 else float(op[(cp, 'open')][np.argmin(np.abs(K - spv)), 0])
    return K[ok], pr[ok], off[ok], a
def predict_all(c, cp, j):
    K, pr, off, a = otm_set(c, cp, j)
    if len(K) == 0: return None
    pP = np.array([K[np.argmin(np.abs(pr - p))] for p in GRID_P]); pF = np.array([K[np.argmin(np.abs(pr - f * a))] if a == a else np.nan for f in GRID_F]); pK = np.array([K[np.argmin(np.abs(off - k))] for k in GRID_K])
    return pP, pF, pK
recs = []
for r in Db.itertuples():
    pr0 = predict_all(r.cid, r.cp, r.jm); pr15 = predict_all(r.cid, r.cp, min(r.jm + 15, 354))
    if pr0 is None or pr15 is None: continue
    recs.append(dict(cid=r.cid, und=r.und, cp=r.cp, jm=r.jm, strike=r.strike, lots=r.lots, step=STEP[r.cid], pred=pr0, pred15=pr15, opening=r.jm <= 1))
Lr = pd.DataFrame(recs); R['l1_orders'] = len(Lr); R['l1_opening_orders'] = int(Lr.opening.sum())
def loco_rule(df, which, grid, weight_lots=True):
    """fit the rule parameter on the other cycles (max exact-match share by lots), score the held-out cycle; also score the +15 min placebo with the same parameter"""
    ex = ex15 = w1 = tot = 0.0; picks = []
    for c in df.cid.unique():
        tr = df[df.cid != c]; te = df[df.cid == c]
        if len(tr) == 0: continue
        sc = np.zeros(len(grid))
        for q in tr.itertuples(): sc += (q.pred[which] == q.strike) * q.lots
        g = int(np.argmax(sc)); picks.append(float(grid[g]))
        for q in te.itertuples():
            tot += q.lots; ex += (q.pred[which][g] == q.strike) * q.lots; ex15 += (q.pred15[which][g] == q.strike) * q.lots; w1 += (abs(q.pred[which][g] - q.strike) <= q.step + 1e-6) * q.lots
    return dict(exact=ex / tot, within1=w1 / tot, placebo_exact_plus15=ex15 / tot, param_median=float(np.median(picks)), param_q25=float(np.quantile(picks, .25)), param_q75=float(np.quantile(picks, .75)), lots=tot)
rows = []
for sub, df in (('all buy orders', Lr), ('opening (09:15-09:16)', Lr[Lr.opening]), ('intraday', Lr[~Lr.opening]), ('NIFTY', Lr[Lr.und == 'NIFTY']), ('SENSEX', Lr[Lr.und == 'SENSEX'])):
    for nm, w, g in (('premium target P* (Rs)', 0, GRID_P), ('fraction of ATM premium', 1, GRID_F), ('fixed OTM steps', 2, GRID_K)):
        if len(df) > 5: rows.append(dict(subset=sub, rule=nm, orders=len(df), **loco_rule(df, w, g)))
L1 = pd.DataFrame(rows); L1.round(4).to_csv(f'{OUT}/bl_d0w_long_strike.csv', index=False)
# ---------- L2 opening count
op_rows = []
for c in sorted(set(Lr[Lr.opening].cid)):
    for cp in ('CE', 'PE'):
        z = Lr[(Lr.cid == c) & (Lr.cp == cp) & Lr.opening]; t = TL.get((c, cp)); o = TL.get((c, 'PE' if cp == 'CE' else 'CE'))
        if t is None: continue
        op_rows.append(dict(cid=c, und=CY.und[c], cp=cp, open_lots=int(z.lots.sum()) if len(z) else 0, S0=t['S0'], L0=t['L0'], SmL=t['S0'] - t['L0'], S0_oth=o['S0'] if o else np.nan, S_both=t['S0'] + (o['S0'] if o else 0)))
OP = pd.DataFrame(op_rows); res = []
cands = {'carried shorts on the right (S0)': 'S0', 'carried longs on the right (L0)': 'L0', 'carried shorts - longs (S0 - L0)': 'SmL', 'carried shorts both rights': 'S_both'}
for nm, col in cands.items():
    pred = np.zeros(len(OP))
    for c in OP.cid.unique():
        tr = OP[OP.cid != c]; m = float(np.median(tr.open_lots / tr[col].replace(0, np.nan)).__float__()) if (tr[col] > 0).any() else 0; te = OP.cid == c; pred[te.values] = np.round(m * OP[te][col])
    y = OP.open_lots.values; res.append(dict(candidate=nm, n=len(OP), exact=float((pred == y).mean()), within2=float((np.abs(pred - y) <= 2).mean()), mae=float(np.abs(pred - y).mean()), rho=float(stats.spearmanr(OP[col], y).correlation)))
base = np.zeros(len(OP))
for c in OP.cid.unique():
    tr = OP[(OP.cid != c) & (OP.und == OP[OP.cid == c].und.iloc[0])]; base[(OP.cid == c).values] = np.median(tr.open_lots)
res.append(dict(candidate='baseline: median of the other cycles of the same underlying', n=len(OP), exact=float((base == OP.open_lots.values).mean()), within2=float((np.abs(base - OP.open_lots.values) <= 2).mean()), mae=float(np.abs(base - OP.open_lots.values).mean()), rho=np.nan))
L2 = pd.DataFrame(res); L2.round(4).to_csv(f'{OUT}/bl_d0w_long_open.csv', index=False)
# ---------- state of the held longs at the start of each minute (all modules, both days), average cost per strike
def longstate(c):
    z = O[(O.cid == c) & O.role.isin(['open_long', 'close_long'])].copy(); z['t'] = np.where(z.dayno == 0, -1, z.tod); z = z.sort_values(['dayno', 'tt_first', 'row']); out = {}
    for cp in ('CE', 'PE'):
        zz = z[z.cp == cp]; st = {}; i0 = 0; rows_ = zz.itertuples(); lst = list(zz.itertuples()); op = op_[c]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; arr = np.full((376, 6), np.nan)
        for q in lst:
            if q.dayno == 0:
                s_ = st.setdefault(int(q.strike), [0, 0.0])
                if q.role == 'open_long': s_[0] += q.lots; s_[1] += q.lots * q.px_avg
                else: avg = s_[1] / s_[0] if s_[0] else 0; s_[0] -= q.lots; s_[1] -= q.lots * avg
        d0 = [q for q in lst if q.dayno == 1]; p = 0
        for j in range(1, 376):
            lim = 33300 + 60 * j
            while p < len(d0) and d0[p].tod < lim:
                q = d0[p]; s_ = st.setdefault(int(q.strike), [0, 0.0])
                if q.role == 'open_long': s_[0] += q.lots; s_[1] += q.lots * q.px_avg
                else: avg = s_[1] / s_[0] if s_[0] else 0; s_[0] -= q.lots; s_[1] -= q.lots * avg
                p += 1
            lots = [(k, v[0], v[1] / v[0]) for k, v in st.items() if v[0] > 0]
            if not lots: arr[j] = [0, np.nan, np.nan, np.nan, np.nan, 0]; continue
            pr = np.array([op[(cp, 'close')][ki[k], j - 1] if k in ki else np.nan for k, _, _ in lots]); n = np.array([l for _, l, _ in lots], float); cost = np.array([cc for _, _, cc in lots]); rat = pr / cost
            sp = cl[c][j - 1]; off = np.array([((k - sp) / STEP[c]) * (1 if cp == 'CE' else -1) for k, _, _ in lots]); ok = np.isfinite(rat)
            arr[j] = [n.sum(), np.average(rat[ok], weights=n[ok]) if ok.any() else np.nan, np.nanmin(rat) if ok.any() else np.nan, np.nanmax(rat) if ok.any() else np.nan, np.average(off, weights=n), 0]
        out[cp] = arr
    return out
LS_ = {c: longstate(c) for c in sorted(B.cid.unique())}; pd.to_pickle(LS_, f'{OUT}/bl_d0w_longstate.pkl.gz')
B['Ln_own'] = [LS_[c][cp][j][0] for c, cp, j in zip(B.cid, B.cp, B.j)]; B['Lrat_mean'] = [LS_[c][cp][j][1] for c, cp, j in zip(B.cid, B.cp, B.j)]; B['Lrat_min'] = [LS_[c][cp][j][2] for c, cp, j in zip(B.cid, B.cp, B.j)]; B['Lrat_max'] = [LS_[c][cp][j][3] for c, cp, j in zip(B.cid, B.cp, B.j)]; B['Lotm_mean'] = [LS_[c][cp][j][4] for c, cp, j in zip(B.cid, B.cp, B.j)]
B['Ln_oth'] = [LS_[c]['PE' if cp == 'CE' else 'CE'][j][0] for c, cp, j in zip(B.cid, B.cp, B.j)]; B['since_long_buy'] = np.nan; B = B.sort_values(['cid', 'cp', 'j']).reset_index(drop=True)
lb = B.assign(t_=np.where(B.long_buy_lots > 0, B.j, np.nan)); B['since_long_buy'] = (B.j - lb.groupby(['cid', 'cp']).t_.transform(lambda s: s.ffill().shift(1))).values
ls_ = B.assign(t_=np.where(B.long_sell_lots > 0, B.j, np.nan)); B['since_long_sell'] = (B.j - ls_.groupby(['cid', 'cp']).t_.transform(lambda s: s.ffill().shift(1))).values
# ---------- L3 / L4 cell AUC
FAM = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j', 'gap_fav', 'carried_own', 'carried_other'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other', 'phx_prem_low_15', 'phx_prem_low_30', 'phx_prem_low_60', 'phx_prem_low_day'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'])
E_ = sum(FAM.values(), []); BKL = ['S_own', 'L_own', 'S_oth', 'L_oth', 'gap_own', 'gap_oth', 'atm_prem_prev', 'otm_steps_at_1', 'otm_steps_at_2', 'otm_steps_at_3']; LST = ['Ln_own', 'Lrat_mean', 'Lrat_min', 'Lrat_max', 'Lotm_mean', 'Ln_oth', 'since_long_buy', 'since_long_sell']
SETS = {'E existing families': E_, 'E + book of shorts and longs': E_ + BKL, 'E + book + state of held longs': E_ + BKL + LST, 'base + held-long state only': FAM['base'] + LST}
OUTC = {'y_long_buy': 'long buy', 'y_long_sell': 'long sell (intraday)'}; cids = np.sort(B.cid.unique()); CID = B.cid.values
mk = lambda: HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def auc(y, p):
    r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
def task(a):
    out, sname, kind, c = a; X = B[SETS[sname]].values.astype(float); y = B[out].values; te = np.isin(CID, c if isinstance(c, list) else [c]); tr = ~te
    if kind == 'placebo':
        rng = np.random.default_rng(int(c) + 1); y = y.copy()
        for cc in cids: m = np.where(CID == cc)[0]; y[m] = rng.permutation(y[m])
    m = mk(); m.fit(X[tr], y[tr]); return (out, sname, kind, c), np.where(te)[0], m.predict_proba(X[te])[:, 1]
if __name__ == '__main__':
    t0 = time.time(); ver = B.groupby('cid').version.first(); exp_ = B.groupby('cid').expiry.first(); fw_te = []
    for v in ver.unique(): cv = sorted([c for c in cids if ver[c] == v], key=lambda c: exp_[c]); fw_te += cv[int(np.ceil(len(cv) * 2 / 3)):]
    jobs = [(o, s, 'loco', int(c)) for o in OUTC for s in SETS for c in cids] + [(o, s, 'forward', fw_te) for o in OUTC for s in SETS] + [(o, 'E + book + state of held longs', 'placebo', int(c)) for o in OUTC for c in cids]
    with Pool(4) as pool: res = list(pool.imap_unordered(task, jobs, chunksize=4))
    P = {}
    for (o, s, k, c), idx, p in res: P.setdefault((o, s, k), np.full(len(B), np.nan))[idx] = p
    rows = []; rng = np.random.default_rng(3); idxc = {c: np.where(CID == c)[0] for c in cids}
    for o in OUTC:
        y = B[o].values
        for s in SETS:
            p = P[(o, s, 'loco')]; a = auc(y, p); bs = []
            for _ in range(300):
                ii = np.concatenate([idxc[c] for c in rng.choice(cids, len(cids))]); yy = y[ii]
                if 0 < yy.sum() < len(yy): bs.append(auc(yy, p[ii]))
            wc = [auc(y[idxc[c]], p[idxc[c]]) for c in cids if 0 < y[idxc[c]].sum() < len(idxc[c])]; tm = np.isin(CID, fw_te); pf = P[(o, s, 'forward')]; af = auc(y[tm], pf[tm]) if 0 < y[tm].sum() < tm.sum() else np.nan
            pp = P.get((o, s, 'placebo')); rows.append(dict(outcome=OUTC[o], set=s, auc_loco=a, lo=float(np.quantile(bs, .025)), hi=float(np.quantile(bs, .975)), within_cycle=float(np.mean(wc)), forward_auc=af, placebo_auc=auc(y, pp) if pp is not None else np.nan, cells=len(y), positives=int(y.sum())))
    AU = pd.DataFrame(rows); AU.round(4).to_csv(f'{OUT}/bl_d0w_long_auc.csv', index=False); G = []
    for o, nm in OUTC.items():
        z = AU[AU.outcome == nm].set_index('set'); best = z.auc_loco.drop('base + held-long state only').idxmax(); a = z.loc[best]; ok = a.auc_loco >= 0.85 and a.lo > 0.82 and a.forward_auc >= 0.80 and (np.isnan(a.placebo_auc) or a.placebo_auc < 0.65)
        G.append(dict(outcome=nm, best_set=best, auc=a.auc_loco, lo=a.lo, forward=a.forward_auc, placebo=a.placebo_auc, within_cycle=a.within_cycle, E_auc=z.loc['E existing families'].auc_loco, gain_over_E=a.auc_loco - z.loc['E existing families'].auc_loco, gate='met' if ok else 'not met'))
    pd.DataFrame(G).round(4).to_csv(f'{OUT}/bl_d0w_long_gate.csv', index=False)
    # ---------- L5 clearance: which longs are sold at 15:14 (non-stop cycles), by contract
    stop_c = set(O[(O.dayno == 1) & (O.module == 's_')].cid); cr = []
    for c in cids:
        if c in stop_c: continue
        z = O[(O.cid == c) & O.role.isin(['open_long', 'close_long'])]; op = op_[c]; ki = {int(k): x for x, k in enumerate(op['K'])}
        for cp in ('CE', 'PE'):
            zz = z[z.cp == cp]; held = {}; end = {}
            for q in zz.sort_values(['dayno', 'tt_first']).itertuples():
                s_ = 1 if q.role == 'open_long' else -1
                if q.dayno == 1 and q.tod >= 54840: end[int(q.strike)] = end.get(int(q.strike), 0) + s_ * q.lots; continue
                held[int(q.strike)] = held.get(int(q.strike), 0) + s_ * q.lots
            for k, n in held.items():
                if n > 0 and k in ki: sold = min(n, -end.get(k, 0)) if end.get(k, 0) < 0 else 0; cr.append(dict(cid=c, cp=cp, strike=k, lots=n, sold=sold, price=float(op[(cp, 'close')][ki[k], 358]), und=CY.und[c]))
    CR = pd.DataFrame(cr); CR['frac_sold'] = CR.sold / CR.lots; CR.to_csv(f'{OUT}/bl_d0w_long_clear.csv', index=False)
    tot = CR.lots.sum(); R['l5_longs_open_at_1514_lots'] = int(tot); R['l5_share_sold_after_1514'] = float(CR.sold.sum() / tot)
    grid = np.array([0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5]); acc = []
    for c in CR.cid.unique():
        tr = CR[CR.cid != c]; te = CR[CR.cid == c]; best = max(grid, key=lambda g: ((tr.price >= g) == (tr.frac_sold > 0.5)).mul(tr.lots).sum()); acc.append(((te.price >= best) == (te.frac_sold > 0.5)).mul(te.lots).sum())
    R['l5_rule_price_threshold_lots_correct_loco'] = float(np.sum(acc) / tot); R['l5_sell_all_lots_correct'] = float(CR.sold.sum() / tot)
    R['l5_kept_price_median'] = float(CR[CR.frac_sold < 0.5].price.median()); R['l5_sold_price_median'] = float(CR[CR.frac_sold >= 0.5].price.median())
    rec('d0w3', R); print('done', round(time.time() - t0)); pd.set_option('display.width', 250); print(L1.round(3).to_string()); print(L2.round(3).to_string()); print(pd.DataFrame(G).round(3).to_string()); print(AU.round(3).to_string()); print(json.dumps(R, indent=1))
