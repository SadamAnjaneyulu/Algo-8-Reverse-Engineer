"""M2-D wing/body tests: false matches, multiple candidates, partial quantities, unmatched positions, missing metadata, method disagreement (SYNTHETIC_TEST) + real-ledger checks."""
import dataclasses as dc, hashlib, json, os
import pytest
from conftest import PE, REPO
from pe import wing_body as wb
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators.synthetic import Builder, BASE_TS
M = 'SYNTHETIC_TEST'
N = lambda cp='CE', k=24000, exp='2026-01-08', und='NIFTY': (cp, k, exp, und)


def mk(spec, meta_overrides=None):
    """spec rows: (role, key, ts_offset_s, qty, parent, entry_minute_offset or None). role: body (sell, module num) / wing (buy, module h_) opening. Returns (LineageSet, meta, fills)"""
    b = Builder('wb'); ids = {}; meta = {}
    for role, key, t, q, parent, e in spec:
        if key not in ids: ids[key] = b.add_inst(cp=key[0], strike=key[1], expiry=key[2], und=key[3])
        b.fill(ids[key], t, -1 if role == 'body' else 1, q, 10000 if role == 'body' else 300, parent=parent, module='num' if role == 'body' else 'h_')
        if parent not in meta: meta[parent] = dict(parent_order_id=parent, order_entry_minute_s=None if e is None else BASE_TS + 60 * e, app_key_last6='632469')
    meta.update(meta_overrides or {}); ins, fills = b.out(); return LineageSet(fills, ins, M, 'src'), meta, fills


def links(R, m, level='OPENING'): return sorted((l['wing_parent'], l['body_parent']) for l in R.links[m] if l['level'] == level)


def test_false_matches_different_right_expiry_underlying_are_never_linked():
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('PE', 24000), 0, 65, 'B_pe', 0), ('body', N('CE', 24000, '2026-01-15'), 0, 65, 'B_exp', 0), ('body', N('CE', 77000, und='SENSEX'), 0, 65, 'B_und', 0), ('body', N('CE'), 0, 65, 'B_ok', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta)
    for m in ('W1', 'W1_S60', 'W2', 'W2_S60'): assert links(R, m) == [('W', 'B_ok')], m
    wb.check(R, ls)


def test_primary_requires_same_entry_minute_and_S60_is_inclusive_at_60_and_excludes_61():
    spec = [('wing', N('CE', 24800), 100, 65, 'W', 1), ('body', N('CE'), 100 - 60, 65, 'B60', 0), ('body', N('CE', 24100), 100 - 61, 65, 'B61', 0), ('body', N('CE', 24200), 100 + 60, 65, 'B60after', 2)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta)
    assert links(R, 'W1') == [] and links(R, 'W1_S60') == [('W', 'B60'), ('W', 'B60after')]                                   # |dt| = 60 inclusive, 61 excluded, entry minute irrelevant for the sensitivity
    assert all(l['same_entry_minute'] == 0 and l['in_primary_candidate_set'] == 0 for l in R.links['W1_S60'])
    wb.check(R, ls)


