"""N7 (post-hoc, after N2-N5): which conditions do counter-labelled sales meet, against chance. Outputs bl_d0n_decomp.csv, bl_d0n_decomp_excl.csv, bl_d0n_minute15.csv, bl_summary_d0n5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); rng = np.random.default_rng(113); R = {}
other = lambda c: 'PE' if c == 'CE' else 'CE'
D = SO[SO.row >= 0].copy(); P = PN.set_index('row').loc[D.row.values]; D['prem_low_60'] = P.phx_prem_low_60.values > 0; D['prem_low_day'] = P.phx_prem_low_day.values > 0; D['prem_newlow_j'] = P.phx_prem_newlow_c.values > 0; D['spot_fresh_60'] = P.fresh_60.values > 0; D['m15'] = P.min_in_15.values; D['clock_min'] = D.m15.isin([0, 1, 14]); D['counter'] = D.type == 'counter-sell solo'
def near(s, bb, w, sh=0):
    k = np.zeros(len(s), bool)
    for n_, q in enumerate(s.itertuples()):
        b = bb[(bb.cid == q.cid) & (bb.cp == other(q.cp))].tod.values; k[n_] = bool(len(b) and (np.abs(b - (q.tod + sh)) <= w).any())
    return k
SLB = X[X.type == '3 stop-loss']; D['bb_2s'] = near(D, X, 2); D['sl_2s'] = near(D, SLB, 2); D['bb_2s_null'] = (near(D, X, 2, 900).astype(float) + near(D, X, 2, -900).astype(float)) / 2
conds = ['sl_2s', 'bb_2s', 'prem_low_60', 'prem_low_day', 'prem_newlow_j', 'spot_fresh_60', 'clock_min']
chance = {'sl_2s': np.nan, 'bb_2s': float(D.bb_2s_null.mean()), 'prem_low_60': float(PN.phx_prem_low_60.mean()), 'prem_low_day': float(PN.phx_prem_low_day.mean()), 'prem_newlow_j': float(PN.phx_prem_newlow_c.mean()), 'spot_fresh_60': float(PN.fresh_60.mean()), 'clock_min': float(PN.min_in_15.isin([0, 1, 14]).mean())}
rows = [dict(condition=c, counter_labelled=float(D[D.counter][c].mean()), other_solo=float(D[~D.counter][c].mean()), all_panel_cells_chance=chance[c]) for c in conds]; DC = pd.DataFrame(rows); DC.to_csv(f'{OUT}/bl_d0n_decomp.csv', index=False); print(DC.round(3).to_string(index=False))
# exclusive precedence (lots): same-instant buy-back (<=2 s) -> premium at 60-min low (j-1) -> spot fresh 60-min extreme -> clock minutes (0,1,14) -> none
def cls(r):
    if r.bb_2s: return '1 buy-back within 2 s'
    if r.prem_low_60: return '2 R′ premium at 60-min low'
    if r.spot_fresh_60: return '3 spot fresh 60-min extreme'
    if r.clock_min: return '4 minute 0/1/14 of the 15-min block'
    return '5 none of these'
D['why'] = [cls(r) for r in D.itertuples()]
EX = D.groupby(['why', 'counter']).lots.sum().unstack().fillna(0); EX = EX / EX.sum(); EX.columns = ['other_solo_share', 'counter_labelled_share']; EX = EX[['counter_labelled_share', 'other_solo_share']].reset_index(); EX.to_csv(f'{OUT}/bl_d0n_decomp_excl.csv', index=False); print(EX.round(3).to_string(index=False))
# chance level of the exclusive classes: same precedence over random panel cells would need sales; instead report the plain "none of these" share for random cells with y=1 shifted +/-15 min
sh = []
for s_ in (900, -900, 600, -600):
    Q = D.copy(); Q['j2'] = Q.j + s_ // 60; K = PN.set_index(['cid', 'j', 'cp']); idx = [(q.cid, q.j2, q.cp) for q in Q.itertuples()]; ok = np.array([i in K.index for i in idx]); Pk = K.loc[[i for i, o in zip(idx, ok) if o]]
    cls_ = np.where(Pk.phx_prem_low_60 > 0, 2, np.where(Pk.fresh_60 > 0, 3, np.where(Pk.min_in_15.isin([0, 1, 14]), 4, 5))); sh.append(float((cls_ == 5).mean()))
R['none_share_shifted_cells_ex_bb'] = float(np.mean(sh)); R['n_orders'] = len(D); R['n_counter_orders'] = int(D.counter.sum())
M = D.groupby(['m15', 'counter']).lots.sum().unstack().fillna(0); M = M / M.sum(); M.columns = ['other_solo_share', 'counter_labelled_share']; M['chance_share_of_cells'] = 1 / 15; M.reset_index().to_csv(f'{OUT}/bl_d0n_minute15.csv', index=False)
R['excl'] = EX.round(4).to_dict('records'); R['decomp'] = DC.round(4).to_dict('records'); rec('d0n5', R); print(R['none_share_shifted_cells_ex_bb'])
