"""[RAW][IMPL] expiry-boundary: for the 81 instruments left non-flat, when was the last fill relative to expiry day; does the raw file contain ANY fill after expiry day or any settlement-like field."""
import os, sys, json, datetime, collections
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import ref_model as RM
rows=RM.load_raw(); R=RM.replay_ref(RM.order_fills(rows,'src'),'FIFO')
def day(s): y,m,d=map(int,s.split('-')); return (datetime.date(y,m,d)-datetime.date(1970,1,1)).days
last=collections.defaultdict(lambda:0)
for r in rows: last[r['inst']]=max(last[r['inst']],r['ts'])
op=[i for i,v in R.final_inv.items() if v!=0]
gap=collections.Counter(); sess=collections.Counter(); units=collections.Counter(); sgn=collections.Counter()
for i in op:
    g=day(i.split('|')[1])-((last[i]+19800)//86400); gap[g]+=1; units['abs']+=abs(R.final_inv[i]); sgn['short' if R.final_inv[i]<0 else 'long']+=1
    t=(last[i]+19800)%86400; sess['last_fill_ist_hhmm_ge_1530' if t>=15*3600+1800 else 'before_1530']+=1
exp_days=sorted({day(r['expiry']) for r in rows}); maxexp=max(exp_days); lastday=(rows[-1]['ts']+19800)//86400
out=dict(open_instruments=len(op),days_between_last_fill_and_expiry_day=dict(gap),last_fill_time=dict(sess),units=dict(units),direction=dict(sgn),max_expiry=str(datetime.date(1970,1,1)+datetime.timedelta(maxexp)),last_data_day=str(datetime.date(1970,1,1)+datetime.timedelta(lastday)),
  instruments_with_expiry_after_last_data_day=sum(1 for i in R.final_inv if day(i.split('|')[1])>lastday),
  by_underlying=dict(collections.Counter(i.split('|')[0] for i in op)),
  max_ist_time_of_any_fill=max((r['ts']+19800)%86400 for r in rows), min_ist_time_of_any_fill=min((r['ts']+19800)%86400 for r in rows))
# remaining units exposure
out['n_expiry_dates']=len(exp_days)
# fills on a day later than expiry for same instrument?
out['fills_after_expiry']=sum(1 for r in rows if (r['ts']+19800)//86400>day(r['expiry']))
json.dump(out,open(os.path.join(HERE,'expiry_analysis_result.json'),'w'),indent=1); print(json.dumps(out,indent=1))
