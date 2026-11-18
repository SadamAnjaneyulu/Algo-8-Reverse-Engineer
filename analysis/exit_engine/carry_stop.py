"""Carried-lot stop test (Info.txt: 'carry forward SL of 4% on the positions carried forward to expiry').
On D0, split open short lots into CARRIED (cheapest open lot entered on D-1) vs FRESH (entered on D0). For carried lots compare candidate
references: own entry, D-1 last price, D0 first price; and spot % move since D-1 close.  python3 analysis/exit_engine/carry_stop.py"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
C = os.path.join(os.path.dirname(HERE), '_cache'); OUT = os.path.join(HERE, 'results')
P = pd.read_pickle(os.path.join(C, 'exit_panel.pkl'))
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl')); ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
STOP_LIKE = ['1 individual lot stop-loss', '2 same-contract partial buy-back', '3 side-level reduction', '4 basket-level reduction', '11 unexplained']
D0 = P[P.is_d1 == 0].copy()
D0['since_open'] = ((D0.m - D0.m.dt.normalize() - pd.Timedelta('09:15:00')).dt.total_seconds() / 60)
D0['carried'] = D0.min_since_cheap > D0.since_open + 1
# reference prices per contract: D-1 last close, D0 first open
op['day'] = op.ts.dt.normalize()
last_d1 = op.sort_values('ts').groupby(['und', 'expiry', 'cp', 'strike', 'day']).c.last()
first_d0 = op.sort_values('ts').groupby(['und', 'expiry', 'cp', 'strike', 'day']).o.first()
days = {k: sorted(v) for k, v in op.groupby(['und', 'expiry']).day.unique().items()}
def ref(row, which):
    dd = days.get((row.und, row.expiry), [])
    if len(dd) < 2: return np.nan
    if which == 'd1close': return last_d1.get((row.und, row.expiry, row.cp, row.strike, dd[-2]), np.nan)
    return first_d0.get((row.und, row.expiry, row.cp, row.strike, dd[-1]), np.nan)
keys = D0[['und', 'expiry', 'cp', 'strike']].drop_duplicates()
keys['ref_d1close'] = [ref(r, 'd1close') for r in keys.itertuples()]; keys['ref_d0open'] = [ref(r, 'd0open') for r in keys.itertuples()]
D0 = D0.merge(keys, on=['und', 'expiry', 'cp', 'strike'], how='left')
sc = ix.assign(day=ix.ts.dt.normalize()).sort_values('ts').groupby(['und', 'day']).close.last()
D0['S_d1close'] = [sc.get((u, days.get((u, e), [None, None])[-2] if len(days.get((u, e), [])) >= 2 else None), np.nan) for u, e in zip(D0.und, D0.expiry)]
lines = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); lines.append(s)
D0['y_stop'] = (D0.label == '1 individual lot stop-loss').astype(int); D0['y_any'] = D0.label.isin(STOP_LIKE).astype(int)
say('D0 open-short contract-minutes: carried', int(D0.carried.sum()), '| fresh', int((~D0.carried).sum()))
say('\nlot-stop hazard by minute-high / OWN cheapest entry, carried vs fresh:')
say(D0.groupby(['carried', pd.cut(D0.rh_cheap, [0, 1.3, 1.45, 1.55, 1.7, 2.0, 3.0, 100])], observed=True).y_stop.mean().unstack(0).round(3).to_string())
Cr = D0[D0.carried & D0.ref_d1close.notna()].copy()
Cr['rh_d1'] = Cr.hi / Cr.ref_d1close; Cr['rh_d0o'] = Cr.hi / Cr.ref_d0open
Cr['spot_pct_d1'] = (Cr.px * 0 + 1) * np.nan
for col, name in [('rh_d1', 'minute-high / D-1 close of the contract'), ('rh_d0o', 'minute-high / D0 opening price of the contract')]:
    say(f'\ncarried lots - stop-like exit hazard by {name}:')
    say(Cr.groupby(pd.cut(Cr[col], [0, 0.8, 1.0, 1.04, 1.1, 1.2, 1.3, 1.45, 1.55, 1.7, 2.0, 3.0, 100]), observed=True).y_any.agg(['size', 'mean']).round(3).T.to_string())
# spot move since D-1 close (adverse for the leg), in %
spot_at = ix.set_index(['und', 'ts']).close
Cr['S_now'] = [spot_at.get((u, m - pd.Timedelta(minutes=1)), np.nan) for u, m in zip(Cr.und, Cr.m)]
Cr['adv_pct'] = (Cr.S_now - Cr.S_d1close) / Cr.S_d1close * 100 * np.where(Cr.cp == 'CE', 1, -1)
say('\ncarried lots - stop-like exit hazard by ADVERSE spot move since D-1 close (%):')
say(Cr.groupby(pd.cut(Cr.adv_pct, [-10, -0.5, 0, 0.25, 0.5, 0.75, 1.0, 1.5, 2, 4, 10]), observed=True).y_any.agg(['size', 'mean']).round(3).T.to_string())
open(os.path.join(OUT, 'carry_stop_report.txt'), 'w').write('\n'.join(lines))
