"""Item 2: recompute the two reversal measures from the raw CSV (own code) for the full ledger and the two frozen cycles, under baseline and hybrid ordering.
PER_FILL: before*after < 0 for one fill.  PARENT_LEVEL: per (instrument, parent, second) group, sign(inventory before the group's first fill) * sign(inventory after its last fill) < 0."""
import json
from collections import OrderedDict
import rawload as R

sgn = lambda x: (x > 0) - (x < 0)


def measures(ordered):
    inv = {}; pf = []; groups = OrderedDict()
    for f in ordered:
        b = inv.get(f['inst'], 0); a = b + f['side'] * f['qty']; inv[f['inst']] = a
        if sgn(b) * sgn(a) < 0: pf.append((f['row'], f['inst'], f['parent'], f['ts']))
        k = (f['inst'], f['parent'], f['ts'])
        g = groups.get(k)
        if g is None: g = groups[k] = dict(b=b, a=a, rows=[])
        g['a'] = a; g['rows'].append(f['row'])
    pl = [(k, g['rows'], g['b'], g['a']) for k, g in groups.items() if sgn(g['b']) * sgn(g['a']) < 0]
    return pf, pl


rows = R.load(); out = {}
scopes = {'full': lambda r: True, 'NIFTY_2026-06-30': lambda r: r['und'] == 'NIFTY' and r['expiry'] == '2026-06-30', 'SENSEX_2026-07-16': lambda r: r['und'] == 'SENSEX' and r['expiry'] == '2026-07-16'}
for sc, pred in scopes.items():
    sub = [r for r in rows if pred(r)]
    for name, order in (('baseline', R.order_baseline), ('hybrid', R.order_hybrid)):
        pf, pl = measures(order(sub)); out[f'{sc}|{name}'] = dict(per_fill=len(pf), parent_level=len(pl), per_fill_rows=[p[0] for p in pf], parent_level_groups=[dict(inst=k[0], parent=k[1], ts=k[2], rows=rr, before=b, after=a) for k, rr, b, a in pl])
        print(sc, name, 'per-fill', len(pf), 'parent-level', len(pl))
# overlap analysis on baseline full
pf, pl = measures(R.order_baseline(rows)); pfrows = {p[0] for p in pf}
both = [g for g in pl if any(r in pfrows for r in g[1])]
only_pl = [g for g in pl if not any(r in pfrows for r in g[1])]
pf_in_pl_rows = {r for g in pl for r in g[1]}
only_pf = [p for p in pf if p[0] not in pf_in_pl_rows]
print('baseline full: parent-level groups containing a per-fill crossing fill of the same group:', len(both), '| parent-level groups with NO per-fill crossing inside the group (crossing made by another parent or via zero):', len(only_pl),
      '| per-fill crossings not inside any parent-level flip group:', len(only_pf))
out['overlap_baseline_full'] = dict(pl_with_pf=len(both), pl_without_pf=len(only_pl), pf_without_pl=len(only_pf), only_pl_groups=[dict(inst=g[0][0], parent=g[0][1], ts=g[0][2], rows=g[1]) for g in only_pl], only_pf_rows=[p[0] for p in only_pf])
# a per-fill crossing the parent-level measure counts as TWO flips? groups per (inst,parent): count parents with >1 flip group
from collections import Counter
c = Counter((g[0][0], g[0][1]) for g in pl); print('parents with more than one parent-level flip group:', sum(1 for v in c.values() if v > 1))
# how many parent-level groups contain fills of other parents interleaved between its first and last fill (same instrument, same second)?
base = R.order_baseline(rows); pos = {f['row']: i for i, f in enumerate(base)}; inter = 0
for k, rr, b, a in pl:
    ii = [pos[r] for r in rr]; lo, hi = min(ii), max(ii)
    others = [f for f in base[lo:hi + 1] if f['inst'] == k[0] and f['ts'] == k[2] and f['parent'] != k[1]]
    inter += bool(others)
print('parent-level flip groups with another parent of the same instrument inside the window (baseline):', inter)
out['pl_groups_with_interleaved_other_parent_baseline'] = inter
json.dump(out, open('item2_reversals_result.json', 'w'), indent=1)
