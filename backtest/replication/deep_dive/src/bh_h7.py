"""H7 refinements, run after proofreading the draft report. (a) isolated-body-order lag histogram (no other body order on the same right within +-20 s) vs null; (b) snapshot-delay test: gap S-L evaluated at (stamp - delta), delta in 0..8 s (all reported);
(c) breakdown of sign-wrong hedge orders; (d) are unmatched body lots offset by an opposite body lot within +-20 s? Outputs outputs/bh_h7_*.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); bk = Book(O); B = O[O.module == 'num']; Wd = O[O.module == 'h_']
# (a)
EDGES = np.arange(-5, 20.0001, .5); h_real = np.zeros(len(EDGES) - 1); h_null = np.zeros(len(EDGES) - 1); SH = [137, -211, 389, -523]; niso = 0
for (u, e, cp, d), b in B.groupby(['und', 'expiry', 'cp', 'dayno']):
    w = Wd[(Wd.und == u) & (Wd.expiry == e) & (Wd.cp == cp) & (Wd.dayno == d)]
    if not len(w): continue
    tb = np.sort(b.tt_first.values)
    for sb, sw in (('Sell', 'Buy'), ('Buy', 'Sell')):
        t_s = np.sort(b[b.side == sb].tt_first.values); tw = np.sort(w[w.side == sw].tt_dec.values)
        if not len(t_s) or not len(tw): continue
        for t in t_s:
            if ((np.abs(tb - t) <= 20) & (tb != t)).any() or (tb == t).sum() > 1: continue
            niso += 1
            for shift, acc in [(0, h_real)] + [(s, h_null) for s in SH]:
                tws = tw + shift; lo = np.searchsorted(tws, t + EDGES[0]); hi = np.searchsorted(tws, t + EDGES[-1])
                if hi > lo: acc += np.histogram(tws[lo:hi] - t, bins=EDGES)[0]
HI = pd.DataFrame({'lag_lo': EDGES[:-1], 'lag_hi': EDGES[1:], 'real': h_real, 'null_per_shift': h_null / len(SH)}); HI.to_csv(f'{OUT}/bh_h7_isolated_lag.csv', index=False)
e_ = HI[(HI.lag_lo >= -2) & (HI.lag_hi <= 2.5)]; p_ = HI[(HI.lag_lo >= 2.5) & (HI.lag_hi <= 10)]
print('(a) isolated body lots (counted per direction):', niso, '| lags in [-2,2.5): real %.0f vs null %.0f total; lags in [2.5,10): real %.0f vs null %.0f' % (e_.real.sum(), e_.null_per_shift.sum(), p_.real.sum(), p_.null_per_shift.sum()))
# (b)
G = pd.read_csv(f'{OUT}/bh_h3c_wing_orders.csv', dtype={'tag': str}); G = G[G.complete]; res = []
for dl in (0, 1, 2, 3, 4, 5, 6, 8):
    ok = 0; n = 0
    for r in G.itertuples():
        S, Lg, _ = bk.state(r.und, r.expiry, r.cp, r.tt_dec - dl, inclusive=False); ok += (r.sw == S - Lg); n += 1
    res.append((dl, ok / n))
D = pd.DataFrame(res, columns=['delta_s', 'exact_share']); D.to_csv(f'{OUT}/bh_h7_snapshot_delta.csv', index=False); print('(b)', D.round(4).to_dict('records'))
# (c)
c = G.assign(wrong=np.sign(G.sw) != np.sign(G.gap_before)); w = c[c.wrong]
print('(c) sign-wrong', len(w), 'of', len(c)); print(w.groupby(['dayno', 'side']).size().to_dict()); w = w.assign(hh=((w.tt_dec % 100000) // 3600).astype(int)); print('by hour', w.hh.value_counts().sort_index().to_dict(), '| gap_before dist', w.gap_before.value_counts().head(6).to_dict())
w.to_csv(f'{OUT}/bh_h7_sign_wrong.csv', index=False)
# (d)
BL = pd.read_csv(f'{OUT}/bh_h1_body_lots.csv', dtype={'tag': str, 'wing_tag': str}); off = []
for (u, e, cp, d), g in BL.groupby(['und', 'expiry', 'cp', 'dayno']):
    g = g.sort_values('tt'); t = g.tt.values; sd = (g.side == 'Sell').values
    for i in range(len(g)):
        lo = np.searchsorted(t, t[i] - 20); hi = np.searchsorted(t, t[i] + 20, side='right'); idx = [k for k in range(lo, hi) if k != i and sd[k] != sd[i]]; off.append(len(idx) > 0)
BL['has_offset'] = off; print('(d) body lots with an opposite-direction body lot within +-20 s: matched %.3f vs unmatched %.3f' % (BL[BL.matched].has_offset.mean(), BL[~BL.matched].has_offset.mean()), ' n matched/unmatched', int(BL.matched.sum()), int((~BL.matched).sum()))
BL.groupby(['matched', 'has_offset']).size().unstack().to_csv(f'{OUT}/bh_h7_offset.csv')
