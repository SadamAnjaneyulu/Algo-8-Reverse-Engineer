"""D-1 long side, L6: v_ lumps. Per cycle: lump orders (times, rights, strikes, lots), contract-level book S/L per right just before the first lump order and at each lump order; candidate size rules: S_heavy, S_heavy - S_light, S_heavy at 15:00, lots of the heavier side's body shorts; right = heavier side?
Outputs bl_hg_lump_orders.csv, bl_hg_lump_cyc.csv, bl_summary_hg6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OH = bl_ohlc.load(); d1 = O[O.dayno == 0]; R = {}; rows = []; cyc = []
def book(z, t):
    p = {}
    for q in z[z.te < t].itertuples(): k = (q.cp, int(q.strike)); p[k] = p.get(k, 0) + (1 if q.side.lower() == 'buy' else -1) * q.lots
    return {cp: (-sum(v for (c2, _), v in p.items() if c2 == cp and v < 0), sum(v for (c2, _), v in p.items() if c2 == cp and v > 0)) for cp in ('CE', 'PE')}
for i, r in enumerate(CY.itertuples()):
    z = d1[(d1.und == r.und) & (d1.expiry == r.expiry)].sort_values(['te', 'row']); v = z[z.module == 'v_']; c = OH[(r.und, r.expiry)].close.values
    if not len(v): cyc.append(dict(cid=i, und=r.und, has_lump=0)); continue
    for q in v.itertuples():
        b = book(z, q.te); j = min(int((q.te - 33300) // 60), 374)
        rows.append(dict(cid=i, und=r.und, te=q.te, hhmmss=f'{int(q.te // 3600):02d}:{int(q.te % 3600 // 60):02d}:{int(q.te % 60):02d}', cp=q.cp, strike=q.strike, lots=q.lots, px=q.px_avg, otm_pct=(q.strike / c[j - 1] - 1) * 100 * (1 if q.cp == 'CE' else -1), S_CE=b['CE'][0], L_CE=b['CE'][1], S_PE=b['PE'][0], L_PE=b['PE'][1]))
    t0 = v.te.min(); b0 = book(z, t0); b15 = book(z, 54000); rights = v.groupby('cp').lots.sum()
    hv = 'CE' if b0['CE'][0] > b0['PE'][0] else 'PE'; lt = 'PE' if hv == 'CE' else 'CE'
    cyc.append(dict(cid=i, und=r.und, has_lump=1, t_first=t0, rights=','.join(sorted(rights.index)), lump_CE=int(rights.get('CE', 0)), lump_PE=int(rights.get('PE', 0)), heavy=hv, S_heavy=b0[hv][0], S_light=b0[lt][0], L_heavy=b0[hv][1], S_heavy_1500=b15[hv][0], S_light_1500=b15[lt][0], lump_on_heavy=int(rights.get(hv, 0)), lump_on_light=int(rights.get(lt, 0)), n_orders=len(v)))
V = pd.DataFrame(rows); C = pd.DataFrame(cyc); V.to_csv(f'{OUT}/bl_hg_lump_orders.csv', index=False); C.to_csv(f'{OUT}/bl_hg_lump_cyc.csv', index=False)
L = C[C.has_lump == 1].copy(); y = L.lump_on_heavy
R['cycles_with_lump'] = len(L); R['only_heavy_side'] = float(((L.lump_on_light == 0) & (L.lump_on_heavy > 0)).mean()); R['both_sides'] = float(((L.lump_CE > 0) & (L.lump_PE > 0)).mean())
cands = {'S_heavy': L.S_heavy, 'S_heavy - S_light': L.S_heavy - L.S_light, 'S_heavy at 15:00': L.S_heavy_1500, 'S_heavy - S_light at 15:00': L.S_heavy_1500 - L.S_light_1500}
res = []
for k, x in cands.items():
    ratio = (y / x.replace(0, np.nan)); res.append(dict(rule=k, median_ratio=ratio.median(), q25=ratio.quantile(.25), q75=ratio.quantile(.75), median_abs_err_pct_at_ratio1=float((abs(y - x) / y).median() * 100), exact=float((y == x).mean()), spearman=float(pd.Series(y.values).corr(pd.Series(x.values), method='spearman'))))
T = pd.DataFrame(res); print(T.round(3).to_string(index=False)); R['size_rules'] = T.round(4).to_dict('records')
R['first_time_q'] = L.t_first.quantile([.1, .5, .9]).map(lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}').to_dict(); R['orders_per_cycle_median'] = float(L.n_orders.median()); R['otm_pct_q'] = V.otm_pct.quantile([.1, .5, .9]).round(2).to_dict(); R['px_q'] = V.px.quantile([.1, .5, .9]).round(2).to_dict()
print({k: R[k] for k in ('cycles_with_lump', 'only_heavy_side', 'both_sides', 'first_time_q', 'orders_per_cycle_median', 'otm_pct_q', 'px_q')})
print(L[['cid', 'und', 'heavy', 'S_heavy', 'S_light', 'lump_on_heavy', 'lump_on_light', 'n_orders']].to_string(index=False)); rec('hg6', R)
