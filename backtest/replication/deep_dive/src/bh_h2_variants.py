"""H2 exploratory variants (chosen AFTER seeing that k = 2.5 % is the sharp optimum; flagged exploratory, Holm over all 9 rules in the final table).
For each simple wing buy: T = 0.025 x body ref price; chain close at j_dec-1. Rules: nearest (P25, already), FLOOR = outermost?? -> strike with the largest price <= T, CEIL = strike with the smallest price >= T, NEAREST_LOG = nearest in log price.
Also classify the chosen strike: is it floor-consistent (p_chosen <= T < p_inner)? ceil-consistent (p_chosen >= T > p_outer)?"""
import sys; sys.path.insert(0, '.')
from bh_common import *
S = pd.read_csv(f'{OUT}/bh_h2_simple_tested.csv', dtype={'tag': str}); ch = Chain(); K = .025; rng = np.random.default_rng(1)
def chain_prices(r, jj):
    st = ch.strikes(r.und, r.expiry); cand = st[(st > r.b_strike) if r.cp == 'CE' else (st < r.b_strike)]
    cand = cand if r.cp == 'CE' else cand[::-1]          # inner -> outer
    p = np.array([ch.px(r.und, r.expiry, r.dayno, r.cp, k, jj, 'close') for k in cand]); return cand, p
rows = []
for r in S.itertuples():
    cand, p = chain_prices(r, r.jd - 1); T = K * r.b_ref; ok = ~np.isnan(p) & (p >= .05)
    if not ok.any(): rows.append((np.nan,) * 5); continue
    c, q = cand[ok], p[ok]
    fl = c[q <= T][np.argmax(q[q <= T])] if (q <= T).any() else np.nan; ce = c[q >= T][np.argmin(q[q >= T])] if (q >= T).any() else np.nan; nl = c[np.argmin(np.abs(np.log(q / T)))]
    # consistency of the actual chosen strike
    i = np.where(c == r.strike)[0]
    if len(i): i = i[0]; pc = q[i]; pin = q[i - 1] if i > 0 else np.nan; pout = q[i + 1] if i + 1 < len(q) else np.nan
    else: pc = pin = pout = np.nan
    rows.append((fl, ce, nl, pc / T if pc == pc else np.nan, pin / T if pin == pin else np.nan))
R = pd.DataFrame(rows, columns=['FLOOR', 'CEIL', 'NEAREST_LOG', 'pc_over_T', 'pin_over_T']); S = pd.concat([S.reset_index(drop=True), R], axis=1)
out = []
for nm in ('P25', 'FLOOR', 'CEIL', 'NEAREST_LOG'):
    h = (S[nm] == S.strike); out.append(dict(rule=nm, n=len(S), exact=h.mean().round(3), within_1_step=(np.abs(S[nm] - S.strike) <= S.step * 1.0001).mean().round(3)))
print(pd.DataFrame(out).to_string(index=False))
print('chosen strike price / target T quantiles', S.pc_over_T.quantile([.05, .25, .5, .75, .95]).round(3).tolist(), ' inner neighbour / T', S.pin_over_T.quantile([.05, .25, .5, .75, .95]).round(3).tolist())
print('share chosen <= T:', (S.pc_over_T <= 1).mean().round(3), ' inner > T:', (S.pin_over_T > 1).mean().round(3), ' floor-consistent:', ((S.pc_over_T <= 1) & (S.pin_over_T > 1)).mean().round(3))
S.to_csv(f'{OUT}/bh_h2_simple_variants.csv', index=False)
