"""Builds PHASE1_RULE_REGISTER_FINAL.{csv,md}: every Gate 1 row with its class at Gate 1 and its class after Phase 1, what moved and why. Classes change ONLY where a gate produced evidence; honesty over progress."""
import pandas as pd
G1 = pd.read_csv('PHASE1_RULE_CLASSIFICATION.csv').set_index('id')
ROWS = {  # id: (final class, what Phase 1 changed, evidence, what is still missing)
 'D1-01': ('Unresolved', 'nothing', 'no-trade days are not in the export', 'full list of eligible expiries and no-trade rule'),
 'D1-02': ('Partial', 'nothing new: Gates 3b/3c studied the protective wings and lump, not the closing of the opening wings', 'PHASE1_GATE3_SUMMARY.md', 'closing moment, SENSEX distance change cause'),
 'D1-03': ('Decoded', 'delayed depth sizing rejected (2D); timetable stands (2,086 of 2,112 scheduled straddles matched in B1)', 'PHASE1_GATE2D_RESULT.md', 'timetable is learned per version, not derived'),
 'D1-04': ('Unresolved', 'delayed sizing rejected (2D)', 'PHASE1_GATE2D_RESULT.md', 'repeat entries inside a candle-side; sizing set inside the minute'),
 'D1-05': ('Unresolved', 'solo trigger: V01 book condition and 8 further variants rejected (2A); H6 premium trigger tested and rejected at the decision level in the final loop (F1 0.460 vs 0.437, interval includes 0); trigger Partial, count and timing data-limited', 'PHASE1_GATE2A_RESULT.md, PHASE1_LOOP2_RESULT.md', 'tick path'),
 'D1-06': ('Unresolved', 'feed fidelity tested (C1 diagnostic, 198 of 241 spurious late fires removed) but late recall 0.12-0.15; regime gate rejected', 'PHASE1_GATE2C_RESULT.md', 'late-sale tracker (ticks); G1b untested'),
 'D1-07': ('Unresolved', 'nothing supported', 'PHASE1_GATE2D_RESULT.md', 'batch triggers'),
 'D1-08': ('Partial', 'engine strike rule stands: exact 0.50 with real context (0.25 in F); S2 +0.034 [0.008, 0.064] not enough; S8/S9 tested', 'PHASE1_GATE2B_RESULT.md', 'decision-time variable'),
 'D1-09': ('Unresolved', 'depth sizing rejected earlier and in 2D', 'PHASE1_GATE2D_RESULT.md', 'margin and capital data'),
 'D1-10': ('Partial', 'quantity confirmed earlier; timing/strike unchanged', 'PHASE1_GATE3_SUMMARY.md', 'sub-minute timing'),
 'D1-11': ('Partial', 'W1 0.411 / W2 0.413 vs chance 0.262: weak release model', 'PHASE1_GATE3BC_RESULT.md', 'which wing lot is released'),
 'D1-12': ('Unresolved', '54.5% of missing buy-backs are upstream (U1/U2); independent gap 163 orders; K1-K6 none supported', 'PHASE1_GATE3A_RESULT.md', 'intrabar touches; real trigger for half of the events'),
 'D1-13': ('Unresolved', 'lump side 0.93 decoded; size unexplained by position', 'PHASE1_GATE3BC_RESULT.md', 'margin and capital data'),
 'D1-14': ('Partial', 'nothing supported (2C); final loop: 7 of 8 closing bursts start before the 15:30 candle completes', 'PHASE1_GATE2C_RESULT.md, PHASE1_LOOP2_RESULT.md', 'closing-auction regime B; decision time of body orders'),
 'G1b': ('Candidate', 'final loop: original condition not causal for 7 of 8 bursts; causal analogue (minute 369) 6/8, p 0.0089, precision 0.60: plausible but unconfirmed; excluded from the baseline; no engine change', 'PHASE1_LOOP2_RESULT.md section 4', 'decision rule and time of body orders; 8 post-observation events'),
 'D1-15': ('Partial', 'cycle stop rule CONFIRMED ON THE REAL BOOK in D-1 and D0: cumulative MTM, minute close; 12 of 12 stops, 0 false alarms with the CORRECTED constant 1.25 lakh (interval (1.2177, 1.2902]; the earlier 1.20 false-alarmed on two D-1 sessions); D0 engine uses 1.25; free-running D-1 stop in the engine REJECTED (4 false stops, scheduled straddles 2,046 < 2,076); session vs cycle scope not separable in D-1; timing from completed bars not recoverable', 'PHASE1_LOOP2_RESULT.md section 2, outputs/phase1/9/B_*', 'ticks'),
 'D1-16': ('Confirmed', 'one_lot_v2 execution convention accepted (user decision); guard counts decisions', 'PHASE1_MASTER_GATE_REGISTER.md section 13', ''),
 'D1-17': ('Unresolved', 'era boundary and timetable versions used; regime B (after 7 Dec 2026) unobservable', 'PHASE1_GATE5C_RESULT.md', 'post-7-Dec logs'),
 'D0-01': ('Decoded', 'unchanged; part of D0-C and LOCO-stable', 'PHASE1_GATE7_RESULT.md', 'off-grid pairs'),
 'D0-02': ('Confirmed', 'unchanged', '', ''),
 'D0-03': ('Partial', 'unchanged; opening solo sells (485 lots in three minutes) not predictable', 'D0_OPEN_ROLL.md, PHASE1_GATE5D_RESULT.md', 'tick path'),
 'D0-04': ('Unresolved', 'stop 1.4x and take-profit 0.1x identical in 30 of 30 LOCO folds (Decoded, stable); bursts, carried-lot and other buy-backs unresolved; class F1 0.33', 'PHASE1_GATE7_RESULT.md, PHASE1_GATE5D_RESULT.md', 'burst membership; intrabar touches'),
 'D0-05': ('Unresolved', 'hedge quantity confirmed earlier; opening-long clock X3 REJECTED (count rule does not become order-level agreement)', 'PHASE1_GATE5C_RESULT.md', 'wing vs lump release choice; body-long strikes'),
 'D0-06': ('Decoded', 'post-auction clock: 90% of lots cleared at 15:14 in 9 of 10 cycles (the 15:30+ block is one cycle, SENSEX 2026-08-13 at 15:33); pre-auction: gradual flow plus a sweep at minute 364 (7 of 8); X1 (363) = experimental in-sample candidate, NOT a production default (production 359); CH1 fixed clock and CH2 staggered rejected (CH2 near-miss), CH3 state dependence not supported', 'PHASE1_GATE5B/5C_RESULT.md, PHASE1_LOOP2_RESULT.md section 3', 'regime B clearance (no real log); the 15:33 exception; spread'),
 'D0-07': ('Unresolved', 'nothing', '', 'margin and capital data'),
 'X-01': ('Partial', 'integrated D-1 + D0 engine run free (mode F), final configurations: combined keys F1 0.497 (forward) / 0.498 (historical) vs placebo 0.256; D-1 0.739, D0 0.395-0.397; not accurate order by order', 'PHASE1_GATE6_RESULT.md, PHASE1_LOOP2_RESULT.md section 7', 'order-level agreement far above the current level needs new data'),
 'X-02': ('Confirmed', 'evidence limits restated; no independent validation exists', 'PHASE1_GATE7_RESULT.md', 'post-freeze data'),
}
out = []
for i, (cls, chg, ev, miss) in ROWS.items():
    g = G1.loc[i]; out.append(dict(id=i, day=g.day, component=g.component, class_at_gate1=g.phase1_overall, class_after_phase1=cls, changed=(g.phase1_overall != cls), what_phase1_changed=chg, evidence=ev, still_missing=miss))
