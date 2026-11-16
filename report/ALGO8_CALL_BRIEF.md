# Algo 8 — call brief for Rahul (11 November 2026)

Companion to `ALGO8_COMPLETE_RESEARCH_REPORT.md` (section numbers below refer to it). No new experiments; every number is
from PRs #1–#6.

**What we set out to do.** Reverse-engineer Algo 8, a NIFTY / SENSEX weekly-options strategy run for client GKOHNP140 with
₹2 Cr capital and a three-sentence brief ("BTST … 4 % carry SL … 1 % on expiry day"). The inputs were its fills-only broker
export (39,874 orders, 35 weekly cycles, Jun–Oct 2026) and Breeze 1-minute candles. Separately, look for independent alpha.

## Five most important findings

1. **Structure is reproducible; decisions are not.**
   - What reproduces: the 09:16 ATM opening, 17 pre-expiry clock windows (544 / 544), one-lot child orders (65 / 20), wings at ≤ 2.5 % of the ATM leg, limit = LTP × 1.15 / 0.85, and a cycle stop at ≈ −₹1.30–1.35 L MTM.
   - 0 of 19 components are exact (readiness index 34 %, a subjective score) (§3, §8).
2. **A data defect was caught.** Column 4 "order id" is reused across days: it hides 2,616 orders (6.6 %). Everything since uses column 163 (`UniqueOrderIdentifier`), and the first exit-engine results were withdrawn (§2.1).
3. **The per-lot stop is real but not a single rule.**
   - On D-1, 88 % of crossings of 1.7× the cheapest entry are followed by a buy-back within a minute.
   - About 95 % of stop buy-backs happen at ≥ 1.5× the lowest entry.
   - No reference + constant reaches 80 / 80 (0 of 18 rules; best TEST precision 0.27, recall 0.63).
   - It closes one lot at a time and is weak on expiry day (§4.2).
4. **No model reproduces the decisions.** Exit classifiers on TEST: lot stop P 0.27–0.37 / R 0.52–0.68; side-level 0.21 / 0.40; basket 0.19 / 0.28 (PR #3). The ML decision engine: 0 of 20 tasks at its 75 / 75 standard; its replay predicted no orders (PR #1). Autonomous replay matches ≈ a quarter of exits (§4.8, §6).
5. **Re-sales follow buy-backs only within ≈ 60 s; allocation ownership cannot be inferred.**
   - Clock-B rebalances and lot stops: 3–4× chance in the first minute; nothing after side-level reductions.
   - Ownership is identified for 3.5 % of replacement pairs (§5).

## What we reconstructed vs what remains unknown

| Reconstructed (approximately) | Unknown (not identified in the available data) |
|---|---|
| Weekly cycle, D-1 build-up / D0 management | Extra-entry trigger; later quantities beyond a modal ladder |
| Opening book, ATM strike rule, seed wings, wing budget | Exact stop reference and why most 1.5× crossings are not stopped |
| Pre-expiry schedule; D0 entries while the book is active | Clock-B act / no-act and contract choice |
| Base unit, pricing, module tags, exact P&L replay | Side-level, basket and partial-reduction triggers |
| Cycle stop band; 15:14 flatten (later period) | Replacement strike / quantity; allocation ownership; sizing; lump size |
| Stop anchored to an individual entry, not the contract average | "4 %" and "1 %" rules; short fills seen just after 7 of 12 cycle stops |

## Has alpha been demonstrated? No.

- **Algo 8's own P&L:** +₹15.5 L gross over 30 cycles (t = 1.39). It is the carry of options sold (+₹31.1 L), mostly calls in a falling market, minus management, wings and lump. There is no timing, sizing or directional skill.
- **Market ATM straddle premium:** +3.9 bp, 95 % CI [−12.3, +19.3], so not significant.
- **Best searched candidate:** BTST afternoon short straddle with a 1.55× stop, from 4,512 configurations. Reality check p = 0.104, PBO = 0.25. It is frozen (H1) for a locked out-of-sample test that has **not been run** (no new data yet).
- **OHLCV alpha screening** (Track B): **not run**.

## Next research priorities (ranked)

1. **Locked out-of-sample test of H1** on 2025–26 data. Needs Breeze credentials and confirmed lot sizes.
2. **More Algo 8 trade months**, to validate the reconstructed rules unchanged.
3. **Phase 2 Track B:** five pre-registered alpha families. Quick to run.
4. **Phase 2 Track A:** do OHLCV features add anything beyond premium-vs-entry and cycle MTM?
5. **Explain the post-cycle-stop fills**, and request order-lifecycle records.

## Difficult questions Rahul may ask

**Q1. Have you recovered the algorithm?**
No. We can describe what it does and build an approximate replica, but no component is exact, no exit model reaches
80 / 80, and replay matches ≈ 24 % of exits (TEST, Mode A, minute-open fills). The missing inputs are decision logs,
allocation ids and order lifecycle; more modelling on this sample would not close the gap (§4.8, §8).

**Q2. PR #2 said the stop is 1.55× with 74 % reliability. Is that wrong?**

- The 74.1 % reproduces under its own definition, but it is inflated: 22 % of events had an exit before the trigger, 851 of 1,045 were follow-on lots, and 88 fired on already-closed lots.
- Population-matched, the rates are 58 % vs 68 % (2 min).
- The evidence supports a D-1 band near 1.6–1.7× and a necessary ≥ 1.5× edge. No exact constant is supported (§4.2).

**Q3. Isn't the ML failure just weak models or overfitting?**
Unlikely to be the cause:

- **Coverage:** logistic, LightGBM, CatBoost, GAM, hazard models and trees were all tried, on chronological whole-cycle splits with thresholds fixed before TEST.
- **Two lineages, same ceiling:** different targets, same result.
- **Ablation:** performance comes from the premium ratio and spot move, while removing Greeks, IV, inventory or clock costs nothing (§4.8).
- **What it suggests:** the limit is missing information, not model capacity.

**Q4. Algo 8 made money — why isn't that alpha?**

- The profit decomposes into option carry minus management.
- It shows no timing (−0.3 bp D-1, −3.0 bp D0), sizing (p = 0.34) or directional skill.
- It is concentrated in short calls during an ≈ 7 % NIFTY fall.
- Lineage X's independent attribution turns negative after removing the two largest winners (§9).

**Q5. How do you know there is no look-ahead or selection bias?**

- **Look-ahead:**
  - Splits are chronological by whole cycle.
  - The OHLCV library passes 25 leakage tests and catches 12 / 12 injected leaks.
  - Teacher-forced replay reproduces P&L exactly.
- **Selection bias:**
  - Every date has been inspected.
  - TEST is contaminated for hand-derived constants.
  - The best searched strategy fails the reality check.
- **So:** everything is exploratory, and only the locked OOS test on new data can confirm anything (§10).
