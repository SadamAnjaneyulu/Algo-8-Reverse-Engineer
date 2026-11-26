# Phase 1, Gate 6: integrated D-1 + D0 engine. Preregistration

*Written 2026-11-25 **before** any integrated run. Experiments `P1-6-*`. Components: the frozen D-1 engine at B1 (`one_lot_v2`, accepted) and the D0 engine D0-C (Gate 5a + candidate X1). Existing data only. Evidence label: historical reproduction on development cycles (the D0 fitted parts are the same out-of-fold splits as 5b-5d). Nothing committed. Neither component is changed by this gate.*

## 1. Objective
Run **one continuous cycle**: D-1 session (simulated, flat start) -> end-of-D-1 book -> D0 opening state -> D0 session, with **no real order or real position entering anywhere** (mode F, free-running). Quantify how much D-1 carry error propagates into D0 by comparison with the teacher-forced D0 (mode T, 5d).

## 2. Handoff contract (fixed now)
| Item | Rule |
|---|---|
| Body short lots | every short lot in the D-1 book at the D-1 end -> `D0Opening.lots` as `[right, strike, entry_price]` with the D-1 engine's own entry prices |
| Longs | D-1 wing longs -> module `h_`; overnight lump longs -> module `v_`. **Mapping assumption (labelled):** the D-1 engine books its opening wings together with the protective wings, so they carry as `h_`; in the real log they are `num` (body module) longs and are cleared as body longs, not wing sells. Quantities and contracts are unaffected |
| Other-module shorts | none (the D-1 engine has none); `oshort` empty |
| Cash | sum over the D-1 engine's simulated fills of (sell +, buy -) x fill price x lots x lot size; the D0 cycle stop therefore counts the simulated D-1 result |
| Market | D0 option and spot caches of the cycle; the D-1 strike chain must contain every carried contract (checked) |
| Real inputs | none. The real logs are used only afterwards for scoring |
| Not modelled in D-1 | the `s_` stop module acts in D-1 sessions of the real system; the D-1 engine has no stop. A D-1 stop is not simulated (stated limit); the D0 cycle stop uses cumulative simulated cash |

## 3. Checks and acceptance criteria (fixed now)
| # | Criterion |
|---|---|
| G6-1 | **Handoff identity** (all runs): the D0 opening net position per contract equals the D-1 broker's net position at the D-1 end (wings and lump included, shorts negative); the opening cash equals the sum of the simulated D-1 fills; `D0Engine.reconcile(opening)` holds at the D0 end |
| G6-2 | **No real input / no look-ahead:** the integrated runner has no real-order argument (signature test); the D0 engine's market arrays and the D-1 session are the only inputs; D-1 end state is produced before any D0 minute runs |
| G6-3 | **Contract coverage:** every carried D-1 contract exists in the D0 chain (0 rejected handoffs); otherwise reported, not repaired |
| G6-4 | **Default regression:** the D0 engine fed the REAL opening (mode T) still reproduces the 5d result (keys F1 0.4217, legacy 0.4142) exactly; the frozen B1 D-1 replay is unchanged (legacy lot-level F1 0.6878, scored with the existing D-1 scorer) |
| G6-5 | **Determinism:** the integrated replay reproduces identically on rerun (all runs) |
| G6-6 | **Mode F quality (D0 part):** pooled D0 keys F1 (OOF, `events`, 60 s) >= 0.80 x the mode T value (0.4217 -> >= 0.337) **and** above the shift placebo + 0.10 |
| G6-7 | **Integrated quality (D-1 + D0 orders together, OOF, mode F):** pooled keys F1 (60 s) reported with per-day split; it must be >= placebo + 0.10 |
| G6-8 | **Carry error:** at the D0 open, the contract-level normalised distance between simulated and real book (L1 / gross real lots) is reported (median and distribution); **no threshold** (diagnostic, quantifies the inherited D-1 error) |
| G6-9 | Risk controls on the integrated run: 0 refused orders, peak short lots per right <= 306 (D0) and <= 400 (D-1), peak sell decisions per minute within limits |
Pass rule: Gate 6 is **PASS** if G6-1..G6-7 and G6-9 hold; **CONDITIONAL** if only G6-6/G6-7 quality criteria fail with the loss quantified and attributed (G6-8); **FAIL** if an identity, determinism, input-leak or regression criterion fails. Mode T (5d) and mode F numbers are never mixed.

## 4. Limits stated in advance
D-1 stop module absent; opening wings carried as `h_` (see above); same development cycles; one D-1 realisation per cycle (the replay's intrabar path order is a convention); the three D0 cycles without a D-1 cycle record are not integrated.
