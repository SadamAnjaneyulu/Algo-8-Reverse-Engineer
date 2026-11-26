# Forward recorder: extra state fields for the late-sale hypotheses

*Additive companion, not a change to the frozen forward protocol. `d1_strategy/d1_algo/shadow.py` (hash `6d4b8608…`), the frozen rule (`ca1306cf…`) and the frozen score (`7788f739…`) are untouched; `FORWARD_TEST.md` is not edited. The new fields are written by `d1_algo/shadow_state.py` into a separate file.*

## Use
Replace `ShadowRecorder(...)` by `StateShadowRecorder(...)` (same constructor and same calls: `on_snapshot` about once a second from 09:15, `on_real_order` for every real fill, `close()`). The parent's `minutes_*.jsonl` and `orders_*.jsonl` are **byte-identical** to what the plain recorder writes (tested). One extra file per underlying and day: `state_<und>_<d1>.jsonl`. Every record carries the rule hash and `state_spec_sha` (hash of the field definitions).
Assumption: the recorder runs from the session start with a flat book. Positions, lot counts and marks come from the recorder's own order ledger so cash and positions are from the same instant; `ledger_matches_snapshot` flags any drift from the caller's positions.

## `state_minute` (one per minute, written at the close of minute m for decision minute m + 1; nothing after the close of m is used)
| Field | Definition | Hypothesis it serves |
|---|---|---|
| `STR15`, `straddle`, `straddle_15_minutes_earlier`, `atm_strike`, `index_used_for_atm` | ATM call + put close; ATM nearest the option-implied index (fallback: the future); `STR15` = straddle[m] ÷ straddle[m−15] − 1 | straddle decline → sale (timing) |
| `close`, `close_5_minutes_earlier`, `move_5m_raw` (FUT, FEED, OPT) | minute closes and the 5-minute move | side = contrarian |
| `side.CE/PE.fut_move_5m_steps_oriented` | +move/step for PE, −move/step for CE (positive favours the contrarian side) | side |
| `side.*.sold_lots`, `sold_deficit_oriented` | cumulative open-short lots today per side; other side − this side | lot balance |
| `side.*.net_short_lots`, `net_deficit_oriented` | net short lots held (after covers) | lot balance |
| `side.*.D_fut`, `D_opt` | OTM steps of the nearest net-short strike on the side vs the FUT close and vs the option-implied close (the latter is basis-free); null if no short | re-centring (negative so far) |
| `mtm`, `premium_collected`, `PP`, `GB` | MTM = order cash + marks of open legs; `PP` = MTM ÷ premium collected; `GB` = MTM − earlier peak | profit booking (negative so far) |
| `atm_chain` | close premiums [CE, PE] for the 9 strikes around ATM | rebuild the side's ATM-premium change offline |
| `seconds_since_last_short_sale` | seconds since the last open-short | burst structure |

## `order_state` (one per real order, written before the order is applied)
`action` (`open_short`, `cover_short`, `open_long`, `close_long`, or a combined `close_long+open_short` / `cover_short+open_long` when one order crosses zero), `ledger_net_lots_before`, `sold_lots_before` per side, `seconds_since_last_short_sale` (any side and same side), and for a sale that closes a long: `matched_lots`, `entry_price_fifo`, `exit_over_entry`, `sold_above_entry`. This is the field set the sell-to-close (loss-salvage) observation needs.

## What is and is not recorded
* **Recorded:** everything above, strictly before the decision minute, for minutes 344–384 (window − 16 to the window end).
* **Not recorded (not available to a shadow recorder):** the real system's decision time and inputs. The late sale cannot be tied to an internal trigger without them; if the real engine can log its decision time and rule state, that is the single most valuable field to add.
* The recorder does not place orders and does not change the frozen rule.

## Tests (software validation only)
`d1_strategy/test_shadow_state.py` (7 tests): parent logs byte-identical and frozen file/rule hashes unchanged; order actions, FIFO entry price and sold-lot counts; every state field recomputed independently on a synthetic session (straddle, STR15, 5-minute move and orientation, distances, lot counts, premium collected, MTM, PP, GB); first-second-of-minute orders do not leak into the previous minute (**mutation-checked**: removing the fix fails two tests); determinism; spec hash.
A bug found while writing these tests and fixed: an order placed just after the last snapshot of a minute updated the cash before that minute's close was written, while positions were still the old snapshot. The recorder now closes the finished minute before applying a later-minute order and takes positions from its own ledger.

## Hypotheses these fields let you test (not pre-registered here)
1. Side = contrarian (≥ 65%), `fut_move_5m_steps_oriented` and `D_opt`.
2. Straddle decline raises the hazard, `STR15`, evaluated separately for 15:15–15:29 and 15:30–15:39.
3. Sell-to-close of a long within 60 s of a short burst with exit ÷ entry below 1 (`order_state`).
