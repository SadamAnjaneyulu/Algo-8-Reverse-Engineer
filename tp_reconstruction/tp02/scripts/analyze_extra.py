"""TP-02 supplementary tables: stop-cycle sequences (A), wing / hedge exits (E), per-cycle and per-underlying consistency, matching-convention sensitivity,
chance-adjusted unexplained range for Pop 3, decay distributions of Pop 3 / Pop 4S (H1 descriptive).
python3 tp_reconstruction/tp02/scripts/analyze_extra.py"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp02_common as c
from analyze_mechanisms import Null, load
CFG = c.CFG; A = c.ANALYSIS; SH = CFG['replacement']['null_shifts_seconds']


def stop_cycles(T, L, R):
    """for each cycle with a stop-module (s_) sequence: decision vs fill time of the stop, and what other modules do inside the window (execution time)"""
    w = CFG['stop']['cycle_window']; Rf = R[R.method == 'FIFO'].merge(L[['src_row', 'und', 'expiry', 'module', 'parent_oid', 'cp', 'strike', 't_fill']], on='src_row'); rows = []
    s = L[L.module == 's_'].copy(); s['dec'] = [c.decode_tag_time(o, t) for o, t in zip(s.parent_oid, s.t_fill)]
    for (u, e), g in s.groupby(['und', 'expiry']):
        start = min(g.t_fill.min(), g.dec.min()) - pd.Timedelta(seconds=w['before_seconds']); end = g.t_fill.max() + pd.Timedelta(seconds=w['after_seconds'])
        x = Rf[(Rf.und == u) & (Rf.expiry == e) & (Rf.t_fill >= start) & (Rf.t_fill <= end)]; ts = T[(T.und == u) & (T.expiry == e) & (T.t_exec >= start) & (T.t_exec <= end)]
        op = x[(x.open_qty > 0) & (x.sgn < 0)]; short_close = ts[ts.direction == -1]
        rows.append(dict(und=u, expiry=e.date(), first_stop_decision=g.dec.min(), first_stop_fill=g.t_fill.min(), decision_to_fill_s=(g.t_fill.min() - g.dec.min()).total_seconds() if pd.notna(g.dec.min()) else np.nan, last_stop_fill=g.t_fill.max(), stop_fills=len(g), stop_units=int(g.qty_units.sum()),
                         window_closings_short_s_=int((short_close.module == 's_').sum()), window_closings_short_num=int((short_close.module == 'num').sum()), window_closings_short_h_=int((short_close.module == 'h_').sum()), window_closings_long=int((ts.direction == 1).sum()),
                         window_closings_short_stable_profit=int(short_close.pop1_profit_stable.sum()), window_short_openings_total=len(op), window_short_openings_s_=int((op.module == 's_').sum()), window_short_openings_num=int((op.module == 'num').sum()), window_short_openings_h_=int((op.module == 'h_').sum()),
                         stop_at_open=bool(g.t_fill.min().hour * 60 + g.t_fill.min().minute < 9 * 60 + 30)))
    S = pd.DataFrame(rows); S.to_csv(os.path.join(A, 'stop_cycle_summary.csv'), index=False); return S


def wing_tables(T, L, R, null):
    X = T[T.direction == 1].copy(); S = T[T.direction == -1]; ww = CFG['wing']['link_window_seconds']
    cs = null.CS; link = []; chance = []
    for r in X.itertuples():
        g = cs[r.und]; ep = g.epoch.values; s = g.iloc[np.searchsorted(ep, r.epoch - ww, 'left'):np.searchsorted(ep, r.epoch + ww, 'right')]; link.append(bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any()))
        cc = []
        for sh in SH:
            ti = r.epoch + sh; tod = (ti - r.epoch + (r.t_exec - r.date).total_seconds()) // 60 - 555
            if 0 <= tod < 375: s = g.iloc[np.searchsorted(ep, ti - ww, 'left'):np.searchsorted(ep, ti + ww, 'right')]; cc.append(bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any()))
        chance.append(np.mean(cc) if cc else np.nan)
    X['body_short_closing_within_10s_same_right'] = link; X['chance'] = chance
    rows = []
    for mod, d in list(X.groupby('module')) + [('ALL long closings', X)]:
        rows.append(dict(module=mod, closings=len(d), units=int(d.qty_closed.sum()), share_of_long_closings=len(d) / len(X), gross_pnl_FIFO=round(d.pnl_rupees_FIFO.sum(), 1), gross_pnl_LIFO=round(d.pnl_rupees_LIFO.sum(), 1), gross_pnl_AVG=round(d.pnl_rupees_AVG.sum(), 1),
                         stable_profit_share=(d.consensus_label == 'PROFIT').mean(), stable_loss_share=(d.consensus_label == 'LOSS').mean(), median_exit_ratio_FIFO=d.exit_ratio_FIFO.median(), share_partial=(d.exit_type == 'PARTIAL').mean(),
                         share_with_body_short_closing_within_10s_same_right=d.body_short_closing_within_10s_same_right.mean(), chance_rate=d.chance.mean(), cycles=d.cycle.nunique()))
    W = pd.DataFrame(rows); W.to_csv(os.path.join(A, 'wing_exit_summary.csv'), index=False)
    # quantity relation: body short closing units vs wing partner units (+-10 s, same right), body closings that have a partner
    return W


def union_chance(S, null):
    """share of Pop 3 events that would carry at least one registered flag if the closing time were shifted (chance baseline for the union)"""
    reg = null.reg; em = CFG['expiry']['expiry_management_flag']; rw = CFG['replacement']['window_seconds']; ww = CFG['wing']['link_window_seconds']; vals = []; comp = {k: [] for k in ('clock', 'expiry', 'replacement', 'wing')}
    for u, g in S.groupby('und'):
        os_, cl = null.OS[u], null.CL[u]; eo, ec = os_.epoch.values, cl.epoch.values
        for sh in SH:
            for r in g.itertuples():
                ti = r.epoch + sh; sec = (r.t_exec - r.date).total_seconds() + sh; tod = sec // 60 - 555
                if not (0 <= tod < 375): continue
                mm = int(sec // 60); hhmm = f'{mm // 60:02d}:{mm % 60:02d}'; ph = c.phase_of([mm])[0]
                f_clock = hhmm in reg; f_exp = (r.day_type == em['day']) and ph in em['phases']
                s = os_.iloc[np.searchsorted(eo, ti, 'right'):np.searchsorted(eo, ti + rw, 'right')]; f_rep = bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any())
                s = cl.iloc[np.searchsorted(ec, ti - ww, 'left'):np.searchsorted(ec, ti + ww, 'right')]; f_w = bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any())
                vals.append(f_clock or f_exp or f_rep or f_w); comp['clock'].append(f_clock); comp['expiry'].append(f_exp); comp['replacement'].append(f_rep); comp['wing'].append(f_w)
    return float(np.mean(vals)), {k: float(np.mean(v)) for k, v in comp.items()}


def main():
    T = load(); L = c.tp01('fill_event_ledger.parquet'); R = c.tp01('fill_roles.parquet'); null = Null(L, R); S3 = T[(T.direction == -1) & T.pop3_clean_nonstop]; S = T[T.direction == -1]
    sc = stop_cycles(T, L, R); W = wing_tables(T, L, R, null)
    # ---- per cycle / per underlying consistency
    def agg(g):
        return pd.Series(dict(short_closings=len(g), units=int(g.qty_closed.sum()), stop_confirmed=int((g.stop_class == 'STOP_CONFIRMED').sum()), stop_possible=int((g.stop_class == 'STOP_POSSIBLE').sum()), clock=int(g.flag_clock.sum()), expiry_mgmt=int(g.flag_expiry_mgmt.sum()),
                              replacement=int(g.flag_replacement.sum()), wing_linked=int(g.flag_wing_linked.sum()), basket=int(g.flag_basket.sum()), stable_profit=int(g.pop1_profit_stable.sum()), pop3=int(g.pop3_clean_nonstop.sum()), pop4_registered=int(g.pop4_unexplained_body.sum()), pop4s_strict=int(g.pop4s_unexplained_strict.sum())))
    bc = S.groupby(['und', 'expiry']).apply(agg, include_groups=False).reset_index(); bc.to_csv(os.path.join(A, 'mechanism_by_cycle.csv'), index=False)
    bu = S.groupby('und').apply(agg, include_groups=False).reset_index(); bu['stop_confirmed_share'] = bu.stop_confirmed / bu.short_closings; bu['stop_possible_share'] = bu.stop_possible / bu.short_closings; bu['pop3_share_of_stable_profit'] = bu.pop3 / bu.stable_profit; bu.to_csv(os.path.join(A, 'mechanism_by_underlying.csv'), index=False)
    # ---- matching-convention sensitivity of the mechanism shares
    rows = []
    for m in c.METHODS + ['STABLE (all three)']:
        d = S[S.pop1_profit_stable] if m.startswith('STABLE') else S[S[f'label_{m}'] == 'PROFIT']; n = len(d)
        rows.append(dict(profit_defined_by=m, profit_short_closings=n, stop_confirmed=(d.stop_class == 'STOP_CONFIRMED').mean(), stop_possible=(d.stop_class == 'STOP_POSSIBLE').mean(), stop_not_evidenced=(d.stop_class == 'STOP_NOT_EVIDENCED').mean(), clock=d.flag_clock.mean(), expiry_mgmt=d.flag_expiry_mgmt.mean(),
                         replacement=d.flag_replacement.mean(), replacement_strict=d.flag_replacement_strict.mean(), wing_linked=d.flag_wing_linked.mean(), basket=d.flag_basket.mean(), body_module=(d.module == 'num').mean(), stable_across_conventions=d.pop1_profit_stable.mean()))
    pd.DataFrame(rows).to_csv(os.path.join(A, 'mechanism_by_convention.csv'), index=False)
    # ---- Pop 3 chance-adjusted unexplained range
    u_obs = (S3.flag_clock | S3.flag_expiry_mgmt | S3.flag_replacement | S3.flag_wing_linked).mean(); u_null, comp = union_chance(S3, null); us_obs = (S3.flag_clock | S3.flag_expiry_mgmt | S3.flag_replacement_strict | S3.flag_wing_linked_strict).mean()
    rows = [dict(item='Pop 3 events', value=len(S3)), dict(item='cycles', value=S3.cycle.nunique()), dict(item='registered union flag rate', value=u_obs), dict(item='chance union flag rate (time-shifted)', value=u_null), dict(item='excess over chance', value=u_obs - u_null),
            dict(item='unexplained, registered flags (events)', value=int((~(S3.flag_clock | S3.flag_expiry_mgmt | S3.flag_replacement | S3.flag_wing_linked)).sum())), dict(item='unexplained, strict flags (events)', value=int(S3.pop4s_unexplained_strict.sum())),
            dict(item='unexplained upper range: 1 - (flag rate - chance), events', value=int(round(len(S3) * (1 - (u_obs - u_null))))), dict(item='strict unexplained and not in a multi-contract batch (events)', value=int((S3.pop4s_unexplained_strict & ~S3.flag_basket).sum())),
            dict(item='strict unexplained and not in a batch and not stop-adjacent (adverse >= 1.15x)', value=int((S3.pop4s_unexplained_strict & ~S3.flag_basket & ~S3['stop_adverse_premium_1.15']).sum()) if 'stop_adverse_premium_1.15' in S3 else np.nan)]
    rows += [dict(item=f'chance rate of flag: {k}', value=v) for k, v in comp.items()]
    pd.DataFrame(rows).to_csv(os.path.join(A, 'unexplained_range_pop3.csv'), index=False)
    # ---- H1 descriptive: decay-ratio distribution and cluster rule for Pop 3 and Pop 4S under each convention
    from test_hypotheses import BinHazard  # noqa: F401  (import check only)
    from analyze_mechanisms import FLAGS  # noqa: F401
    h = CFG['hypotheses']['H1_decay']; out = []
    for name, d in (('Pop 3', S3), ('Pop 4S', S[S.pop4s_unexplained_strict]), ('Pop 4 registered', S[S.pop4_unexplained_body])):
        for m in c.METHODS:
            ratio = 100 * d[f'exit_ratio_{m}']; b = (np.floor(ratio / h['bins_pct']) * h['bins_pct']).clip(0, 95); cnt = b.value_counts().reindex(np.arange(0, 100, h['bins_pct']), fill_value=0).sort_index(); v = cnt.values.astype(float)
            for i, key in enumerate(cnt.index):
                nb = [v[j] for j in range(max(0, i - 3), min(len(v), i + 4)) if j != i]; med = float(np.median(nb)) if nb else np.nan; ex = v[i] / med if med > 0 else np.nan
                out.append(dict(population=name, convention=m, bin_lo_pct=key, events=int(v[i]), neighbour_median=med, excess_ratio=ex, is_cluster=bool(v[i] >= h['min_count'] and ex >= h['excess_ratio']), pop_events=len(d)))
            pts = d[f'ref_px_{m}'] - d.px_fill
            out.append(dict(population=name, convention=m, bin_lo_pct=-1, events=len(d), neighbour_median=d[f'exit_ratio_{m}'].median(), excess_ratio=pts.median(), is_cluster=False, pop_events=len(d)))   # row -1: median exit ratio and median premium drop (points)
    H = pd.DataFrame(out); H.to_csv(os.path.join(A, 'h1_decay_distribution_by_population.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70); print(sc.to_string(index=False)); print(W.round(3).to_string(index=False)); print(pd.DataFrame(rows).to_string(index=False)); print(H[H.is_cluster])


if __name__ == '__main__':
    main()
