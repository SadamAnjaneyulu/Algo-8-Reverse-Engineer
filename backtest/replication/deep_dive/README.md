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

Paired-sell and close logic (plan `BODY_PAIRED_SELL_PLAN.md`, report `BODY_PAIRED_SELL_AND_CLOSE_LOGIC.md`): `bl_slot_panel.py` → `bl_slot_test.py` → `bl_slot_strike.py` → `bl_close_panel.py` → `bl_close_test.py` → `bl_paired_fig.py` → `make_paired_report.py`.

Buy-back logic (plan `BODY_CLOSE_LOGIC_PLAN.md`, report `BODY_CLOSE_LOGIC.md`): `bl_close_build.py` → `bl_close_logic1.py` → `bl_close_logic2.py` → `bl_close_logic2b.py` → `bl_close_logic3.py` → `bl_close_logic4.py` → `bl_close_logic5.py` → `bl_close_logic6.py` → `bl_close_logic7.py` → `bl_close_fig.py` → `make_close_report.py` (needs `outputs/bl_all_orders.pkl.gz` from `bl_events.py`).

Capital-loss (book P&L) trigger study for sub-1.2x buy-backs (plan `BODY_CLOSE_CAPITAL_PLAN.md`, report `BODY_CLOSE_CAPITAL.md`): `bl_book_mtm.py` → `bl_book_tests1.py` → `bl_book_tests2.py` (slow, ~10 min) → `bl_book_tests3.py` → `bl_book_tests4.py` → `bl_book_tests5.py` → `bl_book_tests6.py` → `bl_book_tests7.py` (slow) → `bl_book_tests8.py` → `bl_book_tests9.py` (slow) → `bl_capital_fig.py` → `make_capital_report.py` (needs the buy-back study outputs, `bl_close_orders_clusters_D-1/D0.csv` from `bl_close_logic6.py`).

Body sizing study (plan `BODY_SIZING_PLAN.md`, report `BODY_SIZING_LOGIC.md`): `bl_size_build.py` → `bl_size_tests.py` → `bl_size_tests2.py` → `bl_size_fig.py` → `make_size_report.py` (needs `bl_events.py` outputs, `bl_book_panel.csv.gz` from `bl_book_mtm.py`).

Reactive pairs and wave clock (plan `BODY_REACTIVE_PAIR_PLAN.md`, report `BODY_REACTIVE_PAIRS.md`): `bl_react_panel.py` → `bl_react_tests1.py` → `bl_react_tests1b.py` → `bl_react_tests2.py` (slow, ~10 min) → `bl_react_tests3.py` → `bl_react_waves.py` → `bl_react_fig.py` → `make_react_report.py` (needs the sizing study outputs).

Reactive-pair mechanism and sell census (plan `BODY_REACTIVE_MECHANISM_PLAN.md`, report `BODY_REACTIVE_MECHANISM.md`): `bl_mech_panel.py` → `bl_mech_tests1.py` → `bl_mech_strike.py` → `bl_mech_tests2.py` → `bl_mech_census.py` → `bl_mech_fig.py` → `make_mech_report.py` (needs the reactive-pair and sizing outputs).

Reactive-pair look-back verification (plan `BODY_REACTIVE_LOOKBACK_PLAN.md`, report `BODY_REACTIVE_LOOKBACK.md`): `bl_lb_tests.py` → `bl_lb_tests2.py` → `bl_lb_tests3.py` → `bl_lb_fig.py` → `make_lb_report.py` (needs the reactive-pair and mechanism outputs).

Reactive-pair dynamic reference and activation (plan `BODY_REACTIVE_ACTIVATION_PLAN.md`, report `BODY_REACTIVE_ACTIVATION.md`): `bl_act_build.py` → `bl_act_tests.py` (slow) → `bl_act_tests2.py` (slow) → `bl_act_tests3.py` → `bl_act_fig.py` → `make_act_report.py` (needs the reactive-pair, mechanism and look-back outputs).

Reactive-pair indicator search (plan `BODY_REACTIVE_INDICATOR_PLAN.md`, report `BODY_REACTIVE_INDICATOR.md`): `bl_ind_build.py` → `bl_ind_tests.py` → `bl_ind_break.py` → `bl_ind_fine.py` → `bl_ind_fig.py` → `make_ind_report.py` (needs the activation study outputs).

