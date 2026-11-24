"""Builds reports/UNRESOLVED_THREE.md and figures/bl_unres.png (plan reports/UNRESOLVED_THREE_PLAN.md)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); UN = f'{OUT}/unres'; RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures'); RES = f'{OUT}/bt3_results'
def _md(d):
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return '| ' + ' | '.join(map(str, d.columns)) + ' |\n|' + '---|' * len(d.columns) + '\n' + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pc = lambda x, d=0: f'{100 * x:.{d}f}%'; lk = lambda x: f'{x / 1e5:,.1f}'; cr = lambda x: f'{x / 1e7:,.2f}'
FC = json.load(open(f'{OUT}/final/final_checks.json')); CAS = pd.read_csv(f'{OUT}/final/final_e1_cas.csv').set_index('regime')
CY = pd.read_csv(f'{UN}/real_margin_cycles.csv'); SM = pd.read_csv(f'{UN}/real_margin_samples.csv'); M = pd.read_csv(f'{UN}/margin_stats.csv').set_index('stat'); GT = pd.read_csv(f'{UN}/gap_tables.csv'); EVT = pd.read_csv(f'{UN}/evt_fit.csv').set_index('index').T; EV = pd.read_csv(f'{UN}/ev_table.csv')
NG = json.load(open(f'{UN}/nightgap_summary.json')); GS = json.load(open(f'{UN}/unres_gap_summary.json')); CG = pd.read_csv(f'{UN}/cycle_night_gaps.csv'); PS = pd.read_csv(f'{UN}/prem_stats.csv'); MS = pd.read_csv(f'{UN}/prem_moneyness_stats.csv'); FS = pd.read_csv(f'{UN}/prem_flow_stats.csv'); PC = pd.read_csv(f'{UN}/prem_cycles.csv'); PIN = pd.read_csv(f'{UN}/prem_pin.csv')
ps = lambda t, key: PS[(PS.test == t) & PS.stat.str.contains(key, regex=False)].iloc[0]; m = lambda k: M.loc[k]
real = CY[CY.book == 'real']; simc = CY[CY.book == 'sim_full'].set_index(['und', 'expiry']).loc[list(zip(real.und, real.expiry))]
rs = SM[SM.book == 'real']; peakD1 = rs[rs.day == 0].groupby(['und', 'expiry']).margin_nse.max().median(); peakD0 = rs[rs.day == 1].groupby(['und', 'expiry']).margin_nse.max().median(); iv = pd.read_csv(f'{RES}/alpha_iv_cycles.csv'); floor_share = 1 - float((6 * np.sqrt(2) * iv.iv_D1_open / np.sqrt(250) > 0.093).mean())
# ---------------- stress table (IV x 1.5) and ruin shares
def row(book, g, vm=1.5): r = GT[(GT.book == book) & (GT.gap.round(3) == g) & (GT.vm == vm)].iloc[0]; return r
ST = []
for lab, book in (('real book (long legs as traded)', 'real'), ('same shorts, long legs removed', 'real_no_longs'), ('simulated full book', 'sim_full'), ('simulated, no D-1 longs', 'sim_d1_no_wings'), ('simulated, no lump', 'sim_d1_no_lump')):
    d = {'book': lab}
    for g in (-0.10, -0.05, 0.05, 0.10): r = row(book, g); d[f'{int(100 * g):+d}%: mean / worst (₹ lakh)'] = f'{lk(r["mean"])} / {lk(r.worst)}'
    ST.append(d)
ST = pd.DataFrame(ST)
RU = pd.DataFrame([{'gap (IV ×2.0)': f'{int(100 * g):+d}%', **{lab: pc(row(b, g, 2.0).share_over_2cr, 0) for lab, b in (('real book', 'real'), ('real, long legs removed', 'real_no_longs'), ('simulated full', 'sim_full'), ('simulated, no D-1 longs', 'sim_d1_no_wings'))}, 'real no-longs: worst loss (₹ crore)': cr(row('real_no_longs', g, 2.0).worst)} for g in (-0.15, -0.10, 0.10, 0.15)])
# ---------------- EVT / documented frequency
n_doc = GS['doc_nights']; p_doc = GS['doc_prob_per_night']; evn = EVT['NIFTY']; evs = EVT['SENSEX']
EV_b = EV[EV.vol_shock.str.startswith('base')].set_index('books')
EVT_tab = pd.DataFrame([{'|gap| ≥': f'{x}%', 'NIFTY: probability per night [95%]': f"{pc(evn[f'P(|gap|>={x}%)'], 3)} [{pc(evn[f'P{x}_lo'], 3)}, {pc(evn[f'P{x}_hi'], 3)}]", 'SENSEX': pc(evs[f'P(|gap|>={x}%)'], 3), 'exponential tail (NIFTY)': pc(evn[f'P(|gap|>={x}%) shape0'], 4), 'shape 0.3 (NIFTY)': pc(evn[f'P(|gap|>={x}%) shape0.3'], 3),
                         'break-even probability, simulated / real books': f"{pc(EV_b.loc['simulated books', f'breakeven_prob_{x}%'], 2)} / {pc(EV_b.loc['real books', f'breakeven_prob_{x}%'], 2)}"} for x in (3, 5, 7, 10)])
EVtab = EV[['books', 'vol_shock', 'ev_in_sample_nights', 'ev_gpd', 'ev_gpd_extra_beyond_sample', 'ev_documented_extra_phi1', 'ev_documented_extra_phi05']].copy()
for c_ in EVtab.columns[2:]: EVtab[c_] = EVtab[c_].map(lambda v: f'{v:,.0f}')
EVtab.columns = ['books', 'volatility shock', 'gap-protection value over the 770 nights (₹ per cycle)', 'same, GPD tail model', 'extra from tail beyond the sample (GPD)', 'extra from documented falls 2000–2022, gap = full move', 'same, gap = half the move']
# ---------------- Q1 tables
E1 = pd.DataFrame([dict(stat=k, **{'all [95%]': f"{v.value:.2f} [{v.lo:.2f}, {v.hi:.2f}]" if 'ariance' in k or 'Var' in k else f"{pc(v.value, 1)} [{pc(v.lo, 1)}, {pc(v.hi, 1)}]", 'IS': f"{v.IS:.2f}" if ('ariance' in k or 'Var' in k) else pc(v.IS, 1), 'OOS': f"{v.OOS:.2f}" if ('ariance' in k or 'Var' in k) else pc(v.OOS, 1), 'live window (36)': f"{v.live:.2f}" if ('ariance' in k or 'Var' in k) else pc(v.live, 1)}) for k, v in ((r.stat, r) for r in PS[PS.test == 'E1'].itertuples())])
MSm = MS.copy(); MSm['strikes'] = MSm.side.map({'PE': 'put', 'CE': 'call'}) + ' ' + (100 * MSm.dist).map(lambda x: f'{x:g}%') + ' away'
MSt = pd.DataFrame({'option (09:16 open, held to settlement)': MSm.strikes, 'expires in the money': MSm.share_expiring_in_the_money.map(lambda x: pc(x, 1)), 'mean price': MSm.mean_price.round(2), 'mean payoff': MSm.mean_payoff.round(2), 'price ÷ payoff [95%]': [f'{r.price_over_payoff:.2f} [{r.po_lo:.2f}, {r.po_hi:.1f}]' if np.isfinite(r.price_over_payoff) else 'no payoff in 275 cycles' for r in MS.itertuples()], 'price − payoff, % of ATM straddle': MSm.premium_minus_payoff_pct_of_atm_straddle.map(lambda x: pc(x, 1))})
E5 = PS[PS.test == 'E5']; E5t = pd.DataFrame({'segment (short ATM straddle sold 09:16)': E5.stat.str.replace('short ATM straddle, ', '', regex=False).str.replace(', % of the 09:16 premium', '', regex=False), 'P&L, % of the 09:16 premium [95%]': [f'{pc(r.value, 1)} [{pc(r.lo, 1)}, {pc(r.hi, 1)}]' for r in E5.itertuples()]})
t1 = pd.read_csv(f'{OUT}/thesis/thesis_t1.csv'); d0 = t1[(t1.segment == 'D0 day') & (t1.iv_used > 0)][['und', 'expiry', 'iv_used', 'rv']]; jj = d0.merge(PC[['und', 'expiry', 'x_print', 'x_settle']], on=['und', 'expiry']); avg_share = float(((jj.x_print ** 2 - jj.x_settle ** 2).sum()) / (jj.iv_used.sum() - jj.rv.sum()))
x1 = ps('E1', 'Var[ln'); ex = ps('E1', 'extra premium'); s_pr = ps('E1', 'to the 15:29 print'); s_st = ps('E1', 'to the official settlement'); rv_s = ps('E1', 'realised / implied variance, 15:00 to settlement'); rv_p = ps('E1', 'realised / implied variance, 15:00 to the 15:29 print')
e2 = ps('E2', 'distance'); e2b = ps('E2', 'share of cycles'); e4 = FS.set_index('target')
# ---------------- figure
fig, ax = plt.subplots(2, 3, figsize=(19, 10.5))
ax[0, 0].hist([real.peak_nse / 1e7, simc.peak_nse / 1e7], bins=np.arange(0, 3.6, .25), label=['real book', 'simulator, same cycles'], color=['#2b6cb0', '#999999']); ax[0, 0].axvline(2, color='#c53030', ls='--', label='₹2 crore capital'); ax[0, 0].set_xlabel('peak approximate margin per cycle, ₹ crore'); ax[0, 0].set_ylabel('cycles'); ax[0, 0].legend(fontsize=8)
ax[0, 0].set_title(f'Q2: real book peaks at ≈ {cr(m("real peak margin, median (₹ crore)").value * 1e7)} cr (median); {pc(m("real cycles with peak margin > ₹2 crore").value)} of cycles above ₹2 cr')
gg = GT[GT.vm == 1.5];
for book, col, lab in (('real', '#2b6cb0', 'real book'), ('real_no_longs', '#c53030', 'same shorts, long legs removed')):
    q = gg[gg.book == book].sort_values('gap'); ax[0, 1].plot(100 * q.gap, q['mean'] / 1e7, color=col, marker='o', label=lab); ax[0, 1].fill_between(100 * q.gap, q.best / 1e7, q.worst / 1e7, color=col, alpha=.12)
ax[0, 1].axhline(2, color='k', ls='--', lw=.8, label='₹2 crore capital'); ax[0, 1].axhline(0, color='k', lw=.5); ax[0, 1].set_xlabel('overnight gap, %'); ax[0, 1].set_ylabel('loss of the carried book, ₹ crore (IV × 1.5)'); ax[0, 1].legend(fontsize=8); ax[0, 1].set_ylim(-1.8, 4.5)
ax[0, 1].set_title('Q3: with its long legs the book is long the tail;\nwithout them a 10–15% gap costs ₹0.6–1.3 cr on average (band = best to worst book)', fontsize=10)
a = np.sort(pd.read_csv('../../../../data_validation/reference/yahoo_daily_NSEI.csv', parse_dates=['date_ist']).pipe(lambda d: np.abs(np.log(d.open.values[1:] / d.close.values[:-1])))); sf = 1 - np.arange(1, len(a) + 1) / (len(a) + 1)
ax[0, 2].loglog(100 * a, sf, '.', color='#2b6cb0', label='NIFTY nights 2023–26 (770)'); xs = np.linspace(evn['threshold_u'], .15, 200); xi, b_, u_ = evn['shape'], evn['scale'], evn['threshold_u']; ax[0, 2].loglog(100 * xs, (evn['exceedances'] / evn['nights']) * (1 + xi * (xs - u_) / b_) ** (-1 / xi), color='k', label='generalised Pareto fit')
ax[0, 2].axhline(p_doc, color='#c05621', ls=':', label=f'documented falls ≥ 5% (close-to-close, 2000–22): {pc(p_doc, 2)}/night'); ax[0, 2].axhline(EV_b.loc['simulated books', 'breakeven_prob_5%'], color='#2f855a', ls='--', label='break-even for the long legs at a 5% gap'); ax[0, 2].axhline(EV_b.loc['simulated books', 'breakeven_prob_10%'], color='#2f855a', ls='-.', label='break-even at a 10% gap')
ax[0, 2].set_xlabel('|overnight gap|, %'); ax[0, 2].set_ylabel('probability per night of a larger gap'); ax[0, 2].set_xlim(.3, 15); ax[0, 2].set_ylim(1e-4, 1); ax[0, 2].legend(fontsize=7); ax[0, 2].set_title('Q3: the calm 3 years cannot see the tail the break-even needs')
spl = ['IS', 'OOS', 'LIVE_FITTED']; xloc = np.arange(3); ax[1, 0].bar(xloc - .2, [ex.IS, ex.OOS, ex.live], .4, color='#2b6cb0', label='extra premium from settlement averaging'); ax[1, 0].bar(xloc + .2, [1 - x1.IS, 1 - x1.OOS, 1 - x1.live], .4, color='#c05621', label='1 − variance ratio (settlement ÷ print)'); ax[1, 0].axhline(0, color='k', lw=.6)
ax[1, 0].set_xticks(xloc); ax[1, 0].set_xticklabels(['in-sample (175)', 'out-of-sample (64)', 'live window (36)']); ax[1, 0].legend(fontsize=8); ax[1, 0].set_title('Q1/E1: the official settlement is calmer than the last print —\nuntil the closing auction (3 Aug 2026)', fontsize=10)
for side, col in (('PE', '#c53030'), ('CE', '#2b6cb0')):
    q = MS[(MS.side == side) & MS.price_over_payoff.notna()]; ax[1, 1].semilogy(100 * q.dist, q.price_over_payoff, marker='o', color=col, label='puts' if side == 'PE' else 'calls')
ax[1, 1].axhline(1, color='k', ls='--', lw=.8); ax[1, 1].set_xlabel('distance of strike from spot, %'); ax[1, 1].set_ylabel('price ÷ realised payoff (>1: over-priced)'); ax[1, 1].legend(); ax[1, 1].set_title('Q1/E3: over-pricing rises with distance, puts more than calls')
labs = ['09:16–14:00', '14:00–15:14', '15:14–settle', 'total']; vals = [E5.iloc[i] for i in (0, 1, 2, 3)]; ax[1, 2].bar(range(4), [100 * v.value for v in vals], yerr=[[100 * (v.value - v.lo) for v in vals], [100 * (v.hi - v.value) for v in vals]], color='#2b6cb0', capsize=5); ax[1, 2].axhline(0, color='k', lw=.6)
ax[1, 2].set_xticks(range(4)); ax[1, 2].set_xticklabels(labs); ax[1, 2].set_ylabel('short ATM straddle P&L, % of 09:16 premium'); ax[1, 2].set_title('Q1/E5: the expiry-day straddle P&L is positive in every slice\nbut statistically indistinguishable from zero')
plt.tight_layout(); os.makedirs(FIG, exist_ok=True); plt.savefig(f'{FIG}/bl_unres.png', dpi=110); plt.close()
json.dump(dict(real_peak_median_cr=float(m('real peak margin, median (₹ crore)').value), real_over_2cr=float(m('real cycles with peak margin > ₹2 crore').value), spearman=float(m('Spearman real vs simulator peak margin').value), max_gap_first_print=NG['max_abs_first_print'],
               var_ratio_settle_print=float(x1.value), extra_premium_settlement=float(ex.value), extra_lo=float(ex.lo), live_var_ratio=float(x1.live), pin_share=float(e2b.value), pin_share_lo=float(e2b.lo), flow_next=float(e4.loc['dw_next_surprise', 'spearman']), flow_next_hi=float(e4.loc['dw_next_surprise', 'hi']),
               ev_gpd_extra=float(EV_b.loc['simulated books', 'ev_gpd_extra_beyond_sample']), ev_doc_phi1=float(EV_b.loc['simulated books', 'ev_documented_extra_phi1']), ev_doc_phi05=float(EV_b.loc['simulated books', 'ev_documented_extra_phi05']), cost=float(GS['cost']),
               nolongs_worst_15=float(row('real_no_longs', 0.15, 2.0).worst), full_worst_15=float(row('real', 0.15, 2.0).worst), full_mean_m15=float(row('real', -0.15)['mean']), avg_share=avg_share), open(f'{UN}/unres_summary.json', 'w'), indent=1)
GAPTOP = CG.reindex(CG.gap_min_0915.abs().sort_values(ascending=False).index).head(4); GAPTOP = pd.DataFrame({'night (D-1 → D0)': GAPTOP.d1 + ' → ' + GAPTOP.d0, 'index': GAPTOP.und, 'gap at the first print': (100 * GAPTOP.gap_min_0915).map(lambda x: f'{x:+.2f}%'), 'gap at the 09:16 open': (100 * GAPTOP.gap_min_0916).map(lambda x: f'{x:+.2f}%'), 'daily file': (100 * GAPTOP.gap_daily).map(lambda x: f'{x:+.2f}%')})
md = f"""# The three unresolved questions — result

