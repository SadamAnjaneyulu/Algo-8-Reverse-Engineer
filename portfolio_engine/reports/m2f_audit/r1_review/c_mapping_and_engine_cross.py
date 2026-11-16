"""Task C/A cross-check: (1) every engine Fill vs raw row (source_row_id mapping), (2) attach_tie_keys keys vs raw, (3) engine roles (open/close split) vs reviewer replay per policy. pe.* used ONLY to load engine outputs."""
import sys, json, time, collections
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
import rv_replay as R
from pe.generators import historical as H
from pe import replay as rp
from pe.schema import *
repo = '/home/user/Algo-8-Reverse-Engineer'
ins, fills = H.generate(repo)[:2]
F = R.load(); out = {}
mism = collections.Counter(); ex = []
seen = set()
for f in fills:
    r = F[f.source_row_id]; seen.add(f.source_row_id)
    chk = dict(iid=f.instrument_id == r['iid'], ts=f.timestamp_s == r['ep'], side=f.side == r['side'], qty=f.quantity == r['qty'], px=f.price_paise == r['px'], parent=f.parent_order_id == r['pid'])
    for k, v in chk.items():
        if not v: mism[k] += 1; ex.append((f.source_row_id, k))
out['fills'] = len(fills); out['distinct_source_rows'] = len(seen); out['rows_not_covered'] = len(F) - len(seen); out['mismatch_counts'] = dict(mism); out['examples'] = ex[:10]
out['all_dup_flags'] = sum(f.is_duplicate_fill for f in fills)
out['source_row_is_unique_and_in_range'] = len(seen) == len(fills) and min(seen) == 0 and max(seen) == len(F) - 1
# attach_tie_keys
for pol in ('trade_id', 'order_no', 'sensex_trade_id_time'):
    t = time.time(); kf = H.attach_tie_keys(repo, fills, pol); bad = 0
    for f in kf:
        r = F[f.source_row_id]
        if pol == 'trade_id': exp = R.tid_key(r)
        elif pol == 'order_no': exp = (r['ono'],)
        else: exp = (R.sensex_ns(r),)
        if r['und'] != 'SENSEX' and pol == 'sensex_trade_id_time': exp = (0,)
        if f.tie_key != exp: bad += 1
    out[f'attach_{pol}_key_mismatch'] = bad
    out[f'attach_{pol}_types'] = sorted({type(x).__name__ for f in kf for x in f.tie_key}); out[f'attach_{pol}_lens'] = sorted({len(f.tie_key) for f in kf})
# engine roles vs reviewer replay
eng = {}
for pol in ('source_row', 'sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_trade_id_time'):
    fk = H.attach_tie_keys(repo, fills, pol)
    res = rp.replay(fk, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', pol, lineage=False)
    rv = R.replay(F, 'sensex_ns' if pol == 'sensex_trade_id_time' else pol)
    sp = {int(r.fill_id[1:]): (r.open_qty, r.close_qty) for r in res.roles}
    diff = [k for k in rv['split'] if sp.get(k) != rv['split'][k]]
    ep_open = res.state.opened; ep_close = res.state.closed
    eng[pol] = dict(roles=len(res.roles), split_disagree_with_reviewer=len(diff), engine_open=ep_open, engine_close=ep_close, engine_realized=res.state.realized_total(), reviewer_realized=sum(rv['realized'].values()),
                    engine_episodes=len(res.state.episodes), reviewer_episodes=sum(len(v) for v in rv['episodes'].values()), dump_tie_order=res.meta['tie_order'])
out['engine_vs_reviewer'] = eng
json.dump(out, open('c_mapping_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
