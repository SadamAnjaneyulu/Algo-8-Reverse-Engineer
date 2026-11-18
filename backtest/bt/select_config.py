"""In-sample grid evaluation, walk-forward, and the pre-registered selection rule. Uses IN-SAMPLE cycles only."""
import json, sys
import pandas as pd
from . import experiment as X, metrics as M
BASE = dict(slip_pct=0.005, slip_min=0.10, delay_min=0, cost_mult=1.0)
FOLDS = [('2024-11-18', '2025-02-17'), ('2025-02-18', '2025-05-17'), ('2025-05-18', '2025-08-17'), ('2025-08-18', '2025-11-17')]


def is_cycles(): u = X.usable(); return u[u.split == 'IS'].reset_index(drop=True)


def thirds(df):
    d = df.sort_values('d0').reset_index(drop=True); n = len(d); return [d.iloc[:n // 3], d.iloc[n // 3: 2 * n // 3], d.iloc[2 * n // 3:]]


def choose(tab, hold, allowed):
    """tab: {name: DataFrame of cycles (pooled)}; returns (chosen name, reason)"""
    best = sorted(((tab[n].net.sum(), -tab[n].n_orders.sum(), n) for n in allowed), reverse=True)[0][2]
    if best == 'HOLD': return 'HOLD', 'HOLD has the highest in-sample net P&L'
    if tab[best].net.sum() <= tab['HOLD'].net.sum(): return 'HOLD', 'best configuration does not beat HOLD'
    # three chronological thirds, pooled by D0 date boundaries of the whole IS sample
    d0 = pd.concat([tab['HOLD'].d0]).sort_values().reset_index(drop=True); b1, b2 = d0.iloc[len(d0) // 3], d0.iloc[2 * len(d0) // 3]
    t = tab[best]; pos = [(t[t.d0 < b1].net.sum() > 0), (t[(t.d0 >= b1) & (t.d0 < b2)].net.sum() > 0), (t[t.d0 >= b2].net.sum() > 0)]
    if sum(pos) < 2: return 'HOLD', f'best configuration {best} positive in only {sum(pos)} of 3 thirds'
    return best, f'highest in-sample net P&L; positive in {sum(pos)} of 3 thirds'


def main():
    cyc = is_cycles(); names = list(X.grid()); out = {}
    for v in X.VARIANTS:
        X.run_engine(names, v, cyc=cyc, check=True)
        tab = {n: X.account_all(n, v, BASE, cyc=cyc) for n in names}; rows = []
        for n, d in tab.items():
            s = M.summarize(d, n); s.update(config=n, variant=v, parity_all=bool(d.parity.all()), nifty_net=d[d.und == 'NIFTY'].net.sum(), sensex_net=d[d.und == 'SENSEX'].net.sum()); rows.append(s)
        T = pd.DataFrame(rows); T.to_csv(f'results/is_grid_{v}.csv', index=False)
        chosen, why = choose(tab, 'HOLD', names)
        wf = []
        for a, b in FOLDS:
            train = {n: d[d.d0 < a] for n, d in tab.items()}; val = {n: d[(d.d0 >= a) & (d.d0 <= b)] for n, d in tab.items()}
            c, w = choose(train, 'HOLD', names); wf.append(dict(fold=f'{a}..{b}', chosen=c, why=w, val_net_chosen=float(val[c].net.sum()), val_net_hold=float(val['HOLD'].net.sum()), val_cycles=int(len(val['HOLD'])), best_in_hindsight=max(names, key=lambda n: val[n].net.sum()), val_net_best=float(max(val[n].net.sum() for n in names))))
        out[v] = dict(chosen=chosen, reason=why, hold_is_net=float(tab['HOLD'].net.sum()), chosen_is_net=float(tab[chosen].net.sum()), walk_forward=wf, parity_all=bool(T.parity_all.all()))
        print(v, chosen, why, round(tab['HOLD'].net.sum()), round(tab[chosen].net.sum()), 'parity', T.parity_all.all())
    json.dump(out, open('results/is_selection.json', 'w'), indent=1)


if __name__ == '__main__': main()
