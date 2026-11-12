"""Phases 1-4 of the risk-rule validation. Run through run_all.py.  No threshold is fitted: the client constants are used as stated."""
import numpy as np, pandas as pd
from rr_common import (orders, markets, replay_book, ledger, split_of, LOT, CONVS, CARRY_PCT, EXPIRY_LIMIT, ACTION_WIN, SCHEDULED, CLOCKED,
                       CycleBook, fills, minute_of, order_minutes, first_cross, cycle_keys, d_bounds)

PLATFORM = {'152432', '2.18811E+15'}


def _short_lots_open_at(B, t):
    return int(((B.sg < 0) & (B.emi <= t) & (B.xmi >= t)).sum())


def _short_bought_in(B, t0, t1):
    return int(((B.sg < 0) & (B.xmi >= t0) & (B.xmi <= t1)).sum())


# ============================== PHASE 1 ==============================
def phase1():
    o = orders(); mk = markets(); d = fills()
    from mtm import cycle_mtm
    opt = pd.read_pickle(__import__('os').path.join(__import__('rr_common').AN, '_cache', 'opt_candles.pkl'))
    L = {c: ledger(c) for c in CONVS}
    rows, amb, checks = [], [], []
    for (u, e) in cycle_keys():
        m = mk[(u, e)]; d1, d0 = d_bounds(m)
        oc = o[(o.und == u) & (o.expiry == e)]; dc = d[(d.und == u) & (d.expiry == e)].sort_values(['t', 'row'])
        lot = LOT[u]
        # (i) orders vs fills
        lots_orders = oc.lots.sum(); lots_fills = (dc.qty_fill / lot).sum()
        # (ii) final net per contract: fills vs every ledger
        net_f = dc.groupby(['cp', 'strike']).sl.sum().round(6); net_f = net_f[net_f != 0]
        final_ok = {}
        for c in CONVS:
            Lc = L[c][(L[c].und == u) & (L[c].expiry == e)]
            op = Lc[Lc.exit_px.isna()].groupby(['cp', 'strike']).sgn.sum()
            ix = op.index.union(net_f.index)
            final_ok[c] = bool(np.allclose(net_f.reindex(ix).fillna(0).values.astype(float), op.reindex(ix).fillna(0).values.astype(float)))
        # (iii) carried inventory: fills before the first D0 session vs ledger carried counts
        r = dict(und=u, expiry=e.date(), split=split_of(e), has_D1=d1 is not None, has_D0=d0 is not None, orders=len(oc), fills=len(dc),
                 lots_traded=lots_orders, lots_fills=lots_fills, orders_platform_or_manual=int((oc.algoid.isin(PLATFORM) | (oc.tp == 'm_')).sum()),
                 lots_platform_or_manual=float(oc[oc.algoid.isin(PLATFORM) | (oc.tp == 'm_')].lots.sum()), s_orders=int((oc.tp == 's_').sum()))
        if d1 is not None:
            d1date = m['grid'][d1].normalize()
            nd1 = dc[dc.t.dt.normalize() <= d1date].groupby(['cp', 'strike']).sl.sum()
            r.update(carried_short_lots_fills=float(-nd1[nd1 < 0].sum()), carried_long_lots_fills=float(nd1[nd1 > 0].sum()),
                     carried_short_contracts=int((nd1 < 0).sum()), carried_long_contracts=int((nd1 > 0).sum()))
            for c in CONVS:
                Lc = L[c][(L[c].und == u) & (L[c].expiry == e)]
                r[f'carried_short_lots_{c}'] = int(((Lc.sgn < 0) & Lc.carried).sum()); r[f'carried_long_lots_{c}'] = int(((Lc.sgn > 0) & Lc.carried).sum())
            P3L = replay_book('fifo'); P3L = P3L[(P3L.und == u) & (P3L.expiry == e)]
            r['pr3_ledger_carried_short_lots'] = int(((P3L.sgn < 0) & P3L.carried).sum()); r['pr3_ledger_carried_long_lots'] = int(((P3L.sgn > 0) & P3L.carried).sum())
            late = oc[(oc.date < e) & (oc.t_dec_lo > m['grid'][d1] + pd.Timedelta(minutes=1))]
            r['orders_after_last_D1_bar'] = len(late); r['lots_after_last_D1_bar'] = float(late.lots.sum())
            r['late_D1_order_modules'] = ','.join(f'{k}:{v}' for k, v in late.tp.value_counts().items())
            r['last_D1_bar'] = m['grid'][d1].strftime('%H:%M')
            B = CycleBook(u, e, 'cheap', L['cheap'], m)
            sh = B.carried & (B.sg < 0)
            r['carried_short_value_D1_close'] = float((B.ref[sh] * B.lot).sum())
            for c in CONVS:
                Bc = B if c == 'cheap' else CycleBook(u, e, c, L[c], m); shc = Bc.carried & (Bc.sg < 0)
                r[f'carried_short_entry_premium_{c}'] = float((Bc.epx[shc] * Bc.lot).sum())
            r['mtm_at_D1_close'] = float(B.cum()[d1])
        r['open_short_lots_end_of_export'] = float(-net_f[net_f < 0].sum()); r['open_long_lots_end_of_export'] = float(net_f[net_f > 0].sum())
        # (iv) ledger MTM vs fills-based MTM (independent: analysis/mtm.py) at the last minute of each session
        B = CycleBook(u, e, 'cheap', L['cheap'], m); cum = B.cum()
        fm = cycle_mtm(d, opt, u, e)
        r['ledger_vs_fills_mtm_abs_diff_end_of_export'] = float(abs(cum[-1] - fm.iloc[-1]))
        if d1 is not None:   # fills-based MTM includes post-15:29 D-1 trades marked at post-close candles; the ledger marks them at the 15:29 close
            r['ledger_vs_fills_mtm_abs_diff_D1_close'] = float(abs(cum[d1] - fm[fm.index.normalize() == m['grid'][d1].normalize()].iloc[-1]))
        # (v) day identity: realised + unrealised D0 = cumulative(t) - cumulative(D-1 close)
        if d0 is not None:
            Rd, Ud = B.day_parts(); base = cum[d1] if d1 is not None else 0.0
            r['day_identity_max_abs_err'] = float(np.max(np.abs((Rd + Ud)[d0:] - (cum[d0:] - base))))
        r.update({f'final_inventory_matches_fills_{c}': final_ok[c] for c in CONVS})
        rows.append(r)
        # ownership ambiguity: D0 short buybacks whose split between carried and D0-new lots differs across conventions
        if d0 is not None and d1 is not None:
            bb = oc[(oc.side == 'Buy') & (oc.closing_short == True) & (oc.date == e)]
            per = {}
            for c in CONVS:
                Lc = L[c][(L[c].und == u) & (L[c].expiry == e) & (L[c].sgn < 0)]
                per[c] = Lc[Lc.carried].groupby('exit_oid').size()
            for oid, lots in zip(bb.oid, bb.lots):
                v = [int(per[c].get(oid, 0)) for c in CONVS]
                amb.append(dict(und=u, expiry=e.date(), oid=oid, lots=int(lots), carried_closed_cheap=v[0], carried_closed_fifo=v[1], carried_closed_lifo=v[2],
                                ambiguous=len(set(v)) > 1))
    R = pd.DataFrame(rows); A = pd.DataFrame(amb)
    return R, A


