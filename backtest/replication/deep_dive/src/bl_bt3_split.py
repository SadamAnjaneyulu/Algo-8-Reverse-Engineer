"""Explicit in-sample / out-of-sample division of the 3-year cycles (plan reports/BACKTEST3Y_PLAN.md, addendum 1). Uses the boundary of the earlier backtest (bt/config.py): IS = D0 <= 2025-11-17.
split3: IS (development, may be inspected) | OOS (locked, after the IS boundary, never used for the rule fit) | LIVE_FITTED (2026-06-22..2026-10-22: the cycles the rules were fitted on, in-sample for the rules, NOT out-of-sample) | EMBARGO (D-1 in IS, D0 in OOS: excluded from both)."""
import sys, os; sys.path.insert(0, '.')
import pandas as pd
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv')
m = {'IS': 'IS', 'OOS_CLEAN_BEFORE': 'OOS', 'OOS_CLEAN_AFTER': 'OOS', 'OOS_EXPOSED': 'LIVE_FITTED', 'EMBARGO': 'EMBARGO'}; T['split3'] = T.subset.map(m); T.to_csv(f'{OUT}/bl_bt3_cycles.csv', index=False)
t = T.groupby(['split3', 'und']).agg(cycles=('expiry', 'size'), first_d0=('d0', 'min'), last_d0=('d0', 'max')).reset_index(); print(t.to_string(index=False)); print(T.split3.value_counts().to_dict())
