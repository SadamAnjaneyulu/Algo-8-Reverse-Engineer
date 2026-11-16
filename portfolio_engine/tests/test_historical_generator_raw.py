"""D-A08 / D-A02: the historical generator's fills and the ledger verifier are checked against the RAW csv by code that does NOT use any generator code path.

Independence: this file reads Trades_GKOHNP140.csv itself (csv.reader), converts the raw rupee text to integer paise with decimal.Decimal (never float) and compares to the generator output.
Raw columns (M2-F audit): 3 segment, 11 side, 12 underlying, 14 strike, 15 expiry (m/d/Y H:M), 16 right, 33 quantity (units), 137 per-fill price (rupees text), 161 UTC epoch s, 163 parent order id.
A guard test asserts that float truncation (`int(float(px) * 100)`) really differs from the exact paise on this data, so a truncating generator cannot pass.
Mutants executed against these tests are recorded in the remediation report (scratch copies, never committed)."""
import csv, datetime as dt, os
from decimal import Decimal
import pytest
from conftest import REPO

RAW = os.path.join(REPO, 'Trades_GKOHNP140.csv')


def raw_paise(text):
    d = Decimal(text) * 100
    assert d == d.to_integral_value(), text          # every raw price is on the paise grid
    return int(d)


@pytest.fixture(scope='module')
def raw_rows():
    with open(RAW, newline='') as fh: return list(csv.reader(fh))


@pytest.fixture(scope='module')
def generated():
    from pe.generators import historical as H
    ins, fills, src = H.generate(REPO); return ins, fills, src


@pytest.fixture(scope='module')
def ledger_rows():
    """a deterministic in-memory sample of the TP-01 ledger rows as namedtuples, including rows whose float price is truncation-prone"""
    import pandas as pd
    L = pd.read_parquet(os.path.join(REPO, 'tp_reconstruction', 'data', 'fill_event_ledger.parquet'))
    rows = list(L.itertuples(index=False, name='Row'))
    return rows[:300] + rows[20000:20100]


# ------------------------------------------------------------------------------------------------ generator output vs raw (real data)
@pytest.mark.slow
def test_every_generated_fill_equals_the_raw_row_with_exact_decimal_paise(generated, raw_rows):
    ins, fills, _ = generated
    assert len(fills) == len(raw_rows) == 41421 and sorted(f.source_row_id for f in fills) == list(range(41421))
    by = {f.source_row_id: f for f in fills}
    for i, r in enumerate(raw_rows):
        f = by[i]; exp = dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat()
        assert f.price_paise == raw_paise(r[137]), (i, f.price_paise, r[137])
        assert f.timestamp_s == int(r[161]), i
        assert f.side == (1 if r[11] == 'Buy' else -1 if r[11] == 'Sell' else None), i
        assert f.quantity == int(r[33]), i
        assert f.parent_order_id == r[163], i
        assert f.instrument_id == f'{r[12]}|{exp}|{r[16]}|{int(r[14])}', i
        assert f.fill_id == f'F{i:06d}', i


@pytest.mark.slow
def test_instruments_equal_the_raw_contract_fields(generated, raw_rows):
    ins, fills, _ = generated
    want = {}
    for r in raw_rows:
        exp = dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat(); want[f'{r[12]}|{exp}|{r[16]}|{int(r[14])}'] = (r[12], r[3], r[16], int(r[14]), exp)
    assert set(ins) == set(want) and len(ins) == 1674
    for k, v in ins.items(): assert (v.underlying, v.exchange_segment, v.option_type, v.strike, v.expiry) == want[k], k


@pytest.mark.slow
def test_guard_float_truncation_would_differ_from_exact_paise_on_this_data(raw_rows):
    """the test above is only a truncation detector if truncation really changes some prices; count them (hand-checkable: 0.29 rupees * 100 is 28.999999999999996 in binary floating point)"""
    assert int(float('0.29') * 100) == 28 and raw_paise('0.29') == 29
    trunc = sum(1 for r in raw_rows if int(float(r[137]) * 100) != raw_paise(r[137]))
    assert trunc > 0, trunc


# ------------------------------------------------------------------------------------------------ verify_ledger_against_raw: clean pass and corruption
def test_verify_passes_on_the_real_ledger_sample_and_returns_exact_raw_paise(ledger_rows, raw_rows):
    from pe.generators import historical as H
    out = H.verify_ledger_against_raw(REPO, ledger_rows)
    assert len(out) == len(ledger_rows) == 400
    for r in ledger_rows: assert out[int(r.src_row)] == raw_paise(raw_rows[int(r.src_row)][137])


def _corrupt(rows, k, **kw):
    out = list(rows); out[k] = out[k]._replace(**kw); return out


def _verify_error(rows):
    """message of the EngineError raised by verify_ledger_against_raw, or None when it accepted the rows (so a missed corruption is an ASSERTION failure, not a pytest.raises 'DID NOT RAISE' outcome)"""
    from pe.generators import historical as H
    from pe.schema import EngineError
    try: H.verify_ledger_against_raw(REPO, rows)
    except EngineError as e: return str(e)
    return None


