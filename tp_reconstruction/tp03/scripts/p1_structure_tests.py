"""TP-03 Phase 1: E3 (ladder permutation), E5 (strike), E6 (wing selector), E7 (wing quantity), E8 (re-entry). Operational form: tp03/PHASE1_TEST_SPEC.md section 3.
Every p-value is the registered sequential permutation p (seqperm.run_test, per-test seed). Run: ALGO8_MARKET_DIR=... python3 tp_reconstruction/tp03/scripts/p1_structure_tests.py"""
import os, sys, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec, seqperm
tc.assert_frozen(); CFG = tc.CFG; PARAMS = CFG['inference']['permutations']['parameters']; SEED = CFG['inference']['seed']; A = tc.ANALYSIS; STEP = ec.STEP; BASE = ec.BASE
W = pd.read_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet')); D = ec.Data(); LOG = []


def run(test_id, observed, draw, extra=None):
    r = seqperm.run_test(test_id, observed, draw, SEED, PARAMS); r.update(extra or {}); LOG.append(r); return r


def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return (c - h, c + h)


# =========================================================== E3: ladder = window-specific modal quantity
def mode_share(Q):
    """Q [rows, windows] with NaN; share of finite cells equal to their column's modal value"""
    hit = 0; tot = 0
    for j in range(Q.shape[1]):
        c = Q[:, j]; c = c[np.isfinite(c)]
        if len(c) == 0: continue
        vals, cnt = np.unique(c, return_counts=True); hit += cnt.max(); tot += len(c)
    return hit / tot if tot else np.nan


def within_row_shuffle(Q, rng):
    out = np.full_like(Q, np.nan)
    for i in range(Q.shape[0]):
        m = np.isfinite(Q[i]); v = Q[i, m]; out[i, m] = v[rng.permutation(len(v))]
    return out


def q_matrix(kind, und, windows, view='view2_class', qcol='Q_v2'):
    g = W[(W.kind == kind) & (W.und == und) & W.window.isin(windows)]; cyc = sorted(g.cycle.unique()); idx = {c: i for i, c in enumerate(cyc)}; wi = {w: j for j, w in enumerate(sorted(windows))}; Q = np.full((len(cyc), len(wi)), np.nan)
    for r in g.itertuples(index=False):
        if getattr(r, view) == 'ACTION': Q[idx[r.cycle], wi[r.window]] = getattr(r, qcol)
    return Q


