"""M2-F defect B-04: independent, hand-calculated tests of the closing-batch REPORTING layer (summarize rows, total_closing_qty, join_gap_s, batch numbering / batch ids).

Every expected number below is calculated by hand from the scenario in the comments; nothing is produced by running the code under test, and no committed output is read.

SCENARIO (all closing fills are BUYS that close one short position of a CE contract; units are arbitrary but all different so that a dropped or double-counted portion changes a total).
Stream X1 = (NIFTY, expiry 2026-01-08, session 2026-01-05, contract CE 24000). Twelve closing parents, listed as  parent: fills (offset seconds from BASE_TS, qty)  ->  first_ts / last_ts / qty
  A: (100,10)               first 100 last 100 qty 10
  B: (100,20)               first 100 last 100 qty 20     (same second as A; B comes after A in the source rows)
  C: (102,5) (110,7)        first 102 last 110 qty 12     (two closing portions)
  D: (105,30)               first 105 last 105 qty 30
  E: (110,4)                first 110 last 110 qty 4
  F: (116,8)                first 116 last 116 qty 8
  G: (126,4) (130,5)        first 126 last 130 qty 9      (two closing portions)
  H: (137,11)               first 137 last 137 qty 11
  I: (167,13)               first 167 last 167 qty 13
  J: (198,14)               first 198 last 198 qty 14
  K: (258,15)               first 258 last 258 qty 15
  L: (319,16)               first 319 last 319 qty 16
Stream X2 = (NIFTY, 2026-01-08, session 2026-01-06, same contract): U1 (86400+100, 17), U2 (86400+104, 18)  (next IST day => other session)
Stream X3 = (NIFTY, expiry 2026-01-15, session 2026-01-05, contract CE 24000 of the later expiry): T1 (100, 6), T2 (101, 7)
Streams are ordered (underlying, expiry, session): X1 < X2 < X3. Parents: 12 + 2 + 2 = 16. Closing portions: 14 (X1: A1 B1 C2 D1 E1 F1 G2 H1 I1 J1 K1 L1 = 14) + 2 + 2 = 18. Adjacent pairs: 11 + 1 + 1 = 13.
(Opening: 200 short in X1 covers 162 + 35 = 197 closed; 20 short in X3 covers 13.)

C1 gap of an adjacent pair = first(next) - first(prev):
  X1: A>B 0, B>C 2, C>D 105-102=3, D>E 110-105=5, E>F 116-110=6, F>G 126-116=10, G>H 137-126=11, H>I 167-137=30, I>J 198-167=31, J>K 258-198=60, K>L 319-258=61;  X2: 104-100=4;  X3: 101-100=1
  sorted: 0 1 2 3 4 5 6 10 11 30 31 60 61
C2 gap of an adjacent pair = first(next) - last(prev):
  X1: A>B 100-100=0, B>C 102-100=2, C>D 105-110=-5, D>E 110-105=5, E>F 116-110=6, F>G 126-116=10, G>H 137-130=7, H>I 30, I>J 31, J>K 60, K>L 61;  X2 4;  X3 1
  sorted: -5 0 1 2 4 5 6 7 10 30 31 60 61
"""
import pytest
from pe import closing_batches as cb
from pe.generators.synthetic import BASE_TS
from test_closing_batches import make, views_of, sets, CE

CE_LATER = ('CE', 24000, '2026-01-15', 'NIFTY')
DAY = 86400
X1 = ('2026-01-08', '2026-01-05'); X2 = ('2026-01-08', '2026-01-06'); X3 = ('2026-01-15', '2026-01-05')
TOKEN = {'C1': 'CB_FIRST_FILL_GAP', 'C2': 'CB_LAST_TO_FIRST_GAP'}
THR = (2, 5, 10, 30, 60)


