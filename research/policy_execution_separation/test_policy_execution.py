"""Behavioral tests for separated intent and execution, not proof of original rules."""
import json,subprocess,tempfile,unittest,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from model_runner import definitions,policies,mechanics,write_configs
from forensics import atomize,qty_at
from analyse import first_execution_signature

class DefinitionTests(unittest.TestCase):
    def test_small_deterministic_factorial(self):
        self.assertEqual(len(definitions()),84);self.assertEqual(definitions(),definitions())
        self.assertEqual(len({d['model_id'] for d in definitions()}),84)
        self.assertEqual(len(policies()),12);self.assertEqual(len(mechanics()),7)

    def test_mechanics_do_not_change_opening_policy(self):
        self.assertEqual(len({p['opening'] for p in policies()}),1)
        for p in policies():self.assertNotIn('mechanics',p)

    def test_model_serialization_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b';write_configs(definitions(),a);write_configs(definitions(),b);self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_first_execution_does_not_sort_strikes_within_a_minute(self):
        rows=pd.DataFrame([dict(side='Buy',option_type='CE',opening_quantity=65,second=10,source_row=1,strike=26000),dict(side='Buy',option_type='CE',opening_quantity=65,second=12,source_row=2,strike=24500)])
        self.assertEqual(first_execution_signature(rows,'Buy','CE'),dict(strike=26000,source=1,tied_strikes=1))
        rows.loc[1,'second']=10
        self.assertEqual(first_execution_signature(rows,'Buy','CE')['tied_strikes'],2)

    def test_atomic_same_second_and_causal_inventory_lookup(self):
        rows=[]
        for source,t,before,after in [(1,'2026-07-13T09:16:00+05:30',0,-130),(2,'2026-07-13T09:18:00+05:30',-130,-65),(3,'2026-07-13T09:18:00+05:30',-65,0)]:
            rows.append(dict(underlying='NIFTY',expiry_date='2026-07-14',strike=24000,option_type='CE',source_row=source,timestamp_ist=t,parent_id=f'p{source}',quantity_before=before,quantity_after=after))
        history,closures=atomize(pd.DataFrame(rows));rs=next(iter(history.values()))
        self.assertEqual(len(rs),2);self.assertEqual(rs[-1]['before'],-130);self.assertEqual(rs[-1]['after'],0)
        self.assertEqual(closures.iloc[0].closed_quantity,130)
        self.assertEqual(qty_at(rs,rs[-1]['t']-1),-130);self.assertEqual(qty_at(rs,rs[-1]['t']),0)

