"""[IMPL] on [RAW]: same-second tie-order dependency. Orders: src, reversed_src, buys_first, sells_first, random (5 seeds).
Measures, relative to src order: instruments whose episode structure changes, episodes changing identity (episode signature = instrument, ordinal, direction, opened, closed, ended_by, set of opening rows),
fills whose open/close split changes, CP/OA membership changes, closing-allocation (FIFO/LIFO) changes, realized P&L deltas (paise), and which quantities stay invariant."""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import ref_model as RM
from collections import defaultdict
rows=RM.load_raw()
G=defaultdict(list)
for r in rows: G[(r['inst'],r['ts'])].append(r)
multi=[g for g in G.values() if len(g)>1]
out=dict(instrument_second_groups_gt1=len(multi), groups_mixed_side=sum(1 for g in multi if len({x['side'] for x in g})>1),
         groups_same_side_diff_price=sum(1 for g in multi if len({x['side'] for x in g})==1 and len({x['px'] for x in g})>1),
         instruments_in_groups_gt1=len({g[0]['inst'] for g in multi}), instruments_in_mixed_groups=len({g[0]['inst'] for g in multi if len({x['side'] for x in g})>1}),
         parents_with_multiple_fills_same_second=len([1 for g in multi if len({x['parent'] for x in g})==1]))
def sig(R):
    eps={e['id']:(e['dir'],e['opened'],e['closed'],e['ended_by'],e['rev'],e['n_open'],e['n_close']) for e in R.episodes.values()}
    eps_rows={eid:frozenset(r for r,o in R.oa.items() if o['ep']==eid) for eid in R.episodes}
    return eps,eps_rows
base={m:RM.replay_ref(RM.order_fills(rows,'src'),m) for m in ('FIFO','LIFO','AVG')}
bs={m:sig(base[m]) for m in base}
res={}
variants=[('reversed_src',0),('buys_first',0),('sells_first',0)]+[('random',s) for s in range(5)]
for tie,seed in variants:
    ordered=RM.order_fills(rows,tie,seed); key=f'{tie}{seed if tie=="random" else ""}'; res[key]={}
    for m in ('FIFO','LIFO','AVG'):
        R=RM.replay_ref(ordered,m); B=base[m]; e,er=sig(R); be,ber=bs[m]
        inst_chg=set()
        for eid in set(e)|set(be):
            if e.get(eid)!=be.get(eid) or er.get(eid)!=ber.get(eid): inst_chg.add(eid.split('#')[0])
        ep_ident=sum(1 for eid in set(e)|set(be) if e.get(eid)!=be.get(eid) or er.get(eid)!=ber.get(eid))
        ep_struct=sum(1 for eid in set(e)|set(be) if e.get(eid)!=be.get(eid))   # excluding which-fill-opened
        fills_split=sum(1 for r in B.fills if (B.fills[r]['close'],B.fills[r]['open'])!=(R.fills[r]['close'],R.fills[r]['open']))
        fills_ep=sum(1 for r in B.fills if (B.fills[r]['ep_close'],B.fills[r]['ep_open'])!=(R.fills[r]['ep_close'],R.fills[r]['ep_open']))
        oa_members=len(set(B.oa)^set(R.oa)); cp_members=len(set(B.cp)^set(R.cp))
        oa_qty=sum(1 for r in set(B.oa)&set(R.oa) if B.oa[r]['qty']!=R.oa[r]['qty']); cp_qty=sum(1 for r in set(B.cp)&set(R.cp) if B.cp[r]['qty']!=R.cp[r]['qty'])
        oa_ep=sum(1 for r in set(B.oa)&set(R.oa) if B.oa[r]['ep']!=R.oa[r]['ep'])
        cabase={};caR={}
        for x in B.ca: cabase[(x[0],x[1])]=cabase.get((x[0],x[1]),0)+x[2]
        for x in R.ca: caR[(x[0],x[1])]=caR.get((x[0],x[1]),0)+x[2]
        res[key][m]=dict(instruments_changed=len(inst_chg),episodes_identity_changed=ep_ident,episodes_structure_changed=ep_struct,n_episodes=len(R.episodes),fills_open_close_split_changed=fills_split,fills_episode_assignment_changed=fills_ep,
            OA_membership_diff=oa_members,CP_membership_diff=cp_members,OA_qty_diff=oa_qty,CP_qty_diff=cp_qty,OA_episode_diff=oa_ep,CA_pairs_diff=len(set(cabase.items())^set(caR.items())),
            realized_delta_paise=float(R.realized_total-B.realized_total),final_inv_equal=R.final_inv==B.final_inv,OA_total=sum(o['qty'] for o in R.oa.values()),CP_total=sum(c['qty'] for c in R.cp.values()),
            reversal_fills=sum(1 for f in R.fills.values() if f['rev']),cash_equal=R.cash==B.cash)
out['variants']=res
# which mixed-side groups actually change anything under buys/sells first
chg=defaultdict(set)
json.dump(out,open(os.path.join(HERE,'tie_order_result.json'),'w'),indent=1)
print(json.dumps({k:v for k,v in out.items() if k!='variants'},indent=1))
for k,v in res.items():
    print(k); 
    for m,d in v.items(): print('  ',m,{a:b for a,b in d.items() if a not in('n_episodes',)})