def scenario():
    spec = [('open', CE, 0, 200, 'oX'), ('open', CE_LATER, 0, 20, 'oT'),
            ('close', CE, 100, 10, 'A'), ('close', CE, 100, 20, 'B'), ('close', CE, 102, 5, 'C'), ('close', CE, 110, 7, 'C'), ('close', CE, 105, 30, 'D'), ('close', CE, 110, 4, 'E'), ('close', CE, 116, 8, 'F'),
            ('close', CE, 126, 4, 'G'), ('close', CE, 130, 5, 'G'), ('close', CE, 137, 11, 'H'), ('close', CE, 167, 13, 'I'), ('close', CE, 198, 14, 'J'), ('close', CE, 258, 15, 'K'), ('close', CE, 319, 16, 'L'),
            ('close', CE, DAY + 100, 17, 'U1'), ('close', CE, DAY + 104, 18, 'U2'), ('close', CE_LATER, 100, 6, 'T1'), ('close', CE_LATER, 101, 7, 'T2')]
    ls, _ = make(spec); parents, un, multi, V = views_of(ls)
    assert un == [] and multi == [] and len(parents) == 16                                               # sanity of the fixture itself (16 parents counted by hand above)
    return ls, parents, V


@pytest.fixture(scope='module')
def sc(): return scenario()


# ---------------------------------------------------------------------------------------------------------------------------- summarize rows
# per (method, threshold): batches, singleton_batches, pairs_linked, pairs_gap_exactly_threshold, pairs_gap_threshold_plus_1s, largest batch (parents), longest batch duration (s)
# batches = parents - links = 16 - pairs_linked (every linked adjacent pair removes exactly one batch boundary).
#
# C1 gaps: 0 1 2 3 4 5 6 10 11 30 31 60 61
#  g=2 : linked = {0,1,2} = 3; ==2: one (B>C); ==3: one (C>D); batches 16-3 = 13. X1 breaks after A-B-C then D,E,F,G,H,I,J,K,L alone -> {A,B,C} + 9 singles; X2 4>2 -> 2 singles; X3 1<=2 -> 1 pair.
#          singletons 9 + 2 = 11; largest batch 3 (A,B,C); longest duration: A,B,C first 100 max last 110 = 10.
#  g=5 : linked = {0,1,2,3,4,5} = 6; ==5: one (D>E); ==6: one (E>F); batches 10. X1 {A..E}, F,G,H,I,J,K,L (7 singles); X2 4<=5 joined; X3 joined. singletons 7; largest 5; longest: {A..E} 110-100 = 10 (X2 batch is 4).
#  g=10: linked = {0,1,2,3,4,5,6,10} = 8; ==10: one (F>G); ==11: one (G>H); batches 8. X1 {A..G}, H,I,J,K,L (5 singles). singletons 5; largest 7; longest {A..G}: last 130 - 100 = 30.
#  g=30: linked = 8 + {11, 30} = 10; ==30: one (H>I); ==31: one (I>J); batches 6. X1 {A..I}, J,K,L. singletons 3; largest 9; longest {A..I}: 167 - 100 = 67.
#  g=60: linked = 10 + {31, 60} = 12; ==60: one (J>K); ==61: one (K>L); batches 4. X1 {A..K}, L. singletons 1; largest 11; longest {A..K}: 258 - 100 = 158.
# C2 gaps: -5 0 1 2 4 5 6 7 10 30 31 60 61
#  g=2 : linked = {-5,0,1,2} = 4; ==2: one (B>C); ==3: none; batches 12. X1: A-B-C-D chained (C>D gap -5), E..L alone (8 singles) ; X2 2 singles; X3 pair. singletons 10; largest 4; longest {A..D}: max last 110 - 100 = 10.
#  g=5 : linked = {-5,0,1,2,4,5} = 6; ==5: one (D>E); ==6: one (E>F); batches 10. X1 {A..E} + F..L (7); X2/X3 joined. singletons 7; largest 5; longest 110-100 = 10.
#  g=10: linked = 6 + {6,7,10} = 9; ==10: one (F>G); ==11: none; batches 7. X1 {A..H} (G>H = 7) + I,J,K,L (4); singletons 4; largest 8; longest {A..H}: 137 - 100 = 37.
#  g=30: linked = 9 + {30} = 10; ==30: one (H>I); ==31: one (I>J); batches 6. X1 {A..I}, J,K,L. singletons 3; largest 9; longest 167-100 = 67.
#  g=60: linked = 10 + {31, 60} = 12; ==60: one; ==61: one; batches 4. X1 {A..K}, L. singletons 1; largest 11; longest 158.
SUMMARY = {
    ('C1', 2): (13, 11, 3, 1, 1, 3, 10), ('C1', 5): (10, 7, 6, 1, 1, 5, 10), ('C1', 10): (8, 5, 8, 1, 1, 7, 30), ('C1', 30): (6, 3, 10, 1, 1, 9, 67), ('C1', 60): (4, 1, 12, 1, 1, 11, 158),
    ('C2', 2): (12, 10, 4, 1, 0, 4, 10), ('C2', 5): (10, 7, 6, 1, 1, 5, 10), ('C2', 10): (7, 4, 9, 1, 0, 8, 37), ('C2', 30): (6, 3, 10, 1, 1, 9, 67), ('C2', 60): (4, 1, 12, 1, 1, 11, 158),
}
# overlap links (a linked pair whose next.first <= prev.last): only A>B (100 <= 100, touching, not strict) and C>D (105 <= 110, strict). C1 links C>D only from g=5 on (its C1 gap is 3); C2 links it from g=2 on (gap -5).
# C1: g=2 overlap 1 strict 0; g>=5 overlap 2 strict 1.  C2: all g overlap 2 strict 1.  Exactly one batch contains an overlap link in every view.
OVERLAP = {('C1', 2): (1, 0), ('C1', 5): (2, 1), ('C1', 10): (2, 1), ('C1', 30): (2, 1), ('C1', 60): (2, 1), **{('C2', g): (2, 1) for g in THR}}


