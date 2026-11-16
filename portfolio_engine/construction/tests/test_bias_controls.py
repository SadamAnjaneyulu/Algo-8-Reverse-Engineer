"""Bias and validation controls: look-ahead leakage, duplicate events, ordering sensitivity, lineage, risk-limit bypass, single source of position state, M2 untouched."""
import dataclasses, hashlib, os, random
import pytest
from helpers import *
from pc import generators as G
from pc._m2 import M2_PATH, m2_replay, m2_tsvio, m2_ledger
from pc.contract import LookAheadError, Plugin, PluginResult
from pc.engine import Simulation, EngineInvariantError, build_registry
from pc.model import EvalContext, MarkStore, LegView
from pc.scenario import Scenario


def decs(f): return table(f['decisions.tsv'])
def acts(f): return table(f['actions.tsv'])


# ------------------------------------------------------------------ look-ahead
def test_context_refuses_to_return_future_marks():
    ms = MarkStore([(100, 'x', 5), (101, 'x', 7)]); c = EvalContext(100, ms, (), (), {}, ())
    assert c.mark('x') == (5, 100); assert c.mark('y') is None
    with pytest.raises(LookAheadError): c.mark('x', 101)


@pytest.mark.parametrize('name', ['s05_reentry_success', 's08_overlapping_baskets', 's10_random_stress_seed1', 's10_random_stress_seed7', 's10_random_stress_seed42'])
def test_changing_future_marks_never_changes_earlier_decisions(name):
    sc = G.all_scenarios()[name]; cut_ts = sorted({t for t in sc.ticks})[len(sc.ticks) // 2]; base = run(sc.to_text())[1]
    alt = Scenario.parse(sc.to_text()); rnd = random.Random(3)
    alt.marks = [(ts, i, px if ts <= cut_ts else max(5, 5 * rnd.randint(1, 8000))) for ts, i, px in alt.marks]                  # scramble every mark after cut_ts
    alt.marks += [(cut_ts + 10 ** 6, i, 5 * rnd.randint(1, 8000)) for i in alt.instruments]; alt.ticks = sorted(alt.ticks + [cut_ts + 10 ** 6])
    f2 = run(alt.to_text())[1]
    early = lambda f, key: [r for r in table(f[key]) if int(r['ts']) <= cut_ts]
    for key in ('decisions.tsv', 'actions.tsv', 'states.tsv'):
        a, b = early(base, key), early(f2, key); assert a == b and len(a) > 0, key


def test_future_marks_do_change_later_decisions_so_the_test_has_teeth():
    sc = Scenario.parse(scn(example_body())); alt = Scenario.parse(scn(example_body().replace('\t12500\n', '\t10000\n').replace('\t12000\n', '\t10000\n')))
    assert len(acts(run(sc.to_text())[1])) == 2 and len(acts(run(alt.to_text())[1])) == 0


def test_actions_stamped_with_later_information_or_time_are_rejected():
    for extra, reason in ((action(0, 'a', 'CUT', 'SCE', 65, '', 60), 'LOOKAHEAD_VIOLATION'),):
        _, f = run(scn(plugins(False, False, True) + mark(0, SCE, 10000) + tick(0) + extra)); assert acts(f)[0]['reason'] == reason
    class Backdater(Plugin):
        name = 'backdater'; version = '1.0.0'
        def evaluate(self, ctx):
            from pc.contract import ProposedAction
            return PluginResult('OK', [ProposedAction('bd', self.name, self.version, 'CUT', '', 'B1', 'SCE', 65, '', ctx.ts - 100, ctx.ts - 100, 'x')])
    _, f = run(scn(L('PLUGIN', 'backdater', '1.0.0', 1) + tick(0)), extra={'backdater': Backdater}); assert acts(f)[0]['reason'] == 'STALE_ACTION_TIMESTAMP'


# ------------------------------------------------------------------ ordering
def _permute(text, seed):
    lines = text.split('\n'); head = [l for l in lines if l.startswith(('#', 'META', 'INST', 'RISK', 'PLUGIN', 'CONFIG'))]; data = [l for l in lines if l and not l.startswith(('#', 'META', 'INST', 'RISK', 'PLUGIN', 'CONFIG'))]
    random.Random(seed).shuffle(data); return '\n'.join(head + data) + '\n'


@pytest.mark.parametrize('name', ['s05_reentry_success', 's08_overlapping_baskets', 's09_partial_fills_and_duplicates', 's10_random_stress_seed7'])
def test_line_order_of_the_scenario_file_does_not_change_any_output(name):
    text = G.all_scenarios()[name].to_text(); base = run(text)[1]
    for seed in (1, 2, 3): assert run(_permute(text, seed))[1] == base


def test_plugin_registration_order_is_a_disclosed_sensitivity():
    """two plugins propose conflicting same-timestamp cuts of the same leg: whichever is registered first wins. Deterministic for a given order, different between orders."""
    def body(first, second):
        return (L('PLUGIN', first, '1.0.0', 1) + L('PLUGIN', second, '1.0.0', 1) + cfg('basket_cut', 'policy', 'SCHEDULED') + cfg('basket_cut', 'leg_side_filter', 'SHORT') + cfg('basket_cut', 'option_type_filter', 'CE') + cfg('basket_cut', 'units', 130)
                + mark(0, SCE, 10000) + tick(0) + action(0, 'script-cut', 'CUT', 'SCE', 130))
    _, a = run(scn(body('basket_cut', 'scripted_actions'))); _, b = run(scn(body('scripted_actions', 'basket_cut'))); _, a2 = run(scn(body('basket_cut', 'scripted_actions')))
    assert a == a2                                                                                      # deterministic
    # basket_cut first: its 130-unit cut is accepted, then the scripted 130 exceeds the 65 left
    assert [(x['plugin'], x['status']) for x in acts(a)] == [('basket_cut', 'ACCEPTED'), ('scripted_actions', 'REJECTED')]
    # scripted_actions first: its cut is accepted and basket_cut then sees max_cuts_per_leg reached and proposes nothing
    assert [(x['plugin'], x['status']) for x in acts(b)] == [('scripted_actions', 'ACCEPTED')] and acts(a) != acts(b)


# ------------------------------------------------------------------ duplicates
def test_duplicate_seed_events_and_duplicate_action_ids():
    dup = L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 195, 10000, T0)
    _, f = run(scn(dup + dup + plugins(False, False, True) + mark(0, SCE, 10000) + tick(0) + action(0, 'x', 'CUT', 'SCE', 65) + action(0, 'x', 'CUT', 'SCE', 65)))
    assert kv(f, 'duplicate_seed_events_ignored') == '2' and kv(f, 'seed_fills_applied') == '4' and [a['status'] for a in acts(f)] == ['ACCEPTED', 'REJECTED'] and acts(f)[1]['reason'] == 'DUPLICATE_ACTION_ID'
    with pytest.raises(Exception): Scenario.parse(scn(L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 195, 10005, T0)))              # same id, other content: refused, not silently merged
    _, f = run(scn(plugins(False, False, True) + mark(0, SCE, 10000) + tick(0) + action(0, 'x', 'CUT', 'SCE', 65) + action(0, 'x', 'CUT', 'SCE', 65)))
    assert kv(f, 'fills_total') == '5'                                                                  # the duplicate cut did not produce a second fill