# ============================== PHASE 2 ==============================
CARRY_DEFS = {
    'A': ('4 % of the carried lot\'s entry premium (lot level)', 'per lot: entry price x lot size', 'contract'),
    'B': ('4 % of the carried position\'s D-1 closing value (lot level)', 'per contract: D-1 closing mark x lot size', 'contract'),
    'C': ('4 % of the carried portfolio\'s D-1 closing value', 'sum over carried short lots of D-1 closing mark x lot size', 'portfolio'),
    'D': ('4 % individual-position loss (contract position, from entry)', 'per contract: sum over its carried short lots of entry price x lot size', 'contract'),
    'E': ('4 % combined carried-portfolio loss (from entry)', 'sum over carried short lots of entry price x lot size', 'portfolio'),
}


def _contract_tests(B, oc, om, defn):
    """returns list of event dicts for contract-level definitions A/B/D"""
    out = []
    d0 = B.d0_first; n = B.n
    if d0 is None or not (B.carried & (B.sg < 0)).any(): return out
    sh = B.carried & (B.sg < 0)
    t = np.arange(n)
    bb = oc[(oc.side == 'Buy') & (oc.closing_short == True)].assign(mi=om[((oc.side == 'Buy') & (oc.closing_short == True)).values])
    for kk in np.unique(B.k[sh]):
        idx = np.where(sh & (B.k == kk))[0]
        cp, strike = B.m['keys'][kk]
        mark = B.mark[idx[0]]
        open_start = np.array([((B.xmi[idx] >= tt)).any() for tt in t])           # some carried lot of this contract still open at the start of minute t
        elig = open_start & (t >= d0)
        if defn == 'A':
            mins = np.array([B.epx[idx][B.xmi[idx] >= tt].min() if open_start[tt] else np.inf for tt in t])
            cond = mark >= (1 + CARRY_PCT) * mins
            denom = float(B.epx[idx].min() * B.lot)
        elif defn == 'B':
            ref = B.ref[idx[0]]; cond = mark >= (1 + CARRY_PCT) * ref; denom = float(ref * B.lot)
        else:  # D
            pnl = (B.U[idx] + B.R[idx]).sum(axis=0); denom = float((B.epx[idx] * B.lot).sum())
            cond = pnl <= -CARRY_PCT * denom
        hit = np.where(elig & cond)[0]
        tc = int(hit[0]) if len(hit) else None
        b = bb[(bb.cp == cp) & (bb.strike == strike) & (bb.mi >= d0)].sort_values('mi')
        stoplike = b[~b.label.isin(SCHEDULED + CLOCKED) & np.array([open_start[min(x, n - 1)] for x in b.mi])]
        first_sl = int(stoplike.mi.iloc[0]) if len(stoplike) else None
        # no-crossing baseline: eligible minutes before any crossing; outcome = stop-like buyback of this contract within [t, t + 5]
        slm = stoplike.mi.values
        base_t = np.where(elig & (t < (tc if tc is not None else n)))[0]
        y = np.array([((slm >= tt) & (slm <= tt + ACTION_WIN)).any() for tt in base_t]) if len(base_t) else np.zeros(0, bool)
        opn = base_t < d0 + 5
        ev = dict(definition=defn, unit=f'{cp} {int(strike)}', denominator_rs=denom, threshold_rs=CARRY_PCT * denom,
                  carried_short_lots=len(idx), cross_minute=tc, beyond_at_D0_open=bool(tc == d0) if tc is not None else False,
                  first_stoplike_buyback_minute=first_sl, cross_in_open_bin=(tc is not None and tc < d0 + 5),
                  base_open_n=int(opn.sum()), base_open_hits=int(y[opn].sum()), base_later_n=int((~opn).sum()), base_later_hits=int(y[~opn].sum()))
        if tc is not None:
            after = b[b.mi >= tc]
            if len(after):
                a = after.iloc[0]; ev.update(first_action_minute=int(a.mi), delay_min=int(a.mi - tc), first_action_label=a.label, first_action_oid=a.oid)
            delay = ev.get('delay_min')
            if delay is not None and delay <= ACTION_WIN:
                ev['classification'] = 'matched stop' if a.label not in SCHEDULED + CLOCKED else 'scheduled / clock exit after crossing'
            else:
                ev['classification'] = 'false trigger (no buyback within 5 min)'
        elif first_sl is not None:
            ev['classification'] = 'missed stop (stop-like buyback, no prior crossing)'
        else:
            ev['classification'] = 'no crossing, no stop-like buyback'
        if tc is not None and ev['classification'] != 'matched stop' and first_sl is not None:
            ev['missed_stop_also'] = True
        out.append(ev)
    return out


