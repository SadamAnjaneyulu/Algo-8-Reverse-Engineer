"""Capital-loss trigger study, part 9 (post-hoc, labelled): trailing-stop reading. Rebound = price(j-1) / lowest minute close since the oldest open lot's entry (strike-position trough) - 1; also rise from the trough in Rs per lot.
Compared with the short-horizon premium change (lot_pct3, lot_pct1) on D-1 sub-1.2x contract-minutes (target B residual, A all). Univariate AUC (cluster bootstrap), hazard by bin, LOCO gradient boosting incremental value. Outputs bl_book_trail_auc.csv, bl_book_trail_hazard.csv, bl_book_trail_gb.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
ch = Chain(); LOTS = ref.LOT; rng = np.random.default_rng(91)
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz', usecols=['und', 'expiry', 'day', 'j', 'B_total']); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); P = P[(P.day == 'D-1') & (P.r_low < 1.2)].reset_index(drop=True)
resid = ev[ev.klass == 'sub-1.2x residual'].groupby(['und', 'expiry', 'day', 'cp', 'strike', 'j']).size().rename('resid_n').reset_index(); P = P.merge(resid, on=['und', 'expiry', 'day', 'cp', 'strike', 'j'], how='left').merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); P = P[P.B_total.notna()].reset_index(drop=True)
cols = {k: np.full(len(P), np.nan) for k in ('rebound_pct', 'rebound_inr', 'lot_pct1', 'lot_pct3', 'lot_pct5', 'spot_adv1', 'spot_adv3')}
for (u, e, cp), idx in P.groupby(['und', 'expiry', 'cp']).groups.items():
    c = ch.cyc(u, e); si = c['_si']; px = pd.DataFrame(np.array(c[(0, cp, 'close')], dtype=float)).ffill(axis=1).values; spot = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().values; sgn = 1 if cp == 'CE' else -1; lot = LOTS[u]; Q = P.loc[idx]
    for pos, (i, r) in enumerate(Q.iterrows()):
        k = si.get(int(r.strike)); j = int(r.j)
        if k is None: continue
        a = px[k, max(j - 1, 0)]; lo = max(int(j - 1 - r.hold_min), 0) if r.hold_min == r.hold_min else max(j - 30, 0); tr = np.nanmin(px[k, lo:max(j, 1)]); cols['rebound_pct'][i] = (a / tr - 1) * 100 if tr > 0 else np.nan; cols['rebound_inr'][i] = (a - tr) * lot
        for w in (1, 3, 5): b = px[k, max(j - 1 - w, 0)]; cols[f'lot_pct{w}'][i] = (a / b - 1) * 100 if b > 0 else np.nan
        for w in (1, 3): cols[f'spot_adv{w}'][i] = sgn * (spot[max(j - 1, 0)] / spot[max(j - 1 - w, 0)] - 1) * 100
for k, v in cols.items(): P[k] = v
P['abs_itm'] = P.itm_steps.abs(); P['o_r'] = P.o_r_avg; P['tod_min'] = P.j; g = (P.und + P.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
FE0 = ['r_avg', 'r_low', 'r_fifo', 'abs_itm', 'itm_steps', 'hold_min', 'price', 'n_open', 'o_n_open', 'o_r', 'straddle_r', 'tod_min']; SH = ['lot_pct1', 'lot_pct3', 'lot_pct5', 'spot_adv1', 'spot_adv3']; TR = ['rebound_pct', 'rebound_inr']
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
ra = []; hz = []; gbr = []
for tn, y in (('B', (P.resid_n.fillna(0) > 0).astype(int).values), ('A', (P.bb_lots > 0).astype(int).values)):
    for f in TR + ['lot_pct1', 'lot_pct3']:
        x = P[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(80))]; ra.append((tn, f, a, *np.nanquantile(bs, [.025, .975])))
    t = P.groupby(pd.cut(P.rebound_pct, [-1, 0.5, 2, 4, 6, 8, 12, 20, 1000]), observed=False).apply(lambda d: pd.Series({'n': len(d), 'ev': int(y[d.index].sum())})); t['per1000'] = t.ev / t.n * 1000; t = t.reset_index().rename(columns={'rebound_pct': 'bin'}); t.insert(0, 'target', tn); hz.append(t)
    def fold(X, c):
        tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=50, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
    def loco(cs):
        X = P[cs].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
        for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
        return roc_auc_score(y, o)
    base = loco(FE0); r = {'baseline': base, '+ trough rebound': loco(FE0 + TR), '+ short-horizon changes': loco(FE0 + SH), '+ both': loco(FE0 + SH + TR)}; print(f'target {tn}:', {k: round(v, 3) for k, v in r.items()}); gbr += [(tn, k, v, v - base) for k, v in r.items()]
A = pd.DataFrame(ra, columns=['target', 'variable', 'AUC', 'lo', 'hi']).round(3); print(A.to_string(index=False)); H = pd.concat(hz).assign(bin=lambda d: d['bin'].astype(str)); print(H[H.target == 'B'].round(1).to_string(index=False))
A.to_csv(f'{OUT}/bl_book_trail_auc.csv', index=False); H.round(3).to_csv(f'{OUT}/bl_book_trail_hazard.csv', index=False); pd.DataFrame(gbr, columns=['target', 'model', 'LOCO_AUC', 'delta_vs_baseline']).round(4).to_csv(f'{OUT}/bl_book_trail_gb.csv', index=False)
