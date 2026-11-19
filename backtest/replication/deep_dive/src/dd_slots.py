"""D-1 slot sizing study: is the lots-per-slot variation (beyond the per-slot mode) explained by market or book state?"""
import sys; sys.path.insert(0,'.')
from dd_common import *
import data
from bt import cycles as Cy
F=fills(); O=ref.orders(F); O['jc']=O.j.clip(0,374); cyc=pd.read_csv(ref.CYCLES); cl=Cy.cycle_list()
rows=[]
for r in cyc[cyc.has_d1].itertuples():
    m=cl[(cl.und==r.und)&(cl.expiry==r.expiry)].iloc[0]; c=data.load_cycle(r.und,r.expiry,m.d1,m.d0); strikes=c['strikes']; spot=c[(0,'spot')]
    px={}
    for rr in ('CE','PE'):
        a=np.array(c[(0,rr,'close')],float)
        for j in range(1,a.shape[1]):
            q=np.isnan(a[:,j]); a[q,j]=a[q,j-1]
        px[rr]=a
    b=O[(O.und==r.und)&(O.expiry==r.expiry)&(O.dayno==0)&(O.module=='num')]
    for k in range(14):
        j0=1+15*k; win=b[(b.jc>=j0)&(b.jc<j0+3)&(b.side=='Sell')]
        S=spot[j0-1]; K=int(np.argmin(abs(strikes-ref.STEP[r.und]*np.floor(S/ref.STEP[r.und]+0.5))))
        prem=px['CE'][K,j0-1]+px['PE'][K,j0-1]
        before=b[(b.jc<j0)]; sh_ce=-(np.where(before.side=='Sell',1,-1)*before.lots)[before.cp=='CE'].sum()*-1; 
        short_ce=(np.where(before.side=='Sell',1,-1)*before.lots)[before.cp=='CE'].sum(); short_pe=(np.where(before.side=='Sell',1,-1)*before.lots)[before.cp=='PE'].sum()
        mv=(S-spot[max(j0-16,0)])/S*1e4 if j0>16 else np.nan
        rows.append(dict(und=r.und,expiry=r.expiry,k=k,lots_ce=win[win.cp=='CE'].lots.sum(),lots_pe=win[win.cp=='PE'].lots.sum(),premium=prem,book_short=short_ce+short_pe,move15_bp=mv,spot=S,und_lot=ref.LOT[r.und]))
D=pd.DataFrame(rows); D['lots']=(D.lots_ce+D.lots_pe)/2; D.to_csv(f'{OUT}/dd_slot_sizing.csv',index=False)
# slot-mean removal
D['lots_dm']=D.lots-D.groupby('k').lots.transform('mean')
print('variance of lots explained by slot id alone:', round(1-D.lots_dm.var()/D.lots.var(),3))
for f in ('premium','book_short','move15_bp','spot'):
    x=D[['lots_dm',f]].dropna(); xx=x[f]-D.loc[x.index].groupby('k')[f].transform('mean') if f!='move15_bp' else x[f]
    print(f, 'Spearman(lots residual, feature) =', round(pd.Series(x.lots_dm).corr(pd.Series(xx),method='spearman'),3), ' n',len(x))
# premium budget test: CV(lots*premium) vs CV(lots) within slot
cv=lambda s: s.std()/s.mean()
g=D[D.lots>0]; print('mean CV within slot: lots',round(g.groupby('k').lots.apply(cv).mean(),3),' lots*premium',round(g.assign(x=g.lots*g.premium).groupby('k').x.apply(cv).mean(),3))
# per-index
for u in ('NIFTY','SENSEX'): d=D[D.und==u]; print(u,'lots mean',round(d.lots.mean(),2),'premium mean',round(d.premium.mean(),1))
# cycle effect: do cycles with large early slots also have large later slots (cycle-level scale)?
cy=D.groupby(['und','expiry']).lots_dm.mean(); print('between-cycle std of mean residual:',round(cy.std(),3),' vs expected from iid:',round(D.lots_dm.std()/np.sqrt(14),3))
