"""Buy-back third pass, step 5: adverse spot move since the lot's sale (strike steps; + = against this lot: up for calls, down for puts), per sell type, on the lot panel; hazard by adverse steps x ratio band; out-of-fold per-type rules (lot level, +-1 min):
scheduled: ratio_h >= a ; reactive / solo / late: adverse steps >= d OR ratio_h >= a2. Outputs bl_bt_adv.csv, bl_summary_bt5.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); X = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); R = {}
adv = np.zeros(len(X)); ci = X.cid.values; jj = X.j.values; je = X.j.values - X.held.values; sg = np.where(X.cp.values == 'CE', 1, -1)
for i, r in enumerate(CY.itertuples()):
    m = ci == i; c = OH[(r.und, r.expiry)].close.values; st = ref.STEP[r.und]; adv[m] = sg[m] * (c[jj[m] - 1] - c[np.maximum(je[m] - 1, 0)]) / st
X['adv'] = adv; X.to_pickle(f'{OUT}/bl_bt_lot.pkl.gz')
for t, g in X[X.typ.isin(['scheduled', 'reactive', 'solo'])].groupby('typ'):
    t2 = g.groupby(pd.cut(g.adv, [-99, 0, 0.5, 1, 1.5, 2, 2.5, 3, 4, 99]), observed=True).y.agg(['mean', 'size']); print(t, {str(k): (round(a * 100, 2), int(n)) for k, (a, n) in t2.iterrows()})
# per-type lot-level rules, out-of-fold; scoring: each real lot buy-back minute vs predicted first-fire minute of that lot (+-1)
lots = X.groupby('lid').agg(cid=('cid', 'first'), typ=('typ', 'first'), bbj=('bb_j', 'first')).reset_index()
def fire_minutes(sub, cond):
    f = sub[cond].groupby('lid').j.min(); return f
def score(cond, mask_lots):
    sub = X[X.lid.isin(mask_lots)]; f = fire_minutes(sub, cond[X.lid.isin(mask_lots).values]); L = lots[lots.lid.isin(mask_lots)].set_index('lid')
    pred = L.index.map(f); real = L.bbj; tp = int(((~pd.isna(pred)) & (~real.isna()) & (np.abs(pd.Series(pred, index=L.index).astype(float) - real) <= 1)).sum())
    npred = int((~pd.isna(pred)).sum()); nreal = int((~real.isna()).sum()); return 2 * tp / max(npred + nreal, 1), tp / max(npred, 1), tp / max(nreal, 1)
h_cyc = X.cid.values % 2 == 0; rows = []
for typ in ('scheduled', 'reactive', 'solo'):
    tl = lots[lots.typ == typ]; tr_l = tl[tl.cid % 2 == 0].lid.values; te_l = tl[tl.cid % 2 == 1].lid.values
    for fam in ('premium only', 'adverse steps only', 'steps OR premium'):
        grid = [(a, None) for a in np.arange(1.3, 1.91, 0.05)] if fam == 'premium only' else ([(None, d) for d in np.arange(0.5, 4.01, 0.25)] if fam == 'adverse steps only' else [(a, d) for a in np.arange(1.5, 1.91, 0.1) for d in np.arange(0.5, 4.01, 0.25)])
        def cond(p):
            a, d = p; cc = np.zeros(len(X), bool)
            if a is not None: cc |= X.ratio_h.values >= a
            if d is not None: cc |= X.adv.values >= d
            return cc
        oof = []
        for tr, te in ((tr_l, te_l), (te_l, tr_l)):
            b = max(grid, key=lambda p: score(cond(p), tr)[0]); oof.append((b, *score(cond(b), te)))
        rows.append(dict(type=typ, family=fam, params=str([tuple(np.round([v for v in o[0] if v is not None], 2)) for o in oof]), F1=np.mean([o[1] for o in oof]), precision=np.mean([o[2] for o in oof]), recall=np.mean([o[3] for o in oof]))); print(rows[-1])
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_bt_adv.csv', index=False); R['rules'] = T.round(4).to_dict('records'); rec('bt5', R)
