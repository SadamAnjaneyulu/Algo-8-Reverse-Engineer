import unittest
from clarify_position_lifecycle import retained_lower_bound


class RetentionChecks(unittest.TestCase):
    def test_new_basket_does_not_remove_existing_exposure(self):
        before = {(100, 'CE'): -65, (100, 'PE'): -65, (200, 'CE'): 65}
        fills = [dict(strike=150, ot='CE', side='Sell', q=65),
                 dict(strike=250, ot='CE', side='Buy', q=65)]
        self.assertEqual(retained_lower_bound(before, fills), 130)
        self.assertEqual(retained_lower_bound(before, fills, False), 65)

    def test_all_buys_on_old_short_contracts_count_as_possible_closes(self):
        before = {(100, 'CE'): -65, (100, 'PE'): -65}
        fills = [dict(strike=100, ot='CE', side='Buy', q=100)]
        self.assertEqual(retained_lower_bound(before, fills), 65)

    def test_reopened_same_strike_cannot_restore_the_old_lot_bound(self):
        before = {(100, 'CE'): -65}
        fills = [dict(strike=100, ot='CE', side='Buy', q=65),
                 dict(strike=100, ot='CE', side='Sell', q=65)]
        self.assertEqual(retained_lower_bound(before, fills), 0)


if __name__ == '__main__':
    unittest.main()
