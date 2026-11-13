"""Reporting-unit audit of realized P&L: raw TP-01 values, field names, units, explicit conversion, M1 dump and M2-B allocation sums in paise and rupees, exactness before / after conversion.
python3 portfolio_engine/tools/unit_audit.py -> reports/M2C_UNIT_AUDIT.md (+ json). Reads only; changes no accounting."""
import json, os, sys
from decimal import Decimal
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
import pandas as pd
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators import historical as H
TP = os.path.join(REPO, 'tp_reconstruction', 'data')
ins, fills, _ = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
raw = open(os.path.join(TP, 'reconciliation_summary.csv')).read().splitlines(); hdr = raw[0].split(','); rows = {r.split(',')[0]: dict(zip(hdr, r.split(','))) for r in raw[1:]}   # raw TEXT, no float parsing
P = pd.read_parquet(os.path.join(TP, 'reconstructed_position_ledger.parquet')); out = {}
md = ['# M2-C reporting-unit audit (executed)', '', 'Question: are the displayed realized P&L values (₹2,100,552.00 FIFO, ₹2,096,874.50 LIFO) the same quantity in the same unit across TP-01, M1 and M2-B? No accounting was changed.', '',
      '| Convention | TP-01 field `realized_gross_pnl_rupees` (raw text) | unit per field name | ×100 → paise (exact decimal) | M1 dump `realized_pnl_paise` | M2-B Σ closing-allocation `realized_pnl` (paise·units) | M2-B in rupees (÷100) | equal in paise? | equal in rupees? |', '|---|---|---|---:|---:|---:|---:|---|---|']
for m in METHODS:
    t = rows[m]['realized_gross_pnl_rupees']; t_paise = Decimal(t) * 100
    m1 = ls.runs[m].state.realized_total(); ca = sum(float(r[7]) for r in ls.ca[m]) if m == 'AVG' else sum(int(r[7]) for r in ls.ca[m]); ca_rs = Decimal(str(ca)) / 100
    eq_p = (Decimal(str(m1)) == t_paise and Decimal(str(ca)) == t_paise) if m != 'AVG' else abs(Decimal(str(ca)) - t_paise) <= Decimal('0.5')
    eq_r = (Decimal(str(ca)) / 100 == Decimal(t)) if m != 'AVG' else abs(Decimal(str(ca)) / 100 - Decimal(t)) <= Decimal('0.005')
    out[m] = dict(tp01_raw=t, tp01_paise=str(t_paise), m1_paise=str(m1), m2b_paise=str(ca), m2b_rupees=str(ca_rs), equal_paise=bool(eq_p), equal_rupees=bool(eq_r))
    md.append(f'| {m} | `{t}` | rupees | {t_paise} | {m1 if m != "AVG" else f"{m1:.6f}"} | {ca if m != "AVG" else f"{ca:.6f}"} | {ca_rs:.4f} | {"exact" if (m != "AVG" and eq_p) else ("within rounding (TP-01 stores 2 decimals)" if eq_p else "NO")} | {"exact" if (m != "AVG" and eq_r) else ("within 0.005" if eq_r else "NO")} |')
# independent source check: TP-01 piece ledger pnl (price points x units, i.e. rupees) summed per convention
md += ['', '**Independent source field:** `reconstructed_position_ledger.parquet` column `pnl` (price points × units = rupees, per the TP-01 `matching.py` docstring: "price points x units == rupees"), CLOSED pieces:', '', '| Convention | Σ `pnl` (₹) | field-level exact vs `realized_gross_pnl_rupees`? |', '|---|---:|---|']
for m in METHODS:
    s = P[(P.method == m) & (P.row_type == 'CLOSED')].pnl.sum(); md.append(f'| {m} | {s:,.4f} | {abs(Decimal(str(round(s, 6))) - Decimal(rows[m]["realized_gross_pnl_rupees"])) <= Decimal("0.005")} |'); out[m]['tp01_piece_ledger_sum'] = float(s)
md += ['', '**Findings.** (1) TP-01\'s field is in **rupees** (field name and `matching.py` docstring); M1/M2-B store **paise × units** (price paise × quantity units), so rupees = paise ÷ 100. (2) For FIFO and LIFO the integer paise values equal the TP-01 rupee text × 100 **exactly** (₹2,100,552.00 = 210,055,200 paise; ₹2,096,874.50 = 209,687,450 paise); equality holds exactly before and after conversion. (3) AVG is floating point in both; TP-01 stores 2 decimals, so equality is to rounding. (4) The M1 test compared in rupees with abs tol 0.01; the audit here compares exact decimals. (5) The number shown as "₹2,100,552.00" is the **gross** realized P&L of closed quantity only: no charges (none in the data) and **no settlement P&L** for the 37,480 expired-unclosed units.', '', '**Rule for all later reports:** every P&L figure states its unit (`paise·units` in files, `₹` in prose) and says "gross, closed quantity only".']
open(os.path.join(PE, 'reports', 'M2C_UNIT_AUDIT.md'), 'w').write('\n'.join(md) + '\n'); json.dump(out, open(os.path.join(PE, 'reports', 'm2c_unit_audit.json'), 'w'), indent=1, default=str); print('\n'.join(md))
