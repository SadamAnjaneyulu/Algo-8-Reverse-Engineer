# Algo 8 Behaviour Gap Analysis

**Result:** our earlier 4-leg "observed structure" backtest reproduced about **1/300th of the real order flow** and its per-cycle P&L is **uncorrelated (ρ = −0.21)** with the real algo's. Rebuilding the decoded **D-1 ladder** (R1) restores correlation (ρ = 0.35) and the right sign on stop vs non-stop cycles, but captures only ~17 % of live gross P&L (₹4.4 L of ₹26.2 L). The largest missing component is the **expiry-day (D0) short book** (≈ 45 % of body+wing P&L), followed by lots **carried to settlement** (≈ 21 %) and D-1 **off-schedule sales**. Code executed (`live_pnl.py`, `replay.py`, `decision_agreement.py`, `pnl_streams.py`, `d0_sales_classes.py`); numbers are on the 35 cycles for which a real ledger exists (23 Jun–22 Oct 2026). Caveat: that is the same window the rules were decoded from, so agreement here is **fit, not validation**.

## 1. Scale of behaviour (35 live cycles)

| Metric | Real Algo 8 | Earlier 4-leg baseline | R1 ladder | R2 (R1 + D0 median ladder) |
|---|---:|---:|---:|---:|
| Orders per cycle (median) | **1,201** | 4 | 208 | 628 |
| D-1 body lots sold per cycle (mean) | 135 | 6 | 52 | 52 |
| Net short body lots carried overnight (mean) | **89.5** | 6 | 36.9 | 36.9 |
| D0 body lots sold (total) | **12,675** | 0 | 0 | 3,506 |
| Gross P&L, 35 cycles | **₹26.2 L** | ₹1.7 L | ₹4.4 L | ₹4.3 L |
| Per-cycle correlation with live gross P&L | — | **−0.21** | 0.35 | 0.40 |
| Mean gross on the 12 live stop cycles / 23 others | −₹1.56 L / +₹1.95 L | +₹8.3k / +₹3.0k | −₹49k / +₹45k | −₹55k / +₹47k |
| Live stop cycles detected by a −₹1.44 L cycle stop | 12 | — | 1 (FN 11, FP 0) | 4 (FN 8, FP 1) |

The earlier baseline had the *wrong sign* on stop cycles; R1/R2 have the right sign at 1/3–1/4 of the magnitude. An earlier decoded clone (`ALP-03`) reported ρ = 0.48 and ₹7.7 L vs ₹15.5 L on 30 cycles; our R1/R2 land in the same range (₹4.4 L vs ₹26.2 L here; independent corroboration that the ladder alone explains roughly 15–30 % of P&L).

## 2. Where the live money is made (gross, ₹, body+wing modules; FIFO by lot; `pnl_streams_live_vs_sim.csv`)

| Stream | Live | R1 | Share of live total |
|---|---:|---:|---:|
| Body: opened D-1, closed D-1 | −23.1 L | −18.6 L | |
| Body: opened D-1, closed D0 (carry) | +33.7 L | +24.4 L | |
| **Body: opened D-1, held to settlement** | **+5.9 L** | 0 | 24 % |
| **Body: opened D0, closed D0** | **+12.4 L** | 0 | 49 % |
| **Body: opened D0, held to settlement** | +1.8 L | 0 | 7 % |
| Wings (all streams) | −5.6 L | −1.4 L | −22 % |
| **Total body+wing** | **₹25.2 L** | **₹4.4 L** | 100 % |

(Body+wing excludes the lump hedge/stop/manual modules (₹1.6 L) and 425 fills in the 15:30–15:39 extended session, which explains why the FIFO total ₹25.2 L differs from the cash-based ₹26.2 L; all 425 dropped fills are 15:30–15:39.)

**Reading:** R1's D-1 carry stream reproduces 72 % of the live carry (₹24.4 L vs ₹33.7 L) — the ladder, wings, leg stop and cycle stop capture the D-1 machinery reasonably. What R1 lacks is entirely **expiry-day short selling** and the **decision to hold some lots to settlement**.

## 3. Component-by-component gap (what differs and how much it matters)

