"""AND/OR search, model-owned counters and conditional selector leakage guards."""
import unittest
import numpy as np
from datetime import datetime,timedelta
from types import SimpleNamespace

from search_rule_combinations import temporal_filter,beam_search
from search_exit_combinations import condition,first_crossings
from search_conditional_hedges import fit_piecewise,predict_piecewise
from search_sizing_configuration import quantity_score,best_break
from search_joint_entry_exit import active_clock,apply_exit_lock
from check_combo_markouts import basket_markout
from analyze_index_triggers import IST
from export_historical_mimic import fit_model,predict_model
from search_hedge_liquidity import predict as liquidity_prediction


class CombinationChecks(unittest.TestCase):
    def rows(self):
        return [dict(cycle=day,date=day,clock=clock,x_short_units=1) for day in ('a','b','c') for clock in ('09:30','09:31','09:32','09:33')]

    def test_cooldown_uses_predicted_signals_and_resets_per_session(self):
        rows=self.rows();p=temporal_filter(rows,np.ones(len(rows),dtype=bool),cooldown=2,maximum=2)
        np.testing.assert_array_equal(p,[True,False,True,False]*3)

    def test_position_cap_is_prior_book_state_not_current_target_size(self):
        rows=[dict(cycle='a',date='a',clock='09:30',x_short_units=20,target_quantity=1),
              dict(cycle='a',date='a',clock='09:31',x_short_units=19,target_quantity=999)]
        np.testing.assert_array_equal(temporal_filter(rows,[True,True],position_cap=20),[False,True])

    def test_clock_can_participate_in_a_boolean_combination(self):
        rows=self.rows();truth=np.array([True,False,False,False]*3);clock=np.array([True,True,False,False]*3);atom=np.array([True,False,True,False]*3)
        trials=[];catalog=[dict(field='a',text='A')]
        _,_,_=beam_search(rows,truth,np.arange(12),clock,[atom],catalog,trials,'t','p',pool_size=4,width=4)
        self.assertTrue(any(r['kind']=='boolean_combination' and 'CLOCK' in r['expression'] and r['f1']==1 for r in trials))

    def test_profit_activation_is_required_before_trailing_exit(self):
        atom=dict(kind='activated_trail',scope='net_equity',activation=.5,trail=.2)
        self.assertTrue(condition(atom,dict(net_equity_pct_capital=.4,net_equity_drawdown_pct_capital=-.2)))
        self.assertFalse(condition(atom,dict(net_equity_pct_capital=-.1,net_equity_drawdown_pct_capital=-.2)))
        self.assertFalse(condition(atom,dict(net_equity_pct_capital=.6,net_equity_drawdown_pct_capital=0)))

    def test_missing_conditional_hedge_feature_uses_parent_budget(self):
        tree=dict(default_rule=3,field='iv',threshold=15,left=dict(default_rule=1),right=dict(default_rule=2))
        np.testing.assert_array_equal(predict_piecewise(tree,{'iv':np.array([np.nan,10,20])},3),[3,1,2])

    def test_hedge_split_fitting_does_not_read_later_target_matches(self):
        events=[dict(expiry_date=str(i//2)) for i in range(8)]
        hits=np.array([[1,1,0,0,1,1,0,0],[0,0,1,1,0,0,1,1]],dtype=bool)
        features={'x':np.array([0,0,1,1,0,0,1,1],dtype=float)};train=np.arange(6);w=np.ones(8)
        first,_=fit_piecewise(events,hits,features,train,w,{'x':[.5]},max_depth=1,min_events=1,min_cycles=1)
        hits[:,6:]=~hits[:,6:]
        second,_=fit_piecewise(events,hits,features,train,w,{'x':[.5]},max_depth=1,min_events=1,min_cycles=1)
        self.assertEqual(first,second)

    def test_sizing_penalizes_false_allocations_and_missed_allocations(self):
        rows=[dict(cycle='a'),dict(cycle='b')]
        result=quantity_score(rows,['0|0','1|1'],['1|1','0|0'])
        self.assertEqual(result['false_positive_allocations'],1)
        self.assertEqual(result['missed_allocations'],1)
        self.assertEqual(result['exact_rate'],0)

    def test_retrospective_break_requires_observations_on_both_sides(self):
        r=best_break([1,1,1,0,0,0],list('abcdef'),True)
        self.assertEqual(r['first_later_date'],'d')
        self.assertEqual(r['residual_loss'],0)

    def test_active_clock_excludes_closed_books_and_later_labels(self):
        rows=[dict(underlying='NIFTY',phase='expiry',clock='09:30',cycle=str(i),split='calibration',x_short_units=q,y=y)
              for i,(q,y) in enumerate([(1,1),(0,0),(0,0)])]
        rows.append(dict(underlying='NIFTY',phase='expiry',clock='09:30',cycle='later',split='evaluation',x_short_units=1,y=0))
        first=active_clock(rows,list(range(4)),'y');rows[-1]['y']=1
        np.testing.assert_array_equal(first,active_clock(rows,list(range(4)),'y'))
        self.assertTrue(first[-1]);self.assertFalse(first[1])

    def test_stop_cooldown_and_permanent_lock_are_distinct_programs(self):
        rows=[dict(underlying='NIFTY',expiry_date='e',clock=c) for c in ('09:30','09:35','09:45')]
        stop={('NIFTY','e'):570}
        np.testing.assert_array_equal(apply_exit_lock(rows,np.ones(3,dtype=bool),stop,'5'),[False,True,True])
        np.testing.assert_array_equal(apply_exit_lock(rows,np.ones(3,dtype=bool),stop,'day_lock'),[False,False,False])

    def economic_fixture(self):
        t=datetime(2026,7,7,9,30,tzinfo=IST);day='2026-07-07';quotes={}
        for strike,right,price in [(100,'CE',4),(100,'PE',4),(150,'CE',.1),(50,'PE',.1)]:
            quotes[(day,strike,right)]={c:dict(open=price,close=price,volume=100) for c in ('09:29','09:31','09:46')}
        market=SimpleNamespace(quotes=quotes,bar=lambda d,k,o,c:quotes.get((d,k,o),{}).get(c))
        index={('NIFTY',day):[dict(t=t-timedelta(minutes=1),close=100)]}
        return t,market,index

    def test_premium_credit_is_not_profit_when_prices_do_not_change(self):
        t,market,index=self.economic_fixture();r,reason=basket_markout(market,index,'NIFTY','2026-07-07',t,'15_minutes')
        self.assertIsNone(reason);self.assertEqual(r['gross_pnl'],0)
        self.assertLess(r['net_pnl'],0)
        self.assertEqual(r['short_strike'],100)
        self.assertAlmostEqual(r['theoretical_expiry_tail_loss'],(50-7.8)*65)

    def test_missing_markout_quote_is_excluded_not_replaced(self):
        t,market,index=self.economic_fixture();market.quotes[('2026-07-07',150,'CE')].pop('09:46')
        r,reason=basket_markout(market,index,'NIFTY','2026-07-07',t,'15_minutes')
        self.assertIsNone(r);self.assertEqual(reason,'missing_exit_open')

    def test_exported_curve_fit_is_executable_with_missing_inputs(self):
        rows=[dict(a=0,b=None),dict(a=1,b=3),dict(a=2,b=None),dict(a=3,b=8)]
        y=np.array([False,False,True,True]);model,_=fit_model(rows,y,['a','b'])
        self.assertEqual(predict_model(model,rows),y.tolist())
        self.assertEqual(model['historical_exact_rate'],1)

    def test_oi_eligibility_changes_hedge_choice_without_a_target_strike_input(self):
        p=np.array([[2.,1.5]]);k=np.array([[150,200]]);volume=np.array([[100,100]]);oi=np.array([[50,500]])
        ref=np.array([100.]);base=(.025,0,'none','ceiling',0,0);filtered=(.025,0,'none','ceiling',0,100)
        self.assertEqual(liquidity_prediction(p,k,volume,oi,ref,base)[0],150)
        self.assertEqual(liquidity_prediction(p,k,volume,oi,ref,filtered)[0],200)


if __name__=='__main__':unittest.main()
