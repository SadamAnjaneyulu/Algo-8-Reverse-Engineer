"""Accounting invariants checked on a PortfolioState (and optionally after every fill in strict mode)."""
from .schema import *

TOL = 1e-6          # paise x units, AVG method only (floating point pools)


def check_state(state, expected_signed=None):
    """raises InvariantViolation on the first failure; returns the list of checks performed"""
    done = []
    def ok(name, cond, detail=''):
        done.append(name)
        if not cond: raise InvariantViolation(f'{name}: {detail}')
    gross = 0; sgn_sum = {}
    for iid, st in state.s.items():
        ok('inventory_non_negative_in_direction', st.inv >= 0 and (st.inv == 0 or st.dir in (1, -1)), iid)
        lots_q = st.pool_q if state.avg else sum(l[0] for l in st.lots)
        ok('lots_reconcile_to_inventory', lots_q == st.inv, f'{iid}: lots {lots_q} vs inventory {st.inv}')
        ok('per_instrument_opened_minus_closed', st.opened - st.closed == st.inv, f'{iid}')
        gross += st.inv
    ok('portfolio_opened_minus_closed_equals_gross_inventory', state.opened - state.closed == gross, f'{state.opened}-{state.closed} vs {gross}')
    ag = state.agg
    ok('aggregates_reconcile_to_instruments', ag['short_CE'] + ag['short_PE'] + ag['long_CE'] + ag['long_PE'] == gross, str(ag))
    if expected_signed is not None:                                         # independent accumulator: signed sum of applied fills
        for iid, v in expected_signed.items(): ok('signed_inventory_equals_sum_of_fills', state.signed_inventory(iid) == v, f'{iid}: {state.signed_inventory(iid)} vs {v}')
    realized = state.realized_total(); book = state.book_total(); diff = state.cash - (realized + book)
    ok('cash_identity_cash_equals_realized_plus_book_value', (diff == 0) if not state.avg else abs(diff) <= TOL * max(1, state.applied) + 1e-12 * max(1.0, abs(state.cash), abs(realized), abs(book)), f'diff {diff}')
    ep_real = sum(e['realized'] for e in state.episodes.values())
    ok('episode_realized_sums_to_portfolio_realized', (ep_real == realized) if not state.avg else abs(ep_real - realized) <= TOL * max(1, state.applied) + 1e-12 * max(1.0, abs(realized)), f'{ep_real} vs {realized}')
    ok('episode_units_reconcile', sum(e['opened'] - e['closed'] for e in state.episodes.values()) == gross)
    return done
