"""Second-of-minute structure of body exits by day and by price-ratio class (continuous/tick-driven vs minute-clocked)."""
import sys; sys.path.insert(0,'.')
from dd_common import *
F=fills().sort_values(['t','row']); rows=[]
for (u,e,cp,k),g in F[F.module=='num'].groupby(['und','expiry','cp','strike']):
    q=0; cost=0.0   # running short lots and cost basis (avg)
    for r in g.itertuples():
        if r.side=='Sell': cost+=r.px*r.n_lots; q+=r.n_lots
        else:
            if q>0:
                avg=cost/q; rows.append(dict(und=u,expiry=e,day=r.dayno,sec=r.sec,j=r.j,lots=r.n_lots,ratio=r.px/avg,s=r.sec%60,minute_of_hour=(r.sec//60)%60,inf=0))
                take=min(r.n_lots,q); cost-=avg*take; q-=take
D=pd.DataFrame(rows); D['cls']=pd.cut(D.ratio,[0,0.5,1.0,1.4,1.55,1.8,100],labels=['<0.5x','0.5-1x','1-1.4x','1.4-1.55x','1.55-1.8x','>1.8x'])
D.to_csv(f'{OUT}/dd_exit_timing.csv',index=False)
for d in (0,1):
    x=D[D.day==d]; print('day',d,'buy-backs of a recorded short:',len(x))
    t=x.groupby('cls').apply(lambda g: pd.Series(dict(n=len(g),share_s0=(g.s==0).mean(),share_s_le2=(g.s<=2).mean(),share_clockB=(g.minute_of_hour%15==14).mean(),share_ge_15_10=(g.sec>=15*3600+10*60).mean()))).round(3); print(t.to_string())
