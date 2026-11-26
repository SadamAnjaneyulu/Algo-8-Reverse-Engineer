# Algo 8 — D0: burst buy-backs, the other buy-back types, and the body-stream longs

*Plan `D0_BURST_LONG_PLAN.md`, written before the tests (addendum lists the post-hoc steps). In-sample discovery on D0: 25 cycles, 14,910 minute cells (cycle × minute × right, j ≥ 1); every score is leave-one-cycle-out (LOCO) or forward. Figure: `figures/bl_d0w_summary.png`. Scripts `bl_d0w_*.py`.*

## 0. Result

**Coverage moves from 69% to 81% of D0 lots (rule found, or ranking gate met on unseen cycles). The 90% target is not reached.** What is still outside: 14% ranked below the gate or indicative, 5% unresolved. Lot-level reproduction (F1 0.39–0.45) does **not** change: none of the new findings is a rule the simulator can execute.

| tier | meaning | before | after |
|---|---|---|---|
| 1 | rule found (exact rule or ≥ 90% fit) | 63.5% | 63.5% |
| 2 | timing/ranking gate met on unseen cycles (AUC ≥ 0.85, CI lower bound > 0.82, forward ≥ 0.80, placebo < 0.65) | 5.3% | 17.8% |
| 3 | ranked below the gate, indicative (< 150 cells) or only with same-minute information | 21.8% | 14.2% |
| 4 | unresolved or not examined | 9.3% | 4.5% |

*Same tier definitions applied to both columns. The earlier "about 60 / 24 / 15" in chat used a looser judgement; the table above is the computed version.*

| question | answer | evidence |
|---|---|---|
| Can burst buy-backs be timed on unseen cycles? | **Yes at the ranking level, AUC 0.922** (CI 0.905–0.937, forward 0.899, within-cycle 0.865, placebo 0.587). But most of it is knowing *where buy-backs happen at all*: the "any buy-back" score alone ranks bursts at 0.905. Among buy-back cells, burst vs single is only **0.804** AUC. | Observed |
| Did ITM depth, side loss, lots at risk or a clock explain bursts? | **No.** Adding them to the existing families changes AUC by +0.003; time + ITM depth alone gives 0.77. H-B1, H-B2 and H-B4 are not supported as added information. | Observed |
| Which lots does a burst take? | **The biggest losers, not the deepest ITM.** Within a burst minute: unrealised loss AUC 0.83, price ÷ entry 0.80, ITM depth only 0.62; all lot features 0.89. A ranking by loss finds 43% of the lots taken in its top m (chance 13%), the full model 54%. **No threshold rule gives the set** (best F1 0.42, exact set in 0% of cells, count error 10 lots). | Observed; rule Unresolved |
| Other buy-back types | Stop-loss 0.933, take-profit 0.951, partner 0.912, burst member 0.903: **gate met**. Roll-out 0.842 (CI 0.812) and other 0.791: **not met**. | Observed |
| Body-stream longs: strike rule? | **No.** Best is a premium target of ₹3: exact 20% of lots (placebo 10%, bar 60%); fraction of ATM premium 7%; fixed OTM steps 8%. | Observed |
| Opening count of longs? | **No.** No book quantity beats the same-underlying median (exact 26%, error 3.5 lots; the best candidate 12%). | Observed |
| Long buys: when? | AUC 0.927 (forward 0.969), but most buys are the opening minutes. **After the opening (post-hoc): AUC 0.896** (CI 0.853–0.944, placebo 0.643, 111 positive cells, forward 0.949 on 29). The held-long state (price ÷ cost, OTM steps) lifts it from 0.81. Small sample. | Observed |
| Long sells: when? | **Not met.** Intraday AUC 0.831 (forward 0.789). The held-long state helps (+0.07), not enough. | Observed |
| 15:14 clearance of longs | 83.5% of the 1,936 longs open at 15:14 are sold; the kept ones are the cheap ones (median ₹0.20 vs ₹0.75). A price threshold gets 84.2% right against 83.5% for "sell all". | Observed |

## 1. Buy-back types: timing gate (cell = cycle × minute × right)

