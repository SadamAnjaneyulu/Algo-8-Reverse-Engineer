"""TP-02 Phase 3: the profitable short closings and their populations, one row per closing fill.
python3 tp_reconstruction/tp02/scripts/isolate_nonstop_exits.py -> tp02/data/profitable_nonstop_candidates.parquet
Pop 1 stable PROFIT (all three conventions) | Pop 1b convention-sensitive PROFIT (kept apart, never merged into Pop 1) | Pop 2 stop-related | Pop 3 clean non-stop body | Pop 4 / 4S unexplained (registered / strict flags)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp02_common as c

KEEP = ['close_row', 'contract_id', 'und', 'expiry', 'strike', 'cp', 'module', 'parent_oid', 't_exec', 'day_type', 'phase', 'expiry_category', 'exec_minute', 'qty_closed', 'exit_qty_lots', 'inventory_before_lots', 'exit_type', 'session_relation',
        'px_fill', 'profit_class', 'consensus_label', 'stability', 'label_FIFO', 'label_LIFO', 'label_AVG', 'pnl_rupees_FIFO', 'pnl_rupees_LIFO', 'pnl_rupees_AVG', 'ref_px_FIFO', 'ref_px_LIFO', 'ref_px_AVG', 'exit_ratio_FIFO', 'exit_ratio_LIFO', 'exit_ratio_AVG',
        'stop_class', 'stop_reasons', 'adverse_ratio_max_15m', 'in_cycle_stop_window', 'flag_clock', 'flag_expiry_mgmt', 'flag_replacement', 'flag_replacement_strict', 'flag_wing_linked', 'flag_wing_linked_strict', 'flag_basket', 'basket_other_contracts', 'basket_both_rights', 'basket_has_loss_leg',
        'candidate_mechanism', 'mechanism_flags', 'confidence', 'order_ambiguous', 'dq_flag_any', 'pop1_profit_stable', 'pop2_stop_related', 'pop3_clean_nonstop', 'pop4_unexplained_body', 'pop4s_unexplained_strict']


def main():
    T = pd.read_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet')); S = T[(T.direction == -1) & T.profit_class.isin(['STABLE_PROFIT', 'SENSITIVE_PROFIT'])]
    O = S[KEEP].copy(); O['population'] = np.select([O.pop4_unexplained_body, O.pop4s_unexplained_strict, O.pop3_clean_nonstop, O.pop2_stop_related, O.pop1_profit_stable], ['POP4_UNEXPLAINED_REGISTERED', 'POP4S_UNEXPLAINED_STRICT', 'POP3_CLEAN_NONSTOP', 'POP2_STOP_RELATED', 'POP1_OTHER_STABLE_PROFIT'], 'POP1B_CONVENTION_SENSITIVE')
    O.to_parquet(os.path.join(c.DATA, 'profitable_nonstop_candidates.parquet'), index=False); print(len(O)); print(O.population.value_counts().to_dict())


if __name__ == '__main__':
    main()
