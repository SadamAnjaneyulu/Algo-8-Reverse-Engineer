"""Decision B measurement (READ-ONLY, scratch): reversal definitions under the baseline and hybrid orderings, full ledger and the two frozen cycles.
(a) per-fill zero crossing: one fill takes inventory from one non-zero sign to the opposite non-zero sign.
(b) parent-level same-second flip: for (instrument, parent, second): sign of inventory before the parent's first fill that second != sign after its last, both non-zero (other parents' interleaved fills included).
(c) instrument-level same-second flip: same, for the whole (instrument, second) group (any parents)."""
import sys, collections, json
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
from pe.generators import historical as H
from pe import replay as rp
REPO = '/home/user/Algo-8-Reverse-Engineer'
ins, fills, _ = H.generate(REPO)
sgn = lambda x: (x > 0) - (x < 0)
def run(policy, subset=None):
    f2 = H.attach_tie_keys(REPO, fills, policy); eo = 'src' if policy == 'source_row' else policy
    ev = rp.order_events(f2, eo); inv = collections.defaultdict(int); a = []; B = {}; C = {}
    for f in ev:
        if subset and f.instrument_id not in subset: continue
        b = inv[f.instrument_id]; af = b + f.side * f.quantity; inv[f.instrument_id] = af
        if sgn(b) * sgn(af) < 0: a.append(f.source_row_id)
        k = (f.instrument_id, f.parent_order_id, f.timestamp_s); B.setdefault(k, [b, af]); B[k][1] = af
        k2 = (f.instrument_id, f.timestamp_s); C.setdefault(k2, [b, af]); C[k2][1] = af
    flip = lambda d: sorted(k for k, (b, af) in d.items() if sgn(b) * sgn(af) < 0)
    b1 = flip(B); c1 = flip(C)
    return dict(per_fill=len(a), per_fill_rows=a, parent_level=len(b1), parent_level_keys=[list(k) for k in b1], instrument_level=len(c1), instrument_level_keys=[list(k) for k in c1])
out = {}
for name, sub in (('full_ledger', None), ('NIFTY_2026-06-30', {i for i, x in ins.items() if x.underlying == 'NIFTY' and x.expiry == '2026-06-30'}), ('SENSEX_2026-07-16', {i for i, x in ins.items() if x.underlying == 'SENSEX' and x.expiry == '2026-07-16'})):
    out[name] = {p: run(p, sub) for p in ('source_row', 'per_contract_id_sequence')}
    for p, r in out[name].items(): print(name, p, 'per_fill', r['per_fill'], 'parent_level', r['parent_level'], 'instrument_level', r['instrument_level'])
json.dump(out, open('/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/p1/reversal_defs_result.json', 'w'), indent=1)
b = out['full_ledger']['source_row']; print('parent-level but not per-fill (parents):', [k for k in b['parent_level_keys']][:30])
pf = set(b['per_fill_rows'])
