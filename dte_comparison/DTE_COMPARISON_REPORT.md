# 1DTE vs 0DTE contract comparison: Algo 7 and Algo 8

Descriptive only; no strategy rule is fitted. Code: [`dte_compare.py`](dte_compare.py) and
[`kill_switch_tests.py`](kill_switch_tests.py) (both executed). Full metric table: [`DTE_COMPARISON.csv`](DTE_COMPARISON.csv)
(2 algos × 2 actor scopes × DTE bucket × 9 populations). Stage 2 of the skeleton has **not** started.

## 1. Result

| Question | Algo 8 | Algo 7 |
|---|---|---|
| More **distinct contracts** | **0DTE**: 1,449 vs 1,042 (43.9 vs 32.6 per session) | **0DTE**: 1,697 vs 1 |
| More **traded lots** | **0DTE**: 49,997 vs 13,655 (1,515 vs 427 per session, 3.6×) | **0DTE**: 43,328 vs 100 |
| More **premium turnover** | **0DTE**: ₹6.71 Cr vs ₹3.62 Cr (₹20.3 L vs ₹11.3 L per session, 1.8×) | **0DTE**: ₹6.13 Cr vs ₹5,250 |
| Why does 0DTE have more activity? (Algo 8) | **Mainly repeated trading per contract.** Log-share of the 3.6× lot ratio: orders per contract-day 61 %, more contracts per session 24 % (more strikes, ×1.40), lots per order 15 % | Not comparable: one 1DTE session |

* **Algo 8 is a two-bucket strategy:** 32 of its 35 cycles have a 1DTE session, and 817 contracts trade on both days.
  At the end of the 1DTE sessions it carries 3,238 short and 4,749 long lots overnight.
* **Algo 7 is a 0DTE strategy in this export:** 30,171 of 30,192 fills are on the expiry date. Its only 1DTE trading is
  one SENSEX long call (50 lots bought, 50 sold, 21 strikes OTM, 13 fills). There are also 8 fills on Saturday 4 July
  (a non-session, labelled separately). Algo 7's own report says "expiry-day index options" and mentions 8 pre-expiry trades.
* **The 4 % expiry-day kill switch (client-provided) does not match the observed cycle stop** under any of nine tested
  readings (§6). It is registered as RSK-06, a client-provided hypothesis that is not supported. RSK-01 is unchanged.

## 2. Data and definitions (for review)

