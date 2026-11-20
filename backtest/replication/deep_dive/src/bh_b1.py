"""B1: classify every body-stream (numeric tag) order by the contract's net position before it: Sell with net<=0 opens/adds a short, Sell with net>0 closes a long; Buy with net<0 covers a short, Buy with net>=0 opens/adds a long.
Same classification for hedge-stream (h_) orders. Contract-level, all modules, event order as in bh_h3c. Output outputs/bh_b1_order_roles.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
X = fills_x(); O = order_table(X); O['te'] = np.where(O.module.isin(['h_', 's_', 'v_', 'm_']), O.tt_dec, O.tt_first); O['sl'] = np.where(O.side == 'Buy', O.lots, -O.lots)
rows = []
for (u, e), o in O.groupby(['und', 'expiry']):
    comp = bool(o.complete.iloc[0]); o = o.sort_values(['te', 'row']); net = {}
    for r in o.itertuples():
        k = (r.cp, r.strike); n0 = net.get(k, 0)
        role = ('open_short' if n0 <= 0 else 'close_long') if r.side == 'Sell' else ('cover_short' if n0 < 0 else 'open_long')
        rows.append((r.tag, u, e, r.dayno, r.module, r.cp, r.strike, r.side, r.lots, n0, role, r.te, comp)); net[k] = n0 + r.sl
R = pd.DataFrame(rows, columns=['tag', 'und', 'expiry', 'dayno', 'module', 'cp', 'strike', 'side', 'lots', 'net_before', 'role', 'te', 'complete']); R.to_csv(f'{OUT}/bh_b1_order_roles.csv', index=False)
c = R[R.complete]
print(c.groupby(['module', 'dayno', 'role']).lots.sum().unstack('role').fillna(0).astype(int))
