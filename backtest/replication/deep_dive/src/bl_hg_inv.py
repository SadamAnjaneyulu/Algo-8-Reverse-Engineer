"""D-1 long side, L1: inventory and lifecycle of every D-1 long-side order; contract-level book S/L per right through the day (all modules, flat at the D-1 open); quiet-time balance; L-S at the D-1 close vs v_ lots; wing premium and distance (steps, sigma units).
Outputs bl_hg_inv_roles.csv, bl_hg_inv_hour.csv, bl_hg_close.csv, bl_hg_wings.csv, bl_summary_hg1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OH = bl_ohlc.load(); R = {}
d1 = O[O.dayno == 0].copy(); d1['hour'] = ((d1.te - 33300) // 3600 + 9).astype(int); d1['lng'] = d1.role.isin(['open_long', 'close_long'])
roles = d1.groupby(['module', 'role']).agg(orders=('lots', 'size'), lots=('lots', 'sum'), cycles=('expiry', 'nunique')).reset_index(); roles.to_csv(f'{OUT}/bl_hg_inv_roles.csv', index=False); print(roles.to_string(index=False))
hr = d1[d1.lng].pivot_table(index='hour', columns=['module', 'role'], values='lots', aggfunc='sum').fillna(0).astype(int); hr.to_csv(f'{OUT}/bl_hg_inv_hour.csv'); print(hr.to_string())
# book replay
cl = []; quiet = []; wings = []
for i, r in enumerate(CY.itertuples()):
    z = d1[(d1.und == r.und) & (d1.expiry == r.expiry)].sort_values(['te', 'row']); pos = {}; o = OH[(r.und, r.expiry)]; c = o.close.values; st = ref.STEP[r.und]
    sgn = z.side.map({'Buy': 1, 'Sell': -1}) if 'Buy' in set(z.side) else z.side.map({'BUY': 1, 'SELL': -1})
    z = z.assign(sg=sgn.values); last_body = -1e9; te_list = z.te.values
    for q in z.itertuples():
        k = (q.cp, int(q.strike)); pos[k] = pos.get(k, 0) + q.sg * q.lots
        if q.module == 'h_' and q.role == 'open_long':
            j = min(max(int((q.te - 33300) // 60), 1), 374); wings.append(dict(cid=i, und=r.und, cp=q.cp, te=q.te, strike=q.strike, px=q.px_avg, lots=q.lots, off_spot=(q.strike - c[j - 1]) / st * (1 if q.cp == 'CE' else -1)))
    def SL(p, cp): s = -sum(v for (c2, _), v in p.items() if c2 == cp and v < 0); l = sum(v for (c2, _), v in p.items() if c2 == cp and v > 0); return s, l
    # quiet samples: every 60 s, state = all orders with te < t; quiet if no order within the previous 30 s
    for t in range(33300 + 120, 55800, 60):
        if ((te_list >= t - 30) & (te_list < t)).any(): continue
        p = {}
        for q in z[z.te < t].itertuples(): k = (q.cp, int(q.strike)); p[k] = p.get(k, 0) + q.sg * q.lots
        for cp in ('CE', 'PE'):
            s, l = SL(p, cp)
            if s > 0: quiet.append(dict(cid=i, t=t, cp=cp, S=s, L=l))
    v = z[z.module == 'v_']
    for cp in ('CE', 'PE'):
        s, l = SL(pos, cp); cl.append(dict(cid=i, und=r.und, expiry=r.expiry, cp=cp, S_close=s, L_close=l, gap=l - s, v_lots=int(v[v.cp == cp].lots.sum()), body_wing_lots=int(z[(z.module == 'num') & (z.cp == cp)].pipe(lambda x: (x.role == 'open_long') * x.lots).sum())))
Q = pd.DataFrame(quiet); C = pd.DataFrame(cl); W = pd.DataFrame(wings); C.to_csv(f'{OUT}/bl_hg_close.csv', index=False); W.to_csv(f'{OUT}/bl_hg_wings.csv', index=False)
R['quiet_balanced_share'] = float((Q.S == Q.L).mean()); R['quiet_n'] = len(Q); R['quiet_L_gt_S'] = float((Q.L > Q.S).mean()); R['quiet_L_lt_S'] = float((Q.L < Q.S).mean())
Q['hour'] = (Q.t - 33300) // 3600 + 9; R['quiet_balanced_by_hour'] = Q.groupby('hour').apply(lambda g: float((g.S == g.L).mean())).round(3).to_dict()
R['close_gap_equals_v'] = float((C.gap == C.v_lots).mean()); R['close_gap_equals_v_plus_bodywing'] = float((C.gap == C.v_lots + C.body_wing_lots).mean()); R['close_flat_or_v'] = float(((C.gap == 0) | (C.gap == C.v_lots)).mean())
R['wing_premium_q'] = W.px.quantile([.1, .25, .5, .75, .9]).round(2).to_dict(); R['wing_off_steps_q'] = W.groupby('und').off_spot.quantile([.25, .5, .75]).round(1).unstack().to_dict('index')
print({k: v for k, v in R.items()}); print(C.groupby('cp')[['S_close', 'L_close', 'gap', 'v_lots']].median()); rec('hg1', R)
