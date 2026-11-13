"""M2-D wing / body association analysis. ANALYTICAL ONLY (Python-only per D5): reads the observed layer (opening allocations, closing portions) and the parent metadata; never changes either.
Every output relationship is INFERRED; no row claims ownership or a protective intent. Many-to-many candidates, unmatched quantities and ambiguity are preserved; nothing is forced one-to-one.
Roles are module-tag ATTRIBUTION only: wing = long item tagged `h_`; body = short item tagged `num` (opening: OA side +1 / -1; closing: closing portions of a LONG / SHORT episode closed by `h_` / `num`).
Unit = parent order x instrument (partial fills of one parent are summed into one item; a parent is never counted as several decisions).
Methods: W1 same underlying+expiry+right+parent ENTRY MINUTE (primary); W1_S60 same underlying+expiry+right+session and |first-fill gap| <= 60 s (sensitivity, execution-time evidence);
W2 / W2_S60 proportional-quantity weights over the W1 / W1_S60 candidates; W3 FIFO queue arithmetic (opening level, no timing claim); W4 number-block = NOT IMPLEMENTED (semantics unresolved); W5 = unmatched / unresolved quantity."""
import bisect
from collections import defaultdict
from .schema import *

LEVELS = ('OPENING', 'CLOSING')
LINK_METHODS = ('W1', 'W1_S60', 'W2', 'W2_S60', 'W3')
S60 = 60
EVIDENCE = {'W1': 'CONFIRMED_OBSERVATION (same underlying, expiry, right and parent entry minute)', 'W1_S60': 'CONFIRMED_OBSERVATION (execution-time proximity <= 60 s; NOT decision-time proximity)',
            'W2': 'CONFIRMED_OBSERVATION of candidates; weights are arithmetic', 'W2_S60': 'CONFIRMED_OBSERVATION of candidates; weights are arithmetic', 'W3': 'ARITHMETIC PAIRING (queue); no timing or ownership claim'}


class Item:
    __slots__ = ('item_id', 'level', 'role', 'parent_id', 'instrument_id', 'und', 'expiry', 'right', 'strike', 'session', 'first_ts', 'last_ts', 'qty', 'px_sum', 'members', 'first_src', 'e_minute', 'app_key', 'module')
    def __init__(self, level, role, parent_id, ins, module):
        self.level = level; self.role = role; self.parent_id = parent_id; self.instrument_id = ins.instrument_id; self.und = ins.underlying; self.expiry = ins.expiry; self.right = ins.option_type; self.strike = ins.strike; self.module = module
        self.item_id = f'WBI:{level}:{role}:{parent_id}:{ins.instrument_id}'; self.qty = 0; self.px_sum = 0; self.members = []; self.first_ts = None; self.last_ts = None; self.first_src = None; self.session = None; self.e_minute = None; self.app_key = None
    @property
    def avg_px(self): return self.px_sum / self.qty
    @property
    def group_key(self): return (self.level, self.und, self.expiry, self.right)


def _meta(parents_meta, pid):
    m = (parents_meta or {}).get(pid) or {}; return m.get('order_entry_minute_s'), (m.get('app_key_last6') if m.get('app_key_last6') else None)


def build_items(ls, parents_meta=None, scope='TAGGED'):
    """items for both levels. scope TAGGED (primary): wing = h_ long, body = num short. scope DIRECTION (sensitivity): wing = any long-side item, body = any short-side item."""
    ins = ls.instruments; items = {}
    def add(level, role, r, module):
        i = ins[r[4]]; it = items.get((level, role, r[3], r[4]))
        if it is None: it = items[(level, role, r[3], r[4])] = Item(level, role, r[3], i, module); it.e_minute, it.app_key = _meta(parents_meta, r[3])
        it.qty += r[8]; it.px_sum += r[8] * r[9]; it.members.append(r[1])
        if it.first_ts is None or r[6] < it.first_ts: it.first_ts = r[6]
        if it.last_ts is None or r[6] > it.last_ts: it.last_ts = r[6]
        if it.first_src is None or r[11] < it.first_src: it.first_src = r[11]
        it.session = day_iso(ist_day(it.first_ts))
    for r in ls.oa.values():
        wing = r[7] == 1 and (r[10] == 'h_' if scope == 'TAGGED' else True); body = r[7] == -1 and (r[10] == 'num' if scope == 'TAGGED' else True)
        if wing: add('OPENING', 'WING', r, r[10])
        elif body: add('OPENING', 'BODY', r, r[10])
    for r in ls.cp.values():
        d = ls.episodes[r[5]]['direction']
        wing = d == 1 and (r[10] == 'h_' if scope == 'TAGGED' else True); body = d == -1 and (r[10] == 'num' if scope == 'TAGGED' else True)
        if wing: add('CLOSING', 'WING', r, r[10])
        elif body: add('CLOSING', 'BODY', r, r[10])
    return sorted(items.values(), key=lambda it: (it.first_ts, it.first_src, it.item_id))


