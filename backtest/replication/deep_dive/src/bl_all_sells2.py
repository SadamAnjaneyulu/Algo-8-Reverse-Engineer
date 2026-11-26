"""Combined D-1 selling reconstruction, recalculated with the recalled solo findings.
Real sells split into: scheduled pairs, reactive pairs, solo (regular), deep-OTM batch sells (solo lots >= 5 strikes from ATM: end-of-day, 3 cycles).
Solo model variants: S0 stated fresh 15-min extreme; S1 earlier-findings rule (fresh favourable 60-min extreme on true highs/lows + book/30-min-move conditions, parameters chosen on the other cycle half); S2 gradient-boosting model of all earlier variables (LOCO, out-of-fold threshold). Each solo fire = 1 lot.
Outputs bl_all2_combined.csv, bl_all2_type.csv, bl_summary_all3.json"""
import sys, warnings, json, ast; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
exec(open('bl_all_sells.py').read().split("ACT = {d['cid']")[0])
R = {}; P = pd.read_pickle(f'{OUT}/bl_solo_panel.pkl.gz'); F2 = pd.read_pickle(f'{OUT}/bl_solo_fires.pkl.gz'); S1 = json.load(open(f'{OUT}/bl_summary_solo1.json'))
r1 = [r for r in S1['rows'] if r['model'].startswith('R1 earlier') and r['unit'] == 'lot'][0]; ch1 = ast.literal_eval(r1['params'])
def r1_flags(cfg):
    N, src, a, b, fv = cfg; m = (P[f'{src}{N}'] == 1) & ((P.own_ratio <= a) | (a == 9) | P.own_ratio.isna()) & ((P.other_ratio >= b) | (b == 0) | P.other_ratio.isna())
    if fv: m &= P.fav30 > 0
    return P[m]
S1F = pd.concat([r1_flags(ch1[h])[lambda x: x.cid % 2 != h] for h in (0, 1)])            # cycles of half (1-h) use parameters chosen on half h
ACT = {}
for d in CYC:
    A = actual(d); K = np.array(ch.cyc(d['und'], d['expiry'])['strikes'], float); jj = A.j.clip(1, 374).values
    atm = np.array([K[np.argmin(np.abs(K - d['c'][j - 1]))] for j in jj]); off = np.abs(A.strike.values - atm) / d['step']; A.loc[(A.typ == 'solo').values & (off >= 5), 'typ'] = 'deep-OTM batch'; ACT[d['cid']] = A
def solo_pred(d, variant):
    K = np.array(ch.cyc(d['und'], d['expiry'])['strikes'], float); near = lambda x: K[np.argmin(np.abs(K - x))]
    if variant == 'S0': sel = P[(P.cid == d['cid']) & (P.bk15 == 1)]
    elif variant == 'S1': sel = S1F[S1F.cid == d['cid']]
    else: sel = F2[(F2.cid == d['cid']) & (F2.fire == 1)]
    return pd.DataFrame([dict(j=int(r.j), cp=r.cp, strike=int(near(d['c'][int(r.j) - 1])), typ='solo') for r in sel.itertuples()])
rows = []; trows = []
for variant, lab in (('S0', 'stated rule (fresh 15-min extreme)'), ('S1', 'earlier-findings rule (out-of-fold)'), ('S2', 'best model of earlier variables (out-of-fold)')):
    agg = {k: [0, 0, 0] for k in ('all', 'excl_deep')}; per = {t: [0, 0, 0] for t in ('scheduled', 'reactive', 'solo')}
    for d in CYC:
        A = ACT[d['cid']]; base = preds(d, solo_on=False); sp = solo_pred(d, variant); Pd = pd.concat([base, sp], ignore_index=True)
        for key, Aa in (('all', A), ('excl_deep', A[A.typ != 'deep-OTM batch'])):
            m = match(Aa.reset_index(drop=True), Pd.reset_index(drop=True), 1); agg[key][0] += len(m); agg[key][1] += len(Pd); agg[key][2] += len(Aa)
        for t in ('scheduled', 'reactive', 'solo'):
            Aa = A[A.typ == t].reset_index(drop=True); Pp = Pd[Pd.typ == t].reset_index(drop=True); m = match(Aa, Pp, 1); per[t][0] += len(m); per[t][1] += len(Pp); per[t][2] += len(Aa)
    for key, (tp, nf, na) in agg.items(): rows.append(dict(solo_variant=lab, scope='all D-1 sold lots' if key == 'all' else 'excluding deep-OTM batch sells', real_lots=na, model_lots=nf, matched=tp, precision=tp / nf, recall=tp / na, F1=2 * tp / (nf + na)))
    for t, (tp, nf, na) in per.items(): trows.append(dict(solo_variant=lab, sell_type=t, real_lots=na, model_lots=nf, matched=tp, precision=tp / max(nf, 1), recall=tp / max(na, 1), F1=2 * tp / max(nf + na, 1)))
C = pd.DataFrame(rows); T = pd.DataFrame(trows); C.round(4).to_csv(f'{OUT}/bl_all2_combined.csv', index=False); T.round(4).to_csv(f'{OUT}/bl_all2_type.csv', index=False); print(C.round(3).to_string(index=False)); print(T.round(3).to_string(index=False))
tot = sum(len(a) for a in ACT.values()); R['shares'] = {t: sum(int((a.typ == t).sum()) for a in ACT.values()) / tot for t in ('scheduled', 'reactive', 'solo', 'deep-OTM batch')}; R['deep_cycles'] = int(sum(int((a.typ == 'deep-OTM batch').any()) for a in ACT.values())); print(R); R['combined'] = C.round(4).to_dict('records'); R['by_type'] = T.round(4).to_dict('records'); rec('all3', R)
