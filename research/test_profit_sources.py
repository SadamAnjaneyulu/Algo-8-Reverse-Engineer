"""Check option-role accounting across partial covers and position reversals."""
import unittest
from decimal import Decimal
from analyze_profit_sources import attribute


def fill(q,price):
    return dict(signed=q,price=Decimal(price),strike=100,ot='CE')


class ProfitSourceChecks(unittest.TestCase):
    def test_partial_short_covers_and_long_reversal_reconcile(self):
        result=attribute([fill(-2,'10'),fill(1,'8'),fill(2,'7'),fill(-1,'9')])
        self.assertEqual(result['short_position_realized_pnl_fifo'],'5')
        self.assertEqual(result['long_position_realized_pnl_fifo'],'2')
        self.assertEqual(result['observed_cashflow_before_costs'],'7')
        self.assertTrue(result['fully_flat'])

    def test_open_position_cash_is_not_realized_profit(self):
        result=attribute([fill(-2,'10'),fill(1,'8')])
        self.assertEqual(result['short_position_realized_pnl_fifo'],'2')
        self.assertEqual(result['observed_cashflow_before_costs'],'12')
        self.assertFalse(result['fully_flat'])
        self.assertEqual(result['residual_contracts'],1)


if __name__=='__main__':
    unittest.main()