@pytest.mark.parametrize('method,g', sorted(SUMMARY))
def test_summarize_row_fields_match_the_hand_calculation(sc, method, g):
    ls, parents, V = sc; rows = {(r['method'], r['threshold_s']): r for r in cb.summarize(V, parents, ls)}; r = rows[(method, g)]
    batches, singles, linked, eq, plus1, largest, longest = SUMMARY[(method, g)]
    assert r['parents'] == 16 and r['closing_portions'] == 18 and r['adjacent_pairs'] == 13       # counted by hand in the module docstring
    assert r['batches'] == batches and r['singleton_batches'] == singles
    assert r['pairs_linked'] == linked and r['pairs_gap_exactly_threshold'] == eq and r['pairs_gap_threshold_plus_1s'] == plus1
    assert batches == 16 - linked                                                                  # consistency of the hand table itself
    assert r['pairs_equal_first_ts'] == 1                                                         # only A and B start in the same second
    assert r['size']['n'] == batches and r['size']['max'] == largest and r['size']['min'] == 1
    assert r['duration_s']['max'] == longest and r['max_duration_over_threshold'] == pytest.approx(longest / g)
    assert (r['overlap_links'], r['strict_overlap_links'], r['batches_with_overlap']) == OVERLAP[(method, g)] + (1,)


def test_summarize_has_exactly_ten_rows_in_method_then_threshold_order(sc):
    ls, parents, V = sc; rows = cb.summarize(V, parents, ls); assert [(r['method'], r['threshold_s']) for r in rows] == [(m, g) for m in ('C1', 'C2') for g in THR]


def test_pairs_linked_includes_a_gap_equal_to_the_threshold(sc):
    """boundary: gap == g must be linked (inclusive rule). g=2: the B>C pair has gap exactly 2 and is among the 3 linked (C1) / 4 linked (C2); with `<` it would be 2 / 3."""
    ls, parents, V = sc; rows = {(r['method'], r['threshold_s']): r for r in cb.summarize(V, parents, ls)}
    assert rows[('C1', 2)]['pairs_linked'] == 3 and rows[('C2', 2)]['pairs_linked'] == 4
    assert rows[('C1', 2)]['pairs_linked'] == sum(len(b['links']) for b in V[('C1', 2)]['batches']) == 3                  # summarize agrees with the links the view really made (13 - 10 = 3 via the view: 13 batches)


