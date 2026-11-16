"""Regression tests for every defect an independent review found in the first version (input syntax, arithmetic range, fill-price fallback, id collisions,
plugin isolation, boundary behaviour, look-ahead through every input kind). Python / C++ agreement on the refusals is checked in test_parity.py."""
import dataclasses, os
import pytest
from helpers import *
from pc import generators as G
from pc.contract import Plugin, PluginResult, ProposedAction, Decision, Spec, OK
from pc.scenario import Scenario, ScenarioError
from pc.engine import Simulation, build_registry
from pc._m2 import m2_replay, m2_tsvio


def acts(f): return table(f['actions.tsv'])
def decs(f): return table(f['decisions.tsv'])
LEG1 = L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 195, 10000, T0)
BIG = 2 ** 63 - 1

BAD = {   # name -> scenario text that every loader must refuse (the same table is replayed against the C++ loader in test_parity.py)
    'int_leading_space': scn('').replace('\t195\t10000', '\t 195\t10000', 1), 'int_trailing_space': scn('').replace('\t195\t10000', '\t195 \t10000', 1), 'int_underscore': scn('').replace('\t195\t10000', '\t1_95\t10000', 1),
    'int_plus_sign': scn('').replace('\t195\t10000', '\t+195\t10000', 1), 'int_arabic_digits': scn('').replace('\t195\t10000', '\t١٩٥\t10000', 1), 'int_beyond_int64': scn(plugins() + risk('max_gross_units', 10 ** 25) + tick(0)),
    'side_wraps_32_bit': scn('').replace('\t-1\t195\t10000', '\t4294967297\t195\t10000', 1), 'crlf_line_endings': scn(plugins() + tick(0)).replace('\n', '\r\n'), 'form_feed_line': scn(plugins() + tick(0)) + '\x0c\n',
    'huge_validator_cooldown': scn(plugins() + risk('reentry_min_cooldown_s', BIG) + tick(0)), 'huge_plugin_cooldown': scn(plugins() + cfg('basket_reentry', 'cooldown_s', BIG) + tick(0)), 'huge_max_wait': scn(plugins() + cfg('basket_reentry', 'max_wait_s', BIG) + tick(0)),
    'huge_trigger_bp': scn(plugins() + cfg('basket_cut', 'trigger_bp', BIG) + tick(0)), 'huge_mark': scn(mark(0, SCE, 10 ** 15) + tick(0)), 'huge_quantity': scn('').replace('\t195\t10000', f'\t{10 ** 12}\t10000', 1),
    'instrument_5_parts': scn('').replace('NIFTY|2026-01-08|CE|24000', 'NIFTY|2026-01-08|CE|24000|X'), 'strike_suffix': scn('').replace('NIFTY|2026-01-08|CE|24000', 'NIFTY|2026-01-08|CE|24000abc'), 'bad_expiry_month': scn('').replace('2026-01-08|CE|24000', '2026-13-08|CE|24000'),
    'option_type_XX': scn('').replace('2026-01-08|CE|24000', '2026-01-08|XX|24000'), 'lot_zero': scn('').replace(f'INST\t{SCE}\t65', f'INST\t{SCE}\t0'), 'lot_negative': scn('').replace(f'INST\t{SCE}\t65', f'INST\t{SCE}\t-65'),
    'negative_timestamp': scn(plugins() + L('MARK', -100, SCE, 10000) + tick(0)), 'negative_tick': scn(plugins() + L('TICK', -1)),
    'evidence_overridden_by_second_meta': scn(L('META', 'evidence', 'REAL'), 'SYNTHETIC_TEST_ONLY'), 'repeated_config': scn(plugins() + cfg('basket_cut', 'units', 65) + cfg('basket_cut', 'units', 130)), 'repeated_instrument': scn(L('INST', SCE, 65)),
    'repeated_risk': scn(risk('max_gross_units', 1) + risk('max_gross_units', 2)), 'config_for_unlisted_plugin': scn(cfg('basket_cut', 'units', 65)), 'action_not_at_a_tick': scn(plugins() + tick(0) + action(7, 'a', 'CUT', 'SCE', 65)),
    'engine_reserved_fill_id': scn('').replace('\tf1\t', '\tPC000001\t', 1), 'pipe_in_basket_id': scn('').replace('\tB1\t', '\tA|B\t'), 'seed_price_not_a_tick': scn('').replace('\t195\t10000', '\t195\t10003', 1),
    'mark_price_not_a_tick': scn(mark(0, SCE, 10003) + tick(0)), 'tab_only_line': scn('') + '\t\n', 'space_only_line': scn('') + '   \n', 'unknown_line_type': scn('BOGUS\t1\n'), 'plugin_enabled_flag_2': scn(L('PLUGIN', 'basket_cut', '1.0.0', 2)),
}


