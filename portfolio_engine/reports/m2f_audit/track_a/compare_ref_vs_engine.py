"""TRACK A task (1): independent raw-derived reference vs committed engine outputs (loaded read-only via pe.generators.historical + LineageSet).
Classes: raw->ref = [RAW]+[IMPL]; comparison engine-vs-ref = [IMPL]/[RAW] (engine outputs are only LOADED, never used to compute the reference)."""
import os, sys, json
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
REPO = '/home/user/Algo-8-Reverse-Engineer'; sys.path.insert(0, os.environ.get('PE_PY', os.path.join(REPO, 'portfolio_engine', 'python')))
from fractions import Fraction
from collections import Counter, defaultdict
import ref_model as RM

OUT = {}
def rec(k, v): OUT[k] = v; print(k, '=>', v if not isinstance(v, (list, dict)) or len(str(v)) < 300 else str(v)[:300] + '...')

rows = RM.load_raw(); rec('raw_rows', len(rows))
# ---- raw sanity / exclusion accounting
bad = dict(side=sum(1 for r in rows if r['side'] == 0), qty_le0=sum(1 for r in rows if r['qty'] <= 0), px_not_tick=sum(1 for r in rows if r['px'] <= 0 or r['px'] % 5), qty_not_lot=sum(1 for r in rows if r['qty'] % RM.LOT[r['und']]),
           orderqty_not_lot=sum(1 for r in rows if r['order_qty'] % RM.LOT[r['und']]), ts_le0=sum(1 for r in rows if r['ts'] <= 0), nonmono_ts=sum(1 for a, b in zip(rows, rows[1:]) if b['ts'] < a['ts']))
rec('raw_validation_failures', bad)
pcount = len({r['parent'] for r in rows}); rec('raw_parent_count_col163', pcount); rec('raw_instrument_count', len({r['inst'] for r in rows}))
rec('raw_partial_status_rows', sum(1 for r in rows if r['status'] == 'PartiallyFilled'))
ordered = RM.order_fills(rows, 'src')
refs = {m: RM.replay_ref(ordered, m) for m in ('FIFO', 'LIFO', 'AVG')}
R = refs['FIFO']
rec('ref_OA', len(R.oa)); rec('ref_CP', len(R.cp)); rec('ref_episodes', len(R.episodes))
rec('ref_OA_units', sum(o['qty'] for o in R.oa.values())); rec('ref_CP_units', sum(c['qty'] for c in R.cp.values()))
rec('ref_reversal_fills', sum(1 for f in R.fills.values() if f['rev']))
rec('ref_fills_open_only', sum(1 for f in R.fills.values() if f['open'] and not f['close'])); rec('ref_fills_close_only', sum(1 for f in R.fills.values() if f['close'] and not f['open'])); rec('ref_fills_split', sum(1 for f in R.fills.values() if f['close'] and f['open']))
# parent roles
role = defaultdict(set)
for r, o in R.oa.items(): role[o['parent']].add('OA')
for r, c in R.cp.items(): role[c['parent']].add('CP')
ref_roles = {p: ('MIXED' if s == {'OA', 'CP'} else 'OPENING_ONLY' if s == {'OA'} else 'CLOSING_ONLY') for p, s in role.items()}
rec('ref_parent_roles', dict(Counter(ref_roles.values()))); rec('ref_parents_with_roles', len(ref_roles))
# convention-independence of the observed layer in the REFERENCE itself
def obs_sig(X): return (sorted((k, tuple(sorted(v.items()))) for k, v in X.oa.items()), sorted((k, tuple(sorted(v.items()))) for k, v in X.cp.items()), X.events, sorted((k, v['dir'], v['opened'], v['closed'], v['ended_by'], v['rev']) for k, v in X.episodes.items()))
rec('ref_observed_layer_identical_across_conventions', obs_sig(refs['FIFO']) == obs_sig(refs['LIFO']) == obs_sig(refs['AVG']))
# FIFO list vs interval implementation
iv = RM.fifo_interval_check(ordered); a = Counter(); b = Counter()
for cp, oa, q, *_ in [(x[0], x[1], x[2]) for x in R.ca]: a[(cp, oa)] += q
for cp, oa, q in iv: b[(cp, oa)] += q
rec('ref_FIFO_lotlist_equals_interval_method', a == b)
sens = 0; fa = defaultdict(dict); la = defaultdict(dict)
for cp, src, q, *_ in refs['FIFO'].ca: fa[cp][src] = fa[cp].get(src, 0) + q
for cp, src, q, *_ in refs['LIFO'].ca: la[cp][src] = la[cp].get(src, 0) + q
sens = sum(1 for cp in R.cp if fa[cp] != la[cp]); rec('ref_cp_convention_sensitive_FIFO_vs_LIFO', sens)
for m in refs: rec(f'ref_realized_paise_{m}', float(refs[m].realized_total) if m == 'AVG' else int(refs[m].realized_total))
rec('ref_cash_paise', R.cash)
# remaining inventory / expiry
last_day = (ordered[-1]['ts'] + 19800) // 86400
import datetime
def day_of(s): y, m, d = map(int, s.split('-')); return (datetime.date(y, m, d) - datetime.date(1970, 1, 1)).days
status = {}
for i, inv in R.final_inv.items():
    exp = day_of(i.split('|')[1]); status[i] = 'CLOSED' if inv == 0 else ('EXPIRED_UNCLOSED' if exp <= last_day else 'OPEN_AT_END_OF_DATA')
