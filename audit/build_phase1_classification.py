"""Phase 1 Gate 1: re-classify every row of the Phase A rule register into the Phase 1 evidence taxonomy (Confirmed / Decoded / Partial / Candidate / Unresolved) per COMPONENT, record whether the gap is feasible to investigate with existing data (and which gate does it) or irreducible without new data. Generated from ALGO8_PHASE_A_RULE_REGISTER.csv (never retyped)."""
import pandas as pd, os
HERE = os.path.dirname(os.path.abspath(__file__)); R = pd.read_csv(f'{HERE}/ALGO8_PHASE_A_RULE_REGISTER.csv')
ORDER = ['Confirmed', 'Decoded', 'Partial', 'Candidate', 'Unresolved']                       # certainty order, most to least
# (components as (class, text) tuples, gate that investigates the feasible part, irreducible without new data)
A = {
 'D1-01': ([('Confirmed', 'cycle definition'), ('Unresolved', 'no-trade filter')], 'none', 'no-trade days are not in the export'),
 'D1-02': ([('Confirmed', 'opening wings form, size, strike distance'), ('Partial', 'when they are closed (G4: 84% within 10 s of a buy-back)')], 'G3', 'SENSEX distance change cause'),
 'D1-03': ([('Confirmed', 'fixed timetable, ATM strike'), ('Decoded', 'lots per slot (modal ladder)')], 'G2D', 'timetable is learned per version, not derived'),
 'D1-04': ([('Decoded', 'two-candle breakout pairs'), ('Unresolved', 'repeat entries inside a candle-side (49 of 274)')], 'G2D', 'why the gate opens at 10:30'),
 'D1-05': ([('Decoded', 'side and a spot-ladder description'), ('Partial', 'book-state gate (own side in profit, other losing): P1-2A V01 removes 75% false solo fires but 74 true ones, rejected under A1/A3/A4'), ('Unresolved', 'spacing, count and timing (H1, H2, H3 contradicted at order level P1-2A; tick-level tracker H5 not testable)')], 'G2A (done: rejected, data-limited)', 'tick path (lots per drip)'),
 'D1-06': ([('Unresolved', 'late solo regime after 15:00')], 'G2C', 'no decision times'),
 'D1-07': ([('Unresolved', 'deep-OTM batches (3 cycles)')], 'G2D', 'too rare to decode'),
 'D1-08': ([('Decoded', 'pair strikes (ATM of previous close)'), ('Partial', 'solo and late strike selection')], 'G2B', 'decision-time premiums exist only for traded contracts'),
 'D1-09': ([('Confirmed', 'single-lot child orders, freeze split'), ('Partial', 'lots per decision'), ('Unresolved', 'capital or margin dependence')], 'G2A', 'margin / capital records'),
 'D1-10': ([('Confirmed', 'wing buys: quantity = gap, about 4 s after the body order'), ('Partial', 'exact strike reference (2.5% of ATM)')], 'G3', ''),
 'D1-11': ([('Confirmed', 'wing release quantity and timing'), ('Partial', 'which wing is released')], 'G3', ''),
 'D1-12': ([('Decoded', 'graded premium stop (1.6x of own entry on the minute high)'), ('Unresolved', 'other half of buy-backs (no recoverable trigger at minute resolution)')], 'G3', 'tick data for intrabar touches'),
 'D1-13': ([('Confirmed', 'lump side and clock regimes'), ('Partial', 'lump strike'), ('Unresolved', 'lump size')], 'G3', 'capital / risk records'),
 'D1-14': ([('Partial', 'late D-1 sales: side replicated, timing and strike partial')], 'G2C', 'decision times'),
 'G1b': ([('Candidate', 'closing pairs at the 15:30 candle-end close (post hoc, excluded from the baseline)')], 'G2C', 'independent confirmation needs new cycles'),
 'D1-15': ([('Decoded', 'cumulative MTM cycle stop, threshold range Rs 1.2-1.36 lakh'), ('Unresolved', 'exact constant and timing')], 'G3', 'tick data'),
 'D1-16': ([('Confirmed', 'order mechanics (one lot, DAY/IOC, limit at LTP +/-15%)')], 'G3', 'acknowledgements, cancels, rejects not in the export'),
 'D1-17': ([('Confirmed', 'observed version and regime dates'), ('Unresolved', 'cause and future changes')], 'G8', 'configuration history'),
 'D0-01': ([('Confirmed', 'pair timetable'), ('Decoded', 'off-grid pairs only partly')], 'G5', ''),
 'D0-02': ([('Confirmed', 'SENSEX V1 strangle timetable (found post hoc)')], 'G5', ''),
 'D0-03': ([('Partial', 'D0 solo sells, counter-sells, replacement stream')], 'G5', 'tick path'),
 'D0-04': ([('Decoded', 'D0 stop (1.4x) and take-profit (0.1x)'), ('Unresolved', 'bursts, carried-lot buy-backs, residual')], 'G5', 'intrabar touches'),
 'D0-05': ([('Confirmed', 'D0 hedge controller quantity and timing'), ('Unresolved', 'wing versus lump release choice')], 'G5', ''),
 'D0-06': ([('Decoded', 'pre-auction clearance clock'), ('Unresolved', 'post-auction clearance clock')], 'G5', 'regime B has no real log'),
 'D0-07': ([('Unresolved', 'D0 sizing')], 'G5', 'same as D-1: set inside the minute'),
 'X-01': ([('Decoded', 'D-1 end-to-end engine replay'), ('Partial', 'D0 research simulator only'), ('Unresolved', 'cycle P&L reproduction')], 'G4/G5/G6', 'cycle P&L dominated by stop flips'),
 'X-02': ([('Confirmed', 'evidence limits')], 'G7/G8', 'decision logs, ticks, configuration, margin, data after 22 Oct 2026'),
}
rows = []
for _, r in R.iterrows():
    comps, gate, irr = A[r['id']]; worst = max(comps, key=lambda c: ORDER.index(c[0]))[0]; best = min(comps, key=lambda c: ORDER.index(c[0]))[0]
    rows.append(dict(id=r['id'], day=r['day'], component=r['component'], phase1_overall=worst, best_component_class=best, components=' ; '.join(f'{a}: {b}' for a, b in comps), register_status=r['status'], delegated_to_gate=gate, irreducible_without_new_data=irr, evidence_label=r['label'], needs_investigation=worst in ('Partial', 'Unresolved', 'Candidate')))
