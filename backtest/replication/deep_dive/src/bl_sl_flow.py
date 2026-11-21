"""After-15:00 solo, step 2: order-flow linkage. (a) For each late regular solo sale vs random control seconds in 15:00-15:30: share with an order of each module/role/leg within windows before/after; (b) per cycle: late solo lots vs late lump (v_) lots, buy-backs, wing closes, reactive/scheduled lots, premium received vs premium paid for late longs.
Outputs bl_sl_flow.csv, bl_sl_cycle.csv, bl_summary_sl2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); R = {}; rng = np.random.default_rng(11)
L = D[(D.typ == 'solo') & ~D.deep & (D.te >= 54000)]
O1 = O[(O.dayno == 0)].copy(); O1['kind'] = O1.module + ' | ' + O1.role + ' | ' + O1.cp
# mark pair membership of body sells for the flow table
pk = D[D.typ != 'solo'][['cid', 'te', 'cp', 'strike', 'typ']]
rows = []
for lo, hi, nm in ((-120, -1, 'before 2 min'), (-10, -1, 'before 10 s'), (1, 10, 'after 10 s'), (1, 120, 'after 2 min')):
    for kind in sorted(O1.kind.unique()):
        ev = []; ct = []
        for i, r in enumerate(CY.itertuples()):
            t = np.sort(O1[(O1.und == r.und) & (O1.expiry == r.expiry) & (O1.kind == kind)].te.values); q = L[L.cid == i].te.values; c = rng.uniform(54000, 55800, 60)
            for arr, lst in ((q, ev), (c, ct)): lo_i = np.searchsorted(t, arr + lo, 'left'); hi_i = np.searchsorted(t, arr + hi, 'right'); lst += list(hi_i > lo_i)
        if np.mean(ev) > 0.03: rows.append(dict(window=nm, order_kind=kind, share_late_solo=np.mean(ev), share_controls=np.mean(ct), lift=np.mean(ev) / max(np.mean(ct), 1e-3)))
F = pd.DataFrame(rows).sort_values(['window', 'lift'], ascending=[True, False]); F.round(3).to_csv(f'{OUT}/bl_sl_flow.csv', index=False); print(F.groupby('window').head(5).round(3).to_string(index=False))
cy = []
for i, r in enumerate(CY.itertuples()):
    z = O1[(O1.und == r.und) & (O1.expiry == r.expiry) & (O1.te >= 54000)]; l = L[L.cid == i]; dd = D[(D.cid == i) & (D.te >= 54000)]
    cy.append(dict(cid=i, late_solo_lots=int(l.lots.sum()), late_solo_premium=float((l.lots * l.px).sum()), lump_lots=int(z[z.module == 'v_'].lots.sum()), lump_premium=float((z[z.module == 'v_'].lots * z[z.module == 'v_'].px_avg).sum()), buyback_lots=int(z[z.role == 'cover_short'].lots.sum()),
                   wing_close_lots=int(z[(z.role == 'close_long')].lots.sum()), wing_open_lots=int(z[(z.module == 'h_') & (z.role == 'open_long')].lots.sum()), react_lots_late=int(dd[dd.typ == 'reactive'].lots.sum()), deep_lots=int(dd[dd.deep].lots.sum()), solo_before_15=int(D[(D.cid == i) & (D.typ == 'solo') & ~D.deep & (D.te < 54000)].lots.sum()), unit=r.unit, und=r.und))
C = pd.DataFrame(cy); C.to_csv(f'{OUT}/bl_sl_cycle.csv', index=False)
for v in ('lump_lots', 'lump_premium', 'buyback_lots', 'wing_close_lots', 'react_lots_late', 'deep_lots', 'solo_before_15'): rr = spearmanr(C.late_solo_lots, C[v]); R[f'rho_{v}'] = [float(rr[0]), float(rr[1])]
rr = spearmanr(C.late_solo_premium, C.lump_premium); R['rho_premium_solo_vs_lump'] = [float(rr[0]), float(rr[1])]; print({k: [round(x, 3) for x in v] for k, v in R.items()}); R['flow'] = F.round(4).to_dict('records'); rec('sl2', R)
