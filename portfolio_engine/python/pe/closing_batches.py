"""Model C closing-batch associations (M2-C): C1 first-fill chaining and C2 last-to-first chaining. ANALYTICAL ONLY: reads the observed layer (closing portions) and never changes it.
A batch groups the closing parent orders of one (underlying, expiry, session) that execute close together. It says nothing about how the positions were opened and nothing about the original decision.
Unit = parent order, represented by its CLOSING portions only (opening executions of a mixed parent never contribute). Whole-second timestamps; link rule is `gap <= threshold` (inclusive).
Determinism: parents are ordered by (first closing-fill ts, smallest closing source_row_id, parent_order_id); chaining is single-linkage over ADJACENT parents in that order."""
import hashlib, json
from collections import defaultdict
from .schema import *

THRESHOLDS = (2, 5, 10, 30, 60)
PRIMARY = 10
METHODS_CB = {'C1': ('CB_FIRST_FILL_GAP', 'first_to_first'), 'C2': ('CB_LAST_TO_FIRST_GAP', 'last_to_first')}
GROUPING_VERSION = 'CB1'


class ParentClose:
    __slots__ = ('parent_id', 'und', 'expiry', 'session', 'first_ts', 'last_ts', 'first_src', 'cps', 'qty')
    def __init__(self, parent_id, und, expiry, session): self.parent_id = parent_id; self.und = und; self.expiry = expiry; self.session = session; self.cps = []; self.qty = 0; self.first_ts = None; self.last_ts = None; self.first_src = None
    @property
    def stream(self): return (self.und, self.expiry, self.session)
    @property
    def key(self): return (self.parent_id,) + self.stream


def closing_parents(ls):
    """ParentClose records from the observed layer of a LineageSet. Returns (parents, unattributable_cp_ids, multi_stream_parents). A closing portion without a parent id is NEVER pooled into a pseudo-parent."""
    ins = ls.instruments; d = {}; unattr = []; streams = defaultdict(set)
    for cp_id in sorted(ls.cp, key=lambda k: (ls.cp[k][6], ls.cp[k][11], k)):
        r = ls.cp[cp_id]; pid = r[3]
        if pid is None or pid == '' or pid == 'NA': unattr.append(cp_id); continue
        i = ins[r[4]]; sess = day_iso(ist_day(r[6])); k = (pid, i.underlying, i.expiry, sess); p = d.get(k)
        if p is None: p = d[k] = ParentClose(pid, i.underlying, i.expiry, sess)
        p.cps.append(r); p.qty += r[8]; streams[pid].add(k[1:])
        if p.first_ts is None or r[6] < p.first_ts: p.first_ts = r[6]
        if p.last_ts is None or r[6] > p.last_ts: p.last_ts = r[6]
        if p.first_src is None or r[11] < p.first_src: p.first_src = r[11]
    return list(d.values()), unattr, sorted(pid for pid, s in streams.items() if len(s) > 1)


def param_hash(method, g):
    return hashlib.sha256(json.dumps(dict(version=GROUPING_VERSION, method=method, threshold_s=g, boundaries=['underlying', 'expiry', 'session(IST date)'], unit='parent order (closing portions only)', order='first_ts,first_src,parent_id',
                                          link='gap<=threshold (inclusive), adjacent parents, single linkage', precision='whole seconds'), sort_keys=True).encode()).hexdigest()[:16]


