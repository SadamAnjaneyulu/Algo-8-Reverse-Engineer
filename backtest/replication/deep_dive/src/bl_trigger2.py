"""Trigger study part 2 (D-1): what precedes a single-leg sale episode?
Episode start = a single-leg (unpaired) body sale on a right with no single-leg sale on that right in the previous 300 s. Risk set = every other minute (not within 300 s after an episode start, not a slot minute) of that cycle-right.
Features are CAUSAL (data up to minute j-1 and orders strictly before minute j). Pre-registered feature list (fixed before running):
 adv1/adv3/adv5/adv15 : signed spot move over the last k minutes in steps, + = adverse to a short of that right (up for CE, down for PE)
 abs5, abs15          : absolute spot move over 5 / 15 minutes
 dev_book             : (spot - weighted-mean short strike of that right) in steps, + = shorts ITM
 ratio_book           : current price / average entry price of the right's short book (>1 = book losing)
 ratio_last           : current price of the last-sold contract / its decision price
 imb                  : shorts of this right minus shorts of the other right (lots)
 S_right              : shorts of this right (lots)
 tsl                  : minutes since the last sale on this right
 tslot                : minutes since the last slot minute
Metric: AUC (episode-start minutes vs risk-set minutes), cluster bootstrap over cycles (400), Holm over the 11 features."""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
O = load_orders(); S = pd.read_pickle(f'{OUT}/bl_trig_sells_d1.pkl.gz'); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); rows = []
OK = [(u, e) for u, e, h in zip(cyc.und, cyc.expiry, cyc.has_d1) if h]
for (u, e) in OK:
    step = ref.STEP[u]; spot = np.array([ch.spot(u, e, 0, j) for j in range(375)]); C = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0)].sort_values(['te', 'row'])
    for cp in ('CE', 'PE'):
        sgn = 1 if cp == 'CE' else -1; me = S[(S.und == u) & (S.expiry == e) & (S.cp == cp)].sort_values('tod'); single = me[~me.paired]; st = single.tod.values
        starts = []; last = -1e9
        for t in st:
            if t - last > 300: starts.append(t)
            last = t
        starts_min = set(int((t - ref.OPEN_SEC) // 60) for t in starts); blocked = set()
        for t in starts: j0 = int((t - ref.OPEN_SEC) // 60); blocked.update(range(j0, j0 + 6))
        c = C[C.cp == cp]; co = C[C.cp != cp]
        for j in range(16, 374):
            slotm = ((j - 1) % 15 == 0)
            if slotm and j not in starts_min: continue
            if j in blocked and j not in starts_min: continue
            T = ref.OPEN_SEC + j * 60; pre = c[c.tod < T]; preo = co[co.tod < T]
            net = pre.groupby('strike').sl.sum(); sh = -net[net < 0]; so = -preo.groupby('strike').sl.sum().clip(upper=0).sum() * -1 if False else (-(preo.groupby('strike').sl.sum()[preo.groupby('strike').sl.sum() < 0]).sum())
            Sr = sh.sum()
            if Sr <= 0: continue
            wk = (sh.index.values * sh.values).sum() / Sr; sp1 = spot[j - 1]
            body_sells = pre[(pre.module == 'num') & (pre.side == 'Sell')]; avg = {}
            for k_, g_ in body_sells.groupby('strike'): avg[k_] = (g_.px_avg * g_.lots).sum() / g_.lots.sum()
            now = {k_: ch.px(u, e, 0, cp, k_, j - 1, 'close') for k_ in sh.index}; ok = [k_ for k_ in sh.index if k_ in avg and now[k_] == now[k_] and avg[k_] > 0]
            rb = sum(sh[k_] * now[k_] for k_ in ok) / sum(sh[k_] * avg[k_] for k_ in ok) if ok else np.nan
            ls = body_sells.iloc[-1] if len(body_sells) else None; rl = ch.px(u, e, 0, cp, ls.strike, j - 1, 'close') / ls.ref_px if ls is not None and ls.ref_px > 0 else np.nan
            lastsale = body_sells.tod.max() if len(body_sells) else np.nan; slot_off = ((j - 1) % 15)
            f = dict(und=u, expiry=e, cp=cp, j=j, event=int(j in starts_min), abs5=abs(sp1 - spot[j - 6]) / step, abs15=abs(sp1 - spot[j - 16]) / step, dev_book=sgn * (sp1 - wk) / step, ratio_book=rb, ratio_last=rl, imb=Sr - so, S_right=Sr, tsl=(T - lastsale) / 60 if lastsale == lastsale else np.nan, tslot=slot_off)
            for k_ in (1, 3, 5, 15): f[f'adv{k_}'] = sgn * (sp1 - spot[j - 1 - k_]) / step
            rows.append(f)
P = pd.DataFrame(rows); P.to_csv(f'{OUT}/bl_trig_panel.csv', index=False); y = P.event.values; print('panel rows', len(P), 'episode starts', int(y.sum()), 'cycles', P.groupby(['und', 'expiry']).ngroups, '| by right', P.groupby('cp').event.sum().to_dict())
feats = ['adv1', 'adv3', 'adv5', 'adv15', 'abs5', 'abs15', 'dev_book', 'ratio_book', 'ratio_last', 'imb', 'S_right', 'tsl', 'tslot']
def auc(x, y): m = ~np.isnan(x); x, y = x[m], y[m]; n1 = y.sum(); n0 = len(y) - n1; r = stats.rankdata(x); return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan
rng = np.random.default_rng(0); cy = (P.und + P.expiry).values; ucy = np.unique(cy); idx = {c: np.where(cy == c)[0] for c in ucy}; res = []
for f in feats:
    x = P[f].values.astype(float); a = auc(x, y); bs = []
    for _ in range(400):
        ii = np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]); b = auc(x[ii], y[ii]); bs.append(b)
    bs = np.array(bs); bs = bs[~np.isnan(bs)]; p = 2 * min((bs <= .5).mean(), (bs >= .5).mean()); res.append((f, a, np.quantile(bs, .025), np.quantile(bs, .975), max(p, 1 / 400), np.isnan(x).mean()))
R = pd.DataFrame(res, columns=['feature', 'AUC', 'lo', 'hi', 'p_boot', 'missing']).sort_values('p_boot'); m = len(R); R['holm_p'] = np.minimum(1, [(m - i) * p for i, p in enumerate(R.p_boot)]); R['holm_p'] = R.holm_p.cummax(); R.round(3).to_csv(f'{OUT}/bl_trig_auc.csv', index=False); print(R.round(3).to_string(index=False))
for cp in ('CE', 'PE'):
    q = P[P.cp == cp]; print(cp, 'episode starts', int(q.event.sum()), '| median adv5 at starts %.2f vs risk set %.2f ; adv15 %.2f vs %.2f ; dev_book %.2f vs %.2f' % (q[q.event == 1].adv5.median(), q[q.event == 0].adv5.median(), q[q.event == 1].adv15.median(), q[q.event == 0].adv15.median(), q[q.event == 1].dev_book.median(), q[q.event == 0].dev_book.median()))
