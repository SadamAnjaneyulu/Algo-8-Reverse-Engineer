# Proposed amendment to the forward-test validation protocol

**Status: PROPOSED. NOT IN FORCE.** Written 2026-11-24 as a separate document. The original pre-registration (`FORWARD_TEST.md`, commit `b6ed61d0`, sha256 `ddd9fc9d…1289`) is **unchanged**; where this document differs from it, the original governs until a dated adoption note is added below. The amendment changes **only** the validation method; the frozen rule (sha256 `ca1306cf…8e03`), the frozen score (`7788f739…d69c`), the features, the window, the reference and the primary endpoint's definition are **not touched**. Machine-readable form: `validation_config.json` → `proposed_amendment`.

**Why it can still be adopted cleanly.** No regime-B data exist, the recorder has not run, and the three regime-A forward sessions (25 Nov, 30 Nov, 2 Dec) are exploratory by the original protocol. Nothing in this amendment was shaped by forward data. **It must be adopted before the first burn-in session (7 Dec 2026) or it becomes contaminated.**

## Amendments
| ID | Change | Why it is necessary | Evidence | Cost | Needs a decision? |
|---|---|---|---|---|---|
| **A1** | At **every** look use the Pocock-adjusted interval (two-sided 2.94%, i.e. 97.06%, for K=2). | The original text says "95% cluster bootstrap" in the metrics table and "Pocock 97.06%" in the stopping rule; the v1 harness used 95%. | One-sided error 2.8–3.9% against 1.8–2.5% (`POWER_ANALYSIS.md`, §2). | A few points of power. | No: this is a clarification. |
| **A2** | **Primary inference = linearised cluster-robust t interval**; the percentile bootstrap is reported alongside as a check. Both are computed; a disagreement is reported, and "confirmed" requires the primary only. | Percentile bootstrap at 30 clusters is slightly anti-conservative in the tails (up to 7% with a cross-fitted clock at K=3). | Size at Δ = 0: linearised 1.4–1.8% (exact clock) and 4.2% (cross-fit); bootstrap 2.0–3.7% and up to 7.2%. | Power 1–5 points lower than the bootstrap. | Yes (method choice). |
| **A3** | **Baseline for regime B = cross-fitted clock**: for each confirmatory cycle, the table from the 10 burn-in cycles plus **all other** confirmatory cycles (leave-own-cycle-out), used by score and baseline alike. The burn-in-only baseline of the original protocol is reported as secondary. | With a burn-in-only table the endpoint stops measuring "adds to the clock" and starts measuring "beats a 10-cycle clock". | False-positive rate where features only offset clock noise: **21% (30 cycles), 37% (60)**, 31% for the K=2 design; cross-fit: **4.2%, 3.8%**, 4.2%. Power loss ≤ 5 points. | The clock table is no longer fully frozen before testing; it is data-dependent but never uses the cycle being scored. | **Yes. This is the most consequential change.** |
| **A4** | **Burn-in data-quality criteria**, decided now, from data-quality metrics only (never performance): ≥ 98% of window minutes with bars per cycle; zero missing order logs; unique order ids; median order-timestamp skew ≤ 2 s; rule hash constant on every record; at least 10 cycles passing. If not met, burn-in extends by up to 5 cycles; the criteria may not be edited afterwards. | The original says burn-in is for "clearance clock, index behaviour, clock table" but defines no pass/fail. | `validation_config.json` → `A4_burn_in_data_quality`. | None. | Thresholds to be confirmed. |
| **A5** | **Sample size and looks**: record the minimum detectable effect (80% power) of the chosen design and **declare confirmation impossible below it**. Two options below. | The first look (30 cycles) is adequate only for effects ≥ +0.075; the design is blind to +0.025. | `POWER_ANALYSIS.md`. | Time. | **Yes.** |
| **A6** | **Disclose and add a causal secondary endpoint.** Every report of the primary ΔAUC must be accompanied by (a) the same score with features through the **previous** minute, and (b) an exploratory score using recorder prices up to the **order second**. Neither may select a rule. | The primary features contain prices after the order (F1); the strictly-pre-minute version showed no gain in development. | `OVERFITTING_AUDIT.md`, §2–3. | None. | No. |
| **A7** | **Operational rules** (implemented in v2): orders de-duplicated by order id; missing-bar rows and positives lost are counted per cycle; the primary endpoint is **not computed before the look**; every output block labelled confirmatory or exploratory; frozen hashes verified before any evaluation. | v1 allowed silent drops, double counting and peeking. | `tests/test_validation_audit.py` (19 tests; 5 injected bugs caught). | None. | No. |
| **A8** | **Roles by D-1 date**: development (before 25 Nov), regime-A forward (25 Nov–6 Dec, exploratory), burn-in (first 10 regime-B cycles), confirmatory (next 30 for look 1, next 30 for look 2), beyond protocol. A cycle is one index D-1 session; roles are fixed by calendar order, not by outcome. | The original definition is in prose only. | `bl_validation.assign_roles` (tested). | None. | No. |

## Options for A5
| | Option K=2 (original) | Option K=3 |
|---|---|---|
| Looks (confirmatory cycles) | 30, 60 | 30, 60, 90 |
| Nominal level per look | 2.94% | 2.21% |
| Total cycles incl. burn-in | 70 (≈ 35 weeks; verdict ≈ Aug 2027) | 100 (≈ 50 weeks; ≈ Nov 2027) |
| Power at +0.098 / +0.075 | 99.6% / 95% | 100% / 99% |
| Power at **+0.050** (exact clock; cross-fit) | **69% (72%)** | **84% (79%)** |
| Power at +0.025 | 18% (29%) | 26% (34%) |
| False positives at Δ = 0 (exact; cross-fit) | 1.8% (4.2%) | 1.8% (4.3%) |
| Minimum effect with 80% power | about +0.06 | about +0.05 |

**Recommendation (for the sponsor to decide):** adopt A1–A4 and A6–A8 before 7 Dec. Keep K=2 unless a 50-week horizon is acceptable. Either way, **write down that a true effect of +0.025 or less cannot be confirmed**, and that "not confirmed" then means "not detectable", not "absent".

## Consequences if adopted
* The primary endpoint, features, coefficients, window and decision rules (confirm when the lower bound is above 0 at the look's level; futility only at look 1 on a point estimate ≤ 0) are unchanged.
* The confirmatory claim becomes harder to reach (cross-fitting and the linearised interval remove two easy routes to a false positive), and it can no longer be reached early by looking sooner.
* The original protocol's burn-in-only baseline remains reported, so both versions are visible.

## Consequences if not adopted
* The regime-B test can "confirm" at 21–37% probability when the features carry no information beyond the true clock (A3), and the harness v1 behaviour (A1) inflates the error further. A confirmation obtained that way should not be believed.

## Not proposed (would change the frozen rule: future research only)
* A tick-resolution trigger that uses prices up to the order second in place of minute bars.
* A pair-burst rule (half the unmatched late orders are CE+PE bursts at 15:28–15:30).
* A shorter or longer ladder gate, the last-strike strike rule, or any change of reference.

## Adoption record
| date | decision | by |
|---|---|---|
| *pending* | | |
