# Reactive pairs — trigger and band identification: pre-registered plan

*Written before any of the tests below were run. Investigation only: no engine/simulator change, no new alpha. In-sample (35 live cycles, 363 reactive pairs on D-1, not a holdout).*

## Question (from the user)
1. Is a Donchian-type channel the real indicator, and which window (60 min or another)?
2. What actually triggers each reactive pair (why do only ~17% of completed-bar breakouts have one)?

## What can and cannot be decided with this data (stated before testing)
* Data: minute closes of the spot, minute open/close/volume per option strike, order ledger with seconds. No spot high/low, no ticks, no bid/ask, no source code.
* "Donchian is the real indicator" can **never be proved** from behaviour: equivalent formulations (position in N-minute range, N-minute breakout, stochastic %K) give the same signal here. The achievable goals are (a) to **rule alternatives out**, (b) to **narrow the window** or show it cannot be narrowed, (c) to find a **state variable that separates firing from non-firing breakouts**, or show that none exists in the data.

## Locked setup
* Panel A (seconds): the existing 363 events and 10,890 control seconds (`bl_act_table`, `bl_ind_table`), live-spot proxy (diagnostic: uses the current minute close).
* Panel B (minutes, new): every D-1 cycle-minute 10:30–15:15 of the 35 cycles with at least 60 minutes of history; label = at least one reactive pair in that minute. All features at the start of the minute use **completed bars only** (causal). A separate, flagged look-ahead variant uses the current minute's close.
* Metrics: AUC (events vs controls, or pair-minutes vs other minutes) with cluster bootstrap over cycles (1,000 draws), leave-one-cycle-out (LOCO) models. No metric is added beyond those listed.

## Blocks
**A. Band definition and window (Panel A).** Candidates: rolling channel of N = 10, 15, …, 120 minutes (step 5 from 20); **expanding** channel since 09:15; both edges together and **upper-edge and lower-edge events separately** (a symmetric rule should give the same N on both). Scores: activation AUC of the absolute position; ratio of share beyond the band (events / controls); **margin distribution** (distance beyond the band in strikes steps: if the trigger is the crossing itself, events should sit closer to the boundary than control seconds that are also beyond the band); log-likelihood of a hazard model with a step at the boundary. Decision rule: N is "identified" only if its AUC is above every N that differs by ≥ 10 minutes with a paired-bootstrap CI excluding 0 **and** upper/lower edges agree; otherwise "plateau". Expanding-since-open "beats" rolling only if it exceeds the best rolling AUC with a CI excluding 0.

**B. Direction at the edge (Panel A).** Hit rate of strike = nearest(live) + step × sign(position) among events beyond the band, versus events not beyond it.

**C. What separates firing from non-firing breakouts (Panel B).** Population: minutes with a completed-bar close beyond the previous 60 closes (N = 60, also N = 45 and 90 as checks). Feature blocks (all causal at the minute start):
* edge: depth beyond the band (steps), run length of the breakout (minutes), side, band width (steps), band-position of the previous bar;
* clock: minutes since 10:30, schedule version;
* order activity: ages of the last pair / reactive pair / body sell / buy-back / other-module order, counts so far today;
* book state: net short lots (CE, PE), net short lots at the target strike on each leg, whether the target strike pair is already open, centre of the short book relative to spot;
* option state: premium (close) of the target strike CE+PE, ratio to the ATM straddle, volume at the target strike and relative to its own trailing mean;
* market: |1-min| and |5-min| spot change, 30-minute realised volatility of 1-minute changes.
Model: logistic regression and gradient boosting, LOCO over cycles; paired cluster-bootstrap AUC differences of each block added to the edge-only model. A block "explains non-firing" only if it adds ≥ 0.03 AUC with a CI excluding 0 and keeps that sign in both halves of the cycles.

**D. Episode view (Panel B).** Episodes = runs of consecutive completed-bar breakout minutes (N = 60). Label = a pair within the first 3 minutes of the episode. Same blocks at the episode start; same decision rule.

**E. Refractory / state machine.** Pair hazard in breakout minutes as a function of minutes since the last reactive pair, pairs so far that day (0, 1, 2, 3+), and the side of the last pair vs the current breakout side. A refractory rule is "supported" if hazard is lower within the first K minutes after a pair by a ratio with a CI excluding 1.

**F. Simplest rule.** Depth-≤ 3 decision tree on Panel B (LOCO); report precision and recall for pair-minutes. A rule counts as "found" only if LOCO precision ≥ 0.5 **and** recall ≥ 0.5 of all pair-minutes (causal version). The look-ahead version is reported separately to show how much of the gap is intra-minute.

## Evidence rules
Observed / Inferred / Unresolved / Not testable. Selection among many candidate N and features is stated; parameter selection for rolling N uses alternating cycle halves as before. No threshold or filter is introduced to improve any metric.

## Not testable here (stated in advance)
Tick-level crossing time; true intraday high/low (Supertrend, SAR, ATR from ranges); order-book/bid-ask; any variable not in the minute data or the ledger; the calculation frequency of the algorithm.
