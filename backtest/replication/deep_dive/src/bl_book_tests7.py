"""Capital-loss trigger study, part 7: is the short-horizon own-right loss signal the LOT'S OWN premium spike, an underlying move, or book-level loss? D-1 contract-minutes with cheapest-entry ratio < 1.2x; target B (residual) and A.
Features added (all causal, minute closes j-1 vs j-1-w, w = 1,3,5,15): own-lot premium change (%), own-lot Rs change per lot, adverse underlying move (% of spot; + = against the short right), right-book mark-only Rs change (dm), other-right mark-only change.
Univariate AUC (cluster bootstrap) and leave-one-cycle-out gradient boosting: baseline 12 variables; + lot/underlying short-horizon changes; + book mark-only changes; + both; permutation of each added block within cycle (3x). Outputs bl_book_lot_auc.csv, bl_book_lot_gb.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
rng = np.random.default_rng(71); ch = Chain(); LOTS = ref.LOT
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); P = P[(P.day == 'D-1') & (P.r_low < 1.2)].reset_index(drop=True)
resid = ev[ev.klass == 'sub-1.2x residual'].groupby(['und', 'expiry', 'day', 'cp', 'strike', 'j']).size().rename('resid_n').reset_index(); P = P.merge(resid, on=['und', 'expiry', 'day', 'cp', 'strike', 'j'], how='left').merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); P = P[P.B_total.notna()].reset_index(drop=True)
W = (1, 3, 5, 15); new = {f'{a}{w}': np.full(len(P), np.nan) for a in ('lot_pct', 'lot_inr', 'spot_adv', 'bk_own', 'bk_oth') for w in W}
for (u, e, cp), idx in P.groupby(['und', 'expiry', 'cp']).groups.items():
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); si = c['_si']; px = pd.DataFrame(np.array(c[(0, cp, 'close')], dtype=float)).ffill(axis=1).values; spot = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().values; sgn = 1 if cp == 'CE' else -1; lot = LOTS[u]; Q = P.loc[idx]
    ki = Q.strike.map(lambda k: si.get(int(k), -1)).values; j = Q.j.values
    for w in W:
        a = np.where(ki >= 0, px[np.maximum(ki, 0), np.maximum(j - 1, 0)], np.nan); b = np.where(ki >= 0, px[np.maximum(ki, 0), np.maximum(j - 1 - w, 0)], np.nan)
        new[f'lot_pct{w}'][idx] = a / b - 1; new[f'lot_inr{w}'][idx] = (a - b) * lot; new[f'spot_adv{w}'][idx] = sgn * (spot[np.maximum(j - 1, 0)] / spot[np.maximum(j - 1 - w, 0)] - 1) * 100
for w in W: P[f'bk_own{w}'] = np.where(P.cp == 'CE', P[f'dm{w}_CE'], P[f'dm{w}_PE']); P[f'bk_oth{w}'] = np.where(P.cp == 'CE', P[f'dm{w}_PE'], P[f'dm{w}_CE'])
for k, v in new.items():
    if not k.startswith('bk'): P[k] = v
P['abs_itm'] = P.itm_steps.abs(); P['o_r'] = P.o_r_avg; P['tod_min'] = P.j
FE0 = ['r_avg', 'r_low', 'r_fifo', 'abs_itm', 'itm_steps', 'hold_min', 'price', 'n_open', 'o_n_open', 'o_r', 'straddle_r', 'tod_min']
LOTB = [f'{a}{w}' for a in ('lot_pct', 'lot_inr', 'spot_adv') for w in W]; BKB = [f'{a}{w}' for a in ('bk_own', 'bk_oth') for w in W]
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
g = (P.und + P.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}; rows = []; gbr = []
for tn, y in (('B', (P.resid_n.fillna(0) > 0).astype(int).values), ('A', (P.bb_lots > 0).astype(int).values)):
    print(f'\n== D-1 target {tn}: rows {len(P):,}, events {y.sum()}')
    for f in LOTB + BKB:
        x = P[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(80))]; rows.append((tn, f, a, *np.nanquantile(bs, [.025, .975])))
    print(pd.DataFrame([r for r in rows if r[0] == tn], columns=['t', 'f', 'AUC', 'lo', 'hi']).drop(columns='t').round(3).to_string(index=False))
    def fold(X, c):
        tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=50, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
    def loco(cols, Qx=P):
        X = Qx[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
        for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
        return roc_auc_score(y, o)
    base = loco(FE0); res = {'baseline': base}
    for nm, cols in (('+ lot/underlying short-horizon', FE0 + LOTB), ('+ book mark-only', FE0 + BKB), ('+ both', FE0 + LOTB + BKB), ('+ lot/underlying, then book on top (book gain)', None)):
        if cols: res[nm] = loco(cols)
    for nm, blk in (('permute lot/underlying block', LOTB), ('permute book block', BKB)):
        nul = []
        for _ in range(3): Qp = P.copy(); Qp[blk] = Qp.groupby(g)[blk].transform(lambda s: rng.permutation(s.values)); nul.append(loco(FE0 + LOTB + BKB, Qp))
        res[nm + ' (all features, one block shuffled)'] = float(np.median(nul))
    full = res['+ both']; print({k: round(v, 3) for k, v in res.items()}); gbr += [(tn, k, v, v - base) for k, v in res.items()]
pd.DataFrame(rows, columns=['target', 'variable', 'AUC', 'lo', 'hi']).round(4).to_csv(f'{OUT}/bl_book_lot_auc.csv', index=False); pd.DataFrame(gbr, columns=['target', 'model', 'LOCO_AUC', 'delta_vs_baseline']).round(4).to_csv(f'{OUT}/bl_book_lot_gb.csv', index=False)