rec('ref_instrument_status', dict(Counter(status.values()))); rec('ref_remaining_units_abs', sum(abs(v) for v in R.final_inv.values()))
rec('ref_remaining_expired_unclosed_units', sum(abs(v) for i, v in R.final_inv.items() if status[i] == 'EXPIRED_UNCLOSED'))
ep_status = Counter()
for e in R.episodes.values():
    rem = e['opened'] - e['closed']
    ep_status['CLOSED' if rem == 0 and e['ended_by'] == 'flat' else 'REVERSED' if rem == 0 else 'EXPIRED_UNCLOSED' if day_of(e['inst'].split('|')[1]) <= last_day else 'OPEN_AT_END_OF_DATA'] += 1
rec('ref_episode_terminal_status', dict(ep_status))
# expiry-boundary: any fill after its instrument's expiry day (IST)?
rec('raw_fills_after_expiry_day', sum(1 for r in rows if (r['ts'] + 19800) // 86400 > day_of(r['expiry'])))
rec('raw_fills_on_expiry_day', sum(1 for r in rows if (r['ts'] + 19800) // 86400 == day_of(r['expiry'])))
rec('raw_distinct_ist_days', len({(r['ts'] + 19800) // 86400 for r in rows}))
# episodes crossing sessions
rec('ref_episodes_spanning_days', sum(1 for e in R.episodes.values() if (e['first_ts'] + 19800) // 86400 != (e['last_ts'] + 19800) // 86400))

# ================= engine outputs (LOAD ONLY)
from pe.generators import historical as H
from pe.lineage_set import LineageSet
try: ins, fills, src = H.generate(REPO)
except Exception as ex:
    rec('ENGINE_EXCEPTION', f'{type(ex).__name__}: {str(ex)[:200]}'); json.dump(dict(results=OUT, mismatches={}), open(os.environ.get('OUT_JSON', os.path.join(HERE, 'compare_ref_vs_engine_result.json')), 'w'), indent=1, default=str); sys.exit(0)
rec('engine_fills', len(fills)); rec('engine_dup_flagged', sum(1 for f in fills if f.is_duplicate_fill))
try: LS = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
except Exception as ex:
    rec('ENGINE_EXCEPTION', f'{type(ex).__name__}: {str(ex)[:200]}'); json.dump(dict(results=OUT, mismatches={}), open(os.environ.get('OUT_JSON', os.path.join(HERE, 'compare_ref_vs_engine_result.json')), 'w'), indent=1, default=str); sys.exit(0)
mism = defaultdict(list)
def chk(name, cond, detail=None):
    if not cond: mism[name].append(detail)
# 0) fill-level agreement with raw
byrow = {f.source_row_id: f for f in fills}
rec('engine_row_ids_equal_raw_rows', sorted(byrow) == list(range(len(rows))))
for r in rows:
    f = byrow.get(r['row'])
    if f is None: mism['fill_missing'].append(r['row']); continue
    t = (f.parent_order_id, f.instrument_id, f.timestamp_s, f.side, f.quantity, f.price_paise, f.requested_quantity, f.order_status)
    u = (r['parent'], r['inst'], r['ts'], r['side'], r['qty'], r['px'], r['order_qty'], r['status'])
    if t != u: mism['fill_field_vs_raw'].append((r['row'], t, u))
    if f.fill_id != RM.to_fill_id(r['row']): mism['fill_id_format'].append(r['row'])
    if f.module_tag != ('?'): pass
mt = Counter((byrow[r['row']].module_tag, r['module']) for r in rows); rec('module_tag_map_engine_vs_raw166', {f'{a}<-{b}': n for (a, b), n in mt.items()})
# 1) OA / CP rows
eoa = {int(k[4:]): v for k, v in LS.oa.items()}; ecp = {int(k[4:]): v for k, v in LS.cp.items()}   # id 'OA:F000123' -> 123
rec('engine_OA', len(eoa)); rec('engine_CP', len(ecp)); rec('engine_episodes', len(LS.episodes)); rec('engine_mixed_parents', len(LS.mixed_parents()))
rec('engine_OA_ids_equal_ref', set(eoa) == set(R.oa)); rec('engine_CP_ids_equal_ref', set(ecp) == set(R.cp))
for key, E, X in (('OA', eoa, R.oa), ('CP', ecp, R.cp)):
    n_ok = 0
    for rw in set(E) | set(X):
        if rw not in E or rw not in X: mism[f'{key}_membership'].append(rw); continue
        e = E[rw]; x = X[rw]
        tup_e = (e[3], e[5], e[6], e[7], e[8], e[9]); tup_x = (x['parent'], x['ep'], x['ts'], x['side'], x['qty'], x['px'])
        if tup_e == tup_x: n_ok += 1
        else: mism[f'{key}_fields'].append((rw, tup_e, tup_x))
    rec(f'{key}_exact_match', n_ok)
# 2) episodes
n_ok = 0
for eid in set(LS.episodes) | set(R.episodes):
    e = LS.episodes.get(eid); x = R.episodes.get(eid)
    if e is None or x is None: mism['episode_membership'].append(eid); continue
    te = (e['direction'], e['opened'], e['closed'], e['n_open_fills'], e['n_close_fills'], e['ended_by'], bool(e['started_by_reversal']), e['first_ts'], e['last_ts'])
    tx = (x['dir'], x['opened'], x['closed'], x['n_open'], x['n_close'], x['ended_by'], x['rev'], x['first_ts'], x['last_ts'])
    if te == tx: n_ok += 1
    else: mism['episode_fields'].append((eid, te, tx))
rec('episodes_exact_match', n_ok)
# 3) lifecycle events
ee = sorted((e[1], e[2], e[3], int(e[4][1:]), e[7], e[8], e[9]) for e in LS.events); xe = sorted(R.events)
rec('lifecycle_events_engine', len(ee)); rec('lifecycle_events_ref', len(xe)); rec('lifecycle_events_identical', ee == xe)
if ee != xe:
    se, sx = set(ee), set(xe); mism['lifecycle'] = [('engine_only', sorted(se - sx)[:5]), ('ref_only', sorted(sx - se)[:5])]
# 4) parent roles
rec('parent_roles_identical', LS.roles == ref_roles)
if LS.roles != ref_roles: mism['roles'] = [(p, LS.roles.get(p), ref_roles.get(p)) for p in set(LS.roles) | set(ref_roles) if LS.roles.get(p) != ref_roles.get(p)][:10]
rec('engine_parent_count', len(LS.roles))
# 5) CA per convention
for m in ('FIFO', 'LIFO', 'AVG'):
    X = refs[m]; E = LS.ca[m]; rec(f'CA_{m}_engine_rows', len(E)); rec(f'CA_{m}_ref_rows', len(X.ca))
    # compare in order (both are in application order): (cp_row, src, qty, entry, exit, pnl, remaining)
    nm = 0; nrow = 0
    for k in range(min(len(E), len(X.ca))):
        e = E[k]; x = X.ca[k]; cp_row = int(e[2][4:])
        if m == 'AVG': src_e = e[3]; src_x = x[1]
        else: src_e = int(e[3][4:]); src_x = x[1]
        qty_ok = (cp_row, src_e, e[4], e[6], e[8]) == (x[0], src_x, x[2], x[4], x[6])
        if m == 'AVG':
            pnl_ok = abs(Fraction(e[7]) - x[5]) < Fraction(1, 10 ** 5) * max(1, 1) if not isinstance(e[7], float) else abs(e[7] - float(x[5])) < 1e-3
            ent_ok = abs(float(e[5]) - float(x[3])) < 1e-6
            if not (pnl_ok and ent_ok): mism['CA_AVG_value'].append((k, e, x))
            else: nm += 1
            if abs(float(e[7]) - float(x[5])) > 1e-9 * max(1.0, abs(float(x[5]))): rec('AVG_float_vs_exact_rel_diff_seen', True)
        else:
            if qty_ok and e[5] == x[3] and e[7] == x[5]: nm += 1
            else: mism[f'CA_{m}_row'].append((k, e, x))
        nrow += 1
    rec(f'CA_{m}_exact_match', nm)
    # totals: engine allocation pnl vs exact reference
    if m == 'AVG':
        et = sum(Fraction(str(e[7])) for e in E); xt = X.realized_total; rec('CA_AVG_total_engine_paise', float(et)); rec('CA_AVG_total_ref_exact_paise', float(xt)); rec('CA_AVG_total_abs_diff_paise', float(abs(et - xt)))
        rec('AVG_exact_total_is_integer', xt.denominator == 1); rec('AVG_ref_total_rupees', float(xt) / 100)
    else:
        et = sum(int(e[7]) for e in E); rec(f'CA_{m}_total_engine_paise', et); rec(f'CA_{m}_total_ref_paise', int(X.realized_total)); chk(f'CA_{m}_total', et == int(X.realized_total), (et, int(X.realized_total)))
        rec(f'CA_{m}_realized_rupees', et / 100)
    # remaining slices
    sl = [t.split('\t') for t in __import__('pe.lineage', fromlist=['x']).slices_tsv(LS.runs[m].state, LS.runs[m].lineage).splitlines()[1:]]
    if m == 'AVG':
        eng = {x[4]: (int(x[5]), float(x[6])) for x in sl}; ref = {k: (v[1], float(v[2])) for k, v in X.slices.items()}
        ok = set(eng) == set(ref) and all(eng[k][0] == ref[k][0] and abs(eng[k][1] - ref[k][1]) < 1e-5 for k in eng)
    else:
        eng = {int(x[3][4:]): (int(x[5]), int(x[6]), x[4]) for x in sl}; ref = {k: (v[1], v[2], v[3]) for k, v in X.slices.items()}; ok = eng == ref
    rec(f'slices_{m}_identical', ok); rec(f'slices_{m}_count', len(sl))
    # final instrument inventory vs engine dump
    inv_e = {}
    for l in LS.runs[m].dump.splitlines():
        p = l.split('\t')
        if p[0] == 'INSTR': inv_e[p[1]] = int(p[2])
    rec(f'final_inventory_{m}_identical', inv_e == X.final_inv)
    rec(f'engine_cash_{m}', LS.runs[m].state.cash); rec(f'cash_equal_ref_{m}', LS.runs[m].state.cash == X.cash)
# 6) sensitivity
n_sens_e = sum(1 for v in LS.sensitivity.values() if v == 'CONVENTION_SENSITIVE'); rec('engine_sensitive_CP', n_sens_e)
sens_ref = {f'CP:{RM.to_fill_id(cp)}' for cp in R.cp if fa[cp] != la[cp]}; rec('sensitive_sets_identical', sens_ref == {k for k, v in LS.sensitivity.items() if v == 'CONVENTION_SENSITIVE'})
# 7) per-fill role agreement
roles_e = {int(r.fill_id[1:]): r for r in LS.runs['FIFO'].roles}; nr = 0
for rw, x in R.fills.items():
    e = roles_e[rw]
    if (e.close_qty, e.open_qty, e.inventory_after, bool(e.is_reversal), e.episode_closed, e.episode_opened) == (x['close'], x['open'], x['inv_after'], x['rev'], x['ep_close'], x['ep_open']): nr += 1
    else: mism['fill_role'].append(rw)
rec('fill_roles_exact_match', nr)
rec('MISMATCH_SUMMARY', {k: len(v) for k, v in mism.items()})
for k, v in mism.items(): print('MISMATCH', k, v[:3])
json.dump(dict(results=OUT, mismatches={k: [str(x) for x in v[:20]] for k, v in mism.items()}), open(os.environ.get('OUT_JSON', os.path.join(HERE, 'compare_ref_vs_engine_result.json')), 'w'), indent=1, default=str)
