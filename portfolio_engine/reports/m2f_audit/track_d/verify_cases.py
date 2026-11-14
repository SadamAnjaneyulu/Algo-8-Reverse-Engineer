"""[RAW]+[IMPL] Case studies: (a) independent re-implementation of the 10 selection RULES from RAW-derived episodes/items (+ committed C1 slice for CT9 only) and comparison with case_studies.json;
(b) per-case record re-derivation from RAW: fills, per-episode opening/closing quantities, opening/closing parents, lifecycle, wing/body candidate membership, related reversal episodes; mixed parents.
(c) selection-effect statistics (rank of chosen candidate among qualifying ones, time of day, D-label).  No pe.* imports.  Usage: verify_cases.py [PE_ROOT]"""
import sys, os, csv, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raw_truth as T
from verify_v4v5v6 import w1_from_raw
PE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(T.REPO, 'portfolio_engine'); DATA = os.path.join(PE, 'reports', 'm2e_data')
FAIL = []; OK = collections.Counter(); STATS = {}
def ck(n, c, d=''):
    if c: OK[n] += 1
    else: FAIL.append((n, str(d)[:300]))
def rd(p): return list(csv.DictReader(open(p, newline=''), delimiter='\t'))


def indep(und, exp):
    cy = f'{und}_{exp}'; t = T.truth(und, exp); R = t['R']; E = R['episodes']
    cnt = collections.defaultdict(collections.Counter)
    for e in R['events']: cnt[e['eid']][e['kind']] += 1
    eps = sorted(E.values(), key=lambda e: (e['first_ts'], e['eid'])); term = {e['eid']: ('REVERSED' if e['ended_by'] == 'reversal' else 'CLOSED' if e['ended_by'] == 'flat' else 'OPEN') for e in E.values()}
    wings, bodies, w1, s60 = w1_from_raw(t); items = t['items']
    item_id = lambda lvl, role, k: f'WBI:{lvl}:{role}:{k[0]}:{k[1]}'
    ep_of = lambda k: sorted(items[k]['eids'])[0]
    b_sorted = sorted(bodies, key=lambda k: (bodies[k]['first'], item_id('OPENING', 'BODY', k))); w_sorted = sorted(wings, key=lambda k: (wings[k]['first'], item_id('OPENING', 'WING', k)))
    w1b = collections.defaultdict(set)
    for w, bs in w1.items():
        for b in bs: w1b[b].add(w)
    s60b = collections.defaultdict(set)
    for w, bs in s60.items():
        for b in bs: s60b[b].add(w)
    cand = collections.OrderedDict()
    cand['CT1_INCREMENTAL_OPENING'] = [(e['eid'], None) for e in eps if cnt[e['eid']]['ADDED'] >= 3]
    cand['CT2_PARTIAL_REDUCTION'] = [(e['eid'], None) for e in eps if cnt[e['eid']]['PARTIALLY_REDUCED'] >= 2 and term[e['eid']] == 'CLOSED']
    cand['CT3_FULL_CLOSURE'] = [(e['eid'], None) for e in eps if term[e['eid']] == 'CLOSED' and cnt[e['eid']]['CLOSED'] == 1 and not cnt[e['eid']]['PARTIALLY_REDUCED']]
    cand['CT4_REMAINING_AT_EXPIRY'] = [(e['eid'], None) for e in eps if term[e['eid']] not in ('CLOSED', 'REVERSED')]
    cand['CT5_REVERSAL'] = [(e['eid'], None) for e in eps if cnt[e['eid']]['REVERSED']]
    cand['CT6_MULTIPLE_CANDIDATE_WINGS'] = [(ep_of(k), item_id('OPENING', 'BODY', k)) for k in b_sorted if len(w1b.get(k, ())) >= 2]
    cand['CT6b_WING_WITH_MULTIPLE_CANDIDATE_BODIES'] = [(ep_of(k), item_id('OPENING', 'WING', k)) for k in w_sorted if len(w1.get(k, ())) >= 2]
    cand['CT7_NO_CANDIDATE_WING'] = [(ep_of(k), item_id('OPENING', 'BODY', k)) for k in b_sorted if len(w1b.get(k, ())) == 0]
    cand['CT8_W1_VS_W1S60_DISAGREEMENT'] = [(ep_of(k), item_id('OPENING', 'BODY', k)) for k in b_sorted if w1b.get(k, set()) != s60b.get(k, set())]
    B = rd(os.path.join(DATA, cy, 'm2c_closing_batches_C1.tsv')); P = rd(os.path.join(DATA, cy, 'm2c_closing_batch_portions_C1.tsv'))
    cb = sorted([b for b in B if b['threshold_s'] == '10' and int(b['n_parents']) >= 2], key=lambda b: (int(b['start_ts']), b['batch_id'])); cpe = {(a['fill']['row'], a['qty']): a['eid'] for a in R['cp']}; c9 = []
    for b in cb:
        ps = sorted([p for p in P if p['batch_id'] == b['batch_id'] and p['threshold_s'] == '10'], key=lambda p: (int(p['timestamp_s']), int(p['source_row_id']))); c9.append((cpe[(int(ps[0]['source_row_id']), int(ps[0]['quantity']))], b['batch_id']))
    cand['CT9_MULTI_PARENT_CLOSING_BATCH'] = c9
    used = {}; sel = {}
    for name, cs in cand.items():
        if not cs: sel[name] = dict(status='UNAVAILABLE'); continue
        fresh = [c for c in cs if c[0] not in used]; ch = (fresh or cs)[0]; used.setdefault(ch[0], name)
        sel[name] = dict(status='AVAILABLE', episode_id=ch[0], anchor=ch[1], n_qualifying=len(cs), rank=cs.index(ch) + 1, chrono_first=cs[0], reused=not fresh)
    return sel, t, w1, s60, w1b, s60b


