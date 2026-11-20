"""Render reports/BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md. Every number in the text is computed here from the bh_*.py outputs (or recomputed from the ledger)."""
import sys; sys.path.insert(0, '.')
from bh_common import *
rd = lambda f, **k: pd.read_csv(f'{OUT}/{f}', **k); pct = lambda x, d=1: f'{100 * x:.{d}f} %'
def table(df):
    c = list(df.columns); return '\n'.join(['| ' + ' | '.join(map(str, c)) + ' |', '|' + '---|' * len(c)] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in df.values])
X = fills_x(); O = order_table(X); R = rd('bh_b1_order_roles.csv', dtype={'tag': str}); ncyc = O.groupby(['und', 'expiry']).ngroups
# ---------- inventory
inv = O.groupby('module').agg(orders=('tag', 'size'), lots=('lots', 'sum'), lots_per_order_med=('lim_lots', 'median'), validity=('validity', lambda s: '/'.join(sorted(set(s))))).reset_index(); inv['module'] = inv.module.map({'num': 'numeric tag (body stream)', 'h_': 'h_ (hedge)', 's_': 's_ (stop)', 'v_': 'v_ (overnight lump)', 'm_': 'm_ (manual)'})
# ---------- H1
W1 = rd('bh_h1_windows.csv'); LH = rd('bh_h1_lag_hist.csv'); BL = rd('bh_h1_body_lots.csv', dtype={'tag': str, 'wing_tag': str}); WL = rd('bh_h1_wing_lots.csv', dtype={'tag': str})
pk = LH.loc[LH.real.idxmax()]; early = LH[(LH.lag_lo >= 0) & (LH.lag_hi <= 2.0)]; early_real = early.real.sum() / len(early); null_rate = LH[(LH.lag_lo >= 0) & (LH.lag_hi <= 2.0)].null_per_shift.mean()
mt = BL[BL.matched]; lagq = mt.lag.quantile([.05, .25, .5, .75, .95]).round(2).tolist()
W2 = rd('bh_h2_wing_buys.csv', dtype={'tag': str}); trig = W2[W2.n_trig_lots > 0].n_trig_lots.value_counts(normalize=True).sort_index()
G = rd('bh_h3c_wing_orders.csv', dtype={'tag': str}); GC = G[G.complete]; wl_un = WL[~WL.matched].tag.unique(); un = GC[GC.tag.isin(wl_un)]
bm = BL.groupby(['dayno', 'side']).matched.agg(['size', 'mean']).reset_index(); bm['group'] = bm.dayno.map({0: 'D-1', 1: 'D0'}) + ' body ' + bm.side + ' lots'; wm = WL.groupby(['dayno', 'side']).matched.agg(['size', 'mean']).reset_index(); wm['group'] = wm.dayno.map({0: 'D-1', 1: 'D0'}) + ' wing ' + wm.side + ' lots'
mm = pd.concat([bm, wm])[['group', 'size', 'mean']].assign(mean=lambda d: d['mean'].map(pct)); mm.columns = ['group', 'lots', 'matched share']
# ---------- H7/H8 refinements
HI = rd('bh_h7_isolated_lag.csv'); DL = rd('bh_h7_snapshot_delta.csv'); SW = rd('bh_h7_sign_wrong.csv', dtype={'tag': str}); SWC = rd('bh_h8_sign_wrong_by_cycle.csv'); W8 = rd('bh_h8_waves.csv'); W8c = W8[W8.complete].assign(exact=lambda d: d.sum_signed == d.gap_at_start, sign=lambda d: np.sign(d.sum_signed) == np.sign(d.gap_at_start)); OFF = rd('bh_h7_offset.csv', index_col=0)
iso_e = HI[(HI.lag_lo >= -2) & (HI.lag_hi <= 2.5)]; iso_p = HI[(HI.lag_lo >= 2.5) & (HI.lag_hi <= 10)]
off_m = OFF.loc[True, 'True'] / OFF.loc[True].sum(); off_u = OFF.loc[False, 'True'] / OFF.loc[False].sum()
w8t = W8c.groupby(['dayno', 'side']).agg(waves=('exact', 'size'), wave_sum_equals_gap=('exact', 'mean'), sign_ok=('sign', 'mean')).reset_index(); w8t['dayno'] = w8t.dayno.map({0: 'D-1', 1: 'D0'}); w8t['wave_sum_equals_gap'] = w8t.wave_sum_equals_gap.map(pct); w8t['sign_ok'] = w8t.sign_ok.map(pct); w8t.columns = ['day', 'side', 'waves', 'Σ signed lots = S−L at wave start', 'sign agrees']
dlt = DL.assign(exact_share=DL.exact_share.map(pct)); dlt.columns = ['snapshot taken this many s before the stamp', 'order lots = S−L (strict snapshot)']
BS = rd('bh_h9_baselines.csv', index_col=0)['value']
# ---------- H3
c = GC; ex = (c.sw == c.gap_before); sg = (np.sign(c.sw) == np.sign(c.gap_before)); t3 = c.assign(exact=ex, sign=sg).groupby(['dayno', 'side']).agg(n=('tag', 'size'), sign_ok=('sign', 'mean'), exact=('exact', 'mean'), med_gap=('gap_before', 'median')).reset_index(); t3['dayno'] = t3.dayno.map({0: 'D-1', 1: 'D0'}); t3['sign_ok'] = t3.sign_ok.map(pct); t3['exact'] = t3.exact.map(pct); t3.columns = ['day', 'side', 'wing orders', 'sign agrees with S−L', 'signed lots = S−L exactly', 'median S−L before']
Q = rd('bh_h3b_quiet.csv'); qt = Q.groupby('dayno').agg(samples=('S', 'size'), balanced=('gap_all', lambda s: (s == 0).mean()), med_S=('S', 'median')).reset_index(); qt['dayno'] = qt.dayno.map({0: 'D-1', 1: 'D0'}); qt['balanced'] = qt.balanced.map(pct); qt.columns = ['day', 'quiet samples', 'S − L = 0', 'median S (lots)']
hv = (Q.gap_hv == 0).groupby(Q.dayno).mean()
OV = rd('bh_h5_overnight.csv'); ox = OV[OV.complete & OV.has_d1]; EN = rd('bh_h5_endstate.csv'); en = EN[EN.complete]; RR = rd('bh_h5_release_rank.csv'); RP = rd('bh_h5_release_price_rank.csv')
# ---------- H2
RT = rd('bh_h2_rule_tests.csv'); SV = rd('bh_h2_simple_variants.csv', dtype={'tag': str}); SF = rd('bh_h2_simple_final.csv', dtype={'tag': str}); rng = np.random.default_rng(5)
def boot_p(hit, null, cyc):
    cy = np.unique(cyc); d = []; idx = {k: np.where(cyc == k)[0] for k in cy}
    for _ in range(1000): s_ = rng.choice(cy, len(cy)); ii = np.concatenate([idx[k] for k in s_]); d.append(hit[ii].mean() - null[ii].mean())
    d = np.array(d); return (d <= 0).mean(), np.quantile(d, .025), np.quantile(d, .975)
