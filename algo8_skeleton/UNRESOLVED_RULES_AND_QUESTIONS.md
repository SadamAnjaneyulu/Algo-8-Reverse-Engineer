# Unresolved rules, placeholders and decisions needed before Stage 2

## 1. Unresolved rules and how the skeleton will hold them

| Rule | Evidence | Skeleton handling |
|---|---|---|
| Extra (off-schedule) sale trigger | ENT-04 (Y AUC 0.887 model vs X 13 / 93 rule) | placeholder |
| Ladder quantity beyond the modal template | SIZ-03, REC-04 | band: lineage Y modal and lineage X modal, each run separately |
| Off-grid strike offset | STK-03, STK-04 | placeholder |
| Side-level and basket reduction triggers | MGT-05, EXT-10 | placeholder |
| Same-contract partial buy-back trigger | EXT-01 (label only) | placeholder |
| Clock-B act / no-act | MGT-03 | placeholder (times and quantity fixed) |
| Re-entry trigger, replacement strike and quantity | MGT-07, ALC-08 | placeholder |
| Allocation ownership | ALC-01, ALC-07 | cheapest / FIFO / LIFO / slot / chain, reported separately |
| Per-lot stop: exact reference and constant | ALC-03, REC-01, REC-02 | band (Q4) |
| D0 per-lot stop scope | EXT-05 | band, lower confidence |
| Cycle-stop constant | RSK-01 | band (Q4) |
| Lump (`v_`) size | SIZ-04 | placeholder |
| Capital / margin sizing | SIZ-05 | not modelled (fixed base units) |
| Eligibility / no-trade filter | ENT-05 | none (trade every cycle in the data) |
| "4 % carry SL" | RSK-02 | placeholder (six interpretations available as `user_rule`) |
| "1 % on expiry day" | RSK-03 | placeholder |
| Final-flatten rule before 3 Aug | EXT-08 | band: 15:14 everywhere vs 15:14 only after 3 Aug |
| Post-cycle-stop short fills | ALC-09 | not simulated; reported in validation |
| Module order inside one poll | spec §D [H] | configurable; default order stated in the spec |
| Profit target / trailing stop | EXT-06 | none in the skeleton unless Stage 3 supports one |

## 2. Assumptions the skeleton cannot avoid (stated, not hidden)

1. One-minute simulation; second-level ordering inside a minute is not represented.
2. Option prices exist only for contracts Algo 8 traded, so a strike it never touched cannot be simulated.
3. Lots open after the last bar settle at intrinsic value from the last index close.
4. No bid/ask: the minute bar is the only price; spread and impact enter only through the fill models and costs.

## 3. Decisions needed (recommended option first)

| # | Decision | Options |
|---|---|---|
| Q1 | **Cost model** (the export has no charges) | **A)** the four registered scenarios already used by `alpha_freeze` (`analysis/engine.py::COSTS`: zero, moderate, conservative, adverse), gross always shown · B) a statutory schedule whose rates you supply · C) gross only |
| Q2 | **Ownership models** for TP and validation | **A)** cheapest, FIFO, LIFO, contract average, slot, chain, all reported separately · B) a subset you name |
| Q3 | **Salvage** (≤ ₹1 / ≤ 5 % buy-backs on D0, 13.5 % of lots) | **A)** expiry-day liquidation, excluded from TP candidates and reported separately · B) treated as profitable discretionary exits |
| Q4 | **Band parameters** in the skeleton | **A)** run each evidenced value separately: lot stop k ∈ {1.55, 1.60, 1.65, 1.70} × reference {cheapest open, own entry}; cycle stop ∈ {−₹1.30 L, −1.33 L, −1.35 L}; ladder {Y, X}; nothing selected on TEST · B) a single value per parameter that you choose |
| Q5 | **Default mode for placeholders** | **A)** report every validation run twice: all placeholders `disabled`, and each placeholder `teacher_forced` one at a time · B) `disabled` only |
| Q6 | **Non-body short lots** (554, opened by `s_` / `h_` / `v_`) | **A)** separate population, excluded from the primary TP test · B) pooled with body shorts |
| Q7 | **TP grid** (360 cells, §6 T3 of the methodology) | **A)** approve as written · B) amend |
| Q8 | **TP decision standard** | **A)** as written (80 / 80 for "identified"; lift + nulls for "mechanism supported") · B) amend |
| Q9 | **Validation tolerances** | **A)** entries and hedges ± 1 min, exits ± 2 min (as PR #3), strikes exact and ± 1 step · B) amend |
