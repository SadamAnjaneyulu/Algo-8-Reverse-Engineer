import json, random, sys
from cx_harness import *
S = {}
def W(inst, t, qty=65, parent=None, e=0, side=1, tag='h_', **k): return dict(inst=inst, t=t, side=side, qty=qty, parent=parent, tag=tag, e=e, **k)
def B(inst, t, qty=65, parent=None, e=0, side=-1, tag='num', **k): return dict(inst=inst, t=t, side=side, qty=qty, parent=parent, tag=tag, e=e, **k)
IDAY = 86400 - (9 * 3600 + 16 * 60)          # BASE_TS + IDAY = IST midnight
S['several_wings_one_body_and_vice_versa'] = [W(N('CE', 24800), 3, parent='W1'), W(N('CE', 24900), 4, parent='W2'), W(N('CE', 25000), 5, parent='W3'), B(N('CE', 24000), 0, parent='B1'), B(N('CE', 24050), 1, parent='B2'), B(N('PE', 24000), 2, parent='Bpe'), W(N('PE', 23000), 6, parent='Wpe')]
S['boundary_60_61_before_after'] = [W(N('CE', 24800), 200, parent='W', e=3), B(N('CE', 24000), 140, parent='b60', e=0), B(N('CE', 24100), 139, parent='b61', e=1), B(N('CE', 24200), 260, parent='a60', e=2), B(N('CE', 24300), 261, parent='a61', e=4)]
S['wing_before_body'] = [W(N('CE', 24800), 0, parent='W'), B(N('CE', 24000), 30, parent='B')]
S['different_right_expiry_underlying'] = [W(N('CE', 24800), 3, parent='W'), B(N('PE', 24000), 0, parent='Bpe'), B(N('CE', 24000, '2026-01-15'), 0, parent='Bexp'), B(N('CE', 80000, und='SENSEX'), 0, parent='Bund'), B(N('CE', 24000), 1, parent='Bok')]
S['ist_midnight_boundary'] = [B(N('CE'), IDAY - 20, parent='B1'), W(N('CE', 24800), IDAY + 20, parent='W1'), B(N('CE', 24050), IDAY + 10, parent='B2')]
S['ist_midnight_exact'] = [B(N('CE'), IDAY - 1, parent='B1'), W(N('CE', 24800), IDAY, parent='W1')]
S['same_ist_day_across_utc_midnight'] = [B(N('CE'), 5 * 3600 + 30 * 60 - (9 * 3600 + 16 * 60) - 10, parent='B1'), W(N('CE', 24800), 5 * 3600 + 30 * 60 - (9 * 3600 + 16 * 60) + 10, parent='W1')]       # IST 05:29:50 vs 05:30:10: UTC midnight, same IST day
S['missing_entry_minute'] = [W(N('CE', 24800), 3, parent='Wn', e=None), B(N('CE'), 0, parent='B', e=0), B(N('CE', 24050), 1, parent='Bn', e=None), W(N('CE', 24900), 2, parent='Wok', e=0)]
S['partial_fills_across_seconds'] = [W(N('CE', 24800), 0, 65, parent='W'), W(N('CE', 24800), 100, 65, parent='W'), W(N('CE', 24800), 200, 65, parent='W'), B(N('CE'), 150, 195, parent='B')]
S['qty_ratios'] = [W(N('CE', 24800), 3, 65, parent='W1'), W(N('CE', 24900), 4, 260, parent='W2'), B(N('CE'), 0, 195, parent='B1'), B(N('CE', 24050), 1, 65, parent='B2')]
S['w2_weights_normalisation'] = [W(N('CE', 24800), 5, 130, parent='W'), B(N('CE', 24000), 0, 65, parent='B1'), B(N('CE', 24050), 10, 195, parent='B2'), B(N('CE', 24100), 20, 260, parent='B3')]
S['w3_unequal_queue'] = [B(N('CE'), 0, 130, parent='B1'), W(N('CE', 24800), 10, 65, parent='W1'), W(N('CE', 24900), 20, 195, parent='W2'), B(N('CE', 24050), 30, 65, parent='B2'), W(N('CE', 25000), 40, 130, parent='W3'), B(N('CE', 24100), 50, 390, parent='B3')]
S['opening_vs_closing_separation_reversal'] = [W(N('CE', 24800), 0, parent='oW', e=0), B(N('CE'), 0, parent='oB', e=0), W(N('CE', 24800), 100, parent='cW', e=1, side=-1, tag='h_'), B(N('CE'), 102, parent='cB', e=1, side=1, tag='num'), B(N('CE', 24800), 200, 130, parent='revB', e=2, side=-1, tag='num')]
S['strike_sign_ce_pe'] = [W(N('CE', 24800), 3, parent='Wc'), B(N('CE', 24000), 0, parent='Bc'), W(N('PE', 23200), 3, parent='Wp'), B(N('PE', 24000), 0, parent='Bp'), W(N('PE', 24500), 3, parent='Wp_inside'), W(N('CE', 23500), 3, parent='Wc_inside')]
S['same_instrument_wing_and_body'] = [B(N('CE'), 0, parent='B1'), W(N('CE'), 3, parent='W1')]
S['direction_scope_nonh_wings'] = [W(N('CE', 24800), 3, parent='Wn', tag='num'), B(N('CE'), 0, parent='B'), W(N('CE', 24900), 4, parent='Wv', tag='v_'), B(N('CE', 24050), 1, parent='Bs', tag='s_')]
S['tie_equal_first_ts'] = [W(N('CE', 24800), 5, parent='W'), B(N('CE', 24000), 5, parent='B1'), B(N('CE', 24050), 5, parent='B2'), B(N('CE', 24100), 7, parent='B3'), B(N('CE', 24150), 3, parent='B4')]
res = {}
for name, spec in S.items():
    for scope in ('TAGGED', 'DIRECTION'):
        d, E, A = compare(spec, scope); res[f'{name}|{scope}'] = dict(n_diffs=len(d), diffs=[str(x) for x in d[:3]], links={m: len(v) for m, v in E.links.items()})