| outcome | best_set | auc | lo | forward | within_cycle | placebo | E_auc | gain_over_E | gate_strict |
|---|---|---|---|---|---|---|---|---|---|
| any buy-back | E + clock | 0.858 | 0.844 | 0.815 | 0.849 | 0.562 | 0.852 | 0.007 | met |
| burst (>= 5 lots) | ALL (E + lot state + clock) | 0.922 | 0.905 | 0.899 | 0.865 | 0.587 | 0.92 | 0.002 | met |
| stop-loss | E + lot state | 0.933 | 0.923 | 0.934 | 0.936 | 0.562 | 0.927 | 0.006 | met |
| take-profit | E existing families | 0.951 | 0.924 | 0.938 | 0.949 | 0.64 | 0.951 | 0 | met |
| partner | E + clock | 0.912 | 0.89 | 0.958 | 0.923 | 0.518 | 0.897 | 0.015 | met |
| roll-out | E + clock | 0.842 | 0.812 | 0.812 | 0.818 | 0.498 | 0.827 | 0.015 | not met |
| burst member | E + lot state | 0.903 | 0.877 | 0.87 | 0.865 | 0.586 | 0.9 | 0.003 | met |
| other | ALL (E + lot state + clock) | 0.792 | 0.753 | 0.78 | 0.79 | 0.511 | 0.788 | 0.003 | not met |

*The placebo shuffles the labels inside each cycle and is run for the **same set** as the score. Take-profit's placebo is 0.640, just under the 0.65 line, because its positives scale with the lots open; it passes by 0.01.*

### All sets

