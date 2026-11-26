"""Verification checks requested in review (no new strategy rules): (1) the 3 Feb 2026 first print vs the first tradeable minute; how often the 09:15 print differs from the 09:16 open;
(2) what the 'Rs 7 lakh' on 3 Feb 2026 is: overnight mark-to-market of each variant's carried book vs the rest of the cycle; (3) settlement-averaging effect before / after the closing auction session (SEBI, effective 3 Aug 2026).
Output outputs/final/final_checks.json, final_e1_cas.csv."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); FI = f'{OUT}/final'; os.makedirs(FI, exist_ok=True); RES = f'{OUT}/bt3_results'; R = {}
G = pd.read_csv(f'{OUT}/unres/cycle_night_gaps.csv'); d = (G.gap_min_0915 - G.gap_min_0916).abs()
R['first_print_vs_0916_diff_over_0.5pct'] = int((d > 0.005).sum()); R['first_print_vs_0916_diff_over_1pct'] = int((d > 0.01).sum()); R['max_abs_gap_0916'] = float(G.gap_min_0916.abs().max())
c = pd.read_pickle(f'{OUT}/bt3/NIFTY_2026-02-03.pkl.gz'); s0 = c['spot0']; C1 = float(c['spot1'].close.iloc[374])
R['feb3'] = dict(d1_close_1529=C1, d0_0915_open=float(s0.open.iloc[0]), d0_0915_low=float(s0.low.iloc[0]), d0_0915_close=float(s0.close.iloc[0]), d0_0916_open=float(s0.open.iloc[1]), gap_first_print=float(np.log(s0.open.iloc[0] / C1)), gap_after_first_minute=float(np.log(s0.close.iloc[0] / C1)))
# (2) overnight mark of the carried book, full vs no D-1 longs
def book_value(F, o, j, field, U=65.0):
    v = 0.0; F = F.groupby(['cp', 'strike']).q.sum(); F = F[F != 0]
    for (cp, k), q in F.items():
        i = int(np.searchsorted(o['K'], k)); p = o[(cp, field)][i, j] if i < len(o['K']) and o['K'][i] == k else np.nan; v += q * U * (p if np.isfinite(p) else 0.0)
    return v
dec = {}
for v in ('full', 'd1_no_wings'):
    F = pd.read_csv(f'{RES}/ablate_{v}_fills.csv.gz'); F = F[(F.und == 'NIFTY') & (F.expiry == '2026-02-03')].copy(); F['q'] = F.side * F.lots; carried = F[F.day == 0]
    v_close = book_value(carried, c['opt1'], 374, 'close'); v_0916 = book_value(carried, c['opt0'], 1, 'open'); cyc = pd.read_csv(f'{RES}/ablate_{v}_cycles.csv').set_index(['und', 'expiry']).loc[('NIFTY', '2026-02-03')]
    short_lots = float(-carried.groupby(['cp', 'strike']).q.sum().clip(upper=0).sum()); long_lots = float(carried.groupby(['cp', 'strike']).q.sum().clip(lower=0).sum())
    dec[v] = dict(overnight_mtm=v_0916 - v_close, cycle_net=float(cyc.net), cycle_gross=float(cyc.gross), carried_short_lots=short_lots, carried_long_lots=long_lots)
R['feb3_decomposition'] = dec; R['feb3_overnight_difference'] = dec['full']['overnight_mtm'] - dec['d1_no_wings']['overnight_mtm']; R['feb3_net_difference'] = dec['full']['cycle_net'] - dec['d1_no_wings']['cycle_net']
# (3) settlement averaging by closing-auction regime
P = pd.read_csv(f'{OUT}/unres/prem_cycles.csv'); T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv')[['und', 'expiry', 'd0']]; P = P.merge(T0, on=['und', 'expiry']); P['regime'] = np.where(P.d0 >= '2026-08-03', 'after CAS (from 3 Aug 2026)', 'before CAS')
rows = []
for reg, g in P.groupby('regime'):
    rows.append(dict(regime=reg, cycles=len(g), var_ratio=float((g.x_settle ** 2).mean() / (g.x_print ** 2).mean()), extra_premium=float((g.pay_print - g.pay_settle).sum() / g.prem_1500.sum()), median_abs_settle_minus_print_bp=float(g.gap_settle_print_bp.abs().median())))
pre26 = P[(P.d0 >= '2026-01-01') & (P.d0 < '2026-08-03')]; rows.append(dict(regime='2026 before CAS (Jan - 2 Aug)', cycles=len(pre26), var_ratio=float((pre26.x_settle ** 2).mean() / (pre26.x_print ** 2).mean()), extra_premium=float((pre26.pay_print - pre26.pay_settle).sum() / pre26.prem_1500.sum()), median_abs_settle_minus_print_bp=float(pre26.gap_settle_print_bp.abs().median())))
E = pd.DataFrame(rows); rng = np.random.default_rng(20261124)
for i, r in E.iterrows():
    g = P[P.regime == r.regime] if r.regime in set(P.regime) else pre26; bs = [((x.x_settle ** 2).mean() / (x.x_print ** 2).mean()) for x in (g.sample(len(g), replace=True, random_state=int(rng.integers(1e9))) for _ in range(2000))]; E.loc[i, 'var_ratio_lo'] = np.quantile(bs, .025); E.loc[i, 'var_ratio_hi'] = np.quantile(bs, .975)
E.to_csv(f'{FI}/final_e1_cas.csv', index=False); R['e1_by_cas'] = E.to_dict('records')
json.dump(R, open(f'{FI}/final_checks.json', 'w'), indent=1, default=float); print(json.dumps(R, indent=1, default=float)[:3500])
