"""Section 4 - first-passage and counterfactual exit tests (short inventory, before the cycle stop).

Contract-level events.  For a short contract, "any lot crossed k x its OWN entry" fires first for the cheapest lot, so own-entry
timing == cheapest-entry timing; own vs cheapest vs average differ in QUANTITY, which is tested separately (quantity test).
References (all causal: built from lots entered in an EARLIER minute and from bars completed before the minute):
  cheap   cheapest open entry          avg     average open entry
  prevclose  contract close of the last D-1 minute (D0 only)      d0open  contract open of the first D0 minute (D0 only)
  runlow  running low since the position was opened (trailing stop)
  target_avg  favourable: low <= k x average entry            runhigh_drop  favourable: low <= k x running high
  mtm     portfolio cumulative LTP-MTM <= -k lakh (cycle level, answered by the s_ module)
OHLC evidence per minute m (never assumes intrabar order):
  definite crossing in m : a print beyond the threshold traded in m (high >= thr for adverse, low <= thr for favourable)
  definitely not crossed : no print beyond the threshold in [entry+1, decision minute] AND the algo's own quote L at decision is inside
  intrabar ambiguous     : the first print beyond the threshold is in the decision minute itself and the quote L is inside
                           (cannot tell whether it traded before or after the decision)
  quote-confirmed        : the algo's own LTP at decision (recovered from the limit band) is beyond the threshold
Exit-association rate = crossing events followed by ANY buy-back of that contract within [m, m+W]  (NOT a stop precision)
Stop-consistent rate  = crossing events followed within W by a stop-consistent exit: not a scheduled/clock exit, the exit's own quote still
                        beyond the threshold, quantity <= lots crossed (own-entry count for 'cheap').  False-trigger rate = 1 - stop-consistent rate.
Stop-like exit coverage = stop-like exits (labels outside scheduled / clock classes) with a definite earlier up-crossing in [x-W, x-1] or a
                        quote-confirmed state; missed-trigger rate = share of stop-like exits that were 'definitely not crossed'.
Latency: trigger->decision bounds [t_dec_lo - (m+60s), t_dec - m]; decision->first fill exact for tagged orders, upper bound for body orders.
python3 analysis/exit_engine/first_passage.py -> results/first_passage_results.csv, first_passage_quantity.csv, first_passage_latency.csv
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from common import orders, markets, replay_book, cycle_stop_minute, RES, SCHEDULED, LOT, split_of

ADV = {'cheap': [1.2, 1.3, 1.4, 1.45, 1.5, 1.55, 1.6, 1.7, 1.8, 2.0, 2.5], 'avg': [1.2, 1.3, 1.4, 1.45, 1.5, 1.55, 1.6, 1.7, 1.8, 2.0, 2.5],
       'prevclose': [1.04, 1.1, 1.2, 1.3, 1.4, 1.5, 1.55, 1.6, 1.8, 2.0, 2.5], 'd0open': [1.04, 1.1, 1.2, 1.3, 1.4, 1.5, 1.55, 1.6, 1.8, 2.0, 2.5],
       'runlow': [1.3, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0]}
FAV = {'target_avg': [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6], 'runhigh_drop': [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]}
MTM_K = [1.0, 1.1, 1.2, 1.25, 1.3, 1.35, 1.4, 1.5]
WINDOWS = [1, 3, 5]
NONSTOP = SCHEDULED + ('8 clock-B rebalance', '6 clock-based exit (clock B, no replacement)', '8b grid rebalance (A/:00 clock)')
GRID_SIZE = sum(len(v) for v in ADV.values()) * 2 + sum(len(v) for v in FAV.values()) * 2 + len(MTM_K)   # x2: high/close basis

def contract_state(Lk, n, cut):
    """per-minute open-short state of one contract from its unit lots (entry_mi < m <= exit_mi): count, cheap, avg, open start, carried mix"""
    cnt = np.zeros(n); s = np.zeros(n); cheap = np.full(n, np.inf); nd1 = np.zeros(n)
    for e, x, p, dday in zip(Lk.entry_mi.values, Lk.exit_mi.values, Lk.entry_px.values, Lk.entry_day.values):
        a, b = e + 1, min(x, cut - 1) + 1
        if b <= a: continue
        cnt[a:b] += 1; s[a:b] += p; cheap[a:b] = np.minimum(cheap[a:b], p); nd1[a:b] += (dday == 0)
    avg = np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan); cheap[cnt == 0] = np.nan
    return cnt, cheap, avg, nd1

def run():
    o = orders(); mk = markets(); Lt = replay_book('cheap'); cs = cycle_stop_minute()
    sh = Lt[Lt.sgn < 0]
    bb = o[(o.closing_short == True)].copy()
    ev_rows, ex_rows, q_rows = [], [], []
    for (u, e), m in mk.items():
        n = len(m['grid']); cut = cs.get((u, e), n); grid = m['grid']; day = m['day']
        d0 = int(day.argmax()) if day.any() else None
        Lc = sh[(sh.und == u) & (sh.expiry == e)]; Bc = bb[(bb.und == u) & (bb.expiry == e)]
        Bc = Bc.assign(mi=[min(int(grid.searchsorted(pd.Timestamp(t).floor('min'))), n - 1) for t in Bc.t_dec_lo])
        for k, Lk in Lc.groupby(['cp', 'strike']):
            if k not in m['k2i']: continue
            kk = m['k2i'][k]; H = m['H'][kk].astype(float); Lo = m['L'][kk].astype(float); Cl = m['C'][kk].astype(float); Cf = m['Cf'][kk].astype(float)
            cnt, cheap, avg, nd1 = contract_state(Lk, n, cut)
            expo = cnt > 0
            if not expo.any(): continue
            # running low / high since the current position was opened (strictly before m)
            runlow = np.full(n, np.nan); runhigh = np.full(n, np.nan); rl = np.inf; rh = -np.inf
            for i in range(n):
                if not expo[i]: rl, rh = np.inf, -np.inf; continue
                runlow[i] = rl if np.isfinite(rl) else np.nan; runhigh[i] = rh if np.isfinite(rh) else np.nan
                if np.isfinite(Lo[i]): rl = min(rl, Lo[i])
                elif np.isfinite(Cf[i]): rl = min(rl, Cf[i])
                if np.isfinite(H[i]): rh = max(rh, H[i])
            if not np.isfinite(runlow).any(): pass
            refs = {'cheap': cheap, 'avg': avg, 'runlow': runlow}
            if d0 is not None and d0 > 0:
                pc = Cf[d0 - 1]; o0 = m['O'][kk, d0:]; o0 = o0[np.isfinite(o0)]
                dmask = (np.arange(n) >= d0)
                refs['prevclose'] = np.where(dmask, pc, np.nan) if np.isfinite(pc) else np.full(n, np.nan)
                refs['d0open'] = np.where(dmask, float(o0[0]), np.nan) if len(o0) else np.full(n, np.nan)
            seg = np.where(day == 0, 'D-1 fresh', np.where(nd1 == 0, 'D0 fresh', np.where(nd1 == cnt, 'D0 carried', 'D0 mixed')))
            ex = Bc[(Bc.cp == k[0]) & (Bc.strike == k[1]) & (Bc.mi < cut)]
            ex_mi = ex.mi.values
            ex_labok = ~ex.label.isin(NONSTOP).values; ex_L = ex.L.values.astype(float); ex_lots = ex.lots.values
            ex_ents = [Lk[(Lk.entry_mi < xm) & (Lk.exit_mi >= xm)].entry_px.values for xm in ex_mi]
            for fam, ks in list(ADV.items()) + list(FAV.items()):
                if fam not in refs and fam not in ('target_avg', 'runhigh_drop'): continue
                if fam == 'target_avg': ref = avg
                elif fam == 'runhigh_drop': ref = runhigh
                else: ref = refs[fam]
                adverse = fam in ADV
                for basis in ('high', 'close'):
                    px = (H if adverse else Lo) if basis == 'high' else Cl
                    for kv in ks:
                        thr = kv * ref
                        ok = expo & np.isfinite(thr) & np.isfinite(px)
                        cond = ok & ((px >= thr) if adverse else (px <= thr))
                        prev = np.concatenate([[False], cond[:-1]])
                        evm = np.where(cond & ~prev)[0]
                        # stop-consistent response: an exit of THIS contract that (a) is not a scheduled/clock exit, (b) whose own quote at
                        # decision is still beyond the threshold, (c) whose quantity <= lots crossed at the quote (own-entry count for 'cheap')
                        sc_ok = np.zeros(len(ex_mi), bool)
                        for j, xm in enumerate(ex_mi):
                            if not ex_labok[j] or not np.isfinite(ex_L[j]) or not np.isfinite(thr[xm]): continue
                            beyond = ex_L[j] >= thr[xm] if adverse else ex_L[j] <= thr[xm]
                            if not beyond: continue
                            if fam == 'cheap': qty = ex_lots[j] <= int((ex_L[j] >= kv * ex_ents[j]).sum())
                            else: qty = ex_lots[j] <= len(ex_ents[j])
                            sc_ok[j] = qty
                        for i in evm:
                            win = {W: (ex_mi >= i) & (ex_mi <= i + W) for W in WINDOWS}
                            ans = {W: bool(win[W].any()) for W in WINDOWS}; sca = {W: bool((win[W] & sc_ok).any()) for W in WINDOWS}
                            nxt = ex_mi[ex_mi >= i]; first = int(nxt.min() - i) if len(nxt) else -1
                            nsc = ex_mi[(ex_mi >= i) & sc_ok]; first_sc = int(nsc.min() - i) if len(nsc) else -1
                            ev_rows.append((u, e, k[0], k[1], fam, basis, kv, i, day[i], seg[i], ans[1], ans[3], ans[5], sca[1], sca[3], sca[5], first, first_sc))
                        # exit-centric evidence
                        for r_, xm in zip(ex.itertuples(), ex_mi):
                            if not expo[xm] or not np.isfinite(thr[xm]): continue
                            q = r_.L
                            qc = bool(np.isfinite(q) and ((q >= thr[xm]) if adverse else (q <= thr[xm])))
                            cm = np.where(cond[:xm + 1])[0]
                            # definite earlier up-crossing within each window (minute < xm) / any print beyond threshold earlier this exposure
                            st = xm
                            while st > 0 and expo[st - 1]: st -= 1
                            cm = cm[cm >= st]
                            ups = evm[(evm >= st) & (evm < xm)]
                            last_up = int(xm - ups.max()) if len(ups) else -1
                            amb = bool(cond[xm] and not np.any(cond[st:xm]) and not qc)
                            never = bool(not len(cm) and not qc)
                            ex_rows.append((u, e, k[0], k[1], fam, basis, kv, r_.oid, r_.label, xm, day[xm], seg[xm], qc, last_up, amb, never, r_.label not in NONSTOP,
                                            bool(np.any(cond[st:xm])), r_.t_dec, r_.t_dec_lo, grid[ups.max()] if len(ups) else pd.NaT))
            # quantity test at each exit order: how many open lots had crossed k x OWN entry at the quote
            for r_, xm in zip(ex.itertuples(), ex_mi):
                op_ = Lk[(Lk.entry_mi < xm) & (Lk.exit_mi >= xm)]
                if not len(op_) or not np.isfinite(r_.L): continue
                ent = op_.entry_px.values
                for kv in (1.45, 1.5, 1.55):
                    q_rows.append((u, e, k[0], k[1], r_.oid, r_.label, xm, day[xm], seg[xm], kv, len(ent), int(r_.lots), int((r_.L >= kv * ent).sum()),
                                   len(ent) if r_.L >= kv * ent.mean() else 0, len(ent) if r_.L >= kv * ent.min() else 0))
    E = pd.DataFrame(ev_rows, columns=['und', 'expiry', 'cp', 'strike', 'ref', 'basis', 'k', 'mi', 'day', 'segment', 'ans1', 'ans3', 'ans5', 'sc1', 'sc3', 'sc5',
                                       'min_to_next_exit', 'min_to_next_sc_exit'])
    X = pd.DataFrame(ex_rows, columns=['und', 'expiry', 'cp', 'strike', 'ref', 'basis', 'k', 'oid', 'label', 'mi', 'day', 'segment', 'quote_conf', 'min_since_up',
                                       'ambiguous', 'never', 'stop_like', 'any_earlier', 't_dec', 't_dec_lo', 't_up'])
    Q = pd.DataFrame(q_rows, columns=['und', 'expiry', 'cp', 'strike', 'oid', 'label', 'mi', 'day', 'segment', 'k', 'open_lots', 'closed', 'n_cross_own', 'n_all_if_avg', 'n_all_if_cheap'])
    for D in (E, X, Q): D['split'] = D.expiry.map(split_of)
    return E, X, Q

def mtm_test():
    """portfolio cumulative LTP-MTM first passage vs the s_ (cycle stop) module.  Close-based MTM and a worst-case bound
    (shorts at the minute high, longs at the minute low) bracket the intrabar path."""
    o = orders(); mk = markets(); Lt = replay_book('cheap'); rows = []
    sfirst = o[o.tp == 's_'].groupby(['und', 'expiry']).agg(t=('t_dec', 'min'))
    for (u, e), m in mk.items():
        n = len(m['grid']); lot = LOT[u]; Lc = Lt[(Lt.und == u) & (Lt.expiry == e)]
        mc = np.zeros(n); mw = np.zeros(n)
        for r in Lc.itertuples():
            if r.cp is None or (r.cp, r.strike) not in m['k2i']: continue
            kk = m['k2i'][(r.cp, r.strike)]; a = r.entry_mi + 1; b = min(r.exit_mi, n - 1) + 1
            Cf = m['Cf'][kk].astype(float); H = np.where(np.isfinite(m['H'][kk]), m['H'][kk], Cf); Lo = np.where(np.isfinite(m['L'][kk]), m['L'][kk], Cf)
            if b > a:
                mc[a:b] += r.sgn * (np.nan_to_num(Cf[a:b], nan=r.entry_px) - r.entry_px) * lot
                adv = H if r.sgn < 0 else Lo
                mw[a:b] += r.sgn * (np.nan_to_num(adv[a:b], nan=r.entry_px) - r.entry_px) * lot
            if r.exit_oid is not None and b < n:
                mc[b:] += r.sgn * (r.exit_px - r.entry_px) * lot; mw[b:] += r.sgn * (r.exit_px - r.entry_px) * lot
        sm = m['grid'].searchsorted(sfirst.loc[(u, e), 't'].floor('min')) if (u, e) in sfirst.index else None
        for kv in MTM_K:
            thr = -kv * 1e5
            hc = np.where(mc <= thr)[0]; hw = np.where(mw <= thr)[0]
            fc = int(hc[0]) if len(hc) else None; fw = int(hw[0]) if len(hw) else None
            if sm is not None:
                lim = sm
                cls = 'definite (close MTM crossed before stop minute)' if (fc is not None and fc < lim) else (
                      'ambiguous (only worst-case bound crossed)' if (fw is not None and fw <= lim) else 'definitely not crossed')
            else:
                cls = 'no stop'
            rows.append((u, e, split_of(e), kv, sm is not None, fc, fw, sm, cls,
                         (pd.Timestamp(sfirst.loc[(u, e), 't']) - m['grid'][fc]).total_seconds() if (sm is not None and fc is not None and fc <= sm) else np.nan))
    return pd.DataFrame(rows, columns=['und', 'expiry', 'split', 'k_lakh', 'stopped', 'first_close_cross_mi', 'first_worst_cross_mi', 'stop_mi', 'class', 'lat_hi_s'])

def summarise(E, X, M):
    """Names are deliberate: an 'exit-association rate' (any later buy-back of the contract) is NOT a stop precision.
    stop_consistent_rate = share of crossing events followed within W by a stop-consistent exit (see run());  false_trigger_rate = 1 - that.
    Coverage is measured on stop-like exits (labels outside scheduled / clock classes); for reference 'cheap' with k <= 1.45 it is partly
    circular because the taxonomy's lot-stop label itself uses quote / cheapest >= 1.45."""
    out = []
    for (ref, basis, kv, sp, sg), g in E.groupby(['ref', 'basis', 'k', 'split', 'segment']):
        xx = X[(X.ref == ref) & (X.basis == basis) & (X.k == kv) & (X.split == sp) & (X.segment == sg) & X.stop_like]
        for W in WINDOWS:
            assoc = g[f'ans{W}'].mean() if len(g) else np.nan; scr = g[f'sc{W}'].mean() if len(g) else np.nan
            if len(xx):
                cov = (((xx.min_since_up >= 1) & (xx.min_since_up <= W)) | xx.quote_conf).mean(); cov_fp = ((xx.min_since_up >= 1) & (xx.min_since_up <= W)).mean()
                amb = xx.ambiguous.mean(); nev = xx.never.mean()
            else: cov = cov_fp = amb = nev = np.nan
            f1 = 2 * scr * cov / (scr + cov) if (np.isfinite(scr) and np.isfinite(cov) and scr + cov > 0) else np.nan
            out.append(dict(reference=ref, basis=basis, k=kv, window_min=W, split=sp, segment=sg, n_crossing_events=len(g),
                            exit_association_rate=assoc, stop_consistent_rate=scr, false_trigger_rate=1 - scr if np.isfinite(scr) else np.nan,
                            n_stop_like_exits=len(xx), stop_like_exit_coverage=cov, coverage_first_passage_only=cov_fp, intrabar_ambiguous_share=amb,
                            definitely_not_crossed_share=nev, missed_trigger_rate=nev, f1_stop_consistent=f1))
    R = pd.DataFrame(out)
    for (kv, sp), g in M.groupby(['k_lakh', 'split']):
        st = g[g.stopped]; crossed = g[g.first_close_cross_mi.notna()]
        r = dict(reference='mtm', basis='close MTM', k=kv, window_min=np.nan, split=sp, segment='cycle', n_crossing_events=len(crossed),
                 stop_consistent_rate=crossed.stopped.mean() if len(crossed) else np.nan, n_stop_like_exits=len(st),
                 stop_like_exit_coverage=(st['class'].str.startswith('definite (')).mean() if len(st) else np.nan,
                 intrabar_ambiguous_share=(st['class'].str.startswith('ambiguous')).mean() if len(st) else np.nan,
                 definitely_not_crossed_share=(st['class'] == 'definitely not crossed').mean() if len(st) else np.nan)
        r['false_trigger_rate'] = 1 - r['stop_consistent_rate'] if np.isfinite(r['stop_consistent_rate']) else np.nan; r['missed_trigger_rate'] = r['definitely_not_crossed_share']
        R = pd.concat([R, pd.DataFrame([r])], ignore_index=True)
    return R

