"""Order-level scorer implementing reports/ORDER_LEVEL_SCORING_SPEC.md (frozen v1.1; the recorded hash is checked before any run).
LIBRARY ONLY: nothing in this module is executed on real data by import. The legacy bridge (section 11.1 of the spec) re-runs the ORIGINAL lot-matching code on the stored replays.

Schemas
  real: cyc, day (0 = D-1, 1 = D0), cp, side ('buy'|'sell'), strike, lots, t (integer second of day, first fill), row (export row), cls, optional validity, module
  sim : cyc, day, cp, side, strike, lots, t (float seconds), seq (emission order), cls, optional validity, module, t_resolution ('second'|'minute')
  attrs: one row per cyc with step (strike step), und, version ('V1'|'V2'), era ('before'|'after'), stop (bool), outlier (bool)
Matching (spec section 4): keys cyc, day, cp, side must be equal; tiers Exact (0 s) / Near (1-5 s) / Broad (6-60 s) matched one-to-one in that order by minimum-cost assignment; the rest is missing (real) or extra (simulated)."""
import os, json, hashlib, ast
import numpy as np, pandas as pd
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__)); DD = os.path.join(HERE, '..')
SPEC = f'{DD}/reports/ORDER_LEVEL_SCORING_SPEC.md'; FREEZE = f'{DD}/outputs/scoring/spec_freeze.json'
TIER_NAMES = ('exact', 'near', 'broad'); TIER_MAX = (0, 5, 60); KEYS = ['cyc', 'day', 'cp', 'side']; BIG = 1e6
STRICTNESS = ('keys', 'strike_within_1', 'strike_exact', 'lots_exact', 'type')

def spec_record():
    """verify the frozen specification before scoring; returns the run-record fragment"""
    f = json.load(open(FREEZE)); h = hashlib.sha256(open(SPEC, 'rb').read()).hexdigest(); assert h == f['sha256'], 'scoring specification changed after the freeze'
    return dict(spec_version=f['version'], spec_sha256=h, scorer_sha256=hashlib.sha256(open(__file__, 'rb').read()).hexdigest())

# --------------------------------------------------------------------------------------------------------------------- preparation
def prepare_real(df):
    r = df.copy(); r['side'] = r.side.str.lower(); r['t'] = r.t.astype(int); r['sec'] = r.t; r['lots'] = r.lots.astype(int); r['strike'] = r.strike.astype(float)
    if 'row' not in r: r['row'] = np.arange(len(r))
    return r.reset_index(drop=True)
def prepare_sim(df):
    s = df.copy(); s['side'] = s.side.str.lower(); s['sec'] = np.floor(s.t.astype(float)).astype(int); s['lots'] = s.lots.astype(int); s['strike'] = s.strike.astype(float)
    if 'seq' not in s: s['seq'] = np.arange(len(s))
    if 't_resolution' not in s: s['t_resolution'] = 'unspecified'
    return s.reset_index(drop=True)

# --------------------------------------------------------------------------------------------------------------------- matching
def _tier_of(d):
    return 0 if d == 0 else (1 if d <= 5 else (2 if d <= 60 else None))
def match_orders(real, sim, step_of, direction='asc'):
    """returns pairs DataFrame (ri, si, tier, dt, dstrike_steps, dlots). Positional indices into real / sim (after prepare_*). One-to-one by construction."""
    real = real.reset_index(drop=True); sim = sim.reset_index(drop=True); sign = 1 if direction == 'asc' else -1; pairs = []
    rg = real.groupby(KEYS, sort=True).indices; sg = sim.groupby(KEYS, sort=True).indices
    for key, ridx in rg.items():
        sidx = sg.get(key)
        if sidx is None: continue
        step = float(step_of[key[0]]); R = sorted(ridx, key=lambda i: (real.at[i, 't'], sign * real.at[i, 'row'])); S = sorted(sidx, key=lambda i: (sim.at[i, 'sec'], sign * sim.at[i, 'seq']))
        rr = {i: n for n, i in enumerate(R)}; ss = {i: n for n, i in enumerate(S)}; ur, us = list(R), list(S)
        for tier in (0, 1, 2):
            if not ur or not us: break
            rt = real.loc[ur, 't'].values.astype(int); st = sim.loc[us, 'sec'].values.astype(int); D = np.abs(st[None, :] - rt[:, None])
            lo, hi = (0, 0) if tier == 0 else ((1, 5) if tier == 1 else (6, 60)); ok = (D >= lo) & (D <= hi)
            if not ok.any(): continue
            rk = real.loc[ur, 'strike'].values; sk = sim.loc[us, 'strike'].values; rl = real.loc[ur, 'lots'].values; sl = sim.loc[us, 'lots'].values
            rrk = np.array([rr[i] for i in ur]); ssk = np.array([ss[i] for i in us])
            C = D + 0.001 * np.abs(sk[None, :] - rk[:, None]) / step + 1e-6 * np.abs(sl[None, :] - rl[:, None]) + 1e-10 * np.abs(ssk[None, :] - rrk[:, None]); C = np.where(ok, C, BIG)
            a, b = linear_sum_assignment(C); keep = [(x, y) for x, y in zip(a, b) if C[x, y] < BIG / 10]
            for x, y in keep:
                i, j = ur[x], us[y]; pairs.append((i, j, tier, int(sim.at[j, 'sec'] - real.at[i, 't']), float((sim.at[j, 'strike'] - real.at[i, 'strike']) / step), int(sim.at[j, 'lots'] - real.at[i, 'lots'])))
            mr = {ur[x] for x, y in keep}; ms = {us[y] for x, y in keep}; ur = [i for i in ur if i not in mr]; us = [j for j in us if j not in ms]
    P = pd.DataFrame(pairs, columns=['ri', 'si', 'tier', 'dt', 'dstrike', 'dlots']).astype({'ri': int, 'si': int, 'tier': int, 'dt': int, 'dstrike': float, 'dlots': int})        # integer dtypes even when nothing matches
    assert P.ri.is_unique and P.si.is_unique, 'one-to-one violated'
    return P

