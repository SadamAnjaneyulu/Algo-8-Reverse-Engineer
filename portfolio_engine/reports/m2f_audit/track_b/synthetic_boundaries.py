from synthetic_lib import *
results = []
for name, f in CASES:
    results.append(compare(name, f()))
    print(results[-1]['case'], results[-1]['status'], results[-1].get('diffs', ''), results[-1].get('engine_multi_stream_parents', ''))

# explicit expected values (hand-derived) for a few boundary cases to detect shared misreading
hand = []
sp = lambda: [sh(N, 100, T0 - 10, 130, 'o'), bu(N, 100, T0, 65, 'A'), bu(N, 100, T0 + 10, 65, 'B')]
hand.append(('gap==g inclusive link C1 g=10', expect(sp, ('C1', 10), [['A', 'B']])))
sp = lambda: [sh(N, 100, T0 - 10, 130, 'o'), bu(N, 100, T0, 65, 'A'), bu(N, 100, T0 + 11, 65, 'B')]
hand.append(('gap==g+1 no link C1 g=10', expect(sp, ('C1', 10), [['A'], ['B']])))
sp = lambda: [sh(N, 100, T0 - 10, 130, 'o'), bu(N, 100, T0, 65, 'A'), bu(N, 100, T0 + 10, 65, 'B')]
hand.append(('gap==g inclusive link C2 g=10 (A single fill)', expect(sp, ('C2', 10), [['A', 'B']])))
sp = lambda: [sh(N, 100, T0 - 10, 260, 'o'), bu(N, 100, T0, 65, 'A'), bu(N, 100, T0 + 20, 65, 'A'), bu(N, 100, T0 + 29, 65, 'B')]
hand.append(('C2 gap = first(B)-last(A)=9 <=10 link; C1 gap=29 no', expect(sp, ('C2', 10), [['A', 'B']])))
hand.append(('C1 same data: no link', expect(sp, ('C1', 10), [['A'], ['B']])))
sp = lambda: [sh(N, 100, IST_MID - 1000, 130, 'o'), bu(N, 100, IST_MID - 1, 65, 'A'), bu(N, 100, IST_MID + 1, 65, 'B')]
hand.append(('IST midnight 2s apart: separate sessions even at 60s', expect(sp, ('C1', 60), [['A'], ['B']])))
for h in hand: print(h)

# missing / NaN timestamps
miss = []
for label, bad in (('None', None), ('NaN', float('nan'))):
    try:
        b = Builder('x'); i = b.add_inst(); b.fill(i, 0, -1, 130, 10000, parent='o'); b.fill(i, 5, 1, 65, 9000, parent='A'); b.fill(i, 7, 1, 65, 9000, parent='B')
        ins, fills = b.out(); import dataclasses as dc
        fills[2] = dc.replace(fills[2], timestamp_s=bad) if hasattr(fills[2], 'timestamp_s') else fills[2]
        ls = LineageSet(fills, ins, 'SYNTHETIC_TEST', 'src'); parents, un, multi = cb.closing_parents(ls)
        v = cb.build_view(parents, 'C1', 10)
        miss.append((label, 'NO_ERROR', [sorted(p.parent_id for p in bt['members']) for bt in v['batches']]))
    except Exception as ex:
        miss.append((label, 'EXCEPTION', repr(ex)[:200]))
print('missing-ts engine behaviour', miss)
import dataclasses; print([f.name for f in dataclasses.fields(Fill)])

dis = 0; exc = 0
for seed in range(600):
    sp_ = gen(random.Random(10_000 + seed)); r = compare(f'fuzz{seed}', sp_)
    if r['status'] == 'DISAGREE': dis += 1; print(r)
    if r['status'] == 'ENGINE_EXCEPTION': exc += 1; print(r)
print('fuzz 600 scenarios x 10 views: disagreements', dis, 'engine exceptions', exc)
json.dump(dict(cases=results, hand=[(h[0], h[1]) for h in hand], missing_ts=miss, fuzz=dict(n=600, disagreements=dis, exceptions=exc)), open('synthetic_boundaries_result.json', 'w'), indent=1, default=str)

# fuzz coverage: how often do the interesting branches fire?
cov = dict(c1_ne_c2=0, multi_stream_parent=0, multi_fill_parent=0, tie_groups=0, mixed_parents=0, n=0)
for seed in range(600):
    sp_ = gen(random.Random(10_000 + seed)); e, parents, multi = run_engine(sp_); cov['n'] += 1
    if any(e[('C1', g)] != e[('C2', g)] for g in TH): cov['c1_ne_c2'] += 1
    if multi: cov['multi_stream_parent'] += 1
    if any(len(p.cps) > 1 for p in parents): cov['multi_fill_parent'] += 1
    if len({(p.stream, p.first_ts) for p in parents}) < len(parents): cov['tie_groups'] += 1
    rep = R.replay([dict(row=i + 1, instr=(u, ex, r, str(s)), side=sd, qty=q, t=t, parent=p, und=u, exp=ex, order_no=p) for i, (u, ex, r, s, t, sd, q, p) in enumerate(sp_)])
    if any(P_['mixed'] for P_ in R.parents_from(rep)): cov['mixed_parents'] += 1
print('fuzz coverage', cov)
json.dump(dict(cases=results, hand=[(h[0], h[1]) for h in hand], missing_ts=miss, fuzz=dict(n=600, disagreements=dis, exceptions=exc, coverage=cov)), open('synthetic_boundaries_result.json', 'w'), indent=1, default=str)
