"""MODE 1 (teacher-forced, component-isolated). Everything original is taken as given (actual book, actual market); ONE component's rule is evaluated and compared with the omitted original behaviour.
Hypotheses and falsifiers are pre-registered in EXECUTION_PARITY_METHODOLOGY.md section 7. All results are IN-SAMPLE. Outputs -> outputs/mode1_*.csv"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import ref, compare as C
sys.path.insert(0, ref.REPL)
import data, rules as R
from bt import cycles as Cy
F = ref.load_fills(); O = ref.orders(F); cyc = pd.read_csv(ref.CYCLES); cl = Cy.cycle_list(); NM = 375; STEP = ref.STEP; rng = np.random.default_rng(5)
O['jc'] = O.j.clip(0, 374)


class Mkt:
    def __init__(self, und, exp):
        m = cl[(cl.und == und) & (cl.expiry == exp)].iloc[0]; self.c = data.load_cycle(und, exp, m.d1, m.d0); self.und = und; self.strikes = self.c['strikes']; self.si = {int(k): i for i, k in enumerate(self.strikes)}; self.px = {}
        for d in (0, 1):
            for r in ('CE', 'PE'):
                a = np.array(self.c[(d, r, 'close')], float)
                for j in range(1, a.shape[1]):
                    mm = np.isnan(a[:, j]); a[mm, j] = a[mm, j - 1]
                self.px[(d, r)] = a
    def spot_prev(self, d, j):
        s = self.c[(d, 'spot')]
        return s[j - 1] if j > 0 else (self.c[(0, 'spot')][NM - 1] if d == 1 else np.nan)
    def open_px(self, d, r, strike, j):
        i = self.si.get(int(strike))
        if i is None: return np.nan
        o = self.c[(d, r, 'open')][i, j]; return o if o == o else self.prev_close(d, r, strike, j)
    def same_close(self, d, r, strike, j):
        i = self.si.get(int(strike)); return np.nan if i is None else self.px[(d, r)][i, j]
    def prev_close(self, d, r, strike, j):
        i = self.si.get(int(strike))
        if i is None: return np.nan
        if j > 0: return self.px[(d, r)][i, j - 1]
        return self.px[(0, r)][i, NM - 1] if d == 1 else np.nan


MK = {}
for r in cyc.itertuples():
    try: MK[(r.und, r.expiry)] = Mkt(r.und, r.expiry)
    except Exception as e: print('no market data', r.und, r.expiry, e)
HAS = {(r.und, r.expiry): (bool(r.has_d1), bool(r.has_d0), bool(r.carry_in_known)) for r in cyc.itertuples()}
out = {}
# ------------------------------------------------------------------ H-STK strike selection (given the actual decision minute)
b = O[(O.module == 'num') & (O.side == 'Sell')].copy(); b = b[[(HAS[(u, e)][0] if d == 0 else HAS[(u, e)][1]) and (u, e) in MK for u, e, d in zip(b.und, b.expiry, b.dayno)]]
b['slot'] = (b.jc - 1) // 15; b['ladder_win'] = (b.dayno == 0) & (((b.jc - 1) % 15) < 3) & (b.slot < 17) & (b.jc >= 1)           # D-1, the 17 ladder slots, first 3 minutes of each (review MEDIUM-1)
b['sched'] = b.ladder_win; b['d0_minute0'] = (b.dayno == 1) & (b.jc == 0)
def ruleK(und, d, j):
    S = MK[(und, exp_)].spot_prev(d, j); return np.nan if S != S else STEP[und] * np.floor(S / STEP[und] + 0.5)
rows = []
for r in b.itertuples():
    mk = MK[(r.und, r.expiry)]; S = mk.spot_prev(r.dayno, r.jc); k = STEP[r.und] * np.floor(S / STEP[r.und] + 0.5) if S == S else np.nan
    sh = int(rng.integers(2, 9)) * 15 * int(rng.choice([-1, 1])); jn = int(np.mod(r.jc + sh, NM)); Sn = mk.spot_prev(r.dayno, jn); kn = STEP[r.und] * np.floor(Sn / STEP[r.und] + 0.5) if Sn == Sn else np.nan
    rows.append(dict(und=r.und, expiry=r.expiry, day=r.dayno, sched=r.sched, d0_minute0=r.d0_minute0, lots=r.lots, err=(r.strike - k) / STEP[r.und] if k == k else np.nan, err_null=(r.strike - kn) / STEP[r.und] if kn == kn else np.nan))
H = pd.DataFrame(rows).dropna(subset=['err']); H.to_csv(f'{ref.OUT}/mode1_strike_errors.csv', index=False)
def sk(x, w=None): return dict(n=len(x), exact=float((x.err == 0).mean()), within1=float((x.err.abs() <= 1).mean()), null_exact=float((x.err_null == 0).mean()), null_within1=float((x.err_null.abs() <= 1).mean()), mean_signed=float(x.err.mean()))
srows = []
for nm, sel in (('all body sells', H), ('D-1', H[H.day == 0]), ('D0', H[H.day == 1]), ('D-1 ladder windows (17 slots, first 3 min)', H[H.sched]), ('D-1 other', H[(H.day == 0) & ~H.sched]), ('D0 minute 0 (previous-day close is the last completed bar)', H[H.d0_minute0]), ('D0 excluding minute 0', H[(H.day == 1) & ~H.d0_minute0]), ('NIFTY', H[H.und == 'NIFTY']), ('SENSEX', H[H.und == 'SENSEX'])): srows.append(dict(subset=nm, **sk(sel)))
print('H-STK orders dropped for NaN spot:', len(b) - len(H), 'of', len(b))
pd.DataFrame(srows).to_csv(f'{ref.OUT}/mode1_strike_summary.csv', index=False); out['strike'] = pd.DataFrame(srows)
# ------------------------------------------------------------------ H-QTY quantity per slot-leg on D-1 (R1 ladder), actual lots in the first 3 minutes of each slot
q = O[(O.module == 'num') & (O.side == 'Sell') & (O.dayno == 0)].copy(); q = q[[HAS[(u, e)][0] for u, e in zip(q.und, q.expiry)]]; q['k'] = (q.jc - 1) // 15; q['off'] = (q.jc - 1) % 15; q = q[(q.off < 3) & (q.k >= 0) & (q.k < 17)]
qa = q.groupby(['und', 'expiry', 'k', 'cp']).lots.sum().rename('actual').reset_index(); full = []
for (u, e), ok in [((r.und, r.expiry), r.has_d1) for r in cyc.itertuples()]:
    if not ok: continue
    for k in range(17):
        for cp in ('CE', 'PE'): full.append((u, e, k, cp))
full = pd.DataFrame(full, columns=['und', 'expiry', 'k', 'cp']).merge(qa, how='left', on=['und', 'expiry', 'k', 'cp']).fillna({'actual': 0}); lad = np.array(R.LADDER_D1)
full['rule'] = lad[full.k.values]; exact = float((full.actual == full.rule).mean()); mae = float((full.actual - full.rule).abs().mean())
null = []
for _ in range(300):
    p = rng.permutation(lad); null.append(float((full.actual == p[full.k.values]).mean()))
modal = full.groupby('k').actual.agg(lambda s: s.mode().iloc[0]); share_mode = float((full.actual == modal.reindex(full.k).values).mean())
loco = []
for (u_, e_), g_ in full.groupby(['und', 'expiry']):
    rest = full[~((full.und == u_) & (full.expiry == e_))]; md_ = rest.groupby('k').actual.agg(lambda t: t.mode().iloc[0]); loco.append(((g_.actual == md_.reindex(g_.k).values).sum(), len(g_)))
loco_exact = sum(a for a, _ in loco) / sum(b_ for _, b_ in loco); nz = full[(full.actual > 0) | (full.rule > 0)]; exact_nz = float((nz.actual == nz.rule).mean())
Q = pd.DataFrame([dict(exact_leave_one_cycle_out=loco_exact, exact_nonzero_cells=exact_nz, zero_zero_cells=int(((full.actual == 0) & (full.rule == 0)).sum()), n_slot_legs=len(full), exact_vs_R1_ladder=exact, mae_lots=mae, null_exact_mean=float(np.mean(null)), null_exact_p95=float(np.quantile(null, .95)), exact_vs_own_window_mode=share_mode, actual_mean_lots=float(full.actual.mean()), rule_mean_lots=float(full.rule.mean()))]); Q.to_csv(f'{ref.OUT}/mode1_quantity_summary.csv', index=False); full.to_csv(f'{ref.OUT}/mode1_quantity_slotlegs.csv', index=False); out['qty'] = Q
# ------------------------------------------------------------------ H-WNG wing selection given the actual body order (partner = h_ Buy same right within 15 s, one-to-one nearest)
wrows = []
for (u, e), mk in MK.items():
    for d in (0, 1):
        if not (HAS[(u, e)][0] if d == 0 else HAS[(u, e)][1]): continue
        bd = O[(O.und == u) & (O.expiry == e) & (O.dayno == d) & (O.module == 'num') & (O.side == 'Sell')].sort_values('sec'); wg = O[(O.und == u) & (O.expiry == e) & (O.dayno == d) & (O.module == 'h_') & (O.side == 'Buy')]
        used = set(); pool = {}
        for r in bd.itertuples():
            cand = wg[(wg.cp == r.cp) & (~wg.tag.isin(used)) & ((wg.sec - r.sec).abs() <= 15)]
            si = mk.si.get(int(r.strike)); bp = mk.prev_close(d, r.cp, r.strike, r.jc) if si is not None else np.nan
            if si is None or bp != bp: continue
            wi = R.wing_strike_index(mk.strikes, r.cp, si, bp, lambda i: mk.px[(d, r.cp)][i, r.jc - 1] if r.jc > 0 else np.nan)
            pool.setdefault((d, r.cp), []).append((si, bp, wi))
            if len(cand) == 0: wrows.append(dict(und=u, expiry=e, day=d, partner=False)); continue
            w = cand.iloc[(cand.sec - r.sec).abs().argmin()]; used.add(w.tag)
            wrows.append(dict(und=u, expiry=e, day=d, partner=True, cp=r.cp, body_strike=r.strike, wing_strike=int(w.strike), rule_strike=int(mk.strikes[wi]) if wi is not None else np.nan, err=(int(w.strike) - int(mk.strikes[wi])) / STEP[u] if wi is not None else np.nan, wing_px=w.px, body_px=bp, ratio=w.px / bp if bp else np.nan, idx_in_pool=len(pool[(d, r.cp)]) - 1))
W = pd.DataFrame(wrows); P = W[W.partner].dropna(subset=['err']).copy()
# null: apply the rule's wing strike of a RANDOM OTHER body of the same right to this wing
nn = []
for g in P.groupby(['und', 'expiry', 'cp']):
    x = g[1]; rs = x.rule_strike.values
    if len(x) > 1: nn.extend(list((x.wing_strike.values == rng.permutation(rs)).astype(float)))
Wsum = pd.DataFrame([dict(body_orders=len(W), with_wing_partner=int(W.partner.sum()), partner_share=float(W.partner.mean()), compared=len(P), exact=float((P.err == 0).mean()), within1=float((P.err.abs() <= 1).mean()), within2=float((P.err.abs() <= 2).mean()), null_exact=float(np.mean(nn)) if nn else np.nan, median_wing_to_body_price_ratio=float(P.ratio.median()), mean_signed_err_steps=float(P.err.mean()))]); Wsum.to_csv(f'{ref.OUT}/mode1_wing_summary.csv', index=False); P.to_csv(f'{ref.OUT}/mode1_wing_pairs.csv', index=False); out['wing'] = Wsum
# ------------------------------------------------------------------ H-CYC cycle stop: MTM trigger vs actual s_ module liquidation (30 complete cycles)
def mtm_series(u, e, mark='prev'):
    mk = MK[(u, e)]; g = F[(F.und == u) & (F.expiry == e) & (F.module != 's_')].sort_values(['t', 'row']); lotu = ref.LOT[u]; T = 2 * NM; cash = np.zeros(T); keys = {}; pos = {}
    for r in g.itertuples():
        t = r.dayno * NM + int(np.clip(r.jc if hasattr(r, 'jc') else r.j, 0, NM - 1)); cash[t:] += -r.sgn * r.n_lots * lotu * r.px; keys.setdefault((r.cp, r.strike), np.zeros(T)); keys[(r.cp, r.strike)][t:] += r.sgn_lots
    mtm = cash.copy(); missing = 0
    for (cp, k), net in keys.items():
        i = mk.si.get(int(k))
        if i is None: missing += 1; continue
        for d in (0, 1):
            for j in range(NM):
                t = d * NM + j; p = mk.prev_close(d, cp, k, j) if mark == 'prev' else (mk.open_px(d, cp, k, j) if mark == 'open' else mk.same_close(d, cp, k, j)); p = 0.0 if p != p else p
                # decision at the START of minute (d, j): positions after fills of previous minutes, LTP = previous completed close
                n_prev = net[t - 1] if t > 0 else 0.0; mtm[t] += n_prev * lotu * p
    # cash must also be as of the start of the minute: shift by one minute
    cash_prev = np.concatenate([[0.0], cash[:-1]]); mtm = cash_prev + (mtm - cash)
    return mtm, missing
stops = F[F.module == 's_'].groupby(['und', 'expiry']).agg(sec_first=('sec', 'min'), day_first=('dayno', 'min'), j_first=('j', 'min')).reset_index(); stops['t_first'] = stops.day_first * NM + stops.j_first.clip(0, 374)
crow = []; Ls = (130000.0, 135000.0, 144000.0); MARKS = ('prev', 'open', 'same')
for r in cyc[cyc.carry_in_known].itertuples():
    if (r.und, r.expiry) not in MK: continue
    s_ = stops[(stops.und == r.und) & (stops.expiry == r.expiry)]; act = len(s_) > 0; ta = int(s_.t_first.iloc[0]) if act else None
    for mark in MARKS:
        mt, miss = mtm_series(r.und, r.expiry, mark); lim = (ta + 1) if act else len(mt)                  # window INCLUDES the decision minute of the first actual s_ order (review HIGH-1); before it the book is the actual book
        row = dict(mark=mark, und=r.und, expiry=r.expiry, actual_stop=act, actual_t=ta, min_mtm_before_stop=float(np.nanmin(mt[:lim])) if lim > 0 else np.nan, min_mtm_before_decision_minute=float(np.nanmin(mt[:ta])) if act and ta else np.nan, mtm_at_stop_decision=float(mt[ta]) if act and ta is not None and ta < len(mt) else np.nan, contracts_without_market=miss)
        for L in Ls:
            fb = C.first_breach(mt, L, lim - 1); row[f'trig_{int(L)}'] = fb is not None; row[f'trig_t_{int(L)}'] = fb
        crow.append(row)
CY = pd.DataFrame(crow); CY.to_csv(f'{ref.OUT}/mode1_cycle_stop.csv', index=False)
cs = []
for mark in MARKS:
    X = CY[CY.mark == mark]
    for L in Ls:
        tp = int((X.actual_stop & X[f'trig_{int(L)}']).sum()); fp = int((~X.actual_stop & X[f'trig_{int(L)}']).sum()); fn = int((X.actual_stop & ~X[f'trig_{int(L)}']).sum()); tn = int((~X.actual_stop & ~X[f'trig_{int(L)}']).sum())
        d = X[X.actual_stop & X[f'trig_{int(L)}']]; te = (d[f'trig_t_{int(L)}'].astype(float) - d.actual_t.astype(float)); cs.append(dict(mark=mark + {'prev': ' (causal, primary)', 'open': ' (open of the decision minute: known at the start of the minute, usable only if the decision is taken after its first print)', 'same': ' (NON-causal diagnostic: includes the decision minute close)'}[mark], L_rupees=L, cycles=len(X), actual_stop_cycles=int(X.actual_stop.sum()), TP=tp, FP=fp, FN=fn, TN=tn, precision=tp / (tp + fp) if tp + fp else np.nan, recall=tp / (tp + fn) if tp + fn else np.nan, timing_err_min_median=float(te.median()) if len(te) else np.nan, within_2min=int((te.abs() <= 2).sum())))
CS = pd.DataFrame(cs); CS.to_csv(f'{ref.OUT}/mode1_cycle_stop_summary.csv', index=False); out['cyc'] = CS
# ------------------------------------------------------------------ H-FLAT final flatten at 15:14 (minute index 359) on D0, split at the 2026-08-03 cut-over
frows = []
def short_lots(g, mask, basis):
    x = g[mask]
    if basis == 'body': x = x[x.module == 'num']
    n = x.groupby(['cp', 'strike']).sgn_lots.sum(); return int((-n[n < 0]).sum()), n
for r in cyc[cyc.has_d0].itertuples():
    g = F[(F.und == r.und) & (F.expiry == r.expiry)].sort_values(['t', 'row']); row = dict(und=r.und, expiry=r.expiry, post_cutover=r.expiry >= '2026-08-03')
    for basis in ('all', 'body'):
        b13, _ = short_lots(g, (g.dayno == 0) | (g.j <= 358), basis); b14, _ = short_lots(g, (g.dayno == 0) | (g.j <= 359), basis); bend, _ = short_lots(g, g.j > -999, basis)
        row.update({f'short_lots_1513_{basis}': b13, f'short_lots_1514_{basis}': b14, f'short_lots_end_{basis}': bend, f'remaining_share_1514_{basis}': (b14 / b13) if b13 else np.nan})
    row['body_buy_lots_in_1514'] = int(g[(g.dayno == 1) & (g.j == 359) & (g.side == 'Buy') & (g.module == 'num')].n_lots.sum()); frows.append(row)
FL = pd.DataFrame(frows); _p = FL[FL.post_cutover & (FL.short_lots_1513_all > 0)]; print('H-FLAT pre-registered falsifier: share of 15:13 shorts still short after 15:14 (post-cutover):', round(_p.short_lots_1514_all.sum() / _p.short_lots_1513_all.sum(), 4), '(falsified only if > 0.5)'); FL.to_csv(f'{ref.OUT}/mode1_final_flatten.csv', index=False); out['flat'] = FL
# ------------------------------------------------------------------ H-CARRY: share of the 15:13 short book still short at the end of the ledger, by distance from the D0 spot at 15:13. Two bases (they disagree: see DISCREPANCY_REGISTER)
crw = []
for r in cyc[cyc.has_d0].itertuples():
    if (r.und, r.expiry) not in MK: continue
    mk = MK[(r.und, r.expiry)]; S = mk.c[(1, 'spot')]; Sx = S[358] if not np.isnan(S[358]) else np.nan
    for basis in ('contract (all modules, ownership/role-free)', 'body-module role basis (assumes num fills touch only body inventory)'):
        g = F[(F.und == r.und) & (F.expiry == r.expiry)]; g = g if basis.startswith('contract') else g[g.module == 'num']
        net13 = g[(g.dayno == 0) | (g.j <= 358)].groupby(['cp', 'strike']).sgn_lots.sum(); netE = g.groupby(['cp', 'strike']).sgn_lots.sum()
        for (cp, k), n in net13.items():
            if n < 0: crw.append(dict(basis=basis, und=r.und, expiry=r.expiry, post_cutover=r.expiry >= '2026-08-03', cp=cp, strike=k, short_lots=-n, still_short=min(max(-netE.get((cp, k), 0), 0), -n), dist_steps=abs(k - Sx) / STEP[r.und]))
CR = pd.DataFrame(crw); CR['bin'] = pd.cut(CR.dist_steps, [-1, 0.5, 1.5, 3, 6, 1e9], labels=['<=0.5', '0.5-1.5', '1.5-3', '3-6', '>6'])
def carry_tab(d): return d.groupby('bin', observed=True).apply(lambda x: pd.Series(dict(contracts=len(x), short_lots_1513=int(x.short_lots.sum()), still_short_at_end=int(x.still_short.sum()), carried_share=float(x.still_short.sum() / x.short_lots.sum())))).reset_index()
CRs = pd.concat([carry_tab(CR[CR.basis == bs]).assign(basis=bs, subset=sn) for bs in CR.basis.unique() for sn, sel in (('all D0', CR.basis == bs), ('post 2026-08-03', (CR.basis == bs) & CR.post_cutover), ('pre 2026-08-03', (CR.basis == bs) & ~CR.post_cutover)) for _ in [0] if True for CRsel in [CR[sel]] if len(CRsel)] if False else [carry_tab(CR[(CR.basis == bs) & m]).assign(basis=bs, subset=sn) for bs in CR.basis.unique() for sn, m in (('all D0', CR.und.notna()), ('post 2026-08-03', CR.post_cutover), ('pre 2026-08-03', ~CR.post_cutover))])
CRs.to_csv(f'{ref.OUT}/mode1_carry_by_distance.csv', index=False); out['carry'] = CRs
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
for k, v in out.items(): print('==', k); print(v.round(3).to_string(index=False) if hasattr(v, 'round') else v)