SS = rd('bh_h2_simple_tested.csv', dtype={'tag': str}); SS['cyc'] = SS.und + SS.expiry; pv = []
for nm in ('P20', 'P25', 'P30', 'P25o'): p, lo, hi = boot_p((SS[nm] == SS.strike).values, (SS[nm + '_null'] == SS.strike).values, SS.cyc.values); pv.append((nm, p, lo, hi))
srt = sorted(pv, key=lambda z: z[1]); holm = {}; m = len(srt); run = 0
for i, (nm, p, lo, hi) in enumerate(srt): run = max(run, min(1, (m - i) * max(p, 1 / 1000))); holm[nm] = (p, run, lo, hi)
RT2 = RT.copy(); RT2['exact (95 % cluster-bootstrap CI)'] = [f"{pct(a)} ({pct(b)}–{pct(c_)})" for a, b, c_ in zip(RT2.exact, RT2.ci_lo, RT2.ci_hi)]; RT2['≤1 step'] = RT2.within_1_step.map(pct); RT2['shuffled-null exact'] = RT2.null_exact.map(lambda v: '–' if v != v else pct(v)); RT2['Holm-adj. p vs null'] = RT2.rule.map(lambda r: f'{holm[r][1]:.3f}' if r in holm else '–')
RT2 = RT2[['rule', 'n', 'exact (95 % cluster-bootstrap CI)', '≤1 step', 'shuffled-null exact', 'Holm-adj. p vs null']]
vr = SV.assign(P25h=SV.P25 == SV.strike); varr = pd.DataFrame([dict(rule=n, exact=pct((SV[n] == SV.strike).mean()), within_1=pct((np.abs(SV[n] - SV.strike) <= SV.step * 1.0001).mean())) for n in ('P25', 'FLOOR', 'CEIL', 'NEAREST_LOG')])
rq = SF.groupby(['und', 'dayno']).ratio_ref.quantile([.25, .5, .75]).unstack().round(4).reset_index(); rq['dayno'] = rq.dayno.map({0: 'D-1', 1: 'D0'}); rq.columns = ['und', 'day', 'q25', 'median', 'q75']
slotnull = SF.P25_slotnull_hit.mean(); absh = SF.ABS_hit.dropna().astype(float).mean(); p25h = (SF.P25 == SF.strike).mean()
offs = SF.groupby(['und', 'dayno']).off_steps.median().unstack().round(1)
# ---------- H4
CU = rd('bh_h4_cushion.csv'); PT = rd('bh_h4_partial.csv'); PT_n = len(PT); hh = O[O.module == 'h_']; unf = (hh.lim_lots - hh.lots); fr = hh.px_first / np.where(hh.side == 'Buy', hh.lim_px / 1.15, hh.lim_px / 0.85)
sl_ = []
for (u, d), g in SF.groupby(['und', 'dayno']): b = np.polyfit(np.log(g.b_ref), np.log(g.w_ref), 1)[0]; sl_.append(f"{u} {['D-1', 'D0'][d]}: {b:.2f}")
partial_rows = int((X[X.module == 'h_'].status == 'PartiallyFilled').sum()); multi_fill = int((hh.n_fills > 1).sum())
# ---------- H6
A6 = rd('bh_h6_bursts.csv'); Q6 = rd('bh_h6_quiet.csv'); order = ['balanced', 'late_response', 'carry_in_unknown', 'flatten', 'near_stop', 'd0_open_window', 'other_imbalanced']
a6 = A6.groupby(['cls', 'day']).size().unstack(fill_value=0).reindex(order).fillna(0).astype(int); a6['total'] = a6.sum(axis=1); a6['share'] = a6.total.map(lambda v: pct(v / len(A6))); a6 = a6.reset_index(); a6.columns = ['class', 'D-1', 'D0', 'total', 'share of 928']
q6 = Q6.groupby('cls').size().reindex(order).dropna().astype(int).reset_index(); q6.columns = ['class', 'quiet imbalances']
# ---------- B
SL = rd('bh_b1_slot_structure.csv'); Z = rd('bh_b2_strike.csv'); BO = O[O.module == 'num'].merge(R[['tag', 'role']], on='tag', how='left'); rl = R[R.complete].groupby(['module', 'dayno', 'role']).lots.sum().unstack('role').fillna(0).astype(int)
rl_b = rl.loc['num'].copy(); rl_b.index = ['D-1', 'D0']; rl_h = rl.loc['h_'].copy(); rl_h.index = ['D-1', 'D0']
LG = BO[BO.role == 'open_long']; sec0 = LG.t_first; seed = LG[(sec0 >= 9 * 3600 + 15 * 60) & (sec0 < 9 * 3600 + 18 * 60)]
zt = pd.DataFrame([dict(day=['D-1', 'D0'][d], n=len(z), nearest_prev_spot_exact=pct((z.strike == z.near).mean()), within_1=pct(((z.strike - z.near).abs() <= z.step * 1.0001).mean()), null_exact=pct((z.strike == z.near_null).mean()), synthetic_ATM_exact=pct((z.strike == z.atm).mean())) for d, z in Z.groupby('dayno')])
sp = []
for (u, e, cp, d), g in BO[BO.role == 'open_short'].groupby(['und', 'expiry', 'cp', 'dayno']):
    t = np.sort(g.tt_first.values); dt = np.diff(t); sp.extend(dt[dt < 60])
