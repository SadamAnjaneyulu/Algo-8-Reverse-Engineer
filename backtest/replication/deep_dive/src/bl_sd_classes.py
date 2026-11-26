"""Solo decode step 10: split regular solo lots into (a) attached to a reactive fire (within 3 s before to 10 s after a reactive pair, any right), (b) after 15:00, (c) intraday stand-alone; per-class share, side behaviour, and the combined model's recall/precision per class (model components: attached extras by depth for (a), the spot ladder for (c), nothing for (b)).
Outputs bl_sd_classes.csv, bl_summary_sd9.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
_s = open('bl_sd_combined.py').read(); exec(_s.split("ids = list(range(len(CY))); rows = []")[0])
Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); X = pd.read_pickle(f'{OUT}/bl_sd_tilt.pkl.gz'); R = {}
S = D[(D.typ == 'solo') & ~D.deep].copy(); cls = []
for r in S.itertuples():
    cy = CY.iloc[r.cid]; g = Pr[(Pr.und == cy.und) & (Pr.expiry == cy.expiry) & Pr.reactive]
    if ((g.te - r.te >= -10) & (g.te - r.te <= 3)).any(): cls.append('attached to a reactive entry')
    elif r.te >= 54000: cls.append('after 15:00')
    else: cls.append('intraday stand-alone')
S['cls'] = cls
a, b = fit_extra(list(range(len(CY)))); rows = []
for c_ in ('attached to a reactive entry', 'intraday stand-alone', 'after 15:00'):
    tp = nf = na = 0; sub = S[S.cls == c_]
    for i in range(len(CY)):
        pr = predict(i, 1.0, a, b, True, c_ == 'attached to a reactive entry', c_ == 'intraday stand-alone')
        for cp in ('CE', 'PE'):
            act = np.bincount(sub[(sub.cid == i) & (sub.cp == cp)].j.clip(0, 375).values.astype(int), minlength=377); p = pr[('solo', cp)].copy()
            if c_ == 'intraday stand-alone': p[345:] = 0
            if c_ == 'after 15:00': p[:] = 0
            tp += fmatch(act, p); nf += int(p.sum()); na += int(act.sum())
    rows.append(dict(solo_class=c_, lots=len(sub), share=len(sub) / len(S), model_component=('extras sized by break depth' if c_.startswith('attached') else ('spot ladder at fresh 60-min extremes' if c_.startswith('intraday') else 'none')), model_lots=nf, precision=tp / max(nf, 1), recall=tp / max(na, 1), F1=2 * tp / max(nf + na, 1)))
C = pd.DataFrame(rows); C.round(4).to_csv(f'{OUT}/bl_sd_classes.csv', index=False); print(C.round(3).to_string(index=False)); R['classes'] = C.round(4).to_dict('records'); R['burst_lots'] = json.load(open(f'{OUT}/bl_summary_sd1.json'))['lots_per_burst']; rec('sd9', R)
