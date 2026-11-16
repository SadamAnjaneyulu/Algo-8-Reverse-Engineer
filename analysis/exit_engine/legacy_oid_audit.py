"""Audit of the base-branch scripts that group by the reused column-4 order id ('oid').  Nothing in analysis/ (outside exit_engine/),
FINDINGS.md or alpha_freeze/ is modified: affected scripts are re-run in a sandbox copy twice - 'orig' (as committed) and 'fixed'
(load.py keys orders by column 163) - and their printed outputs are diffed.
Static part (exact counts): for every script, the rows it groups, the real orders behind them, how many oid groups merge >1 real order.
Dependency part: which caches / findings / frozen inputs consume each script's output.
python3 analysis/exit_engine/legacy_oid_audit.py -> results/legacy_oid_audit.csv, results/legacy_oid_audit_diffs.txt"""
import sys, os, shutil, subprocess, difflib, re
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); ROOT = os.path.dirname(AN); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from load import load_tagged
from common import RES, C
SANDBOX = os.environ.get('LEGACY_AUDIT_DIR', '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/legacy_audit')

SCRIPTS = {  # script: (how oid is used, filter of the grouped rows, consumers, findings that rely on it, rerunnable in sandbox)
    'modules.py': ('groupby(oid).first() over all fills -> order table (limit-band ratio r = px_order/px_fill per module)', lambda d: d,
                   'printed module statistics only', 'FINDINGS: module / tag table, marketable-limit band (+15 %/-15 %, v_ +3 %)', True),
    'report.py': ('orders = g.oid.nunique() per cycle (count only)', lambda d: d, 'printed cycle report', 'FINDINGS: per-cycle order counts', True),
    'alpha_by_module.py': ('first fill per oid -> decision phase -> module label (grid A / clock B / :00 / unchained)', lambda d: d[(d.tp == 'num') & (d.side == 'Sell')],
                           'printed module P&L attribution', 'FINDINGS v6/v7: alpha by module (hold P&L of sales by module)', True),
    'p6_stop_metric.py': ('order counts for the brokerage-adjusted variant only (groupby(oid).t.min(), pre.oid.nunique())', lambda d: d,
                          '_cache/p6_metrics.pkl', 'FINDINGS P6: cycle-stop metric (only its cost-adjusted variant uses oid)', True),
    'p4_strike.py': ('groupby(oid).first() over body sales (px >= 10) -> one row per sale order with chosen strike', lambda d: d[(d.tp == 'num') & (d.side == 'Sell') & (d.px_fill >= 10)],
                     '_cache/p4_orders.pkl -> (p4_orders_feat / p4_orders_prem / p4_orders_cons: writer not in repo) -> p4_ml.py, p4_book.py, a7_transfer.py, b2_*, ml_followups.py',
                     'FINDINGS P4: strike selection (68.5 % top-1), delta-target strikes, premium-target rejection', True),
    'a7_transfer.py': ('groupby(oid).first() over body orders (px >= 5); also reads p4_orders_cons (built from the oid-keyed P4 chain)', lambda d: d[(d.tp == 'num') & (d.px_fill >= 5)],
                       'printed Algo 7 transfer tests', 'FINDINGS v8: Algo 7 cross-insights (delta-target strikes, momentum rebalancing)', True),
    'p4_ml.py': ('groupby(oid) to rank candidates within an order and pick argmax; input p4_orders_prem (oid-keyed P4 chain)', None,
                 '_cache/p4_candidates.pkl -> p4_book.py', 'FINDINGS P4: LightGBM candidate-choice accuracy', False),
    'p4_book.py': ('groupby(oid) to rank candidates within an order; input p4_candidates + p4_orders_cons', None,
                   '_cache/p4_candidates_book.pkl', 'FINDINGS P4: book-state features add < 1 pt', False),
}

def static_counts(d):
    rows = []
    for s, (use, filt, cons, fnd, rerun) in SCRIPTS.items():
        r = dict(script=s, oid_use=use, consumers=cons, findings=fnd)
        if filt is not None:
            x = filt(d); g = x.groupby('oid').tag.nunique()
            r.update(rows_grouped=len(x), real_orders=x.tag.nunique(), oid_groups=len(g), oid_groups_merging=int((g > 1).sum()),
                     real_orders_lost_by_first=int(x.tag.nunique() - len(g)), share_lost=(x.tag.nunique() - len(g)) / max(x.tag.nunique(), 1))
        rows.append(r)
    # cached P4 tables built with the oid key: how many of their rows sit on an oid that is reused by several real orders
    reused = d.groupby('oid').tag.nunique(); reused = set(reused[reused > 1].index)
    for f in ('p4_orders.pkl', 'p4_orders_cons.pkl', 'p4_candidates.pkl'):
        p = os.path.join(C, f)
        if not os.path.exists(p): continue
        x = pd.read_pickle(p); n_reused = int(x.oid.astype(str).isin(reused).sum())
        span = x.groupby('oid').date.nunique() if 'date' in x else None
        rows.append(dict(script=f'cache {f}', oid_use='table keyed by oid', rows_grouped=len(x), oid_groups=x.oid.nunique(),
                         oid_groups_merging=int((span > 1).sum()) if span is not None else np.nan, rows_on_reused_oid=n_reused, share_lost=n_reused / len(x)))
    return pd.DataFrame(rows)

