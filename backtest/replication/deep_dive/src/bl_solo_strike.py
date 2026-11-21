"""Solo recall step 3: strike rule for real solo lots - ATM (previous close) vs the earlier premium-continuity rule (strike whose previous-minute close is nearest the previous body sale price on that right) vs the previous sale's strike. Outputs bl_solo_strike.csv, bl_summary_solo2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_all_sells.py').read().split("ACT = {d['cid']")[0])
R = {}; rows = []
for d in CYC:
    u, e = d['und'], d['expiry']; c_ = ch.cyc(u, e); K = np.array(c_['strikes'], float); A = actual(d); s = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0) & (O.module == 'num') & (O.role == 'open_short')].sort_values('te')
    for r in A[(A.typ == 'solo') & (A.j >= 1) & (A.j <= 374)].itertuples():
        T0 = 33300 + 60 * r.j; prevs = s[(s.cp == r.cp) & (s.te < T0)]
        if not len(prevs): continue
        pp = prevs.px_avg.iloc[-1]; prices = c_[(0, r.cp, 'close')][:, r.j - 1]; ok = ~np.isnan(prices)
        k_prem = K[ok][np.argmin(np.abs(prices[ok] - pp))]; k_atm = K[np.argmin(np.abs(K - d['c'][r.j - 1]))]; k_prev = prevs.strike.iloc[-1]
        rows.append(dict(cp=r.cp, prem=int(k_prem == r.strike), prem_pm1=int(abs(k_prem - r.strike) <= d['step']), atm=int(k_atm == r.strike), atm_pm1=int(abs(k_atm - r.strike) <= d['step']), prev_strike=int(k_prev == r.strike), offset_atm=(r.strike - k_atm) / d['step'] * (1 if r.cp == 'PE' else -1)))
D = pd.DataFrame(rows); out = pd.DataFrame([dict(rule=k, exact=D[c].mean(), within_one_strike=D[c2].mean() if c2 else np.nan) for k, c, c2 in (('premium nearest the previous sale on that right (earlier rule)', 'prem', 'prem_pm1'), ('ATM of the previous close', 'atm', 'atm_pm1'), ('same strike as the previous sale on that right', 'prev_strike', None))])
out.round(4).to_csv(f'{OUT}/bl_solo_strike.csv', index=False); print(out.round(3).to_string(index=False)); print('offset from ATM (steps, + = ITM for the sold right):', D.offset_atm.value_counts(normalize=True).sort_index().round(3).head(9).to_dict())
R['rules'] = out.round(4).to_dict('records'); R['n'] = len(D); R['offset_itm'] = {float(k): float(v) for k, v in D.offset_atm.value_counts(normalize=True).sort_index().items()}; rec('solo2', R)
