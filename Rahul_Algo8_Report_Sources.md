# Rahul — Algo 8 report sources and reproduction

This is a synthesis of frozen research, not a new strategy investigation. Source research is preserved. Data/current-artifact hashes and the saved 252-test/26-artifact validation were inspected and verified.

## Frozen revisions and scope

- Research bundle: `data/local-breeze-fetch` at `21ce61d`.
- Authoritative Strong Findings v 7: `research/strong-findings` at `15a0e5e`.
- Report trade observations: 23 June–22 October 2026; current index store begins 22 June 2026.
- Primary economic cohort: 32 initializedcycles; all 35 is sensitivity. No verified NAV/margin or original proprietary controller.

## Claim-to-source map

| ID | Claim | Source IDs | Definition / scope |
| --- | --- | --- | --- |
| R01 | Verified evidence-base counts | S07 S08 S18 | Direct stored-file and canonical-ledger counts; no synthetic history. |
| R02 | 31/32 initial paired starts near 09:16; 31 ordinary ATM proxy matches | S02 S09 | Paired start, not first exposure; completed-close proxy does not identify the original feed/query. |
| R03 | Common four-role opening size: NIFTY 195; SENSEX 60 | S02 S09 | Observed 09:17 role quantities; exceptions retained, not verified capital or exchange lot sizing. |
| R04 | 17 recurring windows; 529/544 joint structural matches | S02 S10 | One-to-one join of retention, four-role opening quantities, growth and frozen-state Greek changes. |
| R05 | New-short request granularity: 65 NIFTY / 20 SENSEX | S02 S03 | Pre-expiry request sizes: 2022/2032 and 2375/2375; not a recovered size formula. |
| R06 | Latest opening module: 28/32 shorts, 17/32 first wings, 19/32 net roles | S05 | Model 28; true first executed wing pair, gross opening short pair and 09:17 net quantities are different targets. |
| R07 | Earlier selected controller opening contradiction: 0/32 wing pairs and short quantity pairs | S04 S05 | Candidate 13845; preserved legacy first-three-minute test and child-second re-audit, not rewritten by model 28. |
| R08 | 13,864 definitions; earlier later F1 23.3% vs 18.2% baseline | S04 | 15 already-inspected September–October cycles; four-action event macro F1. |
| R09 | Separated model later F1 24.3% | S05 | 14 initialized later cycles; safe model 28 and pending-aware 33 have the same minute F1; different cohort/module from R08. |
| R10 | 3,512 intermediate / 326 final episodes in initialized cycles | S06 | 32 initialized cycles; adjacent covers within 120 s grouped unless opening/date/stratum breaks the episode. |
| R11 | Exit tests: premium-loss 50 P36.4/R9.8; drawdown P18.0/R16.6 | S06 | 24 expanding chronological test cycles; 2200 intermediate starts; same-contract matching within ±120 s; full active-inventory risk set. |
| R12 | 49/59 equal-quantity reversals; distinct closing/opening parents | S05 S13 | Immutable conservative motifs; opposite size <=closed quantity is a cohort restriction, not independent evidence. |
| R13 | Strict bounded non-reversal controls: 9/14; difference CI crosses zero | S13 | Unadjusted cycle bootstrap difference from saved table; weak exact support (one matched case/control). |
| R14 | Universal duplicate variant: 559 predictions, 0/59 hits | S05 S13 | Model 32; exact contract and close time within ±120 s. Shape compatibility does not identify activation. |
| R15 | Late final closures: 9/10 at 15:14; 27/29 by 15:27:33 | S02 S12 | Post-3-Aug late selected closures vs all reconciled final short-book closures; not all legs or every exit. |
| R16 | 4% carry and 1% expiry capital stops are supplied wording | S02 S03 | Denominator, scope, reset, queue handling, NAV and margin remain unidentified. |
| R17 | Primary gross realised / unrealised / combined economics | S01 S14 | 32 initialized cycles; canonical realised plus quote-marked residuals, not verified liquidation or NAV. |
| R18 | Four fixed cost-scenario nets | S01 S15 S19 | Premium-turnover percentage plus per-parent fee plus per-unit allowance; estimated rather than authenticated charges. |
| R19 | Largest-winner exclusion leaves ₹1721.58; top-two exclusion −₹423305.62 | S01 S15 | Primary 32 conservative marked net; order determined by cycle net, not traded fills. |
| R20 | Largest winner: NIFTY 29 Sep, no expiry fills, unrealised ₹540801.92 | S01 S07 S14 | Known initialization but residual paper valuation; source book does not certify post-export holdings or settlement. |
| R21 | Short CE +₹36.185 lakh; short PE −₹8.874 lakh; long CE −₹4.854 lakh; long PE −₹3.514 lakh | S14 | Primary 32 pooled gross direction/right attribution, including residual marks; not original allocation ownership. |
| R22 | Forward/time/own-IV/bridge/residual decomposition | S16 S19 | Primary model variant-valid intervals; own-option IV, explicit fit failures and residual; model sensitivities use common intervals separately. |
| R23 | Paired benchmark intervals span zero; no defensible equal-risk benchmark | S01 S17 | Conservative costs; D_common_clock vsB n 25 /C n 20; quoted shared cycles only, dynamic risks unequal. |
| R24 | Outcome B; original controller and alpha not recovered | S01 S02 | Authoritative closure; neither a proof of no alpha in all periods nor validation of the screenshot. |
| R25 | 252 tests and 26 exactly reproduced numeric artifacts | S18 | Saved passed validation inspected; current code/artifact hashes and frozen source hashes reverified during report build. No trading searches rerun. |
| R26 | Seed geometry differs from routine 2.5% premium-budget proxy | S02 S09 S11 | N26/28 within 100 of 2000 (19 exact); S early 21/22 within 200 of 4000, later 12/12 exactly 2000; routine exact vs tolerance reported separately. |
| R27 | Sampled risk and mean-cycle confidence interval | S15 | Primary 32 conservative cycle-level sample; mean 95% bootstrap includeszero, sampled intracycle drawdown not tick maximum. |
| R28 | No universal whole-basket replacement every quarter hour | S02 S03 S10 | Older long and short exposure necessarily retained in every recurring window; selected side reductions do not imply every contract on that side is flat. |

