"""Per-cycle table for reports/LATE_SALE_RISK.md (one row per complete cycle) -> outputs/risk/per_cycle_table.csv and per_cycle_table.md"""
import os, numpy as np, pandas as pd
RK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs', 'risk')
A = pd.read_csv(f'{RK}/attrib_cycles.csv'); C = pd.read_csv(f'{RK}/cycle_risk.csv'); O = pd.read_csv(f'{RK}/orders_risk.csv'); D = pd.read_csv(f'{RK}/cycle_diagnosis.csv')
late = O[O.j >= 360].groupby(['und', 'd1']).agg(n=('cp', 'size'), ce=('cp', lambda s: int((s == 'CE').sum())), pe=('cp', lambda s: int((s == 'PE').sum()))).reset_index()
T = A.merge(C[['und', 'd1', 'delta_ratio_1415', 'delta_ratio_end', 'late_orders']], on=['und', 'd1']).merge(late, on=['und', 'd1'], how='left'); T['n'] = T.n.fillna(0).astype(int); T['ce'] = T.ce.fillna(0).astype(int); T['pe'] = T.pe.fillna(0).astype(int)
P = O[(O.j >= 360) & (O.outlier == 0)].copy(); P['cyc'] = P.und + '|' + P.d1; P['own'] = P.groupby('cyc').cp.transform(lambda x: x.map(x.value_counts(normalize=True)))
P['h1_a'] = (P.delta_rs_pct_a.abs() < P.delta_rs_pct_b.abs()).astype(float); P['h1_m'] = (P.delta_rs_pct_m.abs() < P.delta_rs_pct_b.abs()).astype(float); P['h2_a'] = (P.asym_a.abs() < P.asym_b.abs()).astype(float); P['h2_m'] = (P.asym_m.abs() < P.asym_b.abs()).astype(float)
P['h3_a'] = ((P.gap_worst_a - P.gap_worst_b) > (P.gap_worst_m - P.gap_worst_b)).astype(float); P['h3_m'] = 1 - P.h3_a; bd = P.SC - P.SP; sg = np.where(P.cp == 'CE', 1.0, -1.0); P['h7_a'] = ((bd + sg * P.lots).abs() < bd.abs()).astype(float); P['h7_m'] = ((bd - sg * P.lots).abs() < bd.abs()).astype(float)
rows = []
for c, g in P.groupby('cyc'):
    if len(g) < 3: continue
    d = {nm: (float(g[f'{nm}_a'].mean()), float((g[f'{nm}_a'] - (g.own * g[f'{nm}_a'] + (1 - g.own) * g[f'{nm}_m'])).mean())) for nm in ('h1', 'h2', 'h3', 'h7')}
    ok = [nm.upper() for nm in d if d[nm][0] >= 0.70 and d[nm][1] >= 0.25]; und, d1 = c.split('|'); rows.append(dict(und=und, d1=d1, h1_rate=d['h1'][0], h1_excess=d['h1'][1], label='+'.join(ok) if ok else 'unexplained by book or VWAP state'))
D2 = pd.DataFrame(rows); T = T.merge(D2, on=['und', 'd1'], how='left')
def best(r):
    g = {k: r[f'd_absdelta_{k}'] for k in ('late_shorts_1515+', 'mid_shorts_1415-1514', 'lump_v_', 'wings_h_', 'covers_stops') if r[f'lots_{k}'] > 0}
    return max(g, key=g.get) if g else '-'
T['biggest_delta_reducer'] = T.apply(best, axis=1)
def lab(r):
    if r.outlier: return 'outlier (240-lot call ratio), excluded'
    if r.n == 0: return 'no sales after 15:15'
    if r.n < 3: return 'too few sales (<3)'
    return 'unexplained by book or VWAP state' if pd.isna(r.label) or r.label.startswith('unexplained') else r.label
T['verdict'] = T.apply(lab, axis=1); T['late_effect_absdelta_k'] = np.where(T.n > 0, T['d_absdelta_late_shorts_1515+'] / 1e3, np.nan); T['late_effect_gap_lakh'] = np.where(T.n > 0, T['d_gap_late_shorts_1515+'] / 1e5, np.nan); T['lump_effect_absdelta_k'] = T['d_absdelta_lump_v_'] / 1e3; T['lump_effect_gap_lakh'] = T['d_gap_lump_v_'] / 1e5      # positive = the group reduces |delta| / reduces the worst gap loss
T = T.sort_values(['d1', 'und']).reset_index(drop=True); T.to_csv(f'{RK}/per_cycle_table.csv', index=False)
f = lambda x, d=1: '' if pd.isna(x) else f'{x:+.{d}f}'
L = ['| cycle (D-1) | era | sales ≥15:15 (CE/PE) | delta ratio 14:15 → close | late sales **reduce** \\|delta\\| by (₹k per 1%) | late sales **improve** worst gap by (₹ lakh) | lump reduces \\|delta\\| by (₹k per 1%) | lump improves worst gap by (₹ lakh) | biggest delta reducer | verdict |', '|---|---|---|---|---|---|---|---|---|---|']
for r in T.itertuples():
    L.append(f"| {r.und[:3]} {r.d1[5:]} | {'post' if r.era == 'after' else 'pre'} | {r.n} ({r.ce}/{r.pe}) | {r.delta_ratio_1415:.2f} → {r.delta_ratio_end:.2f} | {f(r.late_effect_absdelta_k)} | {f(r.late_effect_gap_lakh, 2)} | {f(r.lump_effect_absdelta_k)} | {f(r.lump_effect_gap_lakh, 2)} | {r.biggest_delta_reducer} | {r.verdict} |")
open(f'{RK}/per_cycle_table.md', 'w').write('\n'.join(L) + '\n'); print(len(T), 'cycles'); print(T.verdict.value_counts().to_string()); print(T.biggest_delta_reducer.value_counts().to_string())