Reactive-pair window and trigger study (plan `BODY_REACTIVE_TRIGGER_PLAN.md`, report `BODY_REACTIVE_TRIGGER.md`): `bl_trg_band.py` → `bl_trg_panel.py` → `bl_trg_tests.py` (slow, ~3 min) → `bl_trg_drill.py` → `bl_trg_move.py` → `bl_trg_leg.py` → `bl_trg_fig.py` → `make_trg_report.py` (needs the activation and indicator study outputs).

Reactive-pair per-minute tracker study (plan `BODY_REACTIVE_TRACKER_PLAN.md`, report `BODY_REACTIVE_TRACKER.md`): `bl_trk_timing.py` → `bl_trk_clusters.py` → `bl_trk_sim.py` (slow, ~2 min) → `bl_trk_sim2.py` (slow, ~5 min) → `bl_trk_resid.py` → `bl_trk_cap.py` → `bl_trk_side.py` → `bl_trk_example.py` → `bl_trk_fig.py` → `make_trk_report.py` (needs the trigger study outputs).

Reactive-pair book-state and pace study (plan `BODY_REACTIVE_BOOK_PLAN.md`, report `BODY_REACTIVE_BOOK.md`): `bl_bk_build.py` → `bl_bk_tests.py` → `bl_bk_blocks.py` → `bl_bk_flow.py` → `bl_pc_sim.py` (~3 min) → `bl_pc_tests.py` → `bl_pc_reg.py` (~2 min) → `bl_pc_example.py` → `make_bk_report.py` (needs the tracker and trigger study outputs).

Reactive-pair 30-minute clock study (report `BODY_REACTIVE_CLOCK.md`; exploratory, no plan): `bl_clk_sim.py` → `bl_clk_scan.py` → `bl_clk_chan.py` → `bl_clk_refine.py` → `bl_clk_bars.py` → `bl_clk_repeat.py` → `bl_clk_wings.py` → `bl_clk_wingstate.py` → `bl_clk_example.py` → `make_clk_report.py` (needs the trigger, tracker and book study outputs).

Reactive-pair decoding with true one-minute OHLC (report `BODY_REACTIVE_DECODE.md`; exploratory): `bl_ohlc.py` → `bl_dq_ohlc.py` → `bl_dq_repeat_desc.py` → `bl_dq_repeat_sim.py` → `bl_dq_gates.py` (slow) → `bl_dq_tune.py` → `bl_dq_repeat_gate.py` → `bl_dq_final.py` → `bl_dq_count.py` → `bl_dq_fig.py` → `make_dq_report.py`.

Combined D-1 selling reconstruction (report `D1_SELLING_RECONSTRUCTION.md`): `bl_all_sells.py` → `bl_all_solo.py` → `bl_all_fig.py` → `make_all_report.py` (needs the decoding outputs).

