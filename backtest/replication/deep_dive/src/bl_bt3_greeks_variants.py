"""Greek decomposition of every saved ablation variant (plan reports/ALPHA_SOURCE_PLAN.md): which physical component does each rule add or remove? Trading-minute clock.
Output outputs/bt3_results/greeks_variants_cycles.csv and greeks_variants_diffs.csv"""
import sys, os, warnings, time; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_greeks as G
from multiprocessing import Pool
G.CLOCK = 'trading'; RES = G.RES; OUT = G.OUT; REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}; rng = np.random.default_rng(11)
NAMES = ['full', 'd1_no_ladder', 'd0_no_ladder', 'd0_no_waves', 'd1_no_timetable', 'P1_flip_ladder_direction', 'd0_no_new_sells', 'd1_no_wings', 'no_cycle_stop', 'd0_no_stop_tp', 'd1_no_stops', 'd0_no_counter', 'd0_no_hedge', 'd1_no_lump']
T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]
if __name__ == '__main__':
    t0 = time.time(); out = []
    with Pool(4) as p:
        for nm in NAMES:
            F = pd.read_csv(f'{RES}/ablate_{nm}_fills.csv.gz'); Gp = {k: v for k, v in F.groupby(['und', 'expiry'])}
            jobs = [(r.und, r.expiry, r.d1, r.d0, float(r.unit), r.split3, nm, Gp[(r.und, r.expiry)]) for r in T0.itertuples() if (r.und, r.expiry) in Gp]; res = p.map(G.one, jobs, chunksize=2)
            comp = pd.DataFrame([r for rs, _ in res for r in rs]).groupby(['und', 'expiry'])[['delta', 'gamma', 'theta', 'vega', 'resid']].sum().reset_index(); rec = pd.DataFrame([i for _, i in res])[['und', 'expiry', 'split', 'gross', 'execution', 'premium_sold']]
            d = comp.merge(rec, on=['und', 'expiry']); d['variant'] = nm; out.append(d); print(nm, round(time.time() - t0), 's', flush=True)
    A = pd.concat(out, ignore_index=True); T0['k'] = T0.und.map(REFU) / T0.unit; A = A.merge(T0[['und', 'expiry', 'k', 'd0']], on=['und', 'expiry'])
    for c in ('delta', 'gamma', 'theta', 'vega', 'resid', 'execution', 'gross', 'premium_sold'): A[c + '_k'] = A[c] * A.k
    A['wk'] = pd.to_datetime(A.d0).dt.strftime('%G-%V'); A.to_csv(f'{RES}/greeks_variants_cycles.csv', index=False)
    base = A[A.variant == 'full'].sort_values(['und', 'expiry']).reset_index(drop=True); comps = ['delta_k', 'gamma_k', 'theta_k', 'vega_k', 'resid_k', 'execution_k', 'gross_k']; rows = []
    for nm in NAMES[1:]:
        v = A[A.variant == nm].sort_values(['und', 'expiry']).reset_index(drop=True); assert (v.expiry.values == base.expiry.values).all(); row = dict(variant=nm); u = np.unique(base.wk); idx = {w: np.where(base.wk.values == w)[0] for w in u}
        for c in comps:
            dlt = (v[c] - base[c]).values; b = [dlt[np.concatenate([idx[w] for w in rng.choice(u, len(u))])].mean() for _ in range(1000)]; row[c.replace('_k', '') + '_diff'] = float(dlt.mean()); row[c.replace('_k', '') + '_lo'] = float(np.quantile(b, .025)); row[c.replace('_k', '') + '_hi'] = float(np.quantile(b, .975))
        rows.append(row)
    DF = pd.DataFrame(rows); DF.round(0).to_csv(f'{RES}/greeks_variants_diffs.csv', index=False); full = base[comps].mean().round(0); print('FULL strategy mean per cycle (constant lot size, Rs):'); print(full.to_string()); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    print('variant minus full (Rs per cycle): [what the REMOVED/BROKEN rule contributed is minus this]'); print(DF[['variant', 'delta_diff', 'gamma_diff', 'theta_diff', 'vega_diff', 'resid_diff', 'execution_diff', 'gross_diff', 'gross_lo', 'gross_hi']].round(0).to_string(index=False))
