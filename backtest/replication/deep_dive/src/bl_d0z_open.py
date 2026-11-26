"""D0 opening burst (plan reports/D0_OPEN_ROLL_PLAN.md, Part O). Minute 0 = 09:15:00-09:15:59.
O1 which carried lots are bought back at the first print (lot level), O2 how many, O3 opening sells (composition, count), O4 opening long buys (count), O5 sequence in seconds, O6 gap days.
Outputs bl_d0z_open_lots.csv, bl_d0z_open_rule.csv, bl_d0z_open_count.csv, bl_d0z_open_sells.csv, bl_d0z_open_longs.csv, bl_d0z_open_seq.csv, bl_d0z_open_gap.csv, bl_summary_d0z2.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
R = {}; CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); TL = pd.read_pickle(f'{OUT}/bl_d0u_timeline.pkl.gz')
D = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz'); key = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; D['cid'] = [key.get((a, b), -1) for a, b in zip(D.und, D.expiry)]; T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz')
STEP = {i: ref.STEP[CY.und[i]] for i in range(len(CY))}; stop_open = set(D[(D.module == 's_') & (D.jm <= 0)].cid); stop_any = set(D[D.module == 's_'].cid)
def auc(y, p):
    ok = np.isfinite(p); y = y[ok]; p = p[ok]; r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
# ---------- O1 lot level
rows = []
for c, b in BK.items():
    r = CY.iloc[c]; op = OPT.get((r.und, r.expiry)); sp = SPT.get((r.und, r.expiry))
    if op is None: continue
    ki = {int(k): i for i, k in enumerate(op['K'])}; rem = set(X[(X.cid == c) & (X.j == 0)].lid.values); so = sp.open.iloc[0]
    for L in b['at_open']:
        i = ki.get(int(L['strike']))
        if i is None: continue
        cp = L['cp']; e = L['entry']; o, h, l, cl = (op[(cp, f)][i, 0] for f in ('open', 'high', 'low', 'close')); itm = ((so - L['strike']) / STEP[c]) if cp == 'CE' else ((L['strike'] - so) / STEP[c])
        rows.append(dict(cid=c, und=r.und, version=r.version, lid=L['lid'], cp=cp, strike=L['strike'], entry=e, typ=L['typ'], ro=o / e, rh=h / e, rl=l / e, rc=cl / e, itm=itm, loss=(o - e), taken=int(L['lid'] in rem), stop_open=c in stop_open))
LT = pd.DataFrame(rows); LT['typ_code'] = LT.typ.astype('category').cat.codes; LT['entry_x_ro'] = LT.entry * LT.ro
R['carried_lots'] = len(LT); R['taken_j0'] = int(LT.taken.sum()); R['cycles_stop_open'] = len(stop_open); R['taken_in_stop_open_cycles'] = int(LT[LT.stop_open].taken.sum())
L = LT[~LT.stop_open].copy(); R['lots_no_stop_open'] = len(L); R['taken_no_stop_open'] = int(L.taken.sum()); R['cycles'] = int(L.cid.nunique())
feats = {'price / entry at the first print (open)': 'ro', 'price / entry, minute-0 high': 'rh', 'price / entry, minute-0 low': 'rl', 'price / entry, minute-0 close': 'rc', 'ITM depth at the open (steps)': 'itm', 'entry price': 'entry', 'entry class (code)': 'typ_code', 'strike': 'strike'}
out = []
for nm, col in feats.items():
    wc = [auc(z.taken.values, z[col].values.astype(float)) for _, z in L.groupby(['cid', 'cp']) if 0 < z.taken.sum() < len(z)]; out.append(dict(feature=nm, pooled_auc=auc(L.taken.values, L[col].values.astype(float)), within_cycle_right_auc=float(np.mean(wc)), cells=len(wc)))
cols = ['ro', 'rh', 'rl', 'rc', 'itm', 'entry', 'typ_code', 'strike']; Xm = L[cols].values.astype(float); y = L.taken.values; cid = L.cid.values; p = np.full(len(L), np.nan)
for c in np.unique(cid):
    tr = cid != c; m = HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=30, l2_regularization=1.0, random_state=0); m.fit(Xm[tr], y[tr]); p[~tr] = m.predict_proba(Xm[~tr])[:, 1]
L['p'] = p; wc = [auc(z.taken.values, z.p.values) for _, z in L.groupby(['cid', 'cp']) if 0 < z.taken.sum() < len(z)]; out.append(dict(feature='ALL lot features (LOCO boosting)', pooled_auc=auc(y, p), within_cycle_right_auc=float(np.mean(wc)), cells=len(wc)))
# bootstrap CI of the pooled AUC (cycles)
rng = np.random.default_rng(3); cu = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in cu}; bs = []
for _ in range(300):
    ii = np.concatenate([idx[c] for c in rng.choice(cu, len(cu))]); yy = y[ii]
    if 0 < yy.sum() < len(yy): bs.append(auc(yy, p[ii]))
R['loco_auc_ci'] = [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]
# forward: first two thirds of each version train
ex = L.groupby('cid').agg(version=('version', 'first')); ex['exp'] = [CY.expiry[c] for c in ex.index]; fw_te = []
for v in ex.version.unique(): cv = sorted(ex[ex.version == v].index, key=lambda c: ex.exp[c]); fw_te += cv[int(np.ceil(len(cv) * 2 / 3)):]
tm = L.cid.isin(fw_te).values; m = HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=30, l2_regularization=1.0, random_state=0); m.fit(Xm[~tm], y[~tm]); R['forward_auc'] = float(auc(y[tm], m.predict_proba(Xm[tm])[:, 1])); R['forward_taken'] = int(y[tm].sum())
pl = y.copy(); rngp = np.random.default_rng(1)
for (c, cp), z in L.groupby(['cid', 'cp']): ii = z.index.values; pl[L.index.get_indexer(ii)] = rngp.permutation(y[L.index.get_indexer(ii)])
pp = np.full(len(L), np.nan)
for c in cu:
    tr = cid != c; m = HGB(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=30, l2_regularization=1.0, random_state=0); m.fit(Xm[tr], pl[tr]); pp[~tr] = m.predict_proba(Xm[~tr])[:, 1]
R['placebo_auc'] = float(auc(y, pp)); pd.DataFrame(out).round(4).to_csv(f'{OUT}/bl_d0z_open_lots.csv', index=False)
# threshold rules (fitted on training cycles, held-out cycle scored) and precision@m
rr = []
for nm, col, grid in (('take every lot with minute-0 high / entry >= theta', 'rh', np.arange(1.0, 2.01, 0.05)), ('take every lot with open / entry >= theta', 'ro', np.arange(1.0, 2.01, 0.05))):
    tp = fp = fn = 0; picks = []
    for c in cu:
        tr = L[L.cid != c]; te = L[L.cid == c]
        f1 = lambda th: (lambda pr, t: 2 * (pr & t).sum() / max(2 * (pr & t).sum() + (pr & ~t).sum() + (~pr & t).sum(), 1))((tr[col] >= th).values, tr.taken.values == 1); g = max(grid, key=f1); picks.append(float(g)); pr = (te[col] >= g).values; t = te.taken.values == 1; tp += (pr & t).sum(); fp += (pr & ~t).sum(); fn += (~pr & t).sum()
    rr.append(dict(rule=nm, f1=2 * tp / max(2 * tp + fp + fn, 1), precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), theta_median=float(np.median(picks)), theta_q25=float(np.quantile(picks, .25)), theta_q75=float(np.quantile(picks, .75))))
pm = {}
for col in ('rh', 'ro', 'loss'):
    v = []
    for _, z in L.groupby(['cid', 'cp']):
        k = int(z.taken.sum())
        if k > 0: v.append(z.sort_values(col, ascending=False).head(k).taken.mean())
    pm[col] = float(np.mean(v))
R['precision_at_m'] = pm; R['chance_precision_at_m'] = float(np.mean([z.taken.mean() for _, z in L.groupby(['cid', 'cp']) if z.taken.sum() > 0]))
rr.append(dict(rule='placebo: random set of the true size per cycle and right', f1=np.nan, precision=R['chance_precision_at_m'], recall=np.nan, theta_median=np.nan, theta_q25=np.nan, theta_q75=np.nan)); pd.DataFrame(rr).round(4).to_csv(f'{OUT}/bl_d0z_open_rule.csv', index=False)
# ---------- O2 count per (cycle, right)
ct = []
for (c, cp), z in L.groupby(['cid', 'cp']): ct.append(dict(cid=c, cp=cp, und=z.und.iloc[0], k=int(z.taken.sum()), n=len(z), n_ge12=int((z.rh >= 1.2).sum()), n_ge14=int((z.rh >= 1.4).sum()), n_ge16=int((z.rh >= 1.6).sum()), n_ro14=int((z.ro >= 1.4).sum())))
CT = pd.DataFrame(ct); res = []
def ratio_fit(df, ycol, xcol, per_und=False):
    pred = np.zeros(len(df))
    for c in df.cid.unique():
        tr = df[df.cid != c]; msk = (df.cid == c).values; xs = tr[xcol].replace(0, np.nan); m = float(np.nanmedian(tr[ycol] / xs)) if xs.notna().any() else 0.0; pred[msk] = np.round(m * df[msk][xcol].values)
    return pred
for xcol in ('n_ge12', 'n_ge14', 'n_ge16', 'n_ro14', 'n'):
    pr = ratio_fit(CT, 'k', xcol); yv = CT.k.values; res.append(dict(candidate=f'median fraction x {xcol}', n=len(CT), exact=float((pr == yv).mean()), within1=float((np.abs(pr - yv) <= 1).mean()), mae=float(np.abs(pr - yv).mean()), rho=float(stats.spearmanr(CT[xcol], yv).correlation)))
bs_ = np.zeros(len(CT))
for c in CT.cid.unique(): bs_[(CT.cid == c).values] = np.round(np.median(CT[CT.cid != c].k))
res.append(dict(candidate='baseline: median of the other cycles', n=len(CT), exact=float((bs_ == CT.k.values).mean()), within1=float((np.abs(bs_ - CT.k.values) <= 1).mean()), mae=float(np.abs(bs_ - CT.k.values).mean()), rho=np.nan)); pd.DataFrame(res).round(4).to_csv(f'{OUT}/bl_d0z_open_count.csv', index=False); R['count_cells'] = len(CT); R['k_median'] = float(CT.k.median())
# ---------- O3 opening sells and O4 opening longs per (cycle, right), cycles without a stop at all
rows = []
for c in sorted(set(D.cid[D.cid >= 0])):
    if c in stop_any: continue
    sp = SPT.get((CY.und[c], CY.expiry[c]))
    if sp is None: continue
    st = STEP[c]; ret = (sp.close.iloc[0] - sp.open.iloc[0]) / st; rg = (sp.high.iloc[0] - sp.low.iloc[0]) / st
    for cp in ('CE', 'PE'):
        z = D[(D.cid == c) & (D.cp == cp) & (D.jm.between(0, 2))]; t = TL.get((c, cp)); o = TL.get((c, 'PE' if cp == 'CE' else 'CE'))
        if t is None: continue
        s = z[z.klass == 'body sell']; tt = T[(T.cid == c) & (T.cp == cp) & (T.j <= 2)]
        rows.append(dict(cid=c, und=CY.und[c], cp=cp, sells=int(s.lots.sum()), sells_j1=int(s[s.jm == 1].lots.sum()), sched=int(tt[tt.type == 'scheduled pair'].lots.sum()), opair=int(tt[tt.type == 'opening pair'].lots.sum()), osolo=int(tt[tt.type == 'opening solo'].lots.sum()), bb=int(z[z.klass == 'body buy-back'].lots.sum()), lbuy=int(z[z.klass == 'body long buy'].lots.sum()), S0=t['S0'], L0=t['L0'], S3=t['S'][3], S0_oth=o['S0'] if o else np.nan, ret_adv=(ret if cp == 'CE' else -ret), range_steps=rg, abs_ret=abs(ret)))
O = pd.DataFrame(rows); O['rem'] = O.sells - O.sched; O['rem_nopair'] = O.sells - O.sched - O.opair
comp = O[['sells', 'sched', 'opair', 'osolo', 'bb', 'lbuy']].sum(); R['opening_sell_composition_lots'] = {k: int(v) for k, v in comp.items()}
def fit_table(df, ycol, cands):
    res = []
    for xcol in cands:
        pred = ratio_fit(df, ycol, xcol); yv = df[ycol].values; ok = df[xcol].notna().values; res.append(dict(target=ycol, candidate=f'median ratio x {xcol}', n=int(ok.sum()), exact=float((pred[ok] == yv[ok]).mean()), within2=float((np.abs(pred[ok] - yv[ok]) <= 2).mean()), mae=float(np.abs(pred[ok] - yv[ok]).mean()), rho=float(stats.spearmanr(df[xcol][ok], yv[ok]).correlation)))
    b = np.zeros(len(df))
    for c in df.cid.unique():
        for u in df.und.unique(): msk = ((df.cid == c) & (df.und == u)).values; b[msk] = np.round(np.median(df[(df.cid != c) & (df.und == u)][ycol])) if msk.any() else 0
    res.append(dict(target=ycol, candidate='baseline: median of the other cycles, same underlying', n=len(df), exact=float((b == df[ycol].values).mean()), within2=float((np.abs(b - df[ycol].values) <= 2).mean()), mae=float(np.abs(b - df[ycol].values).mean()), rho=np.nan)); return res
r3 = fit_table(O, 'sells', ['S0', 'L0', 'bb', 'sched', 'range_steps', 'abs_ret', 'S0_oth']) + fit_table(O, 'rem', ['S0', 'bb', 'range_steps', 'abs_ret']); pd.DataFrame(r3).round(4).to_csv(f'{OUT}/bl_d0z_open_sells.csv', index=False)
r4 = fit_table(O, 'lbuy', ['sells', 'sells_j1', 'sched', 'S3', 'S0', 'bb', 'range_steps']); pd.DataFrame(r4).round(4).to_csv(f'{OUT}/bl_d0z_open_longs.csv', index=False)
R['lbuy_range'] = [int(O.lbuy.min()), int(O.lbuy.max())]; R['lbuy_by_und_median'] = {u: float(z.lbuy.median()) for u, z in O.groupby('und')}; R['lbuy_over_sells_j1'] = float((O.lbuy / O.sells_j1.replace(0, np.nan)).median()); R['lbuy_cv'] = float(O.lbuy.std() / O.lbuy.mean())
# ---------- O5 sequence (seconds after 09:15:00), O6 gap days
seq = []; first = {}
for k, z in D[(D.tod < 33300 + 180)].groupby('klass'):
    sec = z.tod - 33300; seq.append(dict(klass=k, cycles=z.cid.nunique(), lots=int(z.lots.sum()), first_s_median=float(z.groupby('cid').tod.min().sub(33300).median()), all_orders_median_s=float(sec.median()), q25=float(sec.quantile(.25)), q75=float(sec.quantile(.75)), share_in_minute0=float((z.jm == 0).mean())))
SQ = pd.DataFrame(seq).sort_values('first_s_median'); SQ.round(1).to_csv(f'{OUT}/bl_d0z_open_seq.csv', index=False)
gap = []
for flag, nm in ((True, 'stop at the open (gap day)'), (False, 'no stop at the open')):
    cs = [c for c in sorted(set(D.cid[D.cid >= 0])) if (c in stop_open) == flag]; z = D[D.cid.isin(cs) & D.jm.between(0, 2)]; g = z.groupby(['cid', 'klass']).lots.sum().unstack(fill_value=0)
    gap.append(dict(group=nm, cycles=len(cs), **{k: float(g[k].median()) if k in g else 0 for k in ('body buy-back', 'body sell', 'body long buy', 'wing sell', 'wing buy', 'stop module', 'hedge other', 'lump salvage')}))
pd.DataFrame(gap).round(1).to_csv(f'{OUT}/bl_d0z_open_gap.csv', index=False)
L[['cid', 'cp', 'ro', 'rh', 'taken', 'p']].to_csv(f'{OUT}/bl_d0z_open_lotlevel.csv', index=False); O.to_csv(f'{OUT}/bl_d0z_open_cells.csv', index=False)
# post-hoc: bootstrap CI of the single-feature pooled AUC (price / entry at the first print and minute-0 high)
for col in ('ro', 'rh'):
    v = L[col].values.astype(float); bs = []
    for _ in range(300):
        ii = np.concatenate([idx[c] for c in rng.choice(cu, len(cu))]); yy = y[ii]
        if 0 < yy.sum() < len(yy): bs.append(auc(yy, v[ii]))
    R['single_auc_ci_' + col] = [float(auc(y, v)), float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]
rec('d0z2', R); pd.set_option('display.width', 250); print(json.dumps(R, indent=1)); print(pd.DataFrame(out).round(3).to_string()); print(pd.DataFrame(rr).round(3).to_string()); print(pd.DataFrame(res).round(3).to_string()); print(pd.DataFrame(r3).round(3).to_string()); print(pd.DataFrame(r4).round(3).to_string()); print(SQ.round(1).to_string()); print(pd.DataFrame(gap).to_string())