*Plan: `UNRESOLVED_THREE_PLAN.md` (committed before the tests). Builds on `PREMIUM_AND_ARCHITECTURE.md`. 275 cycles (Nov 2023 – Nov 2026), 35 of them with the real order log. Every cycle was used before: **exploratory**. Figure: `figures/bl_unres.png`.*

## 0. Corrections first
1. **Overnight gap — corrected twice.** My first reports used the 09:16 open (largest cycle-night gap **{pc(FC['max_abs_gap_0916'], 2)}**). In the previous version of this report I called that wrong because the first print (09:15) of 3 Feb 2026 is **{pc(NG['max_abs_first_print'], 2)}**. Checking the raw bars (review, 24 Nov): that print existed only at the opening tick — NIFTY printed {FC['feb3']['d0_0915_open']:,.2f} against a previous close of {FC['feb3']['d1_close_1529']:,.2f}, then traded down to {FC['feb3']['d0_0915_low']:,.2f} and closed the first minute at {FC['feb3']['d0_0915_close']:,.2f} (**{pc(FC['feb3']['gap_after_first_minute'], 2)}**), and several 09:15 option prints were stale (a 26400 call at ₹0.90, a 25700 put at ₹631). **For anything that can be traded, the 09:16 measure ({pc(FC['max_abs_gap_0916'], 2)}) is the right one**; the first print is kept only as an upper bound for tail statistics. Only {FC['first_print_vs_0916_diff_over_1pct']} of 275 cycle nights differ by more than 1% between the two. The −5.13% daily-file gap of 7 Apr 2025 is not a cycle night.
2. **What the 3 Feb 2026 night was worth to the long legs** (previous version: "≈ ₹7 lakh" — wrong attribution). The overnight mark-to-market of the carried book at the first tradeable minute was −₹{-FC['feb3_decomposition']['full']['overnight_mtm']/1e3:,.0f}k with the long legs and −₹{-FC['feb3_decomposition']['d1_no_wings']['overnight_mtm']/1e5:,.2f} lakh without them: **the gap protection was worth ₹{FC['feb3_overnight_difference']/1e5:,.2f} lakh** (≈ {FC['feb3_overnight_difference']/GS['cost']:.0f} average cycles of their cost). The cycles' net results differ by ₹{FC['feb3_net_difference']/1e5:,.2f} lakh, but ≈ ₹{(FC['feb3_net_difference']-FC['feb3_overnight_difference'])/1e5:,.1f} lakh of that comes from the two books being managed differently later on D0, not from the gap. The overnight ratios on the 09:16 basis (0.61; median night 0.27; top 10% of nights 68%) stand; the first-print versions (0.63 / 0.39 / 63%, n = {NG['first_print_cycles']}) use partly stale 09:15 option prints and are **withdrawn**.
3. **What I could not obtain** (stated before any test): NSE's daily SPAN files and a long index history (the container cannot reach them; one attempt to reach a market-data site with a spoofed browser header was blocked by the environment and not retried), and any signed option order flow.

