"""Builds reports/DESIGN_THESIS.md, figures/bl_thesis.png and outputs/thesis/knowledge_graph_{nodes,edges}.csv (plan reports/DESIGN_THESIS_PLAN.md + Addendum 1).
Inputs: outputs/thesis/thesis_stats.csv, thesis_t2_profile.csv, thesis_t56_stats.csv; the knowledge-graph nodes are written here from the branch reports they cite."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); TH = f'{OUT}/thesis'; RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures')
def _md(d):
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return '| ' + ' | '.join(map(str, d.columns)) + ' |\n|' + '---|' * len(d.columns) + '\n' + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
S = pd.read_csv(f'{TH}/thesis_stats.csv'); P = pd.read_csv(f'{TH}/thesis_t2_profile.csv'); S56 = pd.read_csv(f'{TH}/thesis_t56_stats.csv'); g = lambda lab: S[S.label == lab].iloc[0]; h = lambda st: S56[S56.stat == st].iloc[0]
pc = lambda x, d=1: f'{100 * x:.{d}f}%'
# ---------------- knowledge graph (finding nodes cite the branch file they come from)
N = [  # id, layer, finding, source (branch : file), evidence
('K01', 'context', 'Client wording: "a BTST algorithm" that carries positions to expiry; capital ₹2 crore; 4% carry stop and 1% expiry-day stop', 'all lineages : risk_rule_validation/RISK_RULE_VALIDATION_REPORT.md (Info.txt)', 'Stated by client'),
('K02', 'context', 'Sibling Algo 7 trades the expiry day only (30,171 of 30,192 fills on D0); Algo 8 adds the day before and the overnight carry', 'skeleton-tp lineage : dte_comparison/DTE_COMPARISON_REPORT.md', 'Observed'),
('K03', 'context', 'Cycle = D-1 builds the book, D0 manages it (D0 3.6x the lots, mostly buy-backs and re-sales)', 'dte_comparison; audit STR-01', 'Observed'),
('K04', 'entry', 'First ATM straddle at 09:16 on D-1 (31/32), strike = nearest ATM to the 09:15 close (31/31)', 'strong-findings : STRONG_FINDINGS.md F01-F02', 'Strong'),
('K05', 'entry', 'Protected straddles added on a ~15-minute clock (544/544 windows), common size ladder on both indices (22/22 slots)', 'strong-findings : F07-F13; audit SIZ-03', 'Strong'),
('K06', 'entry', 'Later straddles re-centred near the moving ATM (97% NIFTY, 95% SENSEX within one strike)', 'strong-findings : F14', 'Strong'),
('K07', 'entry', 'Additions fire after rises and falls, IV up and down, book in profit or loss; a falling opening candle still entered', 'strong-findings : POSITION_BUILDING_RATIONALE.md; audit ENT-05', 'Strong (counterexamples)'),
('K08', 'entry', 'No classical index or option indicator is identifiably used (75 + 14 measures, nested chronological models vs shuffled nulls, BH-FDR)', 'allocation / exit-engine lineage : audit STR-03', 'Observed (in-sample)'),
('K09', 'entry', 'IV rises do not explain additions (1% of pre-expiry additions follow a 1-point IV rise)', 'strong-findings : research/IV_THETA_HYPOTHESIS_FINDINGS.md', 'Observed (model IV)'),
('K10', 'risk shape', 'Every addition raises theta and makes vega and gamma more negative (97-98% of windows)', 'strong-findings : F11-F12', 'Strong (model)'),
('K11', 'risk shape', 'Opening and overnight books are theta+, vega-, gamma- (31/31)', 'strong-findings : F25-F26', 'Strong (model)'),
('K12', 'protection', 'Routine wing = highest OTM premium <= 2.5% of the ATM leg premium', 'strong-findings : F15; audit HDG-02', 'Strong (approximate)'),
('K13', 'protection', 'Opening seed wings about 2,000 points out (SENSEX 4,000 before 16 Sep)', 'strong-findings : F05-F06', 'Strong (approximate)'),
('K14', 'protection', 'Every overnight book has long >= short on each right: defined risk overnight (31/31)', 'strong-findings : F34; audit HDG-05', 'Strong'),
('K15', 'protection', 'Protection costs money: real logs -₹8.4 lakh gross on longs; in the simulator wings, lump and hedge lower the mean', 'strong-findings : final_alpha_attribution; body-lifecycle : ALPHA_SOURCE.md', 'Observed'),
('K16', 'management', 'Per-lot stop near 1.55-1.6x entry, one lot at a time (D-1); weak on D0', 'exit-engine lineage : audit EXT-02..05', 'Strong (D-1)'),
('K17', 'management', 'Cycle stop near ₹1.42 lakh on cumulative D-1+D0 MTM; the client 4% / 1% rules do not match behaviour', 'risk_rule_validation', 'Strong / client rule not supported'),
('K18', 'management', 'Momentum-following rebalancing: 68.6% of body orders add delta in the direction of the last 5-min move; no forecasting skill (corr -0.007 / +0.025)', 'audit MGT-09', 'Observed'),
('K19', 'management', 'Exit: late closures in the 15:14 minute (9/10)', 'strong-findings : F29', 'Strong'),
('K20', 'economics', 'Real 32 cycles: gross +₹18.9 lakh; short calls +₹36.2 lakh, short puts -₹8.9 lakh, longs -₹8.4 lakh; model: time +₹87.6 lakh, direction -₹59.0 lakh, IV -₹19.2 lakh', 'strong-findings : final_alpha_attribution', 'Observed / model'),
('K21', 'economics', 'Real logs: no demonstrated alpha vs a frozen opening basket; net depends on costs and two winners; overnight phase +₹5.2 lakh gross', 'strong-findings : final_alpha_attribution; HEDGED_STRADDLE_BENCHMARK_FINDINGS.md', 'Observed'),
('K22', 'economics', '3-year simulation: OOS ₹0.56 lakh per cycle net, t = 1.28; costs take ~51% of gross', 'body-lifecycle : BACKTEST3Y_RESULT.md, ALPHA_SOURCE.md', 'Observed (simulator)'),
('K23', 'economics', 'Simulator: premium decay exceeds gamma loss by ~₹79k per cycle; 85% of holding P&L from short lots on D0', 'body-lifecycle : ALPHA_SOURCE.md', 'Observed (model)'),
('K24', 'economics', 'No seasonal or regime dependence of the weekly result', 'body-lifecycle : BACKTEST3Y_REGIME.md', 'Observed (not supported)'),
('K25', 'market', 'Index momentum has no skill at 15/30/60 min; volatility persistence is the only strong structure', 'stage2-independent-alpha : MILESTONE2_REPORT.md', 'Observed (in-sample)'),
('K26', 'market', 'Realised / implied variance < 1 on D-1, overnight and D0 (T1)', 'this report', 'Observed (3 years)'),
('K27', 'market', 'Short ATM straddle mean P&L positive in each segment, intervals include zero (T1)', 'this report', 'Weak'),
('K28', 'market', 'Expiry-day 15-minute decay is ~9x the D-1 rate and accelerates after 14:00 (T2)', 'this report', 'Descriptive'),
('K29', 'market', 'After the ladder trigger (new 60-min extreme) the index reverts, not continues (T3)', 'this report', 'Observed (short horizons)'),
('K30', 'market', 'The ladder sale reduces |book delta| at 74% of triggers; the opposite sale almost never (T6)', 'this report', 'Observed (post-hoc)'),
('K31', 'market', 'Spreading sales over the 15-min clock does not lower the dispersion of a held-to-expiry carry (T5)', 'this report', 'Not supported (post-hoc)'),
('K32', 'market', 'Short call vs short put: no reliable difference over 3 years (T4)', 'this report', 'Not supported'),
]
NODES = pd.DataFrame(N, columns=['id', 'layer', 'finding', 'source', 'evidence'])
TH_ = [('TH1', 'Near-expiry index options are priced for more movement than occurs: sell ATM premium', ['K26', 'K27', 'K10', 'K11', 'K20', 'K23', 'K04']),
       ('TH2', 'The night before expiry is the richest slice: carry a covered short book overnight (BTST)', ['K01', 'K02', 'K03', 'K14', 'K21', 'K26']),
       ('TH3', 'Expiry-day decay is the fastest: keep selling on D0, leave by 15:14', ['K28', 'K23', 'K03', 'K19']),
       ('TH4', 'Do not forecast direction: stay delta-balanced by selling the side the market moves away from', ['K07', 'K08', 'K09', 'K18', 'K29', 'K30', 'K25']),
       ('TH5', 'Survive the tails: per-lot stop, cycle stop, cheap far wings, covered overnight book', ['K12', 'K13', 'K14', 'K15', 'K16', 'K17']),
       ('TH6', 'Build in small pieces on a clock and re-centre: an execution / averaging device, not a risk reducer', ['K05', 'K06', 'K31'])]
EDGES = pd.DataFrame([dict(source=k, target=t, relation='contradicts' if k in ('K15',) and t == 'TH5' else 'supports') for t, _, ks in TH_ for k in ks]); EDGES.loc[(EDGES.source == 'K31') & (EDGES.target == 'TH6'), 'relation'] = 'qualifies'
EDGES.loc[(EDGES.source == 'K15') & (EDGES.target == 'TH5'), 'relation'] = 'qualifies (cost)'; EDGES.loc[(EDGES.source == 'K27'), 'relation'] = 'weakly supports'
NODES.to_csv(f'{TH}/knowledge_graph_nodes.csv', index=False); EDGES.to_csv(f'{TH}/knowledge_graph_edges.csv', index=False)
merm = 'flowchart LR\n' + '\n'.join(f'  {t}["{t}: {txt[:60]}"]' for t, txt, _ in TH_) + '\n' + '\n'.join(f'  {e.source} -->|{e.relation}| {e.target}' for e in EDGES.itertuples())
# ---------------- tables
seg = ['D-1 day', 'overnight', 'D0 day']
T1 = pd.DataFrame([dict(segment=s, **{'short straddle, % of premium [95%]': f"{pc(g(f'{s}: short ATM straddle, % of premium').value)} [{pc(g(f'{s}: short ATM straddle, % of premium').lo)}, {pc(g(f'{s}: short ATM straddle, % of premium').hi)}]",
                    '₹ per cycle (1 lot)': f"{g(f'{s}: short ATM straddle, Rs per cycle (constant lot)').value:,.0f}", 'IS / OOS / live (% of premium)': ' / '.join(pc(g(f'{s}: short ATM straddle, % of premium')[k]) for k in ('IS', 'OOS', 'LIVE_FITTED')),
                    'realised ÷ implied variance [95%]': f"{g(f'{s}: realised / implied variance').value:.2f} [{g(f'{s}: realised / implied variance').lo:.2f}, {g(f'{s}: realised / implied variance').hi:.2f}]",
                    'variance ratio IS / OOS / live': ' / '.join(f"{g(f'{s}: realised / implied variance')[k]:.2f}" for k in ('IS', 'OOS', 'LIVE_FITTED')), 'verdict (plan)': g(f'{s}: short ATM straddle, % of premium').verdict}) for s in seg])
T3 = S[S.test.isin(['T3', 'T3o', 'T3P'])].copy(); T3['value [95%]'] = T3.apply(lambda r: f'{r.value:,.1f} [{r.lo:,.1f}, {r.hi:,.1f}]', axis=1); T3['IS / OOS / live'] = T3.apply(lambda r: f'{r.IS:,.1f} / {r.OOS:,.1f} / {r.LIVE_FITTED:,.1f}', axis=1)
T3 = T3[['label', 'value [95%]', 'IS / OOS / live', 'p_holm', 'verdict']].rename(columns={'label': 'test', 'p_holm': 'Holm p'})
T4 = S[S.test == 'T4'].copy(); T4['value [95%]'] = T4.apply(lambda r: (f'{pc(r.value)} [{pc(r.lo)}, {pc(r.hi)}]' if '%' in r.unit else f'{r.value:,.1f} [{r.lo:,.1f}, {r.hi:,.1f}]'), axis=1); T4 = T4[['label', 'value [95%]']].rename(columns={'label': 'test'})
d1 = P[P.session == 'D-1'].mean_pct.mean(); d0 = P[P.session == 'D0'].mean_pct.mean(); late = P[(P.session == 'D0') & (P.block_start >= 285)].mean_pct.mean()
t5 = h('sd_ratio_recentred_single'); t5m = h('mean_diff_recentred_single'); t6 = S56[S56.test == 'T6'].iloc[0]; t6o = S56[S56.test == 'T6'].iloc[1]
# ---------------- figure
fig, ax = plt.subplots(2, 2, figsize=(15, 10)); x = np.arange(3); wd = .2
for k, (sp, col) in enumerate((('value', 'k'), ('IS', '#2b6cb0'), ('OOS', '#c05621'), ('LIVE_FITTED', '#999999'))):
    v = [g(f'{s}: realised / implied variance')[sp] for s in seg]; ax[0, 0].bar(x + (k - 1.5) * wd, v, wd, color=col, label={'value': 'all', 'LIVE_FITTED': 'live window'}.get(sp, sp))
lo = [g(f'{s}: realised / implied variance').lo for s in seg]; hi = [g(f'{s}: realised / implied variance').hi for s in seg]; v = [g(f'{s}: realised / implied variance').value for s in seg]
ax[0, 0].errorbar(x - 1.5 * wd, v, yerr=[np.subtract(v, lo), np.subtract(hi, v)], fmt='none', color='k', capsize=4); ax[0, 0].axhline(1, color='#c53030', ls='--'); ax[0, 0].set_xticks(x); ax[0, 0].set_xticklabels(seg); ax[0, 0].set_ylabel('realised ÷ implied variance'); ax[0, 0].legend(fontsize=8); ax[0, 0].set_title('T1: options price more movement than occurs\n(below the red line = premium is rich)')
for sess, col in (('D-1', '#2b6cb0'), ('D0', '#c05621')):
    q = P[P.session == sess]; ax[0, 1].plot(q.block_start / 60 + 9.25, 100 * q.mean_pct, marker='o', color=col, label=sess)
ax[0, 1].axhline(0, color='k', lw=.6); ax[0, 1].set_xlabel('time of day (hours)'); ax[0, 1].set_ylabel('15-min short ATM straddle, mean % of premium'); ax[0, 1].legend(); ax[0, 1].set_title(f'T2: decay per 15 minutes — D0 ≈ {d0 / d1:.0f}× D-1, fastest in the afternoon')
for sess, col, off in (('D-1', '#2b6cb0', -.12), ('D0', '#c05621', .12)):
    labs = [f'{sess} ladder trigger: index continuation {n} (bp, signed)' for n in ('+15 min', '+30 min', '+60 min', 'to session end')]; r = [g(l) for l in labs]
    ax[1, 0].errorbar(np.arange(4) + off, [z.value for z in r], yerr=[[z.value - z.lo for z in r], [z.hi - z.value for z in r]], fmt='o', color=col, capsize=4, label=sess)
ax[1, 0].axhline(0, color='k', lw=.6); ax[1, 0].set_xticks(range(4)); ax[1, 0].set_xticklabels(['+15 min', '+30 min', '+60 min', 'session end']); ax[1, 0].set_ylabel('index return after the trigger, bp (+ = continues)'); ax[1, 0].legend(); ax[1, 0].set_title('T3: after a new 60-minute extreme the index reverts\n(the ladder is not a trend bet)')
ax[1, 1].bar([0, 1], [100 * t6.value, 100 * t6o.value], color=['#2f855a', '#999999'], yerr=[[100 * (t6.value - t6.lo), 100 * (t6o.value - t6o.lo)], [100 * (t6.hi - t6.value), 100 * (t6o.hi - t6o.value)]], capsize=5)
ax[1, 1].set_xticks([0, 1]); ax[1, 1].set_xticklabels(['ladder sale\n(call after a low, put after a high)', 'opposite sale']); ax[1, 1].set_ylabel('% of triggers where |book delta| falls'); ax[1, 1].set_title('T6 (post-hoc): the ladder re-balances the book\'s delta')
plt.tight_layout(); os.makedirs(FIG, exist_ok=True); plt.savefig(f'{FIG}/bl_thesis.png', dpi=110); plt.close()
json.dump(dict(var_ratio={s: float(g(f'{s}: realised / implied variance').value) for s in seg}, var_ratio_hi={s: float(g(f'{s}: realised / implied variance').hi) for s in seg}, d0_over_d1_decay=float(d0 / d1), t3_d1_end=float(g('D-1 ladder trigger: index continuation to session end (bp, signed)').value),
               t6_share=float(t6.value), t6_opposite=float(t6o.value), t5_sd_ratio=float(t5.value), nodes=len(NODES), edges=len(EDGES)), open(f'{TH}/thesis_summary.json', 'w'), indent=1)
v = {s: g(f'{s}: realised / implied variance') for s in seg}
md = f"""# The idea behind Algo 8 — knowledge graph and design thesis

