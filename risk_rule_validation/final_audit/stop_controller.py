"""Final dependency audit, task 2: interaction of the `s_` cycle-stop module with the normal body logic, order by order.

Evidence levels for "was this order submitted before or after the stop?" (the export has no submission timestamps):
  proven   - the order's first fill precedes the stop decision (before); or its broker order number is above the first `s_` order
             number of the SAME number block (after: numbers are a submission sequence only inside a block, DAT-12); or it is a
             tagged order (h_/v_/m_) whose embedded decision time is before / after the stop decision.
  bounded  - number below the first `s_` number of its block but filled after the decision: submitted before the stop module's
             first submission in that block; whether before the decision instant itself cannot be shown.
  inferred - its block has no `s_` order: only the order-entry minute (minute resolution) is available.
  undetermined - block without `s_` and same order-entry minute as the stop.
Position roles use fill-time accounting (running net position per contract at each fill).
Fill times are whole seconds, decision times are microseconds: a fill in the decision second cannot be ordered against the decision.
The position 'at the decision' is therefore the position before the decision second; post-stop events are fills in later seconds.

Outputs (risk_rule_validation/): stop_controller_order_timelines.csv, stop_inventory_transitions.csv
        (final_audit/results/): stop_post_short_causes.csv, stop_module_overlap.csv, stop_controller_summary.csv, schedule_propensity.csv
python3 risk_rule_validation/final_audit/stop_controller.py
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE)
sys.path.insert(0, RR); sys.path.insert(0, os.path.join(RR, 'followup'))
import rr_common as rc
from stop_sequence import load
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
PRE_S = 120; REPL_S = 60


def clock_window(t):
    """PR #3 taxonomy clock label of a time: grid A (:16/:31/:46/:01 slots, +55..180 s), A0 (first 55 s of a quarter), Clock B (last 75 s / first 15 s)."""
    ph = ((t - t.normalize() - pd.Timedelta('09:15:00')).total_seconds()) % 900
    if ph >= 13 * 60 + 45 or ph < 15: return 'clock B window'
    if 55 <= ph < 180: return 'grid A slot window'
    if ph < 55: return 'quarter start (A0)'
    return 'off-grid'


def all_roles(d):
    """fill-level roles for every fill in the export (running net position per contract)"""
    d = d.sort_values(['t', 'row']).copy()
    so = np.zeros(len(d)); sc = np.zeros(len(d)); lo = np.zeros(len(d)); lc = np.zeros(len(d)); nb = np.zeros(len(d)); net = {}
    for i, (k, s, q) in enumerate(zip(zip(d.und, d.expiry, d.cp, d.strike), d.side, d.lots.values)):
        n = net.get(k, 0.0); nb[i] = n
        if s == 'Sell': a = min(max(n, 0.0), q); lc[i] = a; so[i] = q - a; n -= q
        else: a = min(max(-n, 0.0), q); sc[i] = a; lo[i] = q - a; n += q
        net[k] = n
    d['short_open'] = so; d['short_close'] = sc; d['long_open'] = lo; d['long_close'] = lc; d['net_before'] = nb
    return d


def submission_class(r, ts, first_no):
    """(class, evidence) for one order row r (non-s_)"""
    kb = (r.app, r.block)
    if r.t_fill < ts.floor('s'): return 'before the stop decision', 'proven: first fill in an earlier second than the decision'
    if r.dec_exact and r.tp in ('h_', 'v_', 'm_'):
        if r.t_dec > ts: return 'after the stop decision', 'proven: tag decision time'
        return 'before the stop decision (in flight)', 'proven: tag decision time (fill in or after the decision second)'
    if r.t_fill < ts: return 'undetermined', 'none: fill in the decision second (fills are stamped to the second)'
    if kb in first_no:
        if r.no > first_no[kb]: return 'after the stop decision', 'proven: order number above the first s_ order of its block'
        return 'before the first s_ submission of its block (in flight)', 'bounded: order number below the first s_ order of its block'
    if r.om < ts.floor('min'): return 'before the stop decision (in flight)', 'inferred: order-entry minute'
    if r.om > ts.floor('min'): return 'after the stop decision', 'inferred: order-entry minute'
    return 'undetermined', 'none: block without s_, same order-entry minute'


