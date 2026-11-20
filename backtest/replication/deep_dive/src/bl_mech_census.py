"""Reactive-pair mechanism study, step 5 (plan test D): census of EVERY D-1 sell order (all modules) in mutually exclusive classes. Outputs bl_mech_census_orders.csv, bl_mech_census.csv, bl_summary_mech4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); L = pd.read_csv(f'{OUT}/bl_size_lot_classes.csv'); CYv = pd.read_csv(f'{OUT}/bl_size_cycles.csv')[['und', 'expiry']]
S = O[(O.dayno == 0) & (O.side == 'Sell')].copy(); S = S.merge(CYv, on=['und', 'expiry'], how='inner'); S['cls'] = 'residual'
key = lambda d: list(zip(d.und, d.expiry, d.te.round(3), d.cp, d.strike.astype(int)))
# body open_short: use the sizing classes (scheduled / reactive pair / solo), then split solo
bo = S[(S.module == 'num') & (S.role == 'open_short')].copy(); bo['k'] = key(bo); LL = L.copy(); LL['k'] = key(LL); m = dict(zip(LL.k, LL.cls3)); bo['cls'] = bo.k.map(m).fillna('solo')
solo = bo[bo.cls == 'solo'].copy(); solo['tag'] = 'single solo'
for (u, e), g in solo.groupby(['und', 'expiry']):
    g = g.sort_values('te'); ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']
    for i in g.index:
        r = solo.loc[i]; oth = pe if r.cp == 'CE' else ce
        if ((oth.te - r.te).abs() <= 3).any(): solo.loc[i, 'tag'] = 'near-pair (CE and PE within 3 s, different strikes)'
    sc = g.sort_values(['cp', 'strike', 'te']); gp = sc.groupby(['cp', 'strike']).te.diff(); burst = ((gp.isna()) | (gp > 3)).cumsum(); sz = sc.groupby(burst).lots.transform('sum')
    for i in sc.index[(sz >= 3).values]:
        if solo.loc[i, 'tag'] == 'single solo': solo.loc[i, 'tag'] = 'batch (>= 3 lots, one strike/right, within 3 s)'
solo.loc[(solo.tag == 'single solo') & (solo.tod >= 15 * 3600), 'tag'] = 'end-of-day solo (>= 15:00)'
bo.loc[solo.index, 'cls'] = solo.tag
S.loc[bo.index, 'cls'] = bo.cls
S.loc[(S.module == 'num') & (S.role == 'close_long'), 'cls'] = 'body sell closing a long wing'; S.loc[(S.module == 'h_') & (S.role == 'close_long'), 'cls'] = 'hedge-module sell closing a long wing'; S.loc[(S.module == 's_') & (S.role == 'close_long'), 'cls'] = 'stop-module sell closing a long wing'
for md in ('v_', 'm_'): S.loc[(S.module == md), 'cls'] = f'{md} module sell'
S.loc[(S.module == 'h_') & (S.role == 'open_short'), 'cls'] = 'hedge-module sell opening a short'; S.loc[(S.module == 's_') & (S.role == 'open_short'), 'cls'] = 'stop-module sell opening a short'
n = S.groupby(['und', 'expiry']).ngroups; C = S.groupby('cls').agg(orders=('lots', 'size'), lots=('lots', 'sum')); C['lots_per_cycle'] = (C.lots / n).round(1); C['share_of_sold_lots'] = (C.lots / C.lots.sum()).round(4); C['median_clock_h'] = S.groupby('cls').tod.median() / 3600; C['cycles_with'] = S.groupby('cls').apply(lambda d: d.groupby(['und', 'expiry']).ngroups); C = C.sort_values('lots', ascending=False); C.round(3).to_csv(f'{OUT}/bl_mech_census.csv'); print(C.round(3).to_string()); print('total sell lots', int(C.lots.sum()), 'orders', int(C.orders.sum()), 'cycles', n); R['census'] = C.round(4).reset_index().to_dict('list'); R['n_cycles'] = n; R['total_lots'] = int(C.lots.sum())
S[['und', 'expiry', 'module', 'role', 'cp', 'strike', 'te', 'tod', 'lots', 'cls']].to_csv(f'{OUT}/bl_mech_census_orders.csv', index=False)
# near-pair detail
np_ = S[S.cls.str.startswith('near-pair')]; R['near_pair_n'] = len(np_)
if len(np_):
    d = []
    for (u, e), g in np_.groupby(['und', 'expiry']):
        ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']
        for r in ce.itertuples():
            m_ = pe[(pe.te - r.te).abs() <= 3]
            if len(m_): d.append((m_.strike.iloc[0] - r.strike) / ref.STEP[u])
    d = pd.Series(d); R['near_pair_strike_diff_steps'] = d.round(0).value_counts(normalize=True).sort_index().round(3).to_dict(); print('near-pair PE strike minus CE strike (steps):', R['near_pair_strike_diff_steps'])
# batch detail
b = S[S.cls.str.startswith('batch')].sort_values(['und', 'expiry', 'cp', 'strike', 'te']).copy(); gp = b.groupby(['und', 'expiry', 'cp', 'strike']).te.diff(); b['bid'] = ((gp.isna()) | (gp > 3)).cumsum(); Bt = b.groupby('bid').agg(und=('und', 'first'), expiry=('expiry', 'first'), cp=('cp', 'first'), lots=('lots', 'sum'), orders=('lots', 'size'), tod=('tod', 'min'))
R['batch_n'] = len(Bt); R['batch_lots_q'] = Bt.lots.quantile([.1, .5, .75, .9, 1]).tolist(); R['batch_ce_share'] = float((Bt.cp == 'CE').mean()); R['batch_hour'] = {str(k): int(v) for k, v in (Bt.tod // 3600).astype(int).value_counts().sort_index().items()}; R['batch_big_n'] = int((Bt.lots >= 10).sum()); R['batch_big_share_of_lots'] = float(Bt[Bt.lots >= 10].lots.sum() / Bt.lots.sum()); R['batch_single_order_big'] = int(((Bt.lots >= 10) & (Bt.orders == 1)).sum()); R['batch_cycles'] = int(Bt.groupby(['und', 'expiry']).ngroups)
print('batches', R['batch_n'], 'lots q10/50/75/90/max', R['batch_lots_q'], 'CE share', round(R['batch_ce_share'], 2), 'hours', R['batch_hour'], 'big (>=10 lots)', R['batch_big_n'], 'share of batch lots', round(R['batch_big_share_of_lots'], 2))
rec('mech4', R)
