"""Pure, individually testable decision rules for the Algo 8 ladder reconstruction (Python reference implementation).
Each rule carries the evidence status it had when implemented (see DECISION_RULE_EVIDENCE_REGISTER.md). Nothing here is tuned to P&L."""
import numpy as np

# R-LAD-D1: D-1 body ladder, lots per leg (CE and PE equal) at slot k (09:16 + 15 k min). Source: FINDINGS parameter sheet, re-verified on the live ledger in phase3_checks (first 3 minutes of slot: 66-70 % of slot-legs equal the modal value). STRONGLY SUPPORTED.
LADDER_D1 = [3, 2, 3, 1, 3, 1, 2, 2, 1, 1, 3, 1, 0, 2, 0, 0, 1]
SLOT0 = 1                                     # minute index of 09:16 (09:15 = 0)
# R-WING-PREM: wing bought with each body lot; wing strike chosen so that wing price ~ 2.45 % of the body price (median of 2,884 matched wing/body pairs; IQR 2.2-2.6 %). STRONGLY SUPPORTED (exact strike-selection logic unknown).
WING_RATIO = 0.0245
# R-LEGSTOP: buy back a body lot when LTP >= mult x its own entry; lots with entry <= 4 are exempt. PARTIALLY UNDERSTOOD: evidence band 1.55-1.7x (own vs cheapest-lot reference). Central value used, NOT tuned.
LEG_STOP_MULT = 1.6; LEG_STOP_EXEMPT_PX = 4.0
# R-CYCLESTOP: cumulative LTP mark-to-market of the cycle <= -1.44 lakh -> liquidate everything, no further entries. STRONGLY SUPPORTED on the 2026 live sample (82-89 % validated); the rupee constant is NOT known to scale with lot size or period.
CYCLE_STOP_RS = 144_000.0
# R-FLATTEN: D0 forced flatten ~15:14 (bar 15:14). PARTIALLY UNDERSTOOD.
FLATTEN_MIN = 5 * 60 + 59 - 0                # minute index of 15:14 (09:15 = 0): 15:14 -> (15-9)*60 + (14-15) = 359
FLATTEN_MIN = (15 - 9) * 60 + 14 - 15


def nearest_strike(strikes, spot, step):
    """R-STRIKE: strike nearest to the previous completed minute's index close (grid = exchange step). STRONGLY SUPPORTED as a *tendency* (50 % exact, 89 % within one step on D-1)."""
    k = step * np.floor(spot / step + 0.5); i = int(np.argmin(np.abs(strikes - k))); return i


def wing_strike_index(strikes, right, atm_idx, body_px, price_at, ratio=WING_RATIO):
    """Wing: OTM strike on the same side whose last price is closest to ratio x body price (cheapest-first search outward from ATM). price_at(i) returns last price of strike index i."""
    target = ratio * body_px; best, bd = None, 1e18
    rng = range(atm_idx + 1, len(strikes)) if right == 'CE' else range(atm_idx - 1, -1, -1)
    for i in rng:
        p = price_at(i)
        if p != p: continue
        d = abs(p - target)
        if d < bd: best, bd = i, d
        if p < target * 0.5: break
    return best


def leg_stop_hit(px_now, entry_px, mult=LEG_STOP_MULT, exempt=LEG_STOP_EXEMPT_PX):
    return entry_px > exempt and px_now >= mult * entry_px


def cycle_stop_hit(mtm, limit=CYCLE_STOP_RS): return mtm <= -limit
