"""Guard parent reconstruction, minute-boundary pairing and causal features."""
import csv
import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import discover_addition_patterns as study
from analyze_index_triggers import IST


def time(value):
    return datetime.fromisoformat('2026-07-06T'+value).replace(tzinfo=IST)


def order(ot,fill,label='09:30:00',strike=24000,source='1'):
    return dict(underlying='NIFTY',expiry_date='2026-07-07',strike=strike,
                option_type=ot,quantity=65,first_fill_ist=time(fill).isoformat(),
                order_label_ist=time(label).isoformat(),source_rows=source)


class AdditionPatternChecks(unittest.TestCase):
    def test_partial_fills_reconstruct_one_parent_without_exporting_identifiers(self):
        raw=[];fills=[]
        for i,(ot,q,identity) in enumerate([('CE',30,'private-ce'),('CE',35,'private-ce'),('PE',65,'private-pe')],1):
            row=['']*167
            for col,value in {3:'NFO',4:identity,11:'Sell',19:'65',23:'07/06/2026 09:30',166:'private-client'}.items():
                row[col]=value
            raw.append(row)
            fills.append(dict(source=i,t=time(f'09:30:0{i}'),u='NIFTY',expiry=datetime(2026,7,7).date(),
                              strike=24000,ot=ot,side='Sell',q=q,opening=q,reverse_opening=q))
        with TemporaryDirectory() as folder:
            with (Path(folder)/'Trades_GKOHNP140.csv').open('w',newline='') as f:
                csv.writer(f).writerows(raw)
            with patch.object(study,'ROOT',Path(folder)):
                parents,audit=study.parent_orders(fills)
        self.assertEqual(audit['total_parent_orders'],2)
        self.assertEqual([p['quantity'] for p in parents],[65,65])
        self.assertEqual(parents[0]['source_rows'],'1;2')
        self.assertNotIn('private-',json.dumps(parents))

    def test_pair_survives_label_and_execution_minute_boundary(self):
        orders=[order('CE','09:45:59',label='09:45:00'),order('PE','09:46:00',label='09:46:00',source='2')]
        self.assertEqual(study.parent_pairs(orders),[])
        self.assertTrue(study.contains_pair(orders))
        bursts=study.execution_bursts(orders)
        self.assertEqual(len(bursts),1)
        self.assertEqual(bursts[0]['parent_orders'],2)
        self.assertEqual(bursts[0]['ce_quantity'],65)
        self.assertFalse(study.contains_pair([orders[0],order('PE','09:46:00',strike=24050)]))

    def test_second_before_quarter_is_inside_tolerance(self):
        self.assertTrue(study.in_quarter_window(time('13:29:59')))
        self.assertFalse(study.in_quarter_window(time('13:29:57')))
        self.assertTrue(study.in_quarter_window(time('13:32:59')))
        self.assertFalse(study.in_quarter_window(time('13:33:00')))

    def test_features_embargo_current_orders_and_uncompleted_prices(self):
        market=SimpleNamespace(u='NIFTY',expiry='2026-07-07',bar=lambda *a:None,state=lambda *a,**k:None)
        fills=[dict(t=time('09:27:00'),strike=24000,ot='CE',signed=-65,side='Sell',q=65,opening=65),
               dict(t=time('09:29:59'),strike=24000,ot='PE',signed=-65,side='Sell',q=65,opening=65)]
        bars=[dict(t=time(clock),close=price,high=price,low=price) for clock,price in
              [('09:27:00',100),('09:28:00',101),('09:29:00',900)]]
        paired=[dict(event_minute_ist=time('09:27:00').isoformat(),first_leg_time_ist=time('09:27:00').isoformat(),
                     strike=24000,weighted_sold_ce_premium=100,weighted_sold_pe_premium=100),
                dict(event_minute_ist=time('09:29:00').isoformat(),first_leg_time_ist=time('09:29:59').isoformat(),strike=99999)]
        feature=study.FeatureBuilder(market,fills,{('NIFTY','2026-07-06'):bars},paired,
                                     {('2026-07-06','09:28'):100,('2026-07-06','09:29'):999999})
        result=feature.at(time('09:30:00'))
        self.assertEqual(result['short_ce_units'],1)
        self.assertEqual(result['short_pe_units'],0)
        self.assertAlmostEqual(result['spot_return1_pct'],1)
        self.assertEqual(result['time_since_last_pair_min'],2)
        self.assertAlmostEqual(result['equity_pct_capital'],0.0005)
        self.assertEqual(result['drawdown_pct_capital'],0)
        self.assertEqual(result['last_completed_bar_start_ist'],time('09:28:00').isoformat())

    def test_one_cycle_tree_leaf_backs_off_to_supported_parent(self):
        train=[dict(cycle='a',target=1,x=1),dict(cycle='b',target=0,x=0),dict(cycle='c',target=0,x=0)]
        probability,detail=study.train_tree(train,[dict(x=1)],['x'],max_depth=1,min_leaf=1)
        self.assertAlmostEqual(probability[0],0.4)
        self.assertEqual(detail['node_support'][0]['cycles'],3)

    def test_evaluation_target_does_not_enter_clock_probability(self):
        row=dict(underlying='NIFTY',phase='preexpiry',clock='09:30',target=1)
        table=study.clock_table([row])
        self.assertEqual(study.clock_prob(table,{**row,'target':0}),2/3)
        self.assertEqual(study.clock_prob(table,{**row,'target':1}),2/3)

    def test_single_class_metric_does_not_claim_balanced_accuracy(self):
        result=study.metrics([1,1],[0.9,0.9])
        self.assertIsNone(result['balanced_accuracy'])
        self.assertEqual(result['recall'],1)


if __name__=='__main__':
    unittest.main()
