"""Post-auction rebuild, validation (reports/POSTCAS_REBUILD_PLAN.md): old (cycle stop Rs 1.2 lakh) vs rebuilt (Rs 1.45 lakh) simulator against the real log,
groups: pre-auction live cycles, development (D0 3 Aug - 15 Sep 2026), validation (D0 16 Sep - 22 Oct 2026). Output outputs/postcas/eval.csv, eval_cycles.csv, eval_decision.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); PC = f'{OUT}/postcas'; ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(OUT))))
real = pd.read_csv(f'{PC}/diag_cycles.csv'); real = real[real.src == 'real'][['und', 'expiry', 'total']].rename(columns={'total': 'real'})
ctl = pd.read_csv(f'{ROOT}/risk_rule_validation/results/cycle_stop_control.csv')[['und', 'expiry', 'stop']].rename(columns={'stop': 'real_stop'})
old = pd.read_csv(f'{OUT}/prepaper/var_full.csv')[['und', 'expiry', 'd0', 'gross', 'stop_j']].rename(columns={'gross': 'old', 'stop_j': 'old_stop_j'})
new = pd.read_csv(f'{OUT}/prepaper_v2/var_full.csv')[['und', 'expiry', 'gross', 'stop_j']].rename(columns={'gross': 'new', 'stop_j': 'new_stop_j'})
M = real.merge(ctl, on=['und', 'expiry']).merge(old, on=['und', 'expiry']).merge(new, on=['und', 'expiry'])
M['group'] = np.where(M.d0 < '2026-08-03', 'pre-auction live', np.where(M.d0 <= '2026-09-15', 'development', 'validation')); M.to_csv(f'{PC}/eval_cycles.csv', index=False); rows = []
for g, x in M.groupby('group'):
    for v in ('old', 'new'):
        st = x[f'{v}_stop_j'].notna()
        rows.append(dict(group=g, sim=v, cycles=len(x), real_mean=x.real.mean(), sim_mean=x[v].mean(), mae=float((x[v] - x.real).abs().mean()), spearman=float(x[[v, 'real']].corr('spearman').iloc[0, 1]),
                         stops_agree=int((st == x.real_stop).sum()), sim_only_stops=int((st & ~x.real_stop).sum()), real_only_stops=int((~st & x.real_stop).sum())))
E = pd.DataFrame(rows); E.to_csv(f'{PC}/eval.csv', index=False)
v = E[E.group == 'validation'].set_index('sim'); p = E[E.group == 'pre-auction live'].set_index('sim')
dec = dict(val_mae_old=float(v.loc['old', 'mae']), val_mae_new=float(v.loc['new', 'mae']), val_agree_old=int(v.loc['old', 'stops_agree']), val_agree_new=int(v.loc['new', 'stops_agree']), pre_mae_old=float(p.loc['old', 'mae']), pre_mae_new=float(p.loc['new', 'mae']))
dec['accept'] = bool(dec['val_mae_new'] < dec['val_mae_old'] and dec['val_agree_new'] >= dec['val_agree_old'] and dec['pre_mae_new'] <= 1.10 * dec['pre_mae_old'])
json.dump(dec, open(f'{PC}/eval_decision.json', 'w'), indent=1); pd.set_option('display.width', 220); print(E.round(2).to_string()); print(dec)
