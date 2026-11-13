"""M2-D: wing / body association analysis on the REAL ledger (HISTORICAL_OBSERVED_REPLAY). Writes deterministic gzip TSVs, manifest and summary. Analytical only: the observed layer is checked unchanged.
python3 portfolio_engine/tools/m2d_wing_body.py -> reports/m2d_data/"""
import gzip, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); REPO = os.path.dirname(PE); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.schema import *
from pe.lineage_set import LineageSet
from pe import wing_body as wb, provenance
from pe.generators import historical as H
OUT = os.path.join(PE, 'reports', 'm2d_data'); os.makedirs(OUT, exist_ok=True)
ins, fills, src = H.generate(REPO); ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
h0 = hashlib.sha256(''.join(ls.files['FIFO'][n] for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv')).encode()).hexdigest()
rows = H.generate_parents(REPO, ls.roles); meta = {r['parent_order_id']: r for r in rows}
R = wb.analyse(ls, meta, 'TAGGED'); passed = wb.check(R, ls); RD = wb.analyse(ls, meta, 'DIRECTION'); wb.check(RD, ls)
h1 = hashlib.sha256(''.join(ls.files['FIFO'][n] for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv')).encode()).hexdigest(); assert h0 == h1       # associations never touch the observed layer
S = dict(source_hashes=src, invariants_passed=passed, items=len(R.items), links={m: len(v) for m, v in R.links.items()}, w4_number_block='NOT_IMPLEMENTED (number-block semantics UNRESOLVED; not implemented without new evidence or stakeholder confirmation)',
         missing_entry_minute={l: len(v) for l, v in R.no_entry_minute.items()}, observed_layer_hash=h0[:16])
S['coverage'] = {f'{lv}|{m}': wb.coverage(R, lv, m) for lv in wb.LEVELS for m in ('W1', 'W1_S60') + (('W3',) if lv == 'OPENING' else ())}
S['coverage_direction_scope_sensitivity'] = {f'{lv}|{m}': {k: v for k, v in wb.coverage(RD, lv, m).items() if k in ('wing_items', 'body_items', 'wing_units', 'body_units', 'wing_items_with_candidate', 'wing_items_no_candidate', 'wing_units_unmatched', 'body_units_without_wing', 'links')} for lv in wb.LEVELS for m in ('W1', 'W1_S60')}
S['group_level_observed_ratio'] = wb.group_level_ratios(R); S['method_disagreements_opening'] = wb.disagreements(R, 'OPENING'); S['method_disagreements_closing_W1_vs_S60'] = {k: v for k, v in wb.disagreements(R, 'CLOSING').items() if k.startswith('W1')}
S['coverage_by_app_key_W1_opening'] = wb.coverage_split(R, 'W1', 'app_key'); S['coverage_by_app_key_S60_opening'] = wb.coverage_split(R, 'W1_S60', 'app_key'); S['coverage_by_underlying_W1_opening'] = wb.coverage_split(R, 'W1', 'und'); S['coverage_by_day_type_W1_opening'] = wb.coverage_split(R, 'W1', 'day_type')
S['wing_items_by_app_key'] = {k: v['wing_items'] for k, v in S['coverage_by_app_key_W1_opening'].items()}; S['wing_unit_share_second_app_key'] = round(sum(v['wing_units'] for k, v in S['coverage_by_app_key_W1_opening'].items() if k != '632469') / sum(v['wing_units'] for v in S['coverage_by_app_key_W1_opening'].values()), 4)
# link-level extras: otm distance sign, px ratio <= 0.025 (descriptive only), W1 links whose entry minutes equal / W1_S60 links outside the primary set
l1 = [l for l in R.links['W1'] if l['level'] == 'OPENING']; l60 = [l for l in R.links['W1_S60'] if l['level'] == 'OPENING']
S['descriptive_link_properties_opening'] = dict(W1_links=len(l1), W1_share_otm_distance_positive=round(sum(1 for l in l1 if l['otm_distance'] > 0) / len(l1), 4), W1_share_px_ratio_le_0_05=round(sum(1 for l in l1 if l['px_ratio'] <= 0.05) / len(l1), 4), W1_share_dt_abs_le_5s=round(sum(1 for l in l1 if abs(l['dt_s']) <= 5) / len(l1), 4),
                                                W1_S60_links=len(l60), W1_S60_share_in_primary_set=round(sum(l['in_primary_candidate_set'] for l in l60) / len(l60), 4), W1_S60_share_wing_before_body=round(sum(1 for l in l60 if l['dt_s'] < 0) / len(l60), 4))
files = {}
COLS = ['link_id', 'method', 'level', 'wing_item', 'body_item', 'wing_parent', 'body_parent', 'underlying', 'expiry', 'right', 'session', 'wing_first_ts', 'body_first_ts', 'dt_s', 'same_entry_minute', 'wing_qty', 'body_qty', 'qty_ratio', 'weight', 'allocated_wing_units', 'segment', 'wing_strike', 'body_strike', 'otm_distance',
        'wing_avg_px_paise', 'body_avg_px_paise', 'px_ratio', 'wing_app_key', 'body_app_key', 'n_candidates_for_wing', 'n_wings_for_body', 'link_status', 'nearest', 'nearest_tied', 'in_primary_candidate_set', 'membership_provenance', 'evidence_class', 'protective_link', 'claim_type']
for m, links in R.links.items():
    files[f'wing_body_links_{m}.tsv'] = '\n'.join(['\t'.join(COLS)] + ['\t'.join(str(l.get(c, '')) for c in COLS) for l in links]) + '\n'
IC = ['item_id', 'level', 'role', 'parent_order_id', 'instrument_id', 'underlying', 'expiry', 'right', 'strike', 'session', 'first_ts', 'last_ts', 'qty', 'avg_px_paise', 'n_members', 'entry_minute_s', 'app_key_last6', 'module_tag', 'W1_candidates', 'W1_S60_candidates']
c1 = {}; c60 = {}
for l in R.links['W1']: c1[(l['wing_item'] if True else 0)] = c1.get(l['wing_item'], 0) + 1; c1[l['body_item']] = c1.get(l['body_item'], 0) + 1
for l in R.links['W1_S60']: c60[l['wing_item']] = c60.get(l['wing_item'], 0) + 1; c60[l['body_item']] = c60.get(l['body_item'], 0) + 1
files['wing_body_items.tsv'] = '\n'.join(['\t'.join(IC)] + ['\t'.join(str(x) for x in (i.item_id, i.level, i.role, i.parent_id, i.instrument_id, i.und, i.expiry, i.right, i.strike, i.session, i.first_ts, i.last_ts, i.qty, round(i.avg_px, 4), len(i.members), 'NA' if i.e_minute is None else i.e_minute, i.app_key or 'NA', i.module, c1.get(i.item_id, 0), c60.get(i.item_id, 0))) for i in R.items]) + '\n'
man = dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), generated_at_head=provenance.git_sha(REPO), execution_mode='HISTORICAL_OBSERVED_REPLAY', source_hashes=src, scope='TAGGED primary (DIRECTION scope reported as summary sensitivity only)', files={}, reproduce='python3 portfolio_engine/tools/m2d_wing_body.py')
for name, text in files.items():
    path = os.path.join(OUT, name + '.gz')
    with open(path, 'wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as z: z.write(text.encode())
    man['files'][name + '.gz'] = dict(sha256_of_text=hashlib.sha256(text.encode()).hexdigest(), rows=text.count('\n') - 1, bytes_gz=os.path.getsize(path))
json.dump(man, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1); json.dump(S, open(os.path.join(OUT, 'm2d_summary.json'), 'w'), indent=1, default=str)
print(json.dumps({k: v for k, v in S.items() if k in ('items', 'links', 'missing_entry_minute', 'wing_items_by_app_key', 'wing_unit_share_second_app_key', 'method_disagreements_opening', 'descriptive_link_properties_opening')}, indent=1)); print(sum(v['bytes_gz'] for v in man['files'].values()) / 1e6, 'MB gz')
