# Programmed-rule matching protocol

Algo 8 is treated as automated. Unknown rules mean unidentified code/configuration,
not manual discretion. All times are IST. This is execution-rule identification,
not a profit-optimized strategy search. Existing September–October data were
previously examined, so chronological evaluation is not a blinded holdout.

## Questions and non-negotiable distinctions

1. Compare each later short allocation's strike with the cycle's initial sold
   strike and with the contemporaneous completed index minute's ATM proxy.
2. Separate fresh long purchases from short buybacks. Match new hedge parents
   once to their nearest short execution batch, report 2/5/30-second windows,
   and inspect already-existing outward long inventory. Coincidence is not a
   verified basket link; long/short quantities alone do not establish risk limits.
3. Search indicator conditions against additions, buybacks and new protection,
   including negative opportunities. Do not judge a rule only at actual trades.
4. Search exit references and thresholds by first causal crossing, then compare
   with observed terminal material short reductions. Report matching failures.
5. Search hedge selectors against alternative quoted strikes, separately for
   initial, routine and late purchases and for pre-expiry versus expiry.

## Data, causal timing and evaluation

Use the received index and traded-contract option bars and raw fill reconstruction.
Collapse partial fills into parents; exclude role classifications sensitive to
same-second tie reversal. Do not treat every buy as a hedge or every sell as a
new short. Preserve source references without broker/client identifiers.

Three buy parents contain fewer observed fills than their requested quantity.
Keep both quantities; do not invent the unfilled portion.

For a decision minute T, indicators and state use fills strictly before T−1min
and bar starts at most T−2min. Quote selectors separately use the last completed
minute before the actual first fill; exact intraminute quotes are unavailable.
No missing replay price is filled. Indicator initialization and missingness are
reported. Spot indices have no usable traded-volume series here: no fabricated
index VWAP. Intraday TWAP is labeled as such.

Calibrate using expiries through 31 August 2026, evaluate using later expiries.
Select parameters on calibration cycles only. Give each cycle equal weight when
ranking condition/selector candidates. Report calibration and later match rates,
coverage, precision/recall and negatives. Thousands of hypotheses are exploratory;
even a strong later match is a candidate, not proof of original-code identity.

## Frozen indicator families and parameter grids

- Wilder RSI periods 5/7/10/14/21/28; levels 20–80 by 5; neutral bands about 50.
- EMA pairs using fast 3/5/8/9/12/20 and slow 15/20/21/26/30/50/100; direction,
  crosses and normalized separation.
- Bollinger-style close z-scores: 10/20/30/50 bars, levels ±0.5/1/1.5/2/2.5/3.
- Wilder ATR 5/7/10/14/20/21/28/30, normalized thresholds; ADX 7/14/21/28,
  levels 10–50 by 5.
- Supertrend ATR 7/10/14 with multipliers 1/1.5/2/2.5/3; direction/crosses.
- Donchian lookbacks 5/10/15/20/30/60, close breakouts versus earlier bars.
- Spot returns/ranges, opening gap/open-to-now return, TWAP distance; option
  premium/IV changes and known leg-price stress; inventory, buybacks and MTM.
- State predicates and threshold crossings are distinct candidates. Test
  individual conditions and filters on the existing clock/open-book baseline;
  do not declare a generic true-most-of-the-time condition a signal.

## Exit and hedge grids

Exit candidates include cycle MTM, expiry-day change versus previous close or
expiry open, drawdown/trailing loss, profit targets and spot displacement, plus
indicator crossings. Capital-loss/profit grids span 0.1–1.5% (including the stated
1%); test the stated 4% carried-short price increase as a separate reference,
not 4% of capital. Combine diagnostic first crossings with fixed terminal-time
fallbacks (15:14 after 3 August; 15:29 earlier). The actual evolving portfolio
cannot simulate a counterfactual strategy after an earlier hypothetical exit.
Missing/zero-volume marks and carry attribution ambiguity remain explicit.

Hedge selectors: fixed outward distance from current ATM or latest known sold
strike; distance as % spot; premium closest/ceiling/floor across a target grid;
premium as a fraction of known near-ATM straddle value; model absolute delta;
volatility-scaled distance. Compare fresh positive-volume quotes with all
positive-price quotes as a sensitivity. The downloaded chain contains only
contracts traded somewhere in the log: candidate-chain match rates are
conditional on that incomplete retrospective universe. Avoid presenting a
restricted-chain match as a verified full-chain selector.

## Deliverable

Produce explicit strike/hedge association counts, all searched parameter scores,
training-selected candidates and their later predictions/failures, cycle-level
exit timing checks, executable reproduction scripts and focused causal tests.
Update the working rulebook only with evidence-supported patterns.

## Secondary expansions and interpretation limits

The following extensions were added after the first audit/model results, so
they are exploratory even though parameter selection still uses earlier cycles:

- Short-strike grids compare current minute open, completed closes 1/2/3/5 bars
  earlier, parity forward, rounding/offsets, initial/previous strike, hysteresis,
  and quarter-window anchors. Separate scheduled and extra executions. Inspection
  of extra pre-expiry strikes motivated signed momentum shifts/projections using
  completed 1/3/5/10/15-minute changes. Later data influenced that hypothesis's
  introduction; chronological cross-checks are not independent confirmation.
- A faster indicator sensitivity uses actual first-fill minutes with fills
  strictly before T and the completed T−1 bar. It excludes the tolerated
  quarter-window task to prevent its one-second-early fills leaking into state.
  Evaluate one-to-one event matches within 0–2 minutes after a signal as well as
  exact-minute labels. Warm-up/missing observations cannot trigger a predicate.
- Carried-contract first buybacks are compared with previous close, pooled
  average entry, FIFO/LIFO residual-entry costs and expiry opening prices. Test
  fixed stops, profit targets and expiry-only trailing minima with/without an
  opening-price proxy. First buyback is not a verified allocation-specific exit.
- Temporal buyback/new-sale links are assigned at most once within 5/15/30
  seconds; proximity can precede or follow the sale and does not prove a roll.
- Inspecting paired sell/buy premiums motivated a secondary hedge-budget search:
  0.5–10% fractions of the corresponding current ATM leg, previous known short
  leg, or temporally linked short leg, using nearest/ceiling/floor selection.
  The linked-short version is explicitly conditional on that observed short
  strike; it is not an independently forecast short strike or a future fill-price
  input. Keep its results separate from the independently known ATM reference.

The search counts parameter/context evaluations, including repeated parameters
in different cohorts, not that many independent strategy hypotheses. No
family-wise significance or untouched external replication is claimed.
