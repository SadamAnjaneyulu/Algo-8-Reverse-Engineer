"""Evidence-backed report for policy/execution separation; no new model selection."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from model_runner import HERE,ROOT,PRIOR,policies,mechanics


def percent(x):return 'unavailable' if pd.isna(x) else f'{100*x:.1f}%'
def table(rows):
    if not rows:return 'No usable observations.'
    keys=list(rows[0]);return '\n'.join(['| '+' | '.join(keys)+' |','| '+' | '.join('---' for _ in keys)+' |']+['| '+' | '.join(str(r[k]).replace('|',' / ').replace('\n',' ') for k in keys)+' |' for r in rows])


def main():
    config=yaml.safe_load((HERE/'selected_model_config.yaml').read_text());selected=config['selected_model'];best=selected['model_id'];pid=selected['policy_id'];base=pid*7
    summary=pd.read_csv(HERE/'policy_vs_execution_comparison.csv');summary=summary[summary.policy_id.eq(pid)]
    forensic=json.loads((HERE/'forensic_manifest.json').read_text());ledger=pd.read_csv(HERE/'reversal_motif_ledger.csv');hyp=pd.read_csv(HERE/'reversal_hypothesis_summary.csv')
    controls=pd.read_csv(HERE/'quantity_equality_controls.csv');matched=pd.read_csv(HERE/'matched_nonreversal_controls.csv');unc=pd.read_csv(HERE/'paired_cycle_uncertainty.csv')
    components=pd.read_csv(HERE/'component_cycle_scores.csv.gz');coverage=pd.read_csv(HERE/'reversal_pattern_coverage.csv');opening=pd.read_csv(HERE/'opening_vs_prior_contradiction.csv')
    opening_detail=pd.read_csv(HERE/'opening_initialisation_scores.csv');initial=opening[opening.model.eq(str(best))].iloc[0]
    allocations=pd.read_csv(HERE/'recurring_allocation_scores.csv');exits=pd.read_csv(HERE/'intermediate_exit_scores.csv');raw=pd.read_csv(HERE/'closed_loop_cycle_scores.csv.gz')
    frozen=pd.read_csv(HERE/'frozen_targets_cycle_scores.csv.gz');equiv=pd.read_csv(HERE/'observable_equivalence.csv');seed=pd.read_csv(HERE/'seed_geometry_and_quote_audit.csv');audit=pd.read_csv(HERE/'detailed_request_audit.csv.gz')
    late=summary[summary.split.eq(2)&summary.model_id.eq(best)].iloc[0]
    later_cases=components[components.model_id.eq(base)&components.split.eq(2)&components.scope.eq('full')&components.initialization_known]
    seed_both=seed.groupby('cycle_id').intent_within_two_grids.all().sum()
    counts=[]
    for hypothesis,g in hyp.groupby('hypothesis',sort=True):
        for variant,q in g.groupby('variant',sort=True):
            counts.append(dict(Hypothesis=hypothesis,Variant=variant,Compatible=int(q[q.status.eq('compatible')].motifs.sum()),Contradicted_variant=int(q[q.status.eq('contradicted_variant')].motifs.sum()),Unresolved=int(q[q.status.eq('unresolved')].motifs.sum())))
    control_rows=[]
    for size in ['all','one_base','multiple_base']:
        for name in ['fixed_motifs','strict_nonreversal_controls']:
            r=controls[controls.bounded_peak.eq(True)&controls['size'].eq(size)&controls.cohort.eq(name)].iloc[0]
            control_rows.append(dict(Size=size,Cohort=name,N=int(r.cases),Cycles=int(r.cycles),Equal=int(r.equal),Rate=percent(r.rate)))
    ci=pd.read_csv(HERE/'control_cycle_uncertainty.csv');cr=ci[ci.bounded_peak.eq(True)&ci.multiple_base_only.eq(False)].iloc[0];cm=ci[ci.bounded_peak.eq(True)&ci.multiple_base_only.eq(True)].iloc[0]
    repeats=int(ledger.repeat_requested_quantity_atomic.sum());partials=int(ledger.parent_partial_fill_present.sum());same_label=int(ledger.same_order_label_minute.sum());same_price=int(ledger.repeated_request_quantity_and_limit_candidate.sum())
    opening_rows=[]
    for name in ['prior selected13845','prior13845 child-second re-audit',str(base),str(base+1),str(base+4),str(base+5),str(base+6)]:
        r=opening[opening.model.eq(name)].iloc[0];opening_rows.append(dict(Model=name,N=int(r.sessions),Both_first_wings=int(r.both_first_wings_exact),Both_short_gross_quantities=int(r.both_short_gross_exact),All_four_net_at0917='unavailable' if pd.isna(r.four_role_net_exact) else int(r.four_role_net_exact)))
    rows=[]
    for split,label in [(0,'Fit Jun-Jul'),(1,'Internal Aug'),(2,'Inspected Sep-Oct')]:
        for r in summary[summary.split.eq(split)].itertuples():rows.append(dict(Period=label,Model=r.model_id,Mechanics=r.mechanics,Cycles=r.cycles,Event_F1=percent(r.event_macro_f1),Quantity=percent(r.quantity_score),Inventory=percent(r.inventory_score),Final=percent(r.final_score),Penalized_score=f'{r.penalized_score:.4f}'))
    motif_rows=[dict(Model=r.model_id,Predicted_motifs=r.predicted_motifs,Matched_of59=r.matched_contract_time,False_motifs=r.false_motifs,Precision=percent(r.precision),Recall=percent(r.recall)) for r in coverage[coverage.model_id.between(base,base+6)].itertuples()]
    masked_rows=[]
    for model in range(base,base+7):
        q=components[components.model_id.eq(model)&components.split.eq(2)&components.initialization_known]
        full=q[q.scope.eq('full')];clean=q[q.scope.eq('non_motif')];halo=q[q.scope.eq('non_motif_halo')]
        r=unc[unc.model_id.eq(model)&unc.split.eq(2)&unc.scope.eq('non_motif')&unc.metric.eq('event_macro_f1')]
        masked_rows.append(dict(Model=model,Full_F1=percent(full.event_macro_f1.mean()),Outside_motifs_F1=percent(clean.event_macro_f1.mean()),Outside_halo_F1=percent(halo.event_macro_f1.mean()),Change_vs_safe='reference' if not len(r) else f'{100*r.iloc[0].mean_difference:+.2f} pp',Cycle95='reference' if not len(r) else f'[{100*r.iloc[0].low95:+.2f}, {100*r.iloc[0].high95:+.2f}] pp'))
    frozen_rows=[]
    for model,g in frozen[frozen.phase.eq(2)&frozen.split.eq(2)&frozen.initialization_known].groupby('model_id'):
        frozen_rows.append(dict(Model=model,Cycles=len(g),Event_F1=percent(g.event_macro_f1.mean()),Quantity=percent(g.quantity_score.mean()),Inventory=percent(g.inventory_score.mean()),Final=percent(g.final_score.mean())))
    exit_rows=[]
    for model in [base,base+2,base+4,base+5]:
        q=exits[exits.model_id.eq(model)&exits.split.eq(2)&exits.initialization_known]
        for index,g in q.groupby('index'):
            p,a,m=g.predicted.sum(),g.observed.sum(),g.matched.sum();exit_rows.append(dict(Model=model,Index=index,Predicted=int(p),Observed=int(a),Matched=int(m),Precision=percent(m/p if p else np.nan),Recall=percent(m/a if a else np.nan)))
    alloc_rows=[]
    for model,g in allocations[allocations.split.eq('later')].groupby('model_id'):
        alloc_rows.append(dict(Model=model,Windows=len(g),Cycles=g.cycle_id.nunique(),Exact_short_pair=percent(g.short_pair_exact.mean()),Exact_four_roles=percent(g.four_roles_exact.mean()),Mean_abs_error_units=f'{g.absolute_error_base_units.mean():.2f}'))
    examples=[]
    ids=['M01','M03']+[ledger[~ledger.atomic_quantity_equal].motif_id.iloc[0]]
    for r in ledger[ledger.motif_id.isin(ids)].itertuples():examples.append(dict(Motif=r.motif_id,Contract=f'{r.underlying} {r.expiry_date} {r.strike}{r.option_type}',Close=r.first_close_to_zero_ist[11:19],Old_q=int(r.prior_atomic_quantity),Opposite_q=int(r.opposite_quantity),Zero_again=r.neutralized_ist[11:19],Same_grouped_parent=r.same_parent_at_boundary,Partial_parent_present=r.parent_partial_fill_present))
    systems=[]
    full=pd.read_csv(HERE/'policy_vs_execution_comparison.csv');aug=full[full.split.eq(1)].sort_values(['penalized_score','complexity','model_id'],ascending=[False,True,True])
    for system,g in aug.groupby('system',sort=True):
        r=g.iloc[0];l=full[full.model_id.eq(r.model_id)&full.split.eq(2)].iloc[0]
        systems.append(dict(System=system,August_selected=int(r.model_id),Complexity=int(r.complexity),August_score=f'{r.penalized_score:.4f}',Later_F1=percent(l.event_macro_f1),Later_score=f'{l.penalized_score:.4f}'))
    sub=[]
    for model,g in audit.groupby('model_id'):
        sub.append(dict(Model=model,Target_error_base_unit_seconds=int(g.target_error_base_unit_seconds.sum()),Zero_target_contract_seconds=int(g.zero_target_contract_seconds.sum()),Scope='35 received cycles; latent-target deviation, not original target error'))
    granularity=pd.read_csv(HERE/'parent_order_granularity.csv');granularity_rows=[dict(Model=r.model,Index=r.index,Parents=r.new_short_parents,One_base=r.single_base_requests,Rate=percent(r.single_base_rate)) for r in granularity[granularity.phase.eq('preexpiry')&granularity.model.isin(['observed',str(base),str(base+1)])].itertuples()]
    localisation=pd.read_csv(HERE/'case_policy_execution_localisation.csv').classification.value_counts().to_dict();local_rows=[dict(Comparison=k,Cases=v) for k,v in localisation.items()]
    context=pd.read_csv(HERE/'closure_context_controls.csv');context_rows=[dict(Context=r.context,Aged_closures=r.aged_closures,Fixed_motifs=r.motifs,Reopenings10=r.reopenings10) for r in context.itertuples()]
    own=opening_detail[opening_detail.model_id.eq(best)];delayed=own[own.documented_delayed_exception];ordinary=own[~own.documented_delayed_exception]
    nonstandard=[]
    for r in own.itertuples():
        unit=65 if r.index=='NIFTY' else 20
        if not r.documented_delayed_exception and any(getattr(r,'act_'+right+'_'+role+'_net0917')!=3*unit for right in ['CE','PE'] for role in ['short','long']):nonstandard.append(r.entry_date)
    original_targets=pd.read_csv(PRIOR/'outputs/initial_entry_reconstruction.csv');tiecols=[k for k in own if k.endswith('_tied_strikes')];ties=int(own[tiecols].gt(1).any(axis=1).sum())
    text=f'''# Algo8 — latent trading policy versus order management

**The reversals look compatible with cleanup/reconciliation mechanics, but the
mechanism and its activation are not identified. Separating the layers does not
materially improve broad reconstruction in the tested family.** The selected
model is **{best}**, a pooled-clock policy with a pooled-contract premium50% stop
and safe execution. Later event macro F1 is **{percent(late.event_macro_f1)}** on
**14 pre-initialised cycles**, far below80–90%. These later records were already
inspected in previous work; there is no researcher-blind external validation.

## Six direct answers

1. **Deliberate reversals or order management?** Within the immutable59 cases,
   49 have an opposite quantity equal to the final atomic close, all59 use a
   different received parent at that boundary, and27 involve a parent with multiple received child fills.
   This supports investigating repeated/stale close requests or zero-target
   correction. It does not confirm duplicates. An intentional fast round trip
   remains observationally possible, and the strict matched-control sample has
   only{forensic['matched_case_count']} case with{forensic['matched_controls']} control.
2. **Does separation improve later reconstruction?** No material overall gain
   over the same policy with safe execution. Sequential execution and pending-
   aware reconciliation give the same later event F1 at the minute level.
   Delayed variants add about1pp F1 outside motifs, but worsen final liquidation
   and the registered composite. The universal duplicate variant generates
   {int(coverage[coverage.model_id.eq(base+4)].predicted_motifs.iloc[0])} motifs and
   matches0/59 original cases by exact contract within two minutes.
3. **What is identifiable?** Executed quantities, child fragmentation, received
   parent references, atomic book transitions and relative recorded times.
   Original targets, submissions, cancellations, acknowledgement latency and
   whether a repeated payload was intentional are not observed. Some models
   share identical minute action paths despite different subminute execution.
4. **Better intermediate exits without weaker opening?** Opening short quantity
   reconstruction improves from the earlier0/32 benchmark to
   **{int(initial.both_short_gross_exact)}/32**; true first-wing strike pairs improve
   to **{int(initial.both_first_wings_exact)}/32**. All-four-role09:17 net matching is
   only **{int(initial.four_role_net_exact)}/32**. The regular execution variants
   preserve those opening metrics, but do not recover the original exit trigger.
   The overactive stale-state variant breaks opening quantities and is rejected
   by both fit and complexity. Intermediate and final exit results remain separate.
5. **Simplest captured behaviour?** Fixed three-base opening intent, separate
   seed geometry, scheduled pooled-clock accumulation, independent side reductions
   and a dated liquidation deadline, with safe target-bounded execution. This is
   the simplest scored approximation here. Its50% stop,15:10/15:20 carry guard
   and literal seed points are hypotheses, not recovered original instructions.
6. **What remains unresolved?** The latent risk/exit activation, exact seed
   selection, extra allocations/re-entry, allocation ownership, stop reset/scope,
   original pending queue, and causes of the59 overshoots. Submission/cancel/ack
   logs, decision IDs, tick bid/ask, complete-chain data and missing prior
   initialization records would discriminate these explanations.

## Architecture and fixed experiment

```mermaid
flowchart LR
    M[Completed market candles] --> P[Trading policy]
    P --> T[Desired contracts and quantities]
    T --> E[Execution mechanics and pending requests]
    E --> F[Simulated fills, inventory and cash]
    F -->|own confirmed state| P
    Q[Market proxy at fill time] --> E
    H[Audited historical fills and book] -. comparison only .-> S[Scores and mismatches]
    F --> S
```

[Registered plan](REGISTERED_PLAN.md), [measurement audit](MEASUREMENT_NOTES.md).
The experiment contains **12 policies ×7 mechanics =84 models**, without another
indicator bank. Policies compare fixed increments, pooled clock increments,
cumulative targets and capped target restoration, crossed with deadline-only,
premium50 and side-equity100k episode management. All use the same frozen
opening module. Older targets survive additions unless an explicit reduction
changes them. Actual historical inventory/actions never enter a simulated policy.

The seven mechanisms specify base fragmentation, delays, pending persistence,
cancellation acknowledgement, one stale close copy, pending-aware reconciliation
and a deliberately overactive stale/ignore-pending control. Parameters are
explicit in [execution definitions](execution_mechanics_candidates.csv).
The last mechanism is a negative control, not a credible recovered controller.
The selected policy is also replayed with **the same frozen safe-generated target
stream** under every mechanic, separating execution effects from policy feedback.
Those targets are simulated hypotheses, not inferred original decisions.

Quantity/cash accounting and minute scoring reuse the existing reconciled replay
implementation. Primary weights remain.40 event F1,.20 quantity,.30 inventory,
.10 resolved final closure, minus.002 per complexity point. Exact contract/action
matches are one-to-one within±2minutes. Quantity and inventory scores are normalized
overlap measures, not percentages of entirely correct orders/books. P&L does not
select the model. Calendars are conditional on received sessions. Fit quantities
use June–July, August selects, September–October is an already-inspected check.

The quote universe remains the historically traded-contract subset. That is
not independent full-chain eligibility. All comparisons share this restriction
and use only preceding market prices; missing geometric seed contracts have no
fabricated quotes or fills.

All35 cycles are simulated. The3 received expiry-only starts lack prior
initialization and are retained in full outputs, but the same32 pre-initialised
cycles determine selection for every model:11 fit,7 August,14 later. The delayed
NIFTY5October start is retained as an explicit contradiction, without a date-coded
policy exception. Nonstandard observed opening sizes are also separate.

## Forensics: all59 original motifs

The source cohort hash and all source row IDs are preserved in
[forensic manifest](forensic_manifest.json) and
[59-case ledger](reversal_motif_ledger.csv). Its views include:

- [second-by-second net states](reversal_second_timelines.csv.gz);
- [child fills, requested sizes and raw export references](reversal_child_fills.csv.gz);
- [same-contract, same-right and opposite-right activity through15minutes](reversal_neighbor_activity.csv.gz);
- preceding/following minute spot and option marks, subsequent received inventory,
  next activity times and round-trip cashflows in the case ledger.

Recorded seconds are corroborated to export minutes, not independently certified
exchange timestamps. Post-event market changes are descriptive only. A carried
ledger quantity after the last received fill is not independent broker-position
confirmation. No tick price, intent or cancellation is invented.

The quantities are **49 equal,10 below,0 above** the final atomic closed amount.
Zero above is imposed by the original conservative size restriction; it is not
independent evidence that over-sized reversals cannot occur. Equality against
the entire monotone closing burst is **48/59**. Only6 atomic closes are one base;
53 are multi-unit. **{repeats}/59** have a repeated requested parent size at the
close/open boundary, and **{same_label}/59** share at least one export order-label
minute. **{same_price}/59** also repeat a requested-size / candidate-limit-price pair
across distinct references. The limit field is inferred from price bounds, not
an exporter-confirmed order-type schema. Repeated size/price/minute does not
establish duplicated intent. Encoded export-tag categories remain uninterpreted.

Every opposite opening uses a different grouped parent than the final close:
**0/59** share that parent. Thus a *single parent merely filling across zero*
is contradicted under the received grouping convention. Nevertheless **27/59**
involve a parent with multiple received children somewhere in the sequence: partial execution
can coexist with a second close request or reconciliation.

{table(examples)}

For example, M03's opposite-order request is1170 units, with child fills260 and
910. The1170 requested field repeats on its children; adding those request fields
would falsely count2340. Incremental quantities sum to1170. Distinct parent
references still separate the earlier close from that opposite request.

### Competing hypotheses are nonexclusive

{table(counts)}

[Per-case compatibility/contradiction ledger](reversal_hypothesis_scores.csv).
These are necessary observable implications of named variants, not probabilities
or exclusive cause labels. A persistent five-minute reversal fails all59 cases;
a fast intentional round trip is not ruled out. Return to zero within60seconds
is part of case selection, so it cannot independently prove zero-target intent.
The within5second variant fits38/59. The paired-short/clock-label variant tests
a different possible allocation context without requiring five-minute position
persistence. The strict protective-rotation variant's short exclusion can also
exclude an execution overshoot; it does not rule out a mixed hedging purpose.
All59 remain unresolved as unique causes.

### Is quantity equality unusual?

There are **2244** aged same-contract closes to zero; only **93** have another
nonzero same-contract event within10seconds. The others are not counted as
unequal reopenings. A non-motif event can itself be a reversal; strict negative
controls below reopen in the *original* direction. Both case and control rows
receive the same peak-size restriction for this comparison.

{table(control_rows)}

One-base equality is forced when positive quantities are integral base units and
reopening cannot exceed the old one-base quantity. The unadjusted all-size
case/control rate difference is{100*cr.difference:+.1f}pp, with cycle bootstrap
95% interval[{100*cr.low95:+.1f},{100*cr.high95:+.1f}]pp. For multi-unit cases the
contrast is{100*cm.difference:+.1f}pp
[{100*cm.low95:+.1f},{100*cm.high95:+.1f}]pp, but only7 strict controls contribute.
These intervals do not correct selection or poor state overlap.

Exact index/cycle/phase/old-role/closed-size matching without replacement yields
**one case and one control**, separated by about109minutes. There is no adequate
matched sample for a causal unusual-equality conclusion. The result is a
mechanics lead, not an83%-decoded trigger.
Sources: [all closure opportunities](all_closure_controls.csv),
[all/strict control counts](quantity_equality_controls.csv),
[matched controls](matched_nonreversal_controls.csv),
[cycle uncertainty](control_cycle_uncertainty.csv).

## Opening is scored independently

{table(opening_rows)}

The old0/32 benchmark is preserved and a raw-child-second re-audit also gives0/32.
A provisional new9/32 wing count was invalid because minute aggregation sorted
strikes rather than executions. Corrected actual first-fill order uses event
seconds then source row; **{ties}** starts have multiple strikes tied in at least
one first-event second and retain that flag. This measurement correction changes
neither primary minute scores nor selected rules.

The common ordinary sample has31 starts;5October is the delayed exception.
The fixed policy has no hindsight date override. Observed nonstandard ordinary
opening-size dates are{', '.join(sorted(set(nonstandard)))}. The literal intended
seed geometry lies within two grids of both observed wings on **{int(seed_both)}/32**
starts; this is compatibility with prior geometry, not an exact executable rule.
Missing stored seed contracts/quotes remain unfilled. The exact strike reference
and complete option universe are still unresolved.
Sources: [per-start scores and exceptions](opening_initialisation_scores.csv),
[intended geometry versus quote availability](seed_geometry_and_quote_audit.csv),
[prior benchmark and re-audit](opening_vs_prior_contradiction.csv).

## Full policy/execution comparison

August selection by system, on the identical cycle cohort:

{table(systems)}

Same selected policy, all mechanics:

{table(rows)}

### Parent orders and child fills are different

{table(granularity_rows)}

[Parent-request diagnostic](parent_order_granularity.csv). Fragmented expansion
submits one base per parent; delayed partial execution can instead fill one
larger parent in base-sized slices. These are distinct hypotheses. Minute actions
are unchanged by this request partition, so the primary score cannot identify
it. The received requested-size fields support unit fragmentation for routine
pre-expiry short entries, while neither the number of allocation units nor the
exact subsecond leg delays is recovered. The simple safe model is the aggregate
score baseline; it is not a recovered submission engine.

The50% stop is a pooled-contract rule: it is not identified allocation ownership
or a proven original stop. Capital100k episode management and target restoration
are tested alternatives. No result recovers the supplied4%/1% implementation.
The declared delays/expiry assumptions can themselves worsen final fills; that
rejects these configurations, not every possible order-management process.
Full [84-model comparison](policy_vs_execution_comparison.csv),
[policies](desired_inventory_candidates.csv), [selected configuration](selected_model_config.yaml).

### Outside the59 selected sequences

The primary exclusion removes each affected contract-minute overlapping
close−5seconds through neutralisation+5seconds. A second exclusion adds a
±2minute matching halo. Both observed and predicted actions and inventory cells
use the same fixed masks; no historical mask informs a candidate decision.

{table(masked_rows)}

Later comparisons have14 cycles, bootstrapped by whole cycle. Delayed execution
can improve action F1 outside the selected motifs while degrading liquidation;
this partial improvement is not hidden, but does not produce a better complete
controller. [Paired cycle contrasts](paired_cycle_uncertainty.csv).

### Frozen desired targets: isolate execution

{table(frozen_rows)}

These seven replays receive identical safe-generated target streams. Changes
are therefore execution effects under that hypothetical policy, without feeding
observed original targets to the model. [Frozen goals](frozen_targets_goals.csv.gz),
[frozen-target cycle scores](frozen_targets_cycle_scores.csv.gz).

### Later allocations and intermediate exits

Exact17-window pre-expiry quantities, using child seconds and the same
T−2second to T+180second target as the original analysis:

{table(alloc_rows)}

The overactive control retains complete aggregate actions but no exact child-window
size metric. Its extra events still count against the main reconstruction score.
[Allocation detail](recurring_allocation_scores.csv).

Intermediate covers before15:00, both rights pooled within each index:

{table(exit_rows)}

[Right/cycle exit detail](intermediate_exit_scores.csv). The first reduction,
final short-book closure and remaining protection are distinct targets.

## Reversal prediction and intraminute inventory

{table(motif_rows)}

At the recorded first-close times, compare the selected model's own held
contract and desired target to the observed transition. This is a diagnostic,
not an assumption that the original target was zero:

{table(local_rows)}

[Case-level localisation](case_policy_execution_localisation.csv). An absent
model contract points to entry/strike/sizing discrepancies; a retained model
target points to a different decision path if the original intended to flatten.
A zero model target with residual simulated inventory points to execution/data
availability. Original intent remains latent in all three categories.

Observed aged closes by time context:

{table(context_rows)}

[Context controls](closure_context_controls.csv). Time buckets are observable
proxies, not labels for risk or deadline intent. They test a universal
close-copy explanation without inventing original triggers.

The full-copy variant generates the expected flat/opposite/flat *shape* at its
own hypothesized liquidations, but does not predict any of the original59
contract/time sequences. Its559 false motifs are retained as negative evidence.
The real activation gate is still missing. A conditional stale-close explanation
at observed timestamps is not an autonomous reconstruction.
[Coverage](reversal_pattern_coverage.csv), [all simulated closure opportunities](closed_loop_closures.csv.gz).

Some mechanics restore the same inventory before each minute ends, so minute
inventory scores cannot capture their temporary exposure. The detailed trace
therefore integrates absolute quantity distance from the **simulated desired
target**, in base-unit-seconds, and time holding a contract whose target is zero.
These are not comparisons to unobserved original targets. Missing/unfilled seed
quotes also contribute, including for safe execution.

{table(sub)}

[Conservation and transient audit](detailed_request_audit.csv.gz),
[child fills](detailed_fills.csv.gz), [latent requests](detailed_requests.csv.gz).
These are simulated events, not fabricated historical submissions.

## Identifiability and discriminating evidence

[Observable equivalence](observable_equivalence.csv) compares full minute action
traces, not just equal scores. [Discriminating events](candidate_discriminating_events.csv)
gives timestamp, instrument, quantity, each model's action and nearby original
source/parent references. Sequential variants can share minute actions while
assigning different seconds. For example, the tested two-second per-leg staggering is not inferred from
minute agreement; the observed ordinary CE/PE first shorts are within one second
in31/31 starts. Original relative fill ordering is observable;
submission times, queues and acknowledgement/cancellation ordering are absent.

Two policy modules emitting overlapping closes can also look like one policy
instruction copied inside the OMS. Filled-order references do not locate that
duplication at a particular software layer.

A zero target plus stale pending close and correction can produce the same
received inventory pattern as a deliberate brief opposite target followed by
zero. Post-hoc latent choices can explain either; they are not predictive fit.
The observed filled-order references and market minute bars cannot uniquely
choose between such intent hypotheses. The tested universal full-copy process
is contradicted by non-motif opportunities. A more selective duplicate or
reconciliation process remains possible but its actual trigger is not identified.

## Reproduction, tests and remaining conclusion

[README](README.md) contains commands. **217 repository tests pass**: prior201
plus16 tests for the separated engine and forensic measurement. Tests cover
atomic chronology, first-child ordering, opening constraints, independent desired
state, duplicate and delayed fills, cancellation, pending reconciliation,
quantity/cash accounting, future-state independence and deterministic replay.
They establish software behavior, not original-policy truth.

The existing canonical accounting remains the reference. All84×35 model-cycle
request audits conserve requested = executed + cancelled + failed + remaining.
A cold-cache rebuild exactly reproduces the original canonical binary while
preserving checked committed prior outputs. A saved-configuration replay is
verified against the selected detailed trace. See [validation audit](validation_audit.json).

Complete scores, goals and closure audits cover all84 definitions. The August-
selected trace cohort has complete minute actions and a mismatch ledger; detailed
child records cover six regular mechanics of the selected policy. The overactive
negative control keeps all coarse actions and reversals, without its repetitive
multi-gigabyte child dump. All definitions remain reproducible.

**Best-supported behaviour:** timed accumulation with distinct opening/routine
protection and separate risk management. Some rapid opposite openings are
consistent with execution cleanup and should not automatically be called new
intentional allocations.

**Competing explanations:** stale/duplicate close requests, target reconciliation,
multiple pending/partial requests, and deliberate very brief rotations remain
partly observationally equivalent. These are not exclusive posterior labels.

**Unresolved:** original exit activation, exact seed choice, allocation sizing,
re-entry/reset, maximum exposure and queue rules. The separation is useful for
identifying those gaps; it does not recover an80–90% controller or proven alpha.
'''
    replacements={'Algo8':'Algo 8','below80':'below 80','only7':'only 7','only6':'only 6','all59':'all 59','all35':'all 35','All35':'All 35','all84':'all 84','All84':'All 84','of59':'of 59','of32':'of 32','the59':'the 59','the3 ':'the 3 ','same32':'same 32','with31':'with 31','has31':'has 31','in31/31':'in 31/31','NIFTY5October':'NIFTY 5 October','are49':'are 49','equal,10':'equal, 10','below,0':'below, 0','are38/59':'are 38/59','the50%':'the 50%','The50%':'The 50%','before15:00':'before 15:00','within10seconds':'within 10 seconds','within60seconds':'within 60 seconds','within5second':'within 5 second','only14':'only 14','only1 ':'only 1 ','with1 ':'with 1 ','and27':'and 27','into1170':'into 1170','is1170':'is 1170','fills260':'fills 260','and910':'and 910','those1170':'those 1170','count2340':'count 2340','sum to1170':'sum to 1170','within±2minutes':'within ±2 minutes','below80–90%':'below 80–90%','contains **12 policies ×7 mechanics':'contains **12 policies × 7 mechanics','has14 cycles':'has 14 cycles','given0/32':'given 0/32','from the earlier0/32':'from the earlier 0/32','old0/32':'old 0/32','new9/32':'new 9/32','to1170':'to 1170','complete17-window':'complete 17-window','Exact17-window':'Exact 17-window','12models':'12 models','within two minutes':'within two minutes'}
    for old,new in replacements.items():text=text.replace(old,new)
    (HERE/'POLICY_EXECUTION_RECONSTRUCTION.md').write_text(text)
    print('Wrote policy/execution report; selected',best,'later F1',late.event_macro_f1)

if __name__=='__main__':main()
