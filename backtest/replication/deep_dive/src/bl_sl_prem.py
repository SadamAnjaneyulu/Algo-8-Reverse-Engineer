"""After-15:00 solo, step 6 (POST-HOC, labelled): is the trigger the sold option's own premium making a fresh N-minute low (theta/vol decay into the close) rather than a spot extreme?
Panel = bl_sl_panel (15:00-15:29 x right) plus the same panel for 10:30-14:59 (comparison). Candidate contract per right and minute: 1 strike ITM of ATM(previous close) (the modal late solo strike) and ATM.
Variables: pl_same = option 1-min low of minute j below the previous N lows (N = 5, 15, 30); pl_prev = same for minute j-1 (causal); own-fill check: share of sales whose price is within 0.2% of the minute low.
Outputs bl_sl_prem.csv, bl_summary_sl6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc, bl_sd_build
from scipy.stats import rankdata
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}
sol = D[(D.typ == 'solo') & ~D.deep]
def panel(j0, j1):
    rows = []
    for i, r in enumerate(CY.itertuples()):
        o = OH[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values; op = OP[(r.und, r.expiry)]; K = op['K']; st = ref.STEP[r.und]; s = sol[sol.cid == i]
        for j in range(j0, j1):
            atm = K[np.argmin(np.abs(K - c[j - 1]))]
            for cp in ('CE', 'PE'):
                d = dict(cid=i, j=j, cp=cp, y=int(((s.cp == cp) & (s.j == j)).any()), bk15=int((l[j] < l[j - 15:j].min()) if cp == 'CE' else (h[j] > h[j - 15:j].max())), bk15_prev=int((l[j - 1] < l[j - 16:j - 1].min()) if cp == 'CE' else (h[j - 1] > h[j - 16:j - 1].max())))
                for nm, k in (('itm', atm - st if cp == 'CE' else atm + st), ('atm', atm)):
                    w = np.where(np.abs(K - k) < 1)[0]
                    if not len(w): continue
                    pl = op[(cp, 'low')][w[0]]
                    for N in (5, 15, 30): d[f'pl{N}_{nm}'] = int(pl[j] < np.nanmin(pl[j - N:j])); d[f'pl{N}_{nm}_prev'] = int(pl[j - 1] < np.nanmin(pl[j - 1 - N:j - 1]))
                rows.append(d)
    return pd.DataFrame(rows)
def auc(s, y): n1 = y.sum(); n0 = len(y) - n1; return (rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
res = []
for lab, (a, b) in (('late 15:00-15:29', (345, 375)), ('intraday 10:30-14:59', (75, 345))):
    P = panel(a, b).dropna(); y = P.y.values
    for v in [c for c in P.columns if c not in ('cid', 'j', 'cp', 'y')]:
        x = P[v].values; res.append(dict(window=lab, variable=v, base_rate=x.mean(), recall=x[y == 1].mean(), hazard_if=y[x == 1].mean(), hazard_not=y[x == 0].mean(), AUC=auc(x.astype(float), y)))
    # combined: spot extreme OR premium low (same minute) on the ITM contract
    x = ((P.bk15 == 1) | (P.pl15_itm == 1)).values; res.append(dict(window=lab, variable='bk15 OR pl15_itm', base_rate=x.mean(), recall=x[y == 1].mean(), hazard_if=y[x].mean(), hazard_not=y[~x].mean(), AUC=auc(x.astype(float), y)))
    x = ((P.bk15 == 1) & (P.pl15_itm == 1)).values; res.append(dict(window=lab, variable='bk15 AND pl15_itm', base_rate=x.mean(), recall=x[y == 1].mean(), hazard_if=y[x].mean(), hazard_not=y[~x].mean(), AUC=auc(x.astype(float), y)))
    x = ((P.bk15 == 0) & (P.pl15_itm == 1)).values; res.append(dict(window=lab, variable='pl15_itm WITHOUT bk15', base_rate=x.mean(), recall=x[y == 1].mean(), hazard_if=y[x].mean(), hazard_not=y[~x].mean(), AUC=auc(x.astype(float), y)))
T = pd.DataFrame(res); T.round(3).to_csv(f'{OUT}/bl_sl_prem.csv', index=False); print(T.round(3).to_string(index=False)); R['table'] = T.round(4).to_dict('records')
# own-fill check: does Algo 8's own sale set the minute low?
own = []
for q in sol[sol.te >= 54000].itertuples():
    op = OP[(CY.iloc[q.cid].und, CY.iloc[q.cid].expiry)]; w = np.where(np.abs(op['K'] - q.strike) < 1)[0]; j = min(int(q.j), 374)
    if len(w): own.append(q.px <= op[(q.cp, 'low')][w[0]][j] * 1.002)
R['own_fill_at_low_share'] = float(np.mean(own)); print('late sales priced within 0.2% of the minute low:', round(np.mean(own), 3)); rec('sl6', R)