# ------------------------------------------------------------------ lineage
def test_reentry_needs_a_valid_accepted_cut_of_the_same_basket_and_leg():
    pre = plugins(False, False, True) + mark(0, SCE, 10000) + tick(0)
    cases = [(action(0, 'r', 'REENTRY', 'SCE', 65, 'missing'), 'INVALID_CUT_LINEAGE'),
             (action(0, 'c', 'CUT', 'SPE', 65) + action(0, 'r', 'REENTRY', 'SCE', 65, 'c'), 'INVALID_CUT_LINEAGE'),                    # cut of another leg
             (action(0, 'c', 'CUT', 'SCE', 260) + action(0, 'r', 'REENTRY', 'SCE', 65, 'c'), 'INVALID_CUT_LINEAGE'),                   # the cut was rejected
             (action(0, 'r', 'REENTRY', 'SCE', 65, ''), 'INVALID_CUT_LINEAGE')]
    for extra, reason in cases: _, f = run(scn(pre + extra)); assert acts(f)[-1]['reason'] == reason
    # a cut of basket B1 cannot be used by another basket
    two = scn(pre + action(0, 'c', 'CUT', 'SCE', 65) + L('ACTION', T0, 'r', '', '', 'REENTRY', 'B2', 'SCE', 65, 'c', T0, ''))
    _, f = run(two); assert acts(f)[-1]['reason'] == 'INVALID_BASKET_STATE'
    _, f = run(scn(example_body())); lin = {r['fill_id']: r for r in table(f['lineage.tsv'])}
    assert lin['PC000002']['parent_cut_id'] == lin['PC000001']['action_id'] and lin['PC000001']['origin_seed_fills'] == lin['PC000002']['origin_seed_fills'] == 'f1' and lin['f1']['kind'] == 'SEED'