*Plan: `DESIGN_THESIS_PLAN.md` (T1–T4 pre-registered; T5–T6 added in Addendum 1 after T1–T4 were seen, labelled post-hoc). Market tests use only the 3-year D-1/D0 option chains (275 cycles, Nov 2023 – Nov 2026), not my strategy simulator. Every cycle was used before: **exploratory**. Figure: `figures/bl_thesis.png`. Graph data: `outputs/thesis/knowledge_graph_nodes.csv`, `…_edges.csv`.*

## The thesis in one paragraph
**"Index options in the last day and a half before a weekly expiry are priced for more movement than actually happens, and the night before expiry is priced the richest. So sell at-the-money premium all through the day before expiry on a fixed clock, carry a fully covered book overnight (the 'BTST' leg), keep selling on expiry day while time value collapses fastest, and be out by 15:14. Never forecast direction: when the market moves, sell the side it is moving away from so the book stays balanced. Survive the tails with a per-lot stop, a cycle stop of about ₹1.4 lakh, and very cheap far wings."**

That is a **short-volatility, variance-risk-premium harvester specialised to the expiry window**, with a delta-rebalancing rule instead of a forecast. It is not an indicator system and not a directional system.

## How sure each part is
| # | Part of the idea | What the data say | Evidence |
|---|---|---|---|
| TH1 | Near-expiry options are over-priced (sell ATM premium) | Realised ÷ implied variance **{v['D-1 day'].value:.2f} (D-1), {v['overnight'].value:.2f} (overnight), {v['D0 day'].value:.2f} (D0)**, every interval below 1; the books are theta+, vega−, gamma− by construction | **Strong** that the premium exists in variance terms (3 years, market data). **Weak** that a plain short straddle turns it into money: P&L intervals include zero (fat tails) |
| TH2 | The overnight before expiry is the richest slice (BTST carry) | Lowest variance ratio of the three segments ({v['overnight'].value:.2f}); the client calls it BTST; the sibling Algo 7 is expiry-day only; every real overnight book is covered on both sides | **Strong** for the design intent (client wording + structure); **moderate** for the market claim (overnight interval [{v['overnight'].lo:.2f}, {v['overnight'].hi:.2f}] overlaps the others) |
| TH3 | Expiry day decays fastest: keep selling, leave by 15:14 | 15-minute decay on D0 ≈ **{d0 / d1:.0f}×** the D-1 rate, {pc(late)} per block after 14:00; 85% of the simulated holding P&L comes from D0 | **Strong** (descriptive, mechanical: time value must reach zero) |
| TH4 | No forecast; stay delta-balanced by selling into the move | After a new 60-minute extreme the index **reverts** (D-1: {g('D-1 ladder trigger: index continuation +15 min (bp, signed)').value:.1f} bp at +15 min, {g('D-1 ladder trigger: index continuation to session end (bp, signed)').value:.1f} bp to the close); the ladder sale reduces the book's absolute delta at **{pc(t6.value, 0)}** of triggers (opposite sale: {pc(t6o.value, 2)}); no indicator, IV or direction gate found across branches; momentum has no skill | **Strong** that it is not a forecast; **strong (post-hoc)** that the ladder is delta re-balancing. My earlier "trend-aligned ladder" reading in `ALPHA_SOURCE.md` is **withdrawn** (see below) |
| TH5 | Survive the tails | Per-lot ≈1.6× stop, ≈₹1.42 lakh cycle stop, 2.5%-of-premium wings, covered overnight book all observed; their cost in mean P&L is observed; their benefit (margin, tail) is not measurable here | **Strong** for the rules; **unresolved** for why wings are worth their cost (margin is the most likely reason, not testable without margin data) |
| TH6 | Build in small pieces on a clock and re-centre | Staggering the sales does **not** lower the dispersion of a held carry (SD ratio {t5.value:.2f} [{t5.lo:.2f}, {t5.hi:.2f}]); re-centring changes nothing material | The clock is **not** a risk device. **Inferred**: execution / capacity (1-lot DAY orders, freeze limits, averaging entry prices); not testable here |