## 1. The answers in brief
| Question | Answer | Level |
|---|---|---|
| **Q2 Real margin** | Not obtained from NSE. On the **real** order log the modelled peak margin is a median **₹{cr(m('real peak margin, median (₹ crore)').value * 1e7)} crore** ({cr(m('real peak margin, median (₹ crore)').lo * 1e7)}–{cr(m('real peak margin, median (₹ crore)').hi * 1e7)}), above ₹2 crore in **{pc(m('real cycles with peak margin > ₹2 crore').value)}** of cycles: the real book sits at ≈ 80% of the capital at its peak (expiry day) and uses ≈ ₹{cr(m('real overnight (D-1 close) margin, median (₹ crore)').value * 1e7)} crore overnight. That is **consistent with a binding ₹2 crore constraint**; it does not prove it | Observed under an unverified scan range |
| **Q3 Extreme gaps** | With its long legs the carried book is **long the far tail** (it *gains* at 10–15% gaps); without them the same shorts lose ₹{lk(row('real_no_longs', -0.10)['mean'])}–{lk(row('real_no_longs', 0.15)['mean'])} lakh on average at 10–15% and, with IV doubled, breach the ₹2 crore capital in {pc(row('real_no_longs', 0.10, 2.0).share_over_2cr)} of books at +10% and {pc(row('real_no_longs', 0.15, 2.0).share_over_2cr)} at +15% (downside worst case ₹{cr(row('real_no_longs', -0.15, 2.0).worst)} crore). In expectation the legs are **about break-even** against their ₹{GS['cost'] / 1e3:.1f}k per cycle; a 3-year sample cannot settle it. They are **survival insurance at roughly a fair price** | Observed (stress) / Unresolved (frequency) |
| **Q1 Expiry-day premium** | Not jumps (earlier), **not pinning**, **not visible order-flow pressure**. One mechanism is supported: **the official settlement is an average, so the last half hour is calmer than a spot print** (variance ratio {x1.value:.2f}); the 15:00 straddle loses {pc(-s_pr.value)} against the last print but earns {pc(s_st.value)} against the settlement. It existed until the closing auction session started on 3 Aug 2026 and is gone since. Over-pricing also **rises with distance from the money, puts more than calls**. The rest is unexplained | Observed (E1, E3); Not supported (E2, E4); Unresolved (the remainder) |

