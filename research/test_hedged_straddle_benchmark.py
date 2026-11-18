"""Check benchmark cutoff, cash/turnover accounting and sampling units."""
import unittest
from datetime import datetime, timedelta

import benchmark_hedged_straddle as b
from analyze_index_triggers import IST


class FakeQuotes:
    def __init__(self,missing=False):
        self.missing=missing

    def bar(self,u,expiry,contract,day,clock):
        if self.missing:
            return None
        # Open short at 10 and buy back at 6; long opens at 1, exits at 0.5.
        at_exit=day==expiry
        return dict(open=(6 if at_exit else 10) if contract[0]==100 else (.5 if at_exit else 1),volume=100)


class BenchmarkChecks(unittest.TestCase):
    def test_recorded_orders_count_once_and_cutoff_excludes_equal_timestamp(self):
        expiry='2026-07-07'
        cut=datetime(2026,7,7,15,14,tzinfo=IST)
        rows=[dict(t=cut-timedelta(minutes=1),strike=100,ot='CE',signed=-1,q=1,price=10,source=1),
              dict(t=cut-timedelta(minutes=1),strike=100,ot='CE',signed=-1,q=1,price=10,source=2),
              dict(t=cut,strike=100,ot='CE',signed=2,q=2,price=1000,source=3)]
        a=b.actual_at(rows,cut,FakeQuotes(),'NIFTY',expiry,{1:'same-order',2:'same-order',3:'excluded'})
        self.assertEqual(a['gross'],8)
        self.assertEqual(a['orders'],2)  # One observed order plus forced buyback.
        self.assertEqual(a['turnover'],32)
        self.assertEqual(a['units'],4)

    def test_missing_mark_is_not_zero_profit_or_forward_filled(self):
        cut=datetime(2026,7,7,15,14,tzinfo=IST)
        rows=[dict(t=cut-timedelta(minutes=1),strike=100,ot='CE',signed=-1,q=1,price=10,source=1)]
        a=b.actual_at(rows,cut,FakeQuotes(True),'NIFTY','2026-07-07',{1:'order'})
        self.assertIsNone(a['gross'])
        self.assertEqual(a['missing'],'100CE')

    def test_frozen_basket_signs_loss_bound_and_averaging_order_cost(self):
        legs=[((100,'CE'),-1),((100,'PE'),-1),((120,'CE'),1),((80,'PE'),1)]
        a=b.basket_at('NIFTY','2026-07-07','2026-07-06',legs,FakeQuotes(),'09:16','15:14')
        self.assertEqual(a['entry_credit_unit'],18)
        self.assertEqual(a['gross_unit'],7)
        self.assertEqual(a['turnover_unit'],35)
        self.assertEqual(a['max_expiry_loss_unit'],2)
        self.assertEqual(a['orders'],8)
        c=b.basket_at('NIFTY','2026-07-07','2026-07-06',legs,FakeQuotes(),'09:16','15:14',True)
        self.assertAlmostEqual(c['gross_unit'],a['gross_unit'])
        self.assertEqual(c['orders'],92)

    def test_calibration_size_depends_on_dispersion_not_level_of_profit(self):
        q,ideal=b.calibrated_quantity([-200,0,200],[-1,0,1],20)
        shifted,_=b.calibrated_quantity([800,1000,1200],[-1,0,1],20)
        self.assertEqual(q,200)
        self.assertEqual(ideal,200)
        self.assertEqual(q,shifted)

    def test_costs_scale_units_turnover_and_orders_separately(self):
        self.assertEqual(b.cost(10000,100,2,'primary'),25+40+5)
        self.assertEqual(b.cost(10000,100,2,'gross'),0)

    def test_bootstrap_clusters_both_indices_in_same_expiry_week(self):
        rows=[dict(expiry_date='2026-09-01',paired_difference=10),
              dict(expiry_date='2026-09-03',paired_difference=20),
              dict(expiry_date='2026-09-08',paired_difference=30)]
        result=b.week_bootstrap(rows,1000)
        self.assertEqual(result['weeks'],2)
        self.assertEqual(result,b.week_bootstrap(rows,1000))
        self.assertLessEqual(result['lower'],20)
        self.assertGreaterEqual(result['upper'],20)

    def test_stop_executes_next_open_and_can_overshoot_threshold(self):
        legs=[((100,'CE'),-1),((100,'PE'),-1),((120,'CE'),1),((80,'PE'),1)]
        class StopQuotes:
            def bar(self,u,expiry,contract,day,clock):
                if contract[0]!=100:
                    return dict(open=1,close=1,volume=100)
                if day<expiry:
                    return dict(open=10,close=10,volume=100)
                return dict(open=10 if clock=='09:15' else 14,close=13,volume=100)
        result=b.stopped_basket('NIFTY','2026-07-07','2026-07-06',legs,StopQuotes(),100,500)
        self.assertTrue(result['triggered'])
        self.assertEqual(result['execution_clock'],'09:16')
        self.assertEqual(result['gross'],-800)  # Not a fabricated fill at -500.


if __name__=='__main__':
    unittest.main()