| Component | Real behaviour (evidence) | Our earlier baseline | R1/R2 | Matters for P&L? |
|---|---|---|---|---|
| **Entry timing** | 17 D-1 slots; modal lots 3,2,3,1,3,1,2,2,1,1,3,1,0,2,0,0,1 per leg; 66–70 % of slot-legs equal modal in the first 3 min, 88 % at 09:16 (`ladder_d1_agreement.csv`) | single 09:16 entry | ladder implemented | Large: 4 → 52 lots/side |
| Simultaneous 4 legs | CE and PE equal in 80 % of slot-legs (3-min window); wing bought within seconds | yes | yes | — |
| Strike | nearest to previous-minute index close: **50 % exact, 89 % within ±1 step** on D-1; D0 43 % / 79 % (SENSEX D0 33 % exact) | K from 09:15 close | nearest rule | Small; unexplained ±1-step residual (STK-03/04: direction-biased) |
| Quantity | 1 lot per order, 17-slot ladder + off-ladder; 135 body lots sold per D-1 vs 52 on-ladder | 3 lots/leg | ladder only | **Large**: off-schedule D-1 sales earn ₹469/lot vs scheduled ₹323/lot |
| Wing choice | wing price ≈ **2.44 %** of body price (median; IQR 2.2–2.6 %, n = 2,884; ratio flat across slots) and 1 wing lot per body lot | fixed ±2,000/4,000 pts | price-ratio rule | Wing strike matches exactly in only 45–53 % |
| Position management D-1 | buy-backs 1,577 lots vs 527 explained by a 1.6× leg stop; only **49 %** of D-1 reductions occur above 1.2× the cheapest entry (below) | none | leg stop | **Medium** |
| Position management D0 | 12.5 k lots bought back, 12.7 k sold; **60 % of D0 sales are replacements** (re-sold within a minute of a same-side buy-back) | none | leg stop + flatten | **Large** |
| Hold to settlement | 810 body lots (D-1 opened) + 2,681 (D0 opened) not flattened | flatten/settle | flatten 15:14 | Medium (₹7.7 L gross) |
| Risk: cycle stop | 12 of 35 cycles stopped at ≈ −₹1.4 L cumulative LTP MTM | none | −₹1.44 L rule | R1 fires on 1 of 12: the **book is 2.4× larger live**, so our smaller book rarely reaches −₹1.44 L |
| Risk: 4 % carry / 1 % expiry stops (`Info.txt`) | not reproduced (RSK-02/03/07/08) | — | — | Unknown |
| Lump hedge `v_` | overnight single-strike hedge, size unpredictable | — | — | −₹4 L (`ALP-01`) |
| Costs | ≈ 37 k orders; ₹20/order ≈ ₹7.5 L | ₹20 × 4 | modelled | ≈ 40 % of gross live |

## 4. D0 sales: what kind of sale earns the money (association only; `d0_sales_by_class.csv`)

| Opened | Class | Lots | Gross P&L | ₹ per lot |
|---|---|---:|---:|---:|
| D-1 | Scheduled (first 3 min of a slot) | 1,888 | ₹6.1 L | 323 |
| D-1 | **Other (off-slot, not a replacement)** | 2,151 | **₹10.1 L** | 469 |
| D-1 | Replacement (≤ 1 min after same-side buy-back) | 548 | ₹0.5 L | 86 |
| D0 | Scheduled | 1,998 | ₹0.7 L | 35 |
| D0 | **Other** | 2,903 | **₹8.5 L** | 294 |
| D0 | **Replacement** | 6,917 | ₹5.4 L | 78 |

The naive D0 ladder in R2 (scheduled-type sales) earns ~₹35/lot live, so adding it does little (R2 live-window P&L ≈ R1). The money is in the **off-schedule ("other")** sales on both days and in replacements. Their trigger is **not recovered** (ENT-04: a gated per-leg timer predicts *when* with AUC 0.887 but not *why*). **This is the single most important missing rule.**

## 5. Ranking of missing rules by P&L at stake (live gross, body+wing)

| Rank | Missing / weak rule | P&L at stake | Evidence quality |
|---:|---|---:|---|
| 1 | D0 short sales (off-schedule + Clock-B replacements) | ≈ ₹11.3 L net of wings (45 %) | Behaviour observed; trigger/size **unknown** |
| 2 | D-1 off-schedule ("other") sales | ≈ ₹10.1 L of opening P&L; part of R1's shortfall in carry (₹9.3 L) | Timing partly predictable, trigger unknown |
| 3 | Which lots are held to settlement instead of flattened | ₹5.4 L | Unknown (EXT-08: residuals exist) |
| 4 | Stop behaviour (cycle stop, post-stop machinery, 4 %/1 % rules) | 12 stop cycles = −₹18.7 L | Cycle stop strongly supported; scale mismatch |
| 5 | Wing selection details | wings −₹5.6 L total | Strongly supported rule, exact strike 45–53 % |
| 6 | Lump hedge | −₹4 L | Unknown |

## 6. What the gap analysis cannot say
* Why the real algo sizes its D0 book as it does (capital, margin, risk budget): `SIZ-05` — no sizing formula in terms of capital is recovered.
* Whether live and simulated fills are comparable: live fills are marketable limits at ±15 % of LTP with actual book prices; our simulated slippage (0.5 %) is an assumption.
* Anything about 2023–2025: no live ledger exists there.
