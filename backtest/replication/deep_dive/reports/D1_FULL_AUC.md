# Algo 8 — complete D-1 activity (body + hedge): one AUC against the real ledger

*Plan `D1_FULL_AUC_PLAN.md`, written before running. In-sample, D-1 of 32 live cycles. 24,960 cells (cycle × minute 09:15–15:44 × right). Figure: `figures/bl_full_auc.png`.*

## 0. Result
* **Overall AUC for any D-1 activity: 0.961** (variant A). Every class is above your 0.85 target. *Observed.*
* **Macro average over the six activity classes: 0.962.** With everything chained from predictions (no real orders of the current minute anywhere): 0.944. With completed bars only: 0.944.
* By module:
  * **Body:** sell 0.977, buy-back 0.915.
  * **Hedge:** wing buy 0.996 and wing sell 0.997 given the real body orders. Chained from the *predicted* body they are 0.980 / 0.905.
  * **Opening wings:** 0.932.
  * **Overnight lump:** 0.958.

## 1. AUC by activity (95% cycle-bootstrap CI)
| activity | cells with activity | A: hedge given real body (primary) | A-chained: no real orders in the minute | B: causal (completed bars) |
|---|---|---|---|---|
| body sell | 2644 | 0.977 (0.972–0.981) | 0.977 (0.972–0.981) | 0.911 (0.904–0.918) |
| body buy-back | 483 | 0.915 (0.890–0.934) | 0.915 (0.887–0.934) | 0.883 (0.859–0.906) |
| wing buy (h_) | 2553 | 0.996 (0.993–0.998) | 0.980 (0.977–0.983) | 0.995 (0.993–0.998) |
| wing sell (h_) | 438 | 0.997 (0.992–1.000) | 0.905 (0.878–0.928) | 0.996 (0.990–1.000) |
| body-stream long (opening wings) | 172 | 0.932 (0.904–0.958) | 0.932 (0.902–0.958) | 0.907 (0.878–0.939) |
| overnight lump (v_) | 47 | 0.958 (0.920–0.984) | 0.958 (0.916–0.983) | 0.968 (0.951–0.982) |
| **any activity** | 3365 | 0.961 (0.955–0.967) | 0.961 (0.955–0.966) | 0.901 (0.893–0.909) |


## 2. Overall
| variant | AUC any activity | macro average of 6 classes | pooled class × cell |
|---|---|---|---|
| A same-minute, hedge given real body (primary) | 0.961 | 0.962 | 0.988 |
| A-chained (no real orders in the minute) | 0.961 | 0.944 | 0.974 |
| B causal (market lagged 1 min), real body link | 0.901 | 0.944 | 0.979 |


* "Any activity" is the primary overall number: one model predicting whether anything at all happens on that right in that minute. It never sees real orders of the current minute.
* The "pooled class × cell" figure stacks all six classes. It is inflated because the classes have very different base rates (lumps are rare, wing buys common), so it rewards knowing which class is rare. Use the first two columns.

## 3. What each variant means
* **A (primary).** Market features use the current minute's high/low, as in every earlier F1/AUC. The **hedge** classes are scored given the real body orders of this and the previous minute: the hedge module reacts to executed body trades. Body classes, lumps and "any activity" never see real orders of the current minute.
* **A-chained.** The hedge classes get the predicted body-sell and buy-back probabilities instead. This is closest to "run the decoded system on its own".
* **B (causal).** Completed bars only, with the causal sell model.
* **All variants** use the book state (short/long lots, premium ratios) built from the real orders *before* the minute. This is teacher-forced: it asks "given its current position, does the decoded rule set predict what it does next?" It is not a free-running simulation, in which errors would compound.

## 4. Caveats
* AUC measures ranking per minute and right. It does not score strikes or lot counts. Lot-level reconstruction for sells is F1 0.78 (`D1_SELLING_RECONSTRUCTION.md`), and lump size is unresolved (`D1_LUMP.md`).
* In-sample. The decoded rules were found on the same 32 cycles, so this measures how completely the rules describe the observed behaviour, not out-of-sample prediction.
* **Bug found and fixed before reporting.** In the first run the buy-back model could see the real buy-backs of the same minute (its own label), giving AUC 1.000. The causal variant also used the same-minute sell prediction, and it lagged the timetable share, which is a known clock and was never lagged in the sell study. All three were corrected so that real current-minute orders feed only the hedge classes, as the plan specifies. Only the corrected run is reported.

## Evidence labels
Observed: sections 0–2. Not testable: event order inside a minute; a free-running simulation is not part of this test.
