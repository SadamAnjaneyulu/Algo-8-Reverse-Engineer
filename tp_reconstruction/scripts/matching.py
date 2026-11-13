"""Position matching engine (pure functions, no file access).

A fill's role is decided ONLY by the current net inventory of its own contract:
  against the inventory  -> closes min(qty, |inventory|); the excess opens the opposite direction (a reversal)
  with the inventory or flat -> opens.
Three ownership conventions on identical fills:
  FIFO  oldest open lot is closed first          LIFO  newest open lot first
  AVG   the open inventory is one pool at its quantity-weighted average price; a closure takes the pool average
Quantities are integer units (as exported); prices are per-fill prices. Direction: +1 long, -1 short.
Position ("episode"): a run of non-zero inventory in one direction in one contract; flat or a reversal ends it.
Tie orderings inside one (contract, second): 'src' (file row), 'sells_first', 'buys_first'.
"""
from collections import deque
import numpy as np, pandas as pd

TIE_KEY = {'src': lambda sg: 0, 'sells_first': lambda sg: 0 if sg < 0 else 1, 'buys_first': lambda sg: 0 if sg > 0 else 1}


def ordered(fills, tie_order='src'):
    """fills sorted by (contract, execution second, tie key, file row); contracts are independent so only same-contract order matters"""
    f = fills.copy(); f['_tk'] = f.sgn.map(TIE_KEY[tie_order])
    return f.sort_values(['contract_id', 'epoch', '_tk', 'src_row']).drop(columns='_tk')


