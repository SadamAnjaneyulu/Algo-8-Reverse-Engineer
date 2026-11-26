"""Late-sale trigger investigation, part 1 (plan: reports/LATE_SALE_TRIGGER_PLAN.md). EXPLORATORY. Events, scheduled-pair tests (S1-S4), pair-process tests (P1, P2, P3a, P4), premium and lump timing (R2, R3),
execution descriptives (E1, E2), event labelling with chance coverage. Output outputs/trig2/events.csv, tests_part1.json"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy.stats import binomtest, chisquare, ks_2samp, spearmanr, linregress
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; T2 = f'{OUT}/trig2'; os.makedirs(T2, exist_ok=True); W0, W1 = 54900, 56400; W = W1 - W0; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); RNG = np.random.default_rng(20261126); NS = 5000; GAP = 10; BASE = 33360
def cluster(times, sides):
    """times sorted ascending; returns list of (indices) clusters with gaps <= GAP"""
    ev = []; cur = []
    for i in range(len(times)):
        if cur and times[i] - times[i - 1] > GAP: ev.append(cur); cur = []
        cur.append(i)
    if cur: ev.append(cur)
    return ev
def pair_count(ce, pe):
    t = np.r_[ce, pe]; s = np.r_[np.zeros(len(ce)), np.ones(len(pe))]; o = np.argsort(t, kind='stable'); t, s = t[o], s[o]; ev = cluster(t, s)
    return sum(1 for e in ev if len(set(s[e])) == 2), len(ev)
def shift(t, u): return W0 + ((np.asarray(t) - W0 + u) % W)
def rayleigh(t, P):
    ph = 2 * np.pi * (((np.asarray(t) - BASE) % P) / P); n = len(ph); R = abs(np.exp(1j * ph).mean()); z = n * R * R; return float(R), float(min(1.0, np.exp(-z) * (1 + (2 * z - z * z) / (4 * n))))
def run():
    O = DG.real_orders(); O = O.assign(jj=(O.t_first // 60 - 555).astype(int)); Tc = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); Tc = Tc[Tc.ok]; Bk = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(Bk.und, Bk.expiry)); events = []; per = {}
    for r in Tc.itertuples():
        if (r.und, r.expiry) not in keep: continue
        g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0)].sort_values(['t_first', 'row']).reset_index(drop=True)
        if not len(g): continue
        cyc = f'{r.und}|{r.d1}'; post = r.d0 >= CAS; unit = float(r.unit); sells = g[g.role == 'open_short']; late = sells[(sells.t_first >= W0) & (sells.t_first < W1)]; covers = g[g.role == 'cover_short']; lump = g[(g.module == 'v_') & (g.role == 'open_long')]
        # pair ledger over the whole day (FIFO unmatched queues)
        qC = qP = 0; comp = {}; qs = {}
        for i, q in sells.iterrows():
            if q.cp == 'CE':
                comp[i] = qP > 0; qs[i] = (qC, qP)
                if qP > 0: qP -= int(q.lots)
                else: qC += int(q.lots)
            else:
                comp[i] = qC > 0; qs[i] = (qC, qP)
                if qC > 0: qC -= int(q.lots)
                else: qP += int(q.lots)
            qC, qP = max(qC, 0), max(qP, 0)
        per[cyc] = dict(und=r.und, d1=r.d1, post=post, outlier=(r.und, r.d1) == OUTLIER, unit=unit, late=late, sells=sells, covers=covers, lump_t=float(lump.t_first.min()) if len(lump) else np.nan, comp=comp, qs=qs,
                        pre_prem=float((sells[sells.t_first < W0].lots * sells[sells.t_first < W0].px_avg).sum() * unit), late_prem=float((late.lots * late.px_avg).sum() * unit))
        if len(late):
            t = late.t_first.values; s = (late.cp == 'PE').values.astype(int); idx = np.arange(len(late))
            for e in cluster(t, s):
                x = late.iloc[e]; ce = x[x.cp == 'CE']; pe = x[x.cp == 'PE']
                events.append(dict(cyc=cyc, und=r.und, d1=r.d1, era='after' if post else 'before', outlier=int((r.und, r.d1) == OUTLIER), t0=float(x.t_first.min()), t1=float(x.t_first.max()), n=len(x), ce_lots=int(ce.lots.sum()), pe_lots=int(pe.lots.sum()), type='pair' if len(ce) and len(pe) else 'solo',
                                   same_strike=int(x.strike.nunique() == 1), interleg_gap=float(abs(ce.t_first.min() - pe.t_first.min())) if len(ce) and len(pe) else np.nan, med_off=float(x.off_prev.median()), idx=list(x.index), completes=int(any(comp[i] for i in x.index)), first_lim_ratio=float((x.lim_px / x.px_first).median())))
    E = pd.DataFrame(events); P = E[(E.era == 'after') & (E.outlier == 0)].copy(); res = {}; cycs = sorted(set(P.cyc))
    res['events'] = dict(post_events=int(len(P)), post_cycles=len(cycs), pair=int((P.type == 'pair').sum()), solo=int((P.type == 'solo').sum()), orders_per_event=P.n.describe().round(2).to_dict(), pre_events=int(((E.era == 'before') & (E.outlier == 0)).sum()))
    # ---------------- S1 cross-cycle coincidence
    tt = P.t0.values; cc = pd.Categorical(P.cyc).codes
    def coinc(t, c):
        d = np.abs(t[:, None] - t[None, :]) <= 3; m = c[:, None] != c[None, :]; return int((d & m).sum() // 2), int(max(len(set(c[np.abs(t - x) <= 3])) for x in t))
    C0, K0 = coinc(tt, cc); nullC = []; nullK = []
    for _ in range(NS):
        u = RNG.uniform(0, W, len(cycs)); a, b = coinc(shift(tt, u[cc]), cc); nullC.append(a); nullK.append(b)
    nullC, nullK = np.array(nullC), np.array(nullK); res['S1'] = dict(coincident_pairs=C0, null_mean=float(nullC.mean()), null_sd=float(nullC.std()), p=float((1 + (nullC >= C0).sum()) / (NS + 1)), peak_cycles_same_3s=K0, null_peak_mean=float(nullK.mean()), p_peak=float((1 + (nullK >= K0).sum()) / (NS + 1)))
    # ---------------- S2 second of minute; S3 candle end; S4 phase
    sec = P.t0.values % 60; k = int((sec <= 5).sum()); n = len(P); res['S2'] = dict(share_0_5s=k / n, expected=0.1, p=float(binomtest(k, n, 0.1).pvalue), chi2_p=float(chisquare(np.histogram(sec, bins=np.arange(0, 70, 10))[0]).pvalue), bins=np.histogram(sec, bins=np.arange(0, 70, 10))[0].tolist(),
                  pairs_share_0_5s=float((P[P.type == 'pair'].t0 % 60 <= 5).mean()), solos_share_0_5s=float((P[P.type == 'solo'].t0 % 60 <= 5).mean()))
    def shift_null(stat, nd=NS):
        out = []
        for _ in range(nd): u = RNG.uniform(0, W, len(cycs)); out.append(stat(shift(tt, u[cc])))
        return np.array(out)
    inwin = lambda t: int(((t >= 55740) & (t <= 55860)).sum()); k3 = inwin(tt); n3 = shift_null(inwin); res['S3'] = dict(share_candle_end=k3 / n, null_share_mean=float(n3.mean() / n), n=k3, null_n_mean=float(n3.mean()), p=float((1 + (n3 >= k3).sum()) / (NS + 1)), note='circular-shift null (respects the clock profile)')
    res['S4'] = {}
    for Pd in (300, 900, 1800):
        R0 = rayleigh(tt, Pd)[0]; nr = shift_null(lambda t: rayleigh(t, Pd)[0], 2000); res['S4'][str(Pd)] = dict(R=R0, null_R_mean=float(nr.mean()), p=float((1 + (nr >= R0).sum()) / 2001))
    # ---------------- P1 pair share vs null, P2 anatomy
    obs_pairs = 0; obs_ev = 0; ce_t = {}; pe_t = {}
    for c in cycs:
        late = per[c]['late']; ce_t[c] = late[late.cp == 'CE'].t_first.values.astype(float); pe_t[c] = late[late.cp == 'PE'].t_first.values.astype(float); a, b = pair_count(ce_t[c], pe_t[c]); obs_pairs += a; obs_ev += b
    nullp = []; nulls = []
    for _ in range(NS):
        tp = 0; te = 0
        for c in cycs: a, b = pair_count(ce_t[c], shift(pe_t[c], RNG.uniform(0, W))); tp += a; te += b
        nullp.append(tp); nulls.append(tp / te)
    res['P1'] = dict(pair_events=obs_pairs, events=obs_ev, share=obs_pairs / obs_ev, null_share_mean=float(np.mean(nulls)), null_share_sd=float(np.std(nulls)), excess=float(obs_pairs / obs_ev - np.mean(nulls)), p=float((1 + (np.array(nulls) >= obs_pairs / obs_ev).sum()) / (NS + 1)))
    pr = P[P.type == 'pair']; res['P2'] = dict(pair_events=len(pr), equal_lots_each_leg=float((pr.ce_lots == pr.pe_lots).mean()), same_strike=float(pr.same_strike.mean()), interleg_gap_s=pr.interleg_gap.describe().round(1).to_dict(), lots_per_leg=pr.ce_lots.describe().round(1).to_dict(), solo_orders=P[P.type == 'solo'].n.describe().round(1).to_dict())
    # ---------------- P3a completion (order level; own/mirror expectation), P4 replacement
    rows = []
    for c in cycs:
        pc = per[c]; late = pc['late']; own = late.cp.map(late.cp.value_counts(normalize=True))
        for i, q in late.iterrows():
            qC, qP = pc['qs'][i]; fa = float(pc['comp'][i]); fm = float((qC > 0) if q.cp == 'CE' else (qP > 0))     # mirror: the opposite-side order completes if ITS opposite queue is non-empty
            rows.append(dict(cyc=c, i=i, cp=q.cp, t=float(q.t_first), own=float(own[i]), fa=fa, fm=fm, solo=int(E.loc[E.idx.map(lambda z: i in z), 'type'].iloc[0] == 'solo')))
    L = pd.DataFrame(rows); L['exp'] = L.own * L.fa + (1 - L.own) * L.fm
    def boot_excess(df):
        cy = sorted(set(df.cyc)); bs = []
        for _ in range(4000):
            d = RNG.integers(0, len(cy), len(cy)); x = pd.concat([df[df.cyc == cy[i]] for i in d]); bs.append(float((x.fa - x.exp).mean()))
        bs = np.array(bs); return float((df.fa - df.exp).mean()), [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], float(max(2 * min((bs <= 0).mean(), (bs >= 0).mean()), 1 / 4000))
    for nm, df in (('P3a_all', L), ('P3a_solo_events_only', L[L.solo == 1])):
        e, ci, p = boot_excess(df); res[nm] = dict(orders=int(len(df)), observed=float(df.fa.mean()), expected=float(df.exp.mean()), excess=e, ci=ci, p=p)
    day0, day1 = 9 * 3600 + 15 * 60, W1
    def p4hits(c, u):
        pc = per[c]; late = pc['late']; covs = pc['covers']; h = 0
        for cp in ('CE', 'PE'):
            ct = np.sort(day0 + ((covs[covs.cp == cp].t_first.values.astype(float) - day0 + u) % (day1 - day0))); lt = late[late.cp == cp].t_first.values.astype(float)
            h += int((np.searchsorted(ct, lt, side='left') - np.searchsorted(ct, lt - 600, side='left') > 0).sum())
        return h
    tot = sum(len(per[c]['late']) for c in cycs); hit = sum(p4hits(c, 0.0) for c in cycs); nullh = [sum(p4hits(c, RNG.uniform(0, day1 - day0)) for c in cycs) / tot for _ in range(2000)]
    res['P4'] = dict(orders=tot, share=hit / tot, null_mean=float(np.mean(nullh)), excess=float(hit / tot - np.mean(nullh)), p=float((1 + (np.array(nullh) >= hit / tot).sum()) / 2001))
    # ---------------- R2 premium target, R3 lump timing
    R = pd.DataFrame([dict(cyc=c, und=per[c]['und'], pre=per[c]['pre_prem'], late=per[c]['late_prem']) for c in cycs]); R['pre_n'] = R.pre / R.groupby('und').pre.transform('median'); R['late_n'] = R.late / R.groupby('und').pre.transform('median')
    lr = linregress(R.pre_n, R.late_n); sp = spearmanr(R.pre_n, R.late_n); res['R2'] = dict(cycles=len(R), slope=float(lr.slope), slope_se=float(lr.stderr), r2=float(lr.rvalue ** 2), spearman=float(sp.statistic), spearman_p=float(sp.pvalue), target_would_give_slope=-1.0, cv_pre=float(R.pre_n.std() / R.pre_n.mean()), cv_total=float((R.pre_n + R.late_n).std() / (R.pre_n + R.late_n).mean()))
    lump_c = [c for c in cycs if not np.isnan(per[c]['lump_t'])]; ev_by = {c: P[P.cyc == c].t0.values for c in lump_c}; k4 = sum(int(((per[c]['lump_t'] - ev_by[c] >= 0) & (per[c]['lump_t'] - ev_by[c] <= 120)).sum()) for c in lump_c); n4 = sum(len(ev_by[c]) for c in lump_c); nl = []
    for _ in range(NS):
        h = 0
        for c in lump_c: d = per[c]['lump_t'] - shift(ev_by[c], RNG.uniform(0, W)); h += int(((d >= 0) & (d <= 120)).sum())
        nl.append(h / n4)
    res['R3'] = dict(events=n4, cycles_with_lump=len(lump_c), share_within_120s_before_lump=k4 / n4, null_mean=float(np.mean(nl)), excess=float(k4 / n4 - np.mean(nl)), p=float((1 + (np.array(nl) >= k4 / n4).sum()) / (NS + 1)), events_before_lump=float(np.mean([int((ev_by[c] < per[c]['lump_t']).sum()) for c in lump_c]) ))
    # ---------------- E1 / E2 execution descriptives
    gap = [];
    for c in cycs:
        late = per[c]['late']; t = late.t_first.values
        for e in cluster(t, None): gap += list(np.diff(t[e]))
    res['E1'] = dict(orders_per_event=P.n.value_counts().sort_index().to_dict(), inter_order_gap_s=pd.Series(gap).describe().round(2).to_dict(), single_order_events=float((P.n == 1).mean()))
    lim_late = np.concatenate([(per[c]['late'].lim_px / per[c]['late'].px_first).values for c in cycs]); lim_early = np.concatenate([(per[c]['sells'][per[c]['sells'].t_first < 14 * 3600].lim_px / per[c]['sells'][per[c]['sells'].t_first < 14 * 3600].px_first).values for c in cycs])
    res['E2'] = dict(limit_over_fill_late=dict(zip(('p10', 'median', 'p90'), [float(np.quantile(lim_late, q)) for q in (.1, .5, .9)])), limit_over_fill_early=dict(zip(('p10', 'median', 'p90'), [float(np.quantile(lim_early, q)) for q in (.1, .5, .9)])), ks_p=float(ks_2samp(lim_late, lim_early).pvalue))
    # ---------------- labels with chance coverage (post-auction events)
    fires = {}
    for c in cycs:
        pc = per[c]; ev = {cp: sorted(set(pc['sells'][pc['sells'].cp == cp].jj.tolist())) for cp in ('CE', 'PE')}; fut = pd.read_pickle(f'{OUT}/bt3u/{pc["und"]}_{pc["und"] and cycle_expiry(c, Tc)}.pkl.gz')['spot1']; h, l, cl = (fut[k].values.astype(float) for k in ('high', 'low', 'close')); cfg = A.Config(); cfg.ladder_gate_min = 5; cfg.strike_step = 50.0 if pc['und'] == 'NIFTY' else 100.0
        fires[c] = {(j, cp) for j, cps in A.ladder_fires(cl, h, l, ev, cfg).items() for cp in cps}
    def labels(c, ev_rows, shift_u=0.0):
        pc = per[c]; out = []
        for e in ev_rows.itertuples():
            lab = set(); t0 = shift(e.t0, shift_u) if shift_u else e.t0; od = pc['late'].loc[e.idx]
            if e.type == 'pair': lab.add('PAIR')
            if e.type == 'solo' and e.completes: lab.add('COMPLETION')
            tt_ = od.t_first.values + (t0 - e.t0)
            if any(((pc['covers'][pc['covers'].cp == q.cp].t_first.values < tt_[k_]) & (pc['covers'][pc['covers'].cp == q.cp].t_first.values >= tt_[k_] - 600)).any() for k_, (_, q) in enumerate(od.iterrows())): lab.add('REPLACEMENT')
            if not np.isnan(pc['lump_t']) and 0 <= pc['lump_t'] - t0 <= 120: lab.add('LUMP-COUPLED')
            m = int((t0 - BASE) // 60) % 15
            if m in (0, 14): lab.add('GRID')
            jj = (tt_ // 60 - 555).astype(int)
            if any(any(((int(j_) + d, q.cp) in fires[c]) for d in (-1, 0, 1)) for j_, (_, q) in zip(jj, od.iterrows())): lab.add('LADDER')
            out.append(lab)
        return out
    names = ['PAIR', 'COMPLETION', 'REPLACEMENT', 'LUMP-COUPLED', 'GRID', 'LADDER']; obs_lab = {}; cnt = {k: 0 for k in names}; anyc = 0
    for c in cycs:
        ev = P[P.cyc == c]; lbs = labels(c, ev); obs_lab[c] = lbs
        for lb in lbs:
            for k in lb: cnt[k] += 1
            anyc += int(len(lb) > 0)
    nullcnt = {k: [] for k in names}; nullany = []
    for _ in range(200):
        cn = {k: 0 for k in names}; an = 0
        for c in cycs:
            ev = P[P.cyc == c]; lbs = labels(c, ev, RNG.uniform(0, W))
            for lb in lbs:
                for k in lb: cn[k] += 1
                an += int(len(lb) > 0)
        for k in names: nullcnt[k].append(cn[k] / len(P))
        nullany.append(an / len(P))
    res['coverage_raw_shifted'] = {k: dict(observed=cnt[k] / len(P), chance_when_time_shifted=float(np.mean(nullcnt[k])), excess=float(cnt[k] / len(P) - np.mean(nullcnt[k]))) for k in names}; res['coverage_raw_shifted']['ANY'] = dict(observed=anyc / len(P), chance_when_time_shifted=float(np.mean(nullany)), excess=float(anyc / len(P) - np.mean(nullany)))
    # PAIR chance = P1 null share; COMPLETION chance = P3a own/mirror expectation at event level (1 - prod(1-exp) over the solo event's orders); other labels: shifted-time coverage
    cov = {k: dict(res['coverage_raw_shifted'][k]) for k in res['coverage_raw_shifted']}
    cov['PAIR']['chance_when_time_shifted'] = res['P1']['null_share_mean']; cov['PAIR']['excess'] = cov['PAIR']['observed'] - cov['PAIR']['chance_when_time_shifted']; cov['PAIR']['chance_method'] = 'P1 null (independent shift of the PE leg)'
    ce = []
    for e in P.itertuples():
        if e.type == 'solo': ee = L[(L.cyc == e.cyc) & L.i.isin(e.idx)].exp.values; ce.append(float(1 - np.prod(1 - ee)))
        else: ce.append(0.0)
    cov['COMPLETION']['chance_when_time_shifted'] = float(np.mean(ce)); cov['COMPLETION']['excess'] = cov['COMPLETION']['observed'] - float(np.mean(ce)); cov['COMPLETION']['chance_method'] = 'P3a own/mirror expectation (approximate)'
    res['coverage'] = cov
    P['labels'] = ['+'.join(sorted(lb)) if lb else 'unexplained' for c in cycs for lb in obs_lab[c]] if False else None
    lab_rows = {}
    for c in cycs:
        for (ix, e), lb in zip(P[P.cyc == c].iterrows(), obs_lab[c]): lab_rows[ix] = '+'.join(sorted(lb)) if lb else 'unexplained'
    P['labels'] = pd.Series(lab_rows); P.drop(columns=['idx']).to_csv(f'{T2}/events.csv', index=False); json.dump(res, open(f'{T2}/tests_part1.json', 'w'), indent=1, default=float)
    for k, v in res.items(): print(k, json.dumps(v, default=lambda z: round(float(z), 4))[:700])
def cycle_expiry(cyc, Tc):
    u, d1 = cyc.split('|'); return Tc[(Tc.und == u) & (Tc.d1 == d1)].expiry.iloc[0]
if __name__ == '__main__': run()
