"""Track E: stable-identifier audit on the committed outputs (read-only) and on the engine with shuffled input order. usage: id_audit.py <scratch tree root> (engine run from scratch tree; committed files read from <root>/portfolio_engine/reports)
[INV] uniqueness / [REPRO] order invariance. Does not prove ids are semantically right."""
import gzip, os, sys, json, random, collections, hashlib
root = sys.argv[1]; PE = os.path.join(root, 'portfolio_engine'); sys.path.insert(0, os.path.join(PE, 'python'))
from pe.lineage_set import LineageSet
from pe import closing_batches as cb
from pe.generators import historical as H
out = {}
ins, fills, src = H.generate(root); BAD = ('\t', '\n', '\r')
def has_bad(s): return any(c in s for c in BAD)
out['fill_ids'] = dict(n=len(fills), unique=len({f.fill_id for f in fills}) == len(fills), source_rows_unique=len({f.source_row_id for f in fills}) == len(fills), fill_id_is_F_plus_6digit_of_source_row=all(f.fill_id == f'F{f.source_row_id:06d}' for f in fills),
                       max_source_row=max(f.source_row_id for f in fills), fill_id_width_overflow=max(f.source_row_id for f in fills) >= 10**6)
pids = {f.parent_order_id for f in fills}
out['parent_ids'] = dict(n=len(pids), with_colon=sum(':' in p for p in pids), with_pipe=sum('|' in p for p in pids), with_tab_or_newline=sum(has_bad(p) for p in pids), empty_or_NA=sum(p in ('', 'NA', 'None', 'nan') for p in pids), sample=sorted(pids)[:3], types={type(f.parent_order_id).__name__ for f in fills[:50]} and sorted({type(f.parent_order_id).__name__ for f in fills}))
out['text_fields_with_tab_nl'] = sum(has_bad(str(x)) for f in fills for x in (f.parent_order_id, f.module_tag, f.instrument_id, f.evidence_source))
ls = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')
def files_hash(L): return {m: {n: hashlib.sha256(t.encode()).hexdigest()[:16] for n, t in L.files[m].items()} for m in L.files}
base = files_hash(ls); inv = {}
for seed in (1, 2, 3):
    r = random.Random(seed); sh = list(fills); r.shuffle(sh); L2 = LineageSet(sh, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); inv[f'shuffle_seed{seed}'] = files_hash(L2) == base
rev = list(reversed(fills)); inv['reversed_input'] = files_hash(LineageSet(rev, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src')) == base
out['lineage_files_invariant_under_input_reordering'] = inv
ids = collections.Counter(); 
for r in ls.events: ids[r[0]] += 1
out['lifecycle_event_id_dupes'] = sum(1 for v in ids.values() if v > 1)
out['oa_cp_id_dupes'] = len(list(ls.oa)) + len(list(ls.cp)) - len(set(ls.oa) | set(ls.cp))
parents, unattr, multi = cb.closing_parents(ls); views = cb.all_views(parents)
out['batch_ids'] = {f'{m}_{g}': dict(n=len(v['batches']), unique=len({b['batch_id'] for b in v['batches']}) == len(v['batches'])) for (m, g), v in views.items()}
out['batch_id_global_unique_across_views'] = len({b['batch_id'] for v in views.values() for b in v['batches']}) == sum(len(v['batches']) for v in views.values())
R = os.path.join(PE, 'reports')
for d, files in (('m2d_data', ['wing_body_links_W1', 'wing_body_links_W1_S60', 'wing_body_links_W2', 'wing_body_links_W2_S60', 'wing_body_links_W3', 'wing_body_items']),):
    for n in files:
        rows = gzip.open(os.path.join(R, d, n + '.tsv.gz')).read().decode().split('\n')[1:-1]; key = [r.split('\t')[0] for r in rows]; c = collections.Counter(key)
        out[f'm2d.{n}'] = dict(rows=len(rows), distinct_ids=len(c), duplicate_ids=sum(1 for v in c.values() if v > 1), max_multiplicity=max(c.values()))
json.dump(out, open(sys.argv[2], 'w'), indent=1, default=str); print(json.dumps(out, indent=1, default=str)[:3500])
