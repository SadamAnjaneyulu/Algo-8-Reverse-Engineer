"""Reconcile role P&L through covers/flips and test quote-budget quantization."""
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from analyze_index_triggers import IST
from refine_exit_scopes import RoleBook,signal,observed_flat_times
from refine_hedge_budget import rounded_budget


def fill(side,q,opening,price,strike=100):
    return dict(side=side,q=q,opening=opening,price=price,strike=strike,ot='CE',signed=q if side=='Buy' else -q)


class RefinementChecks(unittest.TestCase):
    def test_short_and_long_ledgers_reconcile_realized_and_unrealized(self):
        b=RoleBook();b.apply(fill('Sell',2,2,10));b.apply(fill('Buy',1,0,12));b.apply(fill('Buy',1,1,1,strike=120))
        market=SimpleNamespace(bar=lambda day,k,right,clock:dict(close=11 if k==100 else 2,volume=100))
        r=b.mark(market,'2026-07-07','09:30')
        self.assertEqual(r['short_book_equity'],-3)
        self.assertEqual(r['long_book_equity'],1)
        self.assertEqual(r['net_equity'],-2)
        self.assertEqual(r['realized_equity'],-2)
        self.assertEqual(r['unrealized_equity'],0)
        self.assertEqual(r['gross_losing_open'],-1)

    def test_a_long_to_short_flip_preserves_realized_hedge_profit(self):
        b=RoleBook();b.apply(fill('Buy',1,1,1));b.apply(fill('Sell',2,1,3))
        market=SimpleNamespace(bar=lambda *a:dict(close=2,volume=100))
        r=b.mark(market,'2026-07-07','09:30')
        self.assertEqual(b.inventory[(100,'CE')],-1)
        self.assertEqual(b.average[(100,'CE')],3)
        self.assertEqual(r['realized_equity'],2)
        self.assertEqual(r['short_book_equity'],1)
        self.assertEqual(r['long_book_equity'],2)
        self.assertEqual(r['net_equity'],3)

    def test_missing_wing_does_not_destroy_available_short_scope_or_invent_net(self):
        b=RoleBook();b.apply(fill('Sell',1,1,10));b.apply(fill('Buy',1,1,1,strike=120))
        market=SimpleNamespace(bar=lambda day,k,*a:dict(close=11,volume=100) if k==100 else None)
        r=b.mark(market,'2026-07-07','09:30')
        self.assertEqual(r['short_book_equity'],-1)
        self.assertIsNone(r['long_book_equity'])
        self.assertIsNone(r['net_equity'])
        self.assertIsNone(r['gross_losing_open'])

    def test_role_mismatch_is_not_silently_reclassified(self):
        b=RoleBook();b.apply(fill('Sell',1,1,10))
        with self.assertRaises(ValueError):b.apply(fill('Buy',1,1,12))

    def test_quote_budget_rounding_has_explicit_half_up_and_float_tolerance(self):
        self.assertAlmostEqual(rounded_budget(2.125,.05,'nearest'),2.15)
        self.assertAlmostEqual(rounded_budget(2.125,.05,'floor'),2.1)
        self.assertAlmostEqual(rounded_budget(2.5000000000000004,.05,'floor'),2.5)
        self.assertEqual(rounded_budget(2.123,0,'none'),2.123)

    def test_changing_loss_scope_changes_signal_without_using_exit_label(self):
        t=datetime(2026,7,7,9,16,tzinfo=IST);end=t.replace(hour=15,minute=29)
        cycle=dict(fallback=end,target=t.isoformat(),path=[dict(t=t,short_quantity=65,opening_proxy=False,net=-.5,short=-1.2)])
        self.assertEqual(signal(cycle,'short',-1,'le'),t)
        self.assertEqual(signal(cycle,'net',-1,'le'),end)
        self.assertEqual(signal({**cycle,'target':end.isoformat()},'short',-1,'le'),t)

    def test_whole_book_closures_ignore_a_transient_same_second_zero(self):
        expiry=datetime(2026,7,7).date();start=datetime(2026,7,7,9,16,tzinfo=IST)
        times=[start.replace(day=6),start,start,start.replace(minute=17),start.replace(minute=30),start.replace(hour=10,minute=0)]
        flows=[-65,65,-65,65,-65,65]
        rows=[dict(u='NIFTY',expiry=expiry,t=t,strike=100,ot='CE',signed=q) for t,q in zip(times,flows)]
        with patch('refine_exit_scopes.logs.read_fills',return_value=rows),patch('refine_exit_scopes.write'):
            result=observed_flat_times()[('NIFTY','2026-07-07')]
        self.assertEqual(result['closure_episodes'],2)
        self.assertEqual(result['first_flat'],start.replace(minute=17).isoformat())
        self.assertEqual(result['final_flat'],start.replace(hour=10,minute=0).isoformat())

    def test_a_95percent_reduction_can_leave_a_short_book_open(self):
        expiry=datetime(2026,7,7).date();t=datetime(2026,7,7,9,16,tzinfo=IST)
        rows=[dict(u='NIFTY',expiry=expiry,t=t.replace(day=6),strike=100,ot='CE',signed=-2600),
              dict(u='NIFTY',expiry=expiry,t=t,strike=100,ot='CE',signed=2500),
              dict(u='NIFTY',expiry=expiry,t=t.replace(hour=15,minute=14),strike=100,ot='CE',signed=100)]
        with patch('refine_exit_scopes.logs.read_fills',return_value=rows),patch('refine_exit_scopes.write'):
            result=observed_flat_times()[('NIFTY','2026-07-07')]
        self.assertEqual(result['first_flat'],t.replace(hour=15,minute=14).isoformat())


if __name__=='__main__':unittest.main()
