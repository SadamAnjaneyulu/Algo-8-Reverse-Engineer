"""Verified cost schedule for the pre-paper-trading battery (reports/PREPAPER_PLAN.md). Rates and sources in the plan; NSE exchange charge 0.0495% before 1 Oct 2024 (the earlier code used 0.035% throughout)."""
import datetime as dt
REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}; BROKER = 20.0; GST = 0.18; SEBI = 1e-6; STAMP_BUY = 3e-5; D_TXN = dt.date(2024, 10, 1)
def stt_sell(d): return 0.000625 if d < dt.date(2024, 10, 1) else (0.001 if d < dt.date(2026, 4, 1) else 0.0015)
def txn(und, d, nse_late=0.0003503): return (0.000495 if d < D_TXN else nse_late) if und == 'NIFTY' else 0.000325
def order_costs(und, d, side, value, mult=1.0, nse_late=0.0003503):
    t = txn(und, d, nse_late) * value; s = SEBI * value; g = GST * (BROKER + t + s); st = STAMP_BUY * value if side > 0 else 0.0; stt = stt_sell(d) * value if side < 0 else 0.0
    return mult * (BROKER + t + s + g + st + stt)
def account(f, und, d1, d0, unit, slip_mult=1.0, cost_mult=1.0, nse_late=0.0003503):
    """same structure as bl_bt3_sim.account (slippage max(0.10, 0.5% of price) per side x slip_mult) with the verified schedule"""
    gross = net_px = costs = slip = 0.0; orders = 0; dd = {0: dt.date.fromisoformat(d1), 1: dt.date.fromisoformat(d0)}
    for q in f.itertuples():
        n_o = max(q.n_orders, 1); lots_per = q.lots / n_o; s = max(0.10 * slip_mult, 0.005 * slip_mult * q.price); e = q.price + q.side * s
        gross += -q.side * q.price * q.lots * unit; net_px += -q.side * e * q.lots * unit; slip += s * q.lots * unit; costs += n_o * order_costs(und, dd[q.day], q.side, e * lots_per * unit, cost_mult, nse_late); orders += n_o
    return dict(gross=gross, net=net_px - costs, costs=costs, slippage=slip, orders=orders)
