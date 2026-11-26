"""D0 step 1 (plan D0_PLAN.md): inventory and carry-over checks.
(a) lots by module x role x hour; carried book at the D0 open (real D-1 orders, contract level); share of D0 buy-backs that close carried lots (contract carried from D-1) vs lots sold on D0;
(b) scheduled timetable test: per version, the share of cycles with a body sell in each D0 minute (a fixed timetable shows minutes with a share near 1);
(c) hedge controller: quiet-time balance L = S per right on D0 (contract level, all modules, carried book included);
(d) clock: share of D0 buy-backs at second :00; the 15:14 clearance (lots in 15:14) and stop-module cycles.
Outputs bl_d0_inv_roles.csv, bl_d0_inv_hour.csv, bl_d0_timetable.csv, bl_summary_d0inv.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); R = {}
d0 = O[O.dayno == 1].copy(); d0['j'] = ((d0.tod - 33300) // 60).astype(int); d0['hour'] = (d0.tod // 3600).astype(int); d0['sg'] = np.where(d0.side == 'Buy', 1, -1)
ro = d0.groupby(['module', 'role']).agg(orders=('lots', 'size'), lots=('lots', 'sum'), cycles=('expiry', 'nunique')).reset_index(); ro.to_csv(f'{OUT}/bl_d0_inv_roles.csv', index=False); print(ro.to_string(index=False))
hr = d0.pivot_table(index='hour', columns=['module', 'role'], values='lots', aggfunc='sum').fillna(0).astype(int); hr.to_csv(f'{OUT}/bl_d0_inv_hour.csv'); print(hr.to_string())
carry = []; quiet = []; bbcar = [0, 0]
for i, r in enumerate(CY.itertuples()):
    z1 = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; net = {}
    for q in z1.itertuples(): k = (q.cp, int(q.strike)); net[k] = net.get(k, 0) + (1 if q.side == 'Buy' else -1) * q.lots
    carry.append(dict(cid=i, und=r.und, S_CE=-sum(v for (c, _), v in net.items() if c == 'CE' and v < 0), S_PE=-sum(v for (c, _), v in net.items() if c == 'PE' and v < 0), L_CE=sum(v for (c, _), v in net.items() if c == 'CE' and v > 0), L_PE=sum(v for (c, _), v in net.items() if c == 'PE' and v > 0)))
    z = d0[(d0.und == r.und) & (d0.expiry == r.expiry)].sort_values(['tod', 'row']); carried_short = {k for k, v in net.items() if v < 0}; sold_d0 = set()
    for q in z.itertuples():
        k = (q.cp, int(q.strike))
        if q.module == 'num' and q.role == 'open_short': sold_d0.add(k)
        if q.module == 'num' and q.role == 'cover_short': bbcar[0 if (k in carried_short and k not in sold_d0) else 1] += q.lots
    te = z.tod.values; pos = dict(net); zl = list(z.itertuples()); p_ = 0
    for t in range(33300 + 300, 55800, 60):
        while p_ < len(zl) and zl[p_].tod < t: q = zl[p_]; k = (q.cp, int(q.strike)); pos[k] = pos.get(k, 0) + q.sg * q.lots; p_ += 1
        if ((te >= t - 30) & (te < t)).any(): continue
        for cp in ('CE', 'PE'):
            S = -sum(v for (c, _), v in pos.items() if c == cp and v < 0); L = sum(v for (c, _), v in pos.items() if c == cp and v > 0)
            if S > 0: quiet.append(dict(cid=i, t=t, cp=cp, S=S, L=L))
C = pd.DataFrame(carry); Q = pd.DataFrame(quiet); Q['hour'] = Q.t // 3600
R['carried_book_median'] = C[['S_CE', 'S_PE', 'L_CE', 'L_PE']].median().to_dict(); R['bb_lots_on_carried_only_contracts'] = bbcar[0]; R['bb_lots_other'] = bbcar[1]
R['quiet_balanced'] = float((Q.S == Q.L).mean()); R['quiet_L_gt_S'] = float((Q.L > Q.S).mean()); R['quiet_by_hour'] = Q.groupby('hour').apply(lambda g: float((g.S == g.L).mean())).round(3).to_dict()
# timetable test
tt = []
for v in ('V1', 'V2'):
    cids = [i for i in range(len(CY)) if CY.iloc[i].version == v]; sells = d0[(d0.module == 'num') & (d0.role == 'open_short')].merge(CY.reset_index().rename(columns={'index': 'cid'})[['cid', 'und', 'expiry']], on=['und', 'expiry'])
    sv = sells[sells.cid.isin(cids)]; share = sv.groupby('j').cid.nunique() / len(cids)
    tt.append(dict(version=v, cycles=len(cids), minutes_share_ge_0p8=int((share >= 0.8).sum()), minutes_share_ge_0p6=int((share >= 0.6).sum()), minutes_with_any_sell=int(len(share)), lots_in_ge0p8_minutes=float(sv[sv.j.isin(share[share >= 0.8].index)].lots.sum() / sv.lots.sum())))
T = pd.DataFrame(tt); T.to_csv(f'{OUT}/bl_d0_timetable.csv', index=False); print(T.to_string(index=False))
bb = d0[(d0.module == 'num') & (d0.role == 'cover_short')]; R['bb_sec0'] = float(((bb.tod.round() % 60) == 0).mean()); R['lots_1514'] = int(d0[d0.j == 359].lots.sum()); R['lots_1514_by_role'] = d0[d0.j == 359].groupby(['module', 'role']).lots.sum().to_dict(); R['stop_cycles'] = int(d0[d0.module == 's_'].expiry.nunique())
R['lots_after_1515'] = int(d0[d0.j >= 360].lots.sum())
print({k: v for k, v in R.items() if k != 'lots_1514_by_role'}); print('15:14 lots by role', R['lots_1514_by_role']); R['lots_1514_by_role'] = {str(k): int(v) for k, v in R['lots_1514_by_role'].items()}; rec('d0inv', R)
