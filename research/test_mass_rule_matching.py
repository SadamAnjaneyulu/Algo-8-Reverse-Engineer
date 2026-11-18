"""Checks for causal indicators, parent roles, unique hedge matching and exits."""
import csv
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import audit_strike_hedge_rules as audit
import mass_match_strategy_rules as mass
from strategy_rule_features import indicator_arrays,smooth
from analyze_index_triggers import IST
from scan_carried_contract_rules import remaining_entry_references,contract_signal
from scan_hedge_leg_ratios import select as select_ratio,key as ratio_event_key


def t(clock):return datetime.fromisoformat('2026-07-07T'+clock).replace(tzinfo=IST)


class MassRuleChecks(unittest.TestCase):
    def test_all_indicators_are_prefix_invariant(self):
        prices=[100+i*.1+(i%5)*.03 for i in range(120)]
        bars=[dict(close=p,open=p-.02,high=p+.1,low=p-.1) for p in prices]
        prefix=indicator_arrays(bars[:70],99)
        altered=indicator_arrays(bars[:70]+[dict(close=9999,open=9999,high=99999,low=1)]*50,99)
        for key in prefix:
            np.testing.assert_allclose(prefix[key],altered[key][:70],equal_nan=True,err_msg=key)

    def test_wilder_rsi_uptrend_flat_and_warmup(self):
        def bars(prices):return [dict(close=p,open=p,high=p,low=p) for p in prices]
        up=indicator_arrays(bars(range(100,140)))['rsi_14']
        flat=indicator_arrays(bars([100]*40))['rsi_14']
        self.assertTrue(np.isnan(up[:14]).all())
        self.assertEqual(up[14],100)
        self.assertEqual(flat[14],50)
        np.testing.assert_allclose(smooth([1,2,3,4],3),[np.nan,np.nan,2,8/3],equal_nan=True)

    def test_cross_requires_an_observed_prior_value(self):
        values=np.array([np.nan,60,40,np.nan,60,40])
        previous=np.array([-1,0,1,2,3,4])
        pr=mass.predicate(values,'le',50,'cross',previous)
        np.testing.assert_array_equal(pr,[False,False,True,False,False,True])

    def test_incomplete_parent_retains_only_observed_quantity(self):
        raw=['']*167
        for col,value in {3:'NFO',4:'private-order',19:'340',23:'07/07/2026 09:30'}.items():raw[col]=value
        fill=dict(source=1,t=t('09:30:01'),u='SENSEX',expiry=datetime(2026,7,9).date(),strike=72000,
                  ot='CE',side='Buy',q=40,opening=40,reverse_opening=40,price=2)
        with TemporaryDirectory() as folder:
            with (Path(folder)/'Trades_GKOHNP140.csv').open('w',newline='') as f:csv.writer(f).writerow(raw)
            with patch.object(audit,'ROOT',Path(folder)):parents=audit.reconstruct_parents([fill])
        self.assertEqual(parents[0]['quantity'],40)
        self.assertEqual(parents[0]['requested_quantity'],340)
        self.assertFalse(parents[0]['fully_observed_filled'])
        self.assertEqual(parents[0]['role'],'new_long')
        self.assertNotIn('private-order',str(parents))

    def test_each_hedge_parent_matches_at_most_one_short_batch(self):
        def batch(clock,name):
            return dict(underlying='NIFTY',expiry_date='2026-07-07',date='2026-07-07',event_id=name,
                        parents=[dict(first=t(clock))])
        def buy(clock):return dict(underlying='NIFTY',expiry_date='2026-07-07',role='new_long',first=t(clock))
        matched,ambiguous=audit.assign_new_longs([batch('09:30:00','a'),batch('09:30:10','b')],[buy('09:30:04'),buy('09:30:05')])
        self.assertEqual(len(matched['a']),1)
        self.assertEqual(len(matched['b']),0)
        self.assertEqual(ambiguous,1)

    def test_fixed_gap_does_not_substitute_unquoted_neighbor(self):
        event=dict(option_type='CE',atm=24000,spot=24001,last_short=24050)
        candidates=[dict(strike=26050,price=2,abs_delta=.01)]
        self.assertIsNone(audit.choose_strike(event,candidates,'atm_fixed_gap',2000,'NIFTY'))
        self.assertEqual(audit.choose_strike(event,candidates,'last_short_fixed_gap',2000,'NIFTY'),26050)

    def test_premium_ceiling_floor_are_different_rules(self):
        event=dict(option_type='CE',spot=24000)
        candidates=[dict(strike=24500,price=2.5),dict(strike=24600,price=1.5)]
        self.assertEqual(audit.choose_strike(event,candidates,'premium_ceiling',2,'NIFTY'),24600)
        self.assertEqual(audit.choose_strike(event,candidates,'premium_floor',2,'NIFTY'),24500)

    def test_exit_uses_first_known_crossing_and_never_observed_exit_label(self):
        cycle=dict(fallback=t('15:29'),target=t('10:00').isoformat(),
            path=[dict(t=t('09:16'),x=None,zero_volume=False),dict(t=t('09:17'),x=-.4,zero_volume=True),
                  dict(t=t('09:18'),x=-.6,zero_volume=False)])
        self.assertEqual(mass.predict_exit(cycle,'x',-.3,'le'),t('09:17'))
        self.assertEqual(mass.predict_exit(cycle,'x',-.3,'le',fresh=True),t('09:18'))
        changed={**cycle,'target':t('14:00').isoformat()}
        self.assertEqual(mass.predict_exit(cycle,'x',-.5,'le'),mass.predict_exit(changed,'x',-.5,'le'))
        self.assertEqual(mass.predict_exit(cycle,'x',-1,'le'),t('15:29'))

    def test_clock_training_excludes_own_cycle_and_evaluation_labels(self):
        rows=[dict(underlying='NIFTY',phase='expiry',clock='09:30',cycle='a',split='calibration',y=1),
              dict(underlying='NIFTY',phase='expiry',clock='09:30',cycle='b',split='calibration',y=0),
              dict(underlying='NIFTY',phase='expiry',clock='09:30',cycle='c',split='evaluation',y=1)]
        original=mass.clock_predictions(rows,[0,1,2],'y')
        rows[2]['y']=0
        np.testing.assert_array_equal(original,mass.clock_predictions(rows,[0,1,2],'y'))
        self.assertFalse(original[0]);self.assertTrue(original[1])

    def test_early_execution_tolerance_preserves_feature_embargo(self):
        event=t('13:29:59');decision=mass.normalized_decision_minute(event)
        self.assertEqual(decision,t('13:30'))
        self.assertLess(decision-timedelta(minutes=1),event)

    def test_residual_cost_references_expose_fifo_lifo_ambiguity(self):
        rows=[dict(side='Sell',opening=100,reverse_opening=100,q=100,price=10),
              dict(side='Sell',opening=100,reverse_opening=100,q=100,price=20),
              dict(side='Buy',opening=0,reverse_opening=0,q=100,price=15)]
        r=remaining_entry_references(rows)
        self.assertEqual(r['fifo_entry'],20)
        self.assertEqual(r['lifo_entry'],10)
        self.assertEqual(r['pooled_entry'],15)
        self.assertEqual(r['tracked_short_quantity'],100)

    def test_stated_four_percent_stop_can_gap_at_open_without_future_volume(self):
        row=dict(previous_close=100,fallback=t('15:29'),prices=[dict(t=t('09:15'),price=104,opening=True),
             dict(t=t('09:16'),price=103,opening=False)])
        self.assertEqual(contract_signal(row,'previous_close','fixed_stop',4,opening=True),t('09:15'))
        self.assertEqual(contract_signal(row,'previous_close','fixed_stop',4,opening=False),t('15:29'))

    def test_short_strike_keeps_an_already_known_same_window_reference(self):
        e=dict(previous_same_window_strike=24000,spot_lag_1=24060)
        self.assertEqual(audit.short_strike_prediction(e,('previous_same_window_strike','identity',0),'NIFTY'),24000)
        self.assertEqual(audit.short_strike_prediction(e,('spot_lag_1','nearest',0),'NIFTY'),24050)

    def test_directional_strike_candidate_uses_only_completed_price_change(self):
        e=dict(spot_lag_1=24012,completed_change_10=15)
        self.assertEqual(audit.short_strike_prediction(e,('momentum_shift_10','nearest',1),'NIFTY'),24050)
        self.assertEqual(audit.short_strike_prediction({**e,'completed_change_10':-15},('momentum_shift_10','nearest',1),'NIFTY'),23950)

    def test_two_signals_cannot_both_claim_the_same_later_event(self):
        rows=[dict(cycle='a',date='2026-07-07',clock='09:30'),dict(cycle='a',date='2026-07-07',clock='09:31')]
        result=mass.tolerant_event_score(rows,[False,True],[True,True])
        self.assertEqual(result['matched_events'],1)
        self.assertEqual(result['signals'],2)
        self.assertEqual(result['precision'],.5)

    def test_faster_features_relabel_early_fill_to_its_physical_minute(self):
        base=dict(underlying='NIFTY',expiry_date='2026-07-07',cycle='a',date='2026-07-07',phase='expiry',split='evaluation',
                  paired_sale=0,short_cover=0,new_long=0,cover_quantity=0,long_quantity=0,quarter_target=None,off_quarter=1)
        rows=[dict(base,clock='13:29',feature_cutoff_ist=t('13:28').isoformat(),last_completed_bar_start_ist=t('13:27').isoformat(),known_quantity=5),
              dict(base,clock='13:30',feature_cutoff_ist=t('13:29').isoformat(),last_completed_bar_start_ist=t('13:28').isoformat(),known_quantity=7)]
        parent=dict(underlying='NIFTY',expiry_date='2026-07-07',role='new_long',first=t('13:29:59'),quantity=65)
        result=mass.faster_feature_alignment(rows,[parent])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['clock'],'13:29')
        self.assertEqual(result[0]['feature_cutoff_ist'],t('13:29').isoformat())
        self.assertEqual(result[0]['new_long'],1)
        self.assertEqual(result[0]['known_quantity'],7)

    def test_relative_hedge_budget_changes_when_atm_premium_changes(self):
        chain=[dict(strike=24500,price=4,volume=100),dict(strike=24600,price=2,volume=100)]
        self.assertEqual(select_ratio(chain,100*.025,'ceiling',24000),24600)
        self.assertEqual(select_ratio(chain,200*.025,'ceiling',24000),24500)

    def test_candidate_quote_join_keeps_bought_contract_distinct(self):
        event=dict(underlying='NIFTY',expiry_date='2026-07-07',t=t('09:30').isoformat(),option_type='CE',strike=24600)
        quote=dict(underlying='NIFTY',expiry_date='2026-07-07',event_time_ist=t('09:30').isoformat(),option_type='CE',bought_strike=24600,strike=24500)
        self.assertEqual(ratio_event_key(event),ratio_event_key(quote))


if __name__=='__main__':unittest.main()
