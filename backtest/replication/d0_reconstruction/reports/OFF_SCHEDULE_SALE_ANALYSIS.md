# Off-Schedule D0 Sale Analysis (Phase C, discovery cycles only)

**Result:** off-schedule D0 sales (2,675 orders / 2,905 lots in discovery) are **not** explained by ATM migration, spot movement or book imbalance, and the earlier claim that off-schedule sales are the most profitable class **does not reproduce** under the second-level classification: per-lot P&L is small and statistically indistinguishable across classes (scheduled ₹62, off-schedule ₹81, replacement ₹117 per lot; 95 % cycle-bootstrap intervals overlap zero for the first two). Code executed: `c_offschedule_discovery.py`, `lot_lineage.csv` (FIFO attribution — convention dependent, see `D0_PNL_ATTRIBUTION.md`).

## 1. Scheduled vs off-schedule vs replacement (discovery, order level)

| Class | Orders | Lots | Strike exactly nearest to ATM | Within ±1 step | Median offset (steps) | Wing paired | Wing lots per lot | Wing/body price | Own-side book share of the sale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Scheduled | 2,615 | 2,855 | **57.2 %** | 78.2 % | −0.04 | 62.9 % | 0.86 | 2.7 % | 1.4 % |
| Off-schedule | 2,675 | 2,905 | 40.6 % | 66.8 % | −0.13 | 64.3 % | 0.92 | 2.9 % | 1.1 % |
| Replacement | 2,380 | 4,118 | 31.3 % | 49.7 % | −0.12 | 41.5 % | 0.47 | 4.0 % | 1.2 % |

Off-schedule and replacement sales are **farther from ATM** than scheduled ones (IQR −0.8…+0.4 and −1.1…+0.8 steps vs −0.5…+0.35). Sizes are ~1 % of the own-side book in all classes.

## 2. Questions of the brief
| # | Question | Finding (discovery) |
|---|---|---|
| 1 | When? | Spread across the day (hours 9–15 each 156–440 lots); no clock beyond grid A found. A late burst (15:00–15:06) exists. |
| 2 | Concentrated around buy-backs? | By construction those within 60 s are labelled REPLACEMENT; off-schedule sales are those that are not. |
| 3 | After underlying movement? | Absolute 3-minute spot move before the sale: 0.24 steps (off-schedule) vs 0.19 (all-minutes null) vs 0.22 (scheduled). Barely above chance. |
| 4 | ATM migration? | Nearest strike changed in the previous minute: 15.7 % (off-schedule), 16.1 % (scheduled), 18.3 % (replacement) vs **12.5 % null**; over 3 min 20.1 % vs 20.0 % null; over 5 min 28.9 % vs 24.5 %. **Not supported.** |
| 5 | Restore a portfolio structure? | Share of sales that go to the lighter side of the CE/PE short book: 40 % (off-schedule), 47 % (scheduled), 39 % (replacement): no balancing. |
| 6 | Respond to short-premium changes? | Not tested separately (no premium state variable separates classes). Unknown. |
| 7 | Increase or decrease exposure? | They add short lots (by definition); sizes ~1 % of the side book; with the buy-back rate the net book still grows through the day. |
| 8 | Replace closed contracts or add exposure? | Not separable with the available identifiers (allocation ids are not in the export; ALC-01). Unknown. |
| 9 | Hedges? | 64 % paired with a wing within ~4 s, 0.92 wing lots per lot at 2.9 % of the body. |

## 3. P&L per lot by opening class (D0-opened body lots, FIFO, discovery; `c3_pnl_by_open_class_discovery.csv`)

| Opening class | Lots | Gross P&L (₹) | ₹ per lot | 95 % cycle-bootstrap CI (₹/lot) | Held to settlement |
|---|---:|---:|---:|---|---:|
| Scheduled | 2,855 | 178 k | 62 | −207 … +318 | 0 % |
| Off-schedule | 2,905 | 236 k | 81 | −207 … +409 | 1 % |
| Replacement | 4,118 | 482 k | 117 | +42 … +206 | 29 % |

The previous phase reported ₹35 / ₹294 / ₹78 per lot (scheduled / "other" / replacement; minute-level definitions, all 35 cycles). **That ordering is not robust:** with FIFO/second-level classes the three classes are within each other's uncertainty, and the attribution itself depends on the lot-ownership convention (under LIFO the D0-opened scheduled+off-schedule P&L is −₹7.2 L instead of −₹1.7 L in discovery; `pnl_attribution_fifo_vs_lifo.csv`). Higher historical P&L is **not** treated as evidence of a better entry rule.

## 4. D0 scheduled-sale quantity (discovery)
797 slot-legs: lots per slot-leg mean 3.6 (median 3, max 29). Spearman with slot index −0.34, with the own-side short book −0.09, with cycle MTM −0.07. A slot-mean model explains 26 % of the variance (R²), own-side-book deciles 2 %, index 2 %. **Quantity depends on the time slot, not on the book size** (decreasing through the day). CE = PE lots in 53 % of slots where both are sold (vs 81 % on D-1).

## 5. Late selling (≥ 15:00) and the 15:14 minute
718 orders / 1,584 lots (⌀ price ₹52, strikes twice as far from ATM: median |offset| 1.2 vs 0.6 steps), of which 749 lots at 15:14 in 5 cycles at ≈ ₹1 held to expiry (₹54/lot). Wing pairing only 29 %. Classified mostly as REPLACEMENT_SALE because of the simultaneous final buy-backs, so the label there is misleading. Trigger **Unknown**.

## 6. Verdict
No trigger for off-schedule sales was recovered; ATM migration, spot movement and book balance are rejected as explanations. They are a population of sales that is more dispersed in strike, similarly hedged and not distinguishable by profitability from scheduled ones in this sample.
