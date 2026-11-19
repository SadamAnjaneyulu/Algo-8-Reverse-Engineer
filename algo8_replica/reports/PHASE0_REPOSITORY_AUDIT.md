# Phase 0 — Repository audit before building the mechanical replica

**Status:** read-only audit. No replica code exists yet. Nothing in PR #13 or in any earlier branch was modified.
**Evidence labels used:** VERIFIED (I read or executed it in this session) · REPORTED (stated in a repository report, not re-derived here) · UNKNOWN.

## 0. Result first

1. **There is no entry-capable, event-driven Algo 8 engine in the repository.** Four partial pieces exist (§3) but none does what Part B asks: market state → entry modules → order intents → execution model → lot inventory → management/risk → settlement.
2. **The historical periods the brief proposes as validation/OOS are not untouched.** Two earlier programmes already ran frozen, published IS/OOS evaluations on the same 2023–2026 data (§5): the 4-leg basket backtest (OOS = 18 Nov 2025 → 2026) and the R1/R2 ladder replication (same split). R1 is architecturally close to what the replica will be. **No clean "primary OOS" exists for a replica built from the same rules; the unseen 2025-11-18 → 2026-06-21 block was seen for R1, and only 6 expiries after 2026-10-22 were never evaluated.** The brief's own constraint ("do not call contaminated data OOS") therefore forces a tiered evidence design (§8), decided before any replica result exists.
3. **SENSEX cannot satisfy the proposed split.** It has no data before 2024-05-30 (30 expiries absent), so "Nov 2023 – May 2024 development" is NIFTY-only.
4. **Several engine facts are unchanged by this brief and must be carried forward:** ownership is not identifiable (89 % ambiguous), settlement is a proxy, there is no bid/ask, and option universe = ATM ± 45 strikes around the D-2 close.
5. **Every existing test suite that completed passes** (§6); one (`portfolio_engine/tests`) did not finish in this session. The frozen alpha artefacts are unmodified (git history).

## 1. State verification (VERIFIED)

| Item | Value |
|---|---|
| Repository | `SadamAnjaneyulu/Algo-8-Reverse-Engineer` |
| Base branch / commit | `engineering/position-lifecycle-basket-reconstruction` @ `9e64fbadccce8a09e102e539572b74ae71935380` |
| Remote head of that branch | identical (`git ls-remote`) |
| PR #13 | draft, head `9e64fbad…`, no CI checks configured, no review comments. **Not touched.** |
| Working tree at start | clean |
| Ancestry | HEAD contains the tips of the PR #8–#12 branches (skeleton, Stage 2, TP-01/02/03) and the BT, diagnostics, replication, D0 and lot-lifecycle commits |
| New branch (created after this audit was recorded) | `research/algo8-mechanical-replica`, cut from the base commit above; no force-push, no deletion |
| Large untracked data | `analysis/_cache/*.pkl` (66 files), `backtest/cache/*.pkl` (275 per-cycle caches) are **not in git**; `backtest/results/engine/` is regenerable |

## 2. What the repository contains (VERIFIED by directory inspection unless marked)

