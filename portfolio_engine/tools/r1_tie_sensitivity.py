"""R1 sensitivity report: how much do the reconstruction results depend on the intra-second fill-order CONVENTION?
Runs the PRODUCTION pipeline (LineageSet -> closing batches -> wing/body) under every approved policy over the full ledger and compares each with SOURCE_ROW_ORDER_CONVENTION.
Policies other than source_row are SENSITIVITY-ONLY. Nothing here writes into delivered outputs: results go to reports/r1_tie_order/.
The six populations are reported SEPARATELY (never conflated): (1) groups whose order differs, (2) groups that change opening/closing allocation, (3) episodes/instruments that change identity,
(4) closing-batch membership, (5) wing/body membership, (6) FIFO/LIFO lot attribution of closing fills.  python3 portfolio_engine/tools/r1_tie_sensitivity.py [policy ...]"""
import collections, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tie_policy as tp, closing_batches as cb, wing_body as wb, provenance
from pe.lineage_set import LineageSet
from pe.replay import order_events
from pe.generators import historical as H
OUT = os.path.join(PE, 'reports', 'r1_tie_order'); os.makedirs(OUT, exist_ok=True)
POLICIES = ['source_row', 'sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_trade_id_time']
args = [a for a in sys.argv[1:] if a in tp.POLICIES] or POLICIES
OUT_NAME = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--out=')), 'r1_tie_order_sensitivity.json')      # a scenario run writes its own file; the R1 five-policy result is never overwritten
ins, fills, src = H.generate(REPO); fills.sort(key=lambda f: f.source_row_id)
G = collections.defaultdict(list)
for f in fills: G[(f.instrument_id, f.timestamp_s)].append(f)
G = {k: v for k, v in G.items() if len(v) > 1}                       # same-instrument, same-second groups with >= 2 fills


def run(policy):
    f2 = H.attach_tie_keys(REPO, fills, policy); eo = tp.engine_order(policy); ls = LineageSet(f2, ins, 'HISTORICAL_OBSERVED_REPLAY', eo)
    rank = {f.fill_id: i for i, f in enumerate(order_events(f2, eo))}
    parents, _, _ = cb.closing_parents(ls); views = cb.all_views(parents)
    part = {f'{k[0]}@{k[1]}s': frozenset(frozenset(m.parent_id for m in b['members']) for b in v['batches']) for k, v in views.items()}
    meta = {r['parent_order_id']: r for r in H.generate_parents(REPO, ls.roles)}; R = wb.analyse(ls, meta, 'TAGGED')
    split = {}
    for r in ls.oa.values(): split.setdefault(r[2], [0, 0])[1] += r[8]
    for r in ls.cp.values(): split.setdefault(r[2], [0, 0])[0] += r[8]
    rows = {}
    for r in ls.oa.values(): rows.setdefault(r[5], set()).add(r[11])
    sigs = {eid: ((e['direction'], e['opened'], e['closed'], e['ended_by'], bool(e['started_by_reversal']), e['n_open_fills'], e['n_close_fills']), frozenset(rows.get(eid, ()))) for eid, e in ls.episodes.items()}
    last = {}
    for e in ls.events: last[ls.episodes[e[1]]['instrument_id']] = e[8]
    ca = {c: {} for c in ('FIFO', 'LIFO')}
    for c in ca:
        for r in ls.ca[c]: ca[c].setdefault(r[2], []).append((r[3], r[4]))
    ca_seq = {c: {k: tuple(v) for k, v in d.items()} for c, d in ca.items()}                            # consumption SEQUENCE (order in which lots were consumed)
    ca = {c: {k: tuple(sorted(v)) for k, v in d.items()} for c, d in ca.items()}                          # lot SET with quantities (order ignored)
    return dict(ls=ls, ca=ca, ca_seq=ca_seq, rank=rank, part=part, items={i.item_id for i in R.items}, links={m: {l['link_id'] for l in v} for m, v in R.links.items()}, split={k: tuple(v) for k, v in split.items()}, sigs=sigs, final=last,
                oa=sum(r[8] for r in ls.oa.values()), cp=sum(r[8] for r in ls.cp.values()), body={lv: sum(i.qty for i in R.items if i.level == lv and i.role == 'BODY') for lv in ('OPENING', 'CLOSING')}, wing={lv: sum(i.qty for i in R.items if i.level == lv and i.role == 'WING') for lv in ('OPENING', 'CLOSING')})