@pytest.mark.parametrize('name', list(BAD))
def test_python_refuses_every_malformed_scenario(name):
    with pytest.raises(Exception): run(BAD[name])


def test_non_ascii_and_invalid_utf8_files_are_refused(tmp_path):
    p = tmp_path / 'u.scn'; p.write_bytes(scn(plugins() + tick(0)).encode() + b'\xff\xfe\n')
    with pytest.raises(ScenarioError): Scenario.load(str(p))


# ------------------------------------------------------------------ fill price when no mark exists
def test_a_fill_without_a_mark_uses_the_legs_last_actual_price_and_replays_in_m2(tmp_path):
    text = scn('').replace(L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 195, 10000, T0), L('LEG', 'f1', 'B1', 'SCE', SCE, -1, 65, 10000, T0) + L('LEG', 'f1b', 'B1', 'SCE', SCE, -1, 130, 10050, T0))
    sim, f = run(text + plugins(False, False, True) + tick(0) + action(0, 'c', 'CUT', 'SCE', 65))                          # VWAP entry = 10033 (not a tick), no mark at all
    assert sim.book.leg('B1', 'SCE').entry_price == 10033 and acts(f)[0]['fill_price_paise'] == '10050'
    (tmp_path / 'e.tsv').write_text(f['events.tsv']); (tmp_path / 'i.tsv').write_text(f['instruments.tsv']); ins = m2_tsvio.read_instruments(str(tmp_path / 'i.tsv'))
    m2_replay.replay(m2_tsvio.read_events(str(tmp_path / 'e.tsv'), ins), ins, 'SYNTHETIC_TEST', 'FIFO', 'src', 0, strict=True)       # the unchanged M2 reader accepts every price


# ------------------------------------------------------------------ id collisions
def test_two_outstanding_cuts_of_one_leg_get_distinct_reentry_ids():
    body = plugins(False, True, True) + cfg('basket_reentry', 'cooldown_s', 0) + mark(0, SCE, 10000) + tick(0) + tick(300) + action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'c2', 'CUT', 'SCE', 65)
    _, f = run(scn(body)); re = [a for a in acts(f) if a['type'] == 'REENTRY']
    # cut ids here are 'c1'/'c2' (scripted), the plugin cites them: both re-entries are proposed and both accepted
    assert len(re) == 2 and len({a['action_id'] for a in re}) == 2 and all(a['status'] == 'ACCEPTED' for a in re)
    assert [d['outcome'] for d in decs(f) if d['plugin'] == 'basket_reentry' and d['outcome'] == 'PROPOSED'] == ['PROPOSED', 'PROPOSED']


# ------------------------------------------------------------------ plugin isolation
def _spy(kind):
    class Spy(Plugin):
        name = 'spy'; version = '1.0.0'; out = []
        def evaluate(self, ctx):
            try:
                if kind == 'marks_future': Spy.out.append([px for e in ctx._marks._d.values() for px in e[1]])
                if kind == 'marks_mutate': ctx._marks._d['x'] = 1
                if kind == 'scripted_mutate': ctx.scripted[0].qty = 999
                if kind == 'ctx_mutate': ctx.baskets = ()
                if kind == 'lots_mutate': ctx._lots['x'] = 1
            except Exception as e: Spy.out.append(type(e).__name__)
            return PluginResult()
    return Spy


