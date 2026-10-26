"""Render the allocation/side investigation from audited saved results."""
import csv
import json
from pathlib import Path

from audit_strike_hedge_rules import OUT


def rows(name):
    return list(csv.DictReader((OUT/name).open()))


def pct(value):
    return 'none' if value in ('', None) else f'{100*float(value):.1f}%'


def main():
    overview = json.loads((OUT/'allocation_study_overview.json').read_text())
    sizes = rows('allocation_size_schedule.csv')
    size_table = '| Clock | Base units per role | NIFTY quantity per role | SENSEX quantity per role | Dates matching all four modal quantities: N / S |\n| --- | ---: | ---: | ---: | --- |\n'
    for clock in sorted({r['clock'] for r in sizes if r['phase'] == 'preexpiry'}):
        group = {r['underlying']: r for r in sizes if r['phase'] == 'preexpiry' and r['clock'] == clock}
        n, s = group['NIFTY'], group['SENSEX']
        size_table += f"| {clock} | {float(n['modal_short_CE'])/65:g} | {n['modal_short_CE']} | {s['modal_short_CE']} | {n['modal_joint_sessions']}/{n['sessions']} / {s['modal_joint_sessions']}/{s['sessions']} |\n"
    example = next(r for r in rows('allocation_window_sizes.csv') if r['underlying'] == 'NIFTY' and r['date'] == '2026-07-13' and r['clock'] == '09:16')
    cash_table = '| Role | Actual newly opened quantity | Premium cashflow |\n| --- | ---: | ---: |\n'
    for side, right in [('short', 'CE'), ('short', 'PE'), ('long', 'CE'), ('long', 'PE')]:
        direction = 'received' if side == 'short' else 'paid'
        cash_table += f"| {side} {right} | {example['new_'+side+'_'+right+'_quantity']} | ₹{float(example['new_'+side+'_'+right+'_premium_cash']):,.2f} {direction} |\n"
    direction = rows('allocation_side_direction_summary.csv')
    direction_table = '| Index / short side | Losing first-cover parents with spot data (FIFO) | Spot moved against that short | Fraction |\n| --- | ---: | ---: | ---: |\n'
    for u in ('NIFTY', 'SENSEX'):
        for right in ('CE', 'PE'):
            r = next(r for r in direction if r['attribution'] == 'fifo' and r['underlying'] == u and r['option_type'] == right and r['phase'] == 'preexpiry')
            count, adverse = int(r['losing_short_with_spot']), int(r['losing_short_and_adverse_spot'])
            direction_table += f'| {u} {right} | {count} | {adverse} | {100*adverse/count:.1f}% |\n'
    side = rows('allocation_side_rule_evaluation.csv')
    model_table = '| Exit-onset model | Signal precision | Actual onsets caught | ±2-minute precision / recall |\n| --- | ---: | ---: | --- |\n'
    for phase in ('preexpiry', 'expiry'):
        for scope, group in [('pooled_normalized', 'all'), ('per_index', 'NIFTY'), ('per_index', 'SENSEX'), ('nifty_with_oi', 'NIFTY')]:
            r = next(r for r in side if r['task'] == phase+'|'+scope+'|'+group and r['policy'] == 'best_f1')
            model_table += f"| {r['task']} | {pct(r['precision'])} | {pct(r['recall'])} | {pct(r['tolerance2_precision'])} / {pct(r['tolerance2_recall'])} |\n"
    economics = rows('allocation_economic_quality_summary.csv')
    pe_economic = next(r for r in economics if r['task'] == 'fifo|PE|pooled' and r['quality'] == 'all')
    economic_table = '| Inferred allocation | Quote-quality subset | Allocations / weeks | Mean improvement per ₹10,000 initial static tail loss | Week-resampled 95% interval |\n| --- | --- | --- | ---: | --- |\n'
    for kind in ('CE', 'PE', 'combined'):
        for quality in ('all', 'nonzero_volume_and_payoff_bounds'):
            r = next((r for r in economics if r['task'] == 'fifo|'+kind+'|pooled' and r['quality'] == quality), None)
            if r:
                economic_table += f"| {kind} | {quality} | {r['allocations']} / {r['weeks']} | ₹{float(r['mean_improvement_per_10000_tail_loss']):,.2f} | [₹{float(r['lower']):,.2f}, ₹{float(r['upper']):,.2f}] |\n"
    budget = rows('allocation_budget_evaluation.csv')
    budget_table = '| Conditional sizing, earlier own-index budget | Clock count | Premium budget | Notional budget | Vega budget | Gamma budget | Theta budget |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
    for phase in ('preexpiry', 'expiry'):
        for u in ('NIFTY', 'SENSEX'):
            values = {r['family']: r['exact_rate'] for r in budget if r['scope'] == 'own_index' and r['phase'] == phase and r['underlying'] == u}
            budget_table += '| '+phase+' '+u+' | '+' | '.join(pct(values[k]) for k in ('clock_quantity', 'premium', 'notional', 'vega', 'gamma', 'theta'))+' |\n'
    frozen = json.loads((OUT/'allocation_frozen_stop_summary.json').read_text())
    rates = [r['match_rate'] for r in frozen['evaluation'] if r['model'] == 'selected_stop_program']
    association = json.loads((OUT/'allocation_association_summary.json').read_text())
    entry_results = rows('allocation_entry_filter_evaluation.csv')
    genuine = next(r for r in entry_results if r['task'] == 'expiry_any_short_suppression|pooled_common|all' and r['policy'] == 'best_f1')
    extra_table = '| Corrected off-schedule any-short target | Later positive minutes | Selected signal precision | Actual entries caught |\n| --- | ---: | ---: | ---: |\n'
    for task in ('preexpiry_offschedule_any|pooled_common|all', 'expiry_offschedule_any|pooled_common|all', 'expiry_offschedule_any|per_index|SENSEX'):
        r = next(r for r in entry_results if r['task'] == task and r['policy'] == 'best_f1')
        extra_table += f"| {task} | {r['positives']} | {pct(r['precision'])} | {pct(r['recall'])} |\n"
    text = f'''# Allocation sizes, separate-side exits and NIFTY/SENSEX comparison

The strongest new result is a **shared sizing template**: the separately
computed modal four-role quantities agree after normalizing NIFTY by 65 and
SENSEX by 20 at **all 22 pre-expiry clock slots**. This is evidence of a common
core framework, with index-specific configuration and many daily exceptions.
It is not proof of identical source code or an 80–90% complete reconstruction.

The audit also corrects the earlier entry-filter interpretation. Of the old
**27 missing same-strike pair windows**, **12 contain both-right short sales,
six contain one-right sales and only nine contain no new short**. A filter
cannot be inferred by treating all 27 as rejected entries.

All clock times are IST. Parameters use expiries through 31 August; later
September–October checks were already inspected in previous work. Quantity modes
and direction summaries below describe all observed data, not independent tests.

## 1. What is allocated at each clock

The following are modal **newly opened quantities during each window**, across
strikes in each role. Where a modal vector is zero, that slot most often has no
new allocation; it is not a prohibition on trading. Nonzero modes can occur in
far fewer than 80% of sessions. Initial 09:16 uses 09:15–09:17 to include preceding
hedge fills; quarter windows use T−2 seconds through T+3 minutes, exclusive.

{size_table}
This common relative sequence begins **3, 2, 3, 1, 4, 1, 2**. That is a useful
programmed-schedule hypothesis. Additional trades within a window and same-side
management can make the actual size differ. The full per-date quantities,
pure-parent counts, after-window inventory and per-role premium flows are in
`allocation_window_sizes.csv`.

For example, actual opening flows on 13 July NIFTY are:

{cash_table}
**Premium spending/receipts are not capital allocation or broker margin.** The
₹2 crore note does not specify the reserved margin or risk budget per allocation.
Gross hedge purchases can exceed net holdings: on 17 August NIFTY, opening CE
hedge purchases total 325 units but the 09:17 CE-long inventory is 195 after
intervening sales. Do not equate a fill count, premium credit and net exposure.
The export also does not establish whether stated capital is shared between
indices or reserved separately for each one.
For the 13 July 09:17 frozen opening book, a payoff calculation gives a maximum
expiry loss of **₹{float(example['after_window_frozen_expiry_max_loss_before_costs']):,.2f}**
before costs, conditional on holding that book unchanged. This is a terminal
payoff bound, not margin, capital invested, the actual stop or an intraday
mark-to-market loss bound. Corresponding after-window frozen bounds are exported
as outcomes, not used as pre-entry model features.

### Does a premium or Greek budget explain varying size?

Test earlier per-clock fixed premium, underlying-notional, Vega, Gamma-shock and
Theta budgets with integer-unit rounding, against clock-modal quantities. Fit
rounding on leave-cycle-out earlier data; later quote references precede the
execution window. These are short-core budget proxies, not broker margins.
This test is **conditional on an observed allocation occurring** and does not
predict entry eligibility. Exact joint CE/PE quantity matching is:

{budget_table}
The risk-budget variants do not recover a general 80–90% sizing formula. Quote
coverage and exclusions are exported. Cross-index transferred normalized clock
counts match the same pre-expiry percentages as own-index clock counts on this
quoted subset, further supporting a common timing/weight template.

## 2. What market movement accompanies CE/PE reductions?

A short CE generally loses when the index rises; a short PE generally loses
when it falls. Test spot changes from the entry reference to the completed
minute before the first attributed cover, not an assumed direction.

{direction_table}
These high conditional percentages describe **losing covers after they occur**.
They are not 90–96% successful exit predictors: many adverse moves do not trigger
an order, and some covers occur at profits. FIFO/LIFO attribution sensitivity
and all phases are in `allocation_side_direction_summary.csv`.

The 13 July opening CE shorts close in pieces at 09:50, 09:53 and 09:59 while
their original PE side survives. Same-side new entries often follow within ten
minutes, but the next clock-based sale is not proof of a cover-triggered re-entry.

## 3. Allocation/protection identity and separate-side stop tests

Reconstruct {association['pure_short_parents']:,} stable pure new-short parents.
Infer {association['inferred_fresh_hedge_links']:,} one-to-one outward same-right
fresh-hedge links within five seconds at equal filled quantity;
{association['ambiguous_hedge_links']:,} links have multiple eligible hedge candidates.
The link assignment minimizes time distance. It is not an original allocation ID.
No linked fresh hedge does not imply that existing protection is absent.

Track short entry lots under both FIFO and LIFO. Their FIFO realized short P&L
reconciles with the existing ledger to numerical precision. Observable side
features include pooled and lot cost references, partial reductions, carry
fractions, trailing prices, side-specific hedge-inclusive equity and known prior
inventory. Exact allocation ownership can remain ambiguous at shared strikes.

Two complementary tests were run:

* **Contract-side onsets:** predict an actual covering order after five quiet
  minutes on that contract. Retain no-order opportunities. Fit combinations of
  premium, price/trend, Greeks and risk state on earlier cycles, comparing pooled,
  per-index and per-index/right rules. Report exact-minute and one-to-one
  ±2-minute matches separately. OI is added in a separate NIFTY comparison.
* **Frozen inferred allocations:** test side verticals and same-strike combined
  four-leg subsets using {frozen['atoms']} loss/profit/carry/trailing atoms,
  {frozen['or_pairs']:,} OR pairs and an expiry time fallback. Entry-cost, short
  premium, hedge-inclusive value and prior-close carry references differ.
  Target the first partial short reduction, using both FIFO/LIFO attribution.

The onset models' earlier-selected best-F1 later results are:

{model_table}
Separate index/right models also fail to reach both 80–90% precision and broad
coverage. The frozen stop programs match only **{100*min(rates):.1f}–{100*max(rates):.1f}%**
of later first-reduction targets within two minutes across tested groups.
Examples selected on earlier data include CE premium loss +50% OR 95% hedged
profit, and PE premium/carry stops. Their low matching rates mean these are
**candidates, not recovered original stop instructions**. The supplied 4% carry
and 1% capital statements are not replaced by these fitted thresholds.

## 4. Greeks, IV, OI and range filters

Build {overview['audits']['contract_minutes']:,} past-known active-short contract
minutes and 24,860 full-session portfolio contexts. Compute model-estimated
Delta, Gamma, Vega, Theta, per-contract IV and full-book/side exposures, normalized
by premium, quantity or stated capital. Add IV changes, Gamma price-shock cost,
RSI/EMA/Bollinger/ATR/ADX/Supertrend/breakout features, trend efficiency, prior
session context, intraday realized-volatility proxies, volume and same-strike OI.
Market inputs are completed candles; full-book Greeks stay missing if any active
leg cannot be fitted. These are Black-model estimates, not exchange Greeks.

**SENSEX OI is unavailable in the received data (all supplied values are zero).**
NIFTY OI/PCR/change tests do not produce a robust high-coverage trigger. The data
contain traded contracts, not the full chain; market-wide OI concentration,
max-pain and a full-chain OI projection are not identifiable from this subset.

### Correct the labels before inferring a range gate

Among 273 later expiry quarter opportunities, 184 have actual prior short
exposure. Of these, **175 have any new short entry, 169 have both rights and
157 qualify as a same-strike pair**. The remaining 89 inactive-book opportunities
have no new shorts in the tested window. Thus a timer plus active-book baseline
gets **95.1% any-entry precision and 100% coverage**, with nine false signals.
That is conditional decision matching, not an autonomous original controller.

NIFTY contributes 80/83 active positives; SENSEX contributes 95/101. The nine
truly empty windows are three NIFTY and six SENSEX cases. Revised models and
named range filters test this target separately from missing a pair or a right.
The earlier-selected pooled risk/Greek model identifies
**{genuine['true_positives']}/{genuine['positives']}** genuine no-entry windows but also rejects
**{genuine['false_positives']}** valid entry windows. Its entry precision/coverage are
{pct(genuine['entry_precision'])}/{pct(genuine['entry_recall'])}, versus 95.1%/100% for the
simple active-book timer. It has not recovered a useful common rejection rule.
They do not justify inventing a universal range filter. A high entry precision
alone can be achieved by predicting almost every active timer; it is necessary
also to identify the rare true rejections without rejecting valid entries.

One concrete correction is SENSEX 10 September: at 09:45 new CE sales are at
**74,900** and PE sales at **74,700**. Their strike sets do not overlap. Selling
continues but the same-strike pair label is false. The strategy therefore has
straddle-like, different-strike and one-sided activity; not every addition is a
new ATM straddle.

The old 265 later paired “extra” event minutes also include
**{overview['extra_label_boundary']['timer_only_within2s_of_next_quarter']} minutes** whose new-short parents all begin
within two seconds of the upcoming quarter. New off-schedule targets remove
the full fixed timer window and include one-right/different-strike entries.
Those labels must not be confused with the older physical-minute paired labels.
The revised any-short off-schedule tests count one-right and different-strike
sales, exclude the fixed timer interval and use all no-order opportunities:

{extra_table}
The stricter SENSEX expiry setting reaches 85.7% precision on 28 signals but
captures only 24/243 actual off-schedule event minutes (9.9%). Its 90%-target
setting catches only nine. Neither reaches the joint 80–90% goal. These targets
cover the studied 09:30–14:43 off-clock band, not every possible overnight or
opening decision; nominal order labels also do not establish a verified signal
timestamp or resolve all pending fills.

Initial no-trade calendar eligibility is still not labeled by the export, so
this does not prove the absence of every possible opening range filter.

## 5. Same algorithm on both indices?

**Strong evidence supports the same core family and sizing template, with
different configuration.** The shared 22-slot modal schedule is directly
observable. Both indices use protected short options, repeated allocations,
side-specific reductions and expiry management. Distinctions include observed
65/20 quantity units, 50/100 strike grids, initial wing histories, routine hedge
budget rounding, date-specific schedule changes and differing expiry activity.

Per-index fitting sometimes helps a particular metric but does not recover an
80–90% exit controller. Neither similar best-fit thresholds nor different fitted
trees can prove whether the original source code is shared. The September
SENSEX different-strike activity is a real configuration/selection clue, not
evidence that a generic range indicator caused those entries.

## 6. Economic diagnostic after costs

For unambiguous inferred links, compare the selected stop with holding the same
frozen allocation until the clock signal. Share actual entry prices and quantity;
execute exits at next-minute opens. Apply 25 bps premium turnover, ₹20 per order
and ₹0.05 per transacted quantity. Normalize by initial static expiry tail loss,
not margin. These are overlapping conditional allocations, not account NAV.

{economic_table}
The PE-side result is a lead to investigate, not recovered Algo 8 alpha. The
PE candidate still averages **₹{float(pe_economic['mean_candidate_net_per_10000_tail_loss']):,.2f}**
after costs per ₹10,000 initial static tail loss, versus
**₹{float(pe_economic['mean_clock_net_per_10000_tail_loss']):,.2f}** for the clock comparison.
This is loss reduction in that subset, not positive expected profit. The
controller's low matching rates mean it differs substantially from the recorded
one. Quality filters are ex-post sensitivities, not entry/exit rules. The subset
does not test entry selection, initial capital allocation, dynamic risk equality,
all searched-model uncertainty or new independent data. Candidate and clock
absolute net outcomes are also exported; an improvement is not necessarily a
positive expected return.

## 7. Deliverables and reproduction

`allocation_study_overview.json` audits causal cutoffs, quote/lot accounting,
later-only predictions and valid frozen exit deadlines, and hashes the artifacts.
All **151 repository tests pass**, including Greek/scalar reconciliation,
FIFO/LIFO accounting, one-to-one associations, cooldown ownership, event matching,
single-class folds, carry references and activated trailing logic.

```bash
python research/analyze_allocation_sizes.py
python research/build_allocation_side_features.py
python research/build_allocation_index_context.py
python research/analyze_side_allocations.py
python research/audit_entry_window_labels.py
python research/search_side_controllers.py
python research/scan_side_exit_hypotheses.py
python research/search_entry_risk_filters.py
python research/search_allocation_budgets.py
python research/scan_allocated_stop_rules.py
python research/audit_allocation_economics.py
python research/summarize_allocation_side_study.py
python research/write_allocation_side_report.py
python -m unittest discover -s research -p 'test_*.py'
```

The next identification problem is the per-allocation activation/exit state:
which requested entry is linked to which protection, its reference/reset level,
and which side is permitted to re-enter. The observed common clock weights,
different-strike episodes, nine actual empty opportunities and first cover
events provide concrete tests. A new high historical fit should not replace
those missing states or be called profitable alpha without a full replay.
'''
    (Path(__file__).resolve().parent/'ALLOCATION_SIDE_FINDINGS.md').write_text(text)


if __name__ == '__main__':
    main()
