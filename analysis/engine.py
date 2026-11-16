"""Minute-bar backtester for Algo-8-style short-straddle books (clone + research variants).
All assumptions are explicit config: fill model, stop-fill rule, costs (tracked as components, priced afterwards), lot sizes.
Decision at the START of minute m uses only bars completed before m (index close of m-1, option closes of m-1).
"""
import numpy as np, pandas as pd
from dataclasses import dataclass, field
LOT = {'NIFTY': 65, 'SENSEX': 20}
STEP = {'NIFTY': 50, 'SENSEX': 100}

class Cycle:
    """market data for one (underlying, expiry): sessions = [D-1 date, D0 date] (D-1 may be absent)."""
    def __init__(self, und, expiry, sessions, idx, opt):
        self.und, self.expiry, self.sessions = und, expiry, sessions
        ix = idx[(idx.und == und) & (idx.ts.dt.normalize().isin(sessions))].sort_values('ts')
        self.t = pd.DatetimeIndex(ix.ts.values); self.S = ix.close.values; self.n = len(self.t)
        self.day = np.array([0 if (len(sessions) == 2 and x.normalize() == sessions[0]) else 1 for x in self.t])   # 0 = D-1, 1 = D0
        self.hhmm = np.array([x.strftime('%H:%M') for x in self.t])
        o = opt[(opt.und == und) & (opt.expiry == expiry) & (opt.ts.isin(self.t))]
        self.keys = sorted(set(zip(o.cp, o.strike))); self.k2i = {k: i for i, k in enumerate(self.keys)}
        pos = {t: i for i, t in enumerate(self.t)}
        shp = (len(self.keys), self.n)
        self.O = np.full(shp, np.nan); self.H = np.full(shp, np.nan); self.L = np.full(shp, np.nan); self.C = np.full(shp, np.nan)
        ki = np.array([self.k2i[(a, b)] for a, b in zip(o.cp, o.strike)]); ti = np.array([pos[t] for t in o.ts])
        self.O[ki, ti] = o.o.values; self.H[ki, ti] = o.h.values; self.L[ki, ti] = o.l.values; self.C[ki, ti] = o.c.values
        self.Cf = pd.DataFrame(self.C.T).ffill().values.T          # forward-filled closes for marking
        self.settle = self.S[-1]
        self.strikes = {cp: np.array(sorted(k for c, k in self.keys if c == cp)) for cp in ('CE', 'PE')}

@dataclass
class Config:
    name: str = 'clone'
    schedule: list = field(default_factory=list)      # [(day 0/1, 'HH:MM', lots_per_leg)]
    strike_offset: int = 0                             # steps from ATM (applied to both legs)
    wing_frac: float = None                            # wing premium budget as fraction of straddle premium (per side); None = no wings
    leg_stop: float = None                             # per-lot multiple of own entry; None = off
    stop_fill: str = 'level'                           # 'level' (max(open, level)) | 'high' | 'next_open'
    wing_with_leg: bool = True                         # sell the lot's wing when the lot is stopped
    cycle_stop: float = None                           # rupees (positive number = loss limit), checked on minute-close MTM
    exit_time: str = '15:14'                           # D0 flatten time (fill at that minute's open); None = hold to expiry settlement
    d1_exit_time: str = None                           # optional: flatten on D-1 (no carry)
    fill: str = 'open'                                 # entries: 'open' of decision minute | 'prevclose'
    vrp_min: float = None                              # optional filter: enter only if straddle_premium/expected_move >= vrp_min (see research)
    filt: object = None                                # optional callable(cycle, i) -> bool

def _px(cy, k, i, fill):
    if fill == 'open':
        v = cy.O[k, i]
        return v if np.isfinite(v) else cy.Cf[k, i - 1] if i > 0 else np.nan
    return cy.Cf[k, i - 1] if i > 0 else np.nan

