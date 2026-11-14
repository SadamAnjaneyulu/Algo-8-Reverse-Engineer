"""Independent detector for mutation testing.  usage: PE_PY=<mutated mirror python dir> MIRROR_ROOT=<mirror root> python3 mut_detector.py
Compares the (possibly mutated) engine against the OWN reference (ref_closing.py) on (A) hand-built + fuzzed synthetic scenarios, deep (partition, batch attributes,
member join gaps/overlap flags, portion rows, ids) and (B) the full real ledger (partitions for 10 views, summarize/stability/c2 sensitivity numbers).  Hash check of the
emitted TSV text vs committed manifest is reported separately as [REPRO].  Prints one JSON line."""
import os, sys, json, hashlib, random, collections, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synthetic_lib import *
import ref_closing as R
SC = '/tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/m2f_b/'
out = dict(A=[], B=[], REPRO=[], errors=[])

def tsv(text):
    L = text.rstrip('\n').split('\n'); h = L[0].split('\t'); return [dict(zip(h, l.split('\t'))) for l in L[1:]]

def deep(name, spec):
    fills = [dict(row=i + 1, instr=(u, e, r, str(s)), side=sd, qty=q, t=t, parent=p, und=u, exp=e, order_no=p) for i, (u, e, r, s, t, sd, q, p) in enumerate(spec)]
    P = R.parents_from(R.replay(fills)); rowq = {f['row']: f['close_qty'] for f in R.replay(fills)}
    b_ = Builder('d'); ids = {}
    for (und, exp, right, strike, t, side, q, parent) in spec:
        k = (und, exp, right, strike)
        if k not in ids: ids[k] = b_.add_inst(cp=right, strike=int(strike), expiry=exp, und=und)
        b_.fill(ids[k], t - BASE_TS, 1 if side == 'Buy' else -1, q, 10000, parent=parent)
    ins, fl = b_.out(); ls = LineageSet(fl, ins, 'SYNTHETIC_TEST', 'src'); parents, unattr, multi = cb.closing_parents(ls)
    views = cb.all_views(parents); bad = []
    files = {}
    for m in ('C1', 'C2'): files[m] = cb.files_for_method(views, m, ls)
    for m in ('C1', 'C2'):
        Bf = tsv(files[m][f'closing_batches_{m}.tsv']); Mf = tsv(files[m][f'closing_batch_members_{m}.tsv']); Pf = tsv(files[m][f'closing_batch_portions_{m}.tsv'])
        for g in TH:
            mine = R.build(P, m, g); token = ('CB_FIRST_FILL_GAP' if m == 'C1' else 'CB_LAST_TO_FIRST_GAP') + f'_{g}S'
            cnt = collections.Counter(); exp_ids = {}
            for b in mine:
                cnt[b['stream']] += 1; exp_ids[(b['stream'], frozenset(b['pids']))] = f"INF:CLOSING_BATCH@{token}:{b['stream'][0]}:{b['stream'][1]}:{b['stream'][2]}:{cnt[b['stream']]:03d}"
            eb = [r for r in Bf if int(r['threshold_s']) == g]; em = collections.defaultdict(list); ep = collections.defaultdict(list)
            for r in Mf:
                if int(r['threshold_s']) == g: em[r['batch_id']].append(r)
            for r in Pf:
                if int(r['threshold_s']) == g: ep[r['batch_id']].append(r)
            got = {}
            for r in eb:
                key = ((r['underlying'], r['expiry'], r['session']), frozenset(x['parent_order_id'] for x in em[r['batch_id']])); got[key] = r
            if set(got) != set(exp_ids): bad.append(f'{name} {m}{g}: partition differs'); continue
            for key, r in got.items():
                b = next(x for x in mine if (x['stream'], frozenset(x['pids'])) == key)
                if r['batch_id'] != exp_ids[key]: bad.append(f'{name} {m}{g}: id {r["batch_id"]} != {exp_ids[key]}')
                chk = [(int(r['n_parents']), len(b['pids'])), (int(r['n_closing_portions']), b['ncp']), (int(r['total_closing_qty']), b['qty']), (int(r['start_ts']), b['first']), (int(r['end_ts']), b['last']),
                       (int(r['duration_s']), b['last'] - b['first']), (int(r['n_links']), len(b['links'])), (int(r['max_link_gap_s']), max(b['links']) if b['links'] else 0),
                       (int(r['n_overlap_links']), sum(b['ov'])), (int(r['n_strict_overlap_links']), sum(b['sov'])), (int(r['has_interval_overlap']), int(any(b['ov'])))]
                if any(a != c for a, c in chk): bad.append(f'{name} {m}{g}: batch attrs {[x for x in chk if x[0] != x[1]]}')
                rows = em[r['batch_id']]
                if [x['parent_order_id'] for x in rows] != b['pids'] and sorted(x['parent_order_id'] for x in rows) == sorted(b['pids']) and False: pass
                for i, x in enumerate(rows[1:]):
                    if x['join_gap_s'] != str(b['links'][i]) or int(x['interval_overlap']) != int(b['ov'][i]) or int(x['strict_overlap']) != int(b['sov'][i]): bad.append(f'{name} {m}{g}: member link row')
                if {(int(x['source_row_id']), int(x['quantity'])) for x in ep[r['batch_id']]} != {(row, rowq[row]) for row in b['cps']} or len(ep[r['batch_id']]) != len(b['cps']): bad.append(f'{name} {m}{g}: portion rows')
    return bad