Solo decode and reactive entry size (plan `BODY_SOLO_DECODE_PLAN.md`, report `BODY_SOLO_DECODE.md`): `bl_sd_build.py` → `bl_sd_scan.py` → `bl_sd_state.py` → `bl_sd_balance.py` → `bl_sd_ladder.py` → `bl_sd_tilt.py` → `bl_sd_spotladder.py` → `bl_sd_reactlots.py` → `bl_sd_combined.py` → `bl_sd_classes.py` → `bl_sd_late.py` → `bl_sd_fig.py` → `make_sd_report.py` (then rerun `make_all_report.py`).
After-15:00 solo regime (plan `BODY_SOLO_LATE_PLAN.md`, report `BODY_SOLO_LATE.md`): `bl_sl_greeks.py` → `bl_sl_flow.py` → `bl_sl_panel.py` → `bl_sl_tests.py` → `bl_sl_rest.py` (then the class-table augmentation inside it) → `bl_sl_prem.py` → `bl_sl_rule2.py` → `bl_sl_cond.py` → `bl_sl_fig.py` → `make_sl_report.py`.
One AUC for all D-1 selling (plan `D1_SELLING_AUC_PLAN.md`, report `D1_SELLING_AUC.md`): `bl_auc_all.py` → `bl_auc_all2.py` → `make_auc_report.py`.
D-1 long side / hedge module (plan `D1_LONG_SIDE_PLAN.md`, report `D1_LONG_SIDE.md`): `bl_hg_inv.py` → `bl_hg_lump.py` → `bl_hg_lump2.py` → `bl_hg_strike.py` → `bl_hg_strike2.py` → `bl_hg_life.py` → `bl_hg_fig.py` → `make_hg_report.py`.
Overnight lump (report `D1_LUMP.md`, exploratory): `bl_lp_dec.py` → `bl_lp_risk.py` → `bl_lp_budget.py` → `bl_lp_subset.py` → `bl_lp_equal.py` → `bl_lp_final.py` → `bl_lp_fig.py` → `make_lp_report.py`.
Complete D-1 activity AUC (plan `D1_FULL_AUC_PLAN.md`, report `D1_FULL_AUC.md`): `bl_full_auc.py` → `make_full_report.py` (needs the `bl_auc_all*` outputs).
Free-running complete D-1 reconstruction vs the real ledger (plan `D1_FREE_RUN_PLAN.md`, report `D1_FREE_RUN.md`): `bl_fr_sim.py` (library) → `bl_fr_score.py` → `bl_fr_cell.py` → `make_fr_report.py` (needs the `bl_sd_*`, `bl_lp_dec`, `bl_auc_all_panel` outputs).
Buy-back decode (plan `BUYBACK_DECODE_PLAN.md`, report `BUYBACK_DECODE.md`): `bl_bb_events.py` → `bl_bb_struct.py` → `bl_bb_panel.py` → `bl_bb_right.py` → `bl_bb_vel.py` → `bl_bb_low.py` → `bl_bb_fit.py` → `bl_bb_tf.py` → `bl_sell_err.py` → `bl_rep_fit.py` → `make_bb_report.py`.
Buy-back second pass, stops on losing positions (plan `BUYBACK_STOP2_PLAN.md`, report `BUYBACK_STOP2.md`): `bl_bs_panel.py` → `bl_bs_score.py` → `bl_bs_mkt.py` → `bl_bs_fit.py` → `bl_bs_price.py` → `bl_bs_ab.py` → `bl_bs_profit.py` → `make_bs_report.py`.
Buy-back third pass, why exits differ (report `BUYBACK_STOP3.md`): `bl_bt_inv.py` → `bl_bt_fresh.py` → `bl_bt_lot.py` → `bl_bt_react.py` → `bl_bt_adv.py` → `bl_bt_ctx.py` → `bl_bt_profit.py` → `make_bt_report.py`.
Buy-back rebalancing events in the simulator (plan `BUYBACK_EVENTS_PLAN.md`, report `BUYBACK_EVENTS.md`): `bl_ev_fit.py` → `make_ev_report.py`.
Forward test on unseen cycles (report `D1_FORWARD.md`): `bl_fwd.py` → `make_fwd_report.py`.
D-1 lot construction (plan `D1_LOTS_PLAN.md`, report `D1_LOTS.md`): `bl_err_budget.py` → `bl_qty_events.py` → `bl_solo_burst.py` → `bl_solo_minute.py` → `bl_lots_fit.py` → `bl_lots_ceiling.py` → `make_lots_report.py`.
Learned policies and accuracy scoreboard (plan `D1_ML_PLAN.md`, report `D1_ACCURACY_PUSH.md`): `bl_ml_feat.py` → `bl_ml_fit.py` → `bl_ml_tcheck.py` → `make_ml_report.py`.
Accuracy push round 2 (opening-wing close relabel, joint tuning): `bl_push2.py` → `make_ml_report.py`.
D0 inventory (plan `D0_PLAN.md`, report `D0_INVENTORY.md`): `bl_d0_data.py` (D0 spot and option OHLC caches) → `bl_d0_inv.py` → `make_d0inv_report.py`.

D0 chunk 1, body sells (plan `D0_SELLS_PLAN.md` with addenda 1b/1c, report `D0_SELLS.md`): `bl_d0s_label.py` → `bl_d0s_tests.py` → `bl_d0s_tt.py` → `bl_d0s_solo.py` → `bl_d0s_auc.py` (~1.5 min) → `make_d0s_report.py`; `make_d0inv_report.py` again for the inventory correction note.

D0 chunk 2, body buy-backs (plan `D0_BUYBACKS_PLAN.md` with addenda 2b/2c, report `D0_BUYBACKS.md`): `bl_d0b_ledger.py` → `bl_d0b_tests.py` (~2 min) → `bl_d0b_mach.py` → `bl_d0b_auc.py` (~1 min) → `bl_d0b_side.py` (~7 min) → `bl_d0b_burst.py` → `bl_d0b_carry.py` (~3 min) → `make_d0b_report.py`.

