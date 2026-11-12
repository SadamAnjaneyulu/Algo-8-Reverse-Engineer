"""Milestone 2 addendum: frozen index bars at the end of the session (found after the Milestone 1 audit).

Finding: on every index session from 2026-08-03 to 2026-10-09 (NIFTY and SENSEX) the last bars before 15:20 are flat carried prices
(open = high = low = close = previous close) and the 15:20 bar then jumps to the real level. On 2026-10-12..22 the same minutes are missing
(Milestone 1, check B5). June and July sessions are clean.
This script (i) classifies every session, (ii) counts Milestone 2 observations whose LABEL window contains a frozen bar,
(iii) recomputes the sensitivity results (5-minute labels, grid phases) with and without those observations.
Primary results (grid phase 0, 15/30/60 min) are NOT changed; this is a report, not a re-lock.
python3 stage2_alpha_research/audit/closing_zone_check.py   -> results/m2_closing_zone_*.csv
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); S2 = os.path.dirname(HERE); sys.path.insert(0, S2)
import s2common as sc
from targets import targets as tg
from baselines import run_baselines as rb
from validation import splits as sp, inference as inf
N = sc.N


def sessions(mats):
    rows = []
    for u, (dates, O, H, L, C) in mats.items():
        flat = (O == H) & (H == L) & (L == C)
        same = np.zeros_like(flat); same[:, 1:] = C[:, 1:] == C[:, :-1]
        fz = flat & same
        for i, d in enumerate(dates):
            idx = np.where(fz[i])[0]
            late = idx[idx >= 300]
            rows.append(dict(und=u, date=d, frozen_bars=int(fz[i].sum()), frozen_before_bar_300=int((idx < 300).sum()),
                             first_frozen_bar=int(late.min()) if len(late) else -1, last_frozen_bar=int(late.max()) if len(late) else -1,
                             missing_bars=int(np.isnan(C[i]).sum()),
                             first_real_bar_after=int(late.max()) + 1 if len(late) else -1))
    S = pd.DataFrame(rows)
    S['status'] = np.where(S.first_frozen_bar >= 0, 'frozen tail', np.where(S.missing_bars > 0, 'missing bars', 'clean'))
    return S


def metrics(x):
    r = x.dropna(subset=['tr', 'r'])
    out = dict(n=len(x), dates=x.date.nunique(), mean_r_bp=x.r.mean(), bl3_ic=inf.pearson(r.tr.values, r.r.values), bl3_rank_ic=inf.spearman(r.tr.values, r.r.values),
               bl3_hit=inf.hit_rate(r.tr.values, r.r.values))
    for t, p in (('rv', 'trv'), ('rg', 'trg')):
        y = x.dropna(subset=[t, p]); out[f'bl5_rank_ic_{t}'] = inf.spearman(y[p].values, y[t].values)
    return out


def main():
    G, mats, O, Z = rb.build_panel([5, 15, 30, 60])
    S = sessions(mats); S.to_csv(os.path.join(sc.RES, 'm2_closing_zone_sessions.csv'), index=False)
    G = G.merge(S[['und', 'date', 'first_frozen_bar', 'status']], on=['und', 'date'], how='left')
    G['label_end'] = G.kd + G.h - 1
    G['touch'] = (G.first_frozen_bar >= 0) & (G.label_end >= G.first_frozen_bar)
    G['touch'] |= (G.status == 'missing bars') & (G.label_end >= 361)             # sessions with missing closing minutes (never reached by the primary grid)
    rows = []
    for h in (15, 30, 60, 5):
        phases = [0] if h == 5 else list(range(h))
        for ph in phases:
            x = G[(G.h == h) & G.kd.isin(sp.grid(h, ph))]
            for flag, y in (('all grid rows', x), ('excluding label windows with frozen/missing bars', x[~x.touch])):
                rows.append(dict(horizon_min=h, phase=ph, rows=flag, **metrics(y), touching_rows_in_all=int(x.touch.sum())))
    R = pd.DataFrame(rows); R.to_csv(os.path.join(sc.RES, 'm2_closing_zone_sensitivity.csv'), index=False)
    pd.set_option('display.width', 250)
    print(S.groupby(['und', 'status']).size().unstack(fill_value=0))
    print(S[S.first_frozen_bar >= 0].groupby('und').agg(first=('date', 'min'), last=('date', 'max'), n=('date', 'size'), first_bar_min=('first_frozen_bar', 'min'), first_bar_max=('first_frozen_bar', 'max')))
    prim = R[(R.phase == 0)]
    print(prim.round(4).to_string(index=False))
    for h in (15, 30, 60):
        a = R[(R.horizon_min == h) & (R.rows == 'all grid rows')]; b = R[(R.horizon_min == h) & (R.rows != 'all grid rows')]
        print(h, 'phases: rank IC range all', a.bl3_rank_ic.min().round(3), a.bl3_rank_ic.max().round(3), 'excl', b.bl3_rank_ic.min().round(3), b.bl3_rank_ic.max().round(3),
              '| mean r range all', a.mean_r_bp.min().round(2), a.mean_r_bp.max().round(2), 'excl', b.mean_r_bp.min().round(2), b.mean_r_bp.max().round(2))


if __name__ == '__main__':
    main()
