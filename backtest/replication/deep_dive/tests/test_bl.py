"""Body lifecycle (D-1 / D0) tests: invariants of the event tables, class definitions, and the structural results the report relies on (wide margins, not fitted thresholds). Needs the committed outputs."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import bl_common as C
OUT = C.OUT


def test_events_columns_and_order():
    for nm in ('d1', 'd0'):
        E = pd.read_csv(f'{OUT}/bl_events_{nm}.csv')
        assert {'time_IST', 'module', 'cls', 'right', 'side', 'strike', 'lots', 'strike_minus_ATMprev_steps', 'contract_net_after', 'S_after', 'L_after'} <= set(E.columns)
        for _, g in E.groupby(['und', 'expiry']): assert g.time_IST.is_monotonic_increasing
        assert (E.lots > 0).all() and E.side.isin(['Buy', 'Sell']).all()


def test_contract_net_is_cumulative_across_days():
    E = pd.concat([pd.read_csv(f'{OUT}/bl_events_d1.csv'), pd.read_csv(f'{OUT}/bl_events_d0.csv')]); g = E[(E.und == 'NIFTY') & (E.expiry == '2026-06-30')]
    for (cp, k), h in g.groupby(['right', 'strike']):
        assert (h.contract_net_after.values == np.cumsum(np.where(h.side == 'Buy', h.lots, -h.lots))).all()


def test_slot_minute_definition_and_partition():
    O = C.load_orders(); S = O[(O.module == 'num') & (O.role == 'open_short')]
    assert set(S.cls) == {'slot_minute', 'minute_before_slot', 'roll_sell', 'other'}
    sm = S[S.cls == 'slot_minute']; assert (((sm.tod - (9 * 3600 + 16 * 60)) // 60) % 15 == 0).all()
    assert O[O.module != 'num'].cls.isin(['hedge', 'stop', 'lump', 'manual']).all()


def test_previous_minute_reference_beats_current():
    O = C.load_orders(); sm = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0) & (O.cls == 'slot_minute')]
    assert (sm.strike == sm.atm_prev).mean() > (sm.strike == sm.atm_cur).mean() + 0.05
    d = sm[sm.atm_prev != sm.atm_cur]; assert (d.strike == d.atm_prev).mean() > 2 * (d.strike == d.atm_cur).mean()


def test_scheduled_entries_far_more_atm_than_other():
    A = pd.read_csv(f'{OUT}/bl_d1_A_class.csv').set_index('cls'); assert A.exact_prev['slot_minute'] > 0.75 and A.exact_prev['other'] < 0.35


def test_flatten_break_is_sharp():
    F = pd.read_csv(f'{OUT}/bl_d0_D_flatten_by_cycle.csv'); pre = F[F.d0 <= '2026-08-20']; post = F[F.d0 >= '2026-08-25']
    assert pre.share_1514.max() < 0.1 and post.share_1514.min() > 0.4 and len(pre) >= 10 and len(post) >= 8
    cs = pd.read_csv(f'{OUT}/bl_d0_D_close_shares.csv'); post_rows = cs[cs.post == True]; assert (post_rows.share_closed_1514_1515 > 0.95).all()


def test_d0_sells_mostly_at_existing_short_strikes():
    J = json.load(open(f'{OUT}/bl_summary_d0a.json')); assert J['status_share']['new_strike'] < 0.2 and J['status_share']['carried_strike'] + J['status_share']['existing_short_strike'] > 0.8


def test_overnight_inventory_nonempty_and_carry_share():
    J = json.load(open(f'{OUT}/bl_summary_d1b.json')); assert 0.5 < J['lots_carried'] / J['lots_sold'] < 0.9 and J['zero_short_cycles'] == 0


def test_report_sections():
    t = open(os.path.join(C.REP, 'BODY_LIFECYCLE_D1_D0_INVESTIGATION.md')).read()
    for h in ['## 1. Executive summary', '## 2. ATM reference', '## 3. D-1 study', '### 3A', '### 3B', '### 3C', '### 3D', '### 3E', '### 3F', '## 4. D0 study', '### 4A', '### 4B', '### 4C', '### 4D', '### 4E', '### 4F', '## 5. Deliverables', '## 6. Observed', '## 7. D-1 lifecycle model', '## 8. D0 lifecycle model']: assert h in t, h


def test_paired_sales_are_clock_driven_single_leg_are_not():
    S = pd.read_pickle(f'{OUT}/bl_trig_sells_d1.pkl.gz')
    ray = lambda x, p: abs(np.exp(2j * np.pi * (x % p) / p).mean())
    assert ray(S[S.paired].tod.values, 900) > 0.6 and ray(S[~S.paired].tod.values, 900) < 0.2 and ray(S[~S.paired].tod.values, 60) < 0.2


def test_single_leg_episodes_follow_favourable_moves():
    A = pd.read_csv(f'{OUT}/bl_trig_auc.csv').set_index('feature')
    for f in ('adv5', 'adv15', 'ratio_book', 'dev_book'): assert A.AUC[f] < 0.35 and A.hi[f] < 0.4 and A.holm_p[f] < 0.05
    assert A.holm_p['tslot'] > 0.05                                     # no clock effect inside the single-leg stream


def test_single_leg_strike_follows_premium_not_atm():
    R = pd.read_csv(f'{OUT}/bl_trig_strike_rules.csv').set_index('group'); r = R.loc['single-leg (all)']; assert r.PREVPX_exact > r.ATM_exact + 0.15 and r.PREVPX_exact > r.PREVPX_null_exact + 0.1
    assert R.loc['paired slot-minute (comparison)'].ATM_exact > 0.8


def test_move_trigger_d1_supported_d0_weak():
    A = pd.read_csv(f'{OUT}/bl_move_auc.csv'); a1 = A[A.day == 'D-1'].set_index('feature'); a0 = A[A.day == 'D0'].set_index('feature')
    assert a1.AUC['fav30'] > 0.7 and a1.lo['fav30'] > 0.65 and a1.AUC['own_ratio'] < 0.35 and abs(a1.AUC['book_loss'] - 0.5) < 0.1 and a0.AUC['fav30'] < 0.65


def test_move_trigger_holds_for_both_rights_and_without_closing_minutes():
    R = pd.read_csv(f'{OUT}/bl_move_robust.csv'); R = R[(R.day == 'D-1') & (R.feature == 'fav30')].set_index('subset')
    for k in ('CE only (calls into falls)', 'PE only (puts into rises)', 'NIFTY', 'SENSEX', 'excluding last 15 min (j<360)'): assert R.lo[k] > 0.65


def test_no_heavy_move_threshold_plateau():
    D = pd.read_csv(f'{OUT}/bl_move_dose.csv'); d = D[(D.day == 'D-1') & (D.feature == 'fav30')].reset_index(drop=True)
    assert d.rate_per_1000[2] > 5 * d.rate_per_1000[0] and d.rate_per_1000[2:].max() < 1.6 * d.rate_per_1000[2:4].max()


def test_breakout_variable_is_strong_on_d1_and_both_halves():
    B = pd.read_csv(f'{OUT}/bl_breakout_scan.csv').set_index(['day', 'feature']); r = B.loc[('D-1', 'bk15')]
    assert r.rate_on > 5 * r.rate_off and r.AUC_gain_over_baseline > 0.03 and r.lo > 0.01
    H = pd.read_csv(f'{OUT}/bl_breakout_halves.csv'); h = H[(H.day == 'D-1') & (H.feature == 'bk15')]; assert (h.rate_on > 5 * h.rate_off).all()


def test_breakout_beats_greeks_and_vol_groups():
    M = pd.read_csv(f'{OUT}/bl_final_models.csv'); m = M[(M.day == 'D-1') & (M.kind == 'lr')].set_index('model').AUC
    brk = m[[i for i in m.index if i.startswith('3 ')][0]]; gr = m[[i for i in m.index if i.startswith('5 ')][0]]; vo = m[[i for i in m.index if i.startswith('6 ')][0]]
    assert brk > gr + 0.03 and brk > vo + 0.03


def test_rejected_candidates_stay_rejected():
    S = pd.read_csv(f'{OUT}/bl_shape_results.csv').set_index(['day', 'feature']); assert abs(S.loc[('D-1', 'dev_pair'), 'univariate_AUC'] - 0.5) < 0.05 and abs(S.loc[('D-1', 'dev_pair'), 'AUC_gain']) < 0.01
    U = pd.read_csv(f'{OUT}/bl_var_univariate.csv').set_index(['day', 'feature']); assert abs(U.loc[('D-1', 'delta_need'), 'AUC'] - 0.5) < 0.06 and abs(U.loc[('D-1', 'mtm_tot'), 'AUC'] - 0.5) < 0.06
    T = pd.read_csv(f'{OUT}/bl_tilt_results.csv'); t = T[(T.day == 'D-1') & (T.item == 'fav_open') & (T.metric == 'baseline + tilt gap: AUC gain')].iloc[0]; assert t.lo < 0 < t.hi


def test_solo_variable_report_exists():
    t = open(os.path.join(C.REP, 'BODY_SOLO_VARIABLE_SEARCH.md')).read(); assert 'fresh favourable extreme' in t and '## 5. Conclusion' in t


def test_scheduled_slots_always_fire_and_others_do_not():
    EX = pd.read_csv(f'{OUT}/bl_slot_execution_d1.csv', index_col=0)
    for k in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13]: assert EX.executed[k] >= 0.96
    for k in (12, 14, 15): assert EX.executed[k] < 0.1
    T = pd.read_csv(f'{OUT}/bl_slot_d1_scheduled.csv'); w = T.pivot_table(index=['und', 'expiry', 'k'], columns='cp', values='lots_paired'); assert (w.CE == w.PE).mean() > 0.98


def test_no_state_variable_explains_slot_quantity():
    ST = pd.read_csv(f'{OUT}/bl_slot_state_tests.csv'); assert len(ST) >= 30 and ST.R2_gain.max() < 0.02 and ((ST.lo > 0) & (ST.R2_gain > ST.perm_null_max)).sum() == 0


def test_cycle_stop_halts_the_schedule():
    O = C.load_orders(); P = pd.read_csv(f'{OUT}/bl_slot_panel.csv'); stp = O[(O.module == 's_') & (O.dayno == 1)].groupby(['und', 'expiry']).tod.min(); d0 = P[(P.day == 'D0') & (P.cp == 'CE')]; aft = ex = 0
    for (u, e), g in d0.groupby(['und', 'expiry']):
        t = stp.get((u, e), np.nan)
        if t == t: m = (C.ref.OPEN_SEC + g.j * 60) >= t; aft += int(m.sum()); ex += int((g[m].lots_paired > 0).sum())
    assert aft > 100 and ex == 0


def test_slot_strike_is_atm_not_delta():
    R = pd.read_csv(f'{OUT}/bl_slot_strike_rules.csv'); r = R[R.day == 'D-1'].set_index('rule').exact; assert r['ATM'] > 0.9 and r['ATM'] > r['DELTA50'] + 0.2 and r['ATM'] > r['FWD'] + 0.2 and r['ATM'] > r['MINCP'] + 0.2 and r['HYST_1.0'] < r['ATM'] - 0.2


def test_d1_closes_follow_premium_move_not_delta():
    H = pd.read_csv(f'{OUT}/bl_close_hazard.csv'); h = H[(H.day == 'D-1') & (H.feature == 'ratio')].reset_index(drop=True); assert h.rate_per_1000.iloc[8] > 20 * h.rate_per_1000.iloc[2] and h.rate_per_1000.is_monotonic_increasing
    d = H[(H.day == 'D-1') & (H.feature == 'abs_delta')].reset_index(drop=True); assert d.rate_per_1000.iloc[-1] < d.rate_per_1000.max() / 3        # no delta limit: the deepest ITM bin is not the highest
    U = pd.read_csv(f'{OUT}/bl_close_univariate.csv').set_index(['day', 'feature']).AUC; assert U[('D-1', 'ratio')] > 0.7 and U[('D0', 'ratio')] < 0.6


# ---- buy-back (close) logic study: bl_close_build / bl_close_logic1-6 ----
def _flags(day='D-1'):
    F = pd.read_csv(f'{OUT}/bl_close_orders_flags.csv'); return F[F.day == day]


def test_close_orders_table_invariants():
    d = _flags(); assert len(d) == 1324 and (d.lots == 1).all()
    assert (d.n_open >= 1).all()                                         # every D-1 body buy-back closes a tracked body short
    assert (d.low <= d.high + 1e-9).all()                                # cheapest <= highest open entry (same lot list)
    one = d[d.n_open == 1]; assert len(one) > 100 and np.allclose(one.low, one.high)   # one open lot in a list: its min and max coincide (the conventions leave different lots open, so avg/fifo can differ)
    r = d.dec_px / d.px_chain; assert 0.97 < r.median() < 1.03           # decision price (limit / 1.15) ~ previous minute close


def test_close_lot_tracker_reconciles():
    L = pd.read_csv(f'{OUT}/bl_close_lots.csv'); n = L.groupby('conv').size(); assert n.nunique() == 1 and n.iloc[0] == 4671
    for cv, g in L.groupby('conv'): assert g.closed_d1.sum() + (1 - g.closed_d1).sum() == len(g) and abs((1 - g.closed_d1).mean() - 0.693) < 0.01
    P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); assert int(((P.day == 'D-1') & (P.bb_lots > 0)).sum()) == 750          # same buy-back contract-minutes as the earlier close panel
    assert (L[L.closed_d1 == 1].closed_te.notna()).all() and (L[L.closed_d1 == 0].closed_te.isna()).all()


def test_close_pairing_is_rare_and_above_chance():
    R = json.load(open(f'{OUT}/bl_summary_close1.json')); assert R['D-1_paired'] < 0.15 and R['D-1_paired'] > 20 * R['D-1_pair_null'][0] and R['D-1_pair_null'][2] < 0.02
    assert R['D-1_pair_both_ge12'] == 0.0 and R['D-1_pair_one_ge12_one_lt'] > 0.6        # a pair is one stop-like leg plus a leg that is not
    R2 = json.load(open(f'{OUT}/bl_summary_close2.json')); assert R2['D-1_both_ge12_rows'] == 0.0 and R2['D-1_single_higher_leg'][2] > 0.8


def test_close_single_leg_trigger_not_combined():
    A = pd.read_csv(f'{OUT}/bl_close_C_auc.csv'); a = A[(A.day == 'D-1')].set_index(['target', 'variable']).AUC
    for t, own, oth in (('ce', 'r_ce', 'r_pe'), ('pe', 'r_pe', 'r_ce')): assert a[(t, own)] > 0.7 and a[(t, own)] > a[(t, 'r_max')] + 0.03 and a[(t, own)] > a[(t, 'straddle_r')] + 0.03 and a[(t, oth)] < 0.35
    R2 = json.load(open(f'{OUT}/bl_summary_close2.json')); assert all(abs(R2[f'D-1_loco_{t}']['gain']) < 0.01 for t in ('ce', 'pe'))


def test_close_hazard_has_no_step_at_1p2_but_rises_after_1p4():
    P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); Q = P[P.day == 'D-1']
    h = lambda lo, hi: ((Q.bb_lots > 0) & (Q.r_low > lo) & (Q.r_low <= hi)).sum() / ((Q.r_low > lo) & (Q.r_low <= hi)).sum() * 1000
    assert h(1.2, 1.3) < 2 * h(1.1, 1.2) and h(1.3, 1.4) < 2 * h(1.2, 1.3)       # flat through 1.2-1.4
    assert h(1.5, 1.6) > 3 * h(1.4, 1.5) and h(1.7, 1.8) > 25 * h(1.2, 1.3)      # the rise is after 1.4


def test_close_carry_by_max_ratio_and_below12_composition():
    R = json.load(open(f'{OUT}/bl_summary_close5.json')); assert R['low_never12_carried_share'] > 0.75 and R['low_ge17_closed_share'] > 0.9 and R['low_early_never12_carried'] > 0.7
    R6 = json.load(open(f'{OUT}/bl_summary_close6.json')); assert R6['D-1_sub_within3s_of_stop'] > 20 * R6['D-1_sub_within3s_null'] and R6['D-1_join_same_right'] > 0.6 and R6['D-1_join_same_strike'] < 0.2
    R1 = json.load(open(f'{OUT}/bl_summary_close1.json')); assert 0.25 < R1['D-1_below12_r_low'] < 0.4 and R1['D-1_below12_all3'] > 0.25


# ---- capital-loss (book P&L) trigger study: bl_book_* ----
def test_book_pnl_panel_validation_and_stop_scale():
    V = pd.read_csv(f'{OUT}/bl_book_validation.csv'); F = V[(V.end_open_lots == 0) & V.has_d1 & V.has_d0]; assert len(F) >= 15 and (F.last_mtm - F.cash).abs().max() < 1e-6      # cash accounting closes at flat (marks are not validated by this)
    S = pd.read_csv(f'{OUT}/bl_book_first_stop.csv'); assert len(S) == 12 and -1.35 < S.B_lakh.median() < -1.0 and ((S.B_lakh > -1.35) & (S.B_lakh < -1.0)).sum() >= 8   # cycle stop near -1.0..-1.3 lakh on causal marks (earlier U8: -1.30..-1.44 non-causal)
    Bk = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz'); assert Bk.miss_share.mean() < 0.01 and {'dm1_CE', 'dm3_PE', 'B_total', 'DD'} <= set(Bk.columns)


def test_book_level_has_no_identifying_threshold():
    H = pd.read_csv(f'{OUT}/bl_book_hazard.csv'); h = H[(H.day == 'D-1') & (H['var'] == 'B_total') & (H.target == 'B')].set_index('bin').per1000
    assert h['(-1.0, -0.5]'] < h['(-0.5, -0.25]']                         # non-monotone in the loss direction
    E = pd.read_csv(f'{OUT}/bl_book_event_classes.csv'); r = E[(E.day == 'D-1') & (E['class'] == 'sub-1.2x residual')].iloc[0]; assert r['B_total_med_lakh'] > -0.3 and r['share_Btotal<=-1.0L'] < 0.1       # most residual buy-backs are nowhere near the stop level


def test_book_features_help_on_d1_not_d0_and_are_not_book_specific():
    G = pd.read_csv(f'{OUT}/bl_book_gb.csv').set_index(['day', 'target']); assert G.loc[('D-1', 'B'), 'gain_book'] > 0.05 and G.loc[('D-1', 'B'), 'perm_gain_max'] < 0.02 and abs(G.loc[('D0', 'B'), 'gain_book']) < 0.03 and abs(G.loc[('D0', 'A'), 'gain_book']) < 0.03
    L = pd.read_csv(f'{OUT}/bl_book_lot_gb.csv'); m = L[L.target == 'B'].set_index('model').LOCO_AUC; assert m['+ lot/underlying short-horizon'] - m['baseline'] > 0.08 and m['+ both'] - m['+ lot/underlying short-horizon'] < 0.03


def test_book_signal_is_short_horizon_and_graded():
    W = pd.read_csv(f'{OUT}/bl_book_window_auc.csv'); w = W[(W.day == 'D-1') & (W.target == 'B')].set_index('variable').AUC; assert (1 - w['own3']) > 0.7 and abs(w['own60'] - 0.5) < 0.1 and (1 - w['own3']) - (1 - w['own15']) > 0.08
    S = pd.read_csv(f'{OUT}/bl_book_lotshape.csv'); s = S[(S['var'] == 'lot_pct3') & (S.target == 'yB')]
    for sub in ('first half', 'second half', 'NIFTY', 'SENSEX'):
        t = s[s.subset == sub].set_index('bin'); low = t.loc[['(-100.0, -2.0]', '(-2.0, -0.5]', '(-0.5, 0.0]', '(0.0, 1.0]']]; assert t.loc['(8.0, 100.0]', 'per1000'] > 5 * low.ev.sum() / low.n.sum() * 1000
    T = pd.read_csv(f'{OUT}/bl_book_trail_auc.csv'); t = T[T.target == 'B'].set_index('variable').AUC; assert t['rebound_inr'] < t['lot_pct3'] - 0.08


# ---- body sizing study: bl_size_* ----
def test_size_unit_constant_and_pairs_one_lot():
    U = pd.read_csv(f'{OUT}/bl_size_unit.csv'); assert (U[U.und == 'NIFTY'].gcd == 65).all() and (U[U.und == 'SENSEX'].gcd == 20).all() and (U[U.und == 'NIFTY'].min_qty == 65).all() and (U[U.und == 'SENSEX'].min_qty == 20).all()
    R = json.load(open(f'{OUT}/bl_summary_size1.json')); assert R['pair_lots_all_1'] > 0.9 and R['d1_orders_1lot_share'] > 0.99 and R['n_V1'] == 21 and R['n_V2'] == 11


def test_size_timetable_is_fixed_and_total_unchanged_across_versions():
    R = json.load(open(f'{OUT}/bl_summary_size2.json')); assert R['fire_ge95']['V1'] == 1.0 and R['fire_ge95']['V2'] >= 0.85 and R['cell_misses'] / R['cell_obs'] < 0.02 and R['v_diff_net'] == 0 and R['v_diff_cells'] == 14
    T = pd.read_csv(f'{OUT}/bl_size_scheduled_totals.csv'); m = T.groupby('version').ce.mean(); assert abs(m['V1'] - m['V2']) < 1.0 and T.groupby('version').ce.std().max() < 3 and (T.ce - T.pe).abs().max() <= 4
    C = pd.read_csv(f'{OUT}/bl_size_cells.csv'); v1 = C[C.version == 'V1'].set_index('k').groupby('k').ce_mode.sum(); assert list(v1.loc[[0, 1, 2, 3, 4]]) == [3, 2, 3, 1, 4] and v1.get(12, 0) == 0 and v1.get(14, 0) == 0 and v1.get(15, 0) == 0


def test_size_change_window_and_no_notional_rule():
    CP = pd.read_csv(f'{OUT}/bl_size_changepoint.csv'); assert str(CP.iloc[0, 0]) == '2026-09-09' and str(CP.iloc[0, 1]) == '2026-09-16'
    N = pd.read_csv(f'{OUT}/bl_size_notional_dates.csv'); assert N[N.version == 'V1'].notional_lakh.min() >= 14.9 and N[N.version == 'V2'].notional_lakh.max() < 15.3 and N[N.version == 'V2'].notional_lakh.mean() < N[N.version == 'V1'].notional_lakh.mean() - 0.4
    S = pd.read_csv(f'{OUT}/bl_size_state_tests.csv'); assert (S.perm_p * len(S)).clip(upper=1).min() > 0.05 and S[S.target == 'sched_total'].spearman.abs().max() < 0.4


def test_size_class_totals_reconcile():
    L = pd.read_csv(f'{OUT}/bl_size_lot_classes.csv'); assert L.lots.sum() == 4671 and set(L.cls3) == {'scheduled cell', 'reactive pair (outside timetable)', 'solo'}
    R = json.load(open(f'{OUT}/bl_summary_size3.json')); assert 60 <= R['class_per_cycle_median']['scheduled cell'] <= 70 and R['solo_by_right']['CE'] > 1.5 * R['solo_by_right']['PE'] and R['replace_within60'][0] > 3 * R['replace_within60'][1] and abs(R['replace_corr'][0]) < 0.2


# ---- reactive pairs and wave clock: bl_react_* ----
def test_react_pair_table_and_wave_clock():
    P = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); assert P.sched.sum() == 1061 and P.reactive.sum() == 377 and P.groupby(['und', 'expiry']).ngroups == 32
    W = pd.read_csv(f'{OUT}/bl_react_wave_clock.csv'); assert W.groupby('version').size().to_dict() == {'V1': 33, 'V2': 33}
    v1 = W[W.version == 'V1'].clock_time.tolist(); assert v1[:3] == ['09:16:01', '09:16:02', '09:16:07'] and v1[-3:] == ['14:00:00', '14:15:00', '14:30:00'] and '13:30:00' in v1 and '13:45:00' in v1


def test_react_strike_one_off_atm_toward_the_move():
    R1 = json.load(open(f'{OUT}/bl_summary_react1.json')); R3 = json.load(open(f'{OUT}/bl_summary_react3.json'))
    assert R1['atm_hit_react'][0] < 0.1 and R1['atm_hit_sched'][0] > 0.9 and R3['side']['ch15'] > 0.9 and R3['side']['ch5'] > 0.9 and R3['side']['ch1'] < R3['side']['ch15']


def test_react_no_timer_and_weak_buyback_link():
    R1 = json.load(open(f'{OUT}/bl_summary_react1.json')); assert R1['gap_sell_15min_share'] <= R1['gap_sell_15min_null'][1] and R1['seconds_uniform_p'] > 0.01
    assert R1['after_any_60'][0] > 2.5 * R1['after_any_60'][1] and R1['after_any_900'][0] < R1['after_any_900'][1] + 0.05


def test_react_prediction_is_a_weak_tilt_from_market_and_history_only():
    G = pd.read_csv(f'{OUT}/bl_react_gb.csv'); r = G[G.target == 'R'].set_index('model').LOCO_AUC; s = G[G.target == 'S'].set_index('model').LOCO_AUC
    assert r['clock + market'] - r['clock only'] > 0.05 and r['clock + history'] - r['clock only'] > 0.03 and r['clock + book'] - r['clock only'] < 0.03 and r['clock + inventory'] - r['clock only'] < 0.03 and r['all blocks'] > r['all blocks, market shuffled'] + 0.05
    assert s['clock + market'] - s['clock only'] > r['clock + market'] - r['clock only']
    A = pd.read_csv(f'{OUT}/bl_react_auc.csv'); a = A[A.target == 'R']; assert (a.AUC - .5).abs().max() < 0.12
    M = pd.read_csv(f'{OUT}/bl_react_move_hazard.csv'); m = M[(M['var'] == 'a15')].set_index('bin'); assert m.loc['(0.3, 5.0]', 'R_per1000'] < 0.5 * m.loc['(0.0, 0.1]', 'R_per1000'] and m.loc['(0.3, 5.0]', 'solo_per1000'] > 2 * m.loc['(0.0, 0.1]', 'solo_per1000']


# ---- reactive pair mechanism and sell census: bl_mech_* ----
def test_mech_reactive_pairs_have_a_1030_to_1515_gate():
    R = json.load(open(f'{OUT}/bl_summary_mech3.json')); g = R['gate_all']; assert g['start'] == '10:30' and g['stop'] == '15:15' and g['h_in'] > 5 * g['h_out'] and R['gate_boot_start'][0] == '10:30' and R['gate_boot_start'][2] == '10:30'
    G = pd.read_csv(f'{OUT}/bl_mech_gate.csv').set_index('subset'); assert all(G.loc[s, 'start'] == '10:30' and G.loc[s, 'stop'] == '15:15' for s in ('NIFTY', 'SENSEX', 'first half', 'second half', 'V1'))
    assert R['interarrival_cv'] > 1.0


def test_mech_no_volume_or_london_step_and_clock_not_separable():
    R = json.load(open(f'{OUT}/bl_summary_mech1.json')); assert 0.8 < R['vol_ratio_1230_vs_prev'] < 1.25 and R['first_react_before_1100'] > 0.5
    g = R['gb']; assert g['no clock + progress'] > g['clock only (j)'] - 0.02 and g['all proxies + clock'] - g['all proxies, no clock'] < 0.03 and g['no clock + range_open'] < g['clock only (j)']
    O = pd.DataFrame(R['onset']); assert (O.perm_p > 0.05).all()


def test_mech_strike_rule_is_atm_plus_one_step_toward_the_move():
    T = pd.read_csv(f'{OUT}/bl_mech_strike_rules.csv', index_col=0).drop(index=['previous reactive strike +-1 step']); b = T.loc['ATM + 1 step toward 15-min move']
    assert 0.75 < b.reactive_hit < 0.82 and b.timetable_hit < 0.2 and b.half1 > 0.7 and b.half2 > 0.7 and b.NIFTY > 0.7 and b.SENSEX > 0.7
    rest = T.drop(index=[i for i in T.index if i.startswith('ATM + 1 step')]); assert rest.reactive_hit.max() < 0.5


def test_mech_census_has_no_residual_and_hedge_wing_sales_are_the_largest_other_type():
    C = pd.read_csv(f'{OUT}/bl_mech_census.csv', index_col=0); assert C.lots.sum() == 6072 and 'residual' not in C.index and C.orders.sum() == 5152
    assert 0.18 < C.loc['hedge-module sell closing a long wing', 'share_of_sold_lots'] < 0.21 and C.loc['hedge-module sell closing a long wing', 'lots'] > C.loc['batch (>= 3 lots, one strike/right, within 3 s)', 'lots']
    S = pd.read_csv(f'{OUT}/bl_mech_census_orders.csv'); assert S.lots.sum() == 6072 and S.cls.notna().all()
    L = pd.read_csv(f'{OUT}/bl_size_lot_classes.csv'); solo = C.loc[['single solo', 'batch (>= 3 lots, one strike/right, within 3 s)', 'end-of-day solo (>= 15:00)', 'near-pair (CE and PE within 3 s, different strikes)'], 'lots'].sum(); assert solo == L[L.cls3 == 'solo'].lots.sum()


# ---- reactive-pair look-back: bl_lb_* ----
def test_lb_stated_rule_hit_rate_and_sample():
    R = json.load(open(f'{OUT}/bl_summary_lb.json')); assert R['n'] == 363 and 0.78 < R['hit15'] < 0.83 and all(v > 0.75 for v in R['hit15_und'].values()) and all(v > 0.75 for v in R['hit15_half'].values()) and R['dir_zero'] == 0
    S = pd.read_csv(f'{OUT}/bl_lb_sample.csv'); assert len(S) == 10 and int(S.match.sum()) == R['sample_matches'] == 8 and (S['predicted strike'] - S['previous-minute ATM']).abs().isin([50, 100]).all()


def test_lb_length_is_a_plateau_not_15_and_rolling_beats_anchored():
    R = json.load(open(f'{OUT}/bl_summary_lb.json')); D = pd.DataFrame(R['defs']).set_index('direction definition').hit_rate
    assert min(D[f'rolling {L}'] for L in (10, 15, 20, 30, 60)) > 0.78 and D['rolling 15'] > D['previous 15-min block (open to close)'] + 0.15 and max(D[k] for k in D.index if not k.startswith('rolling')) < min(D[f'rolling {L}'] for L in (10, 15, 20, 30, 60))
    assert R['disagree_block_hit'] < 0.15 and R['disagree_rolling_hit'] > 0.7
    L = pd.read_csv(f'{OUT}/bl_lb_live_scan.csv').set_index('L_min'); assert L.hit_rate_live_proxy.loc[[10, 15, 20, 30, 45, 60]].max() - L.hit_rate_live_proxy.loc[[10, 15, 20, 30, 45, 60]].min() < 0.02 and L.hit_rate_live_proxy.loc[1] < L.hit_rate_live_proxy.loc[15] - 0.03 and L.hit_rate_live_proxy.loc[90] < L.hit_rate_live_proxy.loc[15] - 0.05


def test_lb_live_spot_proxy_beats_completed_bar_and_move_does_not_fire():
    R2 = json.load(open(f'{OUT}/bl_summary_lb2.json')); assert R2['live_hit'] > R2['bar_hit'] + 0.05 and R2['live_minus_bar_ci'][0] > 0.03 and R2['bar_vs_sec_rho'] < -0.05 and abs(R2['live_vs_sec_rho']) < 0.1 and R2['late_live'] > R2['late_bar'] + 0.1
    assert R2['hazard_ratio_moving_vs_flat'][1] > 1.2 and abs(R2['hazard_up_down'][0] - R2['hazard_up_down'][1]) < 6


# ---- reactive-pair dynamic reference and activation: bl_act_* ----
def test_act_direction_reference_is_a_trailing_price_not_a_book_anchor():
    D = pd.read_csv(f'{OUT}/bl_act_dirs.csv').set_index('reference X (direction = sign of live spot - X)')
    for k in ('spot 10 min ago', 'spot 15 min ago', 'spot 30 min ago', 'spot 60 min ago', 'SMA 5', 'SMA 10', 'SMA 15', 'SMA 30', 'SMA 60'): assert D.loc[k, 'hit_rate'] > 0.88
    assert D.loc['short-book centre', 'hit_rate'] < 0.85 and all(D.loc[k, 'hit_rate'] < 0.78 for k in ('last timetable pair strike', 'day mid-range', 'opening ATM', 'last body sell strike', 'last reactive pair strike')) and D.diff_vs_spot15.max() < 0.02


def test_act_dead_zone_near_the_moving_average_and_gap_beats_plain_move():
    H = pd.read_csv(f'{OUT}/bl_act_gap_hazard.csv').pivot(index='subset', columns='gap_group', values='per1000'); assert (H['>= 0.5'] / H['|gap| < 0.1 step'] > 5).all() and H.loc['all', '|gap| < 0.1 step'] < 8
    G = pd.read_csv(f'{OUT}/bl_act_gap_auc.csv').set_index('N_min'); assert (G.AUC_abs_gap.loc[[10, 15, 20, 30, 45, 60]] > G.AUC_abs_move_L.loc[[10, 15, 20, 30, 45, 60]] + 0.04).all() and G.AUC_abs_gap.idxmax() in (15, 20, 30, 45) and G.AUC_abs_gap.loc[[3, 120]].max() < G.AUC_abs_gap.max() - 0.05
    R4 = json.load(open(f'{OUT}/bl_summary_act4.json')); b = pd.DataFrame(R4['hazard_bins']); assert (b.per1000 / b.per1000.shift(1)).max() < 3.0          # no >= 3x adjacent step: dead zone, not a threshold


def test_act_causal_spot_position_and_order_activity_carry_the_activation():
    G = pd.read_csv(f'{OUT}/bl_act_gb.csv').set_index('model').LOCO_AUC; assert G['clock only'] < 0.6 and G['clock + ages'] > G['clock only'] + 0.1 and G['CAUSAL (completed bars only): clock + ages + spot_position'] > G['clock + ages'] + 0.08 and G['LIVE-PROXY all blocks'] > G['CAUSAL: all blocks'] and G['CAUSAL: all blocks + current-minute move (look-ahead)'] > G['CAUSAL: all blocks']
    L = pd.read_csv(f'{OUT}/bl_act_lags.csv').set_index('age_of'); assert L.loc['age_oth', 'ev<= 60s'] > 2.5 * L.loc['age_oth', 'ctl<= 60s'] and L.loc['age_bb', 'ev<= 60s'] > 2.5 * L.loc['age_bb', 'ctl<= 60s'] and L.loc['age_sell', 'ev<= 300s'] > L.loc['age_sell', 'ctl<= 300s'] + 0.1


# ---- reactive-pair indicator search: bl_ind_* ----
def test_ind_range_position_leads_activation_and_is_ahead_of_ma_variants():
    F = pd.read_csv(f'{OUT}/bl_ind_family_cv.csv').set_index('family'); B = pd.read_csv(f'{OUT}/bl_ind_boot.csv').set_index('family')
    assert F.A_crossvalidated.idxmax() == 'Donchian position' and F.A_crossvalidated['Donchian position'] > 0.9
    assert F.A_crossvalidated['Donchian position'] > F.A_crossvalidated.drop('Donchian position').max() + 0.02 and (B.drop('Donchian position').A_diff_vs_best_hi < 0).all()
    assert F.A_crossvalidated['SMA gap'] < 0.80 and F.A_crossvalidated['Bollinger z'] > F.A_crossvalidated['SMA gap'] + 0.07


def test_ind_direction_does_not_discriminate_level_indicators():
    F = pd.read_csv(f'{OUT}/bl_ind_family_cv.csv').set_index('family').D_crossvalidated
    lv = F[['Donchian position', 'EMA z', 'Bollinger z', 'gap/ATR', 'EMA gap', 'WMA gap', 'SMA gap', 'momentum', 'MACD']]; assert lv.max() - lv.min() < 0.015 and lv.min() > 0.88
    assert F['SMA cross'] < lv.min() - 0.02 and F['regression line gap'] < lv.min() - 0.05 and F['regression drift'] < lv.min() - 0.02


def test_ind_volatility_or_range_scaling_beats_absolute_gap():
    R = json.load(open(f'{OUT}/bl_summary_ind.json'))['norm_boot']; assert R['z_minus_abs'][0] > 0.02 and R['atr_minus_abs'][0] > 0.02
    C = pd.read_csv(f'{OUT}/bl_ind_combo.csv'); assert C.gain_vs_alone.max() < 0.01 and C.gain_vs_alone.min() > -0.01


def test_ind_channel_length_plateau_and_robustness():
    N = pd.read_csv(f'{OUT}/bl_ind_fine.csv').set_index('N_min'); assert N.AUC.loc[45:65].min() > 0.905 and N.AUC.loc[[30, 90]].max() < N.AUC.max() - 0.015 and N.AUC.idxmax() in (55, 60, 65)
    R = pd.read_csv(f'{OUT}/bl_ind_robust.csv'); assert R['activation_AUC_|position-0.5|_N60'].min() > 0.88 and (R.direction_hit > 0.85).all()


def test_ind_range_edge_breakout_state_but_not_sufficient():
    Bd = pd.read_csv(f'{OUT}/bl_ind_bands.csv'); assert Bd.share_of_events.iloc[0] > 0.6 and Bd.share_of_control_seconds.iloc[0] < 0.1 and Bd.share_of_events.iloc[3] < 0.05 and Bd.share_of_control_seconds.iloc[3] > 0.4
    S = json.load(open(f'{OUT}/bl_summary_ind2.json')); assert S['state']['ratio'][3] > 3.0 and S['episodes_with_pair'] < 0.3 and S['pair_minutes_in_episodes'] < 0.6


# ---- reactive-pair trigger study: bl_trg_* ----
def test_trg_rolling_window_plateau_and_expanding_rejected():
    S = pd.read_csv(f'{OUT}/bl_trg_bandscan.csv').set_index('window'); R = json.load(open(f'{OUT}/bl_summary_trg1.json'))
    assert all(k in R['within_ci_of_best'] for k in ('N45', 'N50', 'N55', 'N60', 'N65')) and all(k in R['excluded_vs_best'] for k in ('N10', 'N20', 'N30', 'N80', 'N120'))
    assert S.AUC['EXP'] < S.AUC['N60'] - 0.25 and S.AUC['N60'] > 0.9 and S.AUC.drop('EXP').idxmax() in ('N50', 'N55', 'N60', 'N65') and R['best_upper'] in ('N45', 'N50', 'N55', 'N60', 'N65') and R['best_lower'] in ('N45', 'N50', 'N55', 'N60', 'N65')
    assert R['dir_hit_N60']['beyond'] > 0.9 and R['dir_hit_N60']['beyond'] > R['dir_hit_N60']['not_beyond'] + 0.08


def test_trg_breakout_necessary_not_sufficient_and_no_simple_rule():
    P = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); y = P.y == 1; la = P.bkLA60 != 0; cau = P.bk60 != 0
    assert (la & y).sum() / y.sum() > 0.7 and (cau & y).sum() / y.sum() < 0.5 and (la & y).sum() / la.sum() < 0.25 and (cau & y).sum() / cau.sum() < 0.15
    T = pd.read_csv(f'{OUT}/bl_trg_tree.csv'); assert not ((T.precision >= 0.5) & (T.recall >= 0.5)).any()


def test_trg_only_order_activity_block_adds_and_time_not_move_paces():
    B = pd.read_csv(f'{OUT}/bl_trg_blocks.csv'); d = B[B.population.str.startswith('LOOK-AHEAD')].set_index(['model', 'features'])
    for m in ('lr', 'gb'): assert d.loc[(m, 'edge + activity'), 'gain_lo'] > 0.03 and all(d.loc[(m, f'edge + {b}'), 'gain_vs_edge_only'] < 0.03 for b in ('clock', 'book', 'option', 'market'))
    U = pd.read_csv(f'{OUT}/bl_trg_uni.csv'); u = U[(U.population == 'LOOK-AHEAD breakout minutes')].set_index('feature'); assert u.AUC.sub(.5).abs().idxmax() == 'age_react' and u.AUC['age_react'] > 0.65 and u.AUC_even['age_react'] > 0.6 and u.AUC_odd['age_react'] > 0.6
    M = pd.read_csv(f'{OUT}/bl_trg_move.csv'); c = M[M.comparison == 'time + move vs time only'].iloc[0]; assert c.lo < 0 < c.hi + 0.05 and c['diff'] < 0.02


def test_trg_refractory_is_conditional_on_breakout_and_legs_slightly_spaced():
    R = json.load(open(f'{OUT}/bl_summary_trg2.json')); r = R['refract_ratio_LA_breakout_lt5_vs_ge5']; a = R['refract_ratio_all']; assert r[2] < 0.7 and a[1] < 1 < a[2]
    L = pd.read_csv(f'{OUT}/bl_trg_leg.csv').iloc[0]; assert L.legs_with_2plus_pair_minutes < L.null_mean_legs_with_2plus and L.null_2plus_p_lower < 0.05 and L.legs_with_a_pair / L.legs < 0.5


# ---- reactive-pair tracker study: bl_trk_* ----
def test_trk_seconds_not_a_fixed_second_clock_and_counts_regular():
    S = pd.read_csv(f'{OUT}/bl_trk_seconds.csv').set_index('group'); assert S.loc['reactive pairs', 'share_first_10s'] < 0.28 and S.loc['scheduled (timetable) pairs', 'share_first_10s'] > 0.4
    R = json.load(open(f'{OUT}/bl_summary_trk1.json')); assert R['cycles_total'] == 32 and 11 < R['mean'] < 12.5 and R['dispersion_var_over_mean'] < 0.6 and abs(R['spearman_pairs_vs_la_breakout_minutes'][0]) < 0.25 and abs(R['spearman_pairs_vs_buyback_lots'][0]) < 0.25 and abs(R['spearman_pairs_vs_scheduled_pairs'][0]) < 0.3


def test_trk_stateful_range_edge_machine_beats_stateless_and_null():
    C = pd.read_csv(f'{OUT}/bl_trk_sim_cv.csv').set_index(['family', 'info']); m1 = C.loc[('M1', 'bar')]; m0 = C.loc[('M0', 'bar')]
    assert m1.F1_tol1 > m1.null_F1_p99 + 0.25 and m1.precision_tol1 >= 0.4 and m1.recall_tol1 >= 0.4 and m1.side_agreement_matched > 0.95 and m1.F1_tol1 > m0.F1_tol1 + 0.1
    assert C.loc[('M2', 'bar'), 'F1_tol1'] < 0.3 and C.loc[('M3', 'bar'), 'F1_tol1'] < 0.3 and C.loc[('M4', 'bar'), 'F1_tol1'] < m1.F1_tol1


def test_trk_validation_random_splits_and_cross_instrument():
    R = json.load(open(f'{OUT}/bl_summary_trk3.json')); assert R['splits']['F1_mean'] > 0.45 and R['splits']['F1_q'][0] > 0.38
    X = pd.read_csv(f'{OUT}/bl_trk_sim2_cross.csv'); assert (X.F1 > 0.38).all() and (X.F1 > X.same_N_K1_F1 + 0.05).all()
    C = pd.read_csv(f'{OUT}/bl_trk_sim2_cv.csv').set_index(['family', 'info']); assert C.loc[('M5', 'bar'), 'F1_tol1'] < C.loc[('M1', 'bar'), 'F1_tol1'] - 0.1 and abs(C.loc[('M7', 'bar'), 'F1_tol1'] - C.loc[('M1', 'bar'), 'F1_tol1']) < 0.03


def test_trk_capacity_and_side_specific_spacing_are_not_decisive():
    P = pd.read_csv(f'{OUT}/bl_trk_cap.csv').set_index('model'); base = P.loc['M1 (cap = none, kappa = 0)']; assert P.loc['M1 + cap', 'count_var_over_mean'] < 0.8 and base.count_var_over_mean > 1.2 and P.loc['M1 + cap', 'F1'] < base.F1 + 0.02 and P.loc['M1 + growing refractory', 'F1'] < base.F1 + 0.05
    S = pd.read_csv(f'{OUT}/bl_trk_side.csv'); assert S.F1.iloc[1] < S.F1.iloc[0] + 0.02


def test_trk_example_cycles_pairs_sit_at_the_range_edge():
    for u in ('NIFTY', 'SENSEX'):
        E = pd.read_csv(f'{OUT}/bl_trk_example_{u}.csv'); assert len(E) == 12 and (E.position_in_70min_range.abs() > 0.4).mean() >= 0.8 and E.machine_fire_within_1min.sum() >= 8 and (E.strike_minus_ATM_steps.abs() == 1).all()
    F = pd.read_csv(f'{OUT}/bl_trk_fires.csv'); assert len(F) == 297 and F.pairs.sum() == 377 and (F.pairs > 1).mean() > 0.15


# ---- reactive-pair book-state / pace study: bl_bk_*, bl_pc_* ----
def test_bk_pair_is_not_a_delta_hedge():
    R = json.load(open(f'{OUT}/bl_summary_bk1.json')); assert R['mean_pair_delta_lots'] < 0.3 and R['abs_delta_events_median'] > 4 and R['share_pair_moves_delta_toward_move_side'] == 1.0 and R['abs_delta_after_events_median'] > 0.9 * R['abs_delta_events_median']
    D = pd.read_csv(f'{OUT}/bl_bk_uni.csv'); v = D[D.variable.isin(['delta_vs_move', 'delta_vs_move_norm', 'itm_short', 'dist_out_move', 'pnl_pct', 'prem_pos60', 'sig_chg15', 'prem_chg15', 'pnl_chg15'])]; assert (v.AUC_within_edge.sub(.5).abs() < 0.1).all()


def test_bk_book_blocks_add_nothing_but_pace_and_activity_do():
    B = pd.read_csv(f'{OUT}/bl_bk_blocks.csv'); d = B[B.population.str.startswith('LOOK-AHEAD')].set_index(['model', 'features'])
    for m in ('lr', 'gb'):
        for f in ('edge + P&L', 'edge + premium/vol'): assert d.loc[(m, f), 'gain'] < 0.04 and d.loc[(m, f), 'gain_lo'] < 0.03
        assert d.loc[(m, 'edge + pace deficit'), 'gain_lo'] > 0.0 and d.loc[(m, 'edge + activity (order ages)'), 'gain_lo'] > 0.0
    P = pd.read_csv(f'{OUT}/bl_bk_pace_uni.csv'); u = P[P.population == 'LOOK-AHEAD breakout minutes'].set_index('variable'); assert u.AUC['def_tot'] > 0.62 and u.AUC['def_react'] > 0.6 and abs(u.AUC['pnl_pct'] - .5) < 0.08 and abs(u.AUC['prem_pos60'] - .5) < 0.08


def test_pc_pace_count_not_exposure_and_hedge_follows_pair():
    R = json.load(open(f'{OUT}/bl_summary_pc2.json')); assert R['def_tot_auc_within_edge'][0] > 0.68 and R['def_react_auc_within_edge'][0] > 0.65 and R['def_short_auc_within_edge'][0] < 0.6 and R['pace_quintiles'][-1]['events_per_control_second'] > 3 * R['pace_quintiles'][0]['events_per_control_second']
    F = pd.read_csv(f'{OUT}/bl_bk_flow.csv'); a = F[(F.window == 'after: 30 s') & (F.order_kind.str.startswith('h_ | open_long'))]; assert (a.share_of_pairs > 0.8).all() and (a.share_of_control_seconds < 0.06).all()


def test_pc_pace_machine_beats_refractory_but_regularity_is_weak():
    C = pd.read_csv(f'{OUT}/bl_pc_cv.csv').set_index(['family', 'info']); m = C.loc[('M10', 'bar')]; assert m.F1_tol1 > 0.52 and m.precision_tol1 > 0.5 and m.recall_tol1 > 0.5 and m.F1_tol1 > m.null_p99 + 0.35 and C.loc[('M10', 'intra'), 'F1_tol0'] > 0.4 and C.loc[('M11', 'bar'), 'F1_tol1'] < 0.45
    B = pd.read_csv(f'{OUT}/bl_pc_boot.csv'); assert (B['diff'] > 0.03).all() and (B.lo > 0).all()
    X = pd.read_csv(f'{OUT}/bl_pc_cross.csv'); assert (X.F1 > 0.5).all(); S = pd.read_csv(f'{OUT}/bl_pc_splits.csv'); assert S.F1.mean() > 0.52 and S.F1.quantile(.025) > 0.45
    G = pd.read_csv(f'{OUT}/bl_pc_reg.csv').set_index('group'); assert G.loc['reactive pairs (all)', 'p_value_regular'] > 0.5 and G.loc['fires (pairs within 5 s merged)', 'p_value_regular'] < 0.1
    A = pd.read_csv(f'{OUT}/bl_pc_age.csv').set_index('model'); assert A.loc['time since last pair + pace deficit (reactive)', 'lo'] < 0
    R = json.load(open(f'{OUT}/bl_summary_pc2.json')); assert abs(R['gap_autocorr']['rho'] - R['gap_autocorr']['null_mean']) < 0.1


# ---- reactive-pair 30-minute clock study: bl_clk_* ----
def test_clk_phase_signature_and_block_length():
    P = pd.read_csv(f'{OUT}/bl_clk_phase_minutes.csv').set_index('minute_of_hour').fires; assert P[0] > 3 * P.drop([0, 30]).median() and P[30] > 3 * P.drop([0, 30]).median()
    M = pd.read_csv(f'{OUT}/bl_clk_moduli.csv').set_index('modulus_seconds'); assert M.loc[1800, 'chi2_p_uniform'] < 0.001 and M.loc[900, 'chi2_p_uniform'] < 0.001 and M.loc[420, 'chi2_p_uniform'] > 0.05
    S = pd.read_csv(f'{OUT}/bl_clk_scan.csv'); b = S.groupby('L').F1.max(); assert b.idxmax() == 30 and b[30] > b.drop(30).max() + 0.01
    p = S[(S.L == 30) & (S.N == 70)].set_index('phase_min').F1; assert p.idxmax() in (29, 0, 1) and p[[0, 1]].min() > p.drop([29, 0, 1]).max() + 0.03


def test_clk_previous_two_completed_bars_is_the_channel():
    C = pd.read_csv(f'{OUT}/bl_clk_chan.csv').set_index(['kind', 'param']); assert C.F1[('bars_prev', 2)] > C.F1.drop(('bars_prev', 2)).max() + 0.02 and C.F1[('bars_prev', 2)] > C.F1[('bars_prev', 1)] + 0.1 and C.F1[('bars_prev', 2)] > C.F1[('bars_prev', 3)] + 0.04
    R = json.load(open(f'{OUT}/bl_summary_clk3.json')); assert R['oof_bars_prev']['params'] == [2, 2] and R['oof_bars_prev']['F1'] > 0.6 and R['oof_bars_prev']['precision'] > 0.65 and R['oof_bars_prev']['F1'] > R['oof_roll']['F1'] + 0.02


def test_clk_bar_level_agreement_and_placebos():
    B = pd.read_csv(f'{OUT}/bl_clk_bars.csv'); b0 = B.iloc[0]; assert b0.precision_bar > 0.85 and b0.recall_bar > 0.95 and b0.odds_ratio > 80 and b0.phi > 0.75
    pl = B[B.machine.str.contains('placebo')]; assert (pl.phi < b0.phi - 0.1).all() and (pl.odds_ratio < b0.odds_ratio / 1.5).all()
    R = pd.read_csv(f'{OUT}/bl_clk_refine.csv').set_index('variant'); assert R.F1['base: prev 2 bars, one entry per bar, completed bars, phase 0'] > 0.62 and R.F1_same_minute['current-minute close (look-ahead proxy)'] > 0.45 and R.F1['phase -1 min'] < 0.55 and R.F1['phase +5 min'] < 0.55
    T = json.load(open(f'{OUT}/bl_summary_clk4.json')); d = T['timing_diff']; assert d['0'] / sum(d.values()) > 0.6 and T['side_agreement'] > 0.98


def test_clk_wings_follow_every_sell_and_do_not_gate_entries():
    R = json.load(open(f'{OUT}/bl_summary_clk5.json')); assert all(v > 0.85 for v in R['follow_share'].values()) and R['follow_share']['reactive'] > 0.9
    for cp in ('CE', 'PE'): assert 0.85 < R['lots_by_leg']['wing_lots'][cp] / R['lots_by_leg']['short_lots'][cp] < 1.0
    W = pd.read_csv(f'{OUT}/bl_clk_wingstate.csv').set_index('variable'); assert abs(W.AUC['cover'] - 0.5) < 0.06 and abs(W.AUC['short_lots'] - 0.5) < 0.08
    E = json.load(open(f'{OUT}/bl_summary_clk9.json')); g = E['entry_given_break_by_sched']; assert g['1']['p'] > 0.85 and g['3']['p'] > 0.85 and E['fires_per_bar']['1'] > E['fires_per_bar']['2'] > E['fires_per_bar']['3']


def test_clk_example_cycles():
    for u in ('NIFTY', 'SENSEX'):
        E = pd.read_csv(f'{OUT}/bl_clk_example_{u}.csv'); assert len(E) == 10 and (E.real_pair_minutes > 0).sum() >= 6
    R = json.load(open(f'{OUT}/bl_summary_clk8.json')); assert R['NIFTY']['both'] >= 7 and R['SENSEX']['both'] >= 6 and R['NIFTY']['actual_only'] == 0


# ---- reactive-pair decoding with true OHLC: bl_dq_* ----
def test_dq_true_ohlc_machine_reaches_target():
    F = pd.read_csv(f'{OUT}/bl_dq_final.csv'); f = F.iloc[0]; assert f.machine.startswith('FINAL') and f.F1 > 0.8 and f.precision > 0.85 and f.recall > 0.7 and f.F1_same_minute > 0.75 and f.bar_recall > 0.95
    assert (F[F.machine.str.contains('placebo')].F1 < f.F1 - 0.05).all() and (F[~F.machine.str.startswith('FINAL') & ~F.machine.str.contains('per candle')].F1 < f.F1 - 0.05).all()
    R = json.load(open(f'{OUT}/bl_summary_dq7.json')); assert R['first_entry']['capture'] > 0.9 and R['first_entry']['exact_share'] > 0.85 and R['budget']['repeat_in_candle'] > R['budget']['no_machine_break'] + R['budget']['first_entry_timing_off']


def test_dq_ohlc_is_what_changed_and_no_margin():
    O = pd.read_csv(f'{OUT}/bl_dq_ohlc.csv').set_index('machine'); assert O.F1['TRUE high/low channel + intrabar high/low break'] > O.F1['closes channel, close break (previous report)'] + 0.15 and O.F1['true high/low channel, close break'] < 0.7 and O.F1['closes channel, intrabar high/low break'] < 0.7
    G = pd.read_csv(f'{OUT}/bl_dq_tune_grid.csv'); g = G.groupby('mu_steps').F1.max(); assert g.idxmax() == 0 and g[0.02] < g[0] - 0.03
    R = json.load(open(f'{OUT}/bl_summary_dq5.json')); assert R['split_F1'][0] > 0.78 and R['split_F1'][1] > 0.75


def test_dq_robust_across_subsets():
    S = pd.read_csv(f'{OUT}/bl_dq_final_subsets.csv'); assert (S.F1 > 0.77).all() and (S.precision > 0.84).all()


def test_dq_repeat_rules_do_not_beat_base_and_count_links_to_book_stress():
    S = pd.read_csv(f'{OUT}/bl_dq_repeat_sim.csv').set_index('rule'); assert (S.drop('none').F1 <= S.F1['none'] + 0.005).all()
    G = pd.read_csv(f'{OUT}/bl_dq_repeat_gate.csv'); assert (G.F1.iloc[1:] <= G.F1.iloc[0] + 0.005).all()
    C = pd.read_csv(f'{OUT}/bl_dq_count.csv').set_index('variable'); assert C.spearman['delta_vs_side'] > 0.2 and C.p['delta_vs_side'] < 0.05 / 19 and C.p['itm_short'] < 0.05 / 19
    R = json.load(open(f'{OUT}/bl_summary_dq2.json')); assert R['new_bar_extreme'] > 0.85 and R['still_beyond_channel'] > 0.85


# ---- combined D-1 selling reconstruction: bl_all_* ----
def test_all_scheduled_solved_reactive_precise_solo_open():
    T = pd.read_csv(f'{OUT}/bl_all_sells_type.csv'); t = T[T.tolerance_min == 1].set_index('sell_type')
    assert t.F1['scheduled'] > 0.95 and t.strike_exact_of_matched['scheduled'] > 0.9 and t.precision['reactive'] > 0.85 and t.recall['reactive'] < 0.7 and t.F1['solo'] < 0.4
    C = pd.read_csv(f'{OUT}/bl_all_sells_combined.csv'); c = C[C.tolerance_min == 1].set_index('model'); assert 0.55 < c.F1['all three rules vs all D-1 sells'] < 0.75 and c.precision['scheduled + reactive only vs all D-1 sells'] > 0.95
    R = json.load(open(f'{OUT}/bl_summary_all1.json')); assert abs(sum(R['actual_share'].values()) - 1) < 1e-9 and R['actual_share']['solo'] > 0.3


def test_all_solo_rule_variants_stay_weak():
    S = pd.read_csv(f'{OUT}/bl_all_solo_rules.csv'); assert S.F1.max() < 0.5
    W = pd.read_csv(f'{OUT}/bl_all_solo_where.csv').set_index('hour_block'); assert W.share['15:00-15:30'] > 0.2


def test_all_recalculated_with_recalled_solo_findings():
    C = pd.read_csv(f'{OUT}/bl_all2_combined.csv'); a = C[C.scope == 'all D-1 sold lots'].set_index('solo_variant')
    assert a.F1.max() > 0.72 and a.F1['stated rule (fresh 15-min extreme)'] < a.F1.max() - 0.08
    T = pd.read_csv(f'{OUT}/bl_all2_type.csv'); s = T[T.sell_type == 'solo']; assert s.F1.max() < 0.5
    R = json.load(open(f'{OUT}/bl_summary_all3.json')); assert 0.04 < R['shares']['deep-OTM batch'] < 0.1 and R['deep_cycles'] == 3
    S = json.load(open(f'{OUT}/bl_summary_solo1.json')); assert S['R2_auc'] > 0.9
    K = pd.read_csv(f'{OUT}/bl_solo_strike.csv'); assert K.exact.iloc[0] > K.exact.iloc[1]


# ---- solo decode: bl_sd_* ----
def test_sd_bursts_and_reactive_attached_extras():
    R = json.load(open(f'{OUT}/bl_summary_sd1.json')); lb = R['lots_per_burst']; assert R['bursts'] < 1508 and lb['1'] / sum(lb.values()) < 0.8
    F = pd.read_csv(f'{OUT}/bl_sd_reactlots.csv'); up = F[F.side > 0]; dn = F[F.side < 0]; assert F.extra_other.sum() < 0.05 * F.extra_fav.sum() and (F.extra_fav > 0).mean() > 0.4
    A = pd.read_csv(f'{OUT}/bl_sd_reactlots_assoc.csv').set_index(['target', 'variable']); assert A.spearman[('extra_fav', 'depth')] > 0.3 and A.p[('extra_fav', 'depth')] < 0.001 and A.spearman[('pairs', 'depth')] > 0.2


def test_sd_state_signals_and_rejected_balancing():
    U = pd.read_csv(f'{OUT}/bl_sd_state_auc.csv').set_index('variable'); assert U.AUC['other_book'] > 0.7 and U.AUC['own_book'] < 0.3 and U.AUC['last_ratio_ext'] < 0.3 and abs(U.AUC['delta_toward'] - 0.5) < 0.1
    B = json.load(open(f'{OUT}/bl_summary_sd3.json')); assert B['ratio_V'] < 0.5 and B['ratio_L'] < 0.4


def test_sd_rules_stay_below_decode_threshold_and_combined_improves():
    S = json.load(open(f'{OUT}/bl_summary_sd6.json')); assert 0.45 < S['oof_burst']['F1'] < 0.7
    C = pd.read_csv(f'{OUT}/bl_sd_combined.csv'); a = C[C.stream == 'all']; assert a.F1.max() > 0.76 and C[C.stream == 'solo'].F1.max() < 0.6
    L = pd.read_csv(f'{OUT}/bl_sd_classes.csv').set_index('solo_class'); assert L.F1['after 15:00'] == 0 and 0.5 < L.share['intraday stand-alone'] < 0.7
    T = json.load(open(f'{OUT}/bl_summary_sd10.json')); assert T['late']['heavier_share'] < T['intraday']['heavier_share'] - 0.15 and T['late']['after_buyback_share'] < 0.05


def test_sl_late_solo_trigger_and_rejections():
    S1 = json.load(open(f'{OUT}/bl_summary_sl1.json')); assert 0.35 < S1['late']['share_reduce_abs_delta'] < 0.6 and S1['intraday']['share_reduce_abs_delta'] < 0.35
    S4 = json.load(open(f'{OUT}/bl_summary_sl4.json')); assert 0.35 < S4['H3']['lot_share_on_lighter_side'] < 0.6 and S4['H2']['median_ratio_solo_to_long'] > 2
    S7 = json.load(open(f'{OUT}/bl_summary_sl7.json')); assert S7['lots'] == 336 and 0.6 < S7['lot_coverage']['spot extreme (E)'] < 0.7 and S7['lot_coverage']['E or premium low'] > 0.85
    R = pd.read_csv(f'{OUT}/bl_sl_rule2.csv').set_index('rule'); assert 0.6 < R.F1['R3'] < 0.7 and R.recall['R3'] > 0.85


def test_sl_blocks_market_dominates_and_panel_shape():
    B = pd.read_csv(f'{OUT}/bl_sl_blocks.csv'); a = B.groupby('block').AUC.max(); assert a['market'] > 0.78 and a['all'] > a['market'] and max(a['greeks'], a['inventory'], a['flow']) < 0.56
    X = pd.read_pickle(f'{OUT}/bl_sl_panel.pkl.gz'); assert len(X) == 32 * 30 * 2 and X.y.sum() == 138 and set(X.cp) == {'CE', 'PE'}
    P = pd.read_csv(f'{OUT}/bl_sl_prem.csv').set_index(['window', 'variable']); h = P.hazard_if
    assert h[('late 15:00-15:29', 'pl15_itm WITHOUT bk15')] > 4 * h[('intraday 10:30-14:59', 'pl15_itm WITHOUT bk15')]


def test_auc_all_d1_selling():
    X = pd.read_pickle(f'{OUT}/bl_auc_all_panel.pkl.gz'); assert len(X) == 32 * 374 * 2 and X.y.sum() == 2635
    assert ((X.sched_share >= 0) & (X.sched_share <= 1)).all()
    A = pd.read_csv(f'{OUT}/bl_auc_all.csv').set_index(['variant', 'model']).AUC; assert A[('A same-minute (primary)', 'gb')] > 0.85 and A[('B causal (market lagged 1 min)', 'gb')] < A[('A same-minute (primary)', 'gb')]
    B = pd.read_csv(f'{OUT}/bl_auc_all2.csv').set_index('variant'); assert abs(B.AUC['A0 same-minute, no book state'] - A[('A same-minute (primary)', 'gb')]) < 0.01 and B.AUC['timetable + clock only'] < 0.85


def test_hg_long_side_controller_strike_lump():
    H1 = json.load(open(f'{OUT}/bl_summary_hg1.json')); assert H1['quiet_balanced_share'] > 0.97 and H1['close_gap_equals_v'] > 0.9
    H = json.load(open(f'{OUT}/bl_summary_hg345.json')); assert H['L3']['buy']['equals_gap'] > 0.95 and H['L4']['outermost'] > H['L4']['chance'] + 0.1 and H['L4']['innermost'] < 0.05
    T = pd.read_csv(f'{OUT}/bl_hg_strike2.csv').set_index('reference'); assert T.exact['atm_px'] > T.null_same_slot_exact['atm_px'] + 0.1 and T.within1['atm_px'] > 0.9 and T.exact['atm_px'] > T.exact['body_fill']
    L = json.load(open(f'{OUT}/bl_summary_hg6b.json')); assert L['share_lump_opposes_book_delta'] > 0.85 and L['ratio_q']['0.5'] < 0.2


def test_lp_lump_structure_timing_and_size():
    D = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); M = D[D.main == 1]; assert len(M) == 30
    cy = pd.read_csv(f'{OUT}/bl_size_cycles.csv').reset_index().rename(columns={'index': 'cid'}); M = M.merge(cy[['cid', 'd1']], on='cid')
    assert (M[M.d1 >= '2026-08-24'].hhmmss >= '15:30:00').all() and (M[M.d1 <= '2026-08-05'].hhmmss < '15:15:00').all()
    O = C.load_orders(); v = O[(O.module == 'v_') & (O.dayno == 0)]; assert v[v.und == 'NIFTY'].lots.max() == 27 and v[v.und == 'SENSEX'].lots.max() == 50
    S = pd.read_csv(f'{OUT}/bl_lp_size.csv'); assert S.MAE_lots.min() > 10
    L6 = json.load(open(f'{OUT}/bl_summary_lp6.json')); assert L6['d0']['sell_over_buy_median'] < 0.2 and L6['d0_contracts']['fully_closed_any_module'] > 0.9


def test_full_d1_activity_auc():
    X = pd.read_pickle(f'{OUT}/bl_full_panel.pkl.gz'); assert len(X) == 32 * 390 * 2 and X.y_any.sum() >= X.y_body_sell.sum()
    T = pd.read_csv(f'{OUT}/bl_full_auc.csv'); A = T[T.variant.str.startswith('A same')].set_index('activity').AUC
    assert (A > 0.85).all() and A['body_buyback'] < 0.99                 # no own-label leak
    O = pd.read_csv(f'{OUT}/bl_full_overall.csv').set_index('variant'); assert O.AUC_any_activity.iloc[0] > 0.9 and O.AUC_any_activity.iloc[2] < O.AUC_any_activity.iloc[0]


def test_fr_free_running_reconstruction():
    OVr = pd.read_csv(f'{OUT}/bl_fr_overall.csv').set_index('variant'); p = OVr.loc['FR free-running (primary)']
    assert p.real_lots == 13655 and 0.6 < p.F1 < 0.8 and p.F1_strict < p.F1_within1 < p.F1 and p.precision > p.recall
    C = pd.read_csv(f'{OUT}/bl_fr_classes.csv'); P = C[C.variant == 'FR free-running (primary)'].set_index('cls'); T = C[C.variant.str.startswith('TF')].set_index('cls')
    assert P.F1['body_buyback'] < P.F1['body_sell'] and T.F1['wing_buy'] > P.F1['wing_buy'] + 0.1 and P.real_lots['not_modelled'] == 457
    X = pd.read_pickle(f'{OUT}/bl_fr_orders.pkl.gz')['FR free-running (primary)']; assert set(X[0].cls) <= {'body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'opening_wings', 'lump'}
    carry = json.load(open(f'{OUT}/bl_summary_fr1.json')); assert 0.3 < carry['carry_FR free-running (primary)']['long_overlap'] < 0.8 and carry['carry_TF-hedge (hedge on real body)']['short_overlap'] > 0.99


def test_bb_buyback_decode():
    G = pd.read_csv(f'{OUT}/bl_bb_eventlevel.csv'); assert len(G) == 841 and 0.4 < (G.r_first >= 1.45).mean() < 0.6
    s = G[G.r_first >= 1.45]; assert s.r_first.quantile(0.9) < 1.85 and s.r_first.median() > 1.5
    V = pd.read_csv(f'{OUT}/bl_bb_vel.csv').set_index('variable'); assert V.F1_pm1_oof['rh_min'] > V.F1_pm1_oof['rc_min']
    TF = pd.read_csv(f'{OUT}/bl_bb_tf.csv'); assert TF[(TF.cls == 'body_buyback')].F1.max() < 0.65
    O1 = pd.read_csv(f'{OUT}/bl_fr_overall.csv').iloc[0]; O2 = pd.read_csv(f'{OUT}/bl_fr2_overall.csv').iloc[0]; assert O2.F1 >= O1.F1 - 0.005
    R = json.load(open(f'{OUT}/bl_summary_rep1.json')); assert all(c['rep_max'] == 0 for c in R['chosen'])


def test_bs_buyback_second_pass():
    E = pd.read_csv(f'{OUT}/bl_bb_events.csv'); assert 0.8 < (E.r_ref_min > 1).mean() < 0.95
    X = pd.read_pickle(f'{OUT}/bl_bs_panel.pkl.gz'); g = X[(X.gate == 1) & (X.ratio_h >= 1.7)]; assert g[g.don60 == 1].y.mean() > 2 * g[g.don60 == 0].y.mean()
    P = pd.read_csv(f'{OUT}/bl_bs_price.csv').set_index('price'); assert P.F1['high'] >= P.F1.max() - 1e-9
    AB = pd.read_csv(f'{OUT}/bl_bs_ab.csv'); assert AB[(AB['mode'] == 'tf_bb') & (AB.cls == 'body_buyback')].F1.iloc[0] < P.F1['high']


def test_bt_buyback_third_pass():
    F = pd.read_csv(f'{OUT}/bl_bt_fresh.csv'); f = F[F.ratio > 1]; assert f[f.mins_held <= 10].ratio.median() < 1.2 < 1.5 < f[f.mins_held > 30].ratio.median()
    X = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); assert X.y.sum() > 1250; s = X[X.typ == 'scheduled']; assert s[s.ratio_h > 1.7].y.mean() > 20 * s[(s.ratio_h > 1.1) & (s.ratio_h <= 1.4)].y.mean()
    B7 = json.load(open(f'{OUT}/bl_summary_bt7.json')); P = pd.DataFrame(B7['table']).set_index('state'); assert P.partner_same_strike_other_right['in profit'] > 3 * P.partner_same_strike_other_right['in loss']


def test_ev_rebalancing_events():
    OV = pd.read_csv(f'{OUT}/bl_ev_overall.csv'); g = lambda m, v: float(OV[(OV['mode'] == m) & OV.variant.str.startswith(v)].F1.iloc[0])
    assert abs(g('free', 'rebalancing') - g('free', 'plain')) < 0.03 and abs(g('tf_bb', 'rebalancing') - g('tf_bb', 'plain')) < 0.01
    C = pd.read_csv(f'{OUT}/bl_ev_classes.csv'); b = C[(C['mode'] == 'tf_bb') & (C.cls == 'body_buyback') & C.variant.str.startswith('plain')].F1.iloc[0]; assert 0.57 < b < 0.60


def test_fwd_unseen_cycles():
    F = pd.read_csv(f'{OUT}/bl_fwd.csv'); assert (F.train_cycles == 21).all() and (F.test_cycles == 11).all()
    assert (F.F1_forward < F.F1_out_of_fold_same_cycles + 0.02).all() and (F.AUC_any_forward > 0.85).all() and (F.F1_forward > 0.5).all()


def test_lots_budget_and_fixes():
    E_ = pd.read_pickle(f'{OUT}/bl_err_lots.pkl.gz'); r = E_[(E_.side == 'real') & (E_.cause != 'matched')].cause.value_counts(); assert r.idxmax() == 'quantity shortfall' and len(E_[E_.side == 'real']) == 13655
    CE = pd.read_csv(f'{OUT}/bl_lots_ceiling.csv'); assert CE.F1.is_monotonic_increasing and CE.F1.iloc[1] - CE.F1.iloc[0] > 0.1
    F = pd.read_csv(f'{OUT}/bl_lots_fit.csv'); fw = F[F.setup.str.startswith(('A', 'B'))].pivot(index='setup', columns='model', values='F1'); assert (fw.fixed <= fw.baseline + 0.005).all()


def test_ml_policies_and_scoreboard():
    M = pd.read_csv(f'{OUT}/bl_ml_fit.csv'); b = M[M.model == 'baseline'].set_index('setup').F1
    for v in ('+ sell policy', '+ buy-back policy', '+ both policies'):
        x = M[M.model == v].set_index('setup').F1; assert not ((x > b + 0.005).all())          # no learned policy improves every setup
    R = json.load(open(f'{OUT}/bl_summary_ml2.json')); assert R['0.1'] > R['ladder_rule']


def test_push2_round_two():
    P = pd.read_csv(f'{OUT}/bl_push2.csv').pivot(index='model', columns='setup', values='F1'); b = P.loc['baseline']
    assert not (P.loc['+ relabel + joint tuning'] > b + 0.005).all() and abs(P.loc['+ opening-wing close relabel'] - b).max() < 0.01


def test_d0s_labels_and_timetable():
    S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); R0 = json.load(open(f'{OUT}/bl_summary_d0s0.json')); assert S.lots.sum() == R0['lots'] and sum(R0['by_label'].values()) == R0['lots']
    p = S[S.pid >= 0]; g = p.groupby(['cid', 'pid']); assert (g.cp.nunique() == 2).all() and (g.strike.nunique() == 1).all() and ((g.tod.max() - g.tod.min()) <= 3).all()
    TT = pd.read_csv(f'{OUT}/bl_d0s_tt.csv'); a = TT[TT.test.str.startswith('T1b timetable (OOF) vs all')].iloc[0]; assert a.F1 > 0.75 and a.precision > 0.9
    b = TT[TT.test.str.startswith('T2b breakout')].F1.iloc[0]; assert b > 2 * TT[TT.test.str.contains('placebo')].F1.max()


def test_d0s_solo_and_auc():
    SO = pd.read_csv(f'{OUT}/bl_d0s_solo.csv').set_index('machine'); m1 = SO.loc['M1 spot ladder'].F1; assert m1 > 3 * SO[SO.index.str.startswith('placebo M1')].F1.max() and m1 > 2 * SO.loc['D-1 ladder unchanged (X 0.2, gate 60, 1 lot)'].F1
    assert SO.loc['M3 r 0.5 real buy-back times (all cycles, reference)'].F1 > 1.5 * SO[SO.index.str.startswith('placebo M3')].F1.max()
    A = pd.read_csv(f'{OUT}/bl_d0s_auc.csv').set_index('variant').AUC; assert A['A same-minute market + rules'] > 0.9 and A['B causal (market lagged 1 min)'] < A['A same-minute market + rules'] < A['C A + real buy-back history (earlier minutes) + book']
    CC = pd.read_csv(f'{OUT}/bl_d0s_auc_cc.csv'); assert (CC.AUC_bb_other_now > 0.55).all()


def test_d0b_ledger_and_hazard():
    X = pd.read_pickle(f'{OUT}/bl_d0b_removed.pkl.gz'); R0 = json.load(open(f'{OUT}/bl_summary_d0b0.json')); assert len(X) == R0['bb_lots'] == 9656 and set(X.origin) == {'D-1', 'D0'}
    H = pd.read_csv(f'{OUT}/bl_d0b_hazard.csv'); h = H[(H.price == 'rh') & (H.origin == 'all')].set_index('ratio_bin').hazard_pct; assert h['(1.7, 1.8]'] > 5 * h['(1.0, 1.1]'] and h['(0.0, 0.1]'] > h['(0.5, 0.75]']


def test_d0b_machines_and_side():
    M = pd.read_csv(f'{OUT}/bl_d0b_mach.csv').set_index('machine').F1; fin = M['K5 + block clock']
    assert M['K2a refit theta and price'] > M['K1 D-1 stop unchanged (high >= 1.6x)'] and fin > 1.5 * M['null: rate-matched random minutes'] and fin > 2 * M['null: final machine shifted +15 min']
    S = pd.read_csv(f'{OUT}/bl_d0b_side_auc.csv'); assert not ((S.AUC_half_even >= 0.7) & (S.AUC_half_odd >= 0.7)).any()          # no side-level trigger passes the pre-set bar
    A = pd.read_csv(f'{OUT}/bl_d0b_auc.csv').set_index('variant').AUC; assert 0.78 < A['A same-minute market + book'] < 0.85 and A['clock only'] < A['B completed bars (causal)']


def test_d0h_controller_and_lump():
    R1 = json.load(open(f'{OUT}/bl_summary_d0h1.json')); h = R1['H1']; assert h['buy']['equals_gap'] > 0.9 and h['buy']['equals_gap_excl_v'] < 0.6 and h['sell']['equals_gap'] > 0.85
    assert 3 < R1['H4_dt_body_q_buy'][2] < 5 and R1['H2']['d1_rule_2p5']['exact'] > 3 * 0.1 and all(o['X'] == 0.025 for o in R1['H2']['oof'])
    R2 = json.load(open(f'{OUT}/bl_summary_d0h2.json')); v = R2['3b_T1']['v_']; assert v['lots_while_L_gt_S'] > 0.99 and v['le_excess'] > 0.98
    A = pd.read_csv(f'{OUT}/bl_d0h_auc.csv'); assert (A[A.variant.str.startswith('teacher')].AUC > 0.97).all() and (A[A.variant.str.startswith('causal')].AUC > A[A.variant == 'clock only'].AUC.values).all()


def test_d0x_stop_and_clearance():
    S2 = pd.read_csv(f'{OUT}/bl_d0x_s2.csv'); g = lambda m, L, sc='cumulative': float(S2[(S2.mark == m) & (S2.L_lakh == L) & (S2.scope == sc)].F1_pm1.iloc[0])
    assert g('close', 1.2) == 1.0 and g('prev_close', 1.2) < 0.6 and S2[S2.scope == 'D0-only'].F1_pm1.max() < 0.5
    R = json.load(open(f'{OUT}/bl_summary_d0x1.json')); b = R['s2_close_L_bounds_lakh']; assert b['nonstop_min_close'] > max(b['stop_cycles_close_at_crossing']) and R['stop_cycles'] == 11
    C2 = pd.read_csv(f'{OUT}/bl_d0x_c2.csv'); assert (C2[C2.lots == 'short'].closed_share > 0.999).all() and (C2[C2.lots == 'long'].accuracy_oof < C2[C2.lots == 'long'].majority_class).all()


def test_d0_free_run():
    OV = pd.read_csv(f'{OUT}/bl_d0_fr_score.csv').set_index('split'); A = pd.read_csv(f'{OUT}/bl_d0_fr_auc.csv').set_index('split')
    assert (OV.F1 > 2 * OV.null_shift15_F1).all() and (OV.F1 > 0.35).all() and (OV.F1 < 0.6).all() and (A.AUC_model > 0.8).all() and (A.AUC_model > A.AUC_raw_simulator).all()
    P = json.load(open(f'{OUT}/bl_d0_fr_params.json')); assert all(set(v['train']).isdisjoint(v['test']) for v in P.values())
    S = pd.read_csv(f'{OUT}/bl_d0_fr_stops.csv'); o = S[S.split.str.startswith('OOF')]; assert (o.agree == 'both').sum() >= 7 and len(o) == 30
