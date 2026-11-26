# Phase 1 unresolved-rules register (Gate 8)

*Every rule or sub-rule whose evidence is not sufficient, with what is known, what blocks it, whether a no-new-data experiment is still feasible, and the single next step. Evidence label: historical reproduction on development cycles. Nothing committed.*

## A. Feasible investigations: all four executed in the Phase 1 final loop (2026-11-25); outcomes in `reports/PHASE1_LOOP2_RESULT.md`
| # | Hypothesis | Outcome | Class |
|---|---|---|---|
| U1 | H6: premium-triggered solo ladder | **Rejected at the decision level**: premium-extreme indicator F1 0.460 vs spot 0.437 (+0.023, interval lower bound -0.002); union worse; no engine variant (preregistered stop rule) | Rejected; trigger remains data-limited |
| U2 | G1b: closing-pair bursts follow the 15:30 candle close | Original condition is **not causal** for 7 of 8 bursts (they start 4-258 s before the candle completes; body orders carry no decision time). Causal analogue (close of minute 369): 6/8, p = 0.0089, precision 0.60; fails at minute 373. No engine change, session not extended | **Plausible but unconfirmed**; data-limited |
| U3 | D-1 session stop | Real D-1 has one stop (NIFTY 2026-09-01); rule **confirmed on the real book** (12/12 stops, 0 false alarms with the corrected constant 1.25 lakh, interval (1.2177, 1.2902]); session vs cycle scope not separable in D-1; **free-running D-1 stop rejected** (4 false stops, scheduled straddles 2,046 < 2,076) | Rule Confirmed (real book); engine candidate Rejected |
| U4 | D0 clearance spread 15:14-15:34 | Post-auction: 15:14 in 9 of 10 cycles; the 15:30+ block is one cycle (SENSEX 2026-08-13, 15:33); pre-auction: flow plus a sweep at minute 364. CH1/CH2 rejected (CH2 near-miss), CH3 not supported; X1 stays experimental/in-sample, production default 359 | Decoded (post-auction clock, pre-auction sweep); spread and the 15:33 exception Unresolved |
Remaining feasible-and-untested ideas after the loop: none identified from the current evidence that is not a re-parameterisation of a rejected mechanism. **Gate 1 criterion (d) is therefore treated as met**: every feasible no-new-data investigation listed in the register has been run to its stop rule. (Open-ended new hypotheses remain possible and are not counted as unmet obligations.)

## B. Data-limited (cannot be closed with the repository's data)
| Rule | What is known | What is missing |
|---|---|---|
| D-1 solo counts and timing (D1-05) | trigger Partial (60-minute fresh extremes cover 71%); one-lot drip convention accepted | tick/one-second path |
| D-1 position sizing (D1-09, D0-07) | none predictive out-of-fold | margin, capital, decision logs |
| D-1 buy-back trigger for half of the events (D1-12) | graded own-premium stop, 87% on lots in loss; 54.5% of mismatches are upstream | intrabar touches |
| D0 buy-back bursts and other buy-backs (D0-04) | stop 1.4x and take-profit 0.1x LOCO-stable | set membership of bursts |
| D0 opening solo sells, body-long strikes, intraday longs (D0-03, D0-05) | opening long count rule approximate (rho 0.92) but X3 rejected at order level | ticks, strike rule |
| Overnight lump size (D1-13) | side 0.93 | margin, capital |
| Late D-1 sales 15:15+ (D1-06, D1-14) | feed fidelity fixed (diagnostic C1), recall 0.12-0.15; closing bursts: causal analogue plausible but unconfirmed | late-sale tracker (ticks); decision times of body orders |
| No-trade filter, eligibility (D1-01) | cycle definition confirmed | days without trades are not exported |
| Regime B (after 7 Dec 2026) (D1-17, D0-06) | none | post-7-Dec order logs |
| Independent validation | none exists | post-22-Oct trade exports or forward paper trading with the frozen configuration |

## C. Decisions that belong to the user (not taken by the system)
| Decision | State |
|---|---|
| Adopt candidate X1 (pre-auction clearance at 15:18) | **not a production default** (decided in the final loop): kept only in the labelled historical-reproduction configuration; in-sample evidence on 8 pre-auction cycles |
| Adopt `one_lot_v2` as the production execution convention | accepted for B1 (user, 2026-11-25) |
| Treat C1 (rebased futures from 15:15) as anything beyond a diagnostic | decided: diagnostic only |
| Further hypotheses beyond U1-U4 | none queued; CH2 (staggered clearance) is a documented near-miss for a future independent test |
| Commit and push | **not authorised**; everything is uncommitted |
