"""R1 tests: intra-second tie-order policies. SOURCE_ROW_ORDER_CONVENTION is the primary deterministic convention (NOT verified execution chronology); every other policy is sensitivity-only.
Expected values are hand-calculated (synthetic) or pinned from the INDEPENDENT M2-F reference run on the raw csv (reports/m2f_audit/r1 + track_a/b/c; no pe imports), never produced by the code under test."""
import dataclasses as dc, os
import pytest
from conftest import PE, REPO
from pe import tie_policy as tp, replay as rp
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators.synthetic import Builder
M = 'SYNTHETIC_TEST'


def splits(ls):
    """fill_id -> (closing units, opening units) from the observed layer"""
    out = {}
    for r in ls.oa.values(): out.setdefault(r[2], [0, 0])[1] += r[8]
    for r in ls.cp.values(): out.setdefault(r[2], [0, 0])[0] += r[8]
    return {k: tuple(v) for k, v in out.items()}


def flip_same_side():
    """long 260; then, in ONE second, two SELLS (390 then 195 in source order). Position crosses zero inside the second although both fills are same-side."""
    b = Builder('flip'); i = b.add_inst(); b.fill(i, 0, 1, 260, 10000, parent='buy'); b.fill(i, 100, -1, 390, 10000, parent='s390'); b.fill(i, 100, -1, 195, 10000, parent='s195'); return b.out()


def mixed_side():
    """long 130; then, in ONE second, BUY 65 then SELL 195 (source order)."""
    b = Builder('mixed'); i = b.add_inst(); b.fill(i, 0, 1, 130, 10000, parent='b130'); b.fill(i, 100, 1, 65, 10000, parent='b65'); b.fill(i, 100, -1, 195, 10000, parent='s195'); return b.out()


def keyed(fills, keys, policy='trade_id'): return [dc.replace(f, tie_key=(policy,) + k) for f, k in zip(fills, keys)]          # keys are LABELLED with their policy (pe.tie_policy.tie_key)


# ------------------------------------------------------------------------------------------------------------- registry, default and guards
def test_default_convention_is_source_row_order():
    assert tp.SOURCE_ROW_ORDER_CONVENTION == 'SOURCE_ROW_ORDER_CONVENTION' and tp.PRIMARY_POLICY == 'source_row'
    assert tp.convention_id('src') == tp.convention_id('source_row') == 'SOURCE_ROW_ORDER_CONVENTION' and tp.engine_order('source_row') == tp.engine_order('src') == 'src'
    import inspect
    assert inspect.signature(rp.replay).parameters['tie_order'].default == 'src' and inspect.signature(LineageSet.__init__).parameters['tie_order'].default == 'src'
    ins, fills = flip_same_side(); ls = LineageSet(fills, ins, M); assert ls.tie == 'src' and ls.convention == 'SOURCE_ROW_ORDER_CONVENTION'


def test_policy_registry_is_exactly_the_approved_set_and_only_source_row_is_primary():
    assert set(tp.POLICIES) == {'source_row', 'sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_trade_id_time'}
    assert [n for n, p in tp.POLICIES.items() if p.primary] == ['source_row'] and all(tp.POLICIES[n].sensitivity_only for n in tp.POLICIES if n != 'source_row')
    assert {n for n, p in tp.POLICIES.items() if p.cpp_supported} == {'source_row', 'sells_first', 'buys_first'} and set(tp.KEYED) == {'trade_id', 'order_no', 'sensex_trade_id_time'}
    assert set(TIE_ORDERS) == {'src', 'sells_first', 'buys_first'} and set(KEYED_TIE_ORDERS) == set(tp.KEYED)         # the C++-parity list is unchanged; new policies are Python-only
    for n in tp.POLICIES:
        if n != 'source_row': assert tp.convention_id(n) == 'SENSITIVITY_ONLY:' + n != tp.SOURCE_ROW_ORDER_CONVENTION


def test_sensitivity_policy_cannot_silently_replace_the_primary_convention():
    assert tp.require_primary('src') == 'SOURCE_ROW_ORDER_CONVENTION' and tp.require_primary('source_row') == 'SOURCE_ROW_ORDER_CONVENTION'
    for n in ('sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_trade_id_time'):
        with pytest.raises(EngineError, match='must use SOURCE_ROW_ORDER_CONVENTION'): tp.require_primary(n, 'delivered output')
    ins, fills = flip_same_side(); ls = LineageSet(fills, ins, M, 'sells_first'); assert ls.convention == 'SENSITIVITY_ONLY:sells_first'
    with pytest.raises(EngineError): tp.require_primary(ls.tie)
    with pytest.raises(EngineError, match='unknown tie-order policy'): tp.resolve('latest_first')


