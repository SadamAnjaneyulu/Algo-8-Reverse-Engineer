"""Conditional addition-pattern study. Not original code or an alpha backtest.

Run: python research/discover_addition_patterns.py --plot
Requires numpy/scikit-learn; matplotlib is optional for figures.
"""
import argparse
import csv
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean, median

import numpy as np
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, brier_score_loss
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text

import analyze_index_triggers as logs
from analyze_iv_theta_hypothesis import Market, iv_change

ROOT=logs.ROOT
OUT=logs.OUT
UNITS={'NIFTY':65,'SENSEX':20}
MARKET_FEATURES=['spot_return1_pct','spot_return5_pct','spot_return15_pct','spot_abs_return5_pct',
 'spot_range5_pct','spot_range15_pct','reference_straddle_pct_spot','reference_premium_change5_pct','reference_iv_pct','iv_change15_points',
 'last_pair_spot_gap_steps','last_pair_abs_spot_gap_steps','last_pair_premium_change_pct','last_pair_max_leg_change_pct']
STATE_FEATURES=['short_ce_units','short_pe_units','long_ce_units','long_pe_units','has_short_book',
 'recent_short_covers5_units','time_since_last_pair_min','equity_pct_capital','equity_change5_pct_capital','drawdown_pct_capital']
META=['is_sensex','is_expiry','calendar_dte']


