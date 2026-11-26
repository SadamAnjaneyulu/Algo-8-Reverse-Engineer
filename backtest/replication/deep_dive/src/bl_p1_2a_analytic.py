"""P1-2A-0: analytical tests T1-T3 of reports/PHASE1_GATE2A_PLAN.md on the existing body-sell ledger. No engine change, no fitting."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import spearmanr
import bl_common, bl_ohlc
OUT = bl_common.OUT; LR = pd.read_csv(f'{OUT}/bodysell/ledger_real.csv'); OH = bl_ohlc.load(); STEP = {'NIFTY': 50.0, 'SENSEX': 100.0}; res = {}
LR['und'] = LR.cyc.str.split('|').str[0]; LR['expiry'] = LR.cyc.str.split('|').str[1]; LR['trig'] = LR.und.map(STEP) * 0.2
solo = LR[LR.inferred_module == 'solo'].sort_values(['cyc', 'cp', 't']).copy(); res['n_real_solo_labelled'] = int(len(solo))
# minute-close spot of the previous completed minute (convention-free)
def prev_close(r):
    o = OH[(r.und, r.expiry)]; j = int(r.minute); return float(o.close.values[j - 1]) if 0 < j <= len(o) else np.nan
solo['pc'] = solo.apply(prev_close, axis=1)
# ---- T1: spacing of consecutive same-type solo sells in DIFFERENT seconds within 60 s
solo['gap'] = solo.groupby(['cyc', 'cp']).t.diff(); solo['d_replay'] = solo.groupby(['cyc', 'cp']).eng_spot.diff().abs() / solo.trig; solo['d_close'] = solo.groupby(['cyc', 'cp']).pc.diff().abs() / solo.trig; solo['dmin'] = solo.groupby(['cyc', 'cp']).minute.diff()
a = solo[(solo.gap > 0) & (solo.gap <= 60)]; b = a[a.dmin > 0]
q = lambda s: {k: round(float(v), 3) for k, v in s.quantile([.1, .25, .5, .75, .9]).items()}
res['T1'] = dict(distinct_second_pairs_within_60s=int(len(a)), replay_spot_units_of_trigger=q(a.d_replay), pairs_in_different_minutes=int(len(b)), minute_close_units_of_trigger=q(b.d_close.dropna()), same_second_pairs=int((solo.gap == 0).sum()),
                 note='replay spot uses the intrabar path convention; minute-close uses only completed-minute closes (pairs in different minutes only)')
# ---- T2: same-second group size vs rungs crossed since the previous same-type group
g = solo.groupby(['cyc', 'cp', 't']).agg(k=('t', 'size'), spot=('eng_spot', 'first'), trig=('trig', 'first')).reset_index().sort_values(['cyc', 'cp', 't'])
g['dt'] = g.groupby(['cyc', 'cp']).t.diff(); g['rungs'] = g.groupby(['cyc', 'cp']).spot.diff().abs() / g.trig; h = g[(g.dt > 0) & (g.dt <= 300)].dropna(subset=['rungs'])
rho, p = spearmanr(h.k, h.rungs); res['T2'] = dict(groups=int(len(g)), groups_k_ge_2=int((g.k >= 2).sum()), pairs_used=int(len(h)), spearman_k_vs_rungs=round(float(rho), 3), p=float(p), mean_rungs_by_k={int(k): round(float(v), 2) for k, v in h.groupby(h.k.clip(upper=5)).rungs.mean().items()}, count_by_k={int(k): int(v) for k, v in h.groupby(h.k.clip(upper=5)).size().items()})
# ---- T3: new N-minute extreme in minutes with a real solo sell vs base rate
rows = []
for (cyc, cp), z in solo.groupby(['cyc', 'cp']):
    o = OH[(z.und.iloc[0], z.expiry.iloc[0])]; hi = o.high.values; lo = o.low.values; mins = set(z.minute.astype(int))
    for N in (5, 15, 30, 60):
        js = range(N, len(o)); f = np.array([(lo[j] < lo[j - N:j].min()) if cp == 'CE' else (hi[j] > hi[j - N:j].max()) for j in js]); sel = np.array([j in mins for j in js])
        rows.append(dict(cyc=cyc, cp=cp, N=N, sell_minutes=int(sel.sum()), sell_with_extreme=int((f & sel).sum()), minutes=int(len(f)), minutes_with_extreme=int(f.sum())))
t3 = pd.DataFrame(rows).groupby('N').sum(numeric_only=True); t3['share_sell_minutes'] = t3.sell_with_extreme / t3.sell_minutes; t3['base_rate'] = t3.minutes_with_extreme / t3.minutes; t3['lift'] = t3.share_sell_minutes / t3.base_rate
res['T3'] = t3.round(4).reset_index().to_dict('records')
json.dump(res, open(f'{OUT}/phase1/2A/T1_T3_analytic.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