def test_session_boundary_is_not_crossed_by_the_sixty_second_window():
    d = 86400 - (9 * 3600 + 16 * 60)                                                                   # BASE_TS + d = 00:00:00 IST next day
    spec = [('body', N('CE'), d - 20, 65, 'B', 0), ('wing', N('CE', 24800), d + 20, 65, 'W', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); assert links(R, 'W1_S60') == []                                        # 40 s apart but different IST sessions


def test_multiple_candidate_bodies_are_all_kept_with_ties_flagged_and_proportional_weights():
    spec = [('wing', N('CE', 24800), 5, 65, 'W', 0), ('body', N('CE', 24000), 0, 65, 'B1', 0), ('body', N('CE', 24050), 10, 130, 'B2', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); L = {l['body_parent']: l for l in R.links['W1']}
    assert set(L) == {'B1', 'B2'} and L['B1']['link_status'] == 'MULTIPLE_CANDIDATES' and L['B1']['nearest_tied'] == 1 and L['B2']['nearest_tied'] == 1       # |dt| = 5 for both: ambiguous, not resolved
    W2 = {l['body_parent']: l for l in R.links['W2']}; assert W2['B1']['weight'] == pytest.approx(1 / 3) and W2['B2']['weight'] == pytest.approx(2 / 3) and sum(l['weighted_wing_units'] for l in R.links['W2']) == pytest.approx(65)
    wb.check(R, ls)


def test_unique_nearest_candidate_is_flagged_without_discarding_the_other():
    spec = [('wing', N('CE', 24800), 5, 65, 'W', 0), ('body', N('CE', 24000), 4, 65, 'B1', 0), ('body', N('CE', 24050), 30, 65, 'B2', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); L = {l['body_parent']: l for l in R.links['W1']}; assert L['B1']['nearest'] == 1 and L['B1']['nearest_tied'] == 0 and L['B2']['nearest'] == 0 and len(L) == 2


def test_partial_quantities_ratio_group_level_and_unmatched_units():
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('CE'), 0, 195, 'B', 0), ('wing', N('CE', 24800), 400, 130, 'W_alone', 7), ('body', N('CE', 24100), 600, 65, 'B_alone', 9)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); l = R.links['W1'][0]
    assert l['qty_ratio'] == pytest.approx(1 / 3) and l['wing_qty'] == 65 and l['body_qty'] == 195 and l['otm_distance'] == 800 and l['px_ratio'] == pytest.approx(300 / 10000) and l['dt_s'] == 3
    c = wb.coverage(R, 'OPENING', 'W1'); assert (c['wing_units'], c['wing_units_unmatched'], c['body_units'], c['body_units_without_wing'], c['wing_items_no_candidate'], c['body_items_without_wing']) == (195, 130, 260, 65, 1, 1)
    g = wb.group_level_ratios(R)['OPENING']; assert g['groups_with_both'] == 1 and g['groups_wing_only'] == 1 and g['groups_body_only'] == 1 and g['ratio']['median'] == pytest.approx(1 / 3) and g['share_exactly_1_of_all_groups'] == 0
    wb.check(R, ls)


def test_wing_uncovered_by_primary_is_recovered_only_as_sensitivity_and_reported_as_unmatched_in_primary():
    spec = [('wing', N('CE', 24800), 30, 65, 'W', 1), ('body', N('CE'), 20, 65, 'B', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); assert wb.coverage(R, 'OPENING', 'W1')['wing_units_unmatched'] == 65 and wb.coverage(R, 'OPENING', 'W1_S60')['wing_units_unmatched'] == 0
    assert wb.disagreements(R)['W1_none_S60_has_candidates'] == 1


def test_missing_entry_minute_excludes_from_primary_only_and_missing_app_key_never_blocks():
    spec = [('wing', N('CE', 24800), 3, 65, 'W', None), ('body', N('CE'), 0, 65, 'B', 0), ('wing', N('CE', 24900), 4, 65, 'W2', 0)]
    ls, meta, _ = mk(spec, meta_overrides={'W2': dict(parent_order_id='W2', order_entry_minute_s=BASE_TS, app_key_last6=None)})
    R = wb.analyse(ls, meta); assert R.no_entry_minute['OPENING'] == ['WBI:OPENING:WING:W:' + next(i for i in ls.instruments if i.endswith('24800'))]
    assert links(R, 'W1') == [('W2', 'B')] and ('W', 'B') in links(R, 'W1_S60')                                                    # no entry minute: not placeable in W1, still eligible by execution time; NA app key does not block
    assert all(l['wing_app_key'] == 'NA' for l in R.links['W1'])
    R2 = wb.analyse(ls, {}); assert R2.links['W1'] == [] and len(R2.links['W1_S60']) == 2                                           # no metadata at all: nothing invented, sensitivity still works


def test_second_app_key_wings_stay_eligible():
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('CE'), 0, 65, 'B', 0)]
    ls, meta, _ = mk(spec); meta['W']['app_key_last6'] = 'F88187'; R = wb.analyse(ls, meta); assert links(R, 'W1') == [('W', 'B')] and R.links['W1'][0]['wing_app_key'] == 'F88187' and R.links['W1'][0]['body_app_key'] == '632469'