| outcome | set | auc_loco | lo | hi | within_cycle | forward_auc | placebo_auc | cells | positives |
|---|---|---|---|---|---|---|---|---|---|
| any buy-back | E existing families | 0.852 | 0.84 | 0.863 | 0.846 | 0.805 |  | 14910 | 1964 |
| any buy-back | E + lot state | 0.851 | 0.838 | 0.862 | 0.844 | 0.81 |  | 14910 | 1964 |
| any buy-back | E + clock | 0.858 | 0.844 | 0.873 | 0.849 | 0.815 |  | 14910 | 1964 |
| any buy-back | ALL (E + lot state + clock) | 0.856 | 0.84 | 0.874 | 0.85 | 0.815 | 0.572 | 14910 | 1964 |
| any buy-back | base + ITM depth only | 0.725 | 0.689 | 0.755 | 0.724 | 0.69 |  | 14910 | 1964 |
| burst (>= 5 lots) | E existing families | 0.92 | 0.898 | 0.932 | 0.875 | 0.912 |  | 14910 | 388 |
| burst (>= 5 lots) | E + lot state | 0.921 | 0.906 | 0.935 | 0.856 | 0.894 |  | 14910 | 388 |
| burst (>= 5 lots) | E + clock | 0.919 | 0.904 | 0.934 | 0.877 | 0.912 |  | 14910 | 388 |
| burst (>= 5 lots) | ALL (E + lot state + clock) | 0.922 | 0.905 | 0.937 | 0.865 | 0.899 | 0.587 | 14910 | 388 |
| burst (>= 5 lots) | base + ITM depth only | 0.772 | 0.735 | 0.804 | 0.761 | 0.713 |  | 14910 | 388 |
| stop-loss | E existing families | 0.927 | 0.918 | 0.936 | 0.929 | 0.932 |  | 14910 | 680 |
| stop-loss | E + lot state | 0.933 | 0.923 | 0.944 | 0.936 | 0.934 |  | 14910 | 680 |
| stop-loss | E + clock | 0.927 | 0.917 | 0.938 | 0.93 | 0.93 |  | 14910 | 680 |
| stop-loss | ALL (E + lot state + clock) | 0.933 | 0.923 | 0.943 | 0.936 | 0.935 | 0.558 | 14910 | 680 |
| stop-loss | base + ITM depth only | 0.76 | 0.731 | 0.788 | 0.782 | 0.741 |  | 14910 | 680 |
| take-profit | E existing families | 0.951 | 0.924 | 0.971 | 0.949 | 0.938 |  | 14910 | 351 |
| take-profit | E + lot state | 0.949 | 0.921 | 0.968 | 0.944 | 0.926 |  | 14910 | 351 |
| take-profit | E + clock | 0.95 | 0.919 | 0.971 | 0.949 | 0.937 |  | 14910 | 351 |
| take-profit | ALL (E + lot state + clock) | 0.949 | 0.928 | 0.968 | 0.946 | 0.926 | 0.656 | 14910 | 351 |
| take-profit | base + ITM depth only | 0.87 | 0.818 | 0.912 | 0.894 | 0.837 |  | 14910 | 351 |
| partner | E existing families | 0.897 | 0.864 | 0.922 | 0.9 | 0.926 |  | 14910 | 149 |
| partner | E + lot state | 0.896 | 0.864 | 0.924 | 0.901 | 0.922 |  | 14910 | 149 |
| partner | E + clock | 0.912 | 0.89 | 0.935 | 0.923 | 0.958 |  | 14910 | 149 |
| partner | ALL (E + lot state + clock) | 0.908 | 0.884 | 0.932 | 0.922 | 0.954 | 0.488 | 14910 | 149 |
| partner | base + ITM depth only | 0.773 | 0.717 | 0.84 | 0.805 | 0.792 |  | 14910 | 149 |
| roll-out | E existing families | 0.827 | 0.788 | 0.848 | 0.8 | 0.781 |  | 14910 | 505 |
| roll-out | E + lot state | 0.821 | 0.783 | 0.846 | 0.8 | 0.796 |  | 14910 | 505 |
| roll-out | E + clock | 0.842 | 0.812 | 0.866 | 0.818 | 0.812 |  | 14910 | 505 |
| roll-out | ALL (E + lot state + clock) | 0.839 | 0.807 | 0.86 | 0.818 | 0.821 | 0.491 | 14910 | 505 |
| roll-out | base + ITM depth only | 0.68 | 0.614 | 0.766 | 0.735 | 0.71 |  | 14910 | 505 |
| burst member | E existing families | 0.9 | 0.879 | 0.92 | 0.868 | 0.872 |  | 14910 | 236 |
| burst member | E + lot state | 0.903 | 0.877 | 0.924 | 0.865 | 0.87 |  | 14910 | 236 |
| burst member | E + clock | 0.9 | 0.872 | 0.92 | 0.871 | 0.871 |  | 14910 | 236 |
| burst member | ALL (E + lot state + clock) | 0.902 | 0.876 | 0.925 | 0.868 | 0.86 | 0.584 | 14910 | 236 |
| burst member | base + ITM depth only | 0.778 | 0.725 | 0.824 | 0.755 | 0.685 |  | 14910 | 236 |
| other | E existing families | 0.788 | 0.757 | 0.816 | 0.777 | 0.737 |  | 14910 | 540 |
| other | E + lot state | 0.786 | 0.758 | 0.82 | 0.779 | 0.733 |  | 14910 | 540 |
| other | E + clock | 0.79 | 0.757 | 0.83 | 0.783 | 0.779 |  | 14910 | 540 |
| other | ALL (E + lot state + clock) | 0.792 | 0.753 | 0.83 | 0.79 | 0.78 | 0.511 | 14910 | 540 |
| other | base + ITM depth only | 0.69 | 0.632 | 0.757 | 0.721 | 0.718 |  | 14910 | 540 |

## 2. Bursts at lot level

| feature | pooled_auc | within_cell_auc | precision_at_m_desc | cells | precision_at_m_asc |
|---|---|---|---|---|---|
| ITM depth (steps) | 0.678 | 0.617 | 0.195 | 386 | 0.057 |
| price / entry (prev close) | 0.763 | 0.798 | 0.472 | 386 | 0.032 |
| premium now | 0.659 | 0.609 | 0.191 | 386 | 0.063 |
| entry price | 0.391 | 0.251 | 0.052 | 386 | 0.369 |
| unrealised loss (lakh) | 0.784 | 0.825 | 0.434 | 386 | 0.023 |
| carried from D-1 | 0.389 | 0.365 | 0.054 | 386 | 0.141 |
| strike | 0.508 | 0.501 | 0.125 | 386 | 0.123 |
| lot id (older = lower) | 0.505 | 0.758 | 0.357 | 386 | 0.054 |
| ALL lot features (LOCO boosting) | 0.851 | 0.89 | 0.54 | 386 |  |

