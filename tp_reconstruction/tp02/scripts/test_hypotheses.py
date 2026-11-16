"""TP-02 Phase 4: registered hypothesis tests H1-H6 on the clean profitable non-stop body population (Pop 3) and the exposure panel.
python3 tp_reconstruction/tp02/scripts/test_hypotheses.py   (needs ALGO8_MARKET_DIR)
Permutation labels are shuffled only inside cycle x day-type x hour strata; bootstrap resamples whole expiry cycles; Holm over the registered primary tests.
Hazard ratios and AUCs are descriptive, not causal."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp02_common as c
sys.path.insert(0, os.path.join(c.PKG, 'scripts')); import market_data as md
CFG = c.CFG; ET = CFG['effect_thresholds']; A = c.ANALYSIS; HZ = CFG['hypotheses']; RNG = np.random.default_rng(CFG['inference']['seed']); NB = CFG['inference']['bootstrap_reps']; HW = HZ['H1_decay']['hazard_window_minutes'] * 60
METH = c.METHODS


# ------------------------------------------------------------------ exposure panel with event flags, mark-to-market and market features
def cycle_mtm(L, R, P, O):
    """cycle mark-to-market at the start of each exposed minute: realised (average cost, closures before the minute) + unrealised (average-cost pool vs the last completed mark), all contracts of the cycle"""
    Ra = R[R.method == 'AVG'].merge(L[['src_row', 'und', 'expiry', 'date']], on='src_row'); pcs = P[(P.method == 'AVG') & (P.row_type == 'CLOSED')]
    pcs = pcs.assign(cycle=pcs.und + '|' + pd.to_datetime(pcs.expiry).dt.strftime('%Y-%m-%d'))
    out = {}; Ob = {k: g for k, g in O.groupby('contract_id')}
    for (u, e), g in Ra.groupby(['und', 'expiry']):
        cyc = u + '|' + pd.Timestamp(e).strftime('%Y-%m-%d'); pp = P_cycle = pcs[pcs.cycle == cyc].sort_values('exit_epoch'); cre = pp.exit_epoch.values + c.IST_S; cum = np.cumsum(pp.pnl.values)
        dates = sorted(g.date.unique()); grid = np.concatenate([(pd.Timestamp(d) - pd.Timestamp('1970-01-01')).total_seconds() + (555 + np.arange(375)) * 60 for d in dates]).astype('int64')
        unreal = np.zeros(len(grid))
        for cid, x in g.sort_values(['epoch', 'src_row']).groupby('contract_id'):
            se = x.epoch.values + c.IST_S; inv = x.inventory_after.values; ref = x.ref_px_after.values
            i = np.searchsorted(se, grid, 'left') - 1; has = i >= 0; iv = np.where(has, inv[np.clip(i, 0, None)], 0.0); rf = np.where(has, ref[np.clip(i, 0, None)], np.nan)
            ob = Ob.get(cid)
            if ob is None: continue
            ts = ((ob.ts - pd.Timestamp('1970-01-01')).dt.total_seconds()).values.astype('int64'); cl = ob.close.values; j = np.searchsorted(ts, grid - 60, 'right') - 1; mk = np.where(j >= 0, cl[np.clip(j, 0, None)], np.nan)
            ok = (iv != 0) & np.isfinite(mk) & np.isfinite(rf); unreal += np.where(ok, np.sign(iv) * (mk - rf) * np.abs(iv), 0.0)
        k = np.searchsorted(cre, grid, 'left'); real = np.where(k > 0, cum[np.clip(k - 1, 0, None)], 0.0) if len(cum) else np.zeros(len(grid))
        d = pd.DataFrame({'cycle': cyc, 'date': np.repeat(dates, 375), 'tod_min': np.tile(np.arange(375), len(dates)), 'mtm': real + unreal, 'mtm_realised': real, 'mtm_unrealised': unreal}); out[cyc] = d
    return pd.concat(out.values(), ignore_index=True)


def index_features(I):
    """index features per (und, date, minute k) using bars completed before the minute (bar k-1 and earlier); frozen closing minutes excluded"""
    fz = md.frozen_sessions(I); I = I.copy(); I['date'] = I.ts.dt.normalize(); I['k'] = ((I.ts - I.date).dt.total_seconds() // 60 - 555).astype(int); I = I[(I.k >= 0) & (I.k < 375)]; rows = []
    for (u, d), g in I.groupby(['und', 'date']):
        a = {cn: np.full(375, np.nan) for cn in ('open', 'high', 'low', 'close')}
        for cn in a: a[cn][g.k.values] = g[cn].values
        C_, H_, L_ = a['close'], a['high'], a['low']; lr = np.full(375, np.nan); lr[1:] = np.log(C_[1:] / C_[:-1])
        for k in range(61, 375):
            last = k - 1
            if (u, d) in fz and k >= 360: continue
            if not (np.isfinite(C_[last]) and np.isfinite(C_[last - 15]) and np.isfinite(C_[last - 60])): continue
            r0 = np.nanmax(H_[last - 29:last - 14]) - np.nanmin(L_[last - 29:last - 14])
            rows.append((u, d, k, 1e4 * np.log(C_[last] / C_[last - 15]), 1e4 * np.log(C_[last] / C_[last - 60]), 1e4 * np.sqrt(np.nansum(lr[last - 29:last + 1] ** 2)),
                         (np.nanmax(H_[last - 14:last + 1]) - np.nanmin(L_[last - 14:last + 1])) / r0 if r0 > 0 else np.nan, 1e4 * np.log(C_[last] / a['open'][0])))
    return pd.DataFrame(rows, columns=['und', 'date', 'tod_min', 'idx_ret_15m_bp', 'idx_ret_60m_bp', 'rv30_bp', 'range_expansion', 'dist_from_open_bp'])


def build_panel(T, L, R, P):
    panel = c.tp01('short_exposure_panel.parquet'); panel['date'] = pd.to_datetime(panel.date); panel['expiry'] = pd.to_datetime(panel.expiry)
    panel['cycle'] = panel.und + '|' + panel.expiry.dt.strftime('%Y-%m-%d'); panel['day_type'] = np.where(panel.date == panel.expiry, 'EXPIRY_DAY', 'CARRY_DAY'); panel['hour'] = (555 + panel.tod_min) // 60
    panel['s'] = ((panel.date - pd.Timestamp('1970-01-01')).dt.total_seconds() + (555 + panel.tod_min) * 60).astype('int64')
    S = T[T.direction == -1]
    for name, mask in (('pop3', S.pop3_clean_nonstop), ('pop4s', S.pop4s_unexplained_strict), ('pop1', S.pop1_profit_stable)):
        ev = {k: np.sort(g.epoch.values + c.IST_S) for k, g in S[mask].groupby('contract_id')}; y5 = np.zeros(len(panel), bool); y1 = np.zeros(len(panel), bool)
        for k, idx in panel.groupby('contract_id').indices.items():
            e = ev.get(k)
            if e is None: continue
            s = panel.s.values[idx]; y5[idx] = (np.searchsorted(e, s + HW, 'left') - np.searchsorted(e, s, 'left')) > 0; y1[idx] = (np.searchsorted(e, s + 60, 'left') - np.searchsorted(e, s, 'left')) > 0
        panel[f'y5_{name}'] = y5; panel[f'y1_{name}'] = y1
    return panel


# ------------------------------------------------------------------ generic binned hazard with permutation and cycle bootstrap
class BinHazard:
    def __init__(self, b, y, strata, cycle, nb):
        self.nb = nb; self.b = b; self.y = y.astype(np.int8); self.ns = int(strata.max()) + 1; self.s = strata; self.cyc = cycle; self.nc = int(cycle.max()) + 1

    def std_hazard(self, b, y, w=None):
        n = np.bincount(b * self.ns + self.s, minlength=self.nb * self.ns, weights=w).reshape(self.nb, self.ns); k = np.bincount(b * self.ns + self.s, weights=y if w is None else y * w, minlength=self.nb * self.ns).reshape(self.nb, self.ns)
        mix = n.sum(0) / max(n.sum(), 1e-9); ok = n >= 20; h = np.where(ok, k / np.maximum(n, 1e-9), 0.0); wt = ok * mix[None, :]
        return np.where(wt.sum(1) > 0, (h * wt).sum(1) / np.maximum(wt.sum(1), 1e-12), np.nan), n.sum(1)

    def ratios(self, std, rows, lo, hi, minrows, side=3):
        r = np.full(self.nb, np.nan)
        for i in range(lo, hi):
            if rows[i] < minrows: continue
            nb_ = [std[j] for j in range(max(lo, i - side), min(hi, i + side + 1)) if j != i and rows[j] >= minrows and np.isfinite(std[j])]
            if len(nb_) and np.mean(nb_) > 0 and np.isfinite(std[i]): r[i] = std[i] / np.mean(nb_)
        return r

    def run(self, lo, hi, minrows, perms, order, gid):
        std, rows = self.std_hazard(self.b, self.y); r = self.ratios(std, rows, lo, hi, minrows); obs = np.nanmax(r) if np.isfinite(r).any() else np.nan; arg = int(np.nanargmax(r)) if np.isfinite(r).any() else -1
        mx = np.empty(perms); rng = np.random.default_rng(CFG['inference']['seed'] + 1)
        for p in range(perms):
            idx = np.lexsort((rng.random(len(self.b)), gid)); bp = self.b[idx]            # rows are pre-sorted by gid, so this shuffles bin labels inside each stratum
            sp, rp = self.std_hazard(bp, self.y); rr = self.ratios(sp, rp, lo, hi, minrows); mx[p] = np.nanmax(rr) if np.isfinite(rr).any() else 0
        pval = (1 + (mx >= obs).sum()) / (perms + 1)
        # cycle bootstrap CI of the best bin's ratio
        w = RNG.multinomial(self.nc, np.ones(self.nc) / self.nc, size=NB).astype(float); bs = []
        for k in range(NB):
            wr = w[k][self.cyc]; sp, rp = self.std_hazard(self.b, self.y, wr)
            if arg >= 0: bs.append(self.ratios(sp, rp, max(lo, arg - 3), min(hi, arg + 4), minrows)[arg])
        bs = np.array(bs, float)
        return dict(max_ratio=obs, best_bin=arg, perm_p=pval, ci_lo=np.nanpercentile(bs, 2.5) if len(bs) else np.nan, ci_hi=np.nanpercentile(bs, 97.5) if len(bs) else np.nan, curve=r, std=std, rows=rows)


def holm(p):
    p = np.asarray(p, float); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0
    for i, j in enumerate(o): run = max(run, (m - i) * p[j]); adj[j] = min(1, run)
    return adj


def verdict(events, cycles, conv_ok, und_ok, cycles_share, p_adj, effect, not_sup):
    if events < 100 or cycles < 10: return 'INCONCLUSIVE'
    if not_sup: return 'NOT_SUPPORTED'
    if effect and conv_ok and und_ok and cycles_share >= 0.6 and p_adj < 0.05: return 'SUPPORTED'
    return 'PARTIAL' if effect else 'NOT_SUPPORTED'


def main():
    T = pd.read_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet')); T['cycle'] = T.und + '|' + T.expiry.dt.strftime('%Y-%m-%d')
    L = c.tp01('fill_event_ledger.parquet'); R = c.tp01('fill_roles.parquet'); P = c.tp01('reconstructed_position_ledger.parquet'); O = md.option_bars(); I = md.index_bars()
    panel = build_panel(T, L, R, P); mt = cycle_mtm(L, R, P, O); panel = panel.merge(mt, on=['cycle', 'date', 'tod_min'], how='left')
    fe = index_features(I); panel = panel.merge(fe, on=['und', 'date', 'tod_min'], how='left'); panel['minutes_to_expiry'] = np.where(panel.day_type == 'EXPIRY_DAY', 375 - panel.tod_min, 375 * 2 - panel.tod_min)
    panel['stratum_key'] = panel.cycle + '|' + panel.day_type + '|' + panel.hour.astype(str); panel = panel.sort_values('stratum_key', kind='stable').reset_index(drop=True)
    gid = pd.factorize(panel.stratum_key)[0]; cyc = pd.factorize(panel.cycle)[0]; cyc_names = pd.factorize(panel.cycle)[1]; strata_id = pd.factorize(panel.day_type + '|' + panel.hour.astype(str))[0]
    panel.to_parquet(os.path.join(c.DATA, 'exposure_panel_tp02.parquet'), index=False)
    S = T[(T.direction == -1) & T.pop3_clean_nonstop]; rows_out = []; curves = []
    perms = ET['permutations']; minrows = ET['min_bin_rows']; rt = ET['ratio_effect_present']; nsb = ET['ratio_not_supported_band']
    # ---------------- H1: fixed premium-decay take-profit (profit side bins of 5 points, 0-100 %) and H4b: cycle mark-to-market bins
    for m in METH:
        ratio = panel[f'ratio_{m}'].values; bnum = np.clip((np.floor(ratio / 5)).astype(int), 0, 59); ok = np.isfinite(ratio)
        pe = panel[ok]; bh = BinHazard(bnum[ok], pe.y5_pop3.values, strata_id[ok], cyc[ok], 60)
        r = bh.run(0, 20, minrows, perms, None, gid[ok]); undr = {}
        for u in ('NIFTY', 'SENSEX'):
            mu = (pe.und == u).values; bu = BinHazard(bnum[ok][mu], pe.y5_pop3.values[mu], strata_id[ok][mu], cyc[ok][mu], 60); sd, rw = bu.std_hazard(bu.b, bu.y); undr[u] = bu.ratios(sd, rw, 0, 20, minrows)[r['best_bin']] if r['best_bin'] >= 0 else np.nan
        cyc_pos = 0; cyc_tot = 0
        for cn in cyc_names:
            mm = (pe.cycle == cn).values
            if mm.sum() < 50: continue
            b2 = BinHazard(bnum[ok][mm], pe.y5_pop3.values[mm], strata_id[ok][mm], np.zeros(mm.sum(), int), 60); sd, rw = b2.std_hazard(b2.b, b2.y); bi = r['best_bin']
            if bi >= 0 and rw[bi] >= 20 and rw[max(0, bi - 3):bi + 4].sum() > rw[bi]:
                nb_ = np.nanmean([sd[j] for j in range(max(0, bi - 3), min(20, bi + 4)) if j != bi]); cyc_tot += 1; cyc_pos += int(np.isfinite(nb_) and nb_ > 0 and sd[bi] / nb_ > 1)
        rows_out.append(dict(test_id=f'H1-{m}', hypothesis='H1 fixed premium-decay TP', convention=m, events=len(S), rows=int(ok.sum()), cycles=int(S.cycle.nunique()), statistic='max controlled hazard ratio over 5-point decay bins 0-100 %', observed=r['max_ratio'], best_bin_pct=5 * r['best_bin'],
                             ci_lo=r['ci_lo'], ci_hi=r['ci_hi'], perm_p=r['perm_p'], ratio_nifty=undr['NIFTY'], ratio_sensex=undr['SENSEX'], cycles_with_effect=f'{cyc_pos}/{cyc_tot}'))
        curves.append(pd.DataFrame({'test': f'H1-{m}', 'bin_lo_pct': 5 * np.arange(20), 'rows': r['rows'][:20], 'std_hazard': r['std'][:20], 'ratio_vs_neighbours': r['curve'][:20]}))
    # H4b: cycle mark-to-market (average-cost basis), bins of Rs 25,000
    mtm = panel.mtm.values; ok = np.isfinite(mtm); step = HZ['H4_basket']['mtm_bin_rupees']; pe = panel[ok]; mb = np.clip(np.floor(pe.mtm.values / step).astype(int) + 40, 0, 79)
    bh = BinHazard(mb, pe.y5_pop3.values, strata_id[ok], cyc[ok], 80); lo, hi = int(np.min(mb)), int(np.max(mb)) + 1; r = bh.run(lo, hi, minrows, perms, None, gid[ok])
    rows_out.append(dict(test_id='H4b-MTM', hypothesis='H4 portfolio-level (cycle mark-to-market) condition', convention='AVG basis', events=len(S), rows=int(ok.sum()), cycles=int(S.cycle.nunique()), statistic=f'max controlled hazard ratio over Rs {step:,} mark-to-market bins', observed=r['max_ratio'],
                         best_bin_pct=(r['best_bin'] - 40) * step, ci_lo=r['ci_lo'], ci_hi=r['ci_hi'], perm_p=r['perm_p'], ratio_nifty=np.nan, ratio_sensex=np.nan, cycles_with_effect=''))
    curves.append(pd.DataFrame({'test': 'H4b-MTM', 'bin_lo_pct': (np.arange(80) - 40) * step, 'rows': r['rows'], 'std_hazard': r['std'], 'ratio_vs_neighbours': r['curve']}))
    # ---------------- H2a: 15-minute grid. Statistic = MAX over the 15 minute-of-hour residues (mod 15) of the controlled closing hazard (residue vs the other residues);
    # the residue is NOT pre-selected, so the permutation p-value is corrected for the choice of residue.
    res = ((555 + panel.tod_min) % 15).values; y = panel.y1_pop3.values; G = gid.max() + 1
    def res_ratios(yy, wr=None, mask=None):
        out = np.full(15, np.nan); w_ = np.ones(len(yy)) if wr is None else wr
        if mask is not None: w_ = w_ * mask
        kk = np.bincount(gid, weights=yy * w_, minlength=G); nn = np.bincount(gid, weights=w_, minlength=G)
        for r_ in range(15):
            sel = res == r_; k1 = np.bincount(gid[sel], weights=(yy * w_)[sel], minlength=G); n1 = np.bincount(gid[sel], weights=w_[sel], minlength=G); k0 = kk - k1; n0 = nn - n1
            ok_ = (n1 >= 5) & (n0 >= 5); den = (n1[ok_] * (k0[ok_] / n0[ok_])).sum(); out[r_] = k1[ok_].sum() / den if den > 0 else np.nan
        return out
    rr = res_ratios(y); obs = np.nanmax(rr); arg = int(np.nanargmax(rr)); mxp = np.empty(perms); rng = np.random.default_rng(CFG['inference']['seed'] + 2)
    for p in range(perms): idx = np.lexsort((rng.random(len(y)), gid)); mxp[p] = np.nanmax(res_ratios(y[idx]))
    pval = (1 + (mxp >= obs).sum()) / (perms + 1)
    w = RNG.multinomial(len(cyc_names), np.ones(len(cyc_names)) / len(cyc_names), size=NB).astype(float); bs = [res_ratios(y, w[k][cyc])[arg] for k in range(NB)]
    pu = {u: res_ratios(y, None, (panel.und == u).values.astype(float))[arg] for u in ('NIFTY', 'SENSEX')}
    cy_eff = cy_tot = 0
    for ci in range(len(cyc_names)):
        v_ = res_ratios(y, None, (cyc == ci).astype(float))[arg]
        if np.isfinite(v_): cy_tot += 1; cy_eff += int(v_ > 1)
    pd.DataFrame({'residue_minute_of_15': np.arange(15), 'controlled_hazard_ratio': rr}).to_csv(os.path.join(A, 'h2a_residue_ratios.csv'), index=False)
    rows_out.append(dict(test_id='H2a-grid', hypothesis='H2 scheduled harvesting: minute-of-hour residue mod 15 (max over 15 residues)', convention='convention-free', events=len(S), rows=len(panel), cycles=int(S.cycle.nunique()), statistic=f'max over 15 residues of the controlled closing hazard (argmax residue {arg})', observed=obs, best_bin_pct=arg,
                         ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5), perm_p=pval, ratio_nifty=pu['NIFTY'], ratio_sensex=pu['SENSEX'], cycles_with_effect=f'{cy_eff}/{cy_tot}'))
    # ---------------- H2b: holding time modulo 15 minutes (per-leg timer). Two readings: (i) any concentration (Rayleigh) and (ii) a timer anchored at entry (phase ~ 0, within 10 s of a multiple)
    pc = P[(P.row_type == 'CLOSED') & (P.direction == -1)]; hist = []
    for m in ('FIFO', 'LIFO'):
        q = pc[pc.method == m].merge(S[['close_row', 'cycle']], on='close_row'); q = q[q.qty == q.und.map(c.LOT)]
        hold = (q.exit_epoch - q.entry_epoch).values; ang = 2 * np.pi * (hold % 900) / 900; Z = np.exp(1j * ang).mean(); Rv = np.abs(Z); phase_s = (np.angle(Z) % (2 * np.pi)) / (2 * np.pi) * 900
        rng = np.random.default_rng(CFG['inference']['seed'] + 3); null = []
        for p in range(perms):
            sh = rng.integers(1800, 3600, len(hold)) * rng.choice([-1, 1], len(hold)); null.append(np.abs(np.exp(1j * 2 * np.pi * (((hold + sh) % 900) / 900)).mean()))
        pc_ = (1 + (np.array(null) >= Rv).sum()) / (perms + 1); share10 = ((hold % 900 <= 10) | (hold % 900 >= 890)).mean(); h_ = np.histogram(hold % 900, bins=15, range=(0, 900))[0]
        hist.append(pd.DataFrame({'convention': m, 'phase_bin_start_s': np.arange(0, 900, 60), 'closings': h_, 'share': h_ / h_.sum()}))
        rows_out.append(dict(test_id=f'H2b-timer-{m}', hypothesis='H2 per-leg 15-minute timer (holding time mod 900 s)', convention=m, events=len(q), rows=len(q), cycles=int(q.cycle.nunique()),
                             statistic=f'Rayleigh concentration of hold mod 900 s (circular mean phase {phase_s:.0f} s; share within 10 s of a multiple {share10:.3f} vs 0.023 chance)', observed=Rv, best_bin_pct=phase_s, ci_lo=np.percentile(null, 2.5), ci_hi=np.percentile(null, 97.5), perm_p=pc_, ratio_nifty=share10, ratio_sensex=np.nan, cycles_with_effect=''))
    pd.concat(hist).to_csv(os.path.join(A, 'h2b_hold_mod15_histogram.csv'), index=False)
    # ---------------- H5: market state, event minutes vs exposed non-event minutes (percentile rank inside strata)
    permsH5 = ET['permutations_h5']; ev = panel.y5_pop3.values.astype(bool)
    for f in HZ['H5_market']['features']:
        v = panel[f].values; ok = np.isfinite(v); pct = np.full(len(v), np.nan)
        d = pd.DataFrame({'g': gid[ok], 'v': v[ok]}); d['pct'] = d.groupby('g').v.rank(pct=True); pct[ok] = d.pct.values
        yy = ev[ok]; pp = pct[ok]; gg = gid[ok]; cc = cyc[ok]
        def stat(lbl): return (pp[lbl] - 0.5).mean() if lbl.any() else 0
        obs = stat(yy); auc = 0.5 + obs / max(1 - yy.mean(), 1e-9) * 0.5 if False else None
        # stratified AUC (pooled Mann-Whitney) for reporting
        rk = pd.DataFrame({'g': gg, 'v': v[ok], 'y': yy}); rk['r'] = rk.groupby('g').v.rank(); U = []; n1 = rk.groupby('g').y.sum(); n0 = rk.groupby('g').y.apply(lambda s: (~s).sum()); sr = rk[rk.y].groupby('g').r.sum()
        Ug = (sr.reindex(n1.index).fillna(0) - n1 * (n1 + 1) / 2); okg = (n1 > 0) & (n0 > 0); auc = float(Ug[okg].sum() / (n1[okg] * n0[okg]).sum())
        mxs = np.empty(permsH5); rng = np.random.default_rng(CFG['inference']['seed'] + 4); order = np.argsort(gg, kind='stable'); gs = gg[order]; ys = yy[order]; ps = pp[order]
        for p in range(permsH5):
            idx = np.lexsort((rng.random(len(gs)), gs)); mxs[p] = (ps[ys[idx]] - 0.5).mean()
        pval = (1 + (np.abs(mxs) >= abs((ps[ys] - 0.5).mean())).sum()) / (permsH5 + 1)
        # cycle bootstrap of the pooled AUC
        cu = pd.DataFrame({'c': cc[okg.reindex(gg).values] if False else cc}); sub = rk.assign(c=cc); sub['n1'] = sub.g.map(n1); sub['n0'] = sub.g.map(n0); Uc = (sub[sub.y].groupby('c').r.sum() - 0).reindex(range(len(cyc_names))).fillna(0)
        per = pd.DataFrame({'g': gg, 'c': cc, 'y': yy}).drop_duplicates('g').set_index('g').c; Ug2 = Ug[okg]; den = (n1[okg] * n0[okg]); cyc_of_g = per.reindex(Ug2.index)
        num_c = Ug2.groupby(cyc_of_g.values).sum().reindex(range(len(cyc_names))).fillna(0).values; den_c = den.groupby(cyc_of_g.values).sum().reindex(range(len(cyc_names))).fillna(0).values
        w = RNG.multinomial(len(cyc_names), np.ones(len(cyc_names)) / len(cyc_names), size=NB).astype(float); bsu = (w @ num_c) / np.maximum(w @ den_c, 1e-9)
        un = {}
        for u in ('NIFTY', 'SENSEX'):
            mu = (panel.und.values[ok] == u); un[u] = auc_simple(v[ok][mu], yy[mu], gg[mu])
        cy_eff = 0; cy_tot = 0
        for ci in range(len(cyc_names)):
            m_ = cc == ci
            if yy[m_].sum() >= 10 and (~yy[m_]).sum() >= 10: cy_tot += 1; cy_eff += int(auc_simple(v[ok][m_], yy[m_], gg[m_]) != 0.5 and (auc_simple(v[ok][m_], yy[m_], gg[m_]) - 0.5) * (auc - 0.5) > 0)
        rows_out.append(dict(test_id=f'H5-{f}', hypothesis='H5 market-state exit', convention='convention-free', events=len(S), rows=int(ok.sum()), cycles=int(S.cycle.nunique()), statistic='stratified AUC, event minutes vs exposed non-event minutes', observed=auc, best_bin_pct=np.nan,
                             ci_lo=np.percentile(bsu, 2.5), ci_hi=np.percentile(bsu, 97.5), perm_p=pval, ratio_nifty=un['NIFTY'], ratio_sensex=un['SENSEX'], cycles_with_effect=f'{cy_eff}/{cy_tot}'))
    # ---------------- H3 / H4a / H6: excess over a time-shift chance baseline among Pop 3
    from analyze_mechanisms import Null
    null = Null(L, R); shifts = CFG['replacement']['null_shifts_seconds']
    def excess_test(name, hyp, obs_flag, null_rate, stat_txt):
        d = S.assign(o=obs_flag.astype(float), n=null_rate); g = d.groupby('cycle').agg(o=('o', 'sum'), n=('n', 'sum'), k=('o', 'size')); cn = g.index.values
        w = RNG.multinomial(len(cn), np.ones(len(cn)) / len(cn), size=NB).astype(float); ex = (w @ g.o.values - w @ g.n.values) / (w @ g.k.values)
        pu = {u: (d[d.und == u].o.mean() - d[d.und == u].n.mean()) for u in ('NIFTY', 'SENSEX')}; per = (g.o / g.k > g.n / g.k).mean()
        rows_out.append(dict(test_id=name, hypothesis=hyp, convention='convention-free', events=len(d), rows=len(d), cycles=len(cn), statistic=stat_txt, observed=d.o.mean() - d.n.mean(), best_bin_pct=d.o.mean(), ci_lo=np.percentile(ex, 2.5), ci_hi=np.percentile(ex, 97.5),
                             perm_p=float((ex <= 0).mean() * 2 if False else max((ex <= 0).mean(), 1 / (NB + 1))), ratio_nifty=pu['NIFTY'], ratio_sensex=pu['SENSEX'], cycles_with_effect=f'{int((g.o > g.n).sum())}/{len(cn)}'))
    rates = null.rates.__self__ if False else None
    # per-event chance rates by shifting (recompute event-wise)
    def event_null(kind):
        out = np.zeros(len(S)); cnt = np.zeros(len(S)); rw = CFG['replacement']['window_seconds']; ww = CFG['wing']['link_window_seconds']; bw = CFG['basket']['window_seconds']; pos = {k: i for i, k in enumerate(S.close_row.values)}
        for u, g in S.groupby('und'):
            os_, cl, cs = null.OS[u], null.CL[u], null.CS[u]; eo, ec, es = os_.epoch.values, cl.epoch.values, cs.epoch.values
            for sh in shifts:
                t = g.epoch.values + sh; tod = (t - g.epoch.values + (g.t_exec - g.date).dt.total_seconds().values) // 60 - 555
                for i in np.where((tod >= 0) & (tod < 375))[0]:
                    r = g.iloc[i]; ti = t[i]; j = pos[r.close_row]; cnt[j] += 1
                    if kind == 'replacement': s = os_.iloc[np.searchsorted(eo, ti, 'right'):np.searchsorted(eo, ti + rw, 'right')]; out[j] += bool(((s.cp == r.cp) & (s.parent_oid != r.parent_oid)).any())
                    elif kind == 'basket': s = cs.iloc[np.searchsorted(es, ti - bw, 'left'):np.searchsorted(es, ti + bw, 'right')]; s = s[(s.parent_oid != r.parent_oid) & (s.contract_id != r.contract_id)]; out[j] += s.contract_id.nunique() >= CFG['basket']['min_other_contracts']
                    elif kind == 'readd':
                        s = os_.iloc[np.searchsorted(eo, ti, 'right'):np.searchsorted(eo, ti + HZ['H3_reduction']['rebuild_window_seconds'], 'right')]; out[j] += bool(((s.contract_id == r.contract_id) & (s.parent_oid != r.parent_oid)).any())
        return out / np.maximum(cnt, 1)
    excess_test('H6-replacement', 'H6 replacement-related realisation', S.flag_replacement.values, event_null('replacement'), 'share of Pop 3 closings with a same-right opening short within 60 s minus time-shift chance rate')
    excess_test('H4a-basket', 'H4 basket-level (simultaneous multi-contract closings)', S.flag_basket.values, event_null('basket'), 'share with >= 2 other contracts closed within +-5 s minus time-shift chance rate')
    excess_test('H3-readd', 'H3 position-level reduction (re-add within 300 s)', (S[f'n_O_short_same_contract_next{HZ["H3_reduction"]["rebuild_window_seconds"]}s'] > 0).values, event_null('readd'), 'share followed by a new short opening in the same contract within 300 s minus time-shift chance rate')
    # ---------------- Holm and verdicts
    Tst = pd.DataFrame(rows_out); Tst['holm_p'] = holm(Tst.perm_p.values)
    def eff(r):
        o = r.observed; t = r.test_id
        if t.startswith('H5'): return (o >= ET['auc_effect_present'] or o <= 1 - ET['auc_effect_present']), (ET['auc_not_supported_band'][0] <= o <= ET['auc_not_supported_band'][1])
        if t.startswith(('H3', 'H4a', 'H6')): return o >= ET['excess_effect_present'], o < 0.05
        if t.startswith('H2b'): return r.perm_p < 0.05 and r.observed >= 0.10, r.perm_p >= 0.2        # NOT in the registered config: R >= 0.10 is more than 3x the null 97.5th percentile (stated in the report)
        return (o >= rt or o <= 1 / rt), (nsb[0] <= o <= nsb[1])
    out = []
    for _, r in Tst.iterrows():
        e, ns = eff(r); conv_ok = True; und_ok = all((x >= rt if not r.test_id.startswith('H5') else abs(x - 0.5) >= 0.05) if np.isfinite(x) else True for x in (r.ratio_nifty, r.ratio_sensex)) if not r.test_id.startswith(('H3', 'H4a', 'H6')) else all(x >= 0.05 for x in (r.ratio_nifty, r.ratio_sensex))
        cs = r.cycles_with_effect; share = (int(cs.split('/')[0]) / max(int(cs.split('/')[1]), 1)) if isinstance(cs, str) and '/' in cs else 1.0
        out.append(verdict(r.events, r.cycles, conv_ok, und_ok, share, r.holm_p, e, ns))
    Tst['effect_present_rule'] = [eff(r)[0] for _, r in Tst.iterrows()]; Tst['verdict'] = out
    # convention sensitivity: H1 verdict must hold for all three conventions
    h1 = Tst[Tst.test_id.str.startswith('H1-')]; allc = (h1.verdict == 'SUPPORTED').all()
    Tst.loc[Tst.test_id.str.startswith('H1-') & ~allc, 'verdict'] = Tst.loc[Tst.test_id.str.startswith('H1-') & ~allc, 'verdict'].replace({'SUPPORTED': 'PARTIAL'})
    Tst.to_csv(os.path.join(A, 'hypothesis_tests.csv'), index=False); pd.concat(curves).to_csv(os.path.join(A, 'hypothesis_curves.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60); print(Tst.drop(columns=['hypothesis', 'statistic']).round(3).to_string(index=False))


def auc_simple(v, y, g):
    d = pd.DataFrame({'g': g, 'v': v, 'y': y}); d['r'] = d.groupby('g').v.rank(); n1 = d.groupby('g').y.sum(); n0 = d.groupby('g').y.apply(lambda s: (~s).sum()); sr = d[d.y].groupby('g').r.sum()
    U = sr.reindex(n1.index).fillna(0) - n1 * (n1 + 1) / 2; ok = (n1 > 0) & (n0 > 0)
    return float(U[ok].sum() / (n1[ok] * n0[ok]).sum()) if ok.any() else 0.5


if __name__ == '__main__':
    main()
