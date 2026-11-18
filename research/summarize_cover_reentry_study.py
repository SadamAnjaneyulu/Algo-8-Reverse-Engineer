"""Write the state-transition assessment and descriptive comparisons."""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from audit_strike_hedge_rules import OUT,ROOT
from rank_trigger_probabilities import save_records
from study_cover_reentry_controls import bootstrap_difference


def table(rows):
    keys=list(rows[0])
    return '\n'.join(['| '+' | '.join(keys)+' |','| '+' | '.join('---' for k in keys)+' |']+
                     ['| '+' | '.join(str(r[k]) for k in keys)+' |' for r in rows])


def percent(value):return f'{100*value:.1f}%'


def plot(summary):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'algo8-matplotlib'))
    os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'algo8-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for column,u in enumerate(('NIFTY','SENSEX')):
        rs=summary[summary.design.eq('post')&summary.phase.eq('expiry')&summary.split.eq('evaluation')&summary.underlying.eq(u)]
        h=[1,5,10];values=[rs[rs.outcome.eq('entry'+str(i))].iloc[0] for i in h]
        axes[0,column].plot(h,[r.treated_rate*100 for r in values],'o-',label='After cover minute')
        axes[0,column].plot(h,[r.control_rate*100 for r in values],'o-',label='Matched no-cover minute')
        axes[0,column].set_title(f"{u}: {values[0].matched} pairs, {values[0].cycles} cycles")
        axes[0,column].set_ylim(0,100);axes[0,column].set_ylabel('Fresh same-side entry (%)');axes[0,column].legend(fontsize=8)
        difference=np.array([r.difference*100 for r in values]);low=np.array([r.weekly_bootstrap_lower*100 for r in values]);high=np.array([r.weekly_bootstrap_upper*100 for r in values])
        axes[1,column].errorbar(h,difference,yerr=[difference-low,high-difference],fmt='o-',capsize=4,color='#276a54')
        axes[1,column].axhline(0,color='gray',lw=1);axes[1,column].set_ylabel('Matched difference (percentage points)')
        axes[1,column].set_ylim(-13,33)
        axes[1,column].set_xlabel('Minutes after completed cover minute')
        for row in (0,1):axes[row,column].set_xticks(h);axes[row,column].grid(alpha=.15)
    fig.suptitle('Later expiry sessions: cover-associated entry timing\nMatched associations; remaining activity imbalance and limited cycles')
    fig.savefig(OUT/'cover_reentry_comparison.png',dpi=160)
    svg=OUT/'cover_reentry_comparison.svg';fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n');plt.close(fig)