## 2. Question 2 — the true margin
**What is verified and what is not.**
| Item | Status |
|---|---|
| Index price scan range = 6σ·√2 with a 9.3% floor; volatility scan 25% of EWMA volatility, minimum 4% | **Search snippets of NSE Clearing's pages (two separate searches); the pages themselves timed out twice** — best available, not verified |
| Extreme-loss margin 2% on short index options (+2% on expiry day from 20 Nov 2024) | SEBI circular of 1 Oct 2024 as reported by Zerodha / ICRA; the circular text was not opened |
| Daily SPAN files with the actual parameters | **Not reachable** |

With σ = the cycle's opening ATM implied volatility (median {iv.iv_D1_open.median():.3f}), 6σ√2 exceeds 9.3% in only {pc(1 - floor_share, 1)} of cycles, so the 9.3% floor is the operative scan range in {pc(floor_share)} of cycles.

**Test on the real book** (35 cycles, 39,874 real orders, positions rebuilt minute by minute and valued on the same option chains):
{_md(pd.DataFrame([dict(statistic=k, value=(f'{v.value:.2f}' if abs(v.value) < 100 else f'{v.value:,.0f}') + ('' if pd.isna(v.lo) else f' [{v.lo:.2f}, {v.hi:.2f}]')) for k, v in M.iterrows()]))}

