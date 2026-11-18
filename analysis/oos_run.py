"""LOCKED OUT-OF-SAMPLE run of the frozen alpha grid on new history (e.g. Mar 2025 - Jun 2026).  Refuses to run if the freeze hash
does not match, or if lot sizes are not supplied.  No parameter is changed on OOS data.
  ALGO8_MARKET_DIR=<new data/breeze/normalized> python3 analysis/oos_run.py --lots lots.json --start 2025-03-01 --end 2026-06-19
lots.json example (CONFIRM against exchange circulars):  {"NIFTY": [["2025-03-01","2025-12-31",75], ["2026-01-01","2026-12-31",65]], "SENSEX": [["2025-03-01","2026-12-31",20]]}"""
import sys, os, json, hashlib, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy.stats import spearmanr
HERE = os.path.dirname(os.path.abspath(__file__)); FZ = os.path.join(HERE, '..', 'alpha_freeze')
def check_freeze():
    h = hashlib.sha256()
    for f in ['protocol.json', 'configs.csv', 'dev_grid_metrics.csv']: h.update(open(os.path.join(FZ, f), 'rb').read())
    want = open(os.path.join(FZ, 'FREEZE_SHA256.txt')).read().strip()
    if h.hexdigest() != want: sys.exit('FREEZE HASH MISMATCH - frozen files were modified; refusing to run OOS.')
    return want
def main():
    p = argparse.ArgumentParser(); p.add_argument('--lots', required=True); p.add_argument('--start', required=True); p.add_argument('--end', required=True)
    p.add_argument('--workers', type=int, default=4); a = p.parse_args()
    fz = check_freeze(); lots = json.load(open(a.lots))
    import market, engine, alpha_grid as G, alpha_eval as E
    from multiprocessing import Pool
    idx = market.load_index(); opt = market.load_options()
    s, e = pd.Timestamp(a.start), pd.Timestamp(a.end)
    idx = idx[(idx.ts >= s) & (idx.ts < e + pd.Timedelta(days=1))]; opt = opt[(opt.ts >= s) & (opt.ts < e + pd.Timedelta(days=1))]
    def lot_for(und, d):
        for lo, hi, n in lots[und]:
            if pd.Timestamp(lo) <= d <= pd.Timestamp(hi): return n
        sys.exit(f'No lot size supplied for {und} on {d.date()}')
    cycles = []
    for (und, ex), _ in opt.groupby(['und', 'expiry']):
        days = sorted(d for d in idx[idx.und == und].ts.dt.normalize().unique() if d <= ex)
        if not days or days[-1] != ex or len(days) < 2: continue
        cy = engine.Cycle(und, ex, days[-2:], idx, opt); cy.lot = lot_for(und, ex); cycles.append(cy)
    print('OOS cycles', len(cycles), 'freeze', fz[:12], flush=True)
    cf = json.load(open(os.path.join(HERE, '_cache', 'grid_configs.json'))) if os.path.exists(os.path.join(HERE, '_cache', 'grid_configs.json')) else pd.read_csv(os.path.join(FZ, 'configs.csv')).to_dict('records')
    em = G.expected_move_table(idx)
    with Pool(a.workers, initializer=G.init, initargs=(cycles, em)) as pool:
        res = [r for rows in pool.imap_unordered(G.work, cf, chunksize=8) for r in rows]
    M = pd.DataFrame(res, columns=['cfg', 'cycle', 'pnl_lot', 'turn_lot', 'orders_lot', 'units_lot', 'missing', 'n_lots', 'cstop'])
    M['und'] = [cycles[k].und for k in M.cycle]; M['expiry'] = [cycles[k].expiry for k in M.cycle]
    M.to_pickle(os.path.join(FZ, 'oos_cycle_pnl.pkl'))
    dev = pd.read_csv(os.path.join(FZ, 'dev_grid_metrics.csv')); out = {}
    for scen in ['zero', 'moderate', 'conservative', 'adverse']:
        M['net'] = E.net_lot(M, scen); P = M.pivot_table(index='cfg', columns=['expiry', 'und'], values='net').sort_index(axis=1)
        met = pd.DataFrame([dict(cfg=c, **E.metrics(x.values)) for c, x in P.iterrows()])
        met.to_csv(os.path.join(FZ, f'oos_metrics_{scen}.csv'), index=False)
        if scen in ('moderate', 'conservative'):
            d = dev[dev.scenario == ('conservative' if scen == 'conservative' else 'moderate')].set_index('cfg').sharpe_cycle
            j = met.set_index('cfg').sharpe_cycle.to_frame('oos').join(d.rename('dev')).dropna()
            rho, pr = spearmanr(j.dev, j.oos); top = j.dev >= j.dev.quantile(0.9)
            rc_p, best = E.reality_check(P.values)
            out[scen] = dict(spearman_dev_vs_oos=rho, p=pr, oos_sharpe_top_decile=j.oos[top].mean(), oos_sharpe_rest=j.oos[~top].mean(), reality_check_p=rc_p, best_mean=best)
    print(json.dumps(out, indent=1, default=float)); json.dump(out, open(os.path.join(FZ, 'oos_tests.json'), 'w'), indent=1, default=float)
if __name__ == '__main__':
    main()
