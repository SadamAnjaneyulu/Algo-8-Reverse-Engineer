# Body-sell mismatch ledger and failure categories: pre-registration

*Written 2026-11-25 **before** any category count was computed. Step 1 of "diagnose, fix, verify" for the body sells only. This step builds the ledger and the breakdown; **it changes no code and fits nothing**. Fixes follow one category at a time, each with its own hypothesis written first. Everything uncommitted. Evidence labels: Observed / Inferred / Weak / Unresolved.*

## Scope and unit
* **Run:** the accepted F run under `one_lot_v2` (`outputs/scoring/d1_F_v2_onelot`, spec v1.1, matching as scored: one-to-one, cumulative 60 s, keys = cycle, option type, side). Historical reproduction on the 32 development cycles.
* **Real body sells:** the 4,408 real orders of class `body_sell` (body module, `open_short`). **Simulated body sells:** the 4,091 simulated orders of class `body_sell` (roles scheduled straddle, breakout straddle, breakout extra, ladder solo).
* **"Miss" means:** no simulated sell on the same option type within 60 s after one-to-one matching. It does **not** mean a wrong decision: a miss can be timing, supply (count), side, or a real trigger absent. Strike and lots are **not** part of the matching key, so they are analysed on matched orders (table below).
* **Persistent in TF-E:** each F-missing real body sell is flagged as persistent if it is also unmatched in the first-decision TF-E run (the 1,145 figure); the others are the 34 recovered by state correction.

## Ledger (one row per real body sell and per simulated body sell)
Cycle, second, option type, side, strike, lots, matched or not (tier, dt, strike difference in steps, lots difference, partner class and role), spot (previous completed minute close, minute open), ATM and strike offset in steps, minute of day, **real book immediately before** the order (short and long lots per option type, net per contract) and the **simulated book immediately before** the same second, the nearest same-type and opposite-type simulated (for real rows) or real (for simulated rows) sell with its distance and match status, **engine view at that second** (ladder references, distance of the running extreme to the ladder trigger in points, channel top/bottom of the current half-hour block and whether spot is beyond it, last scheduled-wave second), the failure category, sub-labels, and the inferred module.

## Failure categories (decision cascade, fixed now; first rule that applies)
For a **missing real** sell R (pool for neighbours = all simulated sell-side orders of any class; pairs are one-to-one, so any same-type simulated sell within 60 s of R is already matched to another real order):
| ID | Rule | Reading | Correction it would need |
|---|---|---|---|
| **M1** | a same-type simulated sell exists within +/-60 s (necessarily matched elsewhere) | **supply / count**: the simulator fired fewer sells than the real system in that window | burst size or suppression logic |
| **M2** | else an *unmatched* opposite-type simulated sell within +/-60 s | **possible wrong side** | side selection |
| **M3** | else an *unmatched* same-type simulated sell within 61-300 s | **timing offset** | timing and event sequencing |
| **M4** | else (no simulated sell of that type within 300 s, none opposite within 60 s) | **trigger never fires** near this order | missing trigger condition, or missing input |
Sub-labels for M1: whether the supplying simulated order is a body sell or another class; for M4: **inferred module of the real order**: *scheduled clock* (its second is within 1 s of 09:16:00 + a timetable value of that cycle's version), *pair* (an opposite-type real sell within 2 s), else *solo*; and *late* if the minute of day is 15:00 or later. For M4-solo the engine's distance to the ladder trigger is reported as a distribution (no threshold is applied).
For an **extra simulated** sell E (pool = all real sell-side orders of any class), mirror categories: **X1** real supply exhausted (a same-type real sell within 60 s, matched elsewhere), **X2** possible wrong side (an unmatched opposite-type real sell within 60 s), **X3** timing offset (an unmatched same-type real sell within 61-300 s), **X4** no real decision nearby (none within 300 s). Sub-label: the simulated role.
For **matched** body sells (detail mismatches, not misses): strike difference in steps (exact, 1, 2 or more), lots difference, timing tier, partner class; by simulated role. These are the "wrong strike" and "wrong quantity" categories.
Windows (60 and 300 s) are fixed here and not varied. The 300 s window is a descriptive cut, not a fitted value.

## Outputs
`outputs/bodysell/ledger_real.csv`, `ledger_sim.csv`, `breakdown.json`, tables as csv; report `BODY_SELL_MISMATCH_BREAKDOWN.md` with the counts per category, the share persistent in TF-E, examples from named cycles, the matched-order detail table, and a prioritisation of the largest fixable category (a proposal only; no fix is built in this step).

## Software verification before reading any count (pre-set)
1. Every real body sell gets exactly one status and exactly one category; every simulated body sell likewise; counts reconcile to F's by-class table (missing real body sells = 1,179; extra simulated body sells = simulated body sells minus matched).
2. Category rules reproduced on a hand-built example with known answers.
3. The ledger's real book equals the cumulative real position after each order (reuses the verified TF-E rebuild); the simulated book equals the cumulative simulated orders.
4. Cascade order is enforced (an order satisfying M1 and M3 is M1).

## Stated limits in advance
Same development cycles; the real log has no decision times (first-fill seconds only) and no module label inside the body module, so the module of a real sell is **inferred**; engine-view columns describe the current engine, not the real system; categories describe how the *simulator differs*, not why the real system acted. A category with a large count may still contain several causes; the examples and sub-labels are there to split it before anything is fixed.

## Addendum 1 (written after the ledger run; post hoc, descriptive only)
After reading the category counts I added **descriptive** checks, none of them tests, none feeding any change: simulated vs real order sizes and lots; same-second multiplicity of same-type sells (real vs simulated); the split of M1 by whether the previous real same-type sell is at the same second; consecutive same-type sells within 60 s expressed in units of the engine's ladder trigger distance (0.2 strike steps) using the engine-view spot; the share of unmatched solo sells at which the engine's new-60-minute-extreme condition holds. They are labelled post hoc in the report. The pre-registered categories, windows and cascade are unchanged.