**What is not supported:** a directional edge, an indicator trigger, an IV-timing trigger, a seasonal effect, an edge from call vs put selling, and a risk reduction from the clock.

## Correction to `ALPHA_SOURCE.md`
There I read the flipped-ladder placebo (−₹35k net per cycle, loss mostly in delta) as a **trend-aligned element**. The market test here says the opposite: the index tends to **revert** after the ladder's trigger, and the ladder's right does **worse** than the opposite right held to the session end (D-1: ₹{g('D-1 ladder trigger: ladder right minus opposite right, held to session end (Rs per lot-event)').value:,.0f} per lot-event). The placebo's gross interval included zero, and flipping the ladder also changes how the whole book interacts with the stops and the cycle stop. The supported reading is **delta re-balancing of a short-gamma book** (T6, MGT-09: "momentum-following rebalancing, no forecasting skill"). `ALPHA_SOURCE.md` is updated to say so.

## 1. Knowledge graph of the branches
22 branches; 18 are contained in `research/algo8-body-lifecycle`. The four not merged (`research/strong-findings`, `research/ml-decision-engine`, `data/local-breeze-fetch`, `research/stage2-independent-alpha`) were read directly. Below: the findings that bear on the idea (nodes), and which part of the thesis each supports (edges).

```mermaid
{merm}
```

