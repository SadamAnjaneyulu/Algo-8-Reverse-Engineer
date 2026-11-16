"""Task D extension: dump bytes + lineage files for the primary convention at 562d7eb6 vs HEAD (run once per PYTHONPATH; prints sha256s)."""
import sys, hashlib, json
from pe.generators import historical as H
from pe import replay as rp
from pe.lineage_set import LineageSet
repo = '/home/user/Algo-8-Reverse-Engineer'
ins, fills = H.generate(repo)[:2]; out = {}
for m in ('FIFO', 'LIFO', 'AVG'):
    r = rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', m, 'src', lineage=True)
    out[m] = dict(dump=hashlib.sha256(r.dump.encode()).hexdigest(), lineage={k: hashlib.sha256(v.encode()).hexdigest() for k, v in rp.lineage_files(r).items()}, roles=hashlib.sha256(rp.roles_tsv(r.roles).encode()).hexdigest())
if len(sys.argv) > 1:
    r = rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', sys.argv[1], lineage=True); out['alias_'+sys.argv[1]] = hashlib.sha256(r.dump.encode()).hexdigest()
print(json.dumps(out, sort_keys=True))
