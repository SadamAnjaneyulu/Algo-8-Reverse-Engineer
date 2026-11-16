"""Track E: Python-version sensitivity of the stdlib engine core. Reads the generated events TSV (no pandas), prints sha256 of every engine output (dump for 3 methods, lineage files, closing-batch files). Run under 3.11 / 3.12 / 3.13 and diff.
usage: <python> pyver_compat.py <scratch tree root> ; also runs strict=True (invariant path with float sum())"""
import hashlib, os, sys, json
root = sys.argv[1]; PE = os.path.join(root, 'portfolio_engine'); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tsvio, replay as rp, closing_batches as cb
from pe.lineage_set import LineageSet
ins = tsvio.read_instruments(os.path.join(PE, 'data_generated', 'historical_instruments.tsv')); fills = tsvio.read_events(os.path.join(PE, 'data_generated', 'historical_events.tsv'), ins)
h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]; out = {'python': sys.version.split()[0]}
for m in ('FIFO', 'LIFO', 'AVG'):
    R = rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', m, 'src', 5000, False, True); out[f'dump_{m}'] = h(R.dump); out[f'checks_{m}'] = len(R.checks)
    for n, t in rp.lineage_files(R).items(): out[f'{n}'] = h(t)
ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); out['ls_check'] = ls.check(fills)[:3] and len(ls.check(fills))
parents, unattr, multi = cb.closing_parents(ls); V = cb.all_views(parents)
for m in ('C1', 'C2'):
    for n, t in cb.files_for_method(V, m, ls).items(): out[n] = h(t)
R = rp.replay(fills[:3000], ins, 'HISTORICAL_OBSERVED_REPLAY', 'AVG', 'src', 0, True, False)    # strict AVG on a prefix (float sum() in invariants)
out['strict_avg_prefix_ok'] = True
print(json.dumps(out, sort_keys=True))