D0 chunk 3, hedge wings / lump / body-stream longs (plan `D0_HEDGE_PLAN.md` with addendum 3b, report `D0_HEDGE.md`): `bl_d0h_tests.py` → `bl_d0h_more.py` (~2 min) → `make_d0h_report.py`.

D0 chunk 4, cycle stop and 15:14 clearance (plan `D0_STOP_CLEAR_PLAN.md`, report `D0_STOP_CLEAR.md`): `bl_d0x_stop.py` → `make_d0x_report.py`.

D0 chunk 5, free-running D0 reconstruction and D0 overview (plan `D0_FREE_RUN_PLAN.md`, report `D0_FREE_RUN.md`): `bl_d0_fr.py` → `bl_d0_fr_score.py` → `make_d0fr_report.py` (needs the chunk 1–4 outputs).

D0 step 1, sell types and strikes 09:15 → close (plan `D0_SELL_TYPES_PLAN.md` with a post-hoc addendum, report `D0_SELL_TYPES.md`): `bl_d0t_types.py` (~1 min) → `make_d0t_report.py`.

D0 step 1b, scheduled selling in depth (plan `D0_SCHEDULED_PLAN.md`, report `D0_SCHEDULED.md`): `bl_d0q_sched.py` → `make_d0q_report.py`.

D0 scheduled selling, one cycle at a time, D-1 vs D0 (report `D0_SCHEDULED_CYCLE.md`): `bl_d0q_cycle.py 4`, `bl_d0q_cycle.py 15`, `bl_d0q_cycle.py 26` → `make_d0qc_report.py` (needs `bl_d0q_sched.py` outputs).

D0 scheduled selling, why 83 pairs vs 33 (report `D0_SCHEDULED_WHY.md`): `bl_d0q_sched.py` → `bl_d0q_detail.py 4` → `bl_d0q_why.py` → `make_d0qw_report.py`.

D0 and D-1 scheduled selling, every clock time and the lots executed at each (report `D0_SCHEDULED_ALLTIMES.md`, four figures `bl_d0q_alltimes_<und>_<ver>.png`): `bl_d0q_sched.py` → `bl_d0q_alltimes.py` → `make_d0qa_report.py`.

How the D0 scheduled selling is scheduled, a bank of timers (plan `D0_SCHED_RULE_PLAN.md` with addendum A, report `D0_SCHED_RULE.md`): `bl_d0r_chains.py` and `bl_d0r_ilp.py` (exploratory) → `bl_d0r_val.py` → `bl_d0r_bank.py` → `bl_d0r_gap.py` → `make_d0r_report.py`; per-cycle check scripts `bl_d0q_detail.py`, `bl_d0q_why.py`, `bl_d0q_alltimes.py`.

D-1 scheduled selling per 15-minute mark (all cycles, used by `D0_SCHED_RULE.md` §1): `bl_d0r_d1marks.py`.

Check of the 14 extra D0 marks (+10 min rule, ATM, lots): `bl_d0r_extra10.py`.