def main():
    o, d = load()
    d = all_roles(d)
    oa = o.set_index('oid')[['no', 'app', 'block', 'om', 't_dec', 'dec_exact', 't_fill', 'lots', 'label', 'tp']].rename(columns={'lots': 'order_lots', 'tp': 'module'})
    d = d.join(oa, on='oid')
    d['date'] = d.t.dt.normalize(); d['hhmm'] = d.t.dt.strftime('%H:%M'); d['day_type'] = np.where(d.date == d.expiry, 'D0', 'D-1')
    stops = d[d.module == 's_'].groupby(['und', 'expiry']).t_dec.min()
    stop_cycles = set(stops.index)
    # ---- schedule propensity: share of NON-stop sessions (same underlying, same day type) with a body short-opening fill in the same clock minute
    ns = d[[(u, e) not in stop_cycles for u, e in zip(d.und, d.expiry)]]
    nsess = ns.groupby(['und', 'day_type']).date.nunique()
    bso = ns[(ns.module == 'num') & (ns.short_open > 0)]
    prop = (bso.groupby(['und', 'day_type', 'hhmm']).date.nunique() / nsess).rename('propensity').reset_index()
    prop.to_csv(os.path.join(OUT, 'schedule_propensity.csv'), index=False)
    P = prop.set_index(['und', 'day_type', 'hhmm']).propensity

    TL, INV, CAUSE, OVER, SUMM = [], [], [], [], []
    for (u, e), ts in stops.items():
        day = ts.normalize(); dt = 'D0' if day == e else 'D-1'
        dc = d[(d.und == u) & (d.expiry == e)].sort_values(['t', 'row'])
        oc = o[(o.und == u) & (o.expiry == e) & (o.date == day)]
        s_ord = oc[oc.tp == 's_']
        first_no = {(a, b): g.no.min() for (a, b), g in s_ord.groupby(['app', 'block'])}
        ts_sec = ts.floor('s')       # fills are stamped to the whole second: only fills of EARLIER seconds are certainly before the decision
        pos0 = dc[dc.t < ts_sec].groupby(['cp', 'strike']).sl.sum(); pos0 = pos0[pos0 != 0]
        pos_incl = dc[dc.t < ts].groupby(['cp', 'strike']).sl.sum()
        sclass = {r.oid: (('stop module', 'tag s_') if r.tp == 's_' else submission_class(r, ts, first_no)) for r in oc.itertuples()}
        w = dc[(dc.date == day) & (dc.t >= ts - pd.Timedelta(seconds=PRE_S))].copy()
        run = dc[dc.t < ts - pd.Timedelta(seconds=PRE_S)].groupby(['cp', 'strike']).sl.sum().to_dict()
        last_sbuy = {}; last_bbuy = {}; closed_before = set(dc[(dc.date == day) & (dc.t < ts - pd.Timedelta(seconds=PRE_S)) & (dc.short_close > 0)][['cp', 'strike']].itertuples(index=False, name=None))
        t_flat_first = None; t_flat_last = None; seq = 0; was_short = True
        for r in w.itertuples():
            seq += 1; k = (r.cp, r.strike); run[k] = run.get(k, 0.0) + r.sl
            sh = {c: sum(-v for (cc, _), v in run.items() if cc == c and v < 0) for c in ('CE', 'PE')}
            lg = {c: sum(v for (cc, _), v in run.items() if cc == c and v > 0) for c in ('CE', 'PE')}
            tot_s = sh['CE'] + sh['PE']
            cls, ev = sclass[r.oid]
            rel = (r.t - ts).total_seconds()
            TL.append(dict(und=u, expiry=e.date(), stop_day=dt, stop_decision=ts, event_seq=seq, fill_time=r.t, seconds_from_stop=round(rel, 3), order_no=r.no, number_block=r.block,
                           app_key=r.app, module=r.module, side=r.side, cp=r.cp, strike=r.strike, fill_lots=r.lots, order_lots=r.order_lots, order_entry_minute=r.om,
                           tag_decision_time=r.t_dec if r.dec_exact else pd.NaT, submission_vs_stop=cls, submission_evidence=ev,
                           short_open_lots=r.short_open, short_close_lots=r.short_close, long_open_lots=r.long_open, long_close_lots=r.long_close,
                           contract_net_after=run[k], pr3_label=r.label))
            INV.append(dict(und=u, expiry=e.date(), event_seq=seq, fill_time=r.t, seconds_from_stop=round(rel, 3), module=r.module, action=f'{r.side} {r.cp} {int(r.strike)} x{int(r.lots)}',
                            short_lots_ce=sh['CE'], short_lots_pe=sh['PE'], long_lots_ce=lg['CE'], long_lots_pe=lg['PE'], short_lots_total=tot_s, long_lots_total=lg['CE'] + lg['PE'],
                            short_contracts=sum(1 for v in run.values() if v < 0), long_contracts=sum(1 for v in run.values() if v > 0), short_book_flat=tot_s < 1e-9))
            if r.t >= ts:
                if tot_s < 1e-9:
                    if t_flat_first is None: t_flat_first = r.t
                    if was_short: t_flat_last = r.t
                    was_short = False
                else: was_short = True
                # ---- causes of post-stop short openings
                if r.short_open > 0:
                    ls, lb = last_sbuy.get(r.cp), last_bbuy.get(r.cp)
                    held_long = pos0.get(k, 0.0) > 0
                    base = dict(und=u, expiry=e.date(), stop_decision=ts, event_seq=seq, fill_time=r.t, seconds_from_stop=round(rel, 3), order_no=r.no, module=r.module, cp=r.cp, strike=r.strike,
                                short_open_lots=r.short_open, order_lots=r.order_lots, position_before_decision_second=pos0.get(k, 0.0), submission_vs_stop=cls, submission_evidence=ev,
                                clock=clock_window(r.t), schedule_propensity_non_stop_sessions=float(P.get((u, dt, r.hhmm), 0.0)),
                                within_60s_after_body_buyback_same_right=bool(lb is not None and 0 <= (r.t - lb).total_seconds() <= REPL_S),
                                within_60s_after_s_buyback_same_right=bool(ls is not None and 0 <= (r.t - ls).total_seconds() <= REPL_S),
                                contract_bought_back_earlier_in_session=k in closed_before, contract_long_at_stop=held_long)
                    CAUSE.append(base)
            if r.short_close > 0:
                closed_before.add(k)
                if r.module == 's_': last_sbuy[r.cp] = r.t
                else: last_bbuy[r.cp] = r.t
        # ---- stop-module orders that overshoot (sell more than is held long / buy more than is short at the fill)
        ws = w[(w.module == 's_')]
        for oid, g in ws.groupby('oid', sort=False):
            g0 = g.iloc[0]; k = (g0.cp, g0.strike); over = g.short_open.sum() if g0.side == 'Sell' else g.long_open.sum()
            if over <= 0: continue
            p0 = pos0.get(k, 0.0); t1 = g.t.min()
            between = w[(w.cp == g0.cp) & (w.strike == g0.strike) & (w.side == g0.side) & (w.t >= ts_sec) & (w.t <= t1) & (w.oid != oid) & (w.row < g.row.min())]
            nb_ = between[between.module != 's_']; sb_ = between[between.module == 's_']
            snap = (g0.order_lots == abs(p0)) and ((p0 > 0) == (g0.side == 'Sell')) and p0 != 0
            if p0 == 0 or (p0 > 0) != (g0.side == 'Sell'): cl = 'contract not held in that direction at the decision'
            elif len(nb_) and len(sb_): cl = 'overlap with non-stop-module orders and an earlier stop-module order'
            elif len(nb_): cl = 'overlap with non-stop-module liquidation of the same position'
            elif len(sb_): cl = 'duplicate: an earlier stop-module order already liquidated it'
            else: cl = 'no earlier liquidation found'
            first_s_buy = w[(w.module == 's_') & (w.short_close > 0) & (w.cp == g0.cp) & (w.t >= ts_sec)].t.min()
            OVER.append(dict(und=u, expiry=e.date(), stop_decision=ts, order_no=g0.no, number_block=g0.block, side=g0.side, cp=g0.cp, strike=g0.strike, order_lots=g0.order_lots,
                             position_before_decision_second=p0, position_incl_decision_second=float(pos_incl.get(k, 0.0)), order_qty_equals_position_at_decision=bool(snap), overshoot_lots=over,
                             other_lots_filled_in_decision_second=float(between[between.t < ts].lots.sum()), first_fill=t1, seconds_from_stop=(t1 - ts).total_seconds(),
                             non_stop_module_lots_between=float(nb_.lots.sum()), non_stop_modules=','.join(sorted(set(nb_.module))), stop_module_lots_before=float(sb_.lots.sum()),
                             non_stop_orders_submission=';'.join(sorted({sclass[x][0] for x in nb_.oid})), non_stop_first_fill=nb_.t.min() if len(nb_) else pd.NaT,
                             first_s_short_buyback_same_right=first_s_buy,
                             sequence_s_buyback_then_other_sale_then_s_sale=bool(len(nb_) and pd.notna(first_s_buy) and first_s_buy <= nb_.t.min() <= t1) if g0.side == 'Sell' else np.nan,
                             classification=cl))
        C = pd.DataFrame([x for x in CAUSE if x['und'] == u and x['expiry'] == e.date()])
        O = pd.DataFrame([x for x in OVER if x['und'] == u and x['expiry'] == e.date()])
        wa = w[w.t >= ts]
        SUMM.append(dict(und=u, expiry=e.date(), stop_decision=ts, stop_day=dt, short_lots_at_decision=float(-pos0[pos0 < 0].sum()), long_lots_at_decision=float(pos0[pos0 > 0].sum()),
                         s_orders=int(ws.oid.nunique()), s_first_fill_s=(ws.t.min() - ts).total_seconds(), s_last_fill_s=(ws.t.max() - ts).total_seconds(),
                         s_blocks=len(first_no), fills_after_decision=len(wa),
                         non_s_orders_after_decision_proven=int(wa[(wa.module != 's_')].oid.map(lambda x: sclass[x][0] == 'after the stop decision' and sclass[x][1].startswith('proven')).groupby(wa[wa.module != 's_'].oid).first().sum()),
                         non_s_orders_in_flight=int(wa[(wa.module != 's_')].oid.map(lambda x: 'in flight' in sclass[x][0]).groupby(wa[wa.module != 's_'].oid).first().sum()),
                         non_s_orders_undetermined=int(wa[(wa.module != 's_')].oid.map(lambda x: sclass[x][0] == 'undetermined').groupby(wa[wa.module != 's_'].oid).first().sum()),
                         post_stop_short_open_lots_non_s=float(C[C.module != 's_'].short_open_lots.sum()) if len(C) else 0.0, post_stop_short_open_lots_s=float(C[C.module == 's_'].short_open_lots.sum()) if len(C) else 0.0,
                         s_overshoot_orders=len(O), s_overshoot_lots=float(O.overshoot_lots.sum()) if len(O) else 0.0,
                         seconds_to_first_flat=(t_flat_first - ts).total_seconds() if t_flat_first is not None else np.nan,
                         seconds_to_final_flat=(t_flat_last - ts).total_seconds() if t_flat_last is not None else np.nan,
                         short_lots_end_of_session=float(sum(-v for v in run.values() if v < 0)), long_lots_end_of_session=float(sum(v for v in run.values() if v > 0))))
    TL = pd.DataFrame(TL); INV = pd.DataFrame(INV); CAUSE = pd.DataFrame(CAUSE); OVER = pd.DataFrame(OVER); SUMM = pd.DataFrame(SUMM)
    TL.to_csv(os.path.join(RR, 'stop_controller_order_timelines.csv'), index=False); INV.to_csv(os.path.join(RR, 'stop_inventory_transitions.csv'), index=False)
    CAUSE.to_csv(os.path.join(OUT, 'stop_post_short_causes.csv'), index=False); OVER.to_csv(os.path.join(OUT, 'stop_module_overlap.csv'), index=False)
    SUMM.to_csv(os.path.join(OUT, 'stop_controller_summary.csv'), index=False)
    pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40)
    print(SUMM.T.to_string())
    return TL, INV, CAUSE, OVER, SUMM


if __name__ == '__main__':
    main()
