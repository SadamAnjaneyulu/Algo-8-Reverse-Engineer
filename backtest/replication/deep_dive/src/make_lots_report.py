"""Builds reports/D1_LOTS.md and figures/bl_lots_summary.png from bl_err_budget*, bl_qty_events, bl_solo_minute, bl_lots_fit*, bl_summary_lf1.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports')
def table(df):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(str(x) for x in r) + ' |\n'
    return s
E_ = pd.read_pickle(f'{OUT}/bl_err_lots.pkl.gz'); Q = pd.read_csv(f'{OUT}/bl_qty_events.csv'); SM = pd.read_csv(f'{OUT}/bl_solo_minute.csv'); F = pd.read_csv(f'{OUT}/bl_lots_fit.csv'); C = pd.read_csv(f'{OUT}/bl_lots_classes.csv'); LF = json.load(open(f'{OUT}/bl_summary_lf1.json'))
real = E_[E_.side == 'real']; sim = E_[E_.side == 'sim']
bud = real[real.cause != 'matched'].cause.value_counts(); bud_t = pd.DataFrame({'cause': bud.index, 'real lots not reproduced': bud.values, 'share': (bud.values / bud.sum() * 100).round(0).astype(int).astype(str) + '%'})
sb = sim[sim.cause != 'matched'].cause.value_counts(); sb_t = pd.DataFrame({'cause': sb.index, 'simulated lots not real': sb.values})
bc = E_[E_.cause != 'matched'].groupby(['cls', 'cause']).size().unstack(fill_value=0).reset_index()
both = Q[(Q.real > 0) & (Q.sim > 0)].assign(diff=lambda d: d.real - d.sim); qe = both.groupby('real_main').agg(cells=('diff', 'size'), real_lots_mean=('real', 'mean'), sim_lots_mean=('sim', 'mean'), lots_short=('diff', lambda d: int(d.clip(lower=0).sum())), lots_extra=('diff', lambda d: int((-d).clip(lower=0).sum()))).round(2).reset_index()
sm = SM[SM.late == 0].groupby(pd.cut(SM[SM.late == 0].depth60, [-9, 0, 0.1, 0.2, 0.4, 0.7, 1, 9]), observed=True).lots.agg(['mean', 'size']).round(2).reset_index(); sm.columns = ['depth beyond 60-min extreme (steps)', 'real solo lots per minute', 'minutes']; sm.iloc[:, 0] = sm.iloc[:, 0].astype(str)
ft = F.copy(); ft = ft.round(3)
ch = pd.DataFrame([c for v in LF['chosen'].values() for c in v])
g = lambda s_, m: F[(F.setup == s_) & (F.model == m)].F1.iloc[0]
setups = list(dict.fromkeys(F.setup))
cl = C.pivot_table(index='cls', columns=['setup', 'model'], values='F1').round(3)
fig, ax = plt.subplots(1, 3, figsize=(17, 4.8))
ax[0].barh(range(len(bud))[::-1], bud.values, color='#dd6b20'); ax[0].set_yticks(range(len(bud))[::-1]); ax[0].set_yticklabels(bud.index); ax[0].set_xlabel('real D-1 lots not reproduced'); ax[0].set_title('(a) Error budget (free-running, out-of-fold)')
ax[1].bar(range(len(sm)), sm.iloc[:, 1], color='#2b6cb0'); ax[1].set_xticks(range(len(sm))); ax[1].set_xticklabels(sm.iloc[:, 0].str.replace('(', '').str.replace(']', ''), rotation=30, fontsize=8); ax[1].set_ylabel('real solo lots per minute'); ax[1].set_xlabel('depth beyond the 60-min extreme (steps)'); ax[1].set_title('(b) Solo lots grow with break depth')
x = np.arange(len(setups)); ax[2].bar(x - .2, [g(s_, 'baseline') for s_ in setups], .4, color='#a0aec0', label='before'); ax[2].bar(x + .2, [g(s_, 'fixed') for s_ in setups], .4, color='#2b6cb0', label='with lot fixes')
for k, s_ in enumerate(setups): ax[2].text(k + .2, g(s_, 'fixed') + .01, f"{g(s_, 'fixed'):.3f}", ha='center', fontsize=8); ax[2].text(k - .2, g(s_, 'baseline') + .01, f"{g(s_, 'baseline'):.3f}", ha='center', fontsize=8)
ax[2].set_xticks(x); ax[2].set_xticklabels([s_.split(' (')[0].replace('out-of-fold halves', 'out-of-fold').replace('A same version', 'unseen: same version').replace('B version change', 'unseen: version change') for s_ in setups], fontsize=8); ax[2].set_ylim(0, 1); ax[2].set_ylabel('overall D-1 lot F1'); ax[2].legend(); ax[2].set_title('(c) Lot-level accuracy before vs after')
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_lots_summary.png'), dpi=130)
txt = f"""# Algo 8 — D-1 lot construction: why lot accuracy lags activity accuracy, and fixes

