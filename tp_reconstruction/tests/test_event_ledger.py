import os, sys
import numpy as np, pandas as pd, pytest
from conftest import real, tc
import build_event_ledger as bl


@pytest.fixture(scope='module')
def raw(): return bl.load_raw()
@pytest.fixture(scope='module')
def L(raw): return bl.build_ledger(raw)


@real
def test_every_source_row_is_in_the_ledger_exactly_once(raw, L):
    assert len(L) == len(raw) and sorted(L.src_row) == list(range(len(raw))) and L.src_line.min() == 1
    assert L.parent_oid.nunique() == raw[tc.COL['parent_oid']].nunique()


@real
def test_ledger_links_back_to_the_raw_record(raw, L):
    r = L.sample(200, random_state=1)
    assert (raw.loc[r.src_row, tc.COL['parent_oid']].values == r.parent_oid.values).all() and (raw.loc[r.src_row, tc.COL['px_fill']].astype(float).values == r.px_fill.values).all()
    assert (raw.loc[r.src_row, tc.COL['qty_fill']].astype(float).values == r.qty_units.values).all()


@real
def test_price_is_the_per_fill_price_not_the_running_order_average(raw, L):
    assert (L.px_fill == pd.to_numeric(raw[tc.COL['px_fill']]).values[L.src_row]).all()
    multi = L[L.groupby('parent_oid').src_row.transform('size') > 1]
    assert (multi.px_fill != multi.px_order_avg).any()                            # col 18 differs from col 137 somewhere in multi-fill orders
    vw = multi.groupby('parent_oid').apply(lambda g: (g.px_fill * g.qty_units).sum() / g.qty_units.sum(), include_groups=False)
    last = multi.sort_values('seq').groupby('parent_oid').px_order_avg.last(); assert (vw - last).abs().max() < 1e-6      # col 18 on the last fill = order VWAP


@real
def test_partial_fills_are_kept_as_separate_rows(raw, L):
    assert (L.order_status == 'PartiallyFilled').sum() == (raw[tc.COL['status']] == 'PartiallyFilled').sum() > 0
    assert (L.groupby('parent_oid').size() > 1).sum() > 0


@real
def test_chronological_order_and_sequence(L):
    assert L.t_fill.is_monotonic_increasing and (L.seq.values == np.arange(len(L))).all()


@real
def test_contracts_are_never_merged(L):
    k = L.groupby('contract_id').agg(u=('und', 'nunique'), e=('expiry', 'nunique'), s=('strike', 'nunique'), c=('cp', 'nunique')); assert (k == 1).all().all()
    assert L.groupby(['und', 'expiry', 'cp', 'strike']).ngroups == L.contract_id.nunique()


@real
def test_quantities_are_whole_lots_and_units_are_not_rescaled(L):
    assert (L.qty_units % L.lot_units == 0).all() and (L.qty_units > 0).all() and (L.qty_lots == L.qty_units / L.lot_units).all()


@real
def test_execution_time_is_the_fill_epoch_not_the_order_entry_minute(raw, L):
    assert (L.t_fill == pd.to_datetime(pd.to_numeric(raw[tc.COL['epoch_trade']]).values[L.src_row], unit='s') + pd.Timedelta(hours=5, minutes=30)).all()
    assert (L.t_fill != L.order_entry_minute).any()


@real
def test_matches_the_earlier_loader_on_shared_fields(raw, L):
    sys.path.insert(0, os.path.join(tc.REPO, 'analysis'))
    import load as old
    d = old.load().set_index('row'); x = L.set_index('src_row')
    assert (d.loc[x.index, 'qty_fill'].values == x.qty_units.values).all() and (d.loc[x.index, 'strike'].values == x.strike.values).all() and (d.loc[x.index, 'side'].values == x.side.values).all()
    assert (d.loc[x.index, 'epoch_trade'].values == x.epoch.values).all()


@real
def test_duplicate_fills_are_flagged_not_dropped(raw):
    two = pd.concat([raw.iloc[:6], raw.iloc[[2]]], ignore_index=True)        # row 2 appears twice
    L = bl.build_ledger(two)
    assert len(L) == 7 and L.dq_duplicate_fill.sum() == 1


@real
def test_data_quality_report_has_no_unexpected_failures(raw, L):
    R = bl.quality_report(L, raw).set_index('check')
    assert R.loc['duplicate fills (order, trade id, time, qty, price, side, contract)', 'status'] == 'PASS'
    assert R.loc['non-positive or off-tick fill price (col 137)', 'status'] == 'PASS' and R.loc['instrument fields inconsistent with description', 'status'] == 'PASS'
    assert R.loc['charge / brokerage fields in the raw file', 'status'] == 'FLAG'
