"""Decision D (owner-approved 2026-11-16): recorded interpretations of the methodology choices, each with a synthetic counterexample or a measurement on the raw ledger.
C2 predecessor = previous parent's last closing fill; stream = underlying x expiry x session; tie-break = smallest CLOSING source row, then parent id; parent identity = raw column 163;
EXPIRED_UNCLOSED stays a schema token (an inference); number-block unresolved; W1 WEAKLY_SUPPORTED, W1_S60 UNRESOLVED, W2 arithmetic weights, W3 arithmetic queue association, protective intent NOT TESTABLE."""
import collections, csv, gzip, json, os
import pytest
from conftest import PE, REPO
from test_closing_batches import make, views_of, sets, CE
from pe import closing_batches as cb
from test_decision_c import quick

CE_NEXT_EXPIRY = ('CE', 24000, '2026-01-15', 'NIFTY')                  # same underlying, different expiry
SENSEX_CE = ('CE', 80000, '2026-01-08', 'SENSEX')


def test_same_underlying_different_expiry_are_never_joined():
    ls, _ = make([('open', CE, 0, 65, 'o1'), ('open', CE_NEXT_EXPIRY, 0, 65, 'o2'), ('close', CE, 100, 65, 'A'), ('close', CE_NEXT_EXPIRY, 101, 65, 'B')]); parents, un, V = quick(ls)
    assert sets(V[('C1', 10)]) == [['A'], ['B']]            # 1 s apart, same underlying, but different expiry streams


def test_same_underlying_and_expiry_different_session_are_never_joined():
    """the synthetic base is 09:16 IST on its day; the next IST midnight is 53,040 s later. A closes 3 s before it, B 2 s after it: 5 s apart (inside every threshold) but in different IST sessions."""
    ls, _ = make([('open', CE, 0, 130, 'o'), ('close', CE, 53037, 65, 'A'), ('close', CE, 53042, 65, 'B')]); parents, un, V = quick(ls)
    assert sorted(p.session for p in parents) != [parents[0].session] * 2 and sets(V[('C1', 60)]) == [['A'], ['B']] and sets(V[('C2', 60)]) == [['A'], ['B']]
    ls2, _ = make([('open', CE, 0, 130, 'o'), ('close', CE, 53030, 65, 'A'), ('close', CE, 53035, 65, 'B')]); parents2, un2, V2 = quick(ls2); assert sets(V2[('C1', 10)]) == [['A', 'B']]          # same 5 s inside one session: joined


def test_different_underlying_are_never_joined():
    ls, _ = make([('open', CE, 0, 65, 'o1'), ('open', SENSEX_CE, 0, 20, 'o2'), ('close', CE, 100, 65, 'A'), ('close', SENSEX_CE, 101, 20, 'B')]); parents, un, V = quick(ls)
    assert sets(V[('C1', 10)]) == [['A'], ['B']]


def test_multiple_closing_fills_in_one_parent_form_one_unit_with_first_and_last_second():
    ls, _ = make([('open', CE, 0, 195, 'o'), ('close', CE, 100, 65, 'A'), ('close', CE, 107, 65, 'A'), ('close', CE, 112, 65, 'B')]); parents, un, V = quick(ls)
    a = next(p for p in parents if p.parent_id == 'A'); assert (a.first_ts, a.last_ts, a.qty) == (a.first_ts, a.first_ts + 7, 130)
    assert sets(V[('C1', 10)]) == [['A'], ['B']] and sets(V[('C2', 10)]) == [['A', 'B']]    # C1: 112 - 100 = 12 > 10 separate; C2: 112 - last 107 = 5 <= 10 joined (the C2 predecessor reference is the previous parent's LAST closing fill)


def test_equal_first_seconds_are_ordered_by_the_smallest_CLOSING_source_row_not_by_an_earlier_opening_row():
    """X opens at row 0 (its smallest source row overall) and closes at row 3; Y closes at row 2. Both first-close at second 100. Smallest CLOSING row: Y (2) before X (3)."""
    ls, _ = make([('open', CE, 0, 130, 'X'), ('open', CE, 0, 130, 'o2'), ('close', CE, 100, 65, 'Y'), ('close', CE, 100, 65, 'X')]); parents, un, V = quick(ls)
    assert [p.parent_id for p in V[('C1', 10)]['batches'][0]['members']] == ['Y', 'X']