def _portfolio_series(B, defn, held):
    sh = B.carried & (B.sg < 0); allc = B.carried
    if defn == 'C':
        denom = float((B.ref[sh] * B.lot).sum())
        if held: s = B.carried_held_day()
        else:
            Rd, Ud = B.day_parts(allc); s = Rd + Ud
    else:  # E
        denom = float((B.epx[sh] * B.lot).sum())
        base = B.cum(allc)[B.d1_last]
        s = base + B.carried_held_day() if held else B.cum(allc)
    return s, denom


def _portfolio_action(B, oc, om, tc, carried_only=False):
    s_mi = om[(oc.tp == 's_').values]
    s_in = bool(((s_mi >= tc) & (s_mi <= tc + ACTION_WIN)).any())
    if carried_only:
        csh = B.carried & (B.sg < 0); open_sh = int((csh & (B.xmi >= tc)).sum()); bought = int((csh & (B.xmi >= tc) & (B.xmi <= tc + ACTION_WIN)).sum())
    else:
        open_sh = _short_lots_open_at(B, tc); bought = _short_bought_in(B, tc, tc + ACTION_WIN)
    share = bought / open_sh if open_sh else np.nan
    return s_in, open_sh, bought, share


def _liquidation_events(B, oc, om):
    """two ground truths per cycle on D0 (reported separately):
    GT1 cycle-stop module (`s_`) fired on D0;  GT2 carried-book liquidation: >= 50 % of the carried short lots open at minute t (at least 4)
    closed within 5 min by non-scheduled orders (salvage / final flatten / platform excluded; cycle-stop orders included)."""
    d0 = B.d0_first
    s_mi = om[(oc.tp == 's_').values]; s_mi = s_mi[s_mi >= d0] if d0 is not None else s_mi[:0]
    gt1 = int(s_mi.min()) if len(s_mi) else None
    lab = pd.Series(B.L.exit_label.values)
    csh = B.carried & (B.sg < 0); ok = csh & ~lab.isin(SCHEDULED[1:]).values      # keep cycle-stop closures, drop salvage / flatten / platform
    gt2 = None
    if d0 is not None:
        for tt in range(d0, B.n):
            op = int((csh & (B.xmi >= tt)).sum())
            if op >= 4 and int((ok & (B.xmi >= tt) & (B.xmi <= tt + ACTION_WIN)).sum()) / op >= 0.5:
                gt2 = tt; break
    return gt1, gt2


