import unittest

import numpy as np
import pandas as pd

from study_cover_reentry_controls import (
    FEATURES,bootstrap_difference,count_window,match_landmarks,
    outside_timer,robust_transform,timer_seconds,
)


def synthetic():
    rows=[]
    for i,clock in enumerate((600,615,630,645)):
        r=dict(eligible=True,cover_onset=int(i==1),quiet_control=int(i!=1),
               new_entries_previous_minute=0,new_parent_previous5_positive=0,
               contract='NIFTY|2026-07-07|CE',date='2026-07-06',clock_phase=0,timer_seconds5=180,
               clock_minutes=clock,underlying='NIFTY',expiry_date='2026-07-07',
               phase='preexpiry',option_type='CE',clock=f'{clock//60:02}:{clock%60:02}',
               week='2026-28',split='calibration',entry5=int(i==1))
        for prefix in ('post','pre'):
            for f in FEATURES:r[prefix+'_'+f]=1. if f in ('own_short','opposite_short') else 0.
        rows.append(r)
    return pd.DataFrame(rows)


class LandmarkBoundaryTests(unittest.TestCase):
    def test_window_is_half_open(self):
        self.assertEqual(count_window(np.array([59.,60.,119.,120.]),60,120),2)

    def test_cover_at_landmark_is_not_prior_information(self):
        events=np.array([120.])
        self.assertEqual(count_window(events,60,120),0)
        self.assertEqual(count_window(events,120,180),1)

    def test_past_entry_is_not_a_forward_entry(self):
        self.assertEqual(count_window(np.array([119.]),120,420),0)

    def test_timer_early_fill_and_exclusive_end(self):
        self.assertTrue(outside_timer(9*3600+29*60+57))
        self.assertFalse(outside_timer(9*3600+29*60+58))
        self.assertFalse(outside_timer(9*3600+32*60+59))
        self.assertTrue(outside_timer(9*3600+33*60))

    def test_timer_exposure_counts_seconds_without_double_counting(self):
        self.assertEqual(timer_seconds(9*3600+30*60),180)
        self.assertEqual(timer_seconds(9*3600+29*60+58),182)
        self.assertEqual(timer_seconds(14*3600+35*60),0)


class MatchingTests(unittest.TestCase):
    def test_matching_does_not_use_future_outcomes(self):
        d=synthetic();before,_=match_landmarks(d,'post')
        d.entry5=1-d.entry5;after,_=match_landmarks(d,'post')
        self.assertEqual(before,after)
        self.assertEqual(len(before),1)
        self.assertEqual(before[0]['control_id'],0)

    def test_different_side_session_is_not_a_control(self):
        d=synthetic();d.loc[d.quiet_control.eq(1),'contract']='other_side_or_cycle'
        pairs,excluded=match_landmarks(d,'post')
        self.assertFalse(pairs);self.assertEqual(len(excluded),1)

    def test_no_same_minute_entry_exclusion_applies_to_controls(self):
        d=synthetic();d.loc[[0,2,3],'new_entries_previous_minute']=1
        pairs,_=match_landmarks(d,'post',exclude_simultaneous=True)
        self.assertFalse(pairs)

    def test_strict_activity_requires_matching_recent_entry_state(self):
        d=synthetic();d.loc[1,'new_parent_previous5_positive']=1
        pairs,_=match_landmarks(d,'post',strict_activity=True)
        self.assertFalse(pairs)

    def test_scaling_earlier_rows_does_not_depend_on_later_values(self):
        d=synthetic();d.loc[3,'split']='evaluation'
        before,_=robust_transform(d,'post');d.loc[3,'post_side_equity']=1e10
        after,_=robust_transform(d,'post')
        np.testing.assert_array_equal(before[:3],after[:3])

    def test_week_bootstrap_keeps_constant_paired_difference(self):
        low,high=bootstrap_difference([{'week':str(i)} for i in range(3)],[1.,1.,1.])
        self.assertEqual((low,high),(1.,1.))

    def test_too_few_weeks_does_not_report_a_zero_width_interval(self):
        low,high=bootstrap_difference([{'week':'one'}],[1.])
        self.assertTrue(np.isnan(low) and np.isnan(high))


if __name__=='__main__':unittest.main()