def test_tiebreak_uses_the_SMALLEST_closing_row_of_a_parent_with_several_closing_fills():
    """X closes at rows 1 and 4, Y at rows 2 and 3 (all in second 100): smallest closing rows X=1 < Y=2 -> [X, Y]; the largest rows would give Y=3 < X=4 -> [Y, X]"""
    ls, _ = make([('open', CE, 0, 260, 'o'), ('close', CE, 100, 65, 'X'), ('close', CE, 100, 65, 'Y'), ('close', CE, 100, 65, 'Y'), ('close', CE, 100, 65, 'X')]); parents, un, V = quick(ls)
    assert [p.parent_id for p in V[('C1', 10)]['batches'][0]['members']] == ['X', 'Y']


def test_parent_identity_is_the_raw_column_163_and_column_4_is_reused_across_parents():
    rows = list(csv.reader(open(os.path.join(REPO, 'Trades_GKOHNP140.csv'), newline=''))); p163 = collections.defaultdict(set); ono = collections.defaultdict(set)
    for r in rows: p163[r[163]].add(r[4]); ono[r[4]].add(r[163])
    assert (len(rows), len(p163), len(ono)) == (41421, 39874, 37258)                 # parents by column 163 vs distinct order numbers (column 4)
    assert sum(1 for v in ono.values() if len(v) > 1) == 2224 and max(len(v) for v in ono.values()) == 6 and all(len(v) == 1 for v in p163.values())     # an order number is shared by up to 6 parents; a parent has exactly one order number
    ls, _ = make([('open', CE, 0, 130, 'P1'), ('close', CE, 100, 65, 'P1'), ('close', CE, 100, 65, 'P2')]); parents, un, V = quick(ls); assert sorted(p.parent_id for p in parents) == ['P1', 'P2']
    sch = open(os.path.join(PE, 'docs', 'SCHEMAS.md')).read(); assert 'raw column **163**' in sch and '37,258' in sch and '39,874' in sch and 'up to 6 parents' in sch      # the data dictionary states the choice and the alternative count


def test_expired_unclosed_remains_a_schema_token_and_is_documented_as_an_inference():
    src = open(os.path.join(PE, 'python', 'pe', 'lineage.py')).read(); assert 'EXPIRED_UNCLOSED' in src
    doc = open(os.path.join(PE, 'docs', 'BASKET_GROUPING_METHODOLOGY.md')).read(); i = doc.index('Decision D'); assert 'inferred from the expiry date and missing closing fills' in doc[i:] and 'no settlement' in doc[i:].lower()


@pytest.mark.parametrize('method,klass,must_not', [('W1', 'WEAKLY_SUPPORTED', 'EXPLICIT'), ('W1_S60', 'UNRESOLVED', 'WEAKLY'), ('W2', 'WEAKLY_SUPPORTED', 'allocation'), ('W2_S60', 'UNRESOLVED', 'WEAKLY'), ('W3', 'UNRESOLVED', 'WEAKLY')])
def test_delivered_wing_body_rows_carry_the_approved_conservative_classes(method, klass, must_not):
    t = gzip.decompress(open(os.path.join(PE, 'reports', 'm2d_data', f'wing_body_links_{method}.tsv.gz'), 'rb').read()).decode().split('\n'); h = t[0].split('\t'); rows = [l.split('\t') for l in t[1:] if l]
    ec = {r[h.index('evidence_class')] for r in rows}; assert len(ec) == 1 and next(iter(ec)).startswith(klass) and must_not not in next(iter(ec)), ec
    assert {r[h.index('protective_link')] for r in rows} == {'UNRESOLVED'} and {r[h.index('claim_type')] for r in rows} == {'ATTRIBUTION'} and all(r[h.index('membership_provenance')].startswith('INFERRED:WING_BODY:') for r in rows)
    if method in ('W2', 'W2_S60'): assert 'weights arithmetic' in next(iter(ec))


def test_tag_based_scope_exclusions_reconcile_with_the_total_units_so_the_denominators_are_explicit():
    """opening units 1,414,545 = tagged wing 617,130 + tagged body 626,765 + excluded 170,650; closing units 1,377,065 = tagged wing 500,775 + tagged body 540,250 + excluded 336,040"""
    S = json.load(open(os.path.join(PE, 'reports', 'm2d_data', 'm2d_summary.json'))); ex = S['scope_exclusions_TAGGED_units']; cov = S['coverage']
    ex_open = sum(v for k, v in ex.items() if k.startswith('OPENING')); ex_close = sum(v for k, v in ex.items() if k.startswith('CLOSING'))
    assert (ex_open, ex_close) == (170650, 336040)
    assert cov['OPENING|W1']['wing_units'] + cov['OPENING|W1']['body_units'] + ex_open == 1414545
    assert cov['CLOSING|W1']['wing_units'] + cov['CLOSING|W1']['body_units'] + ex_close == 1377065
