# Algo 8 exit engine — deep reconstruction (sections 1–3 of the brief)

Branch `research/algo8-exit-engine` (stacked on `claude/friendly-galileo-r3zezw`). Existing research, branches, reports and `alpha_freeze/` (hashes verified) are untouched; all new code is in `analysis/exit_engine/`.
Reproduce: `ledger.py` → `taxonomy.py` → `panel.py` → `triggers.py`, `stop_shape.py`, `carry_stop.py` (needs the Breeze caches built by `analysis/market.py`; see main FINDINGS). Outputs in `analysis/exit_engine/results/`.
Sections 4+ of the brief were truncated in the request ("4. First-passage and co…") and are **not yet done**.

## 1. Data products
* **Exit ledger** (`exit_ledger.pkl`): 15,450 closing orders (10,028 short buy-backs, 5,422 long closes), each with state known **before** the decision: lot-level entries (own / cheapest / average / FIFO / LIFO), recovered quote (limit band), contract/side/strike/cycle P&L and cycle peak, Greeks at decision vs entry (BS on Breeze closes), spot move in ATR units, IV and RV, time since entry / last sale / last buy-back, time to expiry, inventory concentration. Decision time = tag microsecond timestamp where present (`h_`/`s_`/`v_`/`m_`), else first fill.
* **Contract-minute panel** (`exit_panel.pkl`): 209,106 open-short contract-minutes (D‑1 and D0, before any cycle stop), causal features, labelled with the exit category.
* Inventory is tag-agnostic per contract; **cross-module netting** exists (176 short buy-backs sent by the wing module `h_`; 1,044 body sells that closed longs) and is flagged, not forced.

## 2. Exit taxonomy (primary label by precedence + independent flags; `taxonomy.py`)
Short-side buy-backs, share of lots (realised vs average entry, ₹ lakh):

| # | Category | Lot share | Realised | Notes |
|---|---|---:|---:|---|
| 1 | Individual lot stop-loss (quote ≥ 1.45× cheapest entry) | 25.6 % | −45.1 | 64 % first-passage; 52 % followed by a same-side re-sale within 60 s; 46 % inside basket episodes |
| 2 | Same-contract partial buy-back (residual) | 5.0 % | +12.8 | |
| 3 | Side-level reduction (≥2 contracts, one side, ≤10 s) | 11.1 % | +22.9 | median exit 0.58× entry |
| 4 | Basket-level reduction (both sides) | 5.6 % | +8.5 | |
| 5 | Cycle stop & liquidation (`s_`, or after the first `s_`) | 14.2 % | +7.1 | |
| 6 | Clock-based exit: final flatten ≥ 15:10 D0 / clock-B without replacement | 11.6 % / 2.7 % | +37.9 / +6.6 | |
| 7 | Expiry-day salvage (≤ ₹1 or ≤ 5 % of entry) | 12.7 % | +78.6 | |
| 8 | Clock-B rebalance (with same-side sale ±60 s) / grid-A rebalance | 4.6 % / 5.1 % | +11.6 / +9.0 | |
| 9 | Trailing stop / target | **not assigned** | | no crisp trailing rule found (§3) |
| 10 | Manual / platform risk engine (`m_`, AlgoId 152432, 2.18811E+15) | 1.0 % | +1.4 | |
| 11 | Unexplained | 0.8 % | +0.4 | nothing predicts it (all families negative) |

Long-side closes (wings/lump): salvage 6,536 lots, hedge release with a same-side short close ≤60 s 4,653, cycle stop 1,582, platform 1,041, unexplained 910, final flatten 466, lump disposal 292.

## 3. Triggers (information available before each decision)

**Feature families vs exit category** (OOS AUC gain over a timing+inventory baseline, 3 chronological folds):

| Category | Base AUC | Families that add signal |
|---|---:|---|
| 1 Lot stop | 0.684 | **premium ratio +0.28** (P&L, drawdown, spot-ATR, Greeks are proxies of the same move) |
| 4 Basket reduction | 0.727 | **spot move in ATR +0.155**, premium +0.14, drawdown +0.14, time-since-trades +0.12 |
| 2 Partial | 0.716 | premium +0.08, spot +0.07, since-trades +0.06 |
| 3 Side-level | 0.839 | small (≤ +0.05): mostly clock/time |
| 8 / 8b / 6 clock exits, 7 salvage | 0.93–0.98 | none beyond the clock |
| 11 Unexplained | 0.686 | none |

**Static vs dynamic vs trailing**
* **Static level on the entry day.** Lot-stop hazard turns on at **1.45–1.55× the cheapest open entry** (per-minute hazard 0.45 % → 1.1 % → 3.0 %) at the same place across TTE, IV change, adverse spot move, index and entry premium. On **D‑1 it is crisp** (40 % per minute at 1.7–2.0×, 75 % at 2–3×); median delay from first minute-high crossing to exit is **1 min** (75 % within 4 min).
* **No points floor.** `entry + max(a·entry, b)` does not beat the pure ratio (best a = 0.55: recall 0.548 vs 0.547).
* **Dynamic by scope, not by level.** On **D0** the hazard is much weaker (≤ 14 % per minute). Lots **older than 2 h** are rarely stopped. **Carried (D‑1) lots on D0 have no per-lot premium stop** under any reference tested (own entry, D‑1 close, D0 open) and no spot-% stop since D‑1 close (all hazards ≤ 2–5 % per minute). Carried inventory is governed by the cycle stop and scheduled exits. The Info.txt "4 % carry-forward SL" is **not** visible as a per-lot premium or spot rule; it remains undecoded.
* **Trailing: not supported as a rule.** In-profit exits rise only gradually with the bounce off the running low (≈1 % → 2–5 % beyond 1.5–2×, ~6–10 % beyond 3×) and with drawdown from the contract's peak P&L (0.7 % → 5.3 %). There is no threshold, and the same rise is explained by clock exits and rebalances after price swings.
* **Cycle stop** (from earlier work): cumulative LTP-MTM ≈ −₹1.30–1.35 L with 1–20 s check latency.

## Open (pending sections 4+ of the brief)
Exact rules for side/basket reductions (adverse ATR moves are the main signal), the D0 per-lot stop scope (which lots carry it), Clock-B lot selection, and the carry-forward 4 % SL.
