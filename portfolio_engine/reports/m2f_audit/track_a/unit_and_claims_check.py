"""[RAW][IMPL] units / multipliers, mixed-parent decomposition, tie-order union claim (M2B: 20 fills / 5 instruments under sells_first/buys_first)."""
import os, sys, json, math, csv
from decimal import Decimal
from fractions import Fraction
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import ref_model as RM
rows=RM.load_raw(); raw=list(csv.reader(open(RM.RAW,newline='')))
out={}
for u in ('NIFTY','SENSEX'):
    q=[r['qty'] for r in rows if r['und']==u]; out[f'{u}_qty_gcd']=math.gcd(*q); out[f'{u}_qty_min']=min(q); out[f'{u}_qty_max']=max(q); out[f'{u}_rows']=len(q)
# realized in RUPEES straight from the raw price text (Decimal), FIFO, no paise anywhere: (exit-entry)*units*direction, no lot multiplier
for r,rr in zip(rows,raw): r['px_rs']=Decimal(rr[137])
def fifo_rupees(ordered):
    st={}; tot=Decimal(0)
    for f in ordered:
        s=st.setdefault(f['inst'],dict(inv=0,lots=[])); q=f['qty']; inv=s['inv']
        if inv!=0 and (inv>0)!=(f['side']>0):
            c=min(q,abs(inv)); d=1 if inv>0 else -1; need=c
            while need:
                lot=s['lots'][0]; t=min(need,lot[0]); tot+=d*(f['px_rs']-lot[1])*t; lot[0]-=t; need-=t
                if lot[0]==0: s['lots'].pop(0)
            s['inv']=inv+f['side']*c; o=q-c
            if o: s['lots']=[[o,f['px_rs']]]; s['inv']=f['side']*o
        else: s['lots'].append([q,f['px_rs']]); s['inv']+=f['side']*q
    return tot
ordered=RM.order_fills(rows,'src'); out['FIFO_realized_rupees_from_raw_decimal_no_paise']=str(fifo_rupees(ordered))
R=RM.replay_ref(ordered,'FIFO'); out['FIFO_realized_paise_ref']=int(R.realized_total); out['rupees_equals_paise_over_100']=(fifo_rupees(ordered)*100==R.realized_total)
# mixed parents decomposition
rev_par={R.oa[r]['parent'] for r,f in R.fills.items() if f['rev']}
role=defaultdict(set)
for r,o in R.oa.items(): role[o['parent']].add('OA')
for r,c in R.cp.items(): role[c['parent']].add('CP')
mixed={p for p,s in role.items() if len(s)==2}; out['mixed_parents']=len(mixed); out['mixed_with_reversal_fill']=len(mixed&rev_par); out['mixed_without_reversal_fill']=len(mixed-rev_par)
# tie union
base=RM.replay_ref(ordered,'FIFO'); diff_fills=set(); diff_inst=set()
for tie in ('sells_first','buys_first'):
    X=RM.replay_ref(RM.order_fills(rows,tie),'FIFO')
    for r in base.fills:
        a=base.fills[r]; b=X.fills[r]
        if (a['close'],a['open'],a['ep_close'],a['ep_open'])!=(b['close'],b['open'],b['ep_close'],b['ep_open']): diff_fills.add(r); diff_inst.add(rows[r]['inst'])
out['tie_sells_or_buys_first_fills_differing_ref']=len(diff_fills); out['tie_sells_or_buys_first_instruments_differing_ref']=len(diff_inst)
# parent counts: col 163 vs col 4 (order number)
out['distinct_col163_parents']=len({r['parent'] for r in rows}); out['distinct_col4_order_numbers']=len({r['order_no'] for r in rows})
json.dump(out,open(os.path.join(HERE,'unit_and_claims_check_result.json'),'w'),indent=1); print(json.dumps(out,indent=1))
