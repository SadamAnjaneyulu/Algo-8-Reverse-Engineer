"""Unit tests for the allocation-level reconstruction (analysis/allocation).  python -m pytest analysis/allocation/tests"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AL = os.path.dirname(HERE); AN = os.path.dirname(AL)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, AL)
import numpy as np, pandas as pd
import alloc, falsify

def T(s): return pd.Timestamp('2026-07-01 ' + s)

def test_slot_windows():
    assert alloc.slot_of(T('09:16:00'))[0] == 0
    assert alloc.slot_of(T('09:15:58'))[0] == 0            # lineage X window opens 2 s early
    assert alloc.slot_of(T('09:15:57'))[0] == -1
    assert alloc.slot_of(T('09:18:59'))[0] == 0 and alloc.slot_of(T('09:19:00'))[0] == -1
    assert alloc.slot_of(T('10:15:58'))[0] == 4 and alloc.slot_of(T('10:16:00'))[0] == 4
    assert alloc.slot_of(T('10:05:00'))[0] == -1            # off-grid ("extra")
    assert alloc.slot_of(T('09:15:30'))[0] == -1

def test_bursts_gap_rule():
    t = [T('09:16:00'), T('09:16:03'), T('09:16:07'), T('09:16:12'), T('09:16:13')]   # gaps 3, 4, 5, 1  -> a new burst only after the 5 s gap
    s = pd.DataFrame(dict(und='NIFTY', date=pd.Timestamp('2026-07-01'), t_fill=t, oid=range(5)))
    b = alloc.bursts_from_sells(s)
    assert b.burst.tolist() == [1, 1, 1, 2, 2]

def test_chain_detection_finds_a_repeating_phase_and_not_noise():
    # a burst at phase 100 s in 6 different quarter-hours, plus scattered noise bursts
    rng = np.random.default_rng(1); sec = [100 + 900 * q for q in range(6)] + list(rng.uniform(0, 5400, 6))
    b = pd.DataFrame(dict(date=pd.Timestamp('2026-07-01'), sec=sec)); out = alloc.detect_chains(b)
    assert (out.chain.iloc[:6] >= 0).all() and out.chain.iloc[:6].nunique() == 1
    rn = np.random.default_rng(2); noise = pd.DataFrame(dict(date=pd.Timestamp('2026-07-01'), sec=rn.uniform(0, 20000, 10)))
    assert (alloc.detect_chains(noise).chain >= 0).sum() == 0

def test_reference_prices():
    arr = dict(nk=2, ki=np.array([0, 0, 0, 1]), px=np.array([10., 20., 30., 5.]), t0=np.array([1, 2, 3, 4]),
               slot=np.array([0, 0, 1, 2]), chain=np.array([0, 1, 2, 3]))
    R = falsify.refs_at(arr, np.ones(4, bool), None)
    assert R['lot_min (cheapest open lot)'][0] == 10 and R['lot_max (negative control)'][0] == 30
    assert R['contract_wavg (aggregate)'][0] == 20 and R['lot_newest'][0] == 30
    assert R['slot_min (min of slot-allocation avg entry)'][0] == 15     # slot 0 holds lots 10 and 20 -> average 15; slot 1 holds 30
    assert R['chain_min (min of chain-allocation avg entry)'][0] == 10
    assert R['lot_min (cheapest open lot)'][1] == 5
    R2 = falsify.refs_at(arr, np.array([False, True, True, False]), None)     # only the 20 and 30 lots open
    assert R2['lot_min (cheapest open lot)'][0] == 20 and np.isnan(R2['lot_min (cheapest open lot)'][1])

def test_allocation_ids_cover_every_entry_and_lots_are_conserved():
    """On the real clean data: every entry order has all three ids; lot ledger lots == lot-book lots; short lots keep their allocation."""
    from common import orders, replay_book
    o = orders(); A = alloc.build_allocations(o)
    e = o[o.label == 'open']
    assert len(A) == len(e) and set(A.oid) == set(e.oid)
    assert A.alloc_slot.notna().all() and A.alloc_chain.notna().all() and A.alloc_lot.notna().all()
    L = alloc.lot_ledger('cheap', A); assert len(L) == len(replay_book('cheap'))
    assert L.alloc_slot.notna().all() and (L.alloc_slot == 'nonentry').mean() < 0.01      # lots opened by close-labelled orders (flips)
    sh = A[A.role == 'short']; assert (sh.alloc_slot != 'unlinked').all() and (sh.alloc_chain != 'unlinked').all()
    # lots sold in one order stay in one allocation under every definition
    assert (sh.groupby('oid').alloc_slot.nunique() == 1).all()
