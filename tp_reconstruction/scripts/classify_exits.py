"""Phase 3-4: classify every closed quantity and build the exit-event dataset + matching-sensitivity / profitability summaries.
python3 tp_reconstruction/scripts/classify_exits.py
Writes data/exit_events.parquet (closing fill x method), data/exit_event_consensus.parquet (one row per closing fill),
analysis/profitability_summary.csv, matching_sensitivity.csv, expiry_level_summary.csv, underlying_level_summary.csv"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp_common as tc, matching as mt
LABELS = ['PROFIT', 'LOSS', 'BREAKEVEN', 'UNRESOLVED']


def label_pieces(P):
    """piece-level labels (closed rows only); UNRESOLVED when the closing fill's open/close role depends on an unresolvable tie"""
    C = P[P.row_type == 'CLOSED'].copy()
    C['label'] = mt.classify(C.pnl_pts.values, tc.TOL); C.loc[C.order_ambiguous, 'label'] = 'UNRESOLVED'
    return C


def build_exit_events(C, L, roles, EP):
    """aggregate matched pieces to the closing fill (one row per closing fill and method)"""
    C = C.copy(); C['entry_val'] = C.entry_px * C.qty; C['exit_val'] = C.exit_px * C.qty; C['w_epoch'] = C.entry_epoch * C.qty
    for lab in ('PROFIT', 'LOSS', 'BREAKEVEN', 'UNRESOLVED'): C[f'qty_{lab.lower()}'] = np.where(C.label == lab, C.qty, 0)
    g = C.groupby(['method', 'close_row'])
    E = g.agg(contract_id=('contract_id', 'first'), und=('und', 'first'), expiry=('expiry', 'first'), strike=('strike', 'first'), cp=('cp', 'first'), episode_id=('episode_id', 'first'), direction=('direction', 'first'),
              qty_closed=('qty', 'sum'), entry_val=('entry_val', 'sum'), exit_val=('exit_val', 'sum'), pnl=('pnl', 'sum'), w_epoch=('w_epoch', 'sum'), first_entry_epoch=('entry_epoch', 'min'), exit_epoch=('exit_epoch', 'first'),
              n_pieces=('qty', 'size'), qty_profit=('qty_profit', 'sum'), qty_loss=('qty_loss', 'sum'), qty_breakeven=('qty_breakeven', 'sum'), qty_unresolved=('qty_unresolved', 'sum'),
              n_same=('session_relation', lambda s: (s == 'SAME_SESSION').sum()), n_carried=('session_relation', lambda s: (s == 'CARRIED').sum()), n_mixed=('session_relation', lambda s: (s == 'MIXED').sum()),
              order_ambiguous=('order_ambiguous', 'max'), cycle_d1_missing=('cycle_d1_missing', 'max')).reset_index()
    E['entry_px'] = E.entry_val / E.qty_closed; E['exit_px'] = E.exit_val / E.qty_closed; E['pnl_pts_per_unit'] = E.pnl / E.qty_closed
    E['abs_price_change'] = E.exit_px - E.entry_px; E['pct_change_vs_entry'] = 100 * E.abs_price_change / E.entry_px; E['exit_pct_of_entry'] = 100 * E.exit_px / E.entry_px
    E['mean_entry_epoch'] = E.w_epoch / E.qty_closed; E['t_exit'] = pd.to_datetime(E.exit_epoch, unit='s') + pd.Timedelta(hours=5, minutes=30)
    E['hold_minutes_mean'] = (E.exit_epoch - E.mean_entry_epoch) / 60; E['hold_minutes_oldest'] = (E.exit_epoch - E.first_entry_epoch) / 60
    E['label'] = mt.classify(E.pnl_pts_per_unit.values, tc.TOL); E.loc[E.order_ambiguous, 'label'] = 'UNRESOLVED'
    E['session_relation'] = np.where(E.n_carried + E.n_mixed == 0, 'SAME_SESSION', np.where(E.n_same + E.n_mixed == 0, 'CARRIED', 'MIXED'))
    E['qty_lots'] = E.qty_closed / E.und.map(tc.LOT); E['gross_pnl_rupees'] = E.pnl; E['net_pnl_rupees'] = np.nan; E['net_pnl_note'] = 'unavailable: no charge fields in the raw file'
    R = roles.drop_duplicates(['method', 'src_row']).set_index(['method', 'src_row'])
    j = R.loc[list(zip(E.method, E.close_row))]; E['inventory_before'] = j.inventory_before.values; E['inventory_after_close_part'] = np.where(j.open_qty.values > 0, 0, j.inventory_after.values)
    E['remaining_after_units'] = E.inventory_after_close_part.abs(); E['is_reversal_fill'] = j.is_reversal.values
    E['exit_type'] = np.where(E.is_reversal_fill, 'FULL_WITH_REVERSAL', np.where(E.remaining_after_units > 0, 'PARTIAL', 'FULL'))
    lm = L.set_index('src_row'); E['t_fill'] = lm.loc[E.close_row, 't_fill'].values; E['date'] = lm.loc[E.close_row, 'date'].values; E['module'] = lm.loc[E.close_row, 'module'].values
    E['parent_oid'] = lm.loc[E.close_row, 'parent_oid'].values; E['dq_flag_any'] = lm.loc[E.close_row, 'dq_flag_any'].values; E['dte_calendar_days'] = (E.expiry - E.date).dt.days
    # original opened quantity of the position: before this exit and in total
    ro = roles.drop_duplicates(['method', 'src_row']).sort_values(['method', 'epoch', 'src_row']); ro['episode_key'] = ro.episode_opened
    opened_before = {}
    for m, x in ro.groupby('method'):
        x = x[x.open_qty > 0].copy(); x['cum'] = x.groupby('episode_opened').open_qty.cumsum(); opened_before[m] = x.set_index('src_row').cum
    ep = EP.set_index(['method', 'episode_id'])
    E['position_opened_units_total'] = ep.loc[list(zip(E.method, E.episode_id)), 'opened_units'].values
    E['position_max_units'] = ep.loc[list(zip(E.method, E.episode_id)), 'max_units'].values
    E['position_identity'] = 'CONTRACT_INVENTORY_EPISODE (lot ownership not identified)'
    E['matching_convention'] = E.method; E['event_id'] = [f'{m}-{r}' for m, r in zip(E.method, E.close_row)]
    E['ambiguity_flag'] = np.where(E.order_ambiguous, 'ORDER_AMBIGUOUS', '')
    return E.drop(columns=['entry_val', 'exit_val', 'w_epoch', 'inventory_after_close_part'])


