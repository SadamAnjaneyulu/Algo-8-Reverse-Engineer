# D0 Replay Methodology (Phase F)

**Result:** a separate D0 replay module (`d0_sim.py`, Python reference; **not** in the production engine) processes each D0 minute by minute from the **actual overnight book**, uses only information available at each timestamp, records every decision with its reason, and tracks cash and P&L. A perturbation test, unit tests and an independent review support temporal correctness. Intra-minute order is not identifiable; a one-minute-latency alternative shows that behavioural agreement is insensitive to it while P&L is not. Code executed: `d0_sim.py`, `run_replay.py`, `latency_sensitivity.py`; tests in `backtest/tests/test_d0_reconstruction.py`.

## 1. State and time conventions
* **Initial state:** the actual D-1 order flow of the cycle is replayed (`start_book`) into body shorts (FIFO lots with entry prices), wings, and *passive* lots (lump `v_`, stop-module `s_`, manual `m_`, any body longs). Cash = actual cash at fill prices. A test verifies the simulated start book equals the ledger's net short body lots in all 30 cycles (after addendum 1).
* **Index j** = minutes since 09:15; **a decision at minute j uses prices up to the close of minute j−1** (at j = 0, the last D-1 bar; at j = 0 spot = the last D-1 spot); **fills at the open of minute j** (the fallback for an untraded minute is the previous close). The same convention is enforced for stops, marks, wing selection and replacements (the replacement scheduled by minute j executes at j+1 using data up to j).
* **Valuation:** cycle MTM = cash + marks of all open lots (including passive lots, valued at the previous close; contracts missing from the downloaded chain use the lot's last order price — documented limitation, flagged `missing_contract` in the order log). Remaining lots are cash-settled at the official close (Yahoo) after 15:29.
* **Order within a minute (the repo cannot establish the real one):** pending replacements → stops → price stop → final flatten → Clock-B tick → scheduled slot. Alternative sequencing was evaluated as a **+1-minute latency** variant (fills at the next open): all event-agreement metrics unchanged to three decimals (they are bucketed at 2 minutes); the holdout D0 P&L increment changes from +₹0.08 L to −₹1.26 L and the discovery one from ₹6.1 L to ₹8.3 L. **P&L conclusions are fragile to intra-minute assumptions; agreement conclusions are not.** Intra-second ordering of same-minute orders (DAT-14: fills are whole seconds) is unrecoverable.

## 2. Components (frozen rule set D0-v1; parameters in `rules_d0_v1.json`)
| Component | Logic | Evidence status |
|---|---|---|
| S1 scheduled sales | grid-A minutes (mm%15 = 1, j ≥ 1) while the short body book is non-empty: per right, `ladder[slot]` lots (discovery medians), 1 lot per order at the strike nearest the previous-minute spot; wings 1 per lot at the wing price ratio (2.75 %) | timing Strongly supported; quantity Hypothesis |
| S2 Clock-B | mm%15 = 14, from 09:29: if total short lots ≥ 134, buy back 1 lot of the largest short contract (ties: nearest ATM), release 1 wing, sell 1 lot next minute at ATM | Hypothesis |
| S3 price stop (variant V1) | prior-close price ≥ 1.6 × the lot's own entry → buy back that lot and release a wing | Hypothesis (weak on D0) |
| S4 final flatten | at 15:14 (j = 359) buy back all body shorts, sell all wings, no later entries | Strongly supported (timing) |
| Cycle stop | LTP MTM ≤ −₹1.44 L → liquidate body and wings, no further entries | Strongly supported |
| Passive | lump/stop-module/manual lots held to settlement | not simulated |

## 3. Temporal-correctness controls
1. **Perturbation test** (`test_sim_start_book_matches_ledger_and_no_lookahead_at_d0_open`): multiplying D0 minute-0 option closes and adding 1,000 to the 09:15 spot does not change the orders placed at j = 0 (this is the check that exposed the previous phase's D0-open look-ahead).
2. `test_sim_flatten_and_stop_semantics`: all flatten orders at j = 359; after a stop there are no entries.
3. The **independent review** (Gate 6) re-examined the module; findings are in `ENGINE_INTEGRATION_REPORT.md` §3.
4. The simulator never reads the actual D0 orders; actual D0 data enter only in `compare_events.py`.

## 4. Variants and controls
NULL (flatten + cycle stop), V0 (S1 + S2), V1 (V0 + S3). The NULL control already tracks the actual D0 P&L increment with correlation 0.67 (discovery) and reproduces 6 of 7 live stop cycles, because the **actual carried book** and the cycle stop dominate the outcome. **Aggregate agreement with the actual D0 outcome is therefore a weak discriminator of decision logic**; event-level metrics are the primary evidence.

## 5. Known limitations
**Found by the independent review (not fixed, v2):** passive lump/stop-module lots are held to settlement even after a stop (inflates simulated P&L in stopped cycles); replacement sales get no wings (`floor(1×0.47)=0`); the hedge-add comparison is therefore a lower bound; matching uses fixed 2-/10-minute bins (parity-dependent). See `INDEPENDENT_REVIEW_D0.md`.
Minute resolution; fills at bar opens with no slippage in the behavioural comparison; chain gaps for far wings; no lump/stop-module behaviour; one-lot orders (the live algorithm sends one-lot child orders, so quantities are comparable); the actual carry-in book is known only for 30 cycles.
