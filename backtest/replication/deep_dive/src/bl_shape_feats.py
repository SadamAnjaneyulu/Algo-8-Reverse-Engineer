"""Candidate 'shape' variables suggested by the flexible-model importance (multi-horizon spot move + time of day). Pre-registered after seeing GB importance (exploratory) and tested with the same LOCO / permutation-null protocol:
 dev_pair   : favourable distance of spot from the strike of the last PAIRED (clock) sale, in steps (the reference the straddle was struck at)
 dev_pair_pct: same in % of spot ; dev_slotref : favourable % move since the last slot minute
 bk15/bk30/bk60 : 1 if the previous close is the most favourable close of the last 15/30/60 minutes (breakout)
 tsext30    : minutes since the most favourable close of the last 60 minutes
 persist15  : share of the last 15 minute-returns that are favourable
 accel      : fav5 - fav15/3 (recent speed vs the 15-min average speed)
 fav_hi     : favourable move from the previous slot-minute spot (09:16+15k) to now over the elapsed time, normalised by sqrt(elapsed)
Output outputs/bl_shape_panel.csv (feature panel + these)"""
import sys; sys.path.insert(0, '.')
from bl_common import *
F = pd.read_csv(f'{OUT}/bl_feat_panel.csv'); ALL = pd.read_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz'); ch = Chain(); cache = {}; rows = []
for (day, u, e), Q in F.groupby(['day', 'und', 'expiry']):
    d = 0 if day == 'D-1' else 1; spot = np.array([ch.spot(u, e, d, j) for j in range(375)]); step = ref.STEP[u]
    for cp in ('CE', 'PE'):
        sgn = 1 if cp == 'CE' else -1; pr = ALL[(ALL.und == u) & (ALL.expiry == e) & (ALL.cp == cp) & (ALL.dayno == d) & ALL.paired].sort_values('tod'); pt = pr.tod.values; pk = pr.strike.values
        fav = -sgn * (spot / np.roll(spot, 1) - 1); fav[0] = np.nan
        for r in Q[Q.cp == cp].itertuples():
            j = r.j; T0 = ref.OPEN_SEC + j * 60; k = np.searchsorted(pt, T0) - 1; s1 = spot[j - 1]
            dp = -sgn * (s1 - pk[k]) / step if k >= 0 else np.nan; dpp = -sgn * (s1 / pk[k] - 1) * 100 if k >= 0 else np.nan
            slot_j = ((j - 1) // 15) * 15 + 1; sref = spot[slot_j - 1] if slot_j - 1 >= 0 else np.nan; dsl = -sgn * (s1 / sref - 1) * 100 if sref == sref else np.nan
            win = lambda n: -sgn * spot[j - 1 - n:j]; w15 = win(15); w30 = win(30); w60 = win(60); fr = fav[j - 15:j]
            rows.append(dict(index=r.Index, dev_pair=dp, dev_pair_pct=dpp, dev_slotref=dsl, bk15=int(w15[-1] >= np.nanmax(w15) - 1e-9), bk30=int(w30[-1] >= np.nanmax(w30) - 1e-9), bk60=int(w60[-1] >= np.nanmax(w60) - 1e-9), tsext30=(len(w60) - 1 - int(np.nanargmax(w60))), persist15=np.nanmean(fr > 0), accel=r.fav5 - r.fav15 / 3))
S = pd.DataFrame(rows).set_index('index'); F2 = F.join(S); F2.to_csv(f'{OUT}/bl_shape_panel.csv', index=False); print(F2[['dev_pair', 'dev_pair_pct', 'dev_slotref', 'bk15', 'bk60', 'tsext30', 'persist15', 'accel']].describe().round(3).T.to_string())