def test_many_to_many_is_preserved_and_never_forced_one_to_one():
    spec = [('wing', N('CE', 24800), 3, 65, 'W1', 0), ('wing', N('CE', 24900), 4, 65, 'W2', 0), ('body', N('CE', 24000), 0, 65, 'B1', 0), ('body', N('CE', 24050), 1, 65, 'B2', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); assert len(R.links['W1']) == 4 and {l['n_candidates_for_wing'] for l in R.links['W1']} == {2} and {l['n_wings_for_body'] for l in R.links['W1']} == {2}
    assert len(R.links['W3']) == 2 and {(l['wing_parent'], l['body_parent']) for l in R.links['W3']} == {('W1', 'B1'), ('W2', 'B2')}               # the arithmetic queue pairs 1:1; it is a different convention, not the truth


def test_W3_is_arithmetic_conserves_units_and_respects_sessions():
    d = 86400 - (9 * 3600 + 16 * 60)
    spec = [('body', N('CE'), 0, 130, 'B1', 0), ('wing', N('CE', 24800), 10, 65, 'W1', 0), ('wing', N('CE', 24900), 20, 130, 'W2', 0), ('body', N('CE', 24050), d + 10, 65, 'B_next', 400), ('wing', N('CE', 24800), d + 20, 65, 'W_next', 400)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); seg = [(l['wing_parent'], l['body_parent'], l['queue_matched_units']) for l in R.links['W3']]
    assert seg == [('W1', 'B1', 65), ('W2', 'B1', 65), ('W_next', 'B_next', 65)] and R.w3_residual == dict(wing_units_unmatched=65, body_units_unmatched=0)                  # W2 has 65 uncovered units; sessions never mixed
    assert all(l['evidence_class'].startswith('UNRESOLVED') and l['nearest'] == 'NA' and l['link_status'] == 'ARITHMETIC_SEGMENT' for l in R.links['W3']); wb.check(R, ls)
    c = wb.coverage(R, 'OPENING', 'W3'); assert (c['wing_units_unmatched'], c['body_units_without_wing']) == (65, 0)


def test_methods_can_disagree_and_the_disagreement_is_counted_not_resolved():
    spec = [('wing', N('CE', 24800), 60, 65, 'W', 1), ('body', N('CE', 24000), 5, 65, 'A', 1), ('body', N('CE', 24100), 55, 65, 'B', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta)
    assert [(l['body_parent'], l['nearest']) for l in R.links['W1']] == [('A', 1)] and sorted((l['body_parent'], l['nearest']) for l in R.links['W1_S60']) == [('A', 0), ('B', 1)]
    assert wb.disagreements(R)['W1_nearest_differs_from_S60_nearest'] == 1


def test_parent_order_is_one_item_partial_fills_do_not_inflate_candidates():
    b = Builder('wb2'); i1 = b.add_inst(cp='CE', strike=24800); i0 = b.add_inst(cp='CE', strike=24000); meta = {}
    for k in range(3): b.fill(i1, k, 1, 65, 300, parent='W', module='h_')
    b.fill(i0, 0, -1, 65, 10000, parent='B', module='num'); meta = {p: dict(parent_order_id=p, order_entry_minute_s=BASE_TS, app_key_last6='632469') for p in ('W', 'B')}
    ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); R = wb.analyse(ls, meta); assert len([i for i in R.items if i.role == 'WING']) == 1 and R.links['W1'][0]['wing_qty'] == 195 and len(R.links['W1']) == 1


def test_closing_level_uses_closing_portions_of_long_h_and_short_num_episodes():
    b = Builder('wb3'); iw = b.add_inst(cp='CE', strike=24800); ib = b.add_inst(cp='CE', strike=24000)
    b.fill(iw, 0, 1, 65, 300, parent='oW', module='h_'); b.fill(ib, 0, -1, 65, 10000, parent='oB', module='num'); b.fill(iw, 100, -1, 65, 500, parent='cW', module='h_'); b.fill(ib, 102, 1, 65, 9000, parent='cB', module='num')
    meta = {'oW': dict(order_entry_minute_s=BASE_TS), 'oB': dict(order_entry_minute_s=BASE_TS), 'cW': dict(order_entry_minute_s=BASE_TS + 60), 'cB': dict(order_entry_minute_s=BASE_TS + 60)}
    ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); R = wb.analyse(ls, meta)
    assert links(R, 'W1', 'CLOSING') == [('cW', 'cB')] and links(R, 'W1', 'OPENING') == [('oW', 'oB')] and not [l for l in R.links['W3'] if l['level'] == 'CLOSING']; wb.check(R, ls)


