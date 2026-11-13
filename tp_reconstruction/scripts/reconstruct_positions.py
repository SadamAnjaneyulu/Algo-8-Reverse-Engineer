"""Phase 2-3: reconstruct positions under FIFO / LIFO / average cost and reconcile quantities.
python3 tp_reconstruction/scripts/reconstruct_positions.py
Writes data/reconstructed_position_ledger.parquet (piece level, methods stacked), data/position_episodes.parquet,
data/reconciliation_summary.csv, data/role_ambiguity_fills.csv"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp_common as tc, matching as mt
IST = pd.Timedelta(hours=5, minutes=30)


def to_t(epoch): return pd.to_datetime(epoch, unit='s') + IST


def build(L):
    amb = mt.role_ambiguity(L, tc.TIE_ORDERS)
    meta = L.drop_duplicates('contract_id').set_index('contract_id')[['und', 'expiry', 'strike', 'cp']]
    last_date = L.date.max(); dates_by_row = L.set_index('src_row').date
    d1 = L.groupby(['und', 'expiry']).date.min().reset_index(); d1['d1_in_export'] = d1.date < d1.expiry
    d1_missing = set(zip(d1[~d1.d1_in_export].und, d1[~d1.d1_in_export].expiry))
    pieces, rems, eps, roles_all = [], [], [], []
    for m in tc.METHODS:
        o = mt.run_matching(L, m, tc.PRIMARY_TIE); C, Rm, E, R = o['closures'].copy(), o['remaining'].copy(), o['episodes'].copy(), o['roles'].copy()
        C = C.join(meta, on='contract_id'); C['row_type'] = 'CLOSED'
        C['t_entry'] = to_t(C.entry_epoch); C['t_exit'] = to_t(C.exit_epoch); C['exit_date'] = C.t_exit.dt.normalize()
        first_open = C.open_rows.str.split(';').str[0].astype(int); last_open = C.open_rows.str.split(';').str[-1].astype(int)
        if m == 'AVG':     # a pool may hold lots opened on different days: take the min / max over its contributing fills
            dmin = C.open_rows.map(lambda s: min(dates_by_row[int(x)] for x in s.split(';'))); dmax = C.open_rows.map(lambda s: max(dates_by_row[int(x)] for x in s.split(';')))
        else:
            dmin = dmax = first_open.map(dates_by_row)
        C['entry_date_min'], C['entry_date_max'] = dmin.values, dmax.values
        C['session_relation'] = np.where(C.entry_date_max == C.exit_date, 'SAME_SESSION', np.where(C.entry_date_min < C.exit_date, np.where(C.entry_date_max == C.exit_date, 'MIXED', 'CARRIED'), 'SAME_SESSION'))
        C.loc[(C.entry_date_min < C.exit_date) & (C.entry_date_max == C.exit_date), 'session_relation'] = 'MIXED'
        C['order_ambiguous'] = C.close_row.isin(amb)
        C['qty_lots'] = C.qty / C.und.map(tc.LOT); C['cycle_d1_missing'] = [(u, e) in d1_missing for u, e in zip(C.und, C.expiry)]
        pieces.append(C)
        if len(Rm):
            Rm = Rm.join(meta, on='contract_id'); Rm['row_type'] = 'REMAINING'; Rm['t_entry'] = to_t(Rm.entry_epoch)
            Rm['status'] = np.where(Rm.expiry <= last_date, 'EXPIRED_UNCLOSED', 'OPEN_AT_END_OF_DATA'); Rm['qty_lots'] = Rm.qty / Rm.und.map(tc.LOT); rems.append(Rm)
        E = E.join(meta, on='contract_id'); E['remaining_status'] = np.where(E.remaining_units > 0, np.where(E.expiry <= last_date, 'EXPIRED_UNCLOSED', 'OPEN_AT_END_OF_DATA'), 'CLOSED')
        eps.append(E); R['method'] = m; roles_all.append(R)
    return dict(pieces=pd.concat(pieces, ignore_index=True), remaining=pd.concat(rems, ignore_index=True) if rems else pd.DataFrame(columns=['contract_id', 'episode_id', 'direction', 'qty', 'entry_px', 'entry_epoch', 'open_rows', 'method', 'status']), episodes=pd.concat(eps, ignore_index=True), roles=pd.concat(roles_all, ignore_index=True), ambiguous=amb)


def reconcile(L, B):
    """every fill unit is opened or closed; opened = closed + remaining (per contract and direction, per method); cash identity; ambiguity"""
    rows = []; Lk = L[~L.dq_duplicate_fill]
    for m in tc.METHODS:
        R = B['roles'][B['roles'].method == m]; Cm = B['pieces'][B['pieces'].method == m]; Rm = B['remaining'][B['remaining'].method == m]; E = B['episodes'][B['episodes'].method == m]
        fills_u = int(Lk.qty_units.sum()); op = int(R.open_qty.sum()); cl = int(R.close_qty.sum()); rem = int(Rm.qty.sum()); mc = int(Cm.qty.sum())
        # per contract x direction identity
        ek = E.groupby(['contract_id', 'direction']).agg(op=('opened_units', 'sum'), cl=('closed_units', 'sum'), rem=('remaining_units', 'sum'))
        bad = int(((ek.op - ek.cl - ek.rem) != 0).sum())
        cash = float(-(Lk.sgn * Lk.qty_units * Lk.px_fill).sum()); bv = float(-(Rm.direction * Rm.qty * Rm.entry_px).sum()) if len(Rm) else 0.0; pn = float(Cm.pnl.sum())
        rows.append(dict(method=m, fill_rows=len(Lk), fill_units=fills_u, opened_units=op, closed_units=cl, matched_units=mc, remaining_units=rem,
                         unexplained_fill_units=fills_u - op - cl, unexplained_open_minus_close_minus_remaining=op - cl - rem, unmatched_closed_units=cl - mc,
                         contract_direction_cells=len(ek), cells_not_reconciling=bad, reversal_fills=int(R.is_reversal.sum()), reversal_units_reopened=int(R.loc[R.is_reversal, 'open_qty'].sum()),
                         episodes=len(E), episodes_closed=int((E.remaining_status == 'CLOSED').sum()), episodes_expired_unclosed=int((E.remaining_status == 'EXPIRED_UNCLOSED').sum()), episodes_open_at_end=int((E.remaining_status == 'OPEN_AT_END_OF_DATA').sum()),
                         remaining_expired_unclosed_units=int(Rm.loc[Rm.status == 'EXPIRED_UNCLOSED', 'qty'].sum()) if len(Rm) else 0, remaining_open_at_end_units=int(Rm.loc[Rm.status == 'OPEN_AT_END_OF_DATA', 'qty'].sum()) if len(Rm) else 0,
                         realized_gross_pnl_rupees=round(pn, 2), cash_flow_total=round(cash, 2), remaining_book_value=round(bv, 2), cash_identity_difference=round(cash - (pn + bv), 6),
                         fills_open_only=int(((R.open_qty > 0) & (R.close_qty == 0)).sum()), fills_close_only=int(((R.close_qty > 0) & (R.open_qty == 0)).sum()), fills_split_close_and_open=int(((R.close_qty > 0) & (R.open_qty > 0)).sum()),
                         fills_dq_flagged=int(L.dq_flag_any.sum()), fills_excluded_as_duplicates=int(L.dq_duplicate_fill.sum()),
                         remaining_short_units=int(Rm.loc[Rm.direction < 0, 'qty'].sum()) if len(Rm) else 0, remaining_long_units=int(Rm.loc[Rm.direction > 0, 'qty'].sum()) if len(Rm) else 0,
                         remaining_short_premium_collected=round(float((Rm.loc[Rm.direction < 0, 'qty'] * Rm.loc[Rm.direction < 0, 'entry_px']).sum()), 2) if len(Rm) else 0.0,
                         remaining_long_premium_paid=round(float((Rm.loc[Rm.direction > 0, 'qty'] * Rm.loc[Rm.direction > 0, 'entry_px']).sum()), 2) if len(Rm) else 0.0,
                         tie_ambiguous_fills=len(B['ambiguous'])))
    return pd.DataFrame(rows)


def main():
    L = pd.read_parquet(os.path.join(tc.DATA, 'fill_event_ledger.parquet')); B = build(L)
    P = pd.concat([B['pieces'], B['remaining'].rename(columns={'qty': 'qty'})], ignore_index=True, sort=False)
    P.insert(0, 'piece_id', np.arange(len(P)))
    P.to_parquet(os.path.join(tc.DATA, 'reconstructed_position_ledger.parquet'), index=False)
    B['episodes'].to_parquet(os.path.join(tc.DATA, 'position_episodes.parquet'), index=False)
    B['roles'].to_parquet(os.path.join(tc.DATA, 'fill_roles.parquet'), index=False)
    S = reconcile(L, B); S.to_csv(os.path.join(tc.DATA, 'reconciliation_summary.csv'), index=False)
    amb = L[L.src_row.isin(B['ambiguous'])][['src_row', 'contract_id', 't_fill', 'side', 'qty_units', 'px_fill', 'parent_oid', 'module']]; amb.to_csv(os.path.join(tc.DATA, 'role_ambiguity_fills.csv'), index=False)
    pd.set_option('display.width', 250); print(S.T.to_string()); print(amb.to_string(index=False))


if __name__ == '__main__':
    main()
