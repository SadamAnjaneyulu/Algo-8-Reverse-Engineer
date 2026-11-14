"""[RAW] Is there any raw-source evidence about intra-second ordering? Check monotonicity of candidate sequence columns with file order, and in the 56 mixed-side (instrument,second) groups whether
the candidate sequence keys (col 28 trade id, col 4 order no, col 163 parent id numeric part, col 1) agree with file order."""
import csv, json, os, collections, re
RAW='/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv'
rows=list(csv.reader(open(RAW,newline='')))
out={}
def day(r): return (int(r[161])+19800)//86400
def mono(col,conv=int):
    viol=0; tot=0; prev=None
    for r in rows:
        try: v=conv(r[col])
        except Exception: continue
        d=day(r)
        if prev is not None and prev[0]==d: tot+=1; viol+= v<prev[1]
        prev=(d,v)
    return dict(pairs=tot,decreases=viol)
for c in (28,4,1):
    out[f'monotone_within_day_col{c}']=mono(c)
def pid(r): 
    p=r[163]; return int(p) if p.isdigit() else None
out['monotone_within_day_parent_numeric']=mono(163,lambda s:int(s))
# same-second same-instrument groups
G=collections.defaultdict(list)
for i,r in enumerate(rows):
    inst=f'{r[12]}|{r[15].split(" ")[0]}|{r[16]}|{r[14]}'; G[(inst,int(r[161]))].append((i,r))
mixed=[(k,v) for k,v in G.items() if len({x[1][11] for x in v})>1]
agree={28:0,4:0}; tot=0
rows_out=[]
for k,v in mixed:
    tot+=1
    for c in (28,4):
        seq=[int(re.sub(r'\D','',x[1][c])) for x in v]; 
        if seq==sorted(seq): agree[c]+=1
    rows_out.append([(x[0],x[1][11],x[1][33],x[1][137],x[1][28],x[1][4],x[1][163]) for x in v])
out['mixed_groups']=tot; out['mixed_groups_where_file_order_equals_ascending_trade_id']=agree[28]; out['mixed_groups_where_file_order_equals_ascending_order_no']=agree[4]
out['mixed_group_listing']=rows_out
# does any tie-group of mixed side involve a reversal? -> compute from ref
json.dump(out,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'tie_evidence_raw_result.json'),'w'),indent=1)
print(json.dumps({k:v for k,v in out.items() if k!='mixed_group_listing'},indent=1)); 
for g in rows_out[:8]: print(g)
