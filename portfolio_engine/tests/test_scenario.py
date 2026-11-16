"""Scenario mechanism (R1-C / N2): sensitivity scenarios never write into the delivered directories; every non-delivered output states scenario_id, tie_order_convention, source_hash,
generator_version, execution_mode; the baseline scenario reproduces the delivered historical outputs byte for byte (slow test); intra-second state flags are hand-calculated."""
import collections, gzip, json, os, subprocess, sys
import pytest
from conftest import PE, REPO
from pe import scenario as SC, tie_policy as tp, forensics as F
from pe.schema import EngineError


def test_default_is_the_delivered_baseline():
    s = SC.from_argv(['tool.py'], PE)
    assert s.id == 'baseline' and s.baseline and s.delivered and s.policy == 'source_row' and s.tie == 'src' and s.reports('m2d_data') == os.path.join(PE, 'reports', 'm2d_data')
    assert s.manifest_extra({'raw': 'h'}, 'g') == {'tie_order_convention': tp.CONVENTION_METADATA}              # the delivered manifests keep exactly their existing key


def test_sensitivity_scenario_requires_an_out_root_and_refuses_delivered_directories(tmp_path):
    with pytest.raises(EngineError, match='needs --out-root'): SC.from_argv(['t', '--scenario=per_contract_id_sequence'], PE)
    for d in SC.DELIVERED_DIRS:
        with pytest.raises(EngineError, match='inside the delivered directory'): SC.from_argv(['t', '--scenario=per_contract_id_sequence', f'--out-root={os.path.join(PE, "reports", d, "x")}'], PE)
    s = SC.from_argv(['t', '--scenario=per_contract_id_sequence', f'--out-root={tmp_path}'], PE)
    assert not s.baseline and not s.delivered and s.tie == 'per_contract_id_sequence' and s.reports('m2e_data') == os.path.join(str(tmp_path), 'reports', 'm2e_data')
    with pytest.raises(EngineError, match='unknown tie-order policy'): SC.Scenario('latest_first', PE, str(tmp_path))


def test_non_delivered_manifest_states_scenario_convention_source_generator_and_mode(tmp_path):
    for sid, conv in (('baseline', 'SOURCE_ROW_ORDER_CONVENTION'), ('per_contract_id_sequence', 'SENSITIVITY_ONLY:per_contract_id_sequence')):
        s = SC.Scenario(sid, PE, str(tmp_path)); e = s.manifest_extra({'raw_trades_sha256': 'abc'}, 'tool')
        assert list(e)[0] == 'tie_order_convention' and e['tie_order_convention']['verified_intra_second_chronology'] is False
        sc = e['scenario']; assert sc['scenario_id'] == sid and sc['tie_order_convention'] == conv and sc['source_hash'] == {'raw_trades_sha256': 'abc'} and sc['generator_version'].startswith('tool@')
        assert sc['execution_mode'] == 'HISTORICAL_OBSERVED_REPLAY' and 'UNORDERED_WITHIN_SECOND' in sc['ordering_semantics'] and 'NOT chronology' in sc['ordering_semantics']


def test_intra_second_flags_hand_calculated():
    class Fx:
        def __init__(self, i, ts, inst): self.fill_id, self.source_row_id, self.timestamp_s, self.instrument_id = f'F{i}', i, ts, inst
    class Cy:
        def ordered_fills(self): return [Fx(1, 10, 'A'), Fx(2, 10, 'B'), Fx(3, 10, 'A'), Fx(4, 11, 'A'), Fx(5, 12, 'A'), Fx(6, 12, 'A')]
    h, rows = F.intra_second_flag_table(Cy())
    assert [r[5] for r in rows] == ['UNORDERED_WITHIN_SECOND', 'UNORDERED_WITHIN_SECOND', 'SECOND_END_ORDER_INVARIANT', 'SINGLE_FILL_SECOND', 'UNORDERED_WITHIN_SECOND', 'SECOND_END_ORDER_INVARIANT']
    assert [(r[3], r[4]) for r in rows] == [(3, 2), (3, 2), (3, 2), (1, 1), (2, 1), (2, 1)]


def _norm(path):
    b = open(path, 'rb').read()
    if path.endswith('.json'):
        drop = {'created_utc', 'generated_at_head', 'working_tree_dirty', 'scenario', 'reproduce', 'tie_order_convention'}
        strip = lambda x: {k: strip(v) for k, v in x.items() if k not in drop and k != 'inventory_series_intra_second_flags.tsv'} if isinstance(x, dict) else [strip(v) for v in x] if isinstance(x, list) else x
        return json.dumps(strip(json.loads(b)), sort_keys=True).encode()
    return b


@pytest.mark.slow
def test_baseline_scenario_reproduces_every_generated_delivered_output_byte_for_byte(tmp_path):
    out = tmp_path / 'control'
    p = subprocess.run([sys.executable, os.path.join(PE, 'tools', 'r1c_scenario_run.py'), '--scenario=baseline', f'--out-root={out}'], capture_output=True, text=True); assert p.returncode == 0, p.stderr[-800:]
    roots = ['reports/m2c_data', 'reports/m2c_figures', 'reports/m2d_data', 'reports/m2d_figures', 'reports/m2e_data', 'reports/m2e_figures']
    produced = {os.path.relpath(os.path.join(d, f), out) for r in roots for d, _, fs in os.walk(out / r) for f in fs} | {'reports/M2E_POSITION_CASE_STUDIES.md'}
    delivered = {os.path.relpath(os.path.join(d, f), PE) for r in roots for d, _, fs in os.walk(os.path.join(PE, r)) for f in fs} | {'reports/M2E_POSITION_CASE_STUDIES.md'}
    only_hand_written = {'reports/m2e_data/review_dispositions.json'}
    flags = {f'reports/m2e_data/{c}/inventory_series_intra_second_flags.tsv' for c in ('NIFTY_2026-06-30', 'SENSEX_2026-07-16')}          # scenario-only sidecars (NEW by design)
    assert delivered - produced == only_hand_written and produced - delivered == flags, (sorted(delivered - produced), sorted(produced - delivered))
    assert len(delivered) == 168 and not [r for r in sorted(produced & delivered) if _norm(os.path.join(out, r)) != _norm(os.path.join(PE, r))]
    man = json.load(open(out / 'reports' / 'm2e_data' / 'NIFTY_2026-06-30' / 'manifest.json')); assert man['scenario']['scenario_id'] == 'baseline' and man['scenario']['tie_order_convention'] == 'SOURCE_ROW_ORDER_CONVENTION'
