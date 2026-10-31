"""Conditional quantity and stage-one gating, with held-cycle errors."""
from __future__ import annotations
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from lightgbm import LGBMClassifier, LGBMRegressor
from .models import chronological_folds,feature_columns


def run_quantities(data,meta,protocol,predictions,out):
    scores=[]; errors=[]; manifests=[]
    for fold,(_,train_ids,test_ids) in enumerate(chronological_folds(meta,protocol)):
        for level in ['side','contract']:
            for right,name in [('CE','ce'),('PE','pe')]:
                for role,action in [('short_open','add_'+name if level=='side' else 'new_short'),
                                    ('short_close','reduce_'+name if level=='side' else 'reduce_contract'),
                                    ('long_open','buy_protection'),('long_close','sell_protection')]:
                    g=data[data.level.eq(level)&data.option_type.eq(right)]
                    target=f'y_{name}_{role}_units'
                    tr=g[g.cycle_id.isin(train_ids)&g[target].gt(0)]
                    te=g[g.cycle_id.isin(test_ids)]
                    if len(tr)<12 or len(te)==0:continue
                    for fs in ['clock_inventory','full']:
                        cols=feature_columns(g,fs)
                        cat=[c for c in cols if g[c].dtype=='object' or isinstance(g[c].dtype,pd.CategoricalDtype)]
                        num=[c for c in cols if c not in cat]
                        transform=ColumnTransformer([
                            ('num',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),num),
                            ('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cat)])
                        for family in ['unit_classification','regression']:
                            # Targets retain non-integer observed fractional units explicitly.
                            y=tr[target]
                            if family=='unit_classification' and y.nunique()<2:
                                pred=np.full(len(te),float(y.iloc[0]));model=None
                            else:
                                estimator=LGBMClassifier(n_estimators=100,num_leaves=12,min_child_samples=20,verbosity=-1,n_jobs=2,random_state=protocol['seed']) if family=='unit_classification' else LGBMRegressor(n_estimators=100,num_leaves=12,min_child_samples=20,verbosity=-1,n_jobs=2,random_state=protocol['seed'])
                                model=make_pipeline(transform,estimator)
                                model.fit(tr[cols],y.astype(str) if family=='unit_classification' else y)
                                pred=model.predict(te[cols]).astype(float)
                            pred=np.maximum(0,np.rint(pred))
                            observed=te[target].to_numpy();positive=observed>0
                            stage1=predictions[(predictions.fold==fold)&(predictions.level==level)&(predictions.option_type==right)&(predictions.action==action)&(predictions.feature_set==fs)] if len(predictions) else pd.DataFrame()
                            gates=te.observation_id.map(stage1.set_index('observation_id').prediction if len(stage1) else {}).fillna(0).to_numpy()
                            joint=pred*gates
                            row=dict(fold=fold,level=level,option_type=right,role=role,feature_set=fs,model=family,
                                test_cycles=len(test_ids),conditional_events=int(positive.sum()),
                                exact_units_accuracy=float(np.mean(pred[positive]==observed[positive])) if positive.any() else np.nan,
                                mean_absolute_units_error=float(np.mean(np.abs(pred[positive]-observed[positive]))) if positive.any() else np.nan,
                                joint_exact_accuracy=float(np.mean(joint==observed)),
                                joint_nonzero_exact_accuracy=float(np.mean(joint[positive]==observed[positive])) if positive.any() else np.nan,
                                quantity_direction_agreement=float(np.mean((joint>0)==positive)),
                                stage1_available=bool(len(stage1)),selection='fixed model settings; no P&L optimization')
                            scores.append(row)
                            ef=te[['observation_id','cycle_id','underlying','expiry_date','second','level','option_type','strike']].copy()
                            ef=ef.assign(fold=fold,role=role,feature_set=fs,model=family,actual_units=observed,
                                conditional_predicted_units=pred,predicted_units=joint,absolute_error=np.abs(joint-observed),stage1_gate=gates)
                            errors.append(ef)
                            if fs=='full' and family=='regression':
                                key=f'quantity_fold{fold}_{level}_{right}_{role}'
                                path=out/'selected_model_configurations'/f'{key}.pkl'
                                with path.open('wb') as f:pickle.dump(model,f)
                                conf=dict(fold=fold,level=level,option_type=right,role=role,features=cols,model_path=path.name,
                                    constant=float(y.iloc[0]) if model is None else None,train_cycles=train_ids,test_cycles=test_ids,
                                    fractional_units='recorded in truth; simulated requests rounded to whole observed base units')
                                (path.with_suffix('.json')).write_text(json.dumps(conf,indent=2));manifests.append(conf)
    score=pd.DataFrame(scores);error=pd.concat(errors,ignore_index=True) if errors else pd.DataFrame()
    score.to_csv(out/'allocation_model_scores.csv',index=False)
    error.to_csv(out/'quantity_prediction_errors.csv',index=False)
    if len(error):
        grouped=error[error.level.eq('side')].pivot_table(index=['fold','cycle_id','second','role','feature_set','model'],columns='option_type',values=['actual_units','predicted_units'],aggfunc='sum')
        grouped.columns=['_'.join(x) for x in grouped.columns];grouped=grouped.reset_index()
        if all(x in grouped for x in ['actual_units_CE','actual_units_PE','predicted_units_CE','predicted_units_PE']):
            grouped['actual_symmetric']=grouped.actual_units_CE.eq(grouped.actual_units_PE)
            grouped['predicted_symmetric']=grouped.predicted_units_CE.eq(grouped.predicted_units_PE)
        grouped.to_csv(out/'quantity_symmetry.csv',index=False)
    return score,manifests
