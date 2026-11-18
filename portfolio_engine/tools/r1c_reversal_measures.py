"""Decision B: both reversal measures (never merged) for the full ledger and the two frozen cycles under the baseline and the hybrid ordering, with the exact source rows.
python3 portfolio_engine/tools/r1c_reversal_measures.py  -> reports/r1c_dual_scenario/reversal_measures.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import replay as rp, reversals as RV, tie_policy as tp
from pe.generators import historical as H
ins, fills, src = H.generate(REPO)
cycles = {'full_ledger': None, 'NIFTY_2026-06-30': {i for i, x in ins.items() if x.underlying == 'NIFTY' and x.expiry == '2026-06-30'}, 'SENSEX_2026-07-16': {i for i, x in ins.items() if x.underlying == 'SENSEX' and x.expiry == '2026-07-16'}}
out = dict(definitions={RV.PER_FILL: 'one fill changes the instrument inventory from one non-zero sign to the opposite non-zero sign',
                        RV.PARENT_LEVEL: 'for one (instrument, parent, second): inventory before the parent\'s first fill and after its last fill have opposite non-zero signs (diagnostic; not a broker-designated reversal; not a subset or superset of the per-fill measure)'},
           statement='Neither ordering is verified chronology. The measures are conditional on the same-instrument same-second order.', source_hashes=src, results={})
for name, sub in cycles.items():
    out['results'][name] = {}
    for sc in ('baseline', 'per_contract_id_sequence'):
        pol = tp.PRIMARY_POLICY if sc == 'baseline' else sc; f2 = [f for f in H.attach_tie_keys(REPO, fills, pol) if sub is None or f.instrument_id in sub]
        r = RV.from_fills(rp.order_events(f2, tp.engine_order(pol)))
        out['results'][name][sc] = dict(counts=r['counts'], sentence=RV.sentence(r['counts'][RV.PER_FILL], r['counts'][RV.PARENT_LEVEL], name.replace('_', ' ')), per_fill=r['per_fill'],
                                        parent_level=[{k: v for k, v in g.items()} for g in r['parent_level']], parent_level_without_a_per_fill_event=sum(1 for g in r['parent_level'] if not any(p['parent_order_id'] == g['parent_order_id'] and p['timestamp_s'] == g['timestamp_s'] and p['instrument_id'] == g['instrument_id'] for p in r['per_fill'])),
                                        per_fill_without_a_parent_level_flip=sum(1 for p in r['per_fill'] if not any(g['parent_order_id'] == p['parent_order_id'] and g['timestamp_s'] == p['timestamp_s'] and g['instrument_id'] == p['instrument_id'] for g in r['parent_level'])))
        print(name, sc, r['counts'], flush=True)
os.makedirs(os.path.join(PE, 'reports', 'r1c_dual_scenario'), exist_ok=True)
json.dump(out, open(os.path.join(PE, 'reports', 'r1c_dual_scenario', 'reversal_measures.json'), 'w'), indent=1, sort_keys=True)
