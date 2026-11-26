"""Carried-book comparison (real vs free-running simulator) at the D-1 close, per complete real cycle: size, side balance, strike distance, premium, wings, D-1 P&L.
Also cycle-stop agreement: real vs hybrid (simulated D0 from the real book) vs free-run. Output outputs/d0x/book_compare.csv."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; DX = f'{OUT}/d0x'
O = DG.real_orders(); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok].set_index(['und', 'expiry']); FF = pd.read_csv(f'{OUT}/bt3_results/ablate_full_fills.csv.gz')
ctl = pd.read_csv('../../../../risk_rule_validation/results/cycle_stop_control.csv').set_index(['und', 'expiry']); fr = pd.read_csv(f'{OUT}/prepaper/var_full.csv').set_index(['und', 'expiry'])
def feats(book, c, unit, d1cash):
    S1 = float(c['spot1'].close.iloc[374]); st = S.ref.STEP[c['und']]; L = pd.DataFrame(book['lots'], columns=['cp', 'k', 'e']) if book['lots'] else pd.DataFrame(columns=['cp', 'k', 'e'])
    lg = pd.DataFrame([(m, cp, k, n) for (m, cp, k), n in book['longs'].items()], columns=['m', 'cp', 'k', 'n']) if book['longs'] else pd.DataFrame(columns=['m', 'cp', 'k', 'n'])
    off = lambda cp, k: ((k - S1) if cp == 'CE' else (S1 - k)) / st
    return dict(short_CE=int((L.cp == 'CE').sum()), short_PE=int((L.cp == 'PE').sum()), short_total=len(L), short_offset_mean=float(np.mean([off(a, b) for a, b in zip(L.cp, L.k)])) if len(L) else np.nan,
                short_entry_mean=float(L.e.mean()) if len(L) else np.nan, long_total=int(lg.n.sum()) if len(lg) else 0, long_offset_mean=float(np.average([off(a, b) for a, b in zip(lg.cp, lg.k)], weights=lg.n)) if len(lg) else np.nan,
                imbalance=abs(int((L.cp == 'CE').sum()) - int((L.cp == 'PE').sum())), d1_cash=d1cash)
rows = []
for (u, e), g in O.groupby(['und', 'expiry']):
    if (u, e) not in T.index: continue
    t = T.loc[(u, e)]; d1 = g[g.dayno == 0]; d0 = g[g.dayno == 1]
    if not len(d1) or not len(d0): continue
    c = S.load(u, e); unit = float(t.unit); rb = DG.real_book(d1, unit)
    sf = FF[(FF.und == u) & (FF.expiry == e) & (FF.day == 0)].copy(); sf['sg'] = sf.side; sf['px_avg'] = sf.price; sf['module'] = sf.cls.map({'wing_buy': 'h_', 'lump': 'v_', 'body_long': 'num'}).fillna('num'); sf['t_last'] = sf.j; sf['row'] = range(len(sf))
    sb = DG.real_book(sf, unit)
    _, hy = S.sim_d0(c, S.versions_for(t.d1, t.d0, 'B/V2')[1], S.P_FROZEN, rb, unit, True)
    r = dict(und=u, expiry=e, era='after' if t.d0 >= '2026-08-03' else 'before', real_stop=bool(ctl.loc[(u, e), 'stop']), hybrid_stop=hy['stop_j'] is not None, freerun_stop=bool(pd.notna(fr.loc[(u, e), 'stop_j'])))
    for src, b in (('real', rb), ('sim', sb)): r.update({f'{k}_{src}': v for k, v in feats(b, c, unit, b['cash']).items()})
    rows.append(r)
B = pd.DataFrame(rows); B.to_csv(f'{DX}/book_compare.csv', index=False); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
cols = ['short_total', 'short_CE', 'short_PE', 'imbalance', 'short_offset_mean', 'short_entry_mean', 'long_total', 'long_offset_mean', 'd1_cash']
print(pd.concat({src: B.groupby('era')[[f'{c}_{src}' for c in cols]].mean().set_axis(cols, axis=1) for src in ('real', 'sim')}).round(1).to_string())
for era, g in B.groupby('era'): print(era, len(g), 'stops: real', g.real_stop.sum(), '| hybrid (real book)', g.hybrid_stop.sum(), 'agree', int((g.hybrid_stop == g.real_stop).sum()), '| free-run', g.freerun_stop.sum(), 'agree', int((g.freerun_stop == g.real_stop).sum()))
print(B[B.era == 'after'][['und', 'expiry', 'short_total_real', 'short_total_sim', 'imbalance_real', 'imbalance_sim', 'd1_cash_real', 'd1_cash_sim', 'real_stop', 'hybrid_stop', 'freerun_stop']].round(0).to_string(index=False))
