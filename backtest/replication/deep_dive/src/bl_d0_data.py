"""D0 data: true one-minute spot OHLC and option one-minute OHLC for the expiry day (D0 = expiry date) of each live cycle, same layout as the D-1 caches (index j = bar starting 09:15 + j minutes).
Outputs outputs/bl_d0_spot.pkl.gz ((und, expiry) -> DataFrame j/open/high/low/close), outputs/bl_d0_opt.pkl.gz ((und, expiry) -> {'K', (cp, field): K x 375}), bl_summary_d0data.json"""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import data as D
S_ = D.Src(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); spot = {}; opt = {}; R = {}
for r in CY.itertuples():
    d0 = r.expiry
    try:
        x = S_.csv(f'normalized/{r.und.lower()}/underlying/spot/{d0}.csv'); h = x.datetime.str.slice(11, 16).map(D.MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int))
        spot[(r.und, r.expiry)] = pd.DataFrame({'j': range(375)}).merge(x[['j', 'open', 'high', 'low', 'close']], on='j', how='left').ffill().bfill()
    except Exception as e: R[f'spot_missing_{r.und}_{d0}'] = str(e)[:80]
    try:
        x = S_.csv(f'normalized/{r.und.lower()}/options/exp{r.expiry}_{d0}.csv'); h = x.datetime.str.slice(11, 16).map(D.MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int))
        K = np.array(sorted(x.strike.unique()), float); ki = {k: i for i, k in enumerate(K)}; o = {'K': K}
        for cp in ('CE', 'PE'):
            z = x[x.right == cp]
            for col in ('open', 'high', 'low', 'close'):
                a = np.full((len(K), 375), np.nan); a[z.strike.map(ki).values, z.j.values] = z[col].values; o[(cp, col)] = pd.DataFrame(a).T.ffill().T.values
        opt[(r.und, r.expiry)] = o
    except Exception as e: R[f'opt_missing_{r.und}_{d0}'] = str(e)[:80]
pd.to_pickle(spot, f'{OUT}/bl_d0_spot.pkl.gz'); pd.to_pickle(opt, f'{OUT}/bl_d0_opt.pkl.gz'); R['spot_cycles'] = len(spot); R['opt_cycles'] = len(opt); rec('d0data', R); print(R)
