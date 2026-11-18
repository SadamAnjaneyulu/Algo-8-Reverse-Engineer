"""M2-F regression tests added after the independent audit (reports/m2f_audit). Each closes a surviving mutant or a coverage gap found by the audit; none changes any delivered output.
Defect ids refer to reports/M2F_DEFECT_REGISTER.md."""
import csv, gzip, hashlib, json, os
import pytest
from conftest import PE, REPO


@pytest.mark.slow
def test_generator_fields_equal_raw_ledger():
    """D-A08 / Track A mutant M11 (a +19800 s shift in the historical generator survived all 127 accounting/lineage tests): compare the engine's fills to the RAW csv columns.
    Raw columns (verified by the audit): 11 side, 12 underlying, 14 strike, 15 expiry, 16 right, 33 quantity, 137 per-fill price (rupees), 161 UTC epoch seconds."""
    import datetime as dt
    from pe.generators import historical as H
    ins, fills, _ = H.generate(REPO); by = {f.source_row_id: f for f in fills}
    raw = list(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'))))
    assert len(by) == len(raw) == 41421
    for i, r in enumerate(raw):
        f = by[i]
        assert f.timestamp_s == int(r[161]) and f.side == (1 if r[11] == 'Buy' else -1) and f.quantity == int(r[33]) and f.price_paise == round(float(r[137]) * 100)
        assert f.instrument_id == f"{r[12]}|{dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat()}|{r[16]}|{int(r[14])}" and f.parent_order_id == r[163]


def test_w3_weight_is_queue_matched_over_wing_quantity():
    """C-02 / Track C mutant M19 (W3 weight = matched / body_qty survived all 33 wing/body tests): the committed W3 weight column must equal queue_matched_units / wing_qty."""
    t = gzip.open(os.path.join(PE, 'reports', 'm2d_data', 'wing_body_links_W3.tsv.gz'), 'rt').read().rstrip('\n').split('\n'); h = t[0].split('\t'); rows = [dict(zip(h, l.split('\t'))) for l in t[1:]]
    assert rows and all(abs(float(r['weight']) - float(r['queue_matched_units']) / float(r['wing_qty'])) < 1e-9 for r in rows)


@pytest.mark.parametrize('stage', ('m2c_data', 'm2d_data'))
def test_committed_manifests_match_files(stage):
    """E-D03 (part): m2c and m2d manifests were only checked by ad-hoc scripts; hash basis is sha256 of the UNCOMPRESSED text."""
    d = os.path.join(PE, 'reports', stage); m = json.load(open(os.path.join(d, 'manifest.json')))
    assert len(m['files']) == 6
    for n, v in m['files'].items():
        text = gzip.open(os.path.join(d, n), 'rt').read(); assert hashlib.sha256(text.encode()).hexdigest() == v['sha256_of_text'] and text.count('\n') - 1 == v['rows'], n
    assert m['source_hashes']['raw_trades_sha256'] == hashlib.sha256(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), 'rb').read()).hexdigest()
