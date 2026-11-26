# Post-auction rebuild — result

*Plan: `POSTCAS_REBUILD_PLAN.md` (committed before the simulator was changed). Exploratory; real-log cycles split into development (D0 3 Aug – 15 Sep 2026) and validation (D0 16 Sep – 22 Oct 2026).*

## Verdict
* **The rebuild failed its pre-registered validation** (mean absolute error per cycle on validation ₹192,066 → ₹201,026, stop agreement 5 → 5 of 11). By the plan's rule the original simulator is kept for the verdict.
* **The battery re-run on the rebuilt simulator gives the same result: NO-GO, 5 of 8 gates** (G4, G5, G8 fail in both). The post-auction era stays negative in the simulator (₹-43,796 → ₹-37,473 per cycle).
* **What is actually wrong:** not a post-auction mechanism but the expiry-day reconstruction itself. Cycle by cycle the simulator's D0 trading departs from the real one, most in the newest timetable versions (B/V2 from 16 Sep 2026). Fixing that needs more real post-auction cycles than exist (the real log ends on 22 Oct 2026); any further change would have to be tuned on the same 11 validation cycles.

## 1. Diagnosis (real vs simulator, means per cycle)
| era | src | D-1 P&L | D0 P&L | total | D-1 lots sold | D0 lots sold |
|---|---|---|---|---|---|---|
| after | real | 12,876 | 56,016 | 68,891 | 182 | 587 |
| after | sim | 7,597 | 24,534 | 32,131 | 147 | 623 |
| before | real | 43,418 | 42,503 | 85,921 | 157 | 1,000 |
| before | sim | 64,967 | 61,985 | 126,951 | 138 | 756 |

* After the auction the gap is mainly on expiry day; volumes are similar, management differs.
* The simulator's cycle stop fired in 12 of 23 post-auction cycles vs 9 in the real log, and stopped 5 cycles the real system never stopped. Real stop triggers sit at −₹1.36 to −₹1.47 lakh; the simulator used a fitted ₹1.2 lakh.
* Real behaviour not modelled (cache ends 15:29): the overnight lump is bought after 15:30 since the auction (median minute 375 vs 358 before); final clearance on D0 runs a few minutes past 15:14; derivatives trade until 15:40.

## 2. The change tested (R1) and its validation
R1: cycle stop = median real trigger of the non-opening stops in the development period (−₹1.533, −₹1.394, −₹1.448 lakh) → **₹1.45 lakh** (was ₹1.2 lakh). No other change.

| group | sim | cycles | real mean (₹) | simulator mean (₹) | mean abs. error (₹) | spearman | stops agree | simulator-only stops | real-only stops |
|---|---|---|---|---|---|---|---|---|---|
| development | old | 12 | 88,300 | 78,144 | 93,802 | 0.92 | 11 | 1 | 0 |
| development | new | 12 | 88,300 | 76,554 | 94,513 | 0.93 | 12 | 0 | 0 |
| pre-auction live | old | 12 | 85,921 | 126,951 | 129,726 | 0.36 | 11 | 0 | 1 |
| pre-auction live | new | 12 | 85,921 | 124,314 | 128,631 | 0.36 | 11 | 0 | 1 |
| validation | old | 11 | 47,719 | -18,065 | 192,066 | 0.67 | 5 | 4 | 2 |
| validation | new | 11 | 47,719 | -27,025 | 201,026 | 0.65 | 5 | 4 | 2 |

* Accept rule: validation error falls **and** stop agreement does not fall **and** pre-auction error rises ≤ 10% → **not met** (validation error rose; agreement unchanged; 4 simulator-only stops remain because the simulator's book loses more than the real one in those cycles, not because of the threshold).
* Validation cycles show the real reason: e.g. 1 Oct 2026 — real D0 sold 679 lots and made ₹2.93 lakh, the simulator stopped at 09:16 after 82 lots; 13 Oct — real sold 309 lots and stopped, the simulator sold 1,080 and did not.

## 3. Battery: original vs rebuilt simulator (gates unchanged)
| gate | passed original | passed rebuilt | rebuilt value |
|---|---|---|---|
| G1 Costs | PASS | PASS | mean net ₹70,989 (all) / ₹54,238 (OOS) / ₹32,541 (costs ×1.5, slippage ×2) |
| G2 Execution | PASS | PASS | mean net with 1-minute delay ₹43,820 |
| G3 Parameter stability | PASS | PASS | no ±20% / ±5-min change flips or halves the mean |
| G4 Overfitting | FAIL | FAIL | PBO 0.89; Deflated Sharpe 1.00 at N = 83 (1.00 at N = 1,000) |
| G5 Noise floor | FAIL | FAIL | real timetable ₹70,989 vs random-timetable null: 95th pct ₹72,912; real above 90% of 20 null runs |
| G6 Path / tail | PASS | PASS | 1-year 95th-pct max drawdown ₹29.3 lakh; P(1-year loss > 10%) 0.1% |
| G7 Capacity | PASS | PASS | 98.7% of fill volume at ≤ 10% of minute volume |
| G8 Margin-capped book | FAIL | FAIL | mean net ₹63,934; 11.3% of cycles still above ₹2 crore |

* Headline: mean net ₹70,801 → ₹70,989 per cycle; OOS ₹54,242 → ₹54,238; break-even 2.31× → 2.28×; PBO 0.60 → 0.89; random-timetable null: real above 95% → 90% of runs.

By era (simulator mean net per cycle):
| era | cycles | mean_net original (₹) | mean_net rebuilt (₹) |
|---|---|---|---|
| Nov 2023 – Sep 2024 (STT 0.0625%, NSE fee 0.0495%) | 63 | 65,388 | 58,156 |
| Oct 2024 – Mar 2026 (STT 0.1%) | 149 | 95,041 | 98,215 |
| Apr – 2 Aug 2026 (STT 0.15%) | 34 | 72,347 | 67,966 |
| from 3 Aug 2026 (STT 0.15% + closing auction) | 29 | -43,796 | -37,473 |

## 4. What this means for paper trading
* The verdict stays **NO-GO**. The reconstruction is not reliable enough in the current regime to stand in for Algo 8 on paper.
* A legitimate path: **paper-trade by shadowing, not by simulating** — log the real system's decisions (or a broker-side copy) forward from now, and use the simulator only as a reference; or collect more real post-auction cycles (≥ 30) before any further rebuild, split in time, with the rebuild frozen before the validation cycles are looked at.
* Nothing here changes the alpha findings (`FINAL_ALPHA.md`); it limits what the simulator can be trusted for.
