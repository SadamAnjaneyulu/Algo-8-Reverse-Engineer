"""Date-aware transaction-cost model (replaces the flat-rate legacy model in bt/account.py for the v1 backtest). Every rate is listed in COST_MODEL_VERIFICATION.md with its source and status.
STATUS: rates cross-checked against BROKER DISCLOSURES and press reports (secondary sources); the exchange circulars themselves were NOT retrieved. Brokerage is broker-specific and Algo 8's terms are unknown (Rs 20/order is an assumption)."""
from datetime import date
BROKERAGE = 20.0; GST = 0.18; SEBI = 1e-6; STAMP_BUY = 3e-5                         # SEBI Rs 10/crore; stamp 0.003 % on buy premium
CUT_TXN = date(2024, 10, 1); CUT_STT1 = date(2024, 10, 1); CUT_STT2 = date(2026, 4, 1)


def _d(d): return date.fromisoformat(d) if isinstance(d, str) else d


def txn_rate(und, d):
    d = _d(d)
    if und == 'NIFTY': return 0.000495 if d < CUT_TXN else 0.0003503          # NSE index options: 0.0495 % until 2024-09-30; 0.03503 % from 2024-10-01 (Zerodha current page shows 0.03553 %: sensitivity)
    return 0.000495 if d < CUT_TXN else 0.000325                               # BSE Sensex options: 0.0495 % until 2024-09-30; 0.0325 % from 2024-10-01


def stt_sell(d):
    d = _d(d); return 0.000625 if d < CUT_STT1 else (0.001 if d < CUT_STT2 else 0.0015)


def order_costs(und, day, side, value, mult=1.0):
    b = BROKERAGE; t = txn_rate(und, day) * value; s = SEBI * value; g = GST * (b + t + s); stamp = STAMP_BUY * value if side > 0 else 0.0; stt = stt_sell(day) * value if side < 0 else 0.0
    return mult * (b + t + s + g + stamp + stt)
