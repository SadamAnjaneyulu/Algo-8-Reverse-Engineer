"""Gate 5c acceptance evaluation against the criteria fixed in reports/PHASE1_GATE5C_PLAN.md (incl. Addendum 1). Reads outputs/phase1/5c/{V0,X1,X1s364,X3}.json; writes outputs/phase1/5c/acceptance.json."""
import json, os, numpy as np, bl_common
OD = f'{bl_common.OUT}/phase1/5c'; L = lambda n: json.load(open(f'{OD}/{n}.json'))
def evaluate(name, base, var):
    b, v = base['OOF'], var['OOF']; out = {}; r = {}
    r['C1 overall keys F1 >= base - 0.003'] = (v['keys_F1_60s'], b['keys_F1_60s'] - 0.003, v['keys_F1_60s'] >= b['keys_F1_60s'] - 0.003)
    r['C2 legacy lot-level F1 >= 0.4103 - 0.005'] = (v['legacy_D0_OOF']['F1'], 0.4053, v['legacy_D0_OOF']['F1'] >= 0.4103 - 0.005)
    worst = min(((c, v['by_class'][c] - b['by_class'][c]) for c in b['by_class'] if c in v['by_class'] and b['by_class'][c] == b['by_class'][c] and v['by_class'][c] == v['by_class'][c]), key=lambda x: x[1])
    r['C3 every class F1 >= base - 0.02'] = (worst[1], -0.02, worst[1] >= -0.02); r['C3_worst_class'] = worst[0]
    d = {c: v['per_cycle'][c]['f1'] - b['per_cycle'][c]['f1'] for c in b['per_cycle']}; mn = min(d.values())
    r['C4 no cycle falls by > 0.05'] = (mn, -0.05, mn >= -0.05)
    fw = {s: var[s]['keys_F1_60s'] - base[s]['keys_F1_60s'] for s in ('forwardA', 'forwardB')}
    r['C5 forward A and B not lower by > 0.003'] = (fw, -0.003, all(x >= -0.003 for x in fw.values()))
    if name.startswith('X1'):
        pre = [c for c, e in b['era'].items() if e == 'before']; post = [c for c, e in b['era'].items() if e == 'after']
        k1 = v['one_lot']['win_clear_buyback_all']['F1']; k1b = b['one_lot']['win_clear_buyback_all']['F1']
        r['K1 one_lot clearance-window F1 >= base + 0.10 and events window F1 not lower'] = ((k1, v['win_clear_buyback_all']['F1']), (k1b + 0.10, b['win_clear_buyback_all']['F1']), k1 >= k1b + 0.10 and v['win_clear_buyback_all']['F1'] >= b['win_clear_buyback_all']['F1'])
        imp = [c for c in pre if v['per_cycle'][c]['clear']['real'] and (v['per_cycle'][c]['clear']['F1'] or 0) > (b['per_cycle'][c]['clear']['F1'] or 0)]; has = [c for c in pre if v['per_cycle'][c]['clear']['real']]
        r['K2 clearance-window F1 improves in a majority of pre-auction cycles with a clearance'] = ((len(imp), len(has)), 'majority', len(imp) > len(has) / 2)
        same = all(v['sim_orders_hash'][c] == b['sim_orders_hash'][c] for c in post); r['K3 post-auction cycles identical'] = (same, True, same)
    if name == 'X3':
        o, ob = v['win_open_long'], b['win_open_long']
        r['O1 opening-window body-long recall >= base + 0.10 and precision >= base - 0.05'] = ((o['recall'], o['precision']), (ob['recall'] + 0.10, ob['precision'] - 0.05), o['recall'] >= ob['recall'] + 0.10 and o['precision'] >= ob['precision'] - 0.05)
        have = [c for c in b['per_cycle'] if v['per_cycle'][c]['openl']['real']]; imp = [c for c in have if (v['per_cycle'][c]['openl']['F1'] or 0) > (b['per_cycle'][c]['openl']['F1'] or 0)]
        r['O2 opening-long F1 improves in a majority of cycles with real opening longs'] = ((len(imp), len(have)), 'majority', len(imp) > len(have) / 2)
    ok = all(x[2] for k, x in r.items() if isinstance(x, tuple)); return dict(criteria={k: (list(x) if isinstance(x, tuple) else x) for k, x in r.items()}, passed=ok)
if __name__ == '__main__':
    base = L('V0'); res = {n: evaluate(n, base, L(n)) for n in ('X1', 'X1s364', 'X3')}
    json.dump(res, open(f'{OD}/acceptance.json', 'w'), indent=1, default=float)
    for n, x in res.items():
        print('==', n, 'PASS' if x['passed'] else 'REJECTED')
        for k, v in x['criteria'].items():
            if isinstance(v, list): print('  ', 'ok ' if v[2] else 'FAIL', k, '|', v[0], 'vs', v[1])
