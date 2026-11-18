"""Conditional allocation sizing and explicitly retrospective configuration fits."""
import csv
import json
from collections import Counter,defaultdict
from datetime import datetime
from statistics import mean

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier,export_text

from combo_features import datasets,context_grid
from audit_strike_hedge_rules import OUT,logs,write
from strategy_rule_features import predicate_grid


def quantity_score(rows,truth,predicted):
    actual=np.array([[float(v) for v in y.split('|')] for y in truth]);guess=np.array([[float(v) for v in y.split('|')] for y in predicted])
    exact=np.all(actual==guess,axis=1);nonzero=np.any(actual>0,axis=1);bycycle=defaultdict(list)
    for r,hit in zip(rows,exact):bycycle[r['cycle']].append(bool(hit))
    return dict(opportunities=len(rows),actual_positive_opportunities=int(nonzero.sum()),exact_joint_quantity=int(exact.sum()),exact_rate=float(exact.mean()),
        nonzero_exact_rate=float(exact[nonzero].mean()) if nonzero.any() else None,
        mean_absolute_units_per_right=float(abs(actual-guess).mean()),cycle_mean_exact=mean(mean(v) for v in bycycle.values()),
        false_positive_allocations=int(np.sum(~nonzero&np.any(guess>0,axis=1))),missed_allocations=int(np.sum(nonzero&~np.any(guess>0,axis=1))))


def quantity_clock(train,rows,labels):
    table=defaultdict(Counter)
    for i in train:table[(rows[i]['underlying'],rows[i]['phase'],rows[i]['clock'])][labels[i]]+=1
    return [min(table[(r['underlying'],r['phase'],r['clock'])],key=lambda y:(-table[(r['underlying'],r['phase'],r['clock'])][y],y))
            if table[(r['underlying'],r['phase'],r['clock'])] else '0|0' for r in rows]


def best_break(values,dates,classification=False):
    """One retrospective change point, at least three observed dates each side."""
    best=None
    for cut in range(3,len(values)-2):
        left,right=values[:cut],values[cut:]
        a=Counter(left).most_common(1)[0][0] if classification else float(np.median(left))
        b=Counter(right).most_common(1)[0][0] if classification else float(np.median(right))
        loss=sum(v!=a for v in left)+sum(v!=b for v in right) if classification else sum(abs(v-a) for v in left)+sum(abs(v-b) for v in right)
        key=(loss,cut)
        if best is None or key<best[0]:best=(key,dict(first_later_date=dates[cut],earlier_value=a,later_value=b,residual_loss=float(loss),earlier_dates=cut,later_dates=len(right)))
    return best[1] if best else None


def configuration_fits():
    fits=[]
    opportunities=list(csv.DictReader((OUT/'addition_decision_opportunities.csv').open()))
    wings=list(csv.DictReader((OUT/'trigger_initial_wings.csv').open()))
    for u in ('NIFTY','SENSEX'):
        rs=sorted([r for r in opportunities if r['underlying']==u and r['phase']=='preexpiry' and r['clock']=='13:15'],key=lambda r:r['date'])
        result=best_break([int(r['target']) for r in rs],[r['date'] for r in rs],True)
        if result:fits.append(dict(underlying=u,series='13:15 observed attendance',**result))
        for right in ('CE','PE'):
            rs=sorted([r for r in wings if r['underlying']==u and r['option_type']==right],key=lambda r:r['event_time_ist'])
            result=best_break([float(r['outward_gap']) for r in rs],[r['event_time_ist'][:10] for r in rs])
            if result:fits.append(dict(underlying=u,series=right+' first seed gap',**result))
    write('combo_configuration_change_points.csv',fits)
    return fits


