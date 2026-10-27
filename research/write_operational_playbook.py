"""Generate the requested operational report from audited event-level evidence."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import ROOT,OUT
from analyze_side_allocations import load_parents
from clarify_position_lifecycle import WINDOWS


def table(rows):
    if not rows:return 'No usable observations in this cohort.'
    keys=list(rows[0]);clean=lambda v:str(v).replace('|',' / ').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(keys)+' |','| '+' | '.join('---' for k in keys)+' |']+
                     ['| '+' | '.join(clean(r.get(k,'')) for k in keys)+' |' for r in rows])


def number(v,digits=0):return 'unavailable' if pd.isna(v) else f'{v:,.{digits}f}'
def percent(v):return 'unavailable' if pd.isna(v) else f'{100*v:.1f}%'
def packed(r,prefix='after_'):
    return '/'.join(number(r[prefix+k] if hasattr(r,'get') else getattr(r,prefix+k)) for k in ('CE_short','PE_short','CE_long','PE_long'))
def money(v):return 'unavailable' if pd.isna(v) else f'₹{v:,.2f}'


def main():
    audit=json.loads((OUT/'playbook_book_audit.json').read_text());aa=json.loads((OUT/'playbook_allocation_audit.json').read_text())
    w=pd.read_csv(OUT/'playbook_allocation_windows.csv');dist=pd.read_csv(OUT/'playbook_quantity_distributions.csv')
    e=pd.read_csv(OUT/'playbook_event_book.csv.gz');f=pd.read_csv(OUT/'playbook_fill_ledger.csv.gz')
    initial=pd.read_csv(OUT/'playbook_initial_role_times.csv');cycles=pd.read_csv(OUT/'playbook_cycle_books.csv');sessions=pd.read_csv(OUT/'playbook_session_end_books.csv')
    cadence=pd.read_csv(OUT/'playbook_cadence_summary.csv');market=pd.read_csv(OUT/'playbook_market_state_windows.csv')
    candidates=pd.read_csv(OUT/'playbook_calendar_candidates.csv');openingstates=pd.read_csv(OUT/'playbook_initial_market_states.csv')
    contrast=pd.read_csv(OUT/'playbook_market_size_contrasts.csv');reversal=pd.read_csv(OUT/'playbook_reversal_summary.csv')
    sensitivity=pd.read_csv(OUT/'playbook_frozen_exit_reversal_sensitivity.csv')
    tails=pd.read_csv(OUT/'playbook_negative_call_tail_intervals.csv');parents=load_parents()
    roles=['CE_short','PE_short','CE_long','PE_long']
    ordinary=initial[(initial[roles]>0).all(axis=1)]
    initial_rows=[]
    ce_pe_lag=(pd.to_datetime(ordinary.first_CE_short_ist)-pd.to_datetime(ordinary.first_PE_short_ist)).abs().dt.total_seconds()
    for (u,),g in ordinary.groupby(['underlying']):
        for role in roles:
            values=g[role];counts=values.value_counts();initial_rows.append(dict(Index=u,Leg=role,Sessions=len(g),Minimum=int(values.min()),
                Median=number(values.median()),Maximum=int(values.max()),Mode=int(counts.index[0]),Mode_sessions=int(counts.iloc[0])))
    expiry_starts=w[w.phase.eq('expiry')&w.clock.eq('09:16')&~w.active_short_before]
    expiry_rows=[dict(Index=r.underlying,Expiry=r.expiry_date,Net_book_at_0917=packed(r),
                      Meaning='Recorded flat-start expiry opening; missing prior history cannot be ruled out') for r in expiry_starts.itertuples()]
    schedule=[]
    for clock in ['09:16']+[f'{m//60:02}:{m%60:02}' for m in range(570,871,15)]:
        row=dict(Clock=clock)
        for u in ('NIFTY','SENSEX'):
            q=dist[dist.underlying.eq(u)&dist.phase.eq('preexpiry')&dist.clock.eq(clock)]
            vector=[q[q.role.eq(role)].iloc[0].modal_units for role in roles]
            ce=q[q.role.eq('CE_short')].iloc[0]
            row[u+'_modal_units']=str(vector[0]) if len(set(vector))==1 else '/'.join(map(str,vector))
            row[u+'_CE_min_med_max']='/'.join(number(v,1) for v in (ce.minimum_units,ce.median_units,ce.maximum_units))
        schedule.append(row)
    size=pd.read_csv(OUT/'playbook_size_model_checks.csv')
    size_rows=[dict(Index=r.underlying,Phase=r.phase,Model=r.model,Later_windows=r.windows,Cycles=r.cycles,
                    Exact_short_pair=percent(r.short_pair_match),Exact_four_roles=percent(r.four_role_match)) for r in
               size[size.block.eq('later_Sep_Oct')].itertuples()]
    allocation=[]
    for u,day,clock in [('NIFTY','2026-06-29','09:16'),('NIFTY','2026-06-29','09:30'),('SENSEX','2026-10-07','09:16')]:
        r=w[w.underlying.eq(u)&w.date.eq(day)&w.clock.eq(clock)].iloc[0]
        for role in roles:
            allocation.append(dict(Session=day,Phase=r.phase,Window=clock,Index=u,Leg=role,Before=int(r['before_'+role]),
                Added=int(r['add_'+role]),Removed=int(r['before_'+role]+r['add_'+role]-r['after_'+role]),After=int(r['after_'+role]),
                Current_book=packed(r),Likely_trigger='Opening/timer association; cause unobserved',Confidence='High quantity; inferred trigger'))
    market_rows=[]
    selected=market[market.phase.eq('preexpiry')&market.clock_type.eq('recurring17')&market.axis.isin(['direction15','efficiency15'])]
    for r in selected.itertuples():
        market_rows.append(dict(Index=r.underlying,State=r.axis+': '+r.market_state,Observed_sessions=r.observed_sessions,
            Windows=r.windows,Active=r.active_windows,Allocation_rate=percent(r.allocation_rate),
            Mean_added_units_per_right=number(r.mean_added_short_units_per_right,2),Clock_centered_units=number(r.mean_clock_centered_short_units,2)))
    opening_rows=[dict(Index=r.underlying,Lagged_prior_session=r.market_state,Stored_session_candidates=r.candidate_sessions,
                       Recorded_entry_sessions=r.observed_entry_sessions,Recorded_rate=percent(r.observed_rate),
                       Unknown_no_trade=r.missing_or_unknown_trade_sessions) for r in openingstates[openingstates.axis.eq('prior_session_type')].itertuples()]
    contrasts=[dict(Index=r.underlying,Contrast=r.contrast,Paired_later_sessions=r.paired_sessions,
        Clock_centered_unit_difference=number(r.mean_clock_centered_quantity_difference,2),
        Session_interval='too few sessions' if pd.isna(r.session_bootstrap_lower) else f'[{r.session_bootstrap_lower:+.2f}, {r.session_bootstrap_upper:+.2f}]')
        for r in contrast[contrast.phase.eq('preexpiry')&contrast.block.eq('later_Sep_Oct')].itertuples()]
    miss=[dict(Index=r.underlying,Expiry=r.expiry_date,Preceding_stored_session=r.candidate_preexpiry_date,Status=r.trade_history_status)
          for r in candidates[~candidates.observed_new_short].itertuples()]
    flow_rows=[dict(Index=r.underlying,Phase=r.phase,New_short_parents=r.fresh_short_parents,
        One_base_unit=f'{r.requested_parent_size_one_base_unit}/{r.fresh_short_parents} ({percent(r.requested_parent_size_one_base_unit/r.fresh_short_parents)})',
        Outside_nominal_windows=f'{r.parents_outside_nominal_windows}/{r.fresh_short_parents} ({percent(r.parents_outside_nominal_windows/r.fresh_short_parents)})',
        Late_after1433=r.first_fills_after1433) for r in cadence.itertuples()]
    revrows=[dict(Index=r.underlying,Phase=r.phase,Rapid_motifs=r.motifs,Conservative=r.conservative_motifs,
                  Cycles=r.cycles_with_motif,Flagged_short_parents=r.fully_tagged_new_short_parents,
                  Flagged_long_parents=r.fully_tagged_new_long_parents) for r in reversal.itertuples()]
    frozen=[dict(Model=r.model,Population=r['sample'],Later_cases=r.later_cases,Match_2min=percent(r.match_rate2))
            for _,r in sensitivity.iterrows()]
    exit_rows=[]
    sample=f[f.underlying.eq('NIFTY')&f.date.eq('2026-07-13')&f.timestamp_ist.str[11:19].isin(['09:50:00','09:53:00','09:59:00'])&f.closing_quantity.gt(0)]
    for r in sample.itertuples():
        event=e[e.underlying.eq(r.underlying)&e.expiry_date.eq(r.expiry_date)&e.timestamp_ist.eq(r.timestamp_ist)].iloc[0]
        exit_rows.append(dict(Time=r.timestamp_ist[11:19],Instrument=f'{r.strike} {r.option_type}',Action='Cover short' if r.side=='Buy' else 'Sell protection',
            Closed=r.closing_quantity,Remaining_contract=abs(r.quantity_after),Pooled_realized_PnL=money(r.realized_pnl_change),
            Prior_cycle_mark=money(event.before_equity),Candidate='Loss reduction / attached-wing disposal',
            Alternative='Allocation stop, trail or concurrent controller; threshold unknown',Confidence='High action; low unique trigger'))
    named=pd.read_csv(OUT/'allocation_named_exit_evaluation.csv')
    namedrows=[dict(Index=r.underlying,Phase=r.phase,Hypothesis=r.family,Earlier_selected_threshold=f'{r.field} {r.operator} {r.threshold}',
        Signals=r.signals,TP=r.true_positives,FP=r.false_positives,FN=r.false_negatives,
        Precision=percent(r.precision),Recall=percent(r.recall),Tolerance2_P_R=f'{percent(r.tolerance2_precision)} / {percent(r.tolerance2_recall)}')
        for r in named[named.family.isin(['premium_loss','movement','delta'])].itertuples()]
    scopes=pd.read_csv(OUT/'rule_refine_exit_scope_evaluation.csv')
    scope_rows=[dict(Target=r.target_kind,Scope=r.feature,Rule='time fallback' if r.kind=='fixed_time' else '−1% stated capital',
                     Later=f'{r.matches_within_2m}/{r.cycles}',Early_matches=f'{r.early_matches_2m}/{r.observed_early_exits}',False_early=r.false_early_signals)
        for r in scopes[scopes.kind.isin(['fixed_time','stated_1pct_scope_test'])&scopes.completed_only.eq(False)].itertuples()]
    finalrows=[]
    for u,g in cycles.groupby('underlying'):
        for regime,part in [('before_Aug3',g[g.expiry_date.lt('2026-08-03')]),('from_Aug3',g[g.expiry_date.ge('2026-08-03')])]:
            closures=part[part.final_short_flat_ist.notna()&part.final_short_flat_ist.str[:10].eq(part.expiry_date)]
            late=closures[closures.final_short_flat_ist.str[11:16].ge('15:00')]
            finalrows.append(dict(Index=u,Period=regime,Logged_cycles=len(part),Resolved_expiry_short_closures=len(closures),
                                  Late_closures=len(late),Late_in_1514=int(late.final_short_flat_ist.str[11:16].eq('15:14').sum())))
    role_end=cycles[cycles.underlying.eq('SENSEX')&cycles.expiry_date.eq('2026-10-08')].iloc[0]
    sequence=[dict(Role=role,Final_zero_event=role_end['final_'+role+'_flat_ist'],Meaning='Same-second child ordering is unknown') for role in roles]
    sequence.append(dict(Role='all roles',Final_zero_event=role_end.final_all_flat_ist,Meaning='Recorded full book flat'))
    risk=[
        dict(Level='Order',Variable='Requested quantity',Threshold='Mostly 65 NIFTY / 20 SENSEX base quantities',Action='Multiple child orders build size',Evidence='cadence/distributions',Exceptions='NIFTY expiry and late larger orders',Confidence='High observation; not capital formula'),
        dict(Level='Contract/side',Variable='Maximum short quantity / Delta',Threshold='Observed peaks only; configured cap unknown',Action='Separate covers / side reductions occur',Evidence='full event books and peaks',Exceptions='State varies by date/strike; latent modules',Confidence='High quantities, unresolved limit'),
        dict(Level='Protection',Variable='Wing distance / cost',Threshold='Seed geometry; routine ~2.5% premium proxy',Action='Buy wings, sometimes replace inward',Evidence='strong register and replacement pairs',Exceptions='Exact selector and trigger incomplete',Confidence='High effect / approximate selector'),
        dict(Level='Frozen basket',Variable='Terminal payoff bound',Threshold='NIFTY 13 July 09:17: ₹354,802.50',Action='Bound holds only if the snapshot is unchanged',Evidence='signed payoff calculation',Exceptions='Not margin, intraday stop or dynamic bound',Confidence='Exact conditional arithmetic'),
        dict(Level='Execution',Variable='Net call-tail quantity',Threshold='Negative at some observed states in all 35 cycles',Action='Later fills restore nonnegative call tail',Evidence='atomic event book / tail intervals',Exceptions='Mostly seconds; outside positions may be absent',Confidence='Exact within recorded-book convention'),
        dict(Level='Carry',Variable='Stated 4% stop',Threshold='Denominator/reference/scope unresolved',Action='Could reduce side/basket; not recovered',Evidence='Info.txt and limited prior tests',Exceptions='Cannot force all exits to this interpretation',Confidence='High on wording, low on implementation'),
        dict(Level='Expiry cycle',Variable='Stated 1% entire capital',Threshold='₹200,000 if ₹2 crore is the fixed base',Action='Early liquidation is observed; exact cause unproven',Evidence='Info.txt / fixed-scope checks',Exceptions='Scope/tick/reset/order latency alter marks',Confidence='Stated arithmetic, controller unresolved'),
        dict(Level='Portfolio',Variable='Margin / NAV / allocation across indices',Threshold='₹2 crore stated; actual margin/NAV absent',Action='Cannot reconstruct reserve or funding constraints',Evidence='No broker margin/position ledger',Exceptions='Residuals and omitted holdings/settlement',Confidence='Unresolved'),
        dict(Level='Final liquidation',Variable='Clock / active inventory',Threshold='15:14 concentration conditional on late closures',Action='Close shorts; wings can lag or remain',Evidence='atomic closure sequences',Exceptions='Early, late, partial and re-entry examples',Confidence='High execution facts; moderate clock hypothesis'),
    ]
    risk.append(dict(Level='Carry snapshot',Variable='Long/short quantities per right',Threshold='Long CE >= short CE and long PE >= short PE in 31/31 carry books',
                     Action='Observed end-book condition; explicit guard not identified',Evidence='Independent session-end inventories',
                     Exceptions='Transient intraday mismatches; quantities do not give margin or hedge ownership',Confidence='High observed / inferred purpose'))
    ruleconfidence=[
        dict(Rule='Ordinary first pair at 09:16 and nearest completed-close ATM',Direct='31/32; delayed day first single CE at 09:21',Later_support='October ordinary matches; dates inspected',Counterexample='5 October',Confidence='High observed / input proxy not unique',Next='Original decisions/order submissions'),
        dict(Rule='Recurring protected exposure build-up',Direct='529/544 joint; 32 sessions',Later_support='231/238 later windows',Counterexample='14 failures, one missing Greek fit',Confidence='High structural; not alpha',Next='Original module/allocation IDs'),
        dict(Rule='Fixed child unit, variable order count',Direct='N pre 2022/2032 request 65; S 2375/2375 request 20',Later_support='Whole-sample descriptive, no independent discovery test',Counterexample='Larger NIFTY orders; all multiples of base',Confidence='High order quantity; budget unresolved',Next='Dispatch intent/available margin'),
        dict(Rule='Full four-leg fixed size each timer',Direct='Only 433/544 recurring windows have equal four-role additions',Later_support='Fixed template about half of later size vectors',Counterexample='111 asymmetric windows',Confidence='Rejected as universal',Next='Separate planned, replacement and corrective orders'),
        dict(Rule='Market-range entry gate',Direct='Entries across fixed lagged categories',Later_support='Very few paired state-comparison sessions',Counterexample='Large opening moves still enter',Confidence='Not identified',Next='Certified eligible/no-trade universe'),
        dict(Rule='Cover triggers same-side re-entry',Direct='N later 76/97 vs52/97 controls; S75/113 vs75/113',Later_support='Only four/five cycles; poor strict support',Counterexample='Opposite-side effects; rapid reversal motifs',Confidence='Association / no universal rule',Next='Batch/intent-aware controller traces'),
        dict(Rule='Universal premium/Greek/spot stop',Direct='Recorded reductions; fitted triggers weak',Later_support='Frozen global first-reduction match ~29%',Counterexample='Many no-action conditions and missed covers',Confidence='Unresolved',Next='Allocation references and tick decision data'),
        dict(Rule='Hard 15:14 flatten-all rule',Direct='9/10 late carry-book closures in minute',Later_support='Same inspected sample',Counterexample='Early closures, 15:36:54 and residual wings',Confidence='Likely late fallback, not universal',Next='Exit requests, cancellations and settlement'),
    ]
    def timeline(u,day,clocks):
        q=e[e.underlying.eq(u)&e.date.eq(day)].sort_values('timestamp_ist');rows=[]
        for clock in clocks:
            stamp=day+'T'+clock+'+05:30';prior=q[q.timestamp_ist.lt(stamp)]
            if prior.empty:continue
            r=prior.iloc[-1]
            rows.append(dict(Snapshot_IST=clock,Last_event=r.timestamp_ist[11:19],Book_CEs_PEs_CEl_PEl=packed(r),
                             Realized=money(r.after_realized),Prior_quote_equity=money(r.after_equity),
                             Evidence=r.source_rows))
        return table(rows)
    typical=timeline('NIFTY','2026-06-29',['09:17:00','09:33:00','09:48:00','10:18:00','12:33:00','14:33:00','15:30:00'])
    reduction=timeline('NIFTY','2026-07-13',['09:17:00','09:33:00','09:48:00','09:50:01','09:53:01','09:59:01','14:33:00','15:30:00'])
    restart=timeline('SENSEX','2026-08-06',['09:24:40','09:24:41','09:24:42','09:24:44','09:24:49','09:24:52','09:31:00','09:31:48'])
    final=timeline('SENSEX','2026-10-08',['09:17:00','10:00:00','14:30:00','15:14:00','15:14:39','15:14:41','15:14:43'])
    taildone=tails[~tails.open_at_export_end]
    carry_ends=sessions[sessions.phase.eq('preexpiry')&sessions.after_CE_short.add(sessions.after_PE_short).gt(0)]
    carry_coverage=(carry_ends.after_CE_long>=carry_ends.after_CE_short)&(carry_ends.after_PE_long>=carry_ends.after_PE_short)
    all4=w[w.phase.eq('preexpiry')&w.clock_type.eq('recurring17')]
    peaks=pd.read_csv(OUT/'playbook_quantity_peaks.csv')
    peakrows=[]
    for (u,role),g in peaks.groupby(['underlying','role']):
        r=g.loc[g.quantity.idxmax()]
        peakrows.append(dict(Index=u,Role=role,Observed_maximum=int(r.quantity),Base_units=number(r.base_units),
                             Cycle=r.expiry_date,Event=r.timestamp_ist,Meaning='Observed maximum, not configured cap'))
    risk_extrema=[]
    for (u,phase),g in e.groupby(['underlying','phase']):
        for name in ('delta','vega_one_point','gamma','theta_calendar_day','equity'):
            field='before_'+name;valid=g[g[field].notna()]
            if valid.empty:continue
            risk_extrema.append(dict(underlying=u,phase=phase,metric=name,valid_event_states=len(valid),cycles=valid.expiry_date.nunique(),
                minimum=float(valid[field].min()),maximum=float(valid[field].max()),
                minimum_event=valid.loc[valid[field].idxmin(),'timestamp_ist'],maximum_event=valid.loc[valid[field].idxmax(),'timestamp_ist']))
    from rank_trigger_probabilities import save_records
    save_records('playbook_observed_risk_extrema.csv',risk_extrema)
    expiry_missing=[dict(Index=r.underlying,Expiry=r.expiry_date,Status='No expiry-day fills; earlier flat' if pd.notna(r.final_short_flat_ist) else 'No expiry-day fills; residual short book')
                    for r in cycles.itertuples() if not ((sessions.underlying==r.underlying)&(sessions.expiry_date==r.expiry_date)&sessions.phase.eq('expiry')).any()]
    text=f'''# Algo 8 — Allocation, Entry, Exit and Risk Playbook

Research date: **27 October 2026**. Execution times are observed log event seconds
in **IST**, not independently certified exchange matching times. This report
reconstructs recorded operations; it does not supply a replacement alpha model.

## 1. Executive summary and nine direct answers

1. **Initial units:** ordinary pre-expiry 09:17 books usually hold **195 units
   per role in NIFTY and 60 in SENSEX**. Those are three observed base quantities
   of 65/20, not independently verified exchange lot definitions. Exceptions and
   expiry-only flat starts have different size.
2. **Subsequent size:** variable counts of mainly single-base-unit short orders.
   Common pre-expiry per-role modal weights start **3,2,3,1,4,1,2**. Actual windows
   differ substantially; no exact capital/risk-budget sizing formula is recovered.
3. **Cadence:** 17 recurring pre-expiry windows are strongly established, but
   they are not all activity and not an every-15-minute full-book replacement.
   Late inventory openings occur too; some are corrective reversals. Overall
   management is a mixture of scheduled and other recorded flow.
4. **Market conditions:** observed openings and recurring additions occur across
   lagged directional/choppy, rising/falling and range categories. The full
   eligible/no-entry calendar is unknown, so unconditional market independence
   is not established.
5. **Variables that demonstrably matter:** clock and actual active-book state
   explain much observed timing. Side exposure, strikes and quantities change
   with the book. No unique market threshold is shown to generate the decisions.
6. **Middle reductions:** selected short contracts, CE/PE allocations and wings
   are closed separately. Some losing covers follow adverse moves; some bursts
   show close/overshoot/neutralize mechanics. Exact stop versus trail versus
   combined-controller causes remain unresolved.
7. **Final liquidation:** a strong conditional late concentration occurs around
   **15:14 after 3 August**. It is not a universal all-leg deadline. Shorts and
   wings can finish seconds apart, early exits/re-entry occur, and residuals exist.
8. **Risk limits:** all 31 recorded carry books end with long quantities at least
   matching shorts on each right. ₹2 crore, 4% carry and 1% expiry capital stops are supplied
   wording. ₹200,000 is the arithmetic 1% reference, not a verified trigger.
   Protective positions and measured risk changes are observable; true margin,
   NAV, scope, reset and order-cancellation limits are not.
9. **Exact versus inferred:** quantities, cashflows and atomic book transitions
   are exact within the received-record convention. Intent, original allocation
   IDs, eligibility, decision timestamps and precise controller thresholds are
   not uniquely identified.

### Evidence audit

An independent accounting implementation processed **{audit['fills']:,} fills**,
**{audit['parents']:,} parent orders**, **{audit['cycles']} cycles** and
**{audit['sessions']} observed cycle-sessions**: 32 pre-expiry and 33 expiry.
It retains the full before/after contract book at **{audit['atomic_seconds']:,}
atomic event seconds**. Multiple events/orders in one session are not independent
trials. Net all fills sharing a second before declaring a flat state.

It independently agrees with **{audit['cached_minute_quantity_checks']:,}** cached
minute quantity snapshots and **{audit['independent_minute_pnl_checks']:,}** marked
P&L snapshots, including missing marks. Maximum P&L difference is
**{audit['maximum_legacy_pnl_difference']:.2g} rupees**. Reverse within-second
attribution can change realized versus unrealized P&L by up to
**{money(audit['maximum_reverse_tie_realized_difference'])}**, while net inventory
and cash remain unchanged.

Before-event preceding-quote equity is available in
**{audit['preceding_quote_equity_before_available']:,}/{audit['atomic_seconds']:,}**
seconds; full modeled Greeks in **{audit['greek_before_available']:,}/{audit['atomic_seconds']:,}**.
Missing legs are not zeroed. All market quotes used for event marks precede the
fill minute; after-event marks freeze that same price state. They are stale-price
estimates, not executable NAV. Some order-label minutes precede those quotes,
so an execution-state context is not automatically a pre-decision trigger input.
Window-level market tests use conservative completed candles before the window.

The reconstruction assumes zero inventory before each contract's first received
fill. It cannot establish export completeness, unseen positions, margin or
settlement. The export is treated as the study book; its raw tags do not identify
verified allocation ownership or certify that a single controller generated
every row. Source [Info.txt](Info.txt), [strong register on its dedicated branch](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/research/strong-findings/STRONG_FINDINGS.md),
[cover study](research/COVER_REENTRY_FINDINGS.md),
[controller study](research/DEEP_CONTROLLER_FINDINGS.md) and
[economic-candidate limitations](research/ALPHA_CANDIDATE_FINDINGS.md) were cross-checked.
The one-basket recipe in `alpha_highest_ranked_rulebook.json` is **not used as the
original strategy**: it omits the observed ladder and controller. This report
does not reproduce the earlier screenshot's March 2025–May 2026 backtest.

## 2. Initial-entry rulebook

**Paired entry:** 31/32 observed pre-expiry sessions first pair near 09:16, with
the nearest strike to the completed 09:15 close (NIFTY grid 50; SENSEX grid 100).
The initial shorts can comprise several parents, and wings have their own fills.
The four roles being present at 09:17 does not mean one atomic four-leg trade.
The first CE/PE short fills are in the same observed second on
**{int(ce_pe_lag.eq(0).sum())}/31 ordinary starts**, and within one second on
**31/31**. The first CE wing fill precedes its first CE short on **28/31**;
the first PE wing precedes its short on **30/31**. Each right's first wing and
short are within three seconds on all 31 ordinary starts. This describes first
fills, not completion of all hedge quantity or a proven margin-aware ordering rule.

**Important exception:** NIFTY 5 October first sells a **22450 CE, 65 units at
09:21:21**, buys **23150 CE, 65 at 09:21:24**, then first pairs **22600 CE/PE at
09:30:59**, 130 units each. Its 09:17 book is empty. Earlier references to a
09:30 “initial entry” describe the first pair, not the first exposure.

Ordinary 09:17 net-quantity distributions; excluded delayed-start session is
listed separately rather than allowed to create a zero-size standard:

{table(initial_rows)}

Initial seed wings and routine later hedges differ. NIFTY's first seed is near
±2000 (26/28 wings within 100); early SENSEX near ±4000 (21/22 within 200), later
observed SENSEX ±2000 (12/12 exact from 16 September). These are seed observations,
not exact every-order rules. A routine premium budget near 2.5% of each ATM leg
matches within one strike in about 92–95% of later pre-expiry observations, while
exact strike matching is only about half. Missing full-chain bid/ask quotes and
decision timing prevent uniquely recovering that selector.

Recorded flat-start expiry openings are a different size cohort:

{table(expiry_rows)}

No capital/margin formula follows from those quantities. In particular, larger
expiry starts do not justify scaling the ordinary pre-expiry seed. See
[initial role timestamps](research/outputs/playbook_initial_role_times.csv) for
every role's first event, label, strike and gross versus net 09:17 quantities.

## 3. Market-condition dependence analysis

### Candidate sessions and missing negatives

For each of the 35 logged expiries, take the preceding **stored continuous-index
session** as a bounded candidate. This yields 32 with recorded pre-expiry shorts
and three without. It is not a certified exchange/strategy eligible universe:

{table(miss)}

The 22 June candidate is outside the trade export's date range. For September 15,
September 11 is the preceding stored session; the absence of a September 14 file
is not, by itself, a verified holiday. The other missing pre-expiry histories
cannot be confidently labeled filter rejections or flat positions. Consequently
32/35 is an appearance rate on stored-session candidates, not a verified entry
probability or proof that all eligible sessions were traded.

### Fixed lagged categories

No indicator combination search was run. Prior-15-minute return uses fixed
±0.10% direction bounds; close-path efficiency <=0.30 is choppy, >=0.70 directional;
range <=0.15%, 0.15–0.35%, >0.35% defines small/medium/large. Completed bars before
each window are used; unavailable opening-period history stays unavailable.
Opening comparisons use only the first completed candle, available gap and the
**previous** session's body/range classification. A session's future trend is
never used to explain its opening.

Opening stored-session candidates by lagged prior-session body/range state:

{table(opening_rows)}

**Required market-state table:** recurring pre-expiry windows. Average quantity
is base units per short right; clock-centered quantity subtracts the June/July
per-clock baseline. “Observed sessions” is not a claim of full eligibility.

{table(market_rows)}

All 544 recurring windows contain fresh short inventory; 541 contain all four
opening roles. Entry presence therefore cannot distinguish a direction/chop
gate inside this selected panel. It also does not prove there is no gate outside
the observed sessions. Some nonrecurring windows are empty. Full tables include
range, active-book-conditioned rates and the number of sessions per cell.

Within-session later quantity contrasts after subtracting clock baselines:

{table(contrasts)}

The paired-session support is small and intervals do not establish a consistent
quantity rule from these market categories. Direction can accompany a side's
loss and reduction without being the criterion that authorized a new allocation.
In the prior corrected later expiry study, active-book quarter windows contain
new shorts on 175/184, versus 0/89 inactive windows. That conditional baseline
is stronger than a recovered range gate, but it borrows actual prior inventory
and is not an autonomous controller.

## 4. Allocation schedule and quantity model

The 17 recurring windows are {', '.join(WINDOWS)}. Their bounds are T−2 seconds
through T+3 minutes, exclusive. Opening measurement uses 09:15–09:17. At least
some old long/short inventory survives every recurring window; net short size
increases in 530/544. The complete retained/four-role/growth/Greek conjunction
holds in 529/544, not a universal full-book close/reopen rule.

**Quantity distribution table:** modal base units by role (CEs/PEs/CEl/PEl if
different), and CE-short min/median/max across observed sessions. Multiply base
units by 65/20 for actual quantities. These are distributions, not orders to trade.
Every role's full min/median/max/all tied modes is in the linked CSV.

{table(schedule)}

**Order granularity and cadence:** pure new-short parents, not independent
allocations or signals. Nominal windows here include opening and all quarter
hours 09:30–14:30, so this definition differs from the 17-window subset.

{table(flow_rows)}

All 41,421 incremental fills are whole multiples of the observed base unit.
Pre-expiry NIFTY has 2022/2032 single-base requested short parents; SENSEX has
2375/2375. Thus allocation size usually varies through the number of small
orders, not a continuously varying quantity in each request. A risk budget could
still determine that order count; integer granularity alone does not identify it.

Short CE/PE added quantities are equal in **443/544 windows (81.4%)**; all four
role additions are equal in only **433/544 (79.6%)**. Protection is frequent but
not always equal-sized or simultaneous. Fractional base units are not observed;
multiple roles/strikes and concurrent reductions can change net exposure.

Fixed small sizing comparisons, fit on June/July, checked in August and later
September/October (all already inspected history):

{table(size_rows)}

Replacement-only predicts the new short quantity equals intervening covers;
target restoration predicts the deficit to the previous post-window quantity.
Neither explains pre-expiry additions. Clock modes perform better but do not
recover exact per-date size. Expiry-window zeros can inflate size matching;
scores are limited to the same 17 slots, with coverage and cycles shown. The
old all-history template is not an exact size rule or a capital allocation model.

## 5. Position-by-position allocation examples

**Allocation table:** all quantities are units. Book columns are CEs/PEs/CEl/PEl.
After = before + opened − closed within the window. A flow is not assigned to
an invented original basket.

{table(allocation)}

The complete [fill ledger](research/outputs/playbook_fill_ledger.csv.gz) retains
strike, right, parent/source references, before/after contract quantities, opening
and closing components, cost and realized P&L. The
[atomic event book](research/outputs/playbook_event_book.csv.gz) contains full
before/after contract inventories, gross role quantities, net-call tail, frozen
payoff bound and available P&L/Greeks. Multiple activities can occur in one second.
Net CE/PE quantity means long units minus short units; it is not option Delta.

Allocation/decision time is unobserved. The parent “order label” is minute
resolution and may precede or even round after the event. It cannot substitute
for an order acknowledgement, trigger log or cancellation record. Inventory-
opening quantity is not automatically a newly intended strategy allocation.
One NIFTY long parent has a 10:30 candidate order label and first fill at
15:28:57 on 13 July. Its late execution cannot safely be attributed to a newly
observed 15:28 market trigger. The label itself remains an inferred timestamp.
Parent requested/total quantities repeat on child rows: sum incremental fills,
not repeated requested quantities. Parent lifecycle descriptors are retrospective
audit fields, not pre-decision predictive inputs.

## 6. Intraday exit and reduction rulebook

### Observable actions and an important execution distinction

Short covers, long sales, one-side completion, whole-short-book flat and full-book
flat are separately recorded. Cost/P&L is pooled by contract; FIFO/LIFO alternatives
do not recover unique original basket ownership. All displayed P&L is before costs.

**Exit table — NIFTY 13 July reductions at the original CE's exit times:**

{table(exit_rows)}

These initial CE shorts close while the initial PE and its hedge survive.
The 24050 CE reduction in the same timestamp group concerns a later allocation.
At 09:59:01 the original 24000 CE is gone, but other CE shorts remain: **contract
closure is not the same as closing the entire CE side**.
Observed price losses and adverse spot moves are compatible with loss control;
they do not identify a percentage threshold or prove the move caused the order.

The raw sequence also exposes rapid same-contract reversals. Define the
descriptive motif: close to zero, reopen opposite within ten seconds, neutralize
within sixty. The conservative subset requires the old sign for >=60 seconds
and opposite size no larger than the just-closed quantity. This was specified
after inspecting the 6 August example, not validated as an original instruction.

{table(revrows)}

On SENSEX 6 August, for example, an 79800 CE long sale at 09:24:42 is followed
by new short inventory in that same contract at 09:24:43, then buyback at 09:24:48.
Some short-cover buys similarly create temporary longs that are sold seconds
later. This is compatible with overlapping liquidation/cleanup controllers or
duplicate/queued requests; deliberate rapid trading is not excluded. It is
**not evidence that every temporary opening is a planned alpha allocation**.

Conservatively tagged parents remain a small subset. Removing them from already-
frozen stop predictions without refitting does not solve exit reconstruction:

{table(frozen)}

### Candidate trigger validation and negative examples

Earlier-selected named candidates on actual active-contract onset opportunities;
these are prior finite tests, not a new search. Exact-minute event precision/recall
and one-to-one ±2-minute precision/recall must not be interchanged:

{table(namedrows)}

The many false signals and missed exits rule out presenting these parameters
as original instructions. First-cover timing on inferred parent lots is a
different task from contract-onset event detection; its approximate 29% result
cannot be read as a general 29% strategy accuracy. Continued fills, rapid
reversals, trailing references, allocated risk and latent order intents remain
alternatives. An entire-book condition can coexist with separate-side controls.

The matched cover study also does not identify an independent re-entry rule:
NIFTY later expiry same-side entry within five minutes is 76/97 versus 52/97 controls, with similar
opposite-side activity; SENSEX is 75/113 on both sides. Only four/five cycles are
represented, matching is imperfect and strict support is tiny.

## 7. Final liquidation rulebook

**When additions stop:** 14:30 ends the established recurring ladder, not a
verified ban on later requests or fills. All 32 pre-expiry sessions have some
later short-inventory opening. Some are corrective; late options activity and
larger overlays also occur. No deterministic stop time for *planned* new
allocations can be inferred from opening-role fills alone. Candidate labels and
last new-short events are retained in the underlying tables.

The recorded cycles have 33 resolved final short-book zero times, including one
pre-expiry closure and three expiry-only flat starts. The older 29-cycle timing
result is specifically the resolved **carry-book** subset. Wider expiry closures:

{table(finalrows)}

Within the original carry subset after 3 August, **9/10 late (>=15:00) final
short closures are in 15:14**, not 90% of all exits. Across 29 resolved carry
closures, 27 are complete by 15:27:33. Pre-CAS late closes differ. Continuous cash
phases change on 3 August, while options continue to 15:40; the auction-risk rationale
is plausible context, not a proven algorithmic cause.

**Observed final-liquidation sequence — SENSEX 8 October:**

{table(sequence)}

The final shorts reach zero at 15:14:40; wings reach zero at 15:14:42. Roles sharing
an observed second cannot be ordered more finely from this export. Elsewhere
wings remain or a flat book subsequently reopens. There is no universally
verified hard flatten-all deadline.

No-expiry-fill cases must remain distinct:

{table(expiry_missing)}

NIFTY's September 1 cycle is already fully flat on August 31 at 14:46:36; NIFTY
September 29 retains recorded shorts without expiry fills. SENSEX July 30 retains
20 PE short units. Across all 35 cycles, 11 retain some recorded contract quantity;
expired residuals are not automatically live holdings after expiry, nor are they
assigned invented trades or settlement cashflows.

## 8. Risk-management hierarchy

**Risk table:** observed extrema and model exposures are not configured limits.

{table(risk)}

Observed atomic-book quantity maxima (large late overlays can dominate them):

{table(peakrows)}

Available prior-quote Delta, Vega, Gamma, theta and P&L extrema are exported in
`playbook_observed_risk_extrema.csv`, with valid-state/cycle counts. They are
model-dependent observations, not calibrated constraints or broker risk limits.

The 4%/1% wording comes only from Info.txt. It does not state an exact carry
denominator, allocation margin, mark scope, reference/reset, transaction costs,
order priority or post-stop re-entry policy. Simpler fixed ₹200,000 interpretations
and clock fallback, using the existing 12-cycle later comparison:

{table(scope_rows)}

The 5% material-reduction label is an analysis convention, not a strategy stop.
Opening proxies and minute quotes cannot prove an intratick stop was absent.
These scope failures do not disprove every possible implementation of the
supplied rule; they prevent declaring a uniquely recovered implementation.

### Allocation/risk interaction

Recurring additions mostly increase theta **and** short Vega/Gamma, so adding
wings does not mean the total batch lowers risk. Ordinary opening/carry books
remain short Vega. Matched expiry wing replacements often move inward and
increase Gamma protection; large late long adjustments generally reduce absolute
Vega. These are distinct net effects, not independent evidence of their triggers.

**Carry snapshot constraint:** all **{int(carry_coverage.sum())}/{len(carry_ends)}**
last observed pre-expiry books that still hold shorts have long CE quantity at
least equal to short CE quantity **and** long PE quantity at least equal to short
PE quantity. The remaining pre-expiry session is flat. This is a strong observed
end-book property, consistent with preparation for overnight carry. It does not
prove an explicit guard, exact margin budget, unique hedge mapping or continuous
intraday matching. The finite frozen payoff bound is not an MTM stop.

There are **{len(tails):,} observed negative-net-call-tail intervals** across all 35
cycles in the recorded option book. Median completed interval is
**{taildone.seconds.median():.0f} seconds**; **{int(taildone.seconds.gt(60).sum())}** exceed 60 seconds.
The longest is **{taildone.seconds.max():.0f} seconds**, on 16 October 15:15:45–15:38:11,
associated with the observed larger call-ratio flow. The frozen recorded book
has no finite upside payoff bound during such an interval. This is not a claim
of unlimited realized losses or a measured margin breach: active stops,
subsequent execution and unobserved holdings differ from holding a frozen book
to an arbitrarily high settlement. It demonstrates why long wings somewhere in
the book do not prove continuously matched terminal protection.

## 9. Best-supported controller state machine

States below describe observed operational structure, not original source code.
The trigger requesting risk reduction, eligibility and quantity budget remain
explicitly unresolved. Processes can overlap rather than run serially.

```mermaid
flowchart TD
    E[Calendar/session candidate: eligibility unknown] --> O[Initial role assembly]
    O --> A[Active short-option book with protection]
    A --> T[Recurring allocation decision window]
    T -->|Observed adds; quantity formula unresolved| A
    T -->|Observed empty optional/inactive windows| A
    A --> R[Selected contract or side reduction]
    R --> A
    A --> H[Protection addition or replacement]
    H --> A
    A --> P[Pre-expiry carry preparation: trigger unknown]
    P --> Q[Observed carry snapshot: long quantities cover short quantities]
    Q -->|Expiry-session management| A
    A --> L[Liquidation requested: trigger unresolved]
    L --> C[Partial fills / possible reversal and cleanup]
    C --> S[Short book flat; wings or requests can remain]
    S --> F[Recorded full book flat]
    S -->|Observed later opening flow| A
    F -->|Observed later opening flow; authorization unknown| A
    B[Hypothesized risk-limit breach] -. Not observed as a signal .-> R
    B -. Alternative route .-> L
    K[Conditional late-time fallback hypothesis] -.-> L
```

| Transition | Preconditions | Trigger/action and quantity | Risk check / next state | Evidence / confidence |
| --- | --- | --- | --- | --- |
| Candidate→initial assembly | Logged expiry/session, no prior recorded exposure | Usually09:16, ATM pair and wings; modal195/60 per role | Original eligibility/capital check unknown; active book |31/32 timing; high action, inferred authorization |
| Active→scheduled adds | Recurring window; prior exposure usually remains | Several base-unit orders; selected new strikes near current ATM | Batch often increases short risk; active book |544windows,529joint; high structure |
| Active→other opening flow | Some outside-window executions | Could be allocation, replacement, late overlay or cleanup | Intent/risk budget unknown |Source-linked fills; mixed confidence on purpose |
| Active→partial reduction | Specific short inventory exists | Buy some contracts; sell some protection | Opposite allocations may survive |Exact quantities; stop/target trigger unresolved |
| Active→wing refresh | Existing long protection | Sell old/buy another strike; matched pairs inferred | Inward changes often add Gamma protection |High effect, uncertain unique association/trigger |
| Active→liquidating | Large reduction burst | Close many shorts/wings, often mixed processing | Whole-book cause not logged |Observed; risk/time alternatives |
| Liquidating→temporary reversal→neutralize | Prior same-contract exposure just closed | Opposite reopening and flattening within seconds | Candidate cleanup, not assumed new alpha allocation |Finite observed motifs; intent unresolved |
| Short-flat→full-flat | Remaining long options | Dispose wings or record residuals | No invented settlement |Exact recorded sequence where complete |
| Flat→active again | New recorded opening flow | Can be candidate-labeled after first flat | Permanent lock/cancellation not established |SENSEX6August example; high existence, unknown authorization |
| Risk breach→reduction/liquidation | Supplied rule candidate | Which scope/threshold/reference applies is unknown | Cannot assert a simulated breach as observed |Unresolved signal |

## 10. Representative event timelines

Book order is **CE short / PE short / CE long / PE long**, in units. Snapshots
include events **strictly before** the displayed time. The P&L mark belongs to
the last event's preceding quote, not necessarily a fresh quote at the snapshot.
These sessions were chosen to illustrate distinct known operations, not to
estimate a win rate or claim representative profitability.

### A. Ordinary pre-expiry ladder — NIFTY 29 June, expiry 30 June

{typical}

The initial roles are established, quantities accumulate through later windows,
and the book is carried. “Typical” here refers to the ordinary opening/ladder
structure, not a claim that this day's every adjustment is modal.

### B. Substantial separate-side reductions — NIFTY 13 July, expiry 14 July

{reduction}

Initial 24000 CE/PE shorts coexist with subsequent 24050 CE/PE shorts. The original
CE closes in 65-unit pieces at 09:50/09:53/09:59 with its 26000 CE protection; the
original PE/22000 PE wing persists. Several overlapping allocations are present;
these quantities do not identify a single basket-level stop.

### C. Liquidation, rapid reversals and later entry — SENSEX 6 August

{restart}

The short book first reaches zero at 09:24:40; opposite-direction reversals in
some just-closed contracts are neutralized by 09:24:48–51. At 09:30:58, recorded
new 78900 CE and 78700 PE shorts of 20 each appear with 09:30 labels, then are covered at
09:31:47. These are different-strike shorts and no matching fresh long protection
is recorded in that final restart. New authorization, uncancelled scheduler
dispatch and flattening-controller interaction remain competing explanations.

### D. Expiry late final liquidation — SENSEX 8 October

{final}

The final observed sequence ends shorts before the last wings by two seconds.
The index's later closing/settlement movement must not be used to explain an
earlier exit decision.

## 11. Validation results and counterexamples

- The full research suite passes **190 tests**, including 13 new independent-
  accounting, timestamp-boundary, missing-price and reversal-sequence checks.
- Independent arithmetic and cached checks are reported in section 1; all fill
  sources are retained. Full books and pooled cost reconcile at every event.
- Quantity modes fit June/July, validate August and check September/October.
  Prior research has already inspected these dates; this is chronological
  consistency checking, not an untouched independent test.
- Market comparisons use fixed thresholds, explicit missing history and paired
  session counts. Some cells have only two to six sessions. No future session
  outcome labels a pre-entry trend or chop state.
- Empty optional/inactive windows, three no-recorded-entry calendar candidates,
  missing marks and candidate trigger conditions without action remain visible.
- Delayed one-sided 5 October entry, pre-expiry 31 August closure, residual 29 September
  and 30 July books, post-flat 6 August flow and the late 15:36:54 closure are explicit
  counterexamples to overly simple operational rules.
- Rapid reversals are tagged descriptively; candidate intent is not forced into
  “allocation” or “error.” Removing the conservative subset barely changes the
  already-frozen exit score. No new indicator or threshold grid was run.
- There are no contemporaneous bid/ask quotes, original strategy intent tags,
  broker margin/NAV or complete pending/cancel records. P&L here is before
  fees/slippage, and the report does not make an economic-alpha claim.

## 12. Known, inferred and unresolved rule-confidence table

{table(ruleconfidence)}

The narrowest defensible rulebook is **scheduled accumulation in small integer
order units, near-current-ATM short exposure with distinct protection routines,
selected reductions and a separate liquidation/processing phase**. The same
normalized timing/weight structure appears across indices, but size exceptions,
wing configuration, expiry-only starts and risk/re-entry behavior differ. A
common framework does not establish identical complete controllers.

## 13. Remaining evidence needed for exact rules and reproduction

To distinguish competing implementations, prioritize **original order intent,
allocation/module IDs, submit/ack/modify/cancel events and risk-reference logs**.
These would distinguish planned new allocations from over-closing, queued fills
and corrective actions. A certified eligible-session calendar and no-trade
records are needed to infer entry filters. Broker positions, historical margin,
funding and account NAV are needed for true capital constraints. Tick bid/ask and
decision timestamps would distinguish intrabar stops from trails and price
selection. Settlement records resolve residuals. Complete-chain/new untouched
data are relevant to economic validation, not a substitute for those controller
records. Do not infer missing values or request credentials merely to fill a table.

Reproduce with `reconstruct_operational_book.py`, `audit_operational_allocations.py`,
`audit_execution_reversals.py`, then `write_operational_playbook.py`, under
`research/`. Dependencies are in `research/requirements-deep-controller.txt`.
Independent input fingerprints and coverage are in
[book audit](research/outputs/playbook_book_audit.json). Full outputs include:

- [All fill-level changes](research/outputs/playbook_fill_ledger.csv.gz),
  [atomic full books](research/outputs/playbook_event_book.csv.gz),
  [cycle final roles](research/outputs/playbook_cycle_books.csv),
  [session end inventories](research/outputs/playbook_session_end_books.csv).
- [Allocation windows](research/outputs/playbook_allocation_windows.csv),
  [all role quantity distributions](research/outputs/playbook_quantity_distributions.csv),
  [chronological sizing checks](research/outputs/playbook_size_model_checks.csv),
  [cadence/order granularity](research/outputs/playbook_cadence_summary.csv).
- [Calendar candidates](research/outputs/playbook_calendar_candidates.csv),
  [opening market states](research/outputs/playbook_initial_market_states.csv),
  [window market states](research/outputs/playbook_market_state_windows.csv),
  [fixed state/size contrasts](research/outputs/playbook_market_size_contrasts.csv).
- [Rapid reversal motifs](research/outputs/playbook_rapid_reversal_motifs.csv),
  [candidate parent flags](research/outputs/playbook_reversal_parent_flags.csv),
  [call-tail intervals](research/outputs/playbook_negative_call_tail_intervals.csv),
  [observed quantity peaks](research/outputs/playbook_quantity_peaks.csv).

### Direct answers, revisited

1. **Initial size:** usually 195/60 per role at ordinary pre-expiry starts;
   exceptions, delayed assembly and expiry-only starts are separately measured.
2. **Added size:** variable numbers of mostly65/20-unit requests; the modal clock
   sequence is descriptive, and no exact sizing/capital formula is identified.
3. **Cadence:** strong recurring clock windows plus other allocation, adjustment
   and processing flow; no verified 50-minute rule or universal quarter reset.
4. **Different markets:** entries appear across lagged market categories; missing
   eligibility/no-trade labels prevent an unconditional claim.
5. **Variables altering decisions:** time and actual book state are strongly
   associated. No uniquely identified market or risk threshold is recovered.
6. **Intermediate exits:** selected shorts/wings and sometimes the entire book;
   exact loss/trail/profit/time/controller causes remain unresolved.
7. **Final sequence/deadline:** conditional 15:14 late concentration; shorts/wings
   can finish separately, early/re-entry/residual exceptions exist; no universal
   all-flat deadline is verified.
8. **Risk limits:** same-right long quantities cover shorts in all 31 carry books;
   supplied 4% carry / 1% capital stops and measured protection/exposures;
   scope/reset/action and broker capital/margin limits are not established.
9. **Exactness:** recorded arithmetic and transitions are recoverable; original
   signals, allocation ownership and risk instructions require additional evidence.
'''
    (ROOT/'ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md').write_text(text)


if __name__=='__main__':main()
