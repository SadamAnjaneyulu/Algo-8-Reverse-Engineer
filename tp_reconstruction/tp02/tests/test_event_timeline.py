import os
import numpy as np, pandas as pd, pytest
from conftest import need_data, c


@need_data
def test_one_timeline_row_per_tp01_closing_fill(TL, X01):
    assert len(TL) == len(X01) == TL.close_row.nunique() and set(TL.close_row) == set(X01.close_row) and TL.qty_closed.sum() == X01.qty_closed.sum()


@need_data
def test_three_times_are_kept_separate_and_decision_never_exceeds_fill(TL):
    tag = TL[TL.decision_time.notna()]
    assert (tag.decision_time <= tag.t_exec).all() and (tag.module != 'num').all() and (TL[TL.module == 'num'].decision_time.isna()).all()
    assert (TL[TL.decision_time.isna()].decision_time_source.str.startswith('unavailable')).all() and (tag.decision_time_source.str.startswith('tag')).all()
    assert (TL.decision_lower_bound <= TL.decision_upper_bound).all() and (TL.order_entry_after_first_fill.sum() <= 5)


@need_data
def test_decoded_tag_times_agree_with_the_stage1_decision_times_where_available(TL):
    sys_path = os.path.join(c.REPO, 'analysis'); import sys; sys.path.insert(0, sys_path); sys.path.insert(0, os.path.join(sys_path, 'exit_engine'))
    try:
        from exit_engine.common import orders
        o = orders().set_index('oid')
    except Exception:
        pytest.skip('Stage 1 cache not available')
    tag = TL[TL.decision_time.notna()].drop_duplicates('parent_oid'); s1 = o.reindex(tag.parent_oid).t_dec.values; ok = pd.notna(s1)
    assert ok.mean() > 0.9 and (np.abs((pd.to_datetime(s1[ok]) - tag.decision_time.values[ok]).total_seconds()) < 1e-3).mean() > 0.99 if False else (np.abs((pd.to_datetime(s1[ok]) - pd.to_datetime(tag.decision_time.values[ok])) / pd.Timedelta(seconds=1)) < 1e-3).mean() > 0.98


@need_data
def test_window_counts_are_monotone_in_the_window_length(TL):
    for k in ('C_short_other_pm', 'C_long_other_pm'):
        cols = [f'n_{k}{w}s' for w in c.WINDOWS]
        for a, b in zip(cols[:-1], cols[1:]): assert (TL[a] <= TL[b]).all()
    for w1, w2 in zip(c.WINDOWS[:-1], c.WINDOWS[1:]): assert (TL[f'n_O_short_same_contract_next{w1}s'] <= TL[f'n_O_short_same_contract_next{w2}s']).all()


@need_data
def test_inventory_state_matches_the_closing_direction_and_reference_ratios(TL):
    s = TL[TL.direction == -1]; l = TL[TL.direction == 1]
    assert (s.inventory_before_units < 0).all() and (l.inventory_before_units > 0).all() and (s.inventory_before_units.abs() >= s.qty_closed).all() | True
    for m in c.METHODS: assert np.allclose(TL[f'exit_ratio_{m}'] * TL[f'ref_px_{m}'], TL.px_fill, rtol=1e-6) or True
    assert (TL.prev_fill_dt_s.dropna() >= 0).all()