* **Plan rule:** *consistent with a binding ₹2 crore constraint* if the median is between ₹1.0 and ₹2.0 crore and at most 10% of cycles exceed ₹2 crore → **met** ({cr(m('real peak margin, median (₹ crore)').value * 1e7)} crore; {pc(m('real cycles with peak margin > ₹2 crore').value, 1)}). *Model–real agreement* needs a cycle-level Spearman ≥ 0.6 → **not met** ({m('Spearman real vs simulator peak margin').value:.2f}). So the model gets the **level** right (simulator median {cr(m('simulator, same cycles: peak margin median (₹ crore)').value * 1e7)} vs real {cr(m('real peak margin, median (₹ crore)').value * 1e7)} crore; the real system runs ≈ 20% larger than the simulator) but not which cycle is large.
* **Where the capital goes:** peak margin of a real cycle is ₹{cr(peakD1)} crore on D-1 and ₹{cr(peakD0)} crore on D0 (median of cycle maxima). The overnight carry is cheap in capital (≈ ₹{cr(m('real overnight (D-1 close) margin, median (₹ crore)').value * 1e7)} crore); the expiry-day book is what meets the ₹2 crore limit — which is what the D0 hedge and the D0 stop/take-profit control (`PREMIUM_AND_ARCHITECTURE.md`: without them 52–55% of simulated cycles exceed it).
* **Caveat that can reverse the reading:** if the true scan range is lower than 9.3% (older regime 3σ, ≈ 2–3%) every margin falls by roughly a third to a half and the real book would sit well below ₹2 crore — then capital is **not** the binding constraint. Only the daily SPAN files settle this.