# fuzz
rnd = random.Random(20260101); nd = 0; ndiff = 0; fz = []
for it in range(400):
    insts = [N(cp, 24000 + 100 * k) for cp in ('CE', 'PE') for k in range(3)] + [N('CE', 24000, '2026-01-15')]; spec = []
    for j in range(rnd.randint(3, 14)):
        tag = rnd.choice(('h_', 'num', 'h_', 'num', 's_', 'v_')); side = rnd.choice((1, -1)); par = f'P{rnd.randint(0, 9)}'
        spec.append(dict(inst=rnd.choice(insts), t=rnd.choice((0, 1, 2, 30, 59, 60, 61, 62, 119, 120, IDAY - 5, IDAY + 5)) + rnd.randint(0, 3), side=side, qty=65 * rnd.randint(1, 4), parent=par + ('_' + tag), tag=tag, e=rnd.choice((0, 0, 1, 2, None))))
    # parent -> consistent tag/entry minute
    seen = {}
    for s in spec: seen.setdefault(s['parent'], (s['tag'], s['e'])); s['tag'], s['e'] = seen[s['parent']]
    for scope in ('TAGGED', 'DIRECTION'):
        d, E, A = compare(spec, scope); nd += 1
        if d: ndiff += 1; fz.append((it, scope, [str(x) for x in d[:2]]))
res['fuzz'] = dict(scenarios=nd, with_diffs=ndiff, examples=fz[:5])
json.dump(res, open('cx_result.json', 'w'), indent=1); print(json.dumps({k: (v['n_diffs'] if 'n_diffs' in v else v) for k, v in res.items()}, indent=1)); 
for k, v in res.items():
    if v.get('n_diffs'): print(k, v['diffs'])
