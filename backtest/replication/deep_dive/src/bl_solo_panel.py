"""Solo recall step 1: rebuild the variables of the earlier solo studies (BODY_SELL_TRIGGERS_D1, BODY_SOLO_SELL_MOVE_TEST, BODY_SOLO_VARIABLE_SEARCH) on a D-1 cycle-minute x right panel.
Per (cycle, minute j, right): solo lots sold (label), fresh favourable extreme over N = 5/15/30/60 (closes and true highs/lows), favourable spot move 5/15/30/60 min (steps; + = away from that right's shorts), own-right and other-right short-book price ratio (mark / average entry, body shorts), short lots of each right, position of the previous close in its 15-min range, time of day, slot-minute flag.
Output outputs/bl_solo_panel.pkl.gz"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_all_sells.py').read().split("ACT = {d['cid']")[0])
rows = []
for d in CYC:
    u, e = d['und'], d['expiry']; c_ = ch.cyc(u, e); K = np.array(c_['strikes'], float); ki = {int(k): i for i, k in enumerate(K)}; cl, hi, lo, step = d['c'], d['h'], d['l'], d['step']
    A = actual(d); solo = A[A.typ == 'solo'].groupby(['j', 'cp']).size(); sched_j = set(A[A.typ == 'scheduled'].j)
    z = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & (O.role.isin(['open_short', 'cover_short']))].sort_values(['te', 'row'])
    pos = {}; ptr = 0; zz = list(z.itertuples())
    px = lambda cp, k, j: c_[(0, cp, 'close')][ki[k], j] if k in ki else np.nan
    for j in range(1, 375):
        T0 = 33300 + 60 * j
        while ptr < len(zz) and zz[ptr].te < T0:
            o = zz[ptr]; key = (o.cp, int(o.strike)); n, a = pos.get(key, (0, 0.0))
            if o.role == 'open_short': pos[key] = (n + o.lots, (a * n + o.px_avg * o.lots) / (n + o.lots))
            else: pos[key] = (max(n - o.lots, 0), a)
            ptr += 1
        ratio = {}; lots = {}
        for cp in ('CE', 'PE'):
            num = den = 0.0; L = 0
            for (cpp, k), (n, a) in pos.items():
                if cpp != cp or n <= 0: continue
                p = px(cp, k, j - 1)
                if p == p: num += n * p; den += n * a; L += n
            ratio[cp] = num / den if den > 0 else np.nan; lots[cp] = L
        prev = cl[j - 1]
        for cp in ('CE', 'PE'):
            sgn = -1 if cp == 'CE' else 1          # favourable for a short CE = spot falling; for a short PE = spot rising
            r = dict(cid=d['cid'], und=u, j=j, cp=cp, y=int(solo.get((j, cp), 0) > 0), lots=int(solo.get((j, cp), 0)), slot_minute=int(j in sched_j), hour=T0 / 3600,
                     own_ratio=ratio[cp], other_ratio=ratio['PE' if cp == 'CE' else 'CE'], own_lots=lots[cp], other_lots=lots['PE' if cp == 'CE' else 'CE'])
            for N in (5, 15, 30, 60):
                w = cl[max(j - 1 - N, 0):j - 1]; r[f'fav{N}'] = sgn * (prev - cl[max(j - 1 - N, 0)]) / step
                r[f'bk{N}'] = int(len(w) > 0 and ((prev < w.min()) if cp == 'CE' else (prev > w.max())))
                wl = lo[max(j - N, 0):j]; wh = hi[max(j - N, 0):j]; r[f'bkhl{N}'] = int(len(wl) > 0 and ((lo[j] < wl.min()) if cp == 'CE' else (hi[j] > wh.max())))
            w15 = cl[max(j - 16, 0):j]; r['pos15'] = ((prev - w15.min()) / max(np.ptp(w15), 1e-9)) if cp == 'PE' else ((w15.max() - prev) / max(np.ptp(w15), 1e-9))
            rows.append(r)
P = pd.DataFrame(rows); P.to_pickle(f'{OUT}/bl_solo_panel.pkl.gz'); print(P.shape, 'solo minutes', int(P.y.sum()), 'solo lots', int(P.lots.sum())); print(P.groupby('bk15').y.mean().round(4).to_dict())