def test_provenance_ids_and_no_explicit_or_number_block_rows():
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('CE'), 0, 65, 'B', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); allrows = [l for v in R.links.values() for l in v]
    assert all(l['membership_provenance'] == f'INFERRED:WING_BODY:{l["method"]}' and l['protective_link'] == 'UNRESOLVED' and l['claim_type'] == 'ATTRIBUTION' for l in allrows) and 'W4' not in R.links
    assert not any(l['evidence_class'].startswith('CONFIRMED') for l in allrows) and all(l['observation_basis'] for l in allrows)          # an inferred relationship is never labelled confirmed; the observed fact is a separate column
    assert len({l['link_id'] for l in allrows}) == len(allrows)


def test_association_never_changes_the_observed_layer():
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('CE'), 0, 65, 'B', 0)]
    ls, meta, _ = mk(spec); h = lambda: hashlib.sha256(''.join(ls.files['FIFO'][n] for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv')).encode()).hexdigest(); before = h(); wb.analyse(ls, meta); wb.analyse(ls, meta, 'DIRECTION'); assert h() == before


@pytest.mark.parametrize('mutation', ['wrong_right', 'drop_link', 'weights', 'dup_id', 'wrong_role', 'outside_window'])
def test_check_rejects_corrupted_results(mutation):
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('CE'), 0, 65, 'B', 0), ('body', N('CE', 24050), 1, 65, 'B2', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); wb.check(R, ls)
    if mutation == 'wrong_right': R.by_id[R.links['W1'][0]['body_item']].right = 'PE'
    elif mutation == 'drop_link': R.links['W1'].pop()
    elif mutation == 'weights': R.links['W2'][0]['weight'] = 0.9
    elif mutation == 'dup_id': R.links['W1'][1]['link_id'] = R.links['W1'][0]['link_id']
    elif mutation == 'wrong_role': R.by_id[R.links['W1'][0]['wing_item']].role = 'BODY'
    elif mutation == 'outside_window': R.by_id[R.links['W1_S60'][0]['body_item']].first_ts += 120
    with pytest.raises(InvariantViolation): wb.check(R, ls)


def test_direction_scope_is_a_wider_sensitivity_not_the_primary():
    b = Builder('wb4'); iw = b.add_inst(cp='CE', strike=24800); ib = b.add_inst(cp='CE', strike=24000)
    b.fill(iw, 3, 1, 65, 300, parent='Wn', module='num'); b.fill(ib, 0, -1, 65, 10000, parent='Bn', module='num'); meta = {p: dict(order_entry_minute_s=BASE_TS) for p in ('Wn', 'Bn')}
    ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); assert wb.analyse(ls, meta, 'TAGGED').links['W1'] == [] and len(wb.analyse(ls, meta, 'DIRECTION').links['W1']) == 1


# ----------------------------------------------------------------------------- real ledger (slow)
@pytest.fixture(scope='module')
def real():
    from pe.generators import historical as H
    ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); meta = {r['parent_order_id']: r for r in H.generate_parents(REPO, ls.roles)}; return ls, meta, wb.analyse(ls, meta)


