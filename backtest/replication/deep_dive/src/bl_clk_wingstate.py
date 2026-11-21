"""Does the wing/book state decide which first-break bars get an entry? Machine = previous 2 completed 30-min bars, one entry per side per bar (current-minute close). For each machine fire: matched (a real reactive pair within +-1 min) or not; AUC of wing/book state variables. Outputs bl_clk_wingstate.csv, bl_summary_clk6.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
sys.argv = ['x']; exec(open('bl_clk_refine.py').read().split("rows = []\nfor nm, fn")[0])
exec(open('bl_bk_build.py').read().split('def feats')[0].split("O = load_orders()")[0]) if False else None
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}; R = {}; rows = []
for d in CYC:
    k = (d['und'], CY.expiry.iloc[d['cid']]); cb = CycleBook(k[0], k[1], unit[k])
    for f, s in run2(d, var='intra', per_side=True):
        t = 33300 + 60 * f; pm = min(max(f - 1, 0), 374); st = cb.state(t, d['sp'][f], pm); longs = st.get('net_lots', np.nan) + st.get('short_lots', np.nan)
        rows.append(dict(cid=d['cid'], matched=int(any(abs(a - f) <= 1 for a in d['A'])), short_lots=st.get('short_lots', np.nan), long_lots=longs, cover=longs / max(st.get('short_lots', 1), 1), net_lots=st.get('net_lots', np.nan), itm_short=st.get('itm_short', np.nan), delta=st.get('delta', np.nan), pnl_pct=st.get('pnl_pct', np.nan), hour=t / 3600, min_in_bar=(t % 1800) / 60, side=s))
D = pd.DataFrame(rows)
def auc(x, y): m = ~np.isnan(x); x = x[m]; yy = y[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(x)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
y = D.matched.values; out = []
for v in ('short_lots', 'long_lots', 'cover', 'net_lots', 'itm_short', 'delta', 'pnl_pct', 'hour', 'min_in_bar'): out.append(dict(variable=v, AUC=auc(D[v].values.astype(float), y), AUC_even=auc(D[v].values[D.cid % 2 == 0].astype(float), y[D.cid % 2 == 0]), AUC_odd=auc(D[v].values[D.cid % 2 == 1].astype(float), y[D.cid % 2 == 1]), n=len(D), matched=int(y.sum())))
U = pd.DataFrame(out); U.round(3).to_csv(f'{OUT}/bl_clk_wingstate.csv', index=False); print(U.round(3).to_string(index=False)); R['rows'] = U.round(4).to_dict('records'); rec('clk6', R)
