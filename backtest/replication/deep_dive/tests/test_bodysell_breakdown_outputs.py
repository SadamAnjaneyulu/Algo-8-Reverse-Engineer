"""Regression contract of the saved body-sell ledger run (plan software checks 1 and 3): reconciliation to F's tables, one status per order, the probe replay equals F, M1 neighbours are matched, and the F run and ledgers are not silently changed."""
import os, json, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); B = f'{HERE}/../outputs/bodysell'
R = json.load(open(f'{B}/breakdown.json')); C = R['checks']
def test_ledger_reconciles_to_the_F_tables_and_every_order_has_one_status():
    assert C['reconciles_to_F_tables'] and C['every_real_has_one_status'] and C['every_sim_has_one_status'] and C['real_body_sells'] == 4408 and C['sim_body_sells'] == 4091 and C['real_missing'] == 1179 and C['sim_extra'] == 873
    LR = pd.read_csv(f'{B}/ledger_real.csv'); LS = pd.read_csv(f'{B}/ledger_sim.csv'); assert len(LR) == 4408 and len(LS) == 4091 and LR.category.notna().all() and LS.category.notna().all()
    assert set(LR.category) <= {'matched', 'M1', 'M2', 'M3', 'M4'} and set(LS.category) <= {'matched', 'X1', 'X2', 'X3', 'X4'}
def test_category_counts_add_up_and_cascade_invariants_hold():
    m = {d['category']: d['orders'] for d in R['missing_by_category']}; x = {d['category']: d['orders'] for d in R['extra_by_category']}; assert sum(m.values()) == 1179 and sum(x.values()) == 873 and R['missing_total']['persistent_in_TFE'] + R['missing_total']['recovered_by_TFE'] == 1179
    assert C['M1_with_unmatched_neighbour_(must_be_0)'] == 0                                                     # M1 means the same-type neighbour is matched elsewhere (one-to-one matching is maximal)
def test_probe_replay_reproduces_the_simulated_body_sells_of_F():
    assert C['probe_equals_F_simulated_body_sells'] and C['probe_body_sell_orders'] == 4091
