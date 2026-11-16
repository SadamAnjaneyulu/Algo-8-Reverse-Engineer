"""My own minimal replay (no pe imports): per-instrument signed inventory, FIFO / LIFO realized P&L (exact integers), roles (close/open split), aggregate CE/PE long/short inventory, cash.
Rule (restated from the task, not copied): a fill against the instrument's inventory closes min(q, |inv|) and the excess opens the opposite direction; with / from flat it opens."""
from collections import deque


class Inst:
    __slots__ = ('dir', 'inv', 'lots', 'realized_fifo', 'realized_lifo', 'lots_l')
    def __init__(self): self.dir = 0; self.inv = 0; self.lots = deque(); self.lots_l = []; self.realized_fifo = 0; self.realized_lifo = 0


def replay(ordered, snapshots=True, roles=False):
    S = {}; agg = dict(sCE=0, sPE=0, lCE=0, lPE=0, n=0); cash = 0; opened = 0; closed = 0; rev = 0; RF = 0; RL = 0
    snaps = {}; R = {}; n = len(ordered); touched = set()
    for k, f in enumerate(ordered):
        st = S.get(f['inst'])
        if st is None: st = S[f['inst']] = Inst()
        q = f['qty']; sg = f['side']; px = f['px']; old = st.inv * st.dir; touched.add(f['inst'])
        cq = 0; oq = 0
        if st.dir != 0 and sg == -st.dir:
            cq = min(q, st.inv); d = st.dir
            need = cq; pnl = 0
            while need > 0:
                lot = st.lots[0]; t = min(need, lot[0]); pnl += d * (px - lot[1]) * t; lot[0] -= t; need -= t
                if lot[0] == 0: st.lots.popleft()
            st.realized_fifo += pnl; RF += pnl
            need = cq; pnl = 0
            while need > 0:
                lot = st.lots_l[-1]; t = min(need, lot[0]); pnl += d * (px - lot[1]) * t; lot[0] -= t; need -= t
                if lot[0] == 0: st.lots_l.pop()
            st.realized_lifo += pnl; RL += pnl
            st.inv -= cq; closed += cq
            if st.inv == 0: st.dir = 0; st.lots.clear(); st.lots_l.clear()
            oq = q - cq
            if oq > 0: rev += 1
        else: oq = q
        if oq > 0:
            if st.dir == 0: st.dir = sg
            # FIFO and LIFO need separate lot objects (they mutate independently)
            st.lots.append([oq, px]); st.lots_l.append([oq, px]); st.inv += oq; opened += oq
        new = st.inv * st.dir if st.dir else 0
        cp = f['right']
        if old < 0: agg['s' + cp] -= -old
        elif old > 0: agg['l' + cp] -= old
        if new < 0: agg['s' + cp] += -new
        elif new > 0: agg['l' + cp] += new
        agg['n'] += (new != 0) - (old != 0); cash += -sg * q * px
        if roles: R[f['row']] = (cq, oq)
        if snapshots and (k == n - 1 or ordered[k + 1]['ts'] != f['ts']):
            snaps[f['ts']] = dict(agg=(agg['sCE'], agg['sPE'], agg['lCE'], agg['lPE'], agg['n']), cash=cash, opened=opened, closed=closed, rev=rev,
                                  rfifo=RF, rlifo=RL, touched=tuple(sorted((i, S[i].inv * S[i].dir) for i in touched)))
            touched = set()
    inv = {i: s.inv * s.dir if s.dir else 0 for i, s in S.items()}
    return dict(snaps=snaps, inv=inv, roles=R, S=S, totals=dict(opened=opened, closed=closed, rev=rev, cash=cash,
                rfifo=RF, rlifo=RL))
