"""Expiry-day (D0) fidelity diagnosis: the D0 simulator started from the REAL carried book of each real cycle, compared with the real D0 orders on
entry (what / when / at which strike is sold), exit (when and how lots are bought back, per-lot outcome) and sizing (lots per order, peak short book).
No rule changes. Output outputs/d0x/diag_cycles.csv, diag_lots.csv, diag_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from collections import deque, defaultdict
import bl_bt3_sim as S
OUT = S.OUT; DX = f'{OUT}/d0x'; os.makedirs(DX, exist_ok=True); CAS = '2026-08-03'
def real_orders():
    O = pd.read_pickle(f'{OUT}/bl_all_orders.pkl.gz'); O = O[O.status_last.isin(['Filled', 'PartiallyFilled'])].copy()
    O['j'] = (O.t_last // 60 - 555).clip(0, 374).astype(int); O['sg'] = np.where(O.side == 'Buy', 1, -1); return O.sort_values(['und', 'expiry', 'dayno', 't_last', 'row'])
def real_book(d1, unit):
    """carried book at the D-1 close from the real D-1 orders: short lots with FIFO entry prices, longs by module, cash"""
    q = defaultdict(deque); longs = defaultdict(int); pos = defaultdict(int); cash = 0.0
    for r in d1.itertuples():
        k = (r.cp, int(r.strike)); n = int(r.lots); cash += -r.sg * r.px_avg * n * unit
        for _ in range(n):
            if r.sg < 0:                                                                   # sell: close a long first, else open a short
                if pos[k] > 0:
                    pos[k] -= 1; m = next((mm for (mm, c2, k2), v in longs.items() if c2 == k[0] and k2 == k[1] and v > 0), None)
                    if m: longs[(m, k[0], k[1])] -= 1
                else: pos[k] -= 1; q[k].append(r.px_avg)
            else:
                if pos[k] < 0: pos[k] += 1; q[k].popleft()
                else: pos[k] += 1; longs[(r.module, k[0], k[1])] += 1
    lots = [[cp, kk, e] for (cp, kk), dq in q.items() for e in dq]; return dict(lots=lots, longs={k: v for k, v in longs.items() if v > 0}, cash=cash)
def lot_ledger(rows, start_lots, unit, S0):
    """FIFO per-lot outcomes of shorts on D0: carried lots (from the start book) and lots sold on D0. rows: (j, cp, strike, sg, lots, price, tag)"""
    q = defaultdict(deque); out = []
    for cp, k, e in start_lots: q[(cp, int(k))].append(dict(e=e, j0=-1, src='carried'))
    longpos = defaultdict(int)
    for j, cp, k, sg, n, p, tag in rows:
        key = (cp, int(k))
        for _ in range(int(n)):
            if sg < 0:
                if longpos[key] > 0: longpos[key] -= 1
                else: q[key].append(dict(e=p, j0=j, src='D0 sale', tag=tag))
            else:
                if q[key]: L = q[key].popleft(); out.append(dict(L, x=p, j1=j, exit_tag=tag))
                else: longpos[key] += 1
    for (cp, k), dq in q.items():
        for L in dq: out.append(dict(L, x=max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0), j1=375, exit_tag='expiry'))
    return out
if __name__ == '__main__':
    O = real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok].set_index(['und', 'expiry']); rows = []; lots_rows = []
    for (u, e), g in O.groupby(['und', 'expiry']):
        if (u, e) not in T.index: continue
        t = T.loc[(u, e)]; d1 = g[g.dayno == 0]; d0 = g[g.dayno == 1]
        if not len(d1) or not len(d0): continue
        unit = float(t.unit); c = S.load(u, e); vd1, vd0 = S.versions_for(t.d1, t.d0, 'B/V2'); book = real_book(d1, unit); S0 = float(c['spot0'].close.iloc[374])
        f_sim, info = S.sim_d0(c, vd0, S.P_FROZEN, book, unit, True); F = pd.DataFrame(f_sim, columns=['day', 'j', 'cp', 'strike', 'side', 'lots', 'price', 'cls', 'n_orders'])
        era = 'after' if t.d0 >= CAS else 'before'
        real_rows = [(r.j, r.cp, r.strike, r.sg, r.lots, r.px_avg, r.module) for r in d0.itertuples()]; sim_rows = [(r.j, r.cp, r.strike, r.side, r.lots, r.price, r.cls) for r in F.itertuples()]
        for src, rr in (('real', real_rows), ('sim', sim_rows)):
            L = lot_ledger(rr, book['lots'], unit, S0)
            for x in L: lots_rows.append(dict(und=u, expiry=e, era=era, src=src, **{k: x.get(k) for k in ('e', 'x', 'j0', 'j1', 'tag', 'exit_tag')}, origin=x['src']))
            cash = book['cash'] + sum(-sg * p * n * unit for j, cp, k, sg, n, p, tag in rr); endpos = defaultdict(int)
            for cp, k, ee in book['lots']: endpos[(cp, int(k))] -= 1
            for (m, cp, k), n in book['longs'].items(): endpos[(cp, int(k))] += n
            for j, cp, k, sg, n, p, tag in rr: endpos[(cp, int(k))] += sg * n
            total = cash + sum(n * (max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0)) * unit for (cp, k), n in endpos.items())
            sells = [x for x in rr if x[3] < 0]; buys = [x for x in rr if x[3] > 0]
            rows.append(dict(und=u, expiry=e, era=era, src=src, cycle_total=total, d0_sold=sum(x[4] for x in sells), d0_bought=sum(x[4] for x in buys), sell_orders=len(sells), lots_per_sell_order=np.mean([x[4] for x in sells]) if sells else np.nan,
                             sold_before_1000=sum(x[4] for x in sells if x[0] < 45), sold_1000_1300=sum(x[4] for x in sells if 45 <= x[0] < 225), sold_after_1300=sum(x[4] for x in sells if x[0] >= 225),
                             mean_sell_premium=np.average([x[5] for x in sells], weights=[x[4] for x in sells]) if sells else np.nan, stop_j=info['stop_j'] if src == 'sim' else np.nan, carried_short=len(book['lots'])))
    D = pd.DataFrame(rows); Lz = pd.DataFrame(lots_rows); D.to_csv(f'{DX}/diag_cycles.csv', index=False); Lz.to_csv(f'{DX}/diag_lots.csv', index=False)
    Lz['pnl_per_unit'] = Lz.e - Lz.x; Lz['hold'] = np.where(Lz.j1 >= Lz.j0, Lz.j1 - Lz.j0.clip(lower=0), np.nan)
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    print(D.groupby(['era', 'src'])[['cycle_total', 'd0_sold', 'd0_bought', 'sell_orders', 'lots_per_sell_order', 'sold_before_1000', 'sold_1000_1300', 'sold_after_1300', 'mean_sell_premium']].mean().round(1).to_string())
    print(Lz.groupby(['era', 'src', 'origin']).agg(lots=('e', 'size'), mean_entry=('e', 'mean'), mean_exit=('x', 'mean'), pnl_per_unit=('pnl_per_unit', 'mean'), hold_min=('hold', 'median'), held_to_end=('exit_tag', lambda s: (s == 'expiry').mean())).round(2).to_string())
