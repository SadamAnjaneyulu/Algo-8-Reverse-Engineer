"""Separate narrow timer orders from wider management flow when measuring size."""
import json
from collections import Counter, defaultdict
from datetime import datetime,timedelta

import numpy as np

from audit_strike_hedge_rules import OUT,logs
from analyze_side_allocations import load_parents
from rank_trigger_probabilities import save_records


def modal(values):
    counts=Counter(values)
    return min(counts,key=lambda x:(-counts[x],x))


def main():
    parents=load_parents();cycles=defaultdict(list)
    for p in parents:cycles[(p['underlying'],p['expiry_date'])].append(p)
    slots=['09:16']+[f'{m//60:02d}:{m%60:02d}' for m in range(570,871,15)]
    rows=[]
    roles=[('new_short','CE'),('new_short','PE'),('new_long','CE'),('new_long','PE')]
    for (u,e),batch in sorted(cycles.items()):
        for day in sorted({str(p['first'].date()) for p in batch}):
            if day>e:continue
            for slot in slots:
                t=datetime.fromisoformat(day+'T'+slot).replace(tzinfo=logs.IST)
                for end_seconds in (2,5,10,30,60,180):
                    for kind in ('first_fill','label_minute'):
                        candidates=[p for p in batch if t-timedelta(seconds=2)<=p['first']<t+timedelta(seconds=end_seconds)] if kind=='first_fill' else [p for p in batch if p['label']==t]
                        for quantity in ('quantity','requested_quantity'):
                            sizes=[sum(p[quantity] for p in candidates if p['role']==role and p['option_type']==right)/logs.UNIT[u] for role,right in roles]
                            rows.append(dict(underlying=u,expiry_date=e,date=day,phase='preexpiry' if day<e else 'expiry',
                                             clock=slot,split='calibration' if e<='2026-08-31' else 'evaluation',
                                             definition=kind,end_seconds=end_seconds if kind=='first_fill' else 0,quantity_basis=quantity,
                                             short_CE=sizes[0],short_PE=sizes[1],long_CE=sizes[2],long_PE=sizes[3]))
    # Label-minute rows do not vary with the first-fill cutoff.
    unique={(r['underlying'],r['expiry_date'],r['date'],r['clock'],r['definition'],r['end_seconds'],r['quantity_basis']):r for r in rows}
    rows=list(unique.values());evaluations=[];predictions=[]
    wide={(r['underlying'],r['expiry_date'],r['date'],r['clock']):r for r in rows
          if r['definition']=='first_fill' and r['end_seconds']==180 and r['quantity_basis']=='quantity'}
    definitions=sorted({(r['definition'],r['end_seconds'],r['quantity_basis']) for r in rows})
    for phase in ('preexpiry','expiry'):
        for u in ('NIFTY','SENSEX','pooled'):
            for scope in ('all_windows','ordinary_positive_timer_slots'):
                candidates=[]
                for definition,seconds,quantity in definitions:
                    rs=[r for r in rows if r['phase']==phase and (u=='pooled' or r['underlying']==u) and (r['definition'],r['end_seconds'],r['quantity_basis'])==(definition,seconds,quantity)]
                    train=[r for r in rs if r['split']=='calibration'];test=[r for r in rs if r['split']=='evaluation']
                    modes={clock:tuple(modal([r[k] for r in train if r['clock']==clock]) for k in ('short_CE','short_PE','long_CE','long_PE')) for clock in slots}
                    if scope=='ordinary_positive_timer_slots':
                        reference=[wide[(r['underlying'],r['expiry_date'],r['date'],r['clock'])] for r in train]
                        keep={clock for clock in slots if
                              modal([r['short_CE'] for r in reference if r['clock']==clock])>0 and
                              modal([r['short_PE'] for r in reference if r['clock']==clock])>0}
                        train=[r for r in train if r['clock'] in keep];test=[r for r in test if r['clock'] in keep]
                    def compare(sample):
                        hits=[];pair=[]
                        for r in sample:
                            target=wide[(r['underlying'],r['expiry_date'],r['date'],r['clock'])]
                            actual=tuple(target[k] for k in ('short_CE','short_PE','long_CE','long_PE'))
                            hits.append(actual==modes[r['clock']]);pair.append(actual[:2]==modes[r['clock']][:2])
                        return float(np.mean(hits)),float(np.mean(pair))
                    if not train or not test:continue
                    cal,calpair=compare(train);later,laterpair=compare(test)
                    row=dict(phase=phase,underlying=u,scope=scope,definition=definition,end_seconds=seconds,quantity_basis=quantity,
                             calibration_windows=len(train),calibration_four_role_match=cal,calibration_short_pair_match=calpair,
                             later_windows=len(test),later_four_role_match=later,later_short_pair_match=laterpair)
                    evaluations.append(row);candidates.append((cal,calpair,-seconds,row,modes,test))
                chosen=max(candidates,key=lambda x:x[:3]);record=chosen[3].copy();record['selected_on_earlier']=True
                predictions.append(record)
    save_records('deep_timer_size_window_evaluation.csv',evaluations)
    save_records('deep_timer_size_selected.csv',predictions)
    save_records('deep_timer_size_window_inputs.csv.gz',rows)
    (OUT/'deep_timer_size_summary.json').write_text(json.dumps(dict(definitions=len(definitions),evaluations=len(evaluations),
        note='All definitions predict the same wide T-2s through T+180s filled-quantity target. Positive timer slots are defined using that wide earlier target, avoiding apparent accuracy from narrow-window zeros. Conditional observed sessions. Modes describe parent roles retrospectively, not capital or a maximum-risk rule. Definition selection uses earlier matches.'),indent=2)+'\n')
    for row in predictions:print(json.dumps(row),flush=True)


if __name__=='__main__':main()
