# Data manifest — OHLCV indicator and alpha research (Phase 0)

Branch `research/algo8-ohlcv-indicator-alpha`. Output directory `ohlcv_research/` only. Nothing in `alpha_freeze/`, the stop models, PR #1–#5
findings or the raw trade file is modified. Every number below was produced by [`data_audit.py`](data_audit.py) and
[`build_features.py`](build_features.py) (executed; outputs in [`results/`](results/)). Audit report:
[`results/data_audit_report.txt`](results/data_audit_report.txt).

## 1. Fields used, and fields deliberately not used

| Used | Not used (by constraint) |
|---|---|
| open, high, low, close; option volume; bar timestamps; underlying, expiry, strike, right; the clean Algo 8 order ledger | bid / ask, order book, Greeks, IV surface, **open interest** (present in the option files; never loaded), institutional positioning, decision logs, original parameters |

The loaders in [`common.py`](common.py) read only the columns in the left-hand cell; a unit test asserts it.

## 2. Sources

| Dataset | Source | Coverage | Rows |
|---|---|---|---:|
| Index 1-minute bars (NIFTY, SENSEX) | Breeze, `data/breeze/normalized/indices` (branch `data/local-breeze-fetch`) | 85 sessions per index, 22 Jun – 22 Oct 2026 | 63,678 |
| Option 1-minute bars | Breeze, `data/breeze/normalized/options` | 3,243 contract-days, 23 Jun – 22 Oct 2026 | 1,230,065 (1,210,547 in session) |
| Algo 8 order ledger | PR #3 clean ledger (column-163 key) | 39,874 orders, 35 cycles, 65 underlying-sessions | 39,874 |

The market files are not in this branch; set `ALGO8_MARKET_DIR` to the `normalized` folder. Derived tables go to the git-ignored
`ohlcv_research/_cache/`.

## 3. Quality findings

| Check | Result |
|---|---|
| **Granularity** | 1 minute; every timestamp on a whole minute. |
| **Timezone** | All timestamps carry `+05:30` (IST). Ledger fill times are epoch seconds converted to IST. |
| **Bar label = bar START** | **Confirmed against the ledger:** 97.3 % of 41,421 Algo 8 fills lie inside [low, high] of the bar labelled with the fill's own minute, against 61.3 % for the next bar and 58.7 % for the previous one. The 2.7 % outside are small (median ₹0.25) and 65 % of them fit an adjacent bar: second-level clock skew at minute edges. |
| **Duplicates** | None (index or option); one file per session / contract-day. |
| **Index sessions** | 85 per index, identical dates. Weekdays without a session: 26 Jun, 14 Sep, 2 Oct, 20 Oct 2026. |
| **Index missing bars** | 72 minutes in total, all in the last 8 sessions (12–22 Oct): 15:16–15:19 every day, plus 15:29 on some. No interpolation is applied. |
| **Index OHLC sanity** | 0 inconsistent rows; 0.9 % zero-range bars. |
| **Index volume** | **Invalid: `provider_volume` is 0 in all 63,678 rows.** No index volume, VWAP, OBV or CMF feature can be built. |
| **Option session bars** | 95.2 % of contract-days have all 375 bars; 97.8 % have ≥ 370; 28 contract-days have < 300. Consecutive-bar gap is 1 minute for 99.5 % of bars; maximum gap 40 minutes. |
| **Option post-close bars** | 19,518 bars at **15:30–15:39** (0.84 % of volume). They are dropped everywhere. |
| **Option OHLC sanity** | 0 inconsistent rows; every close on the ₹0.05 tick. |
| **Option volume** | Valid: non-negative integers, **100 % multiples of the lot size** (NIFTY 65, SENSEX 20). In 24,898 contract-minutes where Algo 8 filled, bar volume ≥ Algo 8's own quantity in 99.99 %. |
| **Stale prices** | 2.3 % of in-session bars have zero volume and 99 % of those are flat (a carried last price, not a trade). 5.5 % of bars are flat; 21 % repeat the previous close. Features carry a close at most 5 minutes and report `bar_age_min`. |
| **Instrument mapping** | NIFTY ↔ NSE (`NFO`), strike step 50, lot 65; SENSEX ↔ BSE (`BFO`, Breeze code `BSESEN`), step 100, lot 20. 100 % of strikes on the step grid. |
| **Expiry mapping** | NIFTY: 18 weekly expiries (17 Tuesdays, one Monday: 19 Oct, because 20 Oct was a holiday). SENSEX: 17 Thursdays. One expiry per underlying per session. Days to expiry: 0 or 1 (and 3 for the Friday before the Monday expiry). |
| **Ledger ↔ market mapping** | **100 % of orders (and lots) have candles for their contract-day; all 65 ledger sessions have index bars.** |
| **Fresh bar at the decision minute** | For 96.6 % of orders the traded contract has a bar that completed exactly at the decision minute; for 3.4 % there is no completed bar that day yet (mostly decisions in the 09:15 minute). No order relies on a bar older than 15 minutes. |