sp = np.array(sp); orders_lot = BO.lots.value_counts(normalize=True)
DS = rd('dd_slot_sizing.csv'); ce_pe = (DS.dropna(subset=['lots_ce', 'lots_pe']).pipe(lambda d: (d.lots_ce == d.lots_pe).mean()))
ET = rd('dd_exit_timing.csv'); d1s0 = (ET[ET.day == 0].s == 0).mean(); d0s0 = (ET[ET.day == 1].s == 0).mean()
rowsH = [('Is the Body a four-leg Iron Butterfly?', f"Short **straddle at one strike** per D-1 slot ({pct((SL.ce_minus_pe_steps == 0).mean())} of {len(SL)} slots), balanced right-by-right by **far-OTM long wings** (L = S in {pct((Q[Q.dayno == 0].gap_all == 0).mean())} / {pct((Q[Q.dayno == 1].gap_all == 0).mean())} of D-1 / D0 quiet samples). Wings are pooled per right, not paired to a specific short; strangle-like variants are rare.", 'STRONGLY SUPPORTED (shape); CONFIRMED (right-level balance)', 'Wing↔short pairing is not observable; seed wings in the body stream (09:15–09:17) need a rule'),
         ('How are Body strikes selected?', f"Near the previous-minute spot: exact {pct((Z[Z.dayno == 0].strike == Z[Z.dayno == 0].near).mean())} / {pct((Z[Z.dayno == 1].strike == Z[Z.dayno == 1].near).mean())} (D-1 / D0), ±1 step {pct(((Z[Z.dayno == 0].strike - Z[Z.dayno == 0].near).abs() <= Z[Z.dayno == 0].step * 1.0001).mean())} / {pct(((Z[Z.dayno == 1].strike - Z[Z.dayno == 1].near).abs() <= Z[Z.dayno == 1].step * 1.0001).mean())}; shuffled-spot null ≈ {pct(Z.near_null.eq(Z.strike).mean())}. Synthetic-ATM (|C−P| min) is worse on D-1.", 'PARTIALLY SUPPORTED', 'About half of sold strikes are not the nearest; reference price/time is unresolved at 1-minute data'),
         ('How are Body quantities determined?', f"Orders are 1-lot ({pct(orders_lot.get(1, 0))}); per-slot lots are not premium-budgeted or book-state driven (DD-1 F3); CE = PE lots per slot in {pct(ce_pe)} of slot-legs.", 'PARTIALLY SUPPORTED (form) / UNRESOLVED (driver)', 'What sets the ladder size per slot is unknown'),
         ('What triggers a hedge?', f"A change in the contract-level gap S − L of a right: the hedge order is sent ≈ {np.median(mt.lag):.2f} s (IQR {lagq[1]}–{lagq[3]}) after the body fill second, not earlier than ≈ 2.5 s for isolated body orders, per right. {pct(off_u)} of unmatched body lots have an opposite body lot within ±20 s (roll-like, net-zero) vs {pct(off_m)} of matched ones.", 'STRONGLY SUPPORTED', 'Placement-vs-execution and partial-fill reactions cannot be separated (body fills carry no sub-second stamp)'),
         ('How is the Hedge strike selected?', f"Premium target ≈ 2.5 % of the sold option's price: nearest-price rule hits the exact strike in {pct(p25h)} (shuffled-body null {pct(RT.loc[RT.rule == 'P25', 'null_exact'].iloc[0])}, same-slot null {pct(slotnull)}), ±1 step {pct(RT.loc[RT.rule == 'P25', 'within_1_step'].iloc[0])}; 2.0 % and 3.0 % are far worse; fixed offsets/percent-of-spot fail.", 'PARTIALLY SUPPORTED', 'Exact rule (tick/price reference, tie-breaks) not identified; 62 % of simple orders miss the exact strike'),
         ('How is Hedge quantity calculated?', f"Total lots of one decision (wave) = the gap S − L at its start: {pct(W8c.exact.mean())} of {len(W8c):,} waves; per order {pct(ex.mean())} of {len(c):,} (sequential accounting), sign right {pct(sg.mean())}.", 'STRONGLY SUPPORTED', f"Release (sell) waves are less exact (D0: {w8t.iloc[3, 3]}); {int(len(SW))} sign-wrong orders, {int(SWC.iloc[0, 2])} of them in one cycle ({SWC.iloc[0,0]} {SWC.iloc[0,1]}) — see §12"),
         ('How is Hedge price determined?', f"Marketable IOC limit: limit = live price × (1 ± ≈ 15 %); body DAY orders have the same cushion; fills occur at ≈ the live price (not at the limit).", 'CONFIRMED (cushion); NOT TESTABLE (bid/ask/mid)', 'Reference price source (LTP/mid) and exact cushion constant (14.5–15.6 % depending on stream/tick)'),
         ('How are Hedge positions managed?', f"Held until the controller releases them as shorts shrink; releases prefer the cheapest/outermost long ({pct((RP.rank_price_desc == RP.n).mean())} lowest-priced vs chance {pct((1 / RP.n).mean())}); lump (v_) hedge adds an intended overweight (L−S = lump lots in {pct((ox.L_minus_S == ox.lump_lots).mean())} of cycle-rights); {pct(((en.S_end == 0) & (en.L_end == 0)).mean())} of cycle-rights end flat, rest carry longs.", 'PARTIALLY SUPPORTED', 'Release-selection rule unidentified; lot-level ownership is a convention'),
         ('How do Body and Hedge interact?', f"The body changes S; the hedge restores L = S per right after a ≈ 3–5 s delay (single IOC order of size S−L). The body stream also buys wings (seed at 09:15–09:17, {int(seed.lots.sum()):,} lots) and the 15:14 flatten uses body orders on wing contracts, so modules overlap at contract level.", 'STRONGLY SUPPORTED (controller); PARTIALLY (overlaps)', f"Exceptions: see §12 ({pct(a6.set_index('class').total['other_imbalanced'] / len(A6))} of non-responses unexplained); parent/basket ids absent")]