## Figure definitions and sources

### Figure 1 — Observed lifecycle and unresolved activation

Sources: S02 S03 S06. Solid boxes: observed structure. Dashed gold boxes/arrows: conditions or sequencing not recovered. Schematic only; early closures can bypass later stages.
Files: [PNG](rahul_report_figures/Figure_01.png), [SVG](rahul_report_figures/Figure_01.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 2 — Observed recurring-window short allocations

Sources: S10. Gross inventory-opening CE/PE short quantities averaged per right, divided by 65 for NIFTY and 20 for SENSEX; median and IQR. Outliers not shown; windows are not sizing instructions.
Files: [PNG](rahul_report_figures/Figure_02.png), [SVG](rahul_report_figures/Figure_02.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 3 — Recurring-window structural evidence

Sources: S02 S10. 32 sessions ×17 windows. One window lacks a full Greek fit; joint denominator remains 544. Rates are correlated and must not be multiplied.
Files: [PNG](rahul_report_figures/Figure_03.png), [SVG](rahul_report_figures/Figure_03.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 4 — Opening reconstruction: improvement and remaining mismatch

Sources: S05. Different targets: opening gross shorts, true first executed wing pair, 09:17 net roles. Earlier controller contradiction is retained; no unreported net score invented.
Files: [PNG](rahul_report_figures/Figure_04.png), [SVG](rahul_report_figures/Figure_04.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 5 — Autonomous reconstruction remains weak

Sources: S04 S05. Four action types, exact contract/action within ±2 min. Panels have different initialization/cohort/modules; do not read 23.3→24.3 as a controlled improvement.
Files: [PNG](rahul_report_figures/Figure_05.png), [SVG](rahul_report_figures/Figure_05.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 6 — Intermediate-exit precision versus recall

Sources: S06. 24 expanding chronological cycles; 2200 intermediate episode starts; same-contract one-to-one ±120 s. Not an independent-fill test or a full autonomous replay.
Files: [PNG](rahul_report_figures/Figure_06.png), [SVG](rahul_report_figures/Figure_06.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 7 — Reversal quantity equality is suggestive, not causal proof

Sources: S13. Conservative motifs exclude oversize openings. One-base equality can be forced by the size restriction. Saved bootstrap is unadjusted, not a duplication probability.
Files: [PNG](rahul_report_figures/Figure_07.png), [SVG](rahul_report_figures/Figure_07.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 8 — Economic result changes with declared costs

Sources: S01 S14 S15 S19. 32 initialized cycles. Net includes quoted residuals, not verified account returns or settlements. Charges are fixed estimates, not authenticated fees.
Files: [PNG](rahul_report_figures/Figure_08.png), [SVG](rahul_report_figures/Figure_08.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 9 — Conservative net is highly sensitive to winning cycles

Sources: S01 S15. Largest winner: NIFTY 29 Sep; no received expiry-day fills and substantial unrealized quoted gain. This is a sensitivity check, not a rule-selection exercise.
Files: [PNG](rahul_report_figures/Figure_09.png), [SVG](rahul_report_figures/Figure_09.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 10 — Gross role contributions: gains and protection costs

Sources: S14. 32 initialized cycles; pooled role cash plus residual marks, not original allocation P&L. Four roles sum to 18.94 lakh gross; strategy costs are deducted separately once.
Files: [PNG](rahul_report_figures/Figure_10.png), [SVG](rahul_report_figures/Figure_10.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 11 — Model-based repricing decomposition with residual

Sources: S16. Primary 32, primary model variant-valid intervals. Five signed terms sum to 18.94 lakh; time is not causal alpha and the bridge is not identified execution alpha.
Files: [PNG](rahul_report_figures/Figure_11.png), [SVG](rahul_report_figures/Figure_11.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

### Figure 12 — Benchmark uncertainty does not establish alpha

Sources: S17. Conservative costs; D_common_clock hypothetically closes actual pre-deadline inventory at the same candle open. B: 25 and C: 20 separate common cohorts; risk budgets unequal; C uses Aug–Oct after June–July size fitting.
Files: [PNG](rahul_report_figures/Figure_12.png), [SVG](rahul_report_figures/Figure_12.svg). Numeric inputs: `rahul_report_figures/figure_data.json`.

## Source register

### S01 — Final economic closure

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/FINAL_ALPHA_ATTRIBUTION_AND_FALSIFICATION.md)
- [research/final_alpha_attribution/final_verdict.json](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/final_verdict.json)

### S02 — Cumulative Strong Findings v 7

Frozen revision: `15a0e5e`.
- [STRONG_FINDINGS.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/15a0e5e/STRONG_FINDINGS.md)

### S03 — Operational allocation and risk playbook

Frozen revision: `21ce61d`.
- [ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/ALLOCATION_ENTRY_EXIT_RISK_PLAYBOOK.md)
- [research/outputs/playbook_book_audit.json](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/playbook_book_audit.json)

### S04 — Constrained autonomous controller experiment

Frozen revision: `21ce61d`.
- [research/hypothesis_controller_search/HYPOTHESIS_CONTROLLER_SEARCH.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/hypothesis_controller_search/HYPOTHESIS_CONTROLLER_SEARCH.md)
- [research/hypothesis_controller_search/outputs/candidate_scores.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/hypothesis_controller_search/outputs/candidate_scores.csv)
- [research/hypothesis_controller_search/outputs/search_manifest.json](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/hypothesis_controller_search/outputs/search_manifest.json)

### S05 — Policy/execution and opening reconstruction

Frozen revision: `21ce61d`.
- [research/policy_execution_separation/POLICY_EXECUTION_RECONSTRUCTION.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/POLICY_EXECUTION_RECONSTRUCTION.md)
- [research/policy_execution_separation/policy_vs_execution_comparison.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/policy_vs_execution_comparison.csv)
- [research/policy_execution_separation/opening_vs_prior_contradiction.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/opening_vs_prior_contradiction.csv)

### S06 — Intermediate-exit event study

Frozen revision: `21ce61d`.
- [research/intermediate_exit_study/INTERMEDIATE_EXIT_CONTROLLER.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/intermediate_exit_study/INTERMEDIATE_EXIT_CONTROLLER.md)
- [research/intermediate_exit_study/ranked_trigger_hypotheses.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/intermediate_exit_study/ranked_trigger_hypotheses.csv)
- [research/intermediate_exit_study/exit_case_ledger.csv.gz](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/intermediate_exit_study/exit_case_ledger.csv.gz)

### S07 — Canonical source fills and atomic books

Frozen revision: `21ce61d`.
- [research/outputs/playbook_fill_ledger.csv.gz](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/playbook_fill_ledger.csv.gz)
- [research/outputs/playbook_event_book.csv.gz](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/playbook_event_book.csv.gz)
- [research/final_alpha_attribution/data_quality_and_coverage.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/data_quality_and_coverage.csv)

### S08 — Stored index/option data provenance

Frozen revision: `21ce61d`.
- [data/breeze/normalized/indices](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/tree/21ce61d/data/breeze/normalized/indices)
- [data/breeze/metadata/options](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/tree/21ce61d/data/breeze/metadata/options)
- [research/final_alpha_attribution/input_audit.json](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/input_audit.json)

### S09 — Initial entry, seed wings and opening sizes

Frozen revision: `21ce61d`.
- [research/outputs/trigger_initial_entries.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/trigger_initial_entries.csv)
- [research/outputs/trigger_initial_wings.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/trigger_initial_wings.csv)
- [research/outputs/rulebook_opening_allocations.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/rulebook_opening_allocations.csv)

### S10 — Recurring windows, retention and fixed-state risks

Frozen revision: `21ce61d`.
- [research/outputs/playbook_allocation_windows.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/playbook_allocation_windows.csv)
- [research/outputs/allocation_window_sizes.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/allocation_window_sizes.csv)
- [research/outputs/lifecycle_scheduled_window_retention.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/lifecycle_scheduled_window_retention.csv)
- [research/outputs/building_rationale_windows.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/building_rationale_windows.csv)

### S11 — Approximate routine hedge selection

Frozen revision: `21ce61d`.
- [research/outputs/rule_refine_hedge_evaluation.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/rule_refine_hedge_evaluation.csv)
- [research/RULE_REFINEMENT_FINDINGS.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/RULE_REFINEMENT_FINDINGS.md)

### S12 — Final short-book closure observations

Frozen revision: `21ce61d`.
- [research/outputs/rule_refine_exit_target_comparison.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/outputs/rule_refine_exit_target_comparison.csv)
- [research/RULE_REFINEMENT_FINDINGS.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/RULE_REFINEMENT_FINDINGS.md)

### S13 — Fixed reversal motifs and strict controls

Frozen revision: `21ce61d`.
- [research/policy_execution_separation/reversal_motif_ledger.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/reversal_motif_ledger.csv)
- [research/policy_execution_separation/quantity_equality_controls.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/quantity_equality_controls.csv)
- [research/policy_execution_separation/control_cycle_uncertainty.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/control_cycle_uncertainty.csv)
- [research/policy_execution_separation/reversal_pattern_coverage.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/policy_execution_separation/reversal_pattern_coverage.csv)

### S14 — Direct economic and role/phase ledgers

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/cycle_economic_results.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/cycle_economic_results.csv)
- [research/final_alpha_attribution/role_economic_results.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/role_economic_results.csv)
- [research/final_alpha_attribution/phase_economic_results.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/phase_economic_results.csv)

### S15 — Costs, risk, concentration and leave-one-out

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/cost_stress_results.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/cost_stress_results.csv)
- [research/final_alpha_attribution/risk_and_drawdown_summary.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/risk_and_drawdown_summary.csv)
- [research/final_alpha_attribution/leave_one_cycle_out.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/leave_one_cycle_out.csv)

### S16 — Own-IV repricing decomposition

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/cycle_pnl_decomposition.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/cycle_pnl_decomposition.csv)
- [research/final_alpha_attribution/attribution_interval_ledger.csv.gz](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/attribution_interval_ledger.csv.gz)

### S17 — Fixed common-clock benchmark comparisons

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/benchmark_comparison.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/benchmark_comparison.csv)
- [research/final_alpha_attribution/paired_benchmark_differences.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/paired_benchmark_differences.csv)
- [research/final_alpha_attribution/benchmark_exposure_ratios.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/benchmark_exposure_ratios.csv)

### S18 — Final accounting and reproduction validation

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/validation_audit.json](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/validation_audit.json)
- [research/final_alpha_attribution/DATA_QUALITY_AUDIT.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/DATA_QUALITY_AUDIT.md)

### S19 — Frozen definitions and cost assumptions

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/REGISTERED_PLAN.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/REGISTERED_PLAN.md)
- [research/final_alpha_attribution/BENCHMARK_AND_MODEL_CLARIFICATIONS.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/BENCHMARK_AND_MODEL_CLARIFICATIONS.md)
- [research/intermediate_exit_study/REGISTERED_PLAN.md](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/intermediate_exit_study/REGISTERED_PLAN.md)

### S20 — Management and holding-time sensitivities

Frozen revision: `21ce61d`.
- [research/final_alpha_attribution/management_markout_summary.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/management_markout_summary.csv)
- [research/final_alpha_attribution/flow_and_holding_attribution.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/flow_and_holding_attribution.csv)
- [research/final_alpha_attribution/attribution_counterexamples.csv](https://github.com/SadamAnjaneyulu/Algo-8-Reverse-Engineer/blob/21ce61d/research/final_alpha_attribution/attribution_counterexamples.csv)

## Reproduction and checks

```bash
OPENBLAS_NUM_THREADS=1 python rahul_report_figures/build_report.py
python rahul_report_figures/validate_report.py
```

Dependencies: existing repository Python environment (`python-docx`, pandas, NumPy, Matplotlib, PyMuPDF) and LibreOffice/soffice. No broker credentials, network data calls or controller searches are used. The build reads frozen source artifacts and emits only the four requested report deliverables and report-only provenance/validation files.

The original economic reproduction entry point remains `research/final_alpha_attribution/run.py`; it was not rerun for this writing task. Its saved passed validation reports 252 tests and 26 exactly reproduced numeric artifacts. This synthesis verifies their current hashes plus the frozen source input hashes, and validates/render-checks the final documents independently.

## Known boundaries / availability

- Strong Findings is intentionally read from its separate branch/revision, not invented as a file in the active data checkout.
- The older untracked `research/outputs/index_data_audit.json` contains a 154-session acquisition snapshot. It is not used as the current count; 170 files/63,678 bars are verified directly.
- All 12 requested figures have verified source artifacts; no mandatory figure was omitted. C02 is reproduced by the documented join of existing window/retention/Greek artifacts, without changing any study results.
- Legacy 13845 opening 0/32 and dedicated 28 opening 28/32,17/32,19/32 are different experiments/targets and are not substituted.
-23.3%F1 uses 15 later cycles; 24.3%uses 14 initializedlatercycles. Exit P/R uses 24 chronologicalcycles/2200 events; the full initialized study contains 3512 intermediate episodes.
- Reversal bootstrap intervals are unadjusted cycle contrasts and do not establish causality; the strict control sample is small and one-base equality can be forced.
- Economic means/CIs and cost stresses use frozen definitions; benchmark clocks match but risk budgets do not. Quote residuals and hypothetical benchmark closes are not observed settlement.
- Canonical role, phase and modeled attributions are alternative cuts of one P&L. Do not add them; unexplained residuals are not alpha.
- `verified_claims.json` records current source hashes and exact scope counts. `report_validation.json` records document, hyperlink and rendered-page checks.
