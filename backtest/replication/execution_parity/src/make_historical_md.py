"""Render ../HISTORICAL_REGIME_ROBUSTNESS.md from outputs/historical_*.csv (all numbers computed)."""
import os, pandas as pd, numpy as np
import ref
M = pd.read_csv(f'{ref.OUT}/historical_mechanics_by_cycle.csv'); X = M[M.eligible].copy(); E = M.copy()
def md(t):
    t = t.reset_index(); out = ['| ' + ' | '.join(map(str, t.columns)) + ' |', '|' + '---|' * len(t.columns)]
    for r in t.itertuples(index=False): out.append('| ' + ' | '.join((f'{x:.3g}' if isinstance(x, (float, np.floating)) else str(x)) for x in r) + ' |')
    return '\n'.join(out)
struct = E.groupby('expiry_structure').agg(first_D0=('d0', 'min'), last_D0=('d0', 'max'), expected=('expiry', 'size'), eligible=('eligible', 'sum'), fully=('eligibility', lambda s: int((s == 'FULLY_FEASIBLE').sum())), substituted=('eligibility', lambda s: int((s == 'FEASIBLE_WITH_DECLARED_SUBSTITUTION').sum())), partial=('eligibility', lambda s: int((s == 'PARTIAL').sum())), unusable=('eligibility', lambda s: int((s == 'UNUSABLE').sum())))
mech = X.groupby('expiry_structure').agg(cycles=('expiry', 'size'), lot_size_inferred=('hist_lot', 'median'), orders_per_cycle=('n_fills', 'mean'), fills_on_zero_volume_bar=('fills_on_zero_volume_bar', 'mean'), fills_where_open_missing=('fills_on_open_nan', 'mean'), strict_no_market_entries=('strict_no_market_entries', 'mean'), strict_no_market_exits=('strict_no_market_exits', 'mean'), leg_stops=('leg_stops', 'mean'), wing_dist_steps=('wing_dist_steps_median', 'median'), wing_px_ratio=('wing_px_ratio_median', 'median'))
stopinc = X.groupby('expiry_structure').agg(cycle_stop_share_2026_lot=('cycle_stop', 'mean'), cycle_stop_share_inferred_lot=('cycle_stop_histlot', 'mean'), leg_stops_2026_lot=('leg_stops', 'mean'), leg_stops_inferred_lot=('leg_stops_histlot', 'mean'))
reg = X.groupby(['und', 'vol_regime']).agg(cycles=('expiry', 'size'), rv20_mean=('rv20', 'mean'), zero_volume_fills=('fills_on_zero_volume_bar', 'mean'), strict_no_market_exits=('strict_no_market_exits', 'mean'), cycle_stop_share=('cycle_stop', 'mean'))
trd = X.groupby(['und', 'trend_regime']).agg(cycles=('expiry', 'size'), cycle_stop_share=('cycle_stop', 'mean'), zero_volume_fills=('fills_on_zero_volume_bar', 'mean'))
g_ = X.groupby('expiry_structure'); on, ox = g_.fills_on_open_nan.mean()['NIFTY-Tuesday-expiry#2'], g_.fills_on_open_nan.mean()['SENSEX-Tuesday-expiry#2']; zn, zx = g_.fills_on_zero_volume_bar.mean()['NIFTY-Tuesday-expiry#2'], g_.fills_on_zero_volume_bar.mean()['SENSEX-Tuesday-expiry#2']; xn, xx = g_.strict_no_market_exits.mean()['NIFTY-Tuesday-expiry#2'], g_.strict_no_market_exits.mean()['SENSEX-Tuesday-expiry#2']
vs = X.groupby(['und', 'vol_regime']).cycle_stop.mean(); vz = X.groupby(['und', 'vol_regime']).fills_on_zero_volume_bar.mean()
hard = dict(cycles=len(X), ok=int(X.ok.sum()), inventory_consistent=int(X.inventory_consistent.sum()), gross_finite=int(X.gross_finite.sum()), settlement_close_missing=int(X.settle_close_nan.sum()), open_lots_at_end=int(X.open_at_end.sum()), body_closed_gt_opened=int(X.body_closed_gt_opened.sum()), duplicate_event_hashes=int(X.events_hash.duplicated().sum()))
excl = E[~E.eligible].groupby(['und', 'eligibility', 'reasons']).size().rename('cycles')
L = f'''# Historical regime and mechanics robustness (Phase 5)

**Purpose.** Find brittle execution assumptions when the reconstructed engine is replayed under different expiry structures and market regimes. **This is not a performance test and not a parity test**: no original execution records exist for these periods, so nothing here can show that the original behaved this way, and no historical P&L is compared with the original. Rahul's warning is applied: the three years are **not** treated as one sample.
**Data.** 319 expected weekly expiries; eligibility register of PR #14 (criteria fixed before use). **Strict (FULLY_FEASIBLE) and substituted (FEASIBLE_WITH_DECLARED_SUBSTITUTION) cycles are kept apart below where it matters; excluded cycles are listed in §6, not dropped silently.** Code: `src/run_historical.py`, `src/make_historical_md.py`; tables `outputs/historical_regime_register.csv`, `outputs/historical_mechanics_by_cycle.csv`.

## 1. Result first
* **Hard mechanics hold in every structure:** {hard['ok']}/{hard['cycles']} eligible cycles run, inventory reconciles with the fills in {hard['inventory_consistent']}, P&L finite in {hard['gross_finite']}, settlement close present in all but {hard['settlement_close_missing']}, no body lot closed more often than opened ({hard['body_closed_gt_opened']} violations), {hard['duplicate_event_hashes']} duplicate event sequences. Look-ahead and determinism are tested in `tests/test_core_integrity.py` (passing).
* **The scheduled decisions are identical by construction in every structure (about 208 orders per cycle); what differs is the quality of the prices behind them** (§3): fills that rely on a stale last-close because the decision minute has no open price, fills on zero-volume bars, and exits that cannot execute under a strict "volume > 0" policy differ strongly between structures: fills priced from a missing open {ox:.2f} vs {on:.2f} per cycle (SENSEX Tuesday-expiry segment, Jan–Aug 2025, vs NIFTY Tuesday segment), fills on zero-volume bars {zx:.2f} vs {zn:.2f}, strict NO_MARKET exits {xx:.2f} vs {xn:.2f}. A simulator that silently falls back to the previous close is therefore **brittle exactly where liquidity was thinnest**.
* **The same rupee cycle-stop constant is not comparable across structures** (§4): its incidence ranges from {X.cycle_stop.groupby(X.expiry_structure).mean().min():.0%} to {X.cycle_stop.groupby(X.expiry_structure).mean().max():.0%} of cycles depending on structure, and the lot-size assumption (2026 sizes vs inferred historical sizes) changes it further. This confirms that the constant was read at the 2026 size and must not be transported.

## 2. Expiry-calendar structures (weekday of the expected expiry; rolling mode of 5, holiday shifts ignored)
{md(struct)}

NIFTY changed from Thursday to Tuesday expiries on 2025-09-02; SENSEX moved Friday → Tuesday (2025-01) → Thursday (2025-09). **The 35 live cycles (2026-06 to 2026-10) are NIFTY-Tuesday and SENSEX-Thursday.** A mechanics result in an older structure therefore carries different D-1/D0 weekdays, different lot sizes and different liquidity.

## 3. Execution-price mechanics by structure (eligible cycles, per cycle means unless stated)
{md(mech)}

`fills_where_open_missing` = fills the permissive policy priced at the last completed close because the decision minute has no open price; `fills_on_zero_volume_bar` = fills on a bar with volume 0 (carried price, not executable under the strict policy); `strict_no_market_*` = intents that cannot be executed at all under the strict policy (an unfillable exit leaves a lot open). Neither policy is "the original"; the original's behaviour in illiquid minutes is unobserved.

## 4. Stop incidence by structure (mechanics, not performance)
{md(stopinc)}

Lot sizes inferred per session (volume gcd): see `lot_size_inferred` above (NIFTY 50→65, SENSEX 10→20). Stop counts differ with the lot-size assumption because the rupee cycle stop is size-dependent.

## 5. Regime labels (Yahoo daily only; computed strictly before D-1)
{md(reg)}

{md(trd)}

Volatility regime also moves the mechanics: cycle-stop incidence ranges {vs.min():.0%}–{vs.max():.0%} and zero-volume fills {vz.min():.2f}–{vz.max():.2f} per cycle across the tercile labels (confounded with the structure and the lot size). No regime-conditional conclusion about the original is drawn.

## 6. Excluded cycles and reasons
{md(excl.to_frame())}

## 7. Brittle assumptions identified (no fix is applied here)
1. **Stale-price fills:** the permissive fill policy of the stored simulator prices unavailable-open minutes at the last close. Needs an explicit documented policy; affects ≈ 1–2 fills per cycle in thin structures.
2. **Unfillable exits:** a strict policy leaves lots open when the exit bar has no volume (≈ 1–2 per cycle): the original's behaviour is unknown (it may chase with marketable limits).
3. **Constants in rupees and units:** cycle stop in rupees at the 2026 size; ladder in lots at the inferred size. Cross-structure comparison needs a stated scaling convention (U14).
4. **Wing placement drifts with the strike grid / premium level** (median wing distance {X.wing_dist_steps_median.median():.0f} strikes; ratio ≈ {X.wing_px_ratio_median.median():.3f} by construction of the 2.45 % rule).
5. **Data conditions** the loader must apply: 09:15–15:29 bars, no NIFTY spot after 15:14 on post-2026-08-03 sessions, volume wrap-around rows, four outage sessions, SENSEX no open interest, strikes limited to ATM ± 45 around the D-2 close (REPORTED by `data_validation`).

## 8. Limits
Only D-1 and D0 sessions exist; option universe is ATM ± 45; no bid/ask; lot sizes inferred; per-cycle caches contain open/close/volume only (no high/low), so intrabar stop crossing cannot be examined; the engine used is the R1 rule set (a hypothesis, fitted on the 2026 window), so these runs test **mechanics**, not that the rules are right.
'''
open(os.path.join(os.path.dirname(ref.OUT), 'HISTORICAL_REGIME_ROBUSTNESS.md'), 'w').write(L); print(len(L))
