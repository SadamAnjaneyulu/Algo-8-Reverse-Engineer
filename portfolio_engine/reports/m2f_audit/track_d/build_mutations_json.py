"""Turns mutations_raw.json (harness output) into mutations.json (id, change, expected_detector, existing_tests_caught, own_check_caught, detector_independent, notes) and a markdown table."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); R = {r['id']: r for r in json.load(open(os.path.join(HERE, 'mutations_raw.json')))}
EXP = {'m01': ('V3 cohort CSV == aggregation of opening_items by (session, order-entry minute) and tag role', 'recompute from datasets (existing) / raw items (own)'),
 'm02': ('V1 CSV FILL rows == number of fills', ''), 'm03': ('V2 CSV events == lifecycle events', ''), 'm04': ('V3 CSV tag_role == tag/side rule', ''), 'm05': ('V4 CSV row == m2c batch row (duration)', ''), 'm06': ('V5 units: unmatched + 1 + >=2 == observed total, and vs candidate sets', ''), 'm07': ('V6 section G == m2d_summary / raw full-ledger numbers', ''),
 'm08': ('V1 d_label == IST session ordinal', ''), 'm09': ('V1 short_* unsigned == raw signed replay', ''), 'm10': ('fills.tsv exec price == raw col 137 (not col 18)', ''), 'm11': ('PNG footer states execution-price-only / marks missing (text inside PNG)', 'none exists in CSV domain'), 'm12': ('case record parents == raw per-episode parents', ''),
 'm13': ('lifecycle event qty == raw replay', ''), 'm14': ('episode n_parents == distinct parents of its OA/CP', ''), 'm15': ('coverage.json fills == raw counts', ''), 'm16': ('session_carry == last-fill state', ''), 'm17': ('V5 dt_s histogram == binned slice link dt', ''), 'm18': ('M2-C slice batch qty == portions sum == raw closing units', ''), 'm19': ('opening_items avg price paise == notional/qty', ''),
 'm20': ('case figure CSV events == lifecycle events of charted episodes', ''), 'm21': ('V2 CSV inventory_after == lifecycle table', ''), 'm00': ('(control) nothing should fail', '')}
out = []; rows = []
for mid in sorted(R):
    r = R[mid]; own = r['own']; ownfail = {k: v['failed'] for k, v in own.items()}; crash = [k for k, v in own.items() if v['failed'] is None]
    own_caught = any((v['failed'] or 0) > 0 for v in own.values()); pt = r['pytest']; ex_caught = pt['rc'] != 0
    note = f"pytest: {pt['summary'][-110:]}; first failure: {(pt['first_failure'] or [''])[0][:160]}; own failed counts {ownfail}" + (f"; CRASH (not a kill) in {crash}" if crash else '')
    if mid in ('m11',): indep = 'n/a: no detector in either suite reads PNG text'
    elif mid == 'm00': indep = 'n/a (control)'
    else: indep = 'own: yes (raw ledger, no pe imports); existing: ' + ('partly (re-derives via production engine, not through the mutated file)' if ex_caught else 'n/a (not detected)')
    out.append(dict(id=mid.upper().replace('M', 'M-D-'), change=r['change'], expected_detector=EXP[mid][0], existing_tests_caught=ex_caught, own_check_caught=own_caught, detector_independent=indep, notes=note))
    rows.append((mid, r['change'], 'killed' if ex_caught else 'SURVIVED', 'killed' if own_caught else 'SURVIVED'))
json.dump(out, open(os.path.join(HERE, 'mutations.json'), 'w'), indent=1)
print('| id | change | existing tests | Track D checks |\n|---|---|---|---|'); [print('| %s | %s | %s | %s |' % r) for r in rows]
