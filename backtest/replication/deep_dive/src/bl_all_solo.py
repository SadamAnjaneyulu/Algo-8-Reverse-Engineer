"""Solo-sell check for the combined reconstruction: (1) where the real solo lots sit (time of day, order size); (2) the stated fresh-extreme rule on closes vs on true one-minute highs/lows, N = 5-60, inside 09:15-15:00 and over the full day.
Outputs bl_all_solo_where.csv, bl_all_solo_rules.csv, bl_summary_all2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_all_sells.py').read().split("ACT = {d['cid']")[0])
R = {}; ACT = {d['cid']: actual(d) for d in CYC}
A = pd.concat([ACT[i].assign(cid=i) for i in ACT]); S = A[A.typ == 'solo'].copy(); S['hour_block'] = pd.cut((33300 + 60 * S.j) / 3600, [9.25, 10.5, 12, 13.5, 15, 15.5], labels=['09:15-10:30', '10:30-12:00', '12:00-13:30', '13:30-15:00', '15:00-15:30'])
# order size of each solo lot
O1 = O[(O.dayno == 0) & (O.module == 'num') & (O.role == 'open_short')]; big = O1[O1.lots >= 3]; R['solo_lots_in_orders_ge3'] = int(big.lots.sum())
wh = S.groupby('hour_block', observed=True).size().rename('solo_lots').reset_index(); wh['share'] = wh.solo_lots / wh.solo_lots.sum(); wh['CE_share'] = S.groupby('hour_block', observed=True).cp.apply(lambda x: (x == 'CE').mean()).values; wh.round(3).to_csv(f'{OUT}/bl_all_solo_where.csv', index=False); print(wh.round(3).to_string(index=False)); R['where'] = wh.round(4).to_dict('records')
def solo_preds(d, N, src, j_end=374):
    K = np.array(ch.cyc(d['und'], d['expiry'])['strikes'], float); near = lambda x: K[np.argmin(np.abs(K - x))]; c, h, l = d['c'], d['h'], d['l']; out = []
    for j in range(N + 1, j_end + 1):
        if src == 'close':
            p = c[j - 1]; w = c[j - 1 - N:j - 1]; lo_, hi_ = p < w.min(), p > w.max()
        else:
            lo_ = l[j] < l[j - N:j].min(); hi_ = h[j] > h[j - N:j].max()
        if lo_: out.append(dict(j=j, cp='CE', strike=int(near(c[j - 1])), typ='solo'))
        elif hi_: out.append(dict(j=j, cp='PE', strike=int(near(c[j - 1])), typ='solo'))
    return pd.DataFrame(out)
rows = []
for src in ('close', 'true high/low (intrabar)'):
    for N in (5, 15, 30, 60):
        for j_end, lab in ((374, 'full day'), (344, 'until 15:00')):
            na = npd = nm = 0
            for d in CYC:
                a = ACT[d['cid']]; a = a[(a.typ == 'solo') & (a.j <= j_end)]; p = solo_preds(d, N, 'close' if src == 'close' else 'hl', j_end); m = match(a, p, 1); na += len(a); npd += len(p); nm += len(m)
            rows.append(dict(price=src, lookback_min=N, window=lab, actual=na, predicted=npd, matched=nm, precision=nm / npd, recall=nm / na, F1=2 * nm / (na + npd)))
SR = pd.DataFrame(rows); SR.round(4).to_csv(f'{OUT}/bl_all_solo_rules.csv', index=False); print(SR.round(3).to_string(index=False)); R['rules'] = SR.round(4).to_dict('records'); rec('all2', R)
