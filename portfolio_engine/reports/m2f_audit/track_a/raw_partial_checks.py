"""[RAW] partially-filled order / duplicate-flag / module-tag checks directly on the raw CSV."""
import csv, json, collections, os
RAW='/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv'
rows=list(csv.reader(open(RAW,newline='')))
P=collections.defaultdict(list)
for i,r in enumerate(rows): P[r[163]].append((i,int(r[33]),int(r[19]),int(r[20]),r[27],int(r[161]),r[11]))
out={}
unf=[(p,v) for p,v in P.items() if sum(x[1] for x in v)<v[0][2]]
out['unfilled_parents']=[dict(parent=p,fills=len(v),units=sum(x[1] for x in v),req=v[0][2],last_status=v[-1][4],last_remaining_col20=v[-1][3],rows=[x[0] for x in v]) for p,v in unf]
# running remaining consistency: col20 after each fill == req - cumulative units ?
bad=0; badp=[]
for p,v in P.items():
    cum=0
    for x in v:
        cum+=x[1]
        if x[3]!=x[2]-cum: bad+=1; badp.append((p,x[0],x[2],cum,x[3])); break
out['parents_where_col20_not_req_minus_cum']=bad; out['examples_col20_mismatch']=badp[:5]
# last status of each parent
out['parents_last_status']=dict(collections.Counter(v[-1][4] for v in P.values()))
out['parents_with_PartiallyFilled_last_row']=sum(1 for v in P.values() if v[-1][4]=='PartiallyFilled')
out['parents_multi_fill']=sum(1 for v in P.values() if len(v)>1)
# spans dates
out['parents_spanning_ist_dates']=sum(1 for v in P.values() if len({(x[5]+19800)//86400 for x in v})>1)
# module derivation
mod=collections.Counter()
for r in rows:
    p=r[163]; m='num' if p.isdigit() else p.split('_')[0]+'_'
    mod[m]+=1
out['module_by_parent_prefix']=dict(mod)
# same-second same-instrument mixed-side groups
G=collections.defaultdict(list)
for i,r in enumerate(rows):
    inst=f'{r[12]}|{r[15].split(" ")[0]}|{r[16]}|{r[14]}'; G[(inst,int(r[161]))].append((i,r[11],int(r[33]),r[137],r[163]))
mixed=[(k,v) for k,v in G.items() if len({x[1] for x in v})>1]
out['same_instrument_second_groups_gt1']=sum(1 for v in G.values() if len(v)>1); out['same_instrument_second_mixed_side_groups']=len(mixed)
out['mixed_groups_examples']=[(k,v) for k,v in mixed[:6]]
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'raw_partial_checks_result.json'),'w'),indent=1)
print(json.dumps({k:v for k,v in out.items() if k!='mixed_groups_examples'},indent=1)[:3500])
