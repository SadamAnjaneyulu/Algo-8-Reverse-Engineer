"""Hedge-module controller test: after each body burst (orders within 3 s) per right, does the hedge module move long-wing lots W so that W equals body short lots S?"""
import sys; sys.path.insert(0,'.')
from dd_common import *
F=fills().sort_values(['t','row']); T=tagged_orders(F); O=ref.orders(F)
H=T[T.module=='h_'].copy(); H['dW']=np.where(H.side=='Buy',1,-1)*H.lots
B=O[O.module=='num'].copy(); B['dS']=np.where(B.side=='Sell',1,-1)*B.lots
rows=[]
for (u,e,cp),g in F.groupby(['und','expiry','cp']):
    bb=B[(B.und==u)&(B.expiry==e)&(B.cp==cp)].sort_values('sec'); hh=H[(H.und==u)&(H.expiry==e)&(H.cp==cp)]
    # absolute time axis: day offset
    bb=bb.assign(tt=bb.dayno*100000+bb.sec).sort_values('tt'); hh=hh.assign(tt=hh.dayno*100000+hh.t_dec).sort_values('tt')
    S=0; W=0; hi=0; hv=hh.tt.values; hd=hh.dW.values; hday=hh.dayno.values
    burst=(bb.tt.diff().fillna(1e9)>3).cumsum()
    # process chronologically: apply hedge orders that happened before each burst
    for _,gb in bb.groupby(burst):
        t0=gb.tt.min(); t1=gb.tt.max()
        while hi<len(hv) and hv[hi]<=t0: W+=hd[hi]; hi+=1
        S_before=S; W_before=W; dS=gb.dS.sum(); S=S+dS
        j=hi; dW=0
        while j<len(hv) and hv[j]<=t1+10: dW+=hd[j]; j+=1
        rows.append(dict(und=u,expiry=e,cp=cp,day=int(gb.dayno.iloc[0]),tt=t0,S_before=S_before,W_before=W_before,dS=dS,S_after=S,dW=dW,responded=(j>hi)))
D=pd.DataFrame(rows); D=D[D.dS!=0]; D['gap_before']=D.W_before-D.S_before; D['gap_if_unresponded']=D.W_before-D.S_after
D['W_after']=D.W_before+D.dW; D['gap_after']=D.W_after-D.S_after
D.to_csv(f'{OUT}/dd_hedge_bursts.csv',index=False)
print('bursts',len(D),' responded share',round(D.responded.mean(),3))
r=D[D.responded]; n=D[~D.responded]
print('RESPONDED: gap before (W-S_before) median/p25/p75:',r.gap_before.median(),r.gap_before.quantile([.25,.75]).tolist(),' gap AFTER (W-S_after):', 'share ==0',round((r.gap_after==0).mean(),3),' share |gap|<=1',round((r.gap_after.abs()<=1).mean(),3))
print('NOT RESPONDED: gap if no action (W_before-S_after) share==0:',round((n.gap_if_unresponded==0).mean(),3),' share>0 (over-hedged):',round((n.gap_if_unresponded>0).mean(),3),' share<0 (under-hedged):',round((n.gap_if_unresponded<0).mean(),3))
print('NOT RESPONDED by day:',n.groupby('day').size().to_dict(),' of all bursts by day:',D.groupby('day').size().to_dict())
print('responded sells vs buys:',r.groupby(np.sign(r.dS)).size().to_dict(),'; gap_after==0 by sign:',r.groupby(np.sign(r.dS)).apply(lambda x:(x.gap_after==0).mean()).round(3).to_dict())
# sensitivity: does W track S in D0 afternoon (post 14:00)? deviation distribution of W-S at burst start by day and half
D['hour']=((D.tt%100000)//3600).astype(int)
print('median |W-S| before burst by day:',D.groupby('day').gap_before.apply(lambda s:s.abs().median()).to_dict())
