"""Sensitivity of R1 to assumption bands (NOT tuning; each value is inside the evidence band or a stress). Reports Sharpe/net by part."""
import math
from multiprocessing import Pool
from sim import *
from bt import cycles as Cy
cl = Cy.cycle_list(); cl = cl[(cl.status == 'Complete') & cl.split.isin(['IS', 'OOS'])].reset_index(drop=True)
CASES = {'base R1': {}, 'slippage x3': dict(slip_mult=3), 'slippage x6': dict(slip_mult=6), 'costs x2': dict(cost_mult=2), 'leg stop 1.55x': dict(leg_mult=1.55), 'leg stop 1.70x': dict(leg_mult=1.70), 'cycle stop 1.30L': dict(stop_limit=130000), 'cycle stop 2.00L': dict(stop_limit=200000), 'no wings (diagnostic)': dict(wing_on=False)}


def job(a):
    name, kw, r = a
    try:
        cc = Cy.load(r['und'], r['expiry']); c = load_cycle(r['und'], r['expiry'], r['d1'], r['d0']); lot = cc['lot_d1'] or cc['lot_d0']; s = simulate(c, lot, 'R1', **kw)
        return dict(case=name, und=r['und'], d0=r['d0'], d1=r['d1'], split=r['split'], subset=r['subset'], net=s['net'], gross=s['gross'], stopped=s['stopped'] is not None)
    except Exception as ex: return dict(case='ERR', err=str(ex)[:60])


if __name__ == '__main__':
    jobs = [(n, kw, r) for n, kw in CASES.items() for r in cl.to_dict('records')]
    with Pool(4) as p: res = p.map(job, jobs, chunksize=20)
    D = pd.DataFrame(res); print('errors', (D.case == 'ERR').sum()); D = D[D.case != 'ERR']; D.to_csv(f'{RES}/sensitivity_cycles.csv', index=False)
    D['wk'] = pd.to_datetime(D.d0).dt.strftime('%G-W%V'); rows = []
    for n, g in D.groupby('case'):
        for p, f in (('IS', g.split == 'IS'), ('OOS', g.split == 'OOS'), ('OOS clean', g.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])), ('OOS exposed', g.subset == 'OOS_EXPOSED')):
            x = g[f]; w = x.groupby('wk').net.sum() / CAP; rows.append(dict(case=n, part=p, net=x.net.sum(), sharpe=w.mean() / w.std(ddof=1) * math.sqrt(52), stops=int(x.stopped.sum())))
    T = pd.DataFrame(rows); T.to_csv(f'{RES}/sensitivity_summary.csv', index=False); print(T.pivot(index='case', columns='part', values='sharpe').round(2)); print(T.pivot(index='case', columns='part', values='net').round(0))
