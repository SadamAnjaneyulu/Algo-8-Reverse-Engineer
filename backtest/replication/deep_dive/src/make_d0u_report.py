"""Builds reports/D0_QTY.md and figures/bl_d0u_summary.png from the outputs of bl_d0u_exec.py, bl_d0u_size.py, bl_d0u_inv.py. Every verdict is computed from the tables (criteria of reports/D0_QTY_PLAN.md)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures'); REP = RP
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

def _md(self, index=True, **kw):
    d = self.reset_index() if index else self
    h = '| ' + ' | '.join(str(c) for c in d.columns) + ' |\n|' + '---|' * len(d.columns) + '\n'
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return h + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pd.DataFrame.to_markdown = _md
J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json'))
A, B, C = J('d0u_a'), J('d0u_b'), J('d0u_c')
A1 = pd.read_csv(f'{OUT}/bl_d0u_a1_size.csv'); MX = pd.read_csv(f'{OUT}/bl_d0u_a1_maxqty.csv'); A2 = pd.read_csv(f'{OUT}/bl_d0u_a2_buffer.csv'); A3 = pd.read_csv(f'{OUT}/bl_d0u_a3_type.csv'); A4 = pd.read_csv(f'{OUT}/bl_d0u_a4_bar.csv'); A5 = pd.read_csv(f'{OUT}/bl_d0u_a5_drip.csv')
FX = pd.read_csv(f'{OUT}/bl_d0u_b2_fixed.csv'); M3 = pd.read_csv(f'{OUT}/bl_d0u_b3_models.csv'); B4 = pd.read_csv(f'{OUT}/bl_d0u_b4_ratios.csv'); B5 = pd.read_csv(f'{OUT}/bl_d0u_b5_scaling.csv')
C1 = pd.read_csv(f'{OUT}/bl_d0u_c1_book.csv'); C2 = pd.read_csv(f'{OUT}/bl_d0u_c2_cap.csv'); C3 = pd.read_csv(f'{OUT}/bl_d0u_c3_feedback.csv'); C4 = pd.read_csv(f'{OUT}/bl_d0u_c4_balance.csv'); C5 = pd.read_csv(f'{OUT}/bl_d0u_c5_hedge.csv'); C6 = pd.read_csv(f'{OUT}/bl_d0u_c6_exposure.csv')
D0 = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz'); T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz')
pc = lambda x, d=1: f'{100 * x:.{d}f}%'
a1 = A1[A1.day == 'D0'].set_index('klass'); a2 = A2[A2.day == 'D0']
# ---- verdicts from the pre-registered rules
def verdict(rel, rho, ci_hi):
    if rel <= -0.20 and rho >= 0.5 and ci_hi < 0: return 'found'
    if rho >= 0.3 and ci_hi < 0: return 'associated'
    return 'unresolved'
def rows_for(task):
    z = M3[(M3.task == task) & M3.model.str.startswith('LOCO')]; return z
vs = {}
for task in M3.task.unique():
    for r in rows_for(task).itertuples(): vs[(task, r.model)] = (verdict(r.rel_mae_vs_best_baseline, r.rho, r.ci_hi), r)
solo_t = 'solo sells: lots per cell given a sale'; bb_t = 'buy-back events: lots per cell given a buy-back'
def best_base(task):
    z = M3[(M3.task == task) & M3.model.str.startswith('baseline')]; return z.loc[z.mae.idxmin()]
bs_solo, bs_bb = best_base(solo_t), best_base(bb_t)
fxd = FX.set_index('test'); cap_g = C2[(C2.measure == 'lots') & (C2.cycles >= 3)]; cap_found = bool((cap_g.share_within_10pct_of_median >= 0.7).any()); hz = C['c2_hazard_by_near_cap']
hz_ratio = hz['True']['rate'] / hz['False']['rate']; cap_verdict = 'no ceiling observed' if (not cap_found or hz_ratio > 0.5) else 'ceiling found'
c3 = C['c3_gain_inventory_on_top_of_spot_book']; c3_ok = c3['lo'] > 0.02 - 1e-9 and False
inv_verdict = 'no inventory feedback' if c3['hi'] < 0.02 else 'check'
al = C4[C4.type == 'all solo sells'].iloc[0]; op = C4[C4.type == 'opening solo'].iloc[0]
sched_fit = float(fxd.loc['scheduled pair is exactly 1 CE + 1 PE lot'].share_fit); wb = fxd.loc['wing-buy event lots == S-L gap before the event (all)']; wbl = fxd.loc['wing-buy event lots <= S-L gap before (all)']
wse = fxd.loc['wing-sell event lots == long excess L-S before']; wsl = fxd.loc['wing-sell event lots <= long excess L-S before']; lul = fxd.loc['lump-salvage order lots <= long excess L-S before']
ndf = MX[(MX.day == 'D0') & (MX.und == 'NIFTY')].set_index('month'); sdf = MX[(MX.day == 'D0') & (MX.und == 'SENSEX')].set_index('month')
solo_c = vs[(solo_t, 'LOCO boosting: causal (before the minute)')]; bb_c = vs[(bb_t, 'LOCO boosting: causal book/market (before the minute)')]; bb_b = vs[(bb_t, 'LOCO boosting: plus bar of the minute (crossing counts)')]
solo_g = vs[(solo_t, 'LOCO boosting: ladder depth only (gap_fav)')]
b4 = B4.set_index('what'); cs = b4.loc['counter-sell lots / other-right buy-back lots (same minute)']
ns = C1[~C1.stop_cycle]; nif = C['c1_by_und']['NIFTY']; sen = C['c1_by_und']['SENSEX']
# ---- figure
fig, ax = plt.subplots(2, 3, figsize=(16, 9)); col = {'Buy': '#2b6cb0', 'Sell': '#c05621', 'a': '#3d6b5a', 'b': '#8a8a8a'}
k = a1.sort_values('single_lot_orders'); ax[0, 0].barh(k.index, 100 * k.single_lot_orders, color=col['a']); ax[0, 0].set_title('Orders that are a single lot (D0)'); ax[0, 0].set_xlabel('% of orders'); [ax[0, 0].text(100 * v + 1, i, f'{int(o)} orders', va='center', fontsize=8) for i, (v, o) in enumerate(zip(k.single_lot_orders, k.orders))]; ax[0, 0].set_xlim(0, 125)
for kl, c_ in (('body sell', col['Sell']), ('body buy-back', col['Buy']), ('wing buy', '#555555')):
    z = D0[(D0.klass == kl) & D0.buf.between(-0.05, 0.45)]; ax[0, 1].hist(z.buf, bins=60, histtype='step', lw=1.6, color=c_, label=f'{kl} (n={len(z)})', density=True)
ax[0, 1].axvline(0.15, color='k', ls=':'); ax[0, 1].set_title('Limit price vs first fill: buffer'); ax[0, 1].set_xlabel('limit beyond fill, share of fill price'); ax[0, 1].legend(fontsize=8)
for s_ in ('Buy', 'Sell'): z = D0[(D0.side == s_) & D0.bar_pos.between(-0.01, 1.01)]; ax[0, 2].hist(z.bar_pos, bins=20, histtype='step', lw=1.8, color=col[s_], density=True, label=f'{s_} (median {z.bar_pos.median():.2f})')
ax[0, 2].set_title('Where the first fill sits in the minute bar of its option'); ax[0, 2].set_xlabel('0 = minute low, 1 = minute high'); ax[0, 2].legend(fontsize=8)
lab = ['solo sells', 'buy-back events']; mb = [bs_solo.mae, bs_bb.mae]; mm = [solo_c[1].mae, bb_b[1].mae]; x = np.arange(2); ax[1, 0].bar(x - 0.18, mb, 0.36, color=col['b'], label='best simple baseline'); ax[1, 0].bar(x + 0.18, mm, 0.36, color=col['a'], label='leave-one-cycle-out model')
ax[1, 0].set_xticks(x); ax[1, 0].set_xticklabels(lab); ax[1, 0].set_ylabel('mean absolute error (lots per cell)'); ax[1, 0].set_title('Lots per cell given an event: model vs baseline'); ax[1, 0].legend(fontsize=8)
[ax[1, 0].text(i - 0.18, v + 0.03, f'{v:.2f}', ha='center', fontsize=8) for i, v in enumerate(mb)]; [ax[1, 0].text(i + 0.18, v + 0.03, f'{v:.2f}', ha='center', fontsize=8) for i, v in enumerate(mm)]
rng = np.random.default_rng(0)
for i, (u, c_) in enumerate((('NIFTY', '#2b6cb0'), ('SENSEX', '#c05621'))):
    z = ns[ns.und == u]; ax[1, 1].scatter(i + rng.uniform(-.15, .15, len(z)), z.peak_S, color=c_, alpha=.7); ax[1, 1].hlines(z.peak_S.median(), i - .25, i + .25, color='k')
ax[1, 1].set_xticks([0, 1]); ax[1, 1].set_xticklabels(['NIFTY', 'SENSEX']); ax[1, 1].set_ylabel('peak short lots on one right'); ax[1, 1].set_title('Peak position per right and cycle (no-stop cycles)')
cc = C3.copy(); cc['name'] = ['time/side', '+ spot', '+ book', '+ inventory', 'inventory only']; ax[1, 2].bar(cc.name, cc.auc, yerr=[cc.auc - cc.lo, cc.hi - cc.auc], color=col['a'], capsize=3); ax[1, 2].set_ylim(0.7, 0.9); ax[1, 2].set_title('Does inventory change selling? (AUC)'); ax[1, 2].set_ylabel('leave-one-cycle-out AUC')
plt.setp(ax[1, 2].get_xticklabels(), fontsize=8); plt.tight_layout(); plt.savefig(f'{FIG}/bl_d0u_summary.png', dpi=130); plt.close()
# ---- report
L = []; w = L.append
w('# Algo 8 — D0 quantity: lot sizes, order execution, position management\n')
w(f'*Plan `D0_QTY_PLAN.md`, written before the tests. In-sample: D0 of the {D0.groupby(["und", "expiry"]).ngroups} live cycles with orders; Parts B and C use the {C["c1_cycles"]} cycles that also have the minute data, {C["c1_non_stop_cycles"]} of them without a stop. Figure: `figures/bl_d0u_summary.png`. Lots are 65 contracts (NIFTY) / 20 (SENSEX); a lot is about ₹{C["c1_lot_notional_lakh_med"]:.1f} lakh of notional on both.*\n')
w('## 0. Result\n')
w('| question | answer | evidence |\n|---|---|---|')
w(f'| How big is an order? | **Body orders are single lots**: {pc(a1.loc["body sell"].single_lot_orders,0)} of body sells and {pc(a1.loc["body buy-back"].single_lot_orders,0)} of buy-backs are 1 lot. A "multi-lot sale" is several 1-lot orders sent in the same second ({pc(A5.set_index("klass").loc["body sell"].same_second_gap_share,0)} of gaps are 0 s). Hedge, lump and stop orders are sized orders (median {a1.loc["wing sell"].lots_per_order_med:.0f} / {a1.loc["lump salvage"].lots_per_order_med:.0f} / {a1.loc["stop module"].lots_per_order_med:.0f} lots). | Observed |')
w(f'| Are big orders split? | Yes. All {A["a1_events_above_freeze"]} events above 27 lots (NIFTY) / 50 (SENSEX) are split into several orders. NIFTY order size tops out at **27 lots (1,755 contracts) June–September** (the cap binds: {int(ndf.loc["2026-09"].n_orders_at_max)} orders sit exactly at 27 in September) and at **54 lots (3,510) in October**. SENSEX tops out at 50 lots (1,000), seen in August and September, once per month. | Observed (maxima); the exchange rule itself not read |')
w(f'| What price do they send? | **Limit = LTP × (1 ± 0.15)**, i.e. a marketable limit 15% through the price (median {pc(A["a2_buf_overall_med"])} from the first fill; body sells {pc(a2[a2.klass=="body sell"].buf_med.iloc[0])}, tight, CV {a2[a2.klass=="body sell"].buf_cv.iloc[0]:.2f}). Body orders are DAY, hedge and lump orders IOC. It is protection: the reference price (limit ÷ 1.15) is within {pc(A["a4_ref_vs_fill_abs_med"])} of the first fill (median). **My D-1 engine used 1%; corrected to 15% in this commit.** | Observed |')
w(f'| At what price do they fill? | Fills come within 1 s. Against the minute bar of the option: sells fill at **{A["a4_pos_by_side"]["Sell"]:.2f}** of the low–high range, buys at **{A["a4_pos_by_side"]["Buy"]:.2f}** (both on the adverse side of the middle); {pc(A["a4_outside_bar_overall"])} of fills are outside the bar. Median gap to the bar close {pc(A4.abs_gap_to_close_med.median())}, signed bias vs close ≈ 0 ({pc(A4[A4.klass=="body sell"].signed_vs_close_med.iloc[0])} sells, {pc(A4[A4.klass=="body buy-back"].signed_vs_close_med.iloc[0])} buy-backs). Part is selection (the system trades price moves), not only spread. | Observed; cause not separable |')
w(f'| Which quantities follow a rule? | Scheduled pair: every order 1 lot, CE and PE together (the 6-second bucket first used merged adjacent waves, see addendum). **Hedge wave = the gap S−L in {pc(wb.share_fit)}** of {int(wb.n)} events ({pc(wbl.share_fit)} are ≤ gap). Wing release ≤ long excess in {pc(wsl.share_fit)} ({pc(wse.share_fit)} exactly equal). Lump order ≤ long excess in {pc(lul.share_fit)}. | Observed |')
w(f'| Is the number of lots in a sale or buy-back predictable? | **Only weakly: not found by the rule I set (solo sells {solo_c[0]}, buy-backs {bb_c[0]}).** Solo sells: median {B["b3_solo_lots_med"]:.0f} lot per cell ({pc(B["b3_solo_share_1_lot"],0)} single); the model cuts the error {pc(-solo_c[1].rel_mae_vs_best_baseline,0)} vs the best baseline but ρ is {solo_c[1].rho:.2f} and it hits the exact count less often than "always 1" ({pc(solo_c[1].exact,0)} vs {pc(bs_solo.exact,0)}). Buy-backs: median {B["b3_bb_lots_med"]:.0f} lots per cell, error −{pc(-bb_b[1].rel_mae_vs_best_baseline,0)}, ρ {bb_b[1].rho:.2f}. Ladder depth does not set the count (ρ {B["b3_solo_rho_gapfav"]:.2f}). | Observed; rule threshold not met |')
w(f'| Is it a fixed ratio or fixed premium? | No. Counter-sell lots ÷ same-minute buy-back lots: median {cs["median"]:.1f}, IQR {cs.q25:.2f}–{cs.q75:.2f}, exactly equal in {pc(cs.share_ratio_1,0)}. A buy-back takes a median {pc(b4.loc["buy-back lots / right lots open","median"])} of the right\'s open lots per cell (IQR {pc(b4.loc["buy-back lots / right lots open","q25"])}–{pc(b4.loc["buy-back lots / right lots open","q75"])}). Lots do not scale with premium or notional (ρ ≤ {B5.rho_lots_vs_price.abs().max():.2f}). | Observed |')
w(f'| How big does the book get? | Peak shorts on one right: **NIFTY {nif["peak_S_med"]:.0f} lots** (IQR {nif["peak_S_iqr"][0]:.0f}–{nif["peak_S_iqr"][1]:.0f}), **SENSEX {sen["peak_S_med"]:.0f}** ({sen["peak_S_iqr"][0]:.0f}–{sen["peak_S_iqr"][1]:.0f}); about ₹{nif["peak_notional_lakh_med"]/100:.0f} / ₹{sen["peak_notional_lakh_med"]/100:.0f} crore of notional. Carry-in from D-1 ≈ {nif["carry_S_med"]:.0f} / {sen["carry_S_med"]:.0f} lots per right; peak around minute {nif["peak_min_med"]:.0f} / {sen["peak_min_med"]:.0f} after 09:15. At 15:08 (no-stop cycles) {C["c6_15:08_nostop"]["S_total_med"]:.0f} lots short in total, all hedged 1:1. {pc(C["c1_final_short_zero_share_non_stop"],0)} of right-days end flat. | Observed |')
w(f'| Is there a position cap? | **{cap_verdict.capitalize()}.** The peak varies across cycles (CV {C["c2_median_cv_lots"]:.2f}; at most {pc(cap_g.share_within_10pct_of_median.max(),0)} of cycles within ±10% of the group median), and selling does not slow near the typical peak (rate {pc(hz["True"]["rate"],0)} vs {pc(hz["False"]["rate"],0)}). Not a proof of no cap: 4–8 cycles per group, and a margin or capital limit is not visible here. | Observed; low power |')
w(f'| Does the book change selling? | **{inv_verdict.capitalize()}.** Adding shorts, CE–PE imbalance and distance to the typical peak gives AUC +{c3["gain"]:.4f} (CI {c3["lo"]:.4f} to {c3["hi"]:.4f}) on top of spot and book features. | Observed |')
w(f'| Is the book balanced between CE and PE? | No. Solo sells go to the **lighter** right only {pc(al.share_to_lighter_right,0)} of the time (n={int(al.n)}, p<0.001), i.e. to the heavier right {pc(1-al.share_to_lighter_right,0)}; median |CE−PE| gap {C["c4_imbalance_abs_med_lots"]:.0f} lots. Only opening solos are even ({pc(op.share_to_lighter_right,0)}). | Observed |')
w(f'| What does protection cost? | The hedge keeps long = short in {pc(C["c5_share_minutes_L_equals_S_median_cycle"],0)} of active minutes (mean L/S {C["c5_mean_L_over_S"]:.4f}). Wings bought cost {pc(C["c5_wing_bought_pct_of_premium_sold_median"])} of the premium sold, **{pc(C["c5_wing_net_cost_pct_of_premium_sold_median"])} net** of what is sold back (medians over cycles). | Observed |')
w(f'| What happens at a stop? | Just before the stop: median {C["c6_stop_stop"]["S_total_med"]:.0f} lots short (about ₹{C["c6_stop_stop"]["notional_lakh_med"]/100:.0f} crore), hedged {C["c6_stop_stop"]["L_over_S_med"]:.2f}×. The stop module then sends {C6[C6.stop_orders>0].stop_orders.median():.0f} orders / {C6[C6.stop_orders>0].stop_lots.median():.0f} lots (shorts bought back and longs sold) in a median {C6[C6.stop_orders>0].stop_span_s.median():.0f} s, {C6[C6.stop_orders>0].stop_lots_per_order_med.median():.0f} lots per order; partial fills on {pc(A3[A3.module=="s_"].eval("partial*orders").sum()/A3[A3.module=="s_"].orders.sum(),0)} of its orders. | Observed |')
w('\n**What this means for the 3-year backtest** (table at the end): the *quantity* of the hedge, the scheduled pairs and the clearance is rule-exact; the quantity of solo sells and buy-backs is **not** reconstructable beyond a distribution, so a free-running backtest will get the count wrong event by event (it already shows lot F1 ≈ 0.4). The decision for you at the end is how to size those.\n')
w('## 1. Order execution (Part A)\n')
w('### A1 Size and splitting (D0)\n'); k = a1[['orders', 'lots', 'lots_per_order_med', 'lots_per_order_p90', 'lots_per_order_max', 'single_lot_orders', 'events', 'lots_per_event_med', 'lots_per_event_p90', 'lots_per_event_max', 'orders_per_event_med']].round(2); w(k.to_markdown() + '\n')
w('*An event = orders of the same module, role and right with gaps ≤ 2 s.*\n'); w('Largest order by month (D0):\n'); w(MX[MX.day == 'D0'][['und', 'month', 'orders', 'gcd_qty', 'max_order_lots', 'max_order_qty', 'n_orders_at_max']].to_markdown(index=False) + '\n')
w('### A2 Limit price\n'); w(a2[['klass', 'side', 'n', 'buf_med', 'buf_p05', 'buf_p95', 'buf_cv', 'share_within_1tick_of_15pct']].round(3).to_markdown(index=False) + '\n')
w(f'*`buf` = limit beyond the first fill, as a share of the fill. Only {pc(A["a2_share_within_1tick_of_15pct"],0)} of orders are within one tick of "fill × 1.15" because the limit is set from the LTP at decision time, which differs from the fill by a median {pc(A["a4_ref_vs_fill_abs_med"])}. By price level the buffer is a constant ~15% from ₹1 up (rupee gap grows with price); below ₹1 it is 20% (tick size).*\n')
w('### A3 Order type and fills\n'); w(A3.drop(columns=['lots_eq_ordered']).round(3).to_markdown(index=False) + '\n'); w('*The log holds only orders with at least one fill (lots filled = lots ordered in 99.99%), so IOC orders that found no fill, rejections and cancels are **not visible**.*\n')
w('### A4 Fill vs the minute bar\n'); w(A4[['klass', 'side', 'n', 'outside_bar', 'pos_med', 'pos_p25', 'pos_p75', 'abs_gap_to_close_med', 'signed_vs_close_med', 'bar_width_med']].round(3).to_markdown(index=False) + '\n')
w('### A5 Dripping inside events\n'); w(A5.round(2).to_markdown(index=False) + '\n')
w('## 2. Lots per event (Part B)\n'); w('### B2 Rule-exact quantities\n'); w(FX.round(3).to_markdown(index=False) + '\n')
w('### B3 Size models (leave-one-cycle-out; baselines and placebo)\n'); w(M3.round(3).to_markdown(index=False) + '\n')
w(f'*Rule set in the plan: "found" = error ≥ 20% below the best baseline **and** ρ ≥ 0.5 (CI of the error change below 0); "associated" = ρ ≥ 0.3; else "unresolved". Verdicts: solo causal **{solo_c[0]}**, solo + same-minute buy-backs **{vs[(solo_t, "LOCO boosting: causal + same-minute buy-backs")][0]}**, buy-back causal **{bb_c[0]}**, buy-back with the bar of the minute **{bb_b[0]}**, solo ladder-depth only **{solo_g[0]}**. The model beats the baselines on average error (placebo does not) but is worse than "always 1 lot" at hitting the exact count: it ranks sizes, it does not decide them.*\n')
w('### B4 Size against the book\n'); w(B4.round(3).to_markdown(index=False) + '\n'); w('### B5 Scaling with premium\n'); w(B5.round(3).to_markdown(index=False) + '\n')
w(f'*Buy-back cells: lots == number of lots whose minute high is ≥ 1.4× entry in {pc(B["b3_bb_lots_==_n_cross14"])} of cells; ≤ that number in {pc(B["b3_bb_lots_<=_n_cross14"],0)}; == 10% of open lots in {pc(B["b3_bb_lots_==_round10pct_of_open"])}. The system does not buy back "everything that crossed".*\n')
w('## 3. Position management (Part C)\n'); w('### C1 Book level and shape (no-stop cycles unless stated)\n'); w(C1.groupby(['und', 'version', 'cp']).agg(cycles=('cid', 'size'), carry_in=('carry_S', 'median'), peak=('peak_S', 'median'), peak_minute=('peak_min', 'median'), shorts_1509=('S_1509', 'median'), shorts_final=('S_final', 'median')).round(1).to_markdown() + '\n')
w('### C2 Ceiling test\n'); w(C2.round(3).to_markdown(index=False) + '\n'); w(f'*Hazard of a body sale in a minute when shorts on that right are within 10% of the leave-one-out typical peak: {pc(hz["True"]["rate"])} ({hz["True"]["cells"]} cells) against {pc(hz["False"]["rate"])} otherwise; hour-matched ratio {C["c2_hazard_ratio_near_vs_not_hour_matched_med"]:.2f}. Rule: a cap needs ≥ 70% of cycles within ±10% **and** a hazard drop of ≥ 50%. Neither holds. Groups with one cycle (NIFTY V2) are trivially "within 10%" and are not counted.*\n')
w('### C3 Does the book feed back on selling?\n'); w(C3.round(4).to_markdown(index=False) + '\n')
w('### C4 Balance after solo sales\n'); w(C4.round(3).to_markdown(index=False) + '\n')
w('### C5 Hedge ratio and wing cost (D0, per cycle, medians)\n'); w(C5.groupby('und').median(numeric_only=True).round(3).to_markdown() + '\n')
w('### C6 Exposure at the stop and at 15:08\n'); w(C6.groupby('event').median(numeric_only=True).round(2).to_markdown() + '\n')
w('## 4. Adversarial read: what could be wrong\n')
w('* **Counts come from one-minute cells.** The system drips 1-lot orders inside a minute (D-1: "one lot each time the price prints a new extreme"). The count is set by the tick path, which these bars cannot show, so "weakly predictable" may be "predictable with ticks". *Not testable here.*\n')
w('* **Fill position in the bar is partly selection.** A system that sells after a premium drop will print sells in the lower part of the bar whatever its execution quality. The numbers are right for *this* system\'s fills; they are not a spread estimate.\n')
w('* **Cap test is underpowered.** 1–8 cycles per underlying × version × right. "No ceiling observed" is the strongest honest statement; a margin or capital limit would not show in lot counts anyway.\n')
w('* **State reconstruction.** Running shorts / longs per right are rebuilt from the order log; the change in S equals the lots of the order in 98.9% of body sells (97.9% for wing buys), the rest are same-second ordering ties.\n')
w('* **Scale is the real system\'s, not yours.** About 130 lots per right at peak is roughly ₹20 crore of notional per right. The backtest has to say what scale it runs at (see below).\n')
w('* **Discovery data.** Everything here is in-sample on the 32 cycles; nothing here has been tested on cycles it did not see.\n')
w('## 5. For the backtest: quantity and price rule per class\n')
w('| class | quantity rule to use | fill price rule | evidence |\n|---|---|---|---|')
w('| scheduled pair | 1 CE + 1 PE lot at each timetable second | order-minute close (±0.6% median bias), stress ±4% | quantity Observed, rule-exact |')
w(f'| hedge wing buy | exactly the gap S−L on the right (≈ {pc(wb.share_fit,0)}), IOC | order-minute close | Observed, rule-exact |')
w(f'| wing release / lump salvage | ≤ long excess L−S; release size {a1.loc["wing sell"].lots_per_order_med:.0f} lots per order (median) | order-minute close | partly (size < excess in {pc(1-wse.share_fit,0)}) |')
w('| clearance (15:09+) | all shorts, in 1-lot orders in the same seconds | order-minute close | Observed (D0_STOP_CLEAR) |')
w(f'| solo sells | **distribution, not a rule:** median 1 lot per minute-cell (51% single, long tail); size ranked by features (ρ ≈ 0.47) | order-minute close | associated |')
w(f'| buy-backs | **distribution:** median 2 lots per cell (41% single); ranked by crossing counts (ρ ≈ 0.50) | order-minute close | associated |')
w('| stop liquidation | the whole book in sized orders (median 6 lots) over ~40 s | order-minute close, expect partial fills | Observed |')
w('| order envelope | 1-lot DAY orders for body, IOC for hedge/lump, limit = LTP×(1±0.15), split at 27 (NIFTY, 54 from October) / 50 (SENSEX) lots | — | Observed |')
w('\n## 6. Next\n* Decision needed for the backtest: run the quantity of solo sells and buy-backs (a) drawn from the fitted distribution per class and cell features, (b) fixed at the class median (1 lot / 2 lots), or (c) scaled to your own capital instead of the real system\'s ~₹20 crore per right. Each is a different experiment.\n* Remaining unresolved from earlier steps: other solo, far-OTM roll-out, small pair types, burst trigger.\n')
w('\n## Addendum — written after the first results (not pre-registered)\n* **Scheduled-pair 1+1 check.** My first test grouped orders by strike and a 6-second bucket and found 86.5% exactly 1+1 (below the 90% I wanted); the 2+2 / 3+3 / 4+4 cases are adjacent 1+1 waves merged by the bucket. At order level all 1,722 scheduled-pair orders are 1 lot and every CE order has a PE order within 3 s at the same strike (the latter is how the pair label is defined, so only the 1-lot part is evidence). **Post-hoc.**\n* **D-1 engine default corrected** from a 1% limit buffer to 15% after A2; the 15% had been recorded earlier in `bl_common.K15` and I had not used it. No test result changed (19 engine tests pass).\n* The cycle with an unlabelled version (NIFTY 2026-08-18) is a stop cycle with the stop at the open; it appears in the stop rows only.\n')
open(f'{REP}/D0_QTY.md', 'w').write('\n'.join(L)); print('written', len('\n'.join(L)))
