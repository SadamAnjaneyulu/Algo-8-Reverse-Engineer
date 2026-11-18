"""Write the highest-supported economic hypothesis without a false alpha claim."""
import csv
import json
from pathlib import Path

from audit_strike_hedge_rules import OUT


def rows(name):
    return list(csv.DictReader((OUT/name).open()))


def money(value): return f'₹{float(value):,.2f}'


def main():
    summary = json.loads((OUT/'alpha_candidate_summary.json').read_text())
    chosen = {r['asset']: r for r in summary['selected']}
    nifty = chosen['NIFTY']
    assert nifty['model'] == 'budget_2p5|pre_to_expiry|time_only|none'
    cal, later = nifty['calibration'], nifty['later']
    evidence = next(r for r in rows('alpha_candidate_weekly_evidence.csv') if r['asset'] == 'NIFTY' and r['quality'] == 'all')
    sensitivity = [r for r in rows('alpha_candidate_sensitivity_summary.csv') if r['asset'] == 'NIFTY']
    ordinary = next(r for r in rows('alpha_candidate_ordinary_opening_sensitivity.csv') if r['asset'] == 'NIFTY')
    components = [r for r in rows('alpha_candidate_profit_components.csv') if r['asset'] == 'NIFTY']
    short, hedges, costs = [sum(float(r[k]) for r in components) for k in ('short_premium_pnl', 'long_hedge_pnl', 'cost_stress')]
    baseline = next(r for r in rows('alpha_candidate_baseline_evidence.csv') if r['asset'] == 'NIFTY')
    table = '| Sample | Cycles | Profitable cycles | Net after primary cost stress |\n| --- | ---: | ---: | ---: |\n'
    for label, data in [('June–August selection', cal), ('September–October check', later)]:
        table += f"| {label} | {data['cycles']} | {data['winning_traded_cycles']} | {money(data['net_primary'])} |\n"
    stress_table = '| Frozen-rule sensitivity | Later cycles | Net | Profitable cycles |\n| --- | ---: | ---: | ---: |\n'
    for r in sensitivity:
        stress_table += f"| {r['variant']} | {r['cycles']} | {money(r['net'])} | {r['winning']} |\n"
    other_table = '| Earlier-selected family | Later cycles | Later net |\n| --- | ---: | ---: |\n'
    for asset in ('pooled', 'SENSEX'):
        r = chosen[asset]
        other_table += f"| {asset}: {r['model']} | {r['later']['cycles']} | {money(r['later']['net_primary'])} |\n"
    text = f'''# Algo 8: highest-supported alpha hypothesis and a concrete candidate

**My first-ranked explanation is calendar-based short-volatility carry with
cheap outward protection.** The clock/size ladder builds short-premium exposure;
separate-side management changes which risks survive. The evidence is much
stronger for that structure than for a hidden indicator predicting a range.

This identifies the most plausible **profit engine**, not a certified unique
alpha or recovered original program. Selling volatility can earn compensation
for movement, gap and surface risk; positive samples alone do not establish
excess risk-adjusted return. I cannot assign an honest 80–90% probability that
an unobserved original condition has been identified.

## 1. The cleanest positively performing approximation

An autonomous one-basket candidate was selected on expiries through 31 August.
It does not borrow later observed entries, position states or exits:

1. **NIFTY pre-expiry session, 09:16 signal:** read the completed 09:15 cash-index
   candle. Choose its nearest 50-point ATM strike.
2. Sell that CE and PE; buy an outward CE and PE. Each wing is the highest
   prior fresh quoted premium not exceeding **2.5% of its corresponding ATM
   leg premium**, within the stored quote universe.
3. Test **195 units per role**, three observed 65-unit base quantities. This size
   is not optimized for returns and is not an inferred capital/margin rule.
4. Execute the modeled entry at **09:17 open**, one minute after the signal.
5. Hold through expiry and exit at the **15:14 open**, a preplanned time. The
   earlier ranking preferred this time-only policy; tested range gates and
   separate-leg stops did not improve its selection score.

This candidate applies the routine premium-budget hedge from the start, whereas
the original opening seed wings commonly use a different distance rule. It also
omits the observed later ladder, allocation-specific resets and pending orders.
It is therefore an **economic-core approximation, not an 80–90% execution clone**.
The original 4% carry/1% capital statements remain distinct unresolved controls.

{table}
The later win rate is **{100*later['traded_win_rate']:.1f}%**, not an established
80–90% win probability. Later net remains **{money(later['net_high'])}** under the
higher cost stress. The worst observed later cycle is
**{money(later['worst_cycle_net'])}**, and the closed-cycle drawdown is
**{money(later['closed_cycle_drawdown_rupees'])}**. Those are not intracycle losses
or drawdowns from the original screenshot. Quantities, initial loss budgets,
and unscaled rupee outcomes remain exported rather than extrapolated to a CAGR.

## 2. Where the later profit actually comes from

The seven NIFTY cases reconcile exactly:

| Cashflow source | P&L |
| --- | ---: |
| Short CE/PE: entry receipts minus buyback costs | {money(short)} |
| Long protection: sale proceeds minus purchase costs | {money(hedges)} |
| Modeled transaction costs | −{money(costs)} |
| Net | {money(later['net_primary'])} |

This is direct price/cashflow attribution, not a claim that all premium
compression is pure theta. Spot movement and IV changes also affect buyback
prices. The observed benefit is consistent with collecting short-dated option
premiums and paying for tail protection, not with a recovered RSI/ADX signal.

The broader log evidence supports the same working explanation: 31/32 initial
paired starts near 09:16, recurring pre-expiry additions, common normalized
size weights on both indices, and additions after both rises and falls. A large
opening candle does not invariably block entry. Loss-making CE covers usually
follow rises; loss-making PE covers usually follow falls. Those observations
do not by themselves recover their exact stops or prove profitable risk control.

## 3. What was tested and how the candidate was chosen

The finite bank contains **{summary['model_count']}** combinations: six entry/exit
horizons, two hedge geometries, six exit controllers and seven entry filters.
Horizons isolate pre-expiry intraday, open-to-next-open, open-to-expiry,
late-to-next-open, late-to-expiry and expiry intraday. Controllers include
symmetric 50% premium stops, separate CE50/PE60 stops, 90% profit exits and a
defined candidate expiry-day ₹200,000 gross portfolio stop.

Range, first-minute movement, gap, trend-efficiency and IV/realized-volatility
filters use only pre-entry information. A filter skip is zero only after the
unfiltered policy is quote-valid. Missing quotes/inputs are excluded and cannot
be counted as profitable avoided trades. Exit/filter variants share a valid
cohort within each horizon/geometry, avoiding an advantage from different stop
monitoring exclusions. Cross-horizon quote coverage can still differ.

Selection uses earlier worst leave-one-week-out mean normalized net return,
then median/mean, with minimum data/trade support and simplicity on exact ties.
It does not optimize later profit or an 80–90% win rate. Earlier-only selection
does not make the later data independent: those dates and hedge parameters were
already examined in prior research. Many candidate tests also raise selection
uncertainty beyond the intervals below.

When both sides close together, normalization uses the frozen expiry loss
bound. For independently timed CE/PE exits, it uses a conservative sum of the
side widths less initial credit: two separately timed losses can exceed a
frozen condor's terminal loss. These are gross theoretical loss budgets, not
broker margin or identical Gamma/Vega/funding risk.

## 4. Execution and quote checks

{stress_table}
The ordinary-opening subset, excluding the recorded delayed opening, has
{ordinary['cycles']} later cycles and **{money(ordinary['net_primary'])}** net.
All seven primary later NIFTY cases have nonzero entry/exit candle volume and
no checked vertical-spread price-bound violation. Trade-candle opens still are
not synchronous bid/ask fills or a guarantee of capacity at the tested size.

Primary costs are 25 bps of premium turnover, ₹20 per order and ₹0.05 per
transacted quantity. The parallel-parent sensitivity charges 24 orders instead
of eight for the three-base-unit entry, holding market prices fixed. The high
stress increases turnover/slippage charges. These are assumptions, not invoices.

## 5. What prevents calling this proven alpha

The later weekly bootstrap for NIFTY mean net per ₹10,000 of the theoretical
loss budget is **{money(evidence['mean'])}**, with a 95% interval
**[{money(evidence['lower'])}, {money(evidence['upper'])}]**. It includes zero.
The seven-cycle win-rate Wilson interval is approximately
{100*float(evidence['win_rate_lower']):.1f}–{100*float(evidence['win_rate_upper']):.1f}%.

Against the independent wider seed-wing time baseline there are only
**{baseline['common_cycles']} common later NIFTY cycles**. The candidate earns
**{money(abs(float(baseline['total_difference_net'])))} less** in raw net profit on that
intersection, while using a smaller theoretical loss budget. All four paired
cases are winning candidate cycles; the available comparison omits its two
losing cycles and another winner. Its favorable risk-budget-normalized paired
comparison must not be promoted to full-cohort or independent alpha.

The other earlier-selected economic families fail in the later period:

{other_table}
This does not prove Algo 8 lacks SENSEX alpha. It shows that a generic autonomous
carry prototype does not recover the later SENSEX decisions or profitability.
Original later management, strike configurations and account-level risk are
still missing. A common sizing framework is not proof of equal economic edge.

## 6. Does the observed ATM ladder explain the edge?

A separate controlled test uses earlier-only pooled modal clock weights, the
same total intended quantity and the same base-unit child-order charges. It
compares one opening allocation, averaging the original strikes, fresh ATM
entries at each slot, and one late allocation. It isolates re-centering versus
entry-time averaging rather than borrowing recorded decisions.

In the quote-complete later NIFTY subset, fresh-ATM averaging and next-open exit
produces five profitable cycles out of six. **Do not treat that 83.3% as recovered
alpha:** its common cohort omits 13 October, the biggest losing overnight
opening-basket case in the broader set. Weekly intervals for the incremental
fresh-ATM advantage include zero; SENSEX does not show the same improvement.
The detailed outcomes and exclusions are in `alpha_staggered_*.csv`.

The single-basket NIFTY result above includes all seven later observed NIFTY
cycles, including 13 October. The staged result is a mechanism clue with weaker
coverage, not a preferred headline selected after seeing 5/6 wins. Portfolio
capital stops and side re-entry remain outside that averaging isolation.

## 7. Highest-supported interpretation

**The most likely economic engine is near-expiry volatility carry, protected
with outward options, with timed allocation and separate risk-state management.**
I rank a simple NIFTY pre-expiry protected carry basket as the cleanest current
approximation because it is positive in both chronological periods, survives
the tested execution/cost changes and does not need an invented range trigger.
Its exact current recipe is in `alpha_highest_ranked_rulebook.json`.

That ranking is not a claim of unique original alpha, 80–90% future profitability
or a complete Algo 8 replica. The next decisive test is the frozen candidate
on new complete-chain bid/ask data, with actual margin/funding and no retuning
against those outcomes. Repeatedly fitting the already inspected sample cannot
supply that missing evidence.

## Reproduction

```bash
python research/rank_economic_alpha.py
python research/check_staggered_carry.py
python research/audit_alpha_candidate.py
python research/write_alpha_candidate_report.py
python -m unittest discover -s research -p 'test_*.py'
```

All **159 repository tests pass**. Added checks cover causal entry features,
future-open stop execution, separate-side path risk, cashflow-versus-profit,
missing monitoring/exit quotes, filter abstention, drawdown and idle-cycle
accounting. Output tables retain every candidate cycle, exclusions, calibration
ranking, later results, baseline pairing, cashflow attribution and sensitivities.
Historical eligibility is conditional on the supplied expiry cycles; missing
contracts from the traded-only universe are not invented. The earlier backtest
screenshot is not reproduced.
'''
    (Path(__file__).resolve().parent/'ALPHA_CANDIDATE_FINDINGS.md').write_text(text)


if __name__ == '__main__': main()
