"""Audit statistics on the development cycles (reports/OVERFITTING_AUDIT.md). Frozen rule and score untouched; this only re-measures the reported effect.
(a) reproduction, (b) leave-one-cycle-out vs CHRONOLOGICAL walk-forward, (c) strictly-pre-minute features, (d) order-second profile (look-ahead check), (e) leave-one-cycle-out sensitivity, (f) sample sizes.
Output outputs/audit/dev_stats.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
import bl_validation as V, bl_d0x_diag as DG
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs'); AU = f'{OUT}/audit'; RNG = np.random.default_rng(777); FEATS = ['FUT_ext5', 'FUT_mv1', 'clock']
M = json.load(open(f'{OUT}/fwd/frozen_model.json')); table = M['clock_table']
D = pd.read_csv(f'{OUT}/trig/event_table.csv.gz'); D = D[(D.era == 'after') & (D.outlier == 0)].reset_index(drop=True); D['cyc'] = D.und + '|' + D.expiry; D['tab'] = [table[f'{j}|{s}'] for j, s in zip(D.j, D.side)]
# LOCO clock (as in the original analysis)
ev = D[D.y == 1]; n = D.cyc.nunique(); cnt = ev.groupby(['j', 'side']).cyc.nunique(); own = ev.groupby(['j', 'side', 'cyc']).size().reset_index()[['j', 'side', 'cyc']].assign(m=1)
D = D.merge(own, on=['j', 'side', 'cyc'], how='left'); D['m'] = D.m.fillna(0); D['clock'] = [(cnt.get((j, s), 0) - m) / (n - 1) for j, s, m in zip(D.j, D.side, D.m)]
def fz(T, mdl=M):
    X = T[mdl['features']].copy()
    for c in mdl['features']: X[c] = X[c].fillna(mdl['medians'][c])
    return ((X.values - np.array(mdl['mean'])) / np.array(mdl['std'])) @ np.array(mdl['coef']) + mdl['intercept']
def ci_block(C, a, b, label):
    est = V.delta_from(C, a, b); lo95, hi95 = V.boot_ci(C, a, b, 0.95, 4000, RNG); llo, lhi, se = V.lin_ci(C, a, b, 0.95); return dict(label=label, auc_model=V.auc_from(C, a), auc_base=V.auc_from(C, b), delta=est, boot95=[lo95, hi95], lin95=[llo, lhi], se_lin=se, eff_cycles=V.effective_cycles(C), cycles=int(len(C)))
res = dict(rows=int(len(D)), events=int(D.y.sum()), negatives=int((1 - D.y).sum()), cycles=int(D.cyc.nunique()), events_per_cycle=float(D.y.sum() / D.cyc.nunique()), cycles_with_events=int((D.groupby('cyc').y.sum() > 0).sum()))
# (a) in-sample with the frozen coefficients and the frozen table
T = D.assign(score=fz(D.assign(clock=D.tab)), base=D.tab); Ctab = V.components(T, ['score', 'base']); res['a0_insample_table_DIAGNOSTIC'] = ci_block(Ctab, 'score', 'base', 'frozen coefficients + frozen table scored on the cycles that built them: baseline is inflated (own events are in its cells)')
T = D.assign(score=fz(D), base=D.clock); C = V.components(T, ['score', 'base']); res['a_frozen_coeffs_loco_clock'] = ci_block(C, 'score', 'base', 'frozen coefficients (fitted on all cycles) with leave-own-cycle-out clock; baseline = same clock')
# (b1) leave-one-cycle-out with the 3 features pre-chosen (as in bl_fwd_freeze: LOCO clock, model refit without the held cycle)
cyc = sorted(D.cyc.unique()); oof = np.full(len(D), np.nan)
for h in cyc:
    tr = D[D.cyc != h]; te = D.cyc == h; med = tr[FEATS].median(); X = tr[FEATS].fillna(med).values; mu, sd = X.mean(0), X.std(0) + 1e-9; lr = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, tr.y.values); oof[te.values] = lr.decision_function((D.loc[te, FEATS].fillna(med).values - mu) / sd)
T = D.assign(score=oof, base=D.clock); C1 = V.components(T, ['score', 'base']); res['b1_loco_prechosen'] = ci_block(C1, 'score', 'base', 'leave-one-cycle-out, 3 features pre-chosen on ALL cycles (the reported +0.098)')
# (b2) chronological expanding window: train on earlier cycles only (coefficients AND clock table), predict the next cycle; first 8 cycles are warm-up
order = D.drop_duplicates('cyc').sort_values('d1').cyc.tolist(); oofc = pd.Series(np.nan, index=D.index); basec = pd.Series(np.nan, index=D.index); used = []
for k in range(8, len(order)):
    tr_c, te_c = order[:k], order[k]; tr = D[D.cyc.isin(tr_c)]; te = D.cyc == te_c; evt = tr[tr.y == 1]; tab = evt.groupby(['j', 'side']).cyc.nunique() / len(tr_c)
    trf = tr.assign(clock=[tab.get((j, s), 0.0) for j, s in zip(tr.j, tr.side)])   # table including the training cycles themselves (in-sample for training, as it will be at forward time)
    med = trf[FEATS].median(); X = trf[FEATS].fillna(med).values; mu, sd = X.mean(0), X.std(0) + 1e-9; lr = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, trf.y.values)
    tec = D[te].assign(clock=[tab.get((j, s), 0.0) for j, s in zip(D[te].j, D[te].side)]); oofc[te.values] = lr.decision_function((tec[FEATS].fillna(med).values - mu) / sd); basec[te.values] = tec.clock.values; used.append(te_c)
Tc = D[D.cyc.isin(used)].assign(score=oofc[D.cyc.isin(used)], base=basec[D.cyc.isin(used)]); C2 = V.components(Tc, ['score', 'base']); res['b2_chronological'] = ci_block(C2, 'score', 'base', f'chronological expanding window ({len(used)} test cycles after 8 warm-up cycles), features still pre-chosen on all cycles')
# (c) strictly pre-minute features: same frozen coefficients, features computed through minute j-1 instead of through minute j
Tl = D.assign(FUT_ext5=D.FUTL_ext5, FUT_mv1=D.FUTL_mv1); Cl = V.components(Tl.assign(score=fz(Tl), base=Tl.clock), ['score', 'base']); res['c_lag1_frozen_coeffs'] = ci_block(Cl, 'score', 'base', 'frozen coefficients, features through minute j-1 (strictly before the minute), frozen table')
# (d) order-second profile: positives split by the second of the minute of the first real order; the features use the whole minute
Od = DG.real_orders(); Od = Od.assign(jj=(Od.t_last // 60 - 555).astype(int), sec=(Od.t_last % 60).astype(int)); first = {}
for q in Od[(Od.dayno == 0) & (Od.role == 'open_short')].itertuples(): first.setdefault((q.und + '|' + q.expiry, q.cp, q.jj), q.sec)
D['sec'] = [first.get((c, s, j)) for c, s, j in zip(D.cyc, D.side, D.j)]; prof = {}
for lab, lo, hi in (('early_0_19s', 0, 19), ('mid_20_39s', 20, 39), ('late_40_59s', 40, 59)):
    keep = D[(D.y == 0) | ((D.sec >= lo) & (D.sec <= hi))]; Tk = keep.assign(score=fz(keep.assign(clock=keep.tab)), base=keep.tab); Ck = V.components(Tk, ['score', 'base']); prof[lab] = dict(positives=int(keep.y.sum()), **{k: v for k, v in ci_block(Ck, 'score', 'base', lab).items() if k in ('auc_model', 'auc_base', 'delta', 'boot95')})
res['d_second_profile_insample'] = prof
# (e) leave-one-cycle-out sensitivity
for key, CC in (('a', C), ('b1', C1), ('b2', C2)):
    lo_ = V.leave_one_cycle_out(CC, 'score', 'base'); s = pd.Series(lo_); res[f'e_loo_{key}'] = dict(min=float(s.min()), max=float(s.max()), cycle_of_min=s.idxmin(), cycle_of_max=s.idxmax(), n_below_zero=int((s <= 0).sum()))
# (f) share of the pooled delta contributed by the single largest cycle (influence)
ak = C['U_score'] - C['U_base']; res['f_influence_top_cycle_share_of_numerator'] = float(ak.abs().max() / ak.abs().sum()); res['f_cycles_with_positive_contribution'] = int((ak > 0).sum()); res['f_cycles_with_events'] = int((C.d > 0).sum())
# (g) exploratory, NOT part of the frozen endpoint: strictly-pre-minute features restricted to positives whose first order fell in the first 20 s of the minute
keep = D[(D.y == 0) | (D.sec <= 19)]; Tk = keep.assign(FUT_ext5=keep.FUTL_ext5, FUT_mv1=keep.FUTL_mv1); Ck = V.components(Tk.assign(score=fz(Tk), base=Tk.clock), ['score', 'base']); res['g_lag1_early_second_positives_EXPLORATORY'] = dict(positives=int(keep.y.sum()), **{k: v for k, v in ci_block(Ck, 'score', 'base', 'g').items() if k in ('auc_model', 'auc_base', 'delta', 'boot95')})
keep = D[(D.y == 0) | (D.sec <= 19)]; Ck = V.components(keep.assign(score=fz(keep), base=keep.clock), ['score', 'base']); res['g2_contemporaneous_early_second_positives_EXPLORATORY'] = dict(positives=int(keep.y.sum()), **{k: v for k, v in ci_block(Ck, 'score', 'base', 'g2').items() if k in ('auc_model', 'auc_base', 'delta', 'boot95')})
res['d_second_distribution_of_positives'] = D[D.y == 1].sec.describe().round(1).to_dict()
json.dump(res, open(f'{AU}/dev_stats.json', 'w'), indent=1, default=float)
for k, v in res.items():
    if isinstance(v, dict) and 'lin95' in v: print(f"{k}: model {v['auc_model']:.3f} base {v['auc_base']:.3f} delta {v['delta']:+.3f} boot95 [{v['boot95'][0]:+.3f},{v['boot95'][1]:+.3f}] lin95 [{v['lin95'][0]:+.3f},{v['lin95'][1]:+.3f}] cycles {v['cycles']} eff {v['eff_cycles']:.1f}")
print('g lag1 early', res['g_lag1_early_second_positives_EXPLORATORY'], '| g2 contemporaneous early', res['g2_contemporaneous_early_second_positives_EXPLORATORY'], '| sec dist', res['d_second_distribution_of_positives']); print('LOO b1', res['e_loo_b1']); print({k: res[k] for k in ('rows', 'events', 'negatives', 'cycles', 'events_per_cycle', 'cycles_with_events')}); print('second profile', json.dumps({k: {a: (round(b, 3) if not isinstance(b, list) else [round(x, 3) for x in b]) for a, b in v.items()} for k, v in prof.items()})); print('LOO', res['e_loo_a'], res['e_loo_b2']); print('influence', res['f_influence_top_cycle_share_of_numerator'], res['f_cycles_with_positive_contribution'], '/', res['f_cycles_with_events'])