def consensus(E):
    W = E.pivot(index='close_row', columns='method', values='label'); P = E.pivot(index='close_row', columns='method', values='pnl_pts_per_unit')
    W.columns = [f'label_{c}' for c in W.columns]; P.columns = [f'pnl_pts_{c}' for c in P.columns]
    base = E[E.method == tc.METHODS[0]].set_index('close_row')[['contract_id', 'und', 'expiry', 'strike', 'cp', 'direction', 'qty_closed', 't_fill', 'date', 'module', 'episode_id', 'exit_type', 'session_relation', 'exit_pct_of_entry', 'hold_minutes_mean', 'order_ambiguous']]
    X = base.join(W).join(P)
    lab = X[[f'label_{m}' for m in tc.METHODS]]
    same = lab.nunique(axis=1) == 1
    X['stability'] = np.where(X.order_ambiguous, 'UNRESOLVED_ORDER', np.where(same, 'STABLE', 'CONVENTION_SENSITIVE'))
    X['consensus_label'] = np.where(X.order_ambiguous, 'UNRESOLVED', np.where(same, lab.iloc[:, 0], 'CONVENTION_SENSITIVE'))
    return X.reset_index()


def summaries(P, C, E, X, EP):
    out = {}
    rows = []
    for m in tc.METHODS:
        c = C[C.method == m]; e = E[E.method == m]
        for lab in LABELS:
            cc = c[c.label == lab]; ee = e[e.label == lab]
            rows.append(dict(level='matched piece', method=m, label=lab, count=len(cc), units=int(cc.qty.sum()), lots=round(cc.qty_lots.sum(), 2), gross_pnl_rupees=round(cc.pnl.sum(), 2), share_of_closed_units=round(cc.qty.sum() / c.qty.sum(), 4)))
            rows.append(dict(level='closing fill', method=m, label=lab, count=len(ee), units=int(ee.qty_closed.sum()), lots=round(ee.qty_lots.sum(), 2), gross_pnl_rupees=round(ee.pnl.sum(), 2), share_of_closed_units=round(ee.qty_closed.sum() / e.qty_closed.sum(), 4)))
        for lab in LABELS[:3]:
            f = EP[(EP.method == m) & (EP.remaining_status == 'CLOSED')]; ff = f[f.label == lab]
            rows.append(dict(level='position (fully closed)', method=m, label=lab, count=len(ff), units=int(ff.opened_units.sum()), lots=np.nan, gross_pnl_rupees=round(ff.realized_pnl.sum(), 2), share_of_closed_units=round(ff.opened_units.sum() / f.opened_units.sum(), 4)))
        for stt in ('EXPIRED_UNCLOSED', 'OPEN_AT_END_OF_DATA'):
            ff = EP[(EP.method == m) & (EP.remaining_status == stt)]
            rows.append(dict(level='position (remaining at end)', method=m, label=stt, count=len(ff), units=int(ff.remaining_units.sum()), lots=np.nan, gross_pnl_rupees=round(ff.realized_pnl.sum(), 2), share_of_closed_units=np.nan))
    out['profitability_summary'] = pd.DataFrame(rows)
    # ----- matching sensitivity
    rs = []
    for stt, g in X.groupby('stability'):
        rs.append(dict(section='closing-fill stability', key=stt, closing_fills=len(g), units=int(g.qty_closed.sum()), share_of_fills=round(len(g) / len(X), 4), share_of_units=round(g.qty_closed.sum() / X.qty_closed.sum(), 4)))
    for lab, g in X.groupby('consensus_label'):
        rs.append(dict(section='consensus label', key=lab, closing_fills=len(g), units=int(g.qty_closed.sum()), share_of_fills=round(len(g) / len(X), 4), share_of_units=round(g.qty_closed.sum() / X.qty_closed.sum(), 4)))
    for a, b in [('FIFO', 'LIFO'), ('FIFO', 'AVG'), ('LIFO', 'AVG')]:
        t = pd.crosstab(X[f'label_{a}'], X[f'label_{b}'])
        for ia in t.index:
            for ib in t.columns: rs.append(dict(section=f'label transition {a} -> {b}', key=f'{ia} -> {ib}', closing_fills=int(t.loc[ia, ib]), units=int(X[(X[f'label_{a}'] == ia) & (X[f'label_{b}'] == ib)].qty_closed.sum())))
    for m in tc.METHODS:
        rs.append(dict(section='total realised gross P&L (rupees)', key=m, closing_fills=int((E.method == m).sum()), units=int(C[C.method == m].qty.sum()), pnl_rupees=round(C[C.method == m].pnl.sum(), 2)))
    f = EP[EP.remaining_status == 'CLOSED']; pv = f.pivot(index='episode_id', columns='method', values='realized_pnl')
    rs.append(dict(section='fully closed positions: realised P&L identical across methods', key='positions', closing_fills=len(pv), pnl_rupees=float(np.abs(pv.max(axis=1) - pv.min(axis=1)).max()), units=np.nan))
    out['matching_sensitivity'] = pd.DataFrame(rs)
    # ----- by expiry and underlying (consensus view + per-method P&L)
    X2 = X.copy(); pn = {m: E[E.method == m].set_index('close_row').pnl for m in tc.METHODS}
    for m in tc.METHODS: X2[f'pnl_{m}'] = X2.close_row.map(pn[m]) if 'close_row' in X2 else X2.index.map(pn[m])
    ex = EP[EP.method == tc.METHODS[0]]
    def agg(key, g, keys):
        r = dict(zip(keys, key if isinstance(key, tuple) else (key,)))
        r.update(closing_fills=len(g), closed_units=int(g.qty_closed.sum()), closed_lots=round(float((g.qty_closed / g.und.map(tc.LOT)).sum()), 1), stable_share_units=round(g.loc[g.stability == 'STABLE', 'qty_closed'].sum() / g.qty_closed.sum(), 4),
                 **{f'pnl_{m}': round(g[f'pnl_{m}'].sum(), 2) for m in tc.METHODS})
        for lab in ('PROFIT', 'LOSS', 'BREAKEVEN'): r[f'units_stable_{lab.lower()}'] = int(g.loc[g.consensus_label == lab, 'qty_closed'].sum())
        r['units_convention_sensitive'] = int(g.loc[g.stability == 'CONVENTION_SENSITIVE', 'qty_closed'].sum()); r['units_unresolved_order'] = int(g.loc[g.stability == 'UNRESOLVED_ORDER', 'qty_closed'].sum())
        return r
    e1 = pd.DataFrame([agg(k, g, ['und', 'expiry']) for k, g in X2.groupby(['und', 'expiry'])])
    rem = ex.groupby(['und', 'expiry']).remaining_units.sum().rename('remaining_expired_unclosed_units').reset_index(); e1 = e1.merge(rem, on=['und', 'expiry'], how='left').fillna({'remaining_expired_unclosed_units': 0})
    out['expiry_level_summary'] = e1
    u1 = pd.DataFrame([agg(k, g, ['und', 'direction']) for k, g in X2.groupby(['und', 'direction'])]); out['underlying_level_summary'] = u1
    return out


