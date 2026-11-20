"""H8: wave-level quantity test and sign-wrong concentration. A WAVE = consecutive hedge orders of one right (same cycle) whose stamps are within 0.05 s of the previous one (one decision emitting several orders).
Wave test: sum of signed lots == S - L at the wave's first stamp (book snapshot strictly before it). Output outputs/bh_h8_waves.csv, bh_h8_sign_wrong_by_cycle.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); bk = Book(O); Wd = O[(O.module == 'h_')].sort_values(['und', 'expiry', 'cp', 'tt_dec']); rows = []
for (u, e, cp), g in Wd.groupby(['und', 'expiry', 'cp']):
    comp = bool(bk.d[(u, e, cp)][3]); t = g.tt_dec.values; sw = np.where(g.side == 'Buy', g.lots, -g.lots); wid = np.cumsum(np.r_[1, np.diff(t) > 0.05])
    for w in np.unique(wid):
        m = wid == w; t0 = t[m][0]; S, Lg, _ = bk.state(u, e, cp, t0, inclusive=False); rows.append((u, e, cp, int(g.dayno.values[m][0]), t0, int(m.sum()), int(sw[m].sum()), int(S - Lg), comp, g.side.values[m][0]))
W = pd.DataFrame(rows, columns=['und', 'expiry', 'cp', 'dayno', 't0', 'n_orders', 'sum_signed', 'gap_at_start', 'complete', 'side']); W.to_csv(f'{OUT}/bh_h8_waves.csv', index=False)
c = W[W.complete]; c = c.assign(exact=c.sum_signed == c.gap_at_start, sign=np.sign(c.sum_signed) == np.sign(c.gap_at_start))
print('waves', len(W), 'complete', len(c), '| orders per wave', c.n_orders.value_counts().head(5).to_dict(), '| exact wave sum == gap', c.exact.mean().round(4), 'sign', c.sign.mean().round(4))
print(c.groupby(['dayno', 'side']).agg(n=('exact', 'size'), exact=('exact', 'mean'), sign=('sign', 'mean')).round(3))
print('exact by n_orders: ', c.groupby(c.n_orders.clip(upper=4)).exact.agg(['size', 'mean']).round(3).to_dict('index'))
Gs = pd.read_csv(f'{OUT}/bh_h7_sign_wrong.csv', dtype={'tag': str}); x = Gs.groupby(['und', 'expiry']).size().sort_values(ascending=False); x.to_csv(f'{OUT}/bh_h8_sign_wrong_by_cycle.csv'); print('sign-wrong by cycle (top):', x.head(6).to_dict(), ' cycles with any', len(x))
top = x.index[0]; y = Gs[(Gs.und == top[0]) & (Gs.expiry == top[1])]; print(top, 'gap_before dist', y.gap_before.value_counts().head(4).to_dict(), 'hours', ((y.tt_dec % 100000) // 3600).astype(int).value_counts().sort_index().to_dict(), 'sides', y.side.value_counts().to_dict(), 'lots', y.lots.value_counts().head(3).to_dict())