@pytest.mark.slow
def test_real_items_invariants_and_cross_check_with_tp03_E6_pairing(real):
    ls, meta, R = real; wb.check(R, ls); c = wb.coverage(R, 'OPENING', 'W1')
    assert (c['wing_items'], c['body_items'], c['wing_units'], c['body_units']) == (8399, 13325, 617130, 626765) and R.no_entry_minute == {'OPENING': [], 'CLOSING': []}
    assert c['wing_items_with_candidate'] == 7301                                                         # TP-03 Phase 1 E6 independently paired the same 7,301 of 8,399 wing parents (same minute, same right)
    assert c['wing_units_unmatched'] + sum(R.by_id[k].qty for k in {l['wing_item'] for l in R.links['W1'] if l['level'] == 'OPENING'}) == 617130


@pytest.mark.slow
def test_real_second_app_key_wings_are_eligible_and_group_level_ratio_is_observed_not_ownership(real):
    ls, meta, R = real; ak = wb.coverage_split(R, 'W1', 'app_key'); assert ak['F88187']['wing_items'] == 687 and ak['F88187']['wing_items_with_candidate'] > 0 and ak['F88187']['share_items_with_candidate'] > 0.8
    g = wb.group_level_ratios(R)['OPENING']; assert g['groups_with_both'] == 5446 and abs(g['share_exactly_1_of_groups_with_both'] - 0.8118) < 1e-3 and g['groups_total'] == 7958 and abs(g['share_exactly_1_of_all_groups'] - 0.556) < 1e-3 and abs(g['share_of_wing_units_in_exact_1to1_groups'] - 0.531) < 2e-3


@pytest.mark.slow
def test_real_outputs_reproduce_the_committed_manifest(real):
    ls, meta, R = real; man = json.load(open(os.path.join(PE, 'reports', 'm2d_data', 'manifest.json'))); import gzip
    for name in man['files']:
        text = gzip.open(os.path.join(PE, 'reports', 'm2d_data', name), 'rt').read(); assert hashlib.sha256(text.encode()).hexdigest() == man['files'][name]['sha256_of_text']
    assert len(R.links['W1']) == man['files']['wing_body_links_W1.tsv.gz']['rows']


# ----------------------------------------------------------------------------- tests added after the independent review (mutants that survived)
def test_PE_wing_otm_distance_sign_is_positive_when_the_wing_is_further_out():
    spec = [('wing', N('PE', 23200), 3, 65, 'W', 0), ('body', N('PE', 24000), 0, 65, 'B', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); assert R.links['W1'][0]['otm_distance'] == 800 and R.links['W1'][0]['right'] == 'PE'                                          # a lower strike is further OTM for a put
    spec = [('wing', N('CE', 24800), 3, 65, 'W', 0), ('body', N('CE', 24000), 0, 65, 'B', 0)]; ls, meta, _ = mk(spec); assert wb.analyse(ls, meta).links['W1'][0]['otm_distance'] == 800


def test_item_times_and_session_come_from_the_FIRST_fill():
    d = 86400 - (9 * 3600 + 16 * 60)
    b = Builder('wbt'); iw = b.add_inst(cp='CE', strike=24800); ib = b.add_inst(cp='CE', strike=24000)
    b.fill(iw, d - 30, 1, 65, 300, parent='W', module='h_'); b.fill(iw, d + 30, 1, 65, 300, parent='W', module='h_'); b.fill(ib, d - 20, -1, 65, 10000, parent='B', module='num')
    meta = {p: dict(order_entry_minute_s=BASE_TS + d - 60) for p in ('W', 'B')}; ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); R = wb.analyse(ls, meta); w = next(i for i in R.items if i.role == 'WING')
    assert w.first_ts == BASE_TS + d - 30 and w.last_ts == BASE_TS + d + 30 and w.session == day_iso(ist_day(BASE_TS + d - 30)) and w.qty == 130 and len(R.links['W1_S60']) == 1 and R.links['W1_S60'][0]['dt_s'] == -10


def test_S60_flags_the_primary_set_correctly_and_ignores_app_keys():
    spec = [('wing', N('CE', 24800), 5, 65, 'W1', 0), ('wing', N('CE', 24900), 50, 65, 'W2', 1), ('body', N('CE'), 0, 65, 'B', 0)]
    ls, meta, _ = mk(spec); meta['W2']['app_key_last6'] = 'F88187'; R = wb.analyse(ls, meta); f = {l['wing_parent']: l['in_primary_candidate_set'] for l in R.links['W1_S60']}
    assert f == {'W1': 1, 'W2': 0}                                                                                    # the second-app-key wing is an S60 candidate; only the entry minute differs
    R2 = wb.analyse(ls, {p: dict(m, app_key_last6=None) for p, m in meta.items()}); assert [l['link_id'] for l in R2.links['W1_S60']] == [l['link_id'] for l in R.links['W1_S60']]    # removing every app key changes nothing