| Area | Path | Code files | What it is |
|---|---|---:|---|
| Raw ledger | `Trades_GKOHNP140.csv`, `Info.txt` | — | 41,421 fills / 39,874 orders / 35 cycles; `Info.txt`: BTST, "4 % carry SL", "1 % of capital on expiry day", ₹2 Cr (unverified) |
| Skeleton **spec** | `algo8_skeleton/` | 1 | Stage-1 specification, data map, unresolved-rules list, TP methodology. **Specification only; "there is no strategy code yet"** |
| Take-profit / exit / entry studies | `tp_reconstruction/` | 54 | TP-01/02/03: exit attribution, entry reconstruction (analysis code, not a trading engine) |
| Early analysis + clone | `analysis/` | 81 | `engine.py` minute-bar short-straddle backtester (`Config`: schedule, strike offset, wing fraction, leg stop, cycle stop, fill model); `exit_engine/`, `allocation/`, indicators, grids |
| Portfolio-construction engine | `portfolio_engine/construction/` | (part of 249) | Python reference (`pc`) + C++ (`pc_run`, built) plugin engine: `basket_cut`, `basket_reentry`, `capital_stop`, risk validator, byte-identical Python/C++ parity. **No entry logic, no settlement, no costs** (METHODOLOGY §1) |
| Historical 4-leg backtest | `backtest/bt/`, `backtest/reports/` | 12 | Data adapter from the pinned dataset commit, scenario writer, accounting layer (settlement proxy, slippage, costs, margin proxy), metrics, 26-config grid, frozen OOS run |
| Replication programme | `backtest/replication/` | 61 | R1/R2 ladder simulator (`sim.py`, `rules.py`), live-event tables, decision-agreement scoring, performance run |
| D0 reconstruction | `backtest/replication/d0_reconstruction/` | — | Event table, rule set D0-v1 (frozen, **failed**), `d0_sim.py` v1.1 |
| Lot lifecycle (PR #13) | `backtest/replication/lot_lifecycle/` | — | Fill-level ledger, unit-lot engine with 4 ownership conventions, D0 simulator v2, matching, panel, replacement analysis, 28 tests |
| Diagnostics | `backtest/diagnostics/` | 14 | Sharpe audit, regimes, leg attribution, cost sensitivity |
| Data validation | `data_validation/` | 18 | Independent expiry calendar, coverage tables, defect register (23 defects) |
| Market-data acquisition | `market_data/` | 14 | Resumable Breeze downloader, audit, 16 tests |
| Frozen alpha | `alpha_freeze/` | 0 | H1 overnight short-straddle hypothesis, frozen grid and hashes |
| Other | `ohlcv_research/`, `stage2_alpha_research/`, `dte_comparison/`, `risk_rule_validation/`, `audit/`, `report/` | — | Feature library, baselines/targets/validation harness, DTE and risk-rule studies, registers and the research report |

## 3. What works, what is only a specification, what can be reused

| Capability requested in Part E | Existing implementation | State | Reuse decision |
|---|---|---|---|
| Expiry calendar, D-1/D0 | `data_validation/validation/calendar_evidence.py`, `reports/tables/{nifty,sensex}_expiry_coverage.csv`, `bt/cycles.py::cycle_list` | **Working**; independent of the dataset's own manifest | Reuse (read-only) |
| Market data loader | `bt/gitdata.py` (pinned commit `eb409730…`), 275 per-cycle caches; live-window bars in `analysis/_cache`; `replication/data.py` cycle dict | **Working**; 09:15–15:29 filters required (D05/D06/D21) | Reuse behind a causal `MarketView` |
| Lot size per session | `bt/cycles.py` infers lot from the gcd of option volumes (NIFTY 50/25/75/65, SENSEX 10/20) | Working; **inferred, not supplied** | Reuse, label as inferred |
| Order / fill / execution model | `analysis/engine.py` (open / prev-close fills; level / high / next-open stop fills), `bt/account.py` (delay, slippage, costs) | Working but **not event-driven**; no partial fills, no marketable-limit band | Extend |
| Ledger / position accounting | `portfolio_engine` `PortfolioState.apply_fill` (Python + C++) | **Working**, parity tested | Reuse as accounting authority |
| Lot ownership | `lot_lifecycle/src/lots.py` (FIFO/LIFO/LOW/HIGH, D1 both readings) | Working, **post-hoc over a ledger**, not an online allocator | Port the allocation logic to an online allocator; use the existing engine as the oracle |
| Entry modules | `replication/sim.py` (R1: 17-slot D-1 ladder, wings, leg stop, cycle stop, 15:14 flatten; R2: D0 median ladder fitted to the live window) | Python only; **no lot allocation, no event loop** | Reuse the rule constants; reimplement as modules |
| Per-lot stop | `replication/rules.py::leg_stop_hit` (central 1.55×, exempt entry ≤ 4), `analysis/leg_stop.py` | Hypothesis; band 1.55–1.70 | Reuse as configurable band |
| Cycle stop | `bt/…capital_stop` plugin (Python + C++), `d0_sim_v2.py` | Hypothesis; passive-lot behaviour is an assumption | Reuse with two bounds |
| Teacher-forced validation | `replication/decision_agreement.py`, `live_events.py`; `lot_lifecycle/src/matching.py` (one-to-one window matching, defect C fixed) | Working for fills; legacy fixed-bin matcher **superseded** | Use `matching.py` |
| Settlement | `bt/account.py` (official 15:30 spot bar → Yahoo daily close → 15:29 bar) | **Proxy**; no exchange settlement price in the data | Reuse; report all three |
| Costs | `bt/account.py` | STT 0.0625 %→0.1 %→0.15 % confirmed for 2026 only; **other rates quoted from memory and unverified** (METHODOLOGY §5) | **Must be re-verified from authoritative sources (Part K)** |
| Python/C++ parity | portfolio_engine only (13,525 byte-identical runs) | Parity exists **only** for the cut/re-entry/stop plugin engine | New modules: Python reference first; C++ only if the brief's later parts require it |

**Incomplete or only specified:** the skeleton spec (no code); R1/R2 rules in C++ (none); D0 new-sale/replacement logic (unidentified); lump hedge sizing (unknown); margin (a worst-case-loss proxy, not SPAN); any online order lifecycle (cancel/reject/modify are unobserved).

## 4. Known defects that bind the replica

| Source | Defect | Consequence |
|---|---|---|
| `INDEPENDENT_REVIEW_D0` / lot lifecycle D1–D9 | Fixed-bin matching (C), D0 09:15 look-ahead (D), start book (E), passive lots after a stop (A, **assumption**), replacement wings (B, **unknown**), body-buy ambiguity (D1) | Regression fixtures must be carried over; A, B and D1 stay explicit scenarios |
| Legacy event table (`d0_events.csv`) | Minute-0 features use the same bar | Do not use for any decision input |
| Data D01–D03 | 5 SENSEX expiries without data; no SENSEX before 2024-05-30; open interest zero everywhere in SENSEX | SENSEX shorter; no OI features |
| Data D04 | Muhurat sessions taken as D-1 for two expiries | Exclude or repair |
| Data D05 | NIFTY spot 15:20+ invalid after 2026-08-03 | No spot feature after 15:14 on those sessions |
| Data D06 / D21 | Volume wrap-around (23 rows), four intraday outages | Filter volumes; mask outage sessions |
| Universe | Strikes are ATM ± 45 around the D-2 close; contracts outside it cannot be classed as unlisted or failed | Intents on uncovered strikes → `NO_MARKET`, never a fabricated fill |
| Existing BT | Wing substituted toward ATM in 54 % (NIFTY) / 31 % (SENSEX) of cycles because the 2,000/4,000-point wing did not trade in 09:16–09:20 | Wing liquidity is a first-order feasibility issue for any historical wing rule |
| Costs | Statutory rates unverified except STT 2026 | Re-source before any net figure is reported |
| Existing full-chain caches (`backtest/replication/cache`) | Contain **open, close, volume only — no high/low** | Stop-crossing logic needs high/low; the replica needs its own loader from the pinned dataset commit |
| `alpha_freeze/FREEZE_SHA256.txt` | The two hashes do not match any file currently in `alpha_freeze/` (what they hash is not recorded) | Cannot be re-verified here; git history shows the folder unmodified since commit `d695b777` |

## 5. Contaminated outputs and what that does to the proposed split

| Earlier programme | Period seen | What was evaluated | Consequence for the replica |
|---|---|---|---|
| BT (4-leg basket, 26 configurations) | IS ≤ 2025-11-17 (configuration selection); OOS 2025-11-18 → 2026-11 evaluated **once** | 09:16 ATM short straddle + wings, hold or flatten | The simplest observed-entry baseline of the new brief has **already been scored** on every period |
| Replication R1/R2 | Same IS/OOS split; R1 OOS 0.22 Sharpe (clean 0.20), R1 clean-before-window 0.89 | D-1 ladder + wings + leg stop + cycle stop + carry + D0 management + 15:14 flatten | The replica's full mechanical specification is a superset of R1 → **its historical results are not independent of R1** |
| Live window 2026-06-22 → 2026-10-22 | all 35 live cycles inspected repeatedly | rule discovery | Any rule read from it is contaminated there (already a brief premise) |
| Frozen alpha (H1 overnight straddle) | dev Jun–Oct 2026 | different hypothesis | Not modified; out of scope |

**Usable historical coverage (REPORTED by `data_validation`):** NIFTY 2023-11-08 → 2026-11-09, 155 complete / 3 partial / 2 missing of 160 expected; SENSEX 2024-05-30 → 2026-11-12, 121 complete / 3 partial / 35 missing of 159. Only D-1 and D0 sessions exist.

## 6. Test status (VERIFIED, executed in this session)

| Suite | Result |
|---|---|
| `backtest/tests` (BT, D0, diagnostics, replication) | 34 passed |
| `backtest/replication/lot_lifecycle/tests` | 28 passed |
| `data_validation/tests` | 27 passed |
| `market_data/tests` | 16 passed |
| `ohlcv_research/tests` | 23 passed, 2 skipped |
| `tp_reconstruction/tests` | 70 passed |
| `portfolio_engine/construction/tests` (plugin engine, Python + C++ parity) | 180 passed |
| `stage2_alpha_research/tests` | no tests collected (exit 5): the folder contains only `__pycache__` |
| `portfolio_engine/tests` (M2 accounting suite) | **not completed in this session** (the run was stopped at ~14 % after several minutes; it was not failing). Status UNKNOWN until run separately |
| `algo8_replica/tests` (new, this milestone) | see the latest commit message |

## 7. Rule status entering the replica

| Class | Rules |
|---|---|
| CONFIRMED_OBSERVATION | Cycle = D-1 + D0; order identity = column-163 tag, module from prefix; base unit 65 / 20 (2026 lots); marketable-limit pricing bands; 17 pre-expiry scheduled windows act (544/544); old exposure retained; opening ~09:16 CE+PE shorts; unit-lot book reconciles |
| STRONGLY_SUPPORTED | Opening strike = ATM of the 09:15 close (31/32 first orders); deep-OTM carried lots held to expiry; Clock-B tick times; D-1 scheduled-window additions near ATM (63 % exact, 93 % within one step) |
| HYPOTHESIS | Per-lot stop 1.55–1.70×; cycle MTM stop ≈ −₹1.3 to −1.35 L; seed/routine wing structure; 15:14 final flatten after 3 Aug; cross-right sale after a buy-back; wing coupling to replacement |
| UNKNOWN | Off-schedule entry trigger; quantity beyond the modal ladder; D0 sale trigger; lump sizing; "4 % carry SL"; "1 % on expiry day"; margin sizing; ownership |
| REJECTED | Decay take-profit; ≤ ₹1 salvage; same-contract replacement as a general rule; "60 % of D0 sales are replacements"; first-draft 4.8× / 139-pair replacement result; D0-v1 trigger rules |

## 8. Consequences I am adopting for the plan (decided before any replica result exists)

1. **Branch:** all work on `research/algo8-mechanical-replica`; PR #13 branch frozen.
2. **Evidence tiers instead of a single "OOS":** (T1) strictly never-evaluated data (after 2026-10-22; 3 NIFTY + 3 SENSEX expiries — descriptive only); (T2) 2025-11-18 → 2026-06-21, previously scored for R1/BT → reported as **"previously inspected by related strategies"**, not untouched; (T3) earlier IS/validation periods; (T4) live window, behavioural development only. No result in T2/T3 will be called an independent OOS. This will be repeated in the freeze report.
3. **Split proposal to be audited in Phase 5, not assumed:** the brief's three-period split is impossible for SENSEX before 2024-05-30; the actual split will follow chronological whole-cycle assignment with purge/embargo and will be written to `historical_splits.yaml` before any performance run.
4. **Reuse over rewrite:** the ledger authority stays `PortfolioState.apply_fill`; the online lot allocator will be validated against `lot_lifecycle/src/lots.py` on all 35 cycles.
5. **Python first.** The brief does not require C++ parity for the replica; parity exists only for the unchanged plugin engine, and I will not claim more.

## 9. Open questions that do not block Phase 1 (none needs an answer yet)

* Lot-size scaling in history: the brief says not to apply 2026 sizes to 2023. The existing BT uses **3 lots per leg** at the session's inferred lot size; I will keep "lots" (not "units") as the sizing variable and state it. If you prefer constant notional or constant quantity, say so before the freeze.
* Cost model: Q1 in the skeleton listed four registered scenarios; the brief asks for verified statutory rates. I will source them from authoritative references in Phase 8 and mark each as verified or estimated.