def phase2():
    o = orders(); mk = markets(); L = {c: ledger(c) for c in CONVS}
    events, cyc = [], []
    for (u, e) in cycle_keys():
        m = mk[(u, e)]; d1, d0 = d_bounds(m)
        if d1 is None or d0 is None: continue
        oc = o[(o.und == u) & (o.expiry == e)].reset_index(drop=True); om = order_minutes(oc, m)
        for c in CONVS:
            B = CycleBook(u, e, c, L[c], m)
            if not (B.carried & (B.sg < 0)).any(): continue
            for dfn in ('A', 'B', 'D'):
                for ev in _contract_tests(B, oc, om, dfn):
                    ev.update(und=u, expiry=e.date(), convention=c, split=split_of(e)); events.append(ev)
            gt1, gt2 = _liquidation_events(B, oc, om)
            variants = [('C', False, 'bar_1529'), ('C', True, 'bar_1529'), ('E', False, 'bar_1529'), ('E', True, 'bar_1529')]
            if c == 'cheap': variants.append(('C', True, 'last_print'))
            for dfn, held, refm in variants:
                if held and dfn == 'C' and c != 'cheap': continue            # C-held uses D-1 closing marks only: convention-free, computed once
                Bv = B if refm == 'bar_1529' else CycleBook(u, e, c, L[c], m, ref_mode='last_print')
                s, denom = _portfolio_series(Bv, dfn, held)
                thr = -CARRY_PCT * denom
                tc = first_cross(s, thr, d0)
                conv = c if not held else ('held, convention-free' if dfn == 'C' else f'held, {c} entries')
                if refm == 'last_print': conv += ' | D-1 ref = last print incl. 15:30-15:39 (sensitivity)'
                ev = dict(definition=dfn, unit='carried portfolio', convention=conv, und=u, expiry=e.date(), split=split_of(e),
                          denominator_rs=denom, threshold_rs=-thr, carried_short_lots=int((B.carried & (B.sg < 0)).sum()),
                          pnl_at_D0_open=float(s[d0]), min_pnl_D0=float(np.min(s[d0:])), cross_minute=tc, beyond_at_D0_open=bool(tc == d0) if tc is not None else False,
                          gt1_cycle_stop_minute=gt1, gt2_carried_liquidation_minute=gt2)
                if tc is not None:
                    s_in, op, bq, sh_ = _portfolio_action(B, oc, om, tc, carried_only=True)
                    ev.update(cycle_stop_within_5=s_in, open_carried_short_lots_at_cross=op, carried_short_lots_bought_within_5=bq, share_carried_bought_within_5=sh_)
                    ev['gt1_match'] = s_in
                    ev['gt2_match'] = bool(gt2 is not None and tc <= gt2 <= tc + ACTION_WIN)
                    matched = ev['gt1_match'] or ev['gt2_match']
                    ev['classification'] = ('matched stop (coincides with the cycle stop)' if s_in else 'matched stop (carried-book liquidation, no cycle stop)') if matched else 'false trigger (no liquidation within 5 min)'
                    first = min([x for x in (gt1, gt2) if x is not None and x >= tc], default=None)
                    ev['delay_min'] = int(first - tc) if (matched and first is not None) else np.nan
                else:
                    ev['gt1_match'] = ev['gt2_match'] = False
                    ev['classification'] = 'missed stop (liquidation, no prior crossing)' if (gt1 is not None or gt2 is not None) else 'no crossing, no liquidation'
                events.append(ev)
    E = pd.DataFrame(events)
    # summary per definition x convention
    rows = []
    for (dfn, conv), g in E.groupby(['definition', 'convention']):
        cr = g.cross_minute.notna(); cls = g.classification.astype(str)
        r = dict(definition=dfn, description=CARRY_DEFS[dfn][0], denominator=CARRY_DEFS[dfn][1], unit=CARRY_DEFS[dfn][2], convention=conv,
                 cycles=g[['und', 'expiry']].drop_duplicates().shape[0], units_tested=len(g), crossings=int(cr.sum()), beyond_at_D0_open=int(g.beyond_at_D0_open.sum()))
        if CARRY_DEFS[dfn][2] == 'contract':
            hits = int((cls == 'matched stop').sum()); ev_true = int(g.first_stoplike_buyback_minute.notna().sum())
            io = g.cross_in_open_bin.fillna(False).astype(bool)
            r.update(actual_stop_events=ev_true, matched_stops=hits, matched_same_minute=int(((cls == 'matched stop') & (g.delay_min == 0)).sum()),
                     scheduled_or_clock_exit_after_crossing=int((cls == 'scheduled / clock exit after crossing').sum()), false_triggers=int(cls.str.startswith('false').sum()),
                     missed_stops=ev_true - hits, precision=hits / cr.sum() if cr.sum() else np.nan, recall=hits / ev_true if ev_true else np.nan,
                     hit_rate_crossings_open_bin=float((cls[io] == 'matched stop').mean()) if io.any() else np.nan, crossings_open_bin=int(io.sum()),
                     baseline_rate_open_bin=g.base_open_hits.sum() / g.base_open_n.sum() if g.base_open_n.sum() else np.nan,
                     hit_rate_crossings_after_open=float((cls[cr & ~io] == 'matched stop').mean()) if (cr & ~io).any() else np.nan, crossings_after_open=int((cr & ~io).sum()),
                     baseline_rate_after_open=g.base_later_hits.sum() / g.base_later_n.sum() if g.base_later_n.sum() else np.nan)
        else:
            n1 = int(g.gt1_cycle_stop_minute.notna().sum()); n2 = int(g.gt2_carried_liquidation_minute.notna().sum())
            m1 = int(g.gt1_match.sum()); m2 = int(g.gt2_match.sum())
            m2_only = int((g.gt2_match & ~g.gt1_match.astype(bool)).sum())
            r.update(gt1_cycle_stop_events=n1, gt1_matched=m1, gt2_carried_liquidation_events=n2, gt2_matched=m2, matched_without_cycle_stop=m2_only,
                     false_triggers=int(cls.str.startswith('false').sum()),
                     precision_any=(cr & (g.gt1_match | g.gt2_match)).sum() / cr.sum() if cr.sum() else np.nan,
                     recall_gt1=m1 / n1 if n1 else np.nan, recall_gt2=m2 / n2 if n2 else np.nan)
        r['delay_median_min'] = float(g.loc[cls.str.startswith('matched'), 'delay_min'].median()) if cls.str.startswith('matched').any() else np.nan
        rows.append(r)
    return pd.DataFrame(rows), E


