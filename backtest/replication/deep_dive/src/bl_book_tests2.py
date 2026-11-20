"""Capital-loss trigger study, part 2 (plan tests 4 and 7): contract-minute panel of lots below 1.2x (cheapest-entry ratio). Targets: A = any sub-1.2x buy-back, B = residual sub-1.2x buy-back (not within 3 s of a >=1.5x buy-back).
Univariate AUC (cluster bootstrap over cycles, within-cycle permutation null); leave-one-cycle-out gradient boosting: baseline (12 earlier variables) vs + book P&L variables vs + post-hoc activity controls; permutation of the book columns within cycle.
Outputs bl_book_auc.csv, bl_book_gb.csv, bl_summary_book2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from joblib import Parallel, delayed
rng = np.random.default_rng(21); R = {}; LAKH = 1e5; LOTS = ref.LOT
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz')
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
resid = ev[ev.klass == 'sub-1.2x residual'].groupby(['und', 'expiry', 'day', 'cp', 'strike', 'j']).size().rename('resid_n').reset_index()
stopl = ev[ev.klass == 'stop-like (>=1.5x)'].groupby(['und', 'expiry', 'day', 'j']).size().rename('stop_n').reset_index()
def stop_prev(g, w):
    full = pd.Series(0.0, index=range(-w - 2, 400)); full.loc[g.j.values] = g.stop_n.values; c = full.cumsum(); return pd.Series({j: c.loc[j - 1] - c.loc[j - 1 - w] for j in range(0, 375)})
SP = {}
for (u, e, d), g in stopl.groupby(['und', 'expiry', 'day']): SP[(u, e, d)] = (stop_prev(g, 5), stop_prev(g, 15))
FE0 = ['r_avg', 'r_low', 'r_fifo', 'abs_itm', 'itm_steps', 'hold_min', 'price', 'n_open', 'o_n_open', 'o_r', 'straddle_r', 'tod_min']
BKF = ['B_total', 'B_day', 'DD', 'dB5', 'dB15', 'dB30', 'B_own', 'B_oth', 'B_diff', 'loss_pos_inr', 'loss_lot_inr']; CTL = ['stop_prev5', 'stop_prev15']
out_auc = []; out_gb = []
for day in ('D-1', 'D0'):
    Q = P[(P.day == day) & (P.r_low < 1.2)].reset_index(drop=True); Q = Q.merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left').merge(resid, on=['und', 'expiry', 'day', 'cp', 'strike', 'j'], how='left')
    Q['abs_itm'] = Q.itm_steps.abs(); Q['o_r'] = Q.o_r_avg; Q['tod_min'] = Q.j; Q['B_own'] = np.where(Q.cp == 'CE', Q.B_CE, Q.B_PE); Q['B_oth'] = np.where(Q.cp == 'CE', Q.B_PE, Q.B_CE); Q['B_diff'] = Q.B_own - Q.B_oth
    lot = Q.und.map(LOTS); Q['loss_pos_inr'] = (Q.price - Q.avg) * Q.n_open * lot; Q['loss_lot_inr'] = (Q.price - Q.avg) * lot
    Q['stop_prev5'] = [SP.get((u, e, day), (None, None))[0][j] if SP.get((u, e, day)) else 0 for u, e, j in zip(Q.und, Q.expiry, Q.j)]; Q['stop_prev15'] = [SP.get((u, e, day), (None, None))[1][j] if SP.get((u, e, day)) else 0 for u, e, j in zip(Q.und, Q.expiry, Q.j)]
    Q = Q[Q.B_total.notna()].reset_index(drop=True); g = (Q.und + Q.expiry).values; ucy = np.unique(g); idx = {c: np.where(g == c)[0] for c in ucy}
    for tn, y in (('A', (Q.bb_lots > 0).astype(int).values), ('B', (Q.resid_n.fillna(0) > 0).astype(int).values)):
        print(f'\n===== {day} target {tn}: rows {len(Q):,}, events {y.sum()}'); R[f'{day}_{tn}_rows'] = len(Q); R[f'{day}_{tn}_events'] = int(y.sum())
        for f in BKF + CTL + ['r_low', 'price', 'loss_pos_inr', 'loss_lot_inr']:
            x = Q[f].values.astype(float); a = auc(x, y); bs = [auc(x[ii], y[ii]) for ii in (np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(80))]
            nul = [auc(pd.Series(x).groupby(g).transform(lambda s: rng.permutation(s.values)).values, y) for _ in range(12)]; out_auc.append((day, tn, f, a, np.nanquantile(bs, .025), np.nanquantile(bs, .975), np.nanmedian(nul), np.nanmax(nul)))
        print(pd.DataFrame([r for r in out_auc if r[0] == day and r[1] == tn], columns=['d', 't', 'f', 'AUC', 'lo', 'hi', 'nm', 'nx']).round(3).drop(columns=['d', 't']).to_string(index=False))
        def fold(X, c):
            tr = g != c; m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.06, min_samples_leaf=50, random_state=0).fit(X[tr], y[tr]); return np.where(~tr)[0], m.predict_proba(X[~tr])[:, 1]
        def loco(cols, Qx=Q):
            X = Qx[cols].astype(float); X = X.fillna(X.median()).values; o = np.zeros(len(y))
            for i, p in Parallel(n_jobs=4)(delayed(fold)(X, c) for c in ucy): o[i] = p
            return roc_auc_score(y, o)
        base = loco(FE0); wb = loco(FE0 + BKF); wc = loco(FE0 + BKF + CTL); co = loco(FE0 + CTL); nul = []
        for _ in range(3):
            Qp = Q.copy(); Qp[BKF] = Qp.groupby(g)[BKF].transform(lambda s: rng.permutation(s.values)); nul.append(loco(FE0 + BKF, Qp))
        out_gb.append((day, tn, base, wb, wb - base, wc, wc - base, co, co - base, np.median(nul) - base, max(nul) - base)); print(f'LOCO GB: baseline {base:.3f}; + book {wb:.3f} (gain {wb - base:+.3f}; permuted-book gain median {np.median(nul) - base:+.3f}, max {max(nul) - base:+.3f}); + book + stop-activity controls {wc:.3f} ({wc - base:+.3f}); baseline + controls only {co:.3f} ({co - base:+.3f})')
pd.DataFrame(out_auc, columns=['day', 'target', 'variable', 'AUC', 'lo', 'hi', 'null_median', 'null_max']).round(4).to_csv(f'{OUT}/bl_book_auc.csv', index=False); G = pd.DataFrame(out_gb, columns=['day', 'target', 'baseline', 'plus_book', 'gain_book', 'plus_book_controls', 'gain_book_controls', 'baseline_plus_controls', 'gain_controls_only', 'perm_gain_median', 'perm_gain_max']).round(4); G.to_csv(f'{OUT}/bl_book_gb.csv', index=False); rec('book2', R)