# ---------------------------------------------------------------------------------------------------------------------------- batches, members, numbering
# parent facts (first offset, last offset, closing portions, closing qty):
PARENT = {'A': (100, 100, 1, 10), 'B': (100, 100, 1, 20), 'C': (102, 110, 2, 12), 'D': (105, 105, 1, 30), 'E': (110, 110, 1, 4), 'F': (116, 116, 1, 8), 'G': (126, 130, 2, 9), 'H': (137, 137, 1, 11), 'I': (167, 167, 1, 13),
          'J': (198, 198, 1, 14), 'K': (258, 258, 1, 15), 'L': (319, 319, 1, 16), 'U1': (DAY + 100, DAY + 100, 1, 17), 'U2': (DAY + 104, DAY + 104, 1, 18), 'T1': (100, 100, 1, 6), 'T2': (101, 101, 1, 7)}
# interval flags of a LINKED parent (next.first <= prev.last / next.first < prev.last): B (100 vs A.last 100) touching = (1, 0); D (105 vs C.last 110) = (1, 1); every other linked parent (0, 0)
FLAGS = {'B': ('1', '0'), 'D': ('1', '1')}
# EXPECTED per (method, g): list of (stream, batch number, [(parent, join_gap_s or None for the first member)], total_closing_qty, n_closing_portions, max_link_gap_s)
# totals by hand (qty): A10 B20 C12 D30 E4 F8 G9 H11 I13 J14 K15 L16 U1 17 U2 18 T1 6 T2 7 ; portions: C and G have 2, every other parent 1
E = {}
# C1 g=2: {A,B,C} gaps 0,2 -> 10+20+12 = 42, portions 1+1+2 = 4, max gap 2; D..L alone; U1, U2 alone (gap 4 > 2); {T1,T2} gap 1 -> 13, 2 portions
E[('C1', 2)] = [(X1, 1, [('A', None), ('B', 0), ('C', 2)], 42, 4, 2), (X1, 2, [('D', None)], 30, 1, 0), (X1, 3, [('E', None)], 4, 1, 0), (X1, 4, [('F', None)], 8, 1, 0), (X1, 5, [('G', None)], 9, 2, 0), (X1, 6, [('H', None)], 11, 1, 0),
                (X1, 7, [('I', None)], 13, 1, 0), (X1, 8, [('J', None)], 14, 1, 0), (X1, 9, [('K', None)], 15, 1, 0), (X1, 10, [('L', None)], 16, 1, 0), (X2, 1, [('U1', None)], 17, 1, 0), (X2, 2, [('U2', None)], 18, 1, 0),
                (X3, 1, [('T1', None), ('T2', 1)], 13, 2, 1)]
# C1 g=10: {A..G} gaps 0,2,3,5,6,10 -> 10+20+12+30+4+8+9 = 93, portions 1+1+2+1+1+1+2 = 9, max gap 10; H, I, J, K, L alone; {U1,U2} gap 4 -> 35, 2 portions; {T1,T2} 13
E[('C1', 10)] = [(X1, 1, [('A', None), ('B', 0), ('C', 2), ('D', 3), ('E', 5), ('F', 6), ('G', 10)], 93, 9, 10), (X1, 2, [('H', None)], 11, 1, 0), (X1, 3, [('I', None)], 13, 1, 0), (X1, 4, [('J', None)], 14, 1, 0),
                 (X1, 5, [('K', None)], 15, 1, 0), (X1, 6, [('L', None)], 16, 1, 0), (X2, 1, [('U1', None), ('U2', 4)], 35, 2, 4), (X3, 1, [('T1', None), ('T2', 1)], 13, 2, 1)]
# C1 g=60: {A..K} gaps 0,2,3,5,6,10,11,30,31,60 -> 93 + 11 + 13 + 14 + 15 = 146, portions 9 + 4 = 13, max gap 60; L alone
E[('C1', 60)] = [(X1, 1, [('A', None), ('B', 0), ('C', 2), ('D', 3), ('E', 5), ('F', 6), ('G', 10), ('H', 11), ('I', 30), ('J', 31), ('K', 60)], 146, 13, 60), (X1, 2, [('L', None)], 16, 1, 0),
                 (X2, 1, [('U1', None), ('U2', 4)], 35, 2, 4), (X3, 1, [('T1', None), ('T2', 1)], 13, 2, 1)]