def main():
    slow,_=datasets();targets={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in csv.DictReader((OUT/'addition_decision_opportunities.csv').open())}
    rows=[r for r in slow if r['quarter_target'] is not None]
    labels=[]
    for r in rows:
        target=targets[(r['underlying'],r['expiry_date'],r['date'],r['clock'])];unit=logs.UNIT[r['underlying']]
        labels.append(f"{float(target['new_ce_quantity'])/unit:g}|{float(target['new_pe_quantity'])/unit:g}")
        r['clock_minute']=int(r['clock'][:2])*60+int(r['clock'][3:])-555
    labels=np.array(labels);train=np.array([i for i,r in enumerate(rows) if r['split']=='calibration']);test=np.array([i for i,r in enumerate(rows) if r['split']=='evaluation'])
    fields=[k for k in rows[0] if (predicate_grid([k]) or context_grid([k])) and not k.endswith('_ist')]+['clock_minute','is_sensex','is_expiry']
    fields=sorted(set(fields));x=np.array([[np.nan if r.get(k) is None else r[k] for k in fields] for r in rows],dtype=float)
    groups=np.array([rows[i]['cycle'] for i in train]);folds=GroupKFold(n_splits=4);scores=[];best=None
    for depth in (2,3,4,5,6,8,12,None):
        for leaf in (1,3,5,10,20,40):
            pr=np.empty(len(train),dtype=object)
            for a,b in folds.split(train,groups=groups):
                imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)
                ax=imputer.fit_transform(x[train[a]]);bx=imputer.transform(x[train[b]])
                tree=DecisionTreeClassifier(max_depth=depth,min_samples_leaf=leaf,random_state=20261026);tree.fit(ax,labels[train[a]]);pr[b]=tree.predict(bx)
            stat=quantity_score([rows[i] for i in train],labels[train],pr)
            scores.append(dict(depth=depth if depth is not None else 'unlimited',minimum_leaf=leaf,**stat))
            key=(stat['cycle_mean_exact'],-stat['mean_absolute_units_per_right'],-(depth or 1000),leaf)
            if best is None or key>best[0]:best=(key,depth,leaf,stat)
    imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True);ax=imputer.fit_transform(x[train]);bx=imputer.transform(x[test])
    tree=DecisionTreeClassifier(max_depth=best[1],min_samples_leaf=best[2],random_state=20261026);tree.fit(ax,labels[train]);pr=tree.predict(bx)
    clock=np.array(quantity_clock(train,rows,labels))[test];evaluation=[];predictions=[]
    for kind,predicted in [('clock_quantity',clock),('combined_tree_quantity',pr)]:
        evaluation.append(dict(kind=kind,**quantity_score([rows[i] for i in test],labels[test],predicted)))
        for i,p in zip(test,predicted):predictions.append(dict(underlying=rows[i]['underlying'],expiry_date=rows[i]['expiry_date'],date=rows[i]['date'],phase=rows[i]['phase'],clock=rows[i]['clock'],kind=kind,actual_units=labels[i],predicted_units=p,exact=p==labels[i]))
    all_imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True);all_x=all_imputer.fit_transform(x)
    memorizer=DecisionTreeClassifier(min_samples_leaf=1,random_state=20261026);memorizer.fit(all_x,labels)
    full=dict(**quantity_score(rows,labels,memorizer.predict(all_x)),leaves=int(memorizer.get_n_leaves()),note='All-observed resubstitution, not a later-cycle result.')
    config=configuration_fits()
    write('combo_sizing_calibration_cv.csv',scores);write('combo_sizing_evaluation.csv',evaluation);write('combo_sizing_predictions.csv',predictions)
    (OUT/'combo_sizing_rules.txt').write_text(export_text(tree,feature_names=imputer.get_feature_names_out(fields).tolist(),decimals=4).rstrip()+'\n')
    summary=dict(calibration_model_settings=len(scores),calibration_fold_fits=len(scores)*4,selected_parameters=dict(depth=best[1],minimum_leaf=best[2]),
        calibration_cv=best[3],evaluation=evaluation,all_observed_curve_fit=full,configuration_change_points=config,
        note='Targets are CE/PE short units within observed quarter windows. This is not an account-margin formula. Configuration fits use the full observed date sequence; they do not identify no-trade eligibility or prove a software version change.')
    (OUT/'combo_sizing_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
