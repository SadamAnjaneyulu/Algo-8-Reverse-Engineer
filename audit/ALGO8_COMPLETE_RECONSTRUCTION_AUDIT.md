# Algo 8 — Complete Repository Audit, Strategy Reconstruction & Build-Readiness Assessment

**Snapshot:** 9 November 2026 (final reconciliation) · branch `audit/algo8-reconstruction-audit` (PR #4), stacked on PR #3
head `6b4ef390` · documentation and read-only evidence scripts only; no research logic, model, threshold, `alpha_freeze/`
file, research input or raw trade file was changed.

| Ref (verified against GitHub on 9 Nov 2026) | Commit |
|---|---|
| `main` | `5d6cc5cd` |
| PR #1 `research/ml-decision-engine` (base `research/strong-findings` `dee20138`) | `c5c4f285` |
| PR #2 `claude/friendly-galileo-r3zezw` (base `main`) | `07eee688` |
| PR #3 `research/algo8-exit-engine` (base PR #2 branch) | `6b4ef390` |
| PR #4 `audit/algo8-reconstruction-audit` (base PR #3 branch) | the head of this branch (see the PR page; this table cannot contain its own commit id) |
| `data/local-breeze-fetch` / `research/strong-findings` (no PR) | `34c21f27` / `dee20138` |

All four PRs are **open drafts; none is merged.**

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
  fully autonomously (Mode B). PR #1's lineage-X ML study reaches no 75 % task and its replay abstains.
* **A data-quality defect was found and contained:** column 4 order ids are reused across days. This invalidated PR #3's
  first exit-engine results. They were **rebuilt on the corrected key (column 163) and are final**; none of PR #2's
  headline findings flip, but its per-lot stop statistics are contradicted (see §7A).
* **PR #1's ML study has now been read** (artifact `algo8-research-report`, run 41223605040): 1,280,181 dataset rows,
  six completed action/quantity/replay folds, **0 of 20 action/level tasks reach 75 % precision and recall**, and its
  autonomous replay is **abstention-limited** (288 rows, 0 predicted orders, 0 simulated fills). That is not a successful
  autonomous reconstruction. Its metrics are **not** comparable with PR #3's (§7).
* **Estimated coverage score: ≈ 34 %** (25–34 % depending on how partial components are counted). It is a
  **subjective, unweighted evidence-and-readiness index** over 19 components, not the share of code or decision logic
  recovered and not a probability of replication. **0 of 19 components are exact.**
* **Bottom line:** an approximate behavioural replica can be built now. The exact Algo 8 cannot. Getting there needs
  either privileged data (configuration, decision logs, allocation ids, order lifecycle) or new trade months for
  independent validation, plus the experiments listed in the roadmap.

---

## 2. Repository and branch inventory

### 2.1 Current state

* Seven remote branches: `main`, `data/local-breeze-fetch`, `research/strong-findings`, `research/ml-decision-engine`,
  `claude/friendly-galileo-r3zezw`, `research/algo8-exit-engine`, `audit/algo8-reconstruction-audit`. Latest refs were
  fetched on 9 Nov 2026 (table at the top).
* **No background jobs are running.** All exit-engine stages are complete on the corrected key: clean rebuild, taxonomy,
  first passage, side/basket, Clock B, carried positions, all exit models (11 jobs, TEST scored once), both replay modes
  under three fill assumptions, robustness and missing-data stress, 12 unit tests passing.
* No research branch has been merged into `main`; none was merged during this audit.

### 2.2 Branch / PR table

| Branch / PR | Purpose | Completed work | Important findings | Missing work | Status |
|---|---|---|---|---|---|
| `main` | Raw inputs | `Trades_GKOHNP140.csv`, `Info.txt` (2 commits, 24 Oct 2026) | — | No research merged | Base of everything; **no research findings are on `main`** |
| `data/local-breeze-fetch` (no PR) | Lineage X root: Breeze data fetch and the bulk of lineage X research | 36 commits (25–27 Oct): `data/breeze/` (10,239 files, 639 MB), ~90 scripts and ~45 reports under `research/`, `ALGO8_RULEBOOK.md`, `ALGO8_CURRENT_PICTURE.md`, `ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md`, Rahul report (`.docx/.pdf`, figures); final economic closure at `21ce61db` | Schedule 544/544, opening structure, hedge budget 2.5 %, extra-sale placement, entry baseline, exit-study negatives, economic verdict "no demonstrated alpha" | Exit/re-entry controller, sizing, eligibility (stated in its own docs) | Not merged anywhere; **market data used by lineage Y lives here** |
| `research/strong-findings` (no PR) | Consolidated strong-findings register | +1 file `STRONG_FINDINGS.md` v7 (F01–F34, C01/C02) + merge of the data branch (27 Oct) | As above, with denominators | — | Base of PR #1 |
| `research/ml-decision-engine` — **PR #1** (draft, base `research/strong-findings`) | Resumable chronological ML reconstruction (registered 75 % precision/recall standard) | +20 files: `research/ml_decision_engine/` (18 files), CI workflow/action | No results committed; cloud run **41223605040 succeeded on 31 Oct**; artifact `algo8-research-report` **reviewed on 9 Nov** (§7B) | 0 of 20 action/level tasks reach the registered 75 % standard; replay abstention-limited (0 predicted orders) | Open draft, unmerged; artifact expires 30 Nov 2026; description updated 9 Nov |
| `claude/friendly-galileo-r3zezw` — **PR #2** (draft, base `main`) | Lineage Y: decode, validate on market data, alpha anatomy, backtester, frozen OOS candidates | +59 files (14 commits, 6–8 Nov): `FINDINGS.md` v8, 51 files under `analysis/` (scripts + requirements), `alpha_freeze/` (7 files, SHA-256 `c0623b61…`, `21856dcb…`, commit `d695b777`) | Module tags; limit-band quote recovery; cycle stop ≈ −₹1.30–1.35 L; per-lot stop ≈ 1.55× (now contested); clocks incl. Clock B; no indicators; clone corr 0.48; no alpha; frozen H1 | Locked OOS awaits 2025–26 data and lot sizes; P4 chain unverified after the order-id issue | Open draft; depends on lineage X's `data/breeze` via `ALGO8_MARKET_DIR` (not contained in its own branch) |
| `research/algo8-exit-engine` — **PR #3** (draft, base PR #2's branch) | Lineage Y exit-engine deep reconstruction (sections 1–10) | +40 files (18 commits, 8 Nov): `analysis/exit_engine/` (ledger, taxonomy, book state, first passage, side/basket, Clock-B, carried, models, replay, robustness, audits, tests, `run_all.py`) | Order-key audit; clean first-passage (D-1 stop ≈ 1.6–1.7×; one lot at a time); Clock-B = one-lot ATM re-centring; side/basket triggers unknown; 4 % SL unresolved | Nothing material; the findings doc and PR description were rewritten on the clean build and all sections 3–9 are complete | Open draft; **stacked on PR #2**, so merging it alone into `main` would bring PR #2 with it |
| `audit/algo8-reconstruction-audit` — **PR #4** (draft, base PR #3 branch) | This audit and the final reconciliation | 6 documents in `audit/` plus read-only evidence scripts and CSVs in `audit/evidence/` | See §7A (six conflicts reconciled) | — | Open draft, stacked on PR #3; documentation only |

### 2.3 Ancestry

```text
main (5d6cc5cd)
 ├── data/local-breeze-fetch (34c21f27) ── research/strong-findings (dee20138) ── research/ml-decision-engine (c5c4f285)  [PR #1 → strong-findings]
 └── claude/friendly-galileo-r3zezw (07eee688)  [PR #2 → main]
       └── research/algo8-exit-engine (6b4ef390)  [PR #3 → PR #2 branch]
             └── audit/algo8-reconstruction-audit (PR #4, this audit)
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
| PR #1 Actions artifacts (22, incl. `algo8-research-report` = artifact 13053588580) | GitHub Actions run 41223605040 | **`algo8-research-report` downloaded and reviewed on 9 Nov** (copy in the session scratchpad, not committed); the artifacts expire 30 Nov 2026 |
| `audit/evidence/` | this branch | Two read-only reconciliation scripts and their CSV outputs (§7A); they import PR #2's functions unchanged and read the exit-engine caches |

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
* **Conflicts:** six were reconciled explicitly in [§7A](#7a-reconciliation-of-conflicting-measurements): the D-1 stop
  level (1.55× vs 1.6–1.7×), own-entry vs cheapest-entry reference, extra-sale timing across lineages, the 10:15/10:16
  ladder size, PR #1's abstention replay vs PR #3's replay, and lineage X's macro-F1 vs order-level reproduction. Two are
  definitional and resolved (ladder window; own vs cheapest reference as a *measurement* difference); the rest are
  unresolved on the available data.
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

**Unknown — not identified in the available data** (this does not mean the strategy has no such rule):
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

**What the 34 % is.** It is a **subjective, unweighted evidence-and-readiness index**: each of 19 components was placed
in one of five levels *before* scoring (Exact 1.0 / Approx-high 0.75 / Approx 0.5 / Approx-low 0.25 / Not possible 0) and
the scores were averaged (6.5 / 19). It is **not** the fraction of code, decision logic or P&L recovered, it is not a
probability of replication, and the components are not equally important (the exit components, which carry most of the
unexplained behaviour, score 0–0.25). Sensitivity: 25 % if approx-low counts 0; 74 % of components implementable at all;
**0 of 19 exact**.

**The same evidence, partitioned by what can be done with it** (no numbers beyond the readiness matrix):

| Partition | What falls in it |
|---|---|
| **Implementable with high confidence** (rule known; stated exceptions) | 17 pre-expiry window times; 09:16 opening, ATM seed strikes and wings, 3-unit opening size; one-base-unit child orders, marketable-limit band, IOC/DAY and module tags; the cycle stop at ≈ −₹1.30–1.35 L (constant approximate); 15:14 short-book flatten in the later period |
| **Only approximable** (behaviour known, level or selector approximate) | D-1 per-lot stop as a 1.6–1.7× band of the cheapest open entry (covers ≈ 45 % of stop-like exits); later strike choice (±1 strike 95–97 %); routine wings (≈ 2.5 % budget); ladder quantities as modal templates; Clock-B timing, one-lot size and ATM re-sale; carry book as surviving allocations |
| **Triggers unknown** | extra sales; side-level, basket and partial reductions; Clock-B act/no-act and contract choice; D0 per-lot stop scope; re-entry; salvage and profit-taking beyond timing; reduction contract choice |
| **Blocked by missing data** | lump size; sizing formula and exposure ceiling; denominators and scope of the 4 % carry SL and 1 % expiry stop; entry eligibility (no negatives); pending/cancelled-order handling; allocation ownership; tick-level stop timing; configuration-change causes |
| **Requires genuinely new historical observations** | any out-of-sample validation of any decision rule (every cycle has been inspected); more than 12 cycle-stop events; no-trade sessions for eligibility; whether the 1.6–1.7× band and the 17 windows persist |

**Can an approximate behavioural replica be built now?** **Yes**: calendar, clocks, ATM strikes, wings, base units,
pricing, a D-1 stop band, the cycle stop and the late flatten, with every unknown component an explicit placeholder and
per-component fidelity reported. **Can the exact strategy be reconstructed from the current data?** **No.** Zero
components are exact and no exit-side rule has been recovered to 80/80.

---

## 7. ML reconstruction audit (Phase 5)

### 7.0 Five measures that must not be mixed

The exit-engine studies and PR #1 use different quantities that are easily mistaken for each other. Every number in this
audit is one of these five:

| # | Measure | Definition | Where it appears | What it does **not** show |
|---|---|---|---|---|
| 1 | **Exit-event association** | Any buy-back of the contract within *W* minutes after the minute high crossed *k* × the reference (PR #3 `first_passage.py`, "answered"). E.g. 88 % within 1 min at 1.7× (DEV / VAL / TEST 0.88 / 0.88 / 0.76) | PR #3 §5; PR #2's 74 % is a variant (§7A) | That the buy-back was a stop |
| 2 | **Stop-consistent classification** | A non-scheduled buy-back whose own quote is still beyond the threshold, quantity ≤ lots crossed (PR #3 `first_passage.py`) | PR #3 §5; the ≈ 45 % coverage of stop-like exits | That the trigger is the rule |
| 3 | **ML event prediction** | Precision / recall / AP of a classifier on contract-minute (PR #3) or minute-opportunity (PR #1) rows, thresholds set before scoring | §7.2, §7B | Portfolio behaviour; rare-event base rates matter |
| 4 | **Autonomous portfolio replay** | A model drives its own simulated book; scored by exit match (±2 min), quantity agreement, position divergence and abstention | PR #3 §8 (Mode A / B); PR #1 (abstains) | Economic profit |
| 5 | **Replay P&L** | Cash result of the replay under a fill assumption | PR #3 §8; sensitive to fills (+₹4.6 L / −₹10.3 L, same decisions) | That decisions were reproduced; Mode A P&L is carried by the supplied entries |

These measures are **not interchangeable**. A high association rate (1) does not imply a stop rule was recovered; a good
classification (2) is not a predictive model (3); a predictive model is not an autonomous controller (4); and similar
P&L (5) does not demonstrate matching decisions.

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

"Validation" = VAL (lineage Y) or the study's chronological later check. A TEST column is filled only for lineage Y's exit
engine, which was scored once; the lineage-X PR #1 study is in [§7B](#7b-pr-1-ml-decision-engine-lineage-x-results) and
must not be merged into this table.

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
| Y exit engine §7 (LR, LightGBM, CatBoost, depth-3 trees, discrete hazard; 11 jobs: lot stop, label-free, side, basket, Clock-B, carried, salvage, profit-taking, re-entry, final liquidation, multiclass) | per model | 45 causal book/market features | DEV; thresholds on VAL | See [ML-03](ALGO8_MASTER_FINDINGS_REGISTER.md): e.g. lot stop LGBM P 0.27 / R 0.68 | **TEST (once)**: lot stop 0.27–0.37 / 0.52–0.68; side-level 0.21 / 0.40; basket 0.19 / 0.28; carried 0.32–0.38 / 0.25–0.32; re-entry 0.64–0.67 / 0.63–0.67; Clock-B top-1 0.56 vs 0.35 random; final liquidation 0.75 / 1.00 on 15 events | — | Low; none reaches 80/80; learns timing correlates, not a rule |
| Y exit engine §8 autonomous replay, Mode A (actual base entries; own exits) | Own-book exits, re-entries, wing releases, liquidation | Contract-minute exit + quantity models, re-entry model, final-flatten model (DEV fit, VAL thresholds) | DEV | VAL exit-match P 0.39 / R 0.25 | **TEST P 0.40 / R 0.24**; quantity agreement 0.51; P&L corr 0.87 (₹4.6 L vs ₹7.5 L) | Genuine autonomous (own book); abstention 1–8 % | Low; P&L similarity driven by the supplied entries |
| Y exit engine §8 autonomous replay, Mode B (decoded entries; own exits) | Full autonomous book | same + decoded clone entries | DEV | VAL P 0.45 / R 0.11 | **TEST P 0.37 / R 0.12**; P&L corr 0.59 (−₹3.5 L vs ₹7.5 L) | Fully autonomous | Low |
| Y rule clone inside the replay (1.55× lot stop, cycle stop, 15:14) | — | — | — | Mode A VAL P 0.65 / R 0.16 | Mode A TEST P 0.63 / R 0.18 | Autonomous exits | Low recall |
| X constrained autonomous controller | Contract/action events within 2 min | Clock, budget, premium, book (own simulated inventory) | August-selected | Later macro F1 23.3 % vs 18.2 % baseline; quantity 15.7 %, path 46.1 % | — | Opening contradiction 0/32 | Genuinely autonomous; far below target |
| X policy/execution separation | same | 12 policies × 7 execution mechanisms | 11 fit + 7 Aug | Later macro F1 24.3 %; opening 28/32 shorts, 17/32 wings, 19/32 net roles | — | 0/59 reversal motifs reproduced | Autonomous; below target |
| X intermediate-exit study | Grouped reduction episodes | 12 registered hypotheses | Expanding folds, 24 test cycles | Best 18.0 % P / 16.6 % R; 50 % premium loss 36.4 % / 9.8 % | — | — | Strong negative |
| X entry baseline (timer + actual active book) | Any new short in later expiry windows | Clock + actual book state | — | 95.1 % P / 100 % R | — | **Not autonomous** (uses actual book) | High conditional |
| X combined-rule search trees | Historical minute actions / quantities | 15.9 M rule/parameter contexts | Full sample | Fit all modeled labels in-sample with hundreds of branches | — | Do not reproduce orders or hedge strikes | Overfit by construction |
| X PR #1 ML decision engine | Next-minute received execution actions at three levels (§7B) | Six registered feature sets | Six expanding chronological folds | See §7B (separate table; different target, dataset and evaluation) | — | Abstains: 0 predicted orders, 0 fills | 0 / 20 tasks reach the registered 75 % standard |

### 7.3 Does any model meet 80 % precision and 80 % recall on genuine out-of-sample data?

**No.**
- The only ≥ 80 % figures are either conditional on the actual book (X entry baseline), or structural and in-sample
  (schedule 544/544, C02 529/544).
- No exit, reduction, Clock-B or quantity model reaches 80/80 on validation.
- Lineage Y: the §7 models were scored on TEST once (best exit-class precision / recall 0.37 / 0.52 for the lot stop; side-level 0.21 / 0.40), and its autonomous replay on TEST has exit-match recall 0.12–0.24. None reaches 80 / 80.
- Lineage X (PR #1): 0 of 20 action/level tasks reach the registered 75 % standard; its autonomous replay produced no orders (§7B).

There is also no genuine out-of-sample data. **Previously inspected historical dates are not a genuinely unseen external
test period:** PR #3's TEST (9 cycles) and PR #1's later folds are chronological hold-outs *within* data that both
lineages had already examined, and TEST is contaminated for hand-derived constants. Every cycle has been inspected; the 2025–26 history planned for the alpha
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
| **Teacher-forced replay** (actual orders fed in) | The engine's accounting and causal features match the panel and the cash P&L exactly | Passed on the clean build (12 tests, 9 Nov) — validates software only |
| **Smoke test** (2 DEV cycles, own decisions) | The pipeline runs end to end | Passed; in-sample; not an assessment |
| **Autonomous replay** (own book; no actual exits or future inventory) | Fidelity of a reconstructed controller | Lineage X: macro-F1 23–24 %. Lineage Y (minute-open fills, TEST): Mode A exit-match P 0.40 / R 0.24; Mode B P 0.37 / R 0.12. TEST P&L is very sensitive to fills in Mode A (+₹4.6 L minute-open, +₹5.7 L one-minute delay, −₹10.3 L adverse; actual +₹7.5 L), while exit matching is not (precision 0.36–0.47, recall 0.12–0.24) |

### 7A. Reconciliation of conflicting measurements

Evidence scripts (read-only; no model fitting; PR #2's own functions reused unchanged):
[`stop_definition_reconciliation.py`](evidence/stop_definition_reconciliation.py) →
[`.csv`](evidence/stop_definition_reconciliation.csv) and
[`ladder_window_reconciliation.py`](evidence/ladder_window_reconciliation.py) →
[`.csv`](evidence/ladder_window_reconciliation.csv). The other four items are reconciled from the documents.

| # | Conflict | What each side measured | Reconciliation | Status |
|---|---|---|---|---|
| 1 | **Stop level:** PR #2 ≈ 1.55× vs PR #3 ≈ 1.6–1.7× | **PR #2** (`FINDINGS.md`): per **lot**, trigger = first minute high ≥ 1.55× that lot's **own entry**; "stopped" = next body buy-back of the contract at or after (trigger − 2 min) within 2 / 15 min; no one-to-one matching; 74 % / 82 %. **PR #3**: per contract **exposure**, first minute high ≥ *k* × **cheapest open entry**; D-1 fresh, all 35 cycles; "answered" = any buy-back of the contract in [m, m + *W*] (measure 1) | PR #2's number **reproduces on the clean order data with PR #2's own functions: 74.1 % / 82.0 % (1,045 lot events)**, so it is not a data error. But 22 % of those events already had a buy-back *before* the trigger minute (the window opens 2 min early); 851 of the 1,045 are follow-on lots of a contract already crossed (78 % hit, versus 55.7 % for the 194 first crossings); counting only exits at or after the trigger, first crossings give **46.9 % / 59.8 %**, against PR #3's **41.8 % / 62.1 %** (438 events) | PR #2's 74 % is **supported as a number under its definition but contradicted as evidence for a 1.55× per-lot stop**. The 1.6–1.7× cheapest-entry band is **supported as a descriptive D-1 response**; the exact constant and reference are **UNRESOLVED** |
| 2 | **Own entry vs cheapest entry** as the reference | Lot-level own-entry crossing (PR #2) vs exposure-level cheapest-entry crossing (PR #3) | The first crossing of a contract *is* its cheapest-entry crossing; higher-priced lots cross later, when closing is already under way. That produces the high follow-on rate above without implying a different stop level | **Explained as a measurement difference**; which reference the algo uses is **UNRESOLVED** (needs allocation ownership and the recovered per-order quotes) |
| 3 | **Extra-sale timing:** lineage Y "largely cracked" vs lineage X 13 / 93 caught | **Y**: ranking of off-grid sale *minutes* from timer features (grouped CV AUC 0.887, AP 0.45 vs base 0.105). **X**: an executable trigger reproducing specific extra-sale events (13 of 93) | Different targets: Y's is a probabilistic minute-level ranking (measure 3), X's an event-level rule. Neither is an identified trigger | **Not contradictory, unresolved:** an executable extra-sale trigger is **not identified in the available data** |
| 4 | **Ladder size at 10:15 / 10:16:** X 4, Y 2–3 | **Y** window [10:16:00, 10:19:00); **X** window [10:15:58, 10:19:00) (32 sessions) | Y: CE mean 3.16 (mode 3), PE 2.78. X: CE 4.50 (mode 4), PE 3.94. Lots sold in the final seconds before 10:16:00 add CE 1.34 and PE 1.16, and **3.16 + 1.34 = 4.50, 2.78 + 1.16 = 3.94**: the gap is exactly those early sales | **Resolved as a window-definition difference.** The true slot boundary (poll cadence) is UNKNOWN |
| 5 | **PR #1 abstention replay vs PR #3 replay** | **PR #1**: strict replay, no inventory feedback; unsupported modules abstain; 288 rows (24 cycles × 4 roles × 3 tolerances) | PR #1 emitted **0 predicted orders and 0 simulated fills**, so it has no precision / recall for the replay. PR #3's replay does make exit decisions (TEST 0.40 / 0.24 Mode A, 0.37 / 0.12 Mode B) | **Not a contradiction of results**: PR #1 provides **no** replay evidence; PR #3 provides low-fidelity evidence |
| 6 | **Lineage X macro-F1 vs actual order generation / inventory** | X's later-fold event macro-F1 23–24 % (contract / action events within 2 min; quantity 15.7 %, path 46.1 %); the 95.1 % / 100 % entry baseline | The baseline uses the **actual book** (not autonomous); macro-F1 averages event matches over classes. Neither reproduces orders, quantities and inventory together | **Not contradictory:** different measures (1 / 4); order-level reproduction is **not achieved** |

### 7B. PR #1 ML decision engine (lineage X) results

Source: GitHub Actions run 41223605040, artifact `algo8-research-report` (13053588580; expires 30 Nov 2026). The report's
own header: run complete, input revision `dee20138`, 1,280,181 dataset rows. Six expanding chronological folds, all
quantity and replay folds complete; every date previously inspected. Registered criteria: precision ≥ 0.75, recall ≥ 0.75,
≥ 30 target events, ≥ 5 independent cycles, coverage ≥ 0.8. **Target: the next-minute execution action actually received
(not decision intent).** Full feature set, selected chronological scores:

| Level / action | Cycles | Actual events | Precision | Recall | Meets registered 75 %? |
|---|---:|---:|---:|---:|---|
| basket / initial_entry | 20 | 19 | 0.83 | 1.00 | No: < 30 events (clock + inventory alone: 0.95 / 1.00) |
| basket / add_both | 24 | 1,673 | 0.70 | 0.62 | No |
| side / buy_protection | 24 | 4,280 | 0.73 | 0.59 | No |
| side / add_ce · add_pe | 24 | 2,308 · 2,050 | 0.62 · 0.54 | 0.58 · 0.64 | No |
| side / reduce_ce · reduce_pe | 24 | 874 · 873 | 0.35 · 0.39 | 0.53 · 0.46 | No |
| contract / new_short | 24 | 5,116 | 0.38 | 0.46 | No |
| contract / reduce_contract · close_contract | 24 | 3,168 · 514 | 0.37 · 0.21 | 0.43 · 0.22 | No |
| contract / reenter | 24 | 128 | 0.08 | 0.22 | No |
| basket / one_sided | 24 | 1,012 | 0.27 | 0.32 | No |
| basket / flatten_short · final_liquidation | 16 · 4 | 15 · 1 | 0.00 · 0.00 | 0.00 · 0.00 | No (1.0 / 1.0 for three other feature sets on a **single** event) |

* **0 of 20 action/level tasks** (100 task × feature-set rows) have `target_75_achieved = True`. The only rows with
  precision and recall both ≥ 0.75 are the `initial_entry` (19 events) and `final_liquidation` (1 event) variants, which
  fail the minimum-event rule.
* **Autonomous replay:** 288 rows; status `supported_modules_only; unapproved modules abstain`; **0 predicted orders and
  0 simulated fills in every row**. 216 / 288 rows flag `final_inventory_reproduced = True` and `exact_inventory_fraction`
  is small and non-zero in places, but with no predicted order these describe an empty replayed book and are
  **not evidence of reproduction**. This is an **abstention-limited replay, not a successful autonomous reconstruction.**
* The `incremental_market_feature_value` and stratum files show whether market features add to clock + inventory; they were
  not re-analysed here.

### 7C. Why PR #1 and PR #3 are not combined

| | PR #1 (lineage X) | PR #3 (lineage Y) |
|---|---|---|
| Dataset | 1,280,181 minute-opportunity rows | 205,752 contract-minute rows (DEV 106,389 / VAL 43,679 / TEST 55,684) |
| Target | Next-minute received execution action at basket / side / contract level (≈ 20 classes) | Taxonomy-labelled exit classes (lot stop, side-level, basket, Clock B, carried, …) plus a label-free "any unscheduled buy-back" |
| Evaluation | Six expanding folds, 12–24 cycles, protocol registered before running | DEV 18 / VAL 8 / TEST 9 cycles; thresholds on VAL; TEST scored once |
| Replay | Strict, abstains; 0 orders | Own book, Mode A / B, three fill assumptions |
| Headline | 0 of 20 tasks at 75 % | No class at 80 / 80; lot stop 0.27–0.37 / 0.52–0.68 |

Neither has a genuinely unseen external test period. **Their metrics must not be averaged, ranked against each other or
placed in one performance table.** Both agree qualitatively that exit and reduction decisions are not predictable at 75–80 %.

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
* **Done in this phase (no new data needed):** PR #1's artifact reviewed (§7B); stop-definition and ladder-window
  conflicts reconciled (§7A); lineage Y's robustness suite and adverse / delay-1 replays (90 % bootstrap intervals for
  lot-stop precision 0.25–0.30 and recall 0.63–0.74 on TEST).
* **Possible now:** see §9 (reference per-lot stop with recovered quotes; allocation ownership; Clock-B selection; extra-sale
  triggers across lineages).

## 9. Roadmap (summary)

Full roadmap: [roadmap](ALGO8_RECONSTRUCTION_ROADMAP.md).

**Completed:** clean order-key rebuild; exit models and chronological evaluation; three-fill replay comparison;
robustness and missing-data stress; final PR #3 results and documents; PR #1 artifact review; conflict reconciliation.

**Next, by information value** (no general-purpose ML tuning is recommended):
1. Reconcile the exact per-lot stop reference using the recovered per-order quotes (limit ÷ 1.15 / ÷ 0.85).
2. Reconstruct allocation ownership and per-allocation state.
3. Investigate Clock-B selection and act / no-act.
4. Reconcile extra-sale triggers across both lineages.
5. Obtain the original configuration, risk settings and decision logs, if obtainable.
6. Obtain additional historical Algo 8 trade data for genuinely unseen validation.

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
   - (done) PR #1's ML report reviewed; the clean lineage-Y exit engine finished; stop-level and ladder conflicts reconciled
   - settle the per-lot stop reference with the algo's own recovered quotes
   - reconstruct allocation ownership; investigate Clock-B selection; reconcile extra-sale triggers
2. **Obtain at least one privileged source:**
   - the configuration/source
   - decision logs with allocation ids
   - order-lifecycle logs
   - NAV/margin and risk settings
   - tick quotes

   Without one of these, the side-level, basket, re-entry, sizing and 4 %/1 % rules are likely to stay unknown.
3. **Obtain new Algo 8 trade months** that no study has inspected. Validate every rule there before claiming
   reconstruction.

### DIRECT CONCLUSION

* **Can implement now:** the calendar and clocks, 09:16 opening with ATM seed strikes, wings and 3-unit size, base-unit
  orders with the marketable-limit band, the 17 pre-expiry windows, the cycle stop (approximate constant) and the later-
  period 15:14 flatten.
* **Can only approximate:** the D-1 per-lot stop band (1.6–1.7× of the cheapest open entry), Clock-B timing and one-lot
  ATM re-sale, ladder quantities as modal templates, later strike choice, routine wings, the carry book.
* **Cannot be reconstructed from the current data:** extra-sale, side-level, basket and partial-reduction triggers; Clock-B
  act / no-act and contract choice; D0 per-lot stop scope; re-entry; lump size; the 4 % carry and 1 % expiry stops;
  sizing and exposure ceiling; eligibility.
* **What would materially change this conclusion:** the original configuration or decision logs with allocation ids (turns
  unknowns into reads); order-lifecycle records and tick quotes (resolve stop timing and pending orders); NAV / margin and
  risk settings (the 4 % / 1 % rules and sizing); or additional, unseen months of Algo 8 trades (the only genuine
  out-of-sample test). More modelling on the current sample would not.