def otm_distance(w, b): return (w.strike - b.strike) if w.right == 'CE' else (b.strike - w.strike)        # > 0: the wing is further out of the money than the body strike


def _link(method, w, b, **extra):
    dt = w.first_ts - b.first_ts
    row = dict(link_id=f'WB:{method}:{w.level}:{w.item_id}->{b.item_id}', method=method, level=w.level, wing_item=w.item_id, body_item=b.item_id, wing_parent=w.parent_id, body_parent=b.parent_id, underlying=w.und, expiry=w.expiry, right=w.right, session=w.session,
               wing_first_ts=w.first_ts, body_first_ts=b.first_ts, dt_s=dt, same_entry_minute=int(w.e_minute is not None and w.e_minute == b.e_minute), wing_qty=w.qty, body_qty=b.qty, qty_ratio=round(w.qty / b.qty, 6),
               wing_strike=w.strike, body_strike=b.strike, otm_distance=otm_distance(w, b), wing_avg_px_paise=round(w.avg_px, 4), body_avg_px_paise=round(b.avg_px, 4), px_ratio=round(w.avg_px / b.avg_px, 6),
               wing_app_key=w.app_key or 'NA', body_app_key=b.app_key or 'NA', membership_provenance=f'INFERRED:WING_BODY:{method}', evidence_class=EVIDENCE[method], protective_link='UNRESOLVED', claim_type='ATTRIBUTION')
    row.update(extra); return row


def _annotate(links, wings_with, bodies_with):
    for l in links:
        l['n_candidates_for_wing'] = wings_with[l['wing_item']]; l['n_wings_for_body'] = bodies_with[l['body_item']]; l['link_status'] = 'UNIQUE_CANDIDATE' if wings_with[l['wing_item']] == 1 else 'MULTIPLE_CANDIDATES'


def candidates_w1(items):
    """W1: all bodies with the same level, underlying, expiry, right and parent entry minute. Wings / bodies without an entry minute cannot be placed (reported in `no_entry_minute`)"""
    idx = defaultdict(list); no_e = []
    for it in items:
        if it.role == 'BODY' and it.e_minute is not None: idx[it.group_key + (it.e_minute,)].append(it)
    links = []
    for w in items:
        if w.role != 'WING': continue
        if w.e_minute is None: no_e.append(w.item_id); continue
        cs = idx.get(w.group_key + (w.e_minute,), [])
        if not cs: continue
        m = min(abs(w.first_ts - b.first_ts) for b in cs); ties = sum(1 for b in cs if abs(w.first_ts - b.first_ts) == m)
        for b in sorted(cs, key=lambda b: (abs(w.first_ts - b.first_ts), b.first_ts, b.first_src, b.item_id)): links.append(_link('W1', w, b, nearest=int(abs(w.first_ts - b.first_ts) == m), nearest_tied=int(ties > 1 and abs(w.first_ts - b.first_ts) == m), in_primary_candidate_set=1))
    return links, no_e


