# D-1 algo: the strategy as a running program

This is what you would write to run the day-before-expiry (D-1) strategy yourself: an **event-driven engine** that reads prices every second, builds minute bars, applies the rules with only the information available at that second, sends orders through a risk guard to a broker, and keeps a position book and a state file.

```
 MarketData (feed)  ──►  D1Engine.step()  ──►  RiskGuard  ──►  Broker
   spot, option LTP         bars, signals,         limits,         place(), poll_fills()
                            book, timers           kill switch
                              │
                              └── state file (restart), log
```

## What the engine does each second
1. Read the spot and the contracts it watches; update the one-minute bars.
2. Collect broker fills; update the book (short lots with entry prices, wings, lump) and the pending-order counts.
3. Run the rules, in this order:

| Rule | Behaviour |
|---|---|
| Opening wings | At 09:16:00 buy 3 far OTM calls and 3 far OTM puts (about 40 strikes out). |
| Scheduled straddles | 33 waves at fixed seconds after 09:16:00. Each sells 1 lot call + 1 lot put at the ATM of the **previous completed minute's close**. |
| Breakout straddles | From 10:30 to 15:15: first break per side per 30-minute candle of the high/low of the previous two completed clock-aligned candles. Sell a straddle one strike beyond ATM in the break direction (1 to 3 by break depth) plus favourable-side extras. |
| Solo ladder | One-lot sales when the spot moves 0.2 strike steps beyond a reference (reset at each scheduled/breakout sale) and makes a fresh 60-minute extreme: calls on a fall, puts on a rise. |
| Stops | Each lot is bought back when the running high of its option in the current minute reaches 1.6 times its own entry price (a lot cannot be stopped in the minute it was sold). Cheapest entry first. |
| Wing controller | About 4 seconds after body orders, buy exactly the gap between short and long lots on each right at the OTM strike whose premium is nearest 2.5% of the ATM premium; when shorts fall, sell the excess wings, outermost first. |
| Overnight lump | At the configured minute (15:11 to 15:30 depending on the date regime): on the heavier short side, 0.83x (NIFTY) / 0.50x (SENSEX) the heavy-side short lots, about 2.2 one-day sigmas out. |

4. Every order goes through the risk guard (kill-switch file, halt flag, short-lot limit, orders-per-minute limit, valid limit price), is split at the exchange freeze quantity (27 lots NIFTY, 50 SENSEX), is priced as a marketable limit (LTP -/+ 1%) and is sent.

## Run it on paper
```bash
pip install numpy pandas pytest
python run_paper_example.py          # one synthetic session, second by second, paper broker
python -m pytest test_d1_algo.py -q  # 10 engine tests
```
```python
from d1_algo import ReplayFeed, PaperBroker, D1Engine, config_for, run_replay
feed = ReplayFeed(spot_o, spot_h, spot_l, spot_c, strikes, option_bars)   # your one-minute bars
engine = D1Engine(config_for("NIFTY", "2026-09-08"), feed, PaperBroker(feed))
run_replay(engine, feed)
print(engine.orders_frame())
```
`option_bars[(right, field)]` is an array `[n_strikes, minutes]` for right in CE/PE and field in open/high/low/close.

## Run it live
Implement the two adapters in `d1_algo/live_template.py` (`MyFeed`, `MyBroker`) for your data vendor and broker, test them against the broker's paper or sandbox environment, then run the loop. Requirements for the adapters:
* **Feed:** streaming last-traded prices for the index and every listed strike of the traded expiry, both rights; `now()` in exchange time.
* **Broker:** `place()` sends a limit order using `OrderRequest.tag` as the client order id (idempotent); `poll_fills()` returns confirmations; `positions()` for reconciliation after a restart.
* Restart: `engine.load()` restores the book, done waves, ladder references and bars from the state file; `engine.warm_start(history)` loads completed minute bars if there is no state file. Reconcile `engine.book` with `broker.positions()` before trading.
* Live mode is refused unless `D1_ALLOW_LIVE=1` and `cfg.paper = False`.

## Configuration (`D1Config`)
Instrument (strike step, lot units, freeze quantity), the scheduled timetable (two versions were observed; `config_for(underlying, d1_date)` picks the one for that date), breakout, ladder, stop and wing parameters, lump parameters, execution buffer, and risk limits (`max_short_lots_per_right`, `max_orders_per_minute`, `max_loss_rupees`, `kill_switch_file`, `state_file`).

## How it was checked
* **Replay on the real data:** the one-minute bars of the 32 observed D-1 sessions were replayed second by second through this engine with the paper broker, and its orders compared with the real order log lot by lot (same side and class, within one minute): **F1 0.69, precision 75%, recall 64%** (the constants were fitted on the same 32 sessions, so this is in-sample; the earlier forward test of the same rules gave F1 about 0.63 on unseen cycles).
* **Unit tests:** 10, covering the clock and the ATM strike rule, late waves, wings equal shorts, breakout once per side per candle, the stop, the ladder, the kill switch, freeze-quantity splitting, the state file, and the invariants of a full replayed day.
* `algo8_d1.py` is a separate batch version (whole-day bars in, orders out) used for research; the engine above is the one to build on.

## Files
`d1_algo/` (`config.py`, `models.py`, `interfaces.py`, `book.py`, `bars.py`, `risk.py`, `engine.py`, `sim.py`, `live_template.py`), `test_d1_algo.py`, `run_paper_example.py`, `example_synthetic.py`, `algo8_d1.py` (batch reference), `test_algo8_d1.py`.
