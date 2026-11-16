"""Task 3: hand-built synthetic cases fed to BOTH my reference (ref_closing, no pe import) and pe.closing_batches (via LineageSet + public
functions).  pe.* is used here only to run the engine on synthetic input, never to validate itself.  Class: [IMPL] vs engine."""
import sys, random, json, math, traceback
import os
sys.path.insert(0, os.environ.get('PE_PY', '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python'))
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/reports/m2f_audit/track_b')
import ref_closing as R
from pe import closing_batches as cb
from pe.schema import *
from pe.lineage_set import LineageSet
from pe.generators.synthetic import Builder, BASE_TS
TH = (2, 5, 10, 30, 60)

def run_engine(spec, ordering=None):
    """spec: list of (und, expiry, right, strike, abs_ts, 'Buy'|'Sell', qty, parent)"""
    b = Builder('trackb'); ids = {}
    for (und, exp, right, strike, t, side, q, parent) in spec:
        k = (und, exp, right, strike)
        if k not in ids: ids[k] = b.add_inst(cp=right, strike=int(strike), expiry=exp, und=und)
        b.fill(ids[k], t - BASE_TS, 1 if side == 'Buy' else -1, q, 10000, parent=parent)
    ins, fills = b.out()
    ls = LineageSet(fills, ins, 'SYNTHETIC_TEST', 'src')
    parents, unattr, multi = cb.closing_parents(ls)
    out = {}
    for m in ('C1', 'C2'):
        for g in TH:
            v = cb.build_view(parents, m, g)
            out[(m, g)] = frozenset((bt['stream'], frozenset(p.parent_id for p in bt['members'])) for bt in v['batches'])
    return out, parents, multi

def run_ref(spec):
    fills = [dict(row=i + 1, instr=(u, e, r, str(s)), side=sd, qty=q, t=t, parent=p, und=u, exp=e, order_no=p)
             for i, (u, e, r, s, t, sd, q, p) in enumerate(spec)]
    rep = R.replay(fills); P = R.parents_from(rep)
    out = {}
    for m in ('C1', 'C2'):
        for g in TH:
            out[(m, g)] = frozenset((b['stream'], frozenset(b['pids'])) for b in R.build(P, m, g))
    return out

CASES = []
def case(name):
    def d(f): CASES.append((name, f)); return f
    return d
N = ('NIFTY', '2026-01-08'); N2 = ('NIFTY', '2026-01-15'); S = ('SENSEX', '2026-01-08')
T0 = BASE_TS + 3600
def sh(und_exp, strike, t, q, parent, right='CE'):  # open short
    return (*und_exp, right, strike, t, 'Sell', q, parent)
def bu(und_exp, strike, t, q, parent, right='CE'):  # close by buy
    return (*und_exp, right, strike, t, 'Buy', q, parent)

@case('gap_exactly_threshold_and_plus_one')
def _():
    sp = []
    # one scenario per (g, delta) is composed in one spec using separate expiry streams to isolate each pair
    for gi, g in enumerate(TH):
        for di, d in enumerate((-1, 0, 1)):
            ue = ('NIFTY', f'2026-02-{1+gi*3+di:02d}')
            sp += [sh(ue, 100, T0 - 10, 130, f'o{gi}{di}'), bu(ue, 100, T0, 65, f'A{gi}{di}'), bu(ue, 100, T0 + g + d, 65, f'B{gi}{di}')]
    return sp
@case('equal_timestamps_many_parents_unsorted_input')
def _():
    sp = [sh(N, 100, T0 - 5, 650, 'o')]
    ids = ['9', '10', '2', 'h_5', 'h_10', 'A', 'a']
    random.Random(3).shuffle(ids)
    sp += [bu(N, 100, T0, 65, f'p{i}') for i in ids]
    return sp
@case('multi_fill_parent_interval_overlap')
def _():
    return [sh(N, 100, T0 - 9, 400, 'o'), sh(N, 200, T0 - 9, 400, 'o2', 'PE'), bu(N, 100, T0, 65, 'A'), bu(N, 100, T0 + 20, 65, 'A'), bu(N, 100, T0 + 50, 65, 'A'),
            bu(N, 200, T0 + 10, 65, 'B', 'PE'), bu(N, 200, T0 + 45, 65, 'C', 'PE'), bu(N, 200, T0 + 53, 65, 'D', 'PE'), bu(N, 200, T0 + 120, 65, 'E', 'PE')]
@case('mixed_open_close_parent')
def _():
    return [sh(N, 100, T0 - 9, 65, 'o1'), bu(N, 100, T0, 130, 'M'),            # M closes 65 (flat) and opens a 65 long: reversal
            sh(N, 100, T0 + 30, 65, 'x'), bu(N, 100, T0 + 2, 65, 'Z') if False else bu(N, 100, T0 + 60, 65, 'Q')]
@case('mixed_parent_opening_fill_earlier_than_closing_fill')
def _():
    return [sh(N, 100, T0 - 100, 65, 'o1'), sh(N, 200, T0 - 100, 65, 'o2', 'PE'), bu(N, 200, T0 + 1, 65, 'Z', 'PE'),
            sh(N, 300, T0 - 3, 65, 'M'), bu(N, 100, T0 + 100, 65, 'M')]   # M: opening at T0-3, closing at T0+100
@case('parent_across_instruments_same_und_exp')
def _():
    return [sh(N, 100, T0 - 9, 65, 'o1'), sh(N, 200, T0 - 9, 65, 'o2', 'PE'), bu(N, 100, T0, 65, 'A'), bu(N, 200, T0 + 1, 65, 'A', 'PE'), bu(N, 100, T0 + 3, 65, 'B') if False else sh(N, 300, T0 - 9, 65, 'o3'), bu(N, 300, T0 + 4, 65, 'B')]
