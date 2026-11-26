"""Builds reports/D0_BURST_LONG.md and figures/bl_d0w_summary.png from bl_d0w_* outputs. Coverage tiers are computed from the test outputs with the mapping written below (plan reports/D0_BURST_LONG_PLAN.md)."""
import sys, os, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy import stats
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); FIG = os.path.join(RP, 'figures')
def _md(self, index=True, **kw):
    d = self.reset_index() if index else self
    h = '| ' + ' | '.join(str(c) for c in d.columns) + ' |\n|' + '---|' * len(d.columns) + '\n'
    f = lambda v: ('' if pd.isna(v) else (f'{v:g}' if isinstance(v, (float, np.floating)) else str(v)))
    return h + '\n'.join('| ' + ' | '.join(f(v) for v in r) + ' |' for r in d.itertuples(index=False))
pd.DataFrame.to_markdown = _md
rd = lambda n: pd.read_csv(f'{OUT}/{n}.csv'); J = lambda n: json.load(open(f'{OUT}/bl_summary_{n}.json'))
BG, BA, BP = rd('bl_d0w_burst_gate'), rd('bl_d0w_burst_auc'), rd('bl_d0w_burst_placebo'); LG, LA, LX = rd('bl_d0w_long_gate'), rd('bl_d0w_long_auc'), rd('bl_d0w_extra'); L1, L2 = rd('bl_d0w_long_strike'), rd('bl_d0w_long_open')
BLA, BLR = rd('bl_d0w_burstlots_auc'), rd('bl_d0w_burstlots_rules'); R1, R2, R3, R2b = J('d0w1'), J('d0w2b'), J('d0w3'), J('d0w2b'); FT = rd('bl_d0f_typetable')
D = pd.read_pickle(f'{OUT}/bl_d0u_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); TOT = float(D.lots.sum()); pc = lambda x, d=1: f'{100 * x:.{d}f}%'
# ---- gate with the placebo of the SAME set
BG = BG.merge(BP[['outcome', 'placebo_auc']], on='outcome', how='left'); BG['placebo'] = BG.placebo_auc; BG['gate_strict'] = np.where((BG.auc >= 0.85) & (BG.lo > 0.82) & (BG.forward >= 0.80) & (BG.placebo < 0.65), 'met', 'not met')
# ---- conditional burst discrimination (computed again from the saved predictions)
B = pd.read_pickle(f'{OUT}/bl_d0w_panel.pkl.gz').reset_index(drop=True); P = pd.read_pickle(f'{OUT}/bl_d0w_burst_pred.pkl.gz')
def auc(y, p):
    r = stats.rankdata(p); n1 = y.sum(); n0 = len(y) - n1; return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
m = (B.y_any_bb == 1).values; pb = P[('y_burst', 'ALL (E + lot state + clock)', 'loco')]; pa = P[('y_any_bb', 'E existing families', 'loco')]; cond_auc = auc(B.y_burst.values[m], pb[m]); any_score_auc = auc(B.y_burst.values, pa)
# ---- coverage tiers: 1 rule found (fits >= 90% or exact rule), 2 unseen-cycle ranking gate met, 3 ranked below the gate / indicative / same-minute information only, 4 unresolved
clsl = D.groupby('klass').lots.sum(); ft = FT.set_index('type').lots_share; verd = FT.set_index('type').verdict
bbt = X.type.astype(str).str.slice(0, 2).str.strip().value_counts(normalize=True); bbn = {'1': 'cycle-stop window', '2a': 'clearance', '2b': 'clearance', '2c': 'clearance', '3': 'stop-loss', '4': 'take-profit', '5': 'partner', '6': 'roll-out', '7': 'burst member', '8': 'other'}
bbs = {}
for k, v in bbt.items(): bbs[bbn[k]] = bbs.get(bbn[k], 0) + v
def tier_sell(t, after):
    v = verd[t]
    if t in ('scheduled pair', 'strangle pair'): return 1
    if v.startswith('met (causal)'): return 2
    if 'same-minute' in v or v.startswith('indicative'): return 3
    return 4
gate_bb = dict(zip(BG.outcome, BG.gate_strict)); nm_bb = {'stop-loss': 'stop-loss', 'take-profit': 'take-profit', 'partner': 'partner', 'roll-out': 'roll-out', 'burst member': 'burst member', 'other': 'other'}
def tier_bb(t, after):
    if t in ('cycle-stop window', 'clearance'): return 1
    if after: return 2 if gate_bb[nm_bb[t]] == 'met' else (3 if t == 'roll-out' else 4)
    return 3 if t in ('stop-loss', 'take-profit', 'partner', 'roll-out') else 4
lb = D[D.klass == 'body long buy']; ls = D[D.klass == 'body long sell']; lb_open = lb[lb.tod < 33600].lots.sum(); lb_day = lb[(lb.tod >= 33600) & (lb.tod < 54540)].lots.sum(); lb_late = lb[lb.tod >= 54540].lots.sum(); ls_clear = ls[ls.tod >= 54840].lots.sum(); ls_day = ls[ls.tod < 54840].lots.sum()
xi = LX[(LX.outcome == 'y_long_buy_intra') & LX.set.str.startswith('E + book')].iloc[0]; long_day_buy_met = bool(xi.auc >= 0.85 and xi.lo > 0.82 and xi.placebo_auc < 0.65)
rows = []
def add(cls, lots, tb, ta, note): rows.append(dict(cls=cls, lots=float(lots), share=float(lots) / TOT, tier_before=tb, tier_after=ta, note=note))
for k in ('wing buy', 'wing sell', 'lump salvage'): add(k, clsl[k], 1, 1, 'gap S-L / excess rule, 94-97% exact given the body orders')
add('stop module', clsl['stop module'], 1, 1, 'cumulative MTM stop; liquidates the whole book')
for t in ft.index: add('sell: ' + t, ft[t] * clsl['body sell'], tier_sell(t, False), tier_sell(t, True), verd[t])
for t, v in bbs.items(): add('buy-back: ' + t, v * clsl['body buy-back'], tier_bb(t, False), tier_bb(t, True), ('rule (D0_STOP_CLEAR)' if t in ('cycle-stop window', 'clearance') else 'timing gate ' + gate_bb[nm_bb[t]]))
add('long buy: opening (<= 09:20)', lb_open, 4, 3, 'timing = the opening minutes; strike and count rules not found'); add('long buy: intraday', lb_day, 4, 2 if long_day_buy_met else 3, f'LOCO AUC {xi.auc:.3f}; {int(xi.positives)} positive cells; small sample'); add('long buy: after 15:09', lb_late, 4, 4, 'not examined as a class')
add('long sell: clearance (>= 15:14)', ls_clear, 1, 1, f'{pc(R3["l5_share_sold_after_1514"],0)} of longs open at 15:14 are sold; a price rule adds {100*(R3["l5_rule_price_threshold_lots_correct_loco"]-R3["l5_sell_all_lots_correct"]):.1f} points'); add('long sell: intraday', ls_day, 3, 3, f'AUC {LG[LG.outcome=="long sell (intraday)"].auc.iloc[0]:.3f}, gate not met')
add('hedge other + other', clsl['hedge other'] + clsl['other'], 4, 4, 'not examined')
CV = pd.DataFrame(rows); tot_chk = CV.lots.sum(); cov = lambda col: {t: float(CV[CV[col] == t].share.sum()) for t in (1, 2, 3, 4)}; cb, ca = cov('tier_before'), cov('tier_after')
CV.round(4).to_csv(f'{OUT}/bl_d0w_coverage.csv', index=False)
# ---- figure
fig, ax = plt.subplots(2, 2, figsize=(15, 9)); g = BG.copy(); y = np.arange(len(g)); ax[0, 0].barh(y, g.auc, color=['#3d6b5a' if v == 'met' else '#c05621' for v in g.gate_strict]); ax[0, 0].errorbar(g.auc, y, xerr=[g.auc - g.lo, np.full(len(g), 0.01)], fmt='none', color='k', capsize=2)
ax[0, 0].set_yticks(y); ax[0, 0].set_yticklabels(g.outcome); ax[0, 0].axvline(0.85, color='k', ls=':'); ax[0, 0].set_xlim(0.7, 1.0); ax[0, 0].set_xlabel('leave-one-cycle-out AUC (bar), CI lower bound (whisker)'); ax[0, 0].set_title('Buy-back types: timing/ranking gate (0.85)'); ax[0, 0].invert_yaxis()
v = [BA[(BA.outcome == 'burst (>= 5 lots)') & (BA.set == 'E existing families')].auc_loco.iloc[0], BA[(BA.outcome == 'burst (>= 5 lots)') & (BA.set == 'ALL (E + lot state + clock)')].auc_loco.iloc[0], BA[(BA.outcome == 'burst (>= 5 lots)') & (BA.set == 'base + ITM depth only')].auc_loco.iloc[0], any_score_auc, cond_auc]
ax[0, 1].bar(['existing\nfamilies', '+ lot state\n+ clock', 'time + ITM\ndepth only', 'any buy-back\nscore', 'burst vs single\n(buy-back cells)'], v, color=['#555555', '#3d6b5a', '#c05621', '#2b6cb0', '#2b6cb0']); ax[0, 1].axhline(0.85, color='k', ls=':'); ax[0, 1].set_ylim(0.6, 1.0); ax[0, 1].set_title('Burst timing: where it comes from'); ax[0, 1].set_ylabel('AUC'); [ax[0, 1].text(i, x + 0.005, f'{x:.2f}', ha='center', fontsize=9) for i, x in enumerate(v)]
z = BLA.copy(); z = z[z.feature != 'carried from D-1']; ax[1, 0].barh(z.feature, z.precision_at_m_desc, color='#3d6b5a'); ax[1, 0].axvline(R2['chance_precision_at_m'], color='k', ls=':', label=f'chance {R2["chance_precision_at_m"]:.2f}'); ax[1, 0].set_xlabel('share of the lots taken that a ranking finds in its top m (m = true count)'); ax[1, 0].set_title('Which lots does a burst take?'); ax[1, 0].legend(fontsize=8); ax[1, 0].invert_yaxis()
cols_ = {1: '#3d6b5a', 2: '#2b6cb0', 3: '#d69e2e', 4: '#c05621'}; names_ = {1: 'rule found', 2: 'ranking gate met', 3: 'ranked below gate / indicative', 4: 'unresolved'}
for k, (lab, d) in enumerate((('before this step', cb), ('after', ca))):
    left = 0
    for t in (1, 2, 3, 4): ax[1, 1].barh(k, 100 * d[t], left=left, color=cols_[t], label=names_[t] if k == 0 else None); ax[1, 1].text(left + 50 * d[t], k, f'{100*d[t]:.0f}%', ha='center', va='center', color='w', fontsize=9); left += 100 * d[t]
ax[1, 1].set_yticks([0, 1]); ax[1, 1].set_yticklabels(['before', 'after']); ax[1, 1].set_xlim(0, 100); ax[1, 1].set_xlabel('% of the 49,997 D0 lots'); ax[1, 1].axvline(90, color='k', ls=':'); ax[1, 1].set_title('Coverage by evidence tier (90% target = line)'); ax[1, 1].legend(fontsize=8, loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=2)
plt.tight_layout(); plt.savefig(os.path.join(FIG, 'bl_d0w_summary.png'), dpi=120); plt.close()
# ---- report
L = []; w = L.append
w('# Algo 8 — D0: burst buy-backs, the other buy-back types, and the body-stream longs\n')
w(f'*Plan `D0_BURST_LONG_PLAN.md`, written before the tests (addendum lists the post-hoc steps). In-sample discovery on D0: {R1["cycles"]} cycles, {R1["cells"]:,} minute cells (cycle × minute × right, j ≥ 1); every score is leave-one-cycle-out (LOCO) or forward. Figure: `figures/bl_d0w_summary.png`. Scripts `bl_d0w_*.py`.*\n')
w('## 0. Result\n')
w(f'**Coverage moves from {pc(cb[1]+cb[2],0)} to {pc(ca[1]+ca[2],0)} of D0 lots (rule found, or ranking gate met on unseen cycles). The 90% target is not reached.** What is still outside: {pc(ca[3],0)} ranked below the gate or indicative, {pc(ca[4],0)} unresolved. Lot-level reproduction (F1 0.39–0.45) does **not** change: none of the new findings is a rule the simulator can execute.\n')
w('| tier | meaning | before | after |\n|---|---|---|---|')
for t, mn in ((1, 'rule found (exact rule or ≥ 90% fit)'), (2, 'timing/ranking gate met on unseen cycles (AUC ≥ 0.85, CI lower bound > 0.82, forward ≥ 0.80, placebo < 0.65)'), (3, 'ranked below the gate, indicative (< 150 cells) or only with same-minute information'), (4, 'unresolved or not examined')): w(f'| {t} | {mn} | {pc(cb[t])} | {pc(ca[t])} |')
w(f'\n*Same tier definitions applied to both columns. The earlier "about 60 / 24 / 15" in chat used a looser judgement; the table above is the computed version.*\n')
w('| question | answer | evidence |\n|---|---|---|')
bg = BG.set_index('outcome')
w(f'| Can burst buy-backs be timed on unseen cycles? | **Yes at the ranking level, AUC {bg.loc["burst (>= 5 lots)"].auc:.3f}** (CI {bg.loc["burst (>= 5 lots)"].lo:.3f}–{BA[(BA.outcome=="burst (>= 5 lots)")&(BA.set=="ALL (E + lot state + clock)")].hi.iloc[0]:.3f}, forward {bg.loc["burst (>= 5 lots)"].forward:.3f}, within-cycle {bg.loc["burst (>= 5 lots)"].within_cycle:.3f}, placebo {bg.loc["burst (>= 5 lots)"].placebo:.3f}). But most of it is knowing *where buy-backs happen at all*: the "any buy-back" score alone ranks bursts at {any_score_auc:.3f}. Among buy-back cells, burst vs single is only **{cond_auc:.3f}** AUC. | Observed |')
w(f'| Did ITM depth, side loss, lots at risk or a clock explain bursts? | **No.** Adding them to the existing families changes AUC by {BA[(BA.outcome=="burst (>= 5 lots)")&(BA.set=="ALL (E + lot state + clock)")].auc_loco.iloc[0]-BA[(BA.outcome=="burst (>= 5 lots)")&(BA.set=="E existing families")].auc_loco.iloc[0]:+.3f}; time + ITM depth alone gives {v[2]:.2f}. H-B1, H-B2 and H-B4 are not supported as added information. | Observed |')
w(f'| Which lots does a burst take? | **The biggest losers, not the deepest ITM.** Within a burst minute: unrealised loss AUC {BLA[BLA.feature=="unrealised loss (lakh)"].within_cell_auc.iloc[0]:.2f}, price ÷ entry {BLA[BLA.feature=="price / entry (prev close)"].within_cell_auc.iloc[0]:.2f}, ITM depth only {BLA[BLA.feature=="ITM depth (steps)"].within_cell_auc.iloc[0]:.2f}; all lot features {BLA.iloc[-1].within_cell_auc:.2f}. A ranking by loss finds {pc(BLA[BLA.feature=="unrealised loss (lakh)"].precision_at_m_desc.iloc[0],0)} of the lots taken in its top m (chance {pc(R2["chance_precision_at_m"],0)}), the full model {pc(BLA.iloc[-1].precision_at_m_desc,0)}. **No threshold rule gives the set** (best F1 {BLR.f1.iloc[1]:.2f}, exact set in {pc(BLR.cells_exact_set.iloc[1],0)} of cells, count error {BLR.count_mae.iloc[1]:.0f} lots). | Observed; rule Unresolved |')
w(f'| Other buy-back types | Stop-loss {bg.loc["stop-loss"].auc:.3f}, take-profit {bg.loc["take-profit"].auc:.3f}, partner {bg.loc["partner"].auc:.3f}, burst member {bg.loc["burst member"].auc:.3f}: **gate met**. Roll-out {bg.loc["roll-out"].auc:.3f} (CI {bg.loc["roll-out"].lo:.3f}) and other {bg.loc["other"].auc:.3f}: **not met**. | Observed |')
w(f'| Body-stream longs: strike rule? | **No.** Best is a premium target of ₹3: exact {pc(L1[(L1.subset=="all buy orders")&(L1.rule.str.startswith("premium"))].exact.iloc[0],0)} of lots (placebo {pc(L1[(L1.subset=="all buy orders")&(L1.rule.str.startswith("premium"))].placebo_exact_plus15.iloc[0],0)}, bar 60%); fraction of ATM premium {pc(L1[(L1.subset=="all buy orders")&(L1.rule.str.startswith("fraction"))].exact.iloc[0],0)}; fixed OTM steps {pc(L1[(L1.subset=="all buy orders")&(L1.rule.str.startswith("fixed"))].exact.iloc[0],0)}. | Observed |')
w(f'| Opening count of longs? | **No.** No book quantity beats the same-underlying median (exact {pc(L2[L2.candidate.str.startswith("baseline")].exact.iloc[0],0)}, error {L2[L2.candidate.str.startswith("baseline")].mae.iloc[0]:.1f} lots; the best candidate {pc(L2.exact.iloc[3],0)}). | Observed |')
w(f'| Long buys: when? | AUC {LG[LG.outcome=="long buy"].auc.iloc[0]:.3f} (forward {LG[LG.outcome=="long buy"].forward.iloc[0]:.3f}), but most buys are the opening minutes. **After the opening (post-hoc): AUC {xi.auc:.3f}** (CI {xi.lo:.3f}–{xi.hi:.3f}, placebo {xi.placebo_auc:.3f}, {int(xi.positives)} positive cells, forward 0.949 on 29). The held-long state (price ÷ cost, OTM steps) lifts it from {LX[(LX.outcome=="y_long_buy_intra")&(LX.set=="E existing families")].auc.iloc[0]:.2f}. Small sample. | Observed |')
w(f'| Long sells: when? | **Not met.** Intraday AUC {LG[LG.outcome=="long sell (intraday)"].auc.iloc[0]:.3f} (forward {LG[LG.outcome=="long sell (intraday)"].forward.iloc[0]:.3f}). The held-long state helps (+{LG[LG.outcome=="long sell (intraday)"].gain_over_E.iloc[0]:.2f}), not enough. | Observed |')
w(f'| 15:14 clearance of longs | {pc(R3["l5_share_sold_after_1514"],1)} of the {R3["l5_longs_open_at_1514_lots"]:,} longs open at 15:14 are sold; the kept ones are the cheap ones (median ₹{R3["l5_kept_price_median"]:.2f} vs ₹{R3["l5_sold_price_median"]:.2f}). A price threshold gets {pc(R3["l5_rule_price_threshold_lots_correct_loco"],1)} right against {pc(R3["l5_sell_all_lots_correct"],1)} for "sell all". | Observed |\n')
w('## 1. Buy-back types: timing gate (cell = cycle × minute × right)\n'); w(BG[['outcome', 'best_set', 'auc', 'lo', 'forward', 'within_cycle', 'placebo', 'E_auc', 'gain_over_E', 'gate_strict']].round(3).to_markdown(index=False) + '\n')
w('*The placebo shuffles the labels inside each cycle and is run for the **same set** as the score. Take-profit\'s placebo is 0.640, just under the 0.65 line, because its positives scale with the lots open; it passes by 0.01.*\n')
w('### All sets\n'); w(BA.round(3).to_markdown(index=False) + '\n')
w('## 2. Bursts at lot level\n'); w(BLA.round(3).to_markdown(index=False) + '\n'); w(BLR.round(3).to_markdown(index=False) + '\n')
w(f'*{R2["cells"]} burst cells, {R2["lots"]:,} open-lot rows, {R2["taken"]:,} taken ({pc(R2["taken_share"])}). precision@m = the share of the m lots a ranking puts first that were really taken, m = the true count.*\n')
w('## 3. Body-stream longs\n'); w('### L1 strike rule (leave-one-cycle-out; placebo = the rule applied 15 minutes later)\n'); w(L1.round(3).to_markdown(index=False) + '\n'); w('### L2 opening count\n'); w(L2.round(3).to_markdown(index=False) + '\n')
w('### L3 / L4 timing\n'); w(LG.round(3).to_markdown(index=False) + '\n'); w(LA.round(3).to_markdown(index=False) + '\n'); w('### After the opening minutes (post-hoc)\n'); w(LX.round(3).to_markdown(index=False) + '\n')
w('## 4. Coverage by class\n'); w(CV[['cls', 'lots', 'share', 'tier_before', 'tier_after', 'note']].round(4).to_markdown(index=False) + '\n')
w('### What it would take to reach 90%\n')
gap = [(r.cls, r.share) for r in CV[CV.tier_after >= 3].sort_values('share', ascending=False).itertuples()]
w('| class still outside | share of D0 lots | why |\n|---|---|---|')
for r in CV[CV.tier_after >= 3].sort_values('share', ascending=False).head(10).itertuples(): w(f'| {r.cls} | {pc(r.share)} | tier {r.tier_after}: {r.note} |')
w(f'\nThe classes above sum to {pc(ca[3]+ca[4])}; reaching 90% needs about {pc(0.9-ca[1]-ca[2])} more. The largest pieces are classes whose only high score uses **same-minute information** (replacement solo, other solo, re-centre pair: not available when the order is decided) or that need the **tick path** (counts, exact seconds).\n')
w('## 5. Free run\n* **Unchanged.** No rule from this step can be executed by the simulator: the burst timing is a ranking (the simulator needs a trigger), the burst size and lot selection have no rule, the long strike and opening count have no rule. Lot F1 stays 0.41 / 0.45 / 0.39 (`D0_FREE_RUN`, `D0_SIZING`). A model-driven free run (events from a score threshold) would need every feature recomputed on simulated state and is not done here.\n')
w('## 6. Adversarial read\n')
w(f'* **A ranking is not a trigger.** AUC 0.92 for bursts means the right minutes are ranked above the wrong ones; at the best thresholds earlier work found precision 44% and recall 32% (`D0_PAIR`). Among buy-back cells the burst call is {cond_auc:.2f}.')
w('* **The tier-2 classes are model scores, not rules.** They pass an unseen-cycle test inside one period; they are not statements about other years.')
w('* **Burst size and lot selection stay open** and are what the backtest needs. Taking the biggest losers first is supported (within-minute AUC 0.8), the count is not.')
w('* **Small samples:** intraday long buys 111 positive cells (29 in the forward test), partner 149, burst 388. CIs are wide where cells are few.')
w('* **Everything here is in-sample discovery on 32 cycles from one period.** Nothing has been checked on cycles outside them.')
w('* **The 90% was a coverage target, and coverage is not accuracy.** Even at 90% coverage the lot-level match would stay near the F1 reported, because counts and seconds are not recovered.\n')
w('## Addendum — post-hoc steps (not pre-registered)\n* Placebo re-run for the **best set** of each outcome (the first gate table used the placebo of the ALL set only).\n* Conditional burst-vs-single AUC among buy-back cells, added after seeing AUC 0.92.\n* Long buys and sells **after the opening minutes (j ≥ 5)**, added after seeing that most long buys are in the opening minutes; forward AUC for that subset (0.949 on 29 positives, 0.768 for sells) was computed once, inline.\n* Burst lot ranking by loss and price ÷ entry added to the lot-level test after ITM depth failed (the plan listed ITM depth, ratio, premium, age and origin; loss was derived from ratio and entry).\n')
open(f'{RP}/D0_BURST_LONG.md', 'w').write('\n'.join(L)); print('written', len('\n'.join(L))); print({t: round(cb[t], 3) for t in cb}, {t: round(ca[t], 3) for t in ca}, 'check', round(tot_chk / TOT, 4))
