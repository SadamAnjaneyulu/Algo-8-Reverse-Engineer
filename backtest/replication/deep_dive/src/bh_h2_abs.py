"""H2 falsification of the premium-ratio story. Competing rule ABS: the wing's target price is a fixed absolute level per (und, day, 30-min slot), estimated leave-one-cycle-out (median wing decision-price of other cycles); strike = nearest chain price (j-1 close) among OTM strikes beyond the sold strike.
Also: variance decomposition of log(wing decision price) with (a) und x day x slot fixed effects only, (b) + log(body ref), and a tighter null for P25 (body ref shuffled WITHIN the same und, day and 30-min slot)."""
import sys; sys.path.insert(0, '.')
from bh_common import *
S = pd.read_csv(f'{OUT}/bh_h2_simple_variants.csv', dtype={'tag': str}); ch = Chain(); rng = np.random.default_rng(2)
S['slot'] = ((S.t_dec - ref.OPEN_SEC) // 1800).astype(int); S['cyc'] = S.und + '_' + S.expiry; S['grp'] = S.und + S.dayno.astype(str) + '_' + S.slot.astype(str)
def pick(r, T):
    st = ch.strikes(r.und, r.expiry); cand = st[(st > r.b_strike) if r.cp == 'CE' else (st < r.b_strike)]
    p = np.array([ch.px(r.und, r.expiry, r.dayno, r.cp, k, r.jd - 1, 'close') for k in cand]); ok = ~np.isnan(p) & (p >= .05); return cand[ok][np.argmin(np.abs(p[ok] - T))] if ok.any() else np.nan
abs_hit = []; slot_null = []
for r in S.itertuples():
    tr = S[(S.grp == r.grp) & (S.cyc != r.cyc)]
    abs_hit.append(pick(r, tr.w_ref.median()) == r.strike if len(tr) >= 5 else np.nan)
    pool = S[(S.grp == r.grp)].b_ref.values; slot_null.append(pick(r, .025 * rng.choice(pool)) == r.strike)
S['ABS_hit'] = abs_hit; S['P25_slotnull_hit'] = slot_null; S['P25_hit'] = S.P25 == S.strike
print('n', len(S), ' P25 exact %.3f' % S.P25_hit.mean(), '| P25 with body-ref shuffled within same und/day/slot: %.3f' % S.P25_slotnull_hit.mean(), '| ABS(slot median, LOCO) exact %.3f (n=%d)' % (S.ABS_hit.dropna().astype(float).mean(), S.ABS_hit.notna().sum()))
# variance decomposition
import numpy.linalg as la
y = np.log(S.w_ref.values); X0 = pd.get_dummies(S.grp).values.astype(float); X1 = np.column_stack([X0, np.log(S.b_ref.values)])
def r2(X): b, *_ = la.lstsq(X, y, rcond=None); res = y - X @ b; return 1 - res.var() / y.var()
print('R2 log(wing price): und/day/slot effects only %.3f ; + log(body ref) %.3f' % (r2(X0), r2(X1)))
print('ratio_ref by (und, day) quantiles 10/25/50/75/90:'); print(S.groupby(['und', 'dayno']).ratio_ref.quantile([.1, .25, .5, .75, .9]).unstack().round(4))
S.to_csv(f'{OUT}/bh_h2_simple_final.csv', index=False)
