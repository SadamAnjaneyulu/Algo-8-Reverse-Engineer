# Pre-registration: D0 rule set v1 (frozen before holdout evaluation)

**Split.** Discovery = cycles with D0 < 2026-09-23 (25 cycles with D0 fills, 22 with a known carry-in book). Holdout = D0 ≥ 2026-09-23 (the TEST boundary used by the earlier exit-engine research; 9 cycles, 8 with D0 fills, all 8 with known carry-in: SENSEX 09-24, 10-01, 10-08, 10-15, 10-22; NIFTY 10-06, 10-13, 10-19). NIFTY 2026-09-29 has no D0 data. **Disclosure:** the earlier exit-engine research already *scored* these TEST cycles for other models, and my Phase-4 descriptive tables pooled all 35 cycles (aggregates only, no rule fitting). The holdout is therefore **partially exposed**, not pristine; conclusions are weakened accordingly.

**Rules (parameters in `results/rules_d0_v1.json`, fitted on discovery only by `fit_discovery.py`).**
* S1 scheduled sales: at grid-A minutes (mm%15 = 1 from 09:16) while the book is active, sell the per-slot, per-right median lots of scheduled sales (discovery), at the strike nearest the previous-minute spot, plus wings (price ratio 2.44–2.9 % of the body).
* S2 Clock-B tick (mm%15 = 14 from 09:29): act iff total short body lots ≥ threshold (max-F1 on discovery ticks); buy back 1 lot of the largest short contract; sell 1 lot at ATM the next minute (replacement).
* S3 price stop (variant V1 only): buy back a body lot when price ≥ 1.6 × its own entry (HYPOTHESIS; weak on D0).
* S4 final flatten at 15:14: buy back all body shorts and sell all wings.
* Cycle stop: liquidate everything when LTP MTM ≤ −₹1.44 L.
* Variants: **NULL** (S4 + cycle stop only; control), **V0** (S1+S2), **V1** (V0 + S3).
* Start state of every D0: the **actual** overnight book from the ledger; lump/stop-module/manual lots are passive.

**Evaluation (identical code `compare_events.py`, `run_replay.py`).** Hierarchical count-based matching (L1 exact strike & 2 min, L2 any strike & 2 min, L3 any strike & 10 min). **Pre-registered pass criterion for a rule category:** L2 precision ≥ 0.50 **and** L2 recall ≥ 0.50 on the holdout, and better than NULL. Also reported: portfolio-state correlation/MAE at hourly marks, D0 P&L increment vs actual, stop-cycle agreement. No rule is promoted to "confirmed" by this holdout alone (n = 8 cycles).

**If a rule fails:** the failure is recorded; any modification creates version v2 that needs a new, independent validation period (none exists in the 35-cycle ledger; forward live data or a new export is required). No rule or parameter is changed after the holdout run under this version name.
