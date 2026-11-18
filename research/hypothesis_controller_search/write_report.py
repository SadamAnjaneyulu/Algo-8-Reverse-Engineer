"""Concise, mechanically linked report; no new selection or narrative rule fitting."""
import hashlib,json,os
from pathlib import Path
import numpy as np
import pandas as pd
from prepare import HERE,OUT,digest
from search import ALLOC,EXITS,GATES,WINGS,REENTRY,FINALS,REFS


def pct(v):return 'unavailable' if pd.isna(v) else f'{100*v:.1f}%'
def n(v):return 'unavailable' if pd.isna(v) else f'{v:,.0f}'
def tab(rows):
    if not rows:return 'No eligible observations.'
    keys=list(rows[0]);return '\n'.join(['| '+' | '.join(keys)+' |','| '+' | '.join('---' for k in keys)+' |']+['| '+' | '.join(str(r[k]).replace('|',' / ').replace('\n',' ') for k in keys)+' |' for r in rows])


def main():
    m=json.loads((OUT/'search_manifest.json').read_text());best=m['best_candidate_id'];reg=pd.read_csv(OUT/'candidate_registry.csv');cfg=json.loads(reg[reg.candidate_id.eq(best)].iloc[0].configuration)
    s=pd.read_csv(OUT/'candidate_scores.csv');s=s[s.phase.eq(2)];st=pd.read_csv(OUT/'candidate_stratum_scores.csv.gz');cohort=m['trace_candidate_ids']
    un=pd.read_csv(OUT/'cycle_uncertainty.csv');ab=pd.read_csv(OUT/'market_gate_ablation.csv');eq=pd.read_csv(OUT/'candidate_equivalence_groups.csv');pairs=pd.read_csv(OUT/'top_candidate_equivalence.csv');champ=pd.read_csv(OUT/'component_champions.csv')
    mechanisms=pd.read_csv(OUT/'order_mechanics_diagnostic.csv');rolling=pd.read_csv(OUT/'rolling_origin_scores.csv');lat=pd.read_csv(OUT/'latency1_summary.csv');quote=pd.read_csv(OUT/'strict_quote_sensitivity.csv');economic=pd.read_csv(OUT/'economic_diagnostics.csv')
    inter=pd.read_csv(OUT/'intermediate_cover_scores.csv');initial=pd.read_csv(OUT/'initial_entry_reconstruction.csv');front=pd.read_csv(OUT/'pareto_frontier.csv');baseline=pd.read_csv(OUT/'baseline_reconciliation.csv')
    def score(cid,split):return s[s.candidate_id.eq(cid)&s.split.eq(split)].iloc[0]
    later=score(best,2);simple=score(2320,2);strict=score(0,2);valid=score(best,1)
    comparison=[]
    for split,label in [(0,'Fit June–July'),(1,'Internal August'),(2,'Inspected Sep–Oct')]:
        for cid,name in [(0,'Strict seed clock'),(2320,'Pooled budget clock'),(best,'Registered leader')]:
            q=score(cid,split);comparison.append(dict(Period=label,Controller=f'{cid}: {name}',Cycles=int(q.cycles),Event_macro_F1=pct(q.event_macro_f1),Quantity_score=pct(q.quantity_score),Inventory_score=pct(q.inventory_score),Final_match=pct(q.final_score),Final_targets=int(round(q.final_target*q.cycles)),Penalized_score=f'{q.primary_score:.4f}'))
    role_rows=[]
    for index in [0,1]:
        for phase,label in [(0,'Pre-expiry'),(1,'Expiry')]:
            q=st[st.candidate_id.eq(best)&st.split.eq(2)&st['index'].eq(index)&st.phase.eq(phase)]
            if q.empty:continue
            r=q.iloc[0]
            for a,name in enumerate(['New shorts','Short covers','Wing buys','Wing sells']):
                role_rows.append(dict(Index=['NIFTY','SENSEX'][index],Phase=label,Action=name,Precision=pct(r[f'match{a}']/r[f'pred{a}'] if r[f'pred{a}'] else np.nan),Recall=pct(r[f'match{a}']/r[f'actual{a}'] if r[f'actual{a}'] else np.nan),Cycle_mean_F1=pct(r[f'f1_{a}'])))
    family=[]
    for value,g in champ[champ.family.eq('allocation')].groupby('value'):
        row=g[g.split.eq(1)].iloc[0];late=g[g.split.eq(2)].iloc[0]
        family.append(dict(Allocation=value,August_champion=int(row.candidate_id),August_score=f'{row.primary_score:.4f}',Later_score=f'{late.primary_score:.4f}',Later_quantity=pct(late.quantity_score)))
    gates=[dict(Gate=r.gate,Period=['Fit','August','Later'][r.split],Event_F1=pct(r.event_macro_f1),Quantity=pct(r.quantity_score),Inventory=pct(r.inventory_score),Score=f'{r.primary_score:.4f}') for r in ab.itertuples() if r.split>0]
    uncertainty=[]
    for baseline_id in [0,2320]:
        for metric in ['primary_score','event_macro_f1','inventory_score']:
            r=un[un.baseline_id.eq(baseline_id)&un.split.eq(2)&un['index'].eq('pooled')&un.metric.eq(metric)].iloc[0]
            uncertainty.append(dict(Baseline=baseline_id,Metric=metric,Cycles=r.cycles,Mean_difference=f'{100*r.mean_difference:+.2f} pp',Cycle_bootstrap_95=f'[{100*r.low95:+.2f}, {100*r.high95:+.2f}] pp'))
    stoprows=[]
    for cid in [0,2320,best]:
        q=inter[inter.candidate_id.eq(cid)&inter.split.eq('later_Sep_Oct')]
        for index,g in q.groupby('index'):
            p,a,ma=g.predicted.sum(),g.actual.sum(),g.matched.sum()
            stoprows.append(dict(Controller=cid,Index=index,Before_1500_predicted=int(p),Observed=int(a),Matched=int(ma),Precision=pct(ma/p if p else np.nan),Recall=pct(ma/a if a else np.nan)))
    risk=champ[champ.family.eq('exit')&champ.split.eq(1)].sort_values('primary_score',ascending=False).head(6)
    riskrows=[dict(Exit_family=r.value,August_champion=r.candidate_id,August_score=f'{r.primary_score:.4f}',August_cover_F1=pct(r.f1_1)) for r in risk.itertuples()]
    # Weight sensitivity is fixed in the original specification.
    weights=[]
    for weight in ['primary','event_heavy','inventory_heavy']:
        q=s[s.split.eq(1)].sort_values([weight+'_score','complexity','candidate_id'],ascending=[False,True,True]).iloc[0]
        late=score(int(q.candidate_id),2)
        weights.append(dict(Weights=weight,August_selected=int(q.candidate_id),Complexity=int(q.complexity),August_score=f'{q[weight+"_score"]:.4f}',Later_event_F1=pct(late.event_macro_f1)))
    rolling_rows=[dict(Origin=r.origin,Period=r.period,Controller=r.candidate_id,Cycles=r.cycles,Event_F1=pct(r.event_macro_f1),Score=f'{r.primary_score:.4f}') for r in rolling.itertuples()]
    latency_rows=[]
    for cid in [0,2320,best]:
        for sp in [1,2]:
            q=lat[lat.candidate_id.eq(cid)&lat.split.eq(sp)]
            if len(q):
                r=q.iloc[0];latency_rows.append(dict(Controller=cid,Period=['Fit','August','Later'][sp],Latency1_event_F1=pct(r.event_macro_f1),Latency1_inventory=pct(r.inventory_score),Latency0_event_F1=pct(score(cid,sp).event_macro_f1)))
    qlater=quote[quote.split.eq('later_Sep_Oct')]
    economy=[]
    for cid in [0,2320,best]:
        for index,g in economic[economic.candidate_id.eq(cid)&economic.split.eq(2)].groupby('index'):
            economy.append(dict(Controller=cid,Index=['NIFTY','SENSEX'][index],Cycles=len(g),Priced=int(g.net_pnl.notna().sum()),Net_sum='₹'+n(g.net_pnl.sum(min_count=1)),High_cost_net='₹'+n(g.high_cost_net.sum(min_count=1))))
    cg=eq[eq.candidate_id.eq(best)].iloc[0];dif=pd.read_csv(OUT/'discriminating_events.csv')
    profile=initial[initial.candidate_id.eq(best)&initial.first_received_phase.eq('preexpiry')]
    seed_match=(profile.predicted_first_CE_wing_strike.eq(profile.observed_first_CE_wing_strike)&profile.predicted_first_PE_wing_strike.eq(profile.observed_first_PE_wing_strike))
    exactqty=(profile.predicted_CE_short_quantity.eq(profile.observed_CE_short_quantity)&profile.predicted_PE_short_quantity.eq(profile.observed_PE_short_quantity))
    front=front.sort_values('complexity')
    frontier_rows=[dict(Controller=int(r.candidate_id),Complexity=int(r.complexity),August_raw_score=f'{r.primary_raw:.4f}',August_event_F1=pct(r.event_macro_f1)) for r in front.itertuples()]
    text=f'''# Algo 8 — constrained controller search

**The search makes measurable reconstruction progress, but does not recover an
80–90% controller or establish economic alpha.** The registered August-selected
leader reaches **{pct(later.event_macro_f1)} event macro F1** on the 15 already-
inspected later cycles. The pooled-budget clock baseline reaches
**{pct(simple.event_macro_f1)}**, and the stricter seed baseline
{pct(strict.event_macro_f1)}. These are autonomous action comparisons, not
teacher-forced predictions using the historical book.

The completed bank contains **{m['candidate_count']:,} unique controller definitions**:
13,824 main combinations plus 40 earlier-fit local refinements. Every one is
replayed over all 35 cycles / 65 received cycle-sessions. Candidate count is not
effective sample size; there is no external researcher-blind evaluation.

## Twelve direct answers

1. **Initial entry:** a calendar-conditioned 09:16 clock and nearest preceding-
   close ATM remain the simplest structural explanation. Missing eligible/no-trade
   records prevent identifying the original eligibility gate. The aggregate leader
   is not a faithful opening reconstruction: it uses routine-budget wings from
   the start and scales the opening too. In the first-three-minute gross-action
   comparison it matches both first wing strikes on {int(seed_match.sum())}/{len(profile)}
   received pre-expiry starts, and both short quantities on {int(exactqty.sum())}/{len(profile)}.
2. **Allocation quantities:** pooled normalized clock sizing is the leading
   composite family. Candidate {best} multiplies fitted clock weights by 1.25
   and rounds each role to whole base units. Its later quantity score is only
   **{pct(later.quantity_score)}**. That is normalized action-quantity overlap,
   not exact size accuracy or a recovered capital budget.
3. **Clock versus target/risk:** the clock explanation survives best in this
   grammar. Target restoration, cover replacement and fitted risk/IV sizing are
   genuine autonomous competitors, not calculations from actual future covers.
   Their best validation results are shown below; configured caps remain unknown.
4. **Market gate:** the leader has **no range/efficiency entry gate**. Paired
   ablations below keep the other rules fixed. They do not establish that no
   original filter exists outside the received-session universe.
5. **Intermediate reductions:** the selected composite uses a **50% premium
   increase above its own pooled contract entry cost**, evaluated on completed
   candles. This is a tested approximation, not the original stop. The before-
   15:00 table excludes deadline exits and shows its limited actual cover recall.
6. **Rapid reopen/neutralisation:** safe idempotent closes cannot generate the
   observed opposite-position overshoots. On {len(mechanisms)} conservative motifs,
   a full stale duplicate close matches the immediate opposite quantity in
   {int(mechanisms.exact_full_duplicate_quantity.sum())} cases. This comparison is
   **conditioned on the observed liquidation**; it does not predict its cause or
   prove an execution bug. Submission/cancellation/acknowledgement records are absent.
7. **Final liquidation:** the leader uses 15:27 before 3 August and 15:14 later,
   with separate short and wing instructions and explicit failed fills. Its
   later final-short-flat match is {pct(later.final_score)} on resolved targets.
   This is not a universal all-leg exit rule; early exits and residuals remain.
8. **Risk control:** no tested risk threshold recovers the complete controller.
   Rs200,000 is an explicitly scoped full-cycle expiry loss hypothesis; 4% of
   the simulated preceding-session short debit is one denominator hypothesis.
   Neither is the verified supplied rule. Continuous matched call quantities are
   contradicted by the canonical book; all 31 last pre-expiry carry snapshots
   nevertheless have same-right long quantities covering shorts. Fitted caps and
   flat-ATM-IV Greeks are modeling inputs, not original margin limits.
9. **Indistinguishable rules:** {eq.equivalence_group.nunique():,} distinct action-
   fingerprint groups contain the {len(eq):,} definitions. The leader's group has
   {int(cg.group_size)} definition(s). Hash equality is a reproducible observational
   signature, not proof of original code; exact top-cohort traces are compared
   separately. Near-equivalent leaders and their actual disagreements are exported.
10. **Improvement:** later event F1 improves by
    **{100*(later.event_macro_f1-simple.event_macro_f1):.2f} percentage points** over
    the pooled-budget clock baseline. Its penalized composite improves by
    {100*(later.primary_score-simple.primary_score):.2f} points on the 0–100 scale.
    Cycle bootstrap intervals below include the small sample and do not adjust
    away the earlier researcher inspection or broad candidate selection.
11. **Complexity/weights:** complexity is penalized before ranking. The alternative
    fixed weights select the configurations listed below; exact parameter recovery
    is not robust merely because related clock/budget families recur.
12. **Needed observations:** original strategy/allocation IDs, controller decisions,
    submissions/replacements/cancellations/acknowledgements, tick bid/ask, certified
    eligible/no-trade sessions, complete-chain quotes, settlement and account
    NAV/margin. New untouched records are needed for external validation.

## What was executed and how it was scored

[Registered specification](SEARCH_SPEC.md), [manifest](outputs/search_manifest.json),
[all definitions](outputs/candidate_registry.csv),
[all scores](outputs/candidate_scores.csv),
[ranked leaders](outputs/ranked_candidates.csv),
[saved leader YAML](outputs/best_candidate.yaml).

The six sizing, twelve exit, three market-gate, four wing, four re-entry,
two deadline and two spot-reference families form the main Cartesian bank.
Stage1 baseline slices and stage2 one-component slices are identified in the
registry; stage3 combines them; stage4 refines only June–July-ranked parents.
August chooses the final ranking. September–October were already inspected in
prior work and are labeled an internal chronological check, never a blind test.
Rolling June->July uses separately recalibrated June-only schedules and caps.

Decisions use only previous completed candles and the simulated book. No
historical fill triggers an assumed candidate fill. A positive candle open is a
hypothetical fill; missing opens leave requests unfilled. Exact fixed seed
contracts can be absent in the traded-only chain, so alternative simple budget
baselines are reported. Order labels never become confirmed decision times.
Fragmentation is charged as one request per 65/20 units; the original unfilled
request queue is unknown. Safe repeated closes are capped at current inventory.

Primary score: **0.40 event macro F1 + 0.20 quantity + 0.30 inventory + 0.10 final
closure − 0.002 per complexity point**. Missing final targets are unavailable;
the other weights renormalize, rather than awarding a correct invented closure.
Each cycle is scored separately, then averaged. Exact-contract/action matches
use one-to-one ±2-minute chronological matching. Independent 0/1-minute counts
and one-grid strike tolerance are exported separately. Quantity score is
1−absolute action-quantity error / (actual+predicted quantity); inventory score
is 1−contract L1 path error / (actual+predicted gross path quantity). Neither is
a percentage of completely correct books. False predicted and missed actions
remain in all applicable denominators. P&L never ranks candidates.

## Frozen comparison

{tab(comparison)}

Later action precision/recall by index and phase (micro counts within each
stratum; F1 column is a mean of cycle F1s):

{tab(role_rows)}

Intermediate short covers before 15:00, ±2 minutes, exact contract/action:

{tab(stoprows)}

Source [mismatch ledger](outputs/event_mismatch_ledger.csv.gz),
[predictions](outputs/replay_predictions.csv.gz),
[inventory paths](outputs/inventory_replay.csv.gz),
[tolerance checks](outputs/timestamp_tolerance_scores.csv),
[initial-entry contradictions](outputs/initial_entry_reconstruction.csv).

## What improves sizing and management

Each allocation-family row is its August-selected composite champion; other
components can differ, so this is not a causal isolated allocation comparison.

{tab(family)}

Paired market-gate ablation on the same main-bank controller, other parameters
fixed (a selected-model diagnostic, not an independent test):

{tab(gates)}

Leading exit-family composites selected on August, not later returns:

{tab(riskrows)}

The leader's scale 1.25 and budget-from-opening choices conflict with ordinary
195/60 initial books and separate seed-wing geometry. That is a concrete reason
to retain competing controllers and decline a near-complete reconstruction claim.
Routine hedge additions, held-wing replacement and processing reversals are not
identified as the same intentional action. Flow-class agreement is only an
observable open/reduce/mixed classification; intent remains unknown.

## Robustness, uncertainty and complexity

{tab(uncertainty)}

Expanding-origin checks, with schedules/caps recalibrated before each origin:

{tab(rolling_rows)}

One-minute fill-latency override, unchanged saved decisions/rules and own-book
state replayed under delayed fills:

{tab(latency_rows)}

The strict quote screen requires positive volume for every held preceding mark
and every execution candle, with both policies actively trading. Its later
common baseline/leader cohort contains
{int(qlater.common_strict_cycles.iloc[0]) if len(qlater) else 0} cycles. This is an
ex-post data-quality sensitivity, not an available entry filter or capacity
proof. This severe screen includes opening warm-up minutes without a completed
same-day candle; zero support is not proof of corrupt broker data. It must not
be used to remove losing cases selectively. Missing-IV and
flat-surface Greek assumptions are retained in [coverage](outputs/data_coverage.csv).

A simpler alternative, candidate 2704, has complexity 6 versus the selected
leader's 8, with August penalized scores 0.2660 versus 0.2669. Its later score is
0.2957 versus 0.2963. Such small differences do not identify the extra scaling or
deadline branch as the original rule. It is retained as a competing explanation.

Fixed-weight sensitivity:

{tab(weights)}

August reconstruction/complexity Pareto frontier:

{tab(frontier_rows)}

![Reconstruction and complexity](outputs/pareto_frontier.png)

Full [frontier](outputs/pareto_frontier.csv),
[all equivalence groups](outputs/candidate_equivalence_groups.csv),
[top exact overlaps](outputs/top_candidate_equivalence.csv),
[discriminating events](outputs/discriminating_events.csv),
[conditional order mechanics](outputs/order_mechanics_diagnostic.csv).
The discriminating table gives actual timestamp/instrument/quantity contrasts,
own preceding state and both candidates' actions. Missing controller/order
records prevent turning the better historical match into proof of intent.

## Secondary economic diagnostics

{tab(economy)}

These are marked gross P&L minus assumed costs: 25bps premium turnover, Rs20 per
base request and Rs0.05 per transacted unit; high cost uses 50bps turnover.
Open residuals use available preceding-candle marks, with no invented settlement.
They are not actual Algo8 returns, equal-margin comparisons, executable bid/ask
or evidence that this reconstruction has alpha. Quote failures, changing
exposure and the traded-only option universe prevent that conclusion.

## Reproducibility and validation

The existing playbook book remains the canonical baseline. Feeding its recorded
incremental fills through the simulation accounting reproduces all
**{int(baseline.minute_quantity_checks.sum()):,} minute quantity boundaries** over
35 cycles. Maximum cash difference is {baseline.maximum_cash_error.max():.2g}
rupees. Simulated pooled-cost/realised accounting is also compared with the
canonical event ledger. Atomic child source IDs, requested versus filled sizes,
before/after positions, prior quotes/Greeks and timestamp flags are retained in
[canonical events](outputs/canonical_events.csv.gz) and
[atomic books](outputs/canonical_atomic_books.csv.gz).

Full replay traces are persisted for the {len(cohort)} declared top/baseline
controllers; all {m['candidate_count']:,} configurations, scores, whole-cycle
metrics, phase score vectors and fingerprints remain reproducible. Tests check
accounting, pending fills, missing quotes, deterministic definitions, split
boundaries, independent tolerance matching, and that historical target changes
cannot affect candidate decisions. Tests establish software behavior only.
See [validation audit](outputs/validation_audit.json) for the final results and
[README](README.md) for commands and saved-config replay.

## Best-supported reconstructed behaviour

A clock-driven accumulation engine, moving near-ATM shorts, outward protection
and separate management remain the strongest structure. This search adds an
executable autonomous approximation and measures its limited improvement over
several simple baselines. It does not upgrade prior structural match rates into
full-controller accuracy.

## Plausible competing explanations

Pooled versus index clock schedules, seed versus routine-budget initialization,
premium stops versus other side management, and dated versus uniform deadlines
remain competing approximations. Similar scores and identical observed action
paths identify equivalence classes, not a unique original implementation.

## Unresolved controller logic

The true sizing budget, eligibility, exact per-allocation exits/trails, queue and
re-entry mechanics, large overlays, hedge-refresh cause, 4%/1% scope/reset and
account-level risk limits remain unidentified. The best broad event fit is far
below 80–90%; no missing rule is invented to complete the narrative.
'''
    (HERE/'HYPOTHESIS_CONTROLLER_SEARCH.md').write_text(text)
    os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.cache/matplotlib'))
    # Standalone scientific artifact, not a chart of strategy economic returns.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    q=s[s.split.eq(1)];fig,ax=plt.subplots(figsize=(8,4.5));ax.scatter(q.complexity,q.primary_raw,s=6,alpha=.08,color='#476c9b')
    ax.plot(front.complexity,front.primary_raw,'o-',color='#1b8a68',label='Pareto frontier')
    r=q[q.candidate_id.eq(best)].iloc[0];ax.scatter([r.complexity],[r.primary_raw],s=80,color='#c0523b',label=f'Selected {best}')
    ax.set(xlabel='Registered complexity points',ylabel='August raw reconstruction score',title='Reconstruction versus controller complexity')
    ax.legend();fig.tight_layout();fig.savefig(OUT/'pareto_frontier.png',dpi=180);plt.close(fig)
    m['code_sha256']={p.name:digest(p) for p in HERE.iterdir() if p.suffix in ['.py','.cpp']}
    m['report_sha256']=digest(HERE/'HYPOTHESIS_CONTROLLER_SEARCH.md')
    (OUT/'search_manifest.json').write_text(json.dumps(m,indent=2))
    print('Wrote',HERE/'HYPOTHESIS_CONTROLLER_SEARCH.md')

if __name__=='__main__':main()
