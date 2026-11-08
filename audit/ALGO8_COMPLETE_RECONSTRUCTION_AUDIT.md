# Algo 8 — Complete Repository Audit, Strategy Reconstruction & Build-Readiness Assessment

**Snapshot:** 8 November 2026 · branch `audit/algo8-reconstruction-audit` (stacked on PR #3 head `c43e0d84`) ·
documentation only; no research logic, model, threshold or finding was changed for this audit.

| Document | Contents |
|---|---|
| **This report** | Executive summary, repository inventory, architecture, end-to-end strategy, rule status, readiness, ML audit, data, roadmap, conclusion |
| [Master findings register](ALGO8_MASTER_FINDINGS_REGISTER.md) | Every significant finding with evidence, source line, sample type, class and conflicts |
| [Strategy specification](ALGO8_STRATEGY_SPECIFICATION.md) | Components A–G, rule by rule, with status tags; the executable approximation |
| [Reconstruction readiness](ALGO8_RECONSTRUCTION_READINESS.md) | Readiness matrix, coverage score and the eight direct answers |
| [Data gaps and requirements](ALGO8_DATA_GAPS_AND_REQUIREMENTS.md) | Data we have, data we lack (tied to each unknown), experiments possible now |
| [Roadmap](ALGO8_RECONSTRUCTION_ROADMAP.md) | Dependency-ordered tasks with acceptance criteria |

---

## 1. Executive summary

* **The structure of Algo 8 is well established; its decision logic largely is not.** It is a weekly BTST short-option
  carry engine on NIFTY and SENSEX. It sells ATM CE/PE allocations at fixed clock windows on the pre-expiry session, each
  with outward wings, in one-base-unit child orders (65 NIFTY / 20 SENSEX). It carries the protected book into expiry,
  manages it with per-allocation stops, Clock-B rebalances and assorted reductions, and liquidates on a cycle-level loss
  limit or late in the expiry session.
* **What is reproducible today:**
  - opening book (≈ 28/32 sessions jointly)
  - the scheduled pre-expiry ladder times (544/544 windows)
  - ATM strike choice (opening 31/31; later within one strike 95–97 %)
  - routine wing budget (± 1 strike 92–95 %)
  - base units and pricing
  - the cycle stop (≈ −₹1.30–1.35 L cumulative LTP MTM)
  - the late flatten (15:14 in the later period)
* **What is not:**
  - exact rules for later quantities
  - extra sales
  - side-level, basket and partial reductions
  - Clock-B act/no-act and contract choice
  - re-entry
  - lump-hedge size
  - D0 stop scope
  - the 4 % carry and 1 % expiry stops
  - capital/margin sizing
* **The per-lot stop exists but is not exactly recovered.** On clean data, a D-1 contract whose minute high crosses
  **1.7×** its cheapest open entry is bought back within one minute 88 % of the time, against 38 % at 1.55×. The stop
  closes one lot at a time and explains only ≈ 45 % of stop-like exits. On D0 it is weak, especially for carried lots.
* **No model in either lineage meets 80 % precision and 80 % recall on any important action class out of sample.** The
  best autonomous controller (lineage X) reaches a later event macro-F1 of 23–24 %. Lineage Y's autonomous replay
  matches actual exits with precision 0.40 / recall 0.24 on TEST when fed the actual entries (Mode A), and 0.37 / 0.12
  fully autonomously (Mode B).
* **A data-quality defect was found and contained:** column 4 order ids are reused across days. This invalidated PR #3's
  first exit-engine results. They are being rebuilt, and none of PR #2's headline findings flip.
* **Estimated coverage score: ≈ 34 %** (25–34 % depending on how partial components are counted). This is computed in the
  readiness matrix. **0 of 19 components are exact.** The coverage score is not a probability of exact replication.
* **Bottom line:** an approximate behavioural replica can be built now. The exact Algo 8 cannot. Getting there needs
  either privileged data (configuration, decision logs, allocation ids, order lifecycle) or new trade months for
  independent validation, plus the experiments listed in the roadmap.

---

## 2. Repository and branch inventory

### 2.1 Current state

* Checked-out branch in the main working copy: `research/algo8-exit-engine` (PR #3), clean relative to origin except for
  in-progress run outputs.
* Three research jobs from the previous task ran in that working copy while this audit was written (in a separate
  worktree, so they were not disturbed). The section 8 open-fill replay **completed** and is reported in §7. The
  section 7 models and the section 3 trigger re-run were **stopped at the 2-hour background limit**, so they have no
  results; section 9 robustness and the adverse/delay-1 replays never ran.
* Remote default branch: `main`.

### 2.2 Branch / PR table

| Branch / PR | Purpose | Completed work | Important findings | Missing work | Status |
|---|---|---|---|---|---|
| `main` | Raw inputs | `Trades_GKOHNP140.csv`, `Info.txt` (2 commits, 24 Oct 2026) | — | No research merged | Base of everything; **no research findings are on `main`** |
| `data/local-breeze-fetch` (no PR) | Lineage X root: Breeze data fetch and the bulk of lineage X research | 36 commits (25–27 Oct): `data/breeze/` (10,239 files, 639 MB), ~90 scripts and ~45 reports under `research/`, `ALGO8_RULEBOOK.md`, `ALGO8_CURRENT_PICTURE.md`, `ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md`, Rahul report (`.docx/.pdf`, figures); final economic closure at `21ce61db` | Schedule 544/544, opening structure, hedge budget 2.5 %, extra-sale placement, entry baseline, exit-study negatives, economic verdict "no demonstrated alpha" | Exit/re-entry controller, sizing, eligibility (stated in its own docs) | Not merged anywhere; **market data used by lineage Y lives here** |
| `research/strong-findings` (no PR) | Consolidated strong-findings register | +1 file `STRONG_FINDINGS.md` v7 (F01–F34, C01/C02) + merge of the data branch (27 Oct) | As above, with denominators | — | Base of PR #1 |
| `research/ml-decision-engine` — **PR #1** (draft, base `research/strong-findings`) | Resumable chronological ML reconstruction (registered 75 % precision/recall standard) | +20 files: `research/ml_decision_engine/` (18 files), CI workflow/action | No results committed; cloud run **41223605040 succeeded on 31 Oct** and uploaded a research report and fold artifacts | **Results never reviewed**; PR text still says no final assessment exists; artifacts expire 30 Nov 2026 | Open draft, unmerged |
| `claude/friendly-galileo-r3zezw` — **PR #2** (draft, base `main`) | Lineage Y: decode, validate on market data, alpha anatomy, backtester, frozen OOS candidates | +59 files (14 commits, 6–8 Nov): `FINDINGS.md` v8, 51 files under `analysis/` (scripts + requirements), `alpha_freeze/` (7 files, SHA-256 `c0623b61…`, `21856dcb…`, commit `d695b777`) | Module tags; limit-band quote recovery; cycle stop ≈ −₹1.30–1.35 L; per-lot stop ≈ 1.55× (now contested); clocks incl. Clock B; no indicators; clone corr 0.48; no alpha; frozen H1 | Locked OOS awaits 2025–26 data and lot sizes; P4 chain unverified after the order-id issue | Open draft; depends on lineage X's `data/breeze` via `ALGO8_MARKET_DIR` (not contained in its own branch) |
| `research/algo8-exit-engine` — **PR #3** (draft, base PR #2's branch) | Lineage Y exit-engine deep reconstruction (sections 1–10) | +40 files (18 commits, 8 Nov): `analysis/exit_engine/` (ledger, taxonomy, book state, first passage, side/basket, Clock-B, carried, models, replay, robustness, audits, tests, `run_all.py`) | Order-key audit; clean first-passage (D-1 stop ≈ 1.6–1.7×; one lot at a time); Clock-B = one-lot ATM re-centring; side/basket triggers unknown; 4 % SL unresolved | Sections 3, 7, 8, 9 re-runs; findings doc rewrite; PR description is **stale** (pre-fix numbers) | Open draft; **stacked on PR #2**, so merging it alone into `main` would bring PR #2 with it |
| `audit/algo8-reconstruction-audit` (this branch) | This audit | 6 documents in `audit/` | — | — | New; stacked on PR #3 |

### 2.3 Ancestry

```text
main (5d6cc5cd)
 ├── data/local-breeze-fetch (34c21f27) ── research/strong-findings (dee20138) ── research/ml-decision-engine (c5c4f285)  [PR #1 → strong-findings]
 └── claude/friendly-galileo-r3zezw (07eee688)  [PR #2 → main]
       └── research/algo8-exit-engine (c43e0d84)  [PR #3 → PR #2 branch]
             └── audit/algo8-reconstruction-audit (this audit)
```

The two lineages share only `main`'s two commits. Neither contains the other's research. Lineage Y reads lineage X's
Breeze data through an environment variable, so that is a data dependency, not a code one.

### 2.4 Local / untracked artifacts

| Artifact | Location | Status |
|---|---|---|
| `analysis/_cache/` (699 MB, git-ignored) | main working copy | Regenerable; exit-engine caches rebuilt clean on 8 Nov |
| Exit-engine run logs (`analysis/exit_engine/results/logs/`) | git-ignored except `build_stamp.json` | Transient |
| Worktree of PR #1's branch (`scratchpad/ws_ml`) | session scratchpad | Read-only source of lineage X data and docs |
| Algo 7 report and dump | session uploads | Not in the repository |
| PR #1 Actions artifacts (22, incl. `algo8-research-report`) | GitHub Actions run 41223605040 | Unreviewed; expire 30 Nov 2026 |

### 2.5 Duplicated, superseded and conflicting work

* **Duplicated across lineages:**
  - order/parent reconstruction (both correct; same 39,874 orders)
  - the schedule (X: 17 windows; Y: grid A + :00 clocks; consistent)
  - hedge budget (X: 2.5 % of each ATM leg; Y: 1.0–1.4 % of the straddle; consistent)
  - exit studies (X: registered intermediate-exit study; Y: exit engine; consistent negatives)
  - autonomous replays (X: policy/execution replay; Y: `engine.py` clone and `replay.py`)
  - economic attribution (both: no demonstrated alpha)
* **Superseded / invalidated:** listed in [register §12](ALGO8_MASTER_FINDINGS_REGISTER.md#12-superseded-or-invalidated-statements-do-not-use-without-the-correction).
  The main items:
  - PR #3 sections 1–3 numbers (reused key plus swapped side/basket labels)
  - lineage Y's "74 % of D-1 lots stopped within 2 min at 1.55×"
  - the unverified P4 68.5 %
* **Conflicts that remain open:**
  - D-1 stop level and reference: 1.55× own entry (Y `FINDINGS.md`) vs ≈ 1.6–1.7× cheapest entry (Y clean first-passage, consistent with X's 36 % at 1.5×)
  - extra-sale timing: Y "largely cracked", AUC 0.887; X 13/93 caught
  - ladder size at 10:15/10:16: X 4, Y 2–3
* **Findings not in `main`:** all of them. No research branch has been merged.

---

## 3. Strategy architecture (summary)

Full detail: [specification §A](ALGO8_STRATEGY_SPECIFICATION.md#a-strategy-architecture).

* One cycle per (underlying, weekly expiry): **D-1 build-up and carry, D0 management and liquidation.**
* Modules by order tag: body (numeric), wing hedge `h_`, lump hedge `v_`, stop-loss `s_`, manual `m_` (one day).
* AlgoIds identify the **underlying's book** (99999 NIFTY, 1E+16 SENSEX), a **platform risk actor** (152432) and a
  **second SENSEX hedge app** (2.18811E+15). They do not identify sub-strategies.
* The book is a superposition of many one-base-unit allocations. Original allocation ids are not in the data.
* NIFTY and SENSEX share one normalized framework (same clocks, same base-unit ladder) with index-specific settings.

## 4. Reconstructed end-to-end strategy (summary)

Full detail and status tags: [specification §C–§G](ALGO8_STRATEGY_SPECIFICATION.md#c-entry-engine).

1. **Pre-expiry 09:16** [S]: nearest-ATM K from the 09:15 close; wings first (NIFTY ± 2,000; SENSEX ± 4,000, then ± 2,000
   from 16 Sep); 3 base units per role.
2. **Pre-expiry ladder** [C] times / [S] sizes: 17 windows 09:30 … 14:30. Each sells near-ATM CE/PE allocations (modal
   base units 3, 2, 3, 1, …) with wings at ≈ 2.5 % of the ATM leg premium, and keeps older exposure.
3. **Extra sales** [P]/[U]: off-schedule sales shifted one strike toward the recent move; trigger unknown.
4. **Management** [P]/[U]: per-allocation stops (one lot at a time; D-1 ≈ 1.6–1.7×), partial, side-level and basket
   reductions (triggers unknown), wing replacements and releases, rapid reversal motifs.
5. **Carry** [S]: surviving allocations, long ≥ short on each right; overnight lump hedge on the heavier short side
   (size unknown).
6. **Expiry day:**
   - ladder sales while the book is active [S]
   - Clock B (:14/:29/:44/:59 from 09:29): ≈ 45 % of ticks buy back one lot and re-sell it at ATM [P]
   - weak D0 stops [P]
   - salvage at ≤ ≈ ₹1 [P]
   - 15:14 short-book flatten in the later period [S]
7. **Always on:** the cycle stop [S]. Cumulative LTP MTM ≈ −₹1.30–1.35 L liquidates everything; no new entries
   follow in that cycle.
8. **Execution** [C]: one base unit per child order; marketable limits at LTP × 1.15 / 0.85; body DAY, hedges/stop IOC.

## 5. Confirmed, inferred and unknown rules

**Confirmed (observed in this sample):**
- order identity and pricing band; module tags
- cycle structure
- the 17 pre-expiry windows (544/544)
- base child units
- accumulation without re-centring
- the classification of exits into categories (not their triggers)

**Strong evidence (rule known approximately):**
- 09:16 opening, ATM strike, seed wings, 3-unit opening size
- hedge budget ≈ 2.5 %
- expiry entries while active
- cycle stop ≈ −₹1.30–1.35 L
- one-lot stops with a D-1 response band ≈ 1.6–1.7×
- Clock-B one-lot ATM re-centring
- carry books long ≥ short
- 15:14 late flatten (later period)
- no classical indicators
- no demonstrated alpha

**Partially understood / hypotheses:**
- later strike exact selector
- directional placement of extra sales
- D0 stop hazards by class
- Clock-B act/no-act and contract choice
- reduction contract choice
- re-entry association
- wing release
- salvage
- rapid reversal motifs
- extra-sale timers

**Unknown:**
- extra-sale trigger
- side-level, basket and partial reduction triggers
- exact per-lot stop constant/reference and D0 scope
- 4 % carry SL; 1 % expiry stop (the ₹2 L reading is contradicted)
- lump size
- sizing formula and exposure ceiling
- eligibility filter
- configuration-change causes
- pending-order and cancellation handling
- origin of the −₹1.3 L constant

## 6. Readiness (summary)

Full matrix and calculation: [readiness](ALGO8_RECONSTRUCTION_READINESS.md).

| Level | Components |
|---|---|
| Exact | none |
| Approximate – high | entry timing; initial construction; initial quantity; cycle stop; execution/order handling |
| Approximate | strike selection; final flattening |
| Approximate – low | dynamic quantity; scheduled rebalancing; individual stops; Clock B; re-entry/replacement; hedge adjustment; carry-forward |
| Not possible yet | intermediate exits; side-level exits; basket exits; contract selection; expiry-day stops |

**Estimated coverage score 34 %** (25 % if partial components count as zero; 74 % of components implementable at all;
0 % exact).

---

## 7. ML reconstruction audit (Phase 5)

### 7.1 Protocol review

| Check | Lineage Y exit engine (`analysis/exit_engine/`) | Lineage Y v4 / indicator ML (`analysis/p*_*.py`, `b2_*.py`) | Lineage X (controller searches, exit study, PR #1) |
|---|---|---|---|
| Split | Whole-cycle chronological by expiry: DEV 18 / VAL 8 / TEST 9 cycles ([`common.py#L21-L23`](../analysis/exit_engine/common.py#L21)); no cross-cycle features | Chronological 60/40 by session; grouped CV; 3 expanding folds | Expanding chronological folds; whole-cycle exclusion; later cycles already inspected |
| TEST hygiene | TEST never used for fitting or thresholds, but **contaminated for hand constants** found on all 35 cycles | All cycles explored | All cycles explored |
| Threshold selection | On VAL by F1 ([`models.py#L76-L81`](../analysis/exit_engine/models.py#L76)); early stopping on VAL | In-fold | Inner chronological cycles |
| Leakage controls | Features computed at the start of minute m from bars completed before m; action columns excluded from features (unit test); the teacher-forced replay recomputes features sequentially before applying minute-m orders and reproduces the panel | Causal indicators ([`indicators.py`](../analysis/indicators.py)) | Strict past inventory / completed candles checked (208,885 opportunity rows) |
| Class distribution | Contract-minute panel 205,752 rows (DEV 106,389 / VAL 43,679 / TEST 55,684); any buy-back 2.6 %; lot-stop label 0.68 %; basket 0.47 %; side-level 0.19 %; unexplained 0.02 % | — | Hold is the explicit negative |
| Label circularity | Taxonomy labels defined by thresholds on features (lot stop: quote/cheapest ≥ 1.45; salvage ≤ ₹1 / 5 %). A label-free target (any unscheduled buy-back) is run alongside | — | Stop/target models are labelled "reduction-hazard surrogates" |
| Confusion matrices | Not produced (precision/recall/F1/AP/Brier/ECE are) | Not produced | Reported as false positives / missed exits |

### 7.2 Model table

"Validation" = VAL (lineage Y) or the study's chronological later check. No row reports a TEST result, because none has
been scored.

| Model / action class | Target | Features | Training data | Validation metrics | Test metrics | Autonomous replay result | Reliability |
|---|---|---|---|---|---|---|---|
| Y P1 leg-stop grouping | Other open contracts closed with a stop | Book state | Chronological 60/40 | F1 0.23 (negative) | — | — | Low; shows no grouping rule |
| Y P2 D0 exit hazard | Any D0 buy-back per minute | Clock, book, price ratios | 60/40 | AP 0.11 vs base 0.018 | — | — | Low |
| Y P3 extra-sale timers | Off-grid sale minute; due timer fires | Clock, timer age, windows | Grouped CV | AP 0.45 vs 0.105; AUC 0.887 | — | — | Medium for ranking; not an executable trigger (conflicts with X) |
| Y P4 strike choice | Chosen strike among candidates | Premium closeness, previous sale, moneyness | 60/40 | Top-1 68.5 % vs 58.4 % ATM | — | — | **Unverified** (reused-key chain) |
| Y P5 lump size | Lump lots | Book, premium, Greeks | LOO | Worse than naive median | — | — | None |
| Y B2 indicator ablation | 8 decisions | Clock+book → +price → +indicators | 3 expanding folds + 5 nulls | Indicator gain ≤ null for 6/8 | — | — | Strong negative |
| Y exit engine §5 side-level | ≥ 2 contracts of one side closed (unscheduled) | 45 causal book/market features | DEV | LightGBM VAL AUC 0.87, AP 0.25 (base 3.5 %); tree P 0.11 / R 0.66 | not scored | — | Low; learns timing correlates, not a rule |
| Y exit engine §5 basket | Both sides closed | same | DEV | AUC 0.86, AP 0.15 (base 2.2 %); tree P 0.05 / R 0.81 | not scored | — | Low |
| Y exit engine Clock-B act | Tick buys back anything | Book state one minute before the tick | DEV | LightGBM AUC 0.78; tree P 0.77 / R 0.55 | not scored | — | Medium for ranking; below target |
| Y exit engine Clock-B selection | Which contract (candidate-level) | Contract features | DEV | Best criterion hit@1 0.66 vs 0.41 random; conditional logit 0.52 | not scored | — | Low–medium |
| Y exit engine carried-stop rule | D0 stop-like exit at ≥ 1.5× | Age, premium, decay, TTE, moves, IV | DEV | Tree P 0.16 / R 0.80 | not scored | — | Rejected |
| Y exit engine §7 (LR, LightGBM, CatBoost, depth-3 trees, discrete hazard; lot stop, label-free, side, basket, Clock-B, carried, salvage, profit-taking, re-entry, final liquidation, multiclass) | per model | causal CM/BM features | DEV, VAL thresholds | **No result**: run stopped at the 2-hour background limit | — | — | Not assessed |
| Y exit engine §8 autonomous replay, Mode A (actual base entries; own exits) | Own-book exits, re-entries, wing releases, liquidation | Contract-minute exit + quantity models, re-entry model, final-flatten model (DEV fit, VAL thresholds) | DEV | VAL exit-match P 0.39 / R 0.25 | **TEST P 0.40 / R 0.24**; quantity agreement 0.51; P&L corr 0.87 (₹4.6 L vs ₹7.5 L) | Genuine autonomous (own book); abstention 1–8 % | Low; P&L similarity driven by the supplied entries |
| Y exit engine §8 autonomous replay, Mode B (decoded entries; own exits) | Full autonomous book | same + decoded clone entries | DEV | VAL P 0.45 / R 0.11 | **TEST P 0.37 / R 0.12**; P&L corr 0.59 (−₹3.5 L vs ₹7.5 L) | Fully autonomous | Low |
| Y rule clone inside the replay (1.55× lot stop, cycle stop, 15:14) | — | — | — | Mode A VAL P 0.65 / R 0.16 | Mode A TEST P 0.63 / R 0.18 | Autonomous exits | Low recall |
| X constrained autonomous controller | Contract/action events within 2 min | Clock, budget, premium, book (own simulated inventory) | August-selected | Later macro F1 23.3 % vs 18.2 % baseline; quantity 15.7 %, path 46.1 % | — | Opening contradiction 0/32 | Genuinely autonomous; far below target |
| X policy/execution separation | same | 12 policies × 7 execution mechanisms | 11 fit + 7 Aug | Later macro F1 24.3 %; opening 28/32 shorts, 17/32 wings, 19/32 net roles | — | 0/59 reversal motifs reproduced | Autonomous; below target |
| X intermediate-exit study | Grouped reduction episodes | 12 registered hypotheses | Expanding folds, 24 test cycles | Best 18.0 % P / 16.6 % R; 50 % premium loss 36.4 % / 9.8 % | — | — | Strong negative |
| X entry baseline (timer + actual active book) | Any new short in later expiry windows | Clock + actual book state | — | 95.1 % P / 100 % R | — | **Not autonomous** (uses actual book) | High conditional |
| X combined-rule search trees | Historical minute actions / quantities | 15.9 M rule/parameter contexts | Full sample | Fit all modeled labels in-sample with hundreds of branches | — | Do not reproduce orders or hedge strikes | Overfit by construction |
| X PR #1 ML decision engine | Next-minute execution actions, quantities, replay | Registered feature sets | Chronological folds | **Unread** (artifact `algo8-research-report`) | — | Replay folds uploaded, unread | Unknown |

### 7.3 Does any model meet 80 % precision and 80 % recall on genuine out-of-sample data?

**No.**
- The only ≥ 80 % figures are either conditional on the actual book (X entry baseline), or structural and in-sample
  (schedule 544/544, C02 529/544).
- No exit, reduction, Clock-B or quantity model reaches 80/80 on validation.
- Lineage Y's autonomous replay on TEST: exit-match recall 0.12–0.24.
- PR #1's results are unread.

There is also no genuine out-of-sample data. Every cycle has been inspected; the 2025–26 history planned for the alpha
test contains no Algo 8 trades, so it cannot validate decision rules.

### 7.4 Rule learning vs correlation

The models rank exits mainly by **clock / time-to-expiry, time since the last trade, price ratios and exposure size**.
These are correlates of when the algo acts, not a recovered decision rule. Three observations show this:
- side and basket trees have VAL precision 0.05–0.11 even though AUC is 0.86–0.87 (rare events);
- dropping families moves AUC by a few points;
- lineage X's unrestricted trees fit history only with hundreds of branches.

### 7.5 Teacher-forced vs smoke vs autonomous replay

| Kind | What it proves | Status |
|---|---|---|
| **Teacher-forced replay** (actual orders fed in) | The engine's accounting and causal features match the panel and the cash P&L exactly | Passed on 2 cycles (pre-clean caches; re-run pending) — validates software only |
| **Smoke test** (2 DEV cycles, own decisions) | The pipeline runs end to end | Passed; in-sample; not an assessment |
| **Autonomous replay** (own book; no actual exits or future inventory) | Fidelity of a reconstructed controller | Lineage X: macro-F1 23–24 %. Lineage Y (minute-open fills, TEST): Mode A exit-match P 0.40 / R 0.24; Mode B P 0.37 / R 0.12. Adverse-fill / delay-1 variants not run |

---

## 8. Data requirements (summary)

Full list: [data gaps](ALGO8_DATA_GAPS_AND_REQUIREMENTS.md).

* **Have:** fills-only broker export (Jun–Oct 2026), the three-sentence `Info.txt`, Breeze 1-min index and traded-option
  candles (no full chain, no bid/ask, SENSEX OI zero), Algo 7 uploads (not in repo).
* **Missing, by impact:**
  1. original source/configuration
  2. decision logs
  3. per-order allocation ids
  4. order lifecycle (submit/ack/cancel/reject)
  5. tick option quotes
  6. NAV/margin and risk settings
  7. full chain
  8. platform risk events
  9. eligible-session calendar
  10. **more months of Algo 8 trades** — the only route to genuine out-of-sample validation
* **Possible now:**
  1. read PR #1's artifact
  2. reconcile the stop-level contradiction
  3. time stops with the algo's own recovered quotes
  4. reconstruct allocation identity
  5. finish lineage Y sections 3/7/8/9

## 9. Roadmap (summary)

Full roadmap: [roadmap](ALGO8_RECONSTRUCTION_ROADMAP.md).

1. **Now (no new data):**
   - review PR #1's report
   - finish and document the clean exit engine
   - reconcile the D-1 stop level
   - test stops with recovered quotes
   - attempt allocation identity
2. **First approximate replica:**
   - freeze the executable approximation with explicit placeholders
   - score per component on DEV/VAL/TEST without tuning on TEST
3. **High fidelity:** stops, Clock B, reductions and quantities at ≥ 80 % out of sample; Mode-B replay ≥ 80 % exit matching.
4. **Successful reconstruction:** exact components validated on new Algo 8 trade data, or the original configuration
   reproduced order-by-order.

---

## 10. Final conclusion

### WHAT WE HAVE RECONSTRUCTED

**The skeleton, measured on this sample:**
- the calendar
- the module structure
- the opening book
- the fixed clock schedule of pre-expiry additions
- ATM strike placement (approximately)
- the hedge budget (approximately)
- the base order unit and pricing
- the cycle-level stop (approximately)
- the late-session flatten in the later period

On the exit side we know three things: per-allocation stops exist and close one lot at a time, Clock B on expiry day
re-centres one lot to ATM, and expiry-day salvage occurs. We can classify every exit into a category. We can also
account for every order and reproduce the P&L exactly.

### WHAT WE HAVE NOT RECONSTRUCTED

**The decision logic that does most of the managing:**
- the exact stop constant and its reference
- which lots carry a stop on expiry day
- when extra sales fire
- when and what side-level, basket and partial reductions close
- whether a Clock-B tick acts and which contract it picks
- re-entry
- per-slot quantities
- lump-hedge size
- the 4 % carry-forward and 1 % expiry-day rules
- capital/margin sizing
- eligibility

No exit-side model reaches 80/80, and the best autonomous controller matches about a quarter of events.

### CAN WE BUILD THE SAME EXACT MODEL TODAY?

**No.** Zero of nineteen components are exact, and five have no usable rule at all. We can build an **approximate
behavioural replica**: same calendar, clocks, strikes, wings, units, a stop band, the cycle stop and the late flatten.
Its fidelity must be reported per component. It must not be called Algo 8. Similar P&L or similar-looking orders would
not make it the original strategy.

### WHAT MUST HAPPEN NEXT TO GET THERE?

1. **Close the open research with existing data:**
   - review PR #1's unread ML report
   - finish the clean lineage-Y exit engine (sections 3, 7, 8, 9) and rewrite its findings
   - resolve the D-1 stop-level contradiction
   - time stops with the algo's own recovered quotes
   - try to reconstruct allocation identity
2. **Obtain at least one privileged source:**
   - the configuration/source
   - decision logs with allocation ids
   - order-lifecycle logs
   - NAV/margin and risk settings
   - tick quotes

   Without one of these, the side-level, basket, re-entry, sizing and 4 %/1 % rules are likely to stay unknown.
3. **Obtain new Algo 8 trade months** that no study has inspected. Validate every rule there before claiming
   reconstruction.
