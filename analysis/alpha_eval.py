"""Evaluate the development grid: user's 7 metrics per config & cost scenario, plateau stability, White reality check (stationary
bootstrap over cycles), PBO via CSCV, universe-bias flag. Then FREEZE the full dev ranking + OOS protocol with a SHA-256.
python3 analysis/alpha_eval.py"""
import sys, os, json, hashlib, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from engine import COSTS
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache'); OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alpha_freeze')
M = pd.read_pickle(os.path.join(C, 'grid_cycle_pnl.pkl')); CF = pd.DataFrame(json.load(open(os.path.join(C, 'grid_configs.json'))))
LOTSIZE = {'NIFTY': 65, 'SENSEX': 20}
def net_lot(df, scen):
    a, b, c = COSTS[scen]; return df.pnl_lot - a * df.turn_lot - b * df.orders_lot - c * df.units_lot
CYCLES_PER_YEAR = 104   # 2 weekly cycles x 52 (one per index)
def metrics(x):
    x = np.asarray(x); n = len(x); wins = x[x > 0].sum(); losses = -x[x < 0].sum()
    cum = np.cumsum(x); dd = (cum - np.maximum.accumulate(np.concatenate([[0], cum]))[1:]).min()
    sd = x.std(ddof=1)
    return dict(cycles=n, win_rate=(x > 0).mean(), profit_factor=wins / losses if losses > 0 else np.inf, sharpe_cycle=x.mean() / sd if sd > 0 else np.nan,
                sharpe_ann=x.mean() / sd * np.sqrt(CYCLES_PER_YEAR) if sd > 0 else np.nan, total=x.sum(), mean=x.mean(), max_dd=dd)
def stationary_bootstrap_idx(n, B, p=0.25, rng=None):
    rng = rng or np.random.default_rng(0); out = np.empty((B, n), dtype=int)
    for b in range(B):
        i = rng.integers(n); j = 0
        while j < n:
            out[b, j] = i; j += 1
            i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return out
def reality_check(P, B=2000):
    """P: configs x cycles (chronological). H0: best config has mean <= 0. White (2000) with demeaned bootstrap."""
    mu = P.mean(axis=1); best = mu.max(); n = P.shape[1]
    idx = stationary_bootstrap_idx(n, B); D = P - mu[:, None]
    mx = np.array([D[:, ii].mean(axis=1).max() for ii in idx])
    return float((mx >= best).mean()), float(best)
def pbo_cscv(P, S=6):
    """Probability of Backtest Overfitting (Bailey et al.) with S contiguous blocks of cycles, metric = mean/sd."""
    n = P.shape[1]; blocks = np.array_split(np.arange(n), S); logits = []
    for comb in itertools.combinations(range(S), S // 2):
        tr = np.concatenate([blocks[i] for i in comb]); te = np.concatenate([blocks[i] for i in range(S) if i not in comb])
        f = lambda Q: Q.mean(axis=1) / (Q.std(axis=1, ddof=1) + 1e-9)
        k = np.argmax(f(P[:, tr])); r = (f(P[:, te]) < f(P[:, te])[k]).mean()
        r = min(max(r, 1e-6), 1 - 1e-6); logits.append(np.log(r / (1 - r)))
    logits = np.array(logits); return float((logits <= 0).mean())
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    M = M.sort_values(['cfg', 'expiry', 'und'])
    rows = []
    for scen in ['zero', 'moderate', 'conservative']:
        M['net'] = net_lot(M, scen)
        P = M.pivot_table(index='cfg', columns=['expiry', 'und'], values='net').sort_index(axis=1)
        miss = M.groupby('cfg').missing.sum() / (M.groupby('cfg').n_lots.sum() + M.groupby('cfg').missing.sum()).clip(lower=1)
        for cfg, x in P.iterrows():
            m = metrics(x.values); m.update(cfg=cfg, scenario=scen, missing_share=float(miss.get(cfg, 0)), lots_per_cycle=float(M[M.cfg == cfg].n_lots.mean()) if scen == 'zero' else np.nan)
            rows.append(m)
        if scen == 'conservative':
            Pv = P.values
            rc_p, best = reality_check(Pv); pbo = pbo_cscv(Pv)
            print(f'[{scen}] White reality check: best mean per lot Rs {best:,.0f} | p = {rc_p:.3f} (H0: no config beats zero) | PBO (CSCV, S=6) = {pbo:.2f}')
    R = pd.DataFrame(rows).merge(CF, left_on='cfg', right_on='id')
    R.to_csv(os.path.join(OUT, 'dev_grid_metrics.csv'), index=False)
    con = R[R.scenario == 'conservative'].sort_values('sharpe_cycle', ascending=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    cols = ['cfg', 'group', 'entry', 'exit', 'wing', 'leg', 'cyc', 'vrp', 'cycles', 'win_rate', 'profit_factor', 'sharpe_ann', 'total', 'max_dd', 'missing_share']
    print('\nTop 15 by conservative-cost Sharpe (per-lot P&L, Rs):'); print(con[cols].head(15).round(3).to_string(index=False))
    print('\nBy group (median / 90th pct of annualised Sharpe, conservative):'); print(con.groupby('group').sharpe_ann.describe(percentiles=[.5, .9])[['count', '50%', '90%', 'max']].round(2))
    print('\nMarginal effect of each dimension (median conservative annualised Sharpe):')
    for dim in ['group', 'entry', 'exit', 'wing', 'leg', 'cyc', 'vrp']:
        print(f'  {dim:6s}', con.groupby(con[dim].astype(str)).sharpe_ann.median().round(2).to_dict())
    # FREEZE
    proto = dict(created='before receiving OOS history', dev_sample='2026-06-22..2026-10-22, 30 complete cycles (Algo-8-traded contracts only)',
                 oos_rule='Run EVERY frozen config on the new history unchanged; report the 7 metrics under zero/moderate/conservative/adverse costs; '
                          'test (1) Spearman(dev rank, OOS rank) of conservative Sharpe, (2) OOS mean of dev top-decile vs the rest, (3) White reality check on OOS, '
                          '(4) PBO on dev+OOS; no re-optimisation on OOS. Lot sizes for the OOS period must be confirmed by the user before costs are applied.',
                 n_configs=int(CF.shape[0]))
    json.dump(proto, open(os.path.join(OUT, 'protocol.json'), 'w'), indent=1)
    CF.to_csv(os.path.join(OUT, 'configs.csv'), index=False)
    h = hashlib.sha256()
    for f in ['protocol.json', 'configs.csv', 'dev_grid_metrics.csv']: h.update(open(os.path.join(OUT, f), 'rb').read())
    open(os.path.join(OUT, 'FREEZE_SHA256.txt'), 'w').write(h.hexdigest() + '\n')
    print('\nFROZEN:', h.hexdigest())
