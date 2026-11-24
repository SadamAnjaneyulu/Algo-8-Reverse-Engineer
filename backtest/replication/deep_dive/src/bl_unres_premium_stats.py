"""Statistics for plan reports/UNRESOLVED_THREE_PLAN.md, Question 1 (E1-E5). Week-cluster bootstrap (2,000 draws, seed 20261124).
Output outputs/unres/prem_stats.csv, prem_moneyness_stats.csv, prem_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); UN = f'{OUT}/unres'; B = 1000; rng = np.random.default_rng(20261124)
C = pd.read_csv(f'{UN}/prem_cycles.csv'); M = pd.read_csv(f'{UN}/prem_moneyness.csv'); F = pd.read_csv(f'{UN}/prem_flow.csv')
for d in (C, M, F): d['wk'] = pd.to_datetime(d.expiry).dt.strftime('%G-%V')
def boot(df, f, n=B):
    w = df.wk.unique(); g = {k: v for k, v in df.groupby('wk')}; pt = f(df); bs = []
    for _ in range(n):
        try: bs.append(f(pd.concat([g[k] for k in rng.choice(w, len(w))])))
        except Exception: pass
    bs = np.array(bs, float); bs = bs[np.isfinite(bs)]; return (pt, np.quantile(bs, .025), np.quantile(bs, .975), bs) if len(bs) > 50 else (pt, np.nan, np.nan, bs)
rows = []
def add(test, stat, df, f, pred=''):
    pt, lo, hi, _ = boot(df, f); rows.append(dict(test=test, stat=stat, n=len(df), value=pt, lo=lo, hi=hi, prediction=pred, IS=f(df[df.split == 'IS']) if (df.split == 'IS').sum() > 3 else np.nan, OOS=f(df[df.split == 'OOS']) if (df.split == 'OOS').sum() > 3 else np.nan, live=f(df[df.split == 'LIVE_FITTED']) if (df.split == 'LIVE_FITTED').sum() > 3 else np.nan))
# ---------------- E1 settlement averaging
add('E1', 'Var[ln(settle / spot 15:00)] / Var[ln(spot 15:29 / spot 15:00)]', C, lambda x: (x.x_settle ** 2).mean() / (x.x_print ** 2).mean(), '~1/3 if the settlement is a 30-minute average; 1 if not')
add('E1', 'short straddle from 15:00 to the 15:29 print, % of premium', C, lambda x: (x.prem_1500 - x.pay_print).sum() / x.prem_1500.sum())
add('E1', 'short straddle from 15:00 to the official settlement, % of premium', C, lambda x: (x.prem_1500 - x.pay_settle).sum() / x.prem_1500.sum())
add('E1', 'extra premium from settlement averaging (settlement minus print), % of premium', C, lambda x: (x.pay_print - x.pay_settle).sum() / x.prem_1500.sum(), '> 0')
cv = C[C.w_1500 > 0]; add('E1', 'realised / implied variance, 15:00 to settlement', cv, lambda x: (x.x_settle ** 2).sum() / x.w_1500.sum()); add('E1', 'realised / implied variance, 15:00 to the 15:29 print', cv, lambda x: (x.x_print ** 2).sum() / x.w_1500.sum())
# ---------------- E2 pinning
P = C.dropna(subset=['pin_dist_steps']).copy(); pdist = []
for i, r in P.iterrows():
    st_ = {'NIFTY': 50.0, 'SENSEX': 100.0}[r.und]; o = P[(P.und == r.und) & (P.index != i)].pin_offset_steps.values; pdist.append(float(np.mean(np.abs(r.settle - (r.spot_1400 + o * st_)) / st_)))
P['placebo_dist'] = pdist; P['diff'] = P.pin_dist_steps - P.placebo_dist
add('E2', 'distance of settlement from the max-OI strike minus placebo distance (strike steps)', P, lambda x: x['diff'].mean(), '< 0 if pinned')
add('E2', 'share of cycles where the settlement is closer to the max-OI strike than the placebo', P, lambda x: (x['diff'] < 0).mean(), '> 0.5 if pinned')
P.to_csv(f'{UN}/prem_pin.csv', index=False)
# ---------------- E3 moneyness
MS = []
for (side, d), g in M.groupby(['side', 'dist']):
    pt, lo, hi, _ = boot(g, lambda x: x.price.sum() / x.payoff.sum() if x.payoff.sum() > 0 else np.nan); pt2, lo2, hi2, _ = boot(g, lambda x: (x.price.sum() - x.payoff.sum()) / x.atm_prem.sum())
    MS.append(dict(side=side, dist=d, n=len(g), mean_price=g.price.mean(), mean_payoff=g.payoff.mean(), share_expiring_in_the_money=(g.payoff > 0).mean(), price_over_payoff=pt, po_lo=lo, po_hi=hi, premium_minus_payoff_pct_of_atm_straddle=pt2, pm_lo=lo2, pm_hi=hi2))
MS = pd.DataFrame(MS); MS.to_csv(f'{UN}/prem_moneyness_stats.csv', index=False)
# ---------------- E4 order-flow proxy
Fq = F.dropna(subset=['sv', 'dw_next_surprise', 'dw_surprise']).copy(); sc = Fq.groupby('und').sv.transform(lambda x: x.abs().median()); Fq['z'] = Fq.sv / sc
for c_ in ('dw_next_surprise', 'dw_surprise'): lo_, hi_ = Fq[c_].quantile([.01, .99]); Fq[c_] = Fq[c_].clip(lo_, hi_)
slope = lambda x, y: float(np.polyfit(x.z, x[y], 1)[0])
add('E4', 'next-block change in implied variance not explained by realised variance, per unit of signed volume (z = signed volume / index median |signed volume|)', Fq, lambda x: slope(x, 'dw_next_surprise'), '< 0 if demand pressure reverses')
add('E4', 'same block (contemporaneous), per unit of signed volume', Fq, lambda x: slope(x, 'dw_surprise'), '> 0 (mechanical: sign classified from price)')
# ---------------- E5 where the D0 straddle premium accrues
Q = C.dropna(subset=['prem_0916', 'prem_1400', 'prem_1514']).copy()
for nm, f in (('09:16 to 14:00', lambda x: (x.prem_0916 - x.prem_1400).sum() / x.prem_0916.sum()), ('14:00 to 15:14', lambda x: (x.prem_1400 - x.prem_1514).sum() / x.prem_0916.sum()), ('15:14 to official settlement', lambda x: (x.prem_1514 - x.pay_settle_0916).sum() / x.prem_0916.sum()),
              ('09:16 to official settlement (total)', lambda x: (x.prem_0916 - x.pay_settle_0916).sum() / x.prem_0916.sum()), ('09:16 to the 15:29 print (total)', lambda x: (x.prem_0916 - x.pay_print_0916).sum() / x.prem_0916.sum())): add('E5', f'short ATM straddle, {nm}, % of the 09:16 premium', Q, f)
S = pd.DataFrame(rows); S.to_csv(f'{UN}/prem_stats.csv', index=False)
gp = C.gap_settle_print_bp; summ = dict(settle_print_gap_median_abs_bp=float(gp.abs().median()), settle_print_gap_p95_bp=float(gp.abs().quantile(.95)), pin_cycles=int(len(P)), flow_rows=int(len(Fq)))
json.dump(summ, open(f'{UN}/prem_summary.json', 'w'), indent=1); pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 110)
print(S[['test', 'stat', 'n', 'value', 'lo', 'hi', 'IS', 'OOS', 'live']].round(4).to_string()); print(MS.round(3).to_string()); print(summ)