| rule | f1 | precision | recall | cells_exact_set | count_mae | param_median | cells |
|---|---|---|---|---|---|---|---|
| take every lot ITM >= k steps | 0.267 | 0.206 | 0.377 | 0 | 13.369 | 1 | 388 |
| take every lot with price/entry >= r | 0.417 | 0.398 | 0.438 | 0 | 9.75 | 1.3 | 388 |
| take every lot with premium >= p (Rs) | 0.28 | 0.192 | 0.512 | 0.003 | 20.059 | 80 | 388 |
| placebo: a random set of the true size | 0.219 |  |  |  | 0 |  | 388 |

*388 burst cells, 36,852 open-lot rows, 3,766 taken (10.2%). precision@m = the share of the m lots a ranking puts first that were really taken, m = the true count.*

## 3. Body-stream longs

### L1 strike rule (leave-one-cycle-out; placebo = the rule applied 15 minutes later)

| subset | rule | orders | exact | within1 | placebo_exact_plus15 | param_median | param_q25 | param_q75 | lots |
|---|---|---|---|---|---|---|---|---|---|
| all buy orders | premium target P* (Rs) | 939 | 0.204 | 0.364 | 0.101 | 3 | 3 | 3 | 981 |
| all buy orders | fraction of ATM premium | 939 | 0.07 | 0.169 | 0.067 | 0.048 | 0.048 | 0.048 | 981 |
| all buy orders | fixed OTM steps | 939 | 0.076 | 0.119 | 0.03 | 40 | 40 | 40 | 981 |
| opening (09:15-09:16) | premium target P* (Rs) | 567 | 0.24 | 0.39 | 0.083 | 3 | 3 | 3 | 567 |
| opening (09:15-09:16) | fraction of ATM premium | 567 | 0.1 | 0.189 | 0.079 | 0.05 | 0.05 | 0.05 | 567 |
| opening (09:15-09:16) | fixed OTM steps | 567 | 0.194 | 0.273 | 0.083 | 40 | 40 | 40 | 567 |
| intraday | premium target P* (Rs) | 372 | 0.135 | 0.336 | 0.123 | 3 | 3 | 3 | 414 |
| intraday | fraction of ATM premium | 372 | 0.027 | 0.188 | 0.058 | 0.025 | 0.025 | 0.025 | 414 |
| intraday | fixed OTM steps | 372 | 0.111 | 0.36 | 0.094 | 4 | 4 | 4 | 414 |
| NIFTY | premium target P* (Rs) | 304 | 0.22 | 0.452 | 0.157 | 2.75 | 2.75 | 2.75 | 305 |
| NIFTY | fraction of ATM premium | 304 | 0.207 | 0.426 | 0.164 | 0.058 | 0.058 | 0.058 | 305 |
| NIFTY | fixed OTM steps | 304 | 0.213 | 0.269 | 0.092 | 40 | 40 | 40 | 305 |
| SENSEX | premium target P* (Rs) | 635 | 0.154 | 0.348 | 0.092 | 3.25 | 3.25 | 3.25 | 676 |
| SENSEX | fraction of ATM premium | 635 | 0.089 | 0.22 | 0.047 | 0.018 | 0.018 | 0.018 | 676 |
| SENSEX | fixed OTM steps | 635 | 0.046 | 0.138 | 0.03 | 4 | 4 | 4 | 676 |

### L2 opening count

| candidate | n | exact | within2 | mae | rho |
|---|---|---|---|---|---|
| carried shorts on the right (S0) | 58 | 0 | 0 |  | -0.046 |
| carried longs on the right (L0) | 58 | 0 | 0 |  | -0.054 |
| carried shorts - longs (S0 - L0) | 58 | 0 | 0 |  | 0.122 |
| carried shorts both rights | 58 | 0.121 | 0.5 | 4.879 | 0.079 |
| baseline: median of the other cycles of the same underlying | 58 | 0.259 | 0.586 | 3.534 |  |

### L3 / L4 timing

| outcome | best_set | auc | lo | forward | placebo | within_cycle | E_auc | gain_over_E | gate |
|---|---|---|---|---|---|---|---|---|---|
| long buy | E + book + state of held longs | 0.927 | 0.889 | 0.969 | 0.644 | 0.933 | 0.879 | 0.048 | met |
| long sell (intraday) | E + book + state of held longs | 0.831 | 0.8 | 0.789 | 0.53 | 0.816 | 0.76 | 0.071 | not met |

