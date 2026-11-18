"""DESCRIPTIVE diagnostics of the order-number (raw col 4) and app-key (raw col 166) fields for the number-block audit. This does NOT implement or run any number-block batching interpretation:
it reports field properties and pair-level co-occurrence counts only. python3 portfolio_engine/tools/number_block_diagnostics.py -> reports/m2c_number_block_diagnostics.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE)
import numpy as np, pandas as pd
TP = os.path.join(REPO, 'tp_reconstruction', 'data')
L = pd.read_parquet(os.path.join(TP, 'fill_event_ledger.parquet')); R = pd.read_parquet(os.path.join(TP, 'fill_roles.parquet')); R = R[R.method == 'FIFO'][['src_row', 'close_qty']]; L = L.merge(R, on='src_row')
raw = pd.read_csv(os.path.join(REPO, 'Trades_GKOHNP140.csv'), header=None, dtype=str, keep_default_na=False, usecols=[4, 163, 166]); assert (raw[4].values == L.sort_values('src_row').order_no.values).all()
P = L.groupby('parent_oid').agg(date=('date', 'first'), app=('app_key', 'first'), no=('order_no', lambda s: int(s.iloc[0])), module=('module', 'first'), t_first=('epoch', 'min'), close_q=('close_qty', 'sum')).reset_index()
OUT = {}
OUT['parents'] = len(P); OUT['order_no_unique_per_date'] = bool(P.groupby('date').no.apply(lambda s: s.is_unique).all()); OUT['order_no_constant_within_parent'] = bool((L.groupby('parent_oid').order_no.nunique() == 1).all())
OUT['app_keys_last6'] = {k: int(v) for k, v in P.app.value_counts().items()}; OUT['app_key_full_length'] = sorted(raw[166].str.len().unique().tolist())
P = P.sort_values(['date', 'app', 'no']); P['d'] = P.groupby(['date', 'app']).no.diff(); P['blk'] = P.groupby(['date', 'app']).d.transform(lambda s: (s > 500).cumsum())
OUT['blocks_with_jump_gt_500'] = int(P.groupby(['date', 'app', 'blk']).ngroups)
q = lambda s: {str(k): float(v) for k, v in s.quantile([.5, .75, .9, .95, .99]).items()}
dd = P.d.dropna(); OUT['all_orders_consecutive_number_diff'] = dict(quantiles=q(dd), share_le_20=float((dd <= 20).mean()), share_le_500=float((dd <= 500).mean()), n_gt_500=int((dd > 500).sum()), n=int(len(dd)))
w = dd[dd <= 500]; OUT['within_block_diff'] = dict(quantiles=q(w), share_le_20=float((w <= 20).mean()))
C = P[P.close_q > 0].sort_values(['date', 'app', 'blk', 'no']).copy(); C['dc'] = C.groupby(['date', 'app', 'blk']).no.diff(); C['dt'] = C.groupby(['date', 'app', 'blk']).t_first.diff(); y = C.dropna(subset=['dc'])
OUT['closing_parents'] = int(len(C)); OUT['closing_parents_by_app'] = {k: int(v) for k, v in C.app.value_counts().items()}; OUT['closing_parents_by_module_and_app'] = {a: {m: int(n) for m, n in g.module.value_counts().items()} for a, g in C.groupby('app')}
OUT['closing_parent_adjacent_pairs_in_block'] = int(len(y)); OUT['closing_adjacent_number_diff'] = dict(quantiles=q(y.dc), share_le_20=float((y.dc <= 20).mean()))
OUT['pair_cooccurrence_(adjacent closing parents in one block; NOT batches)'] = dict(number_le_20_and_first_fill_gap_le_10s=int(((y.dc <= 20) & (y.dt.abs() <= 10)).sum()), number_le_20_only=int(((y.dc <= 20) & (y.dt.abs() > 10)).sum()), time_le_10s_only=int(((y.dc > 20) & (y.dt.abs() <= 10)).sum()), neither=int(((y.dc > 20) & (y.dt.abs() > 10)).sum()))
OUT['number_monotone_in_first_fill_time_within_block'] = dict(adjacent_inversions_share=float(((P[P.blk >= 0].sort_values(['date', 'app', 'blk', 'no']).groupby(['date', 'app', 'blk']).t_first.diff() < 0).mean())))
json.dump(OUT, open(os.path.join(PE, 'reports', 'm2c_number_block_diagnostics.json'), 'w'), indent=1); print(json.dumps(OUT, indent=1))
