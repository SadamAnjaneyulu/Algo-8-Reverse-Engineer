"""TRACK C independent reference implementation of M2-D items / W1 / W1_S60 / W2 / W2_S60 / W3.
Written from the approved method text (BASKET_GROUPING_METHODOLOGY.md D6 + M2D report) and NOT from pe/wing_body.py.  Pure python, no pe imports.
Input: list of fill dicts  {row, ts, inst:(und,expiry_iso,right,strike), sgn, qty, px (paise int), parent, tag, emin (epoch s of entry minute or None)}
Time-ordering for the replay: (ts, row).  Opening/closing split: own signed-inventory replay per instrument.  IST session = (ts+19800)//86400."""
from collections import defaultdict
import bisect

IST = 19800


def sess(ts): return (ts + IST) // 86400


def replay(fills, order=lambda f: (f['ts'], f['row'])):
    """returns list of portions: dict(kind 'OPEN'|'CLOSE', dir (sign of the position being opened / closed), fill, qty)"""
    inv = defaultdict(int); out = []
    for f in sorted(fills, key=order):
        i = f['inst']; cur = inv[i]; q = f['qty']; s = f['sgn']
        if cur != 0 and (cur > 0) != (s > 0):                       # trade against inventory
            c = min(q, abs(cur)); out.append(dict(kind='CLOSE', dir=1 if cur > 0 else -1, fill=f, qty=c)); o = q - c
            if o > 0: out.append(dict(kind='OPEN', dir=s, fill=f, qty=o))
        else: out.append(dict(kind='OPEN', dir=s, fill=f, qty=q))
        inv[i] = cur + s * q
    return out


class It:
    def __init__(s, level, role, parent, inst, tag):
        s.level = level; s.role = role; s.parent = parent; s.inst = inst; s.tag = tag; s.qty = 0; s.pxsum = 0; s.first_ts = None; s.first_row = None; s.emin = None; s.nf = 0
    @property
    def key(s): return (s.level, s.role, s.parent, s.inst)
    @property
    def grp(s): return (s.level, s.inst[0], s.inst[1], s.inst[2])
    @property
    def session(s): return sess(s.first_ts)
    @property
    def item_id(s): return f'WBI:{s.level}:{s.role}:{s.parent}:{"|".join(map(str, s.inst))}'


def build_items(portions, scope='TAGGED'):
    items = {}
    for p in portions:
        f = p['fill']; lvl = 'OPENING' if p['kind'] == 'OPEN' else 'CLOSING'
        d = p['dir']                      # opening: side of the opening fill ; closing: direction of the episode being closed
        if scope == 'TAGGED': wing = (d == 1 and f['tag'] == 'h_'); body = (d == -1 and f['tag'] == 'num')
        else: wing = d == 1; body = d == -1
        role = 'WING' if wing else ('BODY' if body else None)
        if role is None: continue
        k = (lvl, role, f['parent'], f['inst']); it = items.get(k)
        if it is None: it = items[k] = It(lvl, role, f['parent'], f['inst'], f['tag']); it.emin = f['emin']
        it.qty += p['qty']; it.pxsum += p['qty'] * f['px']; it.nf += 1
        if it.first_ts is None or f['ts'] < it.first_ts: it.first_ts = f['ts']
        if it.first_row is None or f['row'] < it.first_row: it.first_row = f['row']
    return items


def otm(w, b):
    # wing further out of the money than the body: CE -> higher strike ; PE -> lower strike
    return (w.inst[3] - b.inst[3]) if w.inst[2] == 'CE' else (b.inst[3] - w.inst[3])


def mk(method, w, b, **kw):
    r = dict(method=method, level=w.level, wing=w.key, body=b.key, dt_s=w.first_ts - b.first_ts, wing_qty=w.qty, body_qty=b.qty, qty_ratio=round(w.qty / b.qty, 6), otm=otm(w, b),
             wing_px=round(w.pxsum / w.qty, 4), body_px=round(b.pxsum / b.qty, 4), px_ratio=round((w.pxsum / w.qty) / (b.pxsum / b.qty), 6), same_emin=int(w.emin is not None and w.emin == b.emin))
    r.update(kw); return r


