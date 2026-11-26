"""Regression contract of the execution convention 'one_lot_v2' against the saved 32-cycle runs: the convention is a granularity change only (decisions identical to the preserved freeze_v1 baseline), it is an execution assumption on record, and nothing was blocked by the guard."""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); S = f'{HERE}/../outputs/scoring'
C = json.load(open(f'{S}/split_comparison/comparison.json')); E = json.load(open(f'{S}/execution_convention.json')); A = json.load(open(f'{S}/d1_F/run_record.json')); B = json.load(open(f'{S}/d1_F_v2_onelot/run_record.json'))
def test_decisions_are_identical_between_baseline_and_one_lot():
    k = C['checks']; assert k['keys_only_in_one_run'] == 0 and k['keys_with_different_total_lots'] == 0 and k['total_lots_v1'] == k['total_lots_v2'] and k['non_split_roles_identical_row_by_row'] and k['real_orders_identical_between_runs']
    assert abs(A['legacy_f1_on_this_replay'] - B['legacy_f1_on_this_replay']) < 1e-12 and abs(B['legacy_f1_on_this_replay'] - 0.6878) < 5e-4          # legacy lot-level F1 unchanged
def test_one_lot_run_has_only_single_lots_for_the_identified_roles_and_nothing_rejected():
    assert C['checks']['split_role_lots_all_one_v2'] and B['rejected_orders'] == 0 and B['order_split'] == 'one_lot_v2' and A.get('order_split') in (None, 'freeze_v1') and A['rejected_orders'] == 0
    for r in ('opening_wing_buy', 'stop_buyback'): assert C['split_roles'][r]['lots_v1'] == C['split_roles'][r]['lots_v2'] and C['split_roles'][r]['share_multilot_v2'] == 0.0
def test_the_convention_is_justified_by_the_real_log_for_exactly_the_split_classes():
    ev = C['real_log_evidence']; assert all(ev[r]['share_multilot'] == 0.0 and ev[r]['max_lots'] == 1 for r in ('opening_wing_buy', 'stop_buyback'))
    assert all(v['share_multilot'] > 0.0 for k, v in C['real_log_other_classes'].items() if k in ('body_sell', 'wing_buy', 'wing_sell', 'lump'))       # the other classes are multi-lot in the real log: correctly not split
def test_record_labels_it_an_execution_assumption_with_its_own_version_and_keeps_the_baseline():
    assert E['version'] == 'one_lot_v2' and 'EXECUTION ASSUMPTION' in E['kind'] and set(E['classes']) == {'opening_wing_buy', 'stop_buyback'} and 'd1_F' in E['baseline_preserved'] and 'attempt1_guard_blocked' in E['why_the_guard_change']
    assert os.path.isdir(f'{S}/d1_F_v2_onelot_attempt1_guard_blocked')                    # the blocked first attempt is archived, not deleted

def test_freeze_v1_replay_equals_the_saved_baseline_and_the_refactor_left_v2_unchanged():
    I = json.load(open(f'{S}/split_comparison/freeze_integrity.json')); assert I['freeze_v1']['identical_to_saved'] and I['freeze_v1']['rejected'] == 0 and I['one_lot_v2']['identical_to_saved'] and I['one_lot_v2']['rejected'] == 0
def test_record_carries_the_accepted_guard_conditions_and_the_archive_exists():
    a = E['accepted_conditions']; assert 'decision_id' in a and 'freeze_v1' in a and 'measurement-granularity' in a['interpretation_note'] and 'attempt1_guard_blocked' in a['archive']
    r = json.load(open(f'{S}/d1_F_v2_onelot_attempt1_guard_blocked/run_record.json')); assert r['rejected_orders'] == 29            # the blocked first attempt stays available
