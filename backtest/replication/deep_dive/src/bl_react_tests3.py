"""Reactive-pair study, step 4: strike side vs the recent move, hazard by move size, fresh extremes. Outputs bl_react_side.csv, bl_react_move_hazard.csv, bl_summary_react3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); Pn = pd.read_csv(f'{OUT}/bl_react_panel.csv.gz')
X = Pr[Pr.reactive & (Pr.j <= 373)].merge(Pn[['und', 'expiry', 'j', 'ch1', 'ch3', 'ch5', 'ch15', 'ch30']], on=['und', 'expiry', 'j'], how='inner'); X['side'] = np.sign(X.strike - X.atm_prev); m = X[X.side != 0]; R['n_side'] = len(m); R['n_pairs_with_features'] = len(X); R['atm_share'] = float((X.side == 0).mean())
rows = []
for c in ('ch1', 'ch3', 'ch5', 'ch15', 'ch30'): rows.append((c, float((np.sign(m[c]) == m.side).mean()), len(m)))
S = pd.DataFrame(rows, columns=['window', 'share_strike_side_follows_move', 'n']); S.to_csv(f'{OUT}/bl_react_side.csv', index=False); R['side'] = dict(zip(S.window, S.share_strike_side_follows_move)); print(S.round(3).to_string(index=False))
# for timetable pairs, the same share (reference): do they sit on the ATM instead?
T = Pr[Pr.sched & (Pr.j <= 373)].merge(Pn[['und', 'expiry', 'j', 'ch15']], on=['und', 'expiry', 'j'], how='left'); R['sched_atm_share'] = float((T.strike == T.atm_prev).mean())
rows = []
for c, b in (('a3', [0, .03, .06, .1, .2, 5]), ('a5', [0, .05, .1, .2, .3, 5]), ('a15', [0, .1, .2, .3, 5])):
    t = Pn.groupby(pd.cut(Pn[c], b), observed=True).agg(n=('yR', 'size'), ev=('yR', 'sum'), solo=('yS', 'sum')); t['R_per1000'] = t.ev / t.n * 1000; t['solo_per1000'] = t.solo / t.n * 1000; t = t.reset_index().rename(columns={c: 'bin'}); t.insert(0, 'var', c); rows.append(t)
H = pd.concat(rows); H['bin'] = H.bin.astype(str); H.round(2).to_csv(f'{OUT}/bl_react_move_hazard.csv', index=False); print(H.round(1).to_string(index=False)); R['big_move_a15_ge03'] = [int(Pn[Pn.a15 > 0.3].yR.sum()), int((Pn.a15 > 0.3).sum())]
rec('react3', R)
