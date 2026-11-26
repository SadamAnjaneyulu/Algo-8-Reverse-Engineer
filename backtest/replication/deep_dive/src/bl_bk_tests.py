"""Book-state study step 2 (plan BODY_REACTIVE_BOOK_PLAN.md tests A, B): single-variable AUCs (all seconds / within the range-edge population), hazard by decile, mechanism (effect of each pair on book delta).
Outputs bl_bk_uni.csv, bl_bk_decile.csv, bl_bk_mech.csv, bl_summary_bk1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
R = {}; B = pd.read_pickle(f'{OUT}/bl_bk_S.pkl.gz'); EV = pd.read_pickle(f'{OUT}/bl_bk_events.pkl.gz')
def auc(s, y):
    m = ~np.isnan(s); s = s[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return np.nan if n1 < 10 or n0 < 10 else (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
y = B.y.values; edge = (B.pos_N60.abs() > 0.5).values; half = B.cid.values % 2 == 0
V = ['delta', 'delta_vs_move', 'delta_vs_move_norm', 'delta_ce', 'delta_pe', 'gamma', 'short_lots', 'itm_short', 'net_lots', 'dist_out_move', 'dist_out_opp', 'dist_in_move', 'dist_in_opp', 'pnl_pct', 'pnl_chg5', 'pnl_chg15', 'pnl_chg30', 'delta_chg5', 'delta_chg15', 'delta_chg30', 'sig', 'sig_chg5', 'sig_chg15', 'sig_chg30', 'prem_tgt', 'prem_ratio_atm', 'prem_pos60', 'prem_chg15', 'pair_delta_1lot']
rows = []
for v in V:
    x = B[v].values.astype(float)
    for nm, tf in (('value', x), ('absolute value', np.abs(x))):
        rows.append(dict(variable=v, form=nm, AUC_all=auc(tf, y), AUC_even=auc(tf[half], y[half]), AUC_odd=auc(tf[~half], y[~half]), AUC_within_edge=auc(tf[edge], y[edge]), n_edge=int(edge.sum()), events_edge=int(y[edge].sum())))
U = pd.DataFrame(rows); U['strength'] = (U.AUC_all - .5).abs(); U['strength_edge'] = (U.AUC_within_edge - .5).abs(); U = U.sort_values('strength_edge', ascending=False); U.drop(columns=['strength', 'strength_edge']).round(3).to_csv(f'{OUT}/bl_bk_uni.csv', index=False); print(U.drop(columns=['strength', 'strength_edge']).head(16).round(3).to_string(index=False)); print('  ... top by all-seconds AUC:'); print(U.sort_values('strength', ascending=False).drop(columns=['strength', 'strength_edge']).head(8).round(3).to_string(index=False))
# deciles of the key variables within the edge population
rows = []
for v in ('delta_vs_move', 'delta_vs_move_norm', 'itm_short', 'dist_out_move', 'pnl_pct', 'prem_pos60', 'sig_chg15'):
    d = B[edge & B[v].notna()]; q = pd.qcut(d[v], 5, duplicates='drop'); t = d.groupby(q, observed=True).agg(n=('y', 'size'), events=('y', 'sum')); t['events_share_of_edge_events'] = t.events / t.events.sum(); t['events_per_control'] = t.events / (t.n - t.events); t['variable'] = v
    for k, r in t.reset_index().iterrows(): rows.append(dict(variable=v, bin=str(r.iloc[0]), seconds=int(r.n), events=int(r.events), events_per_control_second=float(r.events_per_control)))
pd.DataFrame(rows).round(4).to_csv(f'{OUT}/bl_bk_decile.csv', index=False); print(pd.DataFrame(rows).round(3).to_string(index=False))
# mechanism: effect of the pair on book delta
E_ = EV.copy(); E_['pair_dl'] = E_.pair_delta_1lot * E_.pair_lots; E_['delta_after'] = E_.delta + E_.pair_dl
m = E_.dropna(subset=['delta', 'pair_dl']); R['n_events'] = int(len(m))
R['share_pair_reduces_abs_delta'] = float((m.delta_after.abs() < m.delta.abs()).mean()); R['share_pair_moves_delta_toward_move_side'] = float((np.sign(m.pair_dl) == m.side).mean()); R['mean_pair_delta_lots'] = float(m.pair_dl.abs().mean())
R['share_book_exposed_against_move_before'] = float((m.delta_vs_move > 0).mean()); R['share_book_exposed_against_move_controls_edge'] = float((B[(B.y == 0) & edge].delta_vs_move > 0).mean()); R['share_book_exposed_against_move_controls_all'] = float((B[B.y == 0].delta_vs_move > 0).mean())
R['median_delta_vs_move_events'] = float(m.delta_vs_move.median()); R['median_delta_vs_move_controls_edge'] = float(B[(B.y == 0) & edge].delta_vs_move.median()); R['abs_delta_events_median'] = float(m.delta.abs().median()); R['abs_delta_controls_edge_median'] = float(B[(B.y == 0) & edge].delta.abs().median()); R['abs_delta_after_events_median'] = float(m.delta_after.abs().median())
R['pair_delta_sign_matches_side_share'] = R['share_pair_moves_delta_toward_move_side']
# if the pair were a delta hedge it would be placed when the book is exposed against the move: compare with the share for a random sign
R['events_delta_vs_move_q'] = [float(x) for x in m.delta_vs_move.quantile([.1, .25, .5, .75, .9])]; R['controls_edge_delta_vs_move_q'] = [float(x) for x in B[(B.y == 0) & edge].delta_vs_move.quantile([.1, .25, .5, .75, .9])]
print(json.dumps(R, indent=1, default=float)); pd.DataFrame([R]).T.to_csv(f'{OUT}/bl_bk_mech.csv'); rec('bk1', R)
