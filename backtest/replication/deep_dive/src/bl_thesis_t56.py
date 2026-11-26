"""Design-thesis plan, Addendum 1 (post-hoc): T5 staggered 15-minute entries vs a single entry; T6 ladder trigger vs reference-book delta.
Output outputs/thesis/thesis_t5.csv, thesis_t6.csv, thesis_t56_stats.csv. Run: OMP_NUM_THREADS=1 python bl_thesis_t56.py"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.special import ndtr
from multiprocessing import Pool
import bl_thesis_tests as TT
OUT = TT.OUT; TH = TT.TH; BT3 = TT.BT3; B = 2000
def leg_delta(price, S, K, is_call):
    s = TT.total_std(price, S, K, is_call)
    if not np.isfinite(s): return (1.0 if S > K else 0.0) if is_call else (-1.0 if S < K else 0.0)        # price at/below intrinsic: deep ITM or worthless
    d1 = (np.log(S / K) + 0.5 * s * s) / s; return ndtr(d1) if is_call else ndtr(d1) - 1
def one(args):
    und, expiry, split = args; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); s1, s0, o1, o0 = c['spot1'], c['spot0'], c['opt1'], c['opt0']; L = TT.LOT[und]
    O1, C1, H1, L1 = (s1[k].values.astype(float) for k in ('open', 'close', 'high', 'low')); O0 = s0.open.values.astype(float)
    blocks = list(range(1, TT.END1 - 14, 15)); K0 = o1['K'][TT.atm_i(o1, O1[1])]; r = dict(und=und, expiry=expiry, split=split)
    def exit_px(K):
        i0 = int(np.searchsorted(o0['K'], K)); return TT.straddle(o0, i0, TT.END0, 'open') if i0 < len(o0['K']) and o0['K'][i0] == K else np.nan
    entries = []
    for mode in ('recentred', 'fixed'):
        pin = pout = 0.0; n = 0
        for j in blocks:
            K = o1['K'][TT.atm_i(o1, O1[j])] if mode == 'recentred' else K0; i = int(np.searchsorted(o1['K'], K)); a = TT.straddle(o1, i, j, 'open'); b = exit_px(K)
            if np.isfinite(a) and np.isfinite(b): pin += a; pout += b; n += 1
            if mode == 'recentred' and np.isfinite(a): entries.append((j, K))
        r[f'{mode}_ret'] = (pin - pout) / pin if pin > 0 else np.nan; r[f'{mode}_n'] = n
    a = TT.straddle(o1, int(np.searchsorted(o1['K'], K0)), 1, 'open'); b = exit_px(K0); r['single_ret'] = (a - b) / a if np.isfinite(a) and np.isfinite(b) else np.nan
    # T6: D-1 ladder triggers (same definition as T3) and the delta of the re-centred reference book sold before that minute
    t6 = []; ref = {'dn': O1[0], 'up': O1[0]}; stp = 0.2 * TT.KSTEP[und]
    for j in range(1, TT.END1):
        lo = max(j - TT.GATE, 0)
        for side in ('dn', 'up'):
            hit = (L1[j] < L1[lo:j].min() and ref['dn'] - L1[j] > stp) if side == 'dn' else (H1[j] > H1[lo:j].max() and H1[j] - ref['up'] > stp)
            if not hit: continue
            ref[side] = L1[j] if side == 'dn' else H1[j]; S = C1[j]; book = [(jj, K) for jj, K in entries if jj <= j]
            if not book: continue
            dbook = 0.0
            for _, K in book:
                i = int(np.searchsorted(o1['K'], K)); dbook -= leg_delta(TT.px(o1, 'CE', 'close', i, j), S, K, True) + leg_delta(TT.px(o1, 'PE', 'close', i, j), S, K, False)
            ia = TT.atm_i(o1, S); Ka = o1['K'][ia]; cp = 'CE' if side == 'dn' else 'PE'; dsale = -leg_delta(TT.px(o1, cp, 'close', ia, j), S, Ka, cp == 'CE')
            t6.append(dict(und=und, expiry=expiry, split=split, j=j, side=side, n_book=len(book), book_delta=dbook, sale_delta=dsale, reduces=abs(dbook + dsale) < abs(dbook), opposite_reduces=abs(dbook - dsale) < abs(dbook)))
    return r, t6
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]
    with Pool(4) as p: res = p.map(one, [(r.und, r.expiry, r.split3) for r in T0.itertuples()], chunksize=4)
    T5 = pd.DataFrame([a for a, _ in res]); T6 = pd.DataFrame([x for _, b in res for x in b]); T5.to_csv(f'{TH}/thesis_t5.csv', index=False); T6.to_csv(f'{TH}/thesis_t6.csv', index=False)
    T5['wk'] = pd.to_datetime(T5.expiry).dt.strftime('%G-%V'); T6['wk'] = pd.to_datetime(T6.expiry).dt.strftime('%G-%V')
    d = T5.dropna(subset=['single_ret', 'recentred_ret', 'fixed_ret']); rng = np.random.default_rng(20261124); w = d.wk.unique(); g = {k: v for k, v in d.groupby('wk')}
    st = lambda x: dict(single_mean=x.single_ret.mean(), recentred_mean=x.recentred_ret.mean(), fixed_mean=x.fixed_ret.mean(), single_sd=x.single_ret.std(), recentred_sd=x.recentred_ret.std(), fixed_sd=x.fixed_ret.std(),
                        sd_ratio_recentred_single=x.recentred_ret.std() / x.single_ret.std(), sd_ratio_recentred_fixed=x.recentred_ret.std() / x.fixed_ret.std(), mean_diff_recentred_single=(x.recentred_ret - x.single_ret).mean(),
                        p5_single=x.single_ret.quantile(.05), p5_recentred=x.recentred_ret.quantile(.05), worst_single=x.single_ret.min(), worst_recentred=x.recentred_ret.min())
    pt = st(d); bs = pd.DataFrame([st(pd.concat([g[k] for k in rng.choice(w, len(w))])) for _ in range(B)])
    rows = [dict(test='T5', stat=k, value=v, lo=bs[k].quantile(.025), hi=bs[k].quantile(.975), IS=st(d[d.split == 'IS'])[k], OOS=st(d[d.split == 'OOS'])[k], LIVE_FITTED=st(d[d.split == 'LIVE_FITTED'])[k]) for k, v in pt.items()]
    c6 = T6.groupby(['und', 'expiry', 'split', 'wk']).agg(reduces=('reduces', 'mean'), opposite_reduces=('opposite_reduces', 'mean'), book_pos_on_dn=('book_delta', lambda x: np.nan)).reset_index()
    sd = T6[T6.side == 'dn'].book_delta.gt(0).mean(); su = T6[T6.side == 'up'].book_delta.lt(0).mean()
    w6 = c6.wk.unique(); g6 = {k: v for k, v in c6.groupby('wk')}; rng = np.random.default_rng(20261124)
    for col in ('reduces', 'opposite_reduces'):
        bs6 = np.array([pd.concat([g6[k] for k in rng.choice(w6, len(w6))])[col].mean() for _ in range(B)])
        rows.append(dict(test='T6', stat=f'share of ladder triggers where the {"ladder" if col == "reduces" else "opposite"} sale reduces |book delta| (cycle-weighted)', value=c6[col].mean(), lo=np.quantile(bs6, .025), hi=np.quantile(bs6, .975),
                         IS=c6[c6.split == 'IS'][col].mean(), OOS=c6[c6.split == 'OOS'][col].mean(), LIVE_FITTED=c6[c6.split == 'LIVE_FITTED'][col].mean()))
    rows.append(dict(test='T6', stat='book delta > 0 at down triggers / < 0 at up triggers (event share)', value=(sd + su) / 2, lo=np.nan, hi=np.nan, IS=np.nan, OOS=np.nan, LIVE_FITTED=np.nan))
    S = pd.DataFrame(rows); S.to_csv(f'{TH}/thesis_t56_stats.csv', index=False); pd.set_option('display.width', 250); print(len(d), 'cycles;', len(T6), 'T6 events'); print(S.round(4).to_string())
