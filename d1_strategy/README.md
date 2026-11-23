# D-1 strategy (session before index-option expiry) — Python reconstruction

A rule-based reconstruction of what the observed system does on the **day before expiry** ("D-1") on index options (NIFTY / SENSEX style weekly expiry), fitted to the order log of 32 live cycles.

## What it does
One pass over the one-minute bars of the day produces every order:

| Role | Rule (short version) |
|---|---|
| `scheduled_straddle` | 33 timetable waves per day at fixed seconds. Each wave sells 1 lot call + 1 lot put at the ATM strike of the previous minute's close. Clock only, no market condition. |
| `breakout_straddle`, `breakout_extra` | From 10:30 to 15:15, first break per side per 30-minute candle of the high/low of the previous two completed candles: sell a straddle one strike beyond ATM in the break direction (1–3 lots by break depth) plus extra single lots on the favourable side. |
| `ladder_solo` | One-lot sales of the option whose side the market is moving away from (calls on a fresh low, puts on a fresh high), every 0.2 strike steps beyond a reference, gated by a fresh 60-minute extreme. |
| `stop_buyback` | Each lot is bought back when its option price reaches about 1.6× its own entry price (minute high). |
| `protective_wing_buy` / `_sell` | After every body order, long lots on each right are kept equal to short lots on that right, at the OTM strike whose premium is nearest 2.5% of the ATM premium. Wings are released outermost first when shorts are bought back. |
| `opening_wing_buy` | 3 far OTM calls + 3 far OTM puts at 09:16, about 40 strikes out. |
| `overnight_lump` | One extra block of OTM longs on the heavier short side before the close, about 2.2 one-day sigmas out, sized about 0.83× (NIFTY) / 0.50× (SENSEX) the heavy-side short lots. |

## Use
```python
import numpy as np
from algo8_d1 import config_for, D1Strategy, OptionChain

# spot_open/high/low/close: arrays of length 375 (09:15..15:29)
# strikes: ascending 1-D array; bars[(right, field)] -> array [n_strikes, 375], right in {"CE","PE"}, field in {"open","high","low","close"}
chain = OptionChain(strikes, bars)
cfg = config_for("NIFTY", "2026-09-08")          # timetable version and lump clock observed for that date
result = D1Strategy(cfg).run(spot_open, spot_high, spot_low, spot_close, chain)
print(result.orders_frame().head())               # minute, right, strike, lots, side, role
print(result.short_lots, result.long_lots)        # end-of-day book carried into expiry day
```
`python example_synthetic.py` runs the whole thing on synthetic data. `python -m pytest test_algo8_d1.py -q` runs the unit tests.

## How well does it reproduce the original?
* **Checked against our research simulator:** on identical parameters this module produces the same orders on **32 of 32 cycles**.
* **Against the real order log** (parameters fitted on the same 32 cycles, so in-sample): lot-level F1 **0.69** (precision 79%, recall 62%), timing ±1 minute and same right.
* **On cycles not used for fitting** (earlier forward test of the same rules): F1 about **0.63**, AUC for "is the system active in this minute" about **0.92**.

| Class | F1 (in-sample, timing ±1 min) |
|---|---|
| Body sells (all three types) | 0.76 |
| Opening wings | 0.97 |
| Wing buys | 0.73 |
| Overnight lump | 0.70 |
| Buy-backs | 0.55 |
| Wing sells | 0.53 |

## Files
`algo8_d1.py` (the strategy), `example_synthetic.py` (demo), `test_algo8_d1.py` (tests).
