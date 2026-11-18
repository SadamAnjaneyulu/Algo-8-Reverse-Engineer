"""Hand-calculated tests of the cut and re-entry plugins and of the risk validation, Python side (the C++ side has the same cases in cpp/tests/test_pc.cpp)."""
import pytest
from helpers import *
from pc.contract import ConfigError


def acts(f): return table(f['actions.tsv'])
def decs(f): return table(f['decisions.tsv'])


def test_the_195_example_step_by_step():
    sim, f = run(scn(example_body()))
    a = acts(f); assert len(a) == 2
    assert (a[0]['status'], a[0]['qty'], a[0]['fill_side'], a[0]['fill_price_paise'], a[0]['ts']) == ('ACCEPTED', '65', '1', '12500', str(T0 + 600))           # buy 65 back at the mark
    assert (a[1]['type'], a[1]['status'], a[1]['parent_cut_id'], a[1]['fill_side'], a[1]['fill_price_paise'], a[1]['ts']) == ('REENTRY', 'ACCEPTED', CUTID, '-1', '11000', str(T0 + 1200))
    st = {(r['event_id'], r['leg_id']): r for r in table(f['states.tsv'])}
    c = st[('PC000001', 'SCE')]; assert (c['qty_before'], c['qty_after'], c['basket_status'], c['instrument_inventory'], c['gross_units'], c['short_units']) == ('195', '130', 'PARTIALLY_CUT', '-130', '715', '325')
    r = st[('PC000002', 'SCE')]; assert (r['qty_before'], r['qty_after'], r['basket_status'], r['instrument_inventory'], r['gross_units'], r['short_units']) == ('130', '195', 'ACTIVE', '-195', '780', '390')
    assert kv(f, 'final_realized_pnl_paise') == '-162500'                                          # (10000 - 12500) * 65 on the closed part
    assert [(d['ts'], d['reason']) for d in decs(f) if d['plugin'] == 'basket_reentry' and d['reason'] == 'COOLDOWN_ACTIVE'] == [(str(T0 + 600), 'COOLDOWN_ACTIVE'), (str(T0 + 900), 'COOLDOWN_ACTIVE')]
    lin = table(f['lineage.tsv'])[-1]; assert (lin['kind'], lin['parent_cut_id'], lin['origin_seed_fills']) == ('REENTRY', CUTID, 'f1')


def fr(extra): return plugins() + cfg('basket_cut', 'policy', 'SCHEDULED') + cfg('basket_cut', 'cut_at_ts', T0 + 300) + extra + tick(0) + tick(300)


def test_partial_basket_cut_rounds_to_lots():
    _, f = run(scn(fr(cfg('basket_cut', 'scope', 'BASKET') + cfg('basket_cut', 'qty_mode', 'FRACTION_BP') + cfg('basket_cut', 'fraction_bp', 3333))))           # 3 lots * 3333/10000 = 0.9999 -> 1 lot
    a = acts(f); assert len(a) == 4 and all(x['status'] == 'ACCEPTED' and x['qty'] == '65' and x['group_id'] == f'basket_cut|{T0 + 300}|B1' for x in a); assert kv(f, 'final_gross_units') == '520'


def test_full_basket_cut_reaches_fully_cut():
    _, f = run(scn(fr(cfg('basket_cut', 'scope', 'BASKET') + cfg('basket_cut', 'fraction_bp', 10000) + cfg('basket_cut', 'qty_mode', 'FRACTION_BP')))); assert kv(f, 'final_gross_units') == '0' and table(f['states.tsv'])[-1]['basket_status'] == 'FULLY_CUT'


def test_individual_side_aware_and_quantity_cuts():
    _, f = run(scn(fr(cfg('basket_cut', 'leg_side_filter', 'SHORT') + cfg('basket_cut', 'option_type_filter', 'PE') + cfg('basket_cut', 'units', 130))))
    a = acts(f); assert len(a) == 1 and (a[0]['leg_id'], a[0]['qty'], a[0]['fill_side']) == ('SPE', '130', '1') and kv(f, 'final_short_units') == '260'
    _, f = run(scn(fr(cfg('basket_cut', 'scope', 'BASKET') + cfg('basket_cut', 'leg_side_filter', 'LONG') + cfg('basket_cut', 'units', 65))))                    # long wings are SOLD to cut
    a = acts(f); assert [(x['leg_id'], x['fill_side']) for x in a] == [('WCE', '-1'), ('WPE', '-1')] and kv(f, 'final_short_units') == '390'