| Item | Definition |
|---|---|
| Algo 8 data | `Trades_GKOHNP140.csv`: 41,421 fills, 35 cycles, 22 Jun – 22 Oct 2026; order = column-163 `UniqueOrderIdentifier` |
| Algo 7 data | `Algo_7_Dump.xlsx` (user-supplied, not committed): 30,192 fills, client PCHNA531, 13 Apr – 15 Sep 2026; order = (`NOWOrderNo`, trade date). `NOWOrderNo` alone is reused across days (948 numbers span more than one date); within a date it maps to one contract and side. `UniqueOrderIdentifier` is missing on 55 fills and spans dates for 5 tags, so it is not used as the key |
| Contract | (underlying, expiry, right, strike). Several orders in one contract count once |
| **0DTE** | trade date = the contract's expiry date |
| **1DTE** | trade date = the last trading session before expiry. Calendar = Breeze index sessions (22 Jun – 22 Oct) plus weekdays with fills in either export. It covers the NIFTY Monday expiry of 19 Oct, whose 1DTE session is Friday 16 Oct (3 calendar days) |
| Other buckets | `2+DTE`: none in either export. `non-session`: Algo 7's 8 Saturday fills |
| Session | (underlying, date) with at least one fill in the bucket. "Per session" = bucket total ÷ that count |
| Position role | Fills in time order against the running net position of each contract, starting at 0 at its first fill. **Short entry** = sell lots that increase a short; **short buyback** = buy lots that reduce a short; **hedge entry** = buy lots that increase a long; **hedge exit** = sell lots that reduce a long. An order that crosses zero is split. The role lots reconcile to traded lots exactly (maximum error 0) |
| Re-entry | Short-entry lots in a contract that already had a short buyback earlier in the same session. An association label, not a recovered trigger |
| Replacement | Short-entry lots within 60 s after a short buyback on the same underlying, session and right (the PR #5 window). An association label |
| ATM distance | ATM = d·round(S/d), S = previous completed minute's index close, d = 50 / 100; distance in strikes, + = OTM. Lot-weighted. Coverage: Algo 8 91–95 % of lots; **Algo 7 50 %** (no index bars before 22 Jun) |
| Turnover | Σ fill price × units, buys and sells |
| Actor scope | "All actors" is reported here. The CSV also has "main-book AlgoIds only" (it excludes the platform risk actor and hedge app; Algo 8 0DTE 48,002 lots vs 49,997) |

## 3. Algo 8: 1DTE vs 0DTE (all fills)

| Metric | 1DTE total | 1DTE per session | 0DTE total | 0DTE per session |
|---|---:|---:|---:|---:|
| Active sessions | 32 | | 33 | |
| Distinct contracts | 1,042 | 32.6 | 1,449 | 43.9 |
| Contract-days | 1,042 | 32.6 | 1,449 | 43.9 |
| Lots | 13,655 | 426.7 | 49,997 | 1,515.1 |
| Underlying units | 571,135 | 17,848 | 2,220,475 | 67,287 |
| Buy orders | 4,763 | 148.8 | 15,975 | 484.1 |
| Sell orders | 5,152 | 161.0 | 13,984 | 423.8 |
| CE / PE contracts | 488 / 554 | 15.2 / 17.3 | 694 / 755 | 21.0 / 22.9 |
| Distinct strikes (whole sample / per session) | 202 | 26.0 | 207 | 36.4 |
| Lots per contract (mean / median) | 13.1 / 9 | | 34.5 / 19 | |
| Average premium, lot-weighted | ₹91.47 | | ₹41.95 | |
| Premium turnover | ₹3.62 Cr | ₹11.3 L | ₹6.71 Cr | ₹20.3 L |
| ATM distance, all lots (median / 90th pct, strikes) | 9 / 22 | | 4 / 16 | |

Contract-days equal contracts because a contract has only one session in each bucket.
Lots are not comparable across underlyings (65 vs 20 units); units and turnover are.

**By population** (lots, contracts and turnover per bucket):

| Population | 1DTE contracts | 1DTE lots (per session) | 1DTE turnover | 0DTE contracts | 0DTE lots (per session) | 0DTE turnover | Median ATM distance 1DTE / 0DTE |
|---|---:|---:|---:|---:|---:|---:|---|
| Short positions (entries + buybacks) | 456 | 6,122 (191) | ₹3.48 Cr | 633 | 24,588 (745) | ₹6.27 Cr | 1 / 1 |
| Long hedges (entries + exits) | 596 | 7,533 (235) | ₹0.14 Cr | 1,018 | 25,409 (770) | ₹0.43 Cr | 16 / 9 |
| Short entries | 456 | 4,680 (146) | ₹2.44 Cr | 483 | 10,730 (325) | ₹2.62 Cr | 0 / 1 |
| Hedge entries | 596 | 6,141 (192) | ₹0.12 Cr | 764 | 10,645 (323) | ₹0.21 Cr | 16 / 8 |
| Short buybacks | 317 | 1,442 (45) | ₹1.04 Cr | 633 | 13,858 (420) | ₹3.66 Cr | 2 / 1 |
| Hedge exits | 284 | 1,392 (44) | ₹0.02 Cr | 998 | 14,764 (447) | ₹0.22 Cr | 18 / 10 |
| Re-entry (same contract) | 197 | 1,220 (38) | ₹0.66 Cr | 283 | 6,407 (194) | ₹1.44 Cr | 1 / 1 |
| Replacement (≤ 60 s, same side) | 95 | 189 (6) | ₹0.07 Cr | 387 | 3,982 (121) | ₹0.67 Cr | 1 / 1 |

Readings:

* **The D-1 book is built; the D0 book is managed.** On 1DTE, 76 % of short lots are entries (4,680 of 6,122). On 0DTE,
  buybacks (13,858) exceed new short entries (10,730), because 0DTE buybacks also close the 3,238 carried short lots.
  Cross-check: the 1,442 1DTE buyback lots equal the PR #3 lot ledger's D-1 exits.
* **Similar entry turnover, very different lots:** short-entry turnover is ₹2.44 Cr (1DTE) vs ₹2.62 Cr (0DTE) for 2.3× the
  lots, because D0 premiums are lower (lot-weighted short-entry premium ₹178 vs ₹74).
* **Wings sit further out on 1DTE** (median 16 vs 9 strikes OTM), as expected from a premium budget (HDG-02).
* Short entries stay at the money in both buckets (90 % / 82 % of lots within ±1 strike).

**Why 0DTE has more activity** ([`dte_decomposition.csv`](dte_decomposition.csv)). Lots per session = contracts per
session × orders per contract-day × lots per order:

| Factor | 1DTE | 0DTE | Ratio | Share of log(3.55) |
|---|---:|---:|---:|---:|
| Contracts per session | 32.6 | 43.9 | 1.35 | 24 % |
| … strikes per session | 26.0 | 36.4 | 1.40 | |
| … rights per strike | 1.26 | 1.22 | 0.97 | |
| Orders per contract-day | 9.5 | 20.7 | 2.17 | **61 %** |
| Lots per order | 1.38 | 1.67 | 1.21 | 15 % |
| Lots per session | 427 | 1,515 | 3.55 | 100 % |

So 0DTE is busier mainly because each contract is traded more often (more add / buyback / re-sale cycles per contract),
then because more strikes are touched, and least because of larger orders.

## 4. Algo 7: 0DTE only

| Metric | 0DTE total | 0DTE per session | 1DTE total |
|---|---:|---:|---:|
| Active sessions | 45 (23 NIFTY, 22 SENSEX) | | 1 (SENSEX) |
| Distinct contracts / contract-days | 1,697 | 37.7 | 1 |
| Lots / units | 43,328 / 1,852,105 | 962.8 / 41,158 | 100 / 2,000 |
| Buy / sell orders | 14,978 / 14,498 | 332.8 / 322.2 | 1 / 1 |
| CE / PE contracts | 844 / 853 | 18.8 / 19.0 | 1 / 0 |
| Distinct strikes (whole sample / per session) | 151 | 30.6 | 1 |
| Lots per contract (mean / median) | 25.5 / 18 | | 100 |
| Average premium, lot-weighted | ₹43.51 | | ₹2.62 |
| Premium turnover | ₹6.13 Cr | ₹13.6 L | ₹5,250 |

By population on 0DTE: short entries 10,589 lots, short buybacks 10,549, hedge entries 11,555, hedge exits 10,635,
re-entries 5,334, replacements 2,826. Short entries sit within ±1 strike of ATM for 78 % of lots, and wings sit at a
median of 9 strikes OTM. These ATM figures cover only 50 % of lots (sessions from 22 Jun).
The 1DTE bucket has **no short positions at all**, so Algo 7 cannot be used to study 1DTE behaviour.

## 5. Cross-algorithm reading (0DTE vs 0DTE only)

Algo 8's 0DTE session is busier than Algo 7's: 43.9 vs 37.7 contracts per session, 1,515 vs 963 lots and ₹20.3 L vs
₹13.6 L turnover. The extra lots come from more orders per contract-day (20.7 vs 17.4) and larger orders (1.67 vs 1.47
lots). Both sample windows only partly overlap (Algo 7 Apr–Sep, Algo 8 Jun–Oct). Algo 8's D0 also carries the D-1 book.

## 6. Risk-rule context: client-provided hypotheses

Added to the register as **RSK-05** and **RSK-06**, both "CLIENT-PROVIDED HYPOTHESIS". The existing rows RSK-01–RSK-04 are unchanged.

* **RSK-05: 20 % capital utilisation.** Not testable: the export contains no margin or capital fields.
* **RSK-06: 4 % expiry-day kill switch.** Each reading was tested separately on Algo 8's 35 cycles, using minute-close
  LTP MTM of the whole book against the first `s_` (cycle-stop module) fill ([`kill_switch_tests.csv`](kill_switch_tests.csv)):

| ID | Reading | Threshold | Stops caught (of 12) | Missed | False triggers (of 23) |
|---|---|---|---:|---:|---:|
| K0 | **Observed rule** (RSK-01), harness check | cumulative −₹1.33 L | **12** | 0 | **0** |
| K1 | 4 % × ₹2 Cr, D0-only | −₹8.0 L | 0 | 12 | 0 |
| K2 | 4 % × ₹2 Cr, cumulative | −₹8.0 L | 0 | 12 | 0 |
| K3 | 4 % × 20 % × ₹2 Cr (₹40 L), D0-only | −₹1.6 L | 8 | 4 | 2 |
| K4 | 4 % × ₹40 L, cumulative | −₹1.6 L | 2 | 10 | 0 |
| K5 | 4 % × 20 % × ₹1 Cr per index, D0-only | −₹0.8 L | 10 | 2 | 5 |
| K6 | same, cumulative | −₹0.8 L | 12 | 0 | 6 |
| K7 | 4 % of gross body premium sold in the cycle, cumulative | dynamic | 12 | 0 | 17 |
| K8 | 4 % of gross body premium sold on D0, D0-only | dynamic | 10 | 2 | 13 |
| K9 | D0 drawdown from the D0 peak ≥ ₹1.6 L | −₹1.6 L | 4 | 8 | 12 |
| K10 | Context: `Info.txt` 1 % × ₹2 Cr on expiry day (RSK-03) | −₹2.0 L | 2 | 10 | 2 |

* Every "expiry-day only" reading misses the D-1 stop (NIFTY, stopped 31 Aug for the 1 Sep expiry). Every one also
  reacts to D0-only losses that the algo did not stop on: SENSEX 9 Jul fell −₹2.16 L on D0 but only −₹0.16 L cumulative,
  and was not stopped. The observed stop is therefore on cumulative cycle MTM, not on expiry-day P&L.
* The observed −₹1.33 L lies between the ₹0.8 L and ₹1.6 L readings. It equals ≈ 3.3 % of ₹40 L or 0.67 % of ₹2 Cr.
  That is arithmetic, not evidence of either base.
* **Conflict of sources:** `Info.txt` gives "4 %" as a *carry-forward* SL and "1 %" as the expiry-day rule. The verbal
  statement gives "4 %" as the expiry-day kill switch. Neither wording matches the data. Both remain recorded as stated.

## 7. Evidence and data limitations

1. Only **fills** are observed: no cancels, rejects, margin or decision logs. Order counts are filled orders.
2. Lot identity is fungible. Roles use the net position, which does not depend on an ownership convention, but it
   cannot say which entry a buyback closes. 0DTE buybacks mix carried and same-day shorts.
3. Re-entry and replacement are timing and contract-history labels, not causes, and they overlap with scheduled entries.
4. Algo 7: there is no index data before 22 Jun, so ATM distance covers 50 % of its lots. Its 1DTE sample is 1 session,
   and the 4 Jul Saturday fills (non-standard AlgoIds, missing order tags) are unexplained.
5. The two exports have different clients, capital, periods (Apr–Sep vs Jun–Oct) and partly different market regimes,
   so cross-algo differences are descriptive.
6. The kill-switch tests use minute-close marks. The real trigger is intraminute (RSK-01), so a cycle whose MTM comes within a
   few thousand rupees of a threshold can be misclassified. The K0 harness check reproduces all 12 stops with 0 false triggers at
   minute resolution, but individual K-row counts can still move by one or two cycles.
7. Every session has been inspected before. All findings are in-sample descriptions.

## 8. Recommendation

| Option | Assessment |
|---|---|
| **Include both 1DTE and 0DTE for Algo 8 (recommended)** | The strategy is defined across both: 32 / 35 cycles have a 1DTE build, 817 contracts and 3,238 short lots carry into 0DTE, and the cycle stop is on cumulative D-1 + D0 MTM. Dropping either day would break the position state the other day depends on. Report every metric **by bucket**, because the two days behave differently (build vs manage, premium ₹178 vs ₹74, wings 16 vs 9 strikes OTM, 2.2× more orders per contract on 0DTE) |
| 0DTE only | Loses the BTST carry, which earlier work found to be the source of the gross P&L (carry of sold options +₹31.1 L), and orphans the carried book |
| 1DTE only | Loses 79 % of Algo 8's lots and the whole exit engine (Clock B, salvage, final flatten) |
| **Algo 7** | Use for **0DTE only**, as a cross-check of shared engine behaviour (same platform and AlgoIds). It provides no 1DTE evidence |

Decisions needed before Stage 2: (a) accept these bucket and role definitions, or amend them; (b) confirm that Rahul's
two statements refer to Algo 8 (GKOHNP140), as assumed here.
