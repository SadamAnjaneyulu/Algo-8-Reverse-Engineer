import sys, os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from load import *
def spot_series(d):
    """synthetic spot from put-call parity: S = K + C - P, using same-strike CE & PE fills in same minute (|S-K| small => ATM, parity most reliable)."""
    d=d.copy(); d['m']=d.t.dt.floor('min')
    g=d.groupby(['date','m','strike','cp']).px_fill.mean().unstack('cp').dropna()
    g=g.reset_index()
    g['S']=g.strike+g.CE-g.PE
    g['dev']=(g.S-g.strike).abs()
    # use the most-ATM strike in that minute
    g=g.sort_values(['date','m','dev']).groupby(['date','m']).first().reset_index()
    return g[['date','m','strike','CE','PE','S']]
if __name__=='__main__':
    d=load(); s=spot_series(d)
    print(len(s)); 
    s.to_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)),'_cache','spot.pkl'))
    print(s.head(20))
    # per day: open spot proxy, close spot proxy
    print(s.groupby('date').S.agg(['first','last','min','max','count']).round(0).to_string())