def test_source_row_alias_is_byte_identical_to_legacy_src():
    ins, fills = flip_same_side(); a = LineageSet(fills, ins, M, 'src'); b = LineageSet(fills, ins, M, 'source_row')
    assert a.files == b.files and rp.replay(fills, ins, M, 'FIFO', 'src').dump == rp.replay(fills, ins, M, 'FIFO', 'source_row').dump
    assert 'source_row' not in rp.replay(fills, ins, M, 'FIFO', 'source_row').dump                       # the dump keeps the legacy token


# ------------------------------------------------------------------------------------------------------------- hand-calculated behaviour of every policy
def test_primary_split_in_same_side_position_flip():
    ins, fills = flip_same_side(); s = splits(LineageSet(fills, ins, M, 'source_row'))
    # source order: S390 closes the 260 long and opens 130 short; S195 opens 195 short
    assert s['S000002'] == (260, 130) and s['S000003'] == (0, 195) and s['S000001'] == (0, 260)


@pytest.mark.parametrize('policy,keys', [('trade_id', [(1,), (9,), (5,)]), ('order_no', [(1,), (9,), (5,)])])
def test_keyed_policies_reorder_a_same_side_flip(policy, keys):
    ins, fills = flip_same_side(); ls = LineageSet(keyed(fills, keys, policy), ins, M, policy); s = splits(ls)
    # key says S195 (5) precedes S390 (9): S195 closes 195 (65 long left); S390 closes 65 and opens 325
    assert s['S000003'] == (195, 0) and s['S000002'] == (65, 325) and ls.convention == 'SENSITIVITY_ONLY:' + policy
    base = LineageSet(fills, ins, M, 'source_row')
    for L in (ls, base): assert (sum(r[8] for r in L.oa.values()), sum(r[8] for r in L.cp.values())) == (585, 260)          # opened / closed units are invariant (260 + 325 opened, 260 closed)


def test_sells_first_and_buys_first_hand_calculated():
    ins, fills = mixed_side()
    src = splits(LineageSet(fills, ins, M, 'source_row')); bf = splits(LineageSet(fills, ins, M, 'buys_first')); sf = splits(LineageSet(fills, ins, M, 'sells_first'))
    assert src['S000002'] == (0, 65) and src['S000003'] == (195, 0) and bf == src                       # buys first == source order here
    assert sf['S000003'] == (130, 65) and sf['S000002'] == (65, 0)                                       # sells first: S195 closes 130, opens 65; B65 then closes 65


def test_keyed_policy_without_keys_is_rejected_and_primary_ignores_keys():
    ins, fills = flip_same_side()
    for n in tp.KEYED:
        with pytest.raises(EngineError, match='needs Fill.tie_key'): LineageSet(fills, ins, M, n)
    junk = keyed(fills, [(9,), (1,), (0,)], 'order_no'); assert LineageSet(junk, ins, M, 'source_row').files == LineageSet(fills, ins, M, 'source_row').files        # keys never affect the primary convention


def test_every_policy_preserves_aggregate_quantities_final_inventory():
    for builder in (flip_same_side, mixed_side):
        ins, fills = builder(); base = LineageSet(fills, ins, M, 'source_row'); keys = [(len(fills) - i,) for i in range(len(fills))]
        for n in tp.POLICIES:
            ls = LineageSet(keyed(fills, keys, n) if tp.POLICIES[n].keyed else fills, ins, M, tp.engine_order(n))
            net = lambda L: sum(r[8] for r in L.oa.values()) - sum(r[8] for r in L.cp.values())
            assert net(ls) == net(base), (builder.__name__, n)
            last = lambda L: {L.episodes[e[1]]['instrument_id']: e[8] for e in L.events}
            assert last(ls) == last(base), (builder.__name__, n)


