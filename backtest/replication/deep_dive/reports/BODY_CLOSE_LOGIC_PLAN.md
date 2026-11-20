# Buy-back logic: single vs combined, positions below 1.2×, and what explains buy-backs below 1.2× — plan, written before the tests

**Questions.** (1) Between 1.2× and 1.7× premium, are the CE and PE of a straddle bought back **together** or **individually**? (2) What happens at the end of D-1 to positions that never reached ~1.2× — closed on D-1 or carried? (3) What triggers a **single-leg** buy-back and what triggers a **combined** buy-back? (4) Do buy-backs happen below 1.2× and, if so, on what basis?

**Definitions.** Reference price for a buy-back order = decision-time price recovered from its limit (limit ÷ 1.15). Entry references (three, because lot ownership inside a strike is unobserved): *average* of open body entries at the strike; *cheapest open entry* (lowest-entry-first convention, which earlier work found to track stop buy-backs); *oldest open entry* (FIFO). Ratio = decision price ÷ entry reference. **Paired buy-back** = a buy-back of the other right at the **same strike** within ±3 s; **partnered** = any buy-back of the other right within ±3 s.

**Tests (D-1 primary, D0 secondary).**
A. Order-level table of every body buy-back (ratio under the three references, pairing, partner's ratio, time held, time of day, fully/partially emptying the strike, re-sell within 60 s).
B. Share of paired vs single buy-backs by ratio class; for paired ones, the two legs' ratios (is one leg high and the other low?).
C. Trigger comparison on a strike-level contract-minute panel (both rights short at the same strike): AUC of own-leg ratio, other-leg ratio, max of the two, straddle ratio (sum of prices ÷ sum of entries) for (i) single-CE, (ii) single-PE, (iii) paired buy-backs; LOCO incremental value and permutation null.
D. Positions at the end of D-1: for every short strike-position, the highest ratio reached (cheapest-entry reference) and whether it was closed on D-1 or carried; carried share by ratio bin.
E. Buy-backs below 1.2×: classify mutually exclusively — partner-triggered (the other leg of the straddle was at ≥ 1.2×), end-of-day (≥ 15:10), roll (re-sold within 60 s), strike clean-up (empties the strike), other — and test whether "other" has any single-variable signal.
F. Buy-back episodes: lots per episode, spacing (is a buy-back also dripped in 1-lot orders?).

**Decision rules fixed now.** "Combined trigger" is supported only if the paired-event AUC of a combined variable (max or straddle ratio) beats every single-leg variable by a bootstrap-CI-excluding-0 margin; the 1.2× level is called a threshold only if the hazard shows a step of ≥ 3× between adjacent bins under the cheapest-entry reference. In-sample, observational; no trading rule recommended.
