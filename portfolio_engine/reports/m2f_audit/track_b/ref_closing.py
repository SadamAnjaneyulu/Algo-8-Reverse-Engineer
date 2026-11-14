"""TRACK B independent reference for Model C closing batches (C1/C2).
Written from the approved text only (BASKET_GROUPING_METHODOLOGY.md D2, tp03/config.yaml exit.batch)
BEFORE reading pe/closing_batches.py.  Pure stdlib; imports nothing from pe.*.
Evidence class of everything computed here: [RAW]/[IMPL] (own replay of raw fills, own chaining).
"""
import csv, collections, datetime, itertools

RAW = '/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv'
IST = 19800

def ist_date(t):
    return (datetime.datetime(1970,1,1) + datetime.timedelta(seconds=t+IST)).date().isoformat()

def load_raw(path=RAW):
    """fills as dicts. 0-based columns verified: 4 order no, 11 side, 12 und, 14 strike, 15 expiry,
    16 right, 33 fill qty, 161 UTC epoch s, 163 parent id.  row = 1-based file line."""
    out = []
    with open(path, newline='') as f:
        for i, r in enumerate(csv.reader(f), start=1):
            exp = datetime.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat()
            out.append(dict(row=i, instr=(r[12], exp, r[16], r[14]), side=r[11], qty=int(r[33]),
                            t=int(r[161]), parent=r[163], und=r[12], exp=exp, order_no=r[4]))
    return out

def replay(fills, tie='file'):
    """own position replay. returns list of dicts, one per fill, with close_qty/open_qty.
    tie: order of fills inside the same (instrument, second): 'file' | 'sells_first' | 'buys_first'."""
    by = collections.defaultdict(list)
    for f in fills: by[f['instr']].append(f)
    res = {}
    for ins, fl in by.items():
        if tie == 'file':
            fl = sorted(fl, key=lambda f: (f['t'], f['row']))
        else:
            sk = (lambda f: 0 if f['side'] == 'Sell' else 1) if tie == 'sells_first' else (lambda f: 0 if f['side'] == 'Buy' else 1)
            fl = sorted(fl, key=lambda f: (f['t'], sk(f), f['row']))
        inv = 0
        for f in fl:
            s = 1 if f['side'] == 'Buy' else -1
            q = f['qty']
            if inv == 0 or (inv > 0) == (s > 0):
                c = 0
            else:
                c = min(q, abs(inv))
            inv += s * q
            res[f['row']] = (c, q - c)
    out = []
    for f in fills:
        c, o = res[f['row']]
        g = dict(f); g['close_qty'] = c; g['open_qty'] = o
        out.append(g)
    return out

def parents_from(rep, first_def='closing', last_def='closing', include_mixed=True, unit='parent'):
    """aggregate to parent units.  first_def/last_def: 'closing' (closing portions only) | 'any' (any fill of parent)
    unit: 'parent' (col163) | 'order_no' (col 4)"""
    key = (lambda f: f['parent']) if unit == 'parent' else (lambda f: f['order_no'])
    allf = collections.defaultdict(list)
    for f in rep: allf[key(f)].append(f)
    P = []
    for pid, fl in allf.items():
        cl = [f for f in fl if f['close_qty'] > 0]
        if not cl: continue
        mixed = any(f['open_qty'] > 0 for f in fl)
        if mixed and not include_mixed: continue
        src_first = fl if first_def == 'any' else cl
        src_last = fl if last_def == 'any' else cl
        P.append(dict(pid=pid, first=min(f['t'] for f in src_first), last=max(f['t'] for f in src_last),
                      minrow_cl=min(f['row'] for f in cl), minrow_any=min(f['row'] for f in fl),
                      qty=sum(f['close_qty'] for f in cl), cps=[f for f in cl], mixed=mixed,
                      # parent stream = the stream of its closing fills (may be several)
                      streams=sorted({(f['und'], f['exp'], ist_date(f['t'])) for f in cl})))
    return P

def pid_key(p, mode):
    if mode == 'str': return p['pid']
    if mode == 'num_first':  # numeric ids by value, tags (non-digit) after in string order
        return (0, int(p['pid']), '') if p['pid'].isdigit() else (1, 0, p['pid'])
    raise ValueError

