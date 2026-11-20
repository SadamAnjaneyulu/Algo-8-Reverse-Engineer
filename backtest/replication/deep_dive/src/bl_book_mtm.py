"""Book-level P&L panel (plan BODY_CLOSE_CAPITAL_PLAN.md). Per cycle and minute: cumulative LTP-marked P&L of the whole ledger (all modules, fill-priced cash + contract-level net positions marked at the previous completed minute close; D0 minute 0 at the D0 open), split by right,
day-start offset, running peak / drawdown, changes over 5/15/30 min, share of open lots without a chain price. Output outputs/bl_book_panel.csv.gz. Validation: flat-end cycles, MTM == realised cash."""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); LOT = ref.LOT; rows = []; val = []
for u, e, hd1, hd0 in zip(cyc.und, cyc.expiry, cyc.has_d1, cyc.has_d0):
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); si = c['_si']; nk = len(K); lot = LOT[u]
    E = O[(O.und == u) & (O.expiry == e)].sort_values(['te', 'row']); evs = list(E.itertuples()); ptr = 0
    net = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; last = {'CE': np.zeros(nk), 'PE': np.zeros(nk)}; xnet = {}; xlast = {}; cash = {'CE': 0.0, 'PE': 0.0}
    def apply(r):
        sgn = 1 if r.side == 'Buy' else -1; k = si.get(int(r.strike)); cash[r.cp] += -sgn * r.lots * r.px_avg * lot
        if k is None: xnet[(r.cp, int(r.strike))] = xnet.get((r.cp, int(r.strike)), 0) + sgn * r.lots; xlast[(r.cp, int(r.strike))] = r.px_avg
        else: net[r.cp][k] += sgn * r.lots; last[r.cp][k] = r.px_avg
    peak = -np.inf; hist = []; start_day = 0.0
    for d, has in ((0, hd1), (1, hd0)):
        if not has: continue
        base = d * 100000
        px = {cp: np.array(c[(d, cp, 'close')], dtype=float) for cp in ('CE', 'PE')}; pxo = {cp: np.array(c[(d, cp, 'open')], dtype=float) for cp in ('CE', 'PE')}
        for cp in ('CE', 'PE'): px[cp] = pd.DataFrame(px[cp]).ffill(axis=1).values
        first = True
        for j in range(0, 375):
            thr = base + ref.OPEN_SEC + j * 60
            while ptr < len(evs) and evs[ptr].te < thr: apply(evs[ptr]); ptr += 1
            m = {}; miss = 0.0; tot = 0.0
            for cp in ('CE', 'PE'):
                p = px[cp][:, j - 1] if j >= 1 else pxo[cp][:, 0]; p = np.where(np.isfinite(p), p, last[cp]); gross = np.abs(net[cp]).sum(); tot += gross
                nanm = ~np.isfinite(px[cp][:, j - 1] if j >= 1 else pxo[cp][:, 0]); miss += np.abs(net[cp])[nanm].sum()
                m[cp] = cash[cp] + float((net[cp] * p).sum()) * lot + sum(v * xlast[(c2, k2)] for (c2, k2), v in xnet.items() if c2 == cp) * lot
            tot += sum(abs(v) for v in xnet.values()); miss += sum(abs(v) for v in xnet.values())
            dm = {}
            for w in (1, 3, 5, 15):
                for cp in ('CE', 'PE'):
                    a = px[cp][:, max(j - 1, 0)] if j >= 1 else pxo[cp][:, 0]; b = px[cp][:, max(j - 1 - w, 0)] if j >= 1 else pxo[cp][:, 0]
                    a = np.where(np.isfinite(a), a, last[cp]); b = np.where(np.isfinite(b), b, a); dm[(w, cp)] = float((net[cp] * (a - b)).sum()) * lot
            B = m['CE'] + m['PE']
            if first: start_day = B; first = False
            peak = max(peak, B); hist.append((u, e, ['D-1', 'D0'][d], j, B, m['CE'], m['PE'], B - start_day, peak - B, miss / tot if tot else 0.0, tot) + tuple(dm[(w, cp)] for w in (1, 3, 5, 15) for cp in ('CE', 'PE')))
        while ptr < len(evs) and evs[ptr].te < base + 100000: apply(evs[ptr]); ptr += 1
    H = pd.DataFrame(hist, columns=['und', 'expiry', 'day', 'j', 'B_total', 'B_CE', 'B_PE', 'B_day', 'DD', 'miss_share', 'open_lots'] + [f'dm{w}_{cp}' for w in (1, 3, 5, 15) for cp in ('CE', 'PE')]); 
    for k in (5, 15, 30): H[f'dB{k}'] = H.groupby('day').B_total.diff(k)
    rows.append(H)
    # validation: flat at the end of the ledger -> MTM equals realised cash
    allnet = sum(np.abs(net[cp]).sum() for cp in net) + sum(abs(v) for v in xnet.values()); val.append((u, e, hd1, hd0, float(allnet), cash['CE'] + cash['PE'], float(H.B_total.iloc[-1]) if len(H) else np.nan))
P = pd.concat(rows); P.to_csv(f'{OUT}/bl_book_panel.csv.gz', index=False); V = pd.DataFrame(val, columns=['und', 'expiry', 'has_d1', 'has_d0', 'end_open_lots', 'cash', 'last_mtm']); V.to_csv(f'{OUT}/bl_book_validation.csv', index=False)
print(P.groupby('day').B_total.describe().round(0).to_string()); print('miss share (open lots without chain price): mean', P.miss_share.mean().round(4), 'p95', P.miss_share.quantile(.95).round(3)); print(V.end_open_lots.eq(0).sum(), 'cycles end flat of', len(V))
F = V[(V.end_open_lots == 0) & V.has_d1 & V.has_d0]; print('flat cycles with both days:', len(F), ' |last_mtm - cash| max', (F.last_mtm - F.cash).abs().max())
