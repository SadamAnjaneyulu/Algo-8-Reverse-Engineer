import unittest
from datetime import timedelta

from rank_economic_alpha import allowed, drawdown, known_features, simulate, stamp, stats


class MemoryQuotes:
    def __init__(self, bars):
        self.bars = bars

    def bar(self, asset, expiry, contract, day, clock):
        return self.bars.get((day, clock, *contract))


class EconomicAlphaChecks(unittest.TestCase):
    def fixture(self):
        day = '2026-07-07'
        legs = [(100, 'CE', -1), (120, 'CE', 1), (100, 'PE', -1), (80, 'PE', 1)]
        bars = {}
        for minute in range(17, 23):
            for (strike, right, sign), price in zip(legs, [10, 1, 10, 1]):
                bars[(day, f'09:{minute:02}', strike, right)] = dict(open=price, close=price, volume=100)
        plan = dict(underlying='NIFTY', expiry_date=day, legs=legs, quantity=1,
                    entry=stamp(day, '09:17'), end=stamp(day, '09:22'), entry_prices=[10, 1, 10, 1],
                    entry_zero_volume=0, credit=18)
        return plan, MemoryQuotes(bars)

    def test_premium_credit_is_not_profit_at_unchanged_prices(self):
        plan, quotes = self.fixture()
        r, failure = simulate(plan, quotes, 'time_only')
        self.assertIsNone(failure)
        self.assertEqual(r['gross'], 0)
        self.assertLess(r['net_primary'], 0)
        self.assertEqual(r['orders'], 8)
        self.assertEqual(r['transacted_units'], 8)

    def test_leg_stop_executes_future_open_not_threshold_price(self):
        plan, quotes = self.fixture()
        quotes.bars[('2026-07-07', '09:17', 100, 'CE')]['close'] = 16
        quotes.bars[('2026-07-07', '09:17', 100, 'PE')]['close'] = 5
        quotes.bars[('2026-07-07', '09:19', 100, 'CE')]['open'] = 30
        quotes.bars[('2026-07-07', '09:19', 120, 'CE')]['open'] = 11
        r, failure = simulate(plan, quotes, 'symmetric_50')
        self.assertIsNone(failure)
        self.assertEqual(r['ce_exit_ist'], stamp('2026-07-07', '09:19').isoformat())
        self.assertEqual(r['pe_exit_ist'], stamp('2026-07-07', '09:22').isoformat())
        self.assertEqual(r['gross'], -10)
        # Closing the two sides at different times can exceed the frozen
        # condor's 20-18=2 loss bound; sum-of-side budgets cover this path.
        self.assertLess(r['gross'], -2)
        self.assertGreaterEqual(r['gross'], -(20+20-18))

    def test_missing_monitor_quote_invalidates_instead_of_skipping_stop(self):
        plan, quotes = self.fixture()
        quotes.bars.pop(('2026-07-07', '09:17', 100, 'CE'))
        r, failure = simulate(plan, quotes, 'symmetric_50')
        self.assertIsNone(r)
        self.assertEqual(failure, 'missing_stop_monitor')

    def test_missing_exit_is_not_assumed_zero(self):
        plan, quotes = self.fixture()
        quotes.bars.pop(('2026-07-07', '09:22', 120, 'CE'))
        r, failure = simulate(plan, quotes, 'time_only')
        self.assertIsNone(r)
        self.assertEqual(failure, 'missing_exit_open')

    def test_unknown_filter_is_different_from_a_rejected_trade(self):
        self.assertIsNone(allowed(dict(iv_over_prior_rv=None), 'iv_prior_rv_ge_1.25'))
        self.assertFalse(allowed(dict(iv_over_prior_rv=1), 'iv_prior_rv_ge_1.25'))
        self.assertTrue(allowed(dict(iv_over_prior_rv=2), 'iv_prior_rv_ge_1.25'))

    def test_entry_features_ignore_future_same_day_bars(self):
        day = '2026-07-07'
        bars = [dict(t=stamp(day, '09:15'), open=100, high=101, low=99, close=100),
                dict(t=stamp(day, '09:16'), open=100, high=10000, low=1, close=10000)]
        quotes = MemoryQuotes({(day, '09:15', 100, right): dict(close=1) for right in ('CE', 'PE')})
        r = known_features({('NIFTY', day): bars}, quotes, 'NIFTY', day, stamp(day, '09:16'), 100)
        self.assertEqual(r['opening_range_pct'], 2)
        self.assertEqual(r['reference_bar_start_ist'], stamp(day, '09:15').isoformat())

    def test_closed_cycle_drawdown_has_zero_initial_peak(self):
        self.assertEqual(drawdown([5, -10, 20]), 10)
        self.assertEqual(drawdown([-5, -2]), 7)
        self.assertEqual(drawdown([5, 10]), 0)

    def test_stats_use_policy_loss_budget_and_include_idle_cycles(self):
        rows = [dict(expiry_date='2026-07-07', underlying='NIFTY', net_primary=10, net_high=9,
                     static_tail_loss=100, risk_budget=1000, trade_allowed=True),
                dict(expiry_date='2026-07-14', underlying='NIFTY', net_primary=0, net_high=0,
                     static_tail_loss=100, risk_budget=1000, trade_allowed=False)]
        r = stats(rows)
        self.assertEqual(r['mean_net_per_10000_tail_loss'], 50)
        self.assertEqual(r['active_cycles'], 1)
        self.assertEqual(r['cycles'], 2)


if __name__ == '__main__':
    unittest.main()