class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name)
        code='''#define SEPARATED_TEST
#include "SOURCE"
#include <cassert>
Cycle fixture(){Cycle d;d.id=0;d.u=0;d.split=0;d.T=7;d.C=4;d.base=65;d.step=50;d.expiry=20260714;
 d.strike={20000,20000,22000,18000};d.right={0,1,0,1};d.minute={10000,10001,10002,10003,10004,10005,10006};d.clock={555,556,557,558,559,560,561};d.session.assign(7,0);d.phase.assign(7,0);
 d.feature.assign(56,NAN);for(int t=0;t<7;t++){d.feature[t*8]=20000;d.feature[t*8+6]=15;}d.feature[0]=NAN;
 d.prior.assign(28,10);d.open.assign(28,10);d.pvol.assign(28,0);d.vol.assign(28,10);d.delta.assign(28,.2);d.vega.assign(28,1);d.gamma.assign(28,.1);
 d.actual.assign(112,0);d.observed.assign(28,0);d.cash.assign(7,0);return d;}
Config config(){Config c{};c.scale=1;c.budget=.025;c.partial=1;c.capscale=1;return c;}
void conservation(const Execution&r){for(auto&a:r.requests)assert(abs(a.signed_quantity)==a.executed+a.cancelled+a.failed+a.remaining);}
int main(int argc,char**argv){string test=argv[1];Cycle d=fixture();Config c=config();Calibration cal{};Mechanics safe{0,0,0,0,0,0,0,0,0,0,1,120};
 if(test=="opening"){DesiredPolicy p(d,cal,0,0);vector<int>q(4);vector<double>cost(4);double realised[2]={};assert(!p.update(0,q,cost,realised));assert(p.update(1,q,cost,realised));assert((p.target==vector<int>{-195,-195,195,195}));}
 vector<GoalRecord>goals={{600060,1,1,{-195,-195,195,195}},{600180,16,2,{0,0,0,0}}};
 if(test=="cash"){Execution r(d,c,cal,0,0,safe,0,0);r.run_separated(&goals);assert(all_of(r.q.begin(),r.q.end(),[](int x){return x==0;}));assert(abs(r.cash)<1e-8);assert(r.goals.size()==2);conservation(r);}
 if(test=="duplicate"){Mechanics m{4,0,0,0,1,0,1,0,0,0,0,120};Execution r(d,c,cal,0,0,m,0,4);r.run_separated(&goals);bool overshoot=false;for(auto&f:r.fills)if(f.origin=="hypothetical_stale_duplicate"){overshoot=true;assert(abs(f.after)==195);}assert(overshoot);assert(all_of(r.q.begin(),r.q.end(),[](int x){return x==0;}));assert(r.goals.size()==2);assert(abs(r.cash)<1e-8);conservation(r);}
 if(test=="delay"){Mechanics m{2,30,5,2,1,0,0,0,0,0,0,120};Execution r(d,c,cal,0,0,m,0,2);r.run_separated(&goals);assert(!r.fills.empty());assert(r.fills[0].second>=goals[0].second+30);for(auto&f:r.fills){assert(f.second>=f.decision);assert(f.incremental_quantity); }conservation(r);}
 if(test=="reconcile"){Mechanics m{5,2,1,2,1,0,0,5,0,1,1,120};Execution r(d,c,cal,0,0,m,0,5);r.run_separated(&goals);assert(r.goals.size()==2);assert(all_of(r.q.begin(),r.q.end(),[](int x){return x==0;}));for(auto&f:r.fills)assert(abs(f.after)<=195);conservation(r);}
 if(test=="future"){Execution a(d,c,cal,0,0,safe,0,0);a.run_separated(&goals);d.actual.assign(112,999999);d.observed.assign(28,999999);for(int t=4;t<7;t++)for(int j=0;j<4;j++)d.open[t*4+j]=999;Execution b(d,c,cal,0,0,safe,0,0);b.run_separated(&goals);assert(a.fills.size()==b.fills.size());for(size_t i=0;i<a.fills.size();i++)if(a.fills[i].second<600240){assert(a.fills[i].second==b.fills[i].second&&a.fills[i].signedq==b.fills[i].signedq&&a.fills[i].price==b.fills[i].price);}}
 if(test=="determinism"){Execution a(d,c,cal,0,0,safe,0,0),b(d,c,cal,0,0,safe,0,0);a.run_separated();b.run_separated();assert(a.pred==b.pred&&a.q==b.q&&a.cash==b.cash);}
 if(test=="expiry_routine"){DesiredPolicy p(d,cal,1,0);vector<int>q(4);vector<double>cost(4);double realised[2]={};p.update(1,q,cost,realised);q=p.target;d.phase[2]=1;d.clock[2]=556;d.session[2]=1;d.prior[2*4]=100;d.prior[2*4+1]=100;d.prior[2*4+2]=1;d.prior[2*4+3]=1;d.pvol.assign(28,1);for(int role=0;role<4;role++)cal.pool[0][1][0][role]=2;assert(p.update(2,q,cost,realised));assert((p.target==vector<int>{-325,-325,325,325}));}
 if(test=="parent_fragmentation"){Mechanics m{1,0,1,2,1,0,0,0,0,0,1,120};Execution r(d,c,cal,0,0,m,0,1);r.run_separated(&goals);int opening=0,closing=0;for(auto&a:r.requests){if(a.at==goals[0].second){opening++;assert(abs(a.signed_quantity)==65);}if(a.at==goals[1].second){closing++;assert(abs(a.signed_quantity)==195);}}assert(opening==12&&closing==4);conservation(r);}
 if(test=="cancel"){vector<GoalRecord>g={{600060,1,1,{-1950,0,0,0}},{600120,16,2,{0,0,0,0}}};Mechanics m{3,30,5,2,0,2,0,0,0,0,0,120};Execution r(d,c,cal,0,0,m,0,3);r.run_separated(&g);int cancelled=0;for(auto&a:r.requests)cancelled+=a.cancelled;assert(cancelled>0);assert(all_of(r.q.begin(),r.q.end(),[](int x){return x==0;}));conservation(r);}
 if(test=="missing"){d.open.assign(28,NAN);Execution r(d,c,cal,0,0,safe,0,0);r.run_separated(&goals);assert(r.fills.empty());assert(r.cash==0);conservation(r);}
}
'''.replace('SOURCE',str(HERE/'execution.cpp')).replace('assert(f.incremental_quantity);','assert(abs(f.signedq)%65==0);')
        p=cls.path/'test.cpp';p.write_text(code)
        subprocess.run(['g++','-O2','-std=c++17',str(p),'-o',str(cls.path/'test')],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def check(self,name):subprocess.run([str(self.path/'test'),name],check=True)
    def test_initial_geometry_uses_only_completed_spot_not_option_volume(self):self.check('opening')
    def test_inventory_and_cash_conservation(self):self.check('cash')
    def test_duplicate_is_execution_not_new_policy_goal(self):self.check('duplicate')
    def test_delays_and_partial_base_slices(self):self.check('delay')
    def test_pending_aware_reconciliation(self):self.check('reconcile')
    def test_future_targets_and_prices_cannot_change_earlier_fills(self):self.check('future')
    def test_deterministic_replay(self):self.check('determinism')
    def test_expiry_0916_is_routine_addition_not_another_seed(self):self.check('expiry_routine')
    def test_base_parent_orders_are_distinct_from_child_partial_fills(self):self.check('parent_fragmentation')
    def test_cancellation_and_partial_fill_quantity_conservation(self):self.check('cancel')
    def test_missing_quotes_do_not_fill(self):self.check('missing')

if __name__=='__main__':unittest.main()
