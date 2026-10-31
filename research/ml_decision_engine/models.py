"""Expanding, purged whole-cycle validation with nested threshold selection."""
from __future__ import annotations
import json
import pickle
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support, mean_absolute_error
from sklearn.inspection import permutation_importance
from .features import Regimes, strict_event_matches

TASKS = {
 'basket': ['initial_entry','add_both','one_sided','flatten_short','final_liquidation'],
 'side': ['add_ce','add_pe','reduce_ce','reduce_pe','close_ce','close_pe','buy_protection','sell_protection','replace_protection','reenter'],
 'contract': ['new_short','reduce_contract','close_contract','buy_protection','sell_protection','reenter'],
}
CATEGORIES = {
 'initial_entry':'entry','add_ce':'entry','add_pe':'entry','add_both':'entry','one_sided':'entry',
 'buy_protection':'hedge','sell_protection':'hedge','replace_protection':'hedge',
 'reenter':'reentry',
}
IDENTIFIERS = ['observation_id','cycle_id','underlying','expiry_date','first_session','timestamp_ist','second','phase','level','strike','option_type']
BASE = ['underlying','phase','option_type','clock_minute','clock_sin','clock_cos','minute_mod15',
        'initial_window','scheduled_window','minutes_to_next_quarter','tau_days',
        'ce_short_units','pe_short_units','ce_long_units','pe_long_units','ce_net_units','pe_net_units',
        'ce_protection_ratio','pe_protection_ratio','contract_units','side_units',
        'position_age_minutes','since_contract_add_minutes','since_contract_close_minutes']
RISK = ['ce_equity','pe_equity','ce_realized','pe_realized','ce_unrealized','pe_unrealized',
        'ce_drawdown','pe_drawdown','basket_equity','basket_realized','basket_unrealized',
        'basket_drawdown','gross_premium','net_premium','book_delta','book_gamma','book_vega','book_theta',
        'contract_delta','contract_gamma','contract_vega','premium_loss_pct','premium_capture_pct',
        'trailing_rebound_pct','previous_closed_pnl','short_unrealized','protection_unrealized']


def feature_columns(frame, feature_set):
    base = [x for x in BASE if x in frame]
    spot = [x for x in frame if any(x.startswith(p) for p in ['return_','atr_','rv_','range_','efficiency_','slope_','persistence_','choppiness_','high_distance_','low_distance_','breakout_','failed_breakout_','intraday_','opening_','vwap_'])]
    option = [x for x in frame if x.startswith(('iv_change_','premium_change_'))]+[x for x in ['atm_iv_pct','iv_minus_rv15','option_mark','entry_cost','relative_strike_grids','previous_bar_volume'] if x in frame]
    groups = {'spot_atr':spot,'option_iv':option,'greeks_pnl':[x for x in RISK if x in frame]}
    extra = [] if feature_set=='clock_inventory' else sum(groups.values(),[]) if feature_set=='full' else groups[feature_set]
    # Absolute strike/cycle/date/session IDs and outcome columns are never inputs.
    return list(dict.fromkeys(base+extra))


def chronological_folds(meta, protocol):
    eligible = sorted([m for m in meta if m['dates'][0]<m['expiry_date']], key=lambda m:(m['expiry_date'],m['underlying']))
    n, block = protocol['minimum_training_cycles'], protocol['test_block_cycles']
    for start in range(n,len(eligible),block):
        tests = eligible[start:start+block]
        boundary = min(m['dates'][0] for m in tests)
        # Also purge an earlier expiry overlapping a test session's market history.
        train = [m for m in eligible[:start] if m['expiry_date']<boundary]
        if len(train)<n:
            continue
        yield len(train), [m['cycle_id'] for m in train], [m['cycle_id'] for m in tests]


