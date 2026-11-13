"""Differential test: an INDEPENDENT minimal reference matcher (different structure: signed running position + exact Fractions, written for this test only) against the engine's lineage on seeded random sequences with many reversals."""
import random
from fractions import Fraction
import pytest
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators.synthetic import Builder


def reference(fills, conv):
    """returns (roles{fill_id:(close,open)}, ca[(cp, source, qty, pnl)], realized_total) using exact arithmetic"""
    book = {}; roles = {}; ca = []; total = Fraction(0)
    for f in sorted(fills, key=lambda x: (x.timestamp_s, x.source_row_id, x.fill_id)):
        if f.is_duplicate_fill: continue
        b = book.setdefault(f.instrument_id, dict(pos=0, lots=[], pool_q=0, pool_v=Fraction(0)))
        pos = b['pos']; q = f.quantity; against = pos != 0 and (pos > 0) != (f.side > 0); close = min(q, abs(pos)) if against else 0; opn = q - close
        if close:
            d = 1 if pos > 0 else -1                                  # direction of the position being closed
            if conv == 'AVG':
                avg = b['pool_v'] / b['pool_q']; pnl = d * (f.price_paise - avg) * close; ca.append((f'CP:{f.fill_id}', 'POOL', close, pnl)); total += pnl
                b['pool_v'] -= avg * close; b['pool_q'] -= close
            else:
                need = close
                while need:
                    i = 0 if conv == 'FIFO' else -1; lot = b['lots'][i]; take = min(need, lot[1]); pnl = d * (f.price_paise - lot[2]) * take; ca.append((f'CP:{f.fill_id}', lot[0], take, Fraction(pnl))); total += pnl
                    lot[1] -= take; need -= take
                    if lot[1] == 0: b['lots'].pop(i)
            b['pos'] = pos + f.side * close
        if opn:
            if conv == 'AVG': b['pool_v'] += f.price_paise * opn; b['pool_q'] += opn
            else: b['lots'].append([f'OA:{f.fill_id}', opn, f.price_paise])
            b['pos'] = b['pos'] + f.side * opn
        if b['pos'] == 0: b['lots'] = []; b['pool_q'] = 0; b['pool_v'] = Fraction(0)
        roles[f.fill_id] = (close, opn)
    return roles, ca, total


def random_events(seed, n=400, n_inst=3):
    r = random.Random(seed); b = Builder('ref', seed); ids = [b.add_inst(strike=24000 + 50 * k) for k in range(n_inst)]; t = 0
    for k in range(n):
        t += r.randint(0, 5); b.fill(r.choice(ids), t, r.choice((-1, 1)), r.choice((20, 40, 65, 100, 130)), 5 * r.randint(10, 400), parent=f'p{k // 2}', dup=r.random() < 0.02)
    return b.out()


@pytest.mark.parametrize('seed', range(40))
def test_engine_equals_independent_reference(seed):
    ins, fills = random_events(seed); ls = LineageSet(fills, ins, 'SYNTHETIC_TEST', 'src'); ls.check(fills)
    for conv in METHODS:
        roles, ca, total = reference(fills, conv); eng = ls.runs[conv]
        # roles: close / open quantity of every fill (observed layer, must be identical for the three conventions)
        mine = {r[2]: 0 for r in ls.oa.values()}; got = {}
        for f in fills:
            if f.is_duplicate_fill: continue
            got[f.fill_id] = (ls.cp[f'CP:{f.fill_id}'][8] if f'CP:{f.fill_id}' in ls.cp else 0, ls.oa[f'OA:{f.fill_id}'][8] if f'OA:{f.fill_id}' in ls.oa else 0)
        assert got == roles, (seed, conv)
        rows = [(r[2], r[3] if conv != 'AVG' else 'POOL', r[4], Fraction(r[7]) if conv != 'AVG' else float(r[7])) for r in ls.ca[conv]]
        if conv == 'AVG':
            assert [(a[0], a[1], a[2]) for a in rows] == [(c[0], c[1], c[2]) for c in ca]; assert all(abs(a[3] - float(c[3])) <= 1e-6 * max(1, abs(a[3])) for a, c in zip(rows, ca))
            assert abs(eng.state.realized_total() - float(total)) <= 1e-4
        else:
            assert rows == [(c[0], c[1], c[2], c[3]) for c in ca], (seed, conv); assert eng.state.realized_total() == total
