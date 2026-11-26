"""D0 chunk 1, addendum 1b (plan reports/D0_SELLS_PLAN.md): D0 pair timetable per (underlying, version), learned on one cycle half (cid parity) and scored on the other.
Wave discovery: greedy over pair-start seconds of active training cycles (before their first s_ order); a wave needs >= 50% of active cycles within +-3 s.
Prediction: each wave before the real stop time -> 1 CE + 1 PE x wave lots at the strike nearest the previous minute's close. Scored on all pair lots and grid-pair lots (+-1 min).
T2b: the D-1 breakout machine vs pair minutes the timetable does not explain, with the T2 placebos.
Outputs bl_d0s_waves.csv (waves learned on all cycles, descriptive), bl_d0s_waves_fold.pkl.gz, bl_d0s_tt.csv, bl_summary_d0s2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_d0s_tests.py').read(); exec(src[:src.index('# ---------------- T1 slot clock')])
exec(src[src.index('def fires(d):'):src.index("OG = S[(S.lab == 'offgrid_pair')]")])
STOP = {}
for i in D0C:
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 's_')]; STOP[i] = float(z.tod.min()) if len(z) else 1e9
PS = S[S.pid >= 0].groupby(['cid', 'pid']).agg(t0=('tod', 'min'), lots=('lots', 'min'), lab=('lab', 'first'), j=('j', 'min')).reset_index()
GRP = lambda i: (CY.iloc[i].und, CY.iloc[i].version)
def waves(train):
    out = []
    for g in sorted({GRP(i) for i in train}):
        tc = [i for i in train if GRP(i) == g]; pool = {i: sorted(PS[PS.cid == i].t0.tolist()) for i in tc}; lots = {i: dict(zip(PS[PS.cid == i].t0, PS[PS.cid == i].lots)) for i in tc}
        while True:
            allt = sorted({round(t) for i in tc for t in pool[i]}); best = None
            for t in allt:
                act = [i for i in tc if STOP[i] > t]
                if not act: continue
                hits = {i: min(pool[i], key=lambda x: abs(x - t)) for i in act if pool[i] and min(abs(x - t) for x in pool[i]) <= 3}
                sh = len(hits) / len(act)
                if best is None or (len(hits), sh) > (len(best[1]), best[2]): best = (t, hits, sh)
            if best is None or best[2] < 0.5 or len(best[1]) < 2: break
            t, hits, sh = best
            for i, x in hits.items(): pool[i].remove(x)
            out.append(dict(und=g[0], version=g[1], t=float(np.median(list(hits.values()))), share=sh, cycles=len(hits), lots=int(max(1, round(np.median([lots[i][x] for i, x in hits.items()]))))))
    return pd.DataFrame(out)
WALL = waves(D0C); WALL['clock'] = [f'{int(t // 3600):02d}:{int(t // 60 % 60):02d}:{int(t % 60):02d}' for t in WALL.t]; WALL.sort_values(['und', 'version', 't']).to_csv(f'{OUT}/bl_d0s_waves.csv', index=False)
R = dict(waves_all=WALL.groupby(['und', 'version']).size().to_dict(), cycles_per_group=pd.Series([GRP(i) for i in D0C]).value_counts().to_dict())
WF = {}; per = []; per_g = []; sk = [0, 0]; expl = set()
for half in (0, 1):
    tr = [i for i in D0C if i % 2 != half]; te = [i for i in D0C if i % 2 == half]; Wt = waves(tr); WF[half] = Wt
    for i in te:
        w = Wt[(Wt.und == CY.iloc[i].und) & (Wt.version == CY.iloc[i].version) & (Wt.t < STOP[i])]; c = M[i]['c']
        pj = []; pk = []
        for x in w.itertuples(): j = int((x.t - 33300) // 60); pj += [j] * x.lots; pk += [atm(i, c[max(j - 1, 0)])] * x.lots
        for cp in ('CE', 'PE'):
            g = S[(S.cid == i) & (S.cp == cp) & (S.pid >= 0)]; a = np.repeat(g.j.values, g.lots.values); per.append((match1(a, pj), len(pj), len(a)))
            gg = g[g.lab == 'grid_pair']; per_g.append((match1(np.repeat(gg.j.values, gg.lots.values), pj), len(pj), int(gg.lots.sum())))
            for jj, kk in zip(pj, pk):
                h = g[(g.j - jj).abs() <= 1]
                if len(h): sk[0] += 1; sk[1] += int((h.strike == kk).any())
        for x in PS[PS.cid == i].itertuples():
            if len(w) and np.min(np.abs(w.t.values - x.t0)) <= 3: expl.add((i, x.pid))
pd.to_pickle(WF, f'{OUT}/bl_d0s_waves_fold.pkl.gz'); rows = []
f, lo, hi = boot(per); a = np.array(per); rows.append(dict(test='T1b timetable (OOF) vs all pair lots', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / a[:, 1].sum(), recall=a[:, 0].sum() / a[:, 2].sum(), real_lots=int(a[:, 2].sum()), sim_lots=int(a[:, 1].sum())))
f, lo, hi = boot(per_g); a = np.array(per_g); rows.append(dict(test='T1b timetable (OOF) vs grid-pair lots only', F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / a[:, 1].sum(), recall=a[:, 0].sum() / a[:, 2].sum(), real_lots=int(a[:, 2].sum()), sim_lots=int(a[:, 1].sum())))
R['t1b_strike_exact'] = sk[1] / max(sk[0], 1); PS['explained'] = [(i, p) in expl for i, p in zip(PS.cid, PS.pid)]
R['t1b_pairs_explained_share'] = float(PS[PS.cid.isin(D0C)].explained.mean()); R['t1b_pairs_explained_by_label'] = PS[PS.cid.isin(D0C)].groupby('lab').explained.mean().round(3).to_dict()
RES = PS[~PS.explained & PS.cid.isin(D0C)]; R['t2b_residual_pairs'] = int(len(RES)); R['t2b_residual_by_hour'] = RES.assign(h=(RES.t0 // 3600).astype(int)).groupby('h').size().to_dict()
def _prior(i, t): b = B[(B.cid == i) & (B.tod > t - 60) & (B.tod <= t)]; return len(b) > 0
R['t2b_residual_with_bb_60s_before'] = float(np.mean([_prior(i, t) for i, t in zip(RES.cid, RES.t0)])); EXP = PS[PS.explained & PS.cid.isin(D0C)]; R['t1b_explained_with_bb_60s_before'] = float(np.mean([_prior(i, t) for i, t in zip(EXP.cid, EXP.t0)]))
R['t2b_residual_before_1000'] = int((RES.t0 < 36000).sum()); R['t2b_residual_0915_0918'] = int((RES.t0 < 33480).sum())
def t2b(shift=0, perm=False):
    per = []
    for n, i in enumerate(D0C):
        srcc = D0C[(n + 1) % len(D0C)] if perm else i; F = [j + shift for j, _ in fires(M[srcc]) if 33300 + 60 * j < STOP[i]]
        A = np.unique(RES[(RES.cid == i) & (RES.j >= 75) & (RES.j <= 360)].j.values); per.append((match1(A, F), len(F), len(A)))
    return per
for nm, kw in (('T2b breakout machine vs residual pair minutes 10:30-15:15', {}), ('T2b placebo: cycle-permuted spot', dict(perm=True)), ('T2b placebo: fires +15 min', dict(shift=15))):
    pp = t2b(**kw); f, lo, hi = boot(pp); a = np.array(pp); rows.append(dict(test=nm, F1=f, ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / max(a[:, 2].sum(), 1), real_lots=int(a[:, 2].sum()), sim_lots=int(a[:, 1].sum())))
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/bl_d0s_tt.csv', index=False); print(T.round(3).to_string(index=False)); print(WALL.groupby(['und', 'version']).agg(waves=('t', 'size'), lots=('lots', 'sum'), share_med=('share', 'median')).to_string())
rec('d0s2', R); print(R)
