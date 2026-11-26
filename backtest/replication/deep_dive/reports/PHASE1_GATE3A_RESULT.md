# Phase 1, Gate 3a: buy-back stop reconstruction. Result

*2026-11-25. Plan `PHASE1_GATE3A_PLAN.md` (with Addenda 1-3), written before each step. Experiments `P1-3A-step1`, `step2` (and its archived first execution), `SL10/SL20/SL30` (`outputs/phase1/3A*`). Existing data only; B1 is the frozen baseline and was not changed. Evidence: historical reproduction on the 32 development cycles. Nothing committed.*

## Gate report
| Field | Content |
|---|---|
| Gate | 3a: body buy-back stop |
| Status | **CONDITIONAL**: no engine change is supported; the split between inherited and independent error is quantified; the independent trigger gap is not reducible with the tested mechanisms |
| Baseline | B1: real 1,324 buy-backs, simulated 933; recall 0.490, precision 0.689, F1 0.573; matched median timing -18 s, strike exact 46.5% (within one 75.3%), lots exact 99.7%, book L1 0.52, matched within 5 s 9.0% |
| Latest result | no variant changes the baseline; K6 best case (30 s latency) timing within 5 s 21.9% but buy-back F1 0.522 |
| Criteria | Step 1 (required first): done. Step 2 support rule (+0.03 F1, interval above 0, >= 20 cycles, LOCO >= 80%): **no mechanism passes**. K6 criteria (1)-(6): **fail** |
| Root causes | (a) **54.5% of missing buy-backs and 17% of extra ones are upstream** (the simulator holds fewer or no lots on that contract: position differences); (b) the rest is count/supply mismatch around existing buy-backs and an **independent trigger gap**: the real system bought back lots well below the 1.6x rule |
| Corrections | none (user condition: no compensation for missing body sells). `stop_latency_s` exists (default 0, tested, mutation-checked) |
| Regression | none (defaults identical to B1; SL runs leave other classes within 0.01) |
| Evidence | `outputs/phase1/3A_step1.json`, `3A_step2.json`, `3A/evaluation_K6.json`, `3A_step1_*.csv`, `src/bl_p1_3a_*.py` |
| Next action | Gate 3b (wing release) and 3c (lump) |

## Step 1: upstream versus independent (B1; reconciles to 1,324 / 933 / 675 / 290)
| Missing real buy-backs (675) | n | Share | Meaning |
|---|--:|--:|---|
| **U1** simulator holds no lot on the contract | 119 | 17.6% | upstream |
| **U2** simulator holds fewer lots than the real book | 249 | 36.9% | upstream |
| S supply: simulated buy-backs within 60 s, matched elsewhere | 142 | 21.0% | count / assignment |
| **I** independent: no simulated buy-back near, the engine rule would **not** fire on the real lot (median minute-high ratio 1.17, IQR 1.02-1.44) | 163 | 24.1% | trigger gap |
| R1 rule fires on the real lot but the simulator did not | 2 | 0.3% | |
**Upstream share of missing: 368 of 675 (54.5%).**
| Extra simulated buy-backs (290) | n | Share |
|---|--:|--:|
| XS real buy-backs within 60 s, matched elsewhere | 173 | 59.7% |
| **XU** the real book held no lot on the contract | 50 | 17.2% |
| XI ratio below 1.6 on the real lot | 34 | 11.7% |
| XR ratio at least 1.6 but the real system did not act | 33 | 11.4% |
**Upstream share of extra: 17.2%.** Supply mismatches run both ways (142 missing, 173 extra: nearly balanced), so a cluster-closing rule that adds buy-backs cannot be the missing piece.

## Step 2: stop mechanisms on the real position, each lot counted once (contract-minute, lots; real position, 1,314 of 1,324 real lots on a contract-minute with an eligible lot)
| Mechanism | F1 | Precision | Recall | vs K1 | Supported |
|---|--:|--:|--:|---|:-:|
| K1 engine rule (minute high >= 1.6x) | 0.251 | 0.391 | 0.185 | | baseline |
| K2 constant ratio (LOCO chooses 1.6 in 32/32 folds; 1.5 0.221, 1.7 0.230) | 0.251 | 0.391 | 0.185 | 0.000 | no |
| K3 previous-close basis | 0.271 | 0.676 | 0.170 | +0.020, interval [-0.079, +0.118], 19 of 32 cycles | no |
| K4 module-specific ratio (LOCO F1 0.232; best in sample = K1) | 0.232 | | | | no |
| K5 cluster closing (best 1.5: 0.218) | 0.218 | 0.286 | 0.176 | -0.034, interval [-0.057, -0.009], 13 of 32 | no (worse) |
**Reading:** even with the real position, the engine's rule reproduces only **18.5% of the real buy-back lots**; precision is moderate (39%). Raising precision (K3) trades away recall. This agrees with the earlier finding that about half of the events have no recoverable trigger at minute resolution. The contract-minute F1 here (0.251) is **not comparable** with the earlier 0.588 (that counted events on the real book with different matching and repeats); mine counts lots once, at their first qualifying minute.

## K6: stop latency (execution convention; timing only)
| Latency | Matched within 5 s (B1 9.0%) | Buy-back F1 (B1 0.573) | Wing sell F1 (B1 0.497) | Criteria |
|---|--:|--:|--:|---|
| 10 s | 6.1% | 0.572 | 0.489 | fails (1) |
| 20 s | 11.9% | 0.567 | 0.488 | fails (1): +2.9 points, needs +5 |
| 30 s | 21.9% | **0.522** | **0.454** | fails (2) and (4): timing improves, recall and wing sells fall |
No latency satisfies all criteria; not adopted, not an open decision.

## Classification and conclusion
* **Body buy-back stop: Decoded** (own-premium stop at about 1.6x of entry on the minute high; best of the tested rules) **for the part it explains; independent trigger gap Unresolved**, quantified at 163 missing orders classed independent (12% of all real buy-backs) plus the count mismatches.
* **Inherited error: 54.5% of missing buy-backs trace to upstream position differences** (body sells, chiefly), consistent with the TF-E recovery (buy-backs only 6% recovered by state correction, because the rest are not state-driven; the 54.5% here is position, not state memory).
* Wing sells inherit the buy-back timing (median 18 s early) and so stay Partial.

## Limits
Same development cycles; lot entry price is the real average fill and which lot a real buy-back closed is not in the log (cheapest-entry-first is the convention); the minute-bar high is an upper bound of the intrabar touch; module labels inferred; first-execution of Step 2 archived (repeat counting) and corrected before any conclusion.