{_md(NODES)}

## 2. Market tests (plan T1–T4)
**T1 — sell one ATM straddle at the start of each segment, buy it back at the end (gross, one lot at the constant lot size).** Round-trip costs for one straddle are 1.3–3.1% of premium (stage-2 estimate), so the D-1 and overnight means are about the size of costs.

{_md(T1)}

* The **variance** result is the strong one: realised variance is 21–39% below what was priced, in all three segments, with intervals excluding 1. In the 2026 live window the D-1 and D0 ratios are **above 1** (premium absent), the overnight one is not — consistent with the weaker live-window result of the backtest.
* The **P&L** of an unhedged straddle is positive in every segment but not significant: the premium is real, but large moves on a few days take much of it back. Turning a variance premium into a steady P&L needs management — which is what the rest of the machine is.
* Overnight measured to the D0 **09:15** open (opening-auction prints) gives {pc(g('overnight (D0 09:15 open): short ATM straddle, % of premium').value)} instead of {pc(g('overnight: short ATM straddle, % of premium').value)}: much of the overnight decay shows up in the first minute's prices.

**T2 — decay per 15 minutes.** Mean of a 15-minute short ATM straddle: D-1 {pc(d1, 2)} of premium per block, D0 {pc(d0, 2)} (≈ {d0 / d1:.0f}×), and {pc(late)} per block after 14:00 on D0. Full profile: `outputs/thesis/thesis_t2_profile.csv`.

