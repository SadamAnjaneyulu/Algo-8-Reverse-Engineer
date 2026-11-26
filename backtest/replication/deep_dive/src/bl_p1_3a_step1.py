"""P1-3A Step 1 (reports/PHASE1_GATE3A_PLAN.md section 3): quantify buy-back mismatches of B1 as upstream (position differences) versus independent (trigger). No engine change. Evidence: historical reproduction."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S, bl_tfe as T
from d1_algo.book import Book
OUT = bl_common.OUT; B1 = f'{OUT}/scoring/d1_F_v2_onelot'; OPEN_S = 33300; RATIO = 1.6; WIN = 60
real = pd.read_csv(f'{B1}/real_orders.csv'); sim = pd.read_csv(f'{B1}/sim_orders.csv'); P = pd.read_csv(f'{B1}/all/pairs.csv'); real['m'] = False; sim['m'] = False; real.loc[P.ri.values, 'm'] = True; sim.loc[P.si.values, 'm'] = True
real['sidel'] = real.side.str.lower(); sim['sidel'] = sim.side.str.lower(); sim['sec'] = np.floor(sim.t.astype(float)).astype(int)
REAL = S.REAL.copy(); REAL['cyc'] = REAL.und + '|' + REAL.expiry; cyc_ix = {f'{r.und}|{r.expiry}': i for i, r in enumerate(S.CY.itertuples())}; PREP = {c: S.prep(i) for c, i in cyc_ix.items()}
def ratio_of(cyc, cp, k, j, entry, which='high'):
    d = PREP[cyc]; arr = d['op'][(cp, which)]; jb = min(max(j, 0), arr.shape[1] - 1); return float(arr[d['ki'][int(k)], jb] / entry) if entry > 0 else np.nan
def book_before(order_df, cyc):
    """generator-free helper: list of (time, snapshot-callable) is replaced by incremental replay below"""
rows_m, rows_x = [], []
for cyc in sorted(set(real.cyc)):
    R = REAL[REAL.cyc == cyc].sort_values('row'); rr = real[real.cyc == cyc].reset_index(); sm = sim[sim.cyc == cyc].sort_values(['sec', 'seq']).reset_index()
    # real book replay: record the state before each real buy-back (class body_buyback)
    book = Book(); rinfo = {}; ridx = {int(r.row): i for i, r in rr.iterrows()}
    for r in R.itertuples():
        key = (r.cp, float(r.strike))
        if r.module == 'num' and r.role == 'cover_short':
            lots = sorted(book.shorts.get(key, []), key=lambda l: l.entry_price); j = int((r.t_first - OPEN_S) // 60)
            ent = lots[0].entry_price if lots else np.nan; emin = lots[0].minute if lots else None
            rinfo[int(r.row)] = dict(held=len(lots), entry=ent, rh=ratio_of(cyc, r.cp, r.strike, j, ent) if lots else np.nan, rc=ratio_of(cyc, r.cp, r.strike, j - 1, ent, 'close') if lots else np.nan, earlier=(emin is not None and emin < j), real_S={c: sum(len(v) for (cc, _), v in book.shorts.items() if cc == c) for c in ('CE', 'PE')})
        T.apply_real(book, dict(t=int(r.t_first), row=int(r.row), cp=r.cp, strike=float(r.strike), side=r.side, lots=int(r.lots), role=r.role, module=r.module, px=float(r.px_avg)))
    # simulated net position per contract before a second
    def sim_net(sec, cp, k): g = sm[(sm.sec < sec) & (sm.cp == cp) & (sm.strike == k)]; return int((g[g.sidel == 'buy'].lots.sum()) - (g[g.sidel == 'sell'].lots.sum()))
    def sim_S(sec): g = sm[sm.sec < sec]; out = {}; 
    # missing real buy-backs
    for r in rr[(rr.cls == 'body_buyback') & (~rr.m)].itertuples():
        info = rinfo[int(r.row)]; sh = max(-sim_net(int(r.t), r.cp, r.strike), 0); buys = sm[(sm.sidel == 'buy') & (sm.cp == r.cp) & ((sm.sec - r.t).abs() <= WIN)]
        if sh == 0: c = 'U1'
        elif sh < info['held']: c = 'U2'
        elif len(buys): c = 'S'
        elif info['rh'] >= RATIO and info['earlier']: c = 'R1'
        else: c = 'I'
        near = (sm[(sm.sidel == 'buy') & (sm.cp == r.cp)].sec - r.t).abs().min() if len(sm[(sm.sidel == 'buy') & (sm.cp == r.cp)]) else np.nan
        rows_m.append(dict(cyc=cyc, row=int(r.row), t=int(r.t), cp=r.cp, strike=r.strike, cls=c, real_held=info['held'], sim_held=sh, ratio_high=info['rh'], ratio_prev_close=info['rc'], nearest_sim_buy_s=near))
    # extra simulated buy-backs
    rb = rr[rr.sidel == 'buy']
    def real_net_before(sec, cp, k):
        g = rr[(rr.t < sec) & (rr.cp == cp) & (rr.strike == k)]; return int((g[g.sidel == 'buy'].lots.sum()) - (g[g.sidel == 'sell'].lots.sum()))
    for e in sm[(sm.cls == 'body_buyback') & (~sm.m)].itertuples():
        held = max(-real_net_before(int(e.sec), e.cp, e.strike), 0); buys = rb[(rb.cp == e.cp) & ((rb.t - e.sec).abs() <= WIN)]
        if held == 0: c = 'XU'
        elif len(buys): c = 'XS'
        else:
            lots = [l for k_, v in [(None, None)] for l in []]
            # real lot ratio on that contract at the order minute (cheapest-entry lot of the real book at that second)
            b2 = Book()
            for r in R[R.t_first < e.sec].itertuples(): T.apply_real(b2, dict(t=int(r.t_first), row=int(r.row), cp=r.cp, strike=float(r.strike), side=r.side, lots=int(r.lots), role=r.role, module=r.module, px=float(r.px_avg)))
            ls = sorted(b2.shorts.get((e.cp, float(e.strike)), []), key=lambda l: l.entry_price); jj = int((e.sec - OPEN_S) // 60); rh = ratio_of(cyc, e.cp, e.strike, jj, ls[0].entry_price) if ls else np.nan
            c = 'XR' if (ls and rh >= RATIO and ls[0].minute < jj) else 'XI'
        rows_x.append(dict(cyc=cyc, t=int(e.sec), cp=e.cp, strike=e.strike, cls=c, real_held=held))
M = pd.DataFrame(rows_m); X = pd.DataFrame(rows_x); M.to_csv(f'{OUT}/phase1/3A_step1_missing.csv', index=False); X.to_csv(f'{OUT}/phase1/3A_step1_extra.csv', index=False)
res = dict(real_buybacks=int((real.cls == 'body_buyback').sum()), sim_buybacks=int((sim.cls == 'body_buyback').sum()), missing=int(len(M)), extra=int(len(X)))
fc = pd.read_csv(f'{B1}/all/by_class.csv').set_index('cls').loc['body_buyback']; res['reconciles_to_B1_by_class'] = bool(res['real_buybacks'] == int(fc.real) and res['sim_buybacks'] == int(fc.sim))
res['missing_by_class'] = {k: int(v) for k, v in M.cls.value_counts().items()}; res['extra_by_class'] = {k: int(v) for k, v in X.cls.value_counts().items()}
up_m = int(M.cls.isin(['U1', 'U2']).sum()); up_x = int((X.cls == 'XU').sum()); res['missing_upstream'] = dict(n=up_m, share=up_m / len(M)); res['extra_upstream'] = dict(n=up_x, share=up_x / len(X))
res['missing_I_ratio_quantiles'] = M[M.cls == 'I'].ratio_high.quantile([.1, .25, .5, .75, .9]).round(3).to_dict(); res['missing_R1_nearest_sim_s'] = M[M.cls == 'R1'].nearest_sim_buy_s.describe().round(1).to_dict()
res['missing_by_class_median_nearest_sim_buy_s'] = {k: float(v) for k, v in M.groupby('cls').nearest_sim_buy_s.median().items()}
st = pd.read_csv(f'{B1}/all/state_after_matched.csv'); bb = P.merge(real[['cls']], left_on='ri', right_index=True); bbi = bb[bb.cls == 'body_buyback'].ri; stb = st[st.ri.isin(bbi)]; res['matched_buyback_state'] = dict(n=int(len(stb)), SL_equal_share=float(stb.SL_equal.mean()), l1_norm_median=float(stb.l1_norm.median()))
mt = P[P.ri.isin(bbi)]; res['matched_buyback_timing'] = dict(n=int(len(mt)), dt_median=float(mt.dt.median()), dt_quantiles={str(k): float(v) for k, v in mt.dt.quantile([.1, .25, .75, .9]).items()}, strike_exact=float((mt.dstrike == 0).mean()), strike_within1=float((mt.dstrike.abs() <= 1).mean()), lots_exact=float((mt.dlots == 0).mean()))
json.dump(res, open(f'{OUT}/phase1/3A_step1.json', 'w'), indent=1); print(json.dumps(res, indent=1))
