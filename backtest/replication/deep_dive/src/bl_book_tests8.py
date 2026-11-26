"""Capital-loss trigger study, part 8: shape of the short-horizon premium-change effect on D-1 sub-1.2x buy-backs (lot's own premium change over 1/3/5 min and adverse underlying move). Hazard by bin per 1000 contract-minutes (target B residual, A all sub-1.2x),
threshold-precision table, chronological halves, NIFTY vs SENSEX. Same feature construction as bl_book_tests7.py. Outputs bl_book_lotshape.csv, bl_book_lotthr.csv, bl_summary_book8.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
ch = Chain(); LOTS = ref.LOT; R = {}
Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz', usecols=['und', 'expiry', 'day', 'j', 'B_total']); ev = pd.read_csv(f'{OUT}/bl_book_events.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); P = P[(P.day == 'D-1') & (P.r_low < 1.2)].reset_index(drop=True)
resid = ev[ev.klass == 'sub-1.2x residual'].groupby(['und', 'expiry', 'day', 'cp', 'strike', 'j']).size().rename('resid_n').reset_index(); P = P.merge(resid, on=['und', 'expiry', 'day', 'cp', 'strike', 'j'], how='left').merge(Bk, on=['und', 'expiry', 'day', 'j'], how='left'); P = P[P.B_total.notna()].reset_index(drop=True)
W = (1, 3, 5); new = {f'{a}{w}': np.full(len(P), np.nan) for a in ('lot_pct', 'spot_adv') for w in W}
for (u, e, cp), idx in P.groupby(['und', 'expiry', 'cp']).groups.items():
    c = ch.cyc(u, e); si = c['_si']; px = pd.DataFrame(np.array(c[(0, cp, 'close')], dtype=float)).ffill(axis=1).values; spot = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().values; sgn = 1 if cp == 'CE' else -1; Q = P.loc[idx]; ki = Q.strike.map(lambda k: si.get(int(k), -1)).values; j = Q.j.values
    for w in W:
        a = np.where(ki >= 0, px[np.maximum(ki, 0), np.maximum(j - 1, 0)], np.nan); b = np.where(ki >= 0, px[np.maximum(ki, 0), np.maximum(j - 1 - w, 0)], np.nan); new[f'lot_pct{w}'][idx] = (a / b - 1) * 100; new[f'spot_adv{w}'][idx] = sgn * (spot[np.maximum(j - 1, 0)] / spot[np.maximum(j - 1 - w, 0)] - 1) * 100
for k, v in new.items(): P[k] = v
P['yB'] = (P.resid_n.fillna(0) > 0).astype(int); P['yA'] = (P.bb_lots > 0).astype(int); yrs = sorted(P.expiry.unique()); med = yrs[len(yrs) // 2]; P['half'] = np.where(P.expiry < med, 'first', 'second'); R['split'] = med
bins = {'lot_pct1': [-100, -2, -0.5, 0, 0.5, 1, 2, 3, 5, 100], 'lot_pct3': [-100, -2, -0.5, 0, 1, 2, 3, 5, 8, 100], 'lot_pct5': [-100, -2, 0, 1, 2, 4, 6, 10, 100], 'spot_adv1': [-100, -0.1, -0.03, 0, 0.03, 0.06, 0.1, 100], 'spot_adv3': [-100, -0.1, -0.03, 0, 0.05, 0.1, 0.2, 100]}
rows = []
for sub, Q0 in (('all', P), ('first half', P[P.half == 'first']), ('second half', P[P.half == 'second']), ('NIFTY', P[P.und == 'NIFTY']), ('SENSEX', P[P.und == 'SENSEX'])):
    for v, b in bins.items():
        for tgt in ('yB', 'yA'):
            t = Q0.groupby(pd.cut(Q0[v], b), observed=False)[tgt].agg(n='size', ev='sum'); t['per1000'] = t.ev / t.n * 1000; t = t.reset_index().rename(columns={v: 'bin'}); t.insert(0, 'target', tgt); t.insert(0, 'var', v); t.insert(0, 'subset', sub); rows.append(t)
H = pd.concat(rows).assign(bin=lambda d: d['bin'].astype(str)); H.to_csv(f'{OUT}/bl_book_lotshape.csv', index=False)
for v in ('lot_pct1', 'lot_pct3', 'spot_adv1'):
    t = H[(H['var'] == v) & (H.target == 'yB')].pivot(index='bin', columns='subset', values='per1000').round(1); n = H[(H['var'] == v) & (H.target == 'yB') & (H.subset == 'all')].set_index('bin')[['n', 'ev']]; t['n(all)'] = n.n; t['events(all)'] = n.ev; order = H[(H['var'] == v) & (H.target == 'yB') & (H.subset == 'all')].bin.tolist(); print(f'\nresidual (target B) hazard per 1000 contract-minutes by {v} (% change over the window; spot in % adverse)'); print(t.reindex(order)[['all', 'first half', 'second half', 'NIFTY', 'SENSEX', 'n(all)', 'events(all)']].to_string())
thr = []; base = P.yB.mean()
for v in ('lot_pct1', 'lot_pct3', 'lot_pct5'):
    for X in (0.5, 1, 2, 3, 5, 8):
        m = (P[v] >= X); thr.append((v, X, int(m.sum()), int(P.yB[m].sum()), P.yB[m].mean(), base, P.yB[m].mean() / base, P.yB[m].sum() / P.yB.sum()))
T = pd.DataFrame(thr, columns=['variable', 'rise_pct_ge', 'contract_minutes', 'events', 'hazard', 'base', 'lift', 'recall']).round(4); T.to_csv(f'{OUT}/bl_book_lotthr.csv', index=False); print('\nthreshold table (residual buy-backs; lot premium rise >= X% over the window):'); print(T.to_string(index=False))
R['base_hazard'] = float(base); R['n_rows'] = len(P); R['n_events_B'] = int(P.yB.sum()); R['thr'] = T.to_dict('list'); rec('book8', R)
