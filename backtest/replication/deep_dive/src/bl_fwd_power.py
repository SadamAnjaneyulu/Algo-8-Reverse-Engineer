"""Power analysis for the frozen forward test (reports/FORWARD_TEST.md). Per-cycle ladder scores of the development cycles (outputs/trig/ladder_scores.csv, post-auction, 16 Oct excluded):
candidate R* = ladder on FUT, gate 5; current simulator R0 = ladder on FEED, gate 60. Statistic = paired difference of pooled event-level F1 (R* - R0) over m forward cycles,
resampling development cycles with replacement (cluster bootstrap). SE(m) = SD of the statistic over 4000 resamples; minimum detectable effect at 80% power / 5% two-sided = 2.8 SE.
Because the candidate was selected on the development cycles its observed effect is optimistic, so power is also reported for shrunken true effects.
Output outputs/fwd/power.csv, power_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import norm
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RNG = np.random.default_rng(99)
def f1(tp, npred, hit, nreal):
    p = tp / max(npred, 1); r = hit / max(nreal, 1); return 2 * p * r / (p + r) if p + r else 0.0
if __name__ == '__main__':
    D = pd.read_csv(f'{OUT}/trig/ladder_scores.csv'); D = D[D.era == 'after']
    a = D[(D.underlying == 'FUT') & (D.G == 5)].set_index(['und', 'expiry']); b = D[(D.underlying == 'FEED') & (D.G == 60)].set_index(['und', 'expiry']); idx = a.index.intersection(b.index)
    A = a.loc[idx, ['tp', 'npred', 'hit', 'nreal']].values; B = b.loc[idx, ['tp', 'npred', 'hit', 'nreal']].values; n = len(idx)
    dev = f1(*A.sum(0)) - f1(*B.sum(0)); rows = []
    for m in (10, 17, 20, 30, 40, 60, 80, 120):
        s = []
        for _ in range(4000):
            k = RNG.integers(0, n, m); s.append(f1(*A[k].sum(0)) - f1(*B[k].sum(0)))
        s = np.array(s); se = s.std(); rows.append(dict(cycles=m, weeks_two_indices=m / 2.0, se=se, mde_80=2.8 * se, power_at_dev_effect=float(norm.cdf(dev / se - 1.96)), power_at_half=float(norm.cdf(dev / 2 / se - 1.96)), power_at_0p05=float(norm.cdf(0.05 / se - 1.96)), power_at_0p10=float(norm.cdf(0.10 / se - 1.96))))
    P = pd.DataFrame(rows); P.to_csv(f'{OUT}/fwd/power.csv', index=False)
    ev = D[(D.underlying == 'FUT') & (D.G == 5)].groupby(['und', 'expiry']).nreal.sum()
    summ = dict(dev_cycles=n, dev_delta_F1=dev, F1_candidate=f1(*A.sum(0)), F1_current=f1(*B.sum(0)), events_per_cycle=float(ev.mean()), cycles_for_mde_0p10=int(P[P.mde_80 <= 0.10].cycles.min()) if (P.mde_80 <= 0.10).any() else None, cycles_for_80pct_power_half_effect=int(P[P.power_at_half >= 0.8].cycles.min()) if (P.power_at_half >= 0.8).any() else None)
    json.dump(summ, open(f'{OUT}/fwd/power_summary.json', 'w'), indent=1, default=float); print(P.round(3).to_string(index=False)); print(json.dumps(summ, indent=1, default=lambda z: round(float(z), 3)))
