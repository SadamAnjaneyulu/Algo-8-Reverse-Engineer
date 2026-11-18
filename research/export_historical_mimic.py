"""Export executable JSON decision programs fitted to every observed label.

These are deliberately curve-fitted historical mimics, not original Algo 8 code.
"""
import argparse
import csv
import json

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.tree import DecisionTreeClassifier,export_text

from audit_strike_hedge_rules import OUT,logs
from combo_features import datasets
from search_rule_combinations import decorate,late_dataset,tree_structure


def fit_model(rows,labels,features):
    x=np.array([[np.nan if r.get(k) is None else r[k] for k in features] for r in rows],dtype=float)
    imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True);values=imputer.fit_transform(x)
    tree=DecisionTreeClassifier(min_samples_leaf=1,random_state=20261026);tree.fit(values,labels)
    model=dict(input_features=features,median_statistics=imputer.statistics_.tolist(),missing_indicator_features=imputer.indicator_.features_.tolist(),
               tree=tree_structure(tree,imputer.get_feature_names_out(features).tolist()),
               rows=len(rows),leaves=int(tree.get_n_leaves()),fit_kind='all_observed_resubstitution')
    actual=tree.predict(values).tolist();reproduced=predict_model(model,rows)
    if actual!=reproduced:raise ValueError('Exported program fails to reproduce fitted estimator.')
    model['historical_exact_rate']=float(np.mean(np.array(actual)==np.array(labels)))
    return model,export_text(tree,feature_names=model['tree']['feature_names'],decimals=8,max_depth=int(tree.get_depth())+1)


def predict_model(model,rows):
    tree=model['tree'];result=[]
    for row in rows:
        original=[np.nan if row.get(k) is None else float(row[k]) for k in model['input_features']]
        values=[model['median_statistics'][i] if not np.isfinite(v) else v for i,v in enumerate(original)]
        values.extend(float(not np.isfinite(original[i])) for i in model['missing_indicator_features'])
        values=np.asarray(values,dtype=np.float32);node=0
        while tree['children_left'][node]>=0:
            node=tree['children_left'][node] if values[tree['feature'][node]]<=tree['threshold'][node] else tree['children_right'][node]
        result.append(tree['classes'][int(np.argmax(tree['values'][node][0]))])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--flow',action='store_true');args=p.parse_args()
    source='combo_flow_action' if args.flow else 'combo_action';programs=json.loads((OUT/(source+'_programs.json')).read_text())
    slow,fast=datasets(include_flow=args.flow);decorate(slow);decorate(fast);late=decorate(late_dataset());models={};texts=[]
    targets={'fresh_pairs':'paired_sale','extra_pairs':'paired_sale','covers':'short_cover','protection':'new_long','quarter_pairs':'quarter_target','large_late_protection':'large_long'}
    for name,spec in programs.items():
        phase,task=name.split('|');dataset=slow if task=='quarter_pairs' else late if task=='large_late_protection' else fast;target=targets[task]
        rows=[r for r in dataset if r['phase']==phase and
              (r[target] is not None if task=='quarter_pairs' else bool(r['off_quarter']) if task=='extra_pairs' else r['clock']>='14:45' if task=='large_late_protection' else True)]
        features=[k for k in spec['tree']['structure']['feature_names'] if not k.startswith('missingindicator_')]
        model,text=fit_model(rows,np.array([bool(r[target]) for r in rows]),features);models[name]=model;texts.append(name+'\n'+text)
    if not args.flow:
        targets_bykey={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in csv.DictReader((OUT/'addition_decision_opportunities.csv').open())}
        rows=[r for r in slow if r['quarter_target'] is not None];labels=[]
        for r in rows:
            target=targets_bykey[(r['underlying'],r['expiry_date'],r['date'],r['clock'])];unit=logs.UNIT[r['underlying']]
            labels.append(f"{float(target['new_ce_quantity'])/unit:g}|{float(target['new_pe_quantity'])/unit:g}")
        # Use the causal numeric inputs of the quarter-action model; no quantities
        # or selected strikes from the target window are admitted as predictors.
        features=models['preexpiry|quarter_pairs']['input_features']
        model,text=fit_model(rows,np.array(labels),features);models['allocation_quantity']=model;texts.append('allocation_quantity\n'+text)
    prefix='combo_full_history_flow' if args.flow else 'combo_full_history'
    (OUT/(prefix+'_programs.json')).write_text(json.dumps(dict(warning='All observed labels used for fitting. Historical mimic only; not original code or independent evaluation.',models=models),indent=2,allow_nan=False)+'\n')
    (OUT/(prefix+'_rules.txt')).write_text('\n\n'.join(texts).rstrip()+'\n')
    print(json.dumps({name:dict(rows=m['rows'],leaves=m['leaves'],historical_exact_rate=m['historical_exact_rate']) for name,m in models.items()},indent=2))


if __name__=='__main__':main()