# --------------------------------------------------------------------------------------------------------------------- ambiguity
def ambiguity(real, sim, P_asc, P_desc):
    """groups (cyc, day, cp, side, second) flagged ambiguous: >= 2 real or >= 2 simulated orders at the same second with differing (strike, lots), or the two tie-break directions pair differently"""
    cell = ['cyc', 'day', 'cp', 'side', 'sec']; amb_r = np.zeros(len(real), bool); amb_s = np.zeros(len(sim), bool)
    for df, flag in ((real, amb_r), (sim, amb_s)):
        g = df.groupby(cell); n = g['lots'].transform('size'); v = g.apply(lambda x: x[['strike', 'lots']].drop_duplicates().shape[0]).rename('nv'); m = df[cell].merge(v.reset_index(), on=cell, how='left').nv.values; flag |= (n.values >= 2) & (m > 1)
    a = P_asc.set_index('ri').si.to_dict(); b = P_desc.set_index('ri').si.to_dict()
    for i in set(a) | set(b):
        if a.get(i) != b.get(i): amb_r[i] = True
        for d_ in (a, b):
            if i in d_: amb_s[d_[i]] |= (a.get(i) != b.get(i))
    return amb_r, amb_s

# --------------------------------------------------------------------------------------------------------------------- metrics
def _f1(tp, ns, nr): return 2 * tp / max(ns + nr, 1)
def pair_flags(real, sim, P, step_of):
    X = P.copy(); r = real.loc[X.ri].reset_index(drop=True); s = sim.loc[X.si].reset_index(drop=True); X['cyc'] = r.cyc.values; X['day'] = r.day.values; X['cls'] = r.cls.values; X['sim_cls'] = s.cls.values
    X['strike_exact'] = (X.dstrike == 0); X['strike_w1'] = X.dstrike.abs() <= 1 + 1e-9; X['lots_exact'] = (X.dlots == 0); X['same_minute'] = (np.floor(s.t.values.astype(float) / 60) == np.floor(r.t.values / 60))
    X['t_resolution'] = s.t_resolution.values
    X['type_ok'] = np.nan; X['type_avail'] = False
    if 'validity' in real and 'validity' in sim:
        have = s.validity.notna().values & r.validity.notna().values                                                          # a pair is type-scored only if the simulator SUPPLIED validity for that order; never inferred
        if 'module' in real and 'module' in sim: have = have & s.module.notna().values
        ok = (r.validity.values == s.validity.values) & ((r.module.values == s.module.values) if ('module' in real and 'module' in sim) else True)
        X['type_avail'] = have; X['type_ok'] = np.where(have, ok, np.nan)
    return X
def tier_tables(real, sim, P):
    n_r, n_s = len(real), len(sim); ex = P.tier.value_counts().reindex([0, 1, 2], fill_value=0); out = []; cum = 0
    for k, nm in enumerate(TIER_NAMES):
        cum += int(ex[k]); out.append(dict(tier=nm, matched=int(ex[k]), share_of_real=ex[k] / max(n_r, 1), share_of_sim=ex[k] / max(n_s, 1), cumulative_matched=cum, cumulative_share_real=cum / max(n_r, 1), cumulative_share_sim=cum / max(n_s, 1), cumulative_tolerance_s=TIER_MAX[k]))
    out.append(dict(tier='unmatched', matched=0, missing_real=n_r - cum, extra_sim=n_s - cum, share_of_real=(n_r - cum) / max(n_r, 1), share_of_sim=(n_s - cum) / max(n_s, 1)))
    return pd.DataFrame(out)