# ============================== PHASE 3 ==============================
SERIES = {
    'S1 realised only (D0)': 'R', 'S2 unrealised only (D0)': 'U', 'S3 combined realised + unrealised (D0 MTM)': 'RU',
    'S4 carried inventory only (D0, realised + unrealised)': 'carried', 'S5 new expiry-day positions only (realised + unrealised)': 'new',
    'S6 context: cycle-cumulative MTM (D-1 + D0)': 'cum'}


def _behaviour(B, oc, om, tc):
    o_sorted = oc.assign(mi=om).sort_values(['mi', 't_dec'])
    before = o_sorted[o_sorted.mi < tc].tail(1); after = o_sorted[o_sorted.mi >= tc]
    short_entries_after = after[(after.side == 'Sell') & (after.label == 'open') & (after.mi > tc)]
    s_mi = om[(oc.tp == 's_').values]
    first_s = int(s_mi.min()) if len(s_mi) else None
    s_in, op, bq, sh_ = _portfolio_action(B, oc, om, tc)
    bb5 = after[(after.side == 'Buy') & (after.closing_short == True) & (after.mi <= tc + ACTION_WIN)]
    return dict(last_order_before=(f"{before.t_dec.iloc[0]:%H:%M:%S} {before.side.iloc[0]} {before.cp.iloc[0]} {int(before.strike.iloc[0])} [{before.label.iloc[0]}]" if len(before) else ''),
                first_order_after=(f"{after.t_dec.iloc[0]:%H:%M:%S} {after.side.iloc[0]} {after.cp.iloc[0]} {int(after.strike.iloc[0])} [{after.label.iloc[0]}]" if len(after) else ''),
                cycle_stop_minute=first_s, crossing_vs_cycle_stop=('no cycle stop' if first_s is None else ('before' if tc < first_s else ('same minute' if tc == first_s else 'after (post-stop)'))),
                new_short_entries_after=int(len(short_entries_after)), entries_cease=len(short_entries_after) == 0,
                new_short_entries_after_5min=int((short_entries_after.mi > tc + ACTION_WIN).sum()),
                kill_switch_consistent=bool((s_in or (sh_ == sh_ and sh_ >= 0.5)) and (short_entries_after.mi > tc + ACTION_WIN).sum() == 0),
                cycle_stop_within_5=s_in, open_short_lots_at_cross=op, short_lots_bought_within_5=bq, share_bought_within_5=sh_,
                buyback_orders_within_5=int(len(bb5)), liquidated=bool(s_in or (sh_ == sh_ and sh_ >= 0.5)),
                continues_trading_15min_later=bool((after.mi > tc + 15).any()),
                crossing_without_action=bool(len(bb5) == 0 and not s_in))