## 4. Coverage limits that shape the research sample

| Limit | Numbers | Consequence |
|---|---|---|
| **Option universe = contracts Algo 8 traded** (plus 752 contract-days it held or traded on the neighbouring day) | 3,243 contract-days; 36–44 strikes per session-expiry | Not the full chain. Strike selection and "what else was available" cannot be studied without bias. |
| **Option data only on D-1 and D0 of each weekly expiry** | NIFTY 33 sessions, SENSEX 34; no option data on 52 / 51 of the 85 index sessions | Option features, option-based alpha tests and option execution exist for 67 underlying-sessions (35 cycles) only. |
| **ATM straddle pair** (CE and PE of the strike nearest the last completed index close) | D-1: both legs in 99.8–99.9 % of minutes. **D0: 91 % (NIFTY) and 84 % (SENSEX); the worst D0 sessions have 0–6 %**, when spot left the strikes Algo 8 traded | The premium-versus-realised-move hypothesis is conditioned on Algo 8's strike set. D0 coverage is incomplete and non-random. |
| **Two indices move together** | Open-to-close return correlation 0.95 | NIFTY and SENSEX are not independent samples: about 85 independent sessions, not 170. |
| **No untouched data** | Every session in 22 Jun – 22 Oct 2026 has been inspected by PRs #1–#5 | All results on this sample are exploratory. No hypothesis can be confirmed here (see §7). |

## 5. Usable research sample

| Use | Sample |
|---|---|
| **Track A (Algo 8 triggers)** | 35 cycles, 65 underlying-sessions (NIFTY 31, SENSEX 34), 39,874 orders. Whole-cycle chronological splits reused from PR #3: **DEV 18 cycles / 34 sessions, VAL 8 / 14, TEST 9 / 17**. TEST is not unseen. |
| **Track B, index-only signals** | 85 sessions per index (≈ 85 independent days), 09:15–15:29, 63,678 bars. |
| **Track B, option premium and option execution** | 67 underlying-sessions with option bars (35 cycles), Algo 8's strike set only. |

## 6. Existing work reused (not repeated)

| Earlier work | What it already established | What this phase adds |
|---|---|---|
| PR #2 `analysis/indicators*.py`, `b2_*.py` (FINDINGS §0c) | 89 causal indicators (75 index, 14 option incl. IV and OI) across 8 decisions, with date-derangement nulls and FDR: **no classical indicator identifiably used**; price location matters for strike-offset direction. Built on the pre-fix order key. | OHLCV-only features (no IV, Greeks, OI); **option volume features, never tested before**; clean order key and corrected action classes. |
| PR #1 artifact (`incremental_market_feature_value.csv`) | Market feature sets add little or nothing over clock + inventory for next-minute actions. | Separate action classes with matched no-action controls. |
| PR #3 exit engine (T4 family ablation, robustness) | Side-level reductions respond to adverse spot moves; clock rebalances and salvage are timing-driven; lot-stop model depends on premium ratio and spot move. | A common, tested feature library and a position-state control (see the panel design). |
| PR #5 phases 2–3 | ≈ 95 % of stop buy-backs occur at ≥ 1.5× the lowest entry, but most crossings are not stopped; re-sale association only within 60 s. | The "crossed but not stopped" state becomes a dedicated panel. |
| PR #2 alpha search and `alpha_freeze/` | 4,512 configurations on the same period; best region not proven (reality-check p = 0.104); H1 frozen for a locked out-of-sample test. | Track B uses five new, individually pre-registered hypotheses. `alpha_freeze/` is untouched and its locked test is separate. |

Given the earlier negative results, the prior that a classical indicator drives Algo 8 is **low**. Track A is designed to detect it if
present and to say so plainly if not.

## 7. What cannot be established with OHLCV and the ledger alone

* **Exact trigger prices and sub-minute ordering.** Bars are 1-minute; body orders are stamped to the minute.
* **Index volume, index VWAP, and any order-flow or liquidity measure.** Index volume is absent; there is no bid / ask.
* **True implied volatility or a volatility risk premium.** Only a premium-to-realised-move proxy from CE + PE closes is possible. It is not IV − RV.
* **Strike selection against the full chain, and anything about untraded strikes.**
* **Realistic fill prices.** Without bid / ask, fills must be assumed (next-bar open with slippage scenarios; high / low as an adverse stress).
* **Whether Algo 8 computes a named indicator.** Several indicators are near-copies of each other (see the catalog's redundancy table). At best a *family* signature can be detected, never the source formula.
* **Out-of-sample confirmation of any alpha.** It needs sessions outside 22 Jun – 22 Oct 2026. The fetch script `analysis/history_fetch.py` exists but has not been run (it needs Breeze credentials).