def latency(X, E, best):
    """trigger->decision bounds for exits with a definite earlier up-crossing at the chosen thresholds; decision->fill for all buy-backs"""
    o = orders(); rows = []
    for (ref, basis, kv) in best:
        xx = X[(X.ref == ref) & (X.basis == basis) & (X.k == kv) & (X.min_since_up >= 1) & (X.min_since_up <= 5) & X.stop_like].copy()
        xx['lat_hi_s'] = (pd.to_datetime(xx.t_dec) - pd.to_datetime(xx.t_up)).dt.total_seconds()
        xx['lat_lo_s'] = ((pd.to_datetime(xx.t_dec_lo) - (pd.to_datetime(xx.t_up) + pd.Timedelta('60s'))).dt.total_seconds()).clip(lower=0)
        for sg, g in xx.groupby('segment'):
            rows.append(dict(what=f'trigger->decision {ref}/{basis}/k={kv}', segment=sg, n=len(g), lo_median_s=g.lat_lo_s.median(), hi_median_s=g.lat_hi_s.median(),
                             hi_p75_s=g.lat_hi_s.quantile(.75), hi_p90_s=g.lat_hi_s.quantile(.9)))
    b = o[o.closing_short == True].copy()
    b['d2f'] = (b.t_fill - pd.to_datetime(b.t_dec)).dt.total_seconds(); b['d2f_hi'] = (b.t_fill - pd.to_datetime(b.t_dec_lo)).dt.total_seconds()
    for (ex, lab), g in b.groupby(['dec_exact', 'label']):
        if len(g) < 10: continue
        rows.append(dict(what='decision->first fill (exact, tagged)' if ex else 'decision->first fill (upper bound, body: fill - order minute start)', segment=lab, n=len(g),
                         lo_median_s=g.d2f.median() if ex else 0.0, hi_median_s=(g.d2f if ex else g.d2f_hi).median(), hi_p75_s=(g.d2f if ex else g.d2f_hi).quantile(.75),
                         hi_p90_s=(g.d2f if ex else g.d2f_hi).quantile(.9)))
        if ex: pass
    b['fill_span'] = (b.t_fill_last - b.t_fill).dt.total_seconds()
    rows.append(dict(what='first fill->last fill (all buy-backs)', segment='all', n=len(b), lo_median_s=b.fill_span.median(), hi_median_s=b.fill_span.median(),
                     hi_p75_s=b.fill_span.quantile(.75), hi_p90_s=b.fill_span.quantile(.9)))
    return pd.DataFrame(rows)

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    E, X, Q = run(); M = mtm_test()
    E.to_pickle(os.path.join(os.path.dirname(HERE), '_cache', 'fp_events.pkl')); X.to_pickle(os.path.join(os.path.dirname(HERE), '_cache', 'fp_exits.pkl'))
    R = summarise(E, X, M)
    R.to_csv(os.path.join(RES, 'first_passage_results.csv'), index=False)
    print('grid size (reference x basis x k):', GRID_SIZE, '| events', len(E), '| exit evidences', len(X))
    # choose per (reference, segment) the k with best DEV F1 at W=5 (selection on DEV only), show VAL / TEST
    sel = R[(R.split == 'DEV') & (R.window_min == 5) & (R.n_crossing_events >= 30)].sort_values('f1_stop_consistent', ascending=False).groupby(['reference', 'basis', 'segment']).head(1)
    show = []
    for r in sel.itertuples():
        for sp in ('DEV', 'VAL', 'TEST'):
            z = R[(R.reference == r.reference) & (R.basis == r.basis) & (R.k == r.k) & (R.segment == r.segment) & (R.split == sp) & (R.window_min == 5)]
            if len(z): show.append(z.iloc[0])
    S = pd.DataFrame(show)[['reference', 'basis', 'k', 'segment', 'split', 'n_crossing_events', 'exit_association_rate', 'stop_consistent_rate', 'n_stop_like_exits',
                            'stop_like_exit_coverage', 'intrabar_ambiguous_share', 'missed_trigger_rate', 'f1_stop_consistent']]
    S.to_csv(os.path.join(RES, 'first_passage_selected.csv'), index=False)
    print('\nBest k per reference/segment chosen on DEV by stop-consistent F1 (W=5 min), evaluated on VAL/TEST:'); print(S.round(3).to_string(index=False))
    print('\nPortfolio MTM (cycle stop):'); print(R[R.reference == 'mtm'][['k', 'split', 'n_crossing_events', 'stop_consistent_rate', 'n_stop_like_exits', 'stop_like_exit_coverage', 'intrabar_ambiguous_share', 'missed_trigger_rate']].round(3).to_string(index=False))
    # response curve: crossing -> first stop-consistent exit vs any exit, W up to 60 min (DEV+VAL), cheapest reference, minute high
    cur = []
    for (kv, sg), z in E[(E.ref == 'cheap') & (E.basis == 'high') & (E.split != 'TEST')].groupby(['k', 'segment']):
        t1 = z.min_to_next_exit.where(z.min_to_next_exit >= 0, np.inf); t2 = z.min_to_next_sc_exit.where(z.min_to_next_sc_exit >= 0, np.inf)
        for W in (0, 1, 2, 5, 10, 15, 30, 60): cur.append(dict(k=kv, segment=sg, window_min=W, n=len(z), any_exit=(t1 <= W).mean(), stop_consistent_exit=(t2 <= W).mean()))
    pd.DataFrame(cur).to_csv(os.path.join(RES, 'first_passage_response_curve.csv'), index=False)
    # quantity test
    Q['pop'] = ~Q.label.isin(SCHEDULED)
    qq = Q[Q['pop'] & (Q.n_cross_own > 0)]
    qs = qq.groupby(['k', 'segment', 'split']).apply(lambda g: pd.Series(dict(n=len(g), own_exact=(g.closed == g.n_cross_own).mean(), all_lots=(g.closed == g.open_lots).mean(),
                                                                       one_lot=(g.closed == 1).mean(), closed_le_crossed=(g.closed <= g.n_cross_own).mean(),
                                                                       mean_closed=g.closed.mean(), mean_crossed=g.n_cross_own.mean(), mean_open=g.open_lots.mean()))).reset_index()
    qs.to_csv(os.path.join(RES, 'first_passage_quantity.csv'), index=False)
    print('\nQuantity test (exits where >=1 lot crossed k x own entry at the quote):'); print(qs.round(3).to_string(index=False))
    best = [('cheap', 'high', 1.55), ('cheap', 'high', 1.45), ('avg', 'high', 1.55)]
    LAT = latency(X, E, best); LAT.to_csv(os.path.join(RES, 'first_passage_latency.csv'), index=False)
    print('\nLatency:'); print(LAT.round(1).to_string(index=False))
