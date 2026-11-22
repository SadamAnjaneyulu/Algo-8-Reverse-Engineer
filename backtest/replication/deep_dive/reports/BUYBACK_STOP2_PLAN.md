# D-1 buy-back — stop indicators on losing positions: plan (second pass)

*Written before the tests. In-sample, D-1 of 32 cycles. The user's premise: buy-backs happen only in loss (profitable shorts are held overnight), and the trigger may be premium-based **and/or** market-based (stop indicators). Checked first: 87% of buy-back orders have the cheapest open lot in loss at the decision price (89% on fills). The other 13% (all lots on the contract in profit) are analysed separately.*

## Design
* **Population (gate):** contract-minutes where the cheapest open lot is in loss, meaning the previous close is above its entry decision price. A variant uses the current minute's high.
* **Label:** a buy-back on the contract in this minute. Scoring allows ±1 minute.
* **Crossing semantics:** for each indicator, test both the **state** (condition true) and the **first crossing** (true now, false in the previous minute for this lot). A real stop fires on the crossing.

## Stop indicators (all causal: completed bars up to the previous minute; "against" = the direction that hurts this right: up for short calls, down for short puts)
* **Premium (lot):** ratio to entry (1.2–2.0); loss in premium points; loss in multiples of the premium's own ATR(14); trailing (price ÷ lowest price since entry).
* **Spot since entry:** adverse spot move since the lot's sale in strike steps, in ATR(14) units, and in % of spot.
* **Trailing / volatility stops on the spot:** Chandelier, i.e. spot beyond the best price since entry plus k × ATR(14), k = 1–4; Supertrend(10, 3) and (7, 2) flipping against; Parabolic SAR (0.02, 0.2) flipping against.
* **Breakouts against:** Donchian 20 / 60 break; Bollinger(20, 2) band break.
* **Trend / momentum:** EMA 9/21 cross against; RSI(14) above 70 (calls) or below 30 (puts); 3- and 5-minute premium speed (from the first pass).
* **Book:** the right's total premium ratio, and the whole-book MTM in ₹ (from the first pass).

## Scores
* AUC; hazard by bin.
* Out-of-fold single-indicator rule F1 (threshold or k chosen on the other cycle half), separately for state and crossing.
* Best two-indicator AND/OR rules, out-of-fold.
* The winner goes into the free-running simulator and replaces the current stop, with all else unchanged.

## Decision rule
* An indicator "is the stop" if its out-of-fold crossing-rule F1 beats the premium-ratio rule by ≥ 0.05 in both halves.
* All tested indicators are reported (multiple testing is acknowledged).
* The profit-side 13% is analysed descriptively.