def write(name,rows):
    if rows:
        with (OUT/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
            w.writeheader();w.writerows(rows)


def parent_orders(rows):
    byrow={r['source']:r for r in rows}
    groups=defaultdict(list)
    tags={}
    with (ROOT/'Trades_GKOHNP140.csv').open(newline='',encoding='utf-8-sig') as f:
        for source,raw in enumerate(csv.reader(f),1):
            label=datetime.strptime(raw[23],'%m/%d/%Y %H:%M').replace(tzinfo=logs.IST)
            key=(str(label.date()),raw[3],raw[4])
            tags.setdefault(raw[166],f'cohort_{len(tags)+1}')
            groups[key].append((raw,byrow[source],label,tags[raw[166]]))
    orders=[]
    mixed=0
    for group in groups.values():
        raw,first,label,tag=group[0]
        if raw[11]!='Sell':
            continue
        if not any(r['opening']>0 for _,r,_,_ in group):
            continue
        pure=all(r['opening']==r['q'] and r['opening']==r['reverse_opening'] for _,r,_,_ in group)
        if not pure:
            mixed+=1;continue
        earliest=min((r for _,r,_,_ in group),key=lambda r:r['t'])
        last=max(r['t'] for _,r,_,_ in group)
        q=sum(r['q'] for _,r,_,_ in group)
        if q!=int(raw[19]) or any(x[2]!=label or x[1]['side']!='Sell' or x[1]['strike']!=first['strike'] or x[1]['ot']!=first['ot'] for x in group):
            raise ValueError('Parent order quantity/identity/label did not reconcile.')
        orders.append(dict(underlying=first['u'],expiry_date=str(first['expiry']),strike=first['strike'],option_type=first['ot'],
            quantity=q,order_label_ist=label.isoformat(),first_fill_ist=earliest['t'].isoformat(),last_fill_ist=last.isoformat(),
            first_fill_minus_label_seconds=(earliest['t']-label).total_seconds(),anonymous_tag_cohort=tag,
            source_rows=';'.join(str(r['source']) for _,r,_,_ in group)))
    return orders,dict(total_parent_orders=len(groups),pure_new_short_parents=len(orders),mixed_or_tie_sensitive_new_short_parents_excluded=mixed)


def parent_pairs(orders):
    groups=defaultdict(list)
    for r in orders:
        groups[(r['underlying'],r['expiry_date'],r['order_label_ist'],r['strike'])].append(r)
    result=[]
    for (u,e,t,k),rs in sorted(groups.items()):
        if {r['option_type'] for r in rs}!={'CE','PE'}:
            continue
        result.append(dict(underlying=u,expiry_date=e,label=t,strike=k,
            ce_qty=sum(r['quantity'] for r in rs if r['option_type']=='CE'),pe_qty=sum(r['quantity'] for r in rs if r['option_type']=='PE'),
            first_fill=min(r['first_fill_ist'] for r in rs),last_fill=max(r['last_fill_ist'] for r in rs),
            parent_orders=len(rs),source_rows=';'.join(r['source_rows'] for r in rs)))
    return result


def contains_pair(orders):
    strikes=defaultdict(set)
    for r in orders:strikes[r['strike']].add(r['option_type'])
    return any(v=={'CE','PE'} for v in strikes.values())


def execution_bursts(orders):
    sessions=defaultdict(list)
    for r in orders:sessions[(r['underlying'],r['expiry_date'],r['first_fill_ist'][:10])].append(r)
    result=[]
    for (u,expiry,day),rs in sorted(sessions.items()):
        clusters=[]
        for r in sorted(rs,key=lambda x:x['first_fill_ist']):
            t=datetime.fromisoformat(r['first_fill_ist'])
            if not clusters or (t-datetime.fromisoformat(clusters[-1][-1]['first_fill_ist'])).total_seconds()>2:
                clusters.append([])
            clusters[-1].append(r)
        for batch in clusters:
            bystrike=defaultdict(list)
            for r in batch:bystrike[r['strike']].append(r)
            for strike,parts in bystrike.items():
                if not contains_pair(parts):continue
                t=min(datetime.fromisoformat(r['first_fill_ist']) for r in parts)
                result.append(dict(underlying=u,expiry_date=expiry,event_time_ist=t.isoformat(),event_minute_ist=t.replace(second=0).isoformat(),
                    strike=strike,parent_orders=len(parts),ce_quantity=sum(r['quantity'] for r in parts if r['option_type']=='CE'),
                    pe_quantity=sum(r['quantity'] for r in parts if r['option_type']=='PE'),
                    first_order_label=min(r['order_label_ist'] for r in parts),
                    source_rows=';'.join(r['source_rows'] for r in parts)))
    return result


def in_quarter_window(t):
    return t.minute%15 in (0,1,2) or (t.minute%15==14 and t.second>=58)


class FeatureBuilder:
    def __init__(self,market,rows,index,paired_fills,equity):
        self.market=market;self.rows=rows;self.index=index;self.paired=paired_fills;self.equity=equity;self.cache={}

    def at(self,t):
        if t in self.cache:
            return dict(self.cache[t])
        # One-minute embargo: label/first-fill clocks disagree by as much as
        # -1 second. No target's own fill or same-window price enters features.
        cutoff=t-timedelta(minutes=1)
        prev=cutoff-timedelta(minutes=1)
        day=str(t.date());clock=prev.strftime('%H:%M');u=self.market.u
        r={k:None for k in MARKET_FEATURES+STATE_FEATURES+['reference_straddle_price']}
        r.update(is_sensex=int(u=='SENSEX'),is_expiry=int(day==self.market.expiry),
                 calendar_dte=(datetime.fromisoformat(self.market.expiry).date()-t.date()).days,
                 feature_cutoff_ist=cutoff.isoformat(),last_completed_bar_start_ist=prev.isoformat())
        past=[x for x in self.rows if x['t']<cutoff]
        inv=Counter()
        for x in past:
            inv[(x['strike'],x['ot'])]+=x['signed']
        for ot in ('CE','PE'):
            r['short_'+ot.lower()+'_units']=sum(max(-q,0) for (k,o),q in inv.items() if o==ot)/UNITS[u]
            r['long_'+ot.lower()+'_units']=sum(max(q,0) for (k,o),q in inv.items() if o==ot)/UNITS[u]
        r['has_short_book']=int(any(q<0 for q in inv.values()))
        r['recent_short_covers5_units']=sum(x['q']-x['opening'] for x in past if x['side']=='Buy' and cutoff-timedelta(minutes=5)<=x['t'])/UNITS[u]
        bars=self.index.get((u,day),[])
        lookup={x['t'].strftime('%H:%M'):x for x in bars}
        b=lookup.get(clock)
        if b:
            spot=b['close']
            for n in (1,5,15):
                old=lookup.get((prev-timedelta(minutes=n)).strftime('%H:%M'))
                if old:
                    r[f'spot_return{n}_pct']=100*(spot/old['close']-1)
                if n in (5,15):
                    history=[x for x in bars if prev-timedelta(minutes=n-1)<=x['t']<=prev]
                    if len(history)==n:
                        r[f'spot_range{n}_pct']=100*(max(x['high'] for x in history)-min(x['low'] for x in history))/spot
            r['spot_abs_return5_pct']=abs(r['spot_return5_pct']) if r['spot_return5_pct'] is not None else None
        current=self.equity.get((day,clock))
        old=self.equity.get((day,(prev-timedelta(minutes=5)).strftime('%H:%M')))
        if current is not None:
            r['equity_pct_capital']=current/20_000_000*100
            if old is not None:r['equity_change5_pct_capital']=(current-old)/20_000_000*100
            history=[v for (d,c),v in self.equity.items() if v is not None and (d<day or (d==day and c<=clock))]
            r['drawdown_pct_capital']=(current-max(history))/20_000_000*100 if history else None
        previous=[p for p in self.paired if datetime.fromisoformat(p['event_minute_ist'])+timedelta(minutes=1)<=cutoff]
        if previous:
            last=max(previous,key=lambda x:(x['first_leg_time_ist'],x['strike']))
            r['time_since_last_pair_min']=(cutoff-datetime.fromisoformat(last['first_leg_time_ist'])).total_seconds()/60
            if b:
                r['last_pair_spot_gap_steps']=(b['close']-last['strike'])/(50 if u=='NIFTY' else 100)
                r['last_pair_abs_spot_gap_steps']=abs(r['last_pair_spot_gap_steps'])
            c,p=self.market.bar(day,last['strike'],'CE',clock),self.market.bar(day,last['strike'],'PE',clock)
            if c and p:
                ce,pe=last['weighted_sold_ce_premium'],last['weighted_sold_pe_premium']
                r['last_pair_premium_change_pct']=100*((c['close']+p['close'])/(ce+pe)-1)
                r['last_pair_max_leg_change_pct']=max(100*(c['close']/ce-1),100*(p['close']/pe-1))
        # Only an already observed paired sale supplies the option reference.
        # A future selected strike must not determine feature quote availability.
        state=self.market.state(day,clock,fixed_strike=last['strike']) if previous else None
        if state:
            r['reference_iv_pct']=100*state['iv']
            c,p=self.market.bar(day,state['strike'],'CE',clock),self.market.bar(day,state['strike'],'PE',clock)
            r['reference_straddle_price']=c['close']+p['close']
            r['reference_straddle_pct_spot']=100*(c['close']+p['close'])/state['spot_guide']
            then=(prev-timedelta(minutes=5)).strftime('%H:%M')
            oc,op=self.market.bar(day,state['strike'],'CE',then),self.market.bar(day,state['strike'],'PE',then)
            if oc and op and oc['close']+op['close']>0:
                r['reference_premium_change5_pct']=100*((c['close']+p['close'])/(oc['close']+op['close'])-1)
            change=iv_change(self.market,state,day,(prev-timedelta(minutes=15)).strftime('%H:%M'))
            if change:r['iv_change15_points']=change['iv_change_points']
        self.cache[t]=dict(r)
        return r


def clock_prob(training,row):
    key=(row['underlying'],row['phase'],row['clock'])
    rs=training.get(key,[])
    return (sum(rs)+1)/(len(rs)+2)


def clock_table(rows):
    result=defaultdict(list)
    for r in rows:result[(r['underlying'],r['phase'],r['clock'])].append(r['target'])
    return result


def metrics(y,p):
    z=[int(x>=.5) for x in p]
    tp=sum(a==1 and b==1 for a,b in zip(y,z));fp=sum(a==0 and b==1 for a,b in zip(y,z));fn=sum(a==1 and b==0 for a,b in zip(y,z))
    pos=int(sum(y));neg=len(y)-pos
    return dict(rows=len(y),positives=pos,negatives=neg,precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/pos if pos else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                balanced_accuracy=float(balanced_accuracy_score(y,z)) if pos and neg else None,
                accuracy=mean(a==b for a,b in zip(y,z)),brier=float(brier_score_loss(y,p)))


def train_tree(train,test,features,max_depth=3,min_leaf=40):
    x=np.array([[np.nan if r[k] is None else r[k] for k in features] for r in train],dtype=float)
    z=np.array([[np.nan if r[k] is None else r[k] for k in features] for r in test],dtype=float)
    y=np.array([r['target'] for r in train],dtype=int)
    imputer=SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)
    x=imputer.fit_transform(x);z=imputer.transform(z)
    names=imputer.get_feature_names_out(features).tolist()
    tree=DecisionTreeClassifier(max_depth=max_depth,min_samples_leaf=min_leaf,random_state=20261026)
    tree.fit(x,y)
    path=tree.decision_path(x).tocsc();parent={}
    for node in range(tree.tree_.node_count):
        for child in (tree.tree_.children_left[node],tree.tree_.children_right[node]):
            if child>=0:parent[child]=node
    support={}
    for node in range(tree.tree_.node_count):
        idx=path.indices[path.indptr[node]:path.indptr[node+1]]
        support[node]=dict(rows=len(idx),cycles=len({train[i]['cycle'] for i in idx}),positives=int(y[idx].sum()))
    predictions=[]
    for leaf in tree.apply(z):
        node=int(leaf)
        while support[node]['cycles']<3 and node in parent:node=parent[node]
        s=support[node];predictions.append((s['positives']+1)/(s['rows']+2))
    importance={names[i]:float(v) for i,v in enumerate(tree.feature_importances_) if v>0}
    return predictions,dict(rules=export_text(tree,feature_names=names,decimals=4),node_support=support,
                            importance=importance,minimum_cycles_backoff=3)