def main():
    summary=pd.read_csv(OUT/'cover_reentry_matched_summary.csv');raw=pd.read_csv(OUT/'cover_reentry_raw_forward.csv')
    rows=[]
    for r in raw.to_dict('records'):
        rows.append(dict(Index=r['underlying'],Phase=r['phase'],Cover_minutes=r['cover_minutes'],
                         Entry_within_5min=f"{r['next_short_within300s']}/{r['cover_minutes']} ({percent(r['next_short_within300s']/r['cover_minutes'])})"))
    primary=summary[summary.design.eq('post')&summary.split.eq('evaluation')&summary.outcome.eq('entry5')]
    matched=[dict(Index=r['underlying'],Phase=r['phase'],Matched=f"{r['matched']}/{r['eligible_cover_onsets']}",Cycles=r['cycles'],
                  After_cover=percent(r['treated_rate']),Control=percent(r['control_rate']),Difference_pp=f"{100*r['difference']:+.1f}",
                  Weekly_interval_pp=f"[{100*r['weekly_bootstrap_lower']:+.1f}, {100*r['weekly_bootstrap_upper']:+.1f}]") for r in primary.to_dict('records')]
    outcomes=summary[summary.design.eq('post')&summary.split.eq('evaluation')&summary.phase.eq('expiry')&summary.outcome.isin(['entry1','offtimer_entry5','opposite_entry5','both_rights_entry5','later_label_entry5','backward_entry5'])]
    specifics=[dict(Index=r['underlying'],Outcome=r['outcome'],After_cover=percent(r['treated_rate']),Control=percent(r['control_rate']),Difference_pp=f"{100*r['difference']:+.1f}") for r in outcomes.to_dict('records')]
    strict=summary[summary.design.eq('post_strict_activity')&summary.split.eq('evaluation')&summary.phase.eq('expiry')&summary.outcome.eq('entry5')]
    stricter=[dict(Index=r['underlying'],Matched=f"{r['matched']}/{r['eligible_cover_onsets']}",Coverage=percent(r['matching_coverage']),
                   After_cover=percent(r['treated_rate']),Control=percent(r['control_rate']),
                   Weekly_interval_pp='Too few weeks' if pd.isna(r['weekly_bootstrap_lower']) else f"[{100*r['weekly_bootstrap_lower']:+.1f}, {100*r['weekly_bootstrap_upper']:+.1f}]") for r in strict.to_dict('records')]
    pred=pd.read_csv(OUT/'cover_reentry_prediction_evaluation.csv');p=pred[pred['sample'].eq('later_check')]
    predictive=[dict(Index=r['underlying'],Phase=r['phase'],Inputs=r['variant'],Log_loss=f"{r['log_loss']:.4f}",
                     Brier=f"{r['brier']:.4f}",Average_precision=f"{r['average_precision']:.4f}") for r in p.to_dict('records')]
    probability=pd.read_csv(OUT/'cover_reentry_prediction_probabilities.csv.gz')
    key=['underlying','phase','expiry_date','date','clock','option_type','target']
    wide=probability.pivot(index=key,columns='variant',values='probability').reset_index()
    increments=[]
    for (u,phase),rs in wide.groupby(['underlying','phase']):
        truth=rs.target.to_numpy()
        def loss(p):
            p=np.clip(p,1e-12,1-1e-12)
            return -(truth*np.log(p)+(1-truth)*np.log(1-p))
        differences=loss(rs.plus_cover.to_numpy())-loss(rs.base.to_numpy())
        pairs=[dict(week='-'.join(map(str,tuple(pd.Timestamp(e).isocalendar())[:2]))) for e in rs.expiry_date]
        low,high=bootstrap_difference(pairs,differences)
        increments.append(dict(underlying=u,phase=phase,rows=len(rs),log_loss_change=float(differences.mean()),weekly_lower=low,weekly_upper=high))
    save_records('cover_reentry_prediction_increment.csv',increments)
    incremental_rows=[dict(Index=r['underlying'],Phase=r['phase'],Log_loss_change=f"{r['log_loss_change']:+.4f}",
                           Weekly_interval=f"[{r['weekly_lower']:+.4f}, {r['weekly_upper']:+.4f}]") for r in increments]
    balances=pd.read_csv(OUT/'cover_reentry_match_balance.csv')
    primary_balance=balances[balances.design.eq('post')&balances.split.eq('evaluation')&balances.phase.eq('expiry')]
    balance_rows=[]
    for u,g in primary_balance.groupby('underlying'):
        worst=g.loc[g.standardized_difference.abs().idxmax()]
        balance_rows.append(dict(Index=u,Largest_absolute_SMD=f"{abs(worst.standardized_difference):.3f}",Feature=worst.feature))
    counts=json.loads((OUT/'cover_reentry_summary.json').read_text())
    text=f'''# Does covering trigger a new entry? Controlled Algo 8 study

**There is a NIFTY expiry-day association, but no recovered general cover-to-
re-entry trigger.** It also predicts entries on the opposite side, matches are
drawn from only four later NIFTY cycles, stricter matching has very limited
support, and adding cover history barely changes predictive performance.
SENSEX does not replicate the five-minute later-sample association.

This executes the first recommended experiment in the supplied assessment.
The initial specification is `COVER_REENTRY_TEST_PLAN.md`; the balance-driven
strict sensitivity is explicitly recorded as a later amendment. Data through
31 August set scaling and model fits; later dates were already inspected in
earlier research and are not untouched independent validation.

## 1. Correct the probability question

The original counts—136/2032 versus 1802/4210 NIFTY and 165/2375 versus
2613/4786 SENSEX—measure **P(recent cover | fresh short parent)**. They do not
say that 42.8% or 54.6% of covers cause another entry.

At the cover-minute level, the forward descriptive question gives:

{table(rows)}

The units differ from the original parent-order table: multiple covers in one
minute are collapsed. This is not a numerical reciprocal. Simultaneous entries
are included in this descriptive table, and final shutdowns count too. A single
late SENSEX cover after 15:35 cannot have five observable minutes before 15:40
and is excluded here. The matched experiment below separates the time ordering.

## 2. What was matched

A landmark T is the boundary after the cover minute completes. A treatment
requires a cover in [T−1m,T), preceded by five quiet cover minutes. The forward
outcome is a fresh same-side short-parent first fill in **[T,T+5m)**. This starts
strictly after the completed cover minute, not necessarily exactly five minutes
after its first fill. Horizons one and ten minutes are sensitivities.

Both treated/control landmarks require an active same-side short before the
previous minute and some short book still active at T. Full-flat events and
missing prior state are recorded as exclusions, not negative outcomes. The
common clock band is 09:16–15:04, leaving all horizons before 15:15.

Match within the **same index, expiry cycle, date and option right**, with the
same quarter-hour phase, identical timer-overlap seconds in the next five
minutes, and no more than 45 minutes' time difference. Nearest controls use
remaining quantities, premium-loss/equity state, Greeks, IV, spot returns,
range and recent entry activity, scaled on earlier rows only. Controls have no
cover in the preceding six minutes. They may cover later; that crossover is
reported rather than removed using future knowledge. Outcomes never select
the match. Controls can be reused; uncertainty resamples expiry weeks.

Primary matching on remaining inventory asks whether cover history adds
information **given the current book**. It may condition away a mechanical
quantity-replacement pathway. The pre-cover-state sensitivity is reported
separately; neither comparison identifies causation.

## 3. Later five-minute comparisons

{table(matched)}

NIFTY expiry: **76/97** cover landmarks versus **52/97** controls contain a fresh
same-side short in the next five minutes. The 97 matches cover 97/118 eligible
onsets (82.2%), but only **four cycles**, with 90 distinct controls. SENSEX has
**75/113 on each side of the comparison**, across five cycles and 108 distinct
controls. Pre-expiry results do not support a common cover-driven entry rule.

![Cover-associated entry timing](outputs/cover_reentry_comparison.png)

## 4. The NIFTY effect is not specific to the covered side

{table(specifics)}

NIFTY's opposite-side effect is at least as large as its same-side effect.
Both rights receive entries in 73/97 post-cover windows versus 48/97 controls;
these entries need not be simultaneous, equal sized or at one strike. This is
compatible with portfolio/allocation activity and does not isolate a rule that
reopens just the stopped leg. Entries also precede these covers more often than
they precede controls, warning of a pre-existing trading burst.

Removing physical timer-window entries leaves a NIFTY association, but this
does not fully remove delayed timer submissions. Candidate order-label checks
exclude already-labeled pending fills from the later-label outcome; order labels
are minute-resolution inferred timestamps, not verified submission records.

## 5. Balance and common support limit the conclusion

Primary match balance still shows material recent-entry/range differences:

{table(balance_rows)}

Therefore the primary controls should not be called perfectly equivalent.
The stricter diagnostic requires exact recent-entry zero/nonzero states,
tighter market/activity calipers and mean distance <= 0.5:

{table(stricter)}

The 80% NIFTY treated rate here is only 12/15 cases, with a 60% control rate and
12.7% matching coverage; it is not an 80%-recovered trigger. The interval includes
no difference. SENSEX has three matched cases, insufficient for a weekly interval.
Tightening balance sacrifices common support. Four cycles and retrospectively
inspected data cannot establish an independent general mechanism.

## 6. Does cover history improve prediction beyond known state?

Fixed regularized logistic models use clock/timer, current inventory, recent
entries, side and market/risk features. The second model adds prior-minute
cover, onset, recent cover quantity and time since cover. Earlier validation
holds complete cycles apart; later fits/thresholds are frozen. Lower log loss
and Brier are better; average precision is not accuracy or a win rate.

{table(predictive)}

Changes are small and inconsistent: NIFTY expiry log loss worsens slightly;
SENSEX improves slightly. Positive change below means worse prediction:

{table(incremental_rows)}

NIFTY expiry's weekly interval is just above zero, indicating deterioration in
this fitted comparison; the other intervals include zero. None establishes
a general predictive improvement. This limited model comparison does not prove cover history has
no possible predictive information; it fails to establish a broad standalone
cover-triggered controller. A five-minute future-entry task is also different
from exact-minute order matching or exit-rule recovery.

## 7. What changes in the working hypothesis

The working architecture remains timed protected short-volatility allocations
with separate risk management. The new process lead is **coordinated activity
around some NIFTY expiry covers**, potentially allocation reseeding or processing
bursts. It is not a verified universal same-side replacement rule, and it does
not transfer automatically to SENSEX. No new 80–90% original trigger or economic
alpha is established. No trading rule or strong-register rate is promoted from
these comparisons.

Other recommendations in the supplied assessment have existing partial work:

- FIFO/LIFO first-reduction/closure studies and entry-module/rank stops:
  `DEEP_CONTROLLER_FINDINGS.md`. Exact exit recovery remains low; do not treat
  the assessment's older 20–38% cohort range as one universal latest score.
- Hedge cost/distance/Greeks timing search and inward-replacement effects:
  `DEEP_CONTROLLER_FINDINGS.md`; effect and trigger remain distinct.
- Overnight time/forward/IV attribution: `IV_THETA_HYPOTHESIS_FINDINGS.md`;
  24/31 carry books fit completely, not an unbiased full-lifecycle attribution.
- Earlier-selected autonomous NIFTY recipe: `outputs/alpha_highest_ranked_rulebook.json`.
  It is already frozen in the economic study; a genuinely untouched complete-chain
  period is not present in the inspected logs. Resplitting them cannot create one.

## Reproduction and evidence

Run `python research/study_cover_reentry_controls.py`, then
`python research/summarize_cover_reentry_study.py`. Dependencies are in
`requirements-deep-controller.txt`. This targeted experiment uses existing
local market/state data and execution records; it makes no broker requests.

Outputs include raw forward rates, all landmarks, matched controls and unmatched
cases, match balance, phase/index/horizon comparisons, model predictions and
weekly loss increments. Boundary and matching tests are in
`test_cover_reentry_controls.py`. Inventory remains conditional on the received
logs and the zero-initial-inventory convention; stable parent role labels and
candidate timestamps do not reveal original strategy allocation IDs.
'''
    plot(summary)
    (ROOT/'research/COVER_REENTRY_FINDINGS.md').write_text(text)


if __name__=='__main__':main()