# C2 g=2: {A,B,C,D} gaps 0,2,-5 -> 10+20+12+30 = 72, portions 5, max gap 2 (the negative gap does not raise the max); E..L alone; U1, U2 alone; {T1,T2} 13
E[('C2', 2)] = [(X1, 1, [('A', None), ('B', 0), ('C', 2), ('D', -5)], 72, 5, 2), (X1, 2, [('E', None)], 4, 1, 0), (X1, 3, [('F', None)], 8, 1, 0), (X1, 4, [('G', None)], 9, 2, 0), (X1, 5, [('H', None)], 11, 1, 0), (X1, 6, [('I', None)], 13, 1, 0),
                (X1, 7, [('J', None)], 14, 1, 0), (X1, 8, [('K', None)], 15, 1, 0), (X1, 9, [('L', None)], 16, 1, 0), (X2, 1, [('U1', None)], 17, 1, 0), (X2, 2, [('U2', None)], 18, 1, 0), (X3, 1, [('T1', None), ('T2', 1)], 13, 2, 1)]
# C2 g=10: {A..H} gaps 0,2,-5,5,6,10,7 -> 93 + 11 = 104, portions 9 + 1 = 10, max gap 10; I, J, K, L alone
E[('C2', 10)] = [(X1, 1, [('A', None), ('B', 0), ('C', 2), ('D', -5), ('E', 5), ('F', 6), ('G', 10), ('H', 7)], 104, 10, 10), (X1, 2, [('I', None)], 13, 1, 0), (X1, 3, [('J', None)], 14, 1, 0), (X1, 4, [('K', None)], 15, 1, 0),
                 (X1, 5, [('L', None)], 16, 1, 0), (X2, 1, [('U1', None), ('U2', 4)], 35, 2, 4), (X3, 1, [('T1', None), ('T2', 1)], 13, 2, 1)]
# C2 g=60: {A..K} gaps 0,2,-5,5,6,10,7,30,31,60 -> 104 + 13 + 14 + 15 = 146, portions 13, max gap 60; L alone
E[('C2', 60)] = [(X1, 1, [('A', None), ('B', 0), ('C', 2), ('D', -5), ('E', 5), ('F', 6), ('G', 10), ('H', 7), ('I', 30), ('J', 31), ('K', 60)], 146, 13, 60), (X1, 2, [('L', None)], 16, 1, 0),
                 (X2, 1, [('U1', None), ('U2', 4)], 35, 2, 4), (X3, 1, [('T1', None), ('T2', 1)], 13, 2, 1)]


def bid(method, g, stream, n): return f'INF:CLOSING_BATCH@{TOKEN[method]}_{g}S:NIFTY:{stream[0]}:{stream[1]}:{n:03d}'


def table(text):
    lines = text.rstrip('\n').split('\n'); head = lines[0].split('\t'); return [dict(zip(head, ln.split('\t'))) for ln in lines[1:]]


@pytest.mark.parametrize('method,g', sorted(E))
def test_batch_records_total_closing_qty_and_ids(sc, method, g):
    ls, parents, V = sc; rows = [r for r in table(cb.files_for_method(V, method, ls)[f'closing_batches_{method}.tsv']) if int(r['threshold_s']) == g]
    exp = E[(method, g)]; assert len(rows) == len(exp)
    for r, (stream, n, plist, total, ncp, maxgap) in zip(rows, exp):
        assert r['batch_id'] == bid(method, g, stream, n), (method, g, stream, n)
        assert (r['underlying'], r['expiry'], r['session']) == ('NIFTY',) + stream
        assert int(r['n_parents']) == len(plist) and int(r['total_closing_qty']) == total and int(r['n_closing_portions']) == ncp
        assert int(r['n_links']) == len(plist) - 1 and int(r['max_link_gap_s']) == maxgap
        assert int(r['start_ts']) == BASE_TS + PARENT[plist[0][0]][0] and int(r['end_ts']) == BASE_TS + max(PARENT[p][1] for p, _ in plist)
        assert int(r['duration_s']) == int(r['end_ts']) - int(r['start_ts'])
    assert sum(int(r['total_closing_qty']) for r in rows) == 162 + 35 + 13                         # every closing unit appears exactly once: X1 162, X2 35, X3 13 (hand sums above)


