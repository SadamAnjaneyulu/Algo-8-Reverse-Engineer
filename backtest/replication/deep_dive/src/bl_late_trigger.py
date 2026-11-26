"""Late D-1 ladder trigger: the engine's own ladder rule with its 60-minute 'new extreme' gate replaced by G minutes (G in 5,10,15,30,60; one parameter).
Decision-level score in the late window (14:15-15:29): predicted (minute, side) fires vs real (minute, side) sales, +-1 minute. G chosen leave-one-cycle-out by F1.
Output outputs/late/trigger_scores.csv, trigger_loco.csv."""
import sys, os, copy, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; LT = f'{OUT}/late'; O = DG.real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; GS = [5, 10, 15, 30, 60]; J0 = 300
rows = []
for r in T.itertuples():
    g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]
    if not len(g): continue
    c = S.load(r.und, r.expiry); s = c['spot1']; h, l, cl = (s[k].values.astype(float) for k in ('high', 'low', 'close')); vd1, _ = S.versions_for(r.d1, r.d0, 'B/V2'); cfg0 = S.d1_config(r.und, r.d1, vd1)
    ev = {'CE': [], 'PE': []}
    for sec in cfg0.timetable: j = A.minute_of(sec); ev['CE'].append(j); ev['PE'].append(j)
    for j, sd, dp in A.breakout_fires(h, l, cfg0): ev['CE'].append(j); ev['PE'].append(j)
    m = (g.t_last // 60 - 555); real = {(int(j), cp) for j, cp, ro in zip(m, g.cp, g.role) if ro == 'open_short' and J0 <= j <= 374}
    for G in GS:
        cfg = copy.copy(cfg0); cfg.ladder_gate_min = G; lad = A.ladder_fires(cl, h, l, ev, cfg); pred = {(j, cp) for j, cps in lad.items() if J0 <= j <= 374 for cp in cps}
        tp = sum(1 for (j, cp) in pred if any((j + d, cp) in real for d in (-1, 0, 1))); hit = sum(1 for (j, cp) in real if any((j + d, cp) in pred for d in (-1, 0, 1)))
        rows.append(dict(und=r.und, expiry=r.expiry, era='after' if r.d0 >= '2026-08-03' else 'before', G=G, pred=len(pred), real=len(real), tp=tp, hit=hit))
R = pd.DataFrame(rows); R.to_csv(f'{LT}/trigger_scores.csv', index=False)
def f1(x): p = x.tp.sum() / max(x.pred.sum(), 1); rc = x.hit.sum() / max(x.real.sum(), 1); return 2 * p * rc / (p + rc) if p + rc else 0.0, p, rc
print('in-sample by G and era (precision / recall / F1):')
for (era, G), x in R.groupby(['era', 'G']): F, p, rc = f1(x); print(f'  {era:6s} G={G:2d}: predicted {x.pred.sum():4d} real {x.real.sum():4d}  precision {p:.2f} recall {rc:.2f} F1 {F:.2f}')
R['cyc'] = R.und + R.expiry; L = []
for cy in R.cyc.unique():
    tr = R[R.cyc != cy]; Gb = max(GS, key=lambda G: f1(tr[tr.G == G])[0]); L.append(R[(R.cyc == cy) & (R.G == Gb)].assign(G_chosen=Gb))
L = pd.concat(L); L.to_csv(f'{LT}/trigger_loco.csv', index=False)
for era, x in L.groupby('era'): F, p, rc = f1(x); b = R[(R.era == era) & (R.G == 60)]; Fb, pb, rb = f1(b); print(f'LOCO {era}: G chosen {sorted(x.G_chosen.unique())} -> precision {p:.2f} recall {rc:.2f} F1 {F:.2f} | current G=60: precision {pb:.2f} recall {rb:.2f} F1 {Fb:.2f}')
