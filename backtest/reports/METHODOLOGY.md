# Methodology
## 1. The engine and how data enters it
`portfolio_engine/construction`: Python reference (`pc`) and C++ runner (`pc_run`), both reading the same scenario text. Flow at every evaluation time t: seed fills with ts <= t are applied to the position ledger (the historical `PortfolioState.apply_fill`) -> each enabled plugin sees a read-only context (marks and baskets with timestamps <= t) -> proposed CUT / REENTRY actions are checked by the risk validator (atomic groups) -> accepted actions become new fills at the latest mark <= t. Plugins never touch the ledger. The engine has **no** entry logic (baskets enter only as `LEG` seed lines), **no** settlement, costs, slippage or margin, and only knows `basket_cut`, `basket_reentry` and `scripted_actions`; I added `capital_stop` (Python and C++, 5 tests, documented in `plugins/stop.py`). The scenario file carries a fixed `SYNTHETIC_TEST_ONLY` evidence stamp that the loader requires; I left it unchanged and marked the description `HISTORICAL_BREEZE_REPLAY`.
Adapter (`bt/`): one scenario per cycle built from the pinned dataset commit: instruments (4 contracts), seed fills (entry), one MARK per completed 1-minute bar (timestamp = bar start + 60 s, price = bar close) and one TICK per minute. No bar is visible before it completes, entries are at the bar open, nothing after D0 is read except the official close for settlement. Marks are last-trade closes including carried zero-volume bars; missing bars leave the previous mark in place.
## 2. Cycles and split
One cycle = one weekly expiry (D-1 + D0). Used only if the validation status is Complete: 275 cycles (NIFTY 154, SENSEX 121), all feasible under the entry rule. Excluded and counted, never skipped silently:
| und | split | status | cycles |
|---|---|---|---|
| NIFTY | EMBARGO | Complete | 1 |
| NIFTY | IS | Complete | 105 |
| NIFTY | IS | Missing | 1 |
| NIFTY | IS | Partial | 1 |
| NIFTY | OOS | Complete | 49 |
| NIFTY | OOS | Missing | 1 |
| NIFTY | OOS | Partial | 2 |
| SENSEX | IS | Complete | 70 |
| SENSEX | IS | Missing | 34 |
| SENSEX | IS | Partial | 3 |
| SENSEX | OOS | Complete | 51 |
| SENSEX | OOS | Missing | 1 |
| Period | Dates | Rule |
|---|---|---|
| In-sample (IS) | first available session (NIFTY 2023-11-08, SENSEX 2024-05-30) to 2025-11-17 | by D0 date |
| Embargo | cycle with D-1 <= 2025-11-17 < D0 (NIFTY expiry 2025-11-18) | dropped |
| Out-of-sample (OOS) | 2025-11-18 to last expiry (NIFTY 2026-11-09, SENSEX 2026-11-12) | by D0 date |
|   OOS exposed | D0 2026-06-22 to 2026-10-22 (inspected during Algo 8 reverse engineering) | subset |
|   OOS clean (before) | D0 2025-11-18 to 2026-06-21 | subset |
|   OOS clean (after) | D0 2026-10-23 on | subset |
## 3. Basket construction (Algo 8 observed structure, rulebook v0.6 'Observed', not decoded)
Decision 09:16 on D-1; K = step x floor(S/step + 0.5), S = close of the 09:15 spot bar (so no D-2 or future price is used for the trade; D-2 was only used to choose which strikes were downloaded); short CE and PE at K; long CE at K+W and long PE at K-W (W 2,000 NIFTY; 4,000 SENSEX, 2,000 from 2026-09-16); three lots per leg; lot size inferred per session from the gcd of option volumes (NIFTY 50/25/75/65, SENSEX 10/20, consistent with the exchange revisions). Each leg enters at the open of the first traded bar (volume > 0) in 09:16-09:20. If a wing never traded in that window the nearest strike toward ATM that did is used (a wing was substituted in 54% of NIFTY and 31% of SENSEX cycles); the average distances were NIFTY 1,916/1,969 points (CE/PE) and SENSEX 3,756/3,776.
## 4. Exit variants
HOLD_SETTLE: carry to expiry; settle at the intrinsic value of the official close (15:30 spot bar; Yahoo daily close when absent; recorded per cycle). The dataset has no settlement price, so this is a proxy. FLATTEN_1525: engine ticks stop at 15:25; open inventory is closed at the 15:25 mark with slippage and costs.
## 5. Execution, costs, margin
Gross = engine reference prices + settlement. Net = trades re-priced for delay and slippage (base max(Rs 0.10, 0.5% of price) against every order), minus Rs 20 brokerage per order, NSE 0.035% / BSE 0.0325% transaction charge, SEBI 0.0001%, stamp 0.003% on buys, GST 18% on (brokerage + transaction + SEBI), STT on sells 0.0625% (to 2024-09-30), 0.1% (to 2026-03-31), 0.15% after, exercise STT on long ITM options 0.125% / 0.15%. The 2026 STT change is confirmed by reports; the other rates are quoted from memory and **unverified**. There is no bid/ask in the data: slippage is an assumption and is stressed (3x, 6x, delay). Margin = worst-case expiry loss of the open positions with premiums ignored (a proxy, not exchange SPAN; real margin and broker terms are unknown). Capital = Rs 2 crore as stated in Info.txt (not verified), constant; peak combined margin proxy 6,446,250 (32.2% of capital, at most 2 baskets at once).
## 6. Metrics
One return per expiry cycle, aggregated to ISO weeks, divided by Rs 2 crore; Sharpe and Sortino annualised with sqrt(52), risk-free 0, no compounding. Drawdown from the minute-level mark-to-market equity path. Annualised return = total net P&L / capital / years of data. A 'trade' is one basket cycle; order counts are reported separately. Sharpe is not computed from individual orders.
## 7. Selection and freezing
Pre-registered in `PREREGISTRATION.md` before any in-sample grid result was seen: 26 configurations; per exit variant the best in-sample net P&L replaces plain holding only if it beats it and is positive in at least 2 of 3 chronological thirds. Result: HOLD_SETTLE -> `cut_t20000_f10000_re_cd1800band` (in-sample Rs 520,143 vs holding Rs 497,091); FLATTEN_1525 -> HOLD (the best candidate failed the thirds test). Frozen at code commit `05433d73d0d86fb9be0d357e5b49f28e87cfebe1`, then committed, then the out-of-sample accounting was run once.
Walk-forward (expanding window, applying the same rule), HOLD_SETTLE:
| fold | chosen | val_net_chosen | val_net_hold | val_cycles | best_in_hindsight | val_net_best |
|---|---|---|---|---|---|---|
| 2024-11-18..2025-02-17 | cut_t5000_f10000_re_none | -35,923 | 13,255 | 25 | cut_t10000_f10000_re_none | 89,303 |
| 2025-02-18..2025-05-17 | cut_t10000_f10000_re_none | -14,348 | -32,320 | 24 | cut_t20000_f10000_re_cd1800band | 54,182 |
| 2025-05-18..2025-08-17 | cut_t5000_f10000_re_none_STOP | 66,722 | 435,160 | 26 | cut_t5000_f10000_re_cd1800band | 463,445 |
| 2025-08-18..2025-11-17 | cut_t20000_f10000_re_cd1800band | 82,675 | 74,204 | 24 | cut_t20000_f10000_re_cd1800 | 100,490 |
The selection procedure earned Rs 99,126 across the four validation blocks against Rs 490,299 for plain holding.
## 8. Verification
13,525 engine runs, each executed by Python and C++: 13,525 byte-identical. Accounting vs engine ledger: in all stop-out cycles the engine's FIFO realised P&L equals the accounting gross P&L exactly. 10 harness tests, 5 plugin tests, existing engine suite (175 + 5) and C++ checks (100/100) pass.