def afternoon_candidate(train,test):
    """Exploratory one-condition search, selected on earlier-cycle CV only."""
    a=[r for r in train if r['underlying']=='NIFTY' and r['phase']=='preexpiry' and r['clock']>='13:00']
    b=[r for r in test if r['underlying']=='NIFTY' and r['phase']=='preexpiry' and r['clock']>='13:00']
    candidates=['reference_straddle_price','reference_straddle_pct_spot','equity_pct_capital',
        'last_pair_abs_spot_gap_steps','spot_abs_return5_pct','iv_change15_points',
        'last_pair_premium_change_pct','recent_short_covers5_units','time_since_last_pair_min']
    groups=sorted({r['cycle'] for r in a});scores=[]
    for field in candidates+['clock_only']:
        predicted=[];truth=[]
        for group in groups:
            earlier=[r for r in a if r['cycle']!=group];held=[r for r in a if r['cycle']==group]
            if field=='clock_only':
                tab=clock_table([r for r in train if r['cycle']!=group])
                pr=[clock_prob(tab,r) for r in held]
            else:
                pr,_=train_tree(earlier,held,[field],max_depth=1,min_leaf=10)
            predicted.extend(pr);truth.extend(r['target'] for r in held)
        scores.append(dict(feature=field,**metrics(truth,predicted)))
    chosen=min(scores,key=lambda r:r['brier'])['feature']
    if chosen=='clock_only':
        table=clock_table(train);prob=[clock_prob(table,r) for r in b];rule=dict(rules='Clock-only table wins the calibration comparison.')
    else:
        prob,rule=train_tree(a,b,[chosen],max_depth=1,min_leaf=10)
    examples=[dict(underlying=r['underlying'],expiry_date=r['expiry_date'],clock=r['clock'],target=r['target'],
                   feature_value=r.get(chosen),probability=p,predicted=int(p>=.5)) for r,p in zip(b,prob)]
    return dict(calibration_cycles=len(groups),evaluation_cycles=len({r['cycle'] for r in b}),
        selected_feature=chosen,training_cycle_cross_validation=scores,selected_rule=rule,
        evaluation_metrics=metrics([r['target'] for r in b],prob),
        note='Secondary exploratory stump study added after global-model results; feature selected only on calibration cycle CV. Not original code or an independent holdout.'),examples


