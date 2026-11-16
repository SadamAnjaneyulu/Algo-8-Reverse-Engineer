"""ALPHA-2: is the D-1 (1-DTE) ATM straddle carry a real premium in this sample? Market-level test independent of the algo:
sell the nearest-ATM straddle at each minute 09:16-15:00 and hold to the expiry close. Session-level mean, bootstrap CI, sign test,
leave-top-k-out, by index, by entry hour, and implied-vs-realized variance comparison.  python3 analysis/alpha_vrp.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy.stats import binomtest
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
settle = ix.groupby(['und', ix.ts.dt.normalize()]).close.last()
pc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).pivot_table(index=['und', 'expiry', 'm', 'strike'], columns='cp', values='c', aggfunc='last').dropna().reset_index()
ixc = ix.set_index(['und', 'ts']).close
pc['S1'] = [ixc.get((u, m - pd.Timedelta(minutes=1)), np.nan) for u, m in zip(pc.und, pc.m)]
pc['step'] = np.where(pc.und == 'NIFTY', 50, 100); pc = pc[pc.strike == (pc.S1 / pc.step).round() * pc.step]
pc = pc[(pc.m.dt.strftime('%H:%M') >= '09:16') & (pc.m.dt.strftime('%H:%M') <= '15:00')]
pc['ST'] = [settle.get((u, e), np.nan) for u, e in zip(pc.und, pc.expiry)]; pc = pc.dropna(subset=['ST'])
pc['date'] = pc.m.dt.normalize(); pc['dte'] = (pc.expiry - pc.date).dt.days
pc['carry_bp'] = (pc.CE + pc.PE - (pc.ST - pc.strike).abs()) / pc.ST * 1e4
pc['prem_bp'] = (pc.CE + pc.PE) / pc.S1 * 1e4; pc['move_bp'] = (pc.ST - pc.strike).abs() / pc.ST * 1e4
pc['grp'] = np.where(pc.dte >= 1, 'D-1 (carry overnight)', 'D0 (expiry day)')
pd.set_option('display.width', 220)
rng = np.random.default_rng(0)
for g, x in pc.groupby('grp'):
    s = x.groupby(['und', 'date']).agg(carry=('carry_bp', 'mean'), prem=('prem_bp', 'mean'), move=('move_bp', 'mean'))
    bs = [s.carry.sample(len(s), replace=True, random_state=i).mean() for i in range(4000)]
    srt = s.carry.sort_values(ascending=False)
    print(f'\n== {g}: sessions {len(s)} | mean carry {s.carry.mean():+.2f} bp of spot (premium {s.prem.mean():.1f} bp vs realised |move| {s.move.mean():.1f} bp)')
    print(f'   95% CI [{np.percentile(bs, 2.5):+.2f}, {np.percentile(bs, 97.5):+.2f}]  | sessions positive {int((s.carry > 0).sum())}/{len(s)}  sign-test p={binomtest(int((s.carry > 0).sum()), len(s)).pvalue:.3f}')
    print(f'   mean excluding best 1/2/3 sessions: {srt.iloc[1:].mean():+.2f} / {srt.iloc[2:].mean():+.2f} / {srt.iloc[3:].mean():+.2f} bp')
    print('   by index:', s.groupby(level='und').carry.agg(['size', 'mean']).round(2).to_dict('index'))
    print('   by entry hour (mean bp):', x.groupby(x.m.dt.hour).carry_bp.mean().round(1).to_dict())
# rupee scale: 1 bp of spot per NIFTY lot (65) ~ 0.0001*24000*65 = Rs 156; per SENSEX lot (20) ~ 0.0001*77000*20 = Rs 154
