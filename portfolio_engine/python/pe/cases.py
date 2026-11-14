"""M2-E position case studies. Selection is PREDEFINED and structural: candidates are scanned in chronological order (first timestamp, then id) and the FIRST qualifying
episode / item / batch is taken. Profit, loss, price and any outcome are never consulted. A case type with no qualifying candidate in THIS cycle is reported UNAVAILABLE
(never borrowed from the other cycle). Cases prefer an episode not already used by an earlier case type; if the only qualifying episode was used, it is reused and flagged.
"""
import os
from collections import Counter, defaultdict
from . import forensics as F

RULES = [
    ('CT1_INCREMENTAL_OPENING', 'first episode (by first fill time) with >= 3 ADDED lifecycle events'),
    ('CT2_PARTIAL_REDUCTION', 'first episode with >= 2 PARTIALLY_REDUCED events and terminal status CLOSED'),
    ('CT3_FULL_CLOSURE', 'first episode whose only closing event is a single CLOSED event (no PARTIALLY_REDUCED, no REVERSED)'),
    ('CT4_REMAINING_AT_EXPIRY', 'first episode whose M2-B terminal status is neither CLOSED nor REVERSED (expired unclosed)'),
    ('CT5_REVERSAL', 'first episode ended by a REVERSED event (extra case type: reversal timeline)'),
    ('CT6_MULTIPLE_CANDIDATE_WINGS', 'first opening BODY item (W1) with >= 2 candidate wing items'),
    ('CT6b_WING_WITH_MULTIPLE_CANDIDATE_BODIES', 'first opening WING item (W1) with >= 2 candidate body items (extra)'),
    ('CT7_NO_CANDIDATE_WING', 'first opening BODY item (W1) with 0 candidate wing items'),
    ('CT8_W1_VS_W1S60_DISAGREEMENT', 'first opening BODY item whose W1 candidate-wing set differs from its W1_S60 candidate-wing set'),
    ('CT9_MULTI_PARENT_CLOSING_BATCH', 'first C1 10 s closing batch (by start time) with >= 2 parent orders; the case episode is the episode of its first member portion')]

EVIDENCE_LINES = dict(
    lifecycle='CONFIRMED_OBSERVATION (fills, parents, lifecycle events, opening and closing quantities are observed and identical under FIFO, LIFO and AVG)',
    closing_allocation='ANALYTICAL: which opening lot a closing portion consumed is convention-dependent (AVG = pooled, NOT_IDENTIFIABLE); no lot ownership is claimed',
    batches='CONFIRMED_OBSERVATION of temporal clustering; a batch is a time-connected closing-order cluster, NOT a decision (decision unit UNRESOLVED)',
    wing_body='W1 WEAKLY_SUPPORTED (inferred candidate, co-submission minute); W1_S60 UNRESOLVED (execution-time proximity, not decision-time evidence); W2 weights are not allocations; W3 is opening-level queue arithmetic, not ownership (UNRESOLVED)',
    ownership='UNRESOLVED / NOT_TESTABLE: lot-level ownership and protective intent cannot be established from the fills')


def _rows(path):
    with open(path) as fh: return F.read_tsv_text(fh.read())[1]


