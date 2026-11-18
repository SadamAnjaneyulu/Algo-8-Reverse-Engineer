"""Task A: reviewer's independent reproduction of the R1 sensitivity populations 1-3, invariants, FIFO delta. Output a_sensitivity_result.json"""
import json, collections
import rv_replay as R
F = R.load(); byrow = {f['row']: f for f in F}
base = R.replay(F, 'source_row'); G = R.groups(F)
res = {'n_fills': len(F), 'multi_fill_groups': len(G), 'mixed_side_groups': sum(1 for v in G.values() if len({f['side'] for f in v}) == 2),
       'base': dict(open=base['tot_open'], close=base['tot_close'], episodes=sum(len(v) for v in base['episodes'].values()), reversal_fills=len(base['rev_rows']),
                    reversal_ended_episodes=sum(1 for v in base['episodes'].values() for e in v if e['end'] == 'REVERSAL'), realized_paise=sum(base['realized'].values()))}
bsig = {iid: {R.ep_sig(e) for e in v} for iid, v in base['episodes'].items()}
res['policies'] = {}
for pol in ('sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_ns'):
    alt = R.replay(F, pol); r = {}
    # population 1: groups whose order differs
    k = R.POLICIES[pol]; differ = []; 
    for (iid, ep), v in G.items():
        so = [f['row'] for f in sorted(v, key=lambda f: f['row'])]
        ao = [f['row'] for f in sorted(v, key=lambda f: (k(f), f['row']))]
        if so != ao: differ.append(((iid, ep), v))
    r['p1_groups_order_differs'] = len(differ)
    r['p1_mixed'] = sum(1 for _, v in differ if len({f['side'] for f in v}) == 2)
    r['p1_same_side'] = r['p1_groups_order_differs'] - r['p1_mixed']
    # population 2
    ch = sorted(row for row in base['split'] if base['split'][row] != alt['split'][row])
    r['p2_fills_split_changed'] = ch
    gch = collections.OrderedDict()
    for row in ch:
        f = byrow[row]; gch.setdefault((f['iid'], f['ep']), []).append(row)
    r['p2_groups'] = [dict(instrument=a, ts=b, changed_rows=v, group_rows=[f['row'] for f in G[(a, b)]], sides=''.join('B' if f['side'] > 0 else 'S' for f in G[(a, b)])) for (a, b), v in gch.items()]
    r['p2_groups_n'] = len(gch); r['p2_mixed'] = sum(1 for (a, b) in gch if len({f['side'] for f in G[(a, b)]}) == 2); r['p2_same_side'] = len(gch) - r['p2_mixed']
    # population 3 (strict signature = direction, set of (row,open,close) pieces, end)
    asig = {iid: {R.ep_sig(e) for e in v} for iid, v in alt['episodes'].items()}
    changed_inst = sorted(i for i in bsig if bsig[i] != asig[i])
    r['p3_instruments_changed'] = changed_inst
    r['p3_episodes_in_base_not_alt'] = sum(len(bsig[i] - asig[i]) for i in changed_inst)
    r['p3_episodes_in_alt_not_base'] = sum(len(asig[i] - bsig[i]) for i in changed_inst)
    # weaker identity: ignore which row (qty/dir/end/n pieces) -> (iid,dir,opened,closed,end,n_open_fills,n_close_fills)
    def weak(e): return (e['iid'], e['dir'], sum(p[1] for p in e['pieces']), sum(p[2] for p in e['pieces']), e['end'], sum(1 for p in e['pieces'] if p[1]), sum(1 for p in e['pieces'] if p[2]))
    wb = {i: collections.Counter(weak(e) for e in v) for i, v in base['episodes'].items()}; wa = {i: collections.Counter(weak(e) for e in v) for i, v in alt['episodes'].items()}
    r['p3_weak_instruments_changed'] = sorted(i for i in wb if wb[i] != wa[i])
    r['p3_weak_episodes_base_not_alt'] = sum(sum((wb[i] - wa[i]).values()) for i in wb)
    # ordinal-id identity (episode id = instrument#ordinal): positions whose record differs + ordinals present on only one side
    def ordcount(i):
        B = [R.ep_sig(e) for e in base['episodes'][i]]; A = [R.ep_sig(e) for e in alt['episodes'][i]]
        n = max(len(A), len(B)); return sum(1 for k in range(n) if (B[k] if k < len(B) else None) != (A[k] if k < len(A) else None))
    r['p3_episodes_changed_by_ordinal_id'] = sum(ordcount(i) for i in changed_inst)
    r['reversal_ended_episodes_base'] = res['base']['reversal_ended_episodes']
    r['reversal_ended_episodes_alt'] = sum(1 for v in alt['episodes'].values() for e in v if e['end'] == 'REVERSAL')
    r['n_episodes_alt'] = sum(len(v) for v in alt['episodes'].values())
    r['tot_open'] = alt['tot_open']; r['tot_close'] = alt['tot_close']; r['units_equal'] = (alt['tot_open'], alt['tot_close']) == (base['tot_open'], base['tot_close'])
    r['final_inventory_equal'] = alt['final'] == base['final']
    r['fifo_realized_delta_paise_total'] = sum(alt['realized'].values()) - sum(base['realized'].values())
    r['fifo_realized_delta_by_instrument'] = {i: alt['realized'][i] - base['realized'][i] for i in base['realized'] if alt['realized'][i] != base['realized'][i]}
    r['p3_changed_reversal_rows_base_vs_alt'] = [sorted(base['rev_rows'] - alt['rev_rows']), sorted(alt['rev_rows'] - base['rev_rows'])]
    res['policies'][pol] = r
json.dump(res, open('a_sensitivity_result.json', 'w'), indent=1)
for p, r in res['policies'].items():
    print(p, {k: (v if not isinstance(v, (list, dict)) else (len(v) if k != 'p2_fills_split_changed' else v)) for k, v in r.items() if k not in ('p2_groups',)})
    for g in r['p2_groups']: print('   ', g)
print(res['base'], res['mixed_side_groups'])
