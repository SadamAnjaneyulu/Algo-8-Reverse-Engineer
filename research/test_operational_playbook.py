import unittest
from decimal import Decimal
from datetime import datetime,timedelta

from reconstruct_operational_book import IndependentBook,PriorSnapshot,classify_flow
from audit_operational_allocations import features,snapshot,mode
from audit_strike_hedge_rules import logs
from audit_execution_reversals import detect_motifs


def fill(side,q,price,k=100,right='CE'):
    return dict(side=side,q=q,price=Decimal(str(price)),strike=k,ot=right)


class AccountingTests(unittest.TestCase):
    def test_partial_close_preserves_average_and_flip_starts_new_cost(self):
        b=IndependentBook();b.apply(fill('Sell',3,100));r=b.apply(fill('Buy',1,120))
        self.assertEqual((r['closing_quantity'],r['opening_quantity']),(1,0))
        self.assertEqual(b.cost[(100,'CE')],100);self.assertEqual(b.realized,-20)
        r=b.apply(fill('Buy',4,90))
        self.assertEqual((r['closing_quantity'],r['opening_quantity']),(2,2))
        self.assertEqual(b.positions[(100,'CE')],2);self.assertEqual(b.cost[(100,'CE')],90)
        self.assertEqual(b.realized,0)

    def test_tie_order_changes_attribution_but_not_cash_or_net_inventory(self):
        a,b=IndependentBook(),IndependentBook()
        for book in (a,b):book.apply(fill('Sell',2,100))
        for r in (fill('Buy',1,110),fill('Sell',1,105)):a.apply(r)
        for r in (fill('Sell',1,105),fill('Buy',1,110)):b.apply(r)
        self.assertEqual(a.positions,b.positions);self.assertEqual(a.cash,b.cash)
        self.assertNotEqual(a.realized,b.realized)

    def test_negative_call_tail_has_no_finite_frozen_upside_bound(self):
        b=IndependentBook();b.apply(fill('Sell',2,5,100));b.apply(fill('Buy',1,1,120))
        self.assertIsNone(b.frozen_loss_bound())

    def test_matched_vertical_frozen_loss_is_width_less_credit(self):
        b=IndependentBook();b.apply(fill('Sell',2,5,100));b.apply(fill('Buy',2,1,120))
        self.assertEqual(b.frozen_loss_bound(),32)

    def test_missing_live_leg_price_is_not_zero_pnl(self):
        class Market:
            def bar(self,*args):return None
            def risk(self,*args):return None
        b=IndependentBook();b.apply(fill('Sell',1,5))
        r=PriorSnapshot(Market()).mark(b,'2026-01-01','09:15',None)
        self.assertIsNone(r['equity']);self.assertIsNone(r['delta'])

    def test_flat_book_has_known_cash_and_zero_risk_without_a_quote(self):
        class Market:pass
        b=IndependentBook();b.cash=Decimal(12);b.realized=Decimal(12)
        r=PriorSnapshot(Market()).mark(b,'2026-01-01','09:15',None)
        self.assertEqual(r['equity'],12);self.assertEqual(r['delta'],0)


class TimingAndFeatureTests(unittest.TestCase):
    def test_snapshot_excludes_fills_at_the_boundary(self):
        t='2026-07-13T09:30:00+05:30'
        seq=dict(times=[t],rows=[{'after_CE_short':65,'after_PE_short':0,'after_CE_long':65,'after_PE_long':0}])
        self.assertEqual(snapshot(seq,t)['CE_short'],0)
        self.assertEqual(snapshot(seq,'2026-07-13T09:30:01+05:30')['CE_short'],65)

    def test_initial_market_features_ignore_future_opening_session(self):
        start=datetime(2026,7,13,9,15,tzinfo=logs.IST)
        bars=[dict(t=start,open=100,close=101,high=102,low=99)]
        index={('NIFTY','2026-07-13'):bars}
        a=features(index,'NIFTY',start+timedelta(minutes=1))
        bars.append(dict(t=start+timedelta(minutes=1),open=101,close=10000,high=10000,low=1))
        self.assertEqual(a,features(index,'NIFTY',start+timedelta(minutes=1)))

    def test_pre_window_feature_requires_completed_bar_before_early_fill(self):
        start=datetime(2026,7,13,9,15,tzinfo=logs.IST)
        bars=[dict(t=start+timedelta(minutes=i),open=100,close=100,high=100,low=100) for i in range(20)]
        r=features({('NIFTY','2026-07-13'):bars},'NIFTY',start+timedelta(minutes=15,seconds=-2))
        self.assertEqual(r['market_available_at_ist'],'2026-07-13T09:29:00+05:30')
        self.assertEqual(r['direction15'],'unavailable')

    def test_tied_quantity_modes_are_reported_without_hiding_alternatives(self):
        chosen,alternatives,n=mode([1,1,2,2])
        self.assertEqual((chosen,alternatives,n),(1,[1,2],2))


class ReversalMotifTests(unittest.TestCase):
    def test_close_reverse_neutralize_preserves_pattern_and_timing(self):
        rows=[dict(t=0,before=0,after=100),dict(t=80,before=100,after=0),
              dict(t=82,before=0,after=-100),dict(t=87,before=-100,after=0)]
        found=detect_motifs(rows)
        self.assertEqual(len(found),1);self.assertTrue(found[0]['conservative'])

    def test_later_new_position_is_not_labeled_fast_reversal(self):
        rows=[dict(t=0,before=0,after=100),dict(t=80,before=100,after=0),
              dict(t=91,before=0,after=-100),dict(t=95,before=-100,after=0)]
        self.assertFalse(detect_motifs(rows))

    def test_direct_flip_restarts_old_sign_age(self):
        rows=[dict(t=0,before=0,after=-100),dict(t=75,before=-100,after=100),
              dict(t=80,before=100,after=0),dict(t=82,before=0,after=-100),dict(t=87,before=-100,after=0)]
        found=detect_motifs(rows)
        self.assertEqual(len(found),1);self.assertFalse(found[0]['conservative'])


if __name__=='__main__':unittest.main()
