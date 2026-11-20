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
