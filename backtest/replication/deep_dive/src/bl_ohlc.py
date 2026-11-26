"""True one-minute spot OHLC for D-1 of each live cycle (the chain cache kept only closes). Index layout matches the chain cache: index j = bar starting 09:15 + j minutes (bar label = bar start; verified in ohlcv_research/data_manifest.md).
Cached at outputs/bl_spot_ohlc.pkl.gz: dict (und, expiry) -> DataFrame[j, open, high, low, close]."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
P_ = f'{OUT}/bl_spot_ohlc.pkl.gz'
def build():
    import data as D
    S = D.Src(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); out = {}
    for r in CY.itertuples():
        x = S.csv(f'normalized/{r.und.lower()}/underlying/spot/{r.d1}.csv'); h = x.datetime.str.slice(11, 16).map(D.MI); x = x[h.notna()].assign(j=h[h.notna()].astype(int))
        a = pd.DataFrame({'j': range(375)}).merge(x[['j', 'open', 'high', 'low', 'close']], on='j', how='left').ffill().bfill(); out[(r.und, r.expiry)] = a
    pd.to_pickle(out, P_); return out
def load():
    return pd.read_pickle(P_) if os.path.exists(P_) else build()
if __name__ == '__main__':
    o = build(); k = list(o)[0]; print(len(o), k); print(o[k].head(3)); ch = Chain(); c = ch.cyc(*k); print('close match with chain cache:', np.nanmax(np.abs(np.array(c[(0, 'spot')], float) - o[k].close.values)))
