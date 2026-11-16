import sys, os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from load import *
def compact(d, date, maxrows=400):
    g=d[d.date==date].copy()
    out=[]
    for (hm), gg in g.groupby('hhmm'):
        parts=[]
        for (side,cp,k),x in gg.groupby(['side','cp','strike']):
            lots=x.lots.sum(); px=(x.px_fill*x.qty_fill).sum()/x.qty_fill.sum()
            parts.append(f"{'B' if side=='Buy' else 'S'}{int(lots)}x{cp}{int(k)}@{px:.1f}")
        out.append(hm+' '+' '.join(parts))
    return out
if __name__=='__main__':
    d=load()
    for dt in sys.argv[1:]:
        print('=====',dt)
        for l in compact(d,dt): print(l)
