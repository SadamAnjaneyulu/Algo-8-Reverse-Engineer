"""SYNTHETIC generator: deterministic, seeded test scenarios (mode SYNTHETIC_TEST). Nothing here is Algo 8 data; evidence class SYNTHETIC_TEST_ONLY."""
import random
from ..schema import *

GENERATOR = 'synthetic'; VERSION = '1'; MODE = 'SYNTHETIC_TEST'
BASE_TS = days_from_civil(2026, 1, 5) * 86400 - IST_OFFSET_S + 9 * 3600 + 16 * 60          # 2026-01-05 09:16 IST


def inst(und='NIFTY', expiry='2026-01-08', cp='CE', strike=24000):
    return Instrument(f'{und}|{expiry}|{cp}|{strike}', und, 'NSEFO', 'OPTION', cp, strike, expiry, 65 if und == 'NIFTY' else 20, TICK_PAISE, 'SYNTHETIC')


class Builder:
    def __init__(self, scenario, seed=0): self.scenario = scenario; self.seed = seed; self.ins = {}; self.fills = []; self.n = 0
    def add_inst(self, **k): i = inst(**k); self.ins[i.instrument_id] = i; return i.instrument_id
    def fill(self, iid, ts_off, side, qty, px_paise, parent=None, requested=None, status='Filled', dup=False, module='num', fid=None):
        self.n += 1; fid = fid or f'S{self.n:06d}'; parent = parent or f'syn_{self.n:06d}'
        self.fills.append(Fill(fid, self.n, parent, module, iid, BASE_TS + ts_off, side, qty, px_paise, qty if requested is None else requested, status, dup, MODE, f'synthetic:{self.scenario}:seed={self.seed}')); return fid
    def out(self): return self.ins, self.fills


def open_close_full():
    b = Builder('open_close_full'); i = b.add_inst(); b.fill(i, 0, -1, 130, 10000); b.fill(i, 60, 1, 130, 8000); return b.out()


def partial_close_fifo_lifo_avg():
    """short 65@100, 65@120, 65@140 ; buy back 130@90 : FIFO closes 100 and 120 lots, LIFO 140 and 120, AVG uses the 120 pool"""
    b = Builder('partial_close_lots'); i = b.add_inst()
    for k, p in enumerate((10000, 12000, 14000)): b.fill(i, k * 60, -1, 65, p)
    b.fill(i, 300, 1, 130, 9000); return b.out()


def reversal():
    """long 65 then sell 130: closes 65 and opens a 65 short (reversal)"""
    b = Builder('reversal'); i = b.add_inst(); b.fill(i, 0, 1, 65, 5000); b.fill(i, 30, -1, 130, 6000); b.fill(i, 90, 1, 65, 5500); return b.out()


def duplicate_fill_flagged():
    b = Builder('duplicate_flagged'); i = b.add_inst(); b.fill(i, 0, -1, 65, 10000); b.fill(i, 0, -1, 65, 10000, dup=True); b.fill(i, 60, 1, 65, 9000); return b.out()


def equal_second_mixed_sides():
    """buy and sell of one FLAT contract in the same second: the role of both fills depends on the tie order (documented ambiguity, never resolved)"""
    b = Builder('equal_second_mixed'); i = b.add_inst(); b.fill(i, 60, 1, 65, 9000, fid='S_BUY'); b.fill(i, 60, -1, 65, 9500, fid='S_SELL'); return b.out()      # flat contract: buy-first opens a long and the sell closes it; sell-first opens a short and the buy closes it


def out_of_order_input():
    b = Builder('out_of_order'); i = b.add_inst(); b.fill(i, 120, 1, 65, 9000); b.fill(i, 0, -1, 65, 10000); return b.out()


def partial_fills_one_parent():
    b = Builder('partial_fills'); i = b.add_inst(); b.fill(i, 0, -1, 65, 10000, parent='P1', requested=195, status='PartiallyFilled'); b.fill(i, 5, -1, 65, 10005, parent='P1', requested=195, status='PartiallyFilled')
    b.fill(i, 60, 1, 130, 9000, parent='P2', requested=195, status='PartiallyFilled'); return b.out()                        # P1 and P2 leave unfilled remainders


def expired_unclosed():
    """short 65 in a contract that expires 2026-01-08; the data continue to 2026-01-12 with another contract: remaining units are EXPIRED_UNCLOSED, no settlement P&L"""
    b = Builder('expired_unclosed'); a = b.add_inst(expiry='2026-01-08', strike=24000); c = b.add_inst(expiry='2026-01-15', strike=24100)
    b.fill(a, 0, -1, 65, 10000); b.fill(c, 7 * 86400, -1, 65, 11000); return b.out()


def cut_reentry_195():
    """SYNTHETIC accounting example from the brief (not an Algo 8 assertion): short CE 195, short PE 195, long CE and PE wings; a cut closes 65 short CE by an ACTUAL fill; a re-entry restores 65 by another fill"""
    b = Builder('cut_reentry_195'); ce = b.add_inst(cp='CE', strike=24000); pe = b.add_inst(cp='PE', strike=24000); wce = b.add_inst(cp='CE', strike=24800); wpe = b.add_inst(cp='PE', strike=23200)
    for k in range(3): b.fill(ce, k, -1, 65, 10000 + 50 * k, parent='basketA_ce', requested=195, status='PartiallyFilled' if k < 2 else 'Filled'); b.fill(pe, k, -1, 65, 9000 + 50 * k, parent='basketA_pe', requested=195, status='PartiallyFilled' if k < 2 else 'Filled')
    b.fill(wce, 10, 1, 195, 200, parent='basketA_wce'); b.fill(wpe, 10, 1, 195, 250, parent='basketA_wpe')
    b.fill(ce, 600, 1, 65, 8000, parent='cut1')                      # partial cut fill: 130 short CE remain
    b.fill(ce, 1200, -1, 65, 8500, parent='reentry1')                # re-entry fill: 195 short CE again
    return b.out()


def random_stress(seed=1, n=3000, n_inst=12):
    """seeded random fills with frequent reversals, equal-second ties, flagged duplicates and partial parents; on-tick prices"""
    r = random.Random(seed); b = Builder('random_stress', seed); ids = []
    for k in range(n_inst // 2):
        ids.append(b.add_inst(cp='CE', strike=24000 + 50 * k)); ids.append(b.add_inst(cp='PE', strike=24000 + 50 * k))
    t = 0
    for k in range(n):
        if r.random() < 0.7: t += r.randint(0, 20)
        i = r.choice(ids); side = r.choice((-1, 1)); q = 65 * r.randint(1, 4); px = 5 * r.randint(2, 4000); dup = r.random() < 0.01
        b.fill(i, t, side, q, px, parent=f'rs_{k // 3}', requested=q * 3 if r.random() < 0.3 else q, status='PartiallyFilled' if r.random() < 0.2 else 'Filled', dup=dup)
    return b.out()


SCENARIOS = dict(open_close_full=open_close_full, partial_close_lots=partial_close_fifo_lifo_avg, reversal=reversal, duplicate_flagged=duplicate_fill_flagged, equal_second_mixed=equal_second_mixed_sides,
                 out_of_order=out_of_order_input, partial_fills=partial_fills_one_parent, expired_unclosed=expired_unclosed, cut_reentry_195=cut_reentry_195, random_stress_seed1=lambda: random_stress(1), random_stress_seed7=lambda: random_stress(7, 5000, 20))
