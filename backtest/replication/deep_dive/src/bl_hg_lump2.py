"""D-1 long side, L6b (POST-HOC hypotheses after bl_hg_lump.py): does the v_ lump (a) neutralise the whole-book delta for the overnight carry, or (b) spend a fixed rupee budget?
Book = all modules, D-1, Black-Scholes delta from the ATM straddle sigma*sqrt(T) (CycleBook). Lump delta = sum lots x delta at each lump strike at its minute. Output bl_hg_lump2.csv, bl_summary_hg6b.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import norm, spearmanr
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
import bl_ohlc
OH = bl_ohlc.load(); CYs = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); V = pd.read_csv(f'{OUT}/bl_hg_lump_orders.csv'); R = {}; rows = []
for i, r in enumerate(CYs.itertuples()):
    v = V[V.cid == i]
    if not len(v): continue
    cb = CycleBook(r.und, r.expiry, r.unit); c = OH[(r.und, r.expiry)].close.values; t0, t1 = v.te.min(), v.te.max(); pm0 = min(int((t0 - 33300) // 60), 374) - 1; S0 = c[pm0]
    b = cb.state(t0, S0, pm0); a = cb.state(t1 + 3.5, S0, pm0); sg = b.get('sig', np.nan)
    ld = 0.0
    for q in v.itertuples():
        d1 = np.log(S0 / q.strike) / sg + sg / 2; ld += q.lots * (norm.cdf(d1) if q.cp == 'CE' else norm.cdf(d1) - 1)
    pmE = 374; e = cb.state(55800 + 600, c[pmE], pmE)
    rows.append(dict(cid=i, und=r.und, unit=r.unit, lots=int(v.lots.sum()), rs=float((v.lots * v.px).sum() * r.unit), delta_before=b.get('delta'), lump_delta=ld, delta_after=a.get('delta'), delta_close=e.get('delta'), t_first=t0, t_last=t1, lumps_span_s=t1 - t0))
X = pd.DataFrame(rows); X['ratio_lump_to_minus_before'] = X.lump_delta / (-X.delta_before); X['abs_reduced'] = (X.delta_after.abs() < X.delta_before.abs()); X.to_csv(f'{OUT}/bl_hg_lump2.csv', index=False)
R['n'] = len(X); R['share_lump_opposes_book_delta'] = float((np.sign(X.lump_delta) == -np.sign(X.delta_before)).mean()); R['share_abs_delta_reduced'] = float(X.abs_reduced.mean())
R['ratio_q'] = X.ratio_lump_to_minus_before.quantile([.25, .5, .75]).round(3).to_dict(); R['abs_delta_before_median'] = float(X.delta_before.abs().median()); R['abs_delta_after_median'] = float(X.delta_after.abs().median()); R['abs_delta_close_median'] = float(X.delta_close.abs().median())
R['spearman_lump_delta_vs_minus_before'] = list(map(float, spearmanr(X.lump_delta, -X.delta_before))); R['spearman_lots_vs_abs_before'] = list(map(float, spearmanr(X.lots, X.delta_before.abs())))
R['rs_cv'] = float(X.rs.std() / X.rs.mean()); R['lots_cv'] = float(X.lots.std() / X.lots.mean()); R['rs_q'] = X.rs.quantile([.1, .5, .9]).round(0).to_dict()
print(X[['cid', 'und', 'lots', 'rs', 'delta_before', 'lump_delta', 'delta_after', 'delta_close']].round(1).to_string(index=False)); print({k: R[k] for k in R}); rec('hg6b', R)