def candidates_s60(items):
    """W1_S60: same level, underlying, expiry, right, session and |first-fill gap| <= 60 s (inclusive). `in_primary_candidate_set` says whether the pair also shares the entry minute"""
    idx = defaultdict(list)
    for it in items:
        if it.role == 'BODY': idx[it.group_key + (it.session,)].append(it)
    for v in idx.values(): v.sort(key=lambda b: (b.first_ts, b.first_src, b.item_id))
    ts = {k: [b.first_ts for b in v] for k, v in idx.items()}; links = []
    for w in items:
        if w.role != 'WING': continue
        k = w.group_key + (w.session,); v = idx.get(k, [])
        if not v: continue
        lo = bisect.bisect_left(ts[k], w.first_ts - S60); hi = bisect.bisect_right(ts[k], w.first_ts + S60); cs = v[lo:hi]
        if not cs: continue
        m = min(abs(w.first_ts - b.first_ts) for b in cs); ties = sum(1 for b in cs if abs(w.first_ts - b.first_ts) == m)
        for b in sorted(cs, key=lambda b: (abs(w.first_ts - b.first_ts), b.first_ts, b.first_src, b.item_id)):
            links.append(_link('W1_S60', w, b, nearest=int(abs(w.first_ts - b.first_ts) == m), nearest_tied=int(ties > 1 and abs(w.first_ts - b.first_ts) == m), in_primary_candidate_set=int(w.e_minute is not None and w.e_minute == b.e_minute)))
    return links


def proportional(base_links, name, items_by_id):
    """W2: spread each wing's units over its candidates in proportion to body units (fractional weights; no integer ownership)"""
    tot = defaultdict(int)
    for l in base_links: tot[l['wing_item']] += l['body_qty']
    out = []
    for l in base_links:
        r = dict(l); r.update(method=name, link_id=l['link_id'].replace(f'WB:{l["method"]}:', f'WB:{name}:', 1), membership_provenance=f'INFERRED:WING_BODY:{name}', evidence_class=EVIDENCE[name], weight=round(l['body_qty'] / tot[l['wing_item']], 9), allocated_wing_units=round(l['wing_qty'] * l['body_qty'] / tot[l['wing_item']], 6)); out.append(r)
    return out


def queue_w3(items):
    """W3: within (underlying, expiry, right, session) at OPENING level, wing units are queue-matched to body units in opening order. Purely arithmetic: no timing, entry-minute or ownership claim."""
    groups = defaultdict(lambda: ([], []))
    for it in items:
        if it.level != 'OPENING': continue
        groups[it.group_key + (it.session,)][0 if it.role == 'WING' else 1].append(it)
    links = []; resid = dict(wing_units_unmatched=0, body_units_unmatched=0)
    for k in sorted(groups):
        ws, bs = groups[k]; ws.sort(key=lambda x: (x.first_ts, x.first_src, x.item_id)); bs.sort(key=lambda x: (x.first_ts, x.first_src, x.item_id)); wi = bi = 0; wl = ws[0].qty if ws else 0; bl = bs[0].qty if bs else 0; seg = 0
        while wi < len(ws) and bi < len(bs):
            u = min(wl, bl); seg += 1
            links.append(_link('W3', ws[wi], bs[bi], allocated_wing_units=u, weight=round(u / ws[wi].qty, 9), segment=seg, nearest=0, nearest_tied=0, in_primary_candidate_set=int(ws[wi].e_minute is not None and ws[wi].e_minute == bs[bi].e_minute)))
            wl -= u; bl -= u
            if wl == 0: wi += 1; wl = ws[wi].qty if wi < len(ws) else 0
            if bl == 0: bi += 1; bl = bs[bi].qty if bi < len(bs) else 0
        resid['wing_units_unmatched'] += (wl + sum(x.qty for x in ws[wi + 1:])) if wi < len(ws) else 0; resid['body_units_unmatched'] += (bl + sum(x.qty for x in bs[bi + 1:])) if bi < len(bs) else 0
    return links, resid


class WingBodyResult:
    pass


def analyse(ls, parents_meta=None, scope='TAGGED'):
    R = WingBodyResult(); R.scope = scope; R.items = build_items(ls, parents_meta, scope); R.by_id = {i.item_id: i for i in R.items}; R.links = {}; R.no_entry_minute = {}
    for level in LEVELS:
        its = [i for i in R.items if i.level == level]; l1, no_e = candidates_w1(its); l60 = candidates_s60(its)
        R.no_entry_minute[level] = no_e
        for name, ls_ in (('W1', l1), ('W1_S60', l60)):
            w = defaultdict(int); b = defaultdict(int)
            for l in ls_: w[l['wing_item']] += 1; b[l['body_item']] += 1
            _annotate(ls_, w, b); R.links.setdefault(name, []).extend(ls_)
            w2 = proportional(ls_, 'W2' if name == 'W1' else 'W2_S60', R.by_id)
            for l in w2: l['n_candidates_for_wing'] = w[l['wing_item']]; l['n_wings_for_body'] = b[l['body_item']]; l['link_status'] = 'UNIQUE_CANDIDATE' if w[l['wing_item']] == 1 else 'MULTIPLE_CANDIDATES'
            R.links.setdefault('W2' if name == 'W1' else 'W2_S60', []).extend(w2)
    l3, R.w3_residual = queue_w3(R.items); w = defaultdict(int); b = defaultdict(int)
    for l in l3: w[l['wing_item']] += 1; b[l['body_item']] += 1
    _annotate(l3, w, b); R.links['W3'] = l3
    return R


