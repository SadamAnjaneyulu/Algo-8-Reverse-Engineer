# D0 P&L Attribution (Phase H)

**Result:** by stream, the actual algorithm's D0 outcome is made by **carried lots that are bought back during the day** (discovery +₹27.5 L; holdout +₹2.6 L, gross, entry→exit including the D-1 leg of the P&L), not by D0-opened sales (discovery +₹1.4 L; holdout +₹4.2 L). The simulation (V1) holds the carried book to the 15:14 flatten (+₹42.8 L discovery) and its price-stop buy-backs lose money (−₹4.3 L), so **the missing intraday buy-back decision process is the largest unreproduced P&L stream**. This does **not** reproduce the previous phase's ranking ("D0 short sales ≈ 45 % of P&L"); likely reasons (not isolated one by one): that pass included the three cycles without a known carry-in book, where buy-backs of unknown carried lots opened spurious long lots, and used minute-level class definitions. **The attribution itself depends on the lot-ownership convention** (FIFO vs LIFO below) and must be read as indicative. Behavioural agreement, not P&L, remains the priority. Code executed: `pnl_attribution.py`, `build_lineage.py`, `build_lineage_lifo.py`; tables `pnl_attribution.csv`, `pnl_attribution_fifo_vs_lifo.csv`.

## 1. Method
Lots that **close on D0 or at settlement** are attributed (lots closed on D-1 are common history for actual and simulation). Gross P&L (reference prices, no slippage/costs) = entry→exit in rupees, FIFO per role/contract. Carried lots keep their D-1 entry price (so their P&L includes the overnight and D-1 portions). For the simulation the same FIFO is run over the simulated orders starting from the actual book; lump/stop-module/manual lots are passive and reported as "not simulated". Cycles with a known carry-in book only (22 discovery, 8 holdout). Holdout numbers come from the frozen simulator run (v1.1).

## 2. Streams (₹ lakh)

| Stream | Disc. actual | Disc. sim V1 | Disc. sim NULL | Hold. actual | Hold. sim V1 | Hold. sim NULL |
|---|---:|---:|---:|---:|---:|---:|
| D0-opened body: scheduled sales | 0.36 | −1.43 | 0 | −0.12 | +1.98 | 0 |
| D0-opened body: off-schedule sales | −2.04 | 0 | 0 | +3.46 | 0 | 0 |
| D0-opened body: replacement sales | +3.12 | +0.23 | 0 | +0.84 | +0.01 | 0 |
| D0-opened body: other classes | −0.09 | 0 | 0 | −0.03 | 0 | 0 |
| **Carried from D-1: bought back (stop-like / Clock-B / other)** | **+27.53** | −4.29 | 0 | +2.61 | −5.21 | 0 |
| Carried: final liquidation (≥ 15:10) | +2.84 | **+42.75** | +47.89 | +1.22 | +11.54 | +9.33 |
| Carried: held to settlement | +0.10 | 0 | 0 | +0.87 | 0 | 0 |
| Carried: other closes (stop module etc.) | +2.40 | −1.84 | −7.08 | +2.93 | −0.18 | −3.58 |
| Wings | −3.70 | −2.85 | −2.42 | −1.70 | −1.40 | −1.29 |
| Passive / not simulated (lump, stop-module, manual) | −2.93 | 0 | 0 | −0.48 | 0 | 0 |
| **Total (D0-closing lots)** | **27.6** | 32.6 | 38.4 | 9.6 | 6.8 | 4.5 |

(The three "Carried" buy-back/final streams are labels of the *closing* order; the actual algorithm monetises the carried book mostly through intraday buy-backs while the simulation does it at the flatten. Totals are close by coincidence of offsetting streams; they are not evidence of replication.)

## 3. Lot-ownership sensitivity (D0-opened vs carried, D0-closing body lots)

| Convention | Split | D0-opened P&L | of which scheduled / off-schedule / replacement | Carried P&L |
|---|---|---:|---|---:|
| FIFO | discovery | +₹1.35 L | +0.36 / −2.04 / +3.12 | +₹32.9 L |
| LIFO | discovery | **−₹3.68 L** | −3.34 / −3.82 / +3.56 | +₹39.8 L |
| FIFO | holdout | +₹4.16 L | −0.12 / +3.46 / +0.84 | +₹7.6 L |
| LIFO | holdout | +₹4.31 L | +0.32 / +3.60 / +0.42 | +₹8.4 L |

The sign of the discovery D0-opened P&L flips with the convention: allocation ownership is **not identifiable** (ALC-01/02), so per-class profitability claims (and any "off-schedule sales earn more") are not supported.

## 4. Which missing rule matters most for P&L?
1. **Intraday buy-back decisions on carried lots** (largest; +27.5 L actual discovery vs −4.3 L simulated, holdout +2.6 vs −5.2). This is where the actual algorithm earns or avoids losses; trigger unknown.
2. Stop-module behaviour (holdout: 1,196 stop lots; "other closes" and passive streams).
3. Replacement sales (+3.1 L discovery) and off-schedule sales (±) — small and convention-dependent.
4. Hedge handling (−3.7 L actual vs −2.9 L simulated): the simulator's wing rules are broadly right in cost.

Per the brief, no rule was optimised to P&L; this table only prioritises *which behaviour* to investigate next.
