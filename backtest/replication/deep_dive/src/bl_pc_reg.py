"""Pace study regularity test (POST-HOC): how closely does each cycle's cumulative count of reactive pairs (and of fires) follow a straight line from 10:30 to 15:15, compared with the same number of events placed at random times in the window (5,000 draws)? Statistic = Kolmogorov-Smirnov distance and RMS deviation of cum(t)/N from (t-t0)/(T-t0).
Outputs bl_pc_reg.csv, bl_summary_pc4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(31); R = {}; Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); F = pd.read_csv(f'{OUT}/bl_trk_fires.csv'); T0, T1 = 37800, 54900
def stat(ts):
    ts = np.sort(ts); n = len(ts); u = (ts - T0) / (T1 - T0); c = np.arange(1, n + 1) / n; ks = max(np.max(np.abs(c - u)), np.max(np.abs(np.arange(0, n) / n - u))); grid = np.linspace(0, 1, 200); cc = np.searchsorted(u, grid, 'right') / n; return ks, np.sqrt(np.mean((cc - grid) ** 2))
rows = []
for nm, src, col in (('reactive pairs (all)', Pr[Pr.reactive].rename(columns={'te': 't'}), 't'), ('fires (pairs within 5 s merged)', F, 't')):
    obs = []; plc = []
    cyc = [g for _, g in src.groupby(['und', 'expiry'])]
    for g in cyc:
        ts = g[col].values; ts = ts[(ts >= T0) & (ts <= T1)]
        if len(ts) < 3: continue
        obs.append(stat(ts))
    obs = np.array(obs); k_o, r_o = obs[:, 0].mean(), obs[:, 1].mean(); pl_k = []; pl_r = []
    for _ in range(3000):
        v = []
        for g in cyc:
            n = int(((g[col].values >= T0) & (g[col].values <= T1)).sum())
            if n < 3: continue
            v.append(stat(rng.uniform(T0, T1, n)))
        v = np.array(v); pl_k.append(v[:, 0].mean()); pl_r.append(v[:, 1].mean())
    rows.append(dict(group=nm, cycles=len(obs), KS_observed=k_o, KS_random_mean=np.mean(pl_k), KS_random_p05=np.quantile(pl_k, .05), RMS_observed=r_o, RMS_random_mean=np.mean(pl_r), RMS_random_p05=np.quantile(pl_r, .05), p_value_regular=float(np.mean(np.array(pl_k) <= k_o))))
RG = pd.DataFrame(rows); RG.round(4).to_csv(f'{OUT}/bl_pc_reg.csv', index=False); print(RG.round(3).T.to_string()); R['rows'] = RG.round(4).to_dict('records'); rec('pc4', R)
