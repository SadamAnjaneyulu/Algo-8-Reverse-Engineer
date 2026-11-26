"""Builds reports/D0_SELL_TYPES.md and figures/bl_d0t_summary.png from bl_d0t_*.csv / bl_d0t_orders.pkl.gz / bl_summary_d0t1.json."""
import sys, os, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy.stats import binomtest
from bl_common import OUT
RP = os.path.join(os.path.dirname(OUT), 'reports'); R = json.load(open(f'{OUT}/bl_summary_d0t1.json'))
TY = pd.read_csv(f'{OUT}/bl_d0t_types.csv'); T2 = pd.read_csv(f'{OUT}/bl_d0t_types2.csv'); CH = pd.read_csv(f'{OUT}/bl_d0t_chance.csv'); CH2 = pd.read_csv(f'{OUT}/bl_d0t_chance2.csv'); SR = pd.read_csv(f'{OUT}/bl_d0t_strikes.csv'); OP = pd.read_csv(f'{OUT}/bl_d0t_opening.csv'); ST = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); OV = pd.read_csv(f'{OUT}/bl_d0t_overlap.csv', index_col=0)
def table(df, fmt=3):
    c = list(df.columns); s = '| ' + ' | '.join(map(str, c)) + ' |\n|' + '|'.join('---' for _ in c) + '|\n'
    for r in df.itertuples(index=False): s += '| ' + ' | '.join(('—' if (isinstance(x, float) and x != x) else (f'{x:.{fmt}f}' if isinstance(x, float) else str(x))) for x in r) + ' |\n'
    return s
ORD2 = ['scheduled pair', 'opening pair', 're-centre pair', 'breakout pair', 'other pair', 'opening solo', 'far-OTM solo', 'counter-sell solo', 'extreme solo', 'replacement solo', 'late solo', 'other solo']
ST['type2'] = np.where((ST.type != 'opening solo') & (~ST.type.str.endswith('pair')) & (ST.off_steps >= 3), 'far-OTM solo', ST.type)
COL = {'scheduled pair': '#2b6cb0', 'opening pair': '#63b3ed', 're-centre pair': '#4299e1', 'breakout pair': '#90cdf4', 'other pair': '#bee3f8', 'opening solo': '#c05621', 'far-OTM solo': '#9f7aea', 'counter-sell solo': '#48bb78', 'extreme solo': '#ecc94b', 'replacement solo': '#a0aec0', 'late solo': '#718096', 'other solo': '#e2e8f0'}
fig, ax = plt.subplots(1, 3, figsize=(19, 5.5))
ST['hh'] = [f'{int(x // 3600):02d}:{"00" if (x % 3600) < 1800 else "30"}' for x in ST.tod]; H = ST.pivot_table(index='hh', columns='type2', values='lots', aggfunc='sum').fillna(0); bot = np.zeros(len(H))
for t in ORD2:
    if t in H: ax[0].bar(range(len(H)), H[t].values, bottom=bot, color=COL[t], label=t, edgecolor='white', lw=.3); bot += H[t].values
ax[0].set_xticks(range(len(H))); ax[0].set_xticklabels(H.index, rotation=60, fontsize=8); ax[0].legend(fontsize=7, ncol=2); ax[0].set_title('D0 sell lots by type, 09:15 → close (30 cycles)', fontsize=10)
ST['ob'] = pd.cut(ST.off_steps, [-99, -2.5, -1.5, -.5, .5, 1.5, 2.5, 99], labels=['≤-3', '-2', '-1', 'ATM', '+1', '+2', '≥+3'])
M = ST.pivot_table(index='type2', columns='ob', values='lots', aggfunc='sum').fillna(0).reindex([t for t in ORD2 if t in set(ST.type2)]); Mn = M.div(M.sum(1), axis=0)
im = ax[1].imshow(Mn.values, cmap='Blues', aspect='auto'); ax[1].set_xticks(range(Mn.shape[1])); ax[1].set_xticklabels(Mn.columns); ax[1].set_yticks(range(len(Mn))); ax[1].set_yticklabels(Mn.index, fontsize=8)
for a in range(Mn.shape[0]):
    for b in range(Mn.shape[1]):
        if Mn.values[a, b] >= .05: ax[1].text(b, a, f'{Mn.values[a, b]:.0%}', ha='center', va='center', fontsize=7, color='white' if Mn.values[a, b] > .5 else 'black')