def sandbox_run(names):
    out = {}
    for variant in ('orig', 'fixed'):
        base = os.path.join(SANDBOX, variant); an = os.path.join(base, 'analysis'); cd = os.path.join(an, '_cache')
        if os.path.exists(base): shutil.rmtree(base)
        os.makedirs(cd)
        for f in os.listdir(AN):
            if f.endswith('.py'): shutil.copy(os.path.join(AN, f), an)
        for f in ('idx_candles.pkl', 'opt_candles.pkl', 'p4_orders_cons.pkl', 'indicators_index.pkl', 'indicators_options.pkl'):
            if os.path.exists(os.path.join(C, f)): shutil.copy(os.path.join(C, f), cd)          # copies, never symlinks: sandbox writes stay in the sandbox
        os.symlink(os.path.join(ROOT, 'Trades_GKOHNP140.csv'), os.path.join(base, 'Trades_GKOHNP140.csv'))
        if variant == 'fixed':
            p = os.path.join(an, 'load.py'); s = open(p).read()
            assert "'oid': r[4]" in s; s = s.replace("'oid': r[4]", "'oid': r[163]"); open(p, 'w').write(s)
        for n in names:
            try:
                res = subprocess.run([sys.executable, n], cwd=an, capture_output=True, text=True, timeout=3600)
                out[(variant, n)] = (res.returncode, res.stdout, res.stderr[-2000:])
            except subprocess.TimeoutExpired:
                out[(variant, n)] = (-9, '', 'timeout')
    return out

def numbers(line): return re.findall(r'-?\d+\.?\d*', line)

if __name__ == '__main__':
    d = load_tagged()
    S = static_counts(d)
    # cycle list behind the frozen grid: alpha_split (und, expiry) vs cycles with both D-1 and D0 fills (oid-free definition)
    A = pd.read_pickle(os.path.join(C, 'alpha_split.pkl'))
    both = d.groupby(['und', 'expiry']).dte.agg(lambda x: (x >= 1).any() and (x == 0).any())
    oidfree = {(u, str(pd.Timestamp(e).date())) for u, e in both[both].index}
    al = {(u, str(pd.Timestamp(e).date())) for u, e in zip(A.und, A.expiry)}
    S = pd.concat([S, pd.DataFrame([dict(script='alpha_freeze inputs: cycle list (alpha_split)', oid_use='none (und, expiry only)',
                                         rows_grouped=len(al), oid_groups=len(oidfree), oid_groups_merging=len(al ^ oidfree),
                                         findings='frozen dev grid reads idx/opt candles + this cycle list only')])], ignore_index=True)
    names = [s for s, v in SCRIPTS.items() if v[4]]
    R = sandbox_run(names)
    diffs = []; dyn = []
    for n in names:
        (c0, o0, e0), (c1, o1, e1) = R[('orig', n)], R[('fixed', n)]
        a, b = o0.splitlines(), o1.splitlines()
        dl = [l for l in difflib.unified_diff(a, b, 'orig', 'fixed', lineterm='', n=0) if not l.startswith(('---', '+++', '@@'))]
        changed = sum(1 for l in dl if l.startswith('-'))
        dyn.append(dict(script=n, orig_exit=c0, fixed_exit=c1, output_lines=len(a), changed_lines=changed, identical=(a == b) and c0 == 0 and c1 == 0))
        diffs.append(f'===== {n}  (orig exit {c0}, fixed exit {c1}; changed lines {changed}/{len(a)}) =====\n' + '\n'.join(dl[:400]) +
                     (f'\n[stderr orig] {e0}' if c0 else '') + (f'\n[stderr fixed] {e1}' if c1 else '') + '\n')
    D = S.merge(pd.DataFrame(dyn), on='script', how='left')
    D.to_csv(os.path.join(RES, 'legacy_oid_audit.csv'), index=False)
    open(os.path.join(RES, 'legacy_oid_audit_diffs.txt'), 'w').write('\n'.join(diffs))
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
    print(D.drop(columns=['oid_use', 'consumers', 'findings']).round(4).to_string(index=False))
