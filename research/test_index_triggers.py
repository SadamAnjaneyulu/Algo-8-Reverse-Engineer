"""Verify timing and inventory semantics used by the index trigger study."""
import unittest
from datetime import datetime
from analyze_index_triggers import IST, final_flat, reference, round_strike


class TriggerStudyChecks(unittest.TestCase):
    def test_event_minute_close_is_never_used(self):
        t=datetime(2026,10,12,9,16,2,tzinfo=IST)
        bars=[dict(t=t.replace(minute=15,second=0),open=100,high=102,low=99,close=101),
              dict(t=t.replace(second=0),open=101.1,high=999,low=90,close=900)]
        b,f=reference({('NIFTY','2026-10-12'):bars},'NIFTY',t)
        self.assertEqual(b['close'],101)
        self.assertEqual(f['completed_range_pct'],3)
        self.assertEqual(f['minute_boundary_open'],101.1)

    def test_auction_event_cannot_reuse_stale_continuous_close(self):
        t=datetime(2026,10,12,15,30,2,tzinfo=IST)
        bars=[dict(t=t.replace(minute=14,second=0),open=100,high=102,low=99,close=101)]
        self.assertEqual(reference({('NIFTY','2026-10-12'):bars},'NIFTY',t),(None,{}))

    def test_strike_rounding_uses_each_index_grid(self):
        self.assertEqual(round_strike(24021.55,'NIFTY'),24000)
        self.assertEqual(round_strike(24025,'NIFTY'),24050)
        self.assertEqual(round_strike(74348.29,'SENSEX'),74300)

    def test_later_reentry_changes_final_flat_time(self):
        times=[datetime(2026,10,12,9,i,tzinfo=IST) for i in (16,17,18,19)]
        states=[dict(t=t,short=q) for t,q in zip(times,(10,0,10,0))]
        self.assertEqual(final_flat(states,'short'),times[-1].isoformat())
        self.assertEqual(final_flat(states[:-1],'short'),'')


if __name__=='__main__':
    unittest.main()