def build_view(parents, method, g):
    """one analytical view: list of batches; each batch = dict(batch_id, members=[ParentClose...], links=[(gap, overlap)...]). C1 gap = first(next) - first(prev); C2 gap = first(next) - last(prev)."""
    token = METHODS_CB[method][0] + f'_{g}S'; streams = defaultdict(list)
    for p in parents: streams[p.stream].append(p)
    batches = []
    for stream in sorted(streams):
        ps = sorted(streams[stream], key=lambda p: (p.first_ts, p.first_src, p.parent_id)); cur = None; n = 0
        for prev, p in zip([None] + ps[:-1], ps):
            if prev is None: link = None
            else:
                gap = p.first_ts - (prev.first_ts if method == 'C1' else prev.last_ts); link = (gap, p.first_ts <= prev.last_ts, p.first_ts < prev.last_ts) if gap <= g else None      # (gap, closed-interval overlap incl. same-second touching, strict overlap)
            if link is None:
                n += 1; cur = dict(batch_id=f'INF:CLOSING_BATCH@{token}:{stream[0]}:{stream[1]}:{stream[2]}:{n:03d}', members=[p], links=[], stream=stream, token=token); batches.append(cur)
            else: cur['members'].append(p); cur['links'].append(link)
    return dict(method=method, threshold_s=g, token=token, batches=batches, parameter_hash=param_hash(method, g))


def all_views(parents):
    return {(m, g): build_view(parents, m, g) for m in ('C1', 'C2') for g in THRESHOLDS}


# ----------------------------------------------------------------------------- invariants (partition + reconciliation); raise InvariantViolation
def check_view(view, parents, cps, unattributable=()):
    seen_parent = set(); seen_cp = set(); total = 0; ids = set()
    by_key = {p.key: p for p in parents}
    for b in view['batches']:
        if b['batch_id'] in ids: raise InvariantViolation(f'duplicate batch id {b["batch_id"]}')
        ids.add(b['batch_id'])
        for p in b['members']:
            if p.key in seen_parent: raise InvariantViolation(f'parent {p.key} in two batches of one view')
            seen_parent.add(p.key)
            if p.stream != b['stream']: raise InvariantViolation('member from another (underlying, expiry, session)')
            if not p.cps: raise InvariantViolation(f'parent {p.parent_id} has no closing portion (opening-only parents are not eligible)')
            for r in p.cps:
                if r[0] != 'CP' or r[1] in seen_cp: raise InvariantViolation(f'closing portion {r[1]} missing / duplicated in one view')
                if cps[r[1]] != r: raise InvariantViolation(f'closing portion {r[1]} differs from the observed layer')
                seen_cp.add(r[1]); total += r[8]
    if seen_parent != set(by_key): raise InvariantViolation('eligible parents not represented exactly once')
    if seen_cp | set(unattributable) != set(cps) or seen_cp & set(unattributable): raise InvariantViolation('closing portions not represented exactly once (batched + unattributable != all)')
    if total + sum(cps[c][8] for c in unattributable) != sum(r[8] for r in cps.values()): raise InvariantViolation('closing quantity does not reconcile')
    return True


def link_pairs(view):
    """set of (stream, previous parent key, next parent key) adjacent pairs that are LINKED in the view (for comparing views)"""
    out = set()
    for b in view['batches']:
        for a, c in zip(b['members'], b['members'][1:]): out.add((a.key, c.key))
    return out


def member_sets(view): return {frozenset(p.key for p in b['members']) for b in view['batches']}


# ----------------------------------------------------------------------------- batch records and files
def role_of(r, ls):
    ep = ls.episodes[r[5]]; d = 'SHORT' if ep['direction'] == -1 else 'LONG'
    return {('SHORT', 'num'): 'SHORT_BODY', ('LONG', 'h_'): 'LONG_WING', ('LONG', 'num'): 'LONG_BODY', ('SHORT', 's_'): 'STOP_SHORT'}.get((d, r[10]), f'OTHER_{d}_{r[10]}')