def test_every_executed_fill_has_exactly_one_lineage_row():
    for n, sc in G.all_scenarios().items():
        sim, f = run(sc.to_text()); ids = [r['fill_id'] for r in table(f['lineage.tsv'])]; assert ids == [x.fill_id for x in sim.fills] and len(set(ids)) == len(ids), n


# ------------------------------------------------------------------ risk-limit bypass
def test_splitting_an_action_into_pieces_does_not_bypass_the_limit():
    body = action(0, 'c', 'CUT', 'SCE', 195) + ''.join(action(0, f'r{k}', 'REENTRY', 'SCE', 65, 'c') for k in range(3))
    _, f = run(scn(plugins(False, False, True) + risk('max_short_units', 390 - 130) + mark(0, SCE, 10000) + tick(0) + body))        # short after cut = 195; limit 260 -> only one 65-lot fits
    assert [a['status'] for a in acts(f)] == ['ACCEPTED', 'ACCEPTED', 'REJECTED', 'REJECTED'] and kv(f, 'final_short_units') == '260'


def test_a_plugin_cannot_use_another_plugins_name_or_reuse_ids_to_slip_past():
    _, f = run(scn(plugins(False, False, True) + mark(0, SCE, 10000) + tick(0) + action(0, 'basket_cut|x', 'CUT', 'SCE', 65, '', 0, 'basket_cut'))); assert acts(f)[0]['reason'] == 'PLUGIN_MISMATCH'


def test_plugin_views_are_immutable_and_cannot_change_state():
    class Tamper(Plugin):
        name = 'tamper'; version = '1.0.0'; seen = []
        def evaluate(self, ctx):
            for b in ctx.baskets:
                for l in b.legs:
                    try: l.current = 0
                    except dataclasses.FrozenInstanceError: Tamper.seen.append('frozen')
            try: ctx.baskets[0].legs.append(None)
            except AttributeError: Tamper.seen.append('tuple')
            try: ctx.baskets[0].status = 'x'
            except dataclasses.FrozenInstanceError: Tamper.seen.append('frozen_basket')
            return PluginResult()
    sim, f = run(scn(L('PLUGIN', 'tamper', '1.0.0', 1) + tick(0)), extra={'tamper': Tamper})
    assert {'frozen', 'tuple', 'frozen_basket'} <= set(Tamper.seen) and kv(f, 'final_gross_units') == '780' and sim.book.leg('B1', 'SCE').current == 195


def test_the_engine_detects_inventory_changed_behind_its_back():
    sim = Simulation(Scenario.parse(scn(plugins() + tick(0)))); sim.run()
    from pc._m2 import m2_schema
    sim.ledger.apply_fill(m2_schema.Fill('rogue', 99, 'rogue', 'x', SCE, T0 + 5, 1, 65, 10000, 65, 'Filled', False, 'SYNTHETIC_TEST', 'rogue'))          # a fill that bypasses the engine
    with pytest.raises(EngineInvariantError): sim._reconcile()


# ------------------------------------------------------------------ one position state: the unchanged M2 ledger
def test_output_events_replayed_by_the_unchanged_m2_engine_give_the_same_state(tmp_path):
    for n, sc in G.all_scenarios().items():
        sim, f = run(sc.to_text()); (tmp_path / 'e.tsv').write_text(f['events.tsv']); (tmp_path / 'i.tsv').write_text(f['instruments.tsv'])
        ins = m2_tsvio.read_instruments(str(tmp_path / 'i.tsv')); fills = m2_tsvio.read_events(str(tmp_path / 'e.tsv'), ins)
        r = m2_replay.replay(fills, ins, 'SYNTHETIC_TEST', sc.method, 'src', 0, strict=True)
        for i in sim.ins: assert f'INSTR\t{i}\t{sim.ledger.signed_inventory(i)}\t' in r.dump or (sim.ledger.signed_inventory(i) == 0 and f'INSTR\t{i}\t' not in r.dump), (n, i)       # an instrument that never traded has no INSTR line
        assert f'TOTAL\trealized_pnl_paise\t{sim.ledger.realized_total()}' in r.dump, n


def test_m2_engine_files_are_unchanged():
    here = os.path.dirname(os.path.abspath(__file__)); m2_root = os.path.dirname(M2_PATH); checked = 0
    for line in open(os.path.join(here, 'm2_sources.sha256')):
        h, rel = line.strip().split('  ')
        p = os.path.join(m2_root, rel)
        if os.path.exists(p): assert hashlib.sha256(open(p, 'rb').read()).hexdigest() == h, rel; checked += 1
    assert checked >= 40
