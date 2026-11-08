"""B2d: mechanical explanations for the two indicator 'signals'.  python3 analysis/b2_mechanism_checks.py
(1) D3: strike = argmin |CE - PE| over listed strikes (prev-minute option closes) vs index-nearest, by clock.
(2) D7: does wick/close-at-crossing absorb the trend-family gain for leg-stop execution?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import b2_indicator_tests as B
C = B.C
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
pcm = op.assign(m=op.ts + pd.Timedelta(minutes=1)).pivot_table(index=['und', 'expiry', 'm', 'strike'], columns='cp', values='c', aggfunc='last')
f = pd.read_pickle(os.path.join(C, 'p4_orders_cons.pkl'))
sec = (f.t - f.t.dt.normalize() - pd.Timedelta('09:15:00')).dt.total_seconds(); ph = sec % 900
f['clock'] = np.where((ph >= 55) & (ph < 180), 'A', np.where((ph >= 13 * 60 + 45) | (ph < 15), 'B', np.where(ph < 55, 'A0', 'unchained')))
pred = []
for r in f.itertuples():
    try: g = pcm.loc[(r.und, r.expiry, r.m)].dropna()
    except KeyError: pred.append(np.nan); continue
    g = g[(g.index >= r.prev_close - 4 * r.step) & (g.index <= r.prev_close + 4 * r.step)]
    pred.append((g.CE - g.PE).abs().idxmin() if len(g) else np.nan)
f['K_parity'] = pred; f['K_index'] = (f.prev_close / f.step).round() * f.step
v = f.dropna(subset=['K_parity'])
print('(1) strike rule accuracy by clock: index-nearest vs min|CE-PE| (traded-strike universe)')
print(v.groupby(['day', 'clock']).apply(lambda x: pd.Series({'n': len(x), 'index_nearest': (x.strike == x.K_index).mean(), 'min_CE_PE': (x.strike == x.K_parity).mean(),
      'either': ((x.strike == x.K_index) | (x.strike == x.K_parity)).mean()}), include_groups=False).round(3).to_string())
# (2) D7
D = B.datasets(); df, base, price, side = D['D7 leg stop executed vs survived']; df = df.dropna(subset=['label']).reset_index(drop=True)
o2 = op.set_index(['und', 'expiry', 'cp', 'strike', 'ts']).sort_index()
k = df.ks.str.split('|', expand=True); df['und_'] = k[0]; df['exp_'] = pd.to_datetime(k[1]); df['cp_'] = k[2]; df['K_'] = k[3].astype(int)
cl, hi = [], []
for r in df.itertuples():
    try: b = o2.loc[(r.und_, r.exp_, r.cp_, r.K_, r.m)]; cl.append(b.c); hi.append(b.h)
    except KeyError: cl.append(np.nan); hi.append(np.nan)
df['close_ratio'] = np.array(cl) / df.entry_px; df['high_ratio'] = np.array(hi) / df.entry_px; df['wick'] = df.high_ratio - df.close_ratio
df['close_above'] = (df.close_ratio >= 1.55).astype(int)
mech = ['close_ratio', 'high_ratio', 'wick', 'close_above']
dates = pd.to_datetime(df.date); y = df.label.astype(int)
real = B.attach(df, side); trend = [c for c in B.IND_COLS if any(t in c for t in ['ema', 'sma', 'macd', 'supertrend', 'adx', 'di_diff'])]
a0 = B.oos_auc(df[base].astype(float), y, dates)
a1 = B.oos_auc(pd.concat([df[base].astype(float), real[trend]], axis=1), y, dates)
a2 = B.oos_auc(df[base + mech].astype(float), y, dates)
a3 = B.oos_auc(pd.concat([df[base + mech].astype(float), real[trend]], axis=1), y, dates)
print(f'\n(2) D7 leg-stop executed: base {a0:.3f} | +trend {a1:.3f} | +crossing-bar mechanics {a2:.3f} | +mechanics+trend {a3:.3f}')
print('   stop rate when crossing-minute CLOSE >= 1.55x entry:', round(df[df.close_above == 1].label.mean(), 3), ' when only the HIGH crossed:', round(df[df.close_above == 0].label.mean(), 3))

# (3) D7: is the "trend" gain just spot displacement since the lot's entry (spot-based stop)?
ixs = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')).set_index(['und', 'ts']).close.sort_index()
ent_m = pd.to_datetime(df.date) + pd.Timedelta('09:16:00') + pd.to_timedelta(df.entry_min, unit='min')
S_e = np.array([ixs.get((u, m - pd.Timedelta(minutes=1)), np.nan) for u, m in zip(df.und_, ent_m)])
S_c = np.array([ixs.get((u, m - pd.Timedelta(minutes=1)), np.nan) for u, m in zip(df.und_, df.m)])
sg = np.where(df.cp_ == 'CE', 1, -1)
df['adv_since_entry_bp'] = (S_c - S_e) / S_e * 1e4 * sg
df['adv_since_entry_steps'] = (S_c - S_e) / np.where(df.und_ == 'NIFTY', 50, 100) * sg
spot = ['adv_since_entry_bp', 'adv_since_entry_steps']
a4 = B.oos_auc(df[base + mech + spot].astype(float), y, dates)
a5 = B.oos_auc(pd.concat([df[base + mech + spot].astype(float), real[trend]], axis=1), y, dates)
print(f'(3) D7: base+mechanics+spot-since-entry {a4:.3f} | +trend on top {a5:.3f}')
q = df.dropna(subset=['adv_since_entry_bp'])
print('   stop rate by adverse spot move since entry (bp):', q.groupby(pd.cut(q.adv_since_entry_bp, [-500, 0, 20, 40, 60, 80, 120, 500])).label.agg(['size', 'mean']).round(2).to_dict('index'))
