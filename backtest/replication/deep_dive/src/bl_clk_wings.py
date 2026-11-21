"""Wing (hedge module) decode and link to the reactive entries. (1) For every body short-sell order leg: is it followed by an h_ long-wing buy of the same type within 10 s; delay, lots, wing strike offset and price; by sell class (scheduled / reactive / other). (2) Wing coverage (long lots / short lots) at the machine's first-break minutes: does coverage separate the break bars that get an entry from those that do not?
Outputs bl_clk_wings.csv, bl_clk_wingrule.csv, bl_summary_clk5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
R = {}; O = load_orders(); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O1 = O[O.dayno == 0]
rows = []; wrows = []
for r in CY.itertuples():
    z = O1[(O1.und == r.und) & (O1.expiry == r.expiry)].sort_values(['te', 'row']); g = Pr[(Pr.und == r.und) & (Pr.expiry == r.expiry)]
    sells = z[(z.module == 'num') & (z.role == 'open_short')]; wings = z[(z.module == 'h_') & (z.role == 'open_long')]
    cls = {}
    for p in g.itertuples(): cls[int(p.te)] = 'scheduled' if p.sched else 'reactive'
    for cp in ('CE', 'PE'):
        s = sells[sells.cp == cp]; w = wings[wings.cp == cp]; wt = w.te.values
        for t_, lots in zip(s.te.values, s.lots.values):
            k = np.searchsorted(wt, t_, 'left'); d = (wt[k] - t_) if k < len(wt) else np.nan; kind = cls.get(int(t_), 'other (solo / near a pair)')
            rows.append(dict(und=r.und, cp=cp, t=t_, kind=kind, lots=lots, delay_to_next_wing=d, wing_within_10s=int(d <= 10) if d == d else 0))
    ce = ch.px if False else None
W = pd.DataFrame(rows); print(W.groupby('kind').agg(sells=('lots', 'size'), share_followed_within_10s=('wing_within_10s', 'mean'), median_delay=('delay_to_next_wing', 'median')).round(3))
W.to_csv(f'{OUT}/bl_clk_wings.csv', index=False); R['follow_share'] = W.groupby('kind').wing_within_10s.mean().round(4).to_dict(); R['n_sells'] = W.groupby('kind').size().to_dict()
# lots: wing lots vs sell lots within each 10-s window per cycle and leg
tot = []
for r in CY.itertuples():
    z = O1[(O1.und == r.und) & (O1.expiry == r.expiry)]; sells = z[(z.module == 'num') & (z.role == 'open_short')]; wings = z[(z.module == 'h_') & (z.role == 'open_long')]
    for cp in ('CE', 'PE'): tot.append(dict(und=r.und, cp=cp, short_lots=int(sells[sells.cp == cp].lots.sum()), wing_lots=int(wings[wings.cp == cp].lots.sum()), body_wing_lots=int(z[(z.module == 'num') & (z.role == 'open_long') & (z.cp == cp)].lots.sum())))
T = pd.DataFrame(tot); print(T.groupby('cp')[['short_lots', 'wing_lots', 'body_wing_lots']].sum()); R['lots_by_leg'] = T.groupby('cp')[['short_lots', 'wing_lots', 'body_wing_lots']].sum().to_dict()
# wing price and offset
wp = O1[(O1.module == 'h_') & (O1.role == 'open_long')]; R['wing_price_q'] = wp.px_avg.quantile([.05, .25, .5, .75, .95]).round(2).to_dict(); print('wing price quantiles', R['wing_price_q'])
print(wp.groupby('cp').px_avg.describe().round(2))
pd.DataFrame([dict(cp=cp, **wp[wp.cp == cp].px_avg.describe().round(3).to_dict()) for cp in ('CE', 'PE')]).to_csv(f'{OUT}/bl_clk_wingrule.csv', index=False)
rec('clk5', R)