D0 buy-back reasons, open to close (plan `D0_BB_TYPES_PLAN.md` with a post-hoc addendum, report `D0_BB_TYPES.md`): `bl_d0b_ledger.py` → `bl_d0b_tests.py` → `bl_d0y_types.py` (~1 min) → `bl_d0y_other.py` → `make_d0y_report.py`.
D0 counter-sells (plan `D0_COUNTER_PLAN.md`, report `D0_COUNTER.md`): `bl_d0s_label.py` → `bl_d0y_types.py` → `bl_d0k_counter.py` (~1 min) → `make_d0k_report.py`.
D0 counter-sell trigger search (plan `D0_CTRIG_PLAN.md` + addendum, report `D0_CTRIG.md`): `bl_d0n_panel.py` → `bl_d0n_model.py` (~3 min) → `bl_d0n_more.py` → `bl_d0n_tight.py` → `bl_d0n_rule.py` (~3 min) → `bl_d0n_decomp.py` → `make_d0n_report.py`.
D0 pair timing and buy-back trigger (plan `D0_PAIR_PLAN.md` + addendum, report `D0_PAIR.md`): `bl_d0p_a.py` (~3 min) → `bl_d0p_a2.py` → `bl_d0p_b.py` (~3 min) → `bl_d0p_b6.py` → `make_d0p_report.py`.
Standalone D-1 package (`/d1_strategy`, document in `/d1_document`) validated against the research simulator and the real ledger: `src/validate_d1_package.py` (~3 min), outputs `bl_d1pkg_*`.
Live-style D-1 engine (`/d1_strategy/d1_algo`) replayed second by second on the 32 real sessions and scored against the real log: `src/validate_engine.py` (~1 min, 4 processes), outputs `bl_d1eng_*`.
D0 counter-sell AUC gate (plan `D0_CAUC_PLAN.md`, report `D0_CAUC.md`): `bl_d0c_auc.py` (~2 min) → `bl_d0c_expl.py` (~3 min) → `make_d0c_report.py`.
D0 solo selling after counter-sells: strangle timetable, replacement stream (plan `D0_REPL_PLAN.md`, report `D0_REPL.md`): `bl_d0e_repl.py` → `bl_d0e_more.py` → `bl_d0e_clock.py` → `bl_d0e_strangle.py` → `bl_d0e_final.py` → `make_d0e_report.py` (~15 min in total).
D0 selling, every type, on unseen cycles (plan `D0_FULL_AUC_PLAN.md`, report `D0_FULL_AUC.md`): `bl_d0f_panel.py` → `OMP_NUM_THREADS=1 bl_d0f_auc.py` (~6 min) → `bl_d0f_abl.py` → `make_d0f_report.py`.

D0 quantity: order execution, lots per event, position management (plan `D0_QTY_PLAN.md`, report `D0_QTY.md`): `bl_d0u_exec.py` → `bl_d0u_size.py` (~2 min) → `bl_d0u_inv.py` → `make_d0u_report.py`.

D0 sizing treatments (A drawn, B fixed median, C scaled) in the free-run simulator (plan `D0_SIZING_PLAN.md`, report `D0_SIZING.md`): `OMP_NUM_THREADS=1 bl_d0v_sizing.py check` (integrity) → `bl_d0v_sizing.py run` (~1 min) → `bl_d0v_analysis.py` → `make_d0v_report.py`.

D0 burst buy-backs, other buy-back types, body-stream longs, coverage (plan `D0_BURST_LONG_PLAN.md`, report `D0_BURST_LONG.md`): `bl_d0w_panel.py` → `OMP_NUM_THREADS=1 bl_d0w_burst.py` (~12 min) → `bl_d0w_burst_placebo.py` → `bl_d0w_burstlots.py` → `bl_d0w_long.py` → `bl_d0w_extra.py` → `make_d0w_report.py`.

D0 roll-out, "other" buy-backs and the opening burst (plan `D0_OPEN_ROLL_PLAN.md`, report `D0_OPEN_ROLL.md`): `bl_d0z_roll.py` (~8 min) → `bl_d0z_post.py` → `bl_d0z_open.py` → `make_d0z_report.py` (needs the `bl_d0w_*` outputs).

3-year combined backtest (plan `BACKTEST3Y_PLAN.md`, pre-registered before any run): phase 0 data, `bl_bt3_data.py` (full option chains for every Complete cycle from the pinned dataset commit, ~40 s, cache in `outputs/bt3/` is git-ignored) → `outputs/bl_bt3_cycles.csv` (cycle table with status, split, unit).

3-year combined backtest (plans `BACKTEST3Y_PLAN.md` + 2 addenda, result `BACKTEST3Y_RESULT.md`): `bl_bt3_data.py` (full chains, ~2 min) → `bl_bt3_split.py` → `bl_bt3_freeze.py` (before any run) → `bl_bt3_check.py` (identity vs the earlier D0 simulator) → `bl_bt3_run.py IS|OOS|LIVE_FITTED A/V1|B/V2 [hold]` → `bl_bt3_stress.py` → `bl_bt3_metrics.py` → `make_bt3_report.py`. OOS is run once after the freeze.

Seasonality / regime investigation of the 3-year backtest (plan `BACKTEST3Y_REGIME_PLAN.md`, report `BACKTEST3Y_REGIME.md`; exploratory): `bl_bt3_run.py LIVE_FITTED A/V1 hold` (diagnostic) → `bl_bt3_regime.py` (~5 min) → `make_regime_report.py`.
