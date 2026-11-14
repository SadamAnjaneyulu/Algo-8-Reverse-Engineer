"""[RAW]+[IMPL] V4/V5/V6 + coverage + full-ledger scope numbers.
 * V4: figure CSVs vs the committed M2-C slices (aggregation by me from the PORTIONS file), conservation against RAW closing allocations (M2-C grouping RULES are NOT audited here).
 * V5/V6: figure CSVs vs my own aggregation of the committed M2-D items/links, plus an independent W1 / W1_S60 candidate-set re-implementation from RAW (tag + entry minute) as a cross-check of the slice.
 * coverage.json and reports/M2E_CYCLE_COVERAGE_REPORT.md numbers vs RAW; full-ledger scope numbers (V6 G-section / SCOPE_WARNING) vs RAW re-implementation.
No pe.* imports.  Usage: python3 verify_v4v5v6.py [PE_ROOT]"""
import sys, os, csv, json, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raw_truth as T

PE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(T.REPO, 'portfolio_engine')
DATA = os.path.join(PE, 'reports', 'm2e_data'); FIG = os.path.join(PE, 'reports', 'm2e_figures'); D_DIR = os.path.join(PE, 'reports', 'm2d_data')
FAIL = []; OK = collections.Counter()
def rd(p, d='\t'):
    with open(p, newline='') as fh: return list(csv.DictReader(fh, delimiter=d))
def ck(name, cond, detail=''):
    if cond: OK[name] += 1
    else: FAIL.append((name, str(detail)[:300]))
THR = (2, 5, 10, 30, 60)


