"""TRACK D independent RAW-SOURCE truth builder.  [RAW]/[IMPL]
Reads ONLY /home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv (+ the TP-03 parquet for window labels).  Does NOT import pe.*, the TP-01 ledger or any engine output.
Raw 0-based columns (verified in verify_raw_columns.py): 4 order no, 11 side, 14 strike, 15 expiry text, 16 right, 18 order running-avg px, 19 order qty, 23 order entry text,
27 status, 33 fill qty, 137 per-fill px (rupees), 161 UTC epoch s, 163 parent id (prefix h_/s_/v_/m_ = module, none = 'num').
"""
import csv, re, os, datetime as dt
from collections import defaultdict, Counter, OrderedDict

REPO = os.environ.get('M2F_REPO', '/home/user/Algo-8-Reverse-Engineer')
RAW = os.path.join(REPO, 'Trades_GKOHNP140.csv')
IST = 19800
CYCLES = (('NIFTY', '2026-06-30'), ('SENSEX', '2026-07-16'))


def ist_str(ts): return dt.datetime.fromtimestamp(ts + IST, dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
def ist_date(ts): return ist_str(ts)[:10]


def load_raw(path=RAW):
    rows = []
    with open(path, newline='') as fh:
        for i, r in enumerate(csv.reader(fh)):
            rows.append(r)
    return rows


def parse_expiry(s):  # '6/23/2026 14:30' -> '2026-06-23'
    d = dt.datetime.strptime(s, '%m/%d/%Y %H:%M'); return d.strftime('%Y-%m-%d')


def fills_for_cycle(raw, und, expiry):
    out = []
    for i, r in enumerate(raw):
        if r[12] != und or parse_expiry(r[15]) != expiry: continue
        pid = r[163]; m = re.match(r'^([a-z]+_)', pid); tag = m.group(1) if m else 'num'
        side = 1 if r[11] == 'Buy' else -1 if r[11] == 'Sell' else None
        assert side is not None
        em = dt.datetime.strptime(r[23], '%m/%d/%Y %H:%M'); em_utc = int((em - dt.datetime(1970, 1, 1)).total_seconds()) - IST   # entry text is IST wall-clock
        px = float(r[137]); paise = round(px * 100); assert abs(paise - px * 100) < 1e-6
        out.append(dict(row=i, parent=pid, tag=tag, iid=f'{und}|{expiry}|{r[16]}|{int(r[14])}', right=r[16], strike=int(r[14]), side=side, qty=int(r[33]), px_paise=paise, px_order_avg_paise=round(float(r[18]) * 100),
                        ts=int(r[161]), req=int(r[19]), status=r[27], order_no=r[4], entry_min_utc=em_utc))
    out.sort(key=lambda f: (f['ts'], f['row']))
    return out


def replay(fills, expiry):
    """signed inventory by instrument; episodes; events; opening / closing allocations (convention-free quantities)."""
    inv = defaultdict(int); epn = defaultdict(int); cur = {}; episodes = OrderedDict(); events = []; oa = []; cp = []; series = []
    for f in fills:
        iid = f['iid']; q = f['qty']; s = f['side']; p = inv[iid]; close_q = 0
        if p != 0 and (1 if p > 0 else -1) == -s:
            close_q = min(q, abs(p)); eid = cur[iid]; E = episodes[eid]; E['closed'] += close_q; E['n_close'] += 1; E['last_ts'] = f['ts']; p_new = p + s * close_q
            cp.append(dict(fill=f, eid=eid, qty=close_q))
            if p_new == 0: kind = 'CLOSED' if close_q == q else 'REVERSED'; E['ended_by'] = 'flat' if close_q == q else 'reversal'
            else: kind = 'PARTIALLY_REDUCED'
            events.append(dict(eid=eid, kind=kind, fill=f, qty=close_q, inv_after=p_new)); inv[iid] = p_new; p = p_new
        open_q = q - close_q
        if open_q > 0:
            created = (p == 0)
            if created:
                epn[iid] += 1; eid = f'{iid}#{epn[iid]}'; cur[iid] = eid
                episodes[eid] = dict(eid=eid, iid=iid, direction='SHORT' if s < 0 else 'LONG', opened=0, closed=0, first_ts=f['ts'], last_ts=f['ts'], n_open=0, n_close=0, ended_by='open', by_reversal=(close_q > 0))
            eid = cur[iid]; E = episodes[eid]; E['opened'] += open_q; E['n_open'] += 1; E['last_ts'] = f['ts']; inv[iid] = p + s * open_q
            oa.append(dict(fill=f, eid=eid, qty=open_q))
            events.append(dict(eid=eid, kind='CREATED' if created else 'ADDED', fill=f, qty=open_q, inv_after=inv[iid]))
        # state after the fill
        ss = {('short', 'CE'): 0, ('short', 'PE'): 0, ('long', 'CE'): 0, ('long', 'PE'): 0}
        for k, v in inv.items():
            if v: ss[('long' if v > 0 else 'short', k.split('|')[2])] += abs(v)
        series.append(dict(fill=f, **{f'{a}_{b}': v for (a, b), v in ss.items()}))
    return dict(inv=dict(inv), episodes=episodes, events=events, oa=oa, cp=cp, series=series)


def d_label(sessions, expiry, s):
    if s == expiry: return 'D0'
    prior = [x for x in sessions if x < expiry]; return f'D-{len(prior) - prior.index(s)}'


def opening_items(R):
    g = OrderedDict()
    for a in R['oa']:
        f = a['fill']; k = (f['parent'], f['iid']); d = g.setdefault(k, dict(parent=f['parent'], iid=f['iid'], tag=f['tag'], side=f['side'], qty=0, notional=0, first=f['ts'], last=f['ts'], n=0, eids=set(), em=f['entry_min_utc'], req=f['req'], order_no=f['order_no']))
        d['qty'] += a['qty']; d['notional'] += a['qty'] * f['px_paise']; d['first'] = min(d['first'], f['ts']); d['last'] = max(d['last'], f['ts']); d['n'] += 1; d['eids'].add(a['eid'])
    return g


_cache = {}
def truth(und, expiry):
    k = (und, expiry)
    if k not in _cache:
        raw = _cache.get('raw') or load_raw(); _cache['raw'] = raw
        fl = fills_for_cycle(raw, und, expiry); R = replay(fl, expiry); sessions = sorted({ist_date(f['ts']) for f in fl})
        _cache[k] = dict(fills=fl, R=R, sessions=sessions, items=opening_items(R))
    return _cache[k]
