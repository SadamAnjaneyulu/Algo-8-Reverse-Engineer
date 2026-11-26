"""Lump study step 3 (POST-HOC budget test): lump spend (Rs, main decision) vs candidate budgets at the decision: D-1 MTM P&L (cash + marks, all modules), gross premium sold on D-1 (body open_short), net premium (sold - bought, all modules), premium sold on the heavy side, current mark of heavy-side shorts.
A budget rule shows as a low coefficient of variation of spend / budget and a high Spearman. Output bl_lp_budget.csv, bl_summary_lp3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
import bl_ohlc
OH = bl_ohlc.load(); CYs = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); D = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); R = {}; rows = []
for x in D[D.main == 1].itertuples():
    r = CYs.iloc[x.cid]; cb = CycleBook(r.und, r.expiry, r.unit); c = OH[(r.und, r.expiry)].close.values; pm = min(int((x.t - 33300) // 60), 374) - 1
    st = cb.state(x.t + 3, c[pm], pm, pnl_only=True)                      # state counts orders with te < t - 3, so t + 3 = everything before the decision
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.te < x.t)]; sg = np.where(z.side == 'Buy', -1, 1)
    gross = float((z[(z.module == 'num') & (z.role == 'open_short')].pipe(lambda q: q.lots * q.px_avg)).sum() * r.unit); net = float((sg * z.lots * z.px_avg).sum() * r.unit)
    heavy = float((z[(z.module == 'num') & (z.role == 'open_short') & (z.cp == x.cp)].pipe(lambda q: q.lots * q.px_avg)).sum() * r.unit)
    rows.append(dict(cid=x.cid, und=x.und, spend=x.lots * x.px * r.unit, mtm_pnl=st['pnl_pct'] / 100 * CAP, gross_prem=gross, net_prem=net, heavy_prem=heavy, heavy_mark=x.prem_short_h * r.unit))
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_lp_budget.csv', index=False)
for b in ('mtm_pnl', 'gross_prem', 'net_prem', 'heavy_prem', 'heavy_mark'):
    q = X.spend / X[b]; R[b] = dict(median_ratio=float(q.median()), cv=float(q.std() / q.mean()), spearman=float(spearmanr(X.spend, X[b])[0]), p=float(spearmanr(X.spend, X[b])[1])); print(b, {k: round(v, 3) for k, v in R[b].items()})
print(X.round(0).to_string(index=False)); rec('lp3', R)
