# Sub-1.2× buy-backs: is there a loss-in-₹ / loss-in-%-of-capital trigger? — plan, written before the tests

**Question (user hypothesis).** Body buy-backs that are *not* explained by the lot's own premium ratio (33–40% of D-1 orders sit below 1.2×; 15–21% of all D-1 buy-backs have no identified basis) may be triggered by a **loss amount (₹)** or a **loss as % of capital** (capital ≈ ₹2 crore).

**Known context (read-only, from earlier work).** Capital ₹2 crore is "stated" in `Info.txt`, not verified. The `s_` cycle stop fires at ≈ −₹1.30 to −1.44 lakh cumulative LTP MTM (U8, OPEN, data-resolution limited) = 0.65–0.72% of ₹2 crore. Info.txt also states a "1% of capital" expiry-day and "4% carry" stop whose reading is unresolved. This study asks whether **body buy-backs below the stop level** react to loss levels.

## Locked definitions
* **Capital C = ₹2,00,00,000** (stated; only used to convert ₹ to %; a level in ₹ is reported with its % so another C can be applied).
* **Book P&L (cumulative, LTP mark):** fill-priced cash flows of **all modules** (body, hedge, stop, lump, manual; lot size NIFTY 65 / SENSEX 20) from the first D-1 fill of the cycle + mark-to-market of all contract-level net positions at the **previous completed minute close** (causal). D0 minute 0 uses the D0 open. Contracts missing from the chain use their last fill price (coverage reported). No costs, no slippage, no settlement.
* Variants (all pre-registered, none added later): **B_total** (since cycle start), **B_day** (since the start of the current day), **DD** (drawdown from the running maximum of B_total), **B_CE / B_PE** (P&L of CE contracts / PE contracts), **own-right loss** and **other-right loss**, **ΔB over 5 / 15 / 30 min**, and for the position itself **own strike-position ₹ loss** (lots × (price − entry) × lot size; vs the ratio).
* Targets: **A** = every D-1 buy-back below 1.2× on the cheapest-open-entry reference (438); **B** = the subset not co-closed within 3 s of a ≥1.5× buy-back (282, the "residual"); same for D0 as secondary.
* Level grid for threshold scans (₹ lakh, equivalently 0.125%–1.25% of C): 0.25, 0.50, … 2.50.

## Tests
1. **Book P&L builder + validation.** Cycles that end flat (24 of 35): the last-minute mark-to-market must equal realised cash P&L computed independently from the ledger (exact, up to missing prices). Compare with the U8 statement (stop cycles at −1.30…−1.44 lakh at the first `s_` order).
2. **Event table.** For every buy-back order, attach the book state at its minute. Compare B_total / B_day / DD / ΔB (in ₹ lakh and % of C) between classes: stop-like (≥1.5×), middle, sub-1.2× co-closed, **residual**.
3. **Hazard scan.** Cycle-minute hazard (cycle-minutes with body shorts open; event = ≥1 target-A / target-B buy-back) by bin of each variable; adjacent-bin steps.
4. **Predictive test.** AUC per variable with cluster bootstrap over cycles and a within-cycle permutation null (cycle-minute level; and contract-minute level controlling the 12 earlier variables via leave-one-cycle-out gradient boosting + permutation of the book features within cycle).
5. **Threshold-crossing event study.** For each level L on the grid, the first minute per cycle with B_total ≤ −L: count of target buy-backs in the next 5 / 15 minutes vs the same cycle's average rate (shifted-time null).
6. **Cycle-stop adjacency.** Share of target buy-backs within ±60 s of any `s_` order vs shifted-time null.
7. **Per-lot ₹ loss vs ratio.** AUC of own strike-position ₹ loss and per-lot ₹ loss vs the premium ratio.

## Decision rules (fixed now)
* A loss level is called a **trigger** only if (i) the target hazard steps ≥ 3× between adjacent bins of that variable, **and** (ii) adding the book variables raises leave-one-cycle-out AUC by ≥ 0.03 over the 12-variable baseline with the within-cycle permutation maximum below the gain, **and** (iii) (i) replicates in both chronological halves of the cycles. Otherwise "not supported".
* Cycles lacking a D-1 or D0 log are excluded from cumulative-P&L claims (unknown carry-in).
* A null result is reported as such; the residual stays Unresolved.

## Limits (known in advance)
Minute marks only; no costs/slippage; capital and the stop reading are stated, not verified; fills at second resolution; the true risk engine may use a different P&L definition (e.g. realised only, premium-based, per-basket), which the variants only partly cover. In-sample; 31 cycles with D-1.