@pytest.mark.parametrize('method,g', sorted(E))
def test_members_file_join_gap_closing_qty_and_batch_ids(sc, method, g):
    ls, parents, V = sc; rows = [r for r in table(cb.files_for_method(V, method, ls)[f'closing_batch_members_{method}.tsv']) if int(r['threshold_s']) == g]
    want = [(bid(method, g, stream, n), p, gap) for stream, n, plist, *_ in E[(method, g)] for p, gap in plist]
    assert [(r['batch_id'], r['parent_order_id'], None if r['join_gap_s'] == '' else int(r['join_gap_s'])) for r in rows] == want
    for r in rows:
        first, last, ncp, qty = PARENT[r['parent_order_id']]
        assert (int(r['parent_first_closing_ts']), int(r['parent_last_closing_ts']), int(r['n_closing_portions']), int(r['closing_qty'])) == (BASE_TS + first, BASE_TS + last, ncp, qty)
        assert r['grouping_convention'] == f'{TOKEN[method]}_{g}S' and int(r['threshold_s']) == g
        if r['join_gap_s'] == '': assert (r['interval_overlap'], r['strict_overlap']) == ('', '')                  # the first member of a batch has no join link
        else: assert (r['interval_overlap'], r['strict_overlap']) == FLAGS.get(r['parent_order_id'], ('0', '0'))


# batches per stream in every view (hand-counted above): C1 g=2: X1 10, X2 2, X3 1 ; g=5: 8,1,1 ; g=10: 6,1,1 ; g=30: 4,1,1 ; g=60: 2,1,1.   C2 g=2: 9,2,1 ; g=5: 8,1,1 ; g=10: 5,1,1 ; g=30: 4,1,1 ; g=60: 2,1,1.
# (C1 g=5: {A..E},F,G,H,I,J,K,L = 8; C1 g=30: {A..I},J,K,L = 4; C2 g=5 same 8 as C1; C2 g=30 same 4)
PER_STREAM = {('C1', 2): (10, 2, 1), ('C1', 5): (8, 1, 1), ('C1', 10): (6, 1, 1), ('C1', 30): (4, 1, 1), ('C1', 60): (2, 1, 1), ('C2', 2): (9, 2, 1), ('C2', 5): (8, 1, 1), ('C2', 10): (5, 1, 1), ('C2', 30): (4, 1, 1), ('C2', 60): (2, 1, 1)}


@pytest.mark.parametrize('method,g', sorted(PER_STREAM))
def test_batch_numbering_starts_at_001_and_is_contiguous_per_stream(sc, method, g):
    ls, parents, V = sc; ids = [b['batch_id'] for b in V[(method, g)]['batches']]
    want = [bid(method, g, s, n) for s, cnt in zip((X1, X2, X3), PER_STREAM[(method, g)]) for n in range(1, cnt + 1)]
    assert ids == want                                                                          # numbering restarts at 001 in each (underlying, expiry, session) stream and never skips
    assert not any(i.endswith(':000') for i in ids)
    assert len(ids) == SUMMARY[(method, g)][0]                                                    # 13/10/8/6/4 and 12/10/7/6/4 batches by hand
    texts = cb.files_for_method(V, method, ls); fids = [r['batch_id'] for r in table(texts[f'closing_batches_{method}.tsv']) if int(r['threshold_s']) == g]; assert fids == want


def test_membership_sets_agree_with_the_hand_chains(sc):
    """the partitions behind the reporting tables (independent of the reporting code)"""
    ls, parents, V = sc
    assert sets(V[('C1', 2)]) == sorted([['A', 'B', 'C'], ['D'], ['E'], ['F'], ['G'], ['H'], ['I'], ['J'], ['K'], ['L'], ['U1'], ['U2'], ['T1', 'T2']])
    assert sets(V[('C2', 2)]) == sorted([['A', 'B', 'C', 'D'], ['E'], ['F'], ['G'], ['H'], ['I'], ['J'], ['K'], ['L'], ['U1'], ['U2'], ['T1', 'T2']])
    assert sets(V[('C1', 10)]) == sorted([list('ABCDEFG'), ['H'], ['I'], ['J'], ['K'], ['L'], ['U1', 'U2'], ['T1', 'T2']])
    assert sets(V[('C2', 10)]) == sorted([list('ABCDEFGH'), ['I'], ['J'], ['K'], ['L'], ['U1', 'U2'], ['T1', 'T2']])