def test_plugins_cannot_reach_future_marks_or_change_engine_state_through_the_context():
    pre = L('PLUGIN', 'spy', '1.0.0', 1) + mark(0, SCE, 10000) + mark(300, SCE, 7775) + tick(0) + tick(300)
    Spy = _spy('marks_future'); run(scn(pre), extra={'spy': Spy}); assert Spy.out == [[10000], [10000, 7775]]               # the t=0 context does not even contain the later mark
    for kind, err in (('marks_mutate', 'TypeError'), ('ctx_mutate', 'AttributeError'), ('lots_mutate', 'TypeError')):
        Spy = _spy(kind); run(scn(pre), extra={'spy': Spy}); assert set(Spy.out) == {err}, kind
    Spy = _spy('scripted_mutate'); sim, f = run(scn(pre + action(0, 'a', 'CUT', 'SCE', 65)), extra={'spy': Spy}); assert 'FrozenInstanceError' in set(Spy.out) and sim.sc.actions[0]['qty'] == 65


def _bad(result_factory):
    class Bad(Plugin):
        name = 'bad'; version = '1.0.0'
        def evaluate(self, ctx): return result_factory(self, ctx)
    return Bad


@pytest.mark.parametrize('label,factory', [
    ('float quantity', lambda s, c: PluginResult(OK, [ProposedAction('x', s.name, s.version, 'CUT', '', 'B1', 'SCE', 65.0, '', c.ts, c.ts, 'r')], [])),
    ('bool quantity', lambda s, c: PluginResult(OK, [ProposedAction('x', s.name, s.version, 'CUT', '', 'B1', 'SCE', True, '', c.ts, c.ts, 'r')], [])),
    ('newline in a decision detail', lambda s, c: PluginResult('NO_ACTION', [], [Decision(c.ts, s.name, s.version, 'B1', 'SCE', 'NOT_PROPOSED', 'X', 'a\n\tb', c.ts)])),
    ('non-ASCII text', lambda s, c: PluginResult('NO_ACTION', [], [Decision(c.ts, s.name, s.version, 'B1', 'SCE', 'NOT_PROPOSED', 'X', 'café', c.ts)])),
    ('decision stamped with later information', lambda s, c: PluginResult('NO_ACTION', [], [Decision(c.ts, s.name, s.version, 'B1', 'SCE', 'NOT_PROPOSED', 'X', 'd', c.ts + 1)])),
    ('decision claiming another plugin', lambda s, c: PluginResult('NO_ACTION', [], [Decision(c.ts, 'basket_cut', s.version, 'B1', 'SCE', 'NOT_PROPOSED', 'X', 'd', c.ts)])),
    ('wrong decision timestamp', lambda s, c: PluginResult('NO_ACTION', [], [Decision(c.ts - 1, s.name, s.version, 'B1', 'SCE', 'NOT_PROPOSED', 'X', 'd', c.ts - 1)])),
    ('not a PluginResult', lambda s, c: {'actions': []}),
    ('unknown status', lambda s, c: PluginResult('MAYBE', [], []))])
def test_invalid_plugin_output_is_dropped_and_logged_as_a_plugin_error(label, factory):
    sim, f = run(scn(L('PLUGIN', 'bad', '1.0.0', 1) + mark(0, SCE, 10000) + tick(0)), extra={'bad': _bad(factory)}); d = decs(f)
    assert len(d) == 1 and d[0]['reason'] == 'PLUGIN_ERROR' and kv(f, 'plugin_errors') == '1' and kv(f, 'fills_total') == '4', label
    for t in f.values(): assert t.count('\n') == len([l for l in t.split('\n') if l]), label            # no stray line breaks reached any output file