def strictness_table(real, sim, X):
    """precision / recall / F1 at each cumulative tolerance and each strictness level"""
    n_r, n_s = len(real), len(sim); rows = []
    for k, nm in enumerate(TIER_NAMES):
        Z = X[X.tier <= k]; masks = {'keys': np.ones(len(Z), bool), 'strike_within_1': Z.strike_w1.values}; masks['strike_exact'] = Z.strike_exact.values; masks['lots_exact'] = Z.strike_exact.values & Z.lots_exact.values
        masks['type'] = (masks['lots_exact'] & (Z.type_ok.fillna(False).astype(bool).values & Z.type_avail.values)) if Z.type_avail.any() else np.full(len(Z), np.nan)
        for lvl in STRICTNESS:
            m = masks[lvl]
            if lvl == 'type' and not Z.type_avail.any(): rows.append(dict(cumulative_tolerance_s=TIER_MAX[k], level=lvl, matched=np.nan, precision=np.nan, recall=np.nan, F1=np.nan, note='order type not available (simulator supplied no validity)')); continue
            tp = int(np.sum(m)); rows.append(dict(cumulative_tolerance_s=TIER_MAX[k], level=lvl, matched=tp, precision=tp / max(n_s, 1), recall=tp / max(n_r, 1), F1=_f1(tp, n_s, n_r)))
    return pd.DataFrame(rows)
def quantity_table(real, sim, X):
    e = X.dlots.abs(); return dict(matched=int(len(X)), lots_exact_share=float(X.lots_exact.mean()) if len(X) else np.nan, abs_error_mean=float(e.mean()) if len(X) else np.nan, abs_error_median=float(e.median()) if len(X) else np.nan, abs_error_p90=float(e.quantile(.9)) if len(X) else np.nan, signed_bias=float(X.dlots.mean()) if len(X) else np.nan)
def burst_lots(real, sim):
    cell = ['cyc', 'day', 'cp', 'side', 'sec']; a = real.groupby(cell).lots.sum().rename('real'); b = sim.groupby(cell).lots.sum().rename('sim'); J = pd.concat([a, b], axis=1).fillna(0); return dict(bursts=int(len(J)), abs_error_mean=float((J.real - J.sim).abs().mean()) if len(J) else np.nan, exact_share=float((J.real == J.sim).mean()) if len(J) else np.nan)
def key_level_agreement(real, sim):
    """share of real orders with ANY simulated order of the same cyc and day within 60 s regardless of cp and side, versus with the keys required"""
    anyk = 0; withk = 0; sg = sim.groupby(['cyc', 'day']).sec.apply(lambda x: np.sort(x.values)).to_dict(); skeys = sim.groupby(KEYS).sec.apply(lambda x: np.sort(x.values)).to_dict()
    for r in real.itertuples():
        a = sg.get((r.cyc, r.day)); k = skeys.get((r.cyc, r.day, r.cp, r.side))
        if a is not None and len(a):
            p = np.searchsorted(a, r.t); anyk += bool((p < len(a) and a[p] - r.t <= 60) or (p > 0 and r.t - a[p - 1] <= 60))
        if k is not None and len(k):
            p = np.searchsorted(k, r.t); withk += bool((p < len(k) and k[p] - r.t <= 60) or (p > 0 and r.t - k[p - 1] <= 60))
    return dict(any_key_within_60s=anyk / max(len(real), 1), same_key_within_60s=withk / max(len(real), 1))
