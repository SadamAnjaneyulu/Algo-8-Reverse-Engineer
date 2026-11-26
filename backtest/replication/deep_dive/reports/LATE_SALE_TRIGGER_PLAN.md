# What triggers the late D-1 sales? Five candidate explanations: pre-registered plan

*Written 2026-11-24 **after** a purely descriptive look at the order-log columns (listed under "Already seen") and **before** any test below. Exploratory, development cycles only; the frozen rule is untouched. Every test is counted; Benjamini-Hochberg (10%) over the 24 primary tests.*

## Already seen (descriptive, not tests)
* The log has **no decision time** (`t_dec` empty). All orders are marketable limits (limit below the average fill for sells) that fill within about a second, so the fill time is effectively the **placement time**: the lateness is real, not a resting-order artefact.
* The earlier decode labels each sell `slot_minute` (minute 09:16 + 15k), `minute_before_slot`, `roll_sell` or `other`. Of 193 late sales (≥ 15:15): 167 `other`, 20 `minute_before_slot`, 5 `slot_minute`, 1 `roll_sell`. The grid covers 2 of every 15 minutes (13%); 25/193 = 13%.
* The engine timetable's last entry is 14:45:00 (19,740 s after 09:16:00): **nothing in the timetable is later than 14:45.**

## Events
A late sale is an order with `open_short`, fill time ≥ 15:15:00. An **event** is a cluster of orders in one cycle with gaps ≤ 10 s. An event is a **pair** if it holds both CE and PE legs, otherwise **solo**. Window for statistics: 15:15:00–15:40:00. Primary sample: post-auction cycles (NIFTY 16 Oct excluded); pre-auction reported separately.

## The five candidate explanations
| ID | Explanation | Test (all against a stated null) |
|---|---|---|
| **S** | **A scheduled pair / timer** | **S1** cross-cycle coincidence: number of event pairs from different cycles within ±3 s of the same clock time; null = each cycle's event times circularly shifted by a uniform random amount inside the window (keeps intra-cycle structure), 5,000 draws. **S2** second-of-minute: share of events starting in seconds :00–:05 vs 5/60 (exact binomial); and a chi-square over six 10-second bins. **S3** proximity to the 30-minute candle end (15:30:00 ± 60 s) vs the window share (binomial). **S4** phase of the event start relative to the 09:16:00 grid for periods of 300, 900 and 1,800 s (Rayleigh tests). |
| **P** | **Completing or adjusting a paired call-and-put process** | **P1** pair share vs null: each cycle's PE event times circularly shifted independently of CE (5,000 draws). **P3a** pair-ledger completion: replay the day's sales into a first-in-first-out ledger of unmatched CE and PE lots; a sale **completes** a pair when the other side's unmatched queue is non-empty; share of late sales that complete vs the share expected for the cycle's side mix. **P3b** hazard AUC of the oriented *sold-lot* deficit (other − same, cumulative sales today irrespective of stops). **P4** replacement: share of late sales preceded within 10 minutes by a same-side cover (a stop); null = the cycle's covers circularly shifted. *P2 (anatomy: lots per leg, same-strike share, inter-leg gap) is descriptive.* |
| **R** | **Extra premium, with the overnight lump as protection** | **R1** package counterfactual per cycle: remove the late sales **and re-size the lump** with that cycle's realised lump ratio (lump lots ÷ heavy-side shorts at lump time), keeping the lump's side and strike; compare premium collected, theta, worst D0-gap loss and |delta|. Supported if theta rises in ≥ 70% of cycles and the median package gap loss is no worse than 5% of the baseline worst gap loss. **R2** premium target: cycle regression of late premium on pre-15:15 premium (a target would give slope ≈ −1). **R3** lump timing: the share of late events in the 120 s before the lump order vs the null (event times circularly shifted). |
| **O** | **Another portfolio-state condition** | **12 new hazard features** (stratified AUC within (cycle, side), curveball null as before): oriented sold-lot deficit; net-lot deficit (re-test); same-side cover lots in the last 5 min; other-side cover lots in the last 5 min; book MTM P&L; MTM change over 15 min; decay of held same-side shorts (price now ÷ average entry); shortfall of same-side net shorts against their day peak; minutes since the last sale; minutes since the last cover; 15-minute change of the ATM straddle; ATM straddle against its 09:20 level. |
| **E** | **An execution / order-management rule** | Descriptive plus two tests: **E1** burst structure: orders per event, inter-order gap, lots per leg (is the event a queued list sent in sequence?); **E2** limit-price rule: limit ÷ first fill for late vs earlier sales (a fixed buffer would mean one execution rule). No trigger is claimed from E alone. |

