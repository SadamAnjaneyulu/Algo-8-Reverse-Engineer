"""Sizing study step 1 (plan BODY_SIZING_PLAN.md): unit constancy, pair/solo tables, change-point scan, modal timetables V1/V2.
Outputs: outputs/bl_size_pairs.csv (every pair, D-1 and D0), bl_size_solo.csv (every non-paired body open_short), bl_size_unit.csv, bl_size_cycles.csv, bl_size_changepoint.csv, bl_size_timetable.csv, bl_summary_size1.json"""
import sys, math, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from functools import reduce
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); R = {}; ch = Chain()
# ---- 1. unit constancy from the raw ledger
D = pd.read_csv(f'{ref.__dict__.get("LEDGER", "/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv")}', header=None, dtype=str, usecols=[12, 19, 23], low_memory=False); D.columns = ['und', 'qty', 'ts']; D['qty'] = pd.to_numeric(D.qty, errors='coerce'); D['month'] = pd.to_datetime(D.ts, format='%m/%d/%Y %H:%M', errors='coerce').dt.to_period('M').astype(str)
U = D.dropna(subset=['qty']).groupby(['und', 'month']).qty.agg(['min', 'max', 'count', lambda s: reduce(math.gcd, s.astype(int).tolist())]).reset_index(); U.columns = ['und', 'month', 'min_qty', 'max_qty', 'fills', 'gcd']; U.to_csv(f'{OUT}/bl_size_unit.csv', index=False); print(U.to_string(index=False)); R['unit_gcd'] = {f'{r.und}|{r.month}': int(r.gcd) for r in U.itertuples()}
# ---- 2. pairs and solos
S = O[(O.module == 'num') & (O.role == 'open_short')].copy(); S['clock'] = S.tod; pr = []; used_all = set()
for (u, e, d), g in S.groupby(['und', 'expiry', 'dayno']):
    ce = g[g.cp == 'CE'].sort_values('te'); pe = g[g.cp == 'PE'].sort_values('te'); used = set()
    for r in ce.itertuples():
        m = pe[(pe.strike == r.strike) & ((pe.te - r.te).abs() <= 3) & (~pe.index.isin(used))]
        if len(m): p = m.iloc[0]; used.add(p.name); used_all.update([r.Index, p.name]); pr.append((u, e, 'D-1' if d == 0 else 'D0', int(r.strike), r.te, r.tod, int(r.lots), int(p.lots), r.cls, r.atm_prev))
