"""TP-03 Phase 1: cycle-level entry timeline and B6 D-1 vs D0 accounting (opening / closing / net / gross, identity check, reconciliation to TP-01). Descriptive; no hypothesis test."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec
tc.assert_frozen(); A = tc.ANALYSIS; D = ec.Data(); RF = D.RF.copy(); BASE = ec.BASE; STEP = ec.STEP
W = pd.read_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet')); P = pd.read_csv(os.path.join(A, 'p1_e5_strike_orders.csv'), parse_dates=['E', 'first_fill', 'date', 'expiry']) if os.path.exists(os.path.join(A, 'p1_e5_strike_orders.csv')) else None
# ---------------------------------------------------------------- B6 accounting
RF['signed'] = RF.sgn * RF.qty_units; RF['day_type'] = np.where(RF.date == RF.expiry, 'D0', 'pre-expiry'); RF['cycle'] = RF.und + '|' + RF.expiry.dt.strftime('%Y-%m-%d')
RF = RF.sort_values(['contract_id', 't_fill', 'src_row']); RF['cum'] = RF.groupby('contract_id').signed.cumsum(); RF['cum_before'] = RF.cum - RF.signed
g = RF.groupby(['cycle', 'und', 'day_type', 'contract_id']).agg(open_u=('open_qty', 'sum'), close_u=('close_qty', 'sum'), gross_u=('qty_units', 'sum'), inv_start=('cum_before', 'first'), inv_end=('cum', 'last'), cp=('cp', 'first')).reset_index()
g['identity_gap'] = (g.open_u - g.close_u) - (g.inv_end.abs() - g.inv_start.abs()); idg = g.identity_gap.abs()
rows = []
for (cy, und, dt), x in g.groupby(['cycle', 'und', 'day_type']):
    f = RF[(RF.cycle == cy) & (RF.day_type == dt)]
    rows.append(dict(cycle=cy, und=und, day_type=dt, parent_orders=f.parent_oid.nunique(), fills=len(f), contracts=x.contract_id.nunique(), opened_units=x.open_u.sum(), closed_units=x.close_u.sum(), net_gross_book_change=x.open_u.sum() - x.close_u.sum(), gross_traded_units=x.gross_u.sum(),
                     start_gross_inventory=x.inv_start.abs().sum(), end_gross_inventory=x.inv_end.abs().sum(), start_short_units=-x.inv_start[x.inv_start < 0].sum(), end_short_units=-x.inv_end[x.inv_end < 0].sum(), start_long_units=x.inv_start[x.inv_start > 0].sum(), end_long_units=x.inv_end[x.inv_end > 0].sum(),
                     opened_CE=x[x.cp == 'CE'].open_u.sum(), opened_PE=x[x.cp == 'PE'].open_u.sum(), closed_CE=x[x.cp == 'CE'].close_u.sum(), closed_PE=x[x.cp == 'PE'].close_u.sum(), identity_gap=float(x.identity_gap.sum())))
B6 = pd.DataFrame(rows); B6.to_csv(os.path.join(A, 'p1_b6_cycle_daytype_accounting.csv'), index=False)
S = B6.groupby(['day_type']).agg(cycle_sessions=('cycle', 'size'), parent_orders=('parent_orders', 'sum'), fills=('fills', 'sum'), opened_units=('opened_units', 'sum'), closed_units=('closed_units', 'sum'), net_gross_book_change=('net_gross_book_change', 'sum'), gross_traded_units=('gross_traded_units', 'sum'), end_gross_inventory=('end_gross_inventory', 'sum')).reset_index()
S['opened_per_fill'] = S.opened_units / S.fills; S['closed_share_of_opened'] = S.closed_units / S.opened_units; tot = dict(day_type='TOTAL', cycle_sessions=int(S.cycle_sessions.sum()), parent_orders=int(S.parent_orders.sum()), fills=int(S.fills.sum()), opened_units=float(S.opened_units.sum()), closed_units=float(S.closed_units.sum()), net_gross_book_change=float(S.net_gross_book_change.sum()), gross_traded_units=float(S.gross_traded_units.sum()))
S = pd.concat([S, pd.DataFrame([tot])], ignore_index=True); S.to_csv(os.path.join(A, 'p1_b6_summary.csv'), index=False)
final = RF.groupby('contract_id').signed.sum(); chk = dict(max_abs_contract_identity_gap=float(idg.max()), contracts_checked=int(len(g)), opened_total=float(RF.open_qty.sum()), closed_total=float(RF.close_qty.sum()), remaining_gross=float(final.abs().sum()), matches_TP01=bool(RF.open_qty.sum() == 1414545 and RF.close_qty.sum() == 1377065 and final.abs().sum() == 37480))
pd.DataFrame([chk]).to_csv(os.path.join(A, 'p1_b6_identity_check.csv'), index=False)
bu = B6.groupby('und').agg(opened=('opened_units', 'sum'), closed=('closed_units', 'sum')); print(S.to_string()); print(chk)
# ---------------------------------------------------------------- cycle timeline
OFF = pd.read_csv(os.path.join(A, 'p1_off_window_events.csv')); Pn = D.parents.copy(); Pn['cycle'] = Pn.und + '|' + Pn.expiry.dt.strftime('%Y-%m-%d'); L = D.L; rows = []
flat_times = {}
for (und, ex), g_ in RF.groupby(['und', 'expiry']):
    gg = g_.sort_values(['t_fill', 'src_row']); inv = {}; tot_short = 0.0; seen = False; flats = []; last_t = None; sec = gg.groupby('t_fill')
    for t, blk in sec:
        for r in blk.itertuples(): inv[r.contract_id] = inv.get(r.contract_id, 0) + r.sgn * r.qty_units
        s = -sum(v for v in inv.values() if v < 0)
        if s > 0: seen = True
        if seen and s == 0 and tot_short > 0: flats.append(t)
        tot_short = s
    flat_times[(und, ex)] = flats
for c in D.cycles.itertuples():
    pn = Pn[(Pn.und == c.und) & (Pn.expiry == c.expiry)].sort_values('first_fill'); w = W[W.cycle == c.cycle]; pre = pn[pn.date < pn.expiry] if len(pn) else pn
    first = pn.iloc[0] if len(pn) else None; init = pn[pn.E == pn.E.min()] if len(pn) else pn; wing = RF[(RF.und == c.und) & (RF.expiry == c.expiry) & (RF.module == 'h_') & (RF.sgn > 0) & (RF.open_qty > 0)].sort_values('t_fill')
    r3 = np.nan; r3k = np.nan
    ix = D.idx[c.und].close; d0 = pd.Timestamp(c.first) + pd.Timedelta(hours=9, minutes=15); s0 = ix.get(d0, np.nan); r3k = STEP[c.und] * np.floor(s0 / STEP[c.und] + 0.5) if np.isfinite(s0) else np.nan
    fin = RF[(RF.und == c.und) & (RF.expiry == c.expiry)].groupby('contract_id').signed.sum() if False else (RF[(RF.und == c.und) & (RF.expiry == c.expiry)].groupby('contract_id').signed.sum())
    sh = fin[fin < 0]; lg = fin[fin > 0]; ce = lambda s_: float(sum(v for k, v in s_.items() if '|CE|' in k)); pe = lambda s_: float(sum(v for k, v in s_.items() if '|PE|' in k))
    stp = D.stops.get((c.und, c.expiry), pd.NaT); fl = flat_times.get((c.und, c.expiry), [])
    rows.append(dict(cycle=c.cycle, und=c.und, expiry=c.expiry, first_session=c.first, has_pre_session=bool(c.has_pre), has_D0_session=bool(c.has_d0), first_body_short_order_minute=first.E if first is not None else pd.NaT, first_body_short_fill=first.first_fill if first is not None else pd.NaT,
                     first_short_CE_fill=pn[pn.cp == 'CE'].first_fill.min() if len(pn) else pd.NaT, first_short_PE_fill=pn[pn.cp == 'PE'].first_fill.min() if len(pn) else pd.NaT, initial_entry_parents=len(init), initial_short_units_CE=float(init[init.cp == 'CE'].base_units.sum()), initial_short_units_PE=float(init[init.cp == 'PE'].base_units.sum()),
                     initial_strikes=','.join(map(str, sorted(init.strike.unique()))), atm_R3_0915=r3k, initial_strike_minus_R3_steps=float((init.strike.mean() - r3k) / STEP[c.und]) if len(init) and np.isfinite(r3k) else np.nan,
                     first_wing_fill=wing.t_fill.min() if len(wing) else pd.NaT, first_wing_strike=wing.strike.iloc[0] if len(wing) else np.nan, wing_parent_orders=wing.parent_oid.nunique(), body_short_parent_orders=len(pn), distinct_short_strikes=pn.strike.nunique(), window_actions_V2=int((w.view2_class == 'ACTION').sum()),
                     no_action_active_windows=int((w.view2_class == 'NO_ACTION_ACTIVE').sum()), off_window_parents=int(((OFF.cycle == c.cycle) & (OFF.event_class == 'OFF_WINDOW_ACTION')).sum()), quantity_units_added_pre=float(pre.base_units.sum()) if len(pre) else 0.0, quantity_units_added_D0=float(pn[pn.date == pn.expiry].base_units.sum()),
                     book_flat_events=len(fl), reentry_after_first_flat=(bool((pn.first_fill > fl[0]).any()) if len(fl) else False), cycle_stop_time=stp, final_short_units_CE=-ce(sh), final_short_units_PE=-pe(sh), final_long_units_CE=ce(lg), final_long_units_PE=pe(lg)))
TL = pd.DataFrame(rows); TL.to_csv(os.path.join(A, 'p1_cycle_entry_timeline.csv'), index=False); print(TL[['cycle', 'first_body_short_order_minute', 'initial_short_units_CE', 'initial_short_units_PE', 'initial_strike_minus_R3_steps', 'body_short_parent_orders', 'no_action_active_windows', 'book_flat_events', 'reentry_after_first_flat']].head(40).to_string())
