"""Phase 5-6: descriptive analysis of PROFIT / LOSS / BREAKEVEN exits and the comparison of candidate patterns with all other exits.
python3 tp_reconstruction/scripts/analyze_exits.py     (needs ALGO8_MARKET_DIR for the market-context and hazard parts)
Descriptive only. Candidate patterns come from the cluster rule fixed in config.yaml before any table was inspected; each is evaluated once and
labelled a HYPOTHESIS at best. Nothing is optimised and no threshold is searched."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp_common as tc
CR = tc.CFG['candidate_rules']; W = int(CR['hazard_window_minutes']); IST_S = 19800
LAB = ['PROFIT', 'LOSS', 'BREAKEVEN']


def q(s, p=(.05, .1, .25, .5, .75, .9, .95)): return {f'p{int(x * 100)}': round(float(s.quantile(x)), 3) for x in p}


# ------------------------------------------------------------------ cluster rule (pre-declared)
def clusters(counts, min_count, ratio, side):
    """counts: Series indexed by an ordered, evenly spaced key. A key is a cluster if count >= min_count and count >= ratio x median(counts of up to `side` neighbours each side, itself excluded)."""
    k = list(counts.index); v = counts.values.astype(float); rows = []
    for i, key in enumerate(k):
        nb = [v[j] for j in range(max(0, i - side), min(len(k), i + side + 1)) if j != i]
        med = float(np.median(nb)) if nb else np.nan
        ex = v[i] / med if med and med > 0 else np.nan
        rows.append(dict(key=key, count=int(v[i]), neighbour_median=med, excess_ratio=ex, is_cluster=bool(v[i] >= min_count and ex >= ratio)))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ A. premium decay, profit per unit, holding, exit behaviour
def decay_tables(E):
    out = []; cl = []
    w = CR['decay_bin_width_pct']
    for m in tc.METHODS:
        for lab, lo, hi in (('PROFIT', 0, 100), ('LOSS', 100, 300)):
            e = E[(E.method == m) & (E.direction == -1) & (E.label == lab)]
            b = np.floor(e.exit_pct_of_entry / w) * w; over = int((b >= hi).sum()); b = b[b < hi]              # bins [lo, hi); closings at or beyond `hi` % are reported as one overflow row, never as a cluster
            cnt = b.value_counts().reindex(np.arange(lo, hi, w), fill_value=0).sort_index()
            c = clusters(cnt, CR['cluster_min_count'], CR['cluster_excess_ratio'], 3)
            for _, r in c.iterrows():
                un = e.loc[b[b == r.key].index, 'qty_closed'].sum()
                out.append(dict(method=m, side=lab, bin_lo_pct=r.key, bin_hi_pct=r.key + w, closing_fills=r['count'], units=int(un), neighbour_median=r.neighbour_median, excess_ratio=r.excess_ratio, is_cluster=r.is_cluster))
            out.append(dict(method=m, side=lab, bin_lo_pct=hi, bin_hi_pct=np.inf, closing_fills=over, units=int(e.loc[e.exit_pct_of_entry >= hi, 'qty_closed'].sum()), neighbour_median=np.nan, excess_ratio=np.nan, is_cluster=False))
    D = pd.DataFrame(out)
    return D


def profit_tables(E):
    rows = []
    for m in tc.METHODS:
        for d in (-1, 1):
            for lab in LAB:
                e = E[(E.method == m) & (E.direction == d) & (E.label == lab)]
                if not len(e): continue
                per_lot = e.pnl_pts_per_unit * e.und.map(tc.LOT)
                top = e.pnl_pts_per_unit.round(2).value_counts().head(5); rows.append(dict(method=m, direction='short' if d < 0 else 'long', label=lab, closing_fills=len(e), units=int(e.qty_closed.sum()), gross_pnl_rupees=round(e.pnl.sum(), 2),
                          **{f'pts_per_unit_{k}': v for k, v in q(e.pnl_pts_per_unit).items()}, **{f'rupees_per_lot_{k}': v for k, v in q(per_lot).items()},
                          top5_values_pts=';'.join(f'{k}:{v}' for k, v in top.items()), top5_share_of_label=round(top.sum() / len(e), 4)))
    return pd.DataFrame(rows)


def hold_tables(E):
    rows = []
    for m in tc.METHODS:
        for (d, lab, sr), e in E[E.method == m].groupby(['direction', 'label', 'session_relation']):
            rows.append(dict(method=m, direction='short' if d < 0 else 'long', label=lab, session_relation=sr, closing_fills=len(e), units=int(e.qty_closed.sum()), **{f'hold_min_{k}': v for k, v in q(e.hold_minutes_mean).items()}))
    return pd.DataFrame(rows)


def behaviour_tables(E, L, R):
    """exit behaviour from the closing fills (FIFO labels; roles are convention-free)"""
    e = E[E.method == 'FIFO'].copy(); e['lots'] = e.qty_closed / e.und.map(tc.LOT); e = e.sort_values('t_fill')
    e['t_s'] = e.exit_epoch.astype(float)
    # time to the next closing fill of the same contract, and whether the position was closed within 5 minutes after a partial exit
    e['next_close_s'] = e.groupby('contract_id').t_s.shift(-1) - e.t_s
    # replacement / re-entry: an opening fill (other parent order) in the same underlying and same right within 60 s after the closure
    op = R[(R.method == 'FIFO') & (R.open_qty > 0)].merge(L[['src_row', 'und', 'cp', 'parent_oid']], on='src_row'); closing_par = e.set_index('close_row').parent_oid
    rep = []; ops = {k: g.sort_values('epoch') for k, g in op.groupby(['und', 'cp'])}
    for r in e.itertuples():
        g = ops.get((r.und, r.cp)); 
        if g is None: rep.append(False); continue
        a = np.searchsorted(g.epoch.values, r.t_s, 'left'); b = np.searchsorted(g.epoch.values, r.t_s + 60, 'right'); rep.append(bool((g.parent_oid.values[a:b] != r.parent_oid).any()))
    e['replacement_open_within_60s'] = rep
    # batch: other closing fills of the same underlying within +-60 s
    bt = []
    for u, g in e.groupby('und'):
        s = g.t_s.values; bt.append(pd.Series(np.searchsorted(s, s + 60, 'right') - np.searchsorted(s, s - 60, 'left') - 1, index=g.index))
    e['other_closings_same_und_pm60s'] = pd.concat(bt)
    b10 = []
    for u, g in e.groupby('und'):
        s_ = g.t_s.values; b10.append(pd.Series(np.searchsorted(s_, s_ + 10, 'right') - np.searchsorted(s_, s_ - 10, 'left') - 1, index=g.index))
    e['other_closings_same_und_pm10s'] = pd.concat(b10)
    rows = []
    for lab in LAB + ['ALL']:
        g = e if lab == 'ALL' else e[e.label == lab]
        for d, nm in ((-1, 'short'), (1, 'long')):
            x = g[g.direction == d]
            if not len(x): continue
            rows.append(dict(label=lab, direction=nm, closing_fills=len(x), share_partial=round((x.exit_type == 'PARTIAL').mean(), 4), share_full=round(x.exit_type.isin(['FULL', 'FULL_WITH_REVERSAL']).mean(), 4),
                             share_one_lot=round((x.lots == 1).mean(), 4), median_lots=float(x.lots.median()), share_next_close_same_contract_within_60s=round((x.next_close_s <= 60).mean(), 4),
                             median_pct_of_position_closed=round(float((x.qty_closed / (x.qty_closed + x.remaining_after_units)).median()), 4), share_followed_by_replacement_open_within_60s=round(x.replacement_open_within_60s.mean(), 4),
                             share_with_other_closings_same_und_within_60s=round((x.other_closings_same_und_pm60s > 0).mean(), 4), share_with_other_closings_same_und_within_10s=round((x.other_closings_same_und_pm10s > 0).mean(), 4), share_carried=round((x.session_relation != 'SAME_SESSION').mean(), 4)))
    return pd.DataFrame(rows), e


# ------------------------------------------------------------------ D. market context at the exit (index bars completed before the exit minute only)
def session_arrays(I):
    I = I.copy(); I['date'] = I.ts.dt.normalize(); I['k'] = ((I.ts - I.date).dt.total_seconds() // 60 - 555).astype(int); I = I[(I.k >= 0) & (I.k < 375)]
    out = {}
    for (u, d), g in I.groupby(['und', 'date']):
        a = {c: np.full(375, np.nan) for c in ('open', 'high', 'low', 'close')}
        for c in a: a[c][g.k.values] = g[c].values
        out[(u, d)] = a
    return out


def context_features(X, I):
    S = session_arrays(I); from market_data import frozen_sessions; fz = frozen_sessions(I); rows = []
    for r in X.itertuples():
        a = S.get((r.und, r.date)); t = r.t_fill; k = int((t - r.date).total_seconds() // 60 - 555)
        f = dict(close_row=r.close_row, ctx_available=False, ctx_reliable=False)
        if a is not None and 61 <= k <= 374:
            c = a['close']; last = k - 1                                    # last COMPLETED bar
            fz_zone = (r.und, r.date) in fz and k >= 360
            if np.isfinite(c[last]) and np.isfinite(c[last - 60]) and np.isfinite(c[last - 15]):
                lr = np.diff(np.log(c[last - 30:last + 1])); hi, lo = a['high'], a['low']
                rng1 = np.nanmax(hi[last - 14:last + 1]) - np.nanmin(lo[last - 14:last + 1]); rng0 = np.nanmax(hi[last - 29:last - 14]) - np.nanmin(lo[last - 29:last - 14])
                f.update(ctx_available=True, ctx_reliable=not fz_zone, idx_ret_15m_bp=1e4 * np.log(c[last] / c[last - 15]), idx_ret_60m_bp=1e4 * np.log(c[last] / c[last - 60]), rv30_bp=1e4 * np.sqrt(np.nansum(lr ** 2)),
                         range_expansion=rng1 / rng0 if rng0 > 0 else np.nan, dist_from_open_bp=1e4 * np.log(c[last] / a['open'][0]) if np.isfinite(a['open'][0]) else np.nan)
        f['tod_min'] = k; f['minutes_to_expiry'] = (r.expiry + pd.Timedelta(hours=15, minutes=30) - t).total_seconds() / 60
        rows.append(f)
    return pd.DataFrame(rows)


def auc_rank(x, y):
    """P(x_profit > x_loss) with ties 0.5 (Mann-Whitney)"""
    from scipy.stats import rankdata
    x = np.asarray(x); y = np.asarray(y); n1, n0 = len(x), len(y)
    if n1 == 0 or n0 == 0: return np.nan
    r = rankdata(np.r_[x, y]); return (r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def context_summary(X, F, reps=500, seed=7):
    d = X.merge(F, on='close_row'); d = d[(d.direction == -1) & d.ctx_available & d.ctx_reliable & d.consensus_label.isin(['PROFIT', 'LOSS'])].copy()
    d['stratum'] = d.minutes_to_expiry.lt(375 + 1).map({True: 'D0', False: 'carry'}) + '_' + (d.tod_min // 60).astype(str)
    feats = ['idx_ret_15m_bp', 'idx_ret_60m_bp', 'rv30_bp', 'range_expansion', 'dist_from_open_bp', 'tod_min', 'minutes_to_expiry']; rng = np.random.default_rng(seed); dates = d.date.unique(); rows = []
    byd = {k: g for k, g in d.groupby('date')}
    def stat(df, f):
        a = df[df.consensus_label == 'PROFIT'][f].dropna().values; b = df[df.consensus_label == 'LOSS'][f].dropna().values; raw = auc_rank(a, b)
        num = den = 0.0
        for s, g in df.groupby('stratum'):                                    # AUC within strata of (expiry day vs carry) x clock hour, weighted by pair count
            p = g[g.consensus_label == 'PROFIT'][f].dropna().values; l = g[g.consensus_label == 'LOSS'][f].dropna().values
            if len(p) >= 5 and len(l) >= 5: num += auc_rank(p, l) * len(p) * len(l); den += len(p) * len(l)
        return raw, (num / den if den else np.nan)
    for f in feats:
        raw, adj = stat(d, f); b_raw, b_adj = [], []
        for _ in range(reps):
            pick = rng.choice(dates, len(dates)); df = pd.concat([byd[x] for x in pick]); r_, a_ = stat(df, f); b_raw.append(r_); b_adj.append(a_)
        a = d[d.consensus_label == 'PROFIT'][f]; l = d[d.consensus_label == 'LOSS'][f]
        rows.append(dict(feature=f, n_profit=int(a.notna().sum()), n_loss=int(l.notna().sum()), median_profit=round(float(a.median()), 3), median_loss=round(float(l.median()), 3), auc_profit_gt_loss=round(raw, 4),
                         auc_ci_lo=round(float(np.nanpercentile(b_raw, 2.5)), 4), auc_ci_hi=round(float(np.nanpercentile(b_raw, 97.5)), 4), auc_within_strata=round(adj, 4), auc_within_strata_ci_lo=round(float(np.nanpercentile(b_adj, 2.5)), 4),
                         auc_within_strata_ci_hi=round(float(np.nanpercentile(b_adj, 97.5)), 4), dates=len(dates)))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ C. contract-minute exposure panel (short inventory) and hazard of a closing fill
def build_panel(L, R, O):
    sh = R[(R.method == 'FIFO') & (R.sgn > 0) & (R.close_qty > 0) & (R.inventory_before < 0)]            # buys that close shorts (roles are convention-free)
    close_ep = {c: np.sort(g.epoch.values + IST_S) for c, g in sh.groupby('contract_id')}
    snaps = {m: {c: (g.epoch.values + IST_S, g.inventory_after.values, g.ref_px_after.values) for c, g in R[R.method == m].sort_values(['contract_id', 'epoch']).groupby('contract_id', sort=False)} for m in tc.METHODS}
    first_fill = L.groupby('contract_id').epoch.min() + IST_S; meta = L.drop_duplicates('contract_id').set_index('contract_id')[['und', 'expiry']]
    O = O[O.contract_id.isin(close_ep.keys() | snaps['FIFO'].keys())]; parts = []
    for c, g in O.groupby('contract_id', sort=False):
        if c not in snaps['FIFO']: continue
        g = g.sort_values('ts'); s = ((g.ts - pd.Timestamp('1970-01-01')).dt.total_seconds()).values.astype('int64')
        prev_close = g.close.shift(1).values; prev_s = np.r_[np.nan, s[:-1]]; stale = (s - prev_s) / 60
        tod = ((g.ts - g.ts.dt.normalize()).dt.total_seconds() // 60 - 555).values
        keep = (s > first_fill[c]) & (tod >= 0) & (tod < 375) & np.isfinite(prev_close) & ((stale <= 5) | (tod == 0))           # prior bar completed and fresh (<= 5 min old); at 09:15 it is the previous session's last bar
        if not keep.any(): continue
        s = s[keep]; row = dict(contract_id=c, und=meta.loc[c, 'und'], expiry=meta.loc[c, 'expiry'], date=g.ts.dt.normalize().values[keep], tod_min=tod[keep], mark=prev_close[keep])
        ok = np.ones(len(s), bool)
        for m in tc.METHODS:
            se, inv, ref = snaps[m][c]; idx = np.searchsorted(se, s, 'left') - 1; has = idx >= 0
            iv = np.where(has, inv[np.clip(idx, 0, None)], 0); rf = np.where(has, ref[np.clip(idx, 0, None)], np.nan)
            row[f'inv_{m}'] = iv; row[f'ref_{m}'] = rf
        ce = close_ep.get(c, np.array([])); n_close = np.searchsorted(ce, s + W * 60, 'left') - np.searchsorted(ce, s, 'left') if len(ce) else np.zeros(len(s), int)
        row['closed_in_window'] = n_close > 0; row['closed_this_minute'] = (np.searchsorted(ce, s + 60, 'left') - np.searchsorted(ce, s, 'left') > 0) if len(ce) else np.zeros(len(s), bool)
        P = pd.DataFrame(row); P = P[P.inv_FIFO < 0]; parts.append(P)
    P = pd.concat(parts, ignore_index=True)
    for m in tc.METHODS: P[f'ratio_{m}'] = 100 * P.mark / P[f'ref_{m}']
    P['d0'] = P.date == P.expiry; P['tod_hour'] = P.tod_min // 60
    return P


def standardized_hazard(P, ratio_col, w, lo, hi, strata=('d0', 'tod_hour')):
    """closing-in-window hazard by decay-ratio bin; directly standardised to the overall (expiry-day x clock-hour) mix"""
    P = P[np.isfinite(P[ratio_col])].copy(); P['bin'] = (np.floor(P[ratio_col] / w) * w).clip(lower=lo, upper=hi)
    mix = P.groupby(list(strata)).size() / len(P); rows = []
    for b, g in P.groupby('bin'):
        h = g.groupby(list(strata)).closed_in_window.agg(['mean', 'size']); h = h[h['size'] >= 20]
        wt = mix.reindex(h.index).values; std = float((h['mean'].values * wt).sum() / wt.sum()) if len(h) and wt.sum() > 0 else np.nan
        rows.append(dict(bin_lo_pct=b, rows=len(g), hazard_raw=float(g.closed_in_window.mean()), hazard_standardised=std, strata_used=len(h), share_of_rows_in_used_strata=float(h['size'].sum() / len(g))))
    return pd.DataFrame(rows)


def hazard_tables(P):
    out = []
    for m in tc.METHODS:
        for und in ('ALL', 'NIFTY', 'SENSEX'):
            Q = P if und == 'ALL' else P[P.und == und]
            H = standardized_hazard(Q, f'ratio_{m}', CR['decay_bin_width_pct'], 0, 300); H.insert(0, 'und', und); H.insert(0, 'convention', m); out.append(H)
    return pd.concat(out, ignore_index=True)


def std_ratio(inb, nb, flag, strata, min_rows=20):
    """hazard ratio controlling for strata: sum_s n_in,s * h_in,s / sum_s n_in,s * h_nb,s over strata with >= min_rows on both sides"""
    a = inb.groupby(list(strata))[flag].agg(['mean', 'size']); b = nb.groupby(list(strata))[flag].agg(['mean', 'size']); j = a.join(b, lsuffix='_in', rsuffix='_nb', how='inner')
    j = j[(j.size_in >= min_rows) & (j.size_nb >= min_rows)]
    if not len(j) or (j.size_in * j.mean_nb).sum() == 0: return np.nan
    return float((j.size_in * j.mean_in).sum() / (j.size_in * j.mean_nb).sum())


def evaluate(P, cond, near, flag, strata=('d0', 'tod_hour')):
    """closing-in-window (or in-minute) hazard inside the condition versus its neighbours, split by expiry day / carry days, underlying and cycle"""
    inb = P[cond]; nb = P[near]; h = lambda d: d[flag].mean() if len(d) else np.nan
    ratio = lambda a, b: h(a) / h(b) if len(a) and len(b) and h(b) > 0 else np.nan
    per = {u: round(ratio(inb[inb.und == u], nb[nb.und == u]), 2) for u in ('NIFTY', 'SENSEX')}
    cy = lambda d: d.assign(cy=d.expiry.dt.strftime('%Y-%m-%d') + d.und).groupby('cy')[flag].mean()
    j = pd.concat([cy(inb).rename('a'), cy(nb).rename('b')], axis=1).dropna()
    return dict(rows_in_condition=len(inb), hazard_in_condition=h(inb), hazard_neighbours=h(nb), hazard_ratio=ratio(inb, nb), hazard_ratio_expiry_day=ratio(inb[inb.d0], nb[nb.d0]), hazard_ratio_carry_days=ratio(inb[~inb.d0], nb[~nb.d0]), hazard_ratio_controlled_for_expiry_day_and_clock_hour=std_ratio(inb, nb, flag, strata),
                per_underlying_ratio=str(per), cycles_elevated=f'{int((j.a > j.b).sum())}/{len(j)}')


def profit_share_after(P, cond, E, m):
    """share of PROFIT among the first closing fill that follows each in-condition panel row within the window (label under convention m)"""
    ce = E[(E.method == m) & (E.direction == -1)]; g = {c: (x.exit_epoch.values + IST_S, x.label.values) for c, x in ce.sort_values('exit_epoch').groupby('contract_id')}
    sub = P[cond & P.closed_in_window]; labs = []
    for c, d, t in zip(sub.contract_id, sub.date, sub.tod_min):
        ep, lb = g[c]; s0 = (pd.Timestamp(d) - pd.Timestamp('1970-01-01')).total_seconds() + (555 + t) * 60; i = np.searchsorted(ep, s0, 'left')
        if i < len(ep) and ep[i] < s0 + W * 60: labs.append(lb[i])
    return {k: round(v, 3) for k, v in pd.Series(labs).value_counts(normalize=True).items()} if labs else {}, len(labs)


def candidate_rows(E, X, P, Dec, clock_cl):
    """each candidate evaluated once; a verdict here is NEVER a trigger claim"""
    rows = []; w = CR['decay_bin_width_pct']
    pc = Dec[(Dec.side == 'PROFIT') & Dec.is_cluster]; bins = sorted(pc.bin_lo_pct.unique())
    rows.append(dict(pattern_id='DECAY-*', family='premium decay', description='profit-side decay-level clusters (5-pp bins of exit premium / entry premium) under the pre-declared rule',
                     result=f'cluster bins: ' + (', '.join(f'{int(b)}-{int(b + w)}% in {sorted(pc[pc.bin_lo_pct == b].method)}' for b in bins) if bins else 'none'),
                     verdict='NO decay-level cluster under all three conventions' if not any((pc.bin_lo_pct == b).sum() == len(tc.METHODS) for b in bins) else 'cluster present under all three conventions (HYPOTHESIS)'))
    for b in bins[:CR['max_candidates']]:
        lo, hi = b, b + w; nconv = int((pc.bin_lo_pct == b).sum())
        for m in tc.METHODS:
            col = f'ratio_{m}'; cond = (P[col] >= lo) & (P[col] < hi); near = ((P[col] >= lo - 15) & (P[col] < lo)) | ((P[col] >= hi) & (P[col] < hi + 15))
            ev = evaluate(P, cond, near, 'closed_in_window'); lab, n = profit_share_after(P, cond, E, m)
            rows.append(dict(pattern_id=f'DECAY-{int(lo)}-{int(hi)}', family='premium decay', description=f'short inventory marked at {int(lo)}-{int(hi)}% of the {m} reference entry; cluster under {nconv}/3 conventions', convention=m, **ev,
                             closings_followed=n, label_mix_of_closings_after_condition=str(lab), verdict='HYPOTHESIS only' if nconv == len(tc.METHODS) else 'convention-dependent; HYPOTHESIS only'))
    for _, c in clock_cl.sort_values('excess_ratio', ascending=False).head(CR['max_candidates']).iterrows():
        hhmm = c.key; k = (pd.Timestamp(f'2000-01-01 {hhmm}') - pd.Timestamp('2000-01-01 09:15')).total_seconds() / 60
        e = E[(E.method == 'FIFO') & (E.direction == -1) & (E.t_fill.dt.strftime('%H:%M') == hhmm)]; allsh = E[(E.method == 'FIFO') & (E.direction == -1)]
        ev = evaluate(P, P.tod_min == k, (P.tod_min >= k - 5) & (P.tod_min <= k + 5) & (P.tod_min != k), 'closed_this_minute', strata=('d0',))
        lab = {m: E[(E.method == m) & (E.direction == -1) & (E.t_fill.dt.strftime('%H:%M') == hhmm)].label.value_counts(normalize=True).round(3).to_dict() for m in tc.METHODS}
        rows.append(dict(pattern_id=f'CLOCK-{hhmm}', family='clock minute', description=f'short-position closing fills at {hhmm} IST', convention='ALL', n_events=len(e), share_of_all_short_closings=round(len(e) / len(allsh), 4), **ev,
                         label_mix_by_convention=str(lab), verdict='HYPOTHESIS only (clock-driven closing); profitability depends on the position, not the clock'))
    return pd.DataFrame(rows)


def main():
    L = pd.read_parquet(os.path.join(tc.DATA, 'fill_event_ledger.parquet')); E = pd.read_parquet(os.path.join(tc.DATA, 'exit_events.parquet')); X = pd.read_parquet(os.path.join(tc.DATA, 'exit_event_consensus.parquet'))
    R = pd.read_parquet(os.path.join(tc.DATA, 'fill_roles.parquet'))
    Dec = decay_tables(E); Dec.to_csv(os.path.join(tc.ANALYSIS, 'premium_decay_distribution.csv'), index=False)
    profit_tables(E).to_csv(os.path.join(tc.ANALYSIS, 'profit_per_unit_summary.csv'), index=False); hold_tables(E).to_csv(os.path.join(tc.ANALYSIS, 'holding_duration_summary.csv'), index=False)
    B, ev = behaviour_tables(E, L, R); B.to_csv(os.path.join(tc.ANALYSIS, 'exit_behavior_summary.csv'), index=False)
    # clock clusters (profit-side short closings, one-minute keys, +-5 minutes), pre-declared rule
    e = E[(E.method == 'FIFO') & (E.direction == -1) & (E.label == 'PROFIT')]; mm = e.t_fill.dt.strftime('%H:%M').value_counts().sort_index()
    allmin = pd.Series(0, index=pd.date_range('2000-01-01 09:15', '2000-01-01 15:39', freq='min').strftime('%H:%M')); cnt = (allmin + mm).fillna(0)
    clock_cl = clusters(cnt, CR['clock_cluster_min_count'], CR['clock_cluster_excess_ratio'], 5); clock_cl.to_csv(os.path.join(tc.ANALYSIS, 'clock_minute_clusters.csv'), index=False)
    clock_cl = clock_cl[clock_cl.is_cluster]
    import market_data as md
    I = md.index_bars(); O = md.option_bars()
    F = context_features(X[X.direction == -1], I); ctx = context_summary(X, F); ctx.to_csv(os.path.join(tc.ANALYSIS, 'market_context_summary.csv'), index=False)
    P = build_panel(L, R, O); P.to_parquet(os.path.join(tc.DATA, 'short_exposure_panel.parquet'), index=False)
    H = hazard_tables(P); H.to_csv(os.path.join(tc.ANALYSIS, 'closing_hazard_by_decay.csv'), index=False)
    C = candidate_rows(E, X, P, Dec, clock_cl); C.to_csv(os.path.join(tc.ANALYSIS, 'exit_pattern_summary.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 70)
    print('panel rows', len(P)); print(B.to_string(index=False)); print(ctx.to_string(index=False)); print(C.T.to_string())


if __name__ == '__main__':
    main()
