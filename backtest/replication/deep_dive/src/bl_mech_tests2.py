"""Reactive-pair mechanism study, step 4 (plan tests A/C): the 10:30-15:15 active window (maximum-likelihood gate with cluster bootstrap, by subset), inter-arrival and refractory behaviour inside the window, spot-distance-to-strike, move since the previous reactive pair.
Outputs bl_mech_gate.csv, bl_mech_interarrival.csv, bl_summary_mech3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(301); R = {}; P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); P['g'] = P.und + P.expiry; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv')
clk = lambda m: f'{(9 * 60 + 15 + m) // 60}:{(9 * 60 + 15 + m) % 60:02d}'
def gate(Q, eps=1e-4):
    y = Q.yR.values; j = Q.j.values; best = (-1e18, None, None)
    for t0 in range(20, 150, 5):
        for t1 in range(280, 375, 5):
            inw = (j >= t0) & (j < t1); n1 = inw.sum(); e1 = y[inw].sum(); h = max(e1 / max(n1, 1), eps); n0 = (~inw).sum(); e0 = y[~inw].sum(); h0 = max(e0 / max(n0, 1), eps); l = e1 * np.log(h) + (n1 - e1) * np.log(1 - h) + e0 * np.log(h0) + (n0 - e0) * np.log(1 - h0)
            if l > best[0]: best = (l, t0, t1, h, h0)
    return best
b = gate(P); R['gate_all'] = dict(start=clk(b[1]), stop=clk(b[2]), h_in=float(b[3]), h_out=float(b[4])); print('ML window:', clk(b[1]), '-', clk(b[2]), f'hazard inside {b[3] * 1000:.1f} per 1000 cycle-minutes, outside {b[4] * 1000:.1f}')
ucy = P.g.unique(); idx = {c: P.index[P.g == c].values for c in ucy}; bs = []
for _ in range(60):
    ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); bb = gate(P.loc[ii].reset_index(drop=True)); bs.append((bb[1], bb[2]))
bs = np.array(bs); R['gate_boot_start'] = [clk(int(x)) for x in np.quantile(bs[:, 0], [.05, .5, .95])]; R['gate_boot_stop'] = [clk(int(x)) for x in np.quantile(bs[:, 1], [.05, .5, .95])]; print('bootstrap 5/50/95% start', R['gate_boot_start'], 'stop', R['gate_boot_stop'])
rows = []
yrs = sorted(P.expiry.unique()); med = yrs[len(yrs) // 2]
for nm, Q in (('NIFTY', P[P.und == 'NIFTY']), ('SENSEX', P[P.und == 'SENSEX']), ('first half', P[P.expiry < med]), ('second half', P[P.expiry >= med]), ('V1', P[P.v2 == 0]), ('V2', P[P.v2 == 1])):
    bb = gate(Q.reset_index(drop=True)); rows.append((nm, len(Q), clk(bb[1]), clk(bb[2]), bb[3] * 1000, bb[4] * 1000))
G = pd.DataFrame(rows, columns=['subset', 'cycle_minutes', 'start', 'stop', 'hazard_in_per1000', 'hazard_out_per1000']).round(2); G.to_csv(f'{OUT}/bl_mech_gate.csv', index=False); print(G.to_string(index=False)); R['gate_subsets'] = G.to_dict('list')
# inside the window: inter-arrival of reactive-pair minutes and refractory
W = P[(P.j >= b[1]) & (P.j < b[2])].copy(); ev = W[W.yR == 1]
W['age_b'] = pd.cut(W.age_react, [0, 1, 2, 3, 5, 10, 20, 40, 400]); t = W.groupby('age_b', observed=True).yR.agg(['size', 'sum']); t['per1000'] = (t['sum'] / t['size'] * 1000).round(1); print('\ninside the window: reactive hazard by minutes since the previous reactive pair'); print(t.to_string()); t.reset_index().assign(age_b=lambda d: d.age_b.astype(str)).to_csv(f'{OUT}/bl_mech_interarrival.csv', index=False)
ia = []
for (u, e), gg in Pr[Pr.reactive].sort_values('te').groupby(['und', 'expiry']):
    tt = gg.te.values; ia += list(np.diff(tt) / 60)
ia = np.array(ia); R['interarrival_q'] = np.quantile(ia, [.1, .25, .5, .75, .9]).tolist(); R['interarrival_mean'] = float(ia.mean()); R['interarrival_cv'] = float(ia.std() / ia.mean()); print(f'inter-arrival between successive reactive pairs (min): q10/25/50/75/90 {np.round(R["interarrival_q"], 1)}; mean {ia.mean():.1f}; CV {ia.std() / ia.mean():.2f} (Poisson = 1)')
R['hazard_age1'] = float(t.per1000.iloc[0]); R['hazard_age_rest'] = float(W[W.age_react > 5].yR.mean() * 1000)
rec('mech3', R)