D = pd.DataFrame(out); D.to_csv('PHASE1_RULE_REGISTER_FINAL.csv', index=False)
moved = D[D.changed]; cnt = D.class_after_phase1.value_counts().to_dict(); c0 = D.class_at_gate1.value_counts().to_dict()
with open('PHASE1_RULE_REGISTER_FINAL.md', 'w') as f:
    f.write("# Phase 1 final rule register (Gate 8)\n\n*Generated by `build_phase1_final_register.py` from `PHASE1_RULE_CLASSIFICATION.csv` (Gate 1) and the gate reports. A class moved only where a gate produced evidence. Evidence label for every row: historical reproduction on development cycles; no independent validation exists. Nothing committed.*\n\n")
    f.write(f"**Overall classes, Gate 1 -> after Phase 1 (27 rows):** Confirmed {c0.get('Confirmed',0)} -> {cnt.get('Confirmed',0)}; Decoded {c0.get('Decoded',0)} -> {cnt.get('Decoded',0)}; Partial {c0.get('Partial',0)} -> {cnt.get('Partial',0)}; Candidate {c0.get('Candidate',0)} -> {cnt.get('Candidate',0)}; Unresolved {c0.get('Unresolved',0)} -> {cnt.get('Unresolved',0)}.\n\n**Rows that moved ({len(moved)}):** " + ', '.join(f"{r.id} ({r.class_at_gate1} -> {r.class_after_phase1})" for r in moved.itertuples()) + ".\n\n")
    f.write("| ID | Day | Component | Gate 1 | After Phase 1 | What Phase 1 changed | Evidence | Still missing |\n|---|---|---|---|---|---|---|---|\n")
    for r in D.itertuples(): f.write(f"| {r.id} | {r.day} | {r.component} | {r.class_at_gate1} | **{r.class_after_phase1}** | {r.what_phase1_changed} | {r.evidence} | {r.still_missing} |\n")
print(c0, cnt, [ (r.id, r.class_at_gate1, r.class_after_phase1) for r in moved.itertuples()])