# ---------------------------------------------------------------------------- reporting (descriptive; no score, no ranking of methods)
def _dist(xs):
    xs = sorted(xs)
    if not xs: return dict(n=0)
    q = lambda f: xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
    return dict(n=len(xs), min=xs[0], p10=q(0.1), median=q(0.5), p90=q(0.9), max=xs[-1])


def coverage(R, level, method):
    wings = [i for i in R.items if i.level == level and i.role == 'WING']; bodies = [i for i in R.items if i.level == level and i.role == 'BODY']; ls = [l for l in R.links[method] if l['level'] == level]
    wl = defaultdict(int); bl = defaultdict(int)
    for l in ls: wl[l['wing_item']] += 1; bl[l['body_item']] += 1
    wu = sum(i.qty for i in wings); bu = sum(i.qty for i in bodies)
    row = dict(level=level, method=method, wing_items=len(wings), body_items=len(bodies), wing_units=wu, body_units=bu, wing_items_with_candidate=len(wl), wing_items_unique_candidate=sum(1 for v in wl.values() if v == 1), wing_items_multiple_candidates=sum(1 for v in wl.values() if v > 1),
               wing_items_no_candidate=len(wings) - len(wl), wing_units_with_candidate=sum(R.by_id[k].qty for k in wl), wing_units_unmatched=wu - sum(R.by_id[k].qty for k in wl), body_items_with_wing_candidate=len(bl), body_items_without_wing=len(bodies) - len(bl),
               body_units_with_wing_candidate=sum(R.by_id[k].qty for k in bl), body_units_without_wing=bu - sum(R.by_id[k].qty for k in bl), links=len(ls),
               candidates_per_wing=_dist(list(wl.values())), wings_per_body=_dist(list(bl.values())), qty_ratio=_dist([l['qty_ratio'] for l in ls]), dt_s=_dist([l['dt_s'] for l in ls]), abs_dt_s=_dist([abs(l['dt_s']) for l in ls]), otm_distance=_dist([l['otm_distance'] for l in ls]), px_ratio=_dist([l['px_ratio'] for l in ls]),
               nearest_tied_links=sum(l['nearest_tied'] for l in ls) if ls and 'nearest_tied' in ls[0] else None)
    return row


def group_level_ratios(R):
    """OBSERVED relationship at group level (no lot assignment needed): per (level, underlying, expiry, right, parent entry minute): wing units vs body units"""
    g = defaultdict(lambda: [0, 0, 0, 0])
    for i in R.items:
        if i.e_minute is None: continue
        k = i.group_key + (i.e_minute,); a = g[k]
        if i.role == 'WING': a[0] += i.qty; a[2] += 1
        else: a[1] += i.qty; a[3] += 1
    out = {}
    for level in LEVELS:
        both = [v for k, v in g.items() if k[0] == level and v[0] > 0 and v[1] > 0]; wo = [v for k, v in g.items() if k[0] == level and v[0] > 0 and v[1] == 0]; bo = [v for k, v in g.items() if k[0] == level and v[1] > 0 and v[0] == 0]
        r = [v[0] / v[1] for v in both]
        out[level] = dict(groups_with_both=len(both), groups_wing_only=len(wo), groups_body_only=len(bo), wing_units_in_wing_only_groups=sum(v[0] for v in wo), body_units_in_body_only_groups=sum(v[1] for v in bo), ratio=_dist(r), share_ratio_exactly_1=(sum(1 for x in r if x == 1) / len(r)) if r else None,
                          share_ratio_lt_1=(sum(1 for x in r if x < 1) / len(r)) if r else None, share_ratio_gt_1=(sum(1 for x in r if x > 1) / len(r)) if r else None)
    return out