# ------------------------------------------------------------------ boundary behaviour (weak spots found by mutation of the first version)
def _cuts(side_legs, mark_px, trig=2000):
    body = plugins(True, False, False) + cfg('basket_cut', 'trigger_bp', trig) + cfg('basket_cut', 'leg_side_filter', side_legs) + cfg('basket_cut', 'units', 65) + mark(0, WCE, 200) + mark(0, SCE, 10000) + mark(300, WCE, mark_px) + tick(0) + tick(300)
    return len(acts(run(scn(body))[1]))


def test_long_leg_trigger_boundary():
    text = scn('').replace(L('LEG', 'f3', 'B1', 'WCE', WCE, 1, 195, 200, T0), L('LEG', 'f3', 'B1', 'WCE', WCE, 1, 195, 10000, T0))
    def n(px): return len(acts(run(text + plugins(True, False, False) + cfg('basket_cut', 'trigger_bp', 2000) + cfg('basket_cut', 'leg_side_filter', 'LONG') + cfg('basket_cut', 'option_type_filter', 'CE') + mark(0, WCE, 10000) + mark(300, WCE, px) + tick(0) + tick(300))[1]))
    assert (n(8005), n(8000), n(7995)) == (0, 1, 1)                                                  # long entry 10000: triggers at mark <= 8000 (inclusive)


def test_max_wait_window_boundary_is_inclusive():
    def reentries(wait): return [a for a in acts(run(scn(example_body(cfg('basket_reentry', 'cooldown_s', 300) + cfg('basket_reentry', 'price_condition', 'NONE') + cfg('basket_reentry', 'max_wait_s', wait))))[1]) if a['type'] == 'REENTRY']
    assert len(reentries(600)) == 1 and reentries(600)[0]['ts'] == str(T0 + 900)                      # cut at +600, first eligible tick +900 = cut + 300 <= wait 600
    assert len(reentries(299)) == 0 and len(reentries(300)) == 1                                       # exactly cut + max_wait is still inside the window


@pytest.mark.parametrize('bp,qty', [(1666, 0), (1667, 65), (5000, 130), (8333, 130), (8334, 195), (10000, 195)])
def test_fraction_rounds_to_the_nearest_lot_half_up(bp, qty):
    body = plugins(True, False, False) + cfg('basket_cut', 'policy', 'SCHEDULED') + cfg('basket_cut', 'qty_mode', 'FRACTION_BP') + cfg('basket_cut', 'fraction_bp', bp) + cfg('basket_cut', 'leg_side_filter', 'SHORT') + cfg('basket_cut', 'option_type_filter', 'CE') + tick(0)
    _, f = run(scn(body)); got = [int(a['qty']) for a in acts(f)]
    assert got == ([qty] if qty else []) and (qty or 'CUT_QTY_ZERO' in {d['reason'] for d in decs(f)})


def test_basket_filter_limits_both_plugins_to_one_basket():
    two = scn('') + L('LEG', 'g1', 'B2', 'SCE', SCE, -1, 130, 10000, T0)
    body = plugins() + cfg('basket_cut', 'policy', 'SCHEDULED') + cfg('basket_cut', 'basket_filter', 'B2') + cfg('basket_cut', 'leg_side_filter', 'SHORT') + cfg('basket_cut', 'option_type_filter', 'CE') + cfg('basket_cut', 'units', 65) + cfg('basket_reentry', 'basket_filter', 'B2') + cfg('basket_reentry', 'cooldown_s', 0) + mark(0, SCE, 10000) + tick(0) + tick(300)
    _, f = run(two + body); a = acts(f); assert [(x['basket_id'], x['type']) for x in a] == [('B2', 'CUT'), ('B2', 'REENTRY')]
    body2 = body.replace(cfg('basket_cut', 'basket_filter', 'B2'), '') + action(0, 'manual-cut-b1', 'CUT', 'SCE', 65)
    _, f = run(two + body2.replace(cfg('basket_reentry', 'basket_filter', 'B2'), cfg('basket_reentry', 'basket_filter', 'B1'))); assert not [x for x in acts(f) if x['type'] == 'REENTRY' and x['basket_id'] == 'B2']