@case('parent_across_expiries_underlyings')
def _():
    return [sh(N, 100, T0 - 9, 65, 'o1'), sh(N2, 100, T0 - 9, 65, 'o2'), sh(S, 100, T0 - 9, 65, 'o3'), bu(N, 100, T0, 65, 'X'), bu(N2, 100, T0 + 1, 65, 'X'), bu(S, 100, T0 + 1, 65, 'Y'),
            sh(N, 150, T0 - 9, 65, 'o4'), bu(N, 150, T0 + 2, 65, 'Z')]
IST_MID = ((BASE_TS + 3 * 86400 + 19800) // 86400) * 86400 - 19800       # an IST midnight
@case('ist_midnight_and_session_boundary')
def _():
    sp = [sh(N, 100, IST_MID - 1000, 650, 'o')]
    sp += [bu(N, 100, IST_MID - 1, 65, 'A'), bu(N, 100, IST_MID + 1, 65, 'B'), bu(N, 100, IST_MID, 65, 'M0'),
           bu(N, 100, IST_MID + 86400 + 9 * 3600, 65, 'C'), bu(N, 100, IST_MID + 86400 + 9 * 3600 + 2, 65, 'D')]
    return sp
@case('utc_midnight_is_not_session_boundary')
def _():
    utc_mid = ((BASE_TS + 5 * 86400) // 86400) * 86400   # 05:30 IST
    return [sh(N, 100, utc_mid - 100, 260, 'o'), bu(N, 100, utc_mid - 1, 65, 'A'), bu(N, 100, utc_mid + 1, 65, 'B')]
@case('long_transitive_chain_each_gap_equals_threshold')
def _():
    sp = []
    for gi, g in enumerate(TH):
        ue = ('SENSEX', f'2026-03-{1+gi:02d}')
        sp += [sh(ue, 100, T0 - 10, 65 * 40, f'o{gi}')] + [bu(ue, 100, T0 + g * k, 65, f'c{gi}_{k:02d}') for k in range(30)]
    return sp
@case('c2_runmax_vs_prev_distinguishing')
def _():
    # A spans [0,100]; B at 10 (single); C at 50 (single); D at 101: C2-prev: D vs C.last=50 ; runmax: vs 100
    return [sh(N, 100, T0 - 9, 650, 'o'), bu(N, 100, T0, 65, 'A'), bu(N, 100, T0 + 100, 65, 'A'), bu(N, 100, T0 + 10, 65, 'B'), bu(N, 100, T0 + 50, 65, 'C'), bu(N, 100, T0 + 101, 65, 'D')]
@case('tie_with_multi_fill_parent_c2')
def _():
    return [sh(N, 100, T0 - 9, 650, 'o'), bu(N, 100, T0, 65, 'P2'), bu(N, 100, T0, 65, 'P1'), bu(N, 100, T0 + 30, 65, 'P1'), bu(N, 100, T0 + 1, 65, 'P3')]
@case('reversal_closing_portion_only')
def _():
    return [sh(N, 100, T0 - 9, 65, 'o'), bu(N, 100, T0, 130, 'R'), sh(N, 100, T0 + 1, 65, 'K')]
@case('opening_only_and_no_closings')
def _():
    return [sh(N, 100, T0 - 9, 65, 'o'), sh(N, 200, T0 - 9, 65, 'o2', 'PE')]

def canon(x): return sorted((tuple(s), tuple(sorted(p))) for s, p in x)

def compare(name, spec):
    try:
        e, parents, multi = run_engine(spec)
    except Exception as ex:
        return dict(case=name, status='ENGINE_EXCEPTION', detail=repr(ex)[:200])
    r = run_ref(spec)
    d = [(k, sorted(set(canon(e[k])) ^ set(canon(r[k])))) for k in e if e[k] != r[k]]
    return dict(case=name, status='AGREE' if not d else 'DISAGREE', n_views=len(e), diffs=[(k, v[:4]) for k, v in d][:4], engine_multi_stream_parents=list(multi))

# fuzz
def gen(rnd):
    n_inst = rnd.randint(1, 5); keys = [(rnd.choice(['NIFTY', 'SENSEX']), rnd.choice(['2026-01-08', '2026-01-15']), rnd.choice(['CE', 'PE']), rnd.choice([100, 200, 300])) for _ in range(n_inst)]
    spec = []; pos = {k: 0 for k in keys}; t = T0; pid = 0
    for _ in range(rnd.randint(8, 60)):
        t += rnd.choice([0, 0, 1, 1, 2, 3, 5, 9, 10, 11, 30, 61, 100, 86400 // 2])
        k = rnd.choice(keys); side = 'Sell' if pos[k] >= 0 and rnd.random() < 0.55 else 'Buy'
        q = rnd.choice([65, 65, 130]); pos[k] += -q if side == 'Sell' else q
        pid = rnd.choice(['P%d' % rnd.randint(0, 20), 'h_%d' % rnd.randint(0, 5), str(rnd.randint(1000, 1020))]) if rnd.random() < 0.6 else 'U_%d' % _
        spec.append((k[0], k[1], k[2], k[3], t, side, q, pid))
    return spec
def expect(spec_fn, view, expected):
    e, *_ = run_engine(spec_fn()); r = run_ref(spec_fn())
    got_e = sorted(sorted(p) for s, p in e[view]); got_r = sorted(sorted(p) for s, p in r[view])
    return got_e == expected, got_r == expected