def boot_improvement(rows,draws=10000):
    groups=defaultdict(list)
    for r in rows:
        d=datetime.fromisoformat(r['expiry_date']).date().isocalendar()
        groups[(d.year,d.week)].append(r['improvement'])
    keys=list(groups);rng=random.Random(20261026);values=[]
    for _ in range(draws):
        sample=[v for k in rng.choices(keys,k=len(keys)) for v in groups[k]]
        values.append(sum(sample)/len(sample))
    values.sort()
    return dict(weeks=len(keys),mean=sum(r['improvement'] for r in rows)/len(rows),
                lower=values[int(.025*(draws-1))],upper=values[int(.975*(draws-1))],draws=draws)


def compare_predictions(predictions,opportunities):
    """Paired comparisons, including state controls, with identical rows."""
    key=lambda r:(r['underlying'],r['expiry_date'],r['date'],r['clock'])
    contexts={key(r):r for r in opportunities}
    models=defaultdict(dict)
    for r in predictions:models[r['model']][key(r)]=r
    result=[]
    comparisons=[('clock_market','clock_open_book'),('clock_state_market','clock_state'),
                 ('market_only','clock_only')]
    for candidate,baseline in comparisons:
        if models[candidate].keys()!=models[baseline].keys():
            raise ValueError('Compared predictions do not have identical opportunities.')
        for scope in ('all','preexpiry','active_expiry'):
            differences=[]
            for k,r in models[candidate].items():
                o=contexts[k]
                if scope=='preexpiry' and o['phase']!='preexpiry':continue
                if scope=='active_expiry' and not(o['phase']=='expiry' and o['has_short_book']):continue
                y=r['target'];p=r['probability'];q=models[baseline][k]['probability']
                differences.append(dict(expiry_date=r['expiry_date'],improvement=(q-y)**2-(p-y)**2))
            result.append(dict(candidate=candidate,baseline=baseline,scope=scope,rows=len(differences),
                               **boot_improvement(differences)))
    return result


