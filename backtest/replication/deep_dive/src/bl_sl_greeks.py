"""After-15:00 solo, step 1: whole-book Greeks (all modules incl. hedge and lump wings; Black-Scholes from the ATM straddle) at each late solo sale and at intraday solo sales: book delta before/after the sale, share of sales that reduce |delta|, delta of the sold leg, delta path 14:30-15:30 per cycle, and the counterfactual of selling the other right.
Outputs bl_sl_greeks.pkl.gz, bl_sl_delta_path.csv, bl_summary_sl1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import norm
src = open('bl_bk_build.py').read().split('def feats')[0]; exec(src)
D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); R = {}; unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}; rows = []; path = []
def leg_delta(cb, S, pm, cp, k):
    sg = cb.sig(S, pm)
    if not (sg == sg) or sg <= 0: return np.nan
    d1 = np.log(S / k) / sg + sg / 2; return norm.cdf(d1) if cp == 'CE' else norm.cdf(d1) - 1
for i, r in enumerate(CY.itertuples()):
    cb = CycleBook(r.und, r.expiry, unit[(r.und, r.expiry)]); sp = cb.sp
    S_ = D[(D.cid == i) & (D.typ == 'solo') & ~D.deep]
    for q in S_.itertuples():
        j = min(max(int((q.te - 33300) // 60), 1), 374); pm = j - 1; Sx = sp[pm]; b = cb.state(q.te, Sx, pm); a = cb.state(q.te + 3.5, Sx, pm)   # state(t) counts orders with te < t - 3
        dl = leg_delta(cb, Sx, pm, q.cp, q.strike); other = 'PE' if q.cp == 'CE' else 'CE'; k_o = cb.K[np.argmin(np.abs(cb.K - Sx))]
        rows.append(dict(cid=i, late=int(q.te >= 54000), cp=q.cp, delta_before=b.get('delta', np.nan), delta_after=a.get('delta', np.nan), sold_leg_delta=-dl, gamma=b.get('gamma', np.nan), short_lots=b.get('short_lots', np.nan), net_lots=b.get('net_lots', np.nan)))
    for t in range(52200, 55801, 60):
        j = min(int((t - 33300) // 60), 374); st = cb.state(t, sp[max(j - 1, 0)], max(j - 1, 0)); path.append(dict(cid=i, t=t, delta=st.get('delta', np.nan), gamma=st.get('gamma', np.nan), net_lots=st.get('net_lots', np.nan), short_lots=st.get('short_lots', np.nan)))
G = pd.DataFrame(rows); P = pd.DataFrame(path); G.to_pickle(f'{OUT}/bl_sl_greeks.pkl.gz'); P.to_csv(f'{OUT}/bl_sl_delta_path.csv', index=False)
G['reduces'] = (G.delta_after.abs() < G.delta_before.abs()).astype(int); G['sell_dir_matches_delta'] = ((G.cp == 'CE') & (G.delta_before > 0) | (G.cp == 'PE') & (G.delta_before < 0)).astype(int)
for k, g in G.groupby('late'):
    lab = 'late' if k else 'intraday'; R[lab] = dict(n=len(g), share_reduce_abs_delta=float(g.reduces.mean()), share_side_opposes_book_delta=float(g.sell_dir_matches_delta.mean()), median_abs_delta_before=float(g.delta_before.abs().median()), median_sold_leg_delta=float(g.sold_leg_delta.abs().median()))
print(R)
Pv = P.pivot(index='cid', columns='t', values='delta'); R['abs_delta_q_at'] = {f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}': [float(x) for x in Pv[t].abs().quantile([.25, .5, .75])] for t in (52200, 53100, 54000, 54900, 55500, 55800) if t in Pv}; print(R['abs_delta_q_at'])
R['delta_sign_15h_vs_1530'] = float(np.mean(np.sign(Pv[54000]) != np.sign(Pv[55800]))); rec('sl1', R)
