"""Buy-back second pass, step 1 (plan BUYBACK_STOP2_PLAN.md): contract-minute panel (all D-1 contract-minutes with open body short lots; real ledger before the minute) with the loss gate and stop indicators.
Lot of reference = the cheapest open lot (highest ratio). All indicators causal (bars up to j-1) except the 'h' (current minute high) premium variant.
Output bl_bs_panel.pkl.gz"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); rows = []
def wilder(x, n):
    out = np.full(len(x), np.nan); out[n - 1] = np.nanmean(x[:n])
    for t in range(n, len(x)): out[t] = (out[t - 1] * (n - 1) + x[t]) / n
    return out
def atr(h, l, c, n=14):
    tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]]))); return wilder(tr, n)
def supertrend(h, l, c, n, m):
    a = atr(h, l, c, n); hl2 = (h + l) / 2; ub = hl2 + m * a; lb = hl2 - m * a; fu = ub.copy(); fl = lb.copy(); d = np.ones(len(c))
    for t in range(1, len(c)):
        if np.isnan(a[t]): continue
        fu[t] = ub[t] if (ub[t] < fu[t - 1] or c[t - 1] > fu[t - 1]) or np.isnan(fu[t - 1]) else fu[t - 1]; fl[t] = lb[t] if (lb[t] > fl[t - 1] or c[t - 1] < fl[t - 1]) or np.isnan(fl[t - 1]) else fl[t - 1]
        d[t] = 1 if c[t] > fu[t - 1] else (-1 if c[t] < fl[t - 1] else d[t - 1])
    return d
def psar(h, l, af0=0.02, afm=0.2):
    d = np.ones(len(h)); s = l[0]; ep = h[0]; af = af0; up = True
    for t in range(1, len(h)):
        s = s + af * (ep - s)
        if up:
            if l[t] < s: up = False; s = ep; ep = l[t]; af = af0
            elif h[t] > ep: ep = h[t]; af = min(af + af0, afm)
        else:
            if h[t] > s: up = True; s = ep; ep = h[t]; af = af0
            elif l[t] < ep: ep = l[t]; af = min(af + af0, afm)
        d[t] = 1 if up else -1
    return d
def ema(x, n): a = 2 / (n + 1); o = np.zeros(len(x)); o[0] = x[0]; [o.__setitem__(t, a * x[t] + (1 - a) * o[t - 1]) for t in range(1, len(x))]; return o
def rsi(c, n=14):
    d = np.diff(c, prepend=c[0]); up = wilder(np.clip(d, 0, None), n); dn = wilder(np.clip(-d, 0, None), n); return 100 - 100 / (1 + up / np.where(dn > 0, dn, 1e-9))
for i, r in enumerate(CY.itertuples()):
    o = OH[(r.und, r.expiry)]; h, l, c = o.high.values, o.low.values, o.close.values; st = ref.STEP[r.und]; A = atr(h, l, c); ST1 = supertrend(h, l, c, 10, 3); ST2 = supertrend(h, l, c, 7, 2); PS = psar(h, l); E9, E21 = ema(c, 9), ema(c, 21); RS = rsi(c)
    MA = pd.Series(c).rolling(20).mean().values; SD = pd.Series(c).rolling(20).std().values
    op = OP[(r.und, r.expiry)]; K = op['K']; ki = {int(k): x for x, k in enumerate(K)}; oatr = {}
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['te', 'row']); zl = list(z.itertuples()); p = 0; book = {}
    bbj = z[z.role == 'cover_short'].assign(j=lambda d: ((d.te - 33300) // 60).astype(int)).groupby(['cp', 'strike', 'j']).lots.sum().to_dict()
    for j in range(3, 375):
        T0 = 33300 + 60 * j
        while p < len(zl) and zl[p].te < T0:
            q = zl[p]; k = (q.cp, int(q.strike))
            if q.role == 'open_short': book.setdefault(k, []).extend([(q.ref_px, int((q.te - 33300) // 60))] * int(q.lots))
            elif book.get(k): book[k].pop(int(np.argmin([x[0] for x in book[k]])))
            p += 1
        for (cp, kk), lots in book.items():
            if not lots or kk not in ki: continue
            x = ki[kk]; sg = 1 if cp == 'CE' else -1; e, je = min(lots, key=lambda t: t[0]); je = max(je, 1)
            if (cp, kk) not in oatr: oatr[(cp, kk)] = atr(op[(cp, 'high')][x], op[(cp, 'low')][x], op[(cp, 'close')][x])
            pc = op[(cp, 'close')][x, j - 1]; ph = op[(cp, 'high')][x, j]; plo = np.nanmin(op[(cp, 'low')][x, je:j]) if j > je else pc
            sp_e = c[je - 1]; best = (l[je:j].min() if sg > 0 else h[je:j].max()) if j > je else sp_e     # most favourable spot since entry (low for short CE)
            a_ = A[j - 1]
            rows.append(dict(cid=i, j=j, cp=cp, strike=kk, y=int(bbj.get((cp, kk, j), 0) > 0), n_y=int(bbj.get((cp, kk, j), 0)), n_open=len(lots), mins_since_entry=j - je,
                             ratio_c=pc / e, ratio_h=ph / e, loss_pts=pc - e, loss_patr=(pc - e) / oatr[(cp, kk)][j - 1] if oatr[(cp, kk)][j - 1] > 0 else np.nan, trail_prem=pc / plo if plo > 0 else np.nan,
                             adv_steps=sg * (c[j - 1] - sp_e) / st, adv_atr=sg * (c[j - 1] - sp_e) / a_ if a_ > 0 else np.nan, adv_pct=sg * (c[j - 1] / sp_e - 1) * 100,
                             chand_atr=sg * (c[j - 1] - best) / a_ if a_ > 0 else np.nan,
                             st1_against=int(ST1[j - 1] == sg), st1_flip=int(ST1[j - 1] == sg and ST1[j - 2] != sg), st2_against=int(ST2[j - 1] == sg), st2_flip=int(ST2[j - 1] == sg and ST2[j - 2] != sg),
                             psar_against=int(PS[j - 1] == sg), psar_flip=int(PS[j - 1] == sg and PS[j - 2] != sg),
                             don20=int(sg * (c[j - 1] - (h[j - 21:j - 1].max() if sg > 0 else l[j - 21:j - 1].min())) > 0) if j > 22 else 0, don60=int(sg * (c[j - 1] - (h[max(j - 61, 0):j - 1].max() if sg > 0 else l[max(j - 61, 0):j - 1].min())) > 0) if j > 3 else 0,
                             boll=int(sg * (c[j - 1] - (MA[j - 1] + sg * 2 * SD[j - 1])) > 0) if j > 21 else 0, ema_against=int(np.sign(E9[j - 1] - E21[j - 1]) == sg), ema_cross=int(np.sign(E9[j - 1] - E21[j - 1]) == sg and np.sign(E9[j - 2] - E21[j - 2]) != sg),
                             rsi_against=sg * (RS[j - 1] - 50), vel3=pc / op[(cp, 'close')][x, max(j - 4, 0)] if op[(cp, 'close')][x, max(j - 4, 0)] > 0 else np.nan))
X = pd.DataFrame(rows); X['gate'] = (X.ratio_c > 1).astype(int); X['gate_h'] = (X.ratio_h > 1).astype(int); X.to_pickle(f'{OUT}/bl_bs_panel.pkl.gz')
print(X.shape, 'buy-back minutes', int(X.y.sum()), 'in gate', int(X[X.gate == 1].y.sum()), 'gate rows', int(X.gate.sum()), 'gate_h', int(X[X.gate_h == 1].y.sum()))
