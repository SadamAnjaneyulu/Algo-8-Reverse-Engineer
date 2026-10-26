# Follow-up: hedge-budget rounding and the meaning of an exit

This continues the [mass rule-matching study](MASS_RULE_MATCH_FINDINGS.md).
It adds 960 hedge-budget comparisons and 2,244 loss-scope/exit-target comparisons
to the original 68,516: **71,720 calibration parameter/context comparisons** in
total. These are exploratory searches on the same previously inspected data,
not independent experiments or a new profit backtest. Parameters are still
chosen using earlier cycles before checking later predictions.

## 1. The pre-expiry 2.5% hedge-budget lead survives refinement

Search fractions 2/2.25/2.5/2.75/3% of the corresponding ATM option premium,
target ticks 0.05/0.10/0.25/0.50/1.00, explicit nearest-half-up/floor/ceiling
rounding or no rounding, and nearest/ceiling/floor option selection. Reuse the
same prior completed, positive-volume OTM quotes and retain all event denominators.

The earlier-selected pre-expiry candidates remain:

| Index | Fraction and target handling | Exact later strike | Exact or adjacent later strike |
| --- | --- | ---: | ---: |
| NIFTY | 2.5%, unrounded budget; highest premium within budget | 316/637 (49.6%) | 586/637 (92.0%) |
| SENSEX | 2.5%, budget rounded to nearest ₹0.10; highest premium within budget | 321/623 (51.5%) | 589/623 (94.5%) |

“Adjacent” means at most one 50-point NIFTY / 100-point SENSEX strike step;
it does not mean the exact original strike was recovered. Across the seven later
pre-expiry cycles per index, exact matches range 42.6–57.0% NIFTY and 44.1–58.4%
SENSEX. Thus the aggregate result is not supplied by just one successful cycle.
The incomplete retrospective chain can still make a selector appear better
than it would against a full contemporaneous chain.

This is a candidate **insurance premium budget**:

```
CE budget ≈ 2.5% × current ATM CE premium
PE budget ≈ 2.5% × current ATM PE premium
choose OTM strikes using each side's budget
```

For example, ATM CE ₹80 and ATM PE ₹100 imply budgets about ₹2 and ₹2.50.
Rising/falling premiums and changing skew naturally move the purchased strikes.
This explains the logic of a variable gap better than a fixed ±2,000 points for
every allocation. It remains separate from the observed initial seed-wing rule.

Expiry-day refinement is less uniform:

- SENSEX selects a 2.5% budget rounded down to ₹0.10, then the nearest quoted
  premium: **526/806 (65.3%)** exact and 696/806 (86.4%) within a strike step.
- An unrounded nearest-premium 2.5% rule already matches 513/806 (63.6%). Most
  improvement over the earlier ceiling selector comes from nearest-versus-ceiling
  selection; rounding contributes about 1.6 percentage points, not the full gain.
- NIFTY selects 2.25% with rounding on calibration, but it performs worse later:
  253/743 (34.1%) exact versus 288/743 (38.8%) for the original 2.5% nearest rule.
  Do not hide this failed refinement or promote it to an original instruction.

Initial, routine and late hedges, quote versus trade prices, within-minute
selection, eligibility and tie handling are still material unknowns. Parameter
rounding alone does not solve the exact selector.

## 2. Separate short-option losses from hedge and realized P&L

The new signed role ledger splits opening shorts, short buybacks, new long
options and long sales, including a contract changing from long to short. It
tracks pooled entry cost, realized P&L and remaining unrealized P&L separately.

Its full-book values reproduce **all 25,565 existing session-minute snapshots**,
including the same missing marks. A missing long-option quote does not invent
a net mark or erase a separately available short-book mark. The identities
checked are:

```
net marked P&L = short-book P&L + long-book P&L
net marked P&L = realized P&L + unrealized P&L
```

Reversing source order inside each second leaves net marked P&L unchanged.
The maximum change in short-book attribution is ₹307; the maximum change in
realized/unrealized attribution is about ₹822.07. These alternative-order
diagnostics are retained; the decomposition is not claimed to identify original
allocation lots or the broker's risk-accounting policy.