| outcome | set | auc_loco | lo | hi | within_cycle | forward_auc | placebo_auc | cells | positives |
|---|---|---|---|---|---|---|---|---|---|
| long buy | E existing families | 0.879 | 0.82 | 0.936 | 0.881 | 0.945 |  | 14910 | 175 |
| long buy | E + book of shorts and longs | 0.874 | 0.803 | 0.942 | 0.887 | 0.949 |  | 14910 | 175 |
| long buy | E + book + state of held longs | 0.927 | 0.889 | 0.959 | 0.933 | 0.969 | 0.644 | 14910 | 175 |
| long buy | base + held-long state only | 0.913 | 0.865 | 0.958 | 0.922 | 0.972 |  | 14910 | 175 |
| long sell (intraday) | E existing families | 0.76 | 0.711 | 0.803 | 0.755 | 0.72 |  | 14910 | 333 |
| long sell (intraday) | E + book of shorts and longs | 0.774 | 0.73 | 0.811 | 0.779 | 0.715 |  | 14910 | 333 |
| long sell (intraday) | E + book + state of held longs | 0.831 | 0.8 | 0.857 | 0.816 | 0.789 | 0.53 | 14910 | 333 |
| long sell (intraday) | base + held-long state only | 0.772 | 0.738 | 0.804 | 0.752 | 0.775 |  | 14910 | 333 |

### After the opening minutes (post-hoc)

| outcome | set | auc | lo | hi | placebo_auc | positives | cells |
|---|---|---|---|---|---|---|---|
| y_long_buy_intra | E existing families | 0.815 | 0.729 | 0.895 | 0.639 | 111 | 14714 |
| y_long_buy_intra | E + book + state of held longs | 0.896 | 0.853 | 0.944 | 0.643 | 111 | 14714 |
| y_long_sell | E existing families | 0.751 | 0.705 | 0.802 | 0.517 | 315 | 14714 |
| y_long_sell | E + book + state of held longs | 0.831 | 0.794 | 0.858 | 0.485 | 315 | 14714 |

## 4. Coverage by class

| cls | lots | share | tier_before | tier_after | note |
|---|---|---|---|---|---|
| wing buy | 9370 | 0.1874 | 1 | 1 | gap S-L / excess rule, 94-97% exact given the body orders |
| wing sell | 9941 | 0.1988 | 1 | 1 | gap S-L / excess rule, 94-97% exact given the body orders |
| lump salvage | 952 | 0.019 | 1 | 1 | gap S-L / excess rule, 94-97% exact given the body orders |
| stop module | 3515 | 0.0703 | 1 | 1 | cumulative MTM stop; liquidates the whole book |
| sell: scheduled pair | 2105.25 | 0.0421 | 1 | 1 | met (causal) |
| sell: strangle pair | 1530.54 | 0.0306 | 1 | 1 | met (causal) |
| sell: counter-sell solo | 1753.7 | 0.0351 | 2 | 2 | met (causal) |
| sell: replacement solo | 1263.56 | 0.0253 | 3 | 3 | met with same-minute information only |
| sell: other solo | 484.025 | 0.0097 | 3 | 3 | met with same-minute information only |
| sell: far-OTM solo | 912.005 | 0.0182 | 2 | 2 | met (causal) |
| sell: extreme solo | 435.113 | 0.0087 | 3 | 3 | indicative (<150 cells) |
| sell: opening solo | 716.357 | 0.0143 | 3 | 3 | indicative (<150 cells) |
| sell: opening pair | 225.199 | 0.0045 | 3 | 3 | indicative (<150 cells) |
| sell: re-centre pair | 293.472 | 0.0059 | 3 | 3 | met with same-minute information only |
| sell: breakout pair | 146.736 | 0.0029 | 3 | 3 | indicative (<150 cells) |
| sell: other pair | 276.149 | 0.0055 | 4 | 4 | not met |
| sell: late solo | 47.893 | 0.001 | 3 | 3 | indicative (<150 cells) |
| buy-back: stop-loss | 3076.93 | 0.0615 | 3 | 2 | timing gate met |
| buy-back: roll-out | 1499.17 | 0.03 | 3 | 3 | timing gate not met |
| buy-back: burst member | 1343.18 | 0.0269 | 4 | 2 | timing gate met |
| buy-back: clearance | 2713.75 | 0.0543 | 1 | 1 | rule (D0_STOP_CLEAR) |
| buy-back: take-profit | 1015.72 | 0.0203 | 3 | 2 | timing gate met |
| buy-back: other | 1009.77 | 0.0202 | 4 | 4 | timing gate not met |
| buy-back: partner | 459.634 | 0.0092 | 3 | 2 | timing gate met |
| buy-back: cycle-stop window | 379.853 | 0.0076 | 1 | 1 | rule (D0_STOP_CLEAR) |
| long buy: opening (<= 09:20) | 724 | 0.0145 | 4 | 3 | timing = the opening minutes; strike and count rules not found |
| long buy: intraday | 340 | 0.0068 | 4 | 2 | LOCO AUC 0.896; 111 positive cells; small sample |
| long buy: after 15:09 | 152 | 0.003 | 4 | 4 | not examined as a class |
| long sell: clearance (>= 15:14) | 1246 | 0.0249 | 1 | 1 | 84% of longs open at 15:14 are sold; a price rule adds 0.7 points |
| long sell: intraday | 1250 | 0.025 | 3 | 3 | AUC 0.831, gate not met |
| hedge other + other | 819 | 0.0164 | 4 | 4 | not examined |

