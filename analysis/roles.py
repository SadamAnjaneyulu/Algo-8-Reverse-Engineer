import sys, os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from load import *
def with_roles(d):
    sp=pd.read_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)),'_cache','spot.pkl'))
    d=d.sort_values('t').copy()
    d['m']=d.t.dt.floor('min')
    out=[]
    for dt,g in d.groupby('date'):
        s=sp[sp.date==dt].sort_values('m')[['m','S']]
        if len(s)==0: g['S']=np.nan; out.append(g); continue
        g=pd.merge_asof(g.sort_values('t'), s.rename(columns={'m':'ms'}).sort_values('ms'), left_on='m', right_on='ms', direction='nearest')
        out.append(g)
    d=pd.concat(out)
    d['dist']=(d.strike-d.S)/d.S*100
    d['adist']=d.dist.abs()
    d['role']=np.where(d.adist<0.8,'ATM','FAR')
    return d.sort_values(['t','row']).reset_index(drop=True)