**T3 — what happens after the ladder's trigger** (new 60-minute low or high at least one ladder step beyond the last one; signed so that + = the move continues):

{_md(T3)}

**T4 — calls vs puts** (D-1 09:16 → D0 15:14):

{_md(T4)}

The real-log asymmetry (short calls +₹36 lakh, short puts −₹8.9 lakh over 32 cycles) is not a stable property over 3 years; it reflects the drift of the 2026 sample.

## 3. Post-hoc tests (Addendum 1)
* **T5 — the 15-minute clock.** One straddle per 15-minute block of D-1, held to D0 15:14, versus one straddle at 09:16: mean difference {pc(t5m.value)} [{pc(t5m.lo)}, {pc(t5m.hi)}] of premium, dispersion ratio {t5.value:.2f} [{t5.lo:.2f}, {t5.hi:.2f}]. Staggering does **not** reduce risk when everything is held to the same expiry. The 3× lower dispersion of the full strategy (`ALPHA_SOURCE.md`) therefore comes from management (stops, ladder, cycle stop), not from the clock.
* **T6 — the ladder's job.** At {len(pd.read_csv(f'{TH}/thesis_t6.csv')):,} D-1 ladder triggers, the reference book (all straddles sold so far that day) has the sign the ladder corrects in {pc(S56[S56.test == 'T6'].iloc[2].value, 0)} of events, and the ladder's sale lowers |book delta| in {pc(t6.value, 0)} (interval [{pc(t6.lo, 0)}, {pc(t6.hi, 0)}]; IS {pc(t6.IS, 0)}, OOS {pc(t6.OOS, 0)}). This is close to mechanical (after a fall a short straddle book is long delta; a short call removes delta), which is exactly why it reads as a **design choice to re-balance by selling** rather than by buying back or using futures.