### What it would take to reach 90%

| class still outside | share of D0 lots | why |
|---|---|---|
| buy-back: roll-out | 3.0% | tier 3: timing gate not met |
| sell: replacement solo | 2.5% | tier 3: met with same-minute information only |
| long sell: intraday | 2.5% | tier 3: AUC 0.831, gate not met |
| buy-back: other | 2.0% | tier 4: timing gate not met |
| hedge other + other | 1.6% | tier 4: not examined |
| long buy: opening (<= 09:20) | 1.4% | tier 3: timing = the opening minutes; strike and count rules not found |
| sell: opening solo | 1.4% | tier 3: indicative (<150 cells) |
| sell: other solo | 1.0% | tier 3: met with same-minute information only |
| sell: extreme solo | 0.9% | tier 3: indicative (<150 cells) |
| sell: re-centre pair | 0.6% | tier 3: met with same-minute information only |

The classes above sum to 18.7%; reaching 90% needs about 8.7% more. The largest pieces are classes whose only high score uses **same-minute information** (replacement solo, other solo, re-centre pair: not available when the order is decided) or that need the **tick path** (counts, exact seconds).

## 5. Free run
* **Unchanged.** No rule from this step can be executed by the simulator: the burst timing is a ranking (the simulator needs a trigger), the burst size and lot selection have no rule, the long strike and opening count have no rule. Lot F1 stays 0.41 / 0.45 / 0.39 (`D0_FREE_RUN`, `D0_SIZING`). A model-driven free run (events from a score threshold) would need every feature recomputed on simulated state and is not done here.

## 6. Adversarial read

* **A ranking is not a trigger.** AUC 0.92 for bursts means the right minutes are ranked above the wrong ones; at the best thresholds earlier work found precision 44% and recall 32% (`D0_PAIR`). Among buy-back cells the burst call is 0.80.
* **The tier-2 classes are model scores, not rules.** They pass an unseen-cycle test inside one period; they are not statements about other years.
* **Burst size and lot selection stay open** and are what the backtest needs. Taking the biggest losers first is supported (within-minute AUC 0.8), the count is not.
* **Small samples:** intraday long buys 111 positive cells (29 in the forward test), partner 149, burst 388. CIs are wide where cells are few.
* **Everything here is in-sample discovery on 32 cycles from one period.** Nothing has been checked on cycles outside them.
* **The 90% was a coverage target, and coverage is not accuracy.** Even at 90% coverage the lot-level match would stay near the F1 reported, because counts and seconds are not recovered.

## Addendum — post-hoc steps (not pre-registered)
* Placebo re-run for the **best set** of each outcome (the first gate table used the placebo of the ALL set only).
* Conditional burst-vs-single AUC among buy-back cells, added after seeing AUC 0.92.
* Long buys and sells **after the opening minutes (j ≥ 5)**, added after seeing that most long buys are in the opening minutes; forward AUC for that subset (0.949 on 29 positives, 0.768 for sells) was computed once, inline.
* Burst lot ranking by loss and price ÷ entry added to the lot-level test after ITM depth failed (the plan listed ITM depth, ratio, premium, age and origin; loss was derived from ratio and entry).
