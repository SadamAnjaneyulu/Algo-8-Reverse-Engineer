# Research limitations and final conclusions
## What was tested
The existing engine's plugin framework (cut, re-entry, stop) on real NIFTY and SENSEX D-1/D0 option data, fed with the Algo 8 observed basket structure, under an explicit execution-cost model, with a frozen configuration and a held-out final year.
## Blockers and unresolved items
1. **The engine has no entry rule.** The basket structure is the rulebook's *observed* pattern from June-October 2026, extrapolated to November 2023 onward (wing width, three lots per leg, 09:16 timing). If Algo 8 traded differently earlier, the results describe a hypothetical strategy.
2. **No bid/ask.** Fills are last-trade prices plus an assumed slippage; the spread of far wings is unobservable. 54% of NIFTY and 31% of SENSEX wings were substituted by a nearer strike because the nominal wing never traded.
3. **No settlement price** in the data; the official close comes from the 15:30 spot bar or Yahoo's daily close.
4. **Cost rates** other than the 2026 STT change are unverified; broker terms and margin are unknown (margin is a proxy). Return figures use the stated, unverified Rs 2 crore.
5. **Stop-loss interpretation.** "4% carry / 1% of capital" is defined here as 4% of the basket margin proxy and 1% of Rs 2 crore; this reading is a choice. The capital stop never helped in sample and is not part of either frozen configuration.
6. **Only D-1/D0 sessions** exist; 275 of 319 expected cycles are usable; SENSEX starts 2024-05-30 and lacks 35 expected expiries; open interest is not used. Cycles with outages, special sessions or missing contracts were excluded, which could bias results toward calmer weeks.
7. **Contamination.** 2026-06-22..2026-10-22 was inspected during reverse engineering. Treat the clean subset (64 cycles, of which only 5 are after the exposed window) as the only independent evidence, and note it is small.
8. **Statistical power.** 100 out-of-sample weekly cycles; results are dominated by a few cycles (98% of out-of-sample net comes from the best five). No significance test is claimed; the configuration grid (26) was searched on 175 cycles.
9. The engine evidence stamp says `SYNTHETIC_TEST_ONLY` by design; the files are labelled in their description.
## Conclusions
* The hold-to-expiry short-straddle-with-far-wings basket is slightly profitable in sample and break-even out of sample once the already-inspected window is removed; it is not robust to 3x slippage on the clean subset.
* The cut and re-entry plugins add no demonstrated value on this data; plain holding beat the selected plugin configuration out of sample and in walk-forward.
* The engine and its C++ twin are consistent with each other and with an independent ledger on real data; the infrastructure is ready for a richer basket-construction layer, but this test cannot say whether Algo 8 itself has an edge.
* Next steps if wanted: obtain real entry/exit rules or the Algo 8 fills for 2023-2025; replace last-trade prices with quotes; verify cost rates; extend data to other days to expiry.