def v4(und, exp, t):
    cy = f'{und}_{exp}'; D = os.path.join(DATA, cy); G = os.path.join(FIG, cy); R = t['R']
    raw_cp = collections.Counter((a['fill']['row'], a['qty']) for a in R['cp']); raw_cp_units = sum(a['qty'] for a in R['cp']); raw_cp_parents = {a['fill']['parent'] for a in R['cp']}
    cp_by_parent = collections.Counter()
    for a in R['cp']: cp_by_parent[a['fill']['parent']] += a['qty']
    for m in ('C1', 'C2'):
        B = rd(os.path.join(D, f'm2c_closing_batches_{m}.tsv')); M = rd(os.path.join(D, f'm2c_closing_batch_members_{m}.tsv')); P = rd(os.path.join(D, f'm2c_closing_batch_portions_{m}.tsv'))
        FB = rd(os.path.join(G, f'V4_{m}_closing_batches.csv'), ','); FM = rd(os.path.join(G, f'V4_{m}_closing_batches__members_10s.csv'), ','); FS = rd(os.path.join(G, f'V4_{m}_closing_batches__sensitivity_by_threshold.csv'), ','); FL = rd(os.path.join(G, f'V4_{m}_closing_batches__longest_chains.csv'), ',')
        for t_ in THR:
            Pt = [p for p in P if p['threshold_s'] == str(t_)]; Bt = [b for b in B if b['threshold_s'] == str(t_)]; Mt = [x for x in M if x['threshold_s'] == str(t_)]
            ck(f'{cy} {m}@{t_} portions == raw CP multiset', collections.Counter((int(p['source_row_id']), int(p['quantity'])) for p in Pt) == raw_cp, f'{len(Pt)} vs {sum(raw_cp.values())}')
            ck(f'{cy} {m}@{t_} units conserved', sum(int(b['total_closing_qty']) for b in Bt) == raw_cp_units == sum(int(p['quantity']) for p in Pt))
            # per-batch recompute from portions
            bp = collections.defaultdict(list)
            for p in Pt: bp[p['batch_id']].append(p)
            ck(f'{cy} {m}@{t_} batch ids', set(bp) == {b['batch_id'] for b in Bt})
            ck(f'{cy} {m}@{t_} each parent in exactly one batch', len({x['parent_order_id'] for x in Mt}) == len(Mt) == len(raw_cp_parents) and {x['parent_order_id'] for x in Mt} == raw_cp_parents, f'{len(Mt)} vs {len(raw_cp_parents)}')
            for b in Bt:
                ps = bp[b['batch_id']]
                ok = (int(b['n_closing_portions']) == len(ps) and int(b['total_closing_qty']) == sum(int(p['quantity']) for p in ps) and int(b['n_parents']) == len({p['parent_order_id'] for p in ps}) and int(b['n_contracts']) == len({p['instrument_id'] for p in ps})
                      and int(b['duration_s']) == int(b['end_ts']) - int(b['start_ts']) and int(b['duration_s']) >= 0 and int(b['max_link_gap_s']) <= t_ and int(b['max_link_gap_s']) <= int(b['duration_s']) + 0)
                if m == 'C1': ok = ok and int(b['start_ts']) == min(int(p['timestamp_s']) for p in ps)       # first-fill convention: start = earliest closing second in the batch
                ck(f'{cy} {m}@{t_} batch aggregates', ok, str(b)[:200])
            for x in Mt:
                mine = sum(int(p['quantity']) for p in Pt if p['parent_order_id'] == x['parent_order_id'])
                ck(f'{cy} {m}@{t_} member qty == raw parent closing qty', int(x['closing_qty']) == mine == cp_by_parent[x['parent_order_id']], str(x)[:200])
        # figure CSV == dataset (10 s)
        B10 = [b for b in B if b['threshold_s'] == '10']; ck(f'{cy} {m} V4 batch rows', len(FB) == len(B10) and {r['batch_id'] for r in FB} == {b['batch_id'] for b in B10})
        bi = {b['batch_id']: b for b in B10}
        for r in FB:
            b = bi.get(r['batch_id']); ses = b['session']
            ck(f'{cy} {m} V4 row', b is not None and all(r[k] == b[k] for k in ('n_parents', 'n_closing_portions', 'total_closing_qty', 'duration_s', 'n_contracts', 'right_class', 'max_link_gap_s')) and r['start_ts_utc_s'] == b['start_ts'] and r['end_ts_utc_s'] == b['end_ts'] and r['start_ist'] == T.ist_str(int(b['start_ts'])) and r['end_ist'] == T.ist_str(int(b['end_ts']))
               and r['d_label_of_session'] == T.d_label(t['sessions'], exp, ses), str(r)[:200])
        M10 = [x for x in M if x['threshold_s'] == '10']; ck(f'{cy} {m} V4 members_10s', len(FM) == len(M10) and collections.Counter((r['batch_id'], r['parent_order_id'], r['closing_qty']) for r in FM) == collections.Counter((x['batch_id'], x['parent_order_id'], x['closing_qty']) for x in M10))
        for r in FM: ck(f'{cy} {m} V4 member ist', r['parent_first_closing_ist'] == T.ist_str(int(r['parent_first_closing_ts_utc_s'])))
        # sensitivity
        for r in FS:
            t_ = int(r['threshold_s']); bt = [b for b in B if b['threshold_s'] == str(t_)]; n = [int(b['n_parents']) for b in bt]; d = sorted(int(b['duration_s']) for b in bt)
            med = d[len(d) // 2]
            ck(f'{cy} {m} V4 sensitivity@{t_}', int(r['batches']) == len(bt) and int(r['singleton_batches']) == sum(1 for x in n if x == 1) and int(r['max_parents_in_batch']) == max(n) and int(r['median_duration_s']) == med and int(r['max_duration_s']) == d[-1]
               and int(r['closing_portions']) == sum(int(b['n_closing_portions']) for b in bt) == sum(raw_cp.values()) and int(r['closing_units']) == raw_cp_units, str(r))
        ck(f'{cy} {m} V4 sensitivity thresholds', [int(r['threshold_s']) for r in FS] == list(THR))
        # longest chains: top-8 by duration at 60 and 10
        for t_ in (60, 10):
            top = sorted([b for b in B if b['threshold_s'] == str(t_)], key=lambda b: (-int(b['duration_s']), b['batch_id']))[:8]
            ck(f'{cy} {m} V4 longest@{t_}', [r['batch_id'] for r in FL if r['threshold_s'] == str(t_)] == [b['batch_id'] for b in top])


def items_from_slice(D):
    it = rd(os.path.join(D, 'm2d_wing_body_items.tsv')); return {r['item_id']: r for r in it}


def w1_from_raw(t):
    """independent W1 / W1_S60 candidate sets from RAW opening items: wing = long h_ ; body = short num ; same right ; W1 same order-entry minute ; W1_S60 same IST session of first fill & |dt first fill| <= 60 s"""
    wings = {k: d for k, d in t['items'].items() if d['tag'] == 'h_' and d['side'] > 0}; bodies = {k: d for k, d in t['items'].items() if d['tag'] == 'num' and d['side'] < 0}
    right = lambda k: k[1].split('|')[2]
    w1 = collections.defaultdict(set); s60 = collections.defaultdict(set)
    for kw, w in wings.items():
        for kb, b in bodies.items():
            if right(kw) != right(kb): continue
            if w['em'] == b['em']: w1[kw].add(kb)
            if T.ist_date(w['first']) == T.ist_date(b['first']) and abs(w['first'] - b['first']) <= 60: s60[kw].add(kb)
    return wings, bodies, w1, s60


def mult(items, m):  # counts by multiplicity bucket 0..5+
    c = collections.Counter(min(len(m.get(k, ())), 5) for k in items); return [c.get(i, 0) for i in range(6)]


def v5v6(und, exp, t):
    cy = f'{und}_{exp}'; D = os.path.join(DATA, cy); G = os.path.join(FIG, cy)
    wings, bodies, w1, s60 = w1_from_raw(t); wi = items_from_slice(D)
    Wsl = {r['item_id']: r for r in wi.values() if r['level'] == 'OPENING' and r['role'] == 'WING'}; Bsl = {r['item_id']: r for r in wi.values() if r['level'] == 'OPENING' and r['role'] == 'BODY'}
    ck(f'{cy} M2-D opening items == raw tag items', {(r['parent_order_id'], r['instrument_id']): int(r['qty']) for r in Wsl.values()} == {k: d['qty'] for k, d in wings.items()} and {(r['parent_order_id'], r['instrument_id']): int(r['qty']) for r in Bsl.values()} == {k: d['qty'] for k, d in bodies.items()})
    links = {m: [l for l in rd(os.path.join(D, f'm2d_wing_body_links_{m}.tsv')) if l['level'] == 'OPENING'] for m in ('W1', 'W1_S60', 'W2', 'W3')}
    key = lambda iid: (iid.split(':', 3)[3].split(':', 1)[0], iid.split(':', 3)[3].split(':', 1)[1])
    slice_w1 = collections.defaultdict(set); slice_s60 = collections.defaultdict(set)
    for l in links['W1']: slice_w1[key(l['wing_item'])].add(key(l['body_item']))
    for l in links['W1_S60']: slice_s60[key(l['wing_item'])].add(key(l['body_item']))
    ck(f'{cy} W1 slice == independent raw W1 sets', dict(slice_w1) == {k: v for k, v in w1.items() if v}, f'{len(slice_w1)} vs {len(w1)}')
    ck(f'{cy} W1_S60 slice == independent raw W1_S60 sets', dict(slice_s60) == {k: v for k, v in s60.items() if v}, f'{len(slice_s60)} vs {len(s60)}')
    # ---- V5 figure CSVs: recomputed by me
    def fcsv(name): return rd(os.path.join(G, name), ',')
    def vmap(rows): return {(r['panel'], r['category']): r['value'] for r in rows}
    Wk = list(wings); Bk = list(bodies)
    def side_maps(w2b):  # wing->bodies dict and body->wings dict
        bw = collections.defaultdict(set)
        for w, bs in w2b.items():
            for b in bs: bw[b].add(w)
        return w2b, bw
    sl_w3 = collections.defaultdict(set)
    for l in links['W3']: sl_w3[key(l['wing_item'])].add(key(l['body_item']))
    for method in ('W1', 'W1_S60', 'W2', 'W3'):
        rows = fcsv(f'V5_{method}_wing_body.csv'); V = vmap(rows)
        w2b = {'W1': w1, 'W2': w1, 'W1_S60': s60, 'W3': sl_w3}[method]; w2b, b2w = side_maps(w2b)
        mw = mult(Wk, w2b); mb = mult(Bk, b2w); lab = lambda i: '5+' if i == 5 else str(i)
        for i in range(6):
            ck(f'{cy} V5 {method} wing mult {i}', int(V[('candidate_multiplicity', f'wing items with {lab(i)} candidate bodies')]) == mw[i], f'{V.get(("candidate_multiplicity", f"wing items with {lab(i)} candidate bodies"))} vs {mw[i]}')
            ck(f'{cy} V5 {method} body mult {i}', int(V[('candidate_multiplicity', f'body items with {lab(i)} candidate wings')]) == mb[i])
        wu = sum(d['qty'] for d in wings.values()); bu = sum(d['qty'] for d in bodies.values())
        if method == 'W3':
            mq = sum(float(l['queue_matched_units']) for l in links['W3'])
            ck(f'{cy} V5 W3 units', float(V[('units', 'wing units: queue-matched')]) == mq and float(V[('units', 'wing units: queue residual')]) == wu - mq and float(V[('units', 'body units: queue residual')]) == bu - mq and float(V[('units', 'wing units: observed total')]) == wu and float(V[('units', 'body units: observed total')]) == bu, str(V)[:300])
            W1p = {(key(l['wing_item']), key(l['body_item'])) for l in links['W1']}; W60 = {(key(l['wing_item']), key(l['body_item'])) for l in links['W1_S60']}; W3p = {(key(l['wing_item']), key(l['body_item'])) for l in links['W3']}
            ck(f'{cy} V5 W3 link overlap', [int(V[('w3_links_vs_candidate_sets', k)]) for k in ('also a W1 link', 'W1_S60 only', 'in neither')] == [len(W3p & W1p), len((W3p & W60) - W1p), len(W3p - W1p - W60)])
        else:
            for nm, items, m in (('wing', wings, w2b), ('body', bodies, b2w)):
                u = sum(d['qty'] for k, d in items.items() if len(m.get(k, ())) == 1); mu = sum(d['qty'] for k, d in items.items() if len(m.get(k, ())) >= 2); z = sum(d['qty'] for k, d in items.items() if len(m.get(k, ())) == 0)
                ck(f'{cy} V5 {method} {nm} units', (int(V[('units', f'{nm} units: exactly 1 candidate')]), int(V[('units', f'{nm} units: >=2 candidates (ambiguous)')]), int(V[('units', f'{nm} units: no candidate (unmatched)')]), int(V[('units', f'{nm} units: observed total')])) == (u, mu, z, u + mu + z) and u + mu + z == sum(d['qty'] for d in items.values()), '')
        if method in ('W1', 'W1_S60'):
            pairs = [(wings[w]['first'] - bodies[b]['first']) for w, bs in w2b.items() for b in bs]; bins = list(range(-60, 62, 4)) if method == 'W1_S60' else list(range(-120, 62, 6)); cl = [max(min(d, bins[-1] - 1), bins[0]) for d in pairs]
            hist = collections.Counter(); 
            for d in cl:
                for i in range(len(bins) - 1):
                    if bins[i] <= d < bins[i + 1]: hist[i] += 1
            for i in range(len(bins) - 1): ck(f'{cy} V5 {method} hist bin {i}', int(V[('dt_s_histogram', f'[{bins[i]},{bins[i + 1]})')]) == hist.get(i, 0), f'{bins[i]} {V.get(("dt_s_histogram", f"[{bins[i]},{bins[i+1]})"))} vs {hist.get(i, 0)}')
            ck(f'{cy} V5 {method} link count == slice', len(pairs) == len(links[method]), f'{len(pairs)} vs {len(links[method])}')
        if method == 'W2':
            sw = collections.defaultdict(float)
            for l in links['W2']: sw[key(l['body_item'])] += float(l['weighted_wing_units'])
            ck(f'{cy} V5 W2 weights per body', all(abs(float(V[('w2_body_vs_weighted_units', k)]) - sw[key(k)]) < 1e-3 for k in [r['category'] for r in rows if r['panel'] == 'w2_body_vs_weighted_units']) and len([r for r in rows if r['panel'] == 'w2_body_vs_weighted_units']) == len(sw))
    # ---- V6
    V = fcsv('V6_coverage_uncertainty_dashboard.csv'); vm = {(r['section'], r['metric']): r['value'] for r in V}; cov = json.load(open(os.path.join(D, 'coverage.json')))
    for nm, items, wm, bm in (('wing', wings, w1, None), ('body', bodies, None, None)):
        pass
    for mname, mp in (('W1', w1), ('W1_S60', s60)):
        w2b2, b2w2 = side_maps(mp)
        for nm, items, m in (('wing', wings, w2b2), ('body', bodies, b2w2)):
            for lab_, cond in (('1 candidate', lambda n: n == 1), ('>=2 candidates', lambda n: n >= 2), ('none', lambda n: n == 0)):
                ck(f'{cy} V6 A {nm} {mname} {lab_}', int(vm[('A_units_by_candidate_status', f'{nm} units, {mname}: {lab_}')]) == sum(d['qty'] for k, d in items.items() if cond(len(m.get(k, ())))))
        mw = mult(Wk, w2b2)
        for i in range(6): ck(f'{cy} V6 B {mname} {i}', int(vm[('B_wing_multiplicity', f'{mname}: wing items with {lab(i)} candidate bodies')]) == mw[i])
    # section C == raw cross-tab of exclusions
    ex = collections.Counter()
    for a in t['R']['oa']:
        f = a['fill']
        if not ((f['side'] > 0 and f['tag'] == 'h_') or (f['side'] < 0 and f['tag'] == 'num')): ex[f"OPENING|{'LONG' if f['side'] > 0 else 'SHORT'}|{f['tag']}"] += a['qty']
    for a in t['R']['cp']:
        d = t['R']['episodes'][a['eid']]['direction']; f = a['fill']
        if not ((d == 'LONG' and f['tag'] == 'h_') or (d == 'SHORT' and f['tag'] == 'num')): ex[f"CLOSING_of_{d}_episode|closing_module|{f['tag']}"] += a['qty']
    cs = {r['metric']: int(r['value']) for r in V if r['section'] == 'C_role_exclusions_units'}; ck(f'{cy} V6 C exclusions == raw cross-tab', cs == dict(ex), f'{cs} vs {dict(ex)}')
    for ln in ([r for r in V if r['section'] == 'D_unclassified_and_missing']): pass
    # section E: batch counts per threshold
    for m in ('C1', 'C2'):
        B = rd(os.path.join(D, f'm2c_closing_batches_{m}.tsv'))
        for t_ in THR: ck(f'{cy} V6 E {m}@{t_}', int(vm[('E_batch_count_sensitivity', f'{m} batches at {t_} s')]) == sum(1 for b in B if b['threshold_s'] == str(t_)))
    d1 = sum(1 for k in bodies if {w for w, bs in w1.items() if k in bs} != {w for w, bs in s60.items() if k in bs}); d1w = sum(1 for k in wings if w1.get(k, set()) != s60.get(k, set()))
    ck(f'{cy} V6 F diff counts', int(vm[('F_sensitivity_unresolved', 'body items with differing W1 vs W1_S60 candidate set')]) == d1 and int(vm[('F_sensitivity_unresolved', 'wing items with differing W1 vs W1_S60 candidate set')]) == d1w, f'{d1} {d1w}')
    # coverage.json vs raw
    R = t['R']; fl = t['fills']; oq = collections.Counter(); cq = collections.Counter()
    for a in R['oa']: oq[a['fill']['row']] += a['qty']
    for a in R['cp']: cq[a['fill']['row']] += a['qty']
    parents = {f['parent'] for f in fl}; pr = collections.defaultdict(set)
    for a in R['oa']: pr[a['fill']['parent']].add('O')
    for a in R['cp']: pr[a['fill']['parent']].add('C')
    cf = cov['fills']
    ck(f'{cy} cov fills', cf['raw_fill_count'] == len(fl) and cf['unique_parent_orders'] == len(parents) and cf['opening_fills'] == sum(1 for f in fl if oq[f['row']]) and cf['closing_fills'] == sum(1 for f in fl if cq[f['row']]) and cf['fills_with_both_opening_and_closing_quantity'] == sum(1 for f in fl if oq[f['row']] and cq[f['row']])
       and cf['opening_units'] == sum(oq.values()) and cf['closing_units'] == sum(cq.values()) and cf['partially_filled_status'] == sum(1 for f in fl if f['status'] == 'PartiallyFilled') and sorted(cf['mixed_parent_ids']) == sorted(p for p in parents if pr[p] == {'O', 'C'}) and cf['duplicate_flagged'] == 0,
       str(cf)[:300])
    ck(f'{cy} cov roles of parents', cf['parent_roles'] == dict(collections.Counter('MIXED' if pr[p] == {'O', 'C'} else 'OPENING_ONLY' if pr[p] == {'O'} else 'CLOSING_ONLY' for p in parents)), str(cf['parent_roles']))
    ce = cov['episodes']; ck(f'{cy} cov episodes', ce['episode_count'] == len(R['episodes']) and ce['started_by_reversal'] == sum(1 for e in R['episodes'].values() if e['by_reversal']) and ce['terminal_status'] == dict(collections.Counter('REVERSED' if e['ended_by'] == 'reversal' else 'CLOSED' for e in R['episodes'].values())) and ce['expired_unclosed'] == sum(1 for v in R['inv'].values() if v))
    ck(f'{cy} cov contracts traded', cov['historical_marks']['contracts_traded'] == len({f['iid'] for f in fl}))
    rc = cov['role_classification']['opening_units_by_tag_role']; mine = collections.Counter()
    for (p, i), d in t['items'].items(): mine['BODY_SHORT_BY_TAG' if (d['tag'] == 'num' and d['side'] < 0) else 'WING_LONG_BY_TAG' if (d['tag'] == 'h_' and d['side'] > 0) else f"UNCLASSIFIED({d['tag']},{'SELL' if d['side'] < 0 else 'BUY'})"] += d['qty']
    ck(f'{cy} cov role units', rc == dict(mine), f'{rc} vs {dict(mine)}')
    ck(f'{cy} cov scope exclusions', cov['role_classification']['m2d_tagged_scope_exclusions_units'] == dict(sorted(ex.items())) or dict(cov['role_classification']['m2d_tagged_scope_exclusions_units']) == dict(ex))
    for s, v in cov['d1_d0'].items():
        ffs = [f for f in fl if T.ist_date(f['ts']) == s]; ck(f'{cy} cov session {s}', v['fills'] == len(ffs) and v['parents'] == len({f['parent'] for f in ffs}) and v['opening_units'] == sum(oq[f['row']] for f in ffs) and v['closing_units'] == sum(cq[f['row']] for f in ffs) and v['first_fill_ist'] == T.ist_str(min(f['ts'] for f in ffs)) and v['last_fill_ist'] == T.ist_str(max(f['ts'] for f in ffs))
           and v['instruments'] == len({f['iid'] for f in ffs}) and v['episodes_started'] == sum(1 for e in R['episodes'].values() if T.ist_date(e['first_ts']) == s) and v['episodes_ended'] == sum(1 for e in R['episodes'].values() if T.ist_date(e['last_ts']) == s) and v['d_label'] == T.d_label(t['sessions'], exp, s), str(v))
    # wing/body coverage counts quoted in the coverage report table
    return dict(wing_no_w1=sum(1 for k in wings if not w1.get(k)), wing_no_s60=sum(1 for k in wings if not s60.get(k)), body_no_w1=sum(1 for k in bodies if not any(k in bs for bs in w1.values())), body_no_s60=sum(1 for k in bodies if not any(k in bs for bs in s60.values())))


def full_ledger():
    """full-ledger scope numbers quoted in SCOPE_WARNING / V6 section G, re-derived from RAW (all cycles)."""
    raw = T.load_raw(); keys = sorted({(r[12], T.parse_expiry(r[15])) for r in raw}); tot = collections.Counter(); closing_excl = 0
    for und, exp in keys:
        t = T.truth(und, exp); wings, bodies, w1, s60 = w1_from_raw(t); tot['wing_items'] += len(wings)
        for nm, mp in (('W1', w1), ('S60', s60)):
            wl = {k: v for k, v in mp.items() if v}; tot[f'{nm}_with'] += len(wl); tot[f'{nm}_unique'] += sum(1 for v in wl.values() if len(v) == 1); tot[f'{nm}_multi'] += sum(1 for v in wl.values() if len(v) > 1); tot[f'{nm}_none'] += len(wings) - len(wl); tot[f'{nm}_unmatched_units'] += sum(d['qty'] for k, d in wings.items() if k not in wl)
        for a in t['R']['cp']:
            d = t['R']['episodes'][a['eid']]['direction']; f = a['fill']
            if not ((d == 'LONG' and f['tag'] == 'h_') or (d == 'SHORT' and f['tag'] == 'num')): closing_excl += a['qty']
    tot['closing_excl'] = closing_excl; tot['wing_units'] = None; return tot


if __name__ == '__main__':
    cov_extra = {}
    for und, exp in T.CYCLES:
        t = T.truth(und, exp); v4(und, exp, t); r = v5v6(und, exp, t); cov_extra[f'{und}_{exp}'] = r
    print('coverage-report wing/body no-candidate counts from raw:', cov_extra)
    fl = full_ledger(); print('FULL-LEDGER from raw:', dict(fl))
    sm = json.load(open(os.path.join(D_DIR, 'm2d_summary.json'))); W1 = sm['coverage']['OPENING|W1']; S = sm['coverage']['OPENING|W1_S60']
    chk = {'W1 wing items': (fl['wing_items'], W1['wing_items']), 'W1 with cand': (fl['W1_with'], W1['wing_items_with_candidate']), 'W1 unique': (fl['W1_unique'], W1['wing_items_unique_candidate']), 'W1 multi': (fl['W1_multi'], W1['wing_items_multiple_candidates']), 'W1 none': (fl['W1_none'], W1['wing_items_no_candidate']), 'W1 unmatched units': (fl['W1_unmatched_units'], W1['wing_units_unmatched']),
           'S60 with': (fl['S60_with'], S['wing_items_with_candidate']), 'S60 none': (fl['S60_none'], S['wing_items_no_candidate']), 'S60 unmatched units': (fl['S60_unmatched_units'], S['wing_units_unmatched']), 'closing excluded units': (fl['closing_excl'], sum(v for k, v in sm['scope_exclusions_TAGGED_units'].items() if k.startswith('CLOSING')))}
    for k, (a, b) in chk.items(): ck(f'FULL-LEDGER {k}', a == b, f'raw-derived {a} vs M2-D summary {b}')
    print('PASSED:', sum(OK.values()), 'checks in', len(OK), 'families; FAILED:', len(FAIL))
    for n, d in FAIL[:40]: print('  FAIL', n, d)
    sys.exit(1 if FAIL else 0)
