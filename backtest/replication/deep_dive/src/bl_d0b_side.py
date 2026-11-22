"""D0 chunk 2, addendum 2b (plan reports/D0_BUYBACKS_PLAN.md): side-level buy-back trigger.
2b-T1: single-variable AUC of side states for burst starts (>= 3 lots, same right, gap <= 30 s) on cells cycle x minute x right in scope (real book, same-minute close; lagged close as sensitivity).
2b-T2: Spearman of burst lots with lots above 1.4x, premium imbalance, open lots. 2b-T3: rebalancing band machine (own-book semantics: real sells, machine's own removals), alone and with K3 (stop + take-profit).
Outputs bl_d0b_side_auc.csv, bl_d0b_side_size.csv, bl_d0b_side_mach.csv, bl_summary_d0b4.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
import bl_greeks
src = open('bl_d0b_mach.py').read(); exec(src[:src.index('rows = []; chosen = {}; PER = {}')])
SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); R = {}
# per-lot price and delta matrices
for i in D0C:
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; K = op['K']; s = SPT[(r.und, r.expiry)].close.values; T = np.maximum(55800 - (33300 + 60 * np.arange(375) + 60), 60) / (365 * 86400.)
    dl = {cp: bl_greeks.surface(op[(cp, 'close')], s, K, T, cp)[1] for cp in ('CE', 'PE')}; ki = {int(k): x for x, k in enumerate(K)}
    L = [l for l in BK[i]['lots'] if not (l['entry_day'] == 0 and l.get('exit_day', 1) == 0 and l['exit_tod'] == l['exit_tod']) and l['strike'] in ki]
    x = np.array([ki[l['strike']] for l in L]); cpi = C[i]['cp']; C[i]['px'] = np.nan_to_num(np.where(cpi[:, None] == 0, op[('CE', 'close')][x], op[('PE', 'close')][x]), nan=0.0)
    C[i]['dl'] = np.nan_to_num(np.abs(np.where(cpi[:, None] == 0, dl['CE'][x], dl['PE'][x])), nan=0.0); C[i]['entry'] = np.array([l['entry'] for l in L]); C[i]['spot'] = s; C[i]['st'] = ref.STEP[r.und]
# bursts (>= 3 lots) -> event minutes
ev = {}; bur = []
for (i, cp), g in XS.groupby(['cid', 'cp']):
    g = g.sort_values('tod'); gid = (g.tod.diff().fillna(1e9) > 30).cumsum()
    for _, x in g.groupby(gid):
        bur.append(dict(cid=i, cp=cp, j=int(x.j.min()), n=len(x)))
        if len(x) >= 3: ev.setdefault((i, cp), set()).add(int(x.j.min()))
BU = pd.DataFrame(bur)
def states(i, j, ci, alive, lag=0):
    d = C[i]; jj = j - lag; m = alive & (d['cp'] == ci); mo = alive & (d['cp'] != ci); px = d['px'][:, jj]; dl = d['dl'][:, jj]; sg = 1 if ci == 0 else -1; s = d['spot']
    vo, vt = px[m].sum(), px[mo].sum(); do_, dt = dl[m].sum(), dl[mo].sum(); rr = (d['H'][m, jj] if lag == 0 else d['Cp'][m, j]) if m.any() else np.array([0.0])
    return dict(stop_rmax=rr.max(), prem_imb=np.log((vo + 1) / (vt + 1)), lot_imb=np.log((m.sum() + 1) / (mo.sum() + 1)), delta_share=do_ / (do_ + dt) if do_ + dt > 0 else 0.5, unreal_loss=float((px[m] - d['entry'][m]).sum()),
                adv_mv5=sg * (s[jj] - s[max(jj - 5, 0)]) / d['st'], n_open=int(m.sum()), n_above14=int((rr >= 1.4).sum()))
rows = []
for i in D0C:
    d = C[i]
    for j in range(2, d['je'] + 1):
        al = (d['j0'] <= j) & (d['jx'] >= j)
        for ci, cp in ((0, 'CE'), (1, 'PE')):
            a = states(i, j, ci, al); b = states(i, j, ci, al, lag=1); rows.append(dict(cid=i, j=j, cp=cp, y=int(j in ev.get((i, cp), set())), **a, **{f'lag_{k}': v for k, v in b.items()}))
X = pd.DataFrame(rows); VARS = ['stop_rmax', 'prem_imb', 'lot_imb', 'delta_share', 'unreal_loss', 'adv_mv5']; rng = np.random.default_rng(9); out = []
for v in VARS:
    for pre in ('', 'lag_'):
        y = X.y.values; p = X[pre + v].values; u = X.cid.unique(); idx = {c_: np.where(X.cid.values == c_)[0] for c_ in u}; bs = []
        for _ in range(300):
            k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))]); bs.append(roc_auc_score(y[k], p[k]))
        h0 = (X.cid % 2 == 0).values; out.append(dict(variable=v, timing='same-minute close' if pre == '' else 'previous close (lag 1)', AUC=roc_auc_score(y, p), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5),
                                                       AUC_half_even=roc_auc_score(y[h0], p[h0]), AUC_half_odd=roc_auc_score(y[~h0], p[~h0])))
TA = pd.DataFrame(out); TA.to_csv(f'{OUT}/bl_d0b_side_auc.csv', index=False); print(TA.round(3).to_string(index=False)); R['events'] = int(X.y.sum()); R['cells'] = int(len(X))
# 2b-T2 burst size
BX = BU.merge(X[['cid', 'j', 'cp', 'n_above14', 'prem_imb', 'n_open', 'delta_share']], on=['cid', 'j', 'cp'], how='inner'); sz = []
for v in ('n_above14', 'prem_imb', 'n_open', 'delta_share'):
    for nm, g in (('all bursts', BX), ('bursts >= 3 lots', BX[BX.n >= 3])): rho, pv = spearmanr(g.n, g[v]); sz.append(dict(variable=v, bursts=nm, n=len(g), spearman=rho, p=pv))
TS = pd.DataFrame(sz); TS.to_csv(f'{OUT}/bl_d0b_side_size.csv', index=False); print(TS.round(3).to_string(index=False))
# 2b-T3 rebalancing band machine (own-book semantics)
def sim(i, var, band, q, K3=None):
    d = C[i]; n = len(d['j0']); ex = np.full(n, 999); out = {0: [], 1: []}
    for j in range(1, d['je'] + 1):
        al = (d['j0'] <= j) & (ex > j)
        if K3:
            hit = al & ((d['H'][:, j] >= K3['theta']) | (d['Lo'][:, j] <= K3.get('tp', -1)))
            for a in np.where(hit)[0]: ex[a] = j; out[d['cp'][a]].append(j)
            al = al & ~hit
        if var is None: continue
        for ci in (0, 1):
            v = states(i, j, ci, al)[var]
            if v > band:
                m = np.where(al & (d['cp'] == ci))[0]
                if not len(m): continue
                k = max(1, int(round(q * len(m)))); sel = m[np.argsort(-d['H'][m, j])[:k]]; ex[sel] = j; al[sel] = False; out[ci] += [j] * len(sel)
    return {'CE': hist(out[0]), 'PE': hist(out[1])}
def sc(pred, cids):
    per = []
    for i in cids:
        x = [0, 0, 0]
        for cp in ('CE', 'PE'): p = pred[i][cp]; a = C[i]['real'][cp]; x[0] += mt(a, p); x[1] += int(p.sum()); x[2] += int(a.sum())
        per.append(tuple(x))
    a = np.array(per); return 2 * a[:, 0].sum() / max(a[:, 1].sum() + a[:, 2].sum(), 1), per
K3s = {h: json.loads(json.load(open(f'{OUT}/bl_d0b_mach_chosen.json'))['K3 + take-profit'][h]) for h in (0, 1)}
res = []; per_all = {}
for mode in ('band alone', 'band + K3', 'K3 alone (own-book, reference)'):
    per = []; ch = []
    for h in (0, 1):
        tr = [i for i in D0C if i % 2 != h]; te = [i for i in D0C if i % 2 == h]; k3 = {'theta': K3s[h]['theta'], 'tp': K3s[h].get('tp', -1)} if mode != 'band alone' else None
        if mode.startswith('K3 alone'): per += sc({i: sim(i, None, 0, 0, k3) for i in te}, te)[1]; ch.append('K3'); continue
        Xt = X[X.cid.isin(tr)]; best = None
        for v in VARS:
            if v == 'adv_mv5': continue
            for qq in (0.9, 0.95, 0.98, 0.99):
                b = float(Xt[v].quantile(qq))
                for q in (0.05, 0.1, 0.2):
                    f, _ = sc({i: sim(i, v, b, q, k3) for i in tr}, tr)
                    if best is None or f > best[0]: best = (f, v, b, q)
        _, v, b, q = best; ch.append(f'{v} > {b:.3g} (q {q})'); per += sc({i: sim(i, v, b, q, k3) for i in te}, te)[1]
    a = np.array(per); per_all[mode] = per; res.append(dict(machine=mode, F1=2 * a[:, 0].sum() / (a[:, 1].sum() + a[:, 2].sum()), precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / a[:, 2].sum(), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()), chosen=' / '.join(ch)))
    print(res[-1])
TM = pd.DataFrame(res); TM.to_csv(f'{OUT}/bl_d0b_side_mach.csv', index=False); print(TM.round(3).to_string(index=False))
R['auc'] = TA.round(4).to_dict('records'); R['size'] = TS.round(4).to_dict('records'); R['mach'] = TM.round(4).to_dict('records'); rec('d0b4', R)
