"""Task C engine edge cases (executed): (1) sensex policy lineage files vs primary (global event order effect), (2) keys attached under policy A replayed under policy B, (3) order_events('source_row') direct, (4) mixed None keys, (5) dump bytes for source_row. pe used as the object under test."""
import sys, hashlib, json
sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/portfolio_engine/python')
from pe.generators import historical as H
from pe import replay as rp
from pe.schema import *
import dataclasses as dc
repo = '/home/user/Algo-8-Reverse-Engineer'
ins, fills = H.generate(repo)[:2]; out = {}
h = lambda d: {k: hashlib.sha256(v.encode()).hexdigest() for k, v in d.items()}
base = rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'src', lineage=True)
sx = rp.replay(H.attach_tie_keys(repo, fills, 'sensex_trade_id_time'), ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'sensex_trade_id_time', lineage=True)
hb, hs = h(rp.lineage_files(base)), h(rp.lineage_files(sx))
out['sensex_policy_lineage_files_identical_to_primary'] = {k: hb[k] == hs[k] for k in hb}
out['sensex_policy_dump_identical_except_tie_order_meta'] = base.dump.replace('tie_order\tsrc', 'tie_order\tX') == sx.dump.replace('tie_order\tsensex_trade_id_time', 'tie_order\tX')
out['sensex_policy_roles_identical'] = rp.roles_tsv(base.roles) == rp.roles_tsv(sx.roles)
# NIFTY-before-SENSEX placement inside a second under sensex policy
o = rp.order_events(H.attach_tie_keys(repo, fills, 'sensex_trade_id_time'), 'sensex_trade_id_time'); ob = rp.order_events(fills, 'src')
out['sensex_policy_global_event_sequence_differs_from_primary'] = [f.fill_id for f in o] != [f.fill_id for f in ob]
out['sensex_policy_global_positions_moved'] = sum(1 for a, b in zip(o, ob) if a.fill_id != b.fill_id)
# keys from policy A replayed under policy B
fa = H.attach_tie_keys(repo, fills, 'trade_id')
r_ab = rp.replay(fa, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'order_no'); r_bb = rp.replay(H.attach_tie_keys(repo, fills, 'order_no'), ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'order_no')
out['trade_id_keys_replayed_as_order_no_accepted_silently'] = True
out['  ...and the result equals true order_no replay'] = r_ab.dump == r_bb.dump
out['  ...dump tie_order meta says'] = [l for l in r_ab.dump.splitlines() if l.startswith('META\ttie_order')][0]
fa2 = rp.replay(fa, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'trade_id')
out['  ...(order_no-labelled run with trade_id keys) equals true trade_id replay'] = r_ab.dump.replace('tie_order\torder_no', 'tie_order\ttrade_id') == fa2.dump
# order_events direct with alias
try: rp.order_events(fills, 'source_row'); out['order_events(source_row)'] = 'accepted'
except Exception as e: out['order_events(source_row)'] = f'{type(e).__name__}: {e}'
# partial None keys
half = [dc.replace(f, tie_key=(1,)) if i % 2 else f for i, f in enumerate(fills)]
try: rp.replay(half, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'trade_id'); out['partial_None_keys'] = 'accepted'
except Exception as e: out['partial_None_keys'] = f'{type(e).__name__}: {str(e)[:80]}'
# a policy-agnostic sensitivity name with fills lacking keys
try: rp.replay(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'order_no'); out['no_keys'] = 'accepted'
except Exception as e: out['no_keys'] = f'{type(e).__name__}: {str(e)[:60]}'
# equal keys fall back to source row: all keys equal => same as src
eq = [dc.replace(f, tie_key=(7,)) for f in fills]
out['all_equal_keys_equals_primary_dump_modulo_label'] = rp.replay(eq, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'trade_id').dump.replace('tie_order\ttrade_id', 'tie_order\tsrc') == base.dump
# input shuffled: primary order must not depend on input order
import random
sh = list(fills); random.Random(1).shuffle(sh)
out['primary_dump_independent_of_input_order(except INPUT_NOT_TIME_ORDERED warn)'] = rp.replay(sh, ins, 'HISTORICAL_OBSERVED_REPLAY', 'FIFO', 'src').dump.replace('INPUT_NOT_TIME_ORDERED\t' , 'X\t').split('WARN')[0] == base.dump.replace('INPUT_NOT_TIME_ORDERED\t', 'X\t').split('WARN')[0]
json.dump(out, open('c_engine_edge_result.json', 'w'), indent=1); print(json.dumps(out, indent=1))
