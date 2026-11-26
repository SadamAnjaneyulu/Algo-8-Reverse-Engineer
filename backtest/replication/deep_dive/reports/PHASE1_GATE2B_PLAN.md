# Phase 1, Gate 2B: solo strike reference. Preregistration

*Written 2026-11-25 **before** any Gate 2B evaluation. Experiments `P1-2B-*`. Baseline B1 (accepted `one_lot_v2` F run). Existing data only (one-minute index bars; option bars for the downloaded chain, forward-filled where nothing traded; the real fills). Evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## 1. Problem
Matched ladder-solo orders have the exact strike only **25.6%** of the time in F (547 matched; 39.7% off by one step, 34.7% by two or more); scheduled straddles 94.5%, breakout straddles 78.6%. Earlier work (G3) found exact agreement 0.44-0.47 for the engine's rule in the last 25 minutes (rule incomplete). Wrong strikes account for 699 matched body sells (407 ladder).

## 2. Evidence already in the repository (not re-run)
* Pairs: ATM of the previous completed close, 94-99% exact. Solo/late: premium-nearest to the last same-side sale within +/-4 strikes (engine rule), exact 0.51-0.54 (D1-08). G3: bars are not the limiter of strike choice (decision drift 2.5% vs strike gap 21%); the rule is incomplete.
* **New fact established while preparing this plan:** the option bar cache holds the **whole downloaded chain** (91 strikes by 375 minutes per cycle), forward-filled where a strike did not trade; within +/-4 strikes of the money every minute has a real bar. The earlier statement that decision-time prices exist "only for traded contracts" is true of the **order log's** limit prices, not of the bars; candidate strikes can be priced from the previous minute's close.

## 3. Competing hypotheses (all kept until tested)
| ID | Rule for the strike of a solo sell on a right | Needs |
|---|---|---|
| S0 | ATM of the previous completed minute close (the pair rule) | spot |
| S1 | **engine rule**: within +/-4 strikes of that ATM, the strike whose previous-minute close premium is nearest (absolute difference) to the last same-side sale price; ATM if none | last sale |
| S1r | as S1 with relative (log-ratio) distance | last sale |
| S2 | the last same-side sold strike | last sale |
| S3 | ATM of the open of the current minute | spot |
| S4 | offset persistence: the previous-close ATM plus the offset (in strikes) the last same-side sale had from ITS previous-close ATM | last sale |
| S5(f) | the strike (within +/-4) whose premium is nearest to f times the premium of the previous-close ATM strike on that right; **one fitted constant f in {0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0}**, leave-one-cycle-out | chain |
| S6 | the strike whose premium is nearest to the last sale price on the **other** right (strangle premium equalisation) | last sale (other) |
Not testable here: delta-based selection (needs an implied-volatility model assumption); hidden or discretionary inputs.

## 4. Experiment P1-2B-0: teacher-forced strike evaluation (no engine change)
Population: the **1,140 real body sells labelled solo** (`outputs/bodysell/ledger_real.csv`, inferred module), each with a previous same-side real sale (orders with no previous same-side sale that day are reported separately and score S0 only). For each order the rules receive **only information strictly before the order**: previous completed minute closes (spot and options), real previous sales of the same cycle (log order), the previous-close ATM. Metrics: exact agreement and within-one-step agreement with the real strike, pooled and per cycle, by underlying, version, era and 15:00+; cluster bootstrap (cycles, 4,000 draws) for differences against S1; the **ceilings**: share of real strikes inside the +/-4 window, and the union (any of S0-S6) agreement.
**Supported** (a rule X versus S1): exact agreement difference >= **+0.05** pooled **and** bootstrap 95% interval of the difference above 0 **and** X >= S1 in at least **20 of 32** cycles **and**, for S5, leave-one-cycle-out held-out advantage >= +0.05 with the same f chosen in >= 80% of folds.

## 5. If a rule is supported: engine candidate (P1-2B-V*)
A switch `solo_strike_rule` (default = S1 = baseline) implements it; the full 32-cycle F replay under `one_lot_v2` is scored. **Acceptance (all):** ladder-solo matched strike-exact share >= 25.6% + 0.05 (absolute); body-sell strict F1 >= B1 0.5954 + 0.01; body-sell keys F1 not below B1 0.7586 - 0.005; scheduled straddles matched >= 2,076 and exact-second share >= 0.659; every other class F1 >= B1 - 0.02; median book L1 <= 0.508 + 0.02; strict F1 improved in >= 20 of 32 cycles. Regression: defaults replay identical to B1; unit tests for the rule; all variants archived.

## 6. If no rule is supported
Solo strike reference stays **Partial**; the residual is quantified (ceiling and union agreement), classified by cause (decision-time variable unknown), and Gate 2B is **CONDITIONAL**. No further strike-rule search on these cycles without a genuinely new mechanism.

## 7. Limits stated in advance
Same development cycles; module labels inferred; the previous-close premium is a lagged proxy for the decision-time price (G3: median drift 2.5%); one fitted constant (S5) under leave-one-cycle-out; eight rules on the same data counted as selection risk.

## Addendum 1 (after P1-2B-0, before the next computation; post hoc, labelled)
**P1-2B-0 headline (`outputs/phase1/2B_strike_eval.json`):** teacher-forced on 1,139 real solo sells with a previous same-side sale: S1 (engine) exact 0.501, within one step 0.881; S2 0.536 (+0.034 vs S1, 95% interval [0.008, 0.064], 26 of 32 cycles >= S1); S4 0.531 (+0.030, interval [-0.003, 0.067], 21 of 32); S1r 0.505; S0 0.190; S3 0.189; S6 0.175; S5 (f fitted LOCO, chosen f = 1.0 in 32 of 32 folds, which equals S0) 0.190. **No rule meets the preregistered bar (+0.05 with the interval above 0).** The real strike lies inside the +/-4 window in 99.5% of orders; the union of all rules reaches 0.733.
**One further mechanism, not a re-parameterisation** (different idea: orders stack on strikes already held), fixed here before it is computed, same support criteria as section 4:
* **S8:** the strike of that right holding the most real short lots just before the order (ties: nearest to the previous-close ATM); ATM if none.
* **S9:** among strikes of that right held just before the order, the one nearest the previous-close ATM; ATM if none.
Held lots = real `open_short` minus `cover_short` lots per contract in log order. Nothing else is added; after S8 and S9 the strike-rule search on these cycles stops.