def make_model(family, frame, columns, seed):
    cat = [c for c in columns if frame[c].dtype=='object' or isinstance(frame[c].dtype,pd.CategoricalDtype)]
    num = [c for c in columns if c not in cat]
    transform = ColumnTransformer([
        ('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),num),
        ('categorical',make_pipeline(SimpleImputer(strategy='most_frequent'),OneHotEncoder(handle_unknown='ignore',sparse_output=False)),cat),
    ],sparse_threshold=0)
    if family in ['logistic','hazard']:
        # A pooled discrete-time logistic hazard; duration is an explicit covariate.
        model = LogisticRegression(C=.2, max_iter=300, random_state=seed)
    elif family=='lightgbm':
        from lightgbm import LGBMClassifier
        model = LGBMClassifier(n_estimators=140,num_leaves=15,max_depth=5,min_child_samples=40,
                               learning_rate=.05,reg_lambda=5,n_jobs=2,verbosity=-1,random_state=seed)
    elif family=='catboost':
        from catboost import CatBoostClassifier
        model = CatBoostClassifier(iterations=140,depth=4,learning_rate=.05,l2_leaf_reg=5,
            thread_count=2,random_seed=seed,verbose=False,allow_writing_files=False)
    elif family=='gam':
        from interpret.glassbox import ExplainableBoostingClassifier
        model = ExplainableBoostingClassifier(interactions=0,max_bins=32,max_rounds=500,
            outer_bags=2,n_jobs=2,random_state=seed)
    else:
        raise ValueError(family)
    return make_pipeline(transform,model)


def fit_sample(model, x, y, seed):
    """Training-only negative subsampling with inverse inclusion weights.

    Validation/test risk sets remain complete. Weights restore training prevalence;
    no test positives or negatives are removed to improve apparent precision.
    """
    rng = np.random.default_rng(seed)
    positive = np.flatnonzero(np.asarray(y)>0)
    negative = np.flatnonzero(np.asarray(y)==0)
    take = min(len(negative),max(3000,min(60000,len(positive)*20)))
    chosen = rng.choice(negative,take,replace=False) if take<len(negative) else negative
    idx = np.r_[positive,chosen]
    weights = np.r_[np.ones(len(positive)),np.full(len(chosen),len(negative)/max(1,len(chosen)))]
    model.fit(x.iloc[idx],np.asarray(y)[idx],**{model.steps[-1][0]+'__sample_weight':weights})
    return model


def scores(y, p):
    pr,re,f1,_=precision_recall_fscore_support(y,p,average='binary',zero_division=0)
    return dict(precision=float(pr),recall=float(re),f1=float(f1),
        eligible_opportunities=len(y),actual_events=int(np.sum(y)),predicted_events=int(np.sum(p)),
        true_positive=int(np.sum(np.asarray(y,dtype=bool)&np.asarray(p,dtype=bool))))


def event_scores(frame, action, tolerance):
    """Observable same-key episodes, not independently identified decisions."""
    totals=np.zeros(3,dtype=int)
    pairs=[]
    for key,g in frame.groupby(['cycle_id','option_type','strike']):
        def episodes(values):
            result=[];previous=None
            for t in sorted(values):
                if previous is None or t-previous>120:
                    result.append(int(t))
                previous=t
            return result
        actual=episodes(g.loc[g.target.eq(1),'second'])
        # Suppression depends only on earlier emitted signals, not future probabilities.
        predicted=[]
        for t in sorted(g.loc[g.prediction.eq(1),'second']):
            if not predicted or t-predicted[-1]>120:
                predicted.append(int(t))
        matches=strict_event_matches(actual,predicted,tolerance)
        totals += [len(actual),len(predicted),len(matches)]
        pairs.extend(dict(cycle_id=key[0],option_type=key[1],strike=key[2],actual_second=a,predicted_second=p,action=action,tolerance_seconds=tolerance) for a,p in matches)
    a,p,m=totals
    precision=m/p if p else 0.; recall=m/a if a else 0.
    return dict(event_precision=float(precision),event_recall=float(recall),
        event_f1=float(2*precision*recall/(precision+recall)) if precision+recall else 0.,
        actual_episodes=int(a),predicted_episodes=int(p),matched_episodes=int(m)),pairs


def task_rows(data,level,action):
    mask=data.level.eq(level)
    if level=='side' and action.endswith(('_ce','_pe')):
        mask &= data.option_type.eq('CE' if action.endswith('_ce') else 'PE')
    if action in ['reduce_contract','close_contract']:
        mask &= data.contract_units.lt(0)
    if action=='reenter':
        # At side level closure history is not identifiable from contract-level age.
        if level=='side':
            return data.iloc[:0]
        mask &= data.since_contract_close_minutes.notna()&data.contract_units.ge(0)
    return data.loc[mask]


def explain(model, held, y, cols, out, name, metadata):
    """Held-cycle permutation effects + SHAP, with failures explicitly recorded."""
    n=min(256,len(held))
    sample=held.sample(n,random_state=802026)
    result=[]
    try:
        imp=permutation_importance(model,sample[cols],y.loc[sample.index],scoring='average_precision',n_repeats=2,random_state=802026,n_jobs=1)
        for col,v,s in zip(cols,imp.importances_mean,imp.importances_std):
            result.append(dict(**metadata,feature=col,importance=float(v),std=float(s),method='held_cycle_permutation_AP'))
        top=np.argsort(imp.importances_mean)[-4:]
        effects=[]
        for index in top:
            col=cols[index]
            if not pd.api.types.is_numeric_dtype(sample[col]):
                continue
            values=sample[col].dropna().quantile([.1,.3,.5,.7,.9]).unique()
            for value in values:
                altered=sample[cols].copy();altered[col]=value
                effects.append(dict(feature=col,value=float(value),mean_predicted_action=float(model.predict_proba(altered)[:,1].mean())))
        pd.DataFrame(effects).to_csv(out/'shap_explanations'/f'{name}_partial_dependence.csv',index=False)
        import shap
        pre, estimator=model.steps[0][1],model.steps[-1][1]
        x=pre.transform(sample[cols])
        feature_names=pre.get_feature_names_out()
        if hasattr(estimator,'coef_'):
            values=x*estimator.coef_[0]
            explanation='exact additive log-odds contributions; baseline intercept separate'
        elif estimator.__class__.__name__.startswith('ExplainableBoosting'):
            local=estimator.explain_local(x)
            values=np.array([local.data(i)['scores'] for i in range(len(x))])
            feature_names=np.array(local.data(0)['names'])
            explanation='EBM exact additive log-odds contributions'
        else:
            values=shap.TreeExplainer(estimator).shap_values(x)
            if isinstance(values,list):values=values[-1]
            if np.asarray(values).ndim==3:values=np.asarray(values)[:,:,-1]
            explanation='TreeSHAP raw model contributions'
        values=np.asarray(values)
        pd.DataFrame(values,columns=feature_names).assign(observation_id=sample.observation_id.to_numpy()).to_parquet(out/'shap_explanations'/f'{name}_values.parquet',index=False)
        importance=pd.DataFrame({'feature':feature_names,'mean_abs_contribution':np.abs(values).mean(axis=0)})
        importance.to_csv(out/'shap_explanations'/f'{name}_global.csv',index=False)
        for regime,g in sample.groupby('direction_regime'):
            indices=sample.index.get_indexer(g.index)
            pd.DataFrame({'feature':feature_names,'mean_abs_contribution':np.abs(values[indices]).mean(axis=0)}).to_csv(out/'shap_explanations'/f'{name}_{regime}.csv',index=False)
        (out/'shap_explanations'/f'{name}_method.json').write_text(json.dumps(dict(method=explanation,rows=n,feature_count=len(feature_names),interactions='EBM constrained additive; tree interactions not interpreted as causal'),indent=2))
    except Exception as exc:
        (out/'shap_explanations'/f'{name}_unavailable.json').write_text(json.dumps({'error':str(exc),'status':'explanation_unavailable'}))
    return result


def train_models(data,meta,protocol,out):
    (out/'selected_model_configurations').mkdir(exist_ok=True)
    (out/'shap_explanations').mkdir(exist_ok=True)
    all_scores=[]; predictions=[]; configurations=[]; importance=[]; faults=[]; regimes=[]
    folds=list(chronological_folds(meta,protocol))
    for fold,(_,train_ids,test_ids) in enumerate(folds):
        train=data[data.cycle_id.isin(train_ids)];test=data[data.cycle_id.isin(test_ids)]
        regime=Regimes().fit(train[train.level.eq('basket')])
        test=regime.transform(test);train=regime.transform(train)
        regimes.append(test[test.level.eq('basket')][IDENTIFIERS+['direction_regime','volatility_regime','volatility_transition','structure_regime','spot','rv_15','atm_iv_pct','ce_short_units','pe_short_units']].assign(fold=fold))
        ordered=sorted(train_ids,key=lambda cid:next(m['expiry_date'] for m in meta if m['cycle_id']==cid))
        inner_ids=ordered[-protocol['inner_validation_cycles']:]
        inner_start=min(next(m['dates'][0] for m in meta if m['cycle_id']==cid) for cid in inner_ids)
        fit_ids=[cid for cid in ordered if next(m['expiry_date'] for m in meta if m['cycle_id']==cid)<inner_start]
        for level,actions in TASKS.items():
            for action in actions:
                tr,te=task_rows(train,level,action),task_rows(test,level,action)
                target='y_'+action
                if len(tr)==0 or len(te)==0 or tr[target].sum()<protocol['minimum_positive_training_events']:
                    faults.append(dict(fold=fold,level=level,action=action,status='insufficient_training_support',training_positives=int(tr[target].sum()) if len(tr) else 0))
                    continue
                inn=tr[tr.cycle_id.isin(fit_ids)]; val=tr[tr.cycle_id.isin(inner_ids)]
                if inn[target].nunique()<2 or val[target].nunique()<2:
                    faults.append(dict(fold=fold,level=level,action=action,status='inner_fold_single_class'))
                    continue
                candidates=[]
                for fs in ['clock_inventory','full','spot_atr','option_iv','greeks_pnl']:
                    cols=feature_columns(tr,fs)
                    for family in protocol['models'] if fs in ['clock_inventory','full'] else ['lightgbm']:
                        if family=='hazard' and action not in ['reduce_contract','close_contract','reduce_ce','reduce_pe','reenter','final_liquidation']:
                            continue
                        try:
                            model=make_model(family,inn,cols,protocol['seed'])
                            fit_sample(model,inn[cols],inn[target],protocol['seed'])
                            probs=model.predict_proba(val[cols])[:,1]
                            choices=[(scores(val[target],probs>=threshold)['f1'],threshold) for threshold in protocol['threshold_grid']]
                            inner_score,threshold=max(choices,key=lambda x:(x[0],x[1]))
                            model=make_model(family,tr,cols,protocol['seed'])
                            fit_sample(model,tr[cols],tr[target],protocol['seed'])
                            probability=model.predict_proba(te[cols])[:,1]
                            pred=(probability>=threshold).astype(int)
                            row=dict(fold=fold,level=level,action=action,feature_set=fs,model=family,threshold=threshold,
                                inner_validation_f1=inner_score,train_cycles=len(train_ids),test_cycles=len(test_ids),
                                feature_count=len(cols),previously_inspected=True,**scores(te[target],pred))
                            trace=te[IDENTIFIERS+['direction_regime','volatility_regime','volatility_transition','structure_regime']].copy()
                            trace['target']=te[target].to_numpy();trace['probability']=probability;trace['prediction']=pred
                            trace=trace.assign(fold=fold,action=action,feature_set=fs,model=family)
                            for tolerance in [0,60,120]:
                                es,_=event_scores(trace,action,tolerance)
                                row.update({f'{k}_{tolerance}s':v for k,v in es.items()})
                            all_scores.append(row)
                            # Select separately inside each feature set, only using INNER validation.
                            inner_metrics=scores(val[target],probs>=threshold)
                            candidates.append((inner_score,fs,family,threshold,cols,model,trace,inner_metrics))
                        except Exception as exc:
                            faults.append(dict(fold=fold,level=level,action=action,feature_set=fs,model=family,status='model_failed',error=str(exc)))
                for fs in ['clock_inventory','full','spot_atr','option_iv','greeks_pnl']:
                    cs=[x for x in candidates if x[1]==fs]
                    if not cs:continue
                    winner=max(cs,key=lambda x:(x[0],-protocol['models'].index(x[2])))
                    inner_score,_,family,threshold,cols,model,trace,inner_metrics=winner
                    trace['selected']=True;predictions.append(trace)
                    key=f'fold{fold}_{level}_{action}_{fs}'
                    conf=dict(fold=fold,level=level,action=action,feature_set=fs,model=family,threshold=threshold,features=cols,
                        train_cycles=train_ids,test_cycles=test_ids,inner_fit_cycles=fit_ids,inner_validation_cycles=inner_ids,
                        training_regime_thresholds=regime.thresholds,inner_metrics=inner_metrics,
                        replay_eligible=inner_metrics['precision']>=.75 and inner_metrics['recall']>=.75 and inner_metrics['actual_events']>=12,
                        selection='inner chronological F1; never P&L or test scores')
                    configurations.append(conf)
                    (out/'selected_model_configurations'/f'{key}.json').write_text(json.dumps(conf,indent=2))
                    with (out/'selected_model_configurations'/f'{key}.pkl').open('wb') as f:pickle.dump(model,f)
                    if fs=='full' and fold==len(folds)-1 and inner_score>=.2:
                        importance.extend(explain(model,te,te[target],cols,out,key,dict(level=level,action=action,fold=fold)))
                print('Trained',fold,level,action,len(candidates),'models',flush=True)
    score=pd.DataFrame(all_scores)
    score.to_csv(out/'chronological_validation_results.csv',index=False)
    pd.DataFrame(faults).to_csv(out/'unavailable_tasks_and_models.csv',index=False)
    pd.DataFrame(importance).to_csv(out/'feature_importance_by_action.csv',index=False)
    pred=pd.concat(predictions,ignore_index=True) if predictions else pd.DataFrame()
    pred.to_parquet(out/'held_cycle_predictions.parquet',index=False)
    labels=pd.concat(regimes,ignore_index=True) if regimes else pd.DataFrame()
    labels.to_parquet(out/'market_regime_labels.parquet',index=False)
    return score,pred,configurations,labels