def disagreements(R, level='OPENING'):
    """cases where methods disagree, per wing item: W1 vs W1_S60 nearest body; W1 candidate set vs W3 body; reported as counts, never resolved"""
    def nearest(m):
        d = defaultdict(set)
        for l in R.links[m]:
            if l['level'] == level and l['nearest']: d[l['wing_item']].add(l['body_item'])
        return d
    n1, n60 = nearest('W1'), nearest('W1_S60'); c1 = defaultdict(set); w3 = defaultdict(set)
    for l in R.links['W1']:
        if l['level'] == level: c1[l['wing_item']].add(l['body_item'])
    for l in R.links['W3']:
        if l['level'] == level: w3[l['wing_item']].add(l['body_item'])
    wings = [i.item_id for i in R.items if i.level == level and i.role == 'WING']; cat = defaultdict(int)
    for w in wings:
        a, b = n1.get(w), n60.get(w)
        if not a and not b: cat['W1_none_and_S60_none'] += 1
        elif not a: cat['W1_none_S60_has_candidates'] += 1
        elif not b: cat['W1_has_S60_none'] += 1
        elif a == b: cat['W1_nearest_equals_S60_nearest'] += 1
        else: cat['W1_nearest_differs_from_S60_nearest'] += 1
        if level != 'OPENING': continue                                                  # W3 is defined at the opening level only
        if w in w3 and c1.get(w): cat['W3_body_in_W1_candidates' if w3[w] <= c1[w] else 'W3_body_outside_W1_candidates'] += 1
        elif w in w3: cat['W3_has_body_W1_none'] += 1
        elif c1.get(w): cat['W1_has_candidates_W3_unmatched'] += 1
    return dict(cat)


def coverage_split(R, method, key):
    """wing-side coverage of `method` split by a property of the wing item: 'app_key', 'und', 'day_type'"""
    out = defaultdict(lambda: dict(wing_items=0, wing_items_with_candidate=0, wing_units=0, wing_units_with_candidate=0))
    has = set(l['wing_item'] for l in R.links[method])
    for i in R.items:
        if i.role != 'WING' or i.level != 'OPENING': continue
        k = {'app_key': i.app_key or 'NA', 'und': i.und, 'day_type': 'D0' if i.session == i.expiry else 'PRE_EXPIRY'}[key]; o = out[k]; o['wing_items'] += 1; o['wing_units'] += i.qty
        if i.item_id in has: o['wing_items_with_candidate'] += 1; o['wing_units_with_candidate'] += i.qty
    return {k: dict(v, share_items_with_candidate=round(v['wing_items_with_candidate'] / v['wing_items'], 4)) for k, v in sorted(out.items())}


def brute_force_pairs(items, method):
    """INDEPENDENT reference for W1 / W1_S60 candidate sets: plain double loop inside (level, underlying, expiry, right) groups"""
    g = defaultdict(lambda: ([], []))
    for i in items: g[i.group_key][0 if i.role == 'WING' else 1].append(i)
    out = set()
    for ws, bs in g.values():
        for w in ws:
            for b in bs:
                if method == 'W1': ok = w.e_minute is not None and w.e_minute == b.e_minute
                else: ok = w.session == b.session and abs(w.first_ts - b.first_ts) <= S60
                if ok: out.add((w.item_id, b.item_id))
    return out