def _raises(rows, field):
    msg = _verify_error(rows)
    assert msg is not None, 'verify_ledger_against_raw accepted a corrupted ledger'
    assert field in msg, msg
    return msg


def test_verify_raises_on_a_changed_price(ledger_rows):
    k = 7; r = ledger_rows[k]; msg = _raises(_corrupt(ledger_rows, k, px_fill=r.px_fill + 0.05), 'price (paise)')       # one tick
    assert f'source row {int(r.src_row)}' in msg


def test_verify_raises_on_a_sub_paise_price_perturbation(ledger_rows):
    """float noise is a real change: 1e-9 rupees must not be rounded away"""
    k = 11; _raises(_corrupt(ledger_rows, k, px_fill=ledger_rows[k].px_fill + 1e-9), 'price (paise)')


def test_verify_raises_on_a_truncated_price(ledger_rows):
    """a ledger carrying the truncated paise of 0.29 rupees (28 paise as 0.28) is rejected"""
    k = 3; _raises(_corrupt(ledger_rows, k, px_fill=ledger_rows[k].px_fill - 0.01), 'price (paise)')


def test_verify_raises_on_a_changed_quantity(ledger_rows):
    k = 5; r = ledger_rows[k]; msg = _raises(_corrupt(ledger_rows, k, qty_units=int(r.qty_units) + 65), 'quantity (units)')
    assert f'source row {int(r.src_row)}' in msg


def test_verify_raises_on_a_changed_side(ledger_rows):
    k = 9; r = ledger_rows[k]; msg = _raises(_corrupt(ledger_rows, k, sgn=-int(r.sgn)), 'side')
    assert f'source row {int(r.src_row)}' in msg


def test_verify_raises_on_a_changed_parent_id(ledger_rows):
    k = 13; r = ledger_rows[k]; msg = _raises(_corrupt(ledger_rows, k, parent_oid=str(r.parent_oid) + '0'), 'parent order id')
    assert f'source row {int(r.src_row)}' in msg


def test_verify_raises_on_a_changed_epoch(ledger_rows):
    k = 15; r = ledger_rows[k]; msg = _raises(_corrupt(ledger_rows, k, epoch=int(r.epoch) + 19800), 'epoch seconds')       # the IST/UTC shift of audit mutant M11
    assert f'source row {int(r.src_row)}' in msg


@pytest.mark.parametrize('field,value,label', [('strike', 1, 'strike'), ('cp', 'XX', 'option right'), ('und', 'XX', 'underlying'), ('contract_id', 'NIFTY|2026-01-01|CE|1', 'contract id'), ('segment', 'XX', 'segment')])
def test_verify_raises_on_changed_instrument_fields(ledger_rows, field, value, label):
    _raises(_corrupt(ledger_rows, 17, **{field: value}), label)


def test_verify_raises_on_a_changed_expiry(ledger_rows):
    import pandas as pd
    r = ledger_rows[19]; _raises(_corrupt(ledger_rows, 19, expiry=r.expiry + pd.Timedelta(days=1)), 'expiry')


def test_verify_reports_the_first_mismatching_source_row_regardless_of_input_order(ledger_rows):
    rows = _corrupt(_corrupt(ledger_rows, 250, qty_units=int(ledger_rows[250].qty_units) + 1), 20, qty_units=int(ledger_rows[20].qty_units) + 1)
    msg = _verify_error(list(reversed(rows)))
    assert msg is not None and f'source row {int(ledger_rows[20].src_row)}:' in msg and f'source row {int(ledger_rows[250].src_row)}:' not in msg, msg


def test_verify_raises_on_unknown_or_duplicate_source_rows(ledger_rows):
    msg = _verify_error(_corrupt(ledger_rows, 2, src_row=10 ** 7)); assert msg is not None and 'source row id' in msg
    msg = _verify_error(ledger_rows + ledger_rows[:1]); assert msg is not None and 'duplicate' in msg


def test_exact_paise_helper_never_uses_float_rounding():
    from pe.generators import historical as H
    assert H._paise_exact('0.29') == 29 and H._paise_exact('2.45') == 245 and H._paise_exact('2.455') is None and H._paise_exact('x') is None and H._paise_exact(repr(0.29)) == 29


@pytest.mark.slow
def test_generate_calls_the_verifier_and_refuses_a_corrupted_ledger(monkeypatch):
    """generate() must run the verification: feed it a ledger whose first row has a wrong price and expect EngineError instead of fills"""
    import pandas as pd
    from pe.generators import historical as H
    from pe.schema import EngineError
    real = pd.read_parquet
    def corrupted(path, *a, **k):
        df = real(path, *a, **k); df.loc[df.index[0], 'px_fill'] = df.loc[df.index[0], 'px_fill'] + 0.05; return df
    monkeypatch.setattr(pd, 'read_parquet', corrupted)
    msg = None
    try: H.generate(REPO)
    except EngineError as e: msg = str(e)
    assert msg is not None, 'generate() returned fills from a corrupted ledger'
    assert 'source row 0' in msg and 'price (paise)' in msg, msg