D = pd.DataFrame(rows); D.to_csv(f'{HERE}/PHASE1_RULE_CLASSIFICATION.csv', index=False)
compc = pd.Series([c for comps, _, _ in A.values() for c, _ in comps]).value_counts().reindex(ORDER).fillna(0).astype(int)
cnt = D.phase1_overall.value_counts().reindex(ORDER).fillna(0).astype(int)
md = ['# Phase 1, Gate 1: rule classification (generated by `build_phase1_classification.py` from the Phase A register)', '', '*Each row is classified by its **least certain component** (overall) and by component. Vocabulary: Confirmed (directly supported by strong observations), Decoded (best-supported reconstruction from several observations), Partial (some behaviour understood, important details remain), Candidate (plausible hypothesis, excluded from the baseline), Unresolved (evidence insufficient). The register keeps the richer Phase A labels; mapping: CONFIRMED to Confirmed, DECODED to Decoded, PARTIAL to Partial, CANDIDATE to Candidate, UNRESOLVED / UNKNOWN / FAILED to Unresolved.*', '', f'**Overall (least certain component), {len(D)} rows:** ' + ', '.join(f'{k} {v}' for k, v in cnt.items()), '', f'**By component ({int(compc.sum())} components):** ' + ', '.join(f'{k} {v}' for k, v in compc.items()), '',
      '| ID | Day | Component | Overall | Components | Gate | Irreducible without new data |', '|---|---|---|---|---|---|---|'] + [f"| {r.id} | {r.day} | {r.component} | **{r.phase1_overall}** | {r.components} | {r.delegated_to_gate} | {r.irreducible_without_new_data} |" for r in D.itertuples()]
open(f'{HERE}/PHASE1_RULE_CLASSIFICATION.md', 'w').write('\n'.join(md) + '\n'); print(cnt.to_dict(), '| needs investigation:', int(D.needs_investigation.sum()), 'of', len(D))
