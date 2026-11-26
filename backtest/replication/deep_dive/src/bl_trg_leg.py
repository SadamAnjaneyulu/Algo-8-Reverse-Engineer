"""Trigger study step 6 (plan block E, one-pair-per-leg reading suggested by the same-side/time findings): are pairs spaced within a breakout leg?
A leg = run of consecutive minutes whose current close is beyond the prior 60 closes on the same side (look-ahead variant) / whose completed bar is (causal variant).
Null: the same number of pair-minutes of each cycle placed at random among that cycle's breakout-leg minutes (2,000 draws). Outputs bl_trg_leg.csv, bl_summary_trg5.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(404); R = {}; P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz').reset_index(drop=True); rows = []
for tag, col in (('look-ahead legs', 'bkLA60'), ('causal legs', 'bk60')):
    legs = []; mins = []
    for c_, g in P.groupby('cid'):
        g = g.sort_values('j'); b = g[col].values; y = g.y.values; lid = np.zeros(len(g), dtype=int); k = 0
        for i in range(len(g)):
            if b[i] != 0:
                if i == 0 or b[i - 1] != b[i] or g.j.values[i] != g.j.values[i - 1] + 1: k += 1
                lid[i] = k
        sel = lid > 0; mins.append(pd.DataFrame({'cid': c_, 'leg': lid[sel], 'y': y[sel]}))
    D = pd.concat(mins); D['key'] = D.cid * 100000 + D.leg
    def stats(d):
        g = d.groupby('key').y.sum(); return int((g >= 1).sum()), int((g >= 2).sum()), int(g.sum())
    ob = stats(D); n_leg = D.key.nunique(); sim = []
    for _ in range(2000):
        d2 = D.copy(); d2['y'] = d2.groupby('cid').y.transform(lambda s: rng.permutation(s.values)); sim.append(stats(d2))
    sim = np.array(sim); rows.append(dict(leg_definition=tag, legs=n_leg, leg_minutes=len(D), pair_minutes_in_legs=ob[2], legs_with_a_pair=ob[0], legs_with_2plus_pair_minutes=ob[1], null_mean_legs_with_pair=sim[:, 0].mean(), null_mean_legs_with_2plus=sim[:, 1].mean(), null_2plus_p_lower=float((sim[:, 1] <= ob[1]).mean()), null_2plus_lo=np.quantile(sim[:, 1], .025), null_2plus_hi=np.quantile(sim[:, 1], .975)))
L = pd.DataFrame(rows); L.round(3).to_csv(f'{OUT}/bl_trg_leg.csv', index=False); print(L.round(3).T.to_string()); R['legs'] = L.round(4).to_dict('records'); rec('trg5', R)
