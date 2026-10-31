"""Support-aware results and honest research answers generated from actual runs."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from .models import CATEGORIES,scores,event_scores


def csv(frame,path,columns=None):
    if frame.empty and columns:frame=pd.DataFrame(columns=columns)
    frame.to_csv(path,index=False,compression='gzip' if str(path).endswith('.gz') else None)


def summarize(data,score,pred,labels,protocol,out):
    aggregate=[];strata=[];regime_rows=[];cycle_rows=[]
    if len(pred):
        for (level,action,fs),g in pred.groupby(['level','action','feature_set']):
            s=scores(g.target,g.prediction)
            row=dict(level=level,action=action,feature_set=fs,independent_cycles=g.cycle_id.nunique(),coverage=1.,**s)
            cycle_checks=[]
            for cid,c in g.groupby('cycle_id'):
                cs=scores(c.target,c.prediction)
                cycle_rows.append(dict(level=level,action=action,feature_set=fs,cycle_id=cid,**cs))
                if cs['actual_events']>=5:cycle_checks.append(cs['precision']>=.75 and cs['recall']>=.75)
            for tol in [0,60,120]:
                es,_=event_scores(g,action,tol);row.update({f'{k}_{tol}s':v for k,v in es.items()})
            row['consistent_supported_cycles']=bool(cycle_checks and all(cycle_checks))
            row['target_75_achieved']=bool(s['precision']>=.75 and s['recall']>=.75 and g.cycle_id.nunique()>=protocol['minimum_target_cycles'] and s['actual_events']>=protocol['minimum_target_events'] and row['consistent_supported_cycles'])
            row['target_scope']='conditional received sessions; previously inspected; row label next-minute execution'
            aggregate.append(row)
            for dimension in ['underlying','phase','direction_regime','volatility_regime','volatility_transition','structure_regime']:
                for value,c in g.groupby(dimension):
                    strata.append(dict(level=level,action=action,feature_set=fs,dimension=dimension,value=value,
                        independent_cycles=c.cycle_id.nunique(),**scores(c.target,c.prediction)))
            if fs=='full':
                for key,c in g.groupby(['underlying','phase','direction_regime','volatility_regime']):
                    regime_rows.append(dict(level=level,action=action,underlying=key[0],phase=key[1],direction=key[2],volatility=key[3],
                        independent_cycles=c.cycle_id.nunique(),empirical_action_probability=float(c.target.mean()),
                        mean_predicted_probability=float(c.probability.mean()),**scores(c.target,c.prediction)))
    agg=pd.DataFrame(aggregate);strat=pd.DataFrame(strata);cycles=pd.DataFrame(cycle_rows)
    csv(agg,out/'selected_chronological_scores.csv', ['level','action','feature_set','precision','recall'])
    csv(strat,out/'validation_scores_by_stratum.csv',['level','action','dimension','value'])
    csv(cycles,out/'validation_scores_by_cycle.csv',['level','action','cycle_id'])
    matrix=pd.DataFrame(regime_rows)
    if len(matrix):
        # Quantity is aggregated over all eligible opportunities, not only successes.
        qty=data[['observation_id']+[c for c in data if c.startswith('y_') and c.endswith('_units')]].copy()
        units=qty.drop(columns='observation_id').sum(axis=1)
        lookup=pd.Series(units.to_numpy(),index=qty.observation_id)
        p=pred[pred.feature_set.eq('full')].copy();p['actual_all_role_units']=p.observation_id.map(lookup)
        mean=p.groupby(['level','action','underlying','phase','direction_regime','volatility_regime']).actual_all_role_units.mean()
        matrix['mean_all_role_units']=[mean.get((r.level,r.action,r.underlying,r.phase,r.direction,r.volatility),np.nan) for r in matrix.itertuples()]
    csv(matrix,out/'market_regime_action_matrix.csv',['level','action','eligible_opportunities','actual_events','precision','recall','independent_cycles'])
    for category in ['entry','position_management','hedge','reentry']:
        selected=agg[[CATEGORIES.get(a,'position_management')==category for a in agg.action]] if len(agg) else pd.DataFrame()
        csv(selected,out/f'{category}_model_scores.csv',['level','action','precision','recall','status'])
    for name in ['stop_loss','profit_target']:
        # Intent is not in the ledger: never invent verified supervised labels.
        surrogate=agg[agg.action.isin(['reduce_contract','close_contract','reduce_ce','reduce_pe','flatten_short'])].copy() if len(agg) else pd.DataFrame()
        if len(surrogate):
            surrogate['modelled_outcome']='observed reduction, not identified '+name
            surrogate['intent_identified']=False
        csv(surrogate,out/f'{name}_model_scores.csv',['modelled_outcome','intent_identified','precision','recall'])
    if len(pred):
        mismatch=pred[pred.target.ne(pred.prediction)].copy()
        mismatch['error_type']=np.where(mismatch.target.eq(1),'missed_action','false_positive')
        csv(mismatch,out/'false_positive_and_missed_action_ledger.csv.gz')
        correct=pred[pred.target.eq(1)&pred.prediction.eq(1)]
        csv(correct.groupby(['level','action','feature_set']).head(5),out/'example_correct_predictions.csv')
    else:
        csv(pd.DataFrame(),out/'false_positive_and_missed_action_ledger.csv.gz',['observation_id','error_type'])
    if len(labels):
        transition=labels.sort_values(['cycle_id','second']).copy()
        for col in ['direction_regime','volatility_regime','spot','rv_15','atm_iv_pct']:
            transition['previous_'+col]=transition.groupby('cycle_id')[col].shift()
        transition['spot_change']=transition.spot-transition.previous_spot
        transition['rv_change']=transition.rv_15-transition.previous_rv_15
        transition['iv_change']=transition.atm_iv_pct-transition.previous_atm_iv_pct
        actions=data[data.level.eq('basket')][['observation_id']+[c for c in data if c.startswith('y_')]]
        transition=transition.merge(actions,on='observation_id',validate='one_to_one')
        csv(transition,out/'market_regime_transition_analysis.csv')
    else:csv(pd.DataFrame(),out/'market_regime_transition_analysis.csv',['previous_direction_regime','direction_regime'])
    if len(agg):
        base=agg[agg.feature_set.eq('clock_inventory')].set_index(['level','action'])
        comparison=[]
        for r in agg[~agg.feature_set.eq('clock_inventory')].itertuples():
            key=(r.level,r.action)
            if key in base.index:
                b=base.loc[key]
                comparison.append(dict(level=r.level,action=r.action,feature_set=r.feature_set,
                    delta_precision=r.precision-b.precision,delta_recall=r.recall-b.recall,delta_f1=r.f1-b.f1,
                    interpretation='paired chronological feature-set difference; correlated features, not causal attribution'))
        csv(pd.DataFrame(comparison),out/'incremental_market_feature_value.csv')
        # Whole-cycle bootstrap of paired differences, not row-level confidence.
        ci=[];rng=np.random.default_rng(protocol['seed'])
        for (level,action),group in cycles.groupby(['level','action']):
            pv=group.pivot_table(index='cycle_id',columns='feature_set',values='f1')
            if not {'full','clock_inventory'}.issubset(pv.columns):continue
            differences=(pv.full-pv.clock_inventory).dropna().to_numpy()
            if not len(differences):continue
            draws=rng.choice(differences,size=(2000,len(differences)),replace=True).mean(axis=1)
            ci.append(dict(level=level,action=action,cycles=len(differences),mean_cycle_f1_difference=float(differences.mean()),
                bootstrap_low95=float(np.quantile(draws,.025)),bootstrap_high95=float(np.quantile(draws,.975)),previously_inspected=True))
        csv(pd.DataFrame(ci),out/'incremental_value_cycle_uncertainty.csv')
    return agg,strat


def write_report(out,agg,strata,replay,manifest):
    def table(frame,columns,limit=30):
        if frame.empty:return 'No supported fitted result is available. See unavailable_tasks_and_models.csv.'
        f=frame[[c for c in columns if c in frame]].head(limit).copy()
        return f.to_csv(index=False)
    full=agg[agg.feature_set.eq('full')] if len(agg) else agg
    recovered=full[full.target_75_achieved] if len(full) else full
    candidates=full[(full.precision>=.5)&(full.recall>=.5)&~full.target_75_achieved] if len(full) else full
    questions=[
        ('What precedes initial entry?', 'See entry_model_scores.csv and market_regime_action_matrix.csv for initial_entry. The opportunity universe is conditional on received sessions; the missing eligible/no-trade calendar prevents identifying an unconditional entry gate.'),
        ('Clock or market-dependent initial entries?', 'Compare clock_inventory and full initial_entry models, including per-cycle scores. The 31/32 opening-time prior is preserved; a few exceptional starts cannot establish a general market gate.'),
        ('Rising, falling and sideways response?', 'market_regime_action_matrix.csv separates lagged direction, volatility and phase. All denominators include unchanged opportunities; no future return defines a predictor.'),
        ('Volatility expansion and contraction?', 'The matrix and validation_scores_by_stratum.csv separate volatility_transition from direction. Quantile cutoffs use training sessions only; descriptive conditional probabilities are not causality.'),
        ('Independent CE and PE management?', 'Side/right tasks and their held-cycle scores retain independent additions, reductions and closures. Co-occurring labels are allowed. Compare index/right strata before inferring shared settings.'),
        ('Additional units?', 'allocation_model_scores.csv compares conditional unit classification/regression and gated nonzero exact counts. quantity_prediction_errors.csv and quantity_symmetry.csv retain the errors. Base 65/20 is observed granularity, not a margin formula.'),
        ('Conditions preceding reductions?', 'Read the active-contract reduction hazards, held-cycle permutation effects and SHAP values. The first-passage ledger records timing/censoring. Accurate relative ranking alone does not identify original stops.'),
        ('Which stop structure?', 'Stop cause is unobserved. stop_loss_model_scores.csv explicitly reports reduction-surrogate metrics, and first_passage_scores.csv reports fixed diagnostic first crossings at contract/side/basket scales. No winning threshold is promoted to source code.'),
        ('Profit target or trailing mechanism?', 'Profit/stop intents cannot be separately supervised from fills. Profit capture, sampled drawdown and rebound are causal features; profit_target_model_scores.csv remains labelled a reduction surrogate. The fixed first-passage checks do not prove a target.'),
        ('Hedge additions and replacements?', 'hedge_model_scores.csv separates long opens, long closes and same-minute replacement flow. A replacement label is an observable coexistence, not an original allocation link. Seed timing is available as clock context; seed and routine selection are not uniquely recovered.'),
        ('Re-entry conditions?', 'Contract-flat-after-close opportunities retain no-reentry examples. reenter means observed same-contract reopening after an earlier close, not proven planned intent. Side-level re-entry remains unsupported without ownership or queue records.'),
        ('Incremental ATR, IV and Greek value?', 'incremental_market_feature_value.csv compares spot_atr, option_iv, greeks_pnl and full models with the clock/inventory baseline. Whole-cycle paired intervals are in incremental_value_cycle_uncertainty.csv. These are correlated feature-group contributions.'),
        ('Features driving decisions?', 'feature_importance_by_action.csv uses held-cycle permutation AP; shap_explanations contains additive/TreeSHAP values by regime and partial-dependence tables. Failed explanations are explicitly recorded. These associations do not certify causal controller conditions.'),
        ('75% precision AND recall?', f'{len(recovered)} full-feature action/level tasks pass the registered support and consistent-cycle row-classification criteria. Inspect timing and coverage independently; this count is not an autonomous-policy success rate or externally blind validation.'),
        ('Does autonomous replay reproduce positions?', 'autonomous_replay_scores.csv reports complete contract paths and action/timing matches. Modules require earlier out-of-cycle support plus the current inner check; unsupported modules abstain. Zero fills or incomplete module support is a failure to reconstruct, not successful inactivity.'),
        ('Stable versus unidentified?', 'See the recovered/candidate tables below and per-cycle/stratum ledgers. Unobserved decision/submission times, allocation IDs, account margin/NAV, full-chain bid/ask and export completeness bound every conclusion.'),
    ]
    text=['# Algo 8 - ML decision engine research report','',
        'This is an extension of STRONG_FINDINGS v7 and the canonical playbook. Existing evidence, selected configurations and numerical outputs are unchanged. All historic dates were previously inspected. Predictions target next-minute received execution actions; original decision intent remains latent.','',
        f"Run status: {manifest['status']}. Input revision: {manifest['source_revision']}. Dataset rows: {manifest.get('dataset_rows',0):,}.",
        '', '## Chronological behavioural results','',
        '```csv',table(full,['level','action','precision','recall','f1','independent_cycles','actual_events','event_precision_60s','event_recall_60s','target_75_achieved']),'```',
        '', '## Autonomous replay','',
        'The strict replay has no historical inventory feedback. Features use its confirmed fills and the preceding market state. Missing module support, quotes or quantity models causes abstention. Its results are scored against actual actions only after decisions. This conservative gate does not manufacture a complete policy.',
        '', '```csv',table(replay,['fold','cycle_id','role','tolerance_seconds','precision','recall','inventory_overlap','exact_inventory_fraction','simulated_fills']),'```',
        '', '## Sixteen research answers','']
    for n,(q,a) in enumerate(questions,1):text.extend([f'### {n}. {q}','',a,''])
    text.extend(['## Economics and limitations','',
        'Autonomous marked paths subtract declared estimated costs. Minute-open simulated fills are hypothetical; actual recorded prices remain comparison truth, not prices granted to predicted trades. Missing marks remain missing. No final short is silently forgiven, no long wing is assumed settled, and neither comparable-risk alpha nor original screenshot returns are established. Greeks use the inherited approximate flat-ATM-IV surface. Bid/ask, full-chain selection, feed latency and subminute decisions remain unavailable.',
        '', '## Recovered behavioural rules','',
        'Only relationships passing support-aware chronological criteria are listed below. They recover conditional execution behaviour, not unique original source code. Previously established structural F01-F34/C01/C02 remain authoritative.',
        '', '```csv',table(recovered,['level','action','precision','recall','independent_cycles','actual_events']),'```',
        '', '## Strong candidate rules','',
        'These have partial chronological discrimination and do not pass the complete target criteria. No universal rule is inferred from the best historical model.',
        '', '```csv',table(candidates,['level','action','precision','recall','independent_cycles']),'```',
        '', '## Unresolved logic','',
        'Stop/target intent and scope, re-entry versus execution cleanup, seed/routine/late wing ownership, sizing/margin limits, exact strike selection, skipped eligible sessions, pending orders and the complete autonomous policy remain unresolved wherever outputs lack adequate support. Same-second ordering and missing intrabar prices prevent exact first-passage inference. Previously inspected chronological checks are not external blind validation.'])
    (out/'ML_DECISION_ENGINE_RESEARCH_REPORT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
