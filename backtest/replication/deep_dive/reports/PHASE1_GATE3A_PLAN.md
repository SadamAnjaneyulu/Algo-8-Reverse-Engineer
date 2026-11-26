# Phase 1, Gate 3a: buy-back stop reconstruction. Preregistration

*Written 2026-11-25 **before** any Gate 3a computation. Experiments `P1-3A-*`. Official baseline B1 (frozen). Existing data only. Evidence: historical reproduction on the 32 development cycles. Nothing committed. The user's conditions (decisions of 2026-11-25) are binding: separate upstream-inherited from independent trigger errors; reconstruct the real position before each buy-back; test the stop against observed buy-backs; check missing and extra; measure timing, strike, quantity and portfolio-state agreement; **do not compensate for missing body sells by changing buy-back rules**; **quantify the remaining mismatches after upstream position differences before any engine change**.*

## 1. Problem (B1 numbers, verified)
Real body buy-backs 1,324 (all single lots); B1 simulates 933. Recall 0.490, precision 0.689, F1 0.573; median timing 15.5 s early; strike exact 47%. 675 real buy-backs are unmatched and about 290 simulated ones are extra.

## 2. Evidence already in the repository (not re-run)
* Decoded (D1-12, `BUYBACK_STOP2/3.md`, `BODY_CLOSE_LOGIC.md`): a graded own-premium stop; the hazard rises 2% to 41% across 1.4-1.8x of entry and is about 10x higher with a fresh 30-60 minute breakout against the position; **87% of buy-backs are on a lot in loss**; on the real book the plain minute-high stop at about 1.6x gives contract-minute F1 0.588; "premium AND breakout" 0.545; "A OR B" 0.566; the close does worse than the high. Half the events (low ratio, near ATM) had no recoverable trigger. **Not reopened.**
* TF-E (this project): with the book corrected, the engine's stop fires first-decision orders with precision 0.845 and recall 0.31; reading all orders (with repeats) gives recall 0.54 at precision 0.25.

## 3. Step 1: quantify upstream versus independent (no engine change; required first)
**Position reconstruction:** the real position before each order from the real log (the verified rebuild of `bl_tfe.apply_real`: lots with entry prices and entry minutes); the simulated position from B1's cumulative simulated orders. For every **missing real buy-back** and every **extra simulated buy-back** of B1 (matching as scored), by this fixed cascade (first rule that applies):
| Missing real buy-back R on contract c at second t | Class |
|---|---|
| the simulator held **no** short lot on c before t | **U1 upstream: position missing** |
| the simulator held fewer lots on c than the real book | **U2 upstream: position short** |
| the simulator held at least as many, and a simulated buy-back on the same type lies within +/-60 s (matched elsewhere) | **S supply** (count) |
| the simulator held enough lots, no buy-back within 60 s, and the engine's stop rule **would fire on the real lot** (minute-high ratio >= 1.6, lot from an earlier minute) | **R1 rule fires on real state but the simulator's state differs** (entry price, timing) |
| the simulator held enough lots, no buy-back within 60 s, and the rule **would not fire** on the real lot (ratio < 1.6) | **I independent trigger gap** (the real system acted below the rule) |
| Extra simulated buy-back E on contract c at second t | Class |
|---|---|
| the real book held **no** short lot on c before t | **XU upstream: position not real** |
| the real book held lots on c and a real buy-back on the same type lies within +/-60 s (matched elsewhere) | **XS supply** |
| the real book held lots, no real buy-back within 60 s, and the real lot's ratio >= 1.6 (the rule is satisfied on real state) | **XR the real system did not act despite the rule** |
| the real book held lots, no real buy-back within 60 s, ratio < 1.6 | **XI simulator state differs (ratio differs)** |
For each class: counts, shares, timing (median offset to the nearest counterpart), strike agreement, lots, and the real-minus-simulated portfolio state before the order. **Reported: the share of missing and of extra buy-backs that are upstream (U1, U2, XU) versus independent (I, XR, XI, R1, S).** Ratio uses the contract's one-minute bar high of the order's minute (an upper bound on the running high the engine sees; labelled) and the real entry price (average fill) of the lot the engine would remove (cheapest entry first).
**Decision after Step 1:** an engine change is considered only for the share classified independent (I, R1, XR, XI); upstream classes are not touched.

## 4. Step 2: teacher-forced stop experiments on the real position (only for the independent share)
Competing mechanisms (each tested once, compared with the engine rule K1 = ratio >= 1.6 on the minute high):
| ID | Mechanism |
|---|---|
| K1 | engine rule (baseline) |
| K2 | one constant ratio in {1.4, 1.5, 1.7, 1.8}, chosen leave-one-cycle-out |
| K3 | stop on the previous completed minute's close instead of the running high |
| K4 | module-specific ratio: lots entered on the scheduled clock vs lots entered otherwise (inferred module); one fitted ratio per class, LOCO |
| K5 | **cluster closing:** when a lot on a right is stopped, the other lots of that right whose ratio is at least the **cluster ratio** are bought back in the same second (one fitted constant in {1.2, 1.3, 1.4, 1.5}, LOCO); motivated by 67-77% of real buy-backs lying in same-right clusters within 5 s |
Teacher-forced on the real position at the order-event level (contract-minute and order level): precision, recall, F1 for the stop decisions, timing offset, strike (contract) agreement, lots, and the real-minus-simulated state. **Supported** if the best mechanism's order-level F1 on the independent share is >= K1 + 0.03 with a cluster-bootstrap interval above 0 and >= 20 of 32 cycles at least equal, and (for fitted constants) the LOCO choice is the same in >= 80% of folds.

