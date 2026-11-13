"""PortfolioState: the only place where executed inventory changes (apply_fill). Pure standard library; mirrors cpp/include/pe/ledger.hpp rule for rule.
Role rule: a fill is decided ONLY by the net inventory of its own instrument: against the inventory it closes min(q, |inv|) and the excess opens the opposite direction (a reversal);
with the inventory or flat it opens. Policies / proposals never call this; an order intent is not a fill."""
from collections import deque
from .schema import *


class _Inst:
    __slots__ = ('dir', 'inv', 'lots', 'pool_q', 'pool_px', 'opened', 'closed', 'realized', 'ep_n', 'eid', 'traded')
    def __init__(self, avg): self.dir = 0; self.inv = 0; self.lots = deque(); self.pool_q = 0; self.pool_px = 0.0; self.opened = 0; self.closed = 0; self.realized = 0.0 if avg else 0; self.ep_n = 0; self.eid = None; self.traded = False


class Role:
    __slots__ = ('fill_id', 'instrument_id', 'close_qty', 'open_qty', 'inventory_after', 'is_reversal', 'episode_closed', 'episode_opened')
    def __init__(self, **k):
        for a in self.__slots__: setattr(self, a, k.get(a))


class PortfolioState:
    def __init__(self, method, instruments):
        assert method in METHODS
        self.method = method; self.avg = method == 'AVG'; self.instruments = instruments; self.s = {}; self.episodes = {}
        self.opened = 0; self.closed = 0; self.reversal_fills = 0; self.reversal_units_reopened = 0; self.cash = 0; self.applied = 0
        self.agg = dict(short_CE=0, short_PE=0, long_CE=0, long_PE=0, open_instruments=0)
        self.applied_ids = set()

    # ------------------------------------------------------------------ aggregates (maintained from signed inventory deltas)
    def _agg_change(self, iid, old, new):
        cp = self.instruments[iid].option_type
        if old < 0: self.agg[f'short_{cp}'] -= -old
        elif old > 0: self.agg[f'long_{cp}'] -= old
        if new < 0: self.agg[f'short_{cp}'] += -new
        elif new > 0: self.agg[f'long_{cp}'] += new
        self.agg['open_instruments'] += (new != 0) - (old != 0)

    def _episode(self, iid, direction, ts, reversal):
        st = self.s[iid]; st.ep_n += 1; eid = f'{iid}#{st.ep_n}'
        self.episodes[eid] = dict(episode_id=eid, direction=direction, opened=0, closed=0, realized=0.0 if self.avg else 0, ended_by='open', n_open_fills=0, n_close_fills=0, started_by_reversal=reversal)
        return eid

    def apply_fill(self, f):
        """apply one non-duplicate fill exactly once; returns its Role"""
        if f.fill_id in self.applied_ids: raise InvariantViolation(f'fill {f.fill_id} applied twice')
        self.applied_ids.add(f.fill_id)
        iid = f.instrument_id; st = self.s.get(iid)
        if st is None: st = self.s[iid] = _Inst(self.avg)
        st.traded = True; q = f.quantity; sg = f.side; px = f.price_paise; old_signed = st.inv * st.dir if st.dir else 0
        close_q = 0; open_q = 0; eid_close = None; eid_open = None; reversal = False; m = self.method
        if st.dir != 0 and sg == -st.dir:                                        # against the inventory: close
            close_q = min(q, st.inv); eid_close = st.eid; ep = self.episodes[eid_close]; d = st.dir
            if m == 'AVG':
                pnl = d * (px - st.pool_px) * close_q; st.pool_q -= close_q
            else:
                need = close_q; pnl = 0
                while need > 0:
                    lot = st.lots[0] if m == 'FIFO' else st.lots[-1]; take = min(need, lot[0]); pnl += d * (px - lot[1]) * take; lot[0] -= take; need -= take
                    if lot[0] == 0: st.lots.popleft() if m == 'FIFO' else st.lots.pop()
            st.realized += pnl; ep['realized'] += pnl; st.inv -= close_q; st.closed += close_q; self.closed += close_q; ep['closed'] += close_q; ep['n_close_fills'] += 1
            if st.inv == 0:
                ep['ended_by'] = 'flat' if q == close_q else 'reversal'; st.dir = 0; st.lots.clear(); st.pool_q = 0; st.pool_px = 0.0
            open_q = q - close_q
            if open_q > 0: reversal = True
        else: open_q = q
        if open_q > 0:
            if st.dir == 0: st.dir = sg; st.eid = self._episode(iid, sg, f.timestamp_s, reversal)
            eid_open = st.eid; ep = self.episodes[eid_open]
            if m == 'AVG': st.pool_px = (st.pool_px * st.pool_q + px * open_q) / (st.pool_q + open_q); st.pool_q += open_q
            else: st.lots.append([open_q, px])
            st.inv += open_q; st.opened += open_q; self.opened += open_q; ep['opened'] += open_q; ep['n_open_fills'] += 1
        if reversal: self.reversal_fills += 1; self.reversal_units_reopened += open_q
        new_signed = st.inv * st.dir if st.dir else 0
        self._agg_change(iid, old_signed, new_signed); self.cash += -sg * q * px; self.applied += 1
        if close_q > q or close_q + open_q != q or (st.dir and st.inv <= 0): raise InvariantViolation(f'role arithmetic broken on {f.fill_id}')
        return Role(fill_id=f.fill_id, instrument_id=iid, close_qty=close_q, open_qty=open_q, inventory_after=new_signed, is_reversal=reversal, episode_closed=eid_close, episode_opened=eid_open)

    # ------------------------------------------------------------------ views
    def signed_inventory(self, iid):
        st = self.s.get(iid); return st.inv * st.dir if st and st.dir else 0

    def book_value(self, iid):
        """premium collected on open shorts minus premium paid on open longs (paise x units); int for FIFO/LIFO, float for AVG"""
        st = self.s.get(iid)
        if not st or not st.dir: return 0.0 if self.avg else 0
        v = st.pool_q * st.pool_px if self.avg else sum(l[0] * l[1] for l in st.lots)
        return v if st.dir < 0 else -v

    def realized_total(self):
        t = 0.0 if self.avg else 0                      # explicit left-to-right loop over sorted ids: Python >= 3.12 sum() compensates float sums, the C++ core does not
        for i in sorted(self.s): t += self.s[i].realized
        return t

    def book_total(self):
        t = 0.0 if self.avg else 0
        for i in sorted(self.s): t += self.book_value(i)
        return t
