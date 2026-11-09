"""Stop-shape follow-ups on the exit panel.  python3 analysis/exit_engine/stop_shape.py
A) static vs dynamic: lot-stop hazard at FIXED rh_cheap bins, compared across TTE / day / IV-change / adverse spot-move / minutes-since-entry.
B) points-floor formula: level = entry + max(a*entry, b) ; forward precision/recall of 'first minute-high crossing -> lot-stop label within 2 min'.
C) delay from first crossing of 1.55x (minute high) to the lot-stop exit."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
C = os.path.join(os.path.dirname(HERE), '_cache'); OUT = os.path.join(HERE, 'results')
P = pd.read_pickle(os.path.join(C, 'exit_panel.pkl')).sort_values(['und', 'expiry', 'cp', 'strike', 'm'])
STOP = '1 individual lot stop-loss'; P['y'] = (P.label == STOP).astype(int)
lines = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); lines.append(s)
Q = P[P.e_cheap > 25]
RB = [1.3, 1.45, 1.55, 1.7, 2.0, 3.0]
say('=== A) lot-stop hazard per minute at fixed minute-high/entry bins (entries > Rs 25) ===')
for name, col, cuts in [('TTE min', 'tte_min', [0, 120, 375, 1000, 5000]), ('D-1?', 'is_d1', [-1, 0.5, 2]), ('IV chg', 'iv_chg', [-5, -0.02, 0.02, 5]),
                        ('adverse spot ATR', 'spot_move_atr', [-100, 0, 2, 5, 100]), ('min since entry', 'min_since_cheap', [0, 30, 120, 5000]), ('index', 'und', None)]:
    grp = Q.groupby(Q[col] if cuts is None else pd.cut(Q[col], cuts), observed=True)
    t = grp.apply(lambda g: g.groupby(pd.cut(g.rh_cheap, RB), observed=True).y.mean(), include_groups=False)
    say(f'-- {name}'); say(t.round(3).to_string())
# B) points-floor formula
say('\n=== B) stop level = entry + max(a*entry, b): forward precision (crossing -> lot-stop within 2 min) and recall ===')
P['ep'] = (P.e_cheap.round(2)).astype(str)
ep_key = ['und', 'expiry', 'cp', 'strike', 'ep']
stops = P[P.y == 1][ep_key + ['m']]
res = []
for a in [0.45, 0.5, 0.55, 0.6, 0.7]:
    for b in [0, 5, 10, 15, 20]:
        for und_scale in [1]:
            lvl = P.e_cheap + np.maximum(a * P.e_cheap, b * np.where(P.und == 'SENSEX', 3.2, 1.0))
            cr = P[P.hi >= lvl]
            first = cr.groupby(ep_key).m.min().reset_index()
            m = first.merge(stops, on=ep_key, how='left', suffixes=('', '_s'))
            m['hit'] = (m.m_s >= m.m - pd.Timedelta(minutes=0)) & (m.m_s <= m.m + pd.Timedelta(minutes=2))
            prec = m.groupby(ep_key + ['m']).hit.any().mean()
            # recall: stops with a predicted first crossing within [-2, 0] minutes
            s2 = stops.merge(first, on=ep_key, how='left', suffixes=('', '_c'))
            rec = ((s2.m_c <= s2.m) & (s2.m_c >= s2.m - pd.Timedelta(minutes=2))).mean()
            res.append(dict(a=a, b_nifty_pts=b, crossings=len(first), precision=round(prec, 3), recall=round(rec, 3)))
R = pd.DataFrame(res).sort_values('recall', ascending=False); say(R.head(12).to_string(index=False))
R.to_csv(os.path.join(OUT, 'stop_formula_grid.csv'), index=False)
# C) delay
say('\n=== C) delay from first minute-high crossing of 1.55x to the lot-stop exit (entries > Rs 25) ===')
Q = P[P.e_cheap > 25].copy()
first = Q[Q.hi >= 1.55 * Q.e_cheap].groupby(ep_key).m.min().rename('m_cross').reset_index()
s = Q[Q.y == 1][ep_key + ['m']].merge(first, on=ep_key, how='left')
s['delay'] = (s.m - s.m_cross).dt.total_seconds() / 60
say('delay quantiles (min):', s.delay.quantile([.1, .25, .5, .75, .9]).round(1).to_dict(), '| no prior crossing (exit before 1.55x on minute high):', round(s.m_cross.isna().mean() + (s.delay < 0).mean(), 3))
first_close = Q[Q.px >= 1.55 * Q.e_cheap].groupby(ep_key).m.min().rename('m_cc').reset_index()
s = s.merge(first_close, on=ep_key, how='left'); s['delay_close'] = (s.m - s.m_cc).dt.total_seconds() / 60
say('delay from first prev-minute CLOSE crossing:', s.delay_close.quantile([.1, .25, .5, .75, .9]).round(1).to_dict())
open(os.path.join(OUT, 'stop_shape_report.txt'), 'w').write('\n'.join(lines))
