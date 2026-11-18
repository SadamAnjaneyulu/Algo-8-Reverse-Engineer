"""Unit tests for Phase 3 (replacement / re-entry continuity).  python -m pytest analysis/allocation/tests"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AL = os.path.dirname(HERE); AN = os.path.dirname(AL)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine')); sys.path.insert(0, AL)
import numpy as np, pandas as pd
import replacement as rp

D = pd.Timestamp('2026-07-01'); E = pd.Timestamp('2026-07-02')

def row(oid, t, side, label, strike, lots, cp='CE', on_grid=False, is_atm=False, inv_before=0, inv_after=0):
    return dict(oid=oid, und='NIFTY', expiry=E, date=D, cp=cp, strike=strike, side=side, label=label, closing_short=side == 'Buy' and label != 'open', lots=lots,
                t=D + pd.Timedelta(t), tp='num', clock=None, vwap=10., L=10., atm_steps=0. if is_atm else 2., is_atm=is_atm, on_grid=on_grid,
                inv_contract_before=inv_before, inv_contract_after=inv_after, inv_right_before=0, inv_right_after=0)

def frame(rows):
    o = pd.DataFrame(rows).sort_values('t').reset_index(drop=True); o['seq'] = np.arange(len(o)); return o

def test_capacity_split_and_classes():
    o = frame([row('r1', '10:00:00', 'Buy', '8 clock-B rebalance', 24000, 2, inv_before=2, inv_after=0),
               row('s1', '10:00:28', 'Sell', 'open', 24100, 3, is_atm=True, inv_before=0, inv_after=3)])      # 3 lots sold, only 2 bought back
    Lk, U = rp.link(o)
    assert Lk.linked_lots.sum() == 2 and U.lots.sum() == 1                                         # never more replacement than buy-back
    assert U.cls.iloc[0] == 'independent off-grid entry (antecedent capacity exhausted)'
    assert Lk.cls.iloc[0] == 'ATM re-centering' and Lk.window.iloc[0] == '0-30 s'

def test_scheduled_sales_do_not_consume_and_negative_dt_is_rejected():
    o = frame([row('r1', '10:15:30', 'Buy', '1 individual lot stop-loss', 24000, 1, inv_before=1, inv_after=0),
               row('s1', '10:16:05', 'Sell', 'open', 24000, 1, on_grid=True),                              # inside the 10:16 schedule window
               row('s2', '10:17:30', 'Sell', 'open', 24000, 1, inv_before=0, inv_after=1)])
    Lk, U = rp.link(o)
    assert set(U.cls) == {'independent scheduled entry'} and Lk.sale_oid.tolist() == ['s2']
    assert Lk.cls.iloc[0] == 'same-contract re-entry after full closure'                                # contract was flat before the sale
    o2 = o.copy(); o2.loc[o2.oid == 's2', 't'] = D + pd.Timedelta('10:15:00')                              # sale filled BEFORE the buy-back (replay order kept)
    Lk2, U2 = rp.link(o2); assert len(Lk2) == 0

def test_same_contract_full_vs_partial_and_unresolved():
    o = frame([row('r1', '11:00:00', 'Buy', '2 same-contract partial buy-back', 24000, 2, inv_before=4, inv_after=2),
               row('s1', '11:00:20', 'Sell', 'open', 24000, 1, inv_before=2, inv_after=3),
               row('r2', '12:00:00', 'Buy', '4 basket-level reduction', 24000, 1, inv_before=3, inv_after=2),
               row('s2', '12:00:10', 'Sell', 'open', 24000, 1, inv_before=2, inv_after=3),
               row('s3', '13:00:00', 'Sell', 'open', 24050, 1, inv_before=0, inv_after=1)])
    Lk, U = rp.link(o); c = dict(zip(Lk.sale_oid, Lk.cls))
    assert c['s1'] == 'partial position replenishment'                                                  # 1 of 2 bought-back lots re-sold
    assert c['s2'] == 'same-contract replacement'
    assert c['s3'] == 'unresolved association'                                                          # > 15 min: no structural claim (remaining r1 lot)

def test_ambiguity_flag_with_two_competing_contracts():
    o = frame([row('r1', '10:00:00', 'Buy', '4 basket-level reduction', 24000, 1, inv_before=1), row('r2', '10:00:01', 'Buy', '4 basket-level reduction', 24100, 1, inv_before=1),
               row('s1', '10:00:30', 'Sell', 'open', 24200, 1)])
    Lk, U = rp.link(o); assert bool(Lk.ownership_ambiguous.iloc[0]) and Lk.red_oid.iloc[0] == 'r2'       # most recent first

def test_lifecycle_event_types_and_carry():
    o = pd.DataFrame(dict(oid=['e1', 'e2', 'x1', 'x2', 'e3', 'x3'], seq=[0, 1, 2, 3, 4, 5], label=['open', 'open', '1 individual lot stop-loss', '3 side-level reduction', 'open', '6 clock-based exit (final flatten)']))
    t = lambda s: pd.Timestamp(s)
    s = pd.DataFrame(dict(thread='T', entry_oid=['e1', 'e2', 'e3'], exit_oid=['x1', 'x2', 'x3'], entry_t=[t('2026-07-01 10:00'), t('2026-07-01 10:15'), t('2026-07-02 10:30')],
                          exit_t=[t('2026-07-01 11:00'), t('2026-07-02 09:40'), t('2026-07-02 15:14')], entry_via=[None, None, 'REPLACE'], cp='CE', strike=24000, und='NIFTY', expiry=E))
    G = rp.lifecycle(s, o, 'C', 'cheap')
    assert G.event.tolist() == ['OPEN', 'ADD', 'REDUCE', 'CARRY', 'CLOSE', 'REPLACE', 'FINAL CLOSE']
    assert (G.inv_after >= 0).all() and G.inv_after.iloc[-1] == 0
