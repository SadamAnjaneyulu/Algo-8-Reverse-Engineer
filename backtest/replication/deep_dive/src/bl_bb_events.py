"""Buy-back decode step 1: every D-1 body buy-back order with the open lots on its contract (real ledger, all body sells before it).
Ratios at decision: buy-back decision price (ref_px = limit / 1.15) / entry decision price (ref_px = limit / 0.85) and / entry fill, for the cheapest, average and most expensive open lot; trailing ratio vs the lowest minute low since the first open lot's entry; second of minute; lots bought on the same contract in the same second.
Outputs bl_bb_events.csv, bl_summary_bb1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); R = {}; rows = []
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row'])
    op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]; book = {}
    for q in z.itertuples():
        k = (q.cp, int(q.strike))
        if q.role == 'open_short': book.setdefault(k, []).extend([(q.te, q.ref_px, q.px_avg)] * int(q.lots)); continue
        lots = book.get(k, [])
        if not lots: rows.append(dict(cid=i, te=q.te, cp=q.cp, strike=q.strike, n_open=0)); continue
        j = min(int((q.te - 33300) // 60), 374); x = ki.get(int(q.strike)); er = np.array([l_[1] for l_ in lots]); ef = np.array([l_[2] for l_ in lots]); t0 = min(l_[0] for l_ in lots); j0 = int((t0 - 33300) // 60)
        lowmin = np.nanmin(op[(q.cp, 'low')][x, j0:j + 1]) if x is not None and j >= j0 else np.nan; sg = 1 if q.cp == 'CE' else -1
        same = z[(z.role == 'cover_short') & (z.cp == q.cp) & (z.strike == q.strike) & ((z.te - q.te).abs() < 1)].lots.sum()
        rows.append(dict(cid=i, te=q.te, sec=int(round(q.te % 60)) % 60, j=j, cp=q.cp, strike=q.strike, n_open=len(lots), same_second_lots=int(same), bb_ref=q.ref_px, bb_fill=q.px_avg,
                         r_ref_min=q.ref_px / er.min(), r_ref_avg=q.ref_px / er.mean(), r_ref_max=q.ref_px / er.max(), r_fill_min=q.px_avg / ef.min(), r_close_min=(op[(q.cp, 'close')][x, j - 1] / ef.min()) if x is not None else np.nan,
                         trail_low=q.ref_px / lowmin if lowmin and lowmin > 0 else np.nan, itm_steps=sg * (c[j - 1] - q.strike) / st, min_since_entry=(q.te - t0) / 60, hour=int(q.te // 3600)))
        # remove the lot with the highest ratio (cheapest entry) - convention, reported
        a = int(np.argmin(er)); lots.pop(a); book[k] = lots
E_ = pd.DataFrame(rows); E_.to_csv(f'{OUT}/bl_bb_events.csv', index=False)
E1 = E_[E_.n_open > 0]
R['n'] = len(E_); R['no_open_lot'] = int((E_.n_open == 0).sum()); R['share_sec0'] = float((E1.sec == 0).mean())
R['q_r_ref_min'] = E1.r_ref_min.quantile([.05, .1, .25, .5, .75, .9]).round(3).to_dict(); R['q_r_ref_min_sec0'] = E1[E1.sec == 0].r_ref_min.quantile([.05, .1, .25, .5, .75]).round(3).to_dict(); R['q_r_ref_min_other'] = E1[E1.sec != 0].r_ref_min.quantile([.05, .1, .25, .5, .75]).round(3).to_dict()
R['q_trail'] = E1.trail_low.quantile([.05, .1, .25, .5, .75]).round(3).to_dict()
print({k: v for k, v in R.items()})
print(pd.cut(E1.r_ref_min, [0, .8, 1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 2, 3, 10]).value_counts().sort_index().to_string())
print('sec0'); print(pd.cut(E1[E1.sec == 0].r_ref_min, [0, .8, 1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 2, 3, 10]).value_counts().sort_index().to_string()); rec('bb1', R)