def run(cy, cfg, collect=False):
    lot = getattr(cy, 'lot', LOT[cy.und]); step = STEP[cy.und]
    sched = {}
    for dd, hm, n in cfg.schedule: sched.setdefault((dd, hm), 0); sched[(dd, hm)] += n
    lots = []        # dict(k, sgn(-1 short/+1 long), entry, wing_of)
    cash = 0.0; orders = 0; units = 0; turnover = 0.0; missing = 0; stopped_cycle = False; ev = []
    def trade(k, sgn, px, n=1):
        nonlocal cash, orders, units, turnover
        cash -= sgn * px * lot * n; orders += n; units += lot * n; turnover += px * lot * n
    def close_lot(L, px):
        trade(L['k'], -L['sgn'], px); L['open'] = False
    for i in range(1, cy.n):
        hm = cy.hhmm[i]; dd = cy.day[i]
        # 1) cycle stop on previous minute close MTM (decided at start of minute i, filled at open of i)
        if cfg.cycle_stop and not stopped_cycle:
            mtm = cash + sum(L['sgn'] * cy.Cf[L['k'], i - 1] * lot for L in lots if L['open'])
            if mtm <= -cfg.cycle_stop:
                for L in lots:
                    if L['open']: close_lot(L, _px(cy, L['k'], i, 'open'))
                stopped_cycle = True; ev.append(('cycle_stop', cy.t[i]))
        if stopped_cycle: break
        # 2) flatten times
        if (cfg.d1_exit_time and dd == 0 and hm == cfg.d1_exit_time) or (cfg.exit_time and dd == 1 and hm == cfg.exit_time):
            for L in lots:
                if L['open']: close_lot(L, _px(cy, L['k'], i, 'open'))
            if dd == 1: break
        # 3) leg stops (intrabar on minute i's high)
        if cfg.leg_stop:
            for L in lots:
                if not L['open'] or L['sgn'] > 0: continue
                k = L['k']; hi = cy.H[k, i]; lvl = cfg.leg_stop * L['entry']
                if np.isfinite(hi) and hi >= lvl:
                    if cfg.stop_fill == 'level': px = max(cy.O[k, i], lvl) if np.isfinite(cy.O[k, i]) else lvl
                    elif cfg.stop_fill == 'high': px = hi
                    else: px = _px(cy, k, i + 1, 'open') if i + 1 < cy.n else cy.Cf[k, i]
                    close_lot(L, px)
                    if cfg.wing_with_leg and L.get('wing') is not None and L['wing']['open']:
                        w = L['wing']; close_lot(w, cy.Cf[w['k'], i])
        # 4) scheduled entries
        n = sched.get((dd, hm), 0)
        if n:
            if cfg.filt is not None and not cfg.filt(cy, i): n = 0
        if n:
            S1 = cy.S[i - 1]; K = round(S1 / step) * step + cfg.strike_offset * step
            kc, kp = cy.k2i.get(('CE', K)), cy.k2i.get(('PE', K))
            if kc is None or kp is None or not np.isfinite(cy.Cf[kc, i - 1]) or not np.isfinite(cy.Cf[kp, i - 1]):
                missing += n
            else:
                pc, pp = _px(cy, kc, i, cfg.fill), _px(cy, kp, i, cfg.fill)
                wings = {}
                if cfg.wing_frac:
                    budget = cfg.wing_frac * (cy.Cf[kc, i - 1] + cy.Cf[kp, i - 1])
                    for cp, sgnk in (('CE', 1), ('PE', -1)):
                        cand = [k for k in cy.strikes[cp] if (k - K) * sgnk > 0]
                        cand = sorted(cand, key=lambda k: abs(k - K))
                        pick = None
                        for k in cand:
                            v = cy.Cf[cy.k2i[(cp, k)], i - 1]
                            if np.isfinite(v) and v <= budget: pick = cy.k2i[(cp, k)]; break
                        wings[cp] = pick
                for _ in range(n):
                    for cp, k, px in (('CE', kc, pc), ('PE', kp, pp)):
                        L = dict(k=k, sgn=-1, entry=px, open=True, wing=None); trade(k, -1, px); lots.append(L)
                        wk = wings.get(cp)
                        if cfg.wing_frac and wk is not None:
                            wp = _px(cy, wk, i, cfg.fill)
                            if np.isfinite(wp):
                                W = dict(k=wk, sgn=1, entry=wp, open=True, wing=None); trade(wk, 1, wp); lots.append(W); L['wing'] = W
                        elif cfg.wing_frac: missing += 0.5
    # settle remaining at expiry intrinsic
    for L in lots:
        if L['open']:
            cp, K = cy.keys[L['k']]
            intr = max(cy.settle - K, 0) if cp == 'CE' else max(K - cy.settle, 0)
            cash += L['sgn'] * intr * lot; L['open'] = False
    out = dict(und=cy.und, expiry=cy.expiry, pnl=cash, orders=orders, units=units, turnover=turnover, missing=missing, cycle_stopped=stopped_cycle,
               n_lots=sum(1 for L in lots if L['sgn'] < 0))
    return out

COSTS = {  # prior study's registered scenarios: % of premium turnover, Rs per parent order, Rs per unit
    'zero': (0.0, 0.0, 0.0), 'moderate': (0.0025, 20.0, 0.05), 'conservative': (0.005, 20.0, 0.10), 'adverse': (0.005, 40.0, 0.20)}
def net(r, scen):
    a, b, c = COSTS[scen]; return r['pnl'] - a * r['turnover'] - b * r['orders'] - c * r['units']

def load_cycles(idx, opt, trades=None):
    """cycles from the market data: expiry + its previous trading session. If trades given, restrict to cycles traded by Algo 8."""
    out = []
    sess = sorted(idx.ts.dt.normalize().unique())
    for (und, e), _ in opt.groupby(['und', 'expiry']):
        days = sorted(d for d in idx[idx.und == und].ts.dt.normalize().unique() if d <= e)
        if not days or days[-1] != e: continue
        s = days[-2:] if len(days) >= 2 else days[-1:]
        out.append(Cycle(und, e, list(s), idx, opt))
    return out
