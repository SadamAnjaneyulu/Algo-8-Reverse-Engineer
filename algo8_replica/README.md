# Algo 8 mechanical replica (work in progress)

Goal: an executable, event-driven replica of the observable Algo 8 architecture, evaluated on 2023–2026 NIFTY/SENSEX option data with explicit evidence tiers. **Not** an optimisation project; nothing here recovers the original algorithm.

| Phase | Status | Where |
|---|---|---|
| 0 Repository audit | done | `reports/PHASE0_REPOSITORY_AUDIT.md` |
| 1 Rule evidence register | done (42 rules) | `config/rule_evidence.yaml`, `reports/RULE_EVIDENCE_REGISTER.md` (generated) |
| 5 (early) Historical data feasibility + eligibility register | done | `reports/HISTORICAL_DATA_FEASIBILITY.md`, `config/eligibility_criteria.yaml`, `experiments/results/cycle_eligibility_register.csv` |
| 2–4 Engine, modules, teacher-forced validation | **not started** | — |
| 6–8 Freeze, historical IS/validation/OOS, costs | not started | — |

Reproduce: `python3 tools/make_register_md.py`; `python3 tools/build_eligibility.py && python3 tools/make_feasibility_md.py`; `python3 -m pytest tests -q`.
Branch `research/algo8-mechanical-replica` was cut from `9e64fbad` (PR #13 head); PR #13 and the frozen alpha research are untouched.
