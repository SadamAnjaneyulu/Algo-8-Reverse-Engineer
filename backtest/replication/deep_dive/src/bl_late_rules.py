"""Late D-1 strike and side rules, teacher-forced: at every real late sale (book state as it really was), does a candidate rule predict the real strike / side?
Candidate rules written here before scoring (0 parameters, except S_OFFSET whose single offset is chosen leave-one-cycle-out). Accuracy with cycle-cluster bootstrap.
Output outputs/late/rule_scores.csv, rule_predictions.csv."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from collections import defaultdict
import bl_bt3_sim as S, bl_d0x_diag as DG
OUT = S.OUT; LT = f'{OUT}/late'; D = pd.read_csv(f'{LT}/late_sales.csv'); O = DG.real_orders(); rng = np.random.default_rng(20261124)
def held_shorts(g, t, cp):
    pos = defaultdict(int)
    for r in g[(g.t_last < t)].itertuples(): pos[(r.cp, int(r.strike))] += r.sg * int(r.lots)
    return {k: -v for (c2, k), v in pos.items() if c2 == cp and v < 0}
P = []
for (u, e), d in D.groupby(['und', 'expiry']):
    c = S.load(u, e); K = c['opt1']['K']; op = c['opt1']; st = S.ref.STEP[u]; g = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0)]
    for r in d.itertuples():
        jj = min(max(int(r.j), 1), 374); sg = 1 if r.cp == 'CE' else -1; atm = r.atm; held = held_shorts(g, r.t, r.cp)
        px = lambda k: (lambda i: float(op[(r.cp, 'close')][i, jj - 1]) if i < len(K) and K[i] == k else np.nan)(int(np.searchsorted(K, k)))
        cand = [k for k in K if abs(k - atm) <= 4 * st]
        prem = (min(cand, key=lambda k: abs(px(k) - r.last_price) if px(k) == px(k) else 1e9) if r.last_price == r.last_price else atm)
        heldk = list(held)
        P.append(dict(und=u, expiry=e, era=r.era, cp=r.cp, strike=r.strike, offset=r.offset,
                      S_ATM=atm, S_LAST=r.last_strike if r.last_strike == r.last_strike else atm, S_PREM=prem,
                      S_BIG=max(held, key=held.get) if held else atm, S_NEARHELD=min(heldk, key=lambda k: abs(k - atm)) if heldk else atm,
                      S_NEARHELD_ITM=min(heldk, key=lambda k: abs(k - (atm - sg * st))) if heldk else atm - sg * st,
                      D_TREND='CE' if r.spot_move_15 < 0 else 'PE', D_MORE='CE' if r.short_CE > r.short_PE else 'PE', D_LESS='CE' if r.short_CE < r.short_PE else 'PE',
                      D_ALT=('PE' if r.last_any_cp == 'CE' else 'CE') if isinstance(r.last_any_cp, str) else 'CE', D_SAME=r.last_any_cp if isinstance(r.last_any_cp, str) else 'CE', st=st, atm=atm))
P = pd.DataFrame(P)
# S_OFFSET: ATM + m steps toward ITM, m chosen as the modal offset of the OTHER cycles (leave-one-cycle-out)
P['cyc'] = P.und + P.expiry; P['S_OFFSET'] = np.nan
for cy in P.cyc.unique():
    m = P[P.cyc != cy].offset.mode().iloc[0]; idx = P.cyc == cy; P.loc[idx, 'S_OFFSET'] = P.loc[idx, 'atm'] + np.where(P.loc[idx, 'cp'] == 'CE', 1, -1) * m * P.loc[idx, 'st']
P.to_csv(f'{LT}/rule_predictions.csv', index=False)
def boot(df, f):
    cy = df.cyc.unique(); g = {k: v for k, v in df.groupby('cyc')}; bs = [f(pd.concat([g[k] for k in rng.choice(cy, len(cy))])) for _ in range(1000)]; return f(df), np.quantile(bs, .025), np.quantile(bs, .975)
rows = []
for era, g in P.groupby('era'):
    for rule in ('S_ATM', 'S_OFFSET', 'S_LAST', 'S_PREM', 'S_BIG', 'S_NEARHELD', 'S_NEARHELD_ITM'):
        for lab, f in (('exact', lambda x, r=rule: (x[r] == x.strike).mean()), ('within 1 step', lambda x, r=rule: (np.abs(x[r] - x.strike) <= x.st + 1e-9).mean())):
            v, lo, hi = boot(g, f); rows.append(dict(era=era, target='strike', rule=rule, measure=lab, value=v, lo=lo, hi=hi))
    for rule in ('D_TREND', 'D_MORE', 'D_LESS', 'D_ALT', 'D_SAME'):
        v, lo, hi = boot(g, lambda x, r=rule: (x[r] == x.cp).mean()); rows.append(dict(era=era, target='side', rule=rule, measure='exact', value=v, lo=lo, hi=hi))
    base = max((g.cp == 'CE').mean(), (g.cp == 'PE').mean()); rows.append(dict(era=era, target='side', rule='base rate (always majority side)', measure='exact', value=base, lo=np.nan, hi=np.nan))
R = pd.DataFrame(rows); R.to_csv(f'{LT}/rule_scores.csv', index=False); pd.set_option('display.width', 200); print(R.round(3).to_string(index=False))
