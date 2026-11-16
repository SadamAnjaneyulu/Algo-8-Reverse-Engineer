"""Writes the human-readable walkthroughs (state before and after every action) and the compact validation report.
  python3 tools/make_examples.py <out_dir>        -> walkthrough_<scenario>.txt, validation_report.tsv, run_<scenario>/ (the seven output files)
The scenario definitions themselves live only in scenarios/ (python -m pc.cli generate scenarios); they are not copied here."""
import csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'python'))
from pc import generators as G
from pc.engine import Simulation

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)


def table(sim, key):
    h, *r = [l.split('\t') for l in sim.files()[key].split('\n') if l and not l.startswith('#')]; return [dict(zip(h, x)) for x in r]


def walkthrough(name, sc, sim):
    dec, act, st = table(sim, 'decisions.tsv'), table(sim, 'actions.tsv'), table(sim, 'states.tsv'); base = G.BASE
    L = [f'WALKTHROUGH {name}  [SYNTHETIC_TEST_ONLY - an illustration of the machinery, not an assertion about Algo 8]', sc.description, '',
         'Units are option units (one NIFTY lot = 65). Prices are in paise (rupees x 100). t+N = N seconds after basket creation.', '']
    cfgs = [f'  {p}.{k} = {v}' for p in sorted(sc.configs) for k, v in sorted(sc.configs[p].items())] + [f'  risk.{k} = {v}' for k, v in sorted(sc.risk.items())]
    L += ['CONFIGURED BY THE USER (not decided by any plugin; every other setting keeps the default in the plugin CONFIG_SPEC):'] + (cfgs or ['  (defaults)']) + ['']
    seeds = [r for r in st if r['action_id'] == 'SEED']
    L += ['Step 0  t+0   BASKET CREATED (seed fills applied through the historical engine's ledger)']
    last = {}
    for r in seeds: last[(r['basket_id'], r['leg_id'])] = r
    for (b, l), r in sorted(last.items()): L += [f'        {b}:{l:<4} {"short" if r["leg_side"] == "-1" else "long "} {r["qty_after"]:>4} units   ({r["instrument_id"]})']
    g = seeds[-1]; L += [f'        ledger gross={g["gross_units"]} short={g["short_units"]}', '']
    times = sorted({int(d['ts']) for d in dec if int(d['ts']) > base} | {int(a['ts']) for a in act}); step = 0
    for t in times:
        step += 1; L.append(f'Step {step}  t+{t - base}')
        for d in dec:
            if int(d['ts']) == t: L.append(f'        plugin {d["plugin"]}: {d["outcome"]} {d["reason"]} {d["basket_id"]}:{d["leg_id"]} ({d["detail"]})')
        for a in act:
            if int(a['ts']) != t: continue
            rows = [r for r in st if r['action_id'] == a['action_id']]
            L.append(f'        action {a["type"]} {a["basket_id"]}:{a["leg_id"]} qty {a["qty"]}  -> {a["status"]}' + (f' ({a["reason"]}: {a["detail"]})' if a['status'] == 'REJECTED' else f'  fill {a["fill_id"]} {"BUY" if a["fill_side"] == "1" else "SELL"} {a["qty"]} @ {int(a["fill_price_paise"]) / 100:.2f}'))
            t_ = [r for r in rows if r['leg_id'] == a['leg_id']][0]; legs = ', '.join(f'{r["leg_id"]} {r["qty_before"]}->{r["qty_after"]}' for r in rows)
            L += [f'            state before/after: {legs}', f'            basket {t_["basket_status"]}; ledger {a["leg_id"]} inventory {t_["instrument_inventory"]}; gross={t_["gross_units"]} short={t_["short_units"]}' + ('  (unchanged: rejected)' if a['status'] == 'REJECTED' else '')]
        L.append('')
    L += ['What this shows: the cut and the re-entry are new explicit fills; no historical fill was changed. The rules are configured examples, not Algo 8 rules.']
    return '\n'.join(L) + '\n'


rows = [('scenario', 'purpose', 'accepted', 'rejected_by_risk_validation', 'not_proposed_by_plugin', 'example_accepted_action', 'example_rejected_action', 'rejection_reason', 'data_origin')]
for name, sc in G.all_scenarios().items():
    sim = Simulation(sc).run(); act, dec = table(sim, 'actions.tsv'), table(sim, 'decisions.tsv')
    sim.write(os.path.join(OUT, 'run_' + name))
    if name in ('s05_reentry_success', 's06_reentry_rejected_cooldown', 's07_reentry_rejected_risk_limit', 's11_basket_lifecycle_demo'): open(os.path.join(OUT, f'walkthrough_{name}.txt'), 'w', newline='\n').write(walkthrough(name, sc, sim))
    ok = next((a for a in act if a['status'] == 'ACCEPTED'), None); bad = next((a for a in act if a['status'] == 'REJECTED'), None)
    fmt = lambda a: f'{a["type"]} {a["basket_id"]}:{a["leg_id"]} qty {a["qty"]}' if a else ''
    rows.append((name, sc.description, sum(a['status'] == 'ACCEPTED' for a in act), sum(a['status'] == 'REJECTED' for a in act), sum(d['outcome'] == 'NOT_PROPOSED' for d in dec), fmt(ok), fmt(bad), (bad['reason'] + ': ' + bad['detail']) if bad else '', 'synthetic simulation (scenarios/' + name + '.scn); not historical Algo 8 data'))
with open(os.path.join(OUT, 'validation_report.tsv'), 'w', newline='') as f: w = csv.writer(f, delimiter='\t', lineterminator='\n'); w.writerows(rows)
print('wrote', len(rows) - 1, 'scenarios to', OUT)
