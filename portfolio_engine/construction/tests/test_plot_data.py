"""The six plots are drawn from the TSV files saved next to them. This test regenerates them and checks every TSV against an independent recount from the simulation logs,
and checks that every data file states where its data come from."""
import csv, os, subprocess, sys
import pytest
from helpers import *
from pc import generators as G

pytest.importorskip('matplotlib')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope='module')
def plots(tmp_path_factory):
    out = tmp_path_factory.mktemp('plots'); r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_plots.py'), str(out)], capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'python'), MPLBACKEND='Agg'))
    assert r.returncode == 0, r.stderr[-500:]
    return out


def tsv(path): return list(csv.DictReader(open(path), delimiter='\t'))
def logs(name): return run(G.all_scenarios()[name].to_text())[1]


def test_every_plot_has_a_png_and_a_data_file_with_provenance(plots):
    for n in ('01_architecture', '02_basket_lifecycle', '03_exposure_over_time', '04_leg_quantity_before_after_cuts', '05_reentry_decision_timeline', '06_risk_validation_and_rejections'):
        assert os.path.getsize(plots / f'{n}.png') > 10000
        rows = tsv(plots / (n + ('_components' if n == '01_architecture' else '') + '.tsv')); assert rows and all(r['data_origin'].strip() for r in rows)
        if n != '01_architecture': assert all(r['data_origin'].startswith('synthetic simulation: ') for r in rows), n
    comp = tsv(plots / '01_architecture_components.tsv'); assert {r['data_origin'] for r in comp} == {'historical observations (external, not included in this ZIP)', 'code that processes historical data', 'code that processes synthetic scenarios', 'synthetic scenario files'}


def test_risk_validation_plot_data_equals_a_recount_of_all_scenario_logs(plots):
    acc = {}; rej = {}; plug = {}
    for n in G.all_scenarios():
        f = logs(n)
        for a in table(f['actions.tsv']):
            if a['status'] == 'ACCEPTED': acc[n] = acc.get(n, 0) + 1
            else: rej.setdefault(a['reason'], {}); rej[a['reason']][n] = rej[a['reason']].get(n, 0) + 1
        for d in table(f['decisions.tsv']):
            if d['outcome'] == 'NOT_PROPOSED': plug.setdefault(d['reason'], {}); plug[d['reason']][n] = plug[d['reason']].get(n, 0) + 1
    got = {(r['layer'], r['outcome_or_reason'], r['scenario']): int(r['count']) for r in tsv(plots / '06_risk_validation_and_rejections.tsv')}
    want = {('validator', 'ACCEPTED', n): c for n, c in acc.items()}
    want.update({('validator', reason, n): c for reason, d in rej.items() for n, c in d.items()}); want.update({('plugin (not proposed)', reason, n): c for reason, d in plug.items() for n, c in d.items()})
    assert got == want


def test_state_plots_equal_the_state_log(plots):
    f = logs('s11_basket_lifecycle_demo'); st = table(f['states.tsv']); base = min(int(r['ts']) for r in st)
    ev = {}
    for r in st:
        if r['event_id'] != '-': ev.setdefault(r['event_id'], []).append(r)
    want = sorted([((int(rs[0]['ts']) - base) / 60, sum(int(x['qty_after']) for x in rs), rs[0]['basket_status'], e) for e, rs in ev.items()], key=lambda x: (x[0], x[3]))
    got = [(float(r['minutes_since_creation']), int(r['basket_total_units_after']), r['basket_status'], r['event_id']) for r in tsv(plots / '02_basket_lifecycle.tsv')]
    assert got == want
    for n in ('s05_reentry_success', 's07_reentry_rejected_risk_limit', 's11_basket_lifecycle_demo'):
        st = table(logs(n)['states.tsv']); b0 = min(int(r['ts']) for r in st); seen = {(r['ts'], r['event_id']): (r['gross_units'], r['short_units']) for r in st}
        got = sorted((float(r['minutes_since_creation']), r['event_id'], r['gross_units'], r['short_units']) for r in tsv(plots / '03_exposure_over_time.tsv') if r['scenario'] == n)
        assert got == sorted(((int(k[0]) - b0) / 60, k[1], v[0], v[1]) for k, v in seen.items()), n
    for n in ('s02_partial_basket_cut', 's03_full_basket_cut', 's05_reentry_success', 's08_overlapping_baskets'):
        f = logs(n); cuts = {a['action_id']: a for a in table(f['actions.tsv']) if a['status'] == 'ACCEPTED' and a['type'] == 'CUT'}
        want = sorted((r['basket_id'], r['action_id'], r['leg_id'], r['qty_before'], r['qty_after']) for r in table(f['states.tsv']) if r['action_id'] in cuts and r['leg_id'] == cuts[r['action_id']]['leg_id'] and r['basket_id'] == cuts[r['action_id']]['basket_id'])
        assert sorted((r['basket_id'], r['action_id'], r['leg_id'], r['qty_before'], r['qty_after']) for r in tsv(plots / '04_leg_quantity_before_after_cuts.tsv') if r['scenario'] == n) == want, n


def test_reentry_timeline_data_equals_the_decision_and_action_logs(plots):
    for n in ('s05_reentry_success', 's06_reentry_rejected_cooldown', 's07_reentry_rejected_risk_limit'):
        f = logs(n); got = [r for r in tsv(plots / '05_reentry_decision_timeline.tsv') if r['scenario'] == n]
        acts = table(f['actions.tsv'])
        assert sum(r['layer'] == 'plugin decision' for r in got) == sum(d['plugin'] == 'basket_reentry' for d in table(f['decisions.tsv'])), n
        assert all(r['action_source'] == 'basket_reentry' for r in got if r['layer'] == 'plugin decision'), n
        assert sorted((r['layer'], r['action_source'], r['outcome_or_reason']) for r in got if r['layer'] != 'plugin decision') == \
            sorted((f"action ({a['type']})", a['plugin'], 'ACCEPTED' if a['status'] == 'ACCEPTED' else 'REJECTED: ' + a['reason']) for a in acts), n
