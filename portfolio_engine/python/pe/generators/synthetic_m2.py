"""SYNTHETIC M2-B scenarios (mode SYNTHETIC_TEST). Quantities need not be lot multiples (e.g. 100 / 130 from the brief); these are accounting tests, not Algo 8 claims."""
from .synthetic import *
from . import synthetic as S


def ab_lots_close():
    """short A 65@100, short B 65@120, buy 65@110: FIFO closes A (+10), LIFO closes B (-10), AVG pool 110 -> 0 and no ownership"""
    b = Builder('ab_lots_close'); i = b.add_inst(); b.fill(i, 0, -1, 65, 10000, parent='A'); b.fill(i, 60, -1, 65, 12000, parent='B'); b.fill(i, 120, 1, 65, 11000, parent='C'); return b.out()


def reversal_100_130():
    """short 100, buy 130 @ : 100 close the short, 30 open a NEW long episode"""
    b = Builder('reversal_100_130'); i = b.add_inst(); b.fill(i, 0, -1, 100, 10000, parent='open'); b.fill(i, 60, 1, 130, 9000, parent='rev'); return b.out()


def multi_cycle_episodes():
    """three openings, partial close, add, partial close, full close, then a fresh episode: episode ids #1 then #2"""
    b = Builder('multi_cycle_episodes'); i = b.add_inst()
    b.fill(i, 0, -1, 65, 10000); b.fill(i, 10, -1, 65, 10500); b.fill(i, 20, -1, 65, 11000); b.fill(i, 100, 1, 65, 9000); b.fill(i, 110, -1, 130, 9500); b.fill(i, 200, 1, 130, 9000); b.fill(i, 210, 1, 195, 8800)
    b.fill(i, 500, -1, 65, 8000); b.fill(i, 510, 1, 65, 7000); return b.out()


def parent_with_partial_fills():
    """one parent, three fills opening the same contract: three OAs, one parent, one decision"""
    b = Builder('parent_partial_fills'); i = b.add_inst(); [b.fill(i, k, -1, 65, 10000 + 5 * k, parent='P1', requested=195, status='PartiallyFilled' if k < 2 else 'Filled') for k in range(3)]; b.fill(i, 100, 1, 195, 9000, parent='P2'); return b.out()


def mixed_parent_two_contracts():
    """parent M opens a short in X (fill 1) and closes a long in Y (fill 2): a MIXED parent that is NOT a reversal"""
    b = Builder('mixed_parent_two_contracts'); x = b.add_inst(strike=24000); y = b.add_inst(strike=24100, cp='PE'); b.fill(y, 0, 1, 65, 5000, parent='L'); b.fill(x, 100, -1, 65, 10000, parent='M'); b.fill(y, 101, -1, 65, 6000, parent='M'); return b.out()


def mixed_parent_reversal():
    """a reversal fill makes its parent MIXED by itself"""
    b = Builder('mixed_parent_reversal'); i = b.add_inst(); b.fill(i, 0, 1, 65, 5000, parent='L'); b.fill(i, 60, -1, 130, 6000, parent='R'); return b.out()


def fifo_lifo_diverge_multi_close():
    """4 shorts at rising prices and three partial buy-backs (100, 60, 80) leaving 20 units: FIFO and LIFO attribute different openings to each closing portion"""
    b = Builder('fifo_lifo_diverge'); i = b.add_inst()
    for k, p in enumerate((10000, 11000, 12000, 13000)): b.fill(i, k * 10, -1, 65, p)
    b.fill(i, 100, 1, 100, 9000); b.fill(i, 110, 1, 60, 9100); b.fill(i, 120, 1, 80, 9200); return b.out()


M2_SCENARIOS = dict(ab_lots_close=ab_lots_close, reversal_100_130=reversal_100_130, multi_cycle_episodes=multi_cycle_episodes, parent_partial_fills=parent_with_partial_fills,
                    mixed_parent_two_contracts=mixed_parent_two_contracts, mixed_parent_reversal=mixed_parent_reversal, fifo_lifo_diverge=fifo_lifo_diverge_multi_close,
                    expired_unclosed=S.expired_unclosed, duplicate_flagged=S.duplicate_fill_flagged, equal_second_mixed=S.equal_second_mixed_sides, random_stress_seed3=lambda: S.random_stress(3, 4000, 16))