def compare(base, alt):
    res = {}; mixed = lambda g: len({f.side for f in g}) > 1
    differ = [g for g in G.values() if [f.fill_id for f in g] != [f.fill_id for f in sorted(g, key=lambda f: alt['rank'][f.fill_id])]]
    changed_fills = {k for k in set(base['split']) | set(alt['split']) if base['split'].get(k) != alt['split'].get(k)}
    split_groups = [g for g in G.values() if any(f.fill_id in changed_fills for f in g)]
    chg_eps = [e for e in set(base['sigs']) | set(alt['sigs']) if base['sigs'].get(e) != alt['sigs'].get(e)]
    res['1_groups_differing_in_order'] = dict(multi_fill_groups=len(G), differing=len(differ), differing_mixed_side=sum(1 for g in differ if mixed(g)), differing_same_side=sum(1 for g in differ if not mixed(g)))
    res['2_groups_changing_open_close_allocation'] = dict(groups=len(split_groups), mixed_side=sum(1 for g in split_groups if mixed(g)), same_side=sum(1 for g in split_groups if not mixed(g)), fills_changed=len(changed_fills),
                                                           fill_rows=sorted(int(k[1:]) for k in changed_fills), groups_detail=[dict(instrument=g[0].instrument_id, ts=g[0].timestamp_s, rows=[f.source_row_id for f in g], sides=''.join('B' if f.side > 0 else 'S' for f in g)) for g in split_groups])
    csig = lambda X: {(e.rsplit('#', 1)[0],) + v for e, v in X['sigs'].items()}
    res['3_episode_identity'] = dict(episodes_changed=len(chg_eps), episodes_changed_definition='ordinal episode id (instrument#n) whose signature differs', episodes_changed_by_content=len(csig(base) - csig(alt)), episodes_changed_by_content_definition='baseline episodes whose (instrument, direction, opened, closed, ended_by, reversal, n_open_fills, n_close_fills, opening-fill set) is absent under the alternative', instruments_changed=len({e.rsplit('#', 1)[0] for e in chg_eps}), instruments=sorted({e.rsplit('#', 1)[0] for e in chg_eps}),
                                     reversal_episodes_base=sum(1 for e in base['ls'].episodes.values() if e['ended_by'] == 'reversal'), reversal_episodes_alt=sum(1 for e in alt['ls'].episodes.values() if e['ended_by'] == 'reversal'))
    bt = {}; bparents = set()
    for k in base['part']:
        gone = base['part'][k] - alt['part'][k]; new = alt['part'][k] - base['part'][k]; bt[k] = dict(baseline_batches=len(base['part'][k]), baseline_batches_not_in_alternative=len(gone), alternative_batches_not_in_baseline=len(new), parents_in_changed_batches=sum(len(p) for p in gone))
        for p in gone | new: bparents |= set(p)
    res['4_closing_batch_membership'] = bt
    chg_items = base['items'] ^ alt['items']; chg_links = {m: base['links'][m] ^ alt['links'][m] for m in base['links']}
    wparents = {x.split(':', 4)[3] for x in chg_items}
    for m, S in chg_links.items():                                                  # link ids: WB:<m>:<level>:<wing item id>-><body item id>; parent ids appear inside the item ids
        for l in S:
            for part in l.split('->'):
                if 'WBI:' in part: wparents.add(part[part.index('WBI:'):].split(':', 4)[3])
    res['5_wing_body_membership'] = dict(items_only_in_one=len(chg_items), links_changed={m: len(S) for m, S in chg_links.items()}, links_baseline={m: len(v) for m, v in base['links'].items()},
                                         opening_body_units=alt['body']['OPENING'], closing_body_units=alt['body']['CLOSING'], opening_wing_units=alt['wing']['OPENING'], closing_wing_units=alt['wing']['CLOSING'])
    sp_par = {f.parent_order_id for g in split_groups for f in g if f.fill_id in changed_fills}
    res['attribution'] = dict(split_changing_groups_whose_parents_appear_in_changed_batches=sum(1 for g in split_groups if {f.parent_order_id for f in g if f.fill_id in changed_fills} & bparents),
                              split_changing_groups_whose_parents_appear_in_changed_wing_body_items_or_links=sum(1 for g in split_groups if {f.parent_order_id for f in g if f.fill_id in changed_fills} & wparents),
                              note='attribution by shared parent order id between the changed-split fills and the changed batch / item / link members; an upper bound on direct causation')
    res['6_lot_attribution'] = {c: dict(closing_fills_compared=len(base['ca'][c]), closing_fills_with_changed_source_lots=sum(1 for k in set(base['ca'][c]) | set(alt['ca'][c]) if base['ca'][c].get(k) != alt['ca'][c].get(k)),
                                        closing_fills_with_changed_consumption_sequence=sum(1 for k in set(base['ca_seq'][c]) | set(alt['ca_seq'][c]) if base['ca_seq'][c].get(k) != alt['ca_seq'][c].get(k))) for c in ('FIFO', 'LIFO')}
    res['6_lot_attribution']['note'] = 'FIFO/LIFO closing allocation: which opening lots a closing fill consumed (analytical layer; AVG is pooled and NOT_IDENTIFIABLE). Counted per closing portion id. `changed_source_lots` compares the set of (opening lot, quantity) pairs; `changed_consumption_sequence` also compares the order in which lots were consumed.'
    res['invariants'] = dict(opening_units=alt['oa'], closing_units=alt['cp'], opening_units_equal=alt['oa'] == base['oa'], closing_units_equal=alt['cp'] == base['cp'], final_inventory_equal=alt['final'] == base['final'])
    return res


out = {'convention': tp.SOURCE_ROW_ORDER_CONVENTION, 'statement': 'deterministic source-row convention, NOT verified intra-second execution chronology', 'source_hashes': src, 'generated_at_head': provenance.git_sha(REPO),
       'policies': {}, 'note_realized_pnl': 'realized P&L deltas are reported by the independent exact-arithmetic reference (reports/m2f_audit/r1/independent_tie_sensitivity_result.json), not by this tool'}
t0 = time.time(); base = run('source_row'); print('source_row', round(time.time() - t0), 's', flush=True)
for p in args:
    if p == 'source_row': continue
    alt = run(p); out['policies'][p] = dict(convention=tp.convention_id(p), sensitivity_only=True, **compare(base, alt)); r = out['policies'][p]
    print(p, round(time.time() - t0), 's | groups differing', r['1_groups_differing_in_order']['differing'], '| split groups', r['2_groups_changing_open_close_allocation']['groups'], '| episodes', r['3_episode_identity']['episodes_changed'],
          '| C1@10 changed', r['4_closing_batch_membership']['C1@10s']['baseline_batches_not_in_alternative'], '| W1 links', r['5_wing_body_membership']['links_changed']['W1'], flush=True)
json.dump(out, open(os.path.join(OUT, OUT_NAME), 'w'), indent=1, sort_keys=True)