## Event labelling and coverage (the answer to "find the trigger")
Each late event gets every label whose rule it satisfies: **PAIR**, **COMPLETION** (P3a), **REPLACEMENT** (P4), **LUMP-COUPLED** (within 120 s before the lump), **LADDER** (matched by the frozen futures ladder, gate 5, ±1 minute, as in the earlier framework), **GRID** (start within :00–:05 of a 09:16 + 15k minute). Coverage = share of events with at least one label, compared with the coverage obtained when event times are circularly shifted (chance coverage). A label **counts as an explanation** only if it is BH-supported **and** its coverage exceeds its chance coverage by at least 0.15. Events with no label are reported as unexplained.

## Decision rules
* A test is **supported** if BH-significant at 10% and meaningful (S1: observed ≥ null mean + 2 SD; S2: share ≥ 0.20; P1: pair share exceeds the null by ≥ 0.15; hazard: AUC ≥ 0.60 or ≤ 0.40; R1 as stated).
* Cycle-level direction: the same direction in at least 60% of cycles with three or more events.
* **Not supported** is "not detectable here", not "absent": about 17 cycles and 150 sales.

## Stated limits in advance
* Fill times are placement times only to within about a second.
* The pair ledger uses sold lots from the log; hidden or manual orders are not seen.
* The lump counterfactual keeps the lump's side and strike and approximates its size rule.
* Exploratory; nothing here can confirm. The forward recorder's pre-order state is needed for causality.

## Addendum 1 (2026-11-24, written after the part-1 first run and before part 2 and part 3 ran)
What the first run of part 1 showed (descriptive, so these additions are **post-hoc and exploratory**): events from different cycles coincide in clock time more than the shift null (S1) and pile into a few minutes (15:20, 15:23, 15:29). Because a uniform-shift null destroys any minute profile, S1 alone cannot tell a *timer* from *the same minutes being busy*. Added tests (script `bl_trig2_clock.py`):
* **S5** minute concentration (sum of squared minute counts across cycles; circular-shift null by cycle).
* **S1b** seconds-level coincidence **given the same minute** (null: redraw each event's second uniformly inside its minute). A real timer shows up here; mere minute-level busyness does not.
* **S6** share of events in the three timetable minutes 15:15 (index freeze), 15:20 (first indicative auction value), 15:29 (official close): chosen from the exchange timetable *after* seeing the histogram, so exploratory.
* **X1** published-index discontinuity: does the minute-level gap |ΔFEED − ΔFUT| (scaled) predict that a late sale happens in the minute? (stratified AUC within cycle; null: shift the sale minutes inside the cycle). Also |ΔFEED| and |ΔFUT| separately.
* **X2** direction: CE sale after an up-move / PE sale after a down-move over the previous 5 minutes, FEED vs FUT.
* P3a was corrected (the mirror flag in the first run made the expected completion equal the actual one by construction); S3 and S4 now use the circular-shift null instead of a uniform null; the PAIR chance coverage uses the P1 null; the COMPLETION chance uses the P3a own/mirror expectation (approximate).
These 8 extra tests are counted: the BH family becomes 32 tests.

## Addendum 2 (written after parts 1–3 ran)
Two further post-hoc additions, both visible in the report: (i) strictly-before-the-minute versions of X1 and X2 (the first versions used information through the sale minute, which is look-ahead), (ii) **S7**, whether all pair events fall in one narrow window (15:28:00–15:31:00), added after I printed the six pair times (window chosen post hoc; Bonferroni over the 22 possible window positions only). Final BH family: **37 tests** (not 32). Part 4 (`bl_trig2_incr.py`) compares five leave-one-cycle-out models on strictly-before features and is outside the BH family.