def main():
    P = pd.read_parquet(os.path.join(tc.DATA, 'reconstructed_position_ledger.parquet')); L = pd.read_parquet(os.path.join(tc.DATA, 'fill_event_ledger.parquet'))
    roles = pd.read_parquet(os.path.join(tc.DATA, 'fill_roles.parquet')); EP = pd.read_parquet(os.path.join(tc.DATA, 'position_episodes.parquet'))
    C = label_pieces(P.drop(columns=['label'], errors='ignore')); P2 = P.drop(columns=['label'], errors='ignore').copy(); P2['label'] = pd.Series(index=P2.index, dtype=object); P2.loc[C.index, 'label'] = C.label.astype(object)            # pieces carry their label in the ledger too
    # episode-level label (fully closed only; remaining positions get no result label)
    EP['pnl_per_unit'] = EP.realized_pnl / EP.opened_units.replace(0, np.nan); EP['label'] = np.where(EP.remaining_status == 'CLOSED', mt.classify(EP.pnl_per_unit.fillna(0).values, tc.TOL), '')
    E = build_exit_events(C, L, roles, EP); X = consensus(E)
    P2.to_parquet(os.path.join(tc.DATA, 'reconstructed_position_ledger.parquet'), index=False); EP.to_parquet(os.path.join(tc.DATA, 'position_episodes.parquet'), index=False)
    E.to_parquet(os.path.join(tc.DATA, 'exit_events.parquet'), index=False); X.to_parquet(os.path.join(tc.DATA, 'exit_event_consensus.parquet'), index=False)
    S = summaries(P2, C, E, X, EP)
    for k, v in S.items(): v.to_csv(os.path.join(tc.ANALYSIS, f'{k}.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
    print(S['profitability_summary'].to_string(index=False)); print(S['matching_sensitivity'][S['matching_sensitivity'].section.isin(['closing-fill stability', 'consensus label', 'total realised gross P&L (rupees)', 'fully closed positions: realised P&L identical across methods'])].to_string(index=False))
    print(S['underlying_level_summary'].to_string(index=False))


if __name__ == '__main__':
    main()