def phase3():
    o = orders(); mk = markets(); L = {c: ledger(c) for c in CONVS}
    rows = []
    for (u, e) in cycle_keys():
        m = mk[(u, e)]; d1, d0 = d_bounds(m)
        if d0 is None: continue
        oc = o[(o.und == u) & (o.expiry == e)].reset_index(drop=True); om = order_minutes(oc, m)
        for c in CONVS:
            B = CycleBook(u, e, c, L[c], m)
            Rd, Ud = B.day_parts()
            ser = {'R': Rd, 'U': Ud, 'RU': Rd + Ud, 'cum': B.cum()}
            Rc, Uc = B.day_parts(B.carried); ser['carried'] = Rc + Uc
            Rn, Un = B.day_parts(B.new_d0); ser['new'] = Rn + Un
            for name, key in SERIES.items():
                if key in ('RU', 'cum') and c != 'cheap': continue          # convention-free series: computed once
                s = ser[key]; tc = first_cross(s, -EXPIRY_LIMIT, d0)
                r = dict(series=name, convention=('convention-free' if key in ('RU', 'cum') else c), und=u, expiry=e.date(), split=split_of(e),
                         threshold_rs=-EXPIRY_LIMIT, min_value_D0=float(np.min(s[d0:])), min_minute=m['grid'][d0 + int(np.argmin(s[d0:]))].strftime('%H:%M'),
                         value_at_D0_close=float(s[-1]), cross_minute=tc, cross_time=(m['grid'][tc].strftime('%H:%M') if tc is not None else ''))
                if tc is not None: r.update(_behaviour(B, oc, om, tc))
                rows.append(r)
    return pd.DataFrame(rows)


