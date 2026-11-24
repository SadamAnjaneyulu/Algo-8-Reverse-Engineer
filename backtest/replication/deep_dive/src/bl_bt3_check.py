"""Identity check V3 (plan reports/BACKTEST3Y_PLAN.md): bl_bt3_sim.sim_d0, fed the REAL carried book of a live cycle, must reproduce bl_d0v_sizing.sim2 (mode M0, s = 1) on the 49 live test cycles
(lots aggregated by class, right, minute, strike; final gross cash). Output outputs/bl_bt3_identity.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_d0v_sizing as Z
import bl_bt3_sim as S
rows = []
for nm in Z.PAR:
    P = Z.make_P(nm)
    for i in Z.PAR[nm]['test']:
        r = Z.CY.iloc[i]; o, info = Z.sim2(i, P, 'M0', 1.0, np.random.default_rng(0), 'ratio'); u = float(r.unit)
        z1 = Z.O[(Z.O.und == r.und) & (Z.O.expiry == r.expiry) & (Z.O.dayno == 0)]; sg = np.where(z1.side.str.lower() == 'buy', 1, -1); cash = float((-sg * z1.px_avg * z1.lots * u).sum()); oth = {}
        for q, s_ in zip(z1.itertuples(), sg):
            if q.module == 'num' and q.role in ('open_short', 'cover_short'): continue
            kk = (q.module, q.cp, int(q.strike)); oth[kk] = oth.get(kk, 0) + s_ * q.lots
        book = dict(lots=[[L['cp'], L['strike'], L['entry']] for L in Z.BK[i]['at_open']], longs={k: v for k, v in oth.items() if v > 0}, oshort={k: -v for k, v in oth.items() if v < 0}, cash=cash)
        cyc = S.load(r.und, r.expiry); P2 = dict(W=P['W'], k3=P['k3'], m1=P['m1'], r=P['r'], ow=P['ow']); fills, inf = S.sim_d0(cyc, r.version, P2, book, u, causal=False)
        f = pd.DataFrame(fills, columns=['day', 'j', 'cp', 'strike', 'side', 'lots', 'price', 'cls', 'n_orders'])
        a = o.groupby(['cls', 'cp', 'j', 'strike']).lots.sum().sort_index(); b = f.groupby(['cls', 'cp', 'j', 'strike']).lots.sum().sort_index()
        same = a.equals(b); diff = int((a.reindex(a.index.union(b.index), fill_value=0) != b.reindex(a.index.union(b.index), fill_value=0)).sum())
        rows.append(dict(split=nm, cid=i, same_lots=same, n_diff_keys=diff, lots_sim2=int(a.sum()), lots_new=int(b.sum()), pnl_sim2=info['pnl'], pnl_new=inf['gross'], rel_pnl_diff=abs(info['pnl'] - inf['gross']) / max(abs(info['pnl']), 1.0)))
R = pd.DataFrame(rows); R.round(6).to_csv(f'{S.OUT}/bl_bt3_identity.csv', index=False); print(len(R), 'cycles; identical lots:', int(R.same_lots.sum()), '; max rel P&L diff', R.rel_pnl_diff.max(), '; median', R.rel_pnl_diff.median()); print(R[~R.same_lots].to_string())