def build(parents, method, g, stream='und_exp_sess', order='first_cl', pid_mode='str', c2_ref='prev',
          inclusive=True, split_parent_by_stream=True):
    """returns list of batches; each batch = dict(stream, pids[list], first, last, qty, links[list of (gap,...)])
    stream: 'und_exp_sess' (default) | 'und_sess' | 'und_exp' | 'und'
    order: 'first_cl' = (first, min closing row, pid)  [my reading: tie by first source_row_id of closing portions]
           'first_any' = (first, min row over ALL fills of parent, pid)
           'first_pid' = (first, pid)
           'first_pid_rev' = (first, reversed pid)  (reversed tie order)
           'first_last' = (first, last, minrow, pid)
    c2_ref: 'prev' | 'runmax_chain' | 'runmax_stream'
    inclusive: gap <= g ; else gap < g"""
    sfun = {'und_exp_sess': lambda s: s, 'und_sess': lambda s: (s[0], None, s[2]),
            'und_exp': lambda s: (s[0], s[1], None), 'und': lambda s: (s[0], None, None)}[stream]
    members = collections.defaultdict(list)
    for p in parents:
        if split_parent_by_stream:
            # a parent whose closing fills lie in several streams becomes several members (per stream)
            per = collections.defaultdict(list)
            for f in p['cps']: per[sfun((f['und'], f['exp'], ist_date(f['t'])))].append(f)
            for s, cl in per.items():
                q = dict(p); q['cps'] = cl; q['first'] = min(f['t'] for f in cl) if len(per) > 1 else p['first']
                q['last'] = max(f['t'] for f in cl) if len(per) > 1 else p['last']
                q['qty'] = sum(f['close_qty'] for f in cl); q['minrow_cl'] = min(f['row'] for f in cl)
                members[s].append(q)
        else:
            members[sfun(p['streams'][0])].append(p)
    def okey(p):
        if order == 'first_cl': return (p['first'], p['minrow_cl'], pid_key(p, pid_mode))
        if order == 'first_any': return (p['first'], p['minrow_any'], pid_key(p, pid_mode))
        if order == 'first_pid': return (p['first'], pid_key(p, pid_mode))
        if order == 'first_pid_rev': return (p['first'], tuple(-ord(c) for c in p['pid']))
        if order == 'first_last': return (p['first'], p['last'], p['minrow_cl'], pid_key(p, pid_mode))
        raise ValueError(order)
    ok = (lambda gap: gap <= g) if inclusive else (lambda gap: gap < g)
    batches = []
    for s in sorted(members, key=lambda x: tuple('' if v is None else v for v in x)):
        L = sorted(members[s], key=okey)
        cur = None
        runmax_stream = None
        for p in L:
            if cur is None:
                link = False
            else:
                prev = cur['pids'][-1]
                if method == 'C1':
                    gap = p['first'] - cur['plast_first']
                else:
                    ref = {'prev': cur['plast_last'], 'runmax_chain': cur['maxlast'],
                           'runmax_stream': runmax_stream}[c2_ref]
                    gap = p['first'] - ref
                link = ok(gap)
            if link:
                cur['ov'].append(p['first'] <= cur['plast_last']); cur['sov'].append(p['first'] < cur['plast_last'])
                cur['pids'].append(p['pid']); cur['links'].append(gap)
                cur['plast_first'] = p['first']; cur['plast_last'] = p['last']
                cur['maxlast'] = max(cur['maxlast'], p['last']); cur['last'] = max(cur['last'], p['last'])
                cur['first_ts_list'].append(p['first']); cur['qty'] += p['qty']; cur['ncp'] += len(p['cps'])
                cur['cps'].extend(f['row'] for f in p['cps'])
            else:
                cur = dict(stream=s, pids=[p['pid']], links=[], plast_first=p['first'], plast_last=p['last'],
                           maxlast=p['last'], first=p['first'], last=p['last'], qty=p['qty'], ncp=len(p['cps']),
                           first_ts_list=[p['first']], cps=[f['row'] for f in p['cps']], ov=[], sov=[])
                batches.append(cur)
            runmax_stream = p['last'] if runmax_stream is None else max(runmax_stream, p['last'])
        # new stream resets runmax_stream via loop above only if set None: handled below
    return batches

# NB runmax_stream is reset per stream because it is re-initialised inside the per-stream loop only when
# declared there; (declared inside loop above).

def partition(batches):
    return frozenset((b['stream'], frozenset(b['pids'])) for b in batches)

def stats(batches):
    n = len(batches)
    return dict(n=n, max_parents=max(len(b['pids']) for b in batches),
                max_dur=max(b['last'] - b['first'] for b in batches),
                singletons=sum(1 for b in batches if len(b['pids']) == 1))
