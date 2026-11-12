"""Stage 2 Milestone 1 tests.  Run:  ALGO8_MARKET_DIR=<normalized dir> python -m pytest stage2_alpha_research/tests -q
Synthetic tests need no data; real-data tests are skipped when the raw market directory is not available."""
import os, sys, hashlib
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); S2 = os.path.dirname(HERE); sys.path.insert(0, S2)
import s2common as sc
from targets import alignment as al
HAVE = bool(os.environ.get(sc.CFG['market']['env_var'])) and os.path.isdir(os.environ.get(sc.CFG['market']['env_var'], ''))
real = pytest.mark.skipif(not HAVE, reason='raw market directory not set')
F = sc.feature_library()


# ---------------------------------------------------------------- no silent substitution
def test_loader_raises_without_the_raw_directory(monkeypatch):
    monkeypatch.delenv(sc.CFG['market']['env_var'], raising=False)
    with pytest.raises(RuntimeError): sc.market_dir()

def test_loaders_do_not_reference_earlier_caches():
    src = open(os.path.join(S2, 's2common.py')).read()
    for banned in ('analysis/_cache', "'_cache', 'exit", 'ohlcv_research/_cache', 'exit_cm', 'exit_bm', 'exit_lots', 'robustness_results'):
        assert banned not in src, banned

def test_provisional_inputs_are_listed_as_excluded():
    ex = ' '.join(sc.CFG['excluded_provisional_inputs'])
    for p in ('exit_cm', 'exit_bm', 'exit_lots_cheap', 'exit_models', 'robustness_results'): assert p in ex


# ---------------------------------------------------------------- label alignment
@pytest.mark.parametrize('h', sc.CFG['targets']['candidate_horizons_min'])
def test_label_window_starts_at_the_decision_and_never_touches_feature_bars(h):
    for kd in al.valid_decisions(h):
        lb = al.label_bars(kd, h); fb = al.feature_bars(kd)
        assert lb[0] == kd and len(lb) == h and lb[-1] <= al.N - 1            # starts at the decision bar, ends inside the session
        assert len(fb) and fb.max() == kd - 1 and not set(fb) & set(lb)        # features: only bars completed before the decision
    assert len(al.label_bars(al.N - h + 1, h)) == 0                           # a window that would cross the close is invalid

@pytest.mark.parametrize('h', sc.CFG['targets']['candidate_horizons_min'])
def test_non_overlapping_grid_and_purge_radius(h):
    g = al.non_overlapping_decisions(h); assert (np.diff(g) == h).all()
    for a, b in zip(g[:-1], g[1:]): assert not set(al.label_bars(a, h)) & set(al.label_bars(b, h))
    assert set(al.label_bars(g[0], h)) & set(al.label_bars(g[0] + al.purge_radius(h) - 1, h))   # closer than the purge radius -> overlap


# ---------------------------------------------------------------- features: synthetic causality
def _synthetic_index(days=3, seed=0):
    rng = np.random.default_rng(seed); rows = []
    for d in pd.bdate_range('2026-01-05', periods=days):
        c = 20000 * np.exp(np.cumsum(rng.normal(0, 3e-4, sc.N))); o = np.r_[c[0], c[:-1]]
        ts = d + sc.OPEN + pd.to_timedelta(np.arange(sc.N), unit='min')
        rows.append(pd.DataFrame(dict(und='NIFTY', ts=ts, open=o, high=np.maximum(o, c) * 1.0002, low=np.minimum(o, c) * 0.9998, close=c)))
    return pd.concat(rows, ignore_index=True)

