"""Solo recall step 2: reconstruct the D-1 solo sells with the earlier findings and rescore.
R0 stated rule (fresh 15-min extreme of closes, 1 lot). R1 rule from the earlier studies: fresh favourable extreme over N AND favourable 30-min move > 0 (optional) AND own-right book ratio <= a AND other-right ratio >= b (grid; chosen on the other cycle half). R2 best model: gradient boosting on all the earlier variables, leave-one-cycle-out, probability threshold chosen on the training cycles (upper bound of what these variables can do as a rule).
Strike: earlier premium-continuity rule (strike whose previous-minute price is nearest the previous sale price on that right) vs ATM, on matched lots.
Outputs bl_solo_recon.csv, bl_solo_fires.pkl.gz, bl_summary_solo1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.ensemble import HistGradientBoostingClassifier
exec(open('bl_all_sells.py').read().split("ACT = {d['cid']")[0])
P = pd.read_pickle(f'{OUT}/bl_solo_panel.pkl.gz'); ACT = {d['cid']: actual(d) for d in CYC}; ids = [d['cid'] for d in CYC]; R = {}
AC = {}
for i in ids:
    a = ACT[i]; a = a[(a.typ == 'solo') & (a.j <= 374)]
    for unit in ('lot', 'minute'):
        aa = a.drop_duplicates(['j', 'cp']) if unit == 'minute' else a
        for cp in ('CE', 'PE'): AC[(i, unit, cp)] = np.bincount(aa[aa.cp == cp].j.values.astype(int), minlength=376).astype(int)
def fmatch(a, p):
    """greedy one-to-one matching of minute-count arrays within +-1 minute: exact first, then neighbours"""
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); tp = int(m.sum()); a -= m; p -= m
    for k in range(len(a)):
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(a) and p[k] > 0 and a[kk] > 0: x = min(p[k], a[kk]); tp += x; p[k] -= x; a[kk] -= x
    return tp
def score(fl, cids, unit='lot'):
    """fl: DataFrame cid, j, cp of predicted solo minutes (1 lot each)"""
    tp = nf = na = 0; g = fl.groupby(['cid', 'cp']).j.apply(lambda x: np.bincount(x.values.astype(int), minlength=376)).to_dict() if len(fl) else {}
    for i in cids:
        for cp in ('CE', 'PE'):
            a = AC[(i, unit, cp)]; p = g.get((i, cp), np.zeros(376, int)); tp += fmatch(a, p); nf += int(p.sum()); na += int(a.sum())
    return 2 * tp / max(nf + na, 1), tp / max(nf, 1), tp / max(na, 1)
rows = []
fl0 = P[P.bk15 == 1][['cid', 'j', 'cp']]
for unit in ('lot', 'minute'): f, p_, r_ = score(fl0, ids, unit); rows.append(dict(model='R0 stated: fresh 15-min extreme of closes', unit=unit, F1=f, precision=p_, recall=r_, params=''))
# R1 grid
grid = [(N, src, a, b, fv) for N in (5, 15, 30, 60) for src in ('bk', 'bkhl') for a in (0.8, 0.9, 1.0, 1.1, 9) for b in (0, 0.9, 1.0, 1.1) for fv in (0, 1)]
def flags(cfg):
    N, src, a, b, fv = cfg; m = (P[f'{src}{N}'] == 1) & ((P.own_ratio <= a) | (a == 9) | P.own_ratio.isna()) & ((P.other_ratio >= b) | (b == 0) | P.other_ratio.isna())
    if fv: m &= P.fav30 > 0
    return P[m][['cid', 'j', 'cp']]
FL = {cfg: flags(cfg) for cfg in grid}
for unit in ('lot', 'minute'):
    tp = nf = na = 0; ch_ = []
    for h in (0, 1):
        tr = [i for i in ids if i % 2 == h]; te = [i for i in ids if i % 2 != h]; best = max(grid, key=lambda c: score(FL[c], tr, unit)[0]); ch_.append(best)
        f, p_, r_ = score(FL[best], te, unit); n_f = len(FL[best][FL[best].cid.isin(te)]); n_a = sum(int(AC[(i, unit, cp)].sum()) for i in te for cp in ('CE', 'PE')); tp += r_ * n_a; nf += n_f; na += n_a
    rows.append(dict(model='R1 earlier-findings rule: fresh extreme AND book conditions (out-of-fold)', unit=unit, F1=2 * tp / (nf + na), precision=tp / nf, recall=tp / na, params=str(ch_)))
    ins = max(grid, key=lambda c: score(FL[c], ids, unit)[0]); f, p_, r_ = score(FL[ins], ids, unit); rows.append(dict(model='R1 in-sample best', unit=unit, F1=f, precision=p_, recall=r_, params=str(ins)))
R['R1_choice'] = {u: None for u in ('lot', 'minute')}
# R2 model (LOCO GB) with threshold chosen on training cycles
feats = [c for c in P.columns if c not in ('cid', 'und', 'j', 'cp', 'y', 'lots')]; P['is_ce'] = (P.cp == 'CE').astype(int); feats += ['is_ce']
X = P[feats].values.astype(float); y = P.y.values; prob = np.zeros(len(P)); thr = {}
for i in ids:
    te = P.cid.values == i; tr = ~te; m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=250, min_samples_leaf=30, l2_regularization=1.0, random_state=0).fit(X[tr], y[tr]); prob[te] = m.predict_proba(X[te])[:, 1]
    pt = m.predict_proba(X[tr])[:, 1]; best = (0, .5)
    for t in np.quantile(pt, np.linspace(.80, .995, 40)):
        tp_ = ((pt >= t) & (y[tr] == 1)).sum(); f_ = 2 * tp_ / ((pt >= t).sum() + y[tr].sum())
        if f_ > best[0]: best = (f_, t)
    thr[i] = best[1]
P['prob'] = prob; P['fire'] = [int(p >= thr[c]) for p, c in zip(P.prob, P.cid)]
fl2 = P[P.fire == 1][['cid', 'j', 'cp']]
for unit in ('lot', 'minute'): f, p_, r_ = score(fl2, ids, unit); rows.append(dict(model='R2 best model on all earlier variables (LOCO, threshold out-of-fold)', unit=unit, F1=f, precision=p_, recall=r_, params='GB'))
from scipy.stats import rankdata
def auc(s, yy): n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
R['R2_auc'] = float(auc(prob, y)); R['R2_auc_excl_slot'] = float(auc(prob[P.slot_minute.values == 0], y[P.slot_minute.values == 0]))
# by time of day for R2 (minute level)
tod = []
for lab, lo_, hi_ in (('09:15-15:00', 0, 344), ('15:00-15:30', 345, 374)):
    tp = nf = na = 0; fl = fl2[(fl2.j >= lo_) & (fl2.j <= hi_)]
    for i in ids:
        for cp in ('CE', 'PE'):
            a = AC[(i, 'lot', cp)].copy(); a[:lo_] = 0; a[hi_ + 1:] = 0; p = np.bincount(fl[(fl.cid == i) & (fl.cp == cp)].j.values.astype(int), minlength=376); tp += fmatch(a, p); nf += int(p.sum()); na += int(a.sum())
    tod.append(dict(window=lab, actual_lots=na, model_lots=nf, precision=tp / max(nf, 1), recall=tp / max(na, 1)))
R['R2_by_time'] = tod; print(pd.DataFrame(tod).round(3).to_string(index=False))
S = pd.DataFrame(rows); S.round(4).to_csv(f'{OUT}/bl_solo_recon.csv', index=False); print(S.round(3).to_string(index=False)); print('R2 AUC', R['R2_auc'])
P[['cid', 'j', 'cp', 'prob', 'fire']].to_pickle(f'{OUT}/bl_solo_fires.pkl.gz'); R['rows'] = S.round(4).to_dict('records'); R['grid_size'] = len(grid); rec('solo1', R)