# ============================== PHASE 4 ==============================
def phase4():
    """Control: the observed cycle stop, reconstructed independently from the algo's own quotes at the stop moment."""
    o = orders(); mk = markets(); d = fills(); L = ledger('cheap')
    rows = []
    for (u, e) in cycle_keys():
        m = mk[(u, e)]; oc = o[(o.und == u) & (o.expiry == e)]; dc = d[(d.und == u) & (d.expiry == e)]
        B = CycleBook(u, e, 'cheap', L, m); cum = B.cum(); lot = LOT[u]
        s = oc[oc.tp == 's_']
        r = dict(und=u, expiry=e.date(), split=split_of(e), stop=len(s) > 0, min_cycle_mtm_minute_close=float(cum.min()))
        if len(s):
            ts = s.t_dec.min(); ms = minute_of(m, ts)
            pos = dc[dc.t < ts].groupby(['cp', 'strike']).sl.sum(); pos = pos[pos != 0]
            cash = dc[dc.t < ts].cash.sum()
            first_batch = s[s.t_dec <= ts + pd.Timedelta(seconds=60)].groupby(['cp', 'strike']).L.first()
            recent = oc[(oc.t_dec <= ts) & (oc.t_dec >= ts - pd.Timedelta(seconds=60)) & (oc.tp != 's_')].sort_values('t_dec').groupby(['cp', 'strike']).L.last()
            val_q = val_all = 0.0; marks = []
            for (cp, k), q in pos.items():
                if (cp, k) in first_batch.index: px, src = first_batch[(cp, k)], 's_ quote'
                elif (cp, k) in recent.index: px, src = recent[(cp, k)], 'other order quote <= 60 s'
                else:
                    kk = m['k2i'][(cp, k)]; px = m['Cf'][kk, max(ms - 1, 0)]; px = px if np.isfinite(px) else 0.0; src = 'minute close (previous minute)'
                v = q * lot * px; val_all += abs(v); val_q += abs(v) if src != 'minute close (previous minute)' else 0.0; marks.append(src)
                cash += v
            r.update(stop_time=ts.strftime('%Y-%m-%d %H:%M:%S'), stop_day=('D0' if ts.normalize() == e else 'D-1'),
                     mtm_at_stop_quote=float(cash), share_value_marked_by_quotes=val_q / val_all if val_all else np.nan,
                     mtm_minute_close_prev=float(cum[max(ms - 1, 0)]), mtm_minute_close_stop_minute=float(cum[ms]),
                     min_mtm_before_stop_minute_close=float(cum[:ms].min()) if ms > 0 else np.nan,
                     open_short_lots_at_stop=float(-pos[pos < 0].sum()), open_long_lots_at_stop=float(pos[pos > 0].sum()),
                     final_cycle_pnl=float(cum[-1]))
            d1, d0 = d_bounds(m)
            if r['stop_day'] == 'D0' and d1 is not None:
                r['d0_mtm_at_stop_quote'] = float(cash - cum[d1])
            pe = oc[(oc.t_dec > ts) & (oc.side == 'Sell') & (oc.label == 'open') & (oc.tp != 's_')]
            sec = (pe.t_fill - ts).dt.total_seconds()
            r.update(short_entries_after_stop=len(pe), short_entry_lots_after_stop=float(pe.lots.sum()), short_entries_within_60s=int((sec <= 60).sum()),
                     short_entries_after_5min=int((sec > 300).sum()), last_short_entry_seconds_after_stop=float(sec.max()) if len(pe) else np.nan,
                     body_orders_entered_before_stop_filled_after=int(((pe.om <= ts.floor('min')) & (pe.tp == 'num')).sum()))
        rows.append(r)
    return pd.DataFrame(rows)


