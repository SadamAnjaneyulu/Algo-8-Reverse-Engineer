"""Final dependency audit, task 1: PR #5 (analysis/allocation) re-run on the session-aware ledger.
Three versions of every PR #5 result file are compared:
  committed  analysis/allocation/results/                        (PR #5, untouched)
  control    <CONTROL_SANDBOX>/analysis/allocation/results/      (same code, PR #3 minute mapping: must reproduce 'committed')
  corrected  <RERUN_SANDBOX>/analysis/allocation/results/        (same code, session-aware minute_index only)
noise = control - committed;  patch effect = corrected - control.
Writes risk_rule_validation/pr5_corrected_ledger_comparison.csv (cell level for metric tables, summary rows for row-level ledgers)
and final_audit/results/pr5_file_summary.csv, pr5_rerun_outputs/ (corrected metric tables).
python3 risk_rule_validation/final_audit/pr5_compare.py"""
import os, sys, glob, shutil
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE); sys.path.insert(0, RR)
import rr_common as rc
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
OLD = os.path.join(rc.AN, 'allocation', 'results')
NEW = os.path.join(os.environ['RERUN_SANDBOX'], 'analysis', 'allocation', 'results')
CTL = os.path.join(os.environ['CONTROL_SANDBOX'], 'analysis', 'allocation', 'results')
ROW_LEVEL = {'allocation_lots.csv.gz', 'position_lifecycle_ledger.csv.gz', 'position_lifecycle_ledger.csv', 'replacement_event_links.csv', 'replacement_ownership_pairs.csv.gz',
             'stop_exit_refs.csv.gz', 'stop_ref_counts.csv.gz', 'unresolved_position_links.csv', 'replacement_hedge_links.csv', 'allocation_ledger_slot.csv', 'allocation_ledger_chain.csv'}


def cells(a, b):
    """(numeric changed mask, text changed mask) for two same-shaped frames"""
    num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c])]
    txt = [c for c in a.columns if c not in num]
    A = a[num].to_numpy(float); B = b[num].to_numpy(float)
    chn = ~(np.isclose(A, B, rtol=1e-9, atol=1e-12) | (np.isnan(A) & np.isnan(B)))
    cht = (a[txt].fillna('').astype(str).values != b[txt].fillna('').astype(str).values) if txt else np.zeros((len(a), 0), bool)
    return num, txt, chn, cht


def main():
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(OLD, '*.csv*')))
    summ, long = [], []
    keep = os.path.join(OUT, 'pr5_rerun_outputs'); os.makedirs(keep, exist_ok=True)
    for f in files:
        pa, pb, pc = (os.path.join(d, f) for d in (OLD, CTL, NEW))
        r = dict(file=f, kind='row-level ledger' if f in ROW_LEVEL else 'metric table')
        if not (os.path.exists(pb) and os.path.exists(pc)):
            r['status'] = 'not produced by the re-run'; summ.append(r); continue
        a, b, c = pd.read_csv(pa, low_memory=False), pd.read_csv(pb, low_memory=False), pd.read_csv(pc, low_memory=False)
        r.update(rows_committed=len(a), rows_control=len(b), rows_corrected=len(c))
        if a.shape == b.shape and list(a.columns) == list(b.columns):
            _, _, n1, t1 = cells(a, b); r['control_reproduces_committed'] = not (n1.any() or t1.any()); r['noise_cells'] = int(n1.sum() + t1.sum())
        else: r['control_reproduces_committed'] = False; r['noise_cells'] = np.nan
        if b.shape == c.shape and list(b.columns) == list(c.columns):
            num, txt, n2, t2 = cells(b, c)
            B = b[num].to_numpy(float); Cc = c[num].to_numpy(float)
            r.update(status='identical' if not (n2.any() or t2.any()) else 'changed', numeric_cells=int(B.size), numeric_cells_changed=int(n2.sum()), text_cells_changed=int(t2.sum()),
                     rows_changed=int((n2.any(axis=1) | (t2.any(axis=1) if t2.size else False)).sum()),
                     max_abs_change=float(np.nanmax(np.abs(np.where(n2, Cc - B, 0)))) if n2.any() else 0.0)
            if f not in ROW_LEVEL and n2.any():
                key = b[txt].fillna('').astype(str).agg(' | '.join, axis=1) if txt else pd.Series([''] * len(b))
                for i, j in zip(*np.where(n2)):
                    long.append(dict(file=f, row=int(i), row_key=key.iloc[i], column=num[j], committed=float(a[num[j]].iloc[i]) if a.shape == b.shape else np.nan,
                                     control=B[i, j], corrected=Cc[i, j], abs_change=Cc[i, j] - B[i, j],
                                     rel_change=(Cc[i, j] - B[i, j]) / abs(B[i, j]) if B[i, j] not in (0, np.nan) and np.isfinite(B[i, j]) and B[i, j] != 0 else np.nan))
        else:
            r.update(status='changed (rows or columns differ)', rows_changed=abs(len(c) - len(b)))
        if r.get('status', '').startswith('changed') and f not in ROW_LEVEL: shutil.copy(pc, os.path.join(keep, f))
        summ.append(r)
    for f in sorted(os.path.basename(p) for p in glob.glob(os.path.join(OLD, '*.txt'))):
        pa, pb, pc = (os.path.join(d, f) for d in (OLD, CTL, NEW))
        if os.path.exists(pb) and os.path.exists(pc):
            ta, tb, tc = open(pa).read(), open(pb).read(), open(pc).read()
            summ.append(dict(file=f, kind='text report', control_reproduces_committed=ta == tb, status='identical' if tb == tc else 'changed'))
            if tb != tc: shutil.copy(pc, os.path.join(keep, f))
    S = pd.DataFrame(summ); S.to_csv(os.path.join(OUT, 'pr5_file_summary.csv'), index=False)
    Lg = pd.DataFrame(long)
    rows_led = S[S.kind == 'row-level ledger'].assign(row=-1, row_key='(row-level ledger: summary only)', column='rows_changed', committed=lambda x: x.rows_committed, control=lambda x: x.rows_control,
                                                      corrected=lambda x: x.rows_corrected, abs_change=lambda x: x.rows_changed, rel_change=lambda x: x.rows_changed / x.rows_control)
    full = pd.concat([Lg, rows_led[['file', 'row', 'row_key', 'column', 'committed', 'control', 'corrected', 'abs_change', 'rel_change']]], ignore_index=True)
    full.to_csv(os.path.join(RR, 'pr5_corrected_ledger_comparison.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 100)
    print(S[['file', 'kind', 'control_reproduces_committed', 'status', 'rows_control', 'rows_corrected', 'numeric_cells', 'numeric_cells_changed', 'rows_changed', 'max_abs_change']].to_string(index=False))
    print('cell-level rows:', len(Lg))


if __name__ == '__main__':
    main()