def load_data(d):
    L = lambda n: _rows(os.path.join(d, n))
    return dict(episodes=L('episodes.tsv'), events=L('lifecycle_events.tsv'), fills={r['fill_id']: r for r in L('fills.tsv')}, items=L('opening_items.tsv'), wb_items={r['item_id']: r for r in L('m2d_wing_body_items.tsv')},
                links={m: L(f'm2d_wing_body_links_{m}.tsv') for m in ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3')}, batches={m: L(f'm2c_closing_batches_{m}.tsv') for m in ('C1', 'C2')}, members={m: L(f'm2c_closing_batch_members_{m}.tsv') for m in ('C1', 'C2')},
                portions={m: L(f'm2c_closing_batch_portions_{m}.tsv') for m in ('C1', 'C2')})


def item_parts(item_id): _, level, role, rest = item_id.split(':', 3); parent, inst = rest.split(':', 1); return level, role, parent, inst


def episode_of_fill(D):
    m = defaultdict(list)
    for e in D['events']: m[e['fill_id']].append(e['episode_id'])
    return m


def _cands(D, method):
    """body item -> set of candidate wing items and wing item -> set of candidate body items (OPENING level)."""
    b = defaultdict(set); w = defaultdict(set)
    for l in D['links'][method]:
        if l['level'] != 'OPENING': continue
        b[l['body_item']].add(l['wing_item']); w[l['wing_item']].add(l['body_item'])
    return b, w


def select(D):
    """Returns {case_type: dict(status, anchor, episode_id, rule, note)}; deterministic."""
    eps = sorted(D['episodes'], key=lambda r: (int(r['first_ts_utc_s']), r['episode_id'])); ev = defaultdict(list)
    for e in D['events']: ev[e['episode_id']].append(e)
    cnt = {k: Counter(x['event_type'] for x in v) for k, v in ev.items()}; used = {}; out = {}; efill = episode_of_fill(D)
    b1, w1 = _cands(D, 'W1'); b60, _ = _cands(D, 'W1_S60')
    oi = {(r['parent_order_id'], r['instrument_id']): r for r in D['items']}
    def ep_of_item(item_id):
        _, _, p, inst = item_parts(item_id); r = oi[(p, inst)]; fid = r['oa_ids'].split(',')[0].split(':')[1]; return efill[fid][0]
    def pick(name, cands, anchor_fn=None):
        rule = dict(RULES)[name]
        if not cands: out[name] = dict(status='UNAVAILABLE', rule=rule, episode_id=None, anchor=None, note='no qualifying candidate in this cycle (not borrowed from another cycle)'); return
        fresh = [c for c in cands if c[0] not in used]; chosen = (fresh or cands)[0]; note = '' if fresh else f'reuses the episode of {used[chosen[0]]} (no distinct qualifying episode)'
        used.setdefault(chosen[0], name); out[name] = dict(status='AVAILABLE', rule=rule, episode_id=chosen[0], anchor=chosen[1], note=note, n_qualifying=len(cands))
    pick('CT1_INCREMENTAL_OPENING', [(r['episode_id'], None) for r in eps if cnt[r['episode_id']]['ADDED'] >= 3])
    pick('CT2_PARTIAL_REDUCTION', [(r['episode_id'], None) for r in eps if cnt[r['episode_id']]['PARTIALLY_REDUCED'] >= 2 and r['terminal_status'] == 'CLOSED'])
    pick('CT3_FULL_CLOSURE', [(r['episode_id'], None) for r in eps if r['terminal_status'] == 'CLOSED' and cnt[r['episode_id']]['CLOSED'] == 1 and not cnt[r['episode_id']]['PARTIALLY_REDUCED']])
    pick('CT4_REMAINING_AT_EXPIRY', [(r['episode_id'], None) for r in eps if r['terminal_status'] not in ('CLOSED', 'REVERSED')])
    pick('CT5_REVERSAL', [(r['episode_id'], None) for r in eps if cnt[r['episode_id']]['REVERSED']])
    bodies = sorted([r for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == 'BODY'], key=lambda r: (int(r['first_ts']), r['item_id']))
    wings = sorted([r for r in D['wb_items'].values() if r['level'] == 'OPENING' and r['role'] == 'WING'], key=lambda r: (int(r['first_ts']), r['item_id']))
    pick('CT6_MULTIPLE_CANDIDATE_WINGS', [(ep_of_item(r['item_id']), r['item_id']) for r in bodies if len(b1.get(r['item_id'], ())) >= 2])
    pick('CT6b_WING_WITH_MULTIPLE_CANDIDATE_BODIES', [(ep_of_item(r['item_id']), r['item_id']) for r in wings if len(w1.get(r['item_id'], ())) >= 2])
    pick('CT7_NO_CANDIDATE_WING', [(ep_of_item(r['item_id']), r['item_id']) for r in bodies if len(b1.get(r['item_id'], ())) == 0])
    pick('CT8_W1_VS_W1S60_DISAGREEMENT', [(ep_of_item(r['item_id']), r['item_id']) for r in bodies if b1.get(r['item_id'], set()) != b60.get(r['item_id'], set())])
    cb = sorted([r for r in D['batches']['C1'] if r['threshold_s'] == '10' and int(r['n_parents']) >= 2], key=lambda r: (int(r['start_ts']), r['batch_id']))
    firstcp = {}
    for r in D['portions']['C1']:
        if r['threshold_s'] == '10': firstcp.setdefault(r['batch_id'], []).append(r)
    cands = []
    for b in cb:
        ps = sorted(firstcp[b['batch_id']], key=lambda r: (int(r['timestamp_s']), int(r['source_row_id']))); cands.append((efill[ps[0]['fill_id']][0], b['batch_id']))
    pick('CT9_MULTI_PARENT_CLOSING_BATCH', cands)
    return out


def record(c, D, name, sel):
    """Compact forensic record for one selected case."""
    if sel['status'] != 'AVAILABLE': return dict(case_type=name, status='UNAVAILABLE', selection_rule=sel['rule'], reason=sel['note'])
    eid = sel['episode_id']; E = next(r for r in D['episodes'] if r['episode_id'] == eid); ev = [e for e in D['events'] if e['episode_id'] == eid]; inst = E['instrument_id']
    fills = [D['fills'][e['fill_id']] for e in ev]; ls = c.ls
    cps = [r for r in ls.cp.values() if r[5] == eid]; oas = [r for r in ls.oa.values() if r[5] == eid]
    cpsens = Counter(ls.sensitivity[r[1]] for r in cps)
    oq_ep = {r[2]: r[8] for r in oas}; cq_ep = {r[2]: r[8] for r in cps}          # per-EPISODE quantities: a reversing fill's opening portion belongs to the successor episode, not this one
    open_parents = sorted({r[3] for r in oas}); close_parents = sorted({r[3] for r in cps}); batch = {}
    for m in ('C1', 'C2'):
        bi = {r['batch_id']: r for r in D['batches'][m] if r['threshold_s'] == '10'}; rows = []
        for mem in D['members'][m]:
            if mem['threshold_s'] == '10' and mem['parent_order_id'] in close_parents:
                b = bi[mem['batch_id']]; rows.append(dict(parent_order_id=mem['parent_order_id'], batch_id=mem['batch_id'], batch_n_parents=int(b['n_parents']), batch_duration_s=int(b['duration_s']), batch_start_ist=F.ist_str(int(b['start_ts'])), batch_end_ist=F.ist_str(int(b['end_ts'])), join_gap_s=mem['join_gap_s'] or 'first member'))
        batch[m] = rows
    itm = [r for r in D['items'] if r['instrument_id'] == inst and any(f"OA:{f['fill_id']}" in r['oa_ids'].split(',') for f in fills)]; wb = []
    for r in itm:
        iid = next((k for k, v in D['wb_items'].items() if v['level'] == 'OPENING' and v['parent_order_id'] == r['parent_order_id'] and v['instrument_id'] == r['instrument_id']), None)
        if iid is None: wb.append(dict(parent_order_id=r['parent_order_id'], tag_role=r['tag_role'], status='NOT_IN_M2D_TAGGED_SCOPE (unclassified by module tag; NOT a claim that no wing existed)')); continue
        d = dict(parent_order_id=r['parent_order_id'], item_id=iid, tag_role=r['tag_role'], role=D['wb_items'][iid]['role'], quantity=int(r['quantity']))
        for m in ('W1', 'W1_S60'):
            other = 'wing_item' if D['wb_items'][iid]['role'] == 'BODY' else 'body_item'; me = 'body_item' if other == 'wing_item' else 'wing_item'
            d[m] = [dict(counterpart=l[other], dt_s=int(l['dt_s']), qty_ratio=l['qty_ratio'], evidence_class=l['evidence_class']) for l in D['links'][m] if l['level'] == 'OPENING' and l[me] == iid]
        d['W2_weighted_units'] = [dict(counterpart=l['wing_item' if D['wb_items'][iid]['role'] == 'BODY' else 'body_item'], weighted_wing_units=l['weighted_wing_units']) for l in D['links']['W2'] if l['level'] == 'OPENING' and l['body_item' if D['wb_items'][iid]['role'] == 'BODY' else 'wing_item'] == iid]
        d['W3_queue_matched_units'] = [dict(counterpart=l['wing_item' if D['wb_items'][iid]['role'] == 'BODY' else 'body_item'], queue_matched_units=l['queue_matched_units']) for l in D['links']['W3'] if l['level'] == 'OPENING' and l['body_item' if D['wb_items'][iid]['role'] == 'BODY' else 'wing_item'] == iid]
        wb.append(d)
    rem = int(E['remaining'])
    return dict(case_type=name, status='AVAILABLE', selection_rule=sel['rule'], selection_note=sel['note'], anchor=sel['anchor'], position_id=eid, instrument_id=inst, direction=E['direction'], right=E['right'], strike=E['strike'],
                fills=[dict(fill_id=f['fill_id'], source_row_id=f['source_row_id'], parent_order_id=f['parent_order_id'], module_tag=f['module_tag'], side=f['side'], quantity=int(f['quantity']), fill_opening_qty=int(f['opening_qty']), fill_closing_qty=int(f['closing_qty']), opening_qty_in_episode=oq_ep.get(f['fill_id'], 0), closing_qty_in_episode=cq_ep.get(f['fill_id'], 0), exec_price_paise=int(f['price_paise']), ts_ist=f['ts_ist'], d_label=f['d_label']) for f in fills],
                opening_parents=open_parents, closing_parents=close_parents,
                lifecycle=[dict(seq=int(e['seq']), event=e['event_type'], ts_ist=e['ts_ist'], quantity=int(e['quantity']), inventory_after=int(e['inventory_after'])) for e in ev],
                opened=int(E['opened']), closed=int(E['closed']), remaining=rem, terminal_status=E['terminal_status'], started_by_reversal=bool(int(E['started_by_reversal'])), ended_by=E['ended_by'],
                convention=dict(observed_layer='identical under FIFO, LIFO, AVG', closing_portions=len(cps), closing_portions_convention_sensitive_FIFO_vs_LIFO=cpsens.get('CONVENTION_SENSITIVE', 0), avg='pooled; lot attribution NOT_IDENTIFIABLE'),
                closing_batch_association_10s=batch, wing_body_candidates=wb,
                evidence=dict(EVIDENCE_LINES), missing_information=['historical market marks (source absent): no mark-to-market, unrealized P&L = NA; execution prices only', 'TP-03 per-parent window id (not published)', 'the decision/rationale for any order (never observable from fills)'],
                can_conclude=['the fills, parents, times and quantities listed, and the lifecycle they imply', f'the position ended {E["terminal_status"]} with remaining {rem} (observed)', 'which closing parents are time-connected within 10 s (C1/C2), as a temporal fact'],
                cannot_conclude=['why any order was placed or closed', 'that a candidate wing/body is the protective counterpart of this position', 'which opening lot a closing portion consumed (convention-dependent)', 'that a position lacked a wing merely because it is outside the role-specific analysis'])
