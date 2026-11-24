"""Freeze the forward-test score and compute the power of its primary test (reports/FORWARD_TEST.md).
Frozen score = L2 logistic (C=0.5, standardised) on three pre-chosen features of the FUT underlying: fresh favourable 5-minute extreme (FUT_ext5), 1-minute favourable move in strike steps
(FUT_mv1) and the minute-of-window clock frequency (LOCO on the development cycles). The three were chosen in 18/18, 17/18 and forced in the nested folds of bl_trig_followup.py.
Frozen clock table = frequency of real sales per (minute, side) over ALL development cycles. Primary forward statistic = stratified AUC(frozen score) - stratified AUC(frozen clock table),
within (cycle, side) blocks, cluster bootstrap over forward cycles. Output outputs/fwd/frozen_model.json (+ sha256), power_auc.csv."""
import sys, os, json, hashlib, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from scipy.stats import norm
from bl_trig_test import prep, blocks, strat
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); TR = f'{OUT}/trig'; FW = f'{OUT}/fwd'; RNG = np.random.default_rng(31); FEATS = ['FUT_ext5', 'FUT_mv1', 'clock']
if __name__ == '__main__':
    D0 = pd.read_csv(f'{TR}/event_table.csv.gz'); A = prep(D0[(D0.era == 'after') & (D0.outlier == 0)].reset_index(drop=True)); cyc = sorted(A.cyc.unique())
    # frozen clock table over all development cycles
    ev = A[A.y == 1]; table = {f'{j}|{s}': float(len(set(ev[(ev.j == j) & (ev.side == s)].cyc)) / len(cyc)) for j in range(360, 385) for s in ('CE', 'PE')}
    # LOCO out-of-fold score with the three frozen features (no selection), for the power analysis
    oof = np.full(len(A), np.nan)
    for held in cyc:
        tr = A[A.cyc != held]; te = A[A.cyc == held]; med = tr[FEATS].median(); Xtr = tr[FEATS].fillna(med).values; mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        lr = LogisticRegression(C=0.5, max_iter=500).fit((Xtr - mu) / sd, tr.y.values); oof[[A.index.get_loc(i) for i in te.index]] = lr.decision_function((te[FEATS].fillna(med).values - mu) / sd)
    A['oof'] = oof; A['clock_tab'] = [table[f'{j}|{s}'] for j, s in zip(A.j, A.side)]
    R, y, bl = blocks(A, ['oof', 'clock']); auc = strat(R, y, bl); ub = np.unique(bl); cyc_of = {b: b.rsplit('|', 1)[0] for b in ub}
    def draw(m):
        k = RNG.integers(0, len(cyc), m); cnt = pd.Series(k).map(lambda i: cyc[i]).value_counts(); return strat(R, y, bl, {b: cnt.get(cyc_of[b], 0) for b in ub})
    rows = []
    for m in (10, 18, 20, 30, 40, 60, 80):
        s = np.array([(lambda a: a[0] - a[1])(draw(m)) for _ in range(2000)]); se = s.std(); d = auc[0] - auc[1]
        rows.append(dict(cycles=m, se=se, mde_80=2.8 * se, power_at_dev=float(norm.cdf(d / se - 1.96)), power_at_half=float(norm.cdf(d / 2 / se - 1.96)), power_at_0p05=float(norm.cdf(0.05 / se - 1.96))))
    P = pd.DataFrame(rows); P.to_csv(f'{FW}/power_auc.csv', index=False)
    # final frozen fit on all development cycles
    med = A[FEATS].median(); X = A[FEATS].fillna(med).values; mu, sd = X.mean(0), X.std(0) + 1e-9; lr = LogisticRegression(C=0.5, max_iter=500).fit((X - mu) / sd, A.y.values)
    model = dict(version=1, features=FEATS, mean=mu.tolist(), std=sd.tolist(), coef=lr.coef_[0].tolist(), intercept=float(lr.intercept_[0]), medians=med.to_dict(), clock_table=table, window=[360, 384], underlying='FUT', basis='median(future - index) over 15:00-15:14',
                 dev_cycles=len(cyc), dev_events=int(A.y.sum()), dev_oof_auc=float(auc[0]), dev_clock_auc=float(auc[1]), dev_delta_auc=float(auc[0] - auc[1]))
    txt = json.dumps(model, indent=1, sort_keys=True); model['sha256_of_above'] = hashlib.sha256(txt.encode()).hexdigest(); open(f'{FW}/frozen_model.json', 'w').write(json.dumps(model, indent=1, sort_keys=True))
    print('dev OOF AUC', round(auc[0], 3), 'clock', round(auc[1], 3), 'delta', round(auc[0] - auc[1], 3)); print(P.round(3).to_string(index=False)); print('coef', dict(zip(FEATS, np.round(lr.coef_[0], 3))), 'sha', model['sha256_of_above'][:16])
