"""Alpha search grid (DEVELOPMENT sample = Jun-Oct 2026; never the locked OOS).  python3 analysis/alpha_grid.py
Each config is run on every cycle; P&L is normalised PER STRADDLE-LOT SOLD so different entry patterns are comparable.
Outputs: _cache/grid_cycle_pnl.pkl (config x cycle matrix, gross + cost components) and grid_configs.json."""
import sys, os, json, itertools, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from multiprocessing import Pool
from engine import Cycle, Config, run, STEP
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
SLOTS = [f'{h:02d}:{m:02d}' for h in range(9, 16) for m in (1, 16, 31, 46) if '09:16' <= f'{h:02d}:{m:02d}' <= '15:01']
LADDER_D1 = [('09:16', 3), ('09:31', 2), ('09:46', 3), ('10:01', 1), ('10:16', 3), ('10:31', 1), ('10:46', 2), ('11:01', 2), ('11:16', 1), ('11:31', 1), ('11:46', 3),
             ('12:01', 1), ('12:31', 2), ('13:16', 1), ('13:30', 1), ('13:45', 1), ('14:00', 1), ('14:15', 1), ('14:30', 1)]
LADDER_D0 = [('09:16', 8), ('09:31', 4), ('09:46', 4), ('10:01', 1), ('10:16', 4), ('10:31', 3), ('10:46', 2), ('11:01', 3), ('11:16', 2), ('11:31', 2), ('11:46', 3),
             ('12:01', 1), ('12:31', 4), ('12:46', 2), ('13:01', 3), ('13:16', 1), ('13:31', 3), ('14:01', 2)]
ENTRY = {'ladder': LADDER_D1, 'uniform15': [(s, 1) for s in SLOTS], 'single0916': [('09:16', 1)], 'single1116': [('11:16', 1)],
         'single1316': [('13:16', 1)], 'single1501': [('15:01', 1)]}
ENTRY_D0 = {'ladderD0': LADDER_D0, 'uniform15': [(s, 1) for s in SLOTS if s <= '14:31'], 'single0916': [('09:16', 1)], 'single1116': [('11:16', 1)], 'single1316': [('13:16', 1)]}
WINGS = [None, 0.006, 0.012, 0.025]; LEG = [None, 1.3, 1.55, 2.0]; CYC = [None, 'on']; VRP = [None, 1.0, 1.2]

_cycles = None; _em = None
def expected_move_table(idx):
    """mean |close-to-close| move of the previous 10 sessions, in index points, available from the start of each session."""
    out = {}
    for und, g in idx.groupby('und'):
        dc = g.groupby(g.ts.dt.normalize()).close.last()
        em = dc.diff().abs().rolling(10).mean().shift(1)
        out.update({(und, d): v for d, v in em.items()})
    return out
def vrp_filter(theta):
    def f(cy, i):
        em = _em.get((cy.und, cy.t[i].normalize()))
        if em is None or not np.isfinite(em): return True        # insufficient history -> filter not applied (labelled)
        S1 = cy.S[i - 1]; K = round(S1 / STEP[cy.und]) * STEP[cy.und]
        kc, kp = cy.k2i.get(('CE', K)), cy.k2i.get(('PE', K))
        if kc is None or kp is None: return False
        prem = cy.Cf[kc, i - 1] + cy.Cf[kp, i - 1]
        frac_left = max((pd.Timestamp(cy.t[i].normalize()) + pd.Timedelta('15:30:00') - cy.t[i]).total_seconds() / 22500, 0.0)
        sessions_left = frac_left + (1.0 if cy.day[i] == 0 else 0.0)
        return prem >= theta * em * np.sqrt(max(sessions_left, 0.1))
    return f
def configs():
    out = []
    for e, x, w, l, c, v in itertools.product(ENTRY, ['D0 09:16', 'D0 10:01', 'D0 12:01', 'D0 15:14', 'expiry'], WINGS, LEG, CYC, VRP):
        out.append(dict(group='BTST', entry=e, exit=x, wing=w, leg=l, cyc=c, vrp=v))
    for e, x, w, l, c, v in itertools.product(ENTRY_D0, ['D0 12:01', 'D0 15:14', 'expiry'], WINGS, LEG, CYC, VRP):
        out.append(dict(group='D0only', entry=e, exit=x, wing=w, leg=l, cyc=c, vrp=v))
    for x, w, l, c, v in itertools.product(['D0 15:14', 'expiry'], WINGS, LEG, CYC, VRP):
        out.append(dict(group='both', entry='ladder+ladderD0', exit=x, wing=w, leg=l, cyc=c, vrp=v))
    for i, c in enumerate(out): c['id'] = i
    return out
def to_cfg(c):
    if c['group'] == 'BTST': sch = [(0, h, n) for h, n in ENTRY[c['entry']]]
    elif c['group'] == 'D0only': sch = [(1, h, n) for h, n in ENTRY_D0[c['entry']]]
    else: sch = [(0, h, n) for h, n in LADDER_D1] + [(1, h, n) for h, n in LADDER_D0]
    lots_leg = sum(n for _, _, n in sch)
    exit_time = None if c['exit'] == 'expiry' else c['exit'].split()[1]
    return Config(name=str(c['id']), schedule=sch, wing_frac=c['wing'], leg_stop=c['leg'], stop_fill='level',
                  cycle_stop=(1600.0 * lots_leg) if c['cyc'] else None,   # ~Rs1.33L for the 83-lot clone book, scaled per lot
                  exit_time=exit_time, filt=vrp_filter(c['vrp']) if c['vrp'] else None), lots_leg
def work(c):
    cfg, lots_leg = to_cfg(c); rows = []
    for k, cy in enumerate(_cycles):
        r = run(cy, cfg); n = max(r['n_lots'], 1)
        rows.append((c['id'], k, r['pnl'] / n, r['turnover'] / n, r['orders'] / n, r['units'] / n, r['missing'], r['n_lots'], r['cycle_stopped']))
    return rows
def init(cyc, em):
    global _cycles, _em; _cycles, _em = cyc, em
if __name__ == '__main__':
    idx = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); opt = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
    A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
    cycles = []
    for r in A.itertuples():
        e = pd.Timestamp(r.expiry); days = sorted(d for d in idx[idx.und == r.und].ts.dt.normalize().unique() if d <= e)
        cycles.append(Cycle(r.und, e, days[-2:], idx, opt))
    em = expected_move_table(idx); cf = configs()
    print('configs', len(cf), 'cycles', len(cycles), flush=True)
    t0 = time.time()
    with Pool(4, initializer=init, initargs=(cycles, em)) as p:
        res = []
        for i, rows in enumerate(p.imap_unordered(work, cf, chunksize=8)):
            res.extend(rows)
            if i % 500 == 0: print(f'{i}/{len(cf)} configs  {time.time() - t0:.0f}s', flush=True)
    M = pd.DataFrame(res, columns=['cfg', 'cycle', 'pnl_lot', 'turn_lot', 'orders_lot', 'units_lot', 'missing', 'n_lots', 'cstop'])
    M['und'] = [cycles[k].und for k in M.cycle]; M['expiry'] = [cycles[k].expiry for k in M.cycle]
    M.to_pickle(os.path.join(C, 'grid_cycle_pnl.pkl')); json.dump(cf, open(os.path.join(C, 'grid_configs.json'), 'w'), indent=0)
    print('done', f'{time.time() - t0:.0f}s', len(M))