def batch_record(b, view, ls):
    ps = b['members']; cps = [r for p in ps for r in p.cps]; ins = ls.instruments; ce = [r for r in cps if ins[r[4]].option_type == 'CE']; pe = [r for r in cps if ins[r[4]].option_type == 'PE']
    roles = defaultdict(int)
    for r in cps: roles[role_of(r, ls)] += r[8]
    start = min(p.first_ts for p in ps); end = max(p.last_ts for p in ps); gaps = [l[0] for l in b['links']]
    buy = sum(r[8] for r in cps if r[7] == 1); sell = sum(r[8] for r in cps if r[7] == -1)
    short_closed = sum(r[8] for r in cps if ls.episodes[r[5]]['direction'] == -1); long_closed = sum(r[8] for r in cps if ls.episodes[r[5]]['direction'] == 1)
    return dict(batch_id=b['batch_id'], grouping_method=view['method'], threshold_s=view['threshold_s'], underlying=b['stream'][0], expiry=b['stream'][1], session=b['stream'][2], n_parents=len(ps), n_closing_portions=len(cps), total_closing_qty=sum(r[8] for r in cps),
                n_contracts=len({r[4] for r in cps}), contracts=','.join(sorted({f'{ins[r[4]].option_type}{ins[r[4]].strike}' for r in cps})), n_cp_CE=len(ce), n_cp_PE=len(pe), qty_CE=sum(r[8] for r in ce), qty_PE=sum(r[8] for r in pe),
                right_class='MIXED' if ce and pe else ('CE_ONLY' if ce else 'PE_ONLY'), buy_qty=buy, sell_qty=sell, short_closed_qty=short_closed, long_closed_qty=long_closed, roles=';'.join(f'{k}:{v}' for k, v in sorted(roles.items())),
                start_ts=start, end_ts=end, duration_s=end - start, n_links=len(b['links']), max_link_gap_s=max(gaps) if gaps else 0, n_overlap_links=sum(1 for l in b['links'] if l[1]), n_strict_overlap_links=sum(1 for l in b['links'] if l[2]), has_interval_overlap=int(any(l[1] for l in b['links'])),
                membership_provenance='INFERRED:CLOSING_BATCH', grouping_convention=b['token'], grouping_version=GROUPING_VERSION, parameter_hash=view['parameter_hash'], evidence_class='CONFIRMED_OBSERVATION (temporal clustering); batch = decision unit UNRESOLVED', claim_type='OBSERVATION')


BATCH_COLUMNS = ['batch_id', 'grouping_method', 'threshold_s', 'underlying', 'expiry', 'session', 'n_parents', 'n_closing_portions', 'total_closing_qty', 'n_contracts', 'contracts', 'n_cp_CE', 'n_cp_PE', 'qty_CE', 'qty_PE', 'right_class', 'buy_qty', 'sell_qty',
                 'short_closed_qty', 'long_closed_qty', 'roles', 'start_ts', 'end_ts', 'duration_s', 'n_links', 'max_link_gap_s', 'n_overlap_links', 'n_strict_overlap_links', 'has_interval_overlap', 'membership_provenance', 'grouping_convention', 'grouping_version', 'parameter_hash', 'evidence_class', 'claim_type']


def files_for_method(views, method, ls):
    """batches / parent members / closing-portion members as TSV text for ONE method (all its thresholds); C1 and C2 are never mixed in a file"""
    B = ['\t'.join(BATCH_COLUMNS)]; Mm = ['batch_id\tgrouping_convention\tthreshold_s\tparent_order_id\tparent_first_closing_ts\tparent_last_closing_ts\tn_closing_portions\tclosing_qty\tjoin_gap_s\tinterval_overlap\tstrict_overlap\tcp_ids']
    Pp = ['batch_id\tgrouping_convention\tthreshold_s\tcp_id\tfill_id\tparent_order_id\tinstrument_id\toption_type\tstrike\tclosing_side\tclosed_direction\tquantity\ttimestamp_s\tmodule_tag\trole\tsource_row_id']
    ins = ls.instruments
    for (m, g), v in sorted(views.items()):
        if m != method: continue
        for b in v['batches']:
            B.append('\t'.join(str(batch_record(b, v, ls)[c]) for c in BATCH_COLUMNS))
            for i, p in enumerate(b['members']):
                lk = b['links'][i - 1] if i else None
                Mm.append('\t'.join(str(x) for x in (b['batch_id'], b['token'], g, p.parent_id, p.first_ts, p.last_ts, len(p.cps), p.qty, '' if lk is None else lk[0], '' if lk is None else int(lk[1]), '' if lk is None else int(lk[2]), ','.join(r[1] for r in p.cps))))
                for r in p.cps: Pp.append('\t'.join(str(x) for x in (b['batch_id'], b['token'], g, r[1], r[2], r[3], r[4], ins[r[4]].option_type, ins[r[4]].strike, 'BUY' if r[7] == 1 else 'SELL', 'SHORT' if ls.episodes[r[5]]['direction'] == -1 else 'LONG', r[8], r[6], r[10], role_of(r, ls), r[11])))
    return {f'closing_batches_{method}.tsv': '\n'.join(B) + '\n', f'closing_batch_members_{method}.tsv': '\n'.join(Mm) + '\n', f'closing_batch_portions_{method}.tsv': '\n'.join(Pp) + '\n'}


