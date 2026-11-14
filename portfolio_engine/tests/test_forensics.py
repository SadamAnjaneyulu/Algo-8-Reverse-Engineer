"""M2-E tests: reconciliation of every visualization dataset against M1/M2-B/M2-C/M2-D, chart-data reproduction, double counting, timezones, D-1/D0 boundaries, evidence labels,
scope warnings, case-selection reproducibility/no-outcome-bias/no-borrowing, and mutation checks of the reconciliation itself. Real frozen cycles; artifacts under reports/m2e_*."""
import copy, csv, dataclasses as dc, gzip, hashlib, json, os
from collections import Counter, defaultdict
import pytest
from conftest import PE, REPO
from pe import forensics as F, cases as K
import m2e_charts as CH

DATA = os.path.join(PE, 'reports', 'm2e_data'); FIG = os.path.join(PE, 'reports', 'm2e_figures'); KEYS = [F.cycle_key(*c) for c in F.CYCLES]


@pytest.fixture(scope='module', params=F.CYCLES, ids=KEYS)
def cyc(request): return F.Cycle(REPO, *request.param)


def drows(cy, name): return F.read_tsv_text(open(os.path.join(DATA, cy, name)).read())[1]
def frows(cy, name):
    with open(os.path.join(FIG, cy, name)) as fh: return list(csv.DictReader(fh))
def fman(cy): return {f['figure']: f for f in json.load(open(os.path.join(FIG, cy, 'figure_manifest.json')))['figures']}


# ------------------------------------------------------------------------------------------------------------ frozen cycles, determinism, manifests
def test_frozen_cycles_are_the_selected_ones():
    assert F.CYCLES == (('NIFTY', '2026-06-30'), ('SENSEX', '2026-07-16'))
    note = open(os.path.join(PE, 'reports', 'DEMO_CYCLE_SELECTION_NOTE.md')).read(); assert 'NIFTY' in note and '2026-06-30' in note and '2026-07-16' in note
    with open(os.path.join(PE, 'reports', 'demo_cycle_scores.csv')) as fh: sel = {r['cycle'] for r in csv.DictReader(fh) if float(r['score']) == 1.0 and r['eligible'] == 'True'}
    assert {'NIFTY|2026-06-30', 'SENSEX|2026-07-16'} <= sel


def test_ist_helpers_not_utc():
    assert F.ist_str(0) == '1970-01-01 05:30:00' and F.ist_date(86400 - 19800) == '1970-01-02' and F.ist_date(86400 - 19801) == '1970-01-01'


@pytest.mark.parametrize('cy', KEYS)
def test_manifest_hashes_match_files(cy):
    man = json.load(open(os.path.join(DATA, cy, 'manifest.json')))
    assert len(man['files']) >= 19
    for n, v in man['files'].items(): assert F.sha(open(os.path.join(DATA, cy, n)).read()) == v['sha256'], n


def test_datasets_reproduce_committed_files(cyc):
    cy = cyc.key; cls, wh, wr = F.tp03_overlay(REPO, cyc)
    for n, t in {'fills.tsv': F.fills_table(cyc), 'inventory_series.tsv': F.inventory_series(cyc), 'lifecycle_events.tsv': F.lifecycle_table(cyc), 'episodes.tsv': F.episodes_table(cyc), 'session_carry.tsv': F.session_carry(cyc), 'opening_items.tsv': F.opening_items(cyc, cls), 'tp03_windows.tsv': (wh, wr)}.items():
        assert F.tsv(*t) == open(os.path.join(DATA, cy, n)).read(), n


def test_m2c_m2d_slices_are_the_committed_memberships(cyc):
    for n, t in F.m2c_slice(REPO, cyc).items(): assert t == open(os.path.join(DATA, cyc.key, 'm2c_' + n)).read()
    for n, t in F.m2d_slice(REPO, cyc).items(): assert t == open(os.path.join(DATA, cyc.key, 'm2d_' + n)).read()
    for m in ('C1', 'C2'):                                         # preserved membership: the cycle slice is exactly the committed rows whose batch id carries this cycle
        full = F.read_gz_text(os.path.join(PE, 'reports', 'm2c_data', f'closing_batches_{m}.tsv.gz')).rstrip('\n').split('\n')[1:]
        mine = {l.split('\t')[0] for l in full if f':{cyc.und}:{cyc.expiry}:' in l.split('\t')[0]}; assert mine == {r['batch_id'] for r in drows(cyc.key, f'm2c_closing_batches_{m}.tsv')}


