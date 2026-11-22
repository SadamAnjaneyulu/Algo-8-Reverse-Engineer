"""D0 chunk 4 (plan reports/D0_STOP_CLEAR_PLAN.md): S1-S3 cycle stop, C1-C3 15:14 clearance.
S1 cycle MTM in rupees (all modules; cash since the D-1 open + open positions x mark x lot size), cumulative and D0-only (minus the 09:15 open-mark MTM).
S2 marks (previous close / open / adverse intrabar / close of the decision minute) x L x scope; predicted stop = first minute MTM <= -L up to the real stop minute (positions = real orders before the minute);
hit = prediction in [stop minute - tol, stop minute]; later minutes are excluded because their marks include the stop's own liquidation;
cycle-level hits (+-1, +-5 min), early fires, misses; choice on one half (cid parity), scored on the other. S3 stop action (descriptive).
C1 lots per minute 15:00-15:35; C2 which open short / long lots at the 15:09 close are closed from 15:10 on (premium threshold, moneyness threshold; out-of-fold; lot accuracy, AUC); C3 15:14 vs later buy-backs.
Outputs bl_d0x_mtm.pkl.gz, bl_d0x_s2.csv, bl_d0x_s2_oof.csv, bl_d0x_s3.csv, bl_d0x_c1.csv, bl_d0x_c2.csv, bl_d0x_c3.csv, bl_summary_d0x1.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); R = {}
D0C = [i for i, r in enumerate(CY.itertuples()) if ((O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)).any()]
MARKS = ('prev_close', 'open', 'adverse_intrabar', 'close'); MT = {}; STOPJ = {}; missing = [0, 0]
for i in D0C:
    r = CY.iloc[i]; u = float(r.unit); z = O[(O.und == r.und) & (O.expiry == r.expiry)].sort_values(['dayno', 'tod', 'row']); sg = np.where(z.side.str.lower() == 'buy', 1, -1)
    z = z.assign(sg=sg, cash=-sg * z.px_avg * z.lots * u); op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}
    s_ = z[(z.dayno == 1) & (z.module == 's_')]; STOPJ[i] = int(max(0, (s_.tod.min() - 33300) // 60)) if len(s_) else None
    d1 = z[z.dayno == 0]; cash = d1.cash.sum(); pos = d1.groupby(['cp', 'strike']).apply(lambda g: (g.sg * g.lots).sum()).to_dict()
    d0 = z[z.dayno == 1]; tl = d0.tod.values; dl = list(d0.itertuples()); p = 0; out = {m: np.zeros(375) for m in MARKS}
    for j in range(375):
        T0 = 33300 + 60 * j
        while p < len(dl) and dl[p].tod < T0:
            q = dl[p]; k = (q.cp, q.strike); pos[k] = pos.get(k, 0) + q.sg * q.lots; cash += q.cash; p += 1
        for m in MARKS:
            v = cash
            for (cp, k), n in pos.items():
                if n == 0: continue
                x = ki.get(int(k))
                if x is None:
                    if m == 'close' and j == 0: missing[0] += 1
                    continue
                if m == 'prev_close': px = op[(cp, 'close')][x, j - 1] if j > 0 else op[(cp, 'open')][x, 0]
                elif m == 'open': px = op[(cp, 'open')][x, j]
                elif m == 'close': px = op[(cp, 'close')][x, j]
                else: px = op[(cp, 'high')][x, j] if n < 0 else op[(cp, 'low')][x, j]
                if px == px: v += n * px * u
            out[m][j] = v
        if j == 0: missing[1] += sum(1 for n in pos.values() if n != 0)
    MT[i] = out
pd.to_pickle(dict(MT=MT, STOPJ=STOPJ), f'{OUT}/bl_d0x_mtm.pkl.gz'); R['contracts_missing_price_share_at_open'] = missing[0] / max(missing[1], 1)
LS = [1.20, 1.30, 1.35, 1.40, 1.44, 1.50]
def pred(i, m, L, scope):
    x = MT[i][m] - (MT[i]['open'][0] if scope == 'D0-only' else 0); js = STOPJ[i]; lim = js if js is not None else 358; hit = np.where(x[:lim + 1] <= -L * 1e5)[0]; return int(hit[0]) if len(hit) else None
def evalc(cids, m, L, scope, tol=1):
    tp = fp = fn = 0; early = 0
    for i in cids:
        pj = pred(i, m, L, scope); js = STOPJ[i]
        if js is None: fp += pj is not None; early += pj is not None
        elif pj is None: fn += 1
        elif js - tol <= pj <= js: tp += 1
        else: fp += 1; fn += 1; early += 1
    return dict(TP=tp, FP=fp, FN=fn, early=early, F1=2 * tp / max(2 * tp + fp + fn, 1))
rows = []
for m, L, sc in itertools.product(MARKS, LS, ('cumulative', 'D0-only')):
    a = evalc(D0C, m, L, sc); b = evalc(D0C, m, L, sc, 5); rows.append(dict(mark=m, L_lakh=L, scope=sc, hits_pm1=a['TP'], hits_pm5=b['TP'], early_fires=a['early'], misses=a['FN'] - (a['FP'] - a['early'] if False else 0), F1_pm1=a['F1'], F1_pm5=b['F1']))
S2 = pd.DataFrame(rows); S2.to_csv(f'{OUT}/bl_d0x_s2.csv', index=False); R['stop_cycles'] = int(sum(v is not None for v in STOPJ.values())); R['stop_minutes'] = {int(i): v for i, v in STOPJ.items() if v is not None}
oo = []
for h in (0, 1):
    tr = [i for i in D0C if i % 2 != h]; te = [i for i in D0C if i % 2 == h]
    for m in MARKS:
        best = max(itertools.product(LS, ('cumulative', 'D0-only')), key=lambda c: (evalc(tr, m, *c)['F1'], -c[0]))
        a = evalc(te, m, *best); oo.append(dict(half=h, mark=m, L_lakh=best[0], scope=best[1], **a))
OO = pd.DataFrame(oo); OO.to_csv(f'{OUT}/bl_d0x_s2_oof.csv', index=False); print(S2[S2.scope == 'cumulative'].pivot(index='L_lakh', columns='mark', values='F1_pm1').round(2).to_string()); print(S2[S2.scope == 'D0-only'].pivot(index='L_lakh', columns='mark', values='F1_pm1').round(2).to_string())
print(OO.groupby('mark')[['TP', 'FP', 'FN']].sum().to_string())
# MTM at the real stop (close mark of the stop minute) and the minimum MTM before it
R['mtm_at_stop_lakh'] = {int(i): dict(close=float(MT[i]['close'][js] / 1e5), prev_close=float(MT[i]['prev_close'][js] / 1e5), adverse=float(MT[i]['adverse_intrabar'][js] / 1e5), D0only_close=float((MT[i]['close'][js] - MT[i]['open'][0]) / 1e5)) for i, js in STOPJ.items() if js is not None}
R['min_mtm_nonstop_lakh'] = {int(i): dict(close=float(MT[i]['close'][:359].min() / 1e5), adverse=float(MT[i]['adverse_intrabar'][:359].min() / 1e5)) for i, js in STOPJ.items() if js is None}
# ---------------- S3 stop action
s3 = []
for i in D0C:
    js = STOPJ[i]
    if js is None: continue
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)]; s_ = z[z.module == 's_']; t0 = s_.tod.min(); after = z[(z.tod > t0) & (z.module != 's_')]
    s3.append(dict(cid=i, und=r.und, expiry=r.expiry, stop_time=f'{int(t0 // 3600):02d}:{int(t0 % 3600 // 60):02d}:{int(t0 % 60):02d}', s_lots=int(s_.lots.sum()), s_orders=len(s_), s_span_s=float(s_.tod.max() - t0), s_cover_short=int(s_[s_.role == 'cover_short'].lots.sum()), s_close_long=int(s_[s_.role == 'close_long'].lots.sum()),
                   other_orders_after=len(after), other_lots_after=int(after.lots.sum()), body_sell_lots_after=int(after[(after.module == 'num') & (after.role == 'open_short')].lots.sum()), body_cover_lots_after=int(after[(after.module == 'num') & (after.role == 'cover_short')].lots.sum()), last_body_sell_after_s=float(after[(after.module == 'num') & (after.role == 'open_short')].tod.max() - t0) if ((after.module == 'num') & (after.role == 'open_short')).any() else np.nan, other_modules_after='/'.join(sorted(after.module.unique())), mtm_close_lakh=R['mtm_at_stop_lakh'][i]['close']))
S3 = pd.DataFrame(s3); S3.to_csv(f'{OUT}/bl_d0x_s3.csv', index=False); print(S3.to_string(index=False))
# ---------------- C1
d = O[(O.dayno == 1) & (O.tod >= 54000) & (O.tod < 56160)].copy(); d['minute'] = [f'15:{int((t - 54000) // 60):02d}' for t in d.tod]; C1 = d.pivot_table(index='minute', columns=['module', 'role'], values='lots', aggfunc='sum').fillna(0).astype(int); C1.columns = [f'{a} {b}' for a, b in C1.columns]; C1.to_csv(f'{OUT}/bl_d0x_c1.csv')
# ---------------- C2 which open lots at the 15:09 close are closed from 15:10 on
lot = []
for i in D0C:
    if STOPJ[i] is not None: continue
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry)].sort_values(['dayno', 'tod']); sg = np.where(z.side.str.lower() == 'buy', 1, -1); z = z.assign(sg=sg)
    pre = z[(z.dayno == 0) | (z.tod < 54600)]; post = z[(z.dayno == 1) & (z.tod >= 54600)]; pos = pre.groupby(['cp', 'strike']).apply(lambda g: int((g.sg * g.lots).sum())).to_dict()
    op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; s = SPT[(r.und, r.expiry)].close.values[354]; st = ref.STEP[r.und]
    for (cp, k), n in pos.items():
        if n == 0 or int(k) not in ki: continue
        px = op[(cp, 'close')][ki[int(k)], 354]; otm = (k - s) / st * (1 if cp == 'CE' else -1); g = post[(post.cp == cp) & (post.strike == k)]
        closed = int(g[g.sg == (1 if n < 0 else -1)].lots.sum()); closed = min(closed, abs(n))
        for t in range(abs(n)): lot.append(dict(cid=i, side='short' if n < 0 else 'long', cp=cp, strike=k, px=px, otm_steps=otm, y=int(t < closed)))
LT = pd.DataFrame(lot); c2 = []
for side, g in LT.groupby('side'):
    base = max(g.y.mean(), 1 - g.y.mean())
    for rule, grid, f in (('premium >= p*', [0.5, 1, 2, 3, 5, 10], lambda df, p: df.px >= p), ('steps OTM <= k*', [-3, -2, -1, 0, 1, 2, 3], lambda df, k: df.otm_steps <= k)):
        acc = []; ch = []
        for h in (0, 1):
            tr = g[g.cid % 2 != h]; te = g[g.cid % 2 == h]; best = max(grid, key=lambda x: (f(tr, x) == tr.y.astype(bool)).mean()); ch.append(best); acc.append(((f(te, best) == te.y.astype(bool)).sum(), len(te)))
        auc = roc_auc_score(g.y, g.px if rule.startswith('premium') else -g.otm_steps) if g.y.nunique() == 2 else np.nan
        c2.append(dict(lots=side, rule=rule, chosen=' / '.join(map(str, ch)), accuracy_oof=sum(a for a, _ in acc) / sum(b for _, b in acc), majority_class=base, AUC_all=auc, n_lots=len(g), closed_share=g.y.mean()))
C2 = pd.DataFrame(c2); C2.to_csv(f'{OUT}/bl_d0x_c2.csv', index=False); print(C2.round(3).to_string(index=False))
# ---------------- C3 15:14 vs later body buy-backs
bb = O[(O.dayno == 1) & (O.module == 'num') & (O.role == 'cover_short') & (O.tod >= 54600)].copy(); c3 = []
for q in bb.itertuples():
    i = next((c for c in D0C if CY.iloc[c].und == q.und and CY.iloc[c].expiry == q.expiry), None)
    if i is None: continue
    op = OPT[(q.und, q.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; s = SPT[(q.und, q.expiry)].close.values[358]; st = ref.STEP[q.und]
    if int(q.strike) not in ki: continue
    c3.append(dict(window='15:10-15:13' if q.tod < 54840 else ('15:14' if q.tod < 54900 else '15:15+'), lots=q.lots, px_1513=op[(q.cp, 'close')][ki[int(q.strike)], 358], otm_steps=(q.strike - s) / st * (1 if q.cp == 'CE' else -1), fill_px=q.px_avg))
C3 = pd.DataFrame(c3); C3s = C3.groupby('window').apply(lambda g: pd.Series(dict(lots=int(g.lots.sum()), px_median=float(np.median(np.repeat(g.px_1513, g.lots))), px_q90=float(np.percentile(np.repeat(g.px_1513, g.lots), 90)), otm_median=float(np.median(np.repeat(g.otm_steps, g.lots))), share_itm=float((np.repeat(g.otm_steps, g.lots) < 0).mean())))).reset_index()
C3s.to_csv(f'{OUT}/bl_d0x_c3.csv', index=False); w = C3[C3.window != '15:10-15:13']; R['c3_auc_px_1514_vs_later'] = float(roc_auc_score(np.repeat((w.window == '15:14').astype(int), w.lots), np.repeat(w.px_1513, w.lots))); R['c3_auc_itm_1514_vs_later'] = float(roc_auc_score(np.repeat((w.window == '15:14').astype(int), w.lots), -np.repeat(w.otm_steps, w.lots))); print(C3s.round(2).to_string(index=False))
R['c2'] = C2.round(4).to_dict('records'); R['c3'] = C3s.round(3).to_dict('records'); R['oof'] = OO.to_dict('records'); R['s2_close_L_bounds_lakh'] = dict(nonstop_min_close=float(min(v['close'] for v in R['min_mtm_nonstop_lakh'].values())), stop_cycles_close_at_crossing=sorted(round(float(min(MT[i]['close'][max(js - 1, 0):js + 1]) / 1e5), 3) for i, js in STOPJ.items() if js is not None)); rec('d0x1', R)
