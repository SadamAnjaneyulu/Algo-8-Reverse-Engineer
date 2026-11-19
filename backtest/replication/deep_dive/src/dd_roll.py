"""D0 'roll' structure: how many body buy-backs are re-sold (same right, within 60 s) and how does the hazard of buying back a short contract depend on its distance from the previous completed spot?"""
import sys; sys.path.insert(0,'.')
from dd_common import *
import data
from bt import cycles as Cy
F=fills().sort_values(['t','row']); cyc=pd.read_csv(ref.CYCLES); cl=Cy.cycle_list(); NM=375
body=F[F.module=='num']
# ---- 1) roll pairs: body Buy (lots n, right r) followed by body Sell same right within 60 s
pairs=[]; tot=0; rolled=0
for (u,e,d,cp),g in body.groupby(['und','expiry','dayno','cp']):
    g=g.sort_values('sec'); b=g[g.side=='Buy']; s=g[g.side=='Sell']; sv=s.sec.values; sl=s.n_lots.values; sk=s.strike.values; used=np.zeros(len(s),bool)
    for r in b.itertuples():
        tot+=r.n_lots; need=r.n_lots
        for i in np.where((sv>=r.sec)&(sv<=r.sec+60)&(~used))[0]:
            take=min(need,sl[i]); 
            if take>0: pairs.append((u,e,d,cp,r.strike,sk[i],take,r.sec,sv[i]-r.sec,r.j)); rolled+=take; need-=take; used[i]=True if take==sl[i] else False
            if need<=0: break
P=pd.DataFrame(pairs,columns=['und','expiry','day','cp','k_old','k_new','lots','sec','delay','j']); P.to_csv(f'{OUT}/dd_roll_pairs.csv',index=False)
print('body buy-back lots',tot,'re-sold (same right, within 60 s):',rolled,round(rolled/tot,3),' by day:',(P.groupby('day').lots.sum()/body[body.side=='Buy'].groupby('dayno').n_lots.sum()).round(3).to_dict())
print('median delay s',P.delay.median(),' same strike share',round((P.k_old==P.k_new).mean(),3))
# ---- 2) distance of old vs new strike from the previous completed spot (D0 only)
rows=[]
for (u,e),g in P[P.day==1].groupby(['und','expiry']):
    m=cl[(cl.und==u)&(cl.expiry==e)].iloc[0]; c=data.load_cycle(u,e,m.d1,m.d0); sp=c[(1,'spot')]; st=ref.STEP[u]
    for r in g.itertuples():
        j=int(min(max(r.j,1),374)); S=sp[j-1]
        if S==S: rows.append((u,r.cp,(r.k_old-S)/st,(r.k_new-S)/st))
R=pd.DataFrame(rows,columns=['und','cp','d_old','d_new']); R['abs_old']=R.d_old.abs(); R['abs_new']=R.d_new.abs(); R.to_csv(f'{OUT}/dd_roll_d0_dist.csv',index=False)
print('D0 roll pairs',len(R),' |old - spot| steps median',round(R.abs_old.median(),2),' |new - spot| median',round(R.abs_new.median(),2),'; share new closer to spot than old:',round((R.abs_new<R.abs_old).mean(),3),'; share old ITM (CE: K<S, PE: K>S):',round(((R.cp=='CE')&(R.d_old<0)|(R.cp=='PE')&(R.d_old>0)).mean(),3))
print('old distance quantiles (steps):',R.abs_old.quantile([.1,.25,.5,.75,.9]).round(2).to_dict(),' new:',R.abs_new.quantile([.1,.25,.5,.75,.9]).round(2).to_dict())