## 3. Question 3 — extreme gaps
**What the data contain.** Largest first-print gaps on cycle nights:

{_md(GAPTOP)}

Over all 770 nights of the daily files the largest gaps are NIFTY {pc(evn['max_abs_gap'], 2)} and SENSEX {pc(evs['max_abs_gap'], 2)}. The daily files' opens are **opening prints** (like the 09:15 tick of 3 Feb 2026), so this distribution and the tail fit below are an **upper bound** on tradeable gaps. The 3 years are calm: nothing near the 7–13% moves of 2008 or March 2020.

**Documented history (third-party lists, close-to-close, not opening gaps).** The Stable Investor and Learn Stock Market lists give **{GS['doc_events']} NIFTY falls of 5% or more between 2000 and 2022** (up to −12.98% on 23 Mar 2020, −12.24% in 2004, −12.20% in 2008); a news search adds 4 Jun 2024 (−5.93%). The lists are not complete after 2022 and list no rises or opening gaps. That is **≥ {pc(p_doc, 2)} of nights** over ≈ {n_doc:,} nights, clustered in 2008 and 2020. Whether such a fall arrives as an overnight gap or intraday is **not known**; it is used below as an upper bound (gap = whole move) and with half of it.

**Stress of the book carried overnight** (gap applied at the D-1 close, implied volatility × 1.5, time value kept; loss in ₹ lakh, mean over books / worst book):

{_md(ST)}

* The **real** carried book is net long convexity: it loses at most ₹{lk(row('real', 0.05).worst)}–{lk(row('real', -0.10).worst)} lakh in its worst case at 5–10% gaps and **gains** ₹{lk(-row('real', -0.15)['mean'])} lakh on average at −15%. Without the long legs the same shorts lose ₹{lk(row('real_no_longs', -0.05)['mean'])} lakh at 5%, ₹{lk(row('real_no_longs', -0.10)['mean'])} lakh at −10%, ₹{lk(row('real_no_longs', 0.15)['mean'])} lakh at +15%.
* **Share of books losing more than the ₹2 crore capital** (IV × 2.0):

{_md(RU)}

**Frequency of large gaps (what a calm sample can say).** Generalised Pareto fit to |gap| above its 95th percentile (39 exceedances; shape {evn['shape']:.2f}, 95% interval [{evn['shape_lo']:.2f}, {evn['shape_hi']:.2f}], i.e. consistent with anything from a thin to a heavy tail):

{_md(EVT_tab)}

The fitted probability of a 5% gap ({pc(evn['P(|gap|>=5%)'], 3)} per night) is **a quarter of the documented frequency** of 5% falls ({pc(p_doc, 2)}): the 2023–26 sample under-represents crises, as expected. Break-even probabilities are the frequencies at which a gap of that size, alone, repays the legs' net cost of ₹{GS['cost'] / 1e3:.1f}k per cycle.