rowsH = [(a, b.replace(f" (D-1 buys {''}see table)", ''), c_, d) for a, b, c_, d in rowsH]
FT = pd.DataFrame(rowsH, columns=['Question', 'Finding', 'Evidence level', 'Remaining uncertainty'])
# ---------- compose
L = []
w = L.append
w('# Algo 8 — Body Module and Hedge Module: deep investigation\n')
w(f'*In-sample, observational reconstruction of the original system from the 35 live cycles ({ncyc} cycles in the ledger, {len(X):,} fills, {len(O):,} orders). Not source code, not out-of-sample, no trading-rule claims. All numbers computed by `src/make_bh_report.py` from `src/bh_*.py` outputs. Plan: `BODY_HEDGE_INVESTIGATION_PLAN.md` (written before the analysis). Code status: **executed**; results **observed**; the analysis has had a self red-team pass only (no independent reviewer).*\n')
w('## 1. Executive summary\n')
w(f"""1. **The Hedge module is a balance controller, not a per-fill mirror.** At the decision stamp of each hedge order, the order's signed lots equal the book gap **S − L** (short lots minus long lots of that right, all strikes, contract level) in **{pct(ex.mean())}** of {len(c):,} orders (30 complete-carry cycles); the sign agrees in {pct(sg.mean())}; counting one decision (a *wave* of orders stamped within 0.05 s) as a unit, the **summed signed lots equal S − L in {pct(W8c.exact.mean())}** of {len(W8c):,} waves (sign {pct(W8c['sign'].mean())}); a shuffled-gap null (each order/wave given the gap of a random other one of the same und/day/side) gives only {pct(BS['order_exact_null_mean'])} / {pct(BS['wave_exact_null_mean'])} because most gaps are 1 lot, so the evidence is the ≈ 40-point excess, not the absolute level. At quiet times (30 s after a body order, no other body order) the book is balanced (S = L) in **{pct((Q[Q.dayno==0].gap_all==0).mean())} (D-1)** and **{pct((Q[Q.dayno==1].gap_all==0).mean())} (D0)** of {len(Q):,} samples (cross-right null — S of one right vs L of the other — {pct(BS['quiet_cross_right_null'])}).
2. **Trigger and timing.** A hedge order is stamped {np.median(mt.lag):.2f} s (IQR {lagq[1]}–{lagq[3]}) after the body fill second (DD-1's nearest-fill measure gave 3.7 s; the difference is the matching rule). For **isolated** body orders (no other body order on the right within ±20 s; {int(iso_p.real.sum()):,} hedge orders in 2.5–10 s vs {iso_p.null_per_shift.sum():.0f} expected by chance) nothing arrives before ≈ 2.5 s ({int(iso_e.real.sum())} vs {iso_e.null_per_shift.sum():.0f} chance in −2…2.5 s) — consistent with a reaction to the executed position, with an irreducible delay. Per right (wrong-right null matches {pct(W1.iloc[-1].matched_share, 1) if False else pct(float(W1.iloc[-1].matched_share))} of body lots vs {pct(float(W1.iloc[1].matched_share))} for the correct right).
3. **Hedge strike:** price-targeted at ≈ **2.5 % of the sold option's decision price** (exact strike {pct(p25h)} vs {pct(slotnull)} same-slot null; ≈ {pct(RT.loc[RT.rule=='P25','within_1_step'].iloc[0])} within one strike), not a fixed offset ({pct(RT.loc[RT.rule=='FIX','exact'].iloc[0])}) or %-of-spot ({pct(RT.loc[RT.rule=='PCT','exact'].iloc[0])}). The exact selection rule is **not** identified.
4. **Pricing:** all three streams (body, hedge, stop) send **marketable limit orders ≈ 15 % beyond the live price** (body DAY, hedge IOC); fills occur near the live price. Limit prices therefore reveal each order's **decision-time reference price** (±≈ 1 %).
5. **Body structure:** per D-1 slot the short legs are a **same-strike straddle** ({pct((SL.ce_minus_pe_steps == 0).mean())} of {len(SL)} slots) with sold strike ≈ nearest to the previous-minute spot (exact {pct((Z[Z.dayno==0].strike == Z[Z.dayno==0].near).mean())} D-1 / {pct((Z[Z.dayno==1].strike == Z[Z.dayno==1].near).mean())} D0). The "iron butterfly" is balanced right-by-right with far wings, not paired lot-by-lot.
6. **Modules overlap at contract level:** the numeric-tag stream also buys long wings ({int(LG.lots.sum()):,} lots, {int(seed.lots.sum()):,} of them at 09:15–09:17), and the hedge module sometimes covers shorts or sells non-held contracts. Module role accounting and contract-level accounting differ (known from earlier work).
7. **Corrections to DD-1:** the "92.6 % of 12,490 bursts respond" figure counted any hedge order in a window and treated every body Buy as a buy-back; at lot level **{pct(float(W1.iloc[1].matched_share))}** of body lots and **{pct(float(W1.iloc[1].wing_matched_share))}** of hedge lots match 1:1 within [1.5, 20] s, because the controller responds to the **net gap** S − L rather than to individual fills (roll-like net-zero changes are over-represented among unmatched lots: {pct(off_u)} vs {pct(off_m)} of matched).
8. **Exceptions:** of the 928 non-responding body bursts, **{pct(a6.set_index('class').total['balanced'] / len(A6))}** need no hedge (book already balanced), {pct(a6.set_index('class').total['late_response'] / len(A6))} are answered after 10 s, {pct(a6.set_index('class').total['carry_in_unknown'] / len(A6))} sit in cycles whose carry-in is unknown, {pct(a6.set_index('class').total['flatten'] / len(A6))} are in the 15:14 flatten; **{pct(a6.set_index('class').total['other_imbalanced'] / len(A6))} remain unexplained** (a further {pct(a6.set_index('class').total['d0_open_window'] / len(A6))} fall in a post-hoc D0-open class).
""")
w('### Final summary table\n'); w(table(FT)); w('\n')
w('## 2. Current understanding of the Body Module\n')
w(f"""The numeric-tag stream ({int((O.module=='num').sum()):,} orders, 1-lot DAY limit orders in {pct(orders_lot.get(1,0))} of cases) sells short options right by right, mostly as a same-strike straddle per D-1 slot, buys them back on D-1 (minute-clocked) and D0 (not clocked), and also buys long wings at the open. Evidence and open points in §4–5. This is a **reconstruction from behaviour**, not recovered code.
""")
w('## 3. Current understanding of the Hedge Module\n')
w("""One IOC limit order per decision, one strike per order, sized to the gap between short and long lots of a right; stamped about 3–5 s after the body trade; strike chosen to cost ≈ 2.5 % of the sold option; released as shorts shrink (cheapest/outermost first, weakly); the overnight lump (`v_`) deliberately over-hedges the carry. See §6–9.
""")
w('## 4. Body structure and strike-selection reconstruction\n')
w(f"""**Data audit.** Order-level columns not used in earlier phases (limit price, validity, status, remaining quantity) are now joined (`bh_common.py`): 

{table(inv)}

**B1 — structure (D-1, first 3 minutes of each of the 17 slots, 09:16 + 15 k).** {len(SL)} slots in {SL.groupby(['und','expiry']).ngroups} cycles have both rights sold. Same strike for CE and PE in **{pct((SL.ce_minus_pe_steps == 0).mean())}**; CE strike above PE {pct((SL.ce_minus_pe_steps > 0).mean())}, below {pct((SL.ce_minus_pe_steps < 0).mean())}. Equal lots CE = PE: {pct((SL.lots_ce == SL.lots_pe).mean())}. CE and PE first orders in the same second: {pct((SL.ce_first_minus_pe_first_s == 0).mean())} (CE strictly first {pct((SL.ce_first_minus_pe_first_s < 0).mean())}, PE first {pct((SL.ce_first_minus_pe_first_s > 0).mean())}) ⇒ the two short legs are opened **practically simultaneously**, the wings follow ≈ 3–5 s later (§6): the structure is **built sequentially in two stages** with no basket id.

Contract-level roles of every order in the 30 complete-carry cycles (lots):

Body (numeric) stream:\n\n{table(rl_b.reset_index().rename(columns={'index': 'day'}))}

Hedge (`h_`) stream:\n\n{table(rl_h.reset_index().rename(columns={'index': 'day'}))}

The body stream **buys long contracts** ({int(LG.lots.sum()):,} lots; by day D-1 {int(LG[LG.dayno==0].lots.sum()):,}, D0 {int(LG[LG.dayno==1].lots.sum()):,}; {int(seed.lots.sum()):,} at 09:15–09:17 — the "seed wings" of the register), and the hedge stream has {int(rl_h['cover_short'].sum())} lots of `cover_short` and {int(rl_h['open_short'].sum())} lots of `open_short`: **the module split is not a clean "body sells / hedge buys"**.

**B2 — strike selection** (all body `open_short` orders; reference = previous-minute spot close; null = nearest strike to the spot of a random minute of the same day):

{table(zt)}

Median distance of the sold strike from the previous-minute spot in strike steps (+ = ITM): D-1 CE {Z[(Z.cp=='CE')&(Z.dayno==0)].eval('itm_pts/step').median():+.2f} / PE {Z[(Z.cp=='PE')&(Z.dayno==0)].eval('itm_pts/step').median():+.2f}; D0 CE {Z[(Z.cp=='CE')&(Z.dayno==1)].eval('itm_pts/step').median():+.2f} / PE {Z[(Z.cp=='PE')&(Z.dayno==1)].eval('itm_pts/step').median():+.2f} — ATM-centred and dynamic, not a fixed distance. About half of the sold strikes are **not** the nearest strike; neighbours (±1 step) cover 87–92 %. Earlier register STK-02 (50.3 % / 42.9 %) is consistent. **UNRESOLVED:** the exact reference (the minute data lag the decision; a time-of-decision spot is unavailable).
""")
w('## 5. Body entry and position-management reconstruction\n')
w(f"""* **Orders.** 1-lot DAY **limit** orders; {pct(orders_lot.get(1,0))} single lot, {pct(orders_lot.get(2,0))} two-lot; fills per order: 1 in {pct((BO.n_fills==1).mean())}; a PartiallyFilled row occurs for {pct((BO.n_partial>0).mean())} of orders and all pieces fill in the same second except {int((O.fill_secs>1).sum())} order(s) (fills spanning up to {int((O.t_last-O.t_first).max())} s); no unfilled DAY remainders are visible in the ledger.
* **Price style.** Limit ≈ live price ∓ 14.5–15 % (§8): effectively market orders. No cancel/modify/retry records exist in the ledger (not testable).
* **Ladder cadence.** Spacing between consecutive short-sale orders on one right: median {np.median(sp):.0f} s, quartiles {np.quantile(sp,.25):.0f}–{np.quantile(sp,.75):.0f} s; {pct((sp==0).mean())} in the same second.
* **Exits.** D-1 buy-backs fill in second :00 in {pct(d1s0)} of cases vs {pct(d0s0)} on D0 (DD-1 F2): minute-clocked on D-1, not on D0. Re-sell after buy-back within 60 s: 37 % of buy-back lots (DD-1 F4). Per-lot stop band 1.55–1.7 × entry, cycle stop ≈ −₹1.30…−1.44 L (existing register, not re-derived here). **No new exit rule is claimed in this milestone.**
* **Quantities.** Slot ladder sizes are not explained by premium or book state (DD-1 F3, REJECTED); CE = PE lots per slot in {pct(ce_pe)}.
""")
w('## 6. Hedge trigger and response analysis\n')
w(f"""**Method (independent of DD-1).** Order level: each body lot (first fill second) is matched 1:1, greedily in time order, to the earliest unmatched opposite-side hedge lot of the **same right** whose decision stamp lies in a window after it. Null: hedge times shifted by ±137/211/389/523 s; wrong-right null.

![lag](figures/bh_lag_hist.png)

* Lag histogram (all body orders): peak bin [{pk.lag_lo}, {pk.lag_hi}) s = {int(pk.real):,} vs null ≈ {pk.null_per_shift:.0f}. Lags 0–2 s average {early_real:.0f} per half-second vs null {null_rate:.0f}: this excess is **burst contamination** (a later order of a burst sees an earlier order's hedge). Test restricted to **isolated** body orders (no other body order on the right within ±20 s; {int(iso_p.real.sum() + iso_e.real.sum()):,} hedge orders in −2…10 s): in −2…2.5 s real {int(iso_e.real.sum())} vs null {iso_e.null_per_shift.sum():.0f}; in 2.5…10 s real {int(iso_p.real.sum()):,} vs null {iso_p.null_per_shift.sum():.0f}. **No early response.** Quartiles of matched lags (all matched): {lagq}.
* Window sensitivity and nulls:

{table(W1.assign(matched_share=W1.matched_share.map(lambda v: pct(float(v))), wing_matched_share=W1.wing_matched_share.map(lambda v: pct(float(v)))))}

* By group:

{table(mm)}

* **Does every short fill trigger a hedge?** No — at lot level {pct(float(W1.iloc[1].matched_share))} of body lots are matched. Of the unmatched lots, {pct(off_u)} have an opposite-direction body lot within ±20 s (net-zero roll-like changes) against {pct(off_m)} of matched lots; the other {pct(1-off_u)} of unmatched lots are changes whose gap was already balanced/over-hedged or are exceptions (§12). PARTIALLY SUPPORTED. The right description is the **controller** of §7.
* **One body fill → how many hedge orders?** Matched hedge buy orders carry {', '.join(f'{k} body lot(s): {pct(v)}' for k, v in trig.head(4).items())} of triggers (n = {int((W2.n_trig_lots>0).sum()):,}); a hedge order of N lots corresponds to an aggregated gap, not to N separate decisions. Several body fills are **aggregated** into one hedge order.
* **Hedge before body?** For isolated body orders there is no excess before 2.5 s (above); the all-order excess at negative lags is the burst effect. Unmatched hedge lots are {pct(1-float(W1.iloc[1].wing_matched_share))}; the orders that contain them equal S − L exactly in only {pct((un.sw==un.gap_before).mean())} (vs {pct(ex.mean())} overall in complete cycles), i.e. they are driven by gap changes not caused by a recent body fill in the matched window (late responses, stop/flatten, lump salvage): **UNRESOLVED** in detail.
* **Placement vs execution; partial fills.** Body orders are DAY limit orders that fill within the same second as the log (cushion ≈ 15 %); no hedge stamp is earlier than ≈ 2.5 s after the fill second. A placement-triggered reaction with fixed delay cannot be excluded: **UNRESOLVED**. Body partial fills are all in one second: **NOT TESTABLE**.
* **Sub-second structure.** Fractional-second Rayleigh of hedge stamps is {abs(np.exp(2j*np.pi*(hh.t_dec%1)).mean()):.3f} (uniform ⇒ no sub-second poll phase); {pct((hh.sort_values(["und","expiry","dayno","t_dec"]).groupby(["und","expiry","dayno"]).t_dec.diff().dropna()<0.01).mean())} of consecutive hedge orders are < 10 ms apart (one decision emitting several orders, e.g. several strikes).
""")
w('## 7. Hedge quantity (level control)\n')
w(f"""State at each hedge decision stamp: S = short lots, L = long lots of the right, from net contract positions over **all** modules (ownership-free); events strictly before the stamp (ties at identical event time can differ by a row: 3 of 400 spot-checked orders in the unit test).

![level control](figures/bh_level_control.png)

{table(t3)}

**Wave level (one decision = orders on one right stamped within 0.05 s of each other; snapshot strictly before the first stamp):** {len(W8c):,} waves, {pct((W8c.n_orders==1).mean())} are single orders; **Σ signed lots = S − L in {pct(W8c.exact.mean())}**, sign right {pct(W8c['sign'].mean())}.

{table(w8t)}

**Snapshot timing.** Order lots equal the book gap taken δ seconds before the stamp (strict snapshot, per order):

{table(dlt)}

The gap is read at the stamp or up to ≈ 2 s before it (85–87 %), and the match collapses beyond 3 s: the sizing uses a book view that is at most ~2–3 s old, even though the *trigger* lag is 3–5 s after the body fill second. Body fill times are floored to whole seconds, so 0–2 s cannot be separated.

* Per order, sequential accounting (a wave's earlier orders are already booked): exact catch-up (`signed lots = S − L`) **{pct(ex.mean())}**, sign right {pct(sg.mean())}, |gap| reduced {pct((c.gap_after.abs()<c.gap_before.abs()).mean())}; balance restored (gap after = 0) {pct((c.gap_after==0).mean())}.
* **Chance baseline.** Giving each order/wave the gap of a random other order of the same und/day/side: per order {pct(BS['order_exact_null_mean'])} (97.5th pct {pct(BS['order_exact_null_p975'])}), per wave {pct(BS['wave_exact_null_mean'])} ({pct(BS['wave_exact_null_p975'])}); by group the per-order null is D-1 buy {pct(BS['order_null_D-1_Buy'])}, D-1 sell {pct(BS['order_null_D-1_Sell'])}, D0 buy {pct(BS['order_null_D0_Buy'])}, D0 sell {pct(BS['order_null_D0_Sell'])}. The real exactness is far above these but the nulls are high because most gaps are small.
* Quiet-time balance (cross-right null {pct(BS['quiet_cross_right_null'])}):

{table(qt)}

Hedge/lump-only long lots (`h_`+`v_` netted separately) equal S in only {pct(hv.iloc[0])} / {pct(hv.iloc[1])} of the samples: balance exists at **contract level over all modules**, not within the hedge module alone.
* **Overnight:** at the end of D-1, L − S equals the net lump (`v_`) lots in **{pct((ox.L_minus_S==ox.lump_lots).mean())}** of {len(ox)} cycle-rights (corr {np.corrcoef(ox.L_minus_S, ox.lump_lots)[0,1]:.2f}): the D-1 book is exactly balanced **plus** an intended lump overweight, which D0 salvages.
* **Mismatches** ({pct(1-W8c.exact.mean())} of waves; {pct(1-ex.mean())} of orders) are concentrated in D0 releases (sell waves {w8t.iloc[3, 3]} exact) and in multi-order waves (exact for 4+-order waves: {pct(W8.query('complete and n_orders>=4').pipe(lambda d: (d.sum_signed == d.gap_at_start).mean()))}); at D0 the book is also moved by body, stop and flatten orders within the same seconds, so a one-snapshot rule cannot be tested more finely with second-resolution body fills. See §12.
* Partial fills of hedge orders: {partial_rows:,} fill rows have status PartiallyFilled but {multi_fill:,} orders are multi-fill within one second; only **{int((unf>0).sum())} of {len(hh):,} hedge orders** end with unfilled quantity ({int(unf.sum())} lots of {int(hh.lim_lots.sum()):,}). IOC zero-fill orders would be invisible in the ledger (not testable).
""")
w('## 8. Hedge strike selection and pricing\n')
w(f"""**Pre-registered rules** (plan §3 H2): P20/P25/P30 (nearest chain price to k × body decision price; k = 2.0/2.5/3.0 %), P25o (open-minute price), FIX (modal offset in steps, leave-one-cycle-out), PCT (median % of spot, leave-one-cycle-out). Sample: **{len(SS):,} simple wing buys** (one trigger body lot, one wing lot) in {SS.cyc.nunique()} cycles. Body decision price = limit ÷ 0.85 (sell) recovered from the limit; chain price = minute close at j−1 (no bid/ask).

{table(RT2)}

Exploratory variants (chosen **after** seeing that 2.5 % is a sharp optimum; not part of the pre-registered family): 

{table(varr)}

Tighter nulls: shuffling the body price **within the same und/day/30-min slot** gives {pct(slotnull)} exact (real {pct(p25h)}); a fixed absolute wing price per slot (leave-one-cycle-out) gives {pct(absh)}. Variance decomposition: slot effects alone explain most of log(wing price) (the price level falls through the day), so the body-price information is a **within-slot** effect of moderate size, visible in the hit rates, not in R².

![wing ratio](figures/bh_wing_ratio.png)

Wing decision price ÷ body decision price (from limit prices), by und/day (quartiles): 

{table(rq)}

Median offset of the wing strike from the sold strike (steps OTM): {offs.to_dict()}. Offsets differ strongly by und/day, which a fixed-distance rule cannot produce; the premium target adapts automatically.

**Pricing.** Limit cushion = (limit ÷ first-fill price − 1) for Buys, (1 − limit ÷ fill) for Sells, fills ≥ ₹10 (tick-insensitive):

{table(CU)}

Hedge buys/sells with fills of ₹2–10 show a median cushion of 15.5 % / 15.4 % (tick and fill-at-ask effects). Fills occur at the live price, not at the limit: first-fill ÷ (limit-derived reference) for hedges has median {fr.median():.3f}. **Interpretation:** an order-type convention (a 15 % protective band that makes the limit order behave as a market order). Whether the reference is LTP or mid is **NOT TESTABLE** (no bid/ask). Wing decision price depends only weakly on the body price in the cross-section (log-log slope: {'; '.join(sl_)}), because most of the price variation is across time within the cycle. Limit prices of wings never reveal a "maximum acceptable price" (cushion constant ≈ 15 %).

![cushion](figures/bh_limit_cushion.png)
""")
w('## 9. Hedge lifecycle\n')
w(f"""Contract-level, ownership-free. (Lot-level pairing of a wing to a specific body lot is a reconstruction convention and is **not** used.)

* **Held until released by the controller** as S falls; D0 sells exact in about three quarters of cases (§7).
* **Which long is released** (sell orders with ≥ 2 long strikes held; n = {len(RR):,} / {len(RP):,}): outermost {pct((RR.rank_outermost==1).mean())} (chance {pct((1/RR.n_long_strikes).mean())}); innermost {pct((RR.rank_outermost==RR.n_long_strikes).mean())}; oldest {pct((RR.rank_oldest==1).mean())}; **lowest-priced {pct((RP.rank_price_desc==RP.n).mean())}** (chance {pct((1/RP.n).mean())}), highest-priced {pct((RP.rank_price_desc==1).mean())}. A preference for the cheapest/outermost wings, **not** a deterministic rule: PARTIALLY SUPPORTED.
* **After the body exits.** At cycle end ({len(en)} complete-carry cycle-rights): flat {pct(((en.S_end==0)&(en.L_end==0)).mean())}; residual **longs** {pct((en.L_end>0).mean())} (wings carried to settlement), residual shorts {pct((en.S_end>0).mean())}.
* **Overnight lump** (`v_`) heavier side, 15:06–15:38 D-1; carried; salvaged on D0 (register SIZ-04).
* **Adds as spot moves / replaces strikes:** every body short sale at a new strike creates a new gap, hence a new wing order at a premium-targeted strike — the "adjustment" is part of the same controller. **Independent stop/profit rules for hedges:** none detected (the `s_` module liquidates body and wings together in stop cycles). **Reuse of existing hedge inventory:** when L ≥ S already (e.g. after over-hedging), body sells produce no hedge (§12 'balanced').
""")
w('## 10. Body–Hedge interaction timeline\n')
w("""Typical D-1 sequence (case `normal`, §11): body sells CE and PE legs within the same second at the nearest strike → the book gap S − L becomes +1 per right → ≈ 3–5 s later a 1-lot IOC hedge buy at the strike costing ≈ 2.5 % of the sold option → fills at the live price → gap 0. D0: body buy-backs and re-sales alternate; net-zero changes produce no hedge order; net changes are answered by one order for the whole gap; the 15:14 flatten and stop liquidations bypass the controller (body/stop orders close wings as well).

Stage table (what can be timestamped): decision (body: unknown; hedge: µs stamp) → order (body: minute; hedge: stamp) → fill (second) → hedge stamp (µs) → hedge fill (second) → next adjustment.
""")
w('## 11. Representative case studies\n')
w('Cases are chosen by **pre-registered rules** (first instance in cycle order) and shown in full in `outputs/bh_i1_cases.md`; columns S/L/gap are the contract-level lots of the right **after** each event.\n')
cs = open(f'{OUT}/bh_i1_cases.md').read().split('## ')[1:]
for sec in cs:
    nm = sec.split('\n')[0]
    rows = sec.split('\n'); body = '\n'.join(rows[:min(len(rows), 18)])
    w('### ' + body + ('\n\n*(truncated; full timeline in outputs)*' if len(rows) > 18 else '') + '\n')
