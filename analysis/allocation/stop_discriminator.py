"""Phase 2b - the discriminating allocation test.  PRE-REGISTERED before running.
Rows: D-1 / D0 contract-minutes with open short lots (falsify.t3_panel; ratio = previous-minute close / reference).  For an alternative reference X in {slot-allocation average,
chain-allocation average, contract (lot-weighted) average} keep only rows where the lowest individual entry price differs MATERIALLY from X:  X_ref / min_entry - 1 >= 10 %.
Because X_ref >= min_entry, ratio_lot >= ratio_X.  Regions at stop multiple k:
   A: lot-level crossed (ratio_lot >= k) but X NOT crossed (ratio_X < k)      B: both crossed      C: lot-level not crossed (baseline)
Hazard h_R = share of rows in region R in which a stop-labelled buy-back of that contract happened in that minute.
   theta = (h_A - h_C) / (h_B - h_C):  theta ~ 1  => A behaves like B  => the INDIVIDUAL entry is the reference;   theta ~ 0 => A behaves like C => the average X is the reference.
Minimum cell sizes (fixed in advance): >= 30 rows and >= 10 stop minutes in each of A and B, otherwise the cell is not reported.
Because the hazard rises steeply with ratio_lot, the A-vs-B comparison is confounded (B rows sit at higher lot-level ratios by construction); the MATCHED test below, which compares
high- and no-dispersion rows at the SAME lot-level ratio, is the registered primary hazard discriminator.  Decision rule for A/B (fixed in advance): lot-level favoured if the 90 % cycle-bootstrap lower bound of theta > 0.5; X favoured if the upper bound < 0.5; otherwise INCONCLUSIVE.
All k in {1.50, 1.55, 1.60, 1.65, 1.70} are reported (no k is selected on any split); DEV / VAL / TEST are reported separately; three ownership conventions.
python3 analysis/allocation/stop_discriminator.py -> results/stop_discriminator.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from common import orders, markets
from alloc import build_allocations, lot_ledger, RES
import falsify

LOT, SLOT, CHAIN, AVG = falsify.REFS[0], falsify.REFS[2], falsify.REFS[3], falsify.REFS[1]
ALT = {'slot-allocation average': SLOT, 'chain-allocation average': CHAIN, 'contract average': falsify.REFS[1]}
KS = [1.50, 1.55, 1.60, 1.65, 1.70]; MAT = 0.10; REP = 2000

def theta_boot(cnt, reps=REP, seed=0):
    """cnt: per-cycle array [nA, yA, nB, yB, nC, yC]."""
    S = cnt.sum(0); f = lambda S: (S[1] / max(S[0], 1) - S[5] / max(S[4], 1)) / max(S[3] / max(S[2], 1) - S[5] / max(S[4], 1), 1e-12)
    rng = np.random.default_rng(seed); idx = rng.integers(0, len(cnt), (reps, len(cnt))); T = []
    for r in range(reps):
        s = cnt[idx[r]].sum(0)
        if s[0] > 0 and s[2] > 0 and s[3] > 0: T.append(f(s))
    return f(S), (np.percentile(T, 5), np.percentile(T, 95)) if len(T) > 50 else (np.nan, np.nan)

STOP = '1 individual lot stop-loss'
BINS = np.round(np.arange(1.45, 2.2501, 0.05), 2)

def matched_delta(cnt, minn=20):
    """cnt (cycles x bins x 4) = [n_high, y_high, n_low, y_low]; bins with >= minn rows in both groups; returns (delta, h_low_weighted, n_bins_used)."""
    S = cnt.sum(0); ok = (S[:, 0] >= minn) & (S[:, 2] >= minn)
    if ok.sum() < 2: return np.nan, np.nan, int(ok.sum())
    nh, yh, nl, yl = S[ok].T; w = nh / nh.sum(); hh = yh / nh; hl = yl / nl
    return float((w * (hh - hl)).sum()), float((w * hl).sum()), int(ok.sum())

def matched_hazard(P, conv, reps=REP, seed=0):
    """Hazard of a stop minute at the SAME lot-level ratio, with the individual entry far below the average (>= 10 %, 'high') or equal to it (< 2 %, 'low').
    Lot-level reference: hazard depends on ratio_lot only => delta ~ 0.  Average reference: high-dispersion rows sit further from the average's threshold => delta < 0.
    Registered rule: 'average favoured' if the 90 % cycle-bootstrap upper bound of delta < 0; 'consistent with lot-level' if the interval contains 0 and its lower bound
    > -50 % of the low-dispersion hazard; else inconclusive.  Minimum 20 rows per group per ratio bin."""
    out = []; rng = np.random.default_rng(seed)
    for alt, col in ALT.items():
        d = P[LOT] / P[col] - 1; bi = np.digitize(P[LOT].values, BINS) - 1
        for day in (0, 1):
            for sp in ('DEV', 'VAL', 'TEST'):
                m = ((P.day == day) & (P.split == sp) & (bi >= 0) & (bi < len(BINS) - 1)).values; hi = (d >= MAT).values; lo = (d < 0.02).values
                cyc = P.cyc.values; y = P.y.values; cl = np.unique(cyc[m]); 
                if len(cl) < 2: continue
                cnt = np.zeros((len(cl), len(BINS) - 1, 4))
                for ci, c in enumerate(cl):
                    mm = m & (cyc == c)
                    for j, (g, yy) in enumerate(((hi, False), (hi, True), (lo, False), (lo, True))):
                        sel = mm & g & (y if yy else np.ones(len(y), bool)); np.add.at(cnt[ci, :, j], bi[sel], 1)
                dl, hl, nb = matched_delta(cnt)
                if not np.isfinite(dl): continue
                boot = [matched_delta(cnt[rng.integers(0, len(cl), len(cl))])[0] for _ in range(reps)]; lo_, hi_ = np.nanpercentile(boot, [5, 95])
                v = 'average favoured' if hi_ < 0 else ('consistent with lot-level' if (lo_ <= 0 <= hi_ and lo_ > -0.5 * hl) else 'inconclusive')
                out.append(dict(conv=conv, alternative=alt, day='D-1' if day == 0 else 'D0', split=sp, bins_used=nb, n_high=int(cnt[:, :, 0].sum()), stops_high=int(cnt[:, :, 1].sum()), n_low=int(cnt[:, :, 2].sum()),
                                stops_low=int(cnt[:, :, 3].sum()), delta=dl, delta_lo=lo_, delta_hi=hi_, h_low_weighted=hl, verdict=v))
    return out

def exit_level(o, L, mk, conv):
    """For every stop-labelled buy-back: the algo's OWN recovered quote L_b divided by the lowest individual entry, the slot / chain allocation average and the
    lot-weighted contract average of the lots open just before the order (open = entered earlier and not yet closed under the convention)."""
    from common import minute_index
    st = o[(o.label == STOP) & (o.closing_short == True) & (o.side == 'Buy')]; out = []
    for key, g in st.groupby([st.und, st.expiry]):
        key = (key[0], key[1])
        if key not in mk: continue
        m = mk[key]; arr = falsify.cycle_arrays(L, mk, key)
        for r in g.itertuples():
            tn = pd.Timestamp(r.t_dec).to_datetime64().astype('datetime64[ns]').astype('int64'); kb = m['k2i'].get((r.cp, r.strike), -1)
            if kb < 0: continue
            open_ = (arr['t0'] < tn) & (arr['t1'] >= tn)
            if not ((arr['ki'] == kb) & open_).any(): continue
            R = falsify.refs_at(arr, open_, None); n_open = int(((arr['ki'] == kb) & open_).sum())
            out.append(dict(conv=conv, split=r.split, day='D-1' if r.dte >= 1 else 'D0', cyc=f'{key[0]}|{key[1]}', oid=r.oid, L=float(r.L), n_open=n_open,
                            lot_min=R[LOT][kb], slot_min=R[SLOT][kb], chain_min=R[CHAIN][kb], wavg=R[falsify.REFS[1]][kb]))
    return pd.DataFrame(out)

def iqr_log(x):
    x = np.log(x[np.isfinite(x) & (x > 0)]); return np.subtract(*np.percentile(x, [75, 25])) if len(x) >= 10 else np.nan

def exit_level_summary(E, reps=REP, seed=0):
    rows = []; rng = np.random.default_rng(seed)
    for (conv, day, sp), g in E.groupby(['conv', 'day', 'split']):
        for alt, col in (('slot-allocation average', 'slot_min'), ('chain-allocation average', 'chain_min'), ('contract average', 'wavg')):
            m = g[(g[col] / g.lot_min) >= 1 + MAT]
            if len(m) < 30: continue
            rl = m.L / m.lot_min; rx = m.L / m[col]; cy = m.cyc.unique(); idx = {c: m[m.cyc == c] for c in cy}; boot = []
            for _ in range(reps):
                x = pd.concat([idx[cy[j]] for j in rng.integers(0, len(cy), len(cy))]); boot.append(iqr_log((x.L / x.lot_min).values) - iqr_log((x.L / x[col]).values))
            d = iqr_log(rl.values) - iqr_log(rx.values); lo, hi = np.nanpercentile(boot, [5, 95])
            rows.append(dict(conv=conv, day=day, split=sp, alternative=alt, n_material=len(m), mean_dispersion=float((m[col] / m.lot_min - 1).mean()), q05_lot=rl.quantile(.05), q50_lot=rl.median(),
                             q05_alt=rx.quantile(.05), q50_alt=rx.median(), iqr_log_lot=iqr_log(rl.values), iqr_log_alt=iqr_log(rx.values), diff_lot_minus_alt=d, diff_lo=lo, diff_hi=hi,
                             verdict='lot-level tighter' if hi < 0 else ('average tighter' if lo > 0 else 'inconclusive')))
    return pd.DataFrame(rows)

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); pd.set_option('display.max_rows', 400)
    o = orders(); mk = markets(); A = build_allocations(o); rows = []; MH = []
    for conv in ('cheap', 'fifo', 'lifo'):
        P = falsify.t3_panel(o, lot_ledger(conv, A), mk, conv); print(conv, len(P), flush=True); MH += matched_hazard(P, conv)
        for alt, col in ALT.items():
            Q = P[(P[col] / P[LOT] <= 1 / (1 + MAT)) | False] if False else P[(P[LOT] / P[col]) >= 1 + MAT]       # X_ref / min_entry - 1 >= MAT  <=>  ratio_lot / ratio_X >= 1 + MAT
            for day in (0, 1):
                for sp in ('DEV', 'VAL', 'TEST'):
                    X = Q[(Q.day == day) & (Q.split == sp)]
                    for k in KS:
                        a = (X[LOT] >= k) & (X[col] < k); b = (X[col] >= k); c = X[LOT] < k
                        if a.sum() < 30 or b.sum() < 30 or (a & X.y).sum() < 10 or (b & X.y).sum() < 10: continue     # pre-registered minimum: 30 rows and 10 stop minutes in A and B
                        per = np.array([[a[X.cyc == cy].sum(), (a & X.y)[X.cyc == cy].sum(), b[X.cyc == cy].sum(), (b & X.y)[X.cyc == cy].sum(), c[X.cyc == cy].sum(), (c & X.y)[X.cyc == cy].sum()]
                                        for cy in X.cyc.unique()])
                        th, ci = theta_boot(per); S = per.sum(0)
                        verdict = 'lot-level favoured' if ci[0] > 0.5 else ('average favoured' if ci[1] < 0.5 else 'inconclusive')
                        rows.append(dict(conv=conv, alternative=alt, day='D-1' if day == 0 else 'D0', split=sp, k=k, rows_A=int(S[0]), stops_A=int(S[1]), rows_B=int(S[2]), stops_B=int(S[3]),
                                         rows_C=int(S[4]), stops_C=int(S[5]), h_A=S[1] / S[0], h_B=S[3] / S[2], h_C=S[5] / max(S[4], 1), theta=th, theta_lo=ci[0], theta_hi=ci[1], verdict=verdict,
                                         n_cycles=len(per), stop_share_in_A=S[1] / max(S[1] + S[3], 1)))
        # share of actual stop minutes (material-dispersion rows) that lie in region A: stops the average-based reference would miss
    R = pd.DataFrame(rows); R.to_csv(os.path.join(RES, 'stop_discriminator.csv'), index=False)
    MHd = pd.DataFrame(MH); MHd.to_csv(os.path.join(RES, 'stop_discriminator_matched_hazard.csv'), index=False)
    print('MATCHED-HAZARD (same lot-level ratio; high vs no dispersion):'); print(MHd.round(4).to_string(index=False)); print(MHd.groupby(['day', 'verdict']).size().unstack(fill_value=0).to_string())
    Ex = pd.concat([exit_level(o, lot_ledger(c, A), mk, c) for c in ('cheap', 'fifo', 'lifo')]); Ex.to_csv(os.path.join(RES, 'stop_exit_refs.csv.gz'), index=False, compression='gzip')
    XS = exit_level_summary(Ex); XS.to_csv(os.path.join(RES, 'stop_discriminator_exit_level.csv'), index=False)
    print('EXIT-LEVEL (material dispersion >= 10 %):'); print(XS.round(3).to_string(index=False)); print(XS.groupby(['day', 'verdict']).size().unstack(fill_value=0).to_string())
    if len(R): print(R[(R.conv == 'cheap') & (R.k.isin([1.5, 1.6, 1.7]))][['alternative', 'day', 'split', 'k', 'rows_A', 'stops_A', 'rows_B', 'stops_B', 'h_A', 'h_B', 'h_C', 'theta', 'theta_lo', 'theta_hi', 'verdict']].round(4).to_string(index=False))
    print('\nHAZARD TEST verdict counts by day (reported cells only):'); print(R.groupby(['day', 'verdict']).size().unstack(fill_value=0).to_string() if len(R) else 'no cell met the minimum counts')
