"""D0 quantity, Part B: lots per event given the event (plan reports/D0_QTY_PLAN.md).
B2 fixed-size classes (scheduled pair 1+1, hedge wave = gap S-L, lump wave <= long excess), B3 leave-one-cycle-out size models for solo sells and buy-back events against three baselines,
B4 size against the book, B5 premium / notional scaling.
Outputs bl_d0u_b2_fixed.csv, bl_d0u_b3_models.csv, bl_d0u_b3_cells.pkl.gz, bl_d0u_b4_ratios.csv, bl_d0u_b5_scaling.csv, bl_summary_d0u_b.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor as HGBR
R = {}; CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); D = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz')
PN = pd.read_pickle(f'{OUT}/bl_d0f_panel.pkl.gz').reset_index(drop=True); T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz')
# ---------- B2a scheduled pair = 1 CE + 1 PE
sp = T[T.type == 'scheduled pair'].copy(); sp['k'] = sp.cid.astype(str) + '_' + sp.strike.astype(str) + '_' + (sp.tod // 6).astype(int).astype(str)
g = sp.groupby('k').agg(ce=('lots', lambda s: s[sp.loc[s.index, 'cp'] == 'CE'].sum()), pe=('lots', lambda s: s[sp.loc[s.index, 'cp'] == 'PE'].sum()))
fx = [dict(test='scheduled pair is exactly 1 CE + 1 PE lot', n=len(g), share_fit=float(((g.ce == 1) & (g.pe == 1)).mean()), share_equal_sides=float((g.ce == g.pe).mean()), median_lots_each_side=float(g.ce.median()))]
R['b2_sched_pair_lots_dist'] = {f'{int(a)}+{int(b)}': int(v) for (a, b), v in g.groupby(['ce', 'pe']).size().sort_values(ascending=False).head(6).items()}
# ---------- B2b hedge wave = gap S - L on its right (state before the event, per right)
D = D.sort_values(['und', 'expiry', 'cp', 'tt_first', 'row']).reset_index(drop=True)
grp = D.groupby(['und', 'expiry', 'cp']); D['S_before'] = grp.S_after.shift(1); D['L_before'] = grp.L_after.shift(1)
chk = D[(D.klass == 'body sell')].dropna(subset=['S_before']); R['b2_state_check_S_diff_equals_lots_body_sell'] = float(((chk.S_after - chk.S_before) == chk.lots).mean())
chkb = D[(D.klass == 'wing buy')].dropna(subset=['L_before']); R['b2_state_check_L_diff_equals_lots_wing_buy'] = float(((chkb.L_after - chkb.L_before) == chkb.lots).mean())
D['gap_before'] = D.S_before - D.L_before
ev = D[D.klass == 'wing buy'].dropna(subset=['gap_before']).groupby('eid').agg(lots=('lots', 'sum'), gap=('gap_before', 'first'), und=('und', 'first'), n=('lots', 'size')).reset_index()
for u, z in [('all', ev)] + [(u, z) for u, z in ev.groupby('und')]:
    fx.append(dict(test=f'wing-buy event lots == S-L gap before the event ({u})', n=len(z), share_fit=float((z.lots == z.gap).mean()), share_equal_sides=np.nan, median_lots_each_side=float(z.lots.median())))
    fx.append(dict(test=f'wing-buy event lots <= S-L gap before ({u})', n=len(z), share_fit=float((z.lots <= z.gap).mean()), share_equal_sides=np.nan, median_lots_each_side=np.nan))
# the gap measured after the whole second (orders of the same second incl. the body order are already in the state, which is what the controller sees)
ev2 = D[D.klass == 'wing sell'].dropna(subset=['L_before']).groupby('eid').agg(lots=('lots', 'sum'), exc=('L_before', 'first'), S=('S_before', 'first'), und=('und', 'first')).reset_index(); ev2['exc'] = ev2.exc - ev2.S
fx.append(dict(test='wing-sell event lots <= long excess L-S before', n=len(ev2), share_fit=float((ev2.lots <= ev2.exc).mean()), share_equal_sides=np.nan, median_lots_each_side=float(ev2.lots.median())))
fx.append(dict(test='wing-sell event lots == long excess L-S before', n=len(ev2), share_fit=float((ev2.lots == ev2.exc).mean()), share_equal_sides=np.nan, median_lots_each_side=np.nan))
lu = D[D.klass == 'lump salvage'].dropna(subset=['L_before']); lu = lu.assign(exc=lu.L_before - lu.S_before)
fx.append(dict(test='lump-salvage order lots <= long excess L-S before', n=len(lu), share_fit=float((lu.lots <= lu.exc).mean()), share_equal_sides=np.nan, median_lots_each_side=float(lu.lots.median())))
pd.DataFrame(fx).round(4).to_csv(f'{OUT}/bl_d0u_b2_fixed.csv', index=False)
# ---------- B3 size models
FAM = dict(base=['hour', 'min_in_15', 'min_in_5', 'is_ce', 'und_nifty', 'v2', 'j', 'gap_fav', 'carried_own', 'carried_other'],
    spot=['fav_ret_1', 'fav_ret_3', 'fav_ret_5', 'fav_ret_15', 'fav_ret_30', 'fav_ret_60', 'fresh_15', 'fresh_30', 'fresh_60', 'fresh_120', 'fresh_day', 'dist_day_ext', 'from_open', 'vol15', 'bars_since_fresh60'],
    prem=['atm_px', 'prem_chg_1', 'prem_chg_3', 'prem_chg_5', 'prem_chg_15', 'prem_vs_daymax', 'prem_vs_daymin', 'prem_vs_open', 'mark_own', 'mark_other'],
    book=['n_own', 'n_other', 'share_own', 'expo_own', 'expo_other', 'expo_share_own', 'mtm_lakh', 'mtm_to_stop', 'sell_own_1', 'sell_own_5', 'sell_own_15', 'sell_other_1', 'sell_other_5', 'sell_other_15', 'since_sale_own'],
    bb=['bb_other_1', 'bb_other_5', 'bb_other_15', 'bb_own_1', 'bb_own_5', 'bb_own_15', 'sl_other_1', 'sl_other_5', 'sl_other_15', 'sl_own_1', 'sl_own_5', 'sl_own_15', 'since_bb_other'])
CAUS = sum(FAM.values(), []); SAME = ['bb_own_same_min', 'bb_other_same_min', 'sl_other_same_min']
mk = lambda: HGBR(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=50, l2_regularization=1.0, random_state=0)
def spearman(a, b):
    return float(stats.spearmanr(a, b).correlation) if len(a) > 3 and np.std(a) > 0 and np.std(b) > 0 else np.nan
def loco_size(df, feats, target='lots', min_leaf=None):
    """leave-one-cycle-out regression on log1p(lots); returns predictions (rounded >= 1) and the baselines"""
    y = df[target].values.astype(float); cid = df.cid.values; X = df[feats].values.astype(float); pred = np.full(len(df), np.nan)
    for c in np.unique(cid):
        tr = cid != c; te = ~tr
        if tr.sum() < 50 or te.sum() == 0: continue
        m = mk(); m.fit(X[tr], np.log1p(y[tr])); pred[te] = np.expm1(m.predict(X[te]))
    return np.maximum(1, np.round(pred))
def metrics(y, p):
    return dict(exact=float((p == y).mean()), within1=float((np.abs(p - y) <= 1).mean()), mae=float(np.abs(p - y).mean()), rho=spearman(p, y))
def boot_ci(df, y, p, b, nb=400, seed=1):
    """cycle bootstrap of MAE(model) - MAE(baseline) (negative = model better) and of its relative improvement"""
    rng = np.random.default_rng(seed); cyc = df.cid.values; u = np.unique(cyc); idx = {c: np.where(cyc == c)[0] for c in u}; out = []
    for _ in range(nb):
        ii = np.concatenate([idx[c] for c in rng.choice(u, len(u))]); out.append((np.abs(p[ii] - y[ii]).mean() - np.abs(b[ii] - y[ii]).mean()) / np.abs(b[ii] - y[ii]).mean())
    return float(np.quantile(out, .025)), float(np.quantile(out, .975))
def prev_event(df, target):
    """size of the previous event of the same cycle and right (training-free baseline); first event of a cycle uses the global median of other cycles"""
    d = df.sort_values(['cid', 'cp', 'j']); prv = d.groupby(['cid', 'cp'])[target].shift(1); return prv.reindex(df.index)
rows = []; CELLS = {}
def run_task(name, df, feats_sets, target='lots'):
    df = df.reset_index(drop=True); y = df[target].values.astype(float); cid = df.cid.values
    # baselines
    med = np.array([np.median(y[cid != c]) for c in cid]); prv = prev_event(df, target).values; prv = np.where(np.isnan(prv), med, prv)
    base = {'class median (other cycles)': med, 'previous event of the same cycle and right': np.maximum(1, np.round(prv)), 'always 1 lot': np.ones(len(df))}
    best = min(base, key=lambda k: np.abs(base[k] - y).mean())
    rng = np.random.default_rng(5); perm = df.copy(); perm['cid_perm'] = perm.cid
    res = {}
    for bn, bp in base.items(): res[bn] = metrics(y, bp); rows.append(dict(task=name, model=f'baseline: {bn}', n=len(df), **res[bn], rel_mae_vs_best_baseline=np.nan, ci_lo=np.nan, ci_hi=np.nan))
    for fn, feats in feats_sets.items():
        p = loco_size(df, feats, target); m = metrics(y, p); lo, hi = boot_ci(df, y, p, base[best]); rel = (np.abs(p - y).mean() - np.abs(base[best] - y).mean()) / np.abs(base[best] - y).mean()
        rows.append(dict(task=name, model=f'LOCO boosting: {fn}', n=len(df), **m, rel_mae_vs_best_baseline=float(rel), ci_lo=lo, ci_hi=hi)); res[fn] = (m, rel); CELLS[(name, fn)] = pd.DataFrame(dict(cid=df.cid, j=df.j, cp=df.cp, y=y, pred=p))
        # placebo: shuffle the target across cells inside the training pool (features unchanged) to check that a gain is not an artefact of the pipeline
    pp = df.copy(); pp[target] = rng.permutation(pp[target].values); fs = list(feats_sets)[-1]; pplace = loco_size(pp, feats_sets[fs], target); mp = metrics(y, pplace)
    rows.append(dict(task=name, model='placebo (training targets shuffled), ' + fs, n=len(df), **mp, rel_mae_vs_best_baseline=float((np.abs(pplace - y).mean() - np.abs(base[best] - y).mean()) / np.abs(base[best] - y).mean()), ci_lo=np.nan, ci_hi=np.nan))
    return best
# ---- solo sells: lots per minute-cell given a solo sale (y=1)
S = PN[PN.y_lots > 0].copy(); S['lots'] = S.y_lots.astype(float); S = S.replace([np.inf, -np.inf], np.nan)
fs_solo = {'causal (before the minute)': CAUS, 'causal + same-minute buy-backs': CAUS + SAME, 'ladder depth only (gap_fav)': ['gap_fav']}
b_solo = run_task('solo sells: lots per cell given a sale', S, fs_solo)
R['b3_solo_cells'] = len(S); R['b3_solo_lots_med'] = float(S.lots.median()); R['b3_solo_share_1_lot'] = float((S.lots == 1).mean()); R['b3_solo_rho_gapfav'] = spearman(S.gap_fav, S.lots); R['b3_solo_best_baseline'] = b_solo
# ---- buy-back events: lots bought back per (cycle, minute, right) in scope (before 15:10, before the cycle stop, not clearance)
X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); X = X[~X.type.astype(str).str.startswith(('1', '2'))]
Pn = pd.read_pickle(f'{OUT}/bl_d0b_panel.pkl.gz')[['cid', 'lid', 'j', 'cp', 'origin', 'entry', 'rh', 'px']]
Pn = Pn.sort_values(['lid', 'j']); Pn['rh_prev'] = Pn.groupby('lid').rh.shift(1)
agg = Pn.groupby(['cid', 'j', 'cp']).agg(n_open=('lid', 'size'), n_cross14=('rh', lambda s: int((s >= 1.4).sum())), n_cross12=('rh', lambda s: int((s >= 1.2).sum())), max_rh=('rh', 'max'), mean_rh=('rh', 'mean'),
                                         n_cross14_prev=('rh_prev', lambda s: int((s >= 1.4).sum())), max_rh_prev=('rh_prev', 'max'), carried_share=('origin', lambda s: float((s == 'D-1').mean())),
                                         prem_open=('px', 'sum')).reset_index()
bb = X.groupby(['cid', 'j', 'cp']).agg(lots=('lid', 'size'), n_strikes=('strike', 'nunique'), stop_lots=('type', lambda s: int(s.astype(str).str.startswith('3').sum()))).reset_index()
B = bb.merge(agg, on=['cid', 'j', 'cp'], how='left').merge(PN[['cid', 'cp'] + CAUS + SAME].drop_duplicates(['cid', 'j', 'cp']), on=['cid', 'j', 'cp'], how='left')
B = B.dropna(subset=['n_open']); B['frac_open'] = B.lots / B.n_open; B['lots'] = B.lots.astype(float); B = B.replace([np.inf, -np.inf], np.nan)
LOT = ['n_open', 'n_cross14', 'n_cross12', 'max_rh', 'mean_rh', 'n_cross14_prev', 'max_rh_prev', 'carried_share', 'prem_open']
fs_bb = {'causal book/market (before the minute)': CAUS + ['n_open', 'n_cross14_prev', 'max_rh_prev', 'carried_share'], 'plus bar of the minute (crossing counts)': CAUS + LOT, 'only crossing count n_cross14': ['n_cross14']}
b_bb = run_task('buy-back events: lots per cell given a buy-back', B, fs_bb)
for nm, f in (('lots == n_cross14', (B.lots == B.n_cross14)), ('lots <= n_cross14', (B.lots <= B.n_cross14)), ('lots == round(10% of open)', (B.lots == np.maximum(1, np.round(0.1 * B.n_open))))): R['b3_bb_' + nm.replace(' ', '_').replace('%', 'pct').replace('(', '').replace(')', '')] = float(f.mean())
R['b3_bb_cells'] = len(B); R['b3_bb_lots_med'] = float(B.lots.median()); R['b3_bb_share_1_lot'] = float((B.lots == 1).mean()); R['b3_bb_frac_open_med'] = float(B.frac_open.median()); R['b3_bb_frac_open_iqr'] = [float(B.frac_open.quantile(.25)), float(B.frac_open.quantile(.75))]
R['b3_bb_rho_n_cross14'] = spearman(B.n_cross14, B.lots); R['b3_bb_rho_n_open'] = spearman(B.n_open, B.lots); R['b3_bb_best_baseline'] = b_bb
M = pd.DataFrame(rows); M.round(4).to_csv(f'{OUT}/bl_d0u_b3_models.csv', index=False); pd.to_pickle(CELLS, f'{OUT}/bl_d0u_b3_cells.pkl.gz')
# ---------- B4 size against the book / other-right buy-back
cs = PN[(PN.y_lots > 0) & (PN.bb_other_same_min > 0)]; r4 = [dict(what='counter-sell lots / other-right buy-back lots (same minute)', n=len(cs), median=float((cs.y_lots / cs.bb_other_same_min).median()), q25=float((cs.y_lots / cs.bb_other_same_min).quantile(.25)), q75=float((cs.y_lots / cs.bb_other_same_min).quantile(.75)),
                                                                                       share_ratio_1=float((cs.y_lots == cs.bb_other_same_min).mean()), rho=spearman(cs.y_lots, cs.bb_other_same_min))]
r4.append(dict(what='solo-sell lots / own-right short lots open', n=len(S), median=float((S.lots / S.n_own.clip(lower=1)).median()), q25=float((S.lots / S.n_own.clip(lower=1)).quantile(.25)), q75=float((S.lots / S.n_own.clip(lower=1)).quantile(.75)), share_ratio_1=np.nan, rho=spearman(S.lots, S.n_own)))
r4.append(dict(what='buy-back lots / right lots open', n=len(B), median=float(B.frac_open.median()), q25=float(B.frac_open.quantile(.25)), q75=float(B.frac_open.quantile(.75)), share_ratio_1=float((B.lots == B.n_open).mean()), rho=spearman(B.lots, B.n_open)))
pd.DataFrame(r4).round(4).to_csv(f'{OUT}/bl_d0u_b4_ratios.csv', index=False)
# ---------- B5 premium / notional scaling inside classes
SP_ = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); SP_['notional'] = SP_.px * SP_.lots; r5 = []
for t, z in SP_.groupby('type'):
    ev_ = z.assign(mn=(z.tod // 60)).groupby(['cid', 'mn', 'cp']).agg(lots=('lots', 'sum'), px=('px', 'mean')).reset_index()
    r5.append(dict(what=f'solo type: {t}', n_events=len(ev_), rho_lots_vs_price=spearman(ev_.lots, ev_.px), med_lots=float(ev_.lots.median()), premium_value_cv=float((ev_.lots * ev_.px).std() / (ev_.lots * ev_.px).mean())))
r5.append(dict(what='buy-back cells', n_events=len(B), rho_lots_vs_price=spearman(B.lots, B.prem_open / B.n_open), med_lots=float(B.lots.median()), premium_value_cv=np.nan))
pd.DataFrame(r5).round(4).to_csv(f'{OUT}/bl_d0u_b5_scaling.csv', index=False)
rec('d0u_b', R); print(json.dumps(R, default=str, indent=1)); pd.set_option('display.width', 250); print(pd.DataFrame(fx).round(3).to_string()); print(M.round(3).to_string()); print(pd.DataFrame(r4).round(3).to_string()); print(pd.DataFrame(r5).round(3).to_string())
