"""Render reports/HISTORICAL_DATA_FEASIBILITY.md from experiments/results/cycle_eligibility_register.csv (all numbers computed, none typed)."""
import os, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = pd.read_csv(f'{ROOT}/experiments/results/cycle_eligibility_register.csv'); ORDER = ['FULLY_FEASIBLE', 'FEASIBLE_WITH_DECLARED_SUBSTITUTION', 'PARTIAL', 'UNUSABLE']
def tab(idx):
    t = R.pivot_table(index=idx, columns='eligibility', values='expiry', aggfunc='count', fill_value=0).reindex(columns=ORDER, fill_value=0); t['expected'] = t.sum(axis=1)
    t['usable (fully + substituted)'] = t.FULLY_FEASIBLE + t.FEASIBLE_WITH_DECLARED_SUBSTITUTION; return t
def md(t):
    t = t.reset_index(); cols = list(t.columns); out = ['| ' + ' | '.join(map(str, cols)) + ' |', '|' + '---|' * len(cols)]
    for r in t.itertuples(index=False): out.append('| ' + ' | '.join(str(x) for x in r) + ' |')
    return '\n'.join(out)
ok = R[R.eligibility.isin(['FULLY_FEASIBLE', 'FEASIBLE_WITH_DECLARED_SUBSTITUTION'])]
w = ok.groupby('und').apply(lambda d: pd.Series(dict(cycles=len(d), opening_atm_executable=f'{d.open_atm_exec.mean():.1%}', CE_wing_exact=f'{d.wing_ce_exact.mean():.1%}', PE_wing_exact=f'{d.wing_pe_exact.mean():.1%}', both_wings_exact=f'{(d.wing_ce_exact & d.wing_pe_exact).mean():.1%}', min_D1_windows_of_17=int(d.d1_windows_exec.min()), min_D0_windows_of_23=int(d.d0_windows_exec.min())))).reset_index().set_index('und')
tot = R.eligibility.value_counts().reindex(ORDER).to_dict()
L = f'''# Historical data feasibility and cycle eligibility register

**Status:** computed from the independent expiry calendar and the full-chain minute caches built from the pinned dataset commit `eb4097308d47ccc75078ab73ba76d33bb1c7030b`. The eligibility criteria (`config/eligibility_criteria.yaml`) were written **before** this table existed; a cycle's class depends only on data availability, never on P&L. No replica performance exists yet.
Register (one row per expected expiry): `experiments/results/cycle_eligibility_register.csv`. Rebuild: `python3 tools/build_eligibility.py && python3 tools/make_feasibility_md.py`.

## 1. Result first
* **Expected cycles: {len(R)}** (NIFTY {int((R.und == 'NIFTY').sum())}, SENSEX {int((R.und == 'SENSEX').sum())}). **FULLY_FEASIBLE {tot['FULLY_FEASIBLE']} · FEASIBLE_WITH_DECLARED_SUBSTITUTION {tot['FEASIBLE_WITH_DECLARED_SUBSTITUTION']} · PARTIAL {tot['PARTIAL']} · UNUSABLE {tot['UNUSABLE']}.** Results will be reported on (a) strictly complete cycles, (b) substituted cycles separately, (c) the full expected-cycle denominator.
* **Scheduled ATM entries are executable almost everywhere** (every usable cycle has all 17 D-1 windows with an executable ATM CE+PE; D0 windows ≥ 21 of 23). **The binding constraint is the seed wings:** both exact wings trade in the 09:16–09:20 window in only the share shown in §3, so a large part of the history needs a declared wing substitution.
* **SENSEX before 2024-05-30 does not exist** (30 expected Friday expiries; plus 5 unreported). The brief's "Nov 2023 – May 2024 development" block is NIFTY-only.
* **Nothing here is out-of-sample.** The evidence tiers of §4 apply; see `PHASE0_REPOSITORY_AUDIT.md` §5.

## 2. Eligibility by index and by proposed period (D0 date)
{md(tab(['und']))}

{md(tab(['period', 'und']))}

## 3. What is executable in the usable cycles
{md(w)}

Policy (fixed in advance): a bar is executable only if its volume is > 0 (zero-volume bars are carried prices); the fill is the open of the first executable bar in the decision minute and the next two; otherwise `NO_MARKET` and no price is invented. A missing exact wing is substituted by the nearest traded strike toward ATM **and flagged**; the replica must record the substitution distance.

## 4. Evidence tiers (contamination), by class
{md(tab(['tier']))}

| Tier | Meaning |
|---|---|
| T3 in-sample of prior programmes | D0 ≤ 2025-11-17: used for configuration selection in the 4-leg backtest and as IS for the R1/R2 ladder replication |
| T2 previously scored by related strategies | 2025-11-18 → 2026-06-21: scored once by the 4-leg backtest (OOS) and by R1/R2 (OOS clean) |
| T4 live window | 2026-06-22 → 2026-10-22: reverse-engineering sample, repeatedly inspected |
| T1 never evaluated | after 2026-10-22: {int((R.tier.str.startswith('T1')).sum())} expiries, too few for inference |

**Consequence.** No block can be called an untouched out-of-sample for a strategy that contains the rules of R1. The brief's three-period split (dev / validation / primary OOS) is retained **as a chronological partition**, but its OOS block is labelled "previously inspected by related strategies" in every table, and conclusions rest on consistency across blocks and on bounded scenarios, not on one number. This treatment is my proposal and is recorded before any replica result exists; if you prefer a different treatment (for example treating everything before 2025-06 as in-sample and refusing to quote any OOS Sharpe), say so before the freeze.

## 5. Unusable and partial cycles (all listed, none dropped silently)
{md(R[R.eligibility.isin(['PARTIAL', 'UNUSABLE'])].groupby(['und', 'validation_status', 'eligibility']).size().rename('cycles').reset_index().set_index(['und', 'validation_status', 'eligibility']))}

Reasons: {R[R.eligibility.isin(['PARTIAL', 'UNUSABLE'])].reasons.str.replace(r'\\d+/17', 'n/17', regex=True).value_counts().to_dict()}. Special/outage sessions come from the data-validation defects D04 and D21; they are excluded, not repaired.

## 6. Known data conditions the loader must apply (REPORTED by `data_validation`, not re-derived here)
09:15–15:29 bars only (15:39 option bars after 2026-08-03; **no NIFTY spot after 15:14** on those sessions, D05) · volume 0 = no trade · drop volumes outside [0, 2^31) (23 wrap-around rows, D06) · mask the four outage sessions (D21) · no SENSEX open interest (D03) · **the existing per-cycle caches contain open, close and volume only — no high/low**, so the replica needs a new loader that also reads high and low for stop-crossing logic · lot size is inferred from the volume gcd, not supplied · option universe = ATM ± 45 around the D-2 close; contracts outside it are `NO_MARKET`.

## 7. Limits of this table
It checks availability of the instruments a scheduled ATM entry and the seed wings would need. It does **not** check the routine-wing budget strike, ladder quantities, stop-crossing bars (no high/low in the cache) or settlement; those are examined when the modules exist. A FULLY_FEASIBLE label means "the entry skeleton can be priced from traded bars", not "the replica is valid in that cycle".
'''
open(f'{ROOT}/reports/HISTORICAL_DATA_FEASIBILITY.md', 'w').write(L); print(len(L))