def schedule_summary(data):
    pre=[r for r in data if r['phase']=='preexpiry']
    clocks=sorted({r['clock'] for r in pre})
    universal=[c for c in clocks if all(r['target'] for r in pre if r['clock']==c)]
    selected=[r for r in pre if r['clock'] in universal]
    regimes={}
    for field in ('spot_return5_pct','reference_premium_change5_pct','iv_change15_points'):
        values=[r[field] for r in selected if r[field] is not None]
        regimes[field]=dict(observations=len(values),positive=sum(v>0 for v in values),
                            negative=sum(v<0 for v in values),zero=sum(v==0 for v in values),
                            minimum=min(values),maximum=max(values))
    return dict(observed_sessions=len({(r['underlying'],r['date']) for r in pre}),
        universal_windows=universal,positive_session_windows=len(selected),
        strict_fill_window_misses=sum(not r['strict_fill_timing_target'] for r in selected),
        coarse_label_window_misses=sum(not r['label_timing_target'] for r in selected),
        completed_market_contexts=regimes)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plot',action='store_true');args=p.parse_args()
    rows=logs.read_fills();orders,parent_summary=parent_orders(rows);pairs=parent_pairs(orders);bursts=execution_bursts(orders)
    index,_=logs.load_index();fill_pairs=logs.pairing(rows,index)
    bycycle=defaultdict(list);metas=defaultdict(list);replays=defaultdict(dict)
    for r in rows:bycycle[(r['u'],str(r['expiry']))].append(r)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());metas[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    for r in csv.DictReader((OUT/'option_minute_portfolio_replay.csv').open()):
        replays[(r['underlying'],r['expiry_date'])][(r['bar_start_ist'][:10],r['bar_start_ist'][11:16])]=float(r['marked_equity_close']) if r['marked_equity_close']!='' else None
    sessions=[]
    for (u,expiry),rs in bycycle.items():
        for day in sorted({str(r['t'].date()) for r in rs}):
            sessions.append((u,expiry,day,'preexpiry' if day<expiry else 'expiry'))
    off_references={}
    positive_labels=set()
    for r in bursts:
        t=datetime.fromisoformat(r['event_time_ist']);phase='preexpiry' if str(t.date())<r['expiry_date'] else 'expiry'
        key=(r['underlying'],r['expiry_date'],str(t.date()),t.strftime('%H:%M'))
        positive_labels.add(key)
        if '09:30'<=t.strftime('%H:%M')<'14:45' and not in_quarter_window(t):off_references[key]=phase
    control_map={};requested=defaultdict(set)
    for key,phase in off_references.items():
        u,expiry,day,clock=key
        choices=[(v,e,d,clock) for v,e,d,p in sessions if v==u and p==phase and e!=expiry and
                 (e<='2026-08-31')==(expiry<='2026-08-31') and (v,e,d,clock) not in positive_labels]
        choices.sort(key=lambda x:(abs((datetime.fromisoformat(x[2])-datetime.fromisoformat(day)).days),x[2]))
        control_map[key]=choices[:5]
        for v,e,d,c in choices[:5]:requested[(v,e)].add((d,c))
    data=[];excluded=[];presence=[];off_cases=[];strike_checks=[];contexts={}
    for (u,expiry),fills in sorted(bycycle.items()):
        market=Market(u,expiry,metas[(u,expiry)],index)
        cycle_pairs=[r for r in fill_pairs if r['underlying']==u and r['expiry_date']==expiry]
        feature=FeatureBuilder(market,fills,index,cycle_pairs,replays[(u,expiry)])
        pp=[r for r in pairs if r['underlying']==u and r['expiry_date']==expiry]
        bb=[r for r in bursts if r['underlying']==u and r['expiry_date']==expiry]
        oo=[r for r in orders if r['underlying']==u and r['expiry_date']==expiry]
        observed_days=sorted({str(r['t'].date()) for r in fills})
        expected=sorted(market.days)
        for day in expected:
            if day not in observed_days:excluded.append(dict(underlying=u,expiry_date=expiry,date=day,reason='No fill records in export; no-trade versus missing-record interpretation unresolved.'))
        for day in observed_days:
            phase='preexpiry' if day<expiry else 'expiry'
            start=datetime.fromisoformat(day+'T09:30').replace(tzinfo=logs.IST)
            for i in range(21):
                t=start+timedelta(minutes=15*i);end=t+timedelta(minutes=3)
                selected=[r for r in pp if t<=datetime.fromisoformat(r['label'])<end]
                selected_fills=[r for r in cycle_pairs if t<=datetime.fromisoformat(r['event_minute_ist'])<end]
                selected_orders=[r for r in oo if t-timedelta(seconds=2)<=datetime.fromisoformat(r['first_fill_ist'])<end]
                strict_orders=[r for r in oo if t<=datetime.fromisoformat(r['first_fill_ist'])<end]
                label_orders=[r for r in oo if t-timedelta(minutes=1)<=datetime.fromisoformat(r['order_label_ist'])<end]
                feat=feature.at(t)
                # No target's observed first fill is permitted before the
                # conservative feature cutoff, including label clock inversions.
                if any(datetime.fromisoformat(r['first_fill_ist'])<datetime.fromisoformat(feat['feature_cutoff_ist']) for r in selected_orders):
                    raise ValueError('Target fill precedes feature embargo.')
                r=dict(underlying=u,expiry_date=expiry,cycle=u+'|'+expiry,date=day,phase=phase,clock=t.strftime('%H:%M'),
                    split='calibration' if expiry<='2026-08-31' else 'evaluation',target=int(contains_pair(selected_orders)),
                    strict_fill_timing_target=int(contains_pair(strict_orders)),label_timing_target=int(contains_pair(label_orders)),
                    legacy_same_minute_fill_target=int(bool(selected_fills)),legacy_same_label_minute_target=int(bool(selected)),
                    same_label_minute_pair_groups=len(selected),
                    any_new_ce_order=any(x['option_type']=='CE' for x in selected_orders),
                    any_new_pe_order=any(x['option_type']=='PE' for x in selected_orders),
                    new_ce_quantity=sum(x['quantity'] for x in selected_orders if x['option_type']=='CE'),
                    new_pe_quantity=sum(x['quantity'] for x in selected_orders if x['option_type']=='PE'),**feat)
                data.append(r)
        for r in bb:
            event=datetime.fromisoformat(r['event_time_ist']);t=event.replace(second=0)
            if not ('09:30'<=t.strftime('%H:%M')<'14:45'):continue
            b=logs.reference(index,u,t)[0]
            state=market.state(str(t.date()),(t-timedelta(minutes=1)).strftime('%H:%M'))
            strike_checks.append(dict(underlying=u,expiry_date=expiry,event_time_ist=r['event_time_ist'],first_order_label=r['first_order_label'],strike=r['strike'],
                spot_nearest=logs.round_strike(b['close'],u) if b else '',
                forward_nearest=logs.round_strike(state['forward'],u) if state else '',
                first_fill_minus_label_seconds=(event-datetime.fromisoformat(r['first_order_label'])).total_seconds()))
            if not in_quarter_window(event):
                off_cases.append(dict(underlying=u,expiry_date=expiry,date=str(t.date()),phase='preexpiry' if str(t.date())<expiry else 'expiry',
                                      clock=t.strftime('%H:%M'),strike=r['strike'],**feature.at(t)))
                contexts[(u,expiry,str(t.date()),t.strftime('%H:%M'))]=feature.at(t)
        for day,clock in requested[(u,expiry)]:
            t=datetime.fromisoformat(day+'T'+clock).replace(tzinfo=logs.IST)
            contexts[(u,expiry,day,clock)]=feature.at(t)
        print(f'Built features {u} {expiry}',flush=True)
    # Collapse multiple strikes at the same off-clock minute; it is one observed
    # decision-time opportunity, not independent evidence from each child order.
    unique={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in off_cases}
    off_cases=list(unique.values())
    matched=[];off_differences=[]
    for case in off_cases:
        key=(case['underlying'],case['expiry_date'],case['date'],case['clock'])
        controls=[k for k in control_map.get(key,[]) if k in contexts and contexts[k]['has_short_book']==case['has_short_book']][:3]
        for k in controls:
            c=contexts[k]
            matched.append(dict(case_underlying=key[0],case_expiry=key[1],case_clock=key[3],control_expiry=k[1],control_date=k[2],
                phase=case['phase'],**{name:c[name] for name in MARKET_FEATURES+STATE_FEATURES}))
        if controls:
            record=dict(underlying=key[0],expiry_date=key[1],clock=key[3],phase=case['phase'],controls=len(controls),
                        case_recent_covers=case['recent_short_covers5_units']>0,
                        control_recent_covers_fraction=mean(contexts[k]['recent_short_covers5_units']>0 for k in controls))
            for field in ('spot_abs_return5_pct','last_pair_abs_spot_gap_steps','last_pair_max_leg_change_pct','recent_short_covers5_units','iv_change15_points'):
                vals=[contexts[k][field] for k in controls if contexts[k][field] is not None]
                record[field+'_case_minus_control_median']=case[field]-median(vals) if case[field] is not None and vals else None
            off_differences.append(record)
    train=[r for r in data if r['split']=='calibration'];test=[r for r in data if r['split']=='evaluation']
    y=[r['target'] for r in test];table=clock_table(train)
    groups=np.array([r['cycle'] for r in train]);folds=GroupKFold(n_splits=4)
    cross=np.zeros(len(train))
    for a,b in folds.split(train,groups=groups):
        tab=clock_table([train[i] for i in a])
        for i in b:cross[i]=clock_prob(tab,train[i])
    for r,pred in zip(train,cross):r['clock_probability']=float(pred)
    for r in test:r['clock_probability']=clock_prob(table,r)
    models={'clock_only':[r['clock_probability'] for r in test],
            'clock_open_book':[r['clock_probability']*r['has_short_book'] for r in test]};rules={}
    for name,features in [('market_only',META+MARKET_FEATURES),('clock_market',META+['clock_probability']+MARKET_FEATURES),
                          ('clock_spot',META+['clock_probability']+MARKET_FEATURES[:6]+['last_pair_spot_gap_steps','last_pair_abs_spot_gap_steps']),
                          ('clock_state',META+['clock_probability']+STATE_FEATURES),
                          ('clock_state_market',META+['clock_probability']+STATE_FEATURES+MARKET_FEATURES)]:
        models[name],rules[name]=train_tree(train,test,features)
    predictions=[];results=[];cycle_results=[]
    for name,probs in models.items():
        for scope,mask in [('all',[True]*len(test)),('preexpiry',[r['phase']=='preexpiry' for r in test]),
                           ('expiry',[r['phase']=='expiry' for r in test]),
                           ('active_book',[r['has_short_book']==1 for r in test]),
                           ('active_expiry',[r['has_short_book']==1 and r['phase']=='expiry' for r in test]),
                           ('nifty_preexpiry_afternoon',[r['underlying']=='NIFTY' and r['phase']=='preexpiry' and r['clock']>='13:00' for r in test])]:
            chosen=[i for i,v in enumerate(mask) if v]
            if chosen:results.append(dict(model=name,scope=scope,**metrics([y[i] for i in chosen],[probs[i] for i in chosen])))
        improvs=[]
        for i,(r,pred) in enumerate(zip(test,probs)):
            predictions.append(dict(underlying=r['underlying'],expiry_date=r['expiry_date'],date=r['date'],phase=r['phase'],clock=r['clock'],
                model=name,target=r['target'],probability=pred,predicted=int(pred>=.5)))
            improvs.append(dict(expiry_date=r['expiry_date'],improvement=(models['clock_only'][i]-y[i])**2-(pred-y[i])**2))
        if name!='clock_only':
            results.append(dict(model=name,scope='weekly_brier_improvement',**boot_improvement(improvs)))
        for key in sorted({(r['underlying'],r['expiry_date']) for r in test}):
            chosen=[i for i,r in enumerate(test) if (r['underlying'],r['expiry_date'])==key]
            cycle_results.append(dict(model=name,underlying=key[0],expiry_date=key[1],**metrics([y[i] for i in chosen],[probs[i] for i in chosen])))
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            for clock in sorted({r['clock'] for r in data}):
                rs=[r for r in data if r['underlying']==u and r['phase']==phase and r['clock']==clock]
                earlier=[r for r in rs if r['split']=='calibration'];later=[r for r in rs if r['split']=='evaluation']
                presence.append(dict(underlying=u,phase=phase,clock=clock,opportunities=len(rs),primary_pair_present=sum(r['target'] for r in rs),
                    strict_fill_present=sum(r['strict_fill_timing_target'] for r in rs),label_pair_present=sum(r['label_timing_target'] for r in rs),
                    calibration_n=len(earlier),calibration_present=sum(r['target'] for r in earlier),
                    evaluation_n=len(later),evaluation_present=sum(r['target'] for r in later)))
    quantities=[]
    for u in ('NIFTY','SENSEX'):
        for phase in ('preexpiry','expiry'):
            selected=[r for r in orders if r['underlying']==u and ('preexpiry' if r['order_label_ist'][:10]<r['expiry_date'] else 'expiry')==phase]
            quantities.append(dict(underlying=u,phase=phase,parents=len(selected),quantity_mode_counts=dict(Counter(r['quantity'] for r in selected)),
                                   first_fill_differs_from_label_minute=sum(r['first_fill_ist'][:16]!=r['order_label_ist'][:16] for r in selected)))
    focused,focused_rows=afternoon_candidate(train,test)
    off_summary=[]
    for phase in ('preexpiry','expiry'):
        rs=[r for r in off_differences if r['phase']==phase]
        features={}
        for field in ('spot_abs_return5_pct','last_pair_abs_spot_gap_steps','last_pair_max_leg_change_pct','recent_short_covers5_units','iv_change15_points'):
            values=[r[field+'_case_minus_control_median'] for r in rs if r[field+'_case_minus_control_median'] is not None]
            features[field]=dict(cases=len(values),median_difference=median(values) if values else None,case_higher=sum(x>0 for x in values))
        off_summary.append(dict(phase=phase,matched_case_minutes=len(rs),cycles=len({r['expiry_date'] for r in rs}),
            case_minutes_with_recent_covers=sum(r['case_recent_covers'] for r in rs),
            mean_control_recent_cover_fraction=mean(r['control_recent_covers_fraction'] for r in rs) if rs else None,features=features))
    comparisons=compare_predictions(predictions,data)
    summary=dict(parent_audit=parent_summary,opportunities=len(data),calibration_rows=len(train),evaluation_rows=len(test),
                 calibration_cycles=len({r['cycle'] for r in train}),evaluation_cycles=len({r['cycle'] for r in test}),
                 results=results,paired_model_comparisons=comparisons,scheduled_build_up=schedule_summary(data),
                 trees=rules,quantity_patterns=quantities,off_clock_parent_pair_minutes=len(off_cases),
                 focused_nifty_afternoon=focused,off_clock_matched_comparisons=off_summary,
                 runtime_versions=dict(sklearn=sklearn.__version__,numpy=np.__version__),
                 limitations=['Conditional on observed export sessions, inferred zero-start inventory and parent/order timestamp semantics; not the complete eligible no-trade universe.',
                    'All features have a one-minute embargo and only completed quotes; target label and first-fill clocks remain proxies, not original signal timestamps.',
                    'Model-input imputation uses calibration medians plus flags only; no inventory or option-price gap is filled.',
                    'Chronological evaluation has been seen in earlier research; small expiry-week clusters and retrospective traded-contract quote availability limit inference.',
                    'Predicting execution occurrence is not proof of causal decision logic, original-code identity or an economic alpha.'])
    write('addition_parent_orders.csv',orders);write('addition_parent_pair_groups.csv',pairs);write('addition_execution_bursts.csv',bursts)
    write('addition_decision_opportunities.csv',data);write('addition_clock_recurrence.csv',presence)
    write('addition_prediction_evaluation.csv',predictions);write('addition_prediction_cycles.csv',cycle_results)
    write('addition_paired_model_comparisons.csv',comparisons)
    write('addition_session_exclusions.csv',excluded);write('addition_off_clock_contexts.csv',off_cases);write('addition_strike_proxy_checks.csv',strike_checks)
    write('addition_off_clock_controls.csv',matched);write('addition_off_clock_case_differences.csv',off_differences)
    write('addition_nifty_afternoon_candidate.csv',focused_rows)
    (OUT/'addition_pattern_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'addition_rule_candidates.txt').write_text('\n\n'.join(name+'\n'+r['rules']+'\nGroup support: '+json.dumps(r['node_support']) for name,r in rules.items())+'\n')
    print(json.dumps(dict(audit=parent_summary,rows=len(data),results=results),indent=2))
    if args.plot:plot(presence,predictions)


def plot(presence,predictions):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/algo8-matplotlib');os.environ.setdefault('XDG_CACHE_HOME','/tmp/algo8-font-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for u,color in [('NIFTY','#177e89'),('SENSEX','#b55a30')]:
        rs=[r for r in presence if r['underlying']==u and r['phase']=='preexpiry']
        x=list(range(len(rs)));axs[0].plot(x,[100*r['primary_pair_present']/r['opportunities'] for r in rs],label=u,color=color,marker='o',markersize=3)
    axs[0].set(xticks=x,xticklabels=[r['clock'] for r in rs],ylabel='% of observed pre-expiry sessions',title='New-short pairs: quarter −2s through quarter +3min')
    axs[0].tick_params(axis='x',rotation=90);axs[0].legend()
    names=sorted({r['model'] for r in predictions})
    scores=[]
    for name in names:
        rs=[r for r in predictions if r['model']==name];scores.append(brier_score_loss([r['target'] for r in rs],[r['probability'] for r in rs]))
    axs[1].barh(names,scores,color='#177e89');axs[1].set(xlabel='Brier prediction error; lower is better',title='September–October chronological evaluation')
    fig.suptitle('Execution-pattern decoding, not a profitability or alpha test',fontsize=12)
    fig.savefig(OUT/'addition_pattern_evidence.png',dpi=150);svg=OUT/'addition_pattern_evidence.svg';fig.savefig(svg)
    svg.write_text('\n'.join(s.rstrip() for s in svg.read_text().splitlines())+'\n');plt.close(fig)


if __name__=='__main__':main()
