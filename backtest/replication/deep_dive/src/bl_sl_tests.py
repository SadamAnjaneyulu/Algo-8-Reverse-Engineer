"""After-15:00 solo, step 4: H2 financing, H3 inventory shaping, late vs intraday drip (same fresh-extreme rule), clock spikes, out-of-fold minute rule.
Outputs bl_sl_cyc.csv, bl_sl_rule.csv, bl_summary_sl4.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
import bl_ohlc
CY = pd.read_csv(f"{OUT}/bl_size_cycles.csv"); O = load_orders(); OH = bl_ohlc.load(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_sl_panel.pkl.gz'); R = {}; unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}
L = D[(D.typ == 'solo') & ~D.deep]; late = L[L.te >= 54000]; intra = L[(L.te >= 37800) & (L.te < 54000)]
# H2 financing: Rs received by late solo vs Rs paid for late longs (h_/v_/num open_long) per cycle; H3: CE/PE short-lot balance before/after the late window
C = []
for i, r in enumerate(CY.itertuples()):
    u, e = r.und, r.expiry; un = unit[(u, e)]; z = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0)]; zl = z[z.te >= 54000]; lt = late[late.cid == i]
    lg = zl[zl.role == 'open_long']; sh = z[z.module == 'num']
    def short(t, cp): q = sh[(sh.te < t) & (sh.cp == cp)]; return q[q.role == 'open_short'].lots.sum() - q[q.role == 'cover_short'].lots.sum()
    C.append(dict(cid=i, und=u, late_solo_lots=lt.lots.sum(), late_solo_rs=(lt.lots * lt.px).sum() * un, late_long_rs=(lg.lots * lg.px_avg).sum() * un, late_long_lots=lg.lots.sum(), bb_rs=(zl[(zl.module == 'num') & (zl.role == 'cover_short')].pipe(lambda q: (q.lots * q.px_avg).sum())) * un,
                  ce_1500=short(54000, 'CE'), pe_1500=short(54000, 'PE'), ce_1530=short(55800, 'CE'), pe_1530=short(55800, 'PE'), late_ce=lt[lt.cp == 'CE'].lots.sum(), late_pe=lt[lt.cp == 'PE'].lots.sum()))
C = pd.DataFrame(C); C['imb_1500'] = (C.ce_1500 - C.pe_1500) / (C.ce_1500 + C.pe_1500); C['imb_1530'] = (C.ce_1530 - C.pe_1530) / (C.ce_1530 + C.pe_1530); C['late_tilt'] = (C.late_ce - C.late_pe) / (C.late_ce + C.late_pe).replace(0, np.nan)
C.to_csv(f'{OUT}/bl_sl_cyc.csv', index=False)
rho = lambda a, b: spearmanr(C[a], C[b], nan_policy='omit')
R['H2'] = dict(rho_rs_solo_vs_long=list(map(float, rho('late_solo_rs', 'late_long_rs'))), rho_rs_solo_vs_buyback=list(map(float, rho('late_solo_rs', 'bb_rs'))), median_ratio_solo_to_long=float((C.late_solo_rs / C.late_long_rs.replace(0, np.nan)).median()))
R['H3'] = dict(rho_tilt_vs_imb1500=list(map(float, rho('late_tilt', 'imb_1500'))), abs_imb_1500_median=float(C.imb_1500.abs().median()), abs_imb_1530_median=float(C.imb_1530.abs().median()), share_cycles_imb_shrinks=float((C.imb_1530.abs() < C.imb_1500.abs()).mean()))
# lot-level: share of late solo lots on the right with fewer short lots at the moment of the sale
fw = []
for q in late.itertuples():
    r = CY.iloc[q.cid]; sh = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & (O.te < q.te)]
    n = {cp: sh[(sh.cp == cp) & (sh.role == 'open_short')].lots.sum() - sh[(sh.cp == cp) & (sh.role == 'cover_short')].lots.sum() for cp in ('CE', 'PE')}; oth = 'PE' if q.cp == 'CE' else 'CE'
    fw.append(np.sign(n[oth] - n[q.cp]))
fw = np.array(fw); R['H3']['lot_share_on_lighter_side'] = float((fw > 0).mean()); R['H3']['lot_share_on_heavier_side'] = float((fw < 0).mean())
print('H2', R['H2']); print('H3', R['H3'])
# late vs intraday: the same fresh-extreme indicators at solo-sale minutes
def ext(df):
    out = []
    for q in df.itertuples():
        o = OH[(CY.iloc[q.cid].und, CY.iloc[q.cid].expiry)]; h, l = o.high.values, o.low.values; j = min(int(q.j), 374)
        f = lambda N, jj: (l[jj] < l[jj - N:jj].min()) if q.cp == 'CE' else (h[jj] > h[jj - N:jj].max())
        out.append(dict(bk15_same=f(15, j), bk15_prev=f(15, j - 1), bk15_any3=any(f(15, x) for x in (j - 2, j - 1, j)), bk60_same=f(60, j)))
    return pd.DataFrame(out).mean()
R['ext_late'] = ext(late).round(4).to_dict(); R['ext_intra'] = ext(intra).round(4).to_dict(); print('late', R['ext_late']); print('intra', R['ext_intra'])
# base rates in the panel (all minute x right cells) and hazard
X['bk15_prev'] = 0
for i in X.cid.unique():
    o = OH[(CY.iloc[i].und, CY.iloc[i].expiry)]; h, l = o.high.values, o.low.values; m = X.cid == i
    X.loc[m, 'bk15_prev'] = [int((l[j - 1] < l[j - 16:j - 1].min()) if cp == 'CE' else (h[j - 1] > h[j - 16:j - 1].max())) for j, cp in zip(X.j[m], X.cp[m])]
R['hazard'] = {k: dict(base=float(X[k].mean()), p_y_given=float(X.y[X[k] == 1].mean()), p_y_not=float(X.y[X[k] == 0].mean()), recall=float(X[k][X.y == 1].mean())) for k in ('bk5', 'bk15', 'bk60', 'bk15_prev')}
print(pd.DataFrame(R['hazard']).T.round(3))
# clock spikes: share of late solo lots by minute and share with a same-minute fresh 15-min extreme

sp = []
for mm in (345, 368, 374):
    q = late[late.j == mm]; e_ = ext(q) if len(q) else pd.Series(dtype=float); sp.append(dict(minute=f'15:{mm - 345:02d}', lots=int(q.lots.sum()), cycles=int(q.cid.nunique()), bk15_same=float(e_.get('bk15_same', np.nan))))
R['spikes'] = sp; print(pd.DataFrame(sp))
# out-of-fold minute rule on the late panel: fire on a right when (market score) > threshold; score = bk15 + bk5 + pos60 (fixed now); threshold chosen on the other cycle half; +-1 minute tolerance
X['score'] = X.bk15 + X.bk5 + (X.pos60 > 0).astype(int)
def score(sub, thr):
    tp = 0; nfire = 0; npos = 0; hit = 0
    for (c_, cp), g in sub.groupby(['cid', 'cp']):
        f = set(g.j[g.score >= thr]); p = set(g.j[g.y == 1]); nfire += len(f); npos += len(p)
        tp += sum(1 for j in f if {j - 1, j, j + 1} & p); hit += sum(1 for j in p if {j - 1, j, j + 1} & f)
    pr = tp / max(nfire, 1); rc = hit / max(npos, 1); return pr, rc, 2 * pr * rc / max(pr + rc, 1e-9)
rows = []
for half in (0, 1):
    tr = X[X.cid % 2 == half]; te = X[X.cid % 2 != half]; best = max((1, 2, 3), key=lambda t: score(tr, t)[2]); pr, rc, f1 = score(te, best); rows.append(dict(fit_half=half, thr=best, precision=pr, recall=rc, F1=f1))
RU = pd.DataFrame(rows); RU.round(3).to_csv(f'{OUT}/bl_sl_rule.csv', index=False); print(RU.round(3)); R['rule'] = RU.round(4).to_dict('records'); R['rule_F1_mean'] = float(RU.F1.mean()); rec('sl4', R)