def test_clamp_and_atomic_group_rejection():
    _, f = run(scn(fr(cfg('basket_cut', 'scope', 'BASKET') + cfg('basket_cut', 'units', 260) + cfg('basket_cut', 'clamp_to_available', 1)))); a = acts(f); assert len(a) == 4 and a[0]['qty'] == '195' and a[0]['status'] == 'ACCEPTED'
    _, f = run(scn(fr(cfg('basket_cut', 'scope', 'BASKET') + cfg('basket_cut', 'units', 260))))
    a = acts(f); assert [x['reason'] for x in a] == ['INSUFFICIENT_INVENTORY', 'GROUP_REJECTED', 'GROUP_REJECTED', 'GROUP_REJECTED'] and kv(f, 'fills_total') == '4' and kv(f, 'final_gross_units') == '780'   # nothing executed


@pytest.mark.parametrize('re_cfg,expected', [
    (cfg('basket_reentry', 'cooldown_s', 3000), 'COOLDOWN_ACTIVE'),
    (cfg('basket_reentry', 'cooldown_s', 100) + cfg('basket_reentry', 'max_wait_s', 100) + cfg('basket_reentry', 'price_condition', 'NONE'), 'WINDOW_EXPIRED'),
    (cfg('basket_reentry', 'band_bp', 100), 'PRICE_CONDITION_NOT_MET'),
    (cfg('basket_reentry', 'max_reentry_fraction_bp', 0), 'REENTRY_LIMIT_REACHED'),
])
def test_reentry_rejection_reasons_from_the_plugin(re_cfg, expected):
    _, f = run(scn(example_body(re_cfg))); assert expected in {d['reason'] for d in decs(f) if d['plugin'] == 'basket_reentry'} and not any(a['type'] == 'REENTRY' for a in acts(f))


def test_reentry_units_mode_and_limit_per_cut():
    body = example_body(cfg('basket_reentry', 'qty_mode', 'UNITS') + cfg('basket_reentry', 'units', 65) + cfg('basket_reentry', 'max_reentries_per_cut', 2) + cfg('basket_cut', 'units', 130))
    _, f = run(scn(body)); a = [x for x in acts(f) if x['type'] == 'REENTRY']; assert [(x['ts'], x['qty']) for x in a] == [(str(T0 + 1200), '65'), (str(T0 + 1500), '65')]


@pytest.mark.parametrize('extra,rk,reason', [
    (action(0, 'a1', 'CUT', 'SCE', 260), '', 'INSUFFICIENT_INVENTORY'), (action(0, 'a1', 'CUT', 'SCE', 30), '', 'INVALID_QUANTITY'), (action(0, 'a1', 'CUT', 'NOPE', 65), '', 'MISSING_OR_INVALID_LEG'),
    (action(0, 'a1', 'CUT', 'SCE', 65, basket='BX'), '', 'INVALID_BASKET_STATE'), (action(0, 'a1', 'SWAP', 'SCE', 65), '', 'INVALID_ACTION_TYPE'), (action(0, 'a1', 'CUT', 'SCE', 130), risk('max_cut_qty_per_action', 65), 'QUANTITY_LIMIT_EXCEEDED'),
    (action(0, 'a1', 'REENTRY', 'SCE', 65, 'nonexistent'), '', 'INVALID_CUT_LINEAGE'), (action(0, 'a1', 'CUT', 'SCE', 65, '', 1), '', 'LOOKAHEAD_VIOLATION'), (action(0, 'a1', 'CUT', 'SCE', 65, '', 0, 'basket_cut'), '', 'PLUGIN_MISMATCH'),
    (action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'r1', 'REENTRY', 'SCE', 130, 'c1'), '', 'REENTRY_LIMIT_EXCEEDED'),
    (action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'r1', 'REENTRY', 'SCE', 65, 'c1'), risk('reentry_min_cooldown_s', 100), 'COOLDOWN_NOT_ELAPSED'),
    (action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'r1', 'REENTRY', 'SCE', 65, 'c1'), risk('max_short_units', 325), 'EXPOSURE_LIMIT_EXCEEDED'),
    (action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'c1', 'CUT', 'SCE', 65), '', 'DUPLICATE_ACTION_ID'),
])
def test_risk_validation_rejects_and_reports_the_reason(extra, rk, reason):
    _, f = run(scn(plugins(False, False, True) + rk + mark(0, SCE, 10000) + tick(0) + extra)); assert acts(f)[-1]['reason'] == reason and acts(f)[-1]['status'] == 'REJECTED'


