# Test the range / theta / IV-management explanation

Hypotheses recorded before this model study's results:

1. The opening protected short-straddle book has positive time decay and negative
   net IV sensitivity. OTM longs should reduce, not necessarily remove, those risks.
2. Sharp forward/index moves can cause losses even at constant IV. IV is therefore
   not assumed to be the sole risk or the cause of every loss.
3. If routine additions are mainly IV-risk reduction, their net IV sensitivity
   should move toward zero; if they are new premium-selling allocations, they may
   instead increase short-IV and convexity exposure. Evaluate the whole minute's
   inventory change at the same prior completed market state.
4. Test whether IV rose before paired short additions and major hedge/exit events.
   Use a 15-minute same-strike IV proxy change; +1 volatility point is an explicit
   descriptive threshold (20% to 21%), not a decoded strategy parameter.
5. Attribute frozen-opening-basket and actual overnight-carry price changes into
   time, forward movement and IV using a symmetric three-factor decomposition.
   It is a model estimate, not direct observation of separate cash profits.

## Model and data constraints

Use European Black pricing with forward inferred from a same-expiry CE/PE pair.
Choose a near-ATM pair among the quoted traded contracts, using the index as a
selection guide; both positive-volume candles are required for primary close
states. After cash close the index guide can be stale and is flagged, while the
forward is still derived from option parity. Available contracts are restricted
to the observed traded universe, not the complete chain.

Primary discount rate is zero for these very short horizons. The modeled expiry
anchor is 15:30 before CAS and 15:35 afterward; neither asserts a supplied actual
settlement timestamp. Sensitivities use a 6% annual discount rate and expiry
anchors five minutes earlier/later. Calendar ACT/365 time includes nights/weekends.
Changing the volatility clock can change apparent overnight IV and theta.

IV is inverted from observed trade-candle prices. Reject prices below intrinsic,
nonpositive time, and effectively unidentifiable extrinsic value (<=0.025 units).
Missing prices/failed inversions remain unavailable. Retain low-premium and
zero-volume flags; no quote interpolation or forward filling. Trade bars need
not be synchronous bid/ask observations, limiting exact IV/Greek measurement.

Strict pre-event features use only the previous completed option minute. Expiry
09:15 events have no same-session completed candle: opening-price proxies are
reported separately and cannot establish subminute causality. Compare 15-minute
changes at the same selected strike to avoid treating an ATM-strike switch as
an IV signal. Moneyness/skew effects still remain possible.

For endpoint attribution, freeze quantities and average the six factor orderings
of time, forward and per-leg IV changes (Shapley allocation). These allocations
sum to the fitted endpoint price change; interactions are assigned symmetrically.
Frozen opening baskets are a counterfactual economics diagnostic. Overnight uses
the actual end-of-pre-expiry inventory and actual option-session endpoints.
Exclude failed legs from fitted totals and disclose unallocated price changes.

No claim of a blinded holdout, unique causal trigger, executable quote, or measured
strategy alpha follows from these estimates. Estimate net Vega for one absolute
IV point and net gamma; do not infer risk from counts of buy/sell orders alone.

## Diagnostics added after the initial model fit

Compare early-loss IV changes with other same-index, same-clock expiry sessions
whose short books are still active. Those controls address the observed general
overnight rise in annualized model IV; they are descriptive matched comparisons,
not an independently selected predictive backtest. Opening proxies remain separate.

Show a strict event-exposure subset excluding any zero-volume or <=0.10-price
legs before/after the event. Keep long-horizon frozen-basket endpoint decompositions
as diagnostics only: tick-floor far-wing prices and large counterfactual IV/time
offsets can make that decomposition unsuitable for an economic claim. Retain its
raw results and limitations rather than interpreting them as actual theta cashflow.
