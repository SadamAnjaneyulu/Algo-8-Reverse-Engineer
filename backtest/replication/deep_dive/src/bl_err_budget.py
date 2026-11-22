"""Lot-construction step 1 (plan D1_LOTS_PLAN.md): error budget of the free-running D-1 reconstruction (primary, out-of-fold orders from bl_fr_score).
Lot-level matching per cycle x class x right (same minute first, then +-1; same sub-type preferred), then every unmatched lot gets one cause:
real: quantity shortfall (simulated lots of the class within +-1 min) / timing (only within 2-5 min) / missed event (none within 5 min) / not modelled;
simulated: quantity excess / timing / spurious. Body sells are split by real sub-type (scheduled, reactive, solo intraday, late solo, deep) and by simulated sub-type.
Outputs bl_err_budget.csv, bl_err_budget_types.csv, bl_summary_eb1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
SDo = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); SDo['sub'] = np.where(SDo.deep, 'deep-OTM', np.where((SDo.typ == 'solo') & (SDo.te >= 54000), 'solo after 15:00', np.where(SDo.typ == 'solo', 'solo intraday', SDo.typ)))
ORD = pd.read_pickle(f'{OUT}/bl_fr_orders.pkl.gz')['FR free-running (primary)']; R = {}
def real_lots(i, cls, cp):
    if cls == 'body_sell':
        z = SDo[(SDo.cid == i) & (SDo.cp == cp)]; z = lots_of(z); return list(zip(z.j.astype(int), z['sub']))
    rj, rk = RL.get((i, cls, cp), (np.array([], int), None)); return [(int(j), cls) for j in rj]
def classify(i, cls, cp, real, sim):
    rj = np.array([j for j, _ in real], int); sj = np.array([j for j, _ in sim], int)
    used_s = np.zeros(len(sim), bool); used_r = np.zeros(len(real), bool); bucket = {}
    for n, j in enumerate(sj): bucket.setdefault(int(j), []).append(n)
    for ps in (0, 1):
        for a, (j, t) in enumerate(real):
            if used_r[a]: continue
            cands = [n for jj in ({j} if ps == 0 else {j - 1, j + 1}) for n in bucket.get(jj, []) if not used_s[n]]
            if cands:
                same = [n for n in cands if sim[n][1] == t] or cands; used_s[same[0]] = True; used_r[a] = True
    out = []
    for a, (j, t) in enumerate(real):
        if used_r[a]: out.append(('real', t, 'matched')); continue
        if cls == 'not_modelled': out.append(('real', t, 'not modelled')); continue
        near1 = len(sj) and np.any(np.abs(sj - j) <= 1); near5 = len(sj) and np.any(np.abs(sj - j) <= 5)
        out.append(('real', t, 'quantity shortfall' if near1 else ('timing (2-5 min)' if near5 else 'missed event')))
    for n, (j, t) in enumerate(sim):
        if used_s[n]: continue
        near1 = len(rj) and np.any(np.abs(rj - j) <= 1); near5 = len(rj) and np.any(np.abs(rj - j) <= 5)
        out.append(('sim', t, 'quantity excess' if near1 else ('timing (2-5 min)' if near5 else 'spurious event')))
    return out
rows = []
for i in ids:
    o = lots_of(ORD[i]) if len(ORD[i]) else ORD[i]
    for cls in NMOD + ['not_modelled']:
        for cp in ('CE', 'PE'):
            real = real_lots(i, cls, cp); g = o[(o.cls == cls) & (o.cp == cp)] if len(o) and cls != 'not_modelled' else o.iloc[0:0]
            sim = list(zip(g.j.astype(int), g.typ.fillna('').replace('', cls))) if len(g) else []
            if cls != 'body_sell': sim = [(j, cls) for j, _ in sim]
            for side, t, cause in classify(i, cls, cp, real, sim): rows.append(dict(cid=i, cls=cls, cp=cp, side=side, sub=t, cause=cause))
E_ = pd.DataFrame(rows); E_.to_pickle(f'{OUT}/bl_err_lots.pkl.gz')
B = E_.groupby(['cls', 'side', 'cause']).size().unstack(['side', 'cause'], fill_value=0); B.to_csv(f'{OUT}/bl_err_budget.csv'); pd.set_option('display.width', 250); print(B.to_string())
tot = E_.groupby(['side', 'cause']).size(); print(tot.to_string())
T = E_[E_.cls == 'body_sell'].groupby(['side', 'sub', 'cause']).size().unstack('cause', fill_value=0); T.to_csv(f'{OUT}/bl_err_budget_types.csv'); print(T.to_string())
R['totals'] = {f'{a}|{b}': int(v) for (a, b), v in tot.items()}; rec('eb1', R)
