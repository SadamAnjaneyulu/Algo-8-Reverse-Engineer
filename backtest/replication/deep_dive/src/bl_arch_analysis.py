"""Question B statistics (plan reports/PREMIUM_AND_ARCHITECTURE_PLAN.md): per variant and price-scan range, margin, capital feasibility (Rs 2 crore), return on peak margin
(paired vs full, week-cluster bootstrap), realised tails and overnight gap stress. Output outputs/arch/arch_stats.csv, arch_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); AR = f'{OUT}/arch'; RES = f'{OUT}/bt3_results'; REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}; B = 2000; CAP = 2e7
A = pd.read_csv(f'{AR}/arch_cycles.csv'); G = pd.read_csv(f'{AR}/arch_gap.csv'); V = ['full', 'd1_no_wings', 'd1_no_lump', 'd0_no_hedge', 'd1_no_stops', 'd0_no_stop_tp', 'no_cycle_stop']
def net(v):
    d = pd.read_csv(f'{RES}/ablate_{v}_cycles.csv'); d = d[d.ok]; k = d.und.map(REFU) / d.unit; return d.assign(net_k=d.net * k, variant=v)[['und', 'expiry', 'd0', 'variant', 'net_k']]
N = pd.concat([net(v) for v in V]); D = A.merge(N, on=['und', 'expiry', 'variant']); D['wk'] = pd.to_datetime(D.d0).dt.strftime('%G-%V')
rows = []
for (p, vs), g in D.groupby(['psr', 'vsr']):
    W = g.pivot_table(index=['und', 'expiry', 'wk'], columns='variant', values=['net_k', 'peak_margin', 'margin_d1_close']).dropna(); W.columns = [f'{a}|{b}' for a, b in W.columns]; W = W.reset_index()
    wk = W.wk.unique(); gr = {k: x for k, x in W.groupby('wk')}; rng = np.random.default_rng(20261124); draws = [pd.concat([gr[k] for k in rng.choice(wk, len(wk))]) for _ in range(B)]
    rom = lambda x, v: x[f'net_k|{v}'].sum() / x[f'peak_margin|{v}'].sum()
    for v in V:
        r = dict(psr=p, vsr=vs, variant=v, cycles=len(W), median_peak_margin=W[f'peak_margin|{v}'].median(), p90_peak_margin=W[f'peak_margin|{v}'].quantile(.9), share_peak_over_2cr=(W[f'peak_margin|{v}'] > CAP).mean(),
                 median_margin_d1_close=W[f'margin_d1_close|{v}'].median(), net_per_cycle=W[f'net_k|{v}'].mean(), return_on_peak_margin=rom(W, v),
                 worst_over_median_margin=W[f'net_k|{v}'].min() / W[f'peak_margin|{v}'].median(), p5_over_median_margin=W[f'net_k|{v}'].quantile(.05) / W[f'peak_margin|{v}'].median())
        if v != 'full':
            bs = np.array([rom(x, v) - rom(x, 'full') for x in draws]); r.update(rom_diff_vs_full=rom(W, v) - rom(W, 'full'), rom_diff_lo=np.quantile(bs, .025), rom_diff_hi=np.quantile(bs, .975))
            bm = np.array([(x[f'margin_d1_close|{v}'] / x['margin_d1_close|full']).median() for x in draws[:500]]); r.update(d1_close_margin_ratio=(W[f'margin_d1_close|{v}'] / W['margin_d1_close|full']).median(), d1_close_ratio_lo=np.quantile(bm, .025), d1_close_ratio_hi=np.quantile(bm, .975))
        rows.append(r)
S = pd.DataFrame(rows); S.to_csv(f'{AR}/arch_stats.csv', index=False)
gs = G.groupby(['variant', 'gap', 'vol_mult']).loss.agg(p95='quantile', worst='max').reset_index() if False else G.groupby(['variant', 'gap', 'vol_mult']).loss.agg([('p95', lambda x: x.quantile(.95)), ('worst', 'max'), ('mean', 'mean')]).reset_index(); gs.to_csv(f'{AR}/arch_gap_stats.csv', index=False)
pc = pd.read_csv(f'{OUT}/premium/premium_cycles.csv'); gaps = np.sqrt(pc.gap2) * 100; obs = dict(max_abs_gap_pct=float(gaps.max()), p99_abs_gap_pct=float(gaps.quantile(.99)), n_over_2pct=int((gaps > 2).sum()), n_over_1pct=int((gaps > 1).sum()), cycles=len(gaps))
summ = dict(observed_gaps=obs); json.dump(summ, open(f'{AR}/arch_summary.json', 'w'), indent=1)
pd.set_option('display.width', 260); pd.set_option('display.max_columns', 30)
print(obs); print(S[S.vsr == 0.04].round(3).to_string()); print(S[S.vsr != 0.04][['psr', 'vsr', 'variant', 'rom_diff_vs_full', 'rom_diff_lo', 'rom_diff_hi', 'share_peak_over_2cr']].round(4).to_string())
print(gs[gs.vol_mult == 1.25].pivot_table(index='gap', columns='variant', values='p95').round(-3).to_string())
