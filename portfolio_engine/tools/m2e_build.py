"""M2-E dataset assembly for the two frozen cycles (NIFTY 2026-06-30, SENSEX 2026-07-16). Read-only on M1/M2-B/M2-C/M2-D; never writes outside reports/m2e_data.
python3 portfolio_engine/tools/m2e_build.py  -> reports/m2e_data/<UND>_<expiry>/*.tsv, coverage.json, manifest.json ; reports/m2e_data/m2e_summary.json"""
import hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import forensics as F, provenance, wing_body as wb
from pe.lineage_set import LineageSet
from pe.generators import historical as H
OUT = os.path.join(PE, 'reports', 'm2e_data'); os.makedirs(OUT, exist_ok=True)
ins_all, fills_all, src = H.generate(REPO); full = LineageSet(fills_all, ins_all, 'HISTORICAL_OBSERVED_REPLAY', 'src')       # full-ledger run, used ONLY to check cycle isolation
S = dict(cycles={}, source_hashes=src, generated_at_head=provenance.git_sha(REPO), version=F.VERSION)
for und, exp in F.CYCLES:
    c = F.Cycle(REPO, und, exp); d = os.path.join(OUT, c.key); os.makedirs(d, exist_ok=True)
    # ---- cycle isolation: cycle-only lineage == full-ledger lineage restricted to the cycle's instruments
    inst = set(c.ins); ev_full = [e for e in full.events if full.episodes[e[1]]['instrument_id'] in inst]
    assert ev_full == list(c.ls.events), 'cycle-only lifecycle events differ from full-ledger run'
    assert {k: v for k, v in full.episodes.items() if v['instrument_id'] in inst} == c.ls.episodes, 'episodes differ'
    assert {k: v for k, v in full.oa.items() if v[4] in inst} == c.ls.oa and {k: v for k, v in full.cp.items() if v[4] in inst} == c.ls.cp, 'OA/CP differ'
    rec = F.reconcile_observed(c)
    # ---- canonical M2-C / M2-D slices must equal a per-cycle recomputation with the committed engines
    sc = F.m2c_slice(REPO, c); sd = F.m2d_slice(REPO, c); files_c, R, rm = F.recompute_m2c_m2d(c)
    for n, t in files_c.items(): assert sc[n] == t, f'M2-C slice != recomputation: {n}'
    items_re = {i.item_id: (i.qty, i.first_ts, i.role, i.level) for i in R.items}; _, items_c = F.read_tsv_text(sd['wing_body_items.tsv'])
    assert items_re == {r['item_id']: (int(r['qty']), int(r['first_ts']), r['role'], r['level']) for r in items_c}, 'M2-D items differ'
    for m, links in R.links.items():
        _, lc = F.read_tsv_text(sd[f'wing_body_links_{m}.tsv'])
        assert [(l['link_id'], l['dt_s'], l['wing_qty'], l['body_qty']) for l in links] == [(r['link_id'], int(r['dt_s']), int(r['wing_qty']), int(r['body_qty'])) for r in lc] or sorted((l['link_id'], l['dt_s'], l['wing_qty'], l['body_qty']) for l in links) == sorted((r['link_id'], int(r['dt_s']), int(r['wing_qty']), int(r['body_qty'])) for r in lc), f'M2-D links differ: {m}'
    cls, wh, wr = F.tp03_overlay(REPO, c)
    tables = {'fills.tsv': F.fills_table(c), 'inventory_series.tsv': F.inventory_series(c), 'session_carry.tsv': F.session_carry(c), 'lifecycle_events.tsv': F.lifecycle_table(c), 'episodes.tsv': F.episodes_table(c), 'opening_items.tsv': F.opening_items(c, cls), 'tp03_windows.tsv': (wh, wr)}
    texts = {n: F.tsv(*t) for n, t in tables.items()}; texts.update({f'm2c_{n}': t for n, t in sc.items()}); texts.update({f'm2d_{n}': t for n, t in sd.items()})
    cov = F.cycle_coverage(c, sc, sd, R, rm); cov['reconciliation'] = rec; cov['cycle_isolation'] = 'cycle-only lineage identical to full-ledger lineage restricted to the cycle (events, episodes, OA, CP)'
    cov['m2c_m2d_vs_recomputation'] = 'IDENTICAL (M2-C 6 files byte-equal; M2-D items and all 5 link views equal)'
    cov['tp03_overlay'] = dict(parents_listed_off_window_or_initial=len(cls), note='TP-03 publishes window rows and per-parent OFF_WINDOW/INITIAL classes for body-short parents only; no per-parent window id; unlisted parents are NOT claimed to be in a window')
    man = dict(cycle=f'{c.und}|{c.expiry}', version=F.VERSION, generated_at_head=provenance.git_sha(REPO), execution_mode='HISTORICAL_OBSERVED_REPLAY', source_hashes=src, timezone='timestamps *_utc_s are UTC epoch seconds; *_ist columns are IST = UTC+05:30', files={}, reproduce='python3 portfolio_engine/tools/m2e_build.py')
    for n, t in texts.items():
        open(os.path.join(d, n), 'w').write(t); man['files'][n] = dict(sha256=F.sha(t), rows=t.count('\n') - 1, bytes=len(t.encode()))
    json.dump(cov, open(os.path.join(d, 'coverage.json'), 'w'), indent=1, default=str); json.dump(man, open(os.path.join(d, 'manifest.json'), 'w'), indent=1)
    S['cycles'][c.key] = dict(fills=cov['fills']['raw_fill_count'], parents=cov['fills']['unique_parent_orders'], episodes=cov['episodes']['episode_count'], reconciliation=rec)
    print(c.key, S['cycles'][c.key])
json.dump(S, open(os.path.join(OUT, 'm2e_summary.json'), 'w'), indent=1, default=str)