# ------------------------------------------------------------------------------------------------------------ reconciliation against M1 / M2-B
def test_observed_layer_reconciles_independently(cyc):
    r = F.reconcile_observed(cyc); assert r['independent_checks'] == 'PASS' and r['opened_units'] == r['closed_units'] and r['final_open_instruments'] == 0


def test_totals_equal_m2b_and_coverage(cyc):
    cov = json.load(open(os.path.join(DATA, cyc.key, 'coverage.json'))); inv = drows(cyc.key, 'inventory_series.tsv'); last = inv[-1]
    assert int(last['cum_opened_units']) == sum(r[8] for r in cyc.ls.oa.values()) == cov['fills']['opening_units'] and int(last['cum_closed_units']) == sum(r[8] for r in cyc.ls.cp.values()) == cov['fills']['closing_units']
    assert len(inv) == cov['fills']['raw_fill_count'] == len(drows(cyc.key, 'fills.tsv'))
    assert len(drows(cyc.key, 'episodes.tsv')) == cov['episodes']['episode_count'] == len(cyc.ls.episodes)


def test_reconciliation_detects_tampering(cyc, monkeypatch):
    real = F.inventory_series
    def bad(c):
        H, R = real(c); R = [list(r) for r in R]; R[len(R) // 2][H.index('short_CE')] += 65; return H, [tuple(r) for r in R]
    monkeypatch.setattr(F, 'inventory_series', bad)
    with pytest.raises(F.ReconciliationError): F.reconcile_observed(cyc)


def test_reconciliation_detects_utc_read_as_ist(cyc):
    c2 = copy.copy(cyc); c2.fills = [dc.replace(f, timestamp_s=f.timestamp_s + 19800) for f in cyc.fills]
    with pytest.raises(F.ReconciliationError, match='timezone suspect'): F.reconcile_observed(c2)


def test_ist_columns_consistent_in_every_dataset(cyc):
    for n, tcol, scol in (('fills.tsv', 'ts_utc_s', 'ts_ist'), ('inventory_series.tsv', 'ts_utc_s', 'ts_ist'), ('lifecycle_events.tsv', 'ts_utc_s', 'ts_ist')):
        for r in drows(cyc.key, n): assert r[scol] == F.ist_str(int(r[tcol])) and r['session_ist'] == F.ist_date(int(r[tcol]))
    for r in drows(cyc.key, 'opening_items.tsv'): assert r['first_ts_ist'] == F.ist_str(int(r['first_ts_utc_s']))


def test_d1_d0_boundaries(cyc):
    labs = {}
    for r in drows(cyc.key, 'fills.tsv'): labs.setdefault(r['session_ist'], set()).add(r['d_label'])
    assert {k: v for k, v in labs.items()} == {cyc.sessions[0]: {'D-1'}, cyc.expiry: {'D0'}} and all(s <= cyc.expiry for s in labs)
    carry = {r['session_ist']: r for r in drows(cyc.key, 'session_carry.tsv')}; inv = drows(cyc.key, 'inventory_series.tsv')
    d1 = [r for r in inv if r['d_label'] == 'D-1'][-1]; assert all(carry[cyc.sessions[0]][k] == d1[k] for k in ('short_CE', 'short_PE', 'long_CE', 'long_PE', 'gross_total'))
    assert int(carry[cyc.expiry]['gross_total']) == 0                                    # flat at the end of D0: nothing remained at expiry
    carry_in = [r for r in frows(cyc.key, 'V1_inventory_evolution.csv') if r['row_kind'] == 'CARRY_IN']; assert len(carry_in) == 2
    assert all(carry_in[1][k] == d1[k] for k in ('short_CE', 'short_PE', 'long_CE', 'long_PE', 'gross_total')) and all(int(carry_in[0][k]) == 0 for k in ('short_CE', 'gross_total'))
    assert carry_in[1]['ts_ist'] == f'{cyc.expiry} 09:15:00'


# ------------------------------------------------------------------------------------------------------------ chart data reproduces plotted values
def test_v1_chart_data_equals_dataset(cyc):
    inv = drows(cyc.key, 'inventory_series.tsv'); ch = [r for r in frows(cyc.key, 'V1_inventory_evolution.csv') if r['row_kind'] == 'FILL']; assert len(ch) == len(inv)
    for a, b in zip(ch, inv):
        for k in ('short_CE', 'short_PE', 'long_CE', 'long_PE', 'net_total', 'gross_total', 'cum_opened_units', 'cum_closed_units'): assert a[k] == b[k]
        assert a['ts_ist'] == b['ts_ist']


def test_v2_partial_reduction_never_a_full_close(cyc):
    ch = frows(cyc.key, 'V2_position_lifecycle_timeline.csv'); ev = [r for r in ch if r['record'] == 'EVENT']; lc = drows(cyc.key, 'lifecycle_events.tsv'); assert len(ev) == len(lc)
    assert {r['event_type'] for r in ev} <= {'CREATED', 'ADDED', 'PARTIALLY_REDUCED', 'CLOSED', 'REVERSED'}
    assert all(int(r['inventory_after']) != 0 for r in ev if r['event_type'] == 'PARTIALLY_REDUCED') and all(int(r['inventory_after']) == 0 for r in ev if r['event_type'] in ('CLOSED', 'REVERSED'))
    eps = [r for r in ch if r['record'] == 'EPISODE']; assert len(eps) == len(cyc.ls.episodes) and all(int(r['remaining']) == int(r['opened']) - int(r['closed']) for r in eps)
    assert [r['event_type'] for r in ev if r['event_type'] == 'REVERSED'].__len__() == sum(e['ended_by'] == 'reversal' for e in cyc.ls.episodes.values())


def test_v3_items_cover_every_opening_allocation_once(cyc):
    items = frows(cyc.key, 'V3_opening_activity_cohort_map.csv'); ds = drows(cyc.key, 'opening_items.tsv'); assert len(items) == len(ds)
    assert sum(int(r['quantity']) for r in items) == sum(r[8] for r in cyc.ls.oa.values())
    oas = [o for r in ds for o in r['oa_ids'].split(',')]; assert len(oas) == len(set(oas)) == len(cyc.ls.oa)                          # no OA double counted, none dropped
    coh = frows(cyc.key, 'V3_opening_activity_cohort_map__entry_minute_cohorts.csv'); assert sum(int(r['body_units_by_tag']) + int(r['wing_units_by_tag']) + int(r['unclassified_units']) for r in coh) == sum(int(r['quantity']) for r in items)
    assert fman(cyc.key)['V3_opening_activity_cohort_map']['items_without_entry_minute'] == 0
    win = frows(cyc.key, 'V3_opening_activity_cohort_map__tp03_windows_overlay.csv'); assert win and all(r['cycle'] == f'{cyc.und}|{cyc.expiry}' for r in win)
    assert {r['tp03_event_class'] for r in items} <= {'NOT_LISTED_BY_TP03_AS_OFF_WINDOW', 'OFF_WINDOW_ACTION', 'INITIAL_ENTRY'}                # never "in window"


@pytest.mark.parametrize('m', ('C1', 'C2'))
def test_v4_batches_reconcile_with_m2c(cyc, m):
    B = drows(cyc.key, f'm2c_closing_batches_{m}.tsv'); Mm = drows(cyc.key, f'm2c_closing_batch_members_{m}.tsv'); P = drows(cyc.key, f'm2c_closing_batch_portions_{m}.tsv'); cp_total = sum(r[8] for r in cyc.ls.cp.values())
    memq = defaultdict(int); memp = defaultdict(set)
    for x in Mm: memq[x['batch_id']] += int(x['closing_qty']); memp[x['batch_id']].add(x['parent_order_id'])
    for b in B: assert memq[b['batch_id']] == int(b['total_closing_qty']) and len(memp[b['batch_id']]) == int(b['n_parents'])
    for t in ('2', '5', '10', '30', '60'):
        bt = [b for b in B if b['threshold_s'] == t]; assert sum(int(b['total_closing_qty']) for b in bt) == cp_total                                     # grouping adds/removes no inventory
        parents = [p for b in bt for p in memp[b['batch_id']]]; assert len(parents) == len(set(parents))                                                    # each closing parent in exactly one batch
        assert sum(int(x['quantity']) for x in P if x['threshold_s'] == t) == cp_total
        assert all(int(b['duration_s']) == int(b['end_ts']) - int(b['start_ts']) for b in bt)
    ch = frows(cyc.key, f'V4_{m}_closing_batches.csv'); assert {r['batch_id'] for r in ch} == {b['batch_id'] for b in B if b['threshold_s'] == '10'}
    sens = frows(cyc.key, f'V4_{m}_closing_batches__sensitivity_by_threshold.csv'); assert [int(r['batches']) for r in sens] == [sum(1 for b in B if b['threshold_s'] == t) for t in ('2', '5', '10', '30', '60')]
    c60 = max(int(b['duration_s']) for b in B if b['threshold_s'] == '60'); c10 = max(int(b['duration_s']) for b in B if b['threshold_s'] == '10'); assert c60 >= c10        # 60 s chaining is at least as long
    assert max(int(r['duration_s']) for r in frows(cyc.key, f'V4_{m}_closing_batches__longest_chains.csv') if r['threshold_s'] == '60') == c60


def test_c1_and_c2_are_not_summed(cyc):
    assert not any('C1+C2' in f['title'] or 'combined' in f['title'].lower() for f in fman(cyc.key).values())
    assert {'V4_C1_closing_batches', 'V4_C2_closing_batches'} <= set(fman(cyc.key))


def test_wing_body_quantities_reconcile_with_m2d(cyc):
    items = drows(cyc.key, 'm2d_wing_body_items.tsv'); op = drows(cyc.key, 'opening_items.tsv'); assert all(r['underlying'] == cyc.und and r['expiry'] == cyc.expiry for r in items)
    q = lambda rows, role, key='qty': sum(int(r[key]) for r in rows if r['role'] == role and r['level'] == 'OPENING') if key == 'qty' else 0
    assert q(items, 'BODY') == sum(int(r['quantity']) for r in op if r['tag_role'] == 'BODY_SHORT_BY_TAG') and q(items, 'WING') == sum(int(r['quantity']) for r in op if r['tag_role'] == 'WING_LONG_BY_TAG')
    keys = [(r['level'], r['role'], r['parent_order_id'], r['instrument_id']) for r in items]; assert len(keys) == len(set(keys))
    cov = json.load(open(os.path.join(DATA, cyc.key, 'coverage.json')))['wing_body_coverage_cycle_level']
    W = [r for r in items if r['level'] == 'OPENING' and r['role'] == 'WING']; assert len(W) == cov['OPENING|W1']['wing_items'] and sum(int(r['qty']) for r in W) == cov['OPENING|W1']['wing_units']


@pytest.mark.parametrize('m', ('W1', 'W1_S60', 'W2', 'W3'))
def test_v5_figure_data_matches_items_and_labels(cyc, m):
    ch = frows(cyc.key, f'V5_{m}_wing_body.csv'); items = drows(cyc.key, 'm2d_wing_body_items.tsv'); wu = sum(int(r['qty']) for r in items if r['level'] == 'OPENING' and r['role'] == 'WING'); bu = sum(int(r['qty']) for r in items if r['level'] == 'OPENING' and r['role'] == 'BODY')
    tot = {r['category']: float(r['value']) for r in ch if r['category'].endswith('observed total')}; assert tot == {'wing units: observed total': wu, 'body units: observed total': bu}
    want = {'W1': 'WEAKLY_SUPPORTED', 'W1_S60': 'UNRESOLVED', 'W2': 'WEAKLY_SUPPORTED (weights)', 'W3': 'UNRESOLVED'}[m]
    assert {r['evidence_class'] for r in ch if r['evidence_class'] != 'OBSERVED'} == {want} and not any('CONFIRMED' in r['evidence_class'] for r in ch)
    if m == 'W3':
        L = [l for l in drows(cyc.key, 'm2d_wing_body_links_W3.tsv') if l['level'] == 'OPENING']; mq = sum(float(l['queue_matched_units']) for l in L)
        d = {r['category']: float(r['value']) for r in ch}; assert d['wing units: queue-matched'] + d['wing units: queue residual'] == wu and d['body units: queue-matched'] + d['body units: queue residual'] == bu and d['wing units: queue-matched'] == mq
    if m == 'W1':
        L = [l for l in drows(cyc.key, 'm2d_wing_body_links_W1.tsv') if l['level'] == 'OPENING']; per = Counter(l['wing_item'] for l in L); W = [r for r in items if r['level'] == 'OPENING' and r['role'] == 'WING']
        none_ = sum(1 for r in W if per.get(r['item_id'], 0) == 0); assert {r['category']: float(r['value']) for r in ch}['wing items with 0 candidate bodies'] == none_
    f = fman(cyc.key)[f'V5_{m}_wing_body']; assert f['scope_warning_shown'] and f['evidence_class'].split()[0] == want.split()[0]


def test_v6_values_and_full_ledger_numbers(cyc):
    ch = frows(cyc.key, 'V6_coverage_uncertainty_dashboard.csv'); d = {(r['section'], r['metric']): r['value'] for r in ch}; items = drows(cyc.key, 'm2d_wing_body_items.tsv'); wu = sum(int(r['qty']) for r in items if r['level'] == 'OPENING' and r['role'] == 'WING')
    assert sum(float(v) for (s, m), v in d.items() if s == 'A_units_by_candidate_status' and m.startswith('wing units, W1:')) == wu
    assert sum(float(v) for (s, m), v in d.items() if s == 'A_units_by_candidate_status' and m.startswith('wing units, W1_S60:')) == wu
    assert sum(float(v) for (s, m), v in d.items() if s == 'A_units_by_candidate_status' and m.startswith('wing units, W3:')) == wu
    S = json.load(open(os.path.join(PE, 'reports', 'm2d_data', 'm2d_summary.json')))['coverage']['OPENING|W1']
    for k, ref in (('wing_items_full_ledger_W1', 8399), ('wing_items_with_candidate_full_ledger_W1', 7301), ('wing_items_unique_full_ledger_W1', 3501), ('wing_items_multiple_full_ledger_W1', 3800), ('wing_items_none_full_ledger_W1', 1098), ('wing_units_unmatched_full_ledger_W1', 133640), ('wing_items_with_candidate_full_ledger_W1_S60', 8204), ('wing_items_none_full_ledger_W1_S60', 195), ('wing_units_unmatched_full_ledger_W1_S60', 68720),
                   ('closing_units_excluded_by_tag_roles_full_ledger', 336040), ('closing_wing_units_in_mixed_module_episodes_full_ledger', 107530)): assert int(float(d[('G_scope_warning_numbers_full_ledger', k)])) == ref, k
    assert S['wing_items'] == 8399
    marks = [r for r in ch if 'MISSING' in r['metric']]; assert marks                                                                      # missing marks are visible
    for sec_ in ('A_units_by_candidate_status', 'C_role_exclusions_units', 'D_unclassified_and_missing', 'E_batch_count_sensitivity', 'F_sensitivity_unresolved'): assert any(r['section'] == sec_ for r in ch)


def test_scope_warning_text_has_required_items_and_is_on_v3_to_v6():
    for s in ('8,399', '7,301', '3,501', '3,800', '1,098', '133,640', '21.7%', '8,204', '195 none', '68,720', '336,040', '107,530', 'NOT lot ownership', 'not decision-time evidence', '`s_`', '`num` seed wings', 'NOT claimed to lack a wing', 'App keys are not a filter'): assert s in CH.SCOPE_WARNING, s
    for cy in KEYS:
        fm = fman(cy)
        for v in ('V3_opening_activity_cohort_map', 'V4_C1_closing_batches', 'V4_C2_closing_batches', 'V5_W1_wing_body', 'V5_W1_S60_wing_body', 'V5_W2_wing_body', 'V5_W3_wing_body', 'V6_coverage_uncertainty_dashboard'): assert fm[v]['scope_warning_shown'], (cy, v)


def test_every_figure_has_png_csv_sources_and_matching_hash(cyc):
    for f in list(fman(cyc.key).values()) + json.load(open(os.path.join(FIG, cyc.key, 'case_figure_manifest.json')))['figures']:
        assert os.path.exists(os.path.join(PE, f['png'])) and f['source_datasets'] and all(os.path.exists(os.path.join(PE, s)) for s in f['source_datasets'])
        assert hashlib.sha256(open(os.path.join(PE, f['data_csv']), 'rb').read()).hexdigest() == f['data_csv_sha256']
        for a in f.get('additional_data_csv', []): assert hashlib.sha256(open(os.path.join(PE, a['data_csv']), 'rb').read()).hexdigest() == a['sha256']
    assert set(fman(cyc.key)) == {'V1_inventory_evolution', 'V2_position_lifecycle_timeline', 'V3_opening_activity_cohort_map', 'V4_C1_closing_batches', 'V4_C2_closing_batches', 'V5_W1_wing_body', 'V5_W1_S60_wing_body', 'V5_W2_wing_body', 'V5_W3_wing_body', 'V6_coverage_uncertainty_dashboard'}


def test_no_marks_or_unrealized_pnl_anywhere(cyc):
    cov = json.load(open(os.path.join(DATA, cyc.key, 'coverage.json')))['historical_marks']; assert cov['historical_mark_status'].startswith('NOT_COMPUTED') and 'unrealized P&L = NA' in cov['prices_used_in_M2E'] and cov['expired_unclosed_positions'] == 0
    import glob
    for p in glob.glob(os.path.join(DATA, cyc.key, '*.tsv')) + glob.glob(os.path.join(FIG, cyc.key, '**', '*.csv'), recursive=True):
        head = open(p).readline().lower(); assert 'unrealized' not in head and 'mark_price' not in head and 'mtm' not in head, p


# ------------------------------------------------------------------------------------------------------------ cases: reproducible, outcome-free, no borrowing
@pytest.fixture(scope='module')
def D(cyc): return K.load_data(os.path.join(DATA, cyc.key))


def test_case_selection_reproducible_and_matches_committed(cyc, D):
    S = K.select(D); assert S == K.select(D); saved = json.load(open(os.path.join(DATA, cyc.key, 'case_studies.json')))['selection']
    assert {n: (s['status'], s['episode_id'], s['anchor']) for n, s in S.items()} == {n: (s['status'], s['episode_id'], s['anchor']) for n, s in saved.items()}


def test_case_selection_ignores_prices_and_outcomes(cyc, D):
    D2 = copy.deepcopy(D)
    for f in D2['fills'].values(): f['price_paise'] = str(int(f['price_paise']) * 7 + 13)
    for it in D2['items']: it['avg_price_paise'] = '1'
    assert K.select(D2) == K.select(D)


def test_case_is_first_qualifying_in_time(cyc, D):
    S = K.select(D); eps = sorted(D['episodes'], key=lambda r: (int(r['first_ts_utc_s']), r['episode_id'])); cnt = defaultdict(Counter)
    for e in D['events']: cnt[e['episode_id']][e['event_type']] += 1
    preds = (('CT1_INCREMENTAL_OPENING', lambda r: cnt[r['episode_id']]['ADDED'] >= 3), ('CT2_PARTIAL_REDUCTION', lambda r: cnt[r['episode_id']]['PARTIALLY_REDUCED'] >= 2 and r['terminal_status'] == 'CLOSED'),
             ('CT3_FULL_CLOSURE', lambda r: r['terminal_status'] == 'CLOSED' and cnt[r['episode_id']]['CLOSED'] == 1 and not cnt[r['episode_id']]['PARTIALLY_REDUCED']))
    used = []
    for name, pred in preds:                                              # brute force: first qualifying episode in time, preferring one not used by an earlier case type
        q = [r['episode_id'] for r in eps if pred(r)]; expect = ([e for e in q if e not in used] or q)[0]
        assert S[name]['episode_id'] == expect and S[name]['n_qualifying'] == len(q), name
        used.append(expect)


def test_unavailable_case_types_not_borrowed(cyc, D):
    S = K.select(D)
    assert S['CT4_REMAINING_AT_EXPIRY']['status'] == 'UNAVAILABLE' and S['CT4_REMAINING_AT_EXPIRY']['episode_id'] is None
    assert (S['CT5_REVERSAL']['status'] == 'AVAILABLE') == (cyc.und == 'NIFTY')
    for s in S.values():
        if s['status'] == 'AVAILABLE': assert s['episode_id'].startswith(f'{cyc.und}|{cyc.expiry}|')                       # an episode of THIS cycle only
    rec = json.load(open(os.path.join(DATA, cyc.key, 'case_studies.json')))['records']; assert rec['CT4_REMAINING_AT_EXPIRY']['status'] == 'UNAVAILABLE' and 'not borrowed' in rec['CT4_REMAINING_AT_EXPIRY']['reason']


def test_case_selection_mutations(cyc, D):
    D2 = copy.deepcopy(D); e0 = D2['episodes'][0]; e0['terminal_status'] = 'EXPIRED_UNCLOSED'
    S = K.select(D2); assert S['CT4_REMAINING_AT_EXPIRY']['status'] == 'AVAILABLE' and S['CT4_REMAINING_AT_EXPIRY']['episode_id'] == e0['episode_id']          # selection logic does see an expired-unclosed episode
    D3 = copy.deepcopy(D); D3['events'] = [e for e in D3['events'] if e['event_type'] != 'REVERSED']; assert K.select(D3)['CT5_REVERSAL']['status'] == 'UNAVAILABLE'
    D4 = copy.deepcopy(D); D4['links']['W1'] = []; S4 = K.select(D4); assert S4['CT6_MULTIPLE_CANDIDATE_WINGS']['status'] == 'UNAVAILABLE' and S4['CT7_NO_CANDIDATE_WING']['status'] == 'AVAILABLE'


def test_case_records_reconcile_with_lineage(cyc):
    rec = json.load(open(os.path.join(DATA, cyc.key, 'case_studies.json')))['records']; n_av = 0
    for n, r in rec.items():
        if r['status'] != 'AVAILABLE': continue
        n_av += 1; E = cyc.ls.episodes[r['position_id']]
        assert sum(f['opening_qty_in_episode'] for f in r['fills']) == r['opened'] == E['opened'] and sum(f['closing_qty_in_episode'] for f in r['fills']) == r['closed'] and r['remaining'] == r['opened'] - r['closed']
        assert {f['fill_id'] for f in r['fills']} == {e[4] for e in cyc.ls.events if e[1] == r['position_id']} and r['lifecycle'][-1]['event'] in ('CLOSED', 'REVERSED')
        for w in r['wing_body_candidates']:
            for m in ('W1', 'W1_S60'):
                for x in w.get(m, []): assert not x['evidence_class'].startswith('CONFIRMED')
    assert n_av >= 8


def test_reversal_case_fill_quantities_split_between_episodes():
    r = json.load(open(os.path.join(DATA, 'NIFTY_2026-06-30', 'case_studies.json')))['records']['CT5_REVERSAL']; rf = [f for f in r['fills'] if f['fill_opening_qty'] and f['fill_closing_qty']]
    assert len(rf) == 1 and rf[0]['opening_qty_in_episode'] == 0 and rf[0]['closing_qty_in_episode'] == rf[0]['fill_closing_qty'] and rf[0]['fill_opening_qty'] + rf[0]['fill_closing_qty'] == rf[0]['quantity']   # regression: found by test_case_records_reconcile_with_lineage


def test_case_charts_exist_for_available_cases(cyc):
    cm = json.load(open(os.path.join(FIG, cyc.key, 'case_figure_manifest.json')))['figures']; rec = json.load(open(os.path.join(DATA, cyc.key, 'case_studies.json')))['records']
    assert {f['case_type'] for f in cm} == {n for n, r in rec.items() if r['status'] == 'AVAILABLE'}
    if cyc.und == 'NIFTY': assert rec['CT5_REVERSAL']['chart_episode_ids'] == [cyc.key.split('_')[0] + '|2026-06-30|CE|24100#1', 'NIFTY|2026-06-30|CE|24100#2']             # reversal shown with its successor, never as a plain close


# ------------------------------------------------------------------------------------------------------------ cycle isolation (slow: full ledger)
@pytest.mark.slow
def test_cycle_isolation_against_full_ledger(cyc):
    from pe.lineage_set import LineageSet
    from pe.generators import historical as H
    ins, fills, _ = H.generate(REPO); full = LineageSet(fills, ins, 'HISTORICAL_OBSERVED_REPLAY', 'src'); inst = set(cyc.ins)
    assert [e for e in full.events if full.episodes[e[1]]['instrument_id'] in inst] == list(cyc.ls.events)
    assert {k: v for k, v in full.episodes.items() if v['instrument_id'] in inst} == cyc.ls.episodes
