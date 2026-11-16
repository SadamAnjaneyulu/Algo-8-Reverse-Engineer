"""TRACK A independent accounting / lineage reference model (M2-F audit).

[RAW]  reads /home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv directly with the csv module (no pandas, no pe.*, no TP-01 parquet).
[IMPL] re-implements signed-position accounting, episodes, opening/closing split, FIFO / LIFO / AVG closing allocation in exact integer
       (FIFO/LIFO) or exact rational (AVG, fractions.Fraction) arithmetic. FIFO is implemented twice (lot list AND cumulative-interval overlap).
Raw columns (0-based, verified by explore scripts): 4 order no, 11 side, 12 underlying, 14 strike, 15 expiry text, 16 right, 19 order qty, 27 status,
33 fill qty (units), 137 per-fill price (rupees), 161 UTC epoch s, 163 parent id (UniqueOrderIdentifier), 166 module/app tag.
"""
import csv, sys
from fractions import Fraction
from decimal import Decimal

RAW = '/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv'
LOT = {'NIFTY': 65, 'SENSEX': 20}


def load_raw(path=RAW):
    """returns list of dict rows in FILE ORDER (row = 0-based file row). Price converted with Decimal (exact) to integer paise."""
    out = []
    with open(path, newline='', encoding='utf-8') as fh:
        for row, r in enumerate(csv.reader(fh)):
            if len(r) != 167: raise ValueError(f'row {row}: {len(r)} columns')
            m, d, y = r[15].split(' ')[0].split('/')
            px = Decimal(r[137]) * 100
            if px != px.to_integral_value(): raise ValueError(f'row {row}: price off paise grid {r[137]}')
            out.append(dict(row=row, parent=r[163], side=(1 if r[11] == 'Buy' else -1 if r[11] == 'Sell' else 0), und=r[12], expiry=f'{int(y):04d}-{int(m):02d}-{int(d):02d}', right=r[16], strike=int(r[14]),
                            ts=int(r[161]), qty=int(r[33]), px=int(px), order_qty=int(r[19]), status=r[27], module=r[166], order_no=r[4], trade_id=r[28],
                            inst=f'{r[12]}|{int(y):04d}-{int(m):02d}-{int(d):02d}|{r[16]}|{int(r[14])}'))
    return out


def order_fills(rows, tie='src', seed=0):
    """alternative same-second orders. Only the order among rows of the SAME (instrument, second) can change any outcome, but we reorder globally within a second."""
    import random
    if tie == 'src': return sorted(rows, key=lambda f: (f['ts'], f['row']))
    if tie == 'reversed_src': return sorted(rows, key=lambda f: (f['ts'], -f['row']))
    if tie == 'buys_first': return sorted(rows, key=lambda f: (f['ts'], 0 if f['side'] > 0 else 1, f['row']))
    if tie == 'sells_first': return sorted(rows, key=lambda f: (f['ts'], 0 if f['side'] < 0 else 1, f['row']))
    if tie == 'random':
        rnd = random.Random(seed); return sorted(rows, key=lambda f: (f['ts'], rnd.random()))
    raise ValueError(tie)


class Ref:
    """result container of one replay"""
    pass


