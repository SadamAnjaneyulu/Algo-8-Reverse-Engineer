"""TP-02 Phase 1: evidence flags and candidate mechanism for every closing fill (definitions registered in tp02/config.yaml).
python3 tp_reconstruction/tp02/scripts/classify_mechanisms.py -> tp02/data/exit_event_mechanisms.parquet
Flags are non-exclusive. STOP_NOT_EVIDENCED is not proof that no stop occurred (no decision logs exist)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp02_common as c
CFG = c.CFG


def stop_windows(L):
    s = L[L.module == 's_'].copy(); s['dec'] = [c.decode_tag_time(o, t) for o, t in zip(s.parent_oid, s.t_fill)]
    w = CFG['stop']['cycle_window']; g = s.groupby(['und', 'expiry']).agg(first_fill=('t_fill', 'min'), last_fill=('t_fill', 'max'), first_dec=('dec', 'min')).reset_index()
    g['start'] = g[['first_fill', 'first_dec']].min(axis=1) - pd.Timedelta(seconds=w['before_seconds']); g['end'] = g.last_fill + pd.Timedelta(seconds=w['after_seconds'])
    return g


def adverse_lookback(T, panel):
    """max mark / reference ratio over the previous N completed minutes of the contract (any convention); NaN if the panel has no fresh mark"""
    n = CFG['stop']['adverse_lookback_minutes']; panel = panel.copy(); panel['rmax'] = panel[[f'ratio_{m}' for m in c.METHODS]].max(axis=1)
    g = {k: (x.tod_min.values, x.rmax.values) for k, x in panel.sort_values('tod_min').groupby(['contract_id', 'date'])}
    out = []
    for r in T.itertuples():
        k = int((r.t_exec - r.date).total_seconds() // 60 - 555); a = g.get((r.contract_id, r.date))
        if a is None: out.append(np.nan); continue
        m = (a[0] >= k - n + 1) & (a[0] <= k); out.append(a[1][m].max() if m.any() else np.nan)
    return np.array(out) / 100.0          # the panel stores percent; thresholds are ratios


def link_features(T, L, R):
    """wing links (+-10 s, +-60 s) and basket evidence (+-5 s)"""
    Rf = R[R.method == 'FIFO'].merge(L[['src_row', 'und', 'cp', 'parent_oid']], on='src_row')
    CL = Rf[(Rf.close_qty > 0) & (Rf.inventory_before > 0)]; CS = Rf[(Rf.close_qty > 0) & (Rf.inventory_before < 0)]
    lab = T.set_index('close_row').pnl_rupees_FIFO
    wl = {(k, u): g.sort_values('epoch') for (k, u), g in [(('L', u), x) for u, x in CL.groupby('und')] + [(('S', u), x) for u, x in CS.groupby('und')]}
    out = []
    ww = [CFG['wing']['link_window_seconds']] + CFG['wing']['link_window_sensitivity']; bw = CFG['basket']['window_seconds']
    for r in T.itertuples():
        f = {}; g = wl[('L', r.und)]; ep = g.epoch.values
        for w in ww:
            s = g.iloc[np.searchsorted(ep, r.epoch - w, 'left'):np.searchsorted(ep, r.epoch + w, 'right')]; s = s[(s.parent_oid != r.parent_oid) & (s.cp == r.cp)]; f[f'wing_linked_pm{w}s'] = len(s) > 0
        g = wl[('S', r.und)]; ep = g.epoch.values; s = g.iloc[np.searchsorted(ep, r.epoch - bw, 'left'):np.searchsorted(ep, r.epoch + bw, 'right')]; s = s[(s.parent_oid != r.parent_oid) & (s.contract_id != r.contract_id)]
        g2 = wl[('L', r.und)]; e2 = g2.epoch.values; s3 = g2.iloc[np.searchsorted(e2, r.epoch - ww[0], 'left'):np.searchsorted(e2, r.epoch + ww[0], 'right')]; s3 = s3[(s3.parent_oid != r.parent_oid) & (s3.cp == r.cp)]
        f['wing_partner_same_units'] = bool(((s3.close_qty) == r.qty_closed).any()) if len(s3) else False
        f['basket_other_contracts'] = s.contract_id.nunique(); f['basket_other_rights'] = ''.join(sorted(set(s.cp))); f['basket_both_rights'] = (set(s.cp) | {r.cp}) == {'CE', 'PE'}
        f['basket_has_loss_leg'] = bool((lab.reindex(s.src_row).values < 0).any()) if len(s) else False
        out.append(f)
    return pd.DataFrame(out, index=T.index)


def classify():
    L = c.tp01('fill_event_ledger.parquet'); R = c.tp01('fill_roles.parquet'); T = pd.read_parquet(os.path.join(c.DATA, 'exit_event_timelines.parquet')); panel = c.tp01('short_exposure_panel.parquet')
    clk = pd.read_csv(os.path.join(c.REPO, CFG['inputs']['clock_clusters'])); reg = sorted(clk[clk.is_cluster].key)
    T['date'] = pd.to_datetime(T.date); T['expiry'] = pd.to_datetime(T.expiry)
    # ---- A stop
    sw = stop_windows(L); T = T.merge(sw[['und', 'expiry', 'start', 'end']], on=['und', 'expiry'], how='left')
    T['in_cycle_stop_window'] = (T.t_exec >= T.start) & (T.t_exec <= T.end); T = T.drop(columns=['start', 'end'])
    T['adverse_ratio_max_15m'] = adverse_lookback(T, panel.assign(date=pd.to_datetime(panel.date)))
    st = CFG['stop']; ar = st['adverse_ratio']
    T['own_ratio_max'] = T[[f'exit_ratio_{m}' for m in c.METHODS]].max(axis=1)
    short = T.direction == -1
    T['stop_adverse_premium'] = short & (T.adverse_ratio_max_15m >= ar); T['stop_own_price'] = short & (T.own_ratio_max >= st['own_price_ratio'])
    for s_ in st['adverse_ratio_sensitivity']: T[f'stop_adverse_premium_{s_}'] = short & (T.adverse_ratio_max_15m >= s_)
    T['stop_possible'] = T.in_cycle_stop_window | T.stop_adverse_premium | T.stop_own_price
    T['stop_class'] = np.where(T.module == 's_', 'STOP_CONFIRMED', np.where(T.stop_possible, 'STOP_POSSIBLE', 'STOP_NOT_EVIDENCED'))
    T['stop_reasons'] = [';'.join(k for k, v in (('cycle_stop_window', a), ('adverse_premium', b), ('own_price', d)) if v) for a, b, d in zip(T.in_cycle_stop_window, T.stop_adverse_premium, T.stop_own_price)]
    # ---- B clock, C expiry
    T['exec_minute'] = T.t_exec.dt.strftime('%H:%M'); T['flag_clock'] = T.exec_minute.isin(reg); T['registered_clock_minutes'] = ','.join(reg)
    T['day_type'] = np.where(T.date == T.expiry, 'EXPIRY_DAY', 'CARRY_DAY'); T['phase'] = c.phase_of(T.t_exec.dt.hour * 60 + T.t_exec.dt.minute)
    em = CFG['expiry']['expiry_management_flag']; T['flag_expiry_mgmt'] = (T.day_type == em['day']) & T.phase.isin(em['phases'])
    T['expiry_category'] = np.where(T.day_type == 'CARRY_DAY', 'D1_CARRY_DAY_REDUCTION', 'D0_' + T.phase)
    # ---- D replacement (short closings only)
    rw = CFG['replacement']['window_seconds']; T['flag_replacement'] = short & ((T[f'n_O_short_same_contract_next{rw}s'] + T[f'n_O_short_same_right_other_strike_next{rw}s']) > 0)
    # ---- E wing, H4 basket
    X = link_features(T, L, R); T = pd.concat([T, X], axis=1)
    T['flag_wing_module'] = T.module == 'h_'; w0 = CFG['wing']['link_window_seconds']; T['flag_wing_linked'] = short & (T.module == 'num') & T[f'wing_linked_pm{w0}s']
    T['flag_wing_linked_strict'] = T.flag_wing_linked & T.wing_partner_same_units
    T['flag_replacement_strict'] = T.flag_replacement & (T.first_open_sequence_evidence == 'opening_order_submitted_after') & (T.first_open_units == T.qty_closed)
    T['flag_basket'] = short & (T.basket_other_contracts >= CFG['basket']['min_other_contracts'])
    # ---- candidate mechanism: one flag -> that family; several -> MULTIPLE; none -> UNEXPLAINED
    fam = [('STOP_POSSIBLE', T.stop_class == 'STOP_POSSIBLE'), ('CLOCK', T.flag_clock), ('EXPIRY_MGMT', T.flag_expiry_mgmt), ('REPLACEMENT', T.flag_replacement), ('WING_LINKED', T.flag_wing_linked | T.flag_wing_module)]
    T['mechanism_flags'] = [';'.join(n for (n, m) in fam if m.iloc[i]) if False else '' for i in range(0)] or ''
    M = pd.DataFrame({n: m.values for n, m in fam}); T['mechanism_flags'] = [';'.join(k for k in M.columns if row[k]) for row in M.to_dict('records')]
    nfl = M.sum(axis=1).values
    mech = np.where(T.order_ambiguous, 'UNRESOLVED', np.where(T.module == 'm_', 'MANUAL', np.where(T.stop_class == 'STOP_CONFIRMED', 'STOP_CONFIRMED',
           np.where(nfl > 1, 'MULTIPLE_POSSIBLE_MECHANISMS', np.where(nfl == 1, T.mechanism_flags, np.where(T.module == 'num', 'UNEXPLAINED_BODY', np.where(T.module == 'v_', 'LUMP_MODULE', 'INSUFFICIENT_EVIDENCE')))))))
    T['candidate_mechanism'] = mech
    T['confidence'] = np.where(T.order_ambiguous, 'UNRESOLVED', np.where(T.stop_class == 'STOP_CONFIRMED', 'HIGH', np.where(nfl == 1, 'MEDIUM', np.where(nfl > 1, 'LOW', np.where(T.module == 'num', 'UNEXPLAINED', 'LOW')))))
    T['evidence'] = [f"stop:{a}({b});clock:{cl};expiry:{e};repl:{r};wing:{w}" for a, b, cl, e, r, w in zip(T.stop_class, T.stop_reasons, T.exec_minute.where(T.flag_clock, '-'), T.expiry_category, T.flag_replacement, T.flag_wing_linked | T.flag_wing_module)]
    # ---- profit classes and populations (short closings)
    T['profit_class'] = np.where(T.direction != -1, 'NOT_SHORT', np.where(T.consensus_label == 'PROFIT', 'STABLE_PROFIT', np.where(T[[f'label_{m}' for m in c.METHODS]].eq('PROFIT').any(axis=1), 'SENSITIVE_PROFIT', 'NOT_PROFIT')))
    T['pop1_profit_stable'] = T.profit_class == 'STABLE_PROFIT'; T['pop2_stop_related'] = short & T.stop_class.isin(['STOP_CONFIRMED', 'STOP_POSSIBLE'])
    T['pop3_clean_nonstop'] = T.pop1_profit_stable & (T.module == 'num') & (T.stop_class == 'STOP_NOT_EVIDENCED') & ~T.order_ambiguous & ~T.dq_flag_any
    T['pop4_unexplained_body'] = T.pop3_clean_nonstop & ~(T.flag_clock | T.flag_expiry_mgmt | T.flag_replacement | T.flag_wing_linked)
    T['pop4s_unexplained_strict'] = T.pop3_clean_nonstop & ~(T.flag_clock | T.flag_expiry_mgmt | T.flag_replacement_strict | T.flag_wing_linked_strict)
    return T


def main():
    T = classify(); T.to_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet'), index=False)
    s = T[T.direction == -1]; print(len(T), len(s)); print(s.stop_class.value_counts().to_dict()); print(s.candidate_mechanism.value_counts().to_dict())
    print({k: int(s[k].sum()) for k in ['pop1_profit_stable', 'pop2_stop_related', 'pop3_clean_nonstop', 'pop4_unexplained_body']})


if __name__ == '__main__':
    main()