# ------------------------------------------------------------------------------------------------------------- per-fill sensitivity keys (pure functions)
def test_key_functions():
    assert tp.trade_id_key('117849') == (117849, 0) and tp.trade_id_key('1782272760351084326-291130') == (1782272760351084326, 291130) and tp.order_no_key('1210048530') == (1210048530,)
    ns = 1782272760351084326                                               # fraction .351 -> epoch is the floor
    assert tp.sensex_time_key('SENSEX', f'{ns}-5', ns // 10**9) == (ns,)
    ns2 = 1782272760651084326                                              # fraction .651 -> epoch is floor+1 (round-half-up)
    assert tp.sensex_time_key('SENSEX', f'{ns2}-5', ns2 // 10**9 + 1) == (ns2,) and tp.sensex_time_key('SENSEX', f'{ns2}-5', ns2 // 10**9) == (1782272760 * 10**9,)
    assert tp.sensex_time_key('SENSEX', '1782986309637335907-15980320', 1782986253) == (1782986253 * 10**9,)      # the exceptional raw fill (row 8079): 56.6 s after its epoch -> NOT trusted
    assert tp.sensex_time_key('SENSEX', '12345', 1782986253) == (1782986253 * 10**9,) and tp.sensex_time_key('NIFTY', '1782272760351084326-5', 1782272760) == (0,)      # malformed / NIFTY never use the id time
    assert tp.tie_key('source_row', 'NIFTY', 'x', 'y', 1) is None


def test_attach_tie_keys_reads_raw_rows_and_leaves_primary_untouched():
    from pe.generators import historical as H
    ins, fills, _ = H.generate(REPO, cycle=('SENSEX', '2026-07-02'))
    assert H.attach_tie_keys(REPO, fills, 'source_row') == fills and all(f.tie_key is None for f in H.attach_tie_keys(REPO, fills, 'source_row'))
    exc = [f for f in H.attach_tie_keys(REPO, fills, 'sensex_trade_id_time') if f.source_row_id == 8079]; assert exc and exc[0].tie_key == ('sensex_trade_id_time', 1782986253 * 10**9)        # exceptional fill falls back to its epoch
    import csv
    raw = {i: r for i, r in enumerate(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), newline='')))}
    for pol, col, fn in (('trade_id', 28, tp.trade_id_key), ('order_no', 4, tp.order_no_key)):
        for f in H.attach_tie_keys(REPO, fills, pol)[:50]: assert f.tie_key == (pol,) + fn(raw[f.source_row_id][col])
    plain = H.attach_tie_keys(REPO, fills, 'sensex_trade_id_time'); ok = [f for f in plain if f.source_row_id != 8079]; assert all(len(f.tie_key) == 2 and f.tie_key[0] == 'sensex_trade_id_time' and f.tie_key[1] > 10**18 for f in ok)


# ------------------------------------------------------------------------------------------------------------- tests added after the independent R1 review (each targets a surviving mutant)
def test_keys_are_labelled_and_a_foreign_policy_key_is_rejected():                     # R1R-08
    ins, fills = flip_same_side(); wrong = keyed(fills, [(1,), (9,), (5,)], 'trade_id')
    with pytest.raises(EngineError, match='another policy'): LineageSet(wrong, ins, M, 'order_no')
    assert tp.tie_key('trade_id', 'NIFTY', '5', '7', 1)[0] == 'trade_id' and tp.tie_key('order_no', 'NIFTY', '5', '7', 1)[0] == 'order_no' and tp.tie_key('sensex_trade_id_time', 'NIFTY', '5', '7', 1)[0] == 'sensex_trade_id_time'


def test_keyed_order_is_timestamp_first_then_key_then_source_row():                 # R2M04, R2M06
    ins, fills = flip_same_side()
    early_big_key = keyed(fills, [(99,), (1,), (1,)])                                  # the earliest fill (second 0) has the LARGEST key: timestamp must still dominate
    assert [f.fill_id for f in rp.order_events(early_big_key, 'trade_id')][0] == 'S000001'
    tied = keyed(fills, [(5,), (7,), (7,)]); assert [f.fill_id for f in rp.order_events(tied, 'trade_id')] == ['S000001', 'S000002', 'S000003']               # equal keys fall back to source row
    two = [dc.replace(tied[1], source_row_id=50), dc.replace(tied[2], source_row_id=40)]; assert [f.source_row_id for f in rp.order_events(two, 'trade_id')] == [40, 50]


def test_partial_or_missing_keys_are_rejected_even_when_only_one_fill_lacks_one():   # R2M05
    ins, fills = flip_same_side(); part = keyed(fills, [(1,), (2,), (3,)]); part[1] = dc.replace(part[1], tie_key=None)
    with pytest.raises(EngineError, match='needs Fill.tie_key'): LineageSet(part, ins, M, 'trade_id')


