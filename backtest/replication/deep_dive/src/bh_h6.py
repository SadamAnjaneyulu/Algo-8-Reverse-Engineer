"""H6: exceptions. (A) the 928 DD-1 body bursts without a wing response within 10 s, classified (mutually exclusive, ordered rules) with the contract-level book S - L at burst end + 10 s;
(B) quiet-time imbalances from bh_h3b (|S - L| != 0 at body order + 30 s with no other body order in between), classified the same way.
Rules in order: carry_in_unknown (cycle log lacks D-1 or D0: S and L are not reconstructable) -> balanced (gap == 0) -> late (a hedge order of the right sign in (+10, +120] s) -> near_stop (an s_ order of the cycle within +-60 s) -> flatten (>= 15:14 on D0) -> d0_open_window (D0 before 09:18, post-hoc class) -> other.
Outputs outputs/bh_h6_bursts.csv, bh_h6_quiet.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); bk = Book(O); Bd = O[O.module == 'num']; Hd = O[O.module == 'h_']; Sd = O[O.module == 's_']; FL = 15 * 3600 + 14 * 60
D = pd.read_csv(f'{OUT}/dd_hedge_bursts.csv')
def classify(u, e, cp, d, t0, t1, gap, hold=10):
    if not bool(bk.d[(u, e, cp)][3]): return 'carry_in_unknown'
    h = Hd[(Hd.und == u) & (Hd.expiry == e) & (Hd.cp == cp) & (Hd.tt_dec > t1 + hold) & (Hd.tt_dec <= t1 + 120)]
    want = 'Buy' if gap > 0 else 'Sell'
    if gap == 0: return 'balanced'
    if (h.side == want).any(): return 'late_response'
    s = Sd[(Sd.und == u) & (Sd.expiry == e)]
    if ((s.tt_dec >= t0 - 60) & (s.tt_dec <= t1 + 60)).any(): return 'near_stop'
    if d == 1 and (t1 % 100000) >= FL: return 'flatten'
    if d == 1 and (t1 % 100000) < 9 * 3600 + 18 * 60: return 'd0_open_window'   # POST-HOC class added after seeing that 54 of 198 residuals sit in 09:15-09:17
    return 'other_imbalanced'
rows = []
nr = D[~D.responded]
for (u, e, cp), g in nr.groupby(['und', 'expiry', 'cp']):
    bb = Bd[(Bd.und == u) & (Bd.expiry == e) & (Bd.cp == cp)].sort_values('tt_first'); burst = (bb.tt_first.diff().fillna(1e9) > 3).cumsum(); ends = bb.groupby(burst).tt_first.agg(['min', 'max'])
    for r in g.itertuples():
        m = ends[ends['min'] == r.tt]; t1 = float(m['max'].iloc[0]) if len(m) else r.tt
        S, L, _ = bk.state(u, e, cp, t1 + 10, inclusive=True); gap = S - L
        rows.append((u, e, cp, r.day, r.tt, t1, r.dS, gap, S, L, classify(u, e, cp, r.day, r.tt, t1, gap), bool(bk.d[(u, e, cp)][3])))
A = pd.DataFrame(rows, columns=['und', 'expiry', 'cp', 'day', 't0', 't1', 'dS', 'gap_at_plus10', 'S', 'L', 'cls', 'complete']); A['hour'] = ((A.t1 % 100000) // 3600).astype(int); A.to_csv(f'{OUT}/bh_h6_bursts.csv', index=False)
print('(A) non-responding bursts', len(A)); print(A.cls.value_counts().to_dict()); print(A.groupby(['day', 'cls']).size().unstack(fill_value=0)); print('by right', A.groupby(['cp', 'cls']).size().unstack(fill_value=0).to_dict('index'))
Q = pd.read_csv(f'{OUT}/bh_h3b_quiet.csv'); Qb = Q[Q.gap_all != 0].copy(); cl = []
for r in Qb.itertuples(): cl.append(classify(r.und, r.expiry, r.cp, r.dayno, r.tt, r.T - 10 if False else r.tt, r.gap_all, hold=30))
Qb['cls'] = cl; Qb['hour'] = ((Qb.tt % 100000) // 3600).astype(int); Qb['under'] = Qb.gap_all > 0; Qb.to_csv(f'{OUT}/bh_h6_quiet.csv', index=False)
print('(B) quiet imbalances', len(Qb), 'of', len(Q), 'samples'); print(Qb.cls.value_counts().to_dict()); print('under-hedged (S>L) share', Qb.under.mean().round(3), 'by day', Qb.groupby('dayno').size().to_dict(), ' hour dist', Qb.hour.value_counts().sort_index().to_dict())