def test_decision_info_ts_records_the_newest_data_actually_used():
    _, f = run(scn(example_body())); d = decs(f)
    nt = [x for x in d if x['reason'] == 'NO_TRIGGER' and x['ts'] == str(T0 + 300)][0]; assert nt['info_ts'] == str(T0 + 300)                       # the mark at +300 was the newest data used
    body = plugins(True, False, False) + cfg('basket_cut', 'scope', 'BASKET') + cfg('basket_cut', 'trigger_bp', 2000) + cfg('basket_cut', 'units', 65) + mark(0, SPE, 9000) + mark(0, WCE, 200) + mark(0, WPE, 250) + mark(100, SCE, 12500) + mark(0, SCE, 10000) + tick(0) + tick(300)
    _, f = run(scn(body)); a = acts(f); assert {x['info_ts'] for x in a} == {str(T0 + 100)} and len(a) == 4                       # basket scope: every action carries the newest mark that triggered it


def test_cut_of_a_fully_cut_basket_is_an_invalid_basket_state_not_just_missing_inventory():
    pre = plugins(False, False, True) + mark(0, SCE, 10000) + tick(0)
    full = ''.join(action(0, f'c{k}', 'CUT', leg, 195) for k, leg in enumerate(('SCE', 'SPE', 'WCE', 'WPE')))
    _, f = run(scn(pre + full + action(0, 'zz-again', 'CUT', 'SCE', 65))); assert acts(f)[-1]['reason'] == 'INVALID_BASKET_STATE'


# ------------------------------------------------------------------ look-ahead through every kind of input (not only marks)
@pytest.mark.parametrize('name', ['s05_reentry_success', 's08_overlapping_baskets', 's11_basket_lifecycle_demo', 's10_random_stress_seed1', 's10_random_stress_seed42'])
def test_appending_future_seeds_ticks_actions_and_config_free_data_changes_nothing_earlier(name):
    sc = G.all_scenarios()[name]; last = max(sc.ticks); base = run(sc.to_text())[1]; alt = Scenario.parse(sc.to_text())
    alt.seeds.append(dict(fill_id='late-1', basket_id='LATE', leg_id='X', instrument_id=sorted(alt.instruments)[0], side=-1, qty=65, price=5000, ts=last + 5000)); alt.ticks.append(last + 6000)
    alt.marks.append((last + 5500, sorted(alt.instruments)[0], 99995)); alt.actions.append(dict(ts=last + 6000, action_id='late-act', plugin='', version='', type='CUT', basket_id='LATE', leg_id='X', qty=65, parent_cut_id='', info_ts=last + 6000, group_id=''))
    f2 = run(alt.to_text())[1]
    for key in ('decisions.tsv', 'actions.tsv', 'states.tsv'):
        early = lambda f: [r for r in table(f[key]) if int(r['ts']) <= last]
        assert early(base) == early(f2) and early(base), key
    for key in ('lineage.tsv', 'events.tsv'):                      # no ts column in lineage: the earlier rows must be an unchanged prefix
        a, b = table(base[key]), table(f2[key]); assert b[:len(a)] == a, key


# ------------------------------------------------------------------ disclosed limitation, pinned so it cannot change silently
def test_opposite_baskets_on_one_instrument_net_in_the_single_ledger():
    two = scn('') + L('LEG', 'g1', 'B2', 'SCE', SCE, 1, 195, 9000, T0 + 1) + plugins() + tick(0) + tick(1)
    sim, f = run(two)
    assert sim.ledger.signed_inventory(SCE) == 0 and sim.ledger.realized_total() == 195 * 1000                  # the long 195@9000 closes the short 195@10000 inside the M2 ledger (its role rule)
    assert [(r['leg_id'], r['qty_after']) for r in table(f['states.tsv']) if r['basket_id'] == 'B2'][-1] == ('SCE', '195')    # ... while both baskets still hold their own claims