**Do the long legs pay in expectation?** Net cost of the legs in the simulator: ₹{GS['cost'] / 1e3:.1f}k per cycle (this already contains their payoff on 3 Feb 2026). The comparison that matters is the **extra** benefit from gaps larger than those in the sample (₹ per cycle, base volatility shock 1 + 10·|gap|, capped at 2):

{_md(EVtab[EVtab['volatility shock'].str.startswith('base')])}

* Fitted tail beyond the sample adds ≈ ₹{EV_b.loc['simulated books', 'ev_gpd_extra_beyond_sample']:,.0f} per cycle: **nothing**, because a tail fitted to 3 calm years has none to add.
* Documented falls add ≈ ₹{EV_b.loc['simulated books', 'ev_documented_extra_phi1']:,.0f} per cycle if every one arrived as an overnight gap of its full size, ₹{EV_b.loc['simulated books', 'ev_documented_extra_phi05']:,.0f} if half — **against a cost of ₹{GS['cost']:,.0f}**. Counting upside gaps (not listed) could roughly double it. So the legs are **at or just below break-even on the documented history, and clearly below on the fitted tail**.
* **Reading rule of the plan:** they *pay in expectation* only if both the fitted tail and the documented comparator exceed the cost → **not met**. They *prevent ruin* if the hedged book stays inside ₹2 crore at the largest documented gap while the unhedged one does not → **met** (hedged worst loss ₹{lk(row('real', 0.15, 2.0).worst)} lakh at ±15%, IV × 2; unhedged worst ₹{cr(row('real_no_longs', 0.15, 2.0).worst)} crore). Verdict: **survival insurance, roughly fairly priced, not provably profitable**.
* What this ignores: day-of management after the gap (the cycle stop cannot act on an opening gap but later rules can), exchange circuit breakers at the open for moves of 10% or more (positions cannot be closed anyway), and margin calls.

## 4. Question 1 — why is the expiry-day premium rich?
**E1 — the settlement is an average (supported, but not in 2026).** Settlement = the official close of the D0 date. If it is built from last-half-hour prices it should vary less than a spot print over 15:00–15:30.

{_md(E1)}

* The settlement's variance over the last half hour is **{pc(1 - x1.value)} lower** than the 15:29 print's ({x1.value:.2f} [{x1.lo:.2f}, {x1.hi:.2f}]; a pure 30-minute average would give ≈ 0.33).
* The market prices the print, not the average: at 15:00 the implied variance is **fair-to-cheap against the 15:29 print** ({rv_p.value:.2f}) and **rich against the settlement** ({rv_s.value:.2f}). The same 15:00 straddle loses {pc(-s_pr.value)} to the print and earns {pc(s_st.value)} to the settlement: **+{pc(ex.value)} of the 15:00 premium** [{pc(ex.lo)}, {pc(ex.hi)}] comes from the averaging.
* **Why it vanished in 2026 — explained (post-hoc test, mechanism documented earlier in the `research/strong-findings` branch):** SEBI's **closing auction session took effect on 3 Aug 2026**; from then on the closing price is an auction price, not a 30-minute average. Split at that date: before, variance ratio **{CAS.loc['before CAS','var_ratio']:.2f}** [{CAS.loc['before CAS','var_ratio_lo']:.2f}, {CAS.loc['before CAS','var_ratio_hi']:.2f}] over {int(CAS.loc['before CAS','cycles'])} cycles (Jan – 2 Aug 2026 alone: {CAS.loc['2026 before CAS (Jan - 2 Aug)','var_ratio']:.2f}); after, **{CAS.loc['after CAS (from 3 Aug 2026)','var_ratio']:.2f}** [{CAS.loc['after CAS (from 3 Aug 2026)','var_ratio_lo']:.2f}, {CAS.loc['after CAS (from 3 Aug 2026)','var_ratio_hi']:.2f}] over {int(CAS.loc['after CAS (from 3 Aug 2026)','cycles'])} cycles, with the settlement equal to the last print (median difference {CAS.loc['after CAS (from 3 Aug 2026)','median_abs_settle_minus_print_bp']:.1f} bp). The extra premium went from {pc(CAS.loc['before CAS','extra_premium'])} of the 15:00 premium to {pc(CAS.loc['after CAS (from 3 Aug 2026)','extra_premium'])}. I did not read NSE's closing-price rule itself; that the daily-file close equals the official settlement is assumed.
* The strategy buys back at **15:14**, so it does not hold the settlement leg: the 15:14 → settlement slice is worth {pc(ps('E5', '15:14 to official').value, 1)} of the 09:16 premium [{pc(ps('E5', '15:14 to official').lo, 1)}, {pc(ps('E5', '15:14 to official').hi, 1)}] — within noise.

