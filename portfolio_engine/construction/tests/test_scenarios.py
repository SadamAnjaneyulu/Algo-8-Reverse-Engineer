"""The ten required generator scenarios: determinism, the SYNTHETIC_TEST_ONLY mark, and the outcome each one is built to show."""
import pytest
from helpers import *
from pc import generators as G
from pc.scenario import Scenario, ScenarioError


@pytest.fixture(scope='module')
def results():
    out = {}
    for n, sc in G.all_scenarios().items(): sim, f = run(sc.to_text()); out[n] = (sim, f)
    return out


def test_generators_are_deterministic_and_marked_synthetic():
    a, b = G.all_scenarios(), G.all_scenarios()
    assert list(a) == list(b) and all(a[n].to_text() == b[n].to_text() for n in a)
    assert all('META\tevidence\tSYNTHETIC_TEST_ONLY' in sc.to_text() for sc in a.values())
    assert G.s10_random_stress(5).to_text() != G.s10_random_stress(6).to_text()
    with pytest.raises(ScenarioError): Scenario.parse(a['s01_complete_basket'].to_text().replace('SYNTHETIC_TEST_ONLY', 'REAL'))
    for n in a: assert Scenario.parse(a[n].to_text()).to_text() == a[n].to_text()                 # file round trip is exact


def test_every_output_file_is_marked_synthetic(results):
    for n, (_, f) in results.items():
        assert set(f) == {'decisions.tsv', 'actions.tsv', 'states.tsv', 'lineage.tsv', 'events.tsv', 'instruments.tsv', 'summary.tsv'}
        assert all('SYNTHETIC_TEST_ONLY' in t.split('\n')[0] for t in f.values()), n


def A(results, n): return table(results[n][1]['actions.tsv'])


def test_s01_complete_basket(results):
    f = results['s01_complete_basket'][1]; assert kv(f, 'fills_total') == '4' and kv(f, 'final_gross_units') == '780' and kv(f, 'final_short_units') == '390' and A(results, 's01_complete_basket') == []


def test_s02_partial_cut(results):
    a = A(results, 's02_partial_basket_cut'); assert len(a) == 4 and {x['qty'] for x in a} == {'65'} and kv(results['s02_partial_basket_cut'][1], 'final_gross_units') == '520'
    assert any(d['reason'] == 'COOLDOWN_ACTIVE' for d in table(results['s02_partial_basket_cut'][1]['decisions.tsv']))


def test_s03_full_cut_and_disabled_plugin(results):
    f = results['s03_full_basket_cut'][1]; assert kv(f, 'final_gross_units') == '0' and 'basket_reentry@1.0.0:0:' in kv(f, 'plugins') and not [d for d in table(f['decisions.tsv']) if d['plugin'] == 'basket_reentry']


def test_s04_rejected_cut(results):
    assert {x['reason'] for x in A(results, 's04_cut_rejected_insufficient_inventory')} == {'INSUFFICIENT_INVENTORY'} and kv(results['s04_cut_rejected_insufficient_inventory'][1], 'fills_total') == '4'


def test_s05_successful_reentry(results):
    a = A(results, 's05_reentry_success'); assert [(x['type'], x['status'], x['qty']) for x in a] == [('CUT', 'ACCEPTED', '65'), ('REENTRY', 'ACCEPTED', '65')] and kv(results['s05_reentry_success'][1], 'final_gross_units') == '780'


def test_s06_cooldown_rejections_at_both_layers(results):
    f = results['s06_reentry_rejected_cooldown'][1]; a = A(results, 's06_reentry_rejected_cooldown')
    assert [x['reason'] for x in a] == ['OK', 'COOLDOWN_NOT_ELAPSED'] and a[1]['action_id'] == 'inj-early-reentry'                 # validator layer
    assert 'COOLDOWN_ACTIVE' in {d['reason'] for d in table(f['decisions.tsv'])} and 'REENTRY_ELIGIBLE' not in {d['reason'] for d in table(f['decisions.tsv'])}   # plugin layer; never re-entered


def test_s07_risk_limit_rejection(results):
    a = A(results, 's07_reentry_rejected_risk_limit'); assert a[0]['status'] == 'ACCEPTED' and {x['reason'] for x in a[1:]} == {'EXPOSURE_LIMIT_EXCEEDED'} and {x['type'] for x in a[1:]} == {'REENTRY'}


def test_s08_overlapping_baskets(results):
    f = results['s08_overlapping_baskets'][1]; a = A(results, 's08_overlapping_baskets')
    assert [(x['basket_id'], x['qty'], x['status']) for x in a if x['plugin'] == 'basket_cut'] == [('B1', '65', 'ACCEPTED'), ('B2', '65', 'ACCEPTED')]
    over = [x for x in a if x['action_id'] == 'inj-b2-overcut'][0]; assert over['reason'] == 'INSUFFICIENT_INVENTORY' and 'available=65' in over['detail']       # B2 holds 130-65 although the ledger still has 195 in that instrument
    last = [r for r in table(f['states.tsv']) if r['instrument_id'] == SCE][-1]; assert last['instrument_inventory'] == '-195'


def test_s09_partial_fills_and_duplicates(results):
    f = results['s09_partial_fills_and_duplicates'][1]; assert kv(f, 'duplicate_seed_events_ignored') == '1' and kv(f, 'seed_fills_applied') == '12'
    assert [x['reason'] for x in A(results, 's09_partial_fills_and_duplicates')] == ['OK', 'DUPLICATE_ACTION_ID']
    sim = results['s09_partial_fills_and_duplicates'][0]; assert sim.book.leg('B1', 'SCE').entry_price == (65 * 10000 + 65 * 10050 + 65 * 10100) // 195 == 10050


@pytest.mark.parametrize('seed', [1, 7, 42])
def test_s10_random_stress_invariants(results, seed):
    sim, f = results[f's10_random_stress_seed{seed}']
    assert int(kv(f, 'actions_accepted')) + int(kv(f, 'actions_rejected')) == int(kv(f, 'actions_proposed'))
    for legs in sim.book.baskets.values():
        for l in legs.values(): assert 0 <= l.current <= l.initial
    claims = {}
    for legs in sim.book.baskets.values():
        for l in legs.values(): claims[l.instrument_id] = claims.get(l.instrument_id, 0) + l.side * l.current
    assert all(sim.ledger.signed_inventory(i) == claims.get(i, 0) for i in sim.ins)
    assert int(kv(f, 'actions_rejected')) > 0 and int(kv(f, 'actions_accepted')) > 0                  # the stress scenarios exercise both outcomes


def test_random_stress_many_seeds_hold_the_invariants():
    for seed in range(100, 130):
        sim, f = run(G.s10_random_stress(seed).to_text()); assert int(kv(f, 'actions_accepted')) + int(kv(f, 'actions_rejected')) == int(kv(f, 'actions_proposed'))