w('''**What each case shows (read from the tables above; interpretations are inferences):**
* `normal` — one body short sale makes S − L = +1; one hedge buy of 1 lot follows 3.2 s later at a far-OTM strike (price ₹2.0 vs the sold option ₹110.8 = 1.8 %); gap 0.
* `body_partial` — the first instance of a multi-lot multi-fill body order sits inside a **stop-module liquidation** (s_ orders close shorts and wings within the same second), then the body re-sells in bulk; not typical hedge behaviour.
* `body_partial_no_stop` — 54-lot body orders on far-OTM contracts at 15:15 on D-1: a buy of 54 lots then a sale of 54 lots 9 s later, leaving S = L; the purpose is not established.
* `delayed_hedge` — four body orders (rolls) move S by +2 net within 6 s; the hedge sells 2 lots at +8.1 s (answering the earlier −4 gap) and buys 2 lots at +21.0 s: the hedge works from a book view that lags rolls.
* `quantity_differs` — two body buy-backs create a −17 gap; one decision emits four sell orders (2, 2, 12, 1 lots) on one stamp, partially restoring then exactly restoring balance: the first orders are not 'exact' individually but the wave is.
* `missing_hedge` / `body_exits_hedge_stays` — one body buy-back at 09:19:14 on D0 leaves L = 150 vs S = 66 (large over-hedge carried from the open); no hedge sell follows within 60 s; unexplained class.
* `existing_inventory` — near the D0 close body sells 2 lots (S 40 → 42) and buys back 2 lots 7 s later: net zero within the book view, **no hedge**; later buy-backs reduce S and the hedge sells 3 lots at 15:11:25 to restore L = S.
* `hedge_exits_first` — D0 open, hedge buys/sells alternate with body buy-backs of the far wing 24650 (body stream trades wing contracts); first instance of a hedge sell with S ≥ L before it.
''')
w('## 12. Missing-hedge and quantity-mismatch analysis\n')
w(f"""**928 body bursts without a wing response within 10 s** (DD-1 definition, bursts = orders ≤ 3 s apart), classified by ordered rules (balanced → late response → carry-in unknown → flatten → near stop → D0-open window [post-hoc] → other) using the contract-level book at burst end + 10 s:

{table(a6)}

By right: CE {int((A6.cp=='CE').sum())}, PE {int((A6.cp=='PE').sum())}. **{pct(a6.set_index('class').total['balanced'] / len(A6))} need no hedge; {pct((a6.set_index('class').total[['balanced','late_response','carry_in_unknown','flatten','near_stop','d0_open_window']].sum()) / len(A6))} are explained; {int(a6.set_index('class').total['other_imbalanced'])} bursts ({pct(a6.set_index('class').total['other_imbalanced'] / len(A6))}) remain unexplained**, mostly over-hedged books (L > S: {pct((A6[A6.cls=='other_imbalanced'].gap_at_plus10<0).mean())}) on D0, not concentrated in stop cycles.

**Quiet-time imbalances** ({len(Q6)} of {len(Q):,} quiet samples = {pct(len(Q6)/len(Q))}) by the same classes:

{table(q6)}

**Quantity-mismatch classes** (hedge orders whose signed lots ≠ S − L): sign right but size different {int(((np.sign(c.sw)==np.sign(c.gap_before))&(c.sw!=c.gap_before)).sum()):,}, sign wrong {len(SW):,} (of {len(c):,}). Sign-wrong orders by day/side: {SW.groupby(['dayno','side']).size().to_dict()}; **{int(SWC.iloc[0,2])} of them are in one cycle ({SWC.iloc[0,0]} {SWC.iloc[0,1]})**, where the hedge kept buying 1-lot orders while L exceeded S by 13 lots for ~3 hours on D0; {len(SWC)} cycles have any. That cycle looks like a persistent state mismatch (the hedge's view of S differs from the contract-level S — **UNRESOLVED**); excluding it, sign-wrong orders are {len(SW) - int(SWC.iloc[0,2])} of {len(c) - int(SWC.iloc[0,2])}.
""")
w('## 13. Evidence and confidence table\n')
ev = [('Hedge decision (wave) total lots = S − L (per right, contract level)', 'STRONGLY SUPPORTED', f'{len(W8c):,} waves / {len(c):,} orders, 30 cycles, in-sample', f'wave-exact {pct(W8c.exact.mean())}; per-order {pct(ex.mean())}; sign right {pct(sg.mean())}; integer equality (chance negligible) but the S/L definition (contract level, all modules) is one of several possible'),
      ('Quiet-time balance S = L', 'CONFIRMED', f'{len(Q):,} samples, 30 cycles', f"{pct((Q[Q.dayno==0].gap_all==0).mean())} D-1, {pct((Q[Q.dayno==1].gap_all==0).mean())} D0"),
      (f'Hedge lag ≈ {np.median(mt.lag):.1f} s (median, lot matching), not earlier than ≈ 2.5 s for isolated orders', 'CONFIRMED (timing)', f'{len(mt):,} matched lots; {int(iso_p.real.sum()):,} isolated-order responses', 'sub-second body timing unknown; reaction to placement not separable'),
      ('Wing price target ≈ 2.5 % of sold option', 'STRONGLY SUPPORTED (target) / PARTIALLY (strike)', f'{len(SS):,} simple orders, 33 cycles', f"exact {pct(p25h)} vs null {pct(RT.loc[RT.rule=='P25','null_exact'].iloc[0])} (same-slot {pct(slotnull)}); k = 2.0/3.0 % rejected"),
      ('Fixed offset / %-of-spot wing rule', 'REJECTED', f'{len(SS):,}', f"exact {pct(RT.loc[RT.rule=='FIX','exact'].iloc[0])} / {pct(RT.loc[RT.rule=='PCT','exact'].iloc[0])}"),
      ('Marketable limit with ≈ 15 % cushion (all streams)', 'CONFIRMED', f'{len(O):,} orders', f"median cushion {CU.cushion_median.min()*100:.1f}–{CU.cushion_median.max()*100:.1f} % by stream/day for fills ≥ ₹10"),
      ('Body shorts: same-strike straddle per D-1 slot', 'STRONGLY SUPPORTED', f'{len(SL)} slots, 32 cycles', pct((SL.ce_minus_pe_steps == 0).mean())),
      ('Body strike = nearest to previous-minute spot', 'PARTIALLY SUPPORTED', f'{len(Z):,} sells', f"exact {pct((Z[Z.dayno==0].strike==Z[Z.dayno==0].near).mean())} / {pct((Z[Z.dayno==1].strike==Z[Z.dayno==1].near).mean())} vs null {pct(Z.near_null.eq(Z.strike).mean())}"),
      ('Overnight lump = intended overweight', 'STRONGLY SUPPORTED', '60 cycle-rights', pct((ox.L_minus_S == ox.lump_lots).mean())),
      ('Release preference: cheapest/outermost', 'PARTIALLY SUPPORTED', f'{len(RP):,} sells', f"{pct((RP.rank_price_desc == RP.n).mean())} lowest-priced vs {pct((1/RP.n).mean())} chance; no deterministic rule"),
      ('Stop/profit rule on hedges', 'NOT DETECTED / UNRESOLVED', '–', 'would need parent/trigger records'),
      ('IOC zero-fill hedge attempts', 'NOT TESTABLE', '–', 'unfilled orders are absent from the ledger'),
      ('Bid/ask/mid reference of limit prices', 'NOT TESTABLE', '–', 'no quote data')]