def main():
    for und, exp in T.CYCLES:
        cy = f'{und}_{exp}'; sel, t, w1, s60, w1b, s60b = indep(und, exp); CS = json.load(open(os.path.join(DATA, cy, 'case_studies.json'))); R = t['R']; E = R['episodes']; ses = t['sessions']; STATS[cy] = {}
        for name, s in sel.items():
            c = CS['selection'][name]; ck(f'{cy} {name} selection status', c['status'] == s['status'], f'{c["status"]} vs {s["status"]}')
            if s['status'] != 'AVAILABLE': STATS[cy][name] = 'UNAVAILABLE'; continue
            ck(f'{cy} {name} selected episode', c['episode_id'] == s['episode_id'], f'{c["episode_id"]} vs {s["episode_id"]}'); ck(f'{cy} {name} anchor', c['anchor'] == s['anchor'], f'{c["anchor"]} vs {s["anchor"]}'); ck(f'{cy} {name} n_qualifying', c['n_qualifying'] == s['n_qualifying'])
            e = E[s['episode_id']]; STATS[cy][name] = dict(episode=s['episode_id'], n_qualifying=s['n_qualifying'], rank_of_chosen_among_qualifying=s['rank'], chosen_is_chronological_first=(s['rank'] == 1 and not s['reused']), reused_episode=s['reused'], episode_first_fill_ist=T.ist_str(e['first_ts']), d_label=T.d_label(ses, exp, T.ist_date(e['first_ts'])))
            # ---- record re-derivation from RAW
            rec = CS['records'][name]; eid = s['episode_id']; ev = [x for x in R['events'] if x['eid'] == eid]
            ck(f'{cy} {name} lifecycle', [(l['event'], l['quantity'], l['inventory_after'], l['ts_ist']) for l in rec['lifecycle']] == [(x['kind'], x['qty'], x['inv_after'], T.ist_str(x['fill']['ts'])) for x in ev])
            ck(f'{cy} {name} episode totals', (rec['opened'], rec['closed'], rec['remaining']) == (e['opened'], e['closed'], e['opened'] - e['closed']) and rec['terminal_status'] == ('REVERSED' if e['ended_by'] == 'reversal' else 'CLOSED') and rec['direction'] == e['direction'] and rec['started_by_reversal'] == e['by_reversal'] and rec['instrument_id'] == e['iid'])
            oq = collections.Counter(); cq = collections.Counter()
            for a in R['oa']:
                if a['eid'] == eid: oq[a['fill']['row']] += a['qty']
            for a in R['cp']:
                if a['eid'] == eid: cq[a['fill']['row']] += a['qty']
            frows = sorted({x['fill']['row'] for x in ev}); fl = {f['row']: f for f in t['fills']}
            ck(f'{cy} {name} fill ids', [f['source_row_id'] for f in rec['fills']] == [str(r) for r in sorted(frows, key=lambda r: (fl[r]['ts'], r))] or sorted(int(f['source_row_id']) for f in rec['fills']) == frows, f'{len(rec["fills"])} vs {len(frows)}')
            for f in rec['fills']:
                r = int(f['source_row_id']); x = fl[r]
                ck(f'{cy} {name} fill fields', f['parent_order_id'] == x['parent'] and f['module_tag'] == x['tag'] and int(f['side']) == x['side'] and f['quantity'] == x['qty'] and f['exec_price_paise'] == x['px_paise'] and f['ts_ist'] == T.ist_str(x['ts']) and f['d_label'] == T.d_label(ses, exp, T.ist_date(x['ts']))
                   and f['opening_qty_in_episode'] == oq[r] and f['closing_qty_in_episode'] == cq[r] and oq[r] + cq[r] <= x['qty'], f'{f}')
            ck(f'{cy} {name} opening parents', rec['opening_parents'] == sorted({a['fill']['parent'] for a in R['oa'] if a['eid'] == eid}) and rec['closing_parents'] == sorted({a['fill']['parent'] for a in R['cp'] if a['eid'] == eid}))
            # wing/body membership: items with an opening allocation in this episode
            mem = {k: d for k, d in t['items'].items() if eid in d['eids']}
            ck(f'{cy} {name} wb membership parents', sorted(w['parent_order_id'] for w in rec['wing_body_candidates']) == sorted(k[0] for k in mem), f'{len(rec["wing_body_candidates"])} vs {len(mem)}')
            for w in rec['wing_body_candidates']:
                k = (w['parent_order_id'], e['iid']); d = mem.get(k)
                if d is None: ck(f'{cy} {name} wb member exists', False, str(w)[:150]); continue
                q_ep = sum(a['qty'] for a in R['oa'] if a['eid'] == eid and a['fill']['parent'] == k[0] and a['fill']['iid'] == k[1]); ck(f'{cy} {name} wb qty in episode', w['quantity_in_this_episode'] == q_ep, f'{w["quantity_in_this_episode"]} vs {q_ep}')
                inscope = (d['tag'] == 'num' and d['side'] < 0) or (d['tag'] == 'h_' and d['side'] > 0); ck(f'{cy} {name} wb scope flag', ('item_id' in w) == inscope, str(w)[:150])
                if inscope:
                    cp1 = (w1 if d['tag'] == 'h_' else w1b); cp60 = (s60 if d['tag'] == 'h_' else s60b); key = lambda iid: tuple(iid.split(':', 3)[3].split(':', 1))
                    ck(f'{cy} {name} W1 candidates', {key(x['counterpart']) for x in w['W1']} == set(cp1.get(k, set())), f'{k}'); ck(f'{cy} {name} W1_S60 candidates', {key(x['counterpart']) for x in w['W1_S60']} == set(cp60.get(k, set())), f'{k}')
                    ck(f'{cy} {name} W1 dt', all(int(x['dt_s']) == ((d['first'] - t['items'][key(x['counterpart'])]['first']) if d['tag'] == 'h_' else (t['items'][key(x['counterpart'])]['first'] - d['first'])) for x in w['W1']))
            # related reversal episodes
            rel = {x['episode_id'] for x in rec['related_reversal_episodes']}
            exp_rel = {x['eid'] for x in E.values() if x['iid'] == e['iid'] and x['eid'] != eid and ((x['by_reversal'] and x['first_ts'] == e['last_ts'] and e['ended_by'] == 'reversal') or (e['by_reversal'] and x['ended_by'] == 'reversal' and x['last_ts'] == e['first_ts']))}
            ck(f'{cy} {name} related reversal episodes', rel == exp_rel, f'{rel} vs {exp_rel}')
    # special: mixed parents / reversing fill
    t = T.truth('NIFTY', '2026-06-30'); R = t['R']
    rev = [x for x in R['events'] if x['kind'] == 'REVERSED']; ck('NIFTY exactly one reversal', len(rev) == 1); f = rev[0]['fill']
    oa = [a for a in R['oa'] if a['fill']['row'] == f['row']]; cp = [a for a in R['cp'] if a['fill']['row'] == f['row']]
    STATS['NIFTY_reversing_fill'] = dict(fill_row=f['row'], parent=f['parent'], qty=f['qty'], closing_portion=[(a['eid'], a['qty']) for a in cp], opening_portion=[(a['eid'], a['qty']) for a in oa], ts_ist=T.ist_str(f['ts']), side=f['side'], tag=f['tag'])
    ck('NIFTY reversing fill is h_30084825701151', f['parent'] == 'h_30084825701151' and len(oa) == 1 and len(cp) == 1 and oa[0]['eid'].endswith('#2') and cp[0]['eid'].endswith('#1') and oa[0]['qty'] + cp[0]['qty'] == f['qty'])
    for und, exp, pid in (('NIFTY', '2026-06-30', 'h_30084825701151'), ('SENSEX', '2026-07-16', 's_16053046299662')):
        t = T.truth(und, exp); R = t['R']; fl = [f for f in t['fills'] if f['parent'] == pid]
        STATS[f'{und}_mixed_parent_{pid}'] = dict(fills=[(f['row'], T.ist_str(f['ts']), f['iid'].split('|', 2)[2], 'BUY' if f['side'] > 0 else 'SELL', f['qty'], f['tag'], [(a['eid'].split('|', 2)[2], 'open', a['qty']) for a in R['oa'] if a['fill']['row'] == f['row']] + [(a['eid'].split('|', 2)[2], 'close', a['qty']) for a in R['cp'] if a['fill']['row'] == f['row']]) for f in fl])
        ds = rd(os.path.join(DATA, f'{und}_{exp}', 'fills.tsv')); mine = {f['row']: f for f in fl}
        for r in ds:
            if r['parent_order_id'] == pid: ck(f'{und} mixed parent fill in dataset', int(r['source_row_id']) in mine and int(r['opening_qty']) == sum(a['qty'] for a in R['oa'] if a['fill']['row'] == int(r['source_row_id'])) and int(r['closing_qty']) == sum(a['qty'] for a in R['cp'] if a['fill']['row'] == int(r['source_row_id'])))
        ck(f'{und} mixed parent: dataset covers all raw fills', {int(r['source_row_id']) for r in ds if r['parent_order_id'] == pid} == set(mine))
    print('PASSED:', sum(OK.values()), 'checks;', len(OK), 'families; FAILED:', len(FAIL))
    for n, d in FAIL[:30]: print('  FAIL', n, d)
    if len(sys.argv) <= 1: json.dump(STATS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'case_selection_stats.json'), 'w'), indent=1, default=str)
    return 1 if FAIL else 0


if __name__ == '__main__': sys.exit(main())