def check(R, ls):
    """independent invariants; raises InvariantViolation on the first failure; returns the ids passed"""
    passed = []
    def ok(i, cond, msg=''):
        if not cond: raise InvariantViolation(f'{i}: {msg}')
        if i not in passed: passed.append(i)
    # 1. item conservation vs the observed rows, recomputed from scratch for the role definition of the scope
    tagged = R.scope == 'TAGGED'; want = defaultdict(int)
    for r in ls.oa.values():
        if r[7] == 1 and (r[10] == 'h_' or not tagged): want[('OPENING', 'WING')] += r[8]
        elif r[7] == -1 and (r[10] == 'num' or not tagged): want[('OPENING', 'BODY')] += r[8]
    for r in ls.cp.values():
        d = ls.episodes[r[5]]['direction']
        if d == 1 and (r[10] == 'h_' or not tagged): want[('CLOSING', 'WING')] += r[8]
        elif d == -1 and (r[10] == 'num' or not tagged): want[('CLOSING', 'BODY')] += r[8]
    have = defaultdict(int)
    for i in R.items: have[(i.level, i.role)] += i.qty
    ok('I-items-conserve-units', dict(want) == dict(have), f'{dict(want)} vs {dict(have)}')
    ids = [l['link_id'] for m in R.links.values() for l in m]; ok('I-unique-link-ids', len(ids) == len(set(ids)))
    seen_members = defaultdict(int)
    for i in R.items:
        for m in i.members: seen_members[m] += 1
    ok('I-each-observed-row-in-at-most-one-item', all(v == 1 for v in seen_members.values()))
    for m, links in R.links.items():
        for l in links:
            w = R.by_id[l['wing_item']]; b = R.by_id[l['body_item']]
            ok('I-roles-and-levels', w.role == 'WING' and b.role == 'BODY' and w.level == b.level == l['level'], l['link_id'])
            ok('I-same-underlying-expiry-right', (w.und, w.expiry, w.right) == (b.und, b.expiry, b.right), l['link_id'])
            ok('I-provenance', l['membership_provenance'] == f'INFERRED:WING_BODY:{m}' and l['protective_link'] == 'UNRESOLVED' and 'EXPLICIT' not in str(l['membership_provenance']), l['link_id'])
            if m in ('W1', 'W2'): ok('I-W1-same-entry-minute', w.e_minute is not None and w.e_minute == b.e_minute, l['link_id'])
            if m in ('W1_S60', 'W2_S60'): ok('I-S60-window', w.session == b.session and abs(w.first_ts - b.first_ts) <= S60, l['link_id'])
    for m in ('W1', 'W1_S60'):
        for level in LEVELS:
            its = [i for i in R.items if i.level == level]; got = {(l['wing_item'], l['body_item']) for l in R.links[m] if l['level'] == level}
            ok('I-candidates-equal-brute-force-reference', got == brute_force_pairs(its, m), f'{m} {level}')
    for m, base in (('W2', 'W1'), ('W2_S60', 'W1_S60')):
        ok('I-W2-same-candidates-as-base', {(l['wing_item'], l['body_item']) for l in R.links[m]} == {(l['wing_item'], l['body_item']) for l in R.links[base]})
        w = defaultdict(float); a = defaultdict(float)
        for l in R.links[m]: w[l['wing_item']] += l['weight']; a[l['wing_item']] += l['allocated_wing_units']
        for k in w: ok('I-W2-weights-sum-to-1-and-units-reconcile', abs(w[k] - 1) < 1e-6 and abs(a[k] - R.by_id[k].qty) < 1e-3 * max(1, len(R.links[m]) // 1000 + 1), k)
    pw = defaultdict(int); pb = defaultdict(int); gw = defaultdict(int); gb = defaultdict(int)
    for l in R.links['W3']: pw[l['wing_item']] += l['allocated_wing_units']; pb[l['body_item']] += l['allocated_wing_units']
    for k, v in pw.items(): ok('I-W3-no-overallocation', v <= R.by_id[k].qty)
    for k, v in pb.items(): ok('I-W3-no-overallocation', v <= R.by_id[k].qty)
    grp = defaultdict(lambda: [0, 0, 0])
    for i in R.items:
        if i.level != 'OPENING': continue
        g = grp[i.group_key + (i.session,)]; g[0 if i.role == 'WING' else 1] += i.qty
    matched = defaultdict(int)
    for l in R.links['W3']: matched[R.by_id[l['wing_item']].group_key + (R.by_id[l['wing_item']].session,)] += l['allocated_wing_units']
    for k, (wu, bu, _) in grp.items(): ok('I-W3-matched-equals-min(wing,body)-per-group', matched.get(k, 0) == min(wu, bu), k)
    ok('I-W3-residual', R.w3_residual['wing_units_unmatched'] == sum(max(0, v[0] - v[1]) for v in grp.values()) and R.w3_residual['body_units_unmatched'] == sum(max(0, v[1] - v[0]) for v in grp.values()))
    return passed
