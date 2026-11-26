"""Buy-back decode step 2: event level (orders on one contract within 3 s). (a) quantity rule for stop-like events: lots closed vs open lots whose own ratio (event decision price / lot entry decision price) >= theta;
(b) low-ratio events (first ratio < 1.45): cluster (stop-like event on the same right within 3 s / 60 s, other strike), roll (body sell on the same right within 10 s / 60 s after), clock second 0, ITM depth, time since entry, trailing ratio.
Outputs bl_bb_qty.csv, bl_bb_lowclass.csv, bl_summary_bb2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); R = {}
G = pd.read_csv(f'{OUT}/bl_bb_eventlevel.csv'); E = pd.read_csv(f'{OUT}/bl_bb_events.csv')
# (a) quantity: rebuild open lots at each event's first order
q = []
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); book = {}; g = G[G.cid == i].set_index('te')
    evstart = set(g.index)
    for o in z.itertuples():
        k = (o.cp, int(o.strike))
        if o.role == 'open_short': book.setdefault(k, []).extend([o.ref_px] * int(o.lots)); continue
        if o.te in evstart and k == (g.loc[o.te].cp if not isinstance(g.loc[o.te], pd.DataFrame) else g.loc[o.te].cp.iloc[0], int(g.loc[o.te].strike if not isinstance(g.loc[o.te], pd.DataFrame) else g.loc[o.te].strike.iloc[0])):
            row = g.loc[o.te] if not isinstance(g.loc[o.te], pd.DataFrame) else g.loc[o.te].iloc[0]; er = np.array(book.get(k, []))
            if len(er): q.append(dict(cid=i, te=o.te, lots=int(row.lots), n_open=len(er), r_first=float(o.ref_px / er.min()), **{f'n_ge_{t}': int((o.ref_px / er >= t).sum()) for t in (1.3, 1.4, 1.45, 1.5, 1.55, 1.6)}))
        lots = book.get(k, [])
        if lots: lots.pop(int(np.argmin(lots)))
Q = pd.DataFrame(q); Q.to_csv(f'{OUT}/bl_bb_qty.csv', index=False); s = Q[Q.r_first >= 1.45]
R['qty'] = {t: dict(exact=float((s.lots == s[f'n_ge_{t}']).mean()), within1=float(((s.lots - s[f'n_ge_{t}']).abs() <= 1).mean())) for t in (1.3, 1.4, 1.45, 1.5, 1.55, 1.6)}; R['qty']['one_lot'] = dict(exact=float((s.lots == 1).mean())); R['qty']['all_open'] = dict(exact=float((s.lots == s.n_open).mean()))
print('quantity rules (stop-like events):', {k: {a: round(b, 3) for a, b in v.items()} for k, v in R['qty'].items()})
# (b) low-ratio events
rows = []
for x in G.itertuples():
    r = CY.iloc[x.cid]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num')]
    st_ = G[(G.cid == x.cid) & (G.cp == x.cp) & (G.r_first >= 1.45) & (G.strike != x.strike)]
    sells = z[(z.role == 'open_short') & (z.cp == x.cp)]
    rows.append(dict(ev=x.Index, low=int(x.r_first < 1.45), cluster3=int(((st_.te - x.te).abs() <= 3).any()), cluster60=int(((st_.te - x.te).abs() <= 60).any()), roll10=int(((sells.te - x.te) >= 0).__and__((sells.te - x.te) <= 10).any()), roll60=int(((sells.te - x.te) >= 0).__and__((sells.te - x.te) <= 60).any()),
                     roll_strike_toward_atm=np.nan, sec0=int(x.sec == 0), itm=x.itm, r_first=x.r_first, lots=x.lots, after_1500=int(x.te >= 54000), hour=int(x.te // 3600)))
L = pd.DataFrame(rows); L.to_csv(f'{OUT}/bl_bb_lowclass.csv', index=False)
for lab, g in L.groupby('low'):
    R[f'low{lab}'] = {k: float(g[k].mean()) for k in ('cluster3', 'cluster60', 'roll10', 'roll60', 'sec0', 'after_1500')} | dict(n=len(g), itm_median=float(g.itm.median()))
    print('low' if lab else 'stop-like', {k: round(v, 3) for k, v in R[f'low{lab}'].items()})
lo = L[L.low == 1]; lo = lo.assign(cls=np.select([lo.cluster3 == 1, lo.roll10 == 1, lo.after_1500 == 1], ['cluster (stop on same right within 3 s)', 'roll (sell on same right within 10 s after)', 'after 15:00'], 'other'))
print(lo.cls.value_counts().to_dict()); print('other: hour dist', lo[lo.cls == 'other'].hour.value_counts().sort_index().to_dict(), 'sec0', lo[lo.cls == 'other'].sec0.mean().round(2), 'itm median', lo[lo.cls == 'other'].itm.median())
R['low_classes'] = lo.cls.value_counts().to_dict(); rec('bb2', R)