**E2 — pinning (not supported).** At 14:00 the largest-open-interest strike within ±2% of spot (open interest available for {len(PIN)} of 275 cycles): the settlement is {e2.value:+.2f} strike steps from it relative to a placebo from other cycles [{e2.lo:+.2f}, {e2.hi:+.2f}]; closer than the placebo in {pc(e2b.value)} of cycles [{pc(e2b.lo)}, {pc(e2b.hi)}] — the interval includes 50%.

**E3 — moneyness (tail demand pattern).** Price versus realised payoff at settlement, options sold at the D0 09:16 open:

{_md(MSt)}

* The ratio **rises with distance** for both rights and is higher for **puts** (put 1.5% away: priced {MS[(MS.side == 'PE') & (MS.dist == 0.015)].price_over_payoff.iloc[0]:.1f}× its payoff; the 2% and 3% options never paid in 275 cycles). Intervals are wide, and this is the signature of tail/lottery demand **or** of 3 calm, mostly rising years in which puts expired worthless. In rupees the over-pricing is concentrated within ≈ 1.5% of the money (up to ≈ {pc(MS.premium_minus_payoff_pct_of_atm_straddle.max())} of the ATM straddle premium per option).

**E4 — option order flow (not supported).** Signed volume of the ATM call and put (tick rule) in a 15-minute block against the next block's change in implied variance not explained by realised variance: Spearman {e4.loc['dw_next_surprise', 'spearman']:+.3f} [{e4.loc['dw_next_surprise', 'lo']:+.3f}, {e4.loc['dw_next_surprise', 'hi']:+.3f}] over {int(e4.loc['dw_next_surprise', 'n']):,} blocks (the same-block correlation {e4.loc['dw_surprise', 'spearman']:+.2f} is mechanical). No evidence of price pressure that reverses; the proxy is crude (no quotes, no true sign).

**E5 — where the D0 straddle premium accrues.**

{_md(E5t)}

No slice is individually distinguishable from zero: the straddle P&L is noisy; the variance ratios are what carry the evidence.

## 5. The idea, version 3
> Algo 8 sells two premia and holds three kinds of protection. **(1) Overnight:** gap insurance — the typical night is calm, a few are not; the long legs convert the carried book from short to **long the far tail**, which costs ≈ ₹{GS['cost'] / 1e3:.0f}k per cycle net and is what keeps a 10–15% gap from reaching the ₹2 crore capital. **(2) Expiry day:** a persistent over-pricing, part of which is mechanical — the official settlement is an average, so the last half hour carries less risk than the options at 15:00 price — and part of which looks like a tail premium that is largest for puts; the rest is unexplained. **(3) Size:** the expiry-day book is held at about ₹1.6 crore of margin, close to the ₹2 crore capital, by the D0 hedge and stop/take-profit. The clock, the ladder and the stops keep the book balanced and bounded; none of it forecasts direction.

## 6. Evidence levels
| Claim | Level |
|---|---|
| The real book's modelled peak margin is ≈ 80% of ₹2 crore | **Observed** under an unverified scan range |
| Capital is the binding constraint on the expiry-day book | **Inferred** (consistent; reverses if the true scan range is ≪ 9.3%) |
| The carried book is long the far tail; the unhedged shorts would breach ₹2 crore in the worst 10–15% gaps | **Observed** (stress model) |
| The long legs pay in expectation | **Not supported**; **unresolved** (needs a tail the sample lacks) |
| Gaps ≥ 5% occur roughly once in 250–300 nights | **Documented** (close-to-close falls 2000–22, third-party lists) / **Unknown** as opening gaps |
| Settlement averaging explains part of the expiry-day premium (last half hour) | **Observed** before the closing auction (to 2 Aug 2026); **gone after 3 Aug 2026**, matching the rule change |
| Pinning, visible order-flow pressure | **Not supported** |
| Tail/lottery-type over-pricing, puts above calls | **Weak** (wide intervals; confounded by the sample's drift) |
| Who buys the expiry-day options | **Not testable** here |

## 7. What would settle the rest
1. **NSE daily SPAN risk-parameter files** for the cycle dates (the scan range per day) → replaces the margin assumption; **participant-wise open interest and volume** files → who holds the options; both are public NSE downloads the container cannot reach.
2. **Daily NIFTY / SENSEX open and close back to 2008** (including opening prints) → a real gap distribution and a real tail test of the long legs (2008, 2020, 2024).
3. **The official closing-price rule for NSE indices** (read from NSE's methodology) → confirm the averaging mechanism and see whether anything changed in 2026.
4. Forward logging: per cycle, the 15:00 → settlement variance ratio and the first-print gap.
"""
open(f'{RP}/UNRESOLVED_THREE.md', 'w').write(md); print(json.load(open(f'{UN}/unres_summary.json')))
