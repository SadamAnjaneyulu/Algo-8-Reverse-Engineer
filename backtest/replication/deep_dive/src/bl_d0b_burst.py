"""D0 chunk 2, burst description (quoted in addendum 2b and the report): in-scope buy-back lots grouped into bursts (same cycle and right, gap <= 30 s).
Per burst: lots, strikes, share of the right's open lots (real book at the burst's first minute), lowest / highest lot ratio, completeness (lots bought / open lots with ratio >= the burst's lowest ratio).
Outputs bl_d0b_bursts.csv, bl_summary_d0b5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_d0b_mach.py').read(); exec(src[:src.index('JJ = np.arange(375)')])
rows = []
for (i, cp), g in XS.groupby(['cid', 'cp']):
    g = g.sort_values('tod'); gid = (g.tod.diff().fillna(1e9) > 30).cumsum(); d = C[i]; ci = 0 if cp == 'CE' else 1
    for _, x in g.groupby(gid):
        j = int(x.j.min()); al = (d['j0'] <= j) & (d['jx'] >= j) & (d['cp'] == ci); rr = d['H'][al, j]
        rows.append(dict(cid=i, cp=cp, j=j, lots=len(x), n_open=int(al.sum()), share_open=len(x) / max(int(al.sum()), 1), strikes=x.strike.nunique(), rmin=x.ratio.min(), rmax=x.ratio.max(), completeness=len(x) / max(int((rr >= x.ratio.min()).sum()), 1)))
BU = pd.DataFrame(rows); BU.to_csv(f'{OUT}/bl_d0b_bursts.csv', index=False); big = BU[BU.lots >= 5]
R = dict(bursts=len(BU), lots_q=BU.lots.quantile([.5, .75, .9, .99]).tolist(), big_bursts=len(big), big_lot_share=float(big.lots.sum() / BU.lots.sum()), big_share_open_q=big.share_open.quantile([.25, .5, .75]).tolist(),
         big_strikes_q=big.strikes.quantile([.5, .9]).tolist(), big_rmin_q=big.rmin.quantile([.1, .5, .9]).tolist(), big_rmax_q=big.rmax.quantile([.1, .5, .9]).tolist(), big_completeness_q=big.completeness.quantile([.25, .5, .75]).tolist(),
         big_mixed_profit_loss=float(((big.rmin < 1) & (big.rmax > 1)).mean()))
Xa = X.copy(); Xa['blk'] = pd.cut(Xa.tod, [0, 34200, 36000, 43200, 50400, 54600, 99999], labels=['09:15-09:30', '09:30-10:00', '10:00-12:00', '12:00-14:00', '14:00-15:10', '15:10+'])
R['origin_D1_share_by_time'] = Xa.groupby('blk', observed=True).origin.apply(lambda s_: float((s_ == 'D-1').mean())).round(3).to_dict(); rec('d0b5', R); print(R)
