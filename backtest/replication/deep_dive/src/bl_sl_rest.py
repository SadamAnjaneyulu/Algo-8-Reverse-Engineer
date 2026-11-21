"""After-15:00 solo, step 5: classify every late solo lot by its nearest explanation (post-hoc decomposition, labelled):
E = same-minute fresh 15-min extreme on its right (CE: new low, PE: new high, true 1-min OHLC); B = cross-right body buy-back within 10 s; W = wing (h_) close/open within 10 s; V = lump (v_) within 30 s; P = scheduled/reactive pair within 10 s; else none. Output bl_sl_class.csv, bl_summary_sl5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OH = bl_ohlc.load(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); R = {}
late = D[(D.typ == 'solo') & ~D.deep & (D.te >= 54000)].copy(); rows = []
for q in late.itertuples():
    r = CY.iloc[q.cid]; o = OH[(r.und, r.expiry)]; h, l = o.high.values, o.low.values; j = min(int(q.j), 374); z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; oth = 'PE' if q.cp == 'CE' else 'CE'; g = Pr[(Pr.und == r.und) & (Pr.expiry == r.expiry)]
    near = lambda m, s: z[m & ((z.te - q.te).abs() <= s)]
    E_ = (l[j] < l[j - 15:j].min()) if q.cp == 'CE' else (h[j] > h[j - 15:j].max())
    B_ = len(near((z.module == 'num') & (z.role == 'cover_short') & (z.cp == oth), 10)) > 0; Bs = len(near((z.module == 'num') & (z.role == 'cover_short') & (z.cp == q.cp), 10)) > 0
    W_ = len(near(z.module == 'h_', 10)) > 0; V_ = len(near(z.module == 'v_', 30)) > 0; P_ = ((g.te - q.te).abs() <= 10).any()
    # premium of the sold contract vs the premium of the buy-back leg it may replace
    rows.append(dict(cid=q.cid, te=q.te, j=q.j, cp=q.cp, lots=q.lots, off=q.off_atm, px=q.px, E=E_, B=B_, Bsame=Bs, W=W_, V=V_, P=P_))
X = pd.DataFrame(rows)
def cls(r):
    if r.E: return 'E extreme'
    if r.B: return 'B cross-right buy-back'
    if r.V: return 'V lump'
    if r.W: return 'W wing'
    if r.P: return 'P pair'
    return 'none'
X['cls'] = X.apply(cls, axis=1); X['minute'] = (X.j - 345).clip(upper=30); X.to_csv(f'{OUT}/bl_sl_class.csv', index=False)
t = X.groupby('cls').lots.agg(['sum', 'size']); t['share_lots'] = t['sum'] / t['sum'].sum(); print(t.round(3)); R['classes'] = t.round(4).reset_index().to_dict('records')
ne = X[~X.E]; R['non_extreme'] = dict(lots=int(ne.lots.sum()), any_coupling=float((ne.B | ne.V | ne.W | ne.P).mean()), B=float(ne.B.mean()), V=float(ne.V.mean()), W=float(ne.W.mean()), P=float(ne.P.mean()))
R['extreme'] = dict(any_coupling=float((X[X.E].B | X[X.E].V | X[X.E].W | X[X.E].P).mean()))
print('non-extreme', R['non_extreme'], 'extreme', R['extreme'])
print(pd.crosstab(X.minute.clip(upper=30).map(lambda m: '15:00' if m == 0 else ('15:01-14' if m < 15 else ('15:15-22' if m < 23 else ('15:23-28' if m < 29 else '15:29+')))), X.cls, values=X.lots, aggfunc='sum').fillna(0).astype(int))
# do the non-extreme late sales sit at a fresh extreme of a longer/other kind (previous minute, 5-min) or at the opposite side?
def f(q, N, jj):
    r = CY.iloc[q.cid]; o = OH[(r.und, r.expiry)]; h, l = o.high.values, o.low.values; return (l[jj] < l[jj - N:jj].min()) if q.cp == 'CE' else (h[jj] > h[jj - N:jj].max())
R['non_extreme_alt'] = dict(bk5_same=float(np.mean([f(q, 5, min(int(q.j), 374)) for q in ne.itertuples()])), bk15_prev2=float(np.mean([f(q, 15, min(int(q.j), 374) - 1) or f(q, 15, min(int(q.j), 374) - 2) for q in ne.itertuples()])))
print(R['non_extreme_alt'])
# direction of the coupling (orders before vs after the sale) and premium state of the sold contract (added after the first pass; post-hoc)
import bl_sd_build
OP = bl_sd_build.load_opt(); add = []
for q in X.itertuples():
    r = CY.iloc[q.cid]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)]; oth = 'PE' if q.cp == 'CE' else 'CE'; j = min(int(q.j), 374)
    b = lambda m, s: z[m & (z.te < q.te) & (z.te >= q.te - s)]; a = lambda m, s: z[m & (z.te > q.te) & (z.te <= q.te + s)]
    op = OP[(r.und, r.expiry)]; K = op['K']; st = z[(z.module == 'num') & (z.role == 'open_short') & (z.te == q.te) & (z.cp == q.cp)].strike; d = {}
    if len(st):
        kk = int(np.where(np.abs(K - st.iloc[0]) < 1)[0][0]); ph, pl = op[(q.cp, 'high')][kk], op[(q.cp, 'low')][kk]; s_ = OH[(r.und, r.expiry)].close.values
        d = dict(prem_newhigh15=ph[j] > np.nanmax(ph[j - 15:j]), prem_newlow15=pl[j] < np.nanmin(pl[j - 15:j]), mv5=(s_[j - 1] - s_[j - 6]) * (1 if q.cp == 'PE' else -1) / ref.STEP[r.und])
    add.append(dict(Wb_close=len(b((z.module == 'h_') & (z.role == 'close_long'), 10)) > 0, Wb_open=len(b((z.module == 'h_') & (z.role == 'open_long'), 10)) > 0, Wa=len(a(z.module == 'h_', 10)) > 0,
                    Bb=len(b((z.module == 'num') & (z.role == 'cover_short') & (z.cp == oth), 10)) > 0, Ba=len(a((z.module == 'num') & (z.role == 'cover_short') & (z.cp == oth), 10)) > 0, Vb=len(b(z.module == 'v_', 60)) > 0,
                    Sb=len(b((z.module == 'num') & (z.role == 'open_short'), 10)) > 0, gap_prev_num=q.te - z[(z.module == 'num') & (z.te < q.te)].te.max(),
                    bb60=len(z[(z.module == 'num') & (z.role == 'cover_short') & ((z.te - q.te).abs() <= 60)]) > 0, v60=len(z[(z.module == 'v_') & ((z.te - q.te).abs() <= 60)]) > 0, **d))
X = pd.concat([X, pd.DataFrame(add)], axis=1); X.to_csv(f'{OUT}/bl_sl_class.csv', index=False)
R['direction'] = {k: dict(extreme=float(X[X.E][k].mean()), non_extreme=float(X[~X.E][k].mean())) for k in ('Wb_close', 'Wb_open', 'Wa', 'Bb', 'Ba', 'Vb', 'Sb', 'bb60', 'v60')}
R['prem_newlow15'] = dict(extreme=float(X[X.E].prem_newlow15.mean()), non_extreme=float(X[~X.E].prem_newlow15.mean())); print(R['direction'], R['prem_newlow15']); rec('sl5', R)
