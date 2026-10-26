"""Separate request-label and first-fill targets; audit the recorded LIMIT field."""
import csv
import gzip
import json
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal
from statistics import median

import numpy as np
from audit_strike_hedge_rules import ROOT,OUT,logs,reconstruct_parents,short_batches,write
from mass_match_strategy_rules import score


def main():
    counts=Counter();improvements=Counter();violations=Counter()
    for r in csv.reader((ROOT/'Trades_GKOHNP140.csv').open()):
        counts[r[25]]+=1;p=Decimal(r[137]);limit=Decimal(r[17])
        improvements[r[11]]+=p<limit if r[11]=='Buy' else p>limit
        violations[r[11]]+=p>limit if r[11]=='Buy' else p<limit
    fills=logs.read_fills();parents=reconstruct_parents(fills);requests=defaultdict(set);ambiguous=set();delays=[]
    for p in parents:
        role=p['role'];phase='preexpiry' if str(p['first'].date())<p['expiry_date'] else 'expiry'
        delays.append(dict(underlying=p['underlying'],expiry_date=p['expiry_date'],phase=phase,role=role,
            first_fill_ist=p['first'].isoformat(),request_label_ist=p['label'].isoformat(),
            first_fill_minus_label_seconds=(p['first']-p['label']).total_seconds(),source_rows=p['sources']))
        task='covers' if role=='short_cover' else 'protection' if role=='new_long' else None
        if task:
            key=(p['underlying'],p['expiry_date'],str(p['label'].date()),p['label'].strftime('%H:%M'))
            requests[task].add(key)
            if p['first']<p['label']:ambiguous.add((task,key))
    for b in short_batches(parents):
        label=min(p['label'] for p in b['parents']);key=(b['underlying'],b['expiry_date'],str(label.date()),label.strftime('%H:%M'))
        requests['fresh_pairs'].add(key)
        if b['start']<label:ambiguous.add(('fresh_pairs',key))
    groups=defaultdict(list)
    with gzip.open(OUT/'combo_action_predictions.csv.gz','rt') as f:
        for r in csv.DictReader(f):
            if r['task'] in requests and r['kind'] in ('boolean_temporal','tree_combinations'):groups[(r['task'],r['phase'],r['kind'])].append(r)
    comparisons=[]
    for (task,phase,kind),rows in groups.items():
        good=[r for r in rows if (task,(r['underlying'],r['expiry_date'],r['date'],r['clock'])) not in ambiguous]
        pred=[r['predicted']=='1' for r in good];labels=[(r['underlying'],r['expiry_date'],r['date'],r['clock']) in requests[task] for r in good]
        comparisons.append(dict(task=task,phase=phase,kind=kind,label_definition='earliest_request_label_minute',**score(labels,pred)))
        comparisons.append(dict(task=task,phase=phase,kind=kind,label_definition='physical_first_fill_minute',**score([r['target']=='1' for r in good],pred)))
    role_summary=[]
    for role in sorted({r['role'] for r in delays}):
        ds=[r['first_fill_minus_label_seconds'] for r in delays if r['role']==role]
        role_summary.append(dict(role=role,parents=len(ds),median_seconds_from_minute_label=median(ds),maximum_seconds=max(ds),over_60_seconds=sum(v>60 for v in ds),negative_seconds=sum(v<0 for v in ds)))
    write('combo_order_label_delays.csv',delays);write('combo_request_vs_fill_evaluation.csv',comparisons)
    (OUT/'combo_order_timing_summary.json').write_text(json.dumps(dict(recorded_order_type_counts=dict(counts),buy_limit_violations=violations['Buy'],sell_limit_violations=violations['Sell'],
        price_improved_records=dict(improvements),role_delay_summary=role_summary,comparison=comparisons,
        note='Column 25 contains LIMIT on the export. Software-managed stops can still submit LIMIT orders. Column 23 is a minute-resolution constant order label, not a verified signal timestamp. The sensitivity relabels the same paired execution cohorts; it does not assert original basket identity.'),indent=2)+'\n')


if __name__=='__main__':main()