def flag_nearest(ws_to_cs):
    out = []
    for w, cs in ws_to_cs:
        m = min(abs(w.first_ts - b.first_ts) for b in cs); nt = sum(1 for b in cs if abs(w.first_ts - b.first_ts) == m)
        for b in cs:
            d = abs(w.first_ts - b.first_ts); out.append((w, b, int(d == m), int(d == m and nt > 1), len(cs)))
    return out


def w1(items, level):
    bodies = defaultdict(list)
    for it in items.values():
        if it.level == level and it.role == 'BODY' and it.emin is not None: bodies[it.grp + (it.emin,)].append(it)
    ws = []
    for it in items.values():
        if it.level == level and it.role == 'WING' and it.emin is not None:
            cs = bodies.get(it.grp + (it.emin,), [])
            if cs: ws.append((it, cs))
    res = []
    for w, b, n, nt, k in flag_nearest(ws): res.append(mk('W1', w, b, nearest=n, tied=nt, n_cand=k))
    return res


def w1_s60(items, level, window=60, strict=False):
    byg = defaultdict(list)
    for it in items.values():
        if it.level == level and it.role == 'BODY': byg[it.grp + (it.session,)].append(it)
    ws = []
    for w in items.values():
        if w.level != level or w.role != 'WING': continue
        cs = [b for b in byg.get(w.grp + (w.session,), []) if (abs(w.first_ts - b.first_ts) < window if strict else abs(w.first_ts - b.first_ts) <= window)]
        if cs: ws.append((w, cs))
    return [mk('W1_S60', w, b, nearest=n, tied=nt, n_cand=k) for w, b, n, nt, k in flag_nearest(ws)]


def w2(base, name):
    tot = defaultdict(int)
    for l in base: tot[l['wing']] += l['body_qty']
    out = []
    for l in base:
        r = dict(l); r['method'] = name; r['weight'] = l['body_qty'] / tot[l['wing']]; r['wunits'] = l['wing_qty'] * l['body_qty'] / tot[l['wing']]; out.append(r)
    return out


def w3(items):
    g = defaultdict(lambda: ([], []))
    for it in items.values():
        if it.level == 'OPENING': g[it.grp + (it.session,)][0 if it.role == 'WING' else 1].append(it)
    links = []; rw = rb = 0; sk = lambda x: (x.first_ts, x.first_row, x.item_id)
    for k, (ws, bs) in g.items():
        ws = sorted(ws, key=sk); bs = sorted(bs, key=sk)
        # expand queue arithmetic by cumulative-sum interval overlap (different algorithm from a two-pointer loop)
        cw = [0]; cb = [0]
        for w in ws: cw.append(cw[-1] + w.qty)
        for b in bs: cb.append(cb[-1] + b.qty)
        seg = 0; tot = min(cw[-1], cb[-1])
        for i, w in enumerate(ws):
            for j, b in enumerate(bs):
                lo = max(cw[i], cb[j]); hi = min(cw[i + 1], cb[j + 1], tot)
                if hi > lo: seg += 1; links.append(mk('W3', w, b, matched=hi - lo, seg=seg, weight=(hi - lo) / w.qty))
        rw += max(0, cw[-1] - cb[-1]); rb += max(0, cb[-1] - cw[-1])
    return links, dict(wing=rw, body=rb)


def analyse(fills, scope='TAGGED', order=lambda f: (f['ts'], f['row'])):
    P = replay(fills, order); I = build_items(P, scope); L = {}
    for lv in ('OPENING', 'CLOSING'):
        a = w1(I, lv); b = w1_s60(I, lv); L.setdefault('W1', []).extend(a); L.setdefault('W1_S60', []).extend(b); L.setdefault('W2', []).extend(w2(a, 'W2')); L.setdefault('W2_S60', []).extend(w2(b, 'W2_S60'))
    L['W3'], res = w3(I)
    return dict(portions=P, items=I, links=L, w3_resid=res)
