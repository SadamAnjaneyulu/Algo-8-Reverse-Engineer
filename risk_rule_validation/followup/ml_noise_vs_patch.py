"""Follow-up audit: separate the session-mapping patch effect from run-to-run nondeterminism in PR #3's ML outputs.
noise  = control (unpatched re-run) - PR #3 committed      patch = patched re-run - control
python3 risk_rule_validation/followup/ml_noise_vs_patch.py   (env RERUN_SANDBOX, CONTROL_SANDBOX)"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE); sys.path.insert(0, RR)
import rr_common as rc
OUT = os.path.join(HERE, 'results')
OLD = os.path.join(rc.AN, 'exit_engine', 'results')
NEW = os.path.join(os.environ['RERUN_SANDBOX'], 'analysis', 'exit_engine', 'results')
CTL = os.path.join(os.environ['CONTROL_SANDBOX'], 'analysis', 'exit_engine', 'results')
FILES = {'exit_model_metrics.csv': (['model', 'algorithm', 'split', 'note'], ['precision', 'recall', 'avg_precision', 'macro_f1', 'quantity_agreement']),
         'autonomous_replay_metrics_open.csv': (None, None), 'robustness_results.csv': (None, None)}


def compare(f, keys, metrics):
    a = pd.read_csv(os.path.join(OLD, f)); b = pd.read_csv(os.path.join(CTL, f)); c = pd.read_csv(os.path.join(NEW, f))
    if keys is None:
        keys = [x for x in a.columns if not pd.api.types.is_numeric_dtype(a[x])]
        metrics = [x for x in a.columns if pd.api.types.is_numeric_dtype(a[x])]
    for df in (a, b, c): df['_r'] = df.groupby(keys, dropna=False).cumcount()
    k = keys + ['_r']
    m = a.merge(b, on=k, how='outer', suffixes=('', '_ctl')).merge(c.rename(columns={x: x + '_new' for x in metrics}), on=k, how='outer')
    rows = []
    for x in metrics:
        if x not in a.columns: continue
        noise = (m[x + '_ctl'] - m[x]).abs(); patch = (m[x + '_new'] - m[x + '_ctl']).abs()
        rows.append(dict(file=f, metric=x, cells=int(m[x].notna().sum()), noise_cells=int((noise > 1e-9).sum()), noise_max=float(noise.max()), noise_median_nonzero=float(noise[noise > 1e-9].median()) if (noise > 1e-9).any() else 0.0,
                         patch_cells=int((patch > 1e-9).sum()), patch_max=float(patch.max()), patch_median_nonzero=float(patch[patch > 1e-9].median()) if (patch > 1e-9).any() else 0.0))
    m.to_csv(os.path.join(OUT, 'ml_three_way_' + f), index=False)
    return pd.DataFrame(rows), m


if __name__ == '__main__':
    allr = []
    for f, (k, mt) in FILES.items():
        if all(os.path.exists(os.path.join(p, f)) for p in (OLD, NEW, CTL)):
            r, m = compare(f, k, mt); allr.append(r)
        else:
            print('missing', f)
    R = pd.concat(allr, ignore_index=True); R.to_csv(os.path.join(OUT, 'ml_noise_vs_patch_summary.csv'), index=False)
    pd.set_option('display.width', 250); print(R.round(4).to_string(index=False))
