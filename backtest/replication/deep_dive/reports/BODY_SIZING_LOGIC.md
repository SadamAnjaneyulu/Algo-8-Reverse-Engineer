# Algo 8 — body position sizing on D-1: how many lots, when, and did the lot-size change matter?

*Investigation only (no simulator change). In-sample, observational: 32 cycles with a D-1 log (21 in version V1, 11 in V2). Plan written before the tests: `BODY_SIZING_PLAN.md`. Every number is read from `outputs/bl_size_*` / `bl_summary_size*.json`. Figure: `figures/bl_size_logic.png`.*

## 0. Answers

| Question | Answer | Evidence level |
|---|---|---|
| Did the **lot size change in September**? | **Not in the ledger.** Every order quantity in every month June–October 2026 is a multiple of **65 (NIFTY) / 20 (SENSEX)**; minimum order = 1 lot throughout. Public sources show the last NIFTY revision (75→65) took effect **30 Dec 2025** and was computed from **September 2025** prices (probably the "September" you remember); I found no report of a September 2026 revision (I did not read the exchange circulars myself). | Observed (ledger); external check unverified at source |
| Is it exactly **1 lot of CE+PE every 15 min**? | **No.** Each *wave* is exactly one 1-lot CE + one 1-lot PE pair at the same strike (94.7% of all pairs, D-1 and D0, are 1+1), but there are **0–4 waves per 15-minute block**, at **fixed seconds inside the block**, on a fixed timetable (§3). Over D-1 the timetable sells **33 CE + 33 PE lots (V1)**; observed 33.7 ± 1.3 CE / 33.5 ± 0.8 PE lots per cycle. | Observed |
| What is the **trigger** for more than 1 lot? | **Only the clock.** The extra lots are additional waves at other seconds of the same block; each timetable cell fires in ≥95% of cycles (100% of V1 cells, 90% of V2 cells; median fire rate 100%); both legs are empty in only 7 of 918 cell-cycle observations. The scheduled total shows **no relation to spot, notional per lot, straddle premium or the day's move** (best Holm-adjusted p over all 36 tests = 0.11, for reactive pairs; for the scheduled total itself 1.00). Why that particular timetable (33 pairs per day, those seconds) cannot be observed. | Observed (clock); reason **Unresolved** |
| What changed in September? | **A re-timing, not a re-sizing.** Between D-1 2026-09-09 and 2026-09-16 (both underlyings) 14 cells changed, net **0 lots**: seven waves were re-timed (each addition sits at or after a removal, i.e. consistent with moving waves later, from seconds up to about an hour; the one-to-one matching is not unique); the scheduled total stayed at ≈ 33–34 pairs. Notional per lot fell ~5% (15.4–15.7 → 14.5–15.2 ₹ lakh) but lots did not rise or fall. SENSEX crossed ₹15 lakh per lot at the change (15.00 → 14.89), NIFTY did not (15.50 → 15.19): a lot-value rule would not give a common date. | Observed; cause **Unresolved** |
| **How many lots in total** are added over D-1? | Median **141 lots sold** (both rights) in D-1 by 15:30, **104 net short** after buy-backs: timetable 66, reactive pairs 30, solo 40 (medians per cycle). | Observed |
| **Single-option (solo) sells** in between? | **1,574 lots = 34% of D-1 sold lots, 40 per cycle (median), 69% on the CE side.** 78% are single 1-lot orders; 90% of bursts are ≤ 2 lots; the largest burst is 54 lots. About 35% of solo lots come after 15:00. Their trigger was studied earlier (breakout, own profit, other leg's loss) and is not re-tested here. | Observed |

## 1. Definitions (locked in the plan)
* **Pair** = body `open_short` CE and PE at the same strike within ±3 s. **Solo** = body `open_short` not in a pair. **Block k** = 15 minutes starting 09:16:00 + 900·k s; **offset** = seconds after the block start. **Cell** = (block, offset window) in which a version's modal timetable has ≥ 0.5 pairs per cycle; the cell quantity of a cycle = body CE (PE) lots sold in the window ±3 s, any strike.
* **Versions** V1 / V2: the best single change-point of the D-1 cell-count vectors (below), not assumed.
* D-1 only; D0 is not analysed here.

## 2. The contract unit (Observed)
| month | NIFTY gcd (qty) | SENSEX gcd (qty) | NIFTY min / max order qty | SENSEX min / max order qty |
|---|---|---|---|---|
| 2026-06 | 65 | 20 | 65 / 1755 | 20 / 1000 |
| 2026-07 | 65 | 20 | 65 / 1755 | 20 / 1000 |
| 2026-08 | 65 | 20 | 65 / 1755 | 20 / 1000 |
| 2026-09 | 65 | 20 | 65 / 1755 | 20 / 1000 |
| 2026-10 | 65 | 20 | 65 / 3510 | 20 / 1000 |

The gcd of all order quantities is the contract unit every month, so there is **no change of unit in the ledger**. All order sizes in this study are therefore in lots of 65 / 20 throughout.

## 3. The timetable: waves at fixed seconds inside each 15-minute block
Pairs per block and the in-block offsets of the waves (V1 = until D-1 2026-09-09, V2 = from 2026-09-16; "2×@+0s" means two 1-lot pairs about 0–2 s after the block start):
| block (IST) | V1 pairs | V1 waves (lots @ seconds after block start) | V2 pairs | V2 waves |
|---|---|---|---|---|
| 9:16 | 3 | 3×@+1…+11s | 3 | 2×@+1…+3s, 1×@+7…+10s |
| 9:31 | 2 | 2×@-1…+2s | 2 | 2×@-1…+2s |
| 9:46 | 3 | 1×@-1…+0s, 1×@+30…+32s, 1×@+65…+67s | 3 | 1×@-1…+0s, 1×@+30…+31s, 1×@+65…+66s |
| 10:01 | 1 | 1×@+9…+11s | 1 | 1×@+9…+10s |
| 10:16 | 4 | 3×@-2…+2s, 1×@+57…+59s | 3 | 2×@-2…+0s, 1×@+57…+58s |
| 10:31 | 1 | 1×@+9…+11s | 2 | 1×@+0…+2s, 1×@+9…+10s |
| 10:46 | 2 | 1×@+30…+32s, 1×@+90…+92s | 2 | 1×@+30…+31s, 1×@+90…+91s |
| 11:01 | 2 | 1×@-1…+1s, 1×@+9…+11s | 1 | 1×@+9…+10s |
| 11:16 | 2 | 1×@-2…+0s, 1×@+57…+59s | 2 | 1×@-2…-1s, 1×@+57…+58s |
| 11:31 | 1 | 1×@+9…+11s | 2 | 1×@+0…+2s, 1×@+9…+10s |
| 11:46 | 3 | 1×@-1…+1s, 1×@+30…+32s, 1×@+90…+92s | 2 | 1×@+30…+31s, 1×@+90…+91s |
| 12:01 | 1 | 1×@+9…+11s | 1 | 1×@+9…+10s |
| 12:16 | 0 | — | 0 | — |
| 12:31 | 2 | 1×@-1…+1s, 1×@+9…+12s | 2 | 1×@+0…+2s, 1×@+9…+11s |
| 12:46 | 0 | — | 0 | — |
| 13:01 | 0 | — | 0 | — |
| 13:16 | 2 | 1×@-1…+0s, 1×@+839…+841s | 0 | — |
| 13:31 | 1 | 1×@+839…+841s | 2 | 1×@+0…+2s, 1×@+839…+840s |
| 13:46 | 1 | 1×@+839…+842s | 1 | 1×@+839…+840s |
| 14:01 | 1 | 1×@+839…+840s | 1 | 1×@+839…+840s |
| 14:16 | 1 | 1×@+839…+842s | 1 | 1×@+839…+840s |
| 14:31 | 0 | — | 2 | 1×@+1…+2s, 1×@+840…+841s |

* **It is a timetable, not a ladder with a trend.** The pairs per block are 3, 2, 3, 1, 4 (V1) / 3, 2, 3, 1, 3 (V2), then 1, 2, 2, 2, 1, 3, 1, 0, 2, 0, 0, 2 …; the same fixed seconds recur across blocks (about +0 s, +10 s, +31 s, +58 s, +66 s, +91 s, and +840 s = the last minute before the next block). Blocks 12, 14 and 15 have **no** scheduled waves (12:16, 12:46, 13:01).
* The timetable is **independent of NIFTY vs SENSEX** (same lots, same seconds) and **the same for CE and PE**.
* The cell quantities are constant across cycles (mode share of cell-cycles, median over cells 100%); the misses are {'0': 2, '21': 5} (cell-cycles with both legs empty, by block: the opening block of NIFTY 2026-10-06, and the last cell (14:45) in five NIFTY V2 cycles and no SENSEX cycle).

## 4. V1 → V2 (the September edit)
Change-point scan over D-1 dates (lowest cost = best single split of the cell-count vectors; the early-group / late-group labels are the D-1 dates on each side):
| last D-1 in early group | first D-1 in late group | cycles early | within-group cost |
|---|---|---|---|
| 2026-09-09 | 2026-09-16 | 21 | 85.0 |
| 2026-09-07 | 2026-09-09 | 20 | 90.0 |
| 2026-09-21 | 2026-09-23 | 23 | 91.0 |
| 2026-09-16 | 2026-09-21 | 22 | 92.0 |

The best split is **after D-1 2026-09-09 / before 2026-09-16**, but the cost is only marginally lower than the next candidates (a coarse metric on 32 cycles), so I treat the change window as **2026-09-10 … 09-16** and V1/V2 membership as above (the earlier paired-sell study found the same window).

Cells whose modal quantity differs V1 → V2:
| block (IST) | offset (s after block start) | V1 CE lots in cell | V2 CE lots in cell | change |
|---|---|---|---|---|
| 9:16 | 1 | 3 | 2 | -1 |
| 9:16 | 7 | 0 | 1 | 1 |
| 10:16 | -2 | 3 | 2 | -1 |
| 10:31 | 0 | 0 | 1 | 1 |
| 11:01 | -1 | 1 | 0 | -1 |
| 11:31 | 0 | 0 | 1 | 1 |
| 11:46 | -1 | 1 | 0 | -1 |
| 12:31 | -1 | 1 | 0 | -1 |
| 12:31 | 0 | 0 | 1 | 1 |
| 13:16 | -1 | 1 | 0 | -1 |
| 13:16 | 839 | 1 | 0 | -1 |
| 13:31 | 0 | 0 | 1 | 1 |
| 14:31 | 1 | 0 | 1 | 1 |
| 14:31 | 840 | 0 | 1 | 1 |

Net change 0 lots: seven cells lose a wave and seven gain one, so waves are **re-timed**, not added or removed. Sorted by block, every gain is at or after the corresponding loss (blocks 0→0/4→5/7→9/10→13/13→17/16→21/16→21), which is consistent with moving waves **later**; the one-to-one matching is not unique. Notional per lot around the change:
| D-1 date | underlying | version | ₹ lakh per lot (unit × spot at D-1 open) |
|---|---|---|---|
| 2026-08-31 | NIFTY | V1 | 15.64 |
| 2026-09-07 | NIFTY | V1 | 15.5 |
| 2026-09-09 | SENSEX | V1 | 15.0 |
| 2026-09-16 | SENSEX | V2 | 14.89 |
| 2026-09-21 | NIFTY | V2 | 15.19 |
| 2026-09-23 | SENSEX | V2 | 14.93 |
| 2026-09-28 | NIFTY | V2 | 14.93 |
| 2026-09-30 | SENSEX | V2 | 14.51 |

* **Lot unit: unchanged.** **Total scheduled lots: unchanged** (V1 33.7 / V2 33.5 CE lots per cycle) although notional per lot fell by about 5%. So the schedule is **not sized from lot value**; and a SEBI lot-size revision cannot be the reason because the unit did not move.
* The two underlyings switch together although SENSEX's lot value crossed ₹15 lakh at the change and NIFTY's did not — consistent with a **common dated configuration edit**, not a market-state rule. Cause: **Unresolved**.

## 5. Is the timetable sized or triggered by something other than the clock?
Spearman correlation across cycles (n = 32; permutation p; strongest five of 36 tests):
| target | state_variable | subset | n | spearman | perm_p | Holm-adjusted p (x36 tests) |
|---|---|---|---|---|---|---|
| reactive pair (outside timetable) | straddle_pct_open | all | 32 | -0.503 | 0.003 | 0.108 |
| reactive pair (outside timetable) | straddle_pct_open | NIFTY | 15 | -0.527 | 0.033 | 1.0 |
| sched_total | straddle_pct_open | all | 32 | -0.308 | 0.073 | 1.0 |
| sched_total | straddle_pct_open | SENSEX | 17 | -0.363 | 0.14 | 1.0 |
| solo | notional_per_lot | SENSEX | 17 | 0.359 | 0.143 | 1.0 |

* No test survives Holm correction. The scheduled total, the reactive pairs and the solo lots show no reliable dependence on notional per lot, spot level, the opening straddle premium or the day's spot move. (The nominal p = 0.003 for reactive pairs vs the opening straddle premium becomes 0.11 after Holm.)
* **Decision rules:** "fixed timetable" — met for V1 (all 28 cells ≥ 95%; scheduled total std 1.3 lots on 34) and essentially for V2 (27 of 30 cells ≥ 95%; the exceptions are the two block-0 cells, where one cycle (NIFTY 2026-10-06) has no pair in the opening block (10 of 11), and one 14:31 cell (6 of 11)); "sized from notional/capital" — **not supported** (no |ρ| ≥ 0.4 surviving the null).

## 6. How quantity builds up through D-1
Median over cycles (both rights, body lots):
| by clock time | sold | of which timetable | bought back | net short |
|---|---|---|---|---|
| 10:00 | 20.0 | 16.0 | 0.0 | 18.5 |
| 11:00 | 44.5 | 32.0 | 4.0 | 38.5 |
| 12:00 | 70.5 | 48.0 | 9.0 | 60.5 |
| 13:00 | 87.0 | 54.0 | 18.5 | 66.0 |
| 14:00 | 102.5 | 60.0 | 26.5 | 77.5 |
| 15:00 | 122.5 | 66.0 | 32.5 | 91.0 |
| 15:30 | 141.0 | 66.0 | 37.5 | 103.5 |

* Roughly **16 timetable lots per hour until ~12:00** (about 8 pairs per hour), then ~6 per hour until 15:00 and none after; reactive pairs and solo lots add the rest, and buy-backs remove about a quarter of what is sold by the end of the day. The net short book grows by about **20 lots per hour in the morning** and about **10 per hour afterwards**.
* Context only (not margin): timetable premium = 1.84% of ₹2 crore per cycle (median), all body sells 3.72%; the net short body at 15:30 is **15.5 crore of option notional** (median; 7.7× the stated capital; lots × unit × spot).

## 7. Lots by class and by hour (mean lots per cycle)
| class | lots per cycle (mean) | median | share of D-1 sold lots |
|---|---|---|---|
| scheduled (timetable cell) | 67.0 | 66 | 46% |
| reactive pair (outside timetable) | 29.8 | 30 | 20% |
| solo | 49.2 | 40 | 34% |

| clock hour | scheduled | reactive pair | solo |
|---|---|---|---|
| 9:00 | 15.8 | 0.4 | 4.0 |
| 10:00 | 16.4 | 1.6 | 6.9 |
| 11:00 | 15.5 | 5.6 | 3.4 |
| 12:00 | 6.2 | 5.4 | 6.2 |
| 13:00 | 5.9 | 6.3 | 4.6 |
| 14:00 | 7.2 | 6.7 | 6.7 |
| 15:00 | 0.0 | 3.8 | 17.3 |

* The **timetable dominates before 12:00**; reactive pairs (a CE and a PE at one strike seconds apart, outside the timetable) and solo sells dominate afterwards. **15:00–15:30 is almost entirely solo sells** (17.3 lots per cycle) with no timetable.
* Solo lots per cycle by version: V1 mean 46 (median 46), V2 mean 56 (median 38; one V2 cycle sells 259 solo lots, which pulls the mean up).
* **Replacement?** Of the non-timetable sells, 19% come within 60 s after a body buy-back in the same cycle (shifted-time chance 4%): a link exists, but the lots sold are not matched to the lots bought back (Spearman 0.05 on 448 buy-back minutes). Not a lot-for-lot replacement.

## 8. Evidence register
| Claim | Label | Basis |
|---|---|---|
| Contract unit constant at 65 / 20 in every month Jun–Oct 2026 | **Observed** | gcd and minimum order quantity by month (§2) |
| No September 2026 lot revision found in public sources; last revision effective 30 Dec 2025 | **Not verified at source** | web search only |
| D-1 CE+PE sells are 1-lot waves on a fixed in-block timetable (0–4 per block) | **Observed** | 918 cell-cycle observations, 100%/90% cells ≥95% |
| About 33 pairs (66 lots) scheduled per D-1, same in V1 and V2 | **Observed** | 33.7 / 33.5 CE lots per cycle |
| September edit re-times 7 waves, net 0 lots, between 2026-09-09 and 09-16 | **Observed** | cell diff + change-point scan |
| Scheduled quantity does not depend on notional, premium, spot or the day's move | **Observed** (not supported) | 36 tests (3 targets × 4 state variables × 3 subsets), none after Holm |
| Why this timetable / why the edit | **Unresolved** | clock facts only |
| Solo sells: 34% of D-1 lots, CE-heavy, mostly single lots | **Observed** | 1311 orders |

## 9. Limits and how this could be wrong
* **Pair detection is a ±3 s rule**; two coincident solo sells at one strike would be called a pair. The timetable cells are stable enough (fire ≥ 95%) that this is unlikely to matter for them, but it can inflate "reactive pairs".
* **Timetable cells** are the modal cells chosen with a ≥ 0.5 pairs-per-cycle cut (a threshold chosen after seeing the cluster table); the V1→V2 diff and totals depend on it only mildly (cells are all ~1.0).
* **Version membership** (V1/V2) comes from a coarse change-point; a cycle could be misassigned near 09-09 / 09-16.
* **Why** a timetable has these seconds and totals cannot be recovered from fills; the instructions behind it (config / code release) are not in the data. A date-based edit in mid-September coincides with nothing I could identify in the ledger.
* **External check:** the "no September revision" point rests on a web search, not on NSE/BSE circulars; the ledger itself shows no unit change either way.
* In-sample; D-1 only; the 5 cycles without D-1/D0 logs are excluded; reconstructed behaviour, not source logic.

## 9b. Files
`src/bl_size_build.py` (unit, pairs, solo, change-point) → `bl_size_tests.py` (cells, totals, V1/V2 diff, misses) → `bl_size_tests2.py` (classes, build-up, solo, replacement, state, notional) → `bl_size_fig.py` → `make_size_report.py`. Outputs `outputs/bl_size_*`, `bl_summary_size*.json`. Tests `tests/test_bl.py` (`test_size_*`).
