# deep_dive — intraday decision-structure studies (read-only on the ledger)

| Study | Report | Code |
|---|---|---|
| DD-1 intraday decision structure | `reports/DD1_INTRADAY_DECISION_STRUCTURE.md` | `src/dd_*.py`, `src/make_dd_report.py` |
| Body lifecycle D-1 / D0 | `reports/BODY_LIFECYCLE_D1_D0_INVESTIGATION.md` (plan: `reports/BODY_LIFECYCLE_PLAN.md`) | `src/bl_*.py`, `src/make_bl_report.py` |
| Body / Hedge module investigation | `reports/BODY_HEDGE_MODULE_DEEP_INVESTIGATION.md` (plan: `reports/BODY_HEDGE_INVESTIGATION_PLAN.md`) | `src/bh_*.py`, `src/make_bh_report.py` |

Run order for the Body/Hedge study (from `src/`): `bh_h1.py` → `bh_b1.py` → `bh_h3b.py` → `bh_h3c.py` → `bh_h2_data.py` → `bh_h2_test.py` → `bh_h2_variants.py` → `bh_h2_abs.py` → `bh_h4.py` → `bh_h5.py` → `bh_h6.py` → `bh_b.py` → `bh_h7.py` → `bh_h8.py` → `bh_h9.py` → `bh_i1.py` → `bh_figs.py` → `make_bh_report.py`. (`dd_hedge.py` must have run first: `bh_h6.py` reads its bursts.) Tests: `python3 -m pytest tests -q` (needs the outputs).
Everything is in-sample (35 live cycles, not a holdout) and describes observed behaviour, not source logic.

Run order for the Body lifecycle study (from `src/`, after the Body/Hedge outputs exist): `bl_events.py` → `bl_explore.py` → `bl_d1a.py` → `bl_d1b.py` → `bl_d0a.py` → `bl_d0b.py` → `bl_d0c.py` → `bl_figs.py` → `make_bl_report.py`. Event tables: `outputs/bl_events_d1.csv`, `outputs/bl_events_d0.csv`.

Solo-sell studies (D-1 clock vs event, then the move/loss hypothesis): `bl_trigger1.py` → `bl_trigger2.py` → `bl_trigger3.py` → `make_trigger_report.py`; `bl_move_panel.py` → `bl_move_test.py` → `bl_move_test2.py` → `bl_move_robust.py` → `bl_move_fig.py` → `make_move_report.py` (reports `BODY_SELL_TRIGGERS_D1.md`, `BODY_SOLO_SELL_MOVE_TEST.md`).

Variable search for solo sells (plan `BODY_SOLO_VARIABLE_SEARCH_PLAN.md`, report `BODY_SOLO_VARIABLE_SEARCH.md`): `bl_feat_panel.py` (needs `bl_greeks.py`) → `bl_var_search.py` → `bl_tilt_test.py` → `bl_var_gb.py` → `bl_shape_feats.py` → `bl_shape_test.py` → `bl_breakout_test.py` → `bl_final_models.py` → `bl_breakout_fig.py` → `make_variable_report.py`.
