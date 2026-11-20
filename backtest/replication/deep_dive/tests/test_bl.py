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