## 5. Step 3: engine candidate (only if supported) and acceptance (fixed now)
Switch default off; full 32-cycle replay under `one_lot_v2`, scored as B1. Acceptance (all): body buy-back F1 >= B1 0.573 + 0.03; strike-and-lots-exact buy-back F1 not lower than B1; recall >= B1 + 0.02 with precision >= B1 - 0.02; wing sell F1 not lower than B1 - 0.02 (they inherit); body-sell F1 >= B1 - 0.005; scheduled straddles >= 2,076 matched; other classes >= B1 - 0.02; median book L1 <= 0.508 + 0.02; legacy lot-level F1 >= 0.6878 - 0.005; buy-back F1 improved in >= 20 of 32 cycles. Failing any = rejected and archived.

## 6. Stop rule
If Step 1 shows the buy-back errors are predominantly upstream, no buy-back engine change is made and Gate 3a is CONDITIONAL with the quantified split. If the independent share is large and Step 2 supports nothing, the independent trigger gap is classified Unresolved (data-limited) and Gate 3a is CONDITIONAL. No further search without a new mechanism.

## 7. Limits stated in advance
Same development cycles; entry prices are fill averages and the lot closed by a real buy-back is not in the log (cheapest-entry-first is the engine's convention); the minute-bar high is an upper bound of the intrabar touch the engine sees; the module of a real lot is inferred; selection counted (Step 2: five mechanisms, three fitted constants).

## Addendum 1 (after Step 1, before Step 2)
**Step 1 result (`outputs/phase1/3A_step1.json`, reconciles to B1: 1,324 real, 933 simulated, 675 missing, 290 extra).** Missing real buy-backs: **U1 119 + U2 249 = 368 upstream (54.5%)**; S supply/count 142 (21%); **I independent trigger gap 163 (24%)** (median minute-high ratio of the real lot 1.17, IQR 1.02-1.44: the real system acted well below the 1.6 rule); R1 2. Extra simulated buy-backs: XS 173 (60%), XU 50 (17%), XI 34, XR 33. Matched buy-backs: median timing -18 s (the simulator is earlier), strike exact 46.5% (within one 75.3%), lots exact 99.7%, S and L equal 0%, book L1 0.52. **Decision per the plan: no buy-back engine change for the upstream share (368 missing, 50 extra).** Step 2 addresses only the independent share and the supply/count classes.
**One execution-timing mechanism added, fixed before it is computed (a convention, not a decision rule):**
| ID | Mechanism |
|---|---|
| K6 | the buy-back order follows the stop touch by a **latency L** seconds, L in {0, 10, 20, 30}, chosen leave-one-cycle-out; judged **only** on timing agreement (share matched within 5 s and 60 s on the teacher-forced real position), never on the stop decision itself |
Evidence for it: the matched buy-backs are a median 18 s earlier than the real ones; the replay's intrabar path order is a convention. The spec's principle 7 applies: exact-second agreement is never a pass/fail gate; K6 is reported as an execution assumption with its own version if adopted.
Step 2 is implemented as a teacher-forced evaluation at (contract, minute) level on the real position at the start of each minute (lots entered in the same minute excluded, as in the engine); predicted lots are the lots with ratio >= R under each mechanism; real lots are the real body buy-backs of that contract and minute. Order-level precision, recall, F1 as lots (min of predicted and real), per cycle, and on the class-I orders separately.

## Addendum 2 (after the first Step 2 execution, before any conclusion was drawn)
The first execution counted a lot as predicted in **every** minute in which it stayed above the ratio on the real position (the real system had not closed it), so repeated predictions of the same lot depressed precision (K1: precision 0.279, F1 0.331). This is the same artefact as the TF-E re-decision loop. **Definition fixed:** each lot is counted **once per mechanism, at the first minute in which it satisfies that mechanism**; in the cluster mechanism K5 the lots added by the cluster rule are likewise counted once. The first execution's output is archived as `outputs/phase1/3A_step2_first_execution_repeat_counting.json`. No other definition changed; nothing was concluded from the first execution.

## Addendum 3 (before the K6 latency runs): acceptance for the execution convention K6
B1 baseline value (computed before the runs, not tuned): of 1,324 real body buy-backs, 649 are matched and **119 are matched within 5 s: share 0.0899**, so criterion (1) reads >= 0.1399. Engine switch `stop_latency_s` (default 0 = baseline): a stop is submitted L seconds after its trigger first holds; L in {10, 20, 30}, chosen leave-one-cycle-out. **K6 is accepted as a candidate execution convention only if all hold:** (1) share of real buy-backs matched within 5 s >= B1 + 0.05; (2) buy-back F1 (keys, 60 s) >= B1 0.573 - 0.01; (3) body-sell F1 >= 0.7586 - 0.005; (4) other class F1 >= B1 - 0.02; (5) legacy lot-level F1 >= 0.6878 - 0.005; (6) the LOCO-chosen L is the same in >= 80% of folds. **Even if it passes it is not adopted into the baseline:** like `one_lot_v2`, an execution convention is recorded as an open decision for the user.
