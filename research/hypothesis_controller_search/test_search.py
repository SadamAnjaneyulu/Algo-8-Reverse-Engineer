"""Tests establish engine behavior, not correctness of a recovered controller."""
import json,sys,tempfile,unittest,subprocess
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import search
from evaluate import matched_actions,timestamp,decode_book
from prepare import HERE,CACHE,ROOT,OUT,split,mode


class GrammarAndScoreTests(unittest.TestCase):
    def test_deterministic_definitions_and_count(self):
        a=search.main_bank();b=search.main_bank()
        self.assertEqual(len(a),13824);self.assertEqual([search.key(c) for c in a],[search.key(c) for c in b])
        self.assertEqual(len(set(search.key(c) for c in a)),13824)

    def test_fit_validation_cycle_separation(self):
        self.assertEqual([split(s) for s in ['2026-07-31','2026-08-01','2026-08-31','2026-09-01']],[0,1,1,2])

    def test_tied_mode_is_reproducible(self):self.assertEqual(mode([3,2,3,2]),2)

    def test_false_and_missed_events_reduce_score(self):
        row={f'{name}{r}':value for r in range(4) for name,value in [('pred',4),('actual',6),('match',2)]}
        row.update(qdenom=10,qerror=6,inventory_denom=10,inventory_error=5,final_target=0,final_match=0)
        d=search.with_metrics(pd.DataFrame([row])).iloc[0]
        self.assertAlmostEqual(d.precision0,.5);self.assertAlmostEqual(d.recall0,1/3);self.assertAlmostEqual(d.event_macro_f1,.4)
        self.assertAlmostEqual(d.quantity_score,.4);self.assertAlmostEqual(d.inventory_score,.5)
        self.assertTrue(np.isnan(d.final_score))
        self.assertAlmostEqual(d.primary_raw,(.4*.4+.2*.4+.3*.5)/.9)

    def test_unavailable_final_target_does_not_become_correct(self):
        row={f'{name}{r}':value for r in range(4) for name,value in [('pred',0),('actual',2),('match',0)]}
        row.update(qdenom=8,qerror=8,inventory_denom=8,inventory_error=8,final_target=0,final_match=0)
        self.assertEqual(search.with_metrics(pd.DataFrame([row])).iloc[0].primary_raw,0)

    def test_complexity_increases_for_extra_branches(self):
        a=search.base_config();b=dict(a,gate=1,reentry=2,latency=1)
        self.assertGreater(search.complexity(b),search.complexity(a))

    def test_one_to_one_matching_counts_false_and_missed_actions(self):
        def action(t,k=100):return dict(minute=t,strike=k,right=0,action=0,quantity=65)
        pairs,extra,miss=matched_actions([action(10),action(10),action(20,150)],[action(11),action(30)],2)
        self.assertEqual(pairs,[(0,0)]);self.assertEqual(extra,[1,2]);self.assertEqual(miss,[1])

    def test_tolerances_are_evaluated_independently(self):
        def action(t):return dict(minute=t,strike=100,right=0,action=0,quantity=65)
        p=[action(10)];a=[action(8),action(10)]
        self.assertEqual(matched_actions(p,a,2)[0],[(0,0)])
        self.assertEqual(matched_actions(p,a,0)[0],[(0,1)])

    def test_timestamp_conversion_and_sparse_book_roundtrip(self):
        self.assertEqual(timestamp(0),'1970-01-01T05:30:00+05:30')
        self.assertEqual(decode_book('[100:0:-65;200:1:20]'),{(100,0):-65,(200,1):20})

    def test_saved_definition_preserves_parameters(self):
        c=search.main_bank()[738]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'c.json';path.write_text(json.dumps(c));self.assertEqual(search.key(c),search.key(json.loads(path.read_text())))


class KernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        source=HERE/'replay.cpp'
        harness='''#define main replay_program_main
#include "SOURCE"
#undef main
#include <cassert>
int main(){
 Cycle d;d.T=5;d.C=2;d.base=65;d.step=50;d.u=0;d.expiry=20260707;
 d.strike={100,150};d.right={0,0};d.minute={1,2,3,4,5};d.clock={556,557,558,559,560};d.session={0,0,0,0,0};d.phase={0,0,0,0,0};
 d.feature.resize(40,NAN);for(int t=0;t<5;t++){d.feature[t*8]=100;d.feature[t*8+6]=15;}
 d.prior.assign(10,10);d.open.assign(10,10);d.pvol.assign(10,1);d.vol.assign(10,1);d.delta.assign(10,.5);d.vega.assign(10,1);d.gamma.assign(10,.1);
 d.actual.assign(40,0);d.observed.assign(10,0);d.cash.assign(5,0);
 Config c{};c.scale=1;c.budget=.025;c.capscale=1;c.partial=1;Calibration cal{};
 Replay r(d,c,cal);
 // Long/short costs, partial cover and a sign reversal at supplied prices.
 r.fill(0,0,-195,0,1,100);r.fill(1,0,65,0,2,120);
 assert(r.q[0]==-130 && abs(r.realized+1300)<1e-8);
 r.fill(2,0,260,0,2,90);assert(r.q[0]==130 && abs(r.realized)<1e-8 && abs(r.cost[0]-90)<1e-8);
 assert(abs(r.cash+11700)<1e-8);
 // A safe close cannot reverse a flat book even when repeated.
 r.fill(3,0,-130,1,2,95);r.fill(3,0,-130,1,2,95);assert(r.q[0]==0);
 // Missing quote cannot silently fill.
 d.open[8]=NAN;r.fill(4,0,-65,0,1);assert(r.q[0]==0 && r.unfilled_by_time[4]==1);
 // Allocation uses preceding quotes, not a future execution open for strike selection.
 d.open[0]=99999;assert(r.atm(0,0)==0);d.feature[0]=149;assert(r.atm(0,0)==1);
 // Latency request remains pending, without reading future fill prices as a signal.
 c.latency=1;Replay pending(d,c,cal);pending.request(0,0,-65,0,1);assert(pending.q[0]==0 && pending.queue.size()==1 && pending.queue[0].t==1);
 // Same-second child sequencing changes attribution, not final net/cash.
 Replay a(d,c,cal),b(d,c,cal);a.fill(0,0,-130,0,1,100);b.fill(0,0,-130,0,1,100);
 a.fill(1,0,65,0,2,110);a.fill(1,0,-65,0,1,105);
 b.fill(1,0,-65,0,1,105);b.fill(1,0,65,0,2,110);
 assert(a.q==b.q && abs(a.cash-b.cash)<1e-8 && abs(a.realized-b.realized)>1e-8);
 // Changing future historical targets cannot alter autonomous decisions.
 d.strike[1]=2100;d.feature[0]=100;d.open.assign(10,10);c.latency=0;c.wing=2;for(int r=0;r<4;r++)cal.clock[0][0][0][r]=3;
 Replay autonomous(d,c,cal);autonomous.run();assert(accumulate(autonomous.pred.begin(),autonomous.pred.end(),0)>0);
 d.observed.assign(10,999999);d.actual.assign(40,999999);Replay other(d,c,cal);other.run();assert(autonomous.pred==other.pred);

}
'''.replace('SOURCE',str(source))
        path=cls.folder/'check.cpp';path.write_text(harness)
        subprocess.run(['g++','-O2','-std=c++17',str(path),'-o',str(cls.folder/'check')],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_accounting_ties_missing_prices_granularity_and_pending_orders(self):subprocess.run([str(self.folder/'check')],check=True)


if __name__=='__main__':unittest.main()