Candidate stop scopes include net, short-only, CE-only, PE-only, realized,
unrealized, short unrealized and gross losing open positions; cycle, previous-
close, expiry-open and drawdown references; and short-premium loss percentages.
Opening marks are separate proxies. Zero-volume marks remain flagged.

## 3. A major reduction, first closure and final closure are different labels

Compare three execution outcomes explicitly:

1. Terminal reduction to at most 5% of carried short quantity.
2. First expiry-day moment the whole short book becomes zero.
3. Final short-book closure after which no observed short exposure returns.

The 5% label is an analysis convention, not a decoded risk instruction. Whole-
book transitions net all events sharing a second, avoiding a fabricated zero
between orders at the same timestamp. For example:

| Cycle | Material reduction | First whole short-book zero | Final whole short-book zero |
| --- | --- | --- | --- |
| NIFTY 7 July | 15:22:29 | 15:26:23 | 15:26:23 |
| SENSEX 6 August | 09:24:48 | 09:24:40 | 09:31:47 |
| NIFTY 13 October | 09:18:11 | 09:18:11 | 09:23:07 |

Attributing every large reduction to a capital stop or calling the first zero
the permanent exit would merge different programmed behaviours.

There are **86 fresh-short parents with first fills after the first short-book
zero**, across 10 cycles. Of those, **20 parents across four cycles have order-
label minutes later than that first closure**. SENSEX 6 August has labels at
09:30 after an initial 09:24:40 closure; NIFTY 13 October has a 09:23 label after
09:18:11. Labels are inferred, but later fills are not all explained by a
single permanent entry lock. Pending-order handling versus newly permitted
entries must be modeled rather than assumed.

## 4. Expanded stop scopes still do not recover exact exits

The added opening snapshots allow 30 cycles: 18 calibration / 12 later for the
material-reduction target. Three cycles missing an active completed-minute mark
in the prior test become eligible through the opening proxy. Whole-book closure
labels have 17 calibration / 12 later cycles; one carried cycle has no observed
complete short closure. These cohorts differ from the original 16/11 comparison.

On the later 12-cycle cohort, including opening proxies:

| Diagnostic first-crossing rule, with fixed late-time fallback | Material reduction within 2m | Final short closure within 2m |
| --- | ---: | ---: |
| Time fallback only | 6/12 | 6/12 |
| Earlier-selected net cycle loss near 0.5% of stated capital | 8/12 | 7/12 |
| Net cycle loss of 1% of capital | 6/12 | 6/12 |
| Short-book cycle loss of 1% of capital | 7/12 | 7/12 |

The selected 0.5% rule also gives two false early signals on later cycles and
mean absolute timing error about 75 minutes. It must **not** replace the supplied
1% capital rule. For early material reductions it matches 4/6; for early final
closures it matches 3/6. Much overall success comes from the late fallback.

For illustration, the known opening mark before SENSEX's 24 September reduction
is about −₹197,464 net versus −₹202,790 for the short book. That case is compatible
with different scope or intraminute interpretations near a ₹200,000 stop.
Other closures occur at very different values; the ledger does not make one
scope a universal explanation.

These tests concern one first crossing on the actual evolving book plus a time
fallback. They do not implement a composite stop/profit/position controller,
cancel pending orders, reset a risk reference or simulate hypothetical re-entry.
Minute quotes and opening proxies cannot establish an exact intraminute trigger.
The stated carry 4% / capital 1% controls remain unresolved in their precise
scope and accounting basis, not disproved as possible components.

## 5. Current decoder status

The strongest observed/reconstructed components are scheduled pre-expiry
allocations, changing short strikes and frequent fresh protection. Directionally
shifted extra-sale strikes and the routine 2.5% ATM-premium hedge budget are
useful candidate mechanisms. Extra-entry timing, exact quote selection, exit
composition and reset/pending-order behaviour remain the missing functions.

## Reproduce

```sh
python research/refine_hedge_budget.py
python research/refine_exit_scopes.py
python -m unittest discover -s research -p test_rule_refinements.py -v
```

`refine_exit_scopes.py --reuse-ledger` reuses the saved component ledger for
label/parameter work. The `rule_refine_*` outputs include every calibration score,
later prediction, per-cycle hedge score, reconciled role marks, loss-scope
contexts, closure episodes and post-closure order-label references. Raw market
prices and trade logs are unchanged.