# ============================== PHASE 2b: placebo ladder (falsification, nothing is selected) ==============================
PLACEBO = (0.02, 0.04, 0.08, 0.16, 0.32, 0.64)

def phase2_placebo():
    """Repeat A, B (contract level) and E (portfolio, ownership as traded) at other percentages. If 4 % were the rule, the response
    should change sharply at 4 %; a smooth curve means the crossing measures 'price went up', not a 4 % instruction."""
    import rr_common as rc
    o = orders(); mk = markets(); L = {c: ledger(c) for c in ('cheap', 'fifo')}
    rows = []
    orig = rc.CARRY_PCT
    try:
        for pct in PLACEBO:
            globals()['CARRY_PCT'] = pct
            ev = []
            for (u, e) in cycle_keys():
                m = mk[(u, e)]; d1, d0 = d_bounds(m)
                if d1 is None or d0 is None: continue
                oc = o[(o.und == u) & (o.expiry == e)].reset_index(drop=True); om = order_minutes(oc, m)
                for c in ('cheap', 'fifo'):
                    B = CycleBook(u, e, c, L[c], m)
                    if not (B.carried & (B.sg < 0)).any(): continue
                    for dfn in ('A', 'B'):
                        for x in _contract_tests(B, oc, om, dfn): x.update(convention=c); ev.append(x)
                    s, denom = _portfolio_series(B, 'E', False); tc = first_cross(s, -pct * denom, d0)
                    gt1, gt2 = _liquidation_events(B, oc, om)
                    s_in = _portfolio_action(B, oc, om, tc, carried_only=True)[0] if tc is not None else False
                    ev.append(dict(definition='E', convention=c, cross_minute=tc, classification=('matched (cycle stop within 5 min)' if s_in else 'false trigger') if tc is not None else 'none',
                                   gt1=gt1 is not None))
            E = pd.DataFrame(ev)
            for (dfn, c), g in E.groupby(['definition', 'convention']):
                cr = g.cross_minute.notna(); cls = g.classification.astype(str)
                r = dict(pct=pct, definition=dfn, convention=c, crossings=int(cr.sum()))
                if dfn in ('A', 'B'):
                    io = g.cross_in_open_bin.fillna(False).astype(bool)
                    r.update(matched=int((cls == 'matched stop').sum()), false_triggers=int(cls.str.startswith('false').sum()),
                             precision=(cls == 'matched stop').sum() / cr.sum() if cr.sum() else np.nan,
                             recall=(cls == 'matched stop').sum() / g.first_stoplike_buyback_minute.notna().sum(),
                             hit_rate_after_open=float((cls[cr & ~io] == 'matched stop').mean()) if (cr & ~io).any() else np.nan, crossings_after_open=int((cr & ~io).sum()),
                             baseline_after_open=g.base_later_hits.sum() / g.base_later_n.sum() if g.base_later_n.sum() else np.nan)
                else:
                    r.update(matched=int(cls.str.startswith('matched').sum()), false_triggers=int((cls == 'false trigger').sum()),
                             d0_cycle_stops=int(g.gt1.sum()), recall_cycle_stop=cls.str.startswith('matched').sum() / g.gt1.sum() if g.gt1.sum() else np.nan)
                rows.append(r)
    finally:
        globals()['CARRY_PCT'] = orig
    return pd.DataFrame(rows)
