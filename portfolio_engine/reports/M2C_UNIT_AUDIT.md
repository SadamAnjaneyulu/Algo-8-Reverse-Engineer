# M2-C reporting-unit audit (executed)

Question: are the displayed realized P&L values (₹2,100,552.00 FIFO, ₹2,096,874.50 LIFO) the same quantity in the same unit across TP-01, M1 and M2-B? No accounting was changed.

| Convention | TP-01 field `realized_gross_pnl_rupees` (raw text) | unit per field name | ×100 → paise (exact decimal) | M1 dump `realized_pnl_paise` | M2-B Σ closing-allocation `realized_pnl` (paise·units) | M2-B in rupees (÷100) | equal in paise? | equal in rupees? |
|---|---|---|---:|---:|---:|---:|---|---|
| FIFO | `2100552.0` | rupees | 210055200.0 | 210055200 | 210055200 | 2100552.0000 | exact | exact |
| LIFO | `2096874.5` | rupees | 209687450.0 | 209687450 | 209687450 | 2096874.5000 | exact | exact |
| AVG | `2100111.63` | rupees | 210011163.00 | 210011162.714088 | 210011162.714088 | 2100111.6271 | within rounding (TP-01 stores 2 decimals) | within 0.005 |

**Independent source field:** `reconstructed_position_ledger.parquet` column `pnl` (price points × units = rupees, per the TP-01 `matching.py` docstring: "price points x units == rupees"), CLOSED pieces:

| Convention | Σ `pnl` (₹) | field-level exact vs `realized_gross_pnl_rupees`? |
|---|---:|---|
| FIFO | 2,100,552.0000 | True |
| LIFO | 2,096,874.5000 | True |
| AVG | 2,100,111.6271 | True |

**Findings.** (1) TP-01's field is in **rupees** (field name and `matching.py` docstring); M1/M2-B store **paise × units** (price paise × quantity units), so rupees = paise ÷ 100. (2) For FIFO and LIFO the integer paise values equal the TP-01 rupee text × 100 **exactly** (₹2,100,552.00 = 210,055,200 paise; ₹2,096,874.50 = 209,687,450 paise); equality holds exactly before and after conversion. (3) AVG is floating point in both; TP-01 stores 2 decimals, so equality is to rounding. (4) The M1 test compared in rupees with abs tol 0.01; the audit here compares exact decimals. (5) The number shown as "₹2,100,552.00" is the **gross** realized P&L of closed quantity only: no charges (none in the data) and **no settlement P&L** for the 37,480 expired-unclosed units.

**Rule for all later reports:** every P&L figure states its unit (`paise·units` in files, `₹` in prose) and says "gross, closed quantity only".
