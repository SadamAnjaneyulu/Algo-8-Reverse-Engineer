"""Performance of the reconstructed ladder (R1, R2) on ALL complete cycles, with the same weekly-Sharpe methodology as the earlier backtest (sum NIFTY+SENSEX per ISO week / Rs 2 crore, sqrt(52), rf 0, net of slippage + statutory costs, official-close (Yahoo) settlement for any lot still open).
The rules were NOT tuned to P&L. R2's D0 ladder is fitted to the live window (hypothesis-level) so R2 is NOT independent on the exposed window."""
import math, json
from multiprocessing import Pool
from sim import *
from bt import cycles as Cy, metrics as M
cl = Cy.cycle_list(); cl = cl[(cl.status == 'Complete') & cl.split.isin(['IS', 'OOS'])].reset_index(drop=True); D0L = d0_median_ladder()


def job(a):
    i, r = a
    try:
        cc = Cy.load(r['und'], r['expiry']); c = load_cycle(r['und'], r['expiry'], r['d1'], r['d0']); lot = cc['lot_d1'] or cc['lot_d0']; out = []
        for v in ('R1', 'R2'):
            s = simulate(c, lot, v, D0L); out.append(dict(variant=v, und=r['und'], expiry=r['expiry'], d1=r['d1'], d0=r['d0'], split=r['split'], subset=r['subset'], lot=lot, gross=s['gross'], net=s['net'], costs=s['costs'], slippage=s['slippage'], n_orders=s['n_orders'], stopped=s['stopped'] is not None))
        return out
    except Exception as ex: return [dict(variant='ERR', und=r['und'], expiry=r['expiry'], err=str(ex)[:80])]


if __name__ == '__main__':
    with Pool(4) as p: res = p.map(job, list(enumerate(cl.to_dict('records'))), chunksize=5)
    D = pd.DataFrame([x for r in res for x in r]); print('errors:', (D.variant == 'ERR').sum()); D = D[D.variant != 'ERR']; D.to_csv(f'{RES}/performance_cycles.csv', index=False)
