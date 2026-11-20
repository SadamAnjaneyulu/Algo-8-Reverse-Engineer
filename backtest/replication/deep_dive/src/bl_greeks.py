"""Black-Scholes helpers shared by the solo-sell variable search."""
import numpy as np
from scipy.special import ndtr
R_ = 0.065; CAP = 2e7
def bs_price(S, K, T, sig, cp):
    d1 = (np.log(S / K) + (R_ + .5 * sig ** 2) * T) / (sig * np.sqrt(T)); d2 = d1 - sig * np.sqrt(T); disc = np.exp(-R_ * T)
    return S * ndtr(d1) - K * disc * ndtr(d2) if cp == 'CE' else K * disc * ndtr(-d2) - S * ndtr(-d1)
def surface(P, S, K, T, cp):
    """IV, delta, gamma, vega arrays (nk, 375) by vectorised bisection; NaN where the price is missing / below intrinsic / < 0.5"""
    Sg = np.broadcast_to(S[None, :], P.shape); Kg = np.broadcast_to(K[:, None], P.shape); Tg = np.broadcast_to(T[None, :], P.shape); disc = np.exp(-R_ * Tg)
    intr = np.maximum(Sg - Kg * disc, 0) if cp == 'CE' else np.maximum(Kg * disc - Sg, 0); ok = np.isfinite(P) & (P >= 0.5) & (P > intr + 0.05) & np.isfinite(Sg) & (Tg > 0)
    lo = np.full(P.shape, 0.02); hi = np.full(P.shape, 3.0)
    with np.errstate(all='ignore'):
        for _ in range(40):
            mid = (lo + hi) / 2; pm = bs_price(Sg, Kg, Tg, mid, cp); up = pm < P; lo = np.where(up, mid, lo); hi = np.where(up, hi, mid)
        iv = np.where(ok, (lo + hi) / 2, np.nan); d1 = (np.log(Sg / Kg) + (R_ + .5 * iv ** 2) * Tg) / (iv * np.sqrt(Tg)); phi = np.exp(-.5 * d1 ** 2) / np.sqrt(2 * np.pi)
        delta = ndtr(d1) if cp == 'CE' else ndtr(d1) - 1; gamma = phi / (Sg * iv * np.sqrt(Tg)); vega = Sg * phi * np.sqrt(Tg) / 100
    # fallback: contracts with a price < 0.5 are far OTM -> delta 0 ; deep ITM with price <= intrinsic -> +-1
    far = np.isfinite(P) & (P < 0.5); delta = np.where(far, 0.0, delta); gamma = np.where(far, 0.0, gamma); vega = np.where(far, 0.0, vega)
    itm = np.isfinite(P) & ~ok & ~far & (P <= intr + 0.05) & (intr > 0); delta = np.where(itm, 1.0 if cp == 'CE' else -1.0, delta); gamma = np.where(itm, 0.0, gamma); vega = np.where(itm, 0.0, vega)
    return iv, delta, gamma, vega