def missing_extra(real, sim, P, attrs=None):
    mr = np.ones(len(real), bool); ms = np.ones(len(sim), bool); mr[P.ri.values] = False; ms[P.si.values] = False
    R = real[mr].assign(block=lambda d: (d.t // 1800).astype(int)); S = sim[ms].assign(block=lambda d: (d.sec // 1800).astype(int)); out = {}
    out['missing_by_cls'] = R.groupby('cls').lots.agg(orders='size', lots='sum').reset_index() if len(R) else pd.DataFrame(); out['extra_by_cls'] = S.groupby('cls').lots.agg(orders='size', lots='sum').reset_index() if len(S) else pd.DataFrame()
    out['missing_by_block'] = R.groupby('block').lots.agg(orders='size', lots='sum').reset_index(); out['extra_by_block'] = S.groupby('block').lots.agg(orders='size', lots='sum').reset_index(); out['missing_by_cyc'] = R.groupby('cyc').lots.agg(orders='size', lots='sum').reset_index(); out['extra_by_cyc'] = S.groupby('cyc').lots.agg(orders='size', lots='sum').reset_index()
    out['totals'] = dict(missing_orders=int(mr.sum()), missing_lots=int(real.lots[mr].sum()), extra_orders=int(ms.sum()), extra_lots=int(sim.lots[ms].sum())); return out

# --------------------------------------------------------------------------------------------------------------------- state
def _ledger(df, tcol, order_cols):
    d = df.sort_values(order_cols).reset_index(drop=True); contracts = sorted(set(zip(d.cp, d.strike))); ci = {c: n for n, c in enumerate(contracts)}; M = np.zeros((len(d), len(contracts)))
    sg = np.where(d.side.values == 'buy', 1, -1) * d.lots.values
    for n, (cp, k, q) in enumerate(zip(d.cp.values, d.strike.values, sg)): M[n, ci[(cp, k)]] = q
    return d, contracts, np.cumsum(M, axis=0)
def state_after_matched(real, sim, P, amb_r=None, amb_s=None):
    """books immediately after each matched event, per (cyc, day); returns per-pair DataFrame of S/L differences per option type and per-contract L1 distance divided by gross real lots"""
    rows = []
    for (cyc, day), rg in real.groupby(['cyc', 'day']):
        sgp = sim[(sim.cyc == cyc) & (sim.day == day)]; ri = set(rg.index); pp = P[P.ri.isin(ri)]
        if not len(pp): continue
        rd, rc, rcum = _ledger(rg.assign(_o=rg.index), 't', ['t', 'row']); sd, sc, scum = _ledger(sgp.assign(_o=sgp.index), 'sec', ['sec', 'seq']); rpos = {o: n for n, o in enumerate(rd._o.values)}; spos = {o: n for n, o in enumerate(sd._o.values)}
        allc = sorted(set(rc) | set(sc)); rcol = {c: n for n, c in enumerate(rc)}; scol = {c: n for n, c in enumerate(sc)}
        for p in pp.itertuples():
            a = rcum[rpos[p.ri]]; b = scum[spos[p.si]]; d = {}
            for cp in ('CE', 'PE'):
                cols_r = [rcol[c] for c in rc if c[0] == cp]; cols_s = [scol[c] for c in sc if c[0] == cp]; ra = a[cols_r] if cols_r else np.zeros(1); sb = b[cols_s] if cols_s else np.zeros(1)
                d[f'S_real_{cp}'] = float(-ra[ra < 0].sum()); d[f'L_real_{cp}'] = float(ra[ra > 0].sum()); d[f'S_sim_{cp}'] = float(-sb[sb < 0].sum()); d[f'L_sim_{cp}'] = float(sb[sb > 0].sum())
            l1 = sum(abs((a[rcol[c]] if c in rcol else 0) - (b[scol[c]] if c in scol else 0)) for c in allc); gross = float(np.abs(a).sum())
            rows.append(dict(cyc=cyc, day=day, ri=p.ri, si=p.si, l1=float(l1), gross_real=gross, ambiguous=bool((amb_r[p.ri] if amb_r is not None else False) or (amb_s[p.si] if amb_s is not None else False)), **d))
    X = pd.DataFrame(rows)
    if len(X):
        X['SL_equal'] = np.all([(X[f'{k}_real_{cp}'] == X[f'{k}_sim_{cp}']) for k in ('S', 'L') for cp in ('CE', 'PE')], axis=0); X['l1_norm'] = X.l1 / X.gross_real.clip(lower=1)
    return X
def checkpoints(real, sim, every=900):
    """books every `every` seconds and at the end of the day (last real order + 1 s), compared contract by contract"""
    rows = []
    for (cyc, day), rg in real.groupby(['cyc', 'day']):
        sg = sim[(sim.cyc == cyc) & (sim.day == day)]; rd, rc, rcum = _ledger(rg, 't', ['t', 'row'])
        if len(sg): sd, sc, scum = _ledger(sg, 'sec', ['sec', 'seq'])
        else: sd, sc, scum = sg.assign(sec=[]), [], np.zeros((0, 0))
        t0 = int(rd.t.min()); t1 = int(rd.t.max()); ts = list(range(t0 - t0 % every + every, t1 + 1, every)) + [t1 + 1]
        for T in ts:
            ir = np.searchsorted(rd.t.values, T, side='left') - 1; a = dict(zip(rc, rcum[ir])) if ir >= 0 else {}
            js = (np.searchsorted(sd.sec.values, T, side='left') - 1) if len(sd) else -1; b = dict(zip(sc, scum[js])) if js >= 0 else {}
            l1 = sum(abs(a.get(c, 0) - b.get(c, 0)) for c in set(a) | set(b)); rows.append(dict(cyc=cyc, day=day, t=T, l1=l1, gross_real=sum(abs(v) for v in a.values()), end_of_day=(T == t1 + 1)))
    return pd.DataFrame(rows)

# --------------------------------------------------------------------------------------------------------------------- per-cycle, bootstrap, placebo, full report
def by_class_table(real, sim, X):
    """matching keys ignore class, so a real order of one class can match a simulated order of another. Recall is therefore counted on the REAL side (real orders of the class that found any partner), precision on the SIMULATED side
    (simulated orders of the class that found any partner); 'matched_same_class' counts pairs whose two classes agree. F1 = harmonic mean of that recall and precision (never above 1)."""
    rows = []
    for c in sorted(set(real.cls) | set(sim.cls)):
        nr, ns = int((real.cls == c).sum()), int((sim.cls == c).sum()); mr = int((X.cls == c).sum()) if len(X) else 0; ms = int((X.sim_cls == c).sum()) if len(X) else 0; same = int(((X.cls == c) & (X.sim_cls == c)).sum()) if len(X) else 0
        rec = mr / nr if nr else np.nan; pre = ms / ns if ns else np.nan; f = 2 * rec * pre / (rec + pre) if (nr and ns and rec + pre > 0) else (0.0 if (nr and ns) else np.nan)
        rows.append(dict(cls=c, real=nr, sim=ns, matched_real_side=mr, matched_sim_side=ms, matched_same_class=same, recall=rec, precision=pre, F1=f))
    return pd.DataFrame(rows)
def per_cycle(real, sim, P, X):
    rows = []; cyc_all = sorted(set(real.cyc) | set(sim.cyc))
    for c in cyc_all:
        nr = int((real.cyc == c).sum()); ns = int((sim.cyc == c).sum()); Z = X[X.cyc == c]; tp = int(len(Z)); tp_full = int((Z.strike_exact & Z.lots_exact).sum()); lr = int(real.lots[real.cyc == c].sum()); ls = int(sim.lots[sim.cyc == c].sum())
        rows.append(dict(cyc=c, real=nr, sim=ns, matched=tp, precision=tp / max(ns, 1), recall=tp / max(nr, 1), F1=_f1(tp, ns, nr), F1_strike_lots_exact=_f1(tp_full, ns, nr), lot_abs_error_mean=float(Z.dlots.abs().mean()) if tp else np.nan, real_lots=lr, sim_lots=ls))
    return pd.DataFrame(rows)
def distribution(pc, col='F1'):
    v = pc[col].dropna(); w = pc.sort_values(col).head(5)[['cyc', col]]
    return dict(n=int(len(v)), median=float(v.median()), iqr=[float(v.quantile(.25)), float(v.quantile(.75))], p10=float(v.quantile(.1)), min=float(v.min()), max=float(v.max()), macro_mean=float(v.mean()), below_0_5=int((v < 0.5).sum()), below_0_3=int((v < 0.3).sum()), worst_five=w.values.tolist())
def bootstrap_f1(pc, n=4000, seed=1):
    rng = np.random.default_rng(seed); m = pc[['matched', 'sim', 'real']].values; out = []
    for _ in range(n): idx = rng.integers(0, len(m), len(m)); s = m[idx].sum(0); out.append(_f1(s[0], s[1], s[2]))
    return [float(np.quantile(out, .025)), float(np.quantile(out, .975))]
def score(real, sim, attrs, mode, evidence_label, shift_placebo=True, bootstrap=4000):
    """full order-level report for one run (one day type). mode in {'F','T','TF-E'}; evidence_label in {'historical reproduction','out-of-fold','independent'}"""
    assert mode in ('F', 'T', 'TF-E') and evidence_label in ('historical reproduction', 'out-of-fold', 'independent')
    rec = spec_record(); real = prepare_real(real); sim = prepare_sim(sim); step_of = attrs.set_index('cyc').step.to_dict()
    Pa = match_orders(real, sim, step_of, 'asc'); Pd = match_orders(real, sim, step_of, 'desc'); ar, as_ = ambiguity(real, sim, Pa, Pd); res = dict(run=dict(**rec, mode=mode, evidence_label=evidence_label, cycles=int(real.cyc.nunique()), real_orders=int(len(real)), sim_orders=int(len(sim))))
    res['ambiguity'] = dict(real_share=float(ar.mean()) if len(real) else 0.0, sim_share=float(as_.mean()) if len(sim) else 0.0)
    out = {}
    for nm, P in (('asc', Pa), ('desc', Pd)):
        X = pair_flags(real, sim, P, step_of); out[nm] = dict(P=P, X=X, tiers=tier_tables(real, sim, P), strict=strictness_table(real, sim, X))
    res['tiers'] = out['asc']['tiers']; res['strictness'] = out['asc']['strict']; X = out['asc']['X']; res['tie_break_range'] = {}
    for lvl in STRICTNESS:
        for tol in TIER_MAX:
            a = out['asc']['strict'].query('level==@lvl and cumulative_tolerance_s==@tol').F1.iloc[0]; b = out['desc']['strict'].query('level==@lvl and cumulative_tolerance_s==@tol').F1.iloc[0]; res['tie_break_range'][f'{lvl}@{tol}s'] = [float(min(a, b)) if a == a else None, float(max(a, b)) if a == a else None]
    res['timing'] = dict(dt_median=float(X.dt.median()) if len(X) else None, dt_iqr=[float(X.dt.quantile(.25)), float(X.dt.quantile(.75))] if len(X) else None, dt_bias=float(X.dt.mean()) if len(X) else None, same_minute_share=float(X.same_minute.mean()) if len(X) else None, by_t_resolution=X.groupby('t_resolution').agg(matched=('tier', 'size'), exact_share=('tier', lambda s: float((s == 0).mean())), same_minute=('same_minute', 'mean')).reset_index().to_dict('records'),
                         note='exact-second share is descriptive only (spec principle 7)')
    res['key_level'] = key_level_agreement(real, sim); res['strike'] = dict(exact_share=float(X.strike_exact.mean()) if len(X) else None, within_1_share=float(X.strike_w1.mean()) if len(X) else None, abs_steps=X.dstrike.abs().describe().round(3).to_dict() if len(X) else {}); res['quantity'] = quantity_table(real, sim, X); res['burst_lots'] = burst_lots(real, sim)
    res['type'] = dict(available=bool(X.type_avail.any()) if len(X) else False, coverage_of_matched=float(X.type_avail.mean()) if len(X) else None, agreement=float(X.type_ok[X.type_avail].astype(float).mean()) if len(X) and X.type_avail.any() else None, note='pairs without simulator-supplied validity are excluded, never assumed'); res['unmatched'] = missing_extra(real, sim, Pa)
    pc = per_cycle(real, sim, Pa, X); res['per_cycle'] = pc; res['per_cycle_F1'] = distribution(pc, 'F1'); res['per_cycle_F1_strike_lots_exact'] = distribution(pc, 'F1_strike_lots_exact'); res['pooled_F1_ci95'] = bootstrap_f1(pc, bootstrap) if bootstrap else None
    res['state_after_matched'] = state_after_matched(real, sim, Pa, ar, as_); res['checkpoints'] = checkpoints(real, sim) if len(real) else pd.DataFrame()
    if shift_placebo:
        sh = sim.copy(); sh['sec'] = sh.sec + 900; Pp = match_orders(real, sh, step_of, 'asc'); res['time_shift_placebo'] = dict(shift_s=900, note='a time-shift placebo, not a universal random-chance baseline; it can preserve or disrupt timetable patterns', tiers=tier_tables(real, sh, Pp), F1_keys_at_60s=_f1(len(Pp), len(sh), len(real)))
    res['by_attribute'] = {}
    for col in ('und', 'version', 'era'):
        if col in attrs:
            g = attrs.set_index('cyc')[col]; rows = []
            for v, cy in attrs.groupby(col).cyc: Z = pc[pc.cyc.isin(cy)]; tp, ns, nr = Z.matched.sum(), Z.sim.sum(), Z.real.sum(); rows.append(dict(value=v, cycles=int(len(Z)), real=int(nr), sim=int(ns), matched=int(tp), F1=_f1(tp, ns, nr)))
            res['by_attribute'][col] = pd.DataFrame(rows)
    res['by_class'] = by_class_table(real, sim, X); res['class_confusion'] = pd.crosstab(X.cls, X.sim_cls).reset_index() if len(X) else pd.DataFrame()
    # --- additional required tables (spec sections 5 and 7)
    blk = lambda t: (t // 1800).astype(int); rb = real.assign(b=blk(real.t)); sb = sim.assign(b=blk(sim.sec)); mb = rb.loc[Pa.ri].b.values; bt = []
    for b in sorted(set(rb.b) | set(sb.b)): nr_, ns_, tp_ = int((rb.b == b).sum()), int((sb.b == b).sum()), int((mb == b).sum()); bt.append(dict(block_start=f'{(b * 1800) // 3600:02d}:{((b * 1800) % 3600) // 60:02d}', real=nr_, sim=ns_, matched_by_real_block=tp_, recall=tp_ / max(nr_, 1), precision=tp_ / max(ns_, 1), F1=_f1(tp_, ns_, nr_)))
    res['by_block'] = pd.DataFrame(bt)
    pcl = pc.dropna(subset=['lot_abs_error_mean']); res['per_cycle_lot_abs_error'] = dict(n=int(len(pcl)), median=float(pcl.lot_abs_error_mean.median()), iqr=[float(pcl.lot_abs_error_mean.quantile(.25)), float(pcl.lot_abs_error_mean.quantile(.75))], max=float(pcl.lot_abs_error_mean.max()), worst_five=pcl.sort_values('lot_abs_error_mean', ascending=False).head(5)[['cyc', 'lot_abs_error_mean']].values.tolist()) if len(pcl) else None
    st = res['state_after_matched']; res['per_cycle_state_error'] = (lambda g: dict(n=int(len(g)), median=float(g.median()), iqr=[float(g.quantile(.25)), float(g.quantile(.75))], max=float(g.max()), worst_five=g.sort_values(ascending=False).head(5).reset_index().values.tolist()))(st.groupby('cyc').l1_norm.mean()) if len(st) else None
    if len(st): res['state_summary'] = dict(matched_events=int(len(st)), SL_equal_share=float(st.SL_equal.mean()), l1_norm_median=float(st.l1_norm.median()), l1_norm_mean=float(st.l1_norm.mean()), ambiguous_share=float(st.ambiguous.mean()))
    if len(X): res['timing_by_class'] = X.groupby('cls').agg(matched=('tier', 'size'), exact=('tier', lambda t: float((t == 0).mean())), near=('tier', lambda t: float((t == 1).mean())), broad=('tier', lambda t: float((t == 2).mean())), same_minute=('same_minute', 'mean'), strike_exact=('strike_exact', 'mean'), lots_exact=('lots_exact', 'mean')).reset_index()
    if bootstrap:
        rng = np.random.default_rng(2); full = pc[['cyc']].assign(tp=[int((X[X.cyc == c].strike_exact & X[X.cyc == c].lots_exact).sum()) for c in pc.cyc], ns=pc.sim.values, nr=pc.real.values).values[:, 1:].astype(float); bs_ = []
        for _ in range(bootstrap): m_ = full[rng.integers(0, len(full), len(full))].sum(0); bs_.append(_f1(m_[0], m_[1], m_[2]))
        res['pooled_F1_strike_lots_exact_ci95'] = [float(np.quantile(bs_, .025)), float(np.quantile(bs_, .975))]
    res['_pairs'] = Pa; return res
def variants(real, sim, attrs, mode, evidence_label, **kw):
    """spec section 3: all cycles; without the outlier cycle(s); non-stop cycles; stop cycles only (a stop ends the day and changes every later number)"""
    out = {}; sets = {'all': set(attrs.cyc), 'without_outlier': set(attrs[~attrs.outlier].cyc), 'non_stop': set(attrs[~attrs.stop].cyc), 'stop_only': set(attrs[attrs.stop].cyc)}
    for k, cy in sets.items():
        if not cy: continue
        r_ = real[real.cyc.isin(cy)]; s_ = sim[sim.cyc.isin(cy)]
        if len(r_): out[k] = score(r_, s_, attrs[attrs.cyc.isin(cy)], mode, evidence_label, **kw)
    return out

# --------------------------------------------------------------------------------------------------------------------- legacy bridge (original matching code, lifted from the original scripts by parsing their source)
def _literal(path, name):
    tree = ast.parse(open(path).read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets): return ast.literal_eval(n.value)
    raise KeyError(name)
def _legacy_match(rj, rk, sj, sk, tol):
    """VERBATIM from validate_engine.py / bl_d0_fr_score.py / bl_fr_score.py (the three copies are identical): lot-level one-to-one matching, minute index, same-minute first then +-1.. , nearest strike breaks ties"""
    bucket = {}
    for n, j in enumerate(sj): bucket.setdefault(int(j), []).append(n)
    used = np.zeros(len(sj), bool); done = np.zeros(len(rj), bool); dk = []
    for ps in range(tol + 1):
        for a in range(len(rj)):
            if done[a]: continue
            best = None
            for jj in ({rj[a]} if ps == 0 else {rj[a] - ps, rj[a] + ps}):
                for n in bucket.get(int(jj), []):
                    if used[n]: continue
                    dd = abs(sk[n] - rk[a])
                    if best is None or dd < best[0]: best = (dd, n)
            if best: used[best[1]] = True; done[a] = True; dk.append(best[0])
    return np.array(dk)
def legacy_d1_scores(ORD, CY, REAL, STEP):
    """D-1 lot-level scoring exactly as validate_engine.py did it (class map and tolerances parsed from that script)."""
    src = os.path.join(HERE, 'validate_engine.py'); CLASS = _literal(src, 'CLASS'); NMOD = _literal(src, 'NMOD'); TOL = {c: 1 for c in NMOD}; TOL['lump'] = 3
    R = REAL.copy(); R['cls'] = [CLASS.get((m, r_), 'not_modelled') for m, r_ in zip(R.module, R.role)]; R.loc[(R.cls == 'opening_wings') & (R.j > 2), 'cls'] = 'not_modelled'
    lots_of = lambda df: df.loc[df.index.repeat(df.lots.astype(int))]; RL = {}
    for i, r in enumerate(CY.itertuples()):
        z = R[(R.und == r.und) & (R.expiry == r.expiry)]
        for (cls, cp), g in z.groupby(['cls', 'cp']): g = lots_of(g); RL[(i, cls, cp)] = (g.j.values.astype(int), g.strike.values.astype(float))
    rows = {c: dict(real=0, sim=0, tp=0, exact=0, within1=0) for c in NMOD + ['not_modelled']}
    for i in range(len(CY)):
        o = ORD[i]; ol = lots_of(o) if len(o) else o; st = STEP[CY.iloc[i].und]
        for cls in NMOD + ['not_modelled']:
            for cp in ('CE', 'PE'):
                rj, rk = RL.get((i, cls, cp), (np.array([], int), np.array([], float))); rows[cls]['real'] += len(rj)
                if cls == 'not_modelled' or not len(ol): continue
                g = ol[(ol.cls == cls) & (ol.cp == cp)]; rows[cls]['sim'] += len(g)
                if len(rj) and len(g):
                    dk = _legacy_match(rj, rk, g.j.values.astype(int), g.strike.values.astype(float), TOL[cls]); rows[cls]['tp'] += len(dk); rows[cls]['exact'] += int((dk == 0).sum()); rows[cls]['within1'] += int((dk <= st).sum())
    f1 = lambda tp, sim, real: 2 * tp / max(sim + real, 1)
    tp = sum(rows[c]['tp'] for c in NMOD); sm = sum(rows[c]['sim'] for c in NMOD); rl = sum(rows[c]['real'] for c in rows)
    out = [dict(cls='ALL', real_lots=rl, sim_lots=sm, matched=tp, precision=tp / sm, recall=tp / rl, F1=f1(tp, sm, rl))]
    for c in NMOD: d = rows[c]; out.append(dict(cls=c, real_lots=d['real'], sim_lots=d['sim'], matched=d['tp'], precision=d['tp'] / max(d['sim'], 1), recall=d['tp'] / max(d['real'], 1), F1=f1(d['tp'], d['sim'], d['real'])))
    return pd.DataFrame(out)
def legacy_d0_scores(sims, cids, CY, O, STEP):
    """D0 lot-level scoring exactly as bl_d0_fr_score.py did it (class map, modelled classes and the minute-index rule parsed from that script)."""
    src = os.path.join(HERE, 'bl_d0_fr_score.py'); CLS = _literal(src, 'CLS'); NMOD = _literal(src, 'NMOD'); REAL = {}
    for i in cids:
        r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)].copy(); z['cls'] = ['stop' if m == 's_' else CLS.get((m, ro), 'not_modelled') for m, ro in zip(z.module, z.role)]; z['j'] = ((z.tod - 33300) // 60).clip(0, 389).astype(int); REAL[i] = z
    expand = lambda df: (np.repeat(df.j.values, df.lots.values).astype(int), np.repeat(df.strike.values, df.lots.values).astype(float))
    rows = {c: dict(real=0, sim=0, tp=0) for c in NMOD}
    for i in cids:
        s = sims[i]
        for c in NMOD:
            for cp in ('CE', 'PE'):
                rj, rk = expand(REAL[i][(REAL[i].cls == c) & (REAL[i].cp == cp)]); g = s[(s.cls == c) & (s.cp == cp)]; sj, sk = expand(g); rows[c]['real'] += len(rj); rows[c]['sim'] += len(sj)
                if len(rj) and len(sj): rows[c]['tp'] += len(_legacy_match(rj, rk, sj, sk, 1))
    tp = sum(d['tp'] for d in rows.values()); sm = sum(d['sim'] for d in rows.values()); rl = sum(d['real'] for d in rows.values())
    return dict(real_lots=rl, sim_lots=sm, matched=tp, precision=tp / sm, recall=tp / rl, F1=2 * tp / (sm + rl))
