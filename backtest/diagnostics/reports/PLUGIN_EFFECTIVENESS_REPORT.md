# Plugin Effectiveness Report

Source: `run_plugin_engine.py`, `plugin_effect.py` → `results/plugin_effectiveness.csv`, `plugin_helped_hurt.csv`, `plugin_cycles_*.csv`, `cut_timing.csv`. Engine runs on OOS cycles for the four non-frozen variants were executed into a **separate** directory (`results/engine/HOLD_SETTLE_DXOOS/`, git-ignored); original engine pickles untouched. The C++ parity check was **not** re-run for these OOS diagnostics (parity was verified earlier on 13,525 engine runs; same plugin code). Code executed, outputs observed.

> **Scope note (OOS protection).** All variants use the **frozen thresholds** (cut trigger 20000 bp, fraction 10000 bp, SHORT legs, 1 cut per leg; re-entry cooldown 1800 s). I did **not** sweep thresholds on OOS and I am **not** selecting anything from these OOS numbers. They are descriptive, and the frozen configuration is unchanged.

"Re-entry only" is not separable: re-entry acts only on legs that a cut has closed. The separable comparisons are plain / cut-only / cut + re-entry / cut + re-entry + band, each with or without capital stops.

## 1. Results (net ₹ / Sharpe / max drawdown ₹ / worst cycle ₹)

| Configuration | IS net | IS Sharpe | OOS net | OOS Sharpe | OOS max DD | OOS clean net | OOS exposed net | Orders OOS | Cycles acted OOS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Plain hold** | 497,091 | 1.10 | **218,329** | 0.69 | −373,160 | +38,687 | 179,642 | 400 | 0 |
| Cut only | 407,814 | 1.10 | −137,543 | −0.50 | −402,576 | −221,394 | 83,850 | 443 | 43 |
| Cut + re-entry (no band) | 444,523 | 1.01 | 121,531 | 0.40 | −450,924 | −85,043 | 206,574 | 483 | 43 |
| Cut + re-entry + band (**frozen**) | 520,143 | 1.26 | 67,163 | 0.22 | −455,512 | −114,188 | 181,351 | 480 | 43 |
| Cut only + capital stop | 209,241 | 0.64 | 49,904 | 0.20 | −294,447 | −86,925 | 136,828 | 516 | 47 |
| Capital stop only | 173,594 | 0.44 | 101,770 | 0.40 | −266,246 | +25,984 | 75,786 | 496 | 24 |

IS max DD: plain −204k, cut-only −158k, frozen −173k, cut+stop −166k, stop-only −256k.

## 2. Helped vs hurt, only on cycles where the plugin acted (net Δ vs plain hold)

| Configuration | Sample | Acted | Helped | Hurt | Sum helped | Sum hurt | **Net Δ** | Worst cycle (hold → config) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Cut only | IS | 64 | 28 | 36 | +450k | −539k | −89k | −89.5k → −78.6k |
| Cut only | OOS | 43 | 23 | 20 | +345k | −701k | **−356k** | −124.2k → −120.4k |
| Cut + re-entry (no band) | OOS | 43 | 18 | 25 | +119k | −216k | −97k | −124.2k → −126.7k |
| Frozen (with band) | IS | 64 | 28 | 36 | +215k | −191k | **+23k** | −89.5k → −96.0k |
| Frozen (with band) | OOS | 43 | 18 | 25 | +96k | −247k | **−151k** | −124.2k → −126.7k |
| Frozen | OOS clean | 28 | 10 | 18 | +69k | −221k | −153k | |
| Capital stop only | OOS | 24 | 10 | 14 | +252k | −369k | −117k | −79.7k → −24.7k (in acted cycles) |

## 3. What the plugins did (answers)

| Question | Finding |
|---|---|
| Positions cut | 64 of 175 IS cycles and 43 of 100 OOS cycles had at least one engine action; each cut leg is bought back whole (fraction_bp 10000). |
| Losses avoided vs recoveries missed | Cut-only: in OOS, helped 23 cycles (+₹345k) and hurt 20 (−₹701k): a loser costs on average 2.3× what a winner saves. Cuts realise a loss at a doubled option price; the cycles that then reverse (premium decays after the spike) forfeit the recovery. |
| **Why cuts can't protect the worst cycle** | The worst cycles lose mostly *before* the first evaluation: first plugin tick is D0 09:16. NIFTY 2026-02-03 opened with the short call at ₹938.7 vs ₹158.5 sold (already −₹152k); the cut bought back at ₹943 and re-entered at ₹937 30 minutes later: net −₹126.7k vs −₹124.2k hold. SENSEX 2026-03-19: cut at ₹1,184, resold at ₹1,343: −₹70.3k vs −₹79.7k (small help). NIFTY 2026-11-03: −₹60.7k vs −₹69.4k (small help). 70 % of cuts fire on D0 and 26 % within the first five minutes of D0 (OOS): they are reacting to the overnight gap, not preventing it. |
| When re-entry helped / hurt | Re-entry adds +₹259k over cut-only in OOS (19 cycles helped, 21 hurt; `plugin_effect.py` output) and +₹37k in IS. It re-enters at the ~doubled price, i.e. it **restores the short-vol position at a higher premium after the gap**. In IS the price-band condition adds +₹76k vs unbanded (13 helped / 9 hurt); in OOS the band **subtracts ₹54k** (2 helped / 4 hurt, only 6 cycles changed). The band's effect is based on 6 OOS cycles and is not distinguishable from noise. |
| Turnover and cost | Cut variants add ≈1–2 orders per acted cycle: OOS orders 400 → 480 (+20 %), friction (slippage+costs) ₹40.1k → ₹70.7k (+₹30.6k) for the frozen configuration. |
| Drawdown | Cuts did **not** reduce drawdown: OOS max DD −₹373k (plain) → −₹456k (frozen). Capital stops did: −₹266k stop-only, −₹294k cut+stop, at the cost of lower IS and OOS net (IS −₹323k, OOS −₹117k vs plain for stop-only). |
| Sharpe | Frozen: IS 1.26 vs 1.10 (+0.16, **inside noise**); OOS 0.22 vs 0.69; clean −0.51 vs +0.17. No plugin configuration improves OOS Sharpe over plain hold. |
| Is exposure reduction = usefulness? | No. Exposure was reduced (shorter holding, 24–47 acted cycles) but net P&L fell in 5 of 5 OOS comparisons; the drawdown improved only for capital stops. |

## 4. Interpretation (with status)
* **Established:** none of the plugin configurations beats plain hold OOS; the frozen configuration's OOS P&L is ₹151k below plain hold and its clean-OOS P&L is −₹114k.
* **Established (decomposition):** the worst-cycle loss is mostly already incurred overnight, and the plugins' first look is at D0 09:16.
* **Plausible, not established:** that cut/re-entry has *no* positive expected value rather than "worse than hold in this sample". IS shows +₹23k for the frozen configuration against ₹497k plain, a gain of 4.6 %, inside noise (the in-sample "improvement" selected the best of 18 configurations).
* **Caveat:** the plugin analysis uses only one set of frozen thresholds; I cannot say whether other settings would behave differently, and — per the rules — did not look.
