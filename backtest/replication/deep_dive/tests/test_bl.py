"""Body lifecycle (D-1 / D0) tests: invariants of the event tables, class definitions, and the structural results the report relies on (wide margins, not fitted thresholds). Needs the committed outputs."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import bl_common as C
OUT = C.OUT


def test_events_columns_and_order():
    for nm in ('d1', 'd0'):
        E = pd.read_csv(f'{OUT}/bl_events_{nm}.csv')
        assert {'time_IST', 'module', 'cls', 'right', 'side', 'strike', 'lots', 'strike_minus_ATMprev_steps', 'contract_net_after', 'S_after', 'L_after'} <= set(E.columns)
        for _, g in E.groupby(['und', 'expiry']): assert g.time_IST.is_monotonic_increasing
        assert (E.lots > 0).all() and E.side.isin(['Buy', 'Sell']).all()


def test_contract_net_is_cumulative_across_days():
    E = pd.concat([pd.read_csv(f'{OUT}/bl_events_d1.csv'), pd.read_csv(f'{OUT}/bl_events_d0.csv')]); g = E[(E.und == 'NIFTY') & (E.expiry == '2026-06-30')]
    for (cp, k), h in g.groupby(['right', 'strike']):
        assert (h.contract_net_after.values == np.cumsum(np.where(h.side == 'Buy', h.lots, -h.lots))).all()


def test_slot_minute_definition_and_partition():
    O = C.load_orders(); S = O[(O.module == 'num') & (O.role == 'open_short')]
    assert set(S.cls) == {'slot_minute', 'minute_before_slot', 'roll_sell', 'other'}
    sm = S[S.cls == 'slot_minute']; assert (((sm.tod - (9 * 3600 + 16 * 60)) // 60) % 15 == 0).all()
    assert O[O.module != 'num'].cls.isin(['hedge', 'stop', 'lump', 'manual']).all()


def test_previous_minute_reference_beats_current():
    O = C.load_orders(); sm = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0) & (O.cls == 'slot_minute')]
    assert (sm.strike == sm.atm_prev).mean() > (sm.strike == sm.atm_cur).mean() + 0.05
    d = sm[sm.atm_prev != sm.atm_cur]; assert (d.strike == d.atm_prev).mean() > 2 * (d.strike == d.atm_cur).mean()


def test_scheduled_entries_far_more_atm_than_other():
    A = pd.read_csv(f'{OUT}/bl_d1_A_class.csv').set_index('cls'); assert A.exact_prev['slot_minute'] > 0.75 and A.exact_prev['other'] < 0.35


def test_flatten_break_is_sharp():
    F = pd.read_csv(f'{OUT}/bl_d0_D_flatten_by_cycle.csv'); pre = F[F.d0 <= '2026-08-20']; post = F[F.d0 >= '2026-08-25']
    assert pre.share_1514.max() < 0.1 and post.share_1514.min() > 0.4 and len(pre) >= 10 and len(post) >= 8
    cs = pd.read_csv(f'{OUT}/bl_d0_D_close_shares.csv'); post_rows = cs[cs.post == True]; assert (post_rows.share_closed_1514_1515 > 0.95).all()


def test_d0_sells_mostly_at_existing_short_strikes():
    J = json.load(open(f'{OUT}/bl_summary_d0a.json')); assert J['status_share']['new_strike'] < 0.2 and J['status_share']['carried_strike'] + J['status_share']['existing_short_strike'] > 0.8


def test_overnight_inventory_nonempty_and_carry_share():
    J = json.load(open(f'{OUT}/bl_summary_d1b.json')); assert 0.5 < J['lots_carried'] / J['lots_sold'] < 0.9 and J['zero_short_cycles'] == 0


def test_report_sections():
    t = open(os.path.join(C.REP, 'BODY_LIFECYCLE_D1_D0_INVESTIGATION.md')).read()
    for h in ['## 1. Executive summary', '## 2. ATM reference', '## 3. D-1 study', '### 3A', '### 3B', '### 3C', '### 3D', '### 3E', '### 3F', '## 4. D0 study', '### 4A', '### 4B', '### 4C', '### 4D', '### 4E', '### 4F', '## 5. Deliverables', '## 6. Observed', '## 7. D-1 lifecycle model', '## 8. D0 lifecycle model']: assert h in t, h
