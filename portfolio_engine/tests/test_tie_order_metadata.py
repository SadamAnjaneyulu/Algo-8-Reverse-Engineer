"""R1 metadata and preservation tests: the convention identifier is stamped into every delivered manifest and run manifest; ONLY metadata changed; no delivered data value changed.
Expected hashes come from reports/m2f_audit/r1/baseline_sha256_before_R1.json (taken at 562d7eb6, before any R1 change), not from the code under test."""
import ast, hashlib, json, os
import pytest
from conftest import PE, REPO
from pe import tie_policy as tp

BASE = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1', 'baseline_sha256_before_R1.json')))['sha256']
MANIFESTS = ['portfolio_engine/reports/m2c_data/manifest.json', 'portfolio_engine/reports/m2d_data/manifest.json', 'portfolio_engine/reports/m2e_data/NIFTY_2026-06-30/manifest.json', 'portfolio_engine/reports/m2e_data/SENSEX_2026-07-16/manifest.json']
sha = lambda p: hashlib.sha256(open(os.path.join(REPO, p), 'rb').read()).hexdigest()
ALLOWED_TO_CHANGE = lambda p: p.startswith(('portfolio_engine/python/', 'portfolio_engine/tests/', 'portfolio_engine/tools/', 'portfolio_engine/reports/m2f_audit/')) or p.endswith('.md') or p in MANIFESTS or p.startswith('portfolio_engine/IMPLEMENTATION')
PRESERVED = [p for p in BASE if not ALLOWED_TO_CHANGE(p)]          # INVERSE rule: every baseline file that is not explicitly allowed to change must be byte-identical (covers data, figures, summaries, fixtures, parity reports, tp_reconstruction, raw csv)


def test_convention_metadata_constant_states_the_limitation():
    m = tp.CONVENTION_METADATA
    assert m['id'] == 'SOURCE_ROW_ORDER_CONVENTION' and m['engine_policy'] == 'src' and m['verified_intra_second_chronology'] is False and 'not verified execution chronology' in m['statement']


@pytest.mark.parametrize('path', MANIFESTS)
def test_delivered_manifest_carries_convention_and_nothing_else_changed(path):
    obj = json.load(open(os.path.join(REPO, path))); assert obj['tie_order_convention'] == tp.CONVENTION_METADATA and list(obj)[-1] == 'tie_order_convention'
    orig = dict(obj); del orig['tie_order_convention']
    assert hashlib.sha256(json.dumps(orig, indent=1).encode()).hexdigest() == BASE[path]            # removing the new key reproduces the baseline bytes exactly


def test_no_delivered_data_value_changed_since_the_r1_baseline():
    changed = [p for p in PRESERVED if p not in MANIFESTS and (not os.path.exists(os.path.join(REPO, p)) or sha(p) != BASE[p])]
    assert len(PRESERVED) >= 400 and not changed, changed[:5]                                         # every dataset, summary, figure, CSV, fixture, tp_reconstruction file and the raw csv is byte-identical


def test_raw_csv_hash_unchanged():
    assert sha('Trades_GKOHNP140.csv') == BASE['Trades_GKOHNP140.csv'] and sha('Trades_GKOHNP140.csv').startswith('86e65ab6ece4')


@pytest.mark.parametrize('tool', ['m2c_closing_batches.py', 'm2d_wing_body.py', 'm2e_build.py'])
def test_delivered_output_builders_assert_primary_and_stamp_metadata(tool):
    tree = ast.parse(open(os.path.join(PE, 'tools', tool)).read()); calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    guards = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == 'require_primary']
    assert guards and all(isinstance(c.args[0], ast.Attribute) and c.args[0].attr == 'tie' for c in guards)          # the guard inspects the policy the LineageSet actually used (ls.tie), not a constant
    assert any(k.arg == 'tie_order_convention' and isinstance(k.value, ast.Attribute) and k.value.attr == 'CONVENTION_METADATA' for c in calls for k in c.keywords)