REG = sorted(set(W[(W.kind == 'PRE') & (~W.control_window)].window)); D0W = sorted(set(W[W.kind == 'D0'].window)); e3 = []
for tag, kind, wins in (('E3a', 'PRE', REG), ('E3b', 'D0', D0W)):
    for view, qcol in (('view2_class', 'Q_v2'), ('view3_class', 'Q_v3')):
        Qn = q_matrix(kind, 'NIFTY', wins, view, qcol); Qs = q_matrix(kind, 'SENSEX', wins, view, qcol); Qp = np.vstack([Qn, Qs]); obs = mode_share(Qp)
        r = run(f'{tag}|{kind}|{view[:5].upper()}', obs, lambda rng, Qp=Qp, obs=obs: mode_share(within_row_shuffle(Qp, rng)), dict(test='E3', n_cells=int(np.isfinite(Qp).sum())))
        e3.append(dict(test=tag, design=kind, view=view[:5].upper(), n_cells=int(np.isfinite(Qp).sum()), mode_share_pooled=obs, mode_share_NIFTY=mode_share(Qn), mode_share_SENSEX=mode_share(Qs), threshold_80_met=obs >= 0.80, p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by']))
# E3c: cross-underlying transfer of the modal ladder (PRE registered windows, view 2)
Qn = q_matrix('PRE', 'NIFTY', REG); Qs = q_matrix('PRE', 'SENSEX', REG)
def modes(Q): return np.array([pd.Series(Q[:, j][np.isfinite(Q[:, j])]).mode().iloc[0] if np.isfinite(Q[:, j]).any() else np.nan for j in range(Q.shape[1])])
def transfer(a, b):
    ma = modes(a); mb = modes(b); hit = np.nansum([(np.isfinite(b[:, j]) & (b[:, j] == ma[j])).sum() for j in range(b.shape[1])]) + np.nansum([(np.isfinite(a[:, j]) & (a[:, j] == mb[j])).sum() for j in range(a.shape[1])]); return hit / (np.isfinite(a).sum() + np.isfinite(b).sum())
obs = transfer(Qn, Qs); r = run('E3c|PRE|V2', obs, lambda rng: transfer(within_row_shuffle(Qn, rng), within_row_shuffle(Qs, rng)), dict(test='E3', n_cells=int(np.isfinite(Qn).sum() + np.isfinite(Qs).sum())))
e3.append(dict(test='E3c', design='PRE', view='VIEW2', n_cells=int(np.isfinite(Qn).sum() + np.isfinite(Qs).sum()), mode_share_pooled=obs, threshold_80_met=obs >= 0.8, p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by']))
pd.DataFrame(e3).to_csv(os.path.join(A, 'p1_e3_results.csv'), index=False)

# =========================================================== E5: strike = ATM of the last completed index close
P = D.parents.copy(); O = pd.read_csv(os.path.join(A, 'p1_off_window_events.csv'), parse_dates=['first_fill']); evclass = dict(zip(O.parent_oid.astype(str), O.event_class)); P['event_class'] = P.parent_oid.astype(str).map(evclass).fillna('WINDOW_ACTION')
P['day_type'] = np.where(P.date == P.expiry, 'D0', 'PRE'); step = P.und.map(STEP)
def refclose(r, which):
    ix = D.idx[r.und].close; Efl = pd.Timestamp(r.E)
    if which == 'R1': t = Efl.floor('min') - pd.Timedelta(minutes=1)
    elif which == 'R2': t = pd.Timestamp(r.first_fill).floor('min') - pd.Timedelta(minutes=1)
    else: t = pd.Timestamp(r.date) + pd.Timedelta(hours=9, minutes=15)
    return float(ix.get(t, np.nan))
for w in ('R1', 'R2', 'R3'): P[w + '_close'] = [refclose(r, w) for r in P.itertuples()]
def katm(S, st): return st * np.floor(S / st + 0.5)
for w in ('R1', 'R2', 'R3'): P[w + '_K'] = katm(P[w + '_close'], step); P[w + '_offset_steps'] = (P.strike - P[w + '_K']) / step
# preceding 15-minute return before the order-entry minute (tilt)
def ret15(r):
    ix = D.idx[r.und].close; e = pd.Timestamp(r.E).floor('min'); a = ix.get(e - pd.Timedelta(minutes=1), np.nan); b = ix.get(e - pd.Timedelta(minutes=16), np.nan); return np.log(a / b) if np.isfinite(a) and np.isfinite(b) else np.nan
P['ret15'] = [ret15(r) for r in P.itertuples()]
# neighbour availability: bars for K +- step at the E-1 bar
def neigh(r):
    t = pd.Timestamp(r.E).floor('min') - pd.Timedelta(minutes=1); ok = 0
    for d in (-1, 1):
        cid = f'{r.und}|{pd.Timestamp(r.expiry):%Y-%m-%d}|{r.cp}|{int(r.strike + d * STEP[r.und])}'; ok += int(np.isfinite(D.opt_close(cid, t)))
    return ok
P['neighbours_with_bars'] = [neigh(r) for r in P.itertuples()]
P.to_csv(os.path.join(A, 'p1_e5_strike_orders.csv'), index=False)
# session minute arrays for the random-reference null
sess_cache = {}
def session_K(und, date):
    k = (und, date)
    if k not in sess_cache:
        ix = D.idx[und].close; day = ix[(ix.index >= pd.Timestamp(date) + pd.Timedelta(hours=9, minutes=15)) & (ix.index < pd.Timestamp(date) + pd.Timedelta(hours=15, minutes=30))]; sess_cache[k] = katm(day.values, STEP[und])
    return sess_cache[k]
def null_matrix(sub):
    """per order: K from every completed session minute (valid first, padded), counts"""
    arrs = [session_K(r.und, r.date) for r in sub.itertuples()]; n = max(len(a) for a in arrs); M = np.full((len(arrs), n), np.nan); cnt = np.array([len(a) for a in arrs])
    for i, a in enumerate(arrs): M[i, :len(a)] = a
    return M, cnt
e5 = []
for w in ('R1', 'R2', 'R3'):
    sub = P[np.isfinite(P[w + '_K']) & ((P.event_class == 'INITIAL_ENTRY') if w == 'R3' else True)]
    exact = (sub.strike == sub[w + '_K']); k = int(exact.sum()); n = len(sub); lo, hi = wilson(k, n)
    M, cnt = null_matrix(sub); Kt = sub.strike.values; ar = np.arange(len(sub))
    def draw(rng, M=M, cnt=cnt, Kt=Kt, ar=ar): return float((M[ar, np.minimum((rng.random(len(cnt)) * cnt).astype(int), cnt - 1)] == Kt).mean())
    r = run(f'E5|exact|{w}', exact.mean(), draw, dict(test='E5', n=n)); chance = float(np.mean([(M[i, :cnt[i]] == Kt[i]).mean() for i in range(len(sub))]))
    e5.append(dict(test=f'E5 exact {w}', n=n, matches=k, rate=k / n, wilson_lo=lo, wilson_hi=hi, chance_baseline_mean=chance, p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by'], status='RUN'))
    # tilt test
    if w == 'R3': e5.append(dict(test='E5 tilt R3', n=0, status='NOT_TESTABLE (no preceding 15-minute return at the 09:15 reference)')); continue
    ne = P[np.isfinite(P[w + '_K']) & (P.strike != P[w + '_K']) & np.isfinite(P.ret15) & (P.ret15 != 0)]; sgn_off = np.sign(ne[w + '_offset_steps'].values); sgn_ret = np.sign(ne.ret15.values); obs = abs(float((sgn_off == sgn_ret).mean()) - 0.5)
    r = run(f'E5|tilt|{w}', obs, lambda rng, a=sgn_off, b=sgn_ret: abs(float((a == b[rng.permutation(len(b))]).mean()) - 0.5), dict(test='E5', n=len(ne)))
    e5.append(dict(test=f'E5 tilt {w}', n=len(ne), matches=int((sgn_off == sgn_ret).sum()), rate=float((sgn_off == sgn_ret).mean()), p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by'], status='RUN'))
pd.DataFrame(e5).to_csv(os.path.join(A, 'p1_e5_results.csv'), index=False)
rows = []
for w in ('R1', 'R2', 'R3'):
    for (und, dt, ec_), g in P.groupby(['und', 'day_type', 'event_class']):
        g = g[np.isfinite(g[w + '_K'])]
        if w == 'R3' and ec_ != 'INITIAL_ENTRY': continue
        if len(g) == 0: continue
        o = g[w + '_offset_steps']; rows.append(dict(reference=w, und=und, day_type=dt, event_class=ec_, orders=len(g), exact=float((o == 0).mean()), within1=float((o.abs() <= 1).mean()), plus1=float((o == 1).mean()), minus1=float((o == -1).mean()), farther=float((o.abs() > 1).mean())))
pd.DataFrame(rows).to_csv(os.path.join(A, 'p1_e5_offsets.csv'), index=False)

# =========================================================== E6: wing = highest-premium OTM strike whose premium <= budget x ATM-leg quote
RF = D.RF; wg = RF[(RF.module == 'h_') & (RF.sgn > 0) & (RF.open_qty > 0)].groupby('parent_oid').agg(und=('und', 'first'), expiry=('expiry', 'first'), date=('date', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), E=('order_entry_minute', 'first'), first_fill=('t_fill', 'min'), units=('open_qty', 'sum'),
                                                                                                         limit=('px_limit', 'first'), px=('px_fill', 'mean')).reset_index()
body = P.rename(columns={'px_mean': 'body_px'}); bym = {k: g.sort_values('first_fill') for k, g in body.groupby(['und', 'expiry', 'date', 'cp', 'E'])}
pair = []
for r in wg.itertuples():
    g = bym.get((r.und, r.expiry, r.date, r.cp, r.E));
    if g is None: pair.append((np.nan, np.nan, np.nan, np.nan)); continue
    g2 = g[g.first_fill <= r.first_fill]; b = (g2 if len(g2) else g).iloc[-1] if len(g) else None; pair.append((b.strike, b.limit / 0.85, b.body_px, b.parent_oid))
wg[['body_strike', 'body_quote_limit', 'body_fill_px', 'body_parent']] = pd.DataFrame(pair, index=wg.index); wg['wing_quote_limit'] = wg.limit / 1.15; wg['day_type'] = np.where(wg.date == wg.expiry, 'D0', 'PRE')
OFFS = np.arange(-3, 4)
def chain(r):
    t = pd.Timestamp(r.E).floor('min') - pd.Timedelta(minutes=1); st = STEP[r.und]; return [D.opt_close(f'{r.und}|{pd.Timestamp(r.expiry):%Y-%m-%d}|{r.cp}|{int(r.strike + j * st)}', t) for j in OFFS]
CH = np.array([chain(r) for r in wg.itertuples()]); wg['atm_leg_bar'] = [D.opt_close(f'{r.und}|{pd.Timestamp(r.expiry):%Y-%m-%d}|{r.cp}|{int(r.body_strike)}', pd.Timestamp(r.E).floor('min') - pd.Timedelta(minutes=1)) if np.isfinite(r.body_strike) else np.nan for r in wg.itertuples()]
wg.to_csv(os.path.join(A, 'p1_e6_wing_orders.csv'), index=False)
dirn = np.where(wg.cp.values == 'CE', -1, 1)            # inward (toward ATM) column offset: CE lower strike, PE higher strike
def rule_eval(P_, budget):
    """P_ [N, 7] premiums of the strike chain centred on the traded wing; budget [N]. Returns (exact, within_one, checkable) boolean arrays"""
    ok = np.isfinite(P_) & np.isfinite(budget)[:, None] & (P_ <= budget[:, None]); masked = np.where(ok, P_, -np.inf); jb = masked.argmax(1); has = np.isfinite(masked.max(1)) & ok.any(1)
    inward = jb + dirn; valid_in = (inward >= 0) & (inward <= 6); ii = np.clip(inward, 0, 6); pin = P_[np.arange(len(P_)), ii]; verified = has & valid_in & np.isfinite(pin) & (pin > budget)
    exact = verified & (jb == 3); within = verified & (np.abs(jb - 3) <= 1); return exact, within, verified
refs = {}
own_bar = CH[:, 3]
refs['algo_quote_from_limit'] = (np.where(np.isfinite(wg.wing_quote_limit.values), wg.wing_quote_limit.values, np.nan), wg.body_quote_limit.values)
refs['last_completed_bar_close'] = (own_bar, wg.atm_leg_bar.values); refs['fill_price'] = (wg.px.values, wg.body_fill_px.values)
strata = (wg.und + '|' + wg.day_type + '|' + wg.cp); scode = pd.factorize(strata)[0]; base_sorted = np.argsort(scode, kind='stable'); e6 = []; sens = []; JOBS = []
def permute_within_strata(budget, rng):
    """vectorised stratified permutation of the budgets (strata = underlying x day type x right)"""
    order = np.argsort(scode + rng.random(len(scode)) * 0.5, kind='stable'); out = np.empty_like(budget); out[base_sorted] = budget[order]; return out
def e6_job(i):
    name, stat_name, P_, budget, obs = JOBS[i]
    def draw(rng):
        e, w_, c = rule_eval(P_, permute_within_strata(budget, rng)); a = e if stat_name == 'exact' else w_; return float(a.sum() / c.sum()) if c.sum() else 0.0
    return seqperm.run_test(f'E6|{stat_name}|{name}', obs, draw, SEED, PARAMS)
for name, (own, atm) in refs.items():
    P_ = CH.copy(); P_[:, 3] = own; budget = CFG['entry']['wing_budget_fraction'] * atm; ex, wi, ck = rule_eval(P_, budget)
    for stat_name, arr in (('exact', ex), ('within_one', wi)):
        n = int(ck.sum()); k = int(arr.sum()); obs = k / n if n else np.nan; JOBS.append((name, stat_name, P_, budget, obs)); e6.append(dict(_n=n, _k=k, _obs=obs, test=f'E6 {stat_name} [{name}]'))
    for frac in (0.015, 0.025, 0.04):
        e_, w_, c_ = rule_eval(P_, frac * atm); sens.append(dict(reference=name, budget_fraction=frac, checkable=int(c_.sum()), exact=float(e_.sum() / c_.sum()) if c_.sum() else np.nan, within_one=float(w_.sum() / c_.sum()) if c_.sum() else np.nan))
import multiprocessing as mp
with mp.get_context('fork').Pool(4) as pool: RES = pool.map(e6_job, range(len(JOBS)))
for row, r in zip(e6, RES):
    r['test_id'] = r.get('test_id'); LOG.append(dict(r, test='E6', n=row['_n'])); lo, hi = wilson(row['_k'], row['_n'])
    row.update(wing_orders=len(wg), paired_with_body=int(np.isfinite(wg.body_strike).sum()), checkable=row.pop('_n'), matches=row.pop('_k'), rate=row.pop('_obs'), wilson_lo=lo, wilson_hi=hi, p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by'])
pd.DataFrame(e6).to_csv(os.path.join(A, 'p1_e6_results.csv'), index=False); pd.DataFrame(sens).to_csv(os.path.join(A, 'p1_e6_budget_sensitivity.csv'), index=False)

# =========================================================== E7: wing quantity vs body quantity (three matching conventions)
def modal_share(r):
    r = np.round(r[np.isfinite(r)], 2)
    if len(r) == 0: return np.nan
    _, c = np.unique(r, return_counts=True); return c.max() / len(r)
wunits = wg.assign(base_units=wg.units / wg.und.map(BASE)); e7 = []
# C1: same window and right
c1 = []
for r in W[W.kind.isin(['PRE', 'D0'])].itertuples(index=False):
    t = pd.Timestamp(r.date) + pd.Timedelta(hours=int(r.window[:2]), minutes=int(r.window[3:])); w0, w1 = t - ec.B0, t + ec.B1
    for cp in ('CE', 'PE'):
        b = P[(P.und == r.und) & (P.expiry == r.expiry) & (P.date == r.date) & (P.cp == cp) & (P.first_fill >= w0) & (P.first_fill < w1)].base_units.sum(); g = wunits[(wunits.und == r.und) & (wunits.expiry == r.expiry) & (wunits.date == r.date) & (wunits.cp == cp) & (wunits.first_fill >= w0) & (wunits.first_fill < w1 + pd.Timedelta(minutes=2))].base_units.sum()
        if b > 0: c1.append(dict(cycle=r.cycle, und=r.und, kind=r.kind, window=r.window, cp=cp, body_units=b, wing_units=g, ratio=g / b))
C1 = pd.DataFrame(c1)
# C2: cycle-day per right totals
tot_b = P.groupby(['und', 'expiry', 'date', 'cp']).base_units.sum().rename('body_units'); tot_w = wunits.groupby(['und', 'expiry', 'date', 'cp']).base_units.sum().rename('wing_units'); C2 = pd.concat([tot_b, tot_w], axis=1).fillna(0).reset_index(); C2 = C2[C2.body_units > 0]; C2['ratio'] = C2.wing_units / C2.body_units; C2['cycle'] = C2.und + '|' + C2.expiry.dt.strftime('%Y-%m-%d')
# C3: wing parent vs its paired body parent
pw = wunits[np.isfinite(wunits.body_parent.astype(float, errors='ignore') if False else wunits.body_strike)].copy(); bu = P.set_index('parent_oid').base_units; pw['body_units'] = pw.body_parent.map(bu); C3 = pw[pw.body_units > 0].assign(ratio=lambda d: d.base_units / d.body_units); C3['cycle'] = C3.und + '|' + C3.expiry.dt.strftime('%Y-%m-%d')
for name, df, grp, wcol in (('C1_same_window_right', C1, ['cycle', 'cp'], 'wing_units'), ('C2_cycle_day_right', C2, ['und', 'cp'], 'wing_units'), ('C3_parent_pair', C3, ['cycle'], 'base_units')):
    bcol = 'body_units'; b = df[bcol].values; w_ = df[wcol].values; gid = df.groupby(grp).ngroup().values; groups = [np.where(gid == g)[0] for g in np.unique(gid)]; obs = modal_share(w_ / b); ratio = w_ / b
    vals, cnt = np.unique(np.round(ratio, 2), return_counts=True); modal = vals[cnt.argmax()]
    def draw(rng, b=b, w_=w_, groups=groups):
        ww = w_.copy()
        for g in groups: ww[g] = w_[g[rng.permutation(len(g))]]
        return modal_share(ww / b)
    r = run(f'E7|{name}', obs, draw, dict(test='E7', n=len(df)))
    e7.append(dict(convention=name, n=len(df), modal_ratio=float(modal), modal_share=obs, median_ratio=float(np.median(ratio)), share_ratio_ge_1=float((ratio >= 1).mean()), p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by']))
pd.DataFrame(e7).to_csv(os.path.join(A, 'p1_e7_results.csv'), index=False); C1.to_csv(os.path.join(A, 'p1_e7_c1_windows.csv'), index=False)

# =========================================================== E8: re-entry follows closures (time-shift null, 15-minute multiples keep the window phase)
cov = RF[(RF.sgn > 0) & (RF.close_qty > 0)]; sess = []
for (und, ex, d), g in P.groupby(['und', 'expiry', 'date']):
    cl = np.sort(((cov[(cov.und == und) & (cov.expiry == ex) & (cov.date == d)].t_fill - pd.Timestamp(d)).dt.total_seconds()).values); op = ((g.first_fill - pd.Timestamp(d)).dt.total_seconds()).values; sess.append((cl, op))
LO, HI = 9 * 3600 + 15 * 60, 15 * 3600 + 30 * 60; SPAN = HI - LO
def share_after_close(shifts):
    hit = 0; n = 0
    for (cl, op), s in zip(sess, shifts):
        x = np.where((op >= LO) & (op < HI), LO + ((op - LO + s) % SPAN), op); j = np.searchsorted(cl, x, 'right') - 1; gap = np.where(j >= 0, x - cl[np.clip(j, 0, max(len(cl) - 1, 0))] if len(cl) else np.inf, np.inf); hit += int(((gap > 0) & (gap <= 600)).sum()); n += len(op)
    return hit / n
obs = share_after_close(np.zeros(len(sess))); r = run('E8|reentry_after_close', obs, lambda rng: share_after_close(rng.integers(1, 25, size=len(sess)) * 900), dict(test='E8', n=sum(len(o) for _, o in sess)))
null_mean = float(np.mean([share_after_close(np.random.default_rng(7 + i).integers(1, 25, size=len(sess)) * 900) for i in range(300)]))
pd.DataFrame([dict(test='E8 re-entry within 10 min after a short-covering fill', openings=sum(len(o) for _, o in sess), sessions=len(sess), observed_share=obs, time_shift_null_mean=null_mean, excess=obs - null_mean, p=r['p'], draws=r['draws'], exceedances=r['exceedances'], stopped_by=r['stopped_by'])]).to_csv(os.path.join(A, 'p1_e8_results.csv'), index=False)
pd.DataFrame(LOG).to_csv(os.path.join(A, 'p1_permutation_log_structure.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
for f in ('p1_e3_results', 'p1_e5_results', 'p1_e6_results', 'p1_e7_results', 'p1_e8_results'): print(f); print(pd.read_csv(os.path.join(A, f + '.csv')).to_string())
