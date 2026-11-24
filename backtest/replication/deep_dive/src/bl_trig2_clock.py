"""Late-sale trigger investigation, part 3: clock-level tests (plan addendum in reports/LATE_SALE_TRIGGER_PLAN.md, written BEFORE this script ran). EXPLORATORY.
S5  minute concentration: sum of squared minute counts of event starts across cycles vs circular-shift null (a timer or a published-time reaction concentrates events in the same minutes on different days).
S1b second-level coincidence conditional on the minute: pairs of events from different cycles in the SAME minute with |second difference| <= 3, vs null that redraws each event's second uniformly inside its minute (keeps the minute profile).
S6  exchange-timetable minutes {15:15 freeze, 15:20 first indicative, 15:29 official close} share vs circular-shift null.
X1  (contemporaneous = through the minute of the sale, NOT causal; *_l = strictly before the minute) published-index discontinuity: per minute 15:15-15:39 d_j = |dFEED_j - dFUT_j| / median |dFUT| ; stratified AUC (within cycle) of d_j for 'any late sale in minute j' vs circular-shift null of the sale minutes inside the cycle.
X2  direction at index minutes: at minutes with a sale, sign of the published-index move over the last 5 min vs side (CE after up, PE after down), FEED vs FUT.
Output outputs/trig2/tests_part3.json, clock_minutes.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S
OUT = S.OUT; T2 = f'{OUT}/trig2'; W0, W1 = 54900, 56400; RNG = np.random.default_rng(20261127); NS = 5000; J0, J1 = 360, 384
def run():
    E = pd.read_csv(f'{T2}/events.csv'); E = E[(E.era == 'after') & (E.outlier == 0)].copy(); E['m'] = (E.t0 // 60 - 915).astype(int); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; cycs = sorted(set(E.cyc)); res = {}; nm = J1 - J0 + 1
    # minute index of event start: j = t0//60 - 555  (09:15 = 555 min), j in 360..384
    E['j'] = (E.t0 // 60 - 555).astype(int); cj = {c: E[E.cyc == c].j.values for c in cycs}
    def counts(jl): return np.bincount(np.concatenate([np.asarray(v) - J0 for v in jl]).astype(int), minlength=nm)[:nm]
    def circ(j, u): return J0 + ((np.asarray(j) - J0 + u) % nm)
    obs = counts(cj.values()); ss0 = int((obs ** 2).sum()); nul = []
    for _ in range(NS): nul.append(int((counts([circ(cj[c], RNG.integers(0, nm)) for c in cycs]) ** 2).sum()))
    nul = np.array(nul); res['S5'] = dict(sumsq=ss0, null_mean=float(nul.mean()), null_sd=float(nul.std()), p=float((1 + (nul >= ss0).sum()) / (NS + 1)), top_minutes={f'{(555 + J0 + i) // 60:02d}:{(555 + J0 + i) % 60:02d}': int(v) for i, v in sorted(enumerate(obs), key=lambda z: -z[1])[:8]})
    # S6 timetable minutes: 15:15 (j=360), 15:20 (365), 15:29 (374)
    TT = {360, 365, 374}; k6 = int(sum(((np.isin(cj[c], list(TT))).sum()) for c in cycs)); n6 = len(E); n6s = []
    for _ in range(NS): n6s.append(int(sum(np.isin(circ(cj[c], RNG.integers(0, nm)), list(TT)).sum() for c in cycs)))
    n6s = np.array(n6s); res['S6'] = dict(events_in_15_15_15_20_15_29=k6, of=n6, share=k6 / n6, null_share_mean=float(n6s.mean() / n6), p=float((1 + (n6s >= k6).sum()) / (NS + 1)), note='minutes chosen from the exchange timetable AFTER seeing the event-minute histogram: exploratory')
    # S1b second-level, conditional on minute
    t = E.t0.values; mj = E.j.values; cc = pd.Categorical(E.cyc).codes
    def c1b(sec):
        d = (np.abs(sec[:, None] - sec[None, :]) <= 3) & (mj[:, None] == mj[None, :]) & (cc[:, None] != cc[None, :]); return int(d.sum() // 2)
    s0 = c1b(t % 60); same_min_pairs = int(((mj[:, None] == mj[None, :]) & (cc[:, None] != cc[None, :])).sum() // 2); nl = np.array([c1b(RNG.uniform(0, 60, len(t))) for _ in range(NS)])
    res['S1b'] = dict(pairs_same_minute_diff_cycle=same_min_pairs, coincident_within_3s=s0, null_mean=float(nl.mean()), p=float((1 + (nl >= s0).sum()) / (NS + 1)))
    # X1/X2 published-index discontinuity
    rows = []
    for c in cycs:
        u, d1 = c.split('|'); r = Tc[(Tc.und == u) & (Tc.d1 == d1)].iloc[0]; fx = pd.read_pickle(f'{OUT}/bt3x/{u}_{r.expiry}.pkl.gz')['spot1'].close.values.astype(float); fu = pd.read_pickle(f'{OUT}/bt3u/{u}_{r.expiry}.pkl.gz')['spot1'].close.values.astype(float)
        dF = np.diff(fx, prepend=np.nan); dU = np.diff(fu, prepend=np.nan); sc = np.nanmedian(np.abs(dU[300:360])) + 1e-9; sold = {j: set() for j in range(J0, J1 + 1)}
        late = pd.read_csv(f'{T2}/events.csv'); late = None
        for e in E[E.cyc == c].itertuples(): sold[e.j].add('CE' if e.ce_lots > 0 else '') ; sold[e.j].add('PE' if e.pe_lots > 0 else '')
        for j in range(J0, J1 + 1):
            rows.append(dict(cyc=c, und=u, j=j, d=abs(dF[j] - dU[j]) / sc, d_feed=abs(dF[j]) / sc, d_fut=abs(dU[j]) / sc, y=int(E[(E.cyc == c)].j.eq(j).any()), up5_feed=fx[j] - fx[j - 5], up5_fut=fu[j] - fu[j - 5], d_l=abs(dF[j - 1] - dU[j - 1]) / sc, d_feed_l=abs(dF[j - 1]) / sc, d_fut_l=abs(dU[j - 1]) / sc, up5_feed_l=fx[j - 1] - fx[j - 6], up5_fut_l=fu[j - 1] - fu[j - 6], ce=int(any(x == 'CE' for x in sold[j])), pe=int(any(x == 'PE' for x in sold[j]))))
    M = pd.DataFrame(rows); M.to_csv(f'{T2}/clock_minutes.csv', index=False)
    def auc_strat(df, col, ycol='y'):
        a = []; w = []
        for c, g in df.groupby('cyc'):
            p = g[g[ycol] == 1][col].dropna().values; n = g[g[ycol] == 0][col].dropna().values
            if len(p) and len(n): a.append(float(((p[:, None] > n[None, :]).sum() + .5 * (p[:, None] == n[None, :]).sum()) / (len(p) * len(n)))); w.append(len(p) * len(n))
        return float(np.average(a, weights=w)), len(a)
    for col in ('d', 'd_feed', 'd_fut', 'd_l', 'd_feed_l', 'd_fut_l'):
        a0, nc = auc_strat(M, col); nl = []
        for _ in range(2000):
            Mn = M.copy(); Mn['y'] = np.concatenate([np.roll(g.y.values, RNG.integers(0, nm)) for _, g in Mn.groupby('cyc', sort=False)]); nl.append(auc_strat(Mn, col)[0])
        nl = np.array(nl); res[f'X1_{col}'] = dict(auc=a0, cycles=nc, null_mean=float(nl.mean()), null_sd=float(nl.std()), p_two_sided=float(min(1, 2 * min((nl >= a0).mean(), (nl <= a0).mean()) + 1 / 2001)))
    # X2 direction: CE sale after up-move, PE sale after down-move, minutes with exactly one side
    for nm_, col in (('feed', 'up5_feed'), ('fut', 'up5_fut'), ('feed_lag1', 'up5_feed_l'), ('fut_lag1', 'up5_fut_l')):
        x = M[(M.ce + M.pe == 1)]; ag = np.where(x.ce == 1, np.sign(x[col]), -np.sign(x[col])); ag = ag[np.isfinite(ag) & (ag != 0)]; k = int((ag > 0).sum()); from scipy.stats import binomtest
        res[f'X2_{nm_}'] = dict(solo_side_minutes=int(len(ag)), share_CE_after_up_or_PE_after_down=k / len(ag), p=float(binomtest(k, len(ag), .5).pvalue))
    json.dump(res, open(f'{T2}/tests_part3.json', 'w'), indent=1, default=float)
    for k, v in res.items(): print(k, json.dumps(v, default=lambda z: round(float(z), 4)))
if __name__ == '__main__': run()