def test_sensex_time_rounding_boundary_is_half_up_at_the_half_nanosecond():        # R2M02
    base = 1782272760 * 10**9
    assert tp.sensex_time_key('SENSEX', f'{base + 499_999_999}-1', 1782272760) == (base + 499_999_999,)                  # fraction just below .5 -> epoch is the floor
    assert tp.sensex_time_key('SENSEX', f'{base + 499_999_999}-1', 1782272761) == (1782272761 * 10**9,)                  # ... so epoch floor+1 is inconsistent -> fallback
    assert tp.sensex_time_key('SENSEX', f'{base + 500_000_000}-1', 1782272761) == (base + 500_000_000,)                  # fraction exactly .5 -> epoch is floor+1
    assert tp.sensex_time_key('SENSEX', f'{base + 500_000_000}-1', 1782272760) == (1782272760 * 10**9,)


def test_alias_table_is_exactly_the_legacy_token_and_order_events_accepts_the_alias():   # R2M14, R1R-09
    assert tp.ALIASES == {'src': 'source_row'}
    ins, fills = flip_same_side(); assert [f.fill_id for f in rp.order_events(fills, 'source_row')] == [f.fill_id for f in rp.order_events(fills, 'src')]


def test_primary_order_does_not_depend_on_input_order():                           # R2M15
    for builder in (flip_same_side, mixed_side):
        ins, fills = builder(); a = LineageSet(fills, ins, M, 'source_row'); b = LineageSet(list(reversed(fills)), ins, M, 'source_row'); assert a.files == b.files


def test_attach_tie_keys_refuses_a_raw_file_that_does_not_match_the_manifest(tmp_path):   # R2M07
    import json as _j
    from pe.generators import historical as H
    (tmp_path / 'tp_reconstruction' / 'data').mkdir(parents=True); (tmp_path / 'Trades_GKOHNP140.csv').write_text('x\n'); (tmp_path / 'tp_reconstruction' / 'data' / 'source_manifest.json').write_text(_j.dumps({'sha256': '0' * 64}))
    ins, fills = flip_same_side()
    with pytest.raises(EngineError, match='hash differs'): H.attach_tie_keys(str(tmp_path), fills, 'trade_id')


def test_cli_refuses_python_only_policies_for_the_cpp_core(tmp_path):              # R1R-09
    from pe import cli, tsvio
    ins, fills = flip_same_side(); ev = str(tmp_path / 'e.tsv'); ip = str(tmp_path / 'i.tsv'); tsvio.write_events(ev, fills, 'x'); tsvio.write_instruments(ip, ins, 'x')
    with pytest.raises(SystemExit, match='Python-only'): cli.main(['replay', '--events', ev, '--instruments', ip, '--mode', M, '--tie', 'trade_id', '--engine', 'cpp'])


def _raw_row_instrument(row):
    import csv, datetime as dt
    for i, r in enumerate(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), newline=''))):
        if i == row: return r[12], dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat()


def test_sensex_policy_orders_by_the_embedded_nanosecond_time_for_every_fill_of_a_cycle():   # R2M18
    from pe.generators import historical as H
    und, exp = _raw_row_instrument(2450); assert und == 'SENSEX'
    ins, fills, _ = H.generate(REPO, cycle=(und, exp)); keyed_fills = H.attach_tie_keys(REPO, fills, 'sensex_trade_id_time')
    import csv
    raw = {i: r for i, r in enumerate(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), newline='')))}
    for f in keyed_fills:                                                                       # independent expectation: parse the raw id; only row 8079 (if in the cycle) is exceptional
        ns = int(raw[f.source_row_id][28].split('-')[0]); expect = ns if (ns + 500_000_000) // 10**9 == f.timestamp_s else f.timestamp_s * 10**9
        assert f.tie_key == ('sensex_trade_id_time', expect), f.source_row_id
    order = [f.source_row_id for f in rp.order_events(keyed_fills, 'sensex_trade_id_time') if f.source_row_id in (2450, 2451, 2452)]
    assert order == [2450, 2452, 2451]                                                          # file order is 2450, 2451, 2452: the ns order differs (same-side group, no accounting effect)


