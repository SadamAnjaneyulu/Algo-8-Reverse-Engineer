# The sell-to-close orders are the wing controller, not a restructuring decision

*Plan: [`LATE_SALE_SEQUENCE_PLAN.md`](LATE_SALE_SEQUENCE_PLAN.md), written before the run. Exploratory, development cycles only. Frozen rule, score and hashes untouched.*

## Result first
The sell-to-close orders (all sold below entry, beside the short bursts) are **mechanical**: the engine's wing controller trimming the long wings **about 4 seconds after a stop-out**, so that long wing lots equal short lots. They are **not** an independent late-sale decision, and they say nothing about what triggers the late *short* sales.

| Evidence | Result |
|---|---|
| **W2: 2–8 s after a body order** | **10 of 13** clusters (median lag **4 s**) vs 2% by chance (p = 0.0002, BH 0.0002); the engine README says "about 4 seconds after body orders" |
| **W3: follows a same-right cover within 60 s** | **11 of 13** vs 6% by chance (p = 0.0002) |
| **Who comes first** | the short burst or cover starts first in **10 of 12** cases with a nearby burst; the sell-to-close follows (median gap 11 s) |
| **W1 as pre-registered: balance restored** | 3 of 13 vs 0.2% (p = 0.0002), but **below my size rule** (excess 0.23 < 0.30). The pre-set definition was flawed (see below) |
| **Post-hoc diagnostic (not pre-registered): wings vs shorts, lump excluded** | After **every** one of the 18 clusters (13 post, 5 pre) the long wing lots equal the short lots **exactly**. Before, there was an excess of 1–21 lots in 16 of 18 (the other two are body-module longs). At random late-window times the wings equal the shorts **99.2%** of the time and the excess is ≥ 1 lot only 0.5% of the time |

**Reading:** a stop-out (cover) cuts the short lots on a right; about 4 s later the controller sells exactly the excess wing lots, outermost first (the sold wing is the outermost held long 66% of the time on average across orders). Both the stop-out and the contrarian short sale on the other side follow from the same price move, which is why the sell-to-close sits beside the short bursts and is usually on the **opposite** type (a long put sold next to short calls sold).

## What changes in the earlier findings
* **Revised:** the "restructuring step that sells decayed longs and adds shorts" reading in `LATE_SALE_FOCUSED.md` is **superseded**. The co-timing in PB2 is real (24 of 27), but it is a shared cause (the price move), not one decision.
* **Sold below entry:** expected, because far-out-of-the-money wings bought earlier decay.
* **Unchanged:** the late **short** sales. Side = contrarian (78% / 85%), no scheduled timer, minute-level clock bunching, no state variable confirmed. The trigger for *when* a late short is sold is still unresolved. Removing the sell-to-close orders (they are controller output, not trigger-driven) makes the question cleaner: only the 148 open-short orders are left to explain.

## Pre-registered tests (BH 10%) and one flawed definition
| ID | Result | BH ≤ 10% | Size rule met |
|---|---|---|---|
| W1 | 3 of 13 vs null mean 0.02 | yes | **no** (excess 0.23 < 0.30) |
| W2 | 10 of 13 vs 0.3 | yes | yes (+0.75) |
| W3 | 11 of 13 vs 0.8 | yes | yes (+0.78) |

W1 failed its size rule for a definitional reason I should have caught: the pre-set long-lot count L **included the overnight lump** (`v_` longs, 14–87 lots on some days), which the wing controller does not manage, and the "excess" tolerance (max(1, 10% of S)) hid the typical 1–3-lot excess. Under the pre-registered rule the verdict is therefore **"W2 and W3 supported, W1 not confirmed"**. The diagnostic that excludes the lump is **post-hoc**, so it supports the reading but does not count as a pre-registered confirmation. It should be confirmed forward with the recorder's `order_state` (`action`, `ledger_net_lots_before`) and ledger, which log exactly these lots.

## Timelines (examples)
`outputs/trig5/timelines.csv` holds every order within ±2 minutes of each sell-to-close cluster. SENSEX 5 Aug: CE shorts are covered at 15:14:05–15:14:18, and `h_` CE wings (80500) are sold at 15:14:02, 15:14:11, 15:14:22 and 15:15:20, each about 4–5 s after a cover; the PE shorts sold at 15:15:14–15:15:21 are the contrarian ladder on the other side.

## Limits
* 13 post-auction clusters in 7 cycles (5 pre-auction clusters): low power, and "supported" here means a very strong association with a documented mechanism, not a proof.
* The two body-module (`num`) sell-to-close clusters (NIFTY 3 Aug, SENSEX 9 Sep) are a different process (body longs closed at 15:29 beside short bursts) and are **not** explained by the wing controller.
* The wing-controller rule is taken from the engine README; I did not re-derive its strike choice ("outermost first" holds for 66% of orders on average, so not always).
* Same development cycles as before.

## Where the late short sale stands
Side: the option that just became cheaper (replicated). Not: risk control, premium target, lump-coupled, general pair, replacement, profit booking, re-centring, or a restructuring step. The sell-to-close orders are the wing controller after stop-outs. **Trigger for the late short: unresolved.** The forward recorder's `order_state` and `state_minute` records are the way to narrow it further.

Files: `src/bl_trig5_sequence.py`, `tests/test_sequence.py`, outputs in `outputs/trig5/` (`clusters.csv`, `timelines.csv`, `sequence.json`, `family.csv`, `wing_diag_excluding_lump.csv`, `wing_diag_summary.json`).
