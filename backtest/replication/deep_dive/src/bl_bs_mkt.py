"""Buy-back second pass, step 3 (post-hoc refinement of the market condition found in step 2): which breakout? Donchian N in {15, 30, 45, 60, 90, 120} on closes (bar j-1, causal) and intrabar (minute j high/low beyond the previous N bars), the reactive two-candle clock channel (previous two 30-min candles' true high/low; close-based and intrabar), and 'running day extreme'.
Rule families (out-of-fold, contract-minute F1 +-1): (A) gate AND ratio_h >= t AND market; (B) gate AND (ratio_h >= t_hi OR (ratio_h >= t_lo AND market)).
Outputs bl_bs_mkt.csv, bl_summary_bs2.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); X = pd.read_pickle(f'{OUT}/bl_bs_panel.pkl.gz').sort_values(['cid', 'cp', 'strike', 'j']).reset_index(drop=True); R = {}
src = open('bl_bs_score.py').read(); exec(src[src.index("key = ("):src.index("CONT = [")])
sg = np.where(X.cp.values == 'CE', 1, -1); MK = {}
for N in (15, 30, 45, 60, 90, 120): MK[f'don{N}_close'] = np.zeros(len(X), bool); MK[f'don{N}_intra'] = np.zeros(len(X), bool)
MK['twocandle_close'] = np.zeros(len(X), bool); MK['twocandle_intra'] = np.zeros(len(X), bool); MK['day_extreme_intra'] = np.zeros(len(X), bool)
for i, r in enumerate(CY.itertuples()):
    m = np.where(X.cid.values == i)[0]
    if not len(m): continue
    o = OH[(r.und, r.expiry)]; hh, ll, cc = o.high.values, o.low.values, o.close.values; jj = X.j.values[m]; s = sg[m]
    for N in (15, 30, 45, 60, 90, 120):
        hi_c = np.array([hh[max(j - 1 - N, 0):j - 1].max() if j > 2 else np.inf for j in jj]); lo_c = np.array([ll[max(j - 1 - N, 0):j - 1].min() if j > 2 else -np.inf for j in jj])
        hi_i = np.array([hh[max(j - N, 0):j].max() for j in jj]); lo_i = np.array([ll[max(j - N, 0):j].min() for j in jj])
        MK[f'don{N}_close'][m] = np.where(s > 0, cc[jj - 1] > hi_c, cc[jj - 1] < lo_c); MK[f'don{N}_intra'][m] = np.where(s > 0, hh[jj] > hi_i, ll[jj] < lo_i)
    H2 = []; L2 = []
    for j in jj:
        b0 = ((33300 + 60 * j) // 1800) * 1800; a = max(int(np.ceil((b0 - 3600 - 33300) / 60)), 0); e = max(int(np.ceil((b0 - 33300) / 60)), 1)
        H2.append(hh[a:e].max() if e > a else np.inf); L2.append(ll[a:e].min() if e > a else -np.inf)
    H2, L2 = np.array(H2), np.array(L2); MK['twocandle_close'][m] = np.where(s > 0, cc[jj - 1] > H2, cc[jj - 1] < L2); MK['twocandle_intra'][m] = np.where(s > 0, hh[jj] > H2, ll[jj] < L2)
    MK['day_extreme_intra'][m] = np.where(s > 0, hh[jj] > np.array([hh[:j].max() for j in jj]), ll[jj] < np.array([ll[:j].min() for j in jj]))
s_ = X.ratio_h.values.astype(float); grid = np.round(np.arange(1.0, 1.91, 0.05), 2); rows = []
for mk_, mv in MK.items():
    for fam in ('A', 'B'):
        oof = []
        for tr in (h, ~h):
            if fam == 'A': best = max(grid, key=lambda t: f1(gate & (s_ >= t) & mv, tr)[0]); res = f1(gate & (s_ >= best) & mv, ~tr); par = best
            else:
                best = max(((a, b) for a in grid for b in grid if b < a), key=lambda ab: f1(gate & ((s_ >= ab[0]) | ((s_ >= ab[1]) & mv)), tr)[0]); res = f1(gate & ((s_ >= best[0]) | ((s_ >= best[1]) & mv)), ~tr); par = best
            oof.append((par, *res))
        rows.append(dict(market=mk_, family=fam, params=str([o[0] for o in oof]), F1_half1=oof[0][1], F1_half2=oof[1][1], F1=np.mean([o[1] for o in oof]), precision=np.mean([o[2] for o in oof]), recall=np.mean([o[3] for o in oof]), share_minutes_true=float(mv[gate].mean())))
T = pd.DataFrame(rows).sort_values('F1', ascending=False); T.round(4).to_csv(f'{OUT}/bl_bs_mkt.csv', index=False); print(T.round(3).head(16).to_string(index=False))
R['table'] = T.round(4).to_dict('records'); pd.to_pickle(MK, f'{OUT}/bl_bs_mk.pkl.gz'); rec('bs2', R)
