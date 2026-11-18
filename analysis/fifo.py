import sys, os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from load import *
from collections import deque
def fifo_pairs(d):
    """Expand fills to 1-lot units; FIFO match opposing units per (und,expiry,cp,strike) across the cycle (D-1 -> D0).
       returns DataFrame of closed round-trips with open/close side."""
    d=d.sort_values(['t','row']).copy()
    rows=[]
    books={}
    for r in d.itertuples():
        key=(r.und,r.expiry,r.cp,r.strike)
        bk=books.setdefault(key,deque())  # open units: (sign, px, t, date, lotsleft)
        lots=r.lots
        sgn=r.sgn
        while lots>1e-9:
            if bk and bk[0][0]!=sgn:
                o=bk[0]; q=min(lots,o[4])
                rows.append(dict(und=r.und,expiry=r.expiry,cp=r.cp,strike=r.strike,open_side='Sell' if o[0]<0 else 'Buy',
                    open_px=o[1],open_t=o[2],close_px=r.px_fill,close_t=r.t,lots=q,lot=r.lot,close_validity=r.validity,open_date=o[3],close_date=r.date))
                o[4]-=q; lots-=q
                if o[4]<=1e-9: bk.popleft()
            else:
                bk.append([sgn,r.px_fill,r.t,r.date,lots]); lots=0
    out=pd.DataFrame(rows)
    out['pnl']=np.where(out.open_side=='Sell',out.open_px-out.close_px,out.close_px-out.open_px)*out.lots*out.lot
    out['hold_min']=(out.close_t-out.open_t).dt.total_seconds()/60
    out['ratio']=out.close_px/out.open_px
    out['carried']=out.open_date!=out.close_date
    return out
