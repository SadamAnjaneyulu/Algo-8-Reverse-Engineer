"""Test signed portfolio valuation, exact-minute gaps and terminal-exit semantics."""
import unittest
from collections import Counter
from datetime import date, datetime, timedelta

from analyze_option_triggers import carry_stop_checks, mark, replay, terminal_reduction
from analyze_index_triggers import IST


class OptionReplayChecks(unittest.TestCase):
    def test_long_short_signs_and_nonsimultaneous_bounds(self):
        b=dict(open=10,high=12,low=8,close=10,volume=0)
        quotes={('2026-07-06',100,'CE'):{'09:15':b},('2026-07-06',100,'PE'):{'09:15':b}}
        inv={(100,'CE'):2,(100,'PE'):-3}
        self.assertEqual(mark(100,inv,quotes,'2026-07-06','09:15'),(90,0,2))
        self.assertEqual(mark(100,inv,quotes,'2026-07-06','09:15','adverse_bound')[0],80)
        self.assertEqual(mark(100,inv,quotes,'2026-07-06','09:15','favorable_bound')[0],100)

    def test_active_missing_minute_does_not_forward_fill_or_become_zero(self):
        quotes={('2026-07-06',100,'CE'):{'09:15':dict(close=10,volume=100)}}
        value,missing,zero=mark(50,{(100,'CE'):2},quotes,'2026-07-06','09:16')
        self.assertIsNone(value)
        self.assertEqual(missing,1)
        self.assertEqual(mark(50,{(100,'CE'):0},quotes,'2026-07-06','09:16'),(50,0,0))

    def test_terminal_exit_waits_for_later_material_reentry(self):
        start=datetime(2026,7,7,9,15,tzinfo=IST)
        states=[dict(t=start+timedelta(minutes=i),short=q) for i,q in enumerate((100,4,10,3,0))]
        self.assertEqual(terminal_reduction(states,'2026-07-07',100,.05),states[3]['t'].isoformat())
        self.assertEqual(terminal_reduction(states,'2026-07-07',100,0),states[4]['t'].isoformat())
        states[-1]['short']=1
        self.assertEqual(terminal_reduction(states,'2026-07-07',100,0),'')

    def test_cash_reconciliation_and_no_previous_day_price_at_expiry_open(self):
        expiry=date(2026,7,7)
        start=datetime(2026,7,6,9,15,tzinfo=IST)
        bar=dict(open=10,high=10,low=9,close=9,volume=100)
        quotes={('2026-07-06',100,'CE'):{(start+timedelta(minutes=i)).strftime('%H:%M'):dict(bar) for i in range(375)},
                ('2026-07-07',100,'CE'):{'09:15':dict(open=12,high=12,low=12,close=12,volume=100)}}
        fills=[dict(t=start+timedelta(minutes=1,seconds=1),expiry=expiry,strike=100,ot='CE',signed=-2,price=10),
               dict(t=datetime(2026,7,7,9,15,2,tzinfo=IST),expiry=expiry,strike=100,ot='CE',signed=2,price=12)]
        cycle,rows=replay('NIFTY',str(expiry),fills,quotes)
        self.assertEqual(cycle['final_cashflow_before_costs'],-4)
        self.assertEqual(cycle['final_observed_marked_equity'],-4)
        self.assertEqual(cycle['preexpiry_last_minute_equity'],2)
        self.assertEqual(cycle['expiry_opening_equity_before_fills'],-4)
        self.assertEqual(cycle['residual_contracts'],0)
        at_open=next(r for r in rows if r['bar_start_ist'].startswith('2026-07-07T09:15'))
        self.assertEqual(at_open['prior_completed_minute_equity_before_fills'],'')
        self.assertEqual(at_open['prior_missing_active_contracts'],1)
        checks=carry_stop_checks('NIFTY',str(expiry),fills,quotes)
        self.assertEqual(len(checks),1)
        self.assertTrue(checks[0]['original_carry_completion_unambiguous'])
        self.assertEqual(checks[0]['first_open_or_completed_close_cross_ist'],datetime(2026,7,7,9,15,tzinfo=IST).isoformat())
        self.assertAlmostEqual(checks[0]['unambiguous_completion_minus_cross_minutes'],2/60)

    def test_original_carry_attribution_remains_ambiguous_after_new_short_sales(self):
        expiry=date(2026,7,7)
        before=datetime(2026,7,6,9,16,tzinfo=IST)
        opening=datetime(2026,7,7,9,15,tzinfo=IST)
        fills=[dict(t=t,expiry=expiry,strike=100,ot='CE',signed=q,price=100) for t,q in
               [(before,-100),(opening+timedelta(minutes=1),-50),
                (opening+timedelta(minutes=2),100),(opening+timedelta(minutes=5),50)]]
        quotes={('2026-07-06',100,'CE'):{'15:29':dict(close=100,volume=100)},
                ('2026-07-07',100,'CE'):{'09:15':dict(open=100,close=105,volume=100)}}
        c=carry_stop_checks('NIFTY',str(expiry),fills,quotes)[0]
        self.assertFalse(c['original_carry_completion_unambiguous'])
        self.assertEqual(c['earliest_original_carry_cover_bound_ist'],fills[2]['t'].isoformat())
        self.assertEqual(c['latest_original_carry_cover_bound_ist'],fills[3]['t'].isoformat())
        self.assertEqual(c['unambiguous_completion_minus_cross_minutes'],'')


if __name__=='__main__':
    unittest.main()
