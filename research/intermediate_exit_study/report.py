"""Evidence-linked concise account of the registered intermediate-exit study."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from build import HERE

def table(d,cols=None,decimals=3):
    d=d[cols].copy() if cols else d.copy()
    def fmt(v):
        if pd.isna(v):return '—'
        if isinstance(v,(float,np.floating)):return str(int(v)) if v.is_integer() else f'{v:.{decimals}f}'
        return str(v).replace('|','/')
    return '| '+' | '.join(d.columns)+' |\n| '+' | '.join(['---']*len(d.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(v) for v in r)+' |' for r in d.itertuples(index=False,name=None))

def run():
    e=pd.read_csv(HERE/'exit_case_ledger.csv.gz');atoms=pd.read_csv(HERE/'short_cover_atoms.csv.gz');up=pd.read_csv(HERE/'upstream_32_27_audit.csv')
    rank=pd.read_csv(HERE/'ranked_trigger_hypotheses.csv');scores=pd.read_csv(HERE/'cycle_validation_scores.csv');folds=pd.read_csv(HERE/'validation_folds.csv')
    summary=json.loads((HERE/'evaluation_summary.json').read_text());controls=json.loads((HERE/'control_selection_summary.json').read_text());manifest=json.loads((HERE/'input_manifest.json').read_text())
    chrono=rank[(rank['mode']=='expanding_chronological')&(rank.tolerance_seconds==120)].copy().sort_values('macro_cycle_f1',ascending=False)
    loco=rank[(rank['mode']=='leave_one_cycle_out')&(rank.tolerance_seconds==120)].copy().sort_values('macro_cycle_f1',ascending=False)
    for d in [chrono,loco]:
        for field in ['precision','recall','f1','macro_cycle_f1','event_feature_coverage']:d[field]=d[field]*100
    diag=pd.read_csv(HERE/'motif_27_pre_event_condition_audit.csv');retained=diag[(diag.classification=='target_retained_at_recorded_flat')&(diag.observed_role=='short_exposure')].copy()
    retained['short_prior_units']=-retained.observed_prior_quantity/retained['index'].map({'NIFTY':65,'SENSEX':20})
    counts=e.groupby(['known_initialization','outcome_stratum']).size().reset_index(name='episodes')
    absent=up[up.classification=='model_contract_absent'].groupby(['observed_role','upstream_class']).size().reset_index(name='cases')
    cov=pd.read_csv(HERE/'feature_coverage_by_cycle.csv');known=e[e.known_initialization].cycle_id.unique();cv=cov[cov.cycle_id.isin(known)].groupby('hypothesis')[['events','events_feature_available','event_condition_satisfied']].sum().reset_index()
    cv['coverage_pct']=100*cv.events_feature_available/cv.events;cv['condition_at_event_pct']=100*cv.event_condition_satisfied/cv.events
    ctx=pd.read_csv(HERE/'matched_feature_contrasts.csv');cc=pd.read_csv(HERE/'matched_condition_contrasts.csv')
    # Attach the conservative short motif's terminal close to its reduction
    # episode. A full flat time is often later than first reduction time.
    lookup=atoms.set_index(['cycle_id','strike','option_type','second'])
    links=[]
    for r in up[up.observed_role=='short_exposure'].itertuples():
        t=int(pd.Timestamp(r.observed_close_ist).timestamp());a=lookup.loc[(r.cycle_id,r.strike,r.right,t)]
        if isinstance(a,pd.DataFrame):a=a.iloc[0]
        event=e[e.event_id==a.event_id].iloc[0]
        links.append(dict(motif_id=r.motif_id,classification=r.classification,event_id=a.event_id,first_reduction_ist=event.timestamp_ist,
            terminal_close_ist=r.observed_close_ist,first_to_terminal_seconds=t-event.second,full_close_is_first_reduction=t==event.second))
    links=pd.DataFrame(links);links.to_csv(HERE/'short_motif_episode_links.csv',index=False)
    condition_table=cc[cc.tier=='same_contract'].copy();condition_table['case_rate_pct']=100*condition_table.case_satisfied/condition_table.case_available
    condition_table['control_rate_pct']=100*condition_table.control_satisfied/condition_table.control_available
    # Named counterexamples chosen deterministically, not as favorable anecdotes.
    failures=pd.read_csv(HERE/'trigger_counterexamples.csv.gz');examples=[]
    for name in ['premium_loss50','adverse_spot5_quarterpct','side_drawdown_halfpct']:
        for kind in ['missed_exit','false_signal']:
            g=failures[(failures.hypothesis==name)&(failures.kind==kind)].sort_values(['cycle_id','second'])
            if len(g):
                r=g.iloc[0];examples.append(dict(hypothesis=name,kind=kind,cycle_id=r.cycle_id,strike=r.strike,right=r.option_type,
                    timestamp_ist=pd.Timestamp(r.second,unit='s',tz='UTC').tz_convert('Asia/Kolkata').isoformat(),event_id=r.event_id))
    examples=pd.DataFrame(examples);examples.to_csv(HERE/'representative_counterexamples.csv',index=False)
    strata=pd.read_csv(HERE/'index_side_phase_scores.csv');ss=strata[strata['mode']=='expanding_chronological'].groupby(['hypothesis','underlying','option_type']).agg(
        cycles=('cycle_id','nunique'),predicted=('predicted','sum'),observed=('observed','sum'),matched=('matched','sum')).reset_index()
    ss['precision_pct']=100*ss.matched/ss.predicted;ss['recall_pct']=100*ss.matched/ss.observed;ss.to_csv(HERE/'index_side_summary.csv',index=False)
    contributing=strata[(strata['mode']=='expanding_chronological')&strata.observed.gt(0)].groupby(['hypothesis','underlying','option_type']).cycle_id.nunique()
    ss['cycles_with_observed_exits']=[int(contributing.get((r.hypothesis,r.underlying,r.option_type),0)) for r in ss.itertuples()]
    ss.to_csv(HERE/'index_side_summary.csv',index=False)
    uncertain=pd.read_csv(HERE/'cycle_bootstrap_comparisons.csv');best=chrono[~chrono.hypothesis.isin(['clock_only','inventory_only','training_selected'])].iloc[0].hypothesis
    cmp=uncertain[(uncertain['mode']=='expanding_chronological')&uncertain.hypothesis.isin([best,'training_selected'])].copy()
    for field in ['mean_f1_difference','low95','high95']:cmp[field]*=100
    fs=pd.read_csv(HERE/'separate_final_liquidation_scores.csv');fs=fs[fs.known_initialization];ft=fs[['predicted','observed','matched','false_positives','missed_exits']].sum()
    frozen=pd.read_csv(HERE/'unchanged_model28_exit_scores.csv');frozen=frozen[frozen.known_initialization];fr=frozen[['predicted','observed','matched','false_positives','missed_exits']].sum()
    timing=rank[(rank['mode']=='expanding_chronological')&rank.hypothesis.isin([best,'training_selected','clock_only','inventory_only'])].copy()
    timing['precision_pct']=100*timing.precision;timing['recall_pct']=100*timing.recall
    final_signal=[]
    predictions=pd.read_csv(HERE/'fixed_trigger_predictions.csv.gz');chronocids=folds[folds['mode']=='expanding_chronological'].test_cycle_id.unique()
    from evaluate import match
    for name in sorted(predictions.hypothesis.unique()):
        pp=predictions[(predictions.hypothesis==name)&predictions.cycle_id.isin(chronocids)];fe=e[e.cycle_id.isin(chronocids)&e.outcome_stratum.eq('final_liquidation')]
        ma,_,_=match(pp,fe,120);final_signal.append(dict(hypothesis=name,signals_matching_final_outcomes=len(ma),intermediate_precision_denominator=len(pp)))
    pd.DataFrame(final_signal).to_csv(HERE/'final_overlap_false_intermediate_signals.csv',index=False)
    comparison=chrono[chrono.hypothesis.isin(['side_drawdown_halfpct','iv_rise1point5','premium_loss50','clock_only','inventory_only','training_selected'])]
    short_table=retained[['motif_id','index','right','premium_loss_pct','side_drawdown_pct','adverse_spot5_pct']]
    condition_table=condition_table[condition_table.hypothesis.isin(['premium_loss50','side_drawdown_halfpct','iv_rise1point5'])]
    idx=ss[ss.hypothesis.isin([best,'training_selected'])].copy()
    text=f'''# Algo 8 — intermediate exit controller

**No tested trigger has adequate out-of-cycle evidence for an 80–90% general
exit rule.** Twelve fixed hypotheses were tested, with no expansion of the bank.
The best chronological average-cycle F1 comes from a sampled side-drawdown rule;
its pooled precision is **18.0%**, recall **16.6%**. A 50% premium-loss rule reaches
**36.4% precision, 9.8% recall**. Relative discrimination improves over the simple
baselines, but most exits remain unexplained.

## The original 32 absent and 27 retained cases

The original 59 motifs include **long protection as well as short exposure**.
The absent group has **9 short covers / 23 long closures**; the retained group has
**7 short covers / 20 long closures**. Long-wing sales are not short stops.

The upstream audit of the 32 absent cases finds:

{table(absent)}

In total, ten have another strike near the actual active epoch's first entry;
13 have no comparable allocation near that entry; eight previously held the same
role but reduced it earlier; one lacks initialization. “Near” means +/-120 seconds,
clipped before the exit. It does not establish unique allocation ownership or
absence at every other time. All eight earlier reductions include the candidate's
risk reason bit, sometimes alongside an allocation change; that is its simulated
reason, not an explanation of the original strategy.

Of the 27 retained cases, 26 retain the same direction; **M06 instead holds a short
where the log closes a long**. For the seven actual short covers, pre-close values
are below. Percentages use pooled live entry cost and the supplied Rs20m capital
reference; adverse spot sign is positive for rising CE / falling PE spot risk.

{table(short_table)}

M12, M13 and M15 close during **09:15**, before the first completed session candle;
their market features remain missing. Also, a terminal close can follow earlier
partial reductions: [episode links](short_motif_episode_links.csv) distinguish those
times. [All 59 upstream cases](upstream_32_27_audit.csv), [entry source histories](motif_active_entry_history.csv)
and [all 27 condition checks](motif_27_pre_event_condition_audit.csv) retain the exceptions.

## Cases, information boundary and controls

**11,716 closing Buy children → 8,197 contract/second atoms → 4,251 reduction
episodes.** Covers within 120 seconds are grouped unless a new short opening,
date change or outcome-stratum change intervenes. An episode is an observable
batch, not a certified original decision. Every source fill/quantity is retained.

The 32 known-initialization cycles contain **3,512 intermediate episodes and 326
final-liquidation episodes**. Three expiry-only starts contribute another 366
intermediate / 47 final episodes, retained as a sensitivity cohort. Two episode
starts have no short in the strict pre-second book because exposure is created
within that second; those cases remain observable limitations.

Features use fills **strictly before the event second** and only the preceding
completed candle. Same-second fills, exit price, later closed size, future re-entry
and parent lifetime totals are excluded. The ledger includes live quantity/cost,
FIFO/LIFO remaining entry histories, option movement, underlying movement, age,
recent allocation, side P&L and sampled peak drawdown. Missing live marks make
side P&L unavailable. Greeks are the inherited flat-ATM-IV approximation, not
broker Greeks; sampled drawdowns are not tick high-water marks. Costs are excluded
from marked P&L. Full-chain eligibility and original allocation ownership are unknown.
Availability means nominal candle completion; actual feed latency and the export
seconds' exchange-time semantics are not independently certified.

The fixed five-minute control pool has **{controls['fixed_grid_pool']:,}** observations;
**{controls['near_cover_excluded']:,}** are excluded for a cover within +/-120s.
Matching yields **{controls['matched_pairs']:,} unique controls for {controls['cases_with_control']:,}/{controls['cases']:,} intermediate cases**.
These control descriptives retain all 35 received cycles; predictive validation
below uses only the 32 cycles with known initialization.
Primary controls use the same contract/session/cycle/right, quantity ratio .5–2,
entry-age/recent-allocation bins and <=60-minute distance. Secondary other-strike
controls are explicitly separate. No control is reused; unmatched cases remain
in scoring. Future proximity labels controls only and never enters a trigger.

Same-contract descriptive condition rates, among available observations:

{table(condition_table,['hypothesis','case_rate_pct','control_rate_pct'])}

These comparisons are not causal estimates. [Control-selection audit](control_selection_audit.csv),
[all pairs](matched_nonexit_controls.csv) and [feature contrasts](matched_feature_contrasts.csv)
show missingness, unmatched cases and support. Minutes/orders are not independent
inferential samples; uncertainty uses whole cycles.

## Registered trigger tests and chronological results

Rules fire on activation or a known new same-contract short addition, with a
five-minute refractory period. Persistent thresholds do not fire every minute;
missing inputs abstain. Precision uses the **full active-short scoring risk set**,
not the matched-control sample. Signals match the same contract's first reduction
one-to-one within **+/-120 seconds**. This allows early warning/execution delay;
it does not identify a submission timestamp.

The table covers **24 chronological test cycles / 2,200 intermediate episodes**.
Each fold uses at least eight strictly earlier-expiry cycles. Clock-only baselines
fit three five-minute bins; inventory-only baselines fit a median event-size
threshold, by index/right/phase with pooled fallback. All twelve trigger levels
remain fixed. `training_selected` chooses by training-cycle mean F1 only.

All percentages below are pooled except `macro_cycle_f1`, which weights cycles
equally. Coverage is feature availability, not matching accuracy.

{table(chrono,['hypothesis','precision','recall','macro_cycle_f1','false_positives','missed_exits','event_feature_coverage'])}

Side drawdown's average-cycle F1 advantage is **10.1 percentage points over clock**
(whole-cycle bootstrap 95% interval **5.0–14.8**) and **8.5 points over inventory**
(**3.4–14.4**). This supports limited relative discrimination, not identification
of the original stop. Absolute precision/recall remain low. Shared calendar shocks
and prior inspection of every date limit this internal validation.

[All chronological/LOCO cycle scores](cycle_validation_scores.csv),
[train/test cycle lists](validation_folds.csv), [ranked hypotheses](ranked_trigger_hypotheses.csv),
[baseline parameters](baseline_fold_parameters.csv), [cycle bootstrap comparisons](cycle_bootstrap_comparisons.csv)
and [timing sensitivity at +/-60/120/300s](ranked_trigger_hypotheses.csv).
LOCO excludes whole cycles but may train on later dates; it is separate from the
chronological check. Every fixed candidate is retained, including failures.

Index/right results for the leading fixed rule and training-selected pipeline:

{table(idx,['hypothesis','underlying','option_type','cycles_with_observed_exits','precision_pct','recall_pct'])}

[Phase-specific results](index_side_phase_scores.csv) and
[all feature coverage/condition frequencies](feature_coverage_by_cycle.csv) retain
weak subgroups. No index/right subgroup justifies a shared or distinct recovered
exit rule. A condition can remain true long before an exit; condition-at-exit
frequency must not be mistaken for timed trigger matching.

## Final liquidation and baseline preservation

Final liquidation is labeled only on expiry at/after 15:00, after the right's last
received new short, with no shorts left at the received end. Future records define
this **outcome only**. Early shutdowns and late nonterminal reductions remain
intermediate. The independent dated deadline diagnostic produces **{int(ft['matched'])}/{int(ft['observed'])}**
final matches from **{int(ft['predicted'])}** signals, with {int(ft['false_positives'])} false signals
and {int(ft['missed_exits'])} missed finals. [Separate final scores](separate_final_liquidation_scores.csv).
Risk signals near final outcomes still count against intermediate precision:
[overlap audit](final_overlap_false_intermediate_signals.csv).

The unchanged model 28 has **{int(fr['matched'])}** intermediate matches from
**{int(fr['predicted'])}** own-inventory cover episodes, against **{int(fr['observed'])}** observed
intermediate episodes. [Comparator scores](unchanged_model28_exit_scores.csv).
This study uses actual inventory; comparing its metrics to autonomous model 28
cannot establish an improved autonomous controller. No prior configuration,
findings, counts or result files are replaced.

## Supported observations and remaining uncertainty

Supported: upstream strike, allocation and earlier-risk-action divergences explain
candidate absence in identifiable subsets. Long closures differ from short covers.
Premium stress, IV change and sampled drawdown distinguish some exits from controls,
but similar states also persist without closure. [Every false signal and missed
exit](trigger_counterexamples.csv.gz) and [representative counterexamples](representative_counterexamples.csv)
are preserved.

**None meets the registered requirement of >=80% precision AND recall, >=80%
feature coverage and >=5 chronological cycles.** There is no recovered general
exit controller or demonstrated economic alpha. The finite study stops here.
Unresolved explanations include allocation/side ownership and stop resets,
portfolio targets/limits, instantaneous quotes/Greeks and pending decisions.
Original decision/submission/cancellation records remain absent.

[Case ledger](exit_case_ledger.csv.gz), [atomic covers](short_cover_atoms.csv.gz),
[source children](short_cover_children.csv.gz), [pre-event risk set](pre_event_risk_set.csv.gz),
[registered protocol](REGISTERED_PLAN.md), [measurement notes](MEASUREMENT_NOTES.md),
[reproduction instructions](README.md), [input hashes](input_manifest.json) and
[validation audit](validation_audit.json). Software tests validate accounting and
information boundaries, not original-strategy truth.
'''
    (HERE/'INTERMEDIATE_EXIT_CONTROLLER.md').write_text(text)
    print('Report complete. Best chronological fixed macro-F1:',best)
if __name__=='__main__':run()
