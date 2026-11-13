"""TP-02 Phase 2: event timeline around every closing fill (all 17,760; short and long).
python3 tp_reconstruction/tp02/scripts/build_exit_timelines.py  ->  tp02/data/exit_event_timelines.parquet
One row per closing fill. Decision, order-entry and fill times are kept separate; decision time is 'unavailable' for body orders."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp02_common as c
W = c.WINDOWS


def counts(times, lo, hi):
    """number of sorted `times` in the closed interval [lo, hi] for each query bound"""
    return np.searchsorted(times, hi, 'right') - np.searchsorted(times, lo, 'left')


def build():
    L = c.tp01('fill_event_ledger.parquet'); R = c.tp01('fill_roles.parquet'); X = c.tp01('exit_event_consensus.parquet'); E = c.tp01('exit_events.parquet')
    Rf = R[R.method == 'FIFO'].set_index('src_row')
    blocks = c.number_blocks(L); Lx = L.set_index('src_row')
    T = X.copy()
    for col in ['parent_oid', 'order_no', 'app_key', 'order_entry_minute', 'qty_units', 'px_fill', 'dq_flag_any', 'epoch']: T[col] = Lx.loc[T.close_row, col].values
    T['t_exec'] = T.t_fill; T['epoch'] = T.epoch.astype('int64')
    # ---- three separate times
    T['decision_time'] = [c.decode_tag_time(o, t) if m != 'num' else pd.NaT for o, t, m in zip(T.parent_oid, T.t_exec, T.module)]
    T['decision_time_source'] = np.where(T.decision_time.notna(), 'tag (exact, microseconds)', 'unavailable (body order or inconsistent tag)')
    par = L.groupby('parent_oid').agg(parent_first_fill=('t_fill', 'min'), parent_last_fill=('t_fill', 'max'), parent_fills=('src_row', 'size'))
    T = T.join(par, on='parent_oid'); T['order_entry_after_first_fill'] = T.order_entry_minute > T.parent_first_fill        # the entry stamp has minute precision and can exceed the first fill by < 60 s (1 case); the bound then uses the first fill
    T['decision_lower_bound'] = np.where(T.decision_time.notna(), T.decision_time, np.minimum(T.order_entry_minute, T.parent_first_fill))
    T['decision_upper_bound'] = np.where(T.decision_time.notna(), T.decision_time, T.parent_first_fill)
    T['order_entry_to_fill_s'] = (T.t_exec - T.order_entry_minute).dt.total_seconds()
    T = T.join(blocks.rename(columns={'app_key': 'app', 'block': 'num_block', 'no': 'order_number'}), on='parent_oid')
    # ---- state before the exit (convention-free), reference premium and decay ratio per convention
    T['inventory_before_units'] = Rf.loc[T.close_row, 'inventory_before'].values.astype(float); T['inventory_before_lots'] = T.inventory_before_units.abs() / T.und.map(c.LOT)
    T['exit_qty_lots'] = T.qty_closed / T.und.map(c.LOT)
    for m in c.METHODS:
        e = E[E.method == m].set_index('close_row'); T[f'ref_px_{m}'] = e.loc[T.close_row, 'entry_px'].values; T[f'exit_ratio_{m}'] = e.loc[T.close_row, 'exit_px'].values / T[f'ref_px_{m}']
        T[f'pnl_rupees_{m}'] = e.loc[T.close_row, 'pnl'].values
    # ---- previous fill / order in the same contract
    Ls = L.sort_values('seq'); prev = Ls.groupby('contract_id').shift(1)
    pv = pd.DataFrame({'src_row': Ls.src_row.values, 'prev_epoch': prev.epoch.values, 'prev_side': prev.side.values, 'prev_qty': prev.qty_units.values, 'prev_parent': prev.parent_oid.values, 'prev_module': prev.module.values}).set_index('src_row')
    T = T.join(pv, on='close_row'); T['prev_fill_dt_s'] = T.epoch - T.prev_epoch; T['prev_same_order'] = T.prev_parent == T.parent_oid
    # ---- event classes (convention-free roles)
    Rr = Rf.reset_index().merge(L[['src_row', 'und', 'cp', 'strike', 'parent_oid', 'module']], on='src_row')
    ev = {'C_short': Rr[(Rr.close_qty > 0) & (Rr.inventory_before < 0)], 'C_long': Rr[(Rr.close_qty > 0) & (Rr.inventory_before > 0)],
          'O_short': Rr[(Rr.open_qty > 0) & (Rr.sgn < 0)], 'O_long': Rr[(Rr.open_qty > 0) & (Rr.sgn > 0)]}
    A = {}                               # (class, und) -> dataframe sorted by epoch
    for k, d in ev.items():
        for u, g in d.groupby('und'): A[(k, u)] = g.sort_values('epoch')
    rows = []
    for r in T.itertuples():
        u, t, cp, cid, par = r.und, r.epoch, r.cp, r.contract_id, r.parent_oid; f = dict(close_row=r.close_row)
        for w in W:
            for k in ('C_short', 'C_long'):
                g = A[(k, u)]; ep = g.epoch.values; lo = np.searchsorted(ep, t - w, 'left'); hi = np.searchsorted(ep, t + w, 'right'); s = g.iloc[lo:hi]
                s = s[(s.src_row != r.close_row) & (s.parent_oid != par)]
                f[f'n_{k}_other_pm{w}s'] = len(s); f[f'n_{k}_other_contracts_pm{w}s'] = s.contract_id.nunique() if len(s) else 0
            g = A[('C_short', u)]; ep = g.epoch.values; s = g.iloc[np.searchsorted(ep, t, 'right'):np.searchsorted(ep, t + w, 'right')]
            f[f'n_next_close_same_contract_{w}s'] = int((s.contract_id == cid).sum())
            for k in ('O_short', 'O_long'):
                g = A[(k, u)]; ep = g.epoch.values; s = g.iloc[np.searchsorted(ep, t, 'right'):np.searchsorted(ep, t + w, 'right')]; s = s[s.parent_oid != par]
                f[f'n_{k}_same_contract_next{w}s'] = int((s.contract_id == cid).sum()); f[f'n_{k}_same_right_other_strike_next{w}s'] = int(((s.cp == cp) & (s.contract_id != cid)).sum()); f[f'n_{k}_opposite_right_next{w}s'] = int((s.cp != cp).sum())
        rows.append(f)
    F = pd.DataFrame(rows); T = T.merge(F, on='close_row')
    # ---- next same-contract close and next replacement-type opening (time, quantity, sequence evidence), within the longest window
    wmax = max(W); first = {}
    cs = A[('C_short', 'NIFTY')]
    nxt = []; 
    for r in T.itertuples():
        g = A[('C_short', r.und)]; ep = g.epoch.values; i0 = np.searchsorted(ep, r.epoch, 'right'); i1 = np.searchsorted(ep, r.epoch + 24 * 3600, 'right'); s = g.iloc[i0:i1]; s = s[s.contract_id == r.contract_id]
        n1 = s.iloc[0] if len(s) else None
        g2 = A[('O_short', r.und)]; ep2 = g2.epoch.values; s2 = g2.iloc[np.searchsorted(ep2, r.epoch, 'right'):np.searchsorted(ep2, r.epoch + wmax, 'right')]; s2 = s2[s2.parent_oid != r.parent_oid]; s2r = s2[s2.cp == r.cp]
        rep = s2r.iloc[0] if len(s2r) else None; rel = None
        if rep is not None: rel = 'same_contract' if rep.contract_id == r.contract_id else 'same_right_other_strike'
        elif len(s2): rep = s2.iloc[0]; rel = 'opposite_right'
        seq = 'unknown'
        if rep is not None:
            a = blocks.loc[rep.parent_oid] if rep.parent_oid in blocks.index else None
            if a is not None and not pd.isna(r.num_block) and a.app_key == r.app and a.block == r.num_block: seq = 'opening_order_submitted_after' if a.no > r.order_number else 'opening_order_submitted_before'
        nxt.append(dict(close_row=r.close_row, next_close_same_contract_dt_s=(n1.epoch - r.epoch) if n1 is not None else np.nan, next_close_same_contract_units=n1.close_qty if n1 is not None else np.nan,
                        first_open_dt_s=(rep.epoch - r.epoch) if rep is not None else np.nan, first_open_relation=rel, first_open_units=rep.open_qty if rep is not None else np.nan, first_open_strike=rep.strike if rep is not None else np.nan,
                        first_open_module=rep.module if rep is not None else None, first_open_sequence_evidence=seq))
    T = T.merge(pd.DataFrame(nxt), on='close_row')
    return T


def main():
    T = build(); T.to_parquet(os.path.join(c.DATA, 'exit_event_timelines.parquet'), index=False); print(T.shape)
    print(T[['decision_time_source']].value_counts().to_dict()); print(T.first_open_relation.value_counts(dropna=False).to_dict()); print(T.first_open_sequence_evidence.value_counts().to_dict())


if __name__ == '__main__':
    main()
