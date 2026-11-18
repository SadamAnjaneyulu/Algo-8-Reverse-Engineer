"""Per-parent stop/target search, including intrabar bounds and entry modules.

FIFO/LIFO ownership is inferred. Intrabar high/low experiments describe touch
bounds; they do not pretend those prices were known before the candle completed.
"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from audit_strike_hedge_rules import ROOT, OUT, logs, Market
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def first_above(values,times,levels):
    positions=np.searchsorted(np.maximum.accumulate(values),levels,side='left')
    return np.where(positions<len(times),times[np.minimum(positions,len(times)-1)],np.inf)


def atom_bank():
    atoms=[dict(family='none',level=0)]
    atoms += [dict(family='loss_pct',level=i) for i in range(1,201)]
    atoms += [dict(family='profit_pct',level=i) for i in range(10,100)]
    atoms += [dict(family='absolute_profit_price',level=x) for x in (.05,.1,.2,.25,.3,.5,.75,1,1.5,2,3,5,7,10,15,20)]
    atoms += [dict(family='trail',level=x,activation=a) for a in (20,40,60) for x in range(5,101,5)]
    return atoms


def crossings(values,prices,times,entry,atoms,mode):
    high=values if mode=='intrabar_bounds' else prices
    result=np.full(len(atoms),np.inf)
    low=np.minimum.accumulate(prices)
    maxima=np.maximum.accumulate(high)
    negative_minima=np.maximum.accumulate(-prices)
    def assign(indices,levels,path):
        where=np.searchsorted(path,levels,side='left')
        result[indices]=np.where(where<len(times),times[np.minimum(where,len(times)-1)],np.inf)
    ix=[i for i,a in enumerate(atoms) if a['family']=='loss_pct']
    assign(ix,[entry*(1+atoms[i]['level']/100) for i in ix],maxima)
    ix=[i for i,a in enumerate(atoms) if a['family']=='profit_pct']
    assign(ix,[-entry*(1-atoms[i]['level']/100) for i in ix],negative_minima)
    ix=[i for i,a in enumerate(atoms) if a['family']=='absolute_profit_price']
    assign(ix,[-atoms[i]['level'] for i in ix],negative_minima)
    for j,a in enumerate(atoms):
        if a['family']=='trail':
            mask=(low<=entry*(1-a['activation']/100))&(prices>=low*(1+a['level']/100))
            ix=np.flatnonzero(mask)
            if len(ix):result[j]=times[ix[0]]
    return result


def choose(matrix,cases,indices,left,right):
    target=np.array([cases[i]['target'] for i in indices])
    fallback=np.array([cases[i]['fallback'] for i in indices])
    subset=matrix[:,indices]
    first=np.minimum(subset[left],subset[right])
    best=None;tested=0
    for lag in (0,1,2):
        predictions=np.minimum(first+lag,fallback)
        errors=np.abs(predictions-target)
        hits=np.sum(errors<=2,axis=1);means=np.mean(np.minimum(errors,600),axis=1)
        complexity=(left!=0).astype(int)+(right!=0).astype(int)
        order=np.lexsort((complexity,means,-hits))
        i=int(order[0]);key=(int(hits[i]),-float(means[i]),-int(complexity[i]),-lag)
        if best is None or key>best[0]:best=(key,i,lag)
        tested+=len(left)
    return best[1:],tested


def main():
    atoms=atom_bank();parents={p['parent_id']:p for p in load_parents() if p['role']=='new_short'}
    rank_groups=defaultdict(list);ranks={}
    for p in parents.values():rank_groups[(p['underlying'],p['expiry_date'],str(p['label'].date()),p['label'].strftime('%H:%M'),p['option_type'])].append(p)
    for batch in rank_groups.values():
        for rank,p in enumerate(sorted(batch,key=lambda p:(p['first'],int(p['sources'].split(';')[0]))),1):ranks[p['parent_id']]=rank
    evidence=list(csv.DictReader((OUT/'allocation_short_first_exit_evidence.csv').open()))
    meta=defaultdict(list);groups=defaultdict(list)
    for p in parents.values():groups[(p['underlying'],p['expiry_date'])].append(p)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m=json.loads(path.read_text());meta[(m['contract']['underlying'],m['contract']['expiry_date'])].append(m)
    index,_=logs.load_index();hitmaps={mode:{} for mode in ('completed_close','intrabar_bounds')};missing={}
    for (u,e),batch in sorted(groups.items()):
        Market(u,e,meta[(u,e)],index)  # Verify stored quote hashes.
        paths=defaultdict(list)
        for m in meta[(u,e)]:
            c=m['contract'];day=c['trade_date']
            with (ROOT/'data/breeze'/m['normalized_path']).open() as f:
                for r in csv.DictReader(f):
                    t=datetime.fromisoformat(r['timestamp_ist'])
                    paths[(c['strike'],c['option_type'])].append((t.timestamp()/60,float(r['high']),float(r['close'])))
        for key in paths:paths[key].sort()
        for p in batch:
            # Discard entry candle: its high can precede the last entry fill.
            entered=p['last'].timestamp()/60
            path=np.array([r for r in paths[(p['strike'],p['option_type'])] if r[0]>=entered])
            if not len(path):continue
            times=path[:,0]+1
            gaps=int(np.sum(np.diff(path[:,0])>1))
            missing[p['parent_id']]=gaps
            for mode in hitmaps:
                hitmaps[mode][p['parent_id']]=crossings(path[:,1],path[:,2],times,p['price'],atoms,mode)
        print('Allocation paths',u,e,flush=True)
    cases=[]
    for r in evidence:
        pid=r['parent_id']
        if pid not in hitmaps['completed_close'] or r['entry_complete_before_cover']!='True':continue
        p=parents[pid];e=p['expiry_date'];target=datetime.fromisoformat(r['first_cover_ist'])
        deadline=datetime.fromisoformat(e+('T15:14' if e>='2026-08-03' else 'T15:25')).replace(tzinfo=logs.IST)
        if p['last']>=deadline:continue
        entry_clock=p['first'].strftime('%H:%M')
        minute=p['first'].hour*60+p['first'].minute
        module='opening' if minute<570 else f'{(minute//15)*15//60:02d}:{(minute//15)*15%60:02d}'
        cases.append(dict(parent_id=pid,underlying=p['underlying'],expiry_date=e,option_type=p['option_type'],
                          phase='preexpiry' if str(p['first'].date())<e else 'expiry',attribution=r['attribution'],
                          split='calibration' if e<='2026-08-31' else 'evaluation',entry_clock=entry_clock,module=module,
                          entry_rank=min(ranks[pid],6),
                          target=target.timestamp()/60,fallback=deadline.timestamp()/60,
                          observed_first_cover_premium_change_pct=float(r['first_cover_premium_change_pct']),
                          path_gap_count=missing[pid]))
    loss=[0]+[i for i,a in enumerate(atoms) if a['family'] in ('loss_pct','trail')]
    profit=[0]+[i for i,a in enumerate(atoms) if a['family'] in ('profit_pct','absolute_profit_price')]
    left=np.repeat(loss,len(profit));right=np.tile(profit,len(loss))
    evaluations=[];predictions=[];programs={};tested=0
    for mode in hitmaps:
        matrix=np.array([hitmaps[mode][c['parent_id']] for c in cases]).T
        for attribution in ('fifo','lifo'):
            for u in ('NIFTY','SENSEX'):
                for phase in ('preexpiry','expiry'):
                    for side in ('CE','PE'):
                        eligible=[i for i,c in enumerate(cases) if c['attribution']==attribution and c['underlying']==u and c['phase']==phase and c['option_type']==side]
                        train=np.array([i for i in eligible if cases[i]['split']=='calibration'],int)
                        test=np.array([i for i in eligible if cases[i]['split']=='evaluation'],int)
                        if not len(train) or not len(test):continue
                        (model,lag),count=choose(matrix,cases,train,left,right);tested+=count
                        module_models={}
                        for module in sorted({cases[i]['module'] for i in train}):
                            ix=np.array([i for i in train if cases[i]['module']==module],int)
                            if len(ix)>=20 and len({cases[i]['expiry_date'] for i in ix})>=3:
                                module_models[module],count=choose(matrix,cases,ix,left,right);tested+=count
                        rank_models={};joint_models={}
                        for rank in sorted({cases[i]['entry_rank'] for i in train}):
                            ix=np.array([i for i in train if cases[i]['entry_rank']==rank],int)
                            if len(ix)>=30 and len({cases[i]['expiry_date'] for i in ix})>=3:
                                rank_models[rank],count=choose(matrix,cases,ix,left,right);tested+=count
                        for module,rank in sorted({(cases[i]['module'],cases[i]['entry_rank']) for i in train}):
                            ix=np.array([i for i in train if cases[i]['module']==module and cases[i]['entry_rank']==rank],int)
                            if len(ix)>=8 and len({cases[i]['expiry_date'] for i in ix})>=4:
                                joint_models[(module,rank)],count=choose(matrix,cases,ix,left,right);tested+=count
                        task='|'.join((mode,attribution,u,phase,side))
                        programs[task]=dict(global_loss=atoms[left[model]],global_profit=atoms[right[model]],lag=lag,
                                            module_rules={k:dict(loss=atoms[left[m]],profit=atoms[right[m]],lag=l) for k,(m,l) in module_models.items()},
                                            rank_rules={str(k):dict(loss=atoms[left[m]],profit=atoms[right[m]],lag=l) for k,(m,l) in rank_models.items()},
                                            module_rank_rules={str(k):dict(loss=atoms[left[m]],profit=atoms[right[m]],lag=l) for k,(m,l) in joint_models.items()})
                        for kind in ('clock_only','global_program','entry_module_program','entry_rank_program','entry_module_rank_program'):
                            rows=[]
                            for i in test:
                                c=cases[i];m,l=module_models.get(c['module'],(model,lag)) if kind=='entry_module_program' else (model,lag)
                                if kind=='entry_rank_program':m,l=rank_models.get(c['entry_rank'],(model,lag))
                                if kind=='entry_module_rank_program':m,l=joint_models.get((c['module'],c['entry_rank']),rank_models.get(c['entry_rank'],(model,lag)))
                                guess=c['fallback'] if kind=='clock_only' else min(matrix[left[m],i]+l,matrix[right[m],i]+l,c['fallback'])
                                row=dict(task=task,model=kind,parent_id=c['parent_id'],underlying=u,expiry_date=c['expiry_date'],
                                         entry_module=c['module'],target=c['target'],predicted=guess,error_minutes=guess-c['target'],
                                         observed_losing_cover=c['observed_first_cover_premium_change_pct']>0,path_gap_count=c['path_gap_count'])
                                rows.append(row);predictions.append(row)
                            losing=[r for r in rows if r['observed_losing_cover']]
                            evaluations.append(dict(task=task,model=kind,later_cases=len(rows),matches2=sum(abs(r['error_minutes'])<=2 for r in rows),
                                match_rate2=np.mean([abs(r['error_minutes'])<=2 for r in rows]),
                                matches5=sum(abs(r['error_minutes'])<=5 for r in rows),
                                losing_cover_cases=len(losing),losing_cover_matches2=sum(abs(r['error_minutes'])<=2 for r in losing),
                                mean_abs_error=np.mean([abs(r['error_minutes']) for r in rows])))
                        print('Tested modules',task,evaluations[-1]['matches2'],'/',len(test),flush=True)
    save_records('deep_allocation_stop_evaluation.csv',evaluations)
    save_records('deep_allocation_stop_predictions.csv.gz',predictions)
    save_records('deep_allocation_stop_cases.csv.gz',cases)
    (OUT/'deep_allocation_stop_programs.json').write_text(json.dumps(programs,indent=2)+'\n')
    (OUT/'deep_allocation_stop_summary.json').write_text(json.dumps(dict(cases=len(cases),atoms=len(atoms),stop_target_pairs=len(left),
        program_context_comparisons=tested,note='Earlier-only per-parent stop/target fits and entry-module refinements. Observed entries, inferred FIFO/LIFO ownership, retrospective inspected later sample; not autonomous. Intrabar high touch is a within-candle bound, not a pre-candle feature. Gap count includes overnight gaps and does not certify full within-session coverage.'),indent=2)+'\n')


if __name__=='__main__':main()
