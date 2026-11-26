"""Phase A G6 (plan: reports/PHASE_A_G1_G6_PLAN.md): do the D0 residual buy-back classes show a price structure in the DECISION-price ratio (ref_px / entry; ref_px = limit-implied decision price)?
Classes: carried residual (entry_day 0, types 5-8), 'other' (type 8), burst members (type 7); reference = known stop class (type 3). Candidate if IQR <= 1.5 x the stop class IQR and median >= 1.2. Output outputs/phaseA/g6.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S
PA = f'{S.OUT}/phaseA'
def stats(x):
    q = x.quantile([.1, .25, .5, .75, .9]); return dict(lots=int(len(x)), q10=float(q[.1]), q25=float(q[.25]), median=float(q[.5]), q75=float(q[.75]), q90=float(q[.9]), iqr=float(q[.75] - q[.25]), share_in_loss=float((x > 1.0).mean()))
def run():
    X = pd.read_pickle(f'{S.OUT}/bl_d0y_lots.pkl.gz'); X = X[X.ratio.notna() & np.isfinite(X.ratio)]; ty = X.type.str[0]
    cls = {'known stop class (type 3, reference)': X[ty == '3'].ratio, 'carried residual (entry on D-1, types 5-8)': X[(X.entry_day == 0) & ty.isin(list('5678'))].ratio, '"other" (type 8)': X[ty == '8'].ratio, 'burst members (type 7)': X[ty == '7'].ratio, 'carried take-profit (type 4, D-1 entry)': X[(ty == '4') & (X.entry_day == 0)].ratio}
    res = {k: stats(v) for k, v in cls.items()}; ref = res['known stop class (type 3, reference)']['iqr']
    for k in list(res):
        if 'reference' in k or 'take-profit' in k: continue
        res[k]['iqr_over_stop_iqr'] = res[k]['iqr'] / ref; res[k]['candidate'] = bool(res[k]['iqr'] <= 1.5 * ref and res[k]['median'] >= 1.2)
    # a second, bar-free view for the carried residual: the same ratio split by the lot's D-1 entry type
    c = X[(X.entry_day == 0) & ty.isin(list('5678'))]; res['carried_residual_by_entry_type'] = {t: stats(g.ratio) for t, g in c.groupby('typ') if len(g) >= 30}
    res['stop_iqr_x1_5'] = 1.5 * ref; res['auc_gate_note'] = 'AUC against non-events not testable: decision prices exist only for traded lots'
    json.dump(res, open(f'{PA}/g6.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3)))
if __name__ == '__main__': run()