# ----------------------------------------------------------------------------- analytical reporting (descriptive; larger is NOT better)
def _dist(xs):
    xs = sorted(xs)
    if not xs: return dict(n=0)
    q = lambda f: xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
    return dict(n=len(xs), min=xs[0], median=q(0.5), mean=round(sum(xs) / len(xs), 3), p90=q(0.9), p99=q(0.99), max=xs[-1])


def summarize(views, parents, ls):
    rows = []
    adj = defaultdict(list)
    for p in parents: adj[p.stream].append(p)
    pairs = []
    for s, ps in adj.items():
        ps.sort(key=lambda p: (p.first_ts, p.first_src, p.parent_id)); pairs += list(zip(ps, ps[1:]))
    for (m, g), v in sorted(views.items()):
        sizes = [len(b['members']) for b in v['batches']]; dur = [max(p.last_ts for p in b['members']) - min(p.first_ts for p in b['members']) for b in v['batches']]; cpn = [sum(len(p.cps) for p in b['members']) for b in v['batches']]
        gaps = [(b.first_ts - a.first_ts) if m == 'C1' else (b.first_ts - a.last_ts) for a, b in pairs]
        rows.append(dict(method=m, threshold_s=g, batches=len(v['batches']), parents=sum(sizes), closing_portions=sum(cpn), singleton_batches=sum(1 for s in sizes if s == 1), size=_dist(sizes), duration_s=_dist(dur), max_duration_over_threshold=(max(dur) / g) if dur else 0,
                         adjacent_pairs=len(pairs), pairs_linked=sum(1 for x in gaps if x <= g), pairs_gap_exactly_threshold=sum(1 for x in gaps if x == g), pairs_gap_threshold_plus_1s=sum(1 for x in gaps if x == g + 1), pairs_equal_first_ts=sum(1 for a, b in pairs if a.first_ts == b.first_ts),
                         overlap_links=sum(1 for b in v['batches'] for l in b['links'] if l[1]), strict_overlap_links=sum(1 for b in v['batches'] for l in b['links'] if l[2]), batches_with_overlap=sum(1 for b in v['batches'] if any(l[1] for l in b['links']))))
    return rows


def stability(views):
    """membership stability across thresholds (per method) and C1 vs C2 (per threshold)"""
    out = {'across_thresholds': [], 'c1_vs_c2': []}
    for m in ('C1', 'C2'):
        for a, b in zip(THRESHOLDS, THRESHOLDS[1:]):
            sa, sb = member_sets(views[(m, a)]), member_sets(views[(m, b)]); out['across_thresholds'].append(dict(method=m, from_s=a, to_s=b, batches_from=len(sa), batches_to=len(sb), identical_batches=len(sa & sb), nested=all(any(x <= y for y in sb) for x in sa)))
    for g in THRESHOLDS:
        s1, s2 = member_sets(views[('C1', g)]), member_sets(views[('C2', g)]); l1, l2 = link_pairs(views[('C1', g)]), link_pairs(views[('C2', g)])
        out['c1_vs_c2'].append(dict(threshold_s=g, c1_batches=len(s1), c2_batches=len(s2), identical_batches=len(s1 & s2), links_only_c1=len(l1 - l2), links_only_c2=len(l2 - l1), links_both=len(l1 & l2), c1_nested_in_c2=all(any(x <= y for y in s2) for x in s1)))
    return out
