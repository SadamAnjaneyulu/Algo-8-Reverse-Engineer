# D-1 lot construction — why lot-level F1 is about 0.63–0.69, and fixes: plan

*Written before the analysis. In-sample, D-1 of 32 cycles. Minute-cell activity is reproduced at F1 0.89 (±1 minute), lots at 0.69 (out-of-fold) and 0.63 (unseen cycles). The gap is lot construction.*

## 1. Error budget (diagnosis)
Every unmatched lot of the current free-running reconstruction (out-of-fold) gets one cause, per class and per sell type.

**Real lots not reproduced:**
* **quantity shortfall:** the simulator acts within ±1 minute on that class and right, but with fewer lots;
* **timing:** the simulator acts only 2–5 minutes away;
* **missed event:** no simulated action within ±5 minutes;
* **not modelled:** classes the simulator does not produce.

**Simulated lots not real:**
* **quantity excess:** a real event exists within ±1 minute, but with fewer lots;
* **timing:** only 2–5 minutes away;
* **spurious event:** nothing real within ±5 minutes.

**Inherited errors:** errors in classes that follow the body (wings, buy-backs, lump) are compared with the same classes run on the real body (tf modes), to separate inherited errors from their own.

## 2. Fixes
* Only for causes that carry a material share of the lost lots.
* Each fix must state the mechanism it represents (for example, a solo ladder that sells one lot per rung crossed).
* Parameters are chosen on the other cycle half.

## 3. Acceptance rule
A fix is kept only if it raises **both** the out-of-fold overall F1 (cycle halves) and the forward overall F1 on unseen cycles (split A of `D1_FORWARD.md`). Every fix tried is reported, kept or not.
