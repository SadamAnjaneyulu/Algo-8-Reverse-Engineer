# D-1 reconstruction — learned decision policies for the undecoded parts: plan

*Written before running. In-sample, D-1 of 32 cycles. The decoded rules stay where they are near-exact (scheduled timetable 0.98, reactive trigger, hedge controller 0.92–0.95 given the body, opening wings, lump timing regime). The two weakest parts, which no single rule reproduces, get learned policies:*

## Policy 1: solo sells (stand-alone, attached extras, after 15:00)
* **Unit:** cycle × minute × right. **Target:** real solo lots in that cell (deep-OTM batches excluded).
* **Features (no real orders):**
  * the market variables of the earlier studies: fresh extremes 5/15/30/60 on closes and true high/low; favourable moves; premium lows; position in the 15-minute range; reactive break, side and depth; break depth beyond the 15- and 60-minute extremes; spot ladder fire; late R3 condition; minute;
  * book state: own and other right's short premium ratio and short lots. Training uses the real book; the simulator uses its own book.
* **Model:** cumulative classifiers P(lots ≥ k), k = 1…4 (gradient boosting, fixed settings).
* **Decision:** place the k-th lot when P(lots ≥ k) ≥ t. The threshold t is chosen on the training cycles for lot F1. The simulator's own rule-based solo ladder and extras are switched off when this policy is on.

## Policy 2: buy-backs
* **Unit:** open lot × minute.
* **Features:** own ratio (minute high and previous close), minutes held, sell type, adverse spot move since sale, 3-minute premium speed, fresh 30-minute breakout against, the right's total premium ratio, open lots on the contract, minute.
* **Model:** gradient-boosting classifier. Buy back the lot when P ≥ τ, with τ chosen on the training cycles for lot F1. It replaces the rule stop when on.

## Validation (same as before)
* Out-of-fold on cycle halves, and forward on unseen cycles: split A (same version) and split B (version change).
* Models, thresholds, timetable and lump time come from training cycles only.
* **Kept only if** the overall lot F1 rises out-of-fold **and** on both forward splits. Each policy is reported alone and combined.
