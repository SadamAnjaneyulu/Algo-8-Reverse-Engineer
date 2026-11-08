"""Allocation timer chains via phase-density with a Poisson null (no transitive linking).
Per session date: phase = seconds since 09:15:00 mod 900 for each sale burst. Slide a 30 s window (5 s step) over the phase circle,
count DISTINCT quarter-hours with a burst in the window. Null: uniform phases -> Poisson(mean = n_q * 30/900) where n_q = number of
distinct quarter-hours containing any burst that day. Keep windows with p < 1e-4, greedily non-overlapping (|dphase| > 30 s).
python3 analysis/chains.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from scipy.stats import poisson
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
b = pd.read_pickle(os.path.join(C, 'sale_bursts.pkl')).sort_values('t').reset_index(drop=True)
b['ph'] = b.sec % 900; b['q'] = (b.sec // 900).astype(int)
W, STEP, PTHR = 30, 5, 1e-4
rows = []; b['chain'] = -1; b['chain_phase'] = np.nan; cid = 0
for date, g in b.groupby('date'):
    nq = g.q.nunique(); lam = nq * W / 900
    cands = []
    for c in np.arange(0, 900, STEP):
        dphi = (g.ph - c + 450) % 900 - 450
        inw = g[(dphi >= -W / 2) & (dphi < W / 2)]
        k = inw.q.nunique()
        if k >= 3: cands.append((poisson.sf(k - 1, lam), -k, c))
    cands.sort()
    chosen = []
    for p, negk, c in cands:
        if p >= PTHR: break
        if all(min(abs(c - c2), 900 - abs(c - c2)) > W for c2 in chosen): chosen.append(c)
    for c in chosen:
        dphi = (g.ph - c + 450) % 900 - 450
        m = g.index[(dphi >= -W / 2) & (dphi < W / 2)]
        b.loc[m, 'chain'] = cid; b.loc[m, 'chain_phase'] = c
        sub = b.loc[m]
        rows.append(dict(chain=cid, date=date, day=sub.day.iloc[0], phase=c, start=sub.t.min(), end=sub.t.max(), n_quarters=sub.q.nunique(),
                         n_bursts=len(sub), p=poisson.sf(sub.q.nunique() - 1, lam)))
        cid += 1
cs = pd.DataFrame(rows)
cs['phase_mmss'] = cs.phase.apply(lambda x: f'{int(x // 60):02d}:{int(x % 60):02d}')
cs['kind'] = np.where(cs.phase.between(40, 160), 'grid-morning', np.where((cs.phase < 25) | (cs.phase > 885), 'grid-:00', 'event-anchored'))
b = b.merge(cs[['chain', 'kind']], on='chain', how='left'); b['kind'] = b.kind.fillna('unchained')
b.to_pickle(os.path.join(C, 'chains.pkl')); cs.to_pickle(os.path.join(C, 'chain_summary.pkl'))
# null check: shuffle phases within each date (keep quarter structure), rerun detection count
def n_detect(df):
    n = 0
    for date, g in df.groupby('date'):
        nq = g.q.nunique(); lam = nq * W / 900
        for c in np.arange(0, 900, 15):
            dphi = (g.ph - c + 450) % 900 - 450
            k = g[(dphi >= -W / 2) & (dphi < W / 2)].q.nunique()
            if k >= 3 and poisson.sf(k - 1, lam) < PTHR: n += 1
    return n
if __name__ == '__main__':
    pd.set_option('display.width', 220); pd.set_option('display.max_rows', 300)
    print('bursts', len(b), '| share in significant chains', round((b.chain >= 0).mean(), 3))
    print(cs.groupby(['day', 'kind']).agg(chains=('chain', 'size'), bursts=('n_bursts', 'sum'), med_quarters=('n_quarters', 'median')).to_string())
    rng = np.random.default_rng(0); nulls = []
    ng = b[b.kind.isin(['event-anchored', 'unchained'])].copy()
    for rep in range(5):
        x = ng.copy(); x['ph'] = rng.uniform(0, 900, len(x)); nulls.append(n_detect(x))
    print('significant phase windows among non-grid bursts: observed', n_detect(ng), '| shuffled-phase null runs', nulls)
    e = cs[cs.kind == 'event-anchored'].sort_values('start')
    print('\nevent-anchored chains: start hour', e.start.dt.hour.value_counts().sort_index().to_dict())
    print(e[['date', 'day', 'phase_mmss', 'start', 'end', 'n_quarters', 'n_bursts', 'p']].head(30).to_string(index=False))
