"""Runnable demo on synthetic data (no market data needed): builds a random-walk spot, prices a strike ladder with Black-Scholes, runs the D-1 strategy
and prints the orders by role plus the end-of-day book. Usage:  python example_synthetic.py"""
import math
import numpy as np
from algo8_d1 import Config, D1Strategy, OptionChain, MINUTES, ROLES


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(spot, strike, tau_years, vol, right):
    return max(_bs_raw(spot, strike, tau_years, vol, right), 0.05)             # listed options never trade below one tick


def _bs_raw(spot, strike, tau_years, vol, right):
    if tau_years <= 0:
        return max(spot - strike, 0.0) if right == "CE" else max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * tau_years) / (vol * math.sqrt(tau_years)); d2 = d1 - vol * math.sqrt(tau_years)
    return spot * norm_cdf(d1) - strike * norm_cdf(d2) if right == "CE" else strike * norm_cdf(-d2) - spot * norm_cdf(-d1)


def make_day(seed=7, spot0=24000.0, vol=0.14, step=50.0):
    rng = np.random.default_rng(seed)
    per_min = vol / math.sqrt(252 * 375)
    path = spot0 * np.exp(np.cumsum(rng.normal(0, per_min, MINUTES * 12))).reshape(MINUTES, 12)   # 12 sub-steps per minute -> OHLC
    o, c = path[:, 0], path[:, -1]; h, l = path.max(axis=1), path.min(axis=1)
    strikes = np.arange(round(spot0 / step) * step - 120 * step, round(spot0 / step) * step + 121 * step, step)
    bars = {(r, f): np.zeros((len(strikes), MINUTES)) for r in ("CE", "PE") for f in ("open", "high", "low", "close")}
    for j in range(MINUTES):
        tau = (1.0 + (MINUTES - j) / MINUTES / 1.0) / 365.0                  # about one to two calendar days to expiry
        for i, k in enumerate(strikes):
            for r in ("CE", "PE"):
                po, pc, ph, pl = (bs_price(s, k, tau, vol * 1.1, r) for s in (o[j], c[j], h[j], l[j]))
                lo_hi = sorted([po, pc, ph, pl]) if r == "CE" else sorted([po, pc, ph, pl])
                p_hi = max(bs_price(h[j], k, tau, vol * 1.1, r), bs_price(l[j], k, tau, vol * 1.1, r), po, pc); p_lo = min(bs_price(h[j], k, tau, vol * 1.1, r), bs_price(l[j], k, tau, vol * 1.1, r), po, pc)
                bars[(r, "open")][i, j], bars[(r, "close")][i, j], bars[(r, "high")][i, j], bars[(r, "low")][i, j] = po, pc, p_hi, p_lo
    return o, h, l, c, OptionChain(strikes, bars)


if __name__ == "__main__":
    o, h, l, c, chain = make_day()
    result = D1Strategy(Config(strike_step=50.0)).run(o, h, l, c, chain)
    df = result.orders_frame()
    print("orders by role (rows, lots):")
    print(df.groupby("role").agg(rows=("lots", "size"), lots=("lots", "sum")).to_string())
    print("\nend-of-day short lots:", sum(result.short_lots.values()), "| long lots:", sum(result.long_lots.values()))
    print("\nrole glossary:"); [print(f"  {k:22s} {v}") for k, v in ROLES.items()]
