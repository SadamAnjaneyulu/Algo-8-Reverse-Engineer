"""Phase 3 data builder: (1) lot-level table of CARRIED body short lots (opened D-1, open at the D0 open) with D0 price-path statistics; (2) contract-minute panel of D0 body-short contracts with an observed buy-back indicator.
Ownership caveat: which lot a buy-back closed is ambiguous (4 conventions); the contract-minute panel uses only convention-free quantities (total short lots, average and cheapest entry of the open lots), the lot table reports FIFO and the spread across conventions.
Cycles with a known carry-in book only (30)."""
from collections import defaultdict
from ledger import *
from data import load_cycle, NM
L = pd.read_csv(f'{OUT}/lots.csv.gz'); F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); C = C[C.carry_in_known]
CONV = ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST')
lots_out = []; panel = []
def px_arrays(c):
    a = {}
    for r in ('CE', 'PE'):
        x = np.concatenate([c[(0, r, 'close')], c[(1, r, 'close')]], axis=1).copy()
        for j in range(1, x.shape[1]): m = np.isnan(x[:, j]); x[m, j] = x[m, j - 1]
        a[r] = x                                        # columns 0..374 = D-1, 375..749 = D0 (ffilled across the night)
    return a
for r in C.itertuples():
    c = load_cycle(r.und, r.expiry, r.d1, r.d0); ki = {int(k): i for i, k in enumerate(c['strikes'])}; P = px_arrays(c); step = 50 if r.und == 'NIFTY' else 100; spot = np.concatenate([c[(0, 'spot')], c[(1, 'spot')]]); spot = pd.Series(spot).ffill().values
    x = L[(L['index'] == r.und) & (L.expiry == r.expiry) & (L.side == 'SHORT') & (L.role == 'body') & (L.entry_day == r.d1)].copy()
    # ---- lot-level carried table (FIFO primary)
    for l in x.itertuples():
        i = ki.get(l.strike); closed_d0 = (l.close_day == r.d0) and l.close_sec >= 0; close_j = (l.close_sec // 60 - 555) if closed_d0 else None
        path = P[l.cp][i, NM:] if i is not None else np.full(NM, np.nan)
        end = min(close_j, NM - 1) if close_j is not None else NM - 1; seg = path[:max(end, 0) + 1] if close_j is not None else path
        open_px = P[l.cp][i, NM - 1] if i is not None else np.nan
        lots_out.append(dict(lot_id=l.lot_id, cycle_id=l.cycle_id, index=r.und, cp=l.cp, strike=l.strike, entry_day_sec=l.entry_sec, entry_price=l.entry_price, d1_last_price=open_px, d0_open_ratio=open_px / l.entry_price if l.entry_price else np.nan,
                             close_reason_FIFO=l.close_reason, close_sec_FIFO=l.close_sec, close_price_FIFO=l.close_price, closed_on_d0=closed_d0, close_minute_FIFO=close_j, hold_minutes_from_d0_open=(close_j if closed_d0 else np.nan), settled=l.close_reason == 'SETTLEMENT',
                             mfe_pts=(l.entry_price - np.nanmin(seg)) if len(seg) and not np.all(np.isnan(seg)) else np.nan, mae_pts=(np.nanmax(seg) - l.entry_price) if len(seg) and not np.all(np.isnan(seg)) else np.nan,
                             off_steps_at_d0_open=(l.strike - spot[NM - 1]) / step, itm_at_d0_open=bool((l.cp == 'CE' and l.strike < spot[NM - 1]) or (l.cp == 'PE' and l.strike > spot[NM - 1])), alloc_agree_all=bool(l.alloc_agree_all),
                             **{f'close_row_{cv}': getattr(l, f'close_row_{cv}') for cv in CONV}))
    # ---- contract-minute panel on D0
    g = F[(F.und == r.und) & (F.expiry == r.expiry)].sort_values(['t', 'row']); books = defaultdict(list); ev = defaultdict(float); gi = 0; fl = list(g.itertuples()); bb_first = {}
    # per minute buy-back lots by contract (body module closing shorts, first fill minute)
    for f in fl:
        if f.module == 'num' and f.side == 'Buy' and f.day == r.d0: ev[(f.cp, int(f.strike), f.sec // 60 - 555)] += f.n_lots
    last_bb_j = -999; mtm_cash = 0.0; ptr = 0
    for j in range(NM):
        tabs = 86400 + (555 + j) * 60
        while ptr < len(fl) and ((0 if fl[ptr].day == r.d1 else 86400) + fl[ptr].sec) < tabs:
            f = fl[ptr]; ptr += 1; mtm_cash += -f.sgn * f.qty_fill * f.px
            if f.module == 'num':
                B = books[(f.cp, int(f.strike))]
                if f.side == 'Sell': B.extend([[f.px, 0 if f.day == r.d1 else 1] for _ in range(f.n_lots)])
                else:
                    for _ in range(f.n_lots):
                        if B: B.pop(0)
                    if f.day == r.d0: last_bb_j = f.sec // 60 - 555
            elif f.module in ('s_', 'm_') and f.side == 'Buy':
                B = books[(f.cp, int(f.strike))]
                for _ in range(f.n_lots):
                    if B: B.pop(0)
        S = spot[NM + j - 1]; mm = (555 + j) % 60; hh = (555 + j) // 60; Tleft = (15.5 * 60 - (555 + j)) / 60
        for (cp, k), B in books.items():
            if not B: continue
            i = ki.get(k)
            if i is None: continue
            pj = P[cp][i, NM + j - 1]; ents = [b[0] for b in B]; avg = float(np.mean(ents)); cheap = float(min(ents)); n = len(B); carried = sum(1 for b in B if b[1] == 0)
            p5 = P[cp][i, max(NM + j - 6, 0)]
            panel.append(dict(und=r.und, expiry=r.expiry, j=j, cp=cp, strike=k, lots=n, carried_lots_FIFO=carried, price=pj, avg_entry=avg, cheapest=cheap, ratio_avg=pj / avg, ratio_cheapest=pj / cheap, off_steps=(k - S) / step, itm=bool((cp == 'CE' and k < S) or (cp == 'PE' and k > S)), hours_left=Tleft, minute_of_hour=mm, clockB=bool(mm % 15 == 14 and hh * 60 + mm >= 9 * 60 + 29),
                              d_price_5m=(pj / p5 - 1) if p5 else np.nan, mins_since_cycle_buyback=(j - last_bb_j) if last_bb_j > -999 else np.nan, buyback_lots=ev.get((cp, k, j), 0.0)))
LT = pd.DataFrame(lots_out); LT.to_csv(f'{OUT}/carried_lots.csv.gz', index=False); PN = pd.DataFrame(panel); PN['event'] = PN.buyback_lots > 0; PN.to_csv(f'{OUT}/contract_minute_panel.csv.gz', index=False)
print(len(LT), 'carried lots;', len(PN), 'contract-minutes; event rate', PN.event.mean().round(4), ' cycles', PN[['und', 'expiry']].drop_duplicates().shape[0])