P = pd.DataFrame(pr, columns=['und', 'expiry', 'day', 'strike', 'te', 'tod', 'lots_ce', 'lots_pe', 'cls', 'atm_prev']); P['k'] = ((P.tod - 33360 + 30) // 900).astype(int); P['off'] = (P.tod - 33360 + 30) % 900 - 30; P['secs_from_open'] = P.tod - 33360
So = S[~S.index.isin(used_all)].copy(); So['day'] = np.where(So.dayno == 0, 'D-1', 'D0'); So['k'] = ((So.tod - 33360 + 30) // 900).astype(int); So['off'] = (So.tod - 33360 + 30) % 900 - 30
P.to_csv(f'{OUT}/bl_size_pairs.csv', index=False); So[['und', 'expiry', 'day', 'cp', 'strike', 'te', 'tod', 'lots', 'cls', 'k', 'off', 'px_avg']].to_csv(f'{OUT}/bl_size_solo.csv', index=False)
d1 = S[S.dayno == 0]; R['d1_sold_lots'] = int(d1.lots.sum()); R['d1_pair_lots'] = int(P[P.day == 'D-1'][['lots_ce', 'lots_pe']].sum().sum()); R['d1_pairs'] = int((P.day == 'D-1').sum()); R['d1_solo_lots'] = int(So[So.day == 'D-1'].lots.sum()); R['d1_orders_1lot_share'] = float((d1.lots == 1).mean()); R['pair_lots_all_1'] = float(((P.lots_ce == 1) & (P.lots_pe == 1)).mean())
print(f"D-1 sold lots {R['d1_sold_lots']}: in pairs {R['d1_pair_lots']} ({R['d1_pair_lots'] / R['d1_sold_lots']:.3f}), solo {R['d1_solo_lots']}; pairs with 1+1 lots: {R['pair_lots_all_1']:.4f}")
# ---- 3. change-point scan on D-1 scheduled-cell counts
cy = cyc[cyc.has_d1].reset_index(drop=True)
def cellvec(u, e):
    x = P[(P.day == 'D-1') & (P.und == u) & (P.expiry == e) & (P.k <= 13)]; v = np.zeros((14, 3)); 
    for r in x.itertuples():
        c = 0 if r.off < 3 else (1 if r.off < 45 else 2) if r.off < 100 else None
        if c is not None: v[r.k, c] += 1
    return v.ravel()
V = np.array([cellvec(u, e) for u, e in zip(cy.und, cy.expiry)]); cy['d1'] = pd.to_datetime(cy.d1); order = np.argsort(cy.d1.values); res = []
for i in range(2, len(order) - 1):
    a, b = V[order[:i]], V[order[i:]]; cost = ((a - np.median(a, axis=0)) ** 2).sum() + ((b - np.median(b, axis=0)) ** 2).sum(); res.append((cy.d1.iloc[order[i - 1]].date(), cy.d1.iloc[order[i]].date(), i, cost))
CP = pd.DataFrame(res, columns=['last_D-1_in_early_group', 'first_D-1_in_late_group', 'n_early', 'within_group_cost']).sort_values('within_group_cost'); CP.to_csv(f'{OUT}/bl_size_changepoint.csv', index=False); print('\nchange-point scan (lowest within-group cost = best split):'); print(CP.head(5).to_string(index=False)); best = CP.iloc[0]; R['changepoint'] = [str(best.iloc[0]), str(best.iloc[1]), float(best.within_group_cost), float(CP.iloc[1].within_group_cost)]
cy['version'] = np.where(cy.d1 >= pd.Timestamp(best.iloc[1]), 'V2', 'V1'); cy['d1_str'] = cy.d1.dt.strftime('%Y-%m-%d'); R['n_V1'] = int((cy.version == 'V1').sum()); R['n_V2'] = int((cy.version == 'V2').sum())
# ---- 4. notional per lot at the D-1 open (unit x spot) and modal timetable
rows = []
for r in cy.itertuples():
    c = ch.cyc(r.und, r.expiry); sp = float(c[(0, 'spot')][1]) if np.isfinite(c[(0, 'spot')][1]) else np.nan; rows.append((r.und, r.expiry, r.d1_str, r.version, ref.LOT[r.und], sp, ref.LOT[r.und] * sp))
CY = pd.DataFrame(rows, columns=['und', 'expiry', 'd1', 'version', 'unit', 'spot_d1_open', 'notional_per_lot']); CY.to_csv(f'{OUT}/bl_size_cycles.csv', index=False)
print('\nnotional per lot (unit x spot, Rs lakh) by underlying and version:'); print((CY.groupby(['und', 'version']).notional_per_lot.agg(['count', 'mean', 'min', 'max']) / [1, 1e5, 1e5, 1e5]).round(2).to_string())
Pd1 = P[P.day == 'D-1'].merge(CY[['und', 'expiry', 'version']], on=['und', 'expiry']); Pd1['sec'] = Pd1.secs_from_open; TT = []
for v in ('V1', 'V2'):
    n = (CY.version == v).sum(); x = Pd1[(Pd1.version == v)].sort_values('sec'); 
    # cluster pair times (seconds from 09:16:00) across cycles of the version: 1-D clustering with 3 s tolerance on the in-block offset + block
    x = x.assign(key=x.k * 1000 + x.off.round(0)); cnt = x.groupby('key').agg(n=('sec', 'size'), k=('k', 'first'), off=('off', 'median'), cycles=('expiry', 'nunique')); cnt['freq'] = cnt.cycles / n; cnt.insert(0, 'version', v); TT.append(cnt.reset_index(drop=True))
TT = pd.concat(TT); TT.to_csv(f'{OUT}/bl_size_timetable_raw.csv', index=False)
rec('size1', R)
