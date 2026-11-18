"""Contract-minute panel for open SHORT contracts (D-1 and D0), causal features, labelled with the exit category of any closing order
of that contract in that minute.  Excludes minutes at/after the cycle-stop.  python3 analysis/exit_engine/panel.py -> _cache/exit_panel.pkl"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from load import load_tagged
from a7_lean import bs_vec, iv_vec
C = os.path.join(os.path.dirname(HERE), '_cache')
def build():
    d = load_tagged().sort_values(['t', 'row']); d['m'] = d.t.dt.floor('min')
    X = pd.read_pickle(os.path.join(C, 'exit_taxonomy.pkl'))
    lab = X[X.closing_short].assign(m=lambda z: pd.to_datetime(z.t_dec).dt.floor('min')).groupby(['und', 'expiry', 'cp', 'strike', 'm']).label.first()
    ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
    I = pd.read_pickle(os.path.join(C, 'indicators_index.pkl')).set_index(['und', 'm'])
    stop_t = d[d.tp == 's_'].groupby(['und', 'expiry']).t.min()
    out = []
    for (u, e), c in d.groupby(['und', 'expiry']):
        days = sorted(c.date.unique()); lot = int(c.lot.iloc[0])
        s = ix[(ix.und == u) & ix.ts.dt.normalize().isin(days)].set_index('ts').close.sort_index()
        if len(s) < 50: continue
        grid = s.index; n = len(grid); gpos = {t: i for i, t in enumerate(grid)}
        oc = op[(op.und == u) & (op.expiry == e) & op.ts.isin(grid)]
        keys = sorted(set(zip(oc.cp, oc.strike)) | set(zip(c.cp, c.strike))); k2i = {k: i for i, k in enumerate(keys)}
        Cm = np.full((len(keys), n), np.nan); Hm = Cm.copy(); Lm = Cm.copy()
        ki = np.array([k2i[(a, b)] for a, b in zip(oc.cp, oc.strike)]); ti = np.array([gpos[t] for t in oc.ts])
        Cm[ki, ti] = oc.c.values; Hm[ki, ti] = oc.h.values; Lm[ki, ti] = oc.l.values
        Cf = pd.DataFrame(Cm.T).ffill().values.T; Lf = np.where(np.isfinite(Lm), Lm, Cf); Hf = np.where(np.isfinite(Hm), Hm, Cf)
        K = np.array([k for _, k in keys], float); isc = np.array([cc == 'CE' for cc, _ in keys])
        T = ((e + pd.Timedelta('15:30:00') - grid).total_seconds().values / (365 * 86400)).clip(min=1 / 525600); S = s.values
        intr = np.where(isc[:, None], np.maximum(S[None] - K[:, None], 0), np.maximum(K[:, None] - S[None], 0))
        Pc = np.maximum(np.nan_to_num(Cf, nan=0.05), intr + 0.05); shp = Pc.shape
        IV = iv_vec(np.broadcast_to(isc[:, None], shp), np.broadcast_to(S[None], shp), np.broadcast_to(K[:, None], shp), np.broadcast_to(T[None], shp), Pc)
        _, DEL = bs_vec(np.broadcast_to(isc[:, None], shp), S[None], K[:, None], T[None], IV)
        fills = {m: g for m, g in c.groupby('m')}
        lots = {k: [] for k in keys}; runmin = {}; runmax = {}; peak_c = {}; cash = 0.0; mtm_peak = 0.0
        cut = gpos.get(stop_t[(u, e)].floor('min'), n) if (u, e) in stop_t.index else n
        atr_s = I.reindex([(u, t) for t in grid])['1m_atr14_bp'].values * S / 1e4
        for i in range(1, min(cut, n)):
            # state at START of minute i (fills before minute i applied), marks = close of i-1
            book = cash + sum(sum(x[0] for x in lots[k]) * lot * Cf[k2i[k], i - 1] for k in keys if lots[k] and np.isfinite(Cf[k2i[k], i - 1]))
            mtm_peak = max(mtm_peak, book)
            side_up = {'CE': 0.0, 'PE': 0.0}
            for k in keys:
                if lots[k] and sum(x[0] for x in lots[k]) < 0 and np.isfinite(Cf[k2i[k], i - 1]):
                    side_up[k[0]] += sum(-x[0] * (x[1] - Cf[k2i[k], i - 1]) for x in lots[k]) * lot
            for k in keys:
                L_ = lots[k]
                if not L_ or sum(x[0] for x in L_) >= 0: continue
                kk = k2i[k]; p = Cf[kk, i - 1]
                if not np.isfinite(p): continue
                ents = np.array([x[1] for x in L_]); cj = int(np.argmin(ents)); ce = ents[cj]; cix = L_[cj][4]
                key = (k, cix)
                if key not in runmin: runmin[key] = np.nanmin(Lf[kk, cix:i]) if i > cix else p; runmax[key] = np.nanmax(Hf[kk, cix:i]) if i > cix else p
                else: runmin[key] = min(runmin[key], Lf[kk, i - 1]); runmax[key] = max(runmax[key], Hf[kk, i - 1])
                up_c = sum(-x[0] * (x[1] - p) for x in L_) * lot; peak_c[k] = max(peak_c.get(k, up_c), up_c)
                strike_up = sum(sum(-x[0] * (x[1] - Cf[k2i[kk2], i - 1]) for x in lots[kk2]) * lot for kk2 in keys if kk2[1] == k[1] and lots[kk2] and np.isfinite(Cf[k2i[kk2], i - 1]))
                se = L_[cj][3]
                out.append((u, e, grid[i], k[0], k[1], len(L_), ce, ents.mean(), p, Hf[kk, i], p / ce, p / ents.mean(), Hf[kk, i] / ce,
                            p / runmin[key] if runmin[key] > 0 else np.nan, runmax[key] / ce, up_c, up_c - peak_c[k], side_up[k[0]], strike_up, book, book - mtm_peak,
                            (S[i - 1] - se) / atr_s[i - 1] * (1 if k[0] == 'CE' else -1) if atr_s[i - 1] > 0 else np.nan,
                            (S[i - 1] - S[max(i - 6, 0)]) / atr_s[i - 1] * (1 if k[0] == 'CE' else -1) if atr_s[i - 1] > 0 else np.nan,
                            IV[kk, i - 1] - IV[kk, cix], abs(DEL[kk, i - 1]) - abs(DEL[kk, cix]), (i - cix), T[i] * 525600, grid[i].normalize() != e,
                            lab.get((u, e, k[0], k[1], grid[i]), 'none')))
            if grid[i] in fills:
                for r in fills[grid[i]].itertuples():
                    k = (r.cp, r.strike); sg = 1 if r.side == 'Buy' else -1; pos = sum(x[0] for x in lots[k]); nn = int(round(r.lots))
                    if (sg > 0 and pos < 0) or (sg < 0 and pos > 0):
                        lots[k].sort(key=lambda x: x[1] if pos < 0 else x[2]); take = min(nn, len(lots[k])); del lots[k][:take]; nn -= take
                    for _ in range(nn): lots[k].append([sg, r.px_fill, r.t, S[i - 1], i])
                    cash += -sg * r.px_fill * lot * int(round(r.lots))
    cols = ['und', 'expiry', 'm', 'cp', 'strike', 'n_lots', 'e_cheap', 'e_avg', 'px', 'hi', 'r_cheap', 'r_avg', 'rh_cheap', 'bounce', 'rmax_cheap', 'upnl_contract',
            'dd_contract', 'upnl_side', 'upnl_strike', 'cycle_mtm', 'cycle_dd', 'spot_move_atr', 'mv5_atr', 'iv_chg', 'absdelta_chg', 'min_since_cheap', 'tte_min', 'is_d1', 'label']
    P = pd.DataFrame(out, columns=cols); P.to_pickle(os.path.join(C, 'exit_panel.pkl')); return P
if __name__ == '__main__':
    P = build(); print(P.shape); print(P.label.value_counts().to_string())
