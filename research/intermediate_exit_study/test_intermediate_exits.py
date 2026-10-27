"""Causal boundaries, accounting, matching, grouping and cycle separation."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
# Give modules unique names when unittest discovery imports other build/evaluate modules.
spec=importlib.util.spec_from_file_location('exit_study_build',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
# evaluate's local import intentionally resolves to this module for this test import.
prior=sys.modules.get('build');sys.modules['build']=build
spec=importlib.util.spec_from_file_location('exit_study_evaluate',HERE/'evaluate.py');ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)
if prior is None:sys.modules.pop('build',None)
else:sys.modules['build']=prior

class ExitStudyTests(unittest.TestCase):
    def fill(self,source,t,before,after,price,side,opening,closing):
        quantity=abs(after-before)
        return SimpleNamespace(source_row=source,second=t,quantity_before=before,quantity_after=after,execution_price=price,side=side,
            opening_quantity=opening,closing_quantity=closing,cash_change=(-1 if side=='Buy' else 1)*quantity*price,
            average_cost_after=price if before==0 else 15 if after==-10 else 0,parent_id=f'p{source}')
    def test_book_cash_and_lot_attribution(self):
        b=build.Book(1);b.apply(self.fill(1,10,0,-10,10,'Sell',10,0),0,0,100)
        b.apply(self.fill(2,20,-10,-20,20,'Sell',10,0),0,0,110)
        b.apply(self.fill(3,30,-20,-10,15,'Buy',0,10),0,0,105)
        self.assertEqual(b.q[0],-10);self.assertEqual(b.cash[0],150)
        self.assertEqual(b.fifo[0][0]['price'],20);self.assertEqual(b.lifo[0][0]['price'],10)
    def risk(self):
        return pd.DataFrame([dict(cycle_id=1,underlying='NIFTY',expiry_date='2026-06-30',date='2026-06-29',phase='preexpiry',strike=24000,option_type='CE',
            second=1000+60*i,short_units=3,known_initialization=True,last_contract_add_seconds=60+60*i,epoch_start_ist='epoch') for i in range(10)])
    def test_persistent_threshold_does_not_emit_every_minute(self):
        r=self.risk();self.assertEqual(len(ev.signals(r,np.ones(len(r),bool))),1)
    def test_new_allocation_rearms_after_refractory(self):
        r=self.risk();r.loc[6:,'last_contract_add_seconds']=np.arange(4)*60+1
        self.assertEqual(ev.signals(r,np.ones(len(r),bool)).second.tolist(),[1000,1360])
    def test_future_risk_rows_do_not_change_past_signals(self):
        r=self.risk();a=ev.signals(r.iloc[:5],np.ones(5,bool));b=ev.signals(r,np.ones(10,bool))
        pd.testing.assert_frame_equal(a,b[b.second<=1240])
    def test_missing_feature_abstains(self):
        r=pd.DataFrame({'premium_loss_pct':[np.nan,49,50,70]});state,valid=ev.masks(r,'premium_loss50')
        self.assertEqual(state.tolist(),[False,False,True,True]);self.assertEqual(valid.tolist(),[False,True,True,True])
    def test_allocation_condition_requires_past_allocation(self):
        r=pd.DataFrame({'premium_loss_pct':[-50,-50,-50,-50],'last_side_add_seconds':[0,1,120,121]})
        self.assertEqual(ev.masks(r,'allocation_profit25')[0].tolist(),[False,True,True,False])
    def test_chronological_matching_maximum_cardinality(self):
        p=pd.DataFrame([dict(cycle_id=0,strike=1,option_type='CE',second=t) for t in [100,200]])
        a=pd.DataFrame([dict(cycle_id=0,strike=1,option_type='CE',second=t,event_id=str(t)) for t in [190,290]])
        pairs,false,miss=ev.match(p,a,100);self.assertEqual((len(pairs),len(false),len(miss)),(2,0,0))
    def test_matching_never_crosses_contract_or_cycle(self):
        p=pd.DataFrame([dict(cycle_id=0,strike=1,option_type='CE',second=100)])
        a=pd.DataFrame([dict(cycle_id=1,strike=1,option_type='CE',second=100)])
        self.assertEqual(ev.metrics(p,a)['matched'],0)
    def test_cover_episode_groups_partials_but_splits_new_allocation(self):
        start=build.sec('2026-06-29T10:00:00+05:30');rows=[]
        for i,(offset,side,before,after,opening,closing) in enumerate([
            (-100,'Sell',0,-130,130,0),(0,'Buy',-130,-65,0,65),
            (60,'Buy',-65,0,0,65),(90,'Sell',0,-65,65,0),(110,'Buy',-65,0,0,65)]):
            rows.append(dict(cycle_id=1,strike=24000,option_type='CE',second=start+offset,side=side,
                opening_quantity=opening,closing_quantity=closing,quantity_before=before,quantity_after=after,
                source_row=i+1,parent_id=f'p{i+1}',tie_sensitive_role=False,incremental_quantity=abs(after-before)))
        old=build.HERE
        with tempfile.TemporaryDirectory() as tmp:
            try:build.HERE=Path(tmp);atoms,episodes=build.make_events(pd.DataFrame(rows))
            finally:build.HERE=old
        self.assertEqual(len(atoms),3);self.assertEqual(episodes.cover_quantity.tolist(),[130,65])
    def test_baseline_fallback_uses_training_only(self):
        r=self.risk();r['time_bin5']=r.second//300
        e=r.iloc[[0,4]].copy();e['clock_minute']=e.time_bin5*5
        params=ev.fit_baselines(r,e)
        self.assertEqual(params['inventory_only'][('ALL','ALL','ALL')],3)
        test=r.copy();test['underlying']='UNSEEN'
        self.assertGreater(len(ev.baseline_predictions(test,params,'inventory_only')),0)
    def test_all_cover_quantity_preserved(self):
        children=pd.read_csv(HERE/'short_cover_children.csv.gz');atoms=pd.read_csv(HERE/'short_cover_atoms.csv.gz');cases=pd.read_csv(HERE/'exit_case_ledger.csv.gz')
        self.assertEqual(len(children),11716);self.assertEqual(len(atoms),8197)
        self.assertEqual(children.closing_quantity.sum(),atoms.cover_quantity.sum());self.assertEqual(atoms.cover_quantity.sum(),cases.cover_quantity.sum())
        self.assertTrue(children.source_row.is_unique);self.assertTrue(atoms.atom_id.is_unique);self.assertTrue(cases.event_id.is_unique)
    def test_strict_feature_availability(self):
        for name in ['exit_case_ledger.csv.gz','pre_event_risk_set.csv.gz','motif_pre_event_features.csv']:
            d=pd.read_csv(HERE/name)
            available=pd.to_datetime(d.market_available_at_ist);cutoff=pd.to_datetime(d.feature_cutoff_ist)
            self.assertTrue((available<=cutoff).all())
            valid=d.latest_fill_available_before_ist.notna()
            self.assertTrue((pd.to_datetime(d.loc[valid,'latest_fill_available_before_ist'])<cutoff[valid]).all())
    def test_independent_pre_event_book_prefix(self):
        d=pd.read_csv(HERE/'exit_case_ledger.csv.gz');f=build.load_fills()
        for r in d.iloc[::300].itertuples():
            past=f[(f.cycle_id==r.cycle_id)&(f.second<r.second)]
            q=past[(past.strike==r.strike)&(past.option_type==r.option_type)].tail(1)
            self.assertEqual(r.snapshot_quantity_before,int(q.quantity_after.iloc[0]) if len(q) else 0)
            side=past[past.option_type==r.option_type];positions=side.groupby('strike').tail(1)
            z=np.load(build.market_cache()/f'cycle_{r.cycle_id:02}.npz');ti=int(np.flatnonzero(z['minutes']==r.second//60)[0]);lookup={(k,'PE' if rr else 'CE'):j for j,(k,rr) in enumerate(zip(z['strikes'],z['rights']))}
            marks=[(x.quantity_after,z['previous'][ti,lookup[(x.strike,x.option_type)]]) for x in positions.itertuples() if x.quantity_after]
            if all(np.isfinite(v) for q,v in marks):self.assertAlmostEqual(r.side_equity_rupees,side.cash_change.sum()+sum(q*float(v) for q,v in marks),places=4)
    def test_controls_are_unique_and_outcome_separated(self):
        p=pd.read_csv(HERE/'matched_nonexit_controls.csv');self.assertTrue(p.control_id.is_unique)
        self.assertTrue(p.quantity_ratio.between(.5,2).all());self.assertTrue(p.time_difference_seconds.abs().le(3600).all())
        pool=pd.read_csv(HERE/'control_pool_audit.csv.gz').set_index('observation_id');self.assertFalse(pool.loc[p.control_id,'near_cover'].any())
        primary=p[p.tier=='same_contract'];self.assertTrue(primary.case_strike.eq(primary.control_strike).all())
    def test_cycle_exclusion_and_chronology(self):
        d=pd.read_csv(HERE/'validation_folds.csv')
        for r in d.itertuples():
            train=list(map(int,r.training_cycles.split(';')));self.assertNotIn(r.test_cycle_id,train)
            if r.mode=='expanding_chronological':self.assertTrue(all(build.META[x]['expiry_date']<r.test_expiry for x in train))
    def test_fixed_59_and_prior_configuration_unchanged(self):
        d=pd.read_csv(HERE/'upstream_32_27_audit.csv');self.assertEqual(d.classification.value_counts().to_dict(),{'model_contract_absent':32,'target_retained_at_recorded_flat':27})
        m=json.loads((HERE/'input_manifest.json').read_text())
        for name,h in m['inputs_sha256'].items():self.assertEqual(build.sha(build.ROOT/name),h,name)
    def test_catalogue_not_expanded(self):
        self.assertEqual(len(ev.RULES),12);self.assertEqual(len(set(ev.NAMES)),12);self.assertEqual(ev.BASES,['clock_only','inventory_only'])

if __name__=='__main__':unittest.main()
