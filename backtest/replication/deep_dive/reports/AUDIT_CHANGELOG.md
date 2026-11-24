# Audit change log (separate from the original pre-registration)

*2026-11-24. Branch `research/algo8-body-lifecycle`, HEAD at audit start `b6ed61d0`. **Nothing is committed or pushed.** Every change below is a new file; **no tracked file was modified or deleted** (`git diff` is empty; `git status` shows only untracked additions).*

## Preserved unchanged (SHA-256 before = after; `outputs/audit/fingerprints_before.txt`, `fingerprints_after.txt`)
| file | sha256 (first 16) |
|---|---|
| `d1_strategy/d1_algo/shadow.py` (frozen rule) | `6d4b860853f88fc0` |
| `outputs/fwd/frozen_model.json` (frozen score) | `990e8b19d83bd4b6` |
| `src/bl_fwd_freeze.py` | `fc97bdf172abb6f9` |
| `src/bl_fwd_eval.py` (harness v1, kept for the record) | `af107be2fb4f38a6` |
| `src/bl_fwd_power.py` (power script v1) | `1075a811686b5616` |
| `reports/FORWARD_TEST.md` (original pre-registration) | `ddd9fc9d54881289` |
| `reports/D0_CLEAR_AND_LATE_TRIGGER_PLAN.md` | `2b4cede9bb7397e0` |

Rule config hash `ca1306cfdd505f34cbbc4ee9470326eb96a8bab45716019d5214673e8a430e03` and frozen-score hash `7788f7394e87c04d117fdf512243386159bcecb56659c995dc495d769820d69c`: unchanged. No experiment, result file or earlier report was deleted.

## Added
| file | purpose |
|---|---|
| `reports/OVERFITTING_AUDIT.md` | findings, severity, selection-bias, leakage and methodology audit |
| `reports/POWER_ANALYSIS.md` | independent power / size analysis |
| `reports/VALIDATION_PROTOCOL_AMENDMENT.md` | **proposed**, not in force; original untouched |
| `reports/EXPERIMENT_LEDGER.md` | reconstructed experiment history (generated) |
| `reports/AUDIT_CHANGELOG.md` | this file |
| `validation_config.json` | machine-readable configuration: original protocol, frozen hashes, proposed amendment |
| `src/bl_validation.py` | statistics core: components, paired ΔAUC, cluster bootstrap and linearised interval, Pocock constants, roles, de-duplication |
| `src/bl_fwd_eval_v2.py` | corrected harness (v1 untouched): roles, Pocock level, no-peeking, de-duplication, missing-data accounting, hash verification |
| `src/bl_audit_pbo.py` `_stats.py` `_selection.py` `_power.py` `_power2.py` `_tables.py` `_ledger.py`, `make_audit_fig.py` | reproducible audit analyses |
| `tests/test_validation_audit.py` | 19 tests (15 requested areas; 5 injected bugs verified caught) |
| `outputs/audit/*` | results: `dev_stats.json`, `selection_null.json`, `pbo_audit.json`, `power_*.csv`, `required_cycles.json`, `experiment_ledger.csv`, `script_inventory.csv`, `power_curves.png`, fingerprints and run logs |

## Behavioural differences between harness v1 and v2 (v1 is preserved; use v2 for forward data)
| aspect | v1 | v2 |
|---|---|---|
| Interval level at each look | 95% | Pocock level from the config (97.06% for K=2) |
| Inference | percentile bootstrap | percentile bootstrap **and** linearised cluster-robust t |
| Cycle roles | none (every cycle in the log directory enters) | roles from D-1 date; primary on confirmatory cycles only |
| Before the scheduled look | computed on whatever is present | refuses (`not_ready`) |
| Order de-duplication | none | by order id, else by (time, side, strike, lots, price) |
| Missing bars | rows dropped silently | counted per cycle, positives lost counted |
| Frozen hashes | not checked | verified before any evaluation |
| Regime-B clock table | looked up if supplied | built from burn-in only, frozen once, refuses to overwrite |
| Output labels | none | every block labelled confirmatory or exploratory |

## Verification run at the end of the audit
* `tests/` (whole deep_dive suite): 179 passed (145 earlier + 19 audit + the other test files); `d1_strategy`: 24 passed.
* Development dry run: output **byte-identical** to the pre-audit file; live-form rule identical to the batch ladder on all 18 cycles; precision 0.4615, recall 0.4583.
* Mutation check of the harness: five injected defects (future bar in a feature, 95% level at every look, burn-in in the confirmatory sample, no de-duplication, peeking allowed) are each caught by at least one test, and the harness was restored.

## Not done (deliberately)
* No change to the frozen rule, its parameters, features, thresholds, reference or execution logic.
* No refitting, no re-selection, no new rule proposed for adoption.
* No amendment applied: all are proposals.
* No commit, no push, no PR update.
