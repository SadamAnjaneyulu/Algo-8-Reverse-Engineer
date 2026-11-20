"""Trigger study part 3 (D-1): does a single-leg sale pick the strike whose premium matches the previous sale on that right?
Rules (pre-registered): ATM(prev close) | PREVPX = chain strike (same right) whose minute-close price at j-1 is nearest to the decision price of the previous body sale on that right | AVGPX = nearest to the running lot-weighted average decision price of earlier sales.
Null for PREVPX/AVGPX: use the target price of a random other single sale of the same cycle. Output outputs/bl_trig_strike_rules.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
S = pd.read_pickle(f'{OUT}/bl_trig_sells_d1.pkl.gz').sort_values(['und', 'expiry', 'cp', 'te', 'row']).reset_index(drop=True); ch = Chain(); rng = np.random.default_rng(0)
S['prev_px'] = S.groupby(['und', 'expiry', 'cp']).ref_px.shift(1); S['cumw'] = S.lots * S.ref_px; S['cl'] = S.groupby(['und', 'expiry', 'cp']).lots.cumsum(); S['cv'] = S.groupby(['und', 'expiry', 'cp']).cumw.cumsum(); S['avg_px'] = (S.cv - S.cumw) / (S.cl - S.lots)
def pick(r, T):
    st = ch.strikes(r.und, r.expiry); j = int(r.j) - 1
    if j < 0 or T != T: return np.nan
    p = np.array([ch.px(r.und, r.expiry, 0, r.cp, k, j, 'close') for k in st]); ok = ~np.isnan(p) & (p >= 1)
    return st[ok][np.argmin(np.abs(p[ok] - T))] if ok.any() else np.nan
out = []
for nm, g in (('single-leg (all)', S[~S.paired]), ('single-leg, other class', S[(~S.paired) & (S.cls == 'other')]), ('paired slot-minute (comparison)', S[S.paired & (S.cls == 'slot_minute')])):
    g = g.dropna(subset=['prev_px', 'avg_px']); pool = g.groupby(['und', 'expiry']).prev_px.apply(list).to_dict(); h = {'ATM': (g.strike == g.atm_prev).values, 'PREVPX': [], 'AVGPX': [], 'PREVPX_null': [], 'PREVPX_pm1': []}
    for r in g.itertuples():
        k1 = pick(r, r.prev_px); k2 = pick(r, r.avg_px); k3 = pick(r, rng.choice(pool[(r.und, r.expiry)])); h['PREVPX'].append(k1 == r.strike); h['AVGPX'].append(k2 == r.strike); h['PREVPX_null'].append(k3 == r.strike); h['PREVPX_pm1'].append(abs(k1 - r.strike) <= r.step * 1.0001 if k1 == k1 else False)
    out.append(dict(group=nm, n=len(g), ATM_exact=np.mean(h['ATM']), ATM_pm1=((g.strike - g.atm_prev).abs() <= g.step * 1.0001).mean(), PREVPX_exact=np.mean(h['PREVPX']), PREVPX_pm1=np.mean(h['PREVPX_pm1']), AVGPX_exact=np.mean(h['AVGPX']), PREVPX_null_exact=np.mean(h['PREVPX_null'])))
R = pd.DataFrame(out).round(3); R.to_csv(f'{OUT}/bl_trig_strike_rules.csv', index=False); print(R.to_string(index=False))