def test_run_manifest_states_the_convention(tmp_path):
    from pe.generators import synthetic as S
    from pe import tsvio, replay as rp, provenance
    ins, fills = S.open_close_full(); ev = str(tmp_path / 'e.tsv'); ip = str(tmp_path / 'i.tsv'); tsvio.write_events(ev, fills, 'x'); tsvio.write_instruments(ip, ins, 'x')
    for tie, want in (('src', 'SOURCE_ROW_ORDER_CONVENTION'), ('source_row', 'SOURCE_ROW_ORDER_CONVENTION'), ('buys_first', 'SENSITIVITY_ONLY:buys_first')):
        res = rp.replay(fills, ins, 'SYNTHETIC_TEST', 'FIFO', tie); cfg = dict(mode='SYNTHETIC_TEST', method='FIFO', tie_order=tie, snapshot_interval=0)
        m = provenance.manifest(res, events_path=ev, instruments_path=ip, config=cfg, implementation='python', reproduce='x'); assert m['tie_order_convention'] == want and m['config']['tie_order'] == tie


def test_sensitivity_report_is_the_independent_reference_result():
    """reports/r1_tie_order (production pipeline) must equal the independent references (M2-F reference run and the R1 reviewer's lot-attribution run; raw csv, no pe imports) on every compared quantity. It compares two committed JSON files: it does not re-run either pipeline (the slow real-ledger tests do)."""
    prod = json.load(open(os.path.join(PE, 'reports', 'r1_tie_order', 'r1_tie_order_sensitivity.json')))['policies']; ind = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1', 'independent_tie_sensitivity_result.json')))
    names = {'sells_first': 'sells_first', 'buys_first': 'buys_first', 'trade_id': 'trade_id_asc', 'order_no': 'order_no_asc'}
    for pol, iname in names.items():
        p, i = prod[pol], ind[iname]
        assert p['2_groups_changing_open_close_allocation']['fills_changed'] == i['accounting']['FIFO']['fills_open_close_split_changed'] and p['3_episode_identity']['episodes_changed'] == i['accounting']['FIFO']['episodes_identity_changed']
        assert p['3_episode_identity']['instruments_changed'] == i['accounting']['FIFO']['instruments_changed'] and p['3_episode_identity']['instruments'] == i['accounting']['FIFO']['_instruments']
        assert p['2_groups_changing_open_close_allocation']['fill_rows'] == i['accounting']['FIFO']['_split_rows']
        for k, v in p['4_closing_batch_membership'].items(): assert v['baseline_batches_not_in_alternative'] == i['batches'][k]['baseline_batches_not_in_alternative']
        for m_ in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3'): assert p['5_wing_body_membership']['links_changed'][m_] == i['wing_body']['links_changed'][m_]
        assert p['5_wing_body_membership']['opening_body_units'] == i['wing_body']['headline']['opening_body_units'] and p['invariants']['final_inventory_equal'] and p['invariants']['opening_units_equal']
    att = json.load(open(os.path.join(PE, 'reports', 'm2f_audit', 'r1_review', 'a_attribution_result.json')))      # the reviewer's own implementation (raw csv, no pe imports)
    for pol, rname in (('sells_first', 'sells_first'), ('buys_first', 'buys_first'), ('trade_id', 'trade_id'), ('order_no', 'order_no'), ('sensex_trade_id_time', 'sensex_ns')):
        for m_ in ('FIFO', 'LIFO'): assert prod[pol]['6_lot_attribution'][m_]['closing_fills_with_changed_consumption_sequence'] == att[f'{m_}|{rname}']['closing_fills_with_different_source_lots'], (pol, m_)
    s = prod['sensex_trade_id_time']; assert s['2_groups_changing_open_close_allocation']['fills_changed'] == 0 and s['3_episode_identity']['episodes_changed'] == 0 and all(v['baseline_batches_not_in_alternative'] == 0 for v in s['4_closing_batch_membership'].values())
    assert all(n == 0 for n in s['5_wing_body_membership']['links_changed'].values()) and s['5_wing_body_membership']['items_only_in_one'] == 0
