# D0 chunk 4: cycle stop and 15:14 clearance — plan

*Written before the tests. In-sample: D0 of the 30 cycles with both logs.*

*Earlier work (`execution_parity` S16 / U8, `d0_reconstruction` R09):*
* *the stop module `s_` liquidates the cycle at a cumulative LTP MTM of about −₹1.30 to −1.44 lakh;*
* *marked at the close of the stop minute (non-causal) it catches 10/9/8 of 11 stops at L = 1.30 / 1.35 / 1.44 lakh with no false alarms; with causal marks it fails;*
* *8 of 11 stops fire in the first 15 minutes.*

*Pre-plan look at the clearance:*
* *at 15:14 the body buys back 1,263 short lots and sells 1,092 body-stream long lots;*
* *body buy-backs continue at 70–210 lots per minute until 15:20, with a tail until about 15:34.*

## Stop
**S1 — cycle MTM in ₹, all modules.** Cash from every order since the D-1 open, plus open positions × mark × lot size.
* Two scopes:
  * **cumulative** from the D-1 open;
  * **D0-only**: minus the MTM at the D0 09:15 open mark.
* Contracts with no D0 price are marked at 0, and their share is reported.

**S2 — which mark and which threshold.**
* Marks at the decision minute j:
  * previous close (causal);
  * open of j;
  * adverse intrabar (the minute high for net-short contracts, the low for net-long);
  * close of j (non-causal).
* L ∈ {1.20, 1.30, 1.35, 1.40, 1.44, 1.50} lakh.
* The predicted stop is the first minute with MTM ≤ −L. Positions follow the real orders up to the start of the minute.
* Per mark × L × scope:
  * hits (predicted within ±1 minute of the first real `s_` order; also within ±5);
  * early fires (more than 5 minutes before the real stop, or in a cycle without a stop);
  * misses.
* Mark, L and scope are chosen on one cycle half and scored on the other (cycle level).

**S3 — what the stop does** (descriptive):
* `s_` lots by role;
* the time span of the liquidation;
* the share of the open book closed;
* body orders after the stop.

## Clearance
**C1 — timing.** Lots per minute 15:00–15:35 by module and role (descriptive).

**C2 — which short contracts are bought back from 15:10 on, and which are left to expire.**
* Unit: open body short lots at the 15:09 close (cycles without a stop).
* Features: premium at 15:09 and moneyness in steps.
* Rules, each fitted on one half and scored on the other:
  * a premium threshold p* ∈ {0.5, 1, 2, 3, 5, 10};
  * a moneyness threshold k* ∈ {−3, −2, −1, 0, 1, 2, 3} steps OTM.
* Reported: lot-level accuracy and AUC. Chance = the majority-class share.
* The same for open long lots: sold from 15:10 on, or kept.

**C3 — 15:14 against later.** The premium and moneyness of the lots bought back at 15:14 against those bought back 15:15–15:35.

## Acceptance
* A rule is kept if it beats its null or chance by ≥ 1.5× (or AUC ≥ 0.70) and the CI excludes it.
* Parameters come from the training half.
* Evidence labels; post-hoc steps are labelled.
