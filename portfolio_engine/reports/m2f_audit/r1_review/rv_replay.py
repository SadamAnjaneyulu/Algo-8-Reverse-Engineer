"""Reviewer's OWN independent replay from the raw csv (no pe.* import, no author reference script). [RAW]+[IMPL]
Raw 0-based columns (verified in FINDINGS): 4 order no, 11 side, 12 underlying, 14 strike, 15 expiry, 16 right, 28 trade id, 33 fill qty, 137 price (rupees), 161 epoch, 163 parent order id."""
import csv, collections, datetime, decimal
from decimal import Decimal
RAW = '/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv'

def load():
    F = []
    with open(RAW, newline='') as fh:
        for i, r in enumerate(csv.reader(fh)):
            exp = datetime.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat()
            iid = f'{r[12]}|{exp}|{r[16]}|{int(r[14])}'
            side = {'Buy': 1, 'Sell': -1}[r[11]]
            price = Decimal(r[137]) * 100
            assert price == price.to_integral_value(), (i, r[137])
            F.append(dict(row=i, iid=iid, und=r[12], side=side, qty=int(r[33]), px=int(price), ep=int(r[161]), tid=r[28], ono=int(r[4]), pid=r[163]))
    return F

def tid_key(f):
    t = f['tid']
    if '-' in t:
        a, b = t.split('-', 1); return (int(a), int(b))
    return (int(t), 0)

def sensex_ns(f):
    if f['und'] != 'SENSEX': return 0
    t = f['tid']
    if len(t) > 19 and t[19] == '-' and t[:19].isdigit():
        ns = int(t[:19])
        if (ns + 500_000_000) // 10**9 == f['ep']: return ns
    return f['ep'] * 10**9

POLICIES = {
    'source_row': lambda f: 0,
    'sells_first': lambda f: 0 if f['side'] < 0 else 1,
    'buys_first': lambda f: 0 if f['side'] > 0 else 1,
    'trade_id': tid_key,
    'order_no': lambda f: f['ono'],
    'sensex_ns': sensex_ns,
}

def order_fills(F, policy):
    """per-instrument processing order: (epoch, key, file row)"""
    k = POLICIES[policy]
    by = collections.defaultdict(list)
    for f in F: by[f['iid']].append(f)
    return {iid: sorted(L, key=lambda f: (f['ep'], k(f), f['row'])) for iid, L in by.items()}

def replay(F, policy):
    """signed position per instrument; open/close split per fill; flat-to-flat episodes; FIFO realized in integer paise."""
    split = {}; episodes = {}; final = {}; realized = {}; rev_rows = set()
    tot_open = tot_close = 0
    for iid, L in order_fills(F, policy).items():
        pos = 0; ep_idx = 0; cur = None; lots = collections.deque(); R = 0; eps = []
        for f in L:
            q = f['qty']; s = f['side']
            if pos == 0 or (pos > 0) == (s > 0):
                c = 0; o = q
            else:
                c = min(q, abs(pos)); o = q - c
            split[f['row']] = (o, c)
            # FIFO realized: close against opposite-sign lots
            rem = c
            while rem:
                lq, lpx = lots[0]   # lq is signed qty
                take = min(rem, abs(lq))
                R += take * ((f['px'] - lpx) if lq > 0 else (lpx - f['px']))
                if take == abs(lq): lots.popleft()
                else: lots[0] = ((abs(lq) - take) * (1 if lq > 0 else -1), lpx)
                rem -= take
            # episode bookkeeping
            if c:
                cur['pieces'].append((f['row'], 0, c))
                if o:  # reversal: closes episode, opens next
                    cur['end'] = 'REVERSAL'; eps.append(cur); cur = None
                    rev_rows.add(f['row'])
                elif abs(pos) == c:
                    cur['end'] = 'FLAT'; eps.append(cur); cur = None
            if o:
                if cur is None:
                    cur = dict(iid=iid, dir=s, pieces=[], end=None)
                cur['pieces'].append((f['row'], o, 0))
                lots.append((s * o, f['px']))
            pos += s * q
            tot_open += o; tot_close += c
        if cur is not None:
            cur['end'] = 'OPEN'; eps.append(cur)
        final[iid] = pos; realized[iid] = R; episodes[iid] = eps
    return dict(split=split, episodes=episodes, final=final, realized=realized, tot_open=tot_open, tot_close=tot_close, rev_rows=rev_rows)

def ep_sig(e):
    return (e['iid'], e['dir'], tuple(sorted(e['pieces'])), e['end'])

def groups(F):
    g = collections.defaultdict(list)
    for f in F: g[(f['iid'], f['ep'])].append(f)
    return {k: v for k, v in g.items() if len(v) >= 2}
