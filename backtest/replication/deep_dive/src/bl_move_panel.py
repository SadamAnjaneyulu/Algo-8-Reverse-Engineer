"""User hypothesis test, step 1: build the right-minute panel (D-1 and D0) with market-move and loss features for solo (single-leg) sells.
Pairing: a body short sale is PAIRED if the other right was sold at the same strike within 3 s; otherwise SOLO. Episode start = first solo sale on a right with no solo sale on that right in the previous 300 s.
Features (causal: spot/option data up to minute j-1, orders strictly before minute j), 'fav' = move FAVOURABLE to a short of that right in % of spot (CE: fall, PE: rise):
 fav5/15/30/60  : % favourable move over the last k minutes ; fav_open : since the session's first minute ; dd_ext : favourable excursion from the running extreme (CE: fall from the day high; PE: rise from the day low)
 own_ratio / other_ratio : price now / average entry of the right's / the other right's short book (>1 = losing)
 book_loss : combined premium P&L of both short books, % of premium collected (+ = loss)
Output outputs/bl_move_panel.csv (all rows, both days), bl_move_solo_sales.pkl.gz"""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); rows = []; solo_all = []
def pair_flags(S):
    S = S.copy().reset_index(drop=True); S['paired'] = False
    for (u, e, d, k), g in S.groupby(['und', 'expiry', 'dayno', 'strike']):
        ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']
        if not len(ce) or not len(pe): continue
        pt = np.sort(pe.tt_first.values); ct = np.sort(ce.tt_first.values)
        for i in ce.index: t = S.at[i, 'tt_first']; j = np.searchsorted(pt, t - 3); S.at[i, 'paired'] = j < len(pt) and pt[j] <= t + 3
        for i in pe.index: t = S.at[i, 'tt_first']; j = np.searchsorted(ct, t - 3); S.at[i, 'paired'] = j < len(ct) and ct[j] <= t + 3
    return S
ALL = pair_flags(O[(O.module == 'num') & (O.role == 'open_short')]); ALL.to_pickle(f'{OUT}/bl_move_solo_sales.pkl.gz')
def book(c, cp, u, e, d, T, j):
    pre = c[(c.cp == cp) & (c.tod < T)]; net = pre.groupby('strike').sl.sum(); sh = -net[net < 0]
    if sh.sum() <= 0: return np.nan, 0, 0.0, 0.0
    bs = pre[(pre.module == 'num') & (pre.side == 'Sell')]; avg = {k: (g.px_avg * g.lots).sum() / g.lots.sum() for k, g in bs.groupby('strike')}; now = {k: ch.px(u, e, d, cp, k, j - 1, 'close') for k in sh.index}
    ok = [k for k in sh.index if k in avg and now[k] == now[k] and avg[k] > 0]
    if not ok: return np.nan, sh.sum(), 0.0, 0.0
    ent = sum(sh[k] * avg[k] for k in ok); cur = sum(sh[k] * now[k] for k in ok); return cur / ent, sh.sum(), cur, ent
for d, flag in ((0, 'has_d1'), (1, 'has_d0')):
    for u, e, h in zip(cyc.und, cyc.expiry, cyc[flag]):
        if not h: continue
        spot = np.array([ch.spot(u, e, d, j) for j in range(375)]); C = O[(O.und == u) & (O.expiry == e) & (O.dayno == d)].sort_values(['te', 'row'])
        if d == 1: C = O[(O.und == u) & (O.expiry == e)].sort_values(['te', 'row'])          # D0 books include the carried D-1 positions
        runhi = np.maximum.accumulate(np.nan_to_num(spot, nan=0)); runlo = np.minimum.accumulate(np.where(np.isnan(spot), 1e12, spot))
        for cp in ('CE', 'PE'):
            sgn = 1 if cp == 'CE' else -1; me = ALL[(ALL.und == u) & (ALL.expiry == e) & (ALL.cp == cp) & (ALL.dayno == d)].sort_values('tod'); solo = me[~me.paired]; st = solo.tod.values
            starts = []; last = -1e9
            for t in st:
                if t - last > 300: starts.append(t)
                last = t
            smin = set(int((t - ref.OPEN_SEC) // 60) for t in st); emin = set(int((t - ref.OPEN_SEC) // 60) for t in starts); blocked = set()
            for t in starts: j0 = int((t - ref.OPEN_SEC) // 60); blocked.update(range(j0 + 1, j0 + 6))
            for j in range(61, 374):
                slotm = ((j - 1) % 15 == 0)
                if slotm and j not in smin: continue
                if j in blocked and j not in emin: continue
                T = ref.OPEN_SEC + j * 60; ratio_o, S_o, cur_o, ent_o = book(C, cp, u, e, d, T, j); ratio_x, S_x, cur_x, ent_x = book(C, 'PE' if cp == 'CE' else 'CE', u, e, d, T, j)
                if S_o <= 0: continue
                sp = spot[j - 1]; f = dict(day=['D-1', 'D0'][d], und=u, expiry=e, cp=cp, j=j, ep=int(j in emin), solo=int(j in smin), own_ratio=ratio_o, other_ratio=ratio_x, S_own=S_o, S_other=S_x,
                    book_loss=((cur_o + cur_x) / (ent_o + ent_x) - 1) * 100 if (ent_o + ent_x) > 0 else np.nan, fav_open=-sgn * (sp / spot[0] - 1) * 100,
                    dd_ext=(runhi[j - 1] - sp) / runhi[j - 1] * 100 if cp == 'CE' else (sp - runlo[j - 1]) / runlo[j - 1] * 100)
                for k in (5, 15, 30, 60): f[f'fav{k}'] = -sgn * (sp / spot[j - 1 - k] - 1) * 100
                rows.append(f)
Pn = pd.DataFrame(rows); Pn.to_csv(f'{OUT}/bl_move_panel.csv', index=False)
print(Pn.groupby('day').agg(rows=('ep', 'size'), episode_starts=('ep', 'sum'), solo_minutes=('solo', 'sum')).to_string()); print('solo share of sold lots:', {d: round(ALL[(ALL.dayno == i) & ~ALL.paired].lots.sum() / ALL[ALL.dayno == i].lots.sum(), 3) for i, d in enumerate(('D-1', 'D0'))})