def test_derisking_is_allowed_above_a_limit_and_wrong_basket_leg_pair_is_not_cross_charged():
    _, f = run(scn(plugins(False, False, True) + risk('max_short_units', 100) + mark(0, SCE, 10000) + tick(0) + action(0, 'c1', 'CUT', 'SCE', 65))); assert acts(f)[0]['status'] == 'ACCEPTED'


def test_many_small_reentries_cannot_exceed_the_cut():
    body = action(0, 'c1', 'CUT', 'SCE', 130) + ''.join(action(0, f'r{k}', 'REENTRY', 'SCE', 65, 'c1') for k in range(3))
    _, f = run(scn(plugins(False, False, True) + risk('max_short_units', 390) + mark(0, SCE, 10000) + tick(0) + body)); a = acts(f)
    assert [x['status'] for x in a] == ['ACCEPTED', 'ACCEPTED', 'ACCEPTED', 'REJECTED'] and a[3]['reason'] == 'REENTRY_LIMIT_EXCEEDED' and kv(f, 'final_short_units') == '390'


def test_plugin_config_validation():
    from pc.plugins import BasketCutPlugin
    with pytest.raises(ConfigError): BasketCutPlugin({'trigger_bp': -1})
    with pytest.raises(ConfigError): BasketCutPlugin({'policy': 'MAGIC'})
    with pytest.raises(ConfigError): BasketCutPlugin({'nope': 1})
    with pytest.raises(ConfigError): BasketCutPlugin({'fraction_bp': 10001})
    assert BasketCutPlugin({}).config['units'] == 65 and BasketCutPlugin({'units': '130'}).config['units'] == 130


# ---- boundary and group tests added after the first mutation run (survivors P09, P19, P21, P30)
def _trigger_cuts(px):
    body = plugins(True, False, False) + cfg('basket_cut', 'trigger_bp', 2000) + cfg('basket_cut', 'leg_side_filter', 'SHORT') + cfg('basket_cut', 'option_type_filter', 'CE') + mark(0, SCE, 10000) + mark(300, SCE, px) + tick(0) + tick(300)
    return len(acts(run(scn(body))[1]))


def test_cut_trigger_boundary_is_inclusive_at_exactly_plus_20_percent():
    assert (_trigger_cuts(11995), _trigger_cuts(12000), _trigger_cuts(12005)) == (0, 1, 1)            # entry 10000, trigger 2000 bp -> threshold 12000


def _reentries(px):
    text = scn(example_body()).replace(f'MARK\t{T0 + 1200}\t{SCE}\t11000\n', f'MARK\t{T0 + 1200}\t{SCE}\t{px}\n')
    return [a for a in acts(run(text)[1]) if a['type'] == 'REENTRY' and a['ts'] == str(T0 + 1200)]


def test_price_band_boundary_is_inclusive_at_exactly_the_band():
    assert (len(_reentries(10620)), len(_reentries(10625)), len(_reentries(14375)), len(_reentries(14380))) == (0, 1, 1, 0)      # cut price 12500, band 1500 bp = 1875 paise


def GA(aid, typ, leg, qty, parent='', group='grp'): return L('ACTION', T0, aid, '', '', typ, 'B1', leg, qty, parent, T0, group)


def test_actions_of_one_group_are_validated_against_each_other():
    pre = plugins(False, False, True) + mark(0, SCE, 10000) + tick(0)
    _, f = run(scn(pre + GA('g1', 'CUT', 'SCE', 130) + GA('g2', 'CUT', 'SCE', 130)))                       # each fits alone (195); together they do not
    assert [a['reason'] for a in acts(f)] == ['GROUP_REJECTED', 'INSUFFICIENT_INVENTORY'] and kv(f, 'fills_total') == '4'
    _, f = run(scn(pre + GA('g1', 'CUT', 'SCE', 65) + GA('g2', 'CUT', 'SPE', 65)))                          # a valid group executes completely
    assert [a['status'] for a in acts(f)] == ['ACCEPTED', 'ACCEPTED'] and kv(f, 'fills_total') == '6'


def test_reentry_is_limited_by_the_cut_it_cites_not_only_by_the_leg():
    pre = plugins(False, False, True) + mark(0, SCE, 10000) + tick(0)
    _, f = run(scn(pre + action(0, 'c1', 'CUT', 'SCE', 65) + action(0, 'c2', 'CUT', 'SCE', 65) + action(0, 'r1', 'REENTRY', 'SCE', 130, 'c1')))   # the leg could take 130 back, cut c1 only gave 65
    assert acts(f)[-1]['reason'] == 'REENTRY_LIMIT_EXCEEDED'
