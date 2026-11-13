"""Independent cross-check of TP-01's closing/opening status per parent order against the Stage 1 order-level ledger
(analysis/exit_engine/common.py::orders, read-only; decision-time ordering and per-order VWAP).
TP-01 orders fills by EXECUTION time; the Stage 1 ledger replays orders in decision-time order, so differences are expected exactly where an order
was decided before, but executed after, another module's order (stop-module overshoot, RSK-12).
python3 tp_reconstruction/scripts/crosscheck_stage1.py   (needs the Stage 1 caches in analysis/_cache; skipped with a message if absent)"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import tp_common as tc


def main():
    sys.path.insert(0, os.path.join(tc.REPO, 'analysis')); sys.path.insert(0, os.path.join(tc.REPO, 'analysis', 'exit_engine'))
    try:
        from exit_engine.common import orders
        o = orders()
    except Exception as e:
        print('Stage 1 order-level cache not available:', repr(e)[:200]); return
    L = pd.read_parquet(os.path.join(tc.DATA, 'fill_event_ledger.parquet')); R = pd.read_parquet(os.path.join(tc.DATA, 'fill_roles.parquet')); R = R[R.method == 'FIFO']
    x = R.merge(L[['src_row', 'parent_oid']], on='src_row'); g = x.groupby('parent_oid').agg(close_units=('close_qty', 'sum'), open_units=('open_qty', 'sum'))
    m = o.set_index('oid').join(g); m['stage1_closing'] = m.label != 'open'; m['tp01_closing'] = m.close_units > 0
    rows = [dict(item='parent orders compared', value=len(m)), dict(item='order lots equal (Stage 1 lots == TP-01 open+close units / lot)', value=float((abs(m.lots - (m.close_units + m.open_units) / m.und.map(tc.LOT)) < 1e-9).mean())),
            dict(item='both closing', value=int((m.stage1_closing & m.tp01_closing).sum())), dict(item='both opening', value=int((~m.stage1_closing & ~m.tp01_closing).sum())),
            dict(item='Stage 1 closing, TP-01 opening only', value=int((m.stage1_closing & ~m.tp01_closing).sum())), dict(item='Stage 1 opening, TP-01 closing (any part)', value=int((~m.stage1_closing & m.tp01_closing).sum())),
            dict(item='TP-01 orders with both closing and opening parts (reversal / mixed)', value=int(((m.close_units > 0) & (m.open_units > 0)).sum()))]
    d = m[m.stage1_closing != m.tp01_closing]
    for (tp, lab, stt), gg in d.groupby(['tp', 'label', 'tp01_closing']): rows.append(dict(item=f'difference: module {tp} | Stage 1 label {lab} | TP-01 closing={stt}', value=len(gg)))
    pd.DataFrame(rows).to_csv(os.path.join(tc.ANALYSIS, 'crosscheck_vs_stage1_ledger.csv'), index=False); print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()
