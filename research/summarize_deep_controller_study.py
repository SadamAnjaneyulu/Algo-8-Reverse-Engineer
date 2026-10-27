"""Generate the reviewed broad-search findings from exported measurements."""
import json
from pathlib import Path

import pandas as pd

from audit_strike_hedge_rules import OUT,ROOT


def table(rows):
    fields=list(rows[0])
    return '\n'.join(['| '+' | '.join(fields)+' |','| '+' | '.join('---' for _ in fields)+' |']+
                     ['| '+' | '.join(str(r[k]) for k in fields)+' |' for r in rows])


def main():
    state={name:json.loads((OUT/name).read_text()) for name in
           ('deep_exit_search_summary.json','deep_extra_search_summary.json','deep_hedge_timing_summary.json')}
    lot=json.loads((OUT/'deep_allocation_stop_summary.json').read_text())
    counts=[dict(Search='Contract-side exits',Programs=f"{state['deep_exit_search_summary.json']['programs_scored']:,}"),
            dict(Search='Off-schedule side entries',Programs=f"{state['deep_extra_search_summary.json']['programs_scored']:,}"),
            dict(Search='Held-hedge replacement timing',Programs=f"{state['deep_hedge_timing_summary.json']['programs_scored']:,}")]
    refresh=pd.read_csv(OUT/'deep_hedge_refresh_summary.csv')
    expiry=refresh[refresh.phase=='expiry'].sum(numeric_only=True)
    exits=pd.read_csv(OUT/'deep_allocation_stop_evaluation.csv');exits['mode']=exits.task.str.split('|').str[0];exits['attribution']=exits.task.str.split('|').str[1]
    summary=exits.groupby(['mode','attribution','model'])[['later_cases','matches2']].sum().reset_index()
    scores=[dict(Market_input=r['mode'],Ownership=r['attribution'],Program=r['model'],Later=f"{int(r['matches2'])}/{int(r['later_cases'])}",Match=f"{r['matches2']/r['later_cases']:.1%}")
            for r in summary.to_dict('records') if r['mode']=='completed_close' and r['attribution']=='fifo']
    sizing=pd.read_csv(OUT/'deep_timer_size_selected.csv')
    sz=[dict(Index=r['underlying'],Phase=r['phase'],Windows=r['later_windows'],Four_roles=f"{r['later_four_role_match']:.1%}",Short_pair=f"{r['later_short_pair_match']:.1%}")
        for r in sizing.to_dict('records') if r['scope']=='ordinary_positive_timer_slots' and r['underlying']!='pooled']
    economic=pd.read_csv(OUT/'deep_controller_economics_summary.csv')
    es=[dict(Index=r['underlying'],Allocations=r['allocations'],Cycles=r['cycles'],Candidate_net=f"₹{r['candidate_net']:,.2f}",Clock_net=f"₹{r['clock_net']:,.2f}",Improved_cycles=r['cycles_improved'])
        for r in economic.to_dict('records') if r['quality']=='nonzero_volume_and_price_bounds']
    audit=pd.read_csv(OUT/'deep_management_audit_summary.csv')
    hedge=[dict(Index=r['underlying'],Phase=r['phase'],Hedge_buys=r['new_long_parents'],Near_new_short=f"{r['long_with_new_short_5s']}/{r['new_long_parents']} ({r['long_with_new_short_5s']/r['new_long_parents']:.1%})",
                New_shorts_after_cover_5min=f"{r['fresh_short_with_cover_5min']}/{r['new_short_parents']}") for r in audit.to_dict('records')]
    notes=[]
    for name in ('deep_exit_search_evaluation.csv','deep_extra_search_evaluation.csv','deep_hedge_timing_evaluation.csv'):
        d=pd.read_csv(OUT/name);best=d[(d.policy=='best_f1')&(d.cooldown==5)]
        for r in best.to_dict('records'):
            notes.append(dict(Task=r['task'],Precision=f"{r['precision']:.1%}",Recall=f"{r['recall']:.1%}",
                              Tolerance_precision='—' if pd.isna(r['tolerance2_precision']) else f"{r['tolerance2_precision']:.1%}",
                              Tolerance_recall='—' if pd.isna(r['tolerance2_recall']) else f"{r['tolerance2_recall']:.1%}"))
    text=f'''# Algo 8: expanded controller search and what it establishes

**The 80–90% reconstruction target has not been reached.** A broader relevant
search still does not recover a precise general exit, re-entry or hedge-refresh
controller. The new useful findings are that most hedge buying accompanies fresh
shorts, genuine expiry-day hedge replacements usually move protection inward,
and side exits materially change the economics of the sampled allocations.

## Search scope and validation

{table(counts)}

These total **{sum(s['programs_scored'] for s in state.values()):,} state-program/group scores**.
They test premium loss/profit, FIFO/LIFO lot costs, previous-close and expiry-open
carry references, activated trailing stops, adverse spot moves, Delta, IV,
Gamma, side/portfolio equity, exposure, old-hedge decay, hedge/ATM premium ratios,
clock gates and time since entries/covers. The grammar includes three-condition
AND programs and gated loss/profit OR programs. It is finite and does not cover
every possible original program. The same expression can be scored in separate
index, right and session groups; these are not millions of independent hypotheses.

A separate allocation-level search tests **{lot['atoms']} atoms**, including
1–200% premium losses, 10–99% profits, fixed low-price exits and activated trails,
in **{lot['stop_target_pairs']:,} stop/target pairs** with 0/1/2-minute delays.
The final study scores **{lot['program_context_comparisons']:,} pair/lag/context
comparisons**, including entry-clock modules and order rank within the entry
minute. Those are repeated contextual comparisons, not that many unique rules.

Thresholds and schedules use expiries through 31 August; later September/October
measurements are reported separately. These later dates were already inspected
in previous research and are not untouched validation. The broad state search
selects on earlier scores without nested cross-validation. Sparse-event tasks
can overfit severely; fitted rules must not be assigned probabilities of being
the original code. Five-minute prediction cooldown results are shown below;
0/15-minute variants are also exported and were not selected on later performance.

## 1. Separate CE/PE exits

{table(scores)}

Matches allow ±2 minutes around the first attributed partial short cover.
FIFO and LIFO ownership are both tested because shared strikes hide original
allocation identity. Simple global programs match approximately 29% of later
first reductions on completed closes. Intrabar high-touch variants improve the
global match only to about 31–32%; a high touch is a within-candle bound, not an
available pre-candle signal or an executable price. Clock/rank refinements do
not establish an 80–90% controller.

For the completed-close/FIFO global candidates, pre-expiry CE fitted loss
thresholds are 48% NIFTY / 55% SENSEX, while SENSEX pre-expiry PE selects 66%.
NIFTY expiry PE selects 61%. These are low-coverage fitted candidates, **not
recovered stop instructions**. Other groups select trailing/profit conditions.
The stated 4% carry stop and 1% of ₹2 crore expiry capital stop retain unresolved
denominators, reset conventions and scope. This search does not redefine them.

The first illustration shows a rising NIFTY, increasing initial CE prices and
separate initial CE covers while the initial PE survives. A rise normally hurts
the short CE and a fall normally hurts the short PE; hedges and IV can modify
the net side result. These illustrative charts are not independent validation.

![NIFTY spot and option prices](outputs/deep_case_nifty_side_exits.png)

## 2. Extra entries and re-entry

The entry search retains no-entry opportunities while testing recent covers,
re-entry delays, fresh allocations, range/movement, Greeks, equity and capacity.
Whole-minute timer neighbors are excluded to avoid treating a T−2-second fill
as an off-schedule decision. These are side-minute labels, not same-strike pair
labels. No tested program combines 80–90% precision with broad event coverage.

{table(hedge)}

The last column is temporal association, not causation: a new short within five
minutes of a cover may also be due to the next timer or another module. Later
high-frequency expiry flow contains far more such associations than pre-expiry
flow. No exact reset/re-entry controller is established.

## 3. What genuine hedge replacements do

Among matched equal-quantity different-strike long replacements within five
seconds, with no nearby same-right fresh short, expiry contributes
**{int(expiry['paired_refreshes'])} parent pairs**. Of these:

- **{int(expiry['inward_refreshes'])}/{int(expiry['paired_refreshes'])} ({expiry['inward_refreshes']/expiry['paired_refreshes']:.1%})** move the hedge strike inward.
- **{int(expiry['gamma_increased'])}/{int(expiry['full_model_cases'])} ({expiry['gamma_increased']/expiry['full_model_cases']:.1%})** increase modeled Gamma protection.
- **{int(expiry['abs_vega_reduced'])}/{int(expiry['full_model_cases'])} ({expiry['abs_vega_reduced']/expiry['full_model_cases']:.1%})** reduce absolute modeled portfolio Vega.
- **{int(expiry['abs_delta_reduced'])}/{int(expiry['full_model_cases'])} ({expiry['abs_delta_reduced']/expiry['full_model_cases']:.1%})** reduce absolute modeled portfolio Delta.

This supports strengthening protection closer to spot near expiry. It does not
make 81–82% a probability that a trigger has been decoded. Before/after risk is
priced at the **same preceding snapshot** and isolates the matched replacement;
other simultaneous orders are omitted from that counterfactual. Associations
are inferred, with {int(expiry['ambiguous_pairs'])} ambiguous expiry pairs.
Trade candles and low premiums limit Greek precision.

The timing search tests held-long premium/cost ratios, premium/ATM ratios,
Delta, distance, spot moves, IV and book risk. It includes
{state['deep_hedge_timing_summary.json']['positive_contract_minutes']} positive contract-minutes;
{state['deep_hedge_timing_summary.json']['excluded_contract_minutes']} observed target contract-minutes
lack a valid held-long/preceding-price/guide representation and remain excluded,
not no-action labels. Timing rules fail to generalize.

![SENSEX spot and hedge prices](outputs/deep_case_sensex_hedge_refresh.png)

Routine hedge-strike selection remains approximated by the prior 2.5%-of-ATM-leg
premium budget, with index/phase rounding and an incomplete historical chain.
The existing within-one-strike match is not exact strike recovery. Frequent
hedge purchases and true replacements are separate mechanisms.

## 4. Size and maximum exposure

All window definitions now predict the **same** T−2-second to T+180-second filled
quantity target. This prevents a narrow two-second window full of zeros from
creating misleading 80–90% sizing accuracy. On earlier-positive timer slots:

{table(sz)}

The shared normalized clock template remains useful but cannot explain all
orders or the maximum-exposure controller. Actual per-cycle/per-role peaks are
exported in `deep_exposure_peaks.csv`; base units of 65/20 are descriptive units,
not asserted exchange lot sizes. Observed maxima are not configured caps.
Hedge purchases, different strikes, partial fills and late overlays make gross
quantity an inadequate risk or capital measure. Premium receipts are not margin.
There is no broker margin/capital-allocation ledger in this export.

One exceptional NIFTY 16 October sequence adds 7,800 long 24000 calls and 15,600
short 24500 calls in three observed 1:2 groups, followed by other closer-call
purchases. It illustrates why not every new short is a fresh ATM straddle and
why a gross peak cannot be interpreted as the normal allocation limit. This
is one cycle, not a recovered general overlay rule or proof of its purpose.

## 5. Do the selected exits improve economics?

Freeze earlier-selected global completed-close/FIFO stops and compare them with
the time exit. Both arms share recorded short entries and unambiguous inferred
equal-quantity outward hedges. Stops execute one further minute later at candle
open; a preplanned time exit uses its clock open. The following common subset
has nonzero endpoint volume and checked vertical-spread price bounds:

{table(es)}

Candidate minus clock differences improve the aggregate, but weekly confidence
intervals include zero for both indices and pooled results. Only 8/15 pooled
cycles improve, and pooled candidate net remains negative. Higher cost stress
does not change that limitation. This is conditional component attribution,
**not actual Algo 8 P&L, autonomous entry alpha or equal dynamic/margin risk**.
Observed entries, incomplete quote paths and inferred links limit interpretation;
the quality screen checks endpoints, not every trigger candle or capacity.

The strongest working profit-engine hypothesis remains protected near-expiry
volatility carry, with timed allocation and separate management. We have not
established that a range indicator predicts entry or that the expanded controls
reproduce the original alpha. The separate autonomous NIFTY carry approximation
in `ALPHA_CANDIDATE_FINDINGS.md` remains a hypothesis, not a complete replica.

## Detailed event decisions and reproduction

`deep_event_market_casebook.csv.gz` contains every reconstructed parent order,
its role/quantity/fill price, preceding spot moves, option premium changes,
ATM IV and available book/side Greeks. Missing context is not replaced with
zero. `deep_order_label_fill_lags.csv` highlights order-label/execution delays;
filled-order logs do not identify all pending orders or cancellations.

Reproduce in order: `deep_event_audit.py`, `deep_controller_search.py`,
`deep_extra_search.py`, `deep_hedge_refresh.py`, `deep_hedge_timing.py`,
`deep_size_windows.py`, `deep_allocation_stops.py`,
`deep_controller_economics.py`, `plot_deep_controller_cases.py`, then
`summarize_deep_controller_study.py`, all under `research/`.
Install dependencies with `python -m pip install -r research/requirements-deep-controller.txt`.
The focused and existing suite passed **165 tests**, including packed-rule
scoring, interleaved-contract crossings, gap handling, first touches and exclusion
of later targets from earlier stop selection. Output checks reconcile all 39,874
parent IDs and verify unique inferred hedge pairs and explicit target coverage.

### State-program event metrics

Exact-minute precision/recall and one-to-one ±2-minute precision/recall are
distinct. A high precision on a tiny subset is not broad controller recovery.

{table(notes)}
'''
    (ROOT/'research/DEEP_CONTROLLER_FINDINGS.md').write_text(text)


if __name__=='__main__':main()
