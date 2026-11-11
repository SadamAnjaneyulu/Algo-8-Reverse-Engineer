"""Client-provided hypothesis test: "4 % expiry-day kill switch" (Rahul, verbal) against Algo 8's observed cycle stop.
Each definition is tested separately; nothing here changes RSK-01..RSK-03.

MTM = minute-close LTP mark of the whole cycle book (body + wings + lump), cumulative from the first D-1 fill (analysis/mtm.py,
which reconciles with the lot book, DAT-08). D0-only MTM = MTM(m) - MTM(last D-1 minute). Stop time = first `s_` fill.
Outcome per cycle: stop cycle with the threshold crossed at or before the stop minute (hit) / stop before any crossing (miss) /
non-stop cycle that crosses (false trigger) / non-stop that never crosses (correct non-trigger).
python3 dte_comparison/kill_switch_tests.py"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.join(os.path.dirname(HERE), 'analysis'); sys.path.insert(0, AN)
from load import load_tagged
from mtm import cycle_mtm
CAP = 2e7
DEFS = [  # id, description, scope, threshold kind, value
    ('K0', 'Observed reference (RSK-01): cumulative MTM <= -Rs 1.33 L (not a hypothesis; harness check)', 'cycle', 'abs', 133000),
    ('K1', '4 % x total capital Rs 2 Cr = Rs 8.0 L, D0-only MTM', 'd0', 'abs', 0.04 * CAP),
    ('K2', '4 % x total capital Rs 2 Cr = Rs 8.0 L, cumulative cycle MTM', 'cycle', 'abs', 0.04 * CAP),
    ('K3', '4 % x 20 % utilised capital (Rs 40 L) = Rs 1.6 L, D0-only MTM', 'd0', 'abs', 0.04 * 0.2 * CAP),
    ('K4', '4 % x 20 % utilised capital (Rs 40 L) = Rs 1.6 L, cumulative cycle MTM', 'cycle', 'abs', 0.04 * 0.2 * CAP),
    ('K5', '4 % x 20 % of a per-index half (Rs 20 L) = Rs 0.8 L, D0-only MTM', 'd0', 'abs', 0.04 * 0.2 * CAP / 2),
    ('K6', '4 % x 20 % of a per-index half (Rs 20 L) = Rs 0.8 L, cumulative cycle MTM', 'cycle', 'abs', 0.04 * 0.2 * CAP / 2),
    ('K7', '4 % of gross body premium sold in the cycle so far, cumulative cycle MTM', 'cycle', 'prem_cycle', 0.04),
    ('K8', '4 % of gross body premium sold on D0 so far, D0-only MTM', 'd0', 'prem_d0', 0.04),
    ('K9', 'D0 drawdown from the D0 running peak >= Rs 1.6 L (4 % x Rs 40 L)', 'd0_dd', 'abs', 0.04 * 0.2 * CAP),
    ('K10', 'Info.txt context: 1 % x Rs 2 Cr = Rs 2.0 L on expiry day, D0-only MTM (already RSK-03)', 'd0', 'abs', 0.01 * CAP),
]

if __name__ == '__main__':
    d = load_tagged(); o = pd.read_pickle(os.path.join(AN, '_cache', 'opt_candles.pkl'))
    rows, paths = [], []
    for (u, e), c in d.groupby(['und', 'expiry']):
        m = cycle_mtm(d, o, u, e)
        day0 = m.index.normalize() == e
        base = m[~day0].iloc[-1] if (~day0).any() else 0.0
        d0 = (m - base).where(day0)
        dd = (d0 - d0.cummax()).where(day0)
        sells = c[(c.tp == 'num') & (c.side == 'Sell')].assign(minute=lambda x: x.t.dt.floor('min'))
        prem = (sells.px_fill * sells.qty_fill).groupby(sells.minute).sum().reindex(m.index).fillna(0)
        prem_cycle = prem.cumsum(); prem_d0 = prem.where(day0, 0).cumsum()
        st = c[c.tp == 's_'].t.min(); stm = st.floor('min') if pd.notna(st) else pd.NaT
        paths.append(dict(und=u, expiry=e, m=m, d0=d0, dd=dd, pc=prem_cycle, p0=prem_d0, stop=stm,
                          stop_day=('D0' if pd.notna(stm) and stm.normalize() == e else ('D-1' if pd.notna(stm) else ''))))
    for kid, desc, scope, kind, val in DEFS:
        res = dict(hit=0, miss=0, false_trigger=0, correct_nontrigger=0); leads = []; miss_d1 = 0
        for p in paths:
            s = {'cycle': p['m'], 'd0': p['d0'], 'd0_dd': p['dd']}[scope]
            thr = {'abs': pd.Series(-val, index=s.index), 'prem_cycle': -val * p['pc'], 'prem_d0': -val * p['p0']}[kind]
            ok = s.notna() & (thr < 0)
            cross = s[ok & (s <= thr)]
            t_cross = cross.index[0] if len(cross) else pd.NaT
            if pd.notna(p['stop']):
                if pd.notna(t_cross) and t_cross <= p['stop']:
                    res['hit'] += 1; leads.append((p['stop'] - t_cross).total_seconds() / 60)
                else:
                    res['miss'] += 1; miss_d1 += p['stop_day'] == 'D-1'
            else:
                res['false_trigger' if pd.notna(t_cross) else 'correct_nontrigger'] += 1
        rows.append(dict(id=kid, definition=desc, **res, stop_cycles_missed_on_D1=miss_d1,
                         median_minutes_cross_to_stop=float(np.median(leads)) if leads else np.nan,
                         max_minutes_cross_to_stop=float(np.max(leads)) if leads else np.nan))
    R = pd.DataFrame(rows); R.to_csv(os.path.join(HERE, 'kill_switch_tests.csv'), index=False)
    P = pd.DataFrame([dict(und=p['und'], expiry=p['expiry'].date(), stop_minute=p['stop'], stop_day=p['stop_day'],
                           min_cycle_mtm=round(p['m'].min()), min_cycle_mtm_before_stop=round(p['m'][p['m'].index < p['stop']].min()) if pd.notna(p['stop']) else np.nan,
                           min_d0_mtm=round(p['d0'].min()) if p['d0'].notna().any() else np.nan, d1_close_mtm=round(p['m'][p['m'].index.normalize() != p['expiry']].iloc[-1]) if (p['m'].index.normalize() != p['expiry']).any() else np.nan,
                           gross_body_premium_sold=round(p['pc'].iloc[-1])) for p in paths])
    P.to_csv(os.path.join(HERE, 'kill_switch_cycle_paths.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 80)
    print(R.to_string(index=False)); print(P.to_string(index=False))