try:
    for name, f in CASES:
        out['A'] += deep(name, f())
    for seed in range(120):
        out['A'] += deep(f'fuzz{seed}', gen(random.Random(10_000 + seed)))
except Exception as ex:
    out['errors'].append('A:' + repr(ex)[:300] + ' | ' + traceback.format_exc().splitlines()[-3][:200])

if os.environ.get('MIRROR_ROOT'):
    try:
        from pe.generators import historical as H
        ins, fills, src = H.generate(os.environ['MIRROR_ROOT']); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
        parents, unattr, multi = cb.closing_parents(ls); views = cb.all_views(parents); E = json.load(open(SC + 'expected_real.json'))
        for (m, g), v in sorted(views.items()):
            got = sorted([list(b['stream']), sorted(p.parent_id for p in b['members'])] for b in v['batches'])
            if got != E['partitions'][f'{m}_{g}']: out['B'].append(f'partition {m}_{g}')
        for r in cb.summarize(views, parents, ls):
            e = E['summary'][f"{r['method']}_{r['threshold_s']}"]
            for k in ('batches', 'singleton_batches', 'pairs_linked', 'pairs_gap_exactly_threshold', 'pairs_gap_threshold_plus_1s', 'pairs_equal_first_ts', 'overlap_links', 'strict_overlap_links', 'batches_with_overlap'):
                if r[k] != e[k]: out['B'].append(f"summary {r['method']}_{r['threshold_s']} {k}")
            if r['duration_s']['max'] != e['max_duration']: out['B'].append(f"summary {r['method']}_{r['threshold_s']} max_duration")
        st = cb.stability(views)
        for r in st['across_thresholds']:
            e = E['stability'][f"{r['method']}_{r['from_s']}_{r['to_s']}"]
            if r['identical_batches'] != e['identical'] or r['nested'] != e['nested']: out['B'].append(f"stability {r['method']} {r['from_s']}-{r['to_s']}")
        for r in cb.c2_rule_sensitivity(parents):
            e = E['c2sens'][str(r['threshold_s'])]
            if (r['c1_batches'], r['c2_approved_rule'], r['c2_tiebreak_parent_id'], r['c2_running_max_reference']) != (e['c1'], e['c2'], e['c2_tie_pid'], e['c2_runmax']): out['B'].append(f"c2sens {r['threshold_s']}")
        man = json.load(open(os.path.join(os.environ['MIRROR_ROOT'], 'portfolio_engine', 'reports', 'm2c_data', 'manifest.json')))['files']
        for m in ('C1', 'C2'):
            for name, text in cb.files_for_method(views, m, ls).items():
                if hashlib.sha256(text.encode()).hexdigest() != man[name + '.gz']['sha256_of_text']: out['REPRO'].append(name)
    except Exception as ex:
        out['errors'].append('B:' + repr(ex)[:300] + ' | ' + traceback.format_exc().splitlines()[-3][:200])
print('RESULT ' + json.dumps(dict(A=len(out['A']), A_sample=out['A'][:3], B=len(out['B']), B_sample=out['B'][:5], REPRO=out['REPRO'], errors=out['errors'])))