def replay_ref(fills, conv):
    """fills: ordered list of dicts (row, parent, inst, ts, side, qty, px ...). conv in FIFO / LIFO / AVG. Exact arithmetic."""
    st = {}                                   # inst -> dict(inv signed int, lots list, ep, ep_n, pool_q, pool_cost (Fraction total paise))
    R = Ref(); R.fills = {}; R.oa = {}; R.cp = {}; R.episodes = {}; R.events = []; R.ca = []; R.conv = conv; ev_seq = {}
    def new_ep(inst, direction, ts, rev):
        s = st[inst]; s['ep_n'] += 1; eid = f'{inst}#{s["ep_n"]}'
        R.episodes[eid] = dict(id=eid, inst=inst, dir=direction, opened=0, closed=0, n_open=0, n_close=0, ended_by='open', rev=rev, first_ts=ts, last_ts=ts, realized=Fraction(0))
        s['ep'] = eid; return eid
    def event(eid, typ, f, q, inv_after, rev):
        n = ev_seq.get(eid, 0) + 1; ev_seq[eid] = n; R.events.append((eid, n, typ, f['row'], q, inv_after, int(rev)))
    for f in fills:
        s = st.setdefault(f['inst'], dict(inv=0, lots=[], ep=None, ep_n=0, pool_q=0, pool_cost=Fraction(0)))
        inv = s['inv']; q = f['qty']; sg = f['side']; px = f['px']
        close_q = 0; open_q = q; ep_close = None; ep_open = None; rev = False
        if inv != 0 and (inv > 0) != (sg > 0):               # opposite sign to the net position -> closes
            close_q = min(q, abs(inv)); open_q = q - close_q; ep_close = s['ep']; E = R.episodes[ep_close]; d = 1 if inv > 0 else -1
            R.cp[f['row']] = dict(ep=ep_close, qty=close_q, px=px, ts=f['ts'], side=sg, parent=f['parent'])
            if conv == 'AVG':
                avg = s['pool_cost'] / s['pool_q']                                    # exact rational average cost per unit
                pnl = d * (px - avg) * close_q
                R.ca.append((f['row'], f'POOL:{ep_close}', close_q, avg, px, pnl, s['pool_q'] - close_q))
                s['pool_cost'] -= avg * close_q; s['pool_q'] -= close_q
            else:
                need = close_q; pnl = 0
                while need:
                    lot = s['lots'][0] if conv == 'FIFO' else s['lots'][-1]           # lot = [row, remaining, entry_px]
                    take = min(need, lot[1]); p_ = d * (px - lot[2]) * take; pnl += p_; lot[1] -= take; need -= take
                    R.ca.append((f['row'], lot[0], take, lot[2], px, p_, lot[1]))
                    if lot[1] == 0: s['lots'].pop(0 if conv == 'FIFO' else -1)
            E['realized'] += pnl; E['closed'] += close_q; E['n_close'] += 1; E['last_ts'] = f['ts']
            s['inv'] = inv + sg * close_q
            if s['inv'] == 0:
                E['ended_by'] = 'flat' if open_q == 0 else 'reversal'; s['lots'] = []; s['pool_q'] = 0; s['pool_cost'] = Fraction(0)
            event(ep_close, 'PARTIALLY_REDUCED' if s['inv'] != 0 else ('CLOSED' if open_q == 0 else 'REVERSED'), f, close_q, s['inv'], False)
            rev = open_q > 0
        if open_q > 0:
            created = s['inv'] == 0
            if created: ep_open = new_ep(f['inst'], sg, f['ts'], rev)
            else: ep_open = s['ep']
            E = R.episodes[ep_open]; E['last_ts'] = f['ts']; E['opened'] += open_q; E['n_open'] += 1
            R.oa[f['row']] = dict(ep=ep_open, qty=open_q, px=px, ts=f['ts'], side=sg, parent=f['parent'])
            if conv == 'AVG': s['pool_cost'] += px * open_q; s['pool_q'] += open_q
            else: s['lots'].append([f['row'], open_q, px])
            s['inv'] += sg * open_q
            event(ep_open, 'CREATED' if created else 'ADDED', f, open_q, s['inv'], rev and created)
        R.fills[f['row']] = dict(close=close_q, open=open_q, inv_after=s['inv'], ep_close=ep_close, ep_open=ep_open, rev=rev)
    R.final_inv = {i: s['inv'] for i, s in st.items()}
    R.slices = {}
    for i, s in st.items():
        if conv == 'AVG':
            if s['inv'] != 0: R.slices[s['ep']] = ('POOL', s['pool_q'], s['pool_cost'] / s['pool_q'])
        else:
            for lot in s['lots']: R.slices[lot[0]] = ('LOT', lot[1], lot[2], s['ep'])
    R.realized_total = sum((e['realized'] for e in R.episodes.values()), Fraction(0))
    R.cash = sum(-f['side'] * f['qty'] * f['px'] for f in fills)
    return R


def fifo_interval_check(fills):
    """[IMPL] second, structurally different FIFO: per episode lay opening quantity on a number line (cumulative), consume closings from the left.
    returns list of (cp_row, oa_row, qty) comparable to the lot-list FIFO."""
    st = {}; out = []
    for f in fills:
        s = st.setdefault(f['inst'], dict(inv=0, open_line=[], consumed=0))   # open_line: (oa_row, start, end)
        inv = s['inv']; q = f['qty']; sg = f['side']
        if inv != 0 and (inv > 0) != (sg > 0):
            c = min(q, abs(inv)); lo, hi = s['consumed'], s['consumed'] + c
            for row, a, b in s['open_line']:
                x, y = max(a, lo), min(b, hi)
                if x < y: out.append((f['row'], row, y - x))
            s['consumed'] = hi; s['inv'] = inv + sg * c; o = q - c
            if s['inv'] == 0: s['open_line'] = []; s['consumed'] = 0
            if o > 0:
                s['open_line'].append((f['row'], 0, o)); s['inv'] = sg * o
        else:
            end = s['open_line'][-1][2] if s['open_line'] else 0
            s['open_line'].append((f['row'], end, end + q)); s['inv'] += sg * q
    return out


def to_fill_id(row): return f'F{row:06d}'
