"""Economic identities, causal benchmark clocks and attribution boundaries."""
import importlib.util,json,sys,unittest
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,HERE/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
old={k:sys.modules.get(k) for k in ['inputs','economics']}
inp=load('final_econ_inputs','inputs.py');sys.modules['inputs']=inp
econ=load('final_econ_economics','economics.py');sys.modules['economics']=econ
attr=load('final_econ_attribution','attribution.py');bench=load('final_econ_benchmarks','benchmarks.py')
for k,v in old.items():
    if v is None:sys.modules.pop(k,None)
    else:sys.modules[k]=v

class FinalEconomicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e=pd.read_csv(HERE/'cycle_economic_results.csv');cls.b=pd.read_csv(HERE/'benchmark_comparison.csv');cls.f=inp.fills()
    def test_decimal_partial_close_and_reversal(self):
        b=inp.DecimalBook();key=(100,'CE');b.apply(key,10,Decimal('10'),'Sell');b.apply(key,10,Decimal('20'),'Sell')
        _,q,closed,opened,pnl=b.apply(key,25,Decimal('12'),'Buy')
        self.assertEqual((q,closed,opened,pnl),(5,20,5,Decimal(60)));self.assertEqual(b.cash,Decimal(0));self.assertEqual(b.cost[key],Decimal(12))
    def test_every_role_and_realised_unrealised_identity(self):
        r=pd.read_csv(HERE/'role_economic_results.csv');g=r.groupby('cycle_id')[['realised_pnl','marked_unrealised_pnl','economic_pnl','fill_cashflow','endpoint_marked_value']].sum().sort_index();e=self.e.sort_values('cycle_id')
        np.testing.assert_allclose(g.economic_pnl,e.marked_economic_pnl,atol=1e-6,rtol=0)
        np.testing.assert_allclose(g.realised_pnl+g.marked_unrealised_pnl,g.economic_pnl,atol=1e-6,rtol=0)
        np.testing.assert_allclose(g.fill_cashflow+g.endpoint_marked_value,g.economic_pnl,atol=1e-6,rtol=0)
    def test_recorded_endpoint_agrees_with_frozen_prior_snapshots(self):
        d=pd.read_csv(inp.SOURCE/'option_minute_portfolio_replay.csv').groupby(['underlying','expiry_date']).tail(1)
        g=self.e.merge(d,on=['underlying','expiry_date']);np.testing.assert_allclose(g.marked_economic_pnl,g.marked_equity_close,rtol=0,atol=1e-6)
    def test_parent_fees_not_charged_per_child(self):
        actual=self.f.groupby('cycle_id').parent_id.nunique().sort_index();e=self.e.sort_values('cycle_id')
        np.testing.assert_array_equal(e.parent_orders,actual)
        for name,(a,b,c) in inp.COSTS.items():np.testing.assert_allclose(e[name+'_cost'],a*e.turnover+b*e.parent_orders+c*e.executed_quantity,atol=1e-6,rtol=0)
    def test_black_vector_matches_existing_scalar_model(self):
        path=inp.ROOT/'research/option_pricing_model.py';spec=importlib.util.spec_from_file_location('existing_black_scalar',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        for F,K,t,s in [(100.,105.,.01,.2),(23000.,22950.,.002,.15),(75000.,76000.,.001,.3)]:
            for r,right in [(0,'CE'),(1,'PE')]:
                x=attr.black(np.array([F]),np.array([K]),np.array([t]),np.array([s]),np.array([r]),.06)[0]
                self.assertAlmostEqual(x,m.price(F,K,t,s,right,.06),places=7)
    def test_own_iv_fit_and_intrinsic_abstention(self):
        F=np.array([100.,100.]);K=np.array([100.,110.]);t=np.array([.02,.02]);s=np.array([.25,.4]);r=np.array([0,1]);p=attr.black(F,K,t,s,r)
        np.testing.assert_allclose(attr.fit_iv(p,F,K,t,r),s,atol=1e-9)
        self.assertTrue(np.isnan(attr.fit_iv(np.array([0.]),np.array([100.]),np.array([100.]),np.array([0.]),np.array([0]))[0]))
    def test_shapley_exact_sum_and_unchanged_factor_zero(self):
        F=np.array([100.,101.]);K=np.array([100.,100.]);t=np.array([.1,.2]);s=np.array([.2,.3]);r=np.array([0,1])
        parts=attr.shapley(F,t,s,F+2,t-.01,s+.02,K,r)
        np.testing.assert_allclose(np.sum(parts,axis=0),attr.black(F+2,K,t-.01,s+.02,r)-attr.black(F,K,t,s,r),atol=1e-10)
        parts=attr.shapley(F,t,s,F,t-.01,s,K,r);np.testing.assert_allclose(parts[0],0,atol=1e-12);np.testing.assert_allclose(parts[2],0,atol=1e-12)
    def test_all_model_decompositions_reconcile_without_double_counting(self):
        d=pd.read_csv(HERE/'cycle_pnl_decomposition.csv');total=d.modeled_direction_pnl+d.modeled_time_pnl+d.modeled_iv_surface_pnl+d.trade_to_bar_mark_bridge+d.unexplained_residual
        np.testing.assert_allclose(total,d.economic_pnl,rtol=0,atol=1e-5)
        np.testing.assert_allclose(d.delta_linear_diagnostic+d.gamma_quadratic_diagnostic+d.direction_higher_and_interaction,d.modeled_direction_pnl,rtol=0,atol=1e-5)
        self.assertFalse(d.model_prices_used_for_liquidation.any())
        common=d[d.coverage.eq('common_all_models')].groupby(['cycle_id','role']).fitted_intervals.nunique();self.assertTrue(common.eq(1).all())
    def test_model_fit_quality_and_missing_prices_not_zeroed(self):
        d=pd.read_csv(HERE/'attribution_interval_ledger.csv.gz');v=d[d.primary_fitted]
        self.assertTrue(((v.volume0>0)&(v.volume1>0)&v.p0.notna()&v.p1.notna()).all())
        np.testing.assert_allclose(v.primary_direction+v.primary_time+v.primary_iv,v.quote_movement,atol=1e-4,rtol=0)
    def test_phase_pnl_sums_to_endpoint(self):
        p=pd.read_csv(HERE/'phase_economic_results.csv');g=p.groupby('cycle_id').gross_pnl.sum().sort_index();np.testing.assert_allclose(g,self.e.sort_values('cycle_id').marked_economic_pnl,rtol=0,atol=1e-6)
    def test_frozen_payoff_tail_and_sampled_drawdown(self):
        z={'strikes':np.array([100,110]),'rights':np.array([0,0])};bound,tail=econ.frozen_risk(np.array([[-1,1],[-2,1]]),np.array([5.,5.]),z)
        self.assertEqual(bound[0],5);self.assertFalse(tail[0]);self.assertTrue(tail[1]);self.assertTrue(np.isnan(bound[1]));self.assertEqual(econ.drawdown([10,20,5,30,-5]),35)
    def test_incomplete_benchmarks_stay_missing(self):
        d=self.b[self.b.benchmark.isin(['B_initial_basket','C_scheduled_accumulation','D_common_clock'])]
        self.assertTrue(d.loc[~d.complete_quotes,'gross_pnl'].isna().all())
        self.assertTrue(self.b[self.b.benchmark=='E_equal_risk_unavailable'].gross_pnl.isna().all());self.assertFalse(self.b.risk_equalized.any())
    def test_scheduled_benchmark_causal_clock_and_earlier_calibration(self):
        d=pd.read_csv(HERE/'scheduled_benchmark_coverage.csv');signal=pd.to_datetime(d.signal_ist);execution=pd.to_datetime(d.modeled_execution_ist)
        self.assertTrue(((execution-signal).dt.total_seconds()==60).all());self.assertTrue((pd.to_datetime(d.feature_available_at_ist)<=signal).all())
        c=json.loads((inp.ROOT/'research/hypothesis_controller_search/outputs/calibration.json').read_text());self.assertEqual(c['fit_through'],'2026-07-31')
        pairs=pd.read_csv(HERE/'paired_benchmark_differences.csv');self.assertFalse(pairs.comparable_risk_budget.any())
    def test_common_clock_uses_strictly_predeadline_actual_book(self):
        for cid in [1,8,14,32]:
            b=self.b[(self.b.cycle_id==cid)&self.b.benchmark.eq('D_common_clock')].iloc[0]
            if not b.complete_quotes:continue
            t=inp.sec(b.exit_ist);f=self.f[(self.f.cycle_id==cid)&self.f.second.lt(t)];last=f.groupby(['strike','option_type']).tail(1);z=inp.cycle_data(cid);i=int(np.flatnonzero(z['minutes']==t//60)[0]);value=0.
            for x in last.itertuples():
                if x.quantity_after:
                    j=int(np.flatnonzero((z['strikes']==x.strike)&(z['rights']==int(x.option_type=='PE')))[0]);value+=x.quantity_after*z['open'][i,j]
            self.assertAlmostEqual(b.gross_pnl,f.cash_change.sum()+value,places=5)
    def test_management_markout_is_local_not_added_profit(self):
        d=pd.read_csv(HERE/'management_fixed_markouts.csv.gz');g=d[d.gross_local_markout_benefit.notna()].iloc[::1000]
        expected=g.closing_quantity*(g.deadline_quote-g.fill_price)*np.where(g.role.str.startswith('short'),1,-1)
        np.testing.assert_allclose(expected,g.gross_local_markout_benefit,rtol=0,atol=1e-6)
        s=pd.read_csv(HERE/'management_markout_summary.csv');self.assertFalse(s.additive_to_strategy_profit.any());self.assertFalse(s.deployable_counterfactual.any())
        c=pd.read_csv(HERE/'management_realised_components.csv.gz');self.assertAlmostEqual(c.realised_pnl.sum(),self.e.gross_realised_pnl.sum(),places=5)
        flow=pd.read_csv(HERE/'flow_and_holding_attribution.csv');self.assertAlmostEqual(flow.cashflow.sum(),self.e.fill_cashflow.sum(),places=5)
        self.assertAlmostEqual(flow.realised_pnl.sum(),self.e.gross_realised_pnl.sum(),places=5)
        self.assertTrue(flow.fifo_quantity_minutes.ge(0).all());self.assertTrue(flow.lifo_quantity_minutes.ge(0).all())
    def test_leave_one_cycle_out_and_initialization_cohorts(self):
        d=pd.read_csv(HERE/'leave_one_cycle_out.csv');g=d[(d.cohort=='primary_32')&d.cost_scenario.eq('conservative')];e=self.e[self.e.known_initialization].set_index('cycle_id')
        self.assertEqual(len(g),32);self.assertEqual(set(g.excluded_cycle_id),set(e.index))
        np.testing.assert_allclose(g.remaining_net,e.conservative_marked_net.sum()-e.loc[g.excluded_cycle_id,'conservative_marked_net'].to_numpy(),rtol=0,atol=1e-6)
        self.assertEqual(len(self.e[self.e.known_initialization]),32);self.assertEqual(len(self.e[self.e.known_initialization&self.e.flat_received_endpoint]),22)
    def test_immutable_prior_inputs_and_original_selected_config(self):
        manifest=json.loads((HERE/'input_audit.json').read_text())
        for name,h in manifest['immutable_inputs_sha256'].items():self.assertEqual(inp.sha(inp.ROOT/name),h,name)
        self.assertEqual(len(self.f),41421);self.assertEqual(self.f.parent_id.nunique(),39874)
    def test_verdict_separates_marked_profit_from_alpha(self):
        v=json.loads((HERE/'final_verdict.json').read_text());self.assertEqual(v['outcome'],'B');self.assertFalse(v['data_support_economic_alpha']);self.assertFalse(v['defensible_equal_risk_benchmark_available'])
        self.assertTrue(v['research_closed']);self.assertFalse(v['data_support_verified_complete_account_profit']);self.assertGreater(v['primary_net_by_cost_scenario']['conservative'],0);self.assertLess(v['primary_net_by_cost_scenario']['adverse_execution'],0)

if __name__=='__main__':unittest.main()