def run_matching(fills, method='FIFO', tie_order='src'):
    """fills: columns contract_id, epoch, src_row, sgn (+1 buy / -1 sell), qty_units (int), px_fill.  Rows flagged dq_duplicate_fill are ignored.
    Returns dict(roles, closures, remaining, episodes)."""
    assert method in ('FIFO', 'LIFO', 'AVG')
    f = fills[~fills.dq_duplicate_fill] if 'dq_duplicate_fill' in fills.columns else fills
    f = ordered(f, tie_order)
    roles, closures, episodes = [], [], {}
    remaining = []
    cid_prev = None; st = None; ep_n = {}

    def new_episode(cid, direction, epoch, from_reversal):
        n = ep_n.get(cid, 0) + 1; ep_n[cid] = n; eid = f'{cid}#{n}'
        episodes[eid] = dict(episode_id=eid, contract_id=cid, direction=direction, open_epoch=epoch, opened_units=0, closed_units=0, entry_value=0.0, exit_value=0.0,
                             n_open_fills=0, n_close_fills=0, started_by_reversal=from_reversal, ended_by='open', last_close_epoch=np.nan, max_units=0)
        return eid

    def flush(cid, st):
        if st is None: return
        if method == 'AVG':
            if st['pool_q'] > 0:
                remaining.append(dict(contract_id=cid, episode_id=st['eid'], direction=st['dir'], qty=st['pool_q'], entry_px=st['pool_px'], entry_epoch=st['pool_w'] / st['pool_q'], open_rows=';'.join(map(str, st['pool_rows']))))
        else:
            for lot in st['lots']:
                remaining.append(dict(contract_id=cid, episode_id=st['eid'], direction=st['dir'], qty=lot[0], entry_px=lot[1], entry_epoch=lot[2], open_rows=str(lot[3])))

    for r in f.itertuples(index=False):
        if r.contract_id != cid_prev:
            flush(cid_prev, st); cid_prev = r.contract_id; st = dict(dir=0, inv=0, lots=deque(), eid=None, pool_q=0, pool_px=0.0, pool_w=0.0, pool_rows=[])
        q = int(r.qty_units); sg = int(r.sgn); px = float(r.px_fill); inv_before = st['inv'] * st['dir'] if st['dir'] else 0
        close_q = 0; open_q = 0; eid_close = None; eid_open = None; reversal = False
        if st['dir'] != 0 and sg == -st['dir']:                    # against the inventory: close
            close_q = min(q, st['inv']); eid_close = st['eid']; d = st['dir']; ep = episodes[eid_close]
            if method == 'AVG':
                closures.append(dict(contract_id=r.contract_id, episode_id=eid_close, close_row=r.src_row, open_row=-1, qty=close_q, direction=d, entry_px=st['pool_px'], exit_px=px,
                                     entry_epoch=st['pool_w'] / st['pool_q'], exit_epoch=r.epoch, open_rows=';'.join(map(str, st['pool_rows']))))
                st['pool_w'] -= st['pool_w'] / st['pool_q'] * close_q; st['pool_q'] -= close_q
            else:
                need = close_q
                while need > 0:
                    lot = st['lots'][0] if method == 'FIFO' else st['lots'][-1]; take = min(need, lot[0])
                    closures.append(dict(contract_id=r.contract_id, episode_id=eid_close, close_row=r.src_row, open_row=lot[3], qty=take, direction=d, entry_px=lot[1], exit_px=px,
                                         entry_epoch=lot[2], exit_epoch=r.epoch, open_rows=str(lot[3])))
                    lot[0] -= take; need -= take
                    if lot[0] == 0: (st['lots'].popleft() if method == 'FIFO' else st['lots'].pop())
            st['inv'] -= close_q; ep['closed_units'] += close_q; ep['exit_value'] += close_q * px; ep['n_close_fills'] += 1; ep['last_close_epoch'] = r.epoch
            if st['inv'] == 0:
                ep['ended_by'] = 'flat' if q == close_q else 'reversal'; st['dir'] = 0; st['lots'].clear(); st['pool_q'] = 0; st['pool_w'] = 0.0; st['pool_rows'] = []
            open_q = q - close_q
            if open_q > 0: reversal = True
        else:
            open_q = q
        if open_q > 0:                                                  # opening part (new, added, or the reversing remainder)
            if st['dir'] == 0:
                st['dir'] = sg; st['eid'] = new_episode(r.contract_id, sg, r.epoch, reversal)
                if method == 'AVG': st['pool_q'] = 0; st['pool_w'] = 0.0; st['pool_px'] = 0.0; st['pool_rows'] = []
            eid_open = st['eid']; ep = episodes[eid_open]
            if method == 'AVG':
                st['pool_px'] = (st['pool_px'] * st['pool_q'] + px * open_q) / (st['pool_q'] + open_q); st['pool_q'] += open_q; st['pool_w'] += open_q * r.epoch; st['pool_rows'].append(r.src_row)
            else:
                st['lots'].append([open_q, px, r.epoch, r.src_row])
            st['inv'] += open_q; ep['opened_units'] += open_q; ep['entry_value'] += open_q * px; ep['n_open_fills'] += 1; ep['max_units'] = max(ep['max_units'], st['inv'])
        if st['dir'] == 0: ref = np.nan
        elif method == 'AVG': ref = st['pool_px']
        elif method == 'FIFO': ref = st['lots'][0][1]
        else: ref = st['lots'][-1][1]
        roles.append(dict(ref_px_after=ref, src_row=r.src_row, contract_id=r.contract_id, epoch=r.epoch, sgn=sg, qty_units=q, px_fill=px, inventory_before=inv_before, inventory_after=st['inv'] * st['dir'] if st['dir'] else 0,
                          close_qty=close_q, open_qty=open_q, is_reversal=reversal, episode_closed=eid_close, episode_opened=eid_open))
    flush(cid_prev, st)
    C = pd.DataFrame(closures); R = pd.DataFrame(roles); Rm = pd.DataFrame(remaining); E = pd.DataFrame(list(episodes.values()))
    if len(C):
        C['pnl_pts'] = C.direction * (C.exit_px - C.entry_px); C['pnl'] = C.pnl_pts * C.qty        # gross, price points x units == rupees
        C['hold_s'] = C.exit_epoch - C.entry_epoch; C['method'] = method; C['tie_order'] = tie_order
    if len(Rm): Rm['method'] = method
    if len(E):
        rem = Rm.groupby('episode_id').qty.sum() if len(Rm) else pd.Series(dtype=float)
        E['remaining_units'] = E.episode_id.map(rem).fillna(0).astype(int); E['method'] = method
        pnl = C.groupby('episode_id').pnl.sum() if len(C) else pd.Series(dtype=float); E['realized_pnl'] = E.episode_id.map(pnl).fillna(0.0)
    return dict(roles=R, closures=C, remaining=Rm, episodes=E)


def role_ambiguity(fills, tie_orders=('src', 'sells_first', 'buys_first')):
    """src_rows of fills whose closing quantity differs between tie orderings (their open/close role is not identifiable)"""
    cq = {}
    for to in tie_orders:
        R = run_matching(fills, 'FIFO', to)['roles'].set_index('src_row').close_qty; cq[to] = R
    D = pd.DataFrame(cq); return set(D.index[(D.nunique(axis=1) > 1)])


def classify(pnl_pts, tol):
    """PROFIT / LOSS / BREAKEVEN by gross P&L per unit; tolerance in price points (inclusive). Values are rounded to 1e-9 so a value sitting exactly on the tolerance is not
    decided by floating-point noise."""
    pnl_pts = np.round(np.asarray(pnl_pts, dtype=float), 9); tol = round(float(tol), 9)
    return np.where(pnl_pts > tol, 'PROFIT', np.where(pnl_pts < -tol, 'LOSS', 'BREAKEVEN'))
