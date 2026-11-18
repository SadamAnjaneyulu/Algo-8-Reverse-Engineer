"""PHASE A: auditable order-level event table for ALL 35 live cycles (both days; D0 flagged). One row per order (column-163 tag, unique per order: DAT-01).
Contains position before/after (single net position per contract, lots), FIFO realised P&L, classification (precedence documented in D0_EVENT_SEQUENCE_ANALYSIS.md), decision-time market observations (previous completed minute), cycle/portfolio state, wing pairing, and post-buyback follow-up links.
Building the table touches holdout cycles (required by Gate 1) but NO rule is fitted here."""
from collections import deque, defaultdict
import datetime
from d0common import *
from data import load_cycle, MI, NM
from bt import cycles as Cy
CL = Cy.cycle_list()


def decode_dt(tag):
    """h_/s_/v_/m_ tags embed DDHHMMSSffffff UTC decision time -> seconds since midnight IST (float)"""
    try: s = tag[2:]; return ((int(s[2:4]) * 3600 + int(s[4:6]) * 60 + int(s[6:8]) + int(s[8:]) / 1e6) + 19800) % 86400
    except Exception: return np.nan


d = live_ledger(); d['expiry'] = pd.to_datetime(d.expiry); d['day_s'] = d.date.dt.strftime('%Y-%m-%d'); d['sec'] = d.t.dt.hour * 3600 + d.t.dt.minute * 60 + d.t.dt.second
orders = d.sort_values(['t', 'row']).groupby('tag').agg(und=('und', 'first'), expiry=('expiry', 'first'), day=('day_s', 'first'), module=('tp', 'first'), side=('side', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), qty=('qty_fill', 'sum'), px=('px_fill', 'last'), t_first=('t', 'min'), t_last=('t', 'max'), sec_first=('sec', 'min'), sec_last=('sec', 'max'), n_fills=('row', 'size'), row0=('row', 'min'), validity=('validity', 'first')).reset_index()
orders['lots'] = orders.qty / orders.und.map(LOT); orders['dec_sec'] = [decode_dt(t) if m != 'num' else np.nan for t, m in zip(orders.tag, orders.module)]
orders['sgn'] = np.where(orders.side == 'Buy', 1, -1); out = []; status = []
for (u, e), g in orders.sort_values(['t_first', 'row0']).groupby(['und', 'expiry']):
    m = CL[(CL.und == u) & (CL.expiry == e.strftime('%Y-%m-%d'))].iloc[0]; days = sorted(g.day.unique()); has_d1 = m.d1 in days; has_d0 = m.d0 in days
    status.append(dict(und=u, expiry=e.strftime('%Y-%m-%d'), d1=m.d1, d0=m.d0, has_d1=has_d1, has_d0=has_d0, carry_in_known=has_d1 and has_d0, split=split_of(e), orders=len(g), d0_orders=int((g.day == m.d0).sum())))
    c = load_cycle(u, e.strftime('%Y-%m-%d'), m.d1, m.d0); strikes = c['strikes']; ki = {int(k): i for i, k in enumerate(strikes)}; lot = LOT[u]; step = 50 if u == 'NIFTY' else 100
    px = {}
    for di in (0, 1):
        for r in ('CE', 'PE'):
            a = c[(di, r, 'close')].copy()
            for j in range(1, NM): mm = np.isnan(a[:, j]); a[mm, j] = a[mm, j - 1]
            px[(di, r)] = a
    books = defaultdict(deque); cash = 0.0; ev = []
    ROUTE = {  # (module, side) -> (roles to close against, role to open)
        ('num', 'Sell'): (['body'], 'body'), ('num', 'Buy'): (['body'], 'body'), ('h_', 'Buy'): (['wing'], 'wing'), ('h_', 'Sell'): (['wing', 'lump'], 'wing'),
        ('v_', 'Buy'): (['lump'], 'lump'), ('v_', 'Sell'): (['lump', 'wing'], 'lump'), ('s_', 'Buy'): (['body', 'lump', 'wing'], 'stop'), ('s_', 'Sell'): (['wing', 'lump', 'body'], 'stop'),
        ('m_', 'Buy'): (['body', 'lump', 'wing'], 'stop'), ('m_', 'Sell'): (['wing', 'lump', 'body'], 'stop')}
    def net_of(cp_, k_, roles=('body', 'wing', 'lump', 'stop')): return sum(x[0] * x[1] for rl in roles for x in books[(cp_, k_, rl)])
    for r in g.itertuples():
        di = 0 if r.day == m.d1 else 1; secs = r.sec_first; mi = int(secs // 60 - 555); pm = min(max(mi - 1, 0), NM - 1)
        key = (r.cp, int(r.strike)); si = ki.get(int(r.strike)); S = c[(di, 'spot')][pm]; p_prev = px[(di, r.cp)][si, pm] if si is not None else np.nan; p_prev2 = px[(di, r.cp)][si, max(pm - 1, 0)] if si is not None else np.nan
        sh = defaultdict(float); lg = defaultdict(float); mark = 0.0; nshort = 0; bshort = defaultdict(float)
        contracts = {(k[0], k[1]) for k, L_ in books.items() if L_}
        for (cp_, k_) in contracts:
            q = net_of(cp_, k_); i_ = ki.get(k_); pp = px[(di, cp_)][i_, pm] if i_ is not None else np.nan
            if abs(q) > 1e-9 and pp == pp: mark += q * lot * pp
            bq = net_of(cp_, k_, ('body',))
            if bq < -1e-9: bshort[cp_] += -bq; nshort += 1
            lq = net_of(cp_, k_, ('wing', 'lump', 'stop'))
            if lq > 1e-9: lg[cp_] += lq
        mtm = cash + mark; bq_before = net_of(*key, ('body',)); net_before = net_of(*key); Lb = books[(key[0], key[1], 'body')]
        sh_lots = [x for x in Lb if x[0] < 0]; cheapest = min([x[2] for x in sh_lots], default=np.nan); avgent = (sum(x[2] * x[1] for x in sh_lots) / sum(x[1] for x in sh_lots)) if sh_lots else np.nan
        closes, openrole = ROUTE[(r.module, r.side)]; q = r.lots; closed = 0.0; rp = 0.0; closed_roles = defaultdict(float); closed_d1 = 0.0; closed_hold = []
        for rl in closes:
            L = books[(key[0], key[1], rl)]
            while q > 1e-9 and L and L[0][0] != r.sgn:
                o = L[0]; t = min(q, o[1]); rp += (o[2] - r.px if o[0] < 0 else r.px - o[2]) * t * lot; closed += t; closed_roles[rl] += t; closed_d1 += t if o[5] == 0 else 0; closed_hold.append((r.t_first - o[4]).total_seconds() / 60); o[1] -= t; q -= t
                if o[1] <= 1e-9: L.popleft()
        opened = 0.0
        if q > 1e-9: books[(key[0], key[1], openrole)].append([r.sgn, q, r.px, r.module, r.t_first, di]); opened = q
        cash += -r.sgn * r.lots * lot * r.px
        ev.append(dict(und=u, expiry=e.strftime('%Y-%m-%d'), split=split_of(e), d1=m.d1, d0=m.d0, day='D0' if di == 1 else 'D-1', tag=r.tag, module=r.module, t=r.t_first, sec=secs, sec_last=r.sec_last, dec_sec=r.dec_sec, minute=mi, side=r.side, cp=r.cp, strike=int(r.strike), lots=r.lots, px=r.px, n_fills=r.n_fills,
                       body_q_before=bq_before, contract_net_before=net_before, contract_net_after=net_of(*key), closed_lots=closed, opened_lots=opened, open_role=openrole if opened else '', realized_pnl=rp, closed_carried_frac=(closed_d1 / closed) if closed else np.nan, closed_roles='|'.join(f'{k}:{v:g}' for k, v in closed_roles.items()), closed_hold_min=np.mean(closed_hold) if closed_hold else np.nan,
                       spot_prev=S, opt_prev_close=p_prev, opt_prev2_close=p_prev2, off_steps=(r.strike - S) / step if S == S else np.nan, cheapest_entry_before=cheapest, avg_entry_before=avgent, ratio_cheapest=(p_prev / cheapest) if cheapest == cheapest else np.nan, ratio_avg=(p_prev / avgent) if avgent == avgent else np.nan,
                       body_short_CE=bshort['CE'], body_short_PE=bshort['PE'], long_lots_CE=lg['CE'], long_lots_PE=lg['PE'], active_short_contracts=nshort, cycle_mtm_prev=mtm, carry_in_known=has_d1 and has_d0))
    out.extend(ev)
E_ = pd.DataFrame(out); S_ = pd.DataFrame(status)
# ---------- classification (precedence documented) ----------
E_ = E_.sort_values(['und', 'expiry', 't', 'sec']).reset_index(drop=True); E_['mm'] = ((E_.sec // 60) % 60).astype(int); E_['ss'] = (E_.sec % 60); E_['hhmm'] = (E_.sec // 3600).astype(int) * 100 + E_.mm
off = ((E_.mm - 1) % 15) * 60 + E_.ss; E_['slot_offset_s'] = off; E_['sched_gridA'] = ((off < 180) | (off >= 898)) & (E_.sec >= 9 * 3600 + 16 * 60 - 2)
off0 = (E_.mm % 15) * 60 + E_.ss; E_['sched_grid00'] = (off0 < 180) & (E_.sec >= 13 * 3600 + 30 * 60) & (E_.sec <= 15 * 3600 + 3 * 60); E_['clockB_minute'] = (E_.mm % 15 == 14) & (E_.sec >= 9 * 3600 + 29 * 60 - 60)
cls = []; E_['prev_bb_sec_same_right'] = np.nan; E_['prev_hedge_sell_sec_same_right'] = np.nan
for (u, e), g in E_.groupby(['und', 'expiry']):
    lastbb = {}; lasths = {}
    for i, r in g.iterrows():
        c_ = 'UNCLASSIFIED'; bb_ago = r.sec - lastbb.get((r.day, r.cp), -1e9); hs_ago = r.sec - lasths.get((r.day, r.cp), -1e9)
        if r.module == 's_': c_ = 'STOP_MODULE_ORDER'
        elif r.module == 'v_': c_ = 'LUMP_HEDGE_ADD' if r.side == 'Buy' else 'LUMP_HEDGE_SALVAGE'
        elif r.module == 'm_': c_ = 'MANUAL'
        elif r.module == 'h_': c_ = ('HEDGE_REPLACEMENT' if hs_ago <= 30 else 'HEDGE_ADD') if r.side == 'Buy' else 'HEDGE_REDUCE'
        elif r.module == 'num':
            if r.side == 'Sell':
                if r.opened_lots > 0 and r.closed_lots == 0:
                    c_ = 'REPLACEMENT_SALE' if bb_ago <= 60 else ('SCHEDULED_SALE' if (r.sched_gridA or r.sched_grid00) else 'OFF_SCHEDULE_SALE')
                else: c_ = 'POSITION_REDUCTION_OF_LONG'
            else:
                if r.closed_lots > 0 and r.opened_lots == 0:
                    c_ = 'FINAL_LIQUIDATION' if (r.day == 'D0' and r.sec >= 15 * 3600 + 10 * 60) else 'BUYBACK'
                else: c_ = 'UNCLASSIFIED'
        cls.append((i, c_))
        if r.module == 'num' and r.side == 'Buy' and r.closed_lots > 0: lastbb[(r.day, r.cp)] = r.sec
        if r.module == 'h_' and r.side == 'Sell': lasths[(r.day, r.cp)] = r.sec
        E_.at[i, 'prev_bb_sec_same_right'] = bb_ago if bb_ago < 1e8 else np.nan
E_['event_class'] = pd.Series(dict(cls))
# ---------- wing pairing (body opening sale <- hedge buy within 15 s, same right) ----------
E_['wing_tag'] = ''; E_['wing_lots'] = 0.0; E_['wing_px'] = np.nan; E_['wing_strike'] = np.nan; E_['wing_delay_s'] = np.nan
for (u, e), g in E_.groupby(['und', 'expiry']):
    wings = g[(g.module == 'h_') & (g.side == 'Buy')].copy(); used = set()
    for i, r in g[(g.module == 'num') & (g.side == 'Sell') & (g.opened_lots > 0)].iterrows():
        cand = wings[(wings.day == r.day) & (wings.cp == r.cp) & (~wings.tag.isin(used)) & ((wings.dec_sec - r.sec).abs() <= 15)]
        if len(cand):
            w = cand.iloc[(cand.dec_sec - r.sec).abs().argsort().iloc[0]]; used.add(w.tag); E_.loc[i, ['wing_tag', 'wing_lots', 'wing_px', 'wing_strike', 'wing_delay_s']] = [w.tag, w.lots, w.px, w.strike, w.dec_sec - r.sec]
# ---------- follow-up of buybacks ----------
E_['follow_kind'] = ''; E_['follow_delay_s'] = np.nan; E_['follow_lots'] = np.nan; E_['follow_strike_steps_vs_atm'] = np.nan; E_['follow_same_contract'] = np.nan; E_['follow_tag'] = ''
for (u, e), g in E_.groupby(['und', 'expiry']):
    sales = g[(g.module == 'num') & (g.side == 'Sell') & (g.opened_lots > 0)]
    for i, r in g[(g.event_class.isin(['BUYBACK', 'FINAL_LIQUIDATION']))].iterrows():
        cand = sales[(sales.day == r.day) & (sales.sec >= r.sec) & (sales.sec <= r.sec + 180) & (sales.index != i)]
        if not len(cand): E_.at[i, 'follow_kind'] = 'NONE_WITHIN_180S'; continue
        same = cand[(cand.cp == r.cp)]
        if not len(same): E_.at[i, 'follow_kind'] = 'OPPOSITE_RIGHT_ONLY'; s = cand.iloc[0]
        else:
            s = same.iloc[0]; E_.at[i, 'follow_kind'] = 'SAME_CONTRACT' if s.strike == r.strike else 'SAME_RIGHT_OTHER_STRIKE'
        E_.loc[i, ['follow_delay_s', 'follow_lots', 'follow_strike_steps_vs_atm', 'follow_same_contract', 'follow_tag']] = [s.sec - r.sec, s.lots, s.off_steps, float(s.strike == r.strike and s.cp == r.cp), s.tag]
E_.to_csv(f'{RES}/d0_events.csv', index=False); S_.to_csv(f'{RES}/cycle_status.csv', index=False)
print(len(E_), 'orders;', E_.groupby('day').size().to_dict()); print(S_[['und', 'expiry', 'has_d1', 'has_d0', 'carry_in_known', 'split', 'd0_orders']].to_string(index=False))
print(E_[E_.day == 'D0'].groupby('event_class').agg(orders=('lots', 'size'), lots=('lots', 'sum')).sort_values('lots', ascending=False))
