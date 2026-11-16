"""Required counterexamples (a) ordering semantics and (b) reversal calculation, executed with the PROJECT code (pe.replay / pe.reversals) on synthetic fills and (b2) my own code on the raw ledger."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(PE, 'python'))
from pe.schema import Fill, Instrument
from pe import replay as RP, reversals as RV
res = {}
INS = {'X': Instrument('X', 'NIFTY', 'NSEFO', 'OPTION', 'CE', 24000, '2030-01-01', 65, 5, 'test'), 'Y': Instrument('Y', 'NIFTY', 'NSEFO', 'OPTION', 'PE', 24000, '2030-01-01', 65, 5, 'test')}
T0 = 1_800_000_000


def F(i, row, parent, inst, ts, side, q, px):
    return Fill(f'F{i:06d}', row, parent, 'num', inst, ts, side, q, px, q, 'Filled', False, 'SYNTHETIC_TEST', 'syn')


# (a) second-end state under two orderings of ONE second (same instrument): inventory and cash agree, the LIFO book / realized do not
fills = [F(1, 1, 'P0', 'X', T0, 1, 10, 10000), F(2, 2, 'PA', 'X', T0 + 1, 1, 10, 12000), F(3, 3, 'PB', 'X', T0 + 1, -1, 10, 11000)]
out = {}
for method in ('FIFO', 'LIFO'):
    for order in ('src', 'sells_first'):
        r = RP.replay(fills, INS, 'SYNTHETIC_TEST', method=method, tie_order=order); s = r.snapshots[-1]
        st = r.state; out[f'{method}|{order}'] = dict(second_end_gross=s['gross_units'], cash=s['cash'], realized_paise=s['realized'], book_value=st.book_value('X'), reversal_fills=st.reversal_fills)
res['a_synthetic_same_instrument_second'] = out
for k, v in out.items(): print('a', k, v)
# (a2) cross-instrument interleaving cannot move any per-instrument or second-end quantity: confirmed on raw data in item1_second_end.py (C-orderings: 0 differences in every field)
# (b) reversal measures: same raw data, two same-instrument orders inside one second
rows_ab = [('F1', 1, 'X', 'P0', T0, 10), ('F2', 2, 'X', 'PA', T0 + 1, -10), ('F3', 3, 'X', 'PB', T0 + 1, -5)]
rows_ba = [rows_ab[0], rows_ab[2], rows_ab[1]]
b = {}
for name, rows in (('A_then_B', rows_ab), ('B_then_A', rows_ba)):
    m = RV.measures(rows); b[name] = m['counts']; print('b order dependence', name, m['counts'])
res['b1_order_dependence'] = b
# (b3) attribution: parent A only BUYS, yet is flagged as a parent-level same-second sign flip because parent B (interleaved) crossed zero
rows = [('F1', 1, 'X', 'P0', T0, 5), ('F2', 2, 'X', 'PA', T0 + 1, 1), ('F3', 3, 'X', 'PB', T0 + 1, -11), ('F4', 4, 'X', 'PA', T0 + 1, 1)]
m = RV.measures(rows); res['b2_attribution'] = dict(counts=m['counts'], parent_level=[dict(parent=g['parent_order_id'], before=g['inventory_before'], after=g['inventory_after']) for g in m['parent_level']], per_fill=[dict(parent=g['parent_order_id']) for g in m['per_fill']]); print('b attribution', res['b2_attribution'])
# (b4) zero-touch two-fill crossing: parent-level flip with NO per-fill zero crossing (+10 -> 0 -> -10 by two fills of one parent)
rows = [('F1', 1, 'X', 'P0', T0, 10), ('F2', 2, 'X', 'PA', T0 + 1, -10), ('F3', 3, 'X', 'PA', T0 + 1, -10)]
m = RV.measures(rows); res['b3_flip_without_per_fill'] = m['counts']; print('b two-fill flat-then-open', m['counts'])
json.dump(res, open(os.path.join(HERE, 'counterexamples_ab_result.json'), 'w'), indent=1)
