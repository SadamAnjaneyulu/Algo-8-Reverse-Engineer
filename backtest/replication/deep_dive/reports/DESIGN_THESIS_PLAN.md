# What idea was Algo 8 built on? — plan

*Written before any of the tests below (2026-11-24). It follows `ALPHA_SOURCE.md` and a read of all 22 branches. Every cycle has been used before, so all tests are **exploratory**; the hypotheses, tests, predictions and reading rules are fixed here so that the answer is not chosen after seeing results.*

## Why this step
`ALPHA_SOURCE.md` showed what the *simulated* book earns (short-premium carry, a trend-aligned ladder, protective rules that cost mean). The question now is the designer's **idea**: the market belief that someone turned into this machine. The machine itself gives strong clues (branch evidence, summarised in `DESIGN_THESIS.md`):

* The client called it **"a BTST algorithm"** that carries positions to expiry (`risk_rule_validation`, client wording).
* A sibling, **Algo 7, trades the expiry day only** (`dte_comparison`); Algo 8 adds the day before and the overnight carry.
* It sells ATM straddles on a **15-minute clock** all day before expiry and on expiry day, buys cheap far wings, carries a fully winged book overnight, and closes by 15:14 (`STRONG_FINDINGS` F01–F34; D-1/D0 decodes).
* A reactive **ladder** sells calls after new 60-minute lows and puts after new 60-minute highs (`bl_bt3_sim.py`, `d1_algo/engine.py`).

These suggest candidate beliefs. Each one makes a **market-level prediction that can be tested on the 3-year chain data without the strategy simulator** (so the test cannot be an artefact of my reconstruction).

## Candidate beliefs and their tests

| # | Belief the designer may have held | Test (market data only; 275 cycles, D-1 + D0 minute chains) | Prediction if the belief is right |
|---|---|---|---|
| B1 | **Options are over-priced near expiry** (implied volatility above what is realised): selling ATM premium pays on average | **T1:** short ATM straddle, re-struck at the start of each segment, held over the segment: D-1 day (09:16 open → 15:29 close), overnight (D-1 15:29 close → D0 09:16 open, sensitivity 09:15 open), D0 day (09:16 open → 15:14 open). Also the **realised ÷ implied variance ratio** per segment (implied variance consumed = change in (straddle ÷ (S·√(2/π)))², realised = sum of squared index log returns, the gap included overnight) | Positive mean P&L and ratio < 1 in the segments the strategy trades |
| B2 | **The overnight before expiry is over-priced** (the "BTST" carry) | T1 overnight segment | Positive mean, interval above zero, and larger per unit of implied variance than the day segments |
| B3 | **Expiry-day decay is the richest** | T1 D0 segment; **T2:** mean P&L of a 15-minute short ATM straddle in every 15-minute block of both days, as % of premium | D0 per-block decay larger than D-1 |
| B4 | **Short-horizon index moves continue** (selling the right on the side the market is leaving earns the move) | **T3:** events = the ladder's own trigger (new 60-minute low or high of the index; D-1 and D0 separately). Forward index return from the event minute's close to +15, +30, +60 minutes and to the session end, signed by the event direction; and the model-free option version: short ATM call vs short ATM put sold at the event minute's close, held to the session end (and, for D-1 events, to D0 15:14) | Signed forward return > 0 (continuation); the ladder's right beats the opposite right |
| B5 | **Calls and puts are priced differently** (skew or drift) | **T4:** short ATM call and short ATM put separately, D-1 09:16 open → D0 15:14 open, per split | Not a belief of the machine (it sells both); reported to explain the real-log asymmetry (short calls +₹36 lakh, short puts −₹8.9 lakh in the 32 real cycles) |

## Statistics (locked)
* Unit = cycle; intervals by **week-cluster bootstrap** (2,000 draws, seed 20261124); NIFTY and SENSEX cycles of one ISO week resampled together. T3 events are clustered by session (resampling weeks keeps that).
* Each test reported for **all cycles** and by **split** (IS / OOS / live window), and by index. P&L in index points, in % of premium, and in ₹ at the constant lot size (NIFTY 65, SENSEX 20). Gross only (no costs); one ATM straddle costs 1.3–3.1% of premium per round trip (stage 2 estimate), quoted next to the result.
* Holm correction over the five primary predictions (T1 D-1, T1 overnight, T1 D0, T3 continuation to session end, T3 option version).

## Reading rules (locked)
* A belief is **supported** if its primary prediction has the predicted sign with a 95% interval excluding zero **and** the same sign in IS and OOS. **Weakly supported**: predicted sign, interval includes zero, same sign in IS and OOS. **Not supported**: otherwise.
* "Supported" means the market behaved as the belief says over these 3 years. It does **not** prove the designer held that belief, nor that it persists.
* Data limits: option minute closes (no bid/ask); D0 09:15 option prices can be stale; ATM implied variance from the straddle approximation is rough at very small premiums (late D0), so the variance ratio is reported only to 15:14.

## Deliverable
`DESIGN_THESIS.md`: (1) a knowledge graph of the findings from all 22 branches (each node: finding, branch/file, evidence level), (2) the test results above, (3) the reconstructed design thesis, each part with its evidence level, (4) what is still unknown.

## Addendum 1 (2026-11-24, written after T1–T4 were run, before T5–T6)
**What I saw:** T3 shows the index **reverting**, not continuing, after the ladder's trigger (signed return −1.4 bp at +15 min, −5.5 bp to the D-1 close; D0 similar but weaker), and the ladder's right does worse than the opposite right held to the session end. This contradicts the "trend-aligned ladder" reading in `ALPHA_SOURCE.md` (which rested on the simulator's flipped placebo, whose gross interval includes zero). A different role for the ladder fits the structure: **keeping a short-straddle book delta-balanced by selling the side the market moves away from**. Two tests are added to check that role and the role of the 15-minute clock. They are post-hoc additions and are labelled so in the result.

| # | Belief | Test | Prediction |
|---|---|---|---|
| B6 | **Spreading the sales over the clock (and re-centring on the current ATM) lowers the risk of a short-premium carry without changing its mean** | **T5:** sell one ATM straddle at the start of every 15-minute block of D-1 (09:16 … 15:01), held to D0 15:14 open, (a) re-struck at each entry's ATM, (b) all at the 09:16 strike; versus the single 09:16 straddle (T4/naive). Per cycle: P&L ÷ premium. Compare mean (bootstrap) and the cycle standard deviation (ratio, bootstrap) | Mean ≈ the single entry; standard deviation lower for (a) than for the single entry and than for (b) |
| B7 | **The ladder is delta rebalancing, not a forecast** | **T6:** at each D-1 ladder trigger of T3, the delta of a reference book = the (a) straddles of T5 sold before that minute (Black, each leg's own implied total standard deviation, r = 0), and the delta of the ladder's sale | The ladder's sale reduces the absolute book delta in most events (> 50%, bootstrap by week) |
