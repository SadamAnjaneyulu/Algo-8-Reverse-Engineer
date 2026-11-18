"""Task 2: measure impact of each methodology ambiguity on all thresholds. [IMPL] own reference only."""
import sys, json, collections
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
from ref_closing import *
TH = (2, 5, 10, 30, 60)
fills = load_raw(); rep = replay(fills)
base_P = parents_from(rep)
def pset(bs): return frozenset((frozenset(x['cps'])) for x in bs)   # partition of closing-portion rows (stream-label independent)
def diff(a, b):
    sa, sb = pset(a), pset(b)
    ob, oa = sb - sa, sa - sb
    parents_aff = sum(len(x) for x in ob)   # closing portions in changed alt batches
    return dict(batches_alt=len(b), batches_base=len(a), batches_only_alt=len(ob), batches_only_base=len(oa),
                portions_in_changed_alt_batches=parents_aff, max_parents=max(len(x['pids']) for x in b),
                max_dur=max(x['last']-x['first'] for x in b))
out = {}
def run(name, method, Pfun_alt=None, **kw):
    for g in TH:
        base = build(base_P, method, g)
        alt = build(Pfun_alt if Pfun_alt is not None else base_P, method, g, **kw)
        out[f'{name}|{method}|{g}'] = diff(base, alt)
# stats of baseline
for m in ('C1', 'C2'):
    for g in TH:
        b = build(base_P, m, g); out[f'BASE|{m}|{g}'] = stats(b)
# A1 tie orders
for m in ('C1', 'C2'):
    for name, kw in [('TIE_minrow_any', dict(order='first_any')), ('TIE_pid_only', dict(order='first_pid')),
                     ('TIE_pid_numeric_first', dict(order='first_cl', pid_mode='num_first')),
                     ('TIE_pid_reversed', dict(order='first_pid_rev')), ('TIE_by_last_then_row', dict(order='first_last'))]:
        run(name, m, **kw)
# A2 C2 reference
for name, kw in [('C2REF_runmax_chain', dict(c2_ref='runmax_chain')), ('C2REF_runmax_stream', dict(c2_ref='runmax_stream'))]:
    run(name, 'C2', **kw)
# combos tie x ref
for t, tk in [('pid_only', dict(order='first_pid')), ('minrow_any', dict(order='first_any'))]:
    for r in ('runmax_chain', 'runmax_stream'):
        run(f'C2COMBO_{t}+{r}', 'C2', c2_ref=r, **tk)
# A3 exclusive threshold
for m in ('C1', 'C2'): run('EXCLUSIVE_gap_lt_g', m, inclusive=False)
# A4 first/last timestamp definition for mixed parents
P_any = parents_from(rep, first_def='any', last_def='any')
for m in ('C1', 'C2'): run('TS_ANYFILL_for_mixed(first&last over all fills of parent)', m, Pfun_alt=P_any)
P_anyfirst = parents_from(rep, first_def='any', last_def='closing')
for m in ('C1', 'C2'): run('TS_FIRST_ANYFILL_only', m, Pfun_alt=P_anyfirst)
# A5 stream definition
for sname in ('und_sess', 'und_exp', 'und'):
    for m in ('C1', 'C2'): run(f'STREAM_{sname}', m, stream=sname)
# A6 mixed parents excluded
P_nomix = parents_from(rep, include_mixed=False)
for m in ('C1', 'C2'): run('EXCLUDE_MIXED_parents', m, Pfun_alt=P_nomix)
out['mixed_parents_with_closing'] = sum(1 for p in base_P if p['mixed'])
# A7 unit = order number instead of col163 tag
P_ord = parents_from(rep, unit='order_no')
out['unit_order_no_parents'] = len(P_ord)
for m in ('C1', 'C2'): run('UNIT_order_number_col4', m, Pfun_alt=P_ord)
# A8 replay tie-handling within same (instrument, second)
for tie in ('sells_first', 'buys_first'):
    rep2 = replay(fills, tie=tie); P2 = parents_from(rep2)
    out[f'REPLAY_{tie}|closing_portions'] = sum(len(p['cps']) for p in P2); out[f'REPLAY_{tie}|closing_units'] = sum(p['qty'] for p in P2)
    out[f'REPLAY_{tie}|parents'] = len(P2)
    nd = sum(1 for a, b in zip(rep, rep2) if (a['close_qty'], a['open_qty']) != (b['close_qty'], b['open_qty']))
    out[f'REPLAY_{tie}|fills_with_changed_split'] = nd
    for m in ('C1', 'C2'): run(f'REPLAY_{tie}', m, Pfun_alt=P2)
# A9 parents spanning streams
span = [p['pid'] for p in base_P if len(p['streams']) > 1]
out['parents_with_closing_fills_in_multiple_streams'] = len(span)
out['parents_with_closing_in_multiple_instruments'] = sum(1 for p in base_P if len({f['instr'] for f in p['cps']}) > 1)
# C2 vs C1 under base
for g in TH:
    out[f'C1_vs_C2_base|{g}'] = diff(build(base_P, 'C1', g), build(base_P, 'C2', g))
# parents where last>first
out['parents_last_gt_first'] = [(p['pid'], p['first'], p['last']) for p in base_P if p['last'] > p['first']]
# tie statistics
c = collections.Counter((p['streams'][0], p['first']) for p in base_P)
out['equal_first_ts_groups'] = sum(1 for v in c.values() if v > 1); out['parents_in_equal_first_ts_groups'] = sum(v for v in c.values() if v > 1)
# does tie order within equal-first groups matter at all? count groups where order matters for C1: never, since gap 0
json.dump(out, open('ambiguity_result.json', 'w'), indent=1, default=str)

import itertools
names = sorted({k.split('|')[0] for k in out if k.count('|') == 2 and not k.startswith(('BASE','C1_vs'))})
print('scenario | method | g: batches_alt (base) ; changed batches only_alt/only_base ; portions in changed alt batches ; maxparents ; maxdur')
for n in names:
    for m in ('C1', 'C2'):
        if f'{n}|{m}|2' not in out: continue
        row = []
        for g in TH:
            v = out[f'{n}|{m}|{g}']
            row.append(f"{g}s:{v['batches_alt']}({v['batches_base']}) d{v['batches_only_alt']}/{v['batches_only_base']} p{v['portions_in_changed_alt_batches']} mp{v['max_parents']} md{v['max_dur']}")
        print(n[:40], m, ' | '.join(row))
for k, v in out.items():
    if not isinstance(v, dict): print(k, v)