# ------------------------------------------------------------------------------------------------------------- real ledger: exact affected rows, invariants, downstream sensitivities (slow)
BASE_BODY = (626765, 540250)
PINS = {   # independent reference (M2-F tracks A/B/C, raw csv, exact arithmetic); 0-based raw/source rows
    'sells_first': dict(instruments={'NIFTY|2026-10-13|PE|22400'}, rows=[39039, 39042], episodes=1, items_only=2, W1=1, W1_S60=2, W2=1, W2_S60=2, W3=0, batches=1, body=(626830, 540315)),
    'buys_first': dict(instruments={'NIFTY|2026-06-23|CE|24000', 'NIFTY|2026-10-13|PE|22400', 'NIFTY|2026-10-13|PE|22450', 'NIFTY|2026-10-19|CE|23000', 'SENSEX|2026-08-20|PE|76900'}, rows=[24730, 24732, 39038, 39041], episodes=12, items_only=4, W1=1, W1_S60=7, W2=1, W2_S60=7, W3=0, batches=2, body=(626680, 540165)),
    'trade_id': dict(instruments={'NIFTY|2026-09-01|CE|24600', 'NIFTY|2026-09-01|PE|23200'}, rows=[27911, 27912, 27916, 27917], episodes=4, items_only=2, W1=6, W1_S60=6, W2=6, W2_S60=6, W3=0, batches=1, body=(625985, 540250)),
    'sensex_trade_id_time': dict(instruments=set(), rows=[], episodes=0, items_only=0, W1=0, W1_S60=0, W2=0, W2_S60=0, W3=0, batches=0, body=BASE_BODY)}
PINS['order_no'] = PINS['trade_id']


def _episode_sigs(ls):
    rows = {}
    for r in ls.oa.values(): rows.setdefault(r[5], set()).add(r[11])
    return {eid: ((e['direction'], e['opened'], e['closed'], e['ended_by'], bool(e['started_by_reversal']), e['n_open_fills'], e['n_close_fills']), frozenset(rows.get(eid, ()))) for eid, e in ls.episodes.items()}


@pytest.fixture(scope='module')
def real():
    from pe.generators import historical as H
    from pe import closing_batches as cb, wing_body as wb
    ins, fills, _ = H.generate(REPO); cache = {}

    def run(policy):
        if policy in cache: return cache[policy]
        f2 = H.attach_tie_keys(REPO, fills, policy); ls = LineageSet(f2, ins, 'HISTORICAL_OBSERVED_REPLAY', tp.engine_order(policy))
        parents, _, _ = cb.closing_parents(ls); views = cb.all_views(parents)
        part = {k: frozenset(frozenset(m.parent_id for m in b['members']) for b in v['batches']) for k, v in views.items()}
        meta = {r['parent_order_id']: r for r in H.generate_parents(REPO, ls.roles)}; R = wb.analyse(ls, meta, 'TAGGED')
        sp = splits(ls); last = {}
        for e in ls.events: last[ls.episodes[e[1]]['instrument_id']] = e[8]
        body = lambda lv: sum(i.qty for i in R.items if i.level == lv and i.role == 'BODY')
        cache[policy] = dict(ls=ls, split=sp, sigs=_episode_sigs(ls), part=part, items={i.item_id for i in R.items}, links={m: {l['link_id'] for l in v} for m, v in R.links.items()}, final=last,
                             oa=sum(r[8] for r in ls.oa.values()), cp=sum(r[8] for r in ls.cp.values()), body=(body('OPENING'), body('CLOSING')))
        return cache[policy]
    return run


@pytest.mark.slow
@pytest.mark.parametrize('policy', ['sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_trade_id_time'])
def test_real_ledger_exact_affected_rows_invariants_and_downstream(real, policy):
    base, alt, pin = real('source_row'), real(policy), PINS[policy]
    assert base['ls'].convention == 'SOURCE_ROW_ORDER_CONVENTION' and alt['ls'].convention == 'SENSITIVITY_ONLY:' + policy
    assert (base['oa'], base['cp']) == (1414545, 1377065) == (alt['oa'], alt['cp']) and base['final'] == alt['final']                       # invariants: aggregate units and final inventory
    changed = sorted(int(k[1:]) for k in set(base['split']) | set(alt['split']) if base['split'].get(k) != alt['split'].get(k)); assert changed == pin['rows']        # exact fills whose open/close split changes
    ep = [e for e in set(base['sigs']) | set(alt['sigs']) if base['sigs'].get(e) != alt['sigs'].get(e)]
    assert len(ep) == pin['episodes'] and {e.rsplit('#', 1)[0] for e in ep} == pin['instruments']                                             # exact episodes / instruments
    for k, bset in base['part'].items(): assert len(bset - alt['part'][k]) == pin['batches'], k                                               # closing-batch membership (C1 and C2, all 5 thresholds)
    assert len(base['items'] ^ alt['items']) == pin['items_only'] and alt['body'] == pin['body']
    for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'): assert len(base['links'][m] ^ alt['links'][m]) == pin[m], m                              # wing/body link membership