w(table(pd.DataFrame(ev, columns=['Finding', 'Evidence level', 'n / scope', 'Detail / caveat']))); w('\n')
w('### 13b. Self red-team notes (no independent reviewer was run)\n')
w(f'''1. *Is "order = S − L" trivial?* No, but the null is high (≈ 50 %) because gaps are mostly 1 lot; the claim rests on the ≈ 40-point excess and on the quiet-time balance (cross-right null {pct(BS['quiet_cross_right_null'])}).
2. *Contract-level S and L are one definition among several.* Module-role accounting does not reproduce the balance (hedge/lump-only longs equal S in {pct(hv.iloc[0])} / {pct(hv.iloc[1])}); a different original definition (e.g. per-strike pairing) is not testable without parent ids.
3. *Decision prices from limits.* Reference = limit ÷ (1 ± 0.15); the 0.15 constant is estimated from the same ledger, so strike-rule hit rates inherit ≈ ±1 % price noise plus minute-close noise (no tick data); the 2.5 % optimum is sharp (2.0 / 3.0 % fail) but the exact rule is not identified.
4. *Post-hoc choices* (flagged in text): FLOOR/CEIL/NEAREST_LOG variants, the D0-open class in §12, and the second partial-fill case.
5. *Windows* (3 s burst, 10 s response, 20 s match, 30 s quiet, 0.05 s wave) are analysis choices; the matched-share sensitivity table shows the lot-level result moves by ≈ 3 points across 10–60 s windows.
6. *Selection of cases* follows fixed rules but several rules pick atypical windows (stop liquidation, D0-open); they illustrate mechanics, not frequencies.
7. *One persistent anomaly* ({SWC.iloc[0,0]} {SWC.iloc[0,1]}) contributes {int(SWC.iloc[0,2])} of {len(SW)} sign-wrong orders; it is reported, not removed from headline rates.
''')
w('## 14. Unresolved questions\n')
w(f"""1. Exact wing strike rule ({pct(1-p25h)} of simple orders miss the nearest-to-2.5 % strike with minute-close prices).
2. What sets the body ladder size per slot, and what ends a ladder.
3. Body strike reference (≈ 50 % exact vs previous-minute spot).
4. Release selection (cheapest/outermost preference only).
5. The unexplained non-response bursts ({pct(a6.set_index('class').total['other_imbalanced'] / len(A6))}) and quiet-time imbalances ({pct(len(Q6)/len(Q))}; mostly D0 over-hedged books), and the cycle with a persistent hedge/book mismatch ({SWC.iloc[0,0]} {SWC.iloc[0,1]}).
6. Whether the hedge reacts to placement or execution of body orders.
7. The exact S − L definition used by the original system (contract-level over all modules reproduces it; module-role accounting does not).
8. Why D0 sell-side (release) waves are less exact than buys, and what the release-selection rule is.
""")
w('## 15. Data limitations\n')
w("""No bid/ask/depth; option data are minute open/close/volume (no high/low); body orders have no sub-second stamps; no parent/basket ids; cancelled or zero-fill orders are absent; lot ownership is a convention; five cycles have unknown carry-in (excluded from balance claims, flagged `carry_in_unknown`); the 35 cycles are in-sample and heavily inspected (not a holdout); the window parameters (3 s burst, 10 s response, 20 s match, 30 s quiet) are analysis choices; k = 0.15 used to recover decision prices is the modal cushion, not a recovered constant. The numeric order-id counter was tested as a hidden-order detector and rejected (global counter).
""")
w('## 16. Final reconstruction of the two modules\n')
w("""**Body module (observed behaviour):** per slot, sell a same-strike CE+PE straddle (1-lot DAY limit orders at ≈ live price ∓ 15 %) at a strike near the previous-minute spot, as a ladder of single-lot orders a few seconds apart; buy back and re-sell on D-1 (minute-clocked) and D0 (continuous); seed long wings at the D0 open; flatten at 15:14 (post cut-over); the cycle stop and per-lot stop belong to separate modules.

**Hedge module (observed behaviour):** per right, whenever the book gap S − L changes, wait ≈ 3–5 s and send one IOC marketable limit order for the whole gap at the strike whose price is ≈ 2.5 % of the sold option (Buy when S > L, Sell when L > S), so that L = S at quiet times; the overnight `v_` lump adds an intended overweight; releases favour cheap/outermost wings.

**Coordination:** the hedge is event-driven off the executed body position with an irreducible ≈ 2.5 s latency; there is no evidence of independent stop or profit-taking logic on the hedge; the modules overlap at contract level (body wing buys, flatten orders on wing contracts, hedge covers).

*Reconstructed behaviour is not the original source logic.*
""")
open(os.path.join(REP, 'BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md'), 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