def test_feature_row_ignores_the_forming_candle_and_everything_after_it():
    I = _synthetic_index(); d = I.ts.dt.normalize().unique()[1]; cut = pd.Timestamp(d) + sc.OPEN + pd.Timedelta(minutes=137)
    full = F.index_features(I); J = I.copy(); fut = J.ts >= cut
    J.loc[fut, ['open', 'high', 'low', 'close']] *= 1.07                                              # perturb the forming candle and all later bars
    pert = F.index_features(J)
    a = full[full.m <= cut].reset_index(drop=True); b = pert[pert.m <= cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)
    assert not np.allclose(full[full.m > cut][F.INDEX_FEATURES].fillna(0).values, pert[pert.m > cut][F.INDEX_FEATURES].fillna(0).values)   # the test has power

def test_decision_minute_is_bar_start_plus_one_minute():
    I = _synthetic_index(days=2); X = F.index_features(I); d = X.date.iloc[0]
    assert X[X.date == d].m.min() == d + sc.OPEN + pd.Timedelta(minutes=1)
    r = X[(X.date == d)].set_index('m').ret_1m_bp; c = I.set_index('ts').close
    m = d + sc.OPEN + pd.Timedelta(minutes=50)
    assert np.isclose(r[m], 1e4 * np.log(c[m - pd.Timedelta(minutes=1)] / c[m - pd.Timedelta(minutes=2)]))   # row at m = log return of the bar that ended at m (catalog definition)


# ---------------------------------------------------------------- real data
@real
def test_real_market_tables_are_clean():
    I, O, man = sc.build_market()
    assert not I.duplicated(['und', 'ts']).any() and not O.duplicated(['und', 'expiry', 'strike', 'cp', 'ts']).any()
    assert (I.ts.dt.second == 0).all() and (O.ts.dt.second == 0).all()
    k = sc.session_minute(I.ts); assert k.between(0, sc.N - 1).all()
    d = I.assign(date=I.ts.dt.normalize()).groupby('und').date.unique()
    assert set(d['NIFTY']) == set(d['SENSEX']) and len(d['NIFTY']) == 85
    assert ((I.high >= I[['open', 'close']].max(axis=1)) & (I.low <= I[['open', 'close']].min(axis=1))).all()
    one = O.assign(date=O.ts.dt.normalize()).groupby(['und', 'date']).expiry.nunique(); assert (one == 1).all()

@real
def test_real_prefix_invariance_one_session():
    I, O, _ = sc.build_market(); u = 'SENSEX'; d = pd.Timestamp('2026-08-13'); days = [pd.Timestamp('2026-08-12'), d]
    Is = I[(I.und == u) & I.ts.dt.normalize().isin(days)]; Os = O[(O.und == u) & O.ts.dt.normalize().isin(days)]
    cut = d + sc.OPEN + pd.Timedelta(minutes=211)
    for fn, cols, keys in ((lambda i, o: F.index_features(i), F.INDEX_FEATURES, ['und', 'm']), (lambda i, o: F.straddle_features(o, i, sc.STEP), F.STRADDLE_FEATURES, ['und', 'expiry', 'm'])):
        a = fn(Is, Os); b = fn(Is[Is.ts < cut], Os[Os.ts < cut])
        a = a[(a.date == d) & (a.m <= cut)].sort_values(keys).reset_index(drop=True); b = b[(b.date == d) & (b.m <= cut)].sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a[keys + cols], b[keys + cols])

@real
def test_audit_outputs_have_no_failed_check_and_match_the_manifest():
    C = pd.read_csv(os.path.join(sc.RES, 'leakage_checks.csv')); assert len(C) >= 20 and (C.status != 'FAIL').all()
    M = pd.read_csv(os.path.join(sc.RES, 'dataset_manifest.csv'))
    lib = M[M.dataset.str.startswith('PR #6 feature library')].sha256.iloc[0]
    assert lib == hashlib.sha256(open(os.path.join(sc.REPO, 'ohlcv_research', 'features.py'), 'rb').read()).hexdigest()     # the library was not edited after the audit
    I = pd.read_csv(os.path.join(sc.RES, 'independence.csv')).set_index('item').value
    assert int(I['index session dates']) == 85 and int(I['option session dates']) == 67 and int(I['untouched (never inspected) dates']) == 0