## 4. How the pieces fit (the designer's logic, reconstructed)
1. **Belief:** weekly index options near expiry carry a variance risk premium (TH1), richest overnight (TH2), collapsing fastest on expiry day (TH3).
2. **Harvest it with ATM straddles** because ATM carries the most time value per lot; re-centre so new sales stay ATM (K06).
3. **Sell continuously, not once**, in 1-lot child orders on a 15-minute clock (K05) — an execution and averaging choice; it does not lower the carry's risk (T5).
4. **Don't predict, re-balance:** when the market leaves the strike, sell the side it is leaving (ladder, K18, T6). This adds premium **and** pulls delta back to neutral, at the cost of selling into short-horizon reversals (T3).
5. **Cap the damage:** per-lot 1.6× stop (K16), ≈₹1.42 lakh cycle stop (K17), cheap far wings so the overnight book is defined-risk (K12–K14), flat by 15:14 (K19). These cost mean P&L (K15) and are the price of staying in the trade on bad days.
6. **Result:** a thin carry. In 3 years it is real in variance terms, positive but statistically weak in P&L, about half eaten by costs, absent in the 2026 live window on D-1 and D0.

## 5. What is still unknown
* **Intent cannot be proven from data.** The thesis is the explanation that fits all 32 nodes with the fewest assumptions; the repo holds no designer document beyond the client's one-sentence description and a backtest screenshot that the logs do not reproduce.
* Why wings are worth their cost (margin benefit is the leading hypothesis; no margin data).
* Whether the premium persists (2026 live window shows it thinner on D-1 and D0).
* Real broker costs, the tick path, and what the real system did before June 2026.
* T5 and T6 were added after seeing T1–T4.

## 6. Next tests
1. Margin: compute exchange SPAN-style margin for the book with and without wings (needs a margin model or broker data) — the open question in TH5.
2. 2020–2022 chains: re-run T1 (variance ratio by segment) on years never used.
3. Forward check: log the realised ÷ implied variance of each new cycle by segment against the numbers above.
"""
open(f'{RP}/DESIGN_THESIS.md', 'w').write(md); print(json.load(open(f'{TH}/thesis_summary.json')))