ax[1].set_xlabel('strike vs ATM (steps; + = OTM for the sold right)'); ax[1].set_title('Which strike each type sells (share of its lots)', fontsize=10)
oo = OP.dropna(subset=['CE_share']); ax[2].scatter(oo.gap_steps, oo.CE_share, s=np.clip(oo.open_sell_lots, 10, 200), color='#c05621', alpha=.7); ax[2].axhline(.5, color='gray', lw=.8, ls=':'); ax[2].axvline(0, color='gray', lw=.8, ls=':')
ax[2].set_xlabel('opening gap (D0 open − D-1 close, strike steps)'); ax[2].set_ylabel('CE share of sells 09:15–09:30'); ax[2].set_title(f"Opening: they sell the side the gap favours (Spearman {R['gap_vs_CE_share_spearman'][0]:.2f})", fontsize=10)
plt.tight_layout(); plt.savefig(os.path.join(RP, 'figures', 'bl_d0t_summary.png'), dpi=130)
s = SR.set_index('type'); t2 = T2.set_index('type2'); fo = R['far_otm']; ro = {x['shift']: x for x in fo['rollout']}; c2 = CH2.set_index('rule'); ch = CH.set_index(['group', 'rule'])
hs = R['heavier_side_sign']; p_heavy = binomtest(hs[0], hs[1]).pvalue; g = R['gap_up_sells_more_CE']; tot = int(T2.lots.sum())
sh = lambda t: t2.loc[t, 'share_lots']
os_ = ST[ST.type == 'opening solo'].groupby('cp').apply(lambda d: float(np.median(np.repeat(d.off_steps.values, d.lots.values)))).to_dict(); top6 = sum(sorted(fo['by_cycle'].values(), reverse=True)[:6]) / fo['lots']
txt = f"""# Algo 8 — D0 step 1: how many kinds of selling, and which strikes (09:15 → close)

*Plan `D0_SELL_TYPES_PLAN.md`, written before the tests. A post-hoc addendum (far-OTM type) was written after the first run. In-sample: D0 of the 30 cycles with both logs, {tot:,} body sell lots. Figure: `figures/bl_d0t_summary.png`.*

## 0. Result: D0 has 9 kinds of selling, plus an unexplained remainder
| # | Kind | Share of D0 sell lots | What triggers it | Strike sold | Evidence |
|---|---|---|---|---|---|
| 1 | **Scheduled pair** (CE + PE) | {sh('scheduled pair'):.0%} | Fixed timetable per underlying × version (seconds repeat across cycles) | ATM {s.loc['scheduled pair', 'exact_atm']:.0%} exact | Observed |
| 2 | **Opening pair** | {sh('opening pair'):.0%} | 09:15–09:18, before the timetable starts | ATM {s.loc['opening pair', 'exact_atm']:.0%}; at a carried strike {s.loc['opening pair', 'carried_strike']:.0%} | Observed |
| 3 | **Opening solo burst** | {sh('opening solo'):.0%} | 09:15–09:18: sells the side the opening gap favours | median offset CE {os_['CE']:+.0f} / PE {os_['PE']:+.0f} steps (− = ITM); at a carried strike {s.loc['opening solo', 'carried_strike']:.0%} | Observed |
| 4 | **Counter-sell** | {sh('counter-sell solo'):.0%} | A buy-back on the other right within ±60 s (51% vs 25% chance) | ATM ±1 {s.loc['counter-sell solo', 'within1']:.0%}; same strike as the other side's buy-back {s.loc['counter-sell solo', 'counter_same_strike_as_other_bb']:.0%} | Observed (about half above chance) |
| 5 | **Far-OTM roll-out** (post-hoc) | {sh('far-OTM solo'):.0%} | After buying back a nearer strike on the same right, sell further OTM ({ro[0]['share']:.0%} vs {min(ro[600]['share'], ro[-600]['share']):.0%}–{max(ro[600]['share'], ro[-600]['share']):.0%} chance) | {fo['off_q'][1]:.0f}–{fo['off_q'][2]:.0f} steps OTM, median ₹{fo['px_q'][1]:.0f} | Observed; mostly SENSEX V1 |
| 6 | **Re-centre pair** | {sh('re-centre pair'):.0%} | A body buy-back within 60 s before ({ch.loc[('pair', 'recentre'), 'share_flagged']:.0%} vs {ch.loc[('pair', 'recentre'), 'chance_share']:.0%} chance) | ATM {s.loc['re-centre pair', 'exact_atm']:.0%}, ±1 {s.loc['re-centre pair', 'within1']:.0%} | Observed |
| 7 | **Fresh-extreme solo** (the D-1 ladder) | {sh('extreme solo'):.0%} | The minute makes a 60-minute favourable extreme ({c2.loc['extreme', 'share_flagged']:.0%} vs {c2.loc['extreme', 'chance_share']:.0%} chance) | ATM ±1 {s.loc['extreme solo', 'within1']:.0%}, leaning ITM | Observed |
| 8 | **Breakout pair** (D-1 two-candle breakout) | {sh('breakout pair'):.0%} | First break of the previous two 30-min candles | ATM ± 1 step ({s.loc['breakout pair', 'within1']:.0%} within one) | Observed |
| 9 | **Late solo** | {sh('late solo'):.1%} | From 15:00 | around ATM | Observed (small) |
| — | **Unexplained**: "replacement" + other solo + other pair | {sh('replacement solo') + sh('other solo') + sh('other pair'):.0%} | "Replacement" (same-right buy-back before) is barely above chance after removing roll-outs ({c2.loc['replacement', 'share_flagged']:.1%} vs {c2.loc['replacement', 'chance_share']:.1%}) | ATM ±1 mostly | Unresolved |

**Strikes overall:**
* **Strike vs ATM:** {s.loc['ALL', 'exact_atm']:.0%} of D0 sell lots are at the ATM strike (nearest the previous minute's close) and {s.loc['ALL', 'within1']:.0%} within one step.
* **Mostly strikes already held, not new ones.**
  * **{s.loc['ALL', 'carried_strike']:.0%}** go to strikes already short from D-1;
  * **{s.loc['ALL', 'D0_strike']:.0%}** to strikes opened earlier on D0;
  * only **{s.loc['ALL', 'new_strike']:.0%}** to new strikes.
* D0 selling **adds to the book they already carry**.

**At the opening (09:15–09:30, {R['open_lots']:,} lots, {R['open_lots'] / tot:.0%} of D0 selling):** the carried book drives the first decisions.
* **The gap side.**
  * The side sold is the one the overnight gap favours: after a gap up they sell more PE, after a gap down more CE.
  * Spearman {R['gap_vs_CE_share_spearman'][0]:.2f} (p {R['gap_vs_CE_share_spearman'][1]:.4f}); against the gap in {g[1] - g[0]} of {g[1]} cycles (p {g[2]:.3f}).
* **Carried strikes.** {R['open_status'].get('carried strike', 0) / R['open_lots']:.0%} of opening lots are added at strikes carried from D-1.
* **The heavier side.** The heavier carried side gets more: median {R['heavier_side_share_median']:.0%} of opening lots; more than half in {hs[0]} of {hs[1]} cycles (p {p_heavy:.2f}). This is weaker than the gap effect.

## 1. Pre-registered taxonomy (primary)
{table(TY)}

**Chance levels along the precedence chain:**

{table(CH)}

**After the far-OTM refinement:**

{table(CH2)}

**Overlap of solo flags** (lots carrying both):

{table(OV.reset_index().rename(columns={'index': 'flag'}), 0)}

## 2. Refined taxonomy (post-hoc: far-OTM roll-out as its own type)
{table(T2.sort_values('lots', ascending=False))}

**Far-OTM roll-out:**
* {fo['lots']} lots in {fo['cycles']} cycles. By underlying × version: {', '.join(f'{k} {v}' for k, v in fo['und'].items())}.
* Time 10/50/90%: {', '.join(f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}' for t in fo['time_q'])}.
* After a same-right buy-back at a nearer strike within 60 s: {ro[0]['share']:.0%} of lots, against {ro[600]['share']:.0%} / {ro[-600]['share']:.0%} with buy-backs shifted +10 / −10 min. Sold premium / bought premium, median {ro[0]['ratio_median']:.2f}.

## 3. Strikes by type
{table(SR)}

Columns:
* `off_*`: strike offset from ATM in steps; + = OTM for the sold right.
* `carried_strike` / `D0_strike` / `new_strike`: whether the strike was already short from D-1, opened earlier on D0, or new.
* `same_as_last_sale`: the same strike as the previous sale on that right.
* `d1_premium_rule`: the strike whose premium is nearest the last sale's premium, the D-1 solo rule.
* Chance for an exact-strike rule ≈ 1/7.

## 4. Opening window per cycle
{table(OP, 2)}

## 5. Caveats
* **In-sample:** 30 cycles. Shares are cycle-weighted by lots; CIs come from a cycle bootstrap in Section 1.
* **Trigger labels are associations.** A label marks a timing coincidence (for example, a buy-back within ±60 s). Only the share **above chance** counts as evidence for the trigger.
* **The far-OTM type is post-hoc** and concentrated in a few cycles: 6 cycles hold {top6:.0%} of it.
* **The ATM reference at 09:15** is the D0 opening price.

## Next
Step 2, as agreed: **quantity, lot sizes and risk** of D0 selling. How many lots each type sells, and what sets the count: slot, book size, gap, premium. How risk is capped per side and per strike.

## Run order
`bl_d0s_label.py` → `bl_d0s_tt.py` (out-of-fold waves) → `bl_d0b_ledger.py` → `bl_d0t_types.py` (~1 min) → `make_d0t_report.py`.
"""
open(os.path.join(RP, 'D0_SELL_TYPES.md'), 'w').write(txt); print('written', len(txt))