*Plan `D1_LOTS_PLAN.md`, written before the analysis. In-sample, D-1 of 32 cycles. Fixes are validated out-of-fold **and** on unseen cycles (forward splits of `D1_FORWARD.md`). Figure: `figures/bl_lots_summary.png`.*

## 0. Result
* **Why lots lag activity.** Of the real lots not reproduced, **{bud.get('quantity shortfall', 0) / bud.sum():.0%} are a quantity shortfall**: the right minute and right side, but too few lots. Then come missed events ({bud.get('missed event', 0) / bud.sum():.0%}), timing 2–5 minutes off ({bud.get('timing (2-5 min)', 0) / bud.sum():.0%}) and classes not modelled ({bud.get('not modelled', 0) / bud.sum():.0%}).
* **Main source of the shortfall: solo sells.** In minutes where the real system's main sell is solo, it places {qe[qe.real_main == 'solo'].real_lots_mean.iloc[0]:.1f} lots against {qe[qe.real_main == 'solo'].sim_lots_mean.iloc[0]:.1f} simulated. The wing buys inherit the same shortfall, because the hedge buys the gap.
* **Mechanism found:** solo lots per minute grow with the **depth of the break beyond the 60-minute extreme**: about 1.3 lots when barely beyond it, 2.3 at 0.2–0.4 steps, 6.6 at 0.7–1 step. This is the same depth-scaling as the reactive extras. The "one lot per 0.2-step rung" idea was rejected (ρ 0.06).
* **After the fixes** (solo depth sizing, late-solo rule, opposite-right counter-sell, chosen on training cycles only):
""" + '\n'.join(f"  * {s_}: overall F1 {g(s_, 'baseline'):.3f} → **{g(s_, 'fixed'):.3f}** ({g(s_, 'fixed') - g(s_, 'baseline'):+.3f})." for s_ in setups) + f"""

## 1. Error budget (current reconstruction, out-of-fold)
{table(bud_t)}
{table(sb_t)}

By class (unmatched lots):
{table(bc)}

## 2. Quantity at events found (same minute, body sells)
{table(qe)}

## 3. Solo lots per minute vs break depth (real, intraday, stand-alone)
{table(sm)}

## 4. Fixes: chosen settings and scores
{table(ch)}

{table(ft)}

By class:
{table(cl.reset_index())}

## 5. What remains, and why
* **Missed events:** mostly buy-backs whose exact trigger is not recoverable at minute resolution (see `BUYBACK_STOP3.md`), plus solo minutes the ladder misses.
* **Timing:** lump orders spread over an 8-minute window in the early regime, and solo drips span neighbouring minutes.
* **Not modelled (3%):** stop module, 15:15 flatten, deep-OTM batches.

## Evidence labels
Observed (executed). Fixes chosen on training cycles and scored on held-out and unseen cycles. In-sample caveat: the mechanisms were found on the same 32 cycles.
"""
open(f'{RP}/D1_LOTS.md', 'w').write(txt); print('ok')
