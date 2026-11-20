"""H2: hedge-strike rules on 'simple' wing buys (1 trigger body lot, 1 wing lot). Candidate list fixed BEFORE running (plan section 3, H2):
 P20/P25/P30: choose the OTM same-side strike (beyond the sold strike) whose chain close at minute j_dec-1 is nearest to k x (body reference price), k = 2.0/2.5/3.0 %
 P25o: same, k = 2.5 %, price = chain open at minute j_dec
 FIX: fixed offset in steps, per (und, day) mode, leave-one-cycle-out
 PCT: fixed distance in % of previous-minute spot, per (und, day) median, leave-one-cycle-out, nearest strike
Null: same rule with the body reference price taken from a different simple order of the same (und, day) (shuffled pairing, seed 0).
Holm over the 6 rules (family) on the exact-hit rate vs the null (cluster bootstrap over cycles for CI)."""
import sys; sys.path.insert(0, '.')
from bh_common import *
W = pd.read_csv(f'{OUT}/bh_h2_wing_buys.csv', dtype={'tag': str}); S = W[W.simple & W.b_strike.notna()].copy(); ch = Chain(); rng = np.random.default_rng(0)
S['jd'] = np.floor((S.t_dec - ref.OPEN_SEC) / 60).astype(int); S['cyc'] = S.und + '_' + S.expiry
def target_choice(r, T, kind='close', jj=None):
    st = ch.strikes(r.und, r.expiry); jj = r.jd - 1 if jj is None else jj
    cand = st[(st > r.b_strike) if r.cp == 'CE' else (st < r.b_strike)]
    p = np.array([ch.px(r.und, r.expiry, r.dayno, r.cp, k, jj, kind) for k in cand]); ok = ~np.isnan(p) & (p >= 0.05)
    if not ok.any(): return np.nan
    return cand[ok][np.argmin(np.abs(p[ok] - T))]
res = {}
for nm, k, kind, jo in (('P20', .020, 'close', -1), ('P25', .025, 'close', -1), ('P30', .030, 'close', -1), ('P25o', .025, 'open', 0)):
    pred = []; nul = []
    for und_day, g in S.groupby(['und', 'dayno']):
        pool = g.b_ref.values
        for r in g.itertuples():
            jj = r.jd + jo; pred.append(target_choice(r, k * r.b_ref, kind, jj)); nul.append(target_choice(r, k * rng.choice(pool), kind, jj))
    S[nm] = pd.Series(pred, index=pd.concat([g for _, g in S.groupby(['und', 'dayno'])]).index); S[nm + '_null'] = pd.Series(nul, index=pd.concat([g for _, g in S.groupby(['und', 'dayno'])]).index)
# FIX and PCT leave-one-cycle-out
S['spot_prev'] = [ch.spot(r.und, r.expiry, r.dayno, r.jd - 1) for r in S.itertuples()]; S['off_pct'] = np.where(S.cp == 'CE', S.strike - S.spot_prev, S.spot_prev - S.strike) / S.spot_prev
fix = []; pct = []
for r in S.itertuples():
    tr = S[(S.und == r.und) & (S.dayno == r.dayno) & (S.cyc != r.cyc)]
    mode = tr.off_steps.round().mode().iloc[0]; fix.append(r.b_strike + (mode if r.cp == 'CE' else -mode) * r.step)
    med = tr.off_pct.median(); tgt = r.spot_prev * (1 + med) if r.cp == 'CE' else r.spot_prev * (1 - med); st = ch.strikes(r.und, r.expiry); pct.append(st[np.argmin(np.abs(st - tgt))])
S['FIX'] = fix; S['PCT'] = pct; S['FIX_null'] = np.nan; S['PCT_null'] = np.nan
out = []
for nm in ('P20', 'P25', 'P30', 'P25o', 'FIX', 'PCT'):
    hit = (S[nm] == S.strike); pm1 = (np.abs(S[nm] - S.strike) <= S.step * 1.0001)
    nh = (S[nm + '_null'] == S.strike) if nm not in ('FIX', 'PCT') else pd.Series(np.nan, index=S.index)
    # cluster bootstrap over cycles
    cy = S.cyc.unique(); bs = []
    for _ in range(500):
        s_ = rng.choice(cy, len(cy)); idx = np.concatenate([np.where(S.cyc.values == c)[0] for c in s_]); bs.append(hit.values[idx].mean())
    out.append(dict(rule=nm, n=len(S), exact=hit.mean(), ci_lo=np.quantile(bs, .025), ci_hi=np.quantile(bs, .975), within_1_step=pm1.mean(), null_exact=nh.mean()))
R = pd.DataFrame(out).round(3); R.to_csv(f'{OUT}/bh_h2_rule_tests.csv', index=False); print(R.to_string(index=False)); print('cycles', S.cyc.nunique())
for nm in ('P25', 'P25o'):
    print(nm, 'by (und, day) exact:', S.assign(h=S[nm] == S.strike).groupby(['und', 'dayno']).h.mean().round(3).to_dict())
S.drop(columns=[]).to_csv(f'{OUT}/bh_h2_simple_tested.csv', index=False)
