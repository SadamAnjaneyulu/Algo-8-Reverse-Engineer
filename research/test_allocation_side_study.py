import unittest
from datetime import datetime, timedelta

import numpy as np
from sklearn.tree import DecisionTreeClassifier

import option_pricing_model as black
from allocation_rule_models import cooldown_predictions, event_tolerance, event_probability
from analyze_side_allocations import match_parents
from build_allocation_side_features import ShortLots, vector_greeks, lot_state
from scan_allocated_stop_rules import first_hits
from search_allocation_budgets import round_units
from search_side_controllers import common_side_features
from analyze_index_triggers import IST
from analyze_allocation_sizes import frozen_expiry_bound


class AllocationSideChecks(unittest.TestCase):
    def test_vector_greeks_reproduce_scalar_black_model(self):
        f, k, tau, sigma = 24000., 24100., 2/365, .2
        prices = [black.price(f, k, tau, sigma, right) for right in ('CE', 'PE')]
        values = vector_greeks(prices, [f]*2, [k]*2, [tau]*2, [True, False])
        for i, right in enumerate(('CE', 'PE')):
            expected = black.greeks(f, k, tau, sigma, right)
            self.assertAlmostEqual(values['iv_pct'][i], 20, places=6)
            for field in ('delta', 'gamma', 'vega_one_point', 'theta_calendar_day'):
                self.assertAlmostEqual(values[field][i], expected[field], places=6)

    def test_unfittable_prices_do_not_create_zero_greeks(self):
        values = vector_greeks([0, 100], [24000, 24000], [24000, 24000], [1/365, -1], [True, True])
        self.assertTrue(np.isnan(values['delta']).all())

    def fill(self, side, price, quantity, opening, minute):
        return dict(strike=100, ot='CE', side=side, price=price, q=quantity, opening=opening,
                    t=datetime(2026, 7, 6, 9, minute, tzinfo=IST))

    def test_fifo_lifo_assignments_differ_but_flat_total_reconciles(self):
        fifo, lifo = ShortLots(), ShortLots(True)
        sequence = [self.fill('Sell', 10, 1, 1, 16), self.fill('Sell', 20, 1, 1, 30),
                    self.fill('Buy', 15, 1, 0, 40), self.fill('Buy', 12, 1, 0, 45)]
        for i, r in enumerate(sequence):
            for lots in (fifo, lifo): lots.apply(r, str(i), 100)
        self.assertEqual(fifo.closes[0]['entry_price'], 10)
        self.assertEqual(lifo.closes[0]['entry_price'], 20)
        self.assertEqual(sum(r['short_realized_pnl'] for r in fifo.closes), 3)
        self.assertEqual(sum(r['short_realized_pnl'] for r in lifo.closes), 3)

    def test_lot_state_does_not_include_already_covered_quantity(self):
        lots = [dict(price=10, remaining=1, entry_spot=100, entry_date='2026-07-06'),
                dict(price=20, remaining=3, entry_spot=110, entry_date='2026-07-07')]
        state = lot_state(lots, 15, '2026-07-07', 108)
        self.assertEqual(state['cost'], 17.5)
        self.assertEqual(state['fraction_over50'], .25)
        self.assertEqual(state['carried_fraction'], .25)

    def test_hedge_matching_does_not_reuse_a_long_parent(self):
        t = datetime(2026, 7, 6, 9, 16, tzinfo=IST)
        shorts = [dict(first=t, quantity=1), dict(first=t+timedelta(seconds=1), quantity=1)]
        longs = [dict(first=t, quantity=1)]
        links = match_parents(shorts, longs, lambda a, b: a['quantity'] == b['quantity'])
        self.assertEqual(len(links), 1)

    def test_hedge_link_respects_time_and_reports_alternatives(self):
        t = datetime(2026, 7, 6, 9, 16, tzinfo=IST)
        short = [dict(first=t)]
        longs = [dict(first=t), dict(first=t+timedelta(seconds=1)), dict(first=t+timedelta(seconds=6))]
        links = match_parents(short, longs, lambda a, b: True)
        self.assertEqual(links[0][3], 2)

    def test_cooldown_is_owned_per_contract_and_resets_each_day(self):
        rows = [dict(contract=k, cycle='c', date=d, clock=t) for d, t, k in
                [('a', '09:30', 'CE'), ('a', '09:30', 'PE'), ('a', '09:31', 'CE'), ('b', '09:30', 'CE')]]
        np.testing.assert_array_equal(cooldown_predictions(rows, [True]*4, 5), [True, True, False, True])

    def test_one_prediction_cannot_match_two_actual_exit_events(self):
        rows = [dict(contract='CE', cycle='c', date='d', clock=t) for t in ('09:30', '09:31', '09:32')]
        score = event_tolerance(rows, [True, False, True], [False, True, False], 2)
        self.assertEqual(score['matched_events'], 1)
        self.assertEqual(score['precision'], 1)
        self.assertEqual(score['recall'], .5)

    def test_one_class_fold_has_no_fabricated_positive_probability(self):
        model = DecisionTreeClassifier().fit([[1], [2]], [False, False])
        np.testing.assert_array_equal(event_probability(model, np.array([[3], [4]])), [0, 0])

    def test_carry_stop_requires_a_reference(self):
        atoms = [dict(family='carry_short_loss', threshold=4, activation=0)]
        hits = first_hits(np.array([110.]), np.array([109.]), np.array([1.]), np.array(['2026-07-07']),
                          100, 99, '2026-07-07', None, None, atoms)
        self.assertTrue(np.isinf(hits[0]))

    def test_trailing_exit_requires_prior_profit_activation(self):
        atoms = [dict(family='activated_hedged_trail', threshold=10, activation=40)]
        hits = first_hits(np.array([100, 105, 110]), np.array([100, 105, 110]), np.array([1., 2., 3.]),
                          np.array(['d']*3), 100, 100, 'e', None, None, atoms)
        self.assertTrue(np.isinf(hits[0]))
        hits = first_hits(np.array([100, 50, 60]), np.array([100, 50, 60]), np.array([1., 2., 3.]),
                          np.array(['d']*3), 100, 100, 'e', None, None, atoms)
        self.assertEqual(hits[0], 3)

    def test_units_rounding_is_integer_not_capital_allocation(self):
        self.assertEqual(round_units(2.5, 'nearest'), 3)
        self.assertEqual(round_units(2.5, 'floor'), 2)
        self.assertEqual(round_units(2.1, 'ceil'), 3)

    def test_common_greeks_keep_vega_while_omitting_oi(self):
        fields = common_side_features(dict(a_contract_vega_one_point_over_premium=1,
                                           a_same_strike_oi_ratio=1, a_oi_change5_pct=1))
        self.assertEqual(fields, ['a_contract_vega_one_point_over_premium'])

    def test_frozen_expiry_bound_is_tail_payoff_not_margin(self):
        inventory = {(24000, 'CE'): -195, (24000, 'PE'): -195,
                     (26000, 'CE'): 195, (22000, 'PE'): 195}
        self.assertAlmostEqual(frozen_expiry_bound(inventory, 35197.5), 354802.5)

    def test_unprotected_net_short_call_has_no_finite_tail_bound(self):
        self.assertIsNone(frozen_expiry_bound({(24000, 'CE'): -65}, 5000))


if __name__ == '__main__':
    unittest.main()
