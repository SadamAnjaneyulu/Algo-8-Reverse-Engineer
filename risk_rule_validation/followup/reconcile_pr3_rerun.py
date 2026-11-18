"""Follow-up audit: compare PR #3's committed outputs with the sandbox re-run (identical code except a session-aware minute_index).
Reads   analysis/exit_engine/results/            (PR #3, unchanged)
        <sandbox>/analysis/exit_engine/results/  (re-run; path in env RERUN_SANDBOX)
Writes  risk_rule_validation/followup/results/pr3_rerun_file_diff.csv, pr3_rerun_lot_changes.csv, pr3_rerun_key_metrics.csv, copies of re-run CSVs
python3 risk_rule_validation/followup/reconcile_pr3_rerun.py"""
import os, sys, shutil, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE); sys.path.insert(0, RR)
import rr_common as rc
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
SB = os.environ['RERUN_SANDBOX']
OLD = os.path.join(rc.AN, 'exit_engine', 'results'); NEW = os.path.join(SB, 'analysis', 'exit_engine', 'results')
OLDC = os.path.join(rc.AN, '_cache'); NEWC = os.path.join(SB, 'analysis', '_cache')


def csv_diff():
    rows = []
    for p in sorted(glob.glob(os.path.join(OLD, '*.csv'))):
        f = os.path.basename(p); q = os.path.join(NEW, f)
        if not os.path.exists(q): rows.append(dict(file=f, status='not produced by re-run')); continue
        a = pd.read_csv(p); b = pd.read_csv(q)
        r = dict(file=f, rows_old=len(a), rows_new=len(b), cols_old=a.shape[1], cols_new=b.shape[1])
        if a.shape == b.shape and list(a.columns) == list(b.columns):
            num = a.select_dtypes('number').columns
            da = a[num].to_numpy(float); db = b[num].to_numpy(float)
            ch = ~((np.isclose(da, db, rtol=1e-9, atol=1e-9)) | (np.isnan(da) & np.isnan(db)))
            nonnum = [c for c in a.columns if c not in num]
            chs = (a[nonnum].astype(str).values != b[nonnum].astype(str).values) if nonnum else np.zeros((len(a), 0), bool)
            r.update(status='identical' if not ch.any() and not chs.any() else 'changed', numeric_cells=int(da.size), numeric_cells_changed=int(ch.sum()),
                     text_cells_changed=int(chs.sum()), rows_changed=int((ch.any(axis=1) | chs.any(axis=1)).sum()),
                     max_abs_change=float(np.nanmax(np.abs(np.where(ch, da - db, 0)))) if ch.any() else 0.0)
        else:
            r.update(status='changed (shape)')
        rows.append(r)
    for p in sorted(glob.glob(os.path.join(OLD, '*.txt'))):
        f = os.path.basename(p); q = os.path.join(NEW, f)
        if os.path.exists(q):
            same = open(p).read() == open(q).read()
            rows.append(dict(file=f, status='identical' if same else 'changed (text report)'))
    D = pd.DataFrame(rows); D.to_csv(os.path.join(OUT, 'pr3_rerun_file_diff.csv'), index=False); return D


def lot_changes():
    rows = []
    for conv in rc.CONVS:
        a = pd.read_pickle(os.path.join(OLDC, f'exit_lots_{conv}.pkl')); b = pd.read_pickle(os.path.join(NEWC, f'exit_lots_{conv}.pkl'))
        k = ['und', 'expiry', 'cp', 'strike', 'sgn', 'entry_oid', 'exit_oid']
        for df in (a, b): df['_n'] = df.groupby(k, dropna=False).cumcount()
        m = a.merge(b, on=k + ['_n'], how='outer', suffixes=('_old', '_new'), indicator=True)
        m['carried_changed'] = m.carried_old.fillna(False).astype(bool) != m.carried_new.fillna(False).astype(bool)
        m['entry_day_changed'] = m.entry_day_old != m.entry_day_new
        for (u, e), g in m.groupby(['und', 'expiry']):
            rows.append(dict(convention=conv, und=u, expiry=e.date(), lots=len(g), unmatched=int((g._merge != 'both').sum()),
                             carried_flag_changed=int(g.carried_changed.sum()), entry_day_changed=int(g.entry_day_changed.sum()),
                             carried_short_old=int((g.carried_old.fillna(False).astype(bool) & (g.sgn < 0)).sum()), carried_short_new=int((g.carried_new.fillna(False).astype(bool) & (g.sgn < 0)).sum()),
                             carried_long_old=int((g.carried_old.fillna(False).astype(bool) & (g.sgn > 0)).sum()), carried_long_new=int((g.carried_new.fillna(False).astype(bool) & (g.sgn > 0)).sum())))
    R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'pr3_rerun_lot_changes.csv'), index=False)
    # cross-check against the risk_rule_validation ledger
    chk = []
    for conv in rc.CONVS:
        b = pd.read_pickle(os.path.join(NEWC, f'exit_lots_{conv}.pkl')); c = rc.ledger(conv)
        for (u, e), g in b.groupby(['und', 'expiry']):
            h = c[(c.und == u) & (c.expiry == e)]
            chk.append(dict(convention=conv, und=u, expiry=e.date(), rerun_carried_short=int((g.carried & (g.sgn < 0)).sum()), rr_carried_short=int((h.carried & (h.sgn < 0)).sum()),
                            rerun_carried_long=int((g.carried & (g.sgn > 0)).sum()), rr_carried_long=int((h.carried & (h.sgn > 0)).sum())))
    C = pd.DataFrame(chk); C['agree'] = (C.rerun_carried_short == C.rr_carried_short) & (C.rerun_carried_long == C.rr_carried_long)
    C.to_csv(os.path.join(OUT, 'pr3_rerun_vs_rr_ledger_check.csv'), index=False)
    return R, C


if __name__ == '__main__':
    D = csv_diff(); R, C = lot_changes()
    keep = os.path.join(OUT, 'pr3_rerun_outputs'); os.makedirs(keep, exist_ok=True)
    for f in D[D.status.astype(str).str.startswith('changed')].file:
        shutil.copy(os.path.join(NEW, f), os.path.join(keep, f))
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 120)
    print(D.to_string(index=False))
    print(R.groupby('convention')[['lots', 'unmatched', 'carried_flag_changed', 'entry_day_changed']].sum())
    print('cycles with carried changes:', R[R.carried_flag_changed > 0].groupby('convention').expiry.nunique().to_dict())
    print('re-run ledger == risk_rule_validation ledger (carried counts):', C.agree.all(), C.agree.sum(), len(C))
