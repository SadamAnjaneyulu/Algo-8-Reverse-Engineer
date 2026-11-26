"""D0 chunk 2, addendum 2c (post-hoc, plan reports/D0_BUYBACKS_PLAN.md): is the stop reference of carried (D-1) lots the D0 opening premium (09:15 minute close) instead of the D-1 entry?
2c-T1 carried-lot panel: AUC of the minute-high ratio vs D-1 entry and vs D0 open; hazard by bin; cycle-bootstrap CI of the AUC difference.
2c-T2 K3 refit (theta x price grid, then take-profit) with carried lots re-based to the D0 open, out-of-fold (cid parity), paired bootstrap of the F1 difference vs K3 with D-1 entry.
Outputs bl_d0b_carry_hz.csv, bl_d0b_carry.csv, bl_summary_d0b6.json"""
import sys, warnings, itertools, copy; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
src = open('bl_d0b_mach.py').read(); exec(src[:src.index('rows = []; chosen = {}; PER = {}')])
P = pd.read_pickle(f'{OUT}/bl_d0b_panel.pkl.gz'); P = P[P.origin == 'D-1'].copy(); ref0 = {}
for i in D0C:
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}
    for cp in ('CE', 'PE'):
        for k, x in ki.items(): ref0[(i, cp, k)] = op[(cp, 'close')][x, 0]
P['open0'] = [ref0.get((i, cp, int(k)), np.nan) for i, cp, k in zip(P.cid, P.cp, P.strike)]; P = P[P.open0 > 0]; P['ro'] = P.rh * P.entry / P.open0
rng = np.random.default_rng(13); u = P.cid.unique(); idx = {c_: np.where(P.cid.values == c_)[0] for c_ in u}; y = P.y.values; a1 = roc_auc_score(y, P.rh); a2 = roc_auc_score(y, P.ro); bs = []
for _ in range(500):
    k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); bs.append(roc_auc_score(y[k], P.ro.values[k]) - roc_auc_score(y[k], P.rh.values[k]))
R = dict(carried_lot_minutes=int(len(P)), carried_events=int(y.sum()), auc_vs_d1_entry=a1, auc_vs_d0_open=a2, auc_diff_ci=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
BINS = [0, .25, .5, .75, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2, 2.5, 99]; hz = []
for col, nm in (('rh', 'D-1 entry'), ('ro', 'D0 open')):
    t = P.groupby(pd.cut(P[col], BINS), observed=True).y.agg(['mean', 'size'])
    for b, x in t.iterrows(): hz.append(dict(reference=nm, ratio_bin=str(b), hazard_pct=100 * x['mean'], lot_minutes=int(x['size'])))
HZ = pd.DataFrame(hz); HZ.to_csv(f'{OUT}/bl_d0b_carry_hz.csv', index=False); print(HZ.pivot(index='ratio_bin', columns='reference', values='hazard_pct').round(2).to_string()); print(R)
# 2c-T2: rebased copy of the machine inputs
C0 = C; C1 = copy.deepcopy(C)
for i in D0C:
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; d = C1[i]; m = d['org'] == 0
    L = [l for l in BK[i]['lots'] if not (l['entry_day'] == 0 and l.get('exit_day', 1) == 0 and l['exit_tod'] == l['exit_tod']) and l['strike'] in ki]
    e = np.array([l['entry'] for l in L]); o0 = np.array([op[(l['cp'], 'close')][ki[l['strike']], 0] for l in L]); f = np.where(m & (o0 > 0), e / np.where(o0 > 0, o0, 1), 1.0)
    for key in ('H', 'Lo', 'Cp'): d[key] = d[key] * f[:, None]
def fitK3(tr):
    best = max(itertools.product(TH_, ('high', 'close')), key=lambda c: f1(dict(theta=c[0], price=c[1]), tr)); P_ = dict(theta=best[0], price=best[1])
    b2 = max(itertools.product((0.1, 0.15, 0.2, 0.25, 0.3, 0.4), (0, 165, 225, 285)), key=lambda c: f1(dict(P_, tp=c[0], tp_gate=c[1]), tr)); P3 = dict(P_, tp=b2[0], tp_gate=b2[1])
    return P3 if f1(P3, tr) > f1(P_, tr) else P_
out = {}; ch = {}
for nm, CC in (('K3, carried lots vs D-1 entry', C0), ('K3, carried lots vs D0 open', C1)):
    C = CC; per = []; ch[nm] = []
    for h in (0, 1):
        tr = [i for i in D0C if i % 2 != h]; te = [i for i in D0C if i % 2 == h]; Pf = fitK3(tr); ch[nm].append(str(Pf)); per += score(Pf, te)[1]
    out[nm] = per
a = np.array(out['K3, carried lots vs D-1 entry'], float); b = np.array(out['K3, carried lots vs D0 open'], float); F = lambda x: 2 * x[:, 0].sum() / (x[:, 1].sum() + x[:, 2].sum()); ds = []
for _ in range(1000): k = rng.integers(0, len(a), len(a)); ds.append(F(b[k]) - F(a[k]))
T = pd.DataFrame([dict(machine=nm, F1=F(np.array(out[nm], float)), chosen=' / '.join(ch[nm])) for nm in out]); T.to_csv(f'{OUT}/bl_d0b_carry.csv', index=False); print(T.to_string(index=False))
R['F1_d1_entry'] = F(a); R['F1_d0_open'] = F(b); R['F1_diff_ci'] = [float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))]; rec('d0b6', R); print(R)
