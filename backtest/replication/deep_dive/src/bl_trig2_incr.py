"""Late-sale trigger investigation, part 4: does any portfolio-state feature add to the frozen directional score, strictly before the minute? (leave-one-cycle-out logistic, same machinery as the audit; EXPLORATORY, counted: 5 comparisons)
Models (all use the strictly-pre-minute futures features FUTL_*, LOCO clock):  A = FUTL_ext5 + FUTL_mv1 + clock ; B = A + sold_deficit ; C = A + straddle_chg_15 ; D = A + sold_deficit + straddle_chg_15 ; E = sold_deficit + straddle_chg_15 + clock (no direction).
Output outputs/trig2/incremental.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
import bl_validation as V
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); T2 = f'{OUT}/trig2'; RNG = np.random.default_rng(4242)
D = pd.read_csv(f'{OUT}/trig/event_table.csv.gz'); D = D[(D.era == 'after') & (D.outlier == 0)].reset_index(drop=True); D['cyc'] = D.und + '|' + D.expiry
ev = D[D.y == 1]; n = D.cyc.nunique(); cnt = ev.groupby(['j', 'side']).cyc.nunique(); own = ev.groupby(['j', 'side', 'cyc']).size().reset_index()[['j', 'side', 'cyc']].assign(m=1)
D = D.merge(own, on=['j', 'side', 'cyc'], how='left'); D['m'] = D.m.fillna(0); D['clock'] = [(cnt.get((j, s), 0) - m) / (n - 1) for j, s, m in zip(D.j, D.side, D.m)]
M = pd.read_csv(f'{T2}/state_minutes.csv'); M = M[M.outlier == 0][['und', 'd1', 'j', 'side', 'sold_deficit', 'net_deficit', 'straddle_chg_15', 'decay_same', 'mtm_change_15']]; D = D.merge(M, on=['und', 'd1', 'j', 'side'], how='left')
D = D.assign(FUTL5=D.FUTL_ext5, FUTL1=D.FUTL_mv1)
MODELS = {'A_frozen_features_strictly_before': ['FUTL5', 'FUTL1', 'clock'], 'B_A_plus_sold_deficit': ['FUTL5', 'FUTL1', 'clock', 'sold_deficit'], 'C_A_plus_straddle_chg_15': ['FUTL5', 'FUTL1', 'clock', 'straddle_chg_15'], 'D_A_plus_both': ['FUTL5', 'FUTL1', 'clock', 'sold_deficit', 'straddle_chg_15'], 'E_state_only_plus_clock': ['sold_deficit', 'straddle_chg_15', 'clock']}
cyc = sorted(D.cyc.unique()); res = dict(rows=int(len(D)), events=int(D.y.sum()), cycles=len(cyc), missing_state_rows=int(D.sold_deficit.isna().sum()), corr_sold_deficit_FUTL5_on_event_rows=float(D[D.y == 1][['sold_deficit', 'FUTL5']].corr().iloc[0, 1]), corr_sold_deficit_FUTL5_all=float(D[['sold_deficit', 'FUTL5']].corr().iloc[0, 1]))
oof = {}
for nm, F in MODELS.items():
    o = np.full(len(D), np.nan)
    for h in cyc:
        tr = D[D.cyc != h]; te = (D.cyc == h).values; med = tr[F].median(); X = tr[F].fillna(med).values; mu, sd = X.mean(0), X.std(0) + 1e-9; lr = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, tr.y.values); o[te] = lr.decision_function((D.loc[te, F].fillna(med).values - mu) / sd)
    oof[nm] = o
T = D.assign(**{k: v for k, v in oof.items()}, base=D.clock); C = V.components(T, list(MODELS) + ['base'])
def blk(a, b):
    lo, hi = V.boot_ci(C, a, b, 0.95, 4000, RNG); llo, lhi, se = V.lin_ci(C, a, b, 0.95); return dict(auc_a=V.auc_from(C, a), auc_b=V.auc_from(C, b), delta=V.delta_from(C, a, b), boot95=[lo, hi], lin95=[llo, lhi], p_lin_two_sided=float(2 * (1 - __import__('scipy.stats', fromlist=['norm']).norm.cdf(abs(V.delta_from(C, a, b) / se)))) if se > 0 else None)
res['aucs'] = {k: V.auc_from(C, k) for k in list(MODELS) + ['base']}; res['clock_auc'] = V.auc_from(C, 'base')
res['B_vs_A'] = blk('B_A_plus_sold_deficit', 'A_frozen_features_strictly_before'); res['C_vs_A'] = blk('C_A_plus_straddle_chg_15', 'A_frozen_features_strictly_before'); res['D_vs_A'] = blk('D_A_plus_both', 'A_frozen_features_strictly_before'); res['E_vs_clock'] = blk('E_state_only_plus_clock', 'base'); res['A_vs_clock'] = blk('A_frozen_features_strictly_before', 'base')
loo = V.leave_one_cycle_out(C, 'C_A_plus_straddle_chg_15', 'A_frozen_features_strictly_before'); res['C_vs_A_leave_one_cycle_out'] = dict(min=float(min(loo.values())), max=float(max(loo.values())), cycles_positive=int(sum(v > 0 for v in loo.values())), of=len(loo))
json.dump(res, open(f'{T2}/incremental.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 4)))
