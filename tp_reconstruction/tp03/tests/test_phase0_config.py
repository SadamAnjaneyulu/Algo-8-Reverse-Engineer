import os, yaml, math
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); TP03 = os.path.dirname(HERE)
CFG = yaml.safe_load(open(os.path.join(TP03, 'config.yaml')))


def test_config_parses_and_is_version_2():
    assert CFG['version'] == 2 and 'claim_types' in CFG and 'cycle_stop_figures' in CFG


def test_entry_windows_and_controls_are_the_21_quarter_hours():
    e = CFG['entry']; allw = sorted(e['d1_windows'] + e['d1_control_windows'])
    assert len(e['d1_windows']) == 17 and len(e['d1_control_windows']) == 4 and len(set(allw)) == 21
    assert allw == [f'{9 + (30 + 15 * k) // 60}:{(30 + 15 * k) % 60:02d}'.zfill(5) for k in range(21)]
    assert e['window_bounds_seconds'] == {'before': 2, 'after': 180}


def test_fifteen_minute_test_uses_all_residues_and_separates_clock_candidates():
    f = CFG['exit']['fifteen_minute']; assert f['full_residue_test']['residues'] == list(range(15)) and set(f['full_residue_test']['applied_to']) == {'fill_minute', 'order_entry_minute'}
    assert len(f['observed_clock_minute_candidates']['minutes']) == 7 and 'tick_minutes_of_15' not in CFG['exit']


def test_permutation_resolution_satisfies_the_holm_requirement():
    p = CFG['inference']['permutations']; assert p['final_inference'] == 10000 and p['exploratory_development_runs'] == 500
    for name, fam in [(k, v) for k, v in CFG['inference']['holm_families'].items() if isinstance(v, dict)]:
        thr = 0.05 / fam['size_upper_bound']; assert math.isclose(thr, fam['smallest_threshold'], rel_tol=2e-3)
        assert 1 / 501 > thr                                  # 500 permutations can never pass Holm
        assert 1 / 10001 <= 0.5 * thr                         # 10,000 can


def test_action_classes_cover_every_opening_module_and_v_never_opens_a_short():
    a = CFG['entry']['action_classes']; assert {'BODY_SHORT_OPEN', 'BODY_LONG_OPEN', 'WING_OPEN', 'LUMP_OPEN', 'STOP_MODULE_SHORT_OPEN', 'OTHER_OPEN'} <= set(a)
    T3 = pd.read_csv(os.path.join(TP03, 'analysis', 'phase0_table3_opening_modules.csv')); shorts = T3[T3.side.str.startswith('sell')]
    assert 'v_' not in set(shorts.module) and set(shorts.module) <= {'num', 's_', 'h_'}


def test_structure_counts_reproduce_the_source_figures():
    T1 = pd.read_csv(os.path.join(TP03, 'analysis', 'phase0_table1_window_reconciliation.csv'), index_col=0)
    r = T1.loc['PRE registered 17 windows']; assert r.session_windows == 544 and r.paired_same_strike == 544 and r.four_roles == 541
    c = T1.loc['PRE 4 control windows (12:15 12:45 13:00 13:15)']; assert c.NO_ACTION_ACTIVE == 85 and c.body_new_short == 43
    P = pd.read_csv(os.path.join(TP03, 'analysis', 'phase0_window_level_counts.csv')); P = P[(P.kind == 'PRE') & ~P.control_window]; assert int((P.four_roles & P.net_short_growth).sum()) == 529


def test_permutation_design_is_non_degenerate_where_claimed():
    T4 = pd.read_csv(os.path.join(TP03, 'analysis', 'phase0_table4_permutation_design.csv'))
    reg = T4[T4.design.str.contains('17 registered') & (T4.outcome == 'body_short')]; assert (reg.windows_with_nonconstant_outcome == 0).all()
    ok = T4[T4.design.str.contains('21 candidate|expiry-day applicable') & (T4.outcome == 'body_short')]
    assert (ok.windows_with_nonconstant_outcome > 0).all() and (ok.minority_class_events >= CFG['entry']['testability_gates']['min_minority_class_events_per_underlying']).all()
    assert (T4.obs_per_stratum_if_cycle_x_window == 1).all() and (T4.log10_distinct_cycle_block_permutations > 6).all()