def test_W3_coverage_reports_queue_residual_units_not_item_counts():
    spec = [('body', N('CE'), 0, 65, 'B', 0), ('wing', N('CE', 24800), 10, 130, 'W', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); c = wb.coverage(R, 'OPENING', 'W3')
    assert c['wing_items_with_candidate'] == 1 and c['wing_units_unmatched'] == 65 and c['wing_units_with_candidate'] == 65 and c['body_units_without_wing'] == 0                         # the wing item has a segment but only 65 of its 130 units are matched


def test_W2_weighted_units_can_exceed_a_body_and_this_is_reported():
    spec = [('wing', N('CE', 24800), 1, 130, 'W1', 0), ('wing', N('CE', 24900), 2, 130, 'W2', 0), ('body', N('CE'), 0, 65, 'B', 0)]
    ls, meta, _ = mk(spec); R = wb.analyse(ls, meta); r = wb.body_weighted_coverage(R, 'W2')['OPENING']; assert r['share_gt_1'] == 1.0 and r['ratio']['max'] == 4.0           # 260 wing units weighted onto a 65-unit body


def test_scope_exclusions_and_closing_origin_are_reported():
    b = Builder('wbs'); i = b.add_inst(cp='CE', strike=24800); j = b.add_inst(cp='CE', strike=24000)
    b.fill(i, 0, 1, 65, 300, parent='numlong', module='num'); b.fill(j, 0, -1, 65, 10000, parent='s', module='s_'); b.fill(i, 50, -1, 65, 400, parent='close_by_num', module='num')
    ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); ex = wb.scope_exclusions(ls); assert ex['OPENING|LONG|num'] == 65 and ex['OPENING|SHORT|s_'] == 65 and ex['CLOSING_of_LONG_episode|closing_module|num'] == 65
    spec = [('wing', N('CE', 24800), 0, 65, 'W', 0)]; ls2, meta, _ = mk(spec); assert wb.closing_wing_origin(wb.analyse(ls2, meta), ls2) == {}


def test_closing_wing_and_body_are_defined_by_the_tag_of_the_closing_fill():
    """a long episode closed by a `num` sell, or a short episode closed by an `h_` buy, is NOT a TAGGED closing item (reported as a scope exclusion); closed by h_ / num it is"""
    b = Builder('wbc'); iw = b.add_inst(cp='CE', strike=24800); ib = b.add_inst(cp='CE', strike=24000)
    b.fill(iw, 0, 1, 130, 300, parent='oW', module='h_'); b.fill(ib, 0, -1, 130, 10000, parent='oB', module='num')
    b.fill(iw, 100, -1, 65, 500, parent='cW_num', module='num'); b.fill(iw, 101, -1, 65, 500, parent='cW_h', module='h_'); b.fill(ib, 102, 1, 65, 9000, parent='cB_h', module='h_'); b.fill(ib, 103, 1, 65, 9000, parent='cB_num', module='num')
    meta = {p: dict(order_entry_minute_s=BASE_TS) for p in ('oW', 'oB', 'cW_num', 'cW_h', 'cB_h', 'cB_num')}; ins, fills = b.out(); ls = LineageSet(fills, ins, M, 'src'); R = wb.analyse(ls, meta)
    assert sorted(i.parent_id for i in R.items if i.level == 'CLOSING' and i.role == 'WING') == ['cW_h'] and sorted(i.parent_id for i in R.items if i.level == 'CLOSING' and i.role == 'BODY') == ['cB_num']
    Rd = wb.analyse(ls, meta, 'DIRECTION'); assert len([i for i in Rd.items if i.level == 'CLOSING' and i.role == 'WING']) == 2
