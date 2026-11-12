"""Stage 2 Milestone 2 tests: targets, baseline predictors, chronological validation, inference tools, costs, reproducibility.
ALGO8_MARKET_DIR=<normalized dir> python -m pytest stage2_alpha_research/tests -q"""
import os, sys, glob
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); S2 = os.path.dirname(HERE); sys.path.insert(0, S2)
import s2common as sc
from targets import targets as tg
from baselines import predictors as pr
from validation import splits as sp, inference as inf, costs as cs
HAVE = bool(os.environ.get(sc.CFG['market']['env_var'])) and os.path.isdir(os.environ.get(sc.CFG['market']['env_var'], ''))
real = pytest.mark.skipif(not HAVE, reason='raw market directory not set')
N = 375; HS = [5, 15, 30, 60]


def _mats(seed=0, D=3):
    rng = np.random.default_rng(seed); C = 20000 * np.exp(np.cumsum(rng.normal(0, 3e-4, (D, N)), axis=1))
    O = np.concatenate([C[:, :1] * 1.0001, C[:, :-1] * (1 + rng.normal(0, 5e-5, (D, N - 1)))], axis=1)          # opens differ from the previous close
    H = np.maximum(O, C) * (1 + np.abs(rng.normal(0, 1e-4, (D, N)))); L = np.minimum(O, C) * (1 - np.abs(rng.normal(0, 1e-4, (D, N))))
    return O, H, L, C


# ---------------------------------------------------------------- locked configuration
def test_locked_decisions():
    c = sc.CFG
    assert c['targets']['horizons_min'] == [15, 30, 60] and c['targets']['sensitivity_horizons_min'] == [5]
    assert c['targets']['entry_reference'] == 'open_of_decision_bar' and c['targets']['cross_session_labels'] is False
    assert c['validation']['primary_folds'] == {'train': 43, 'validation': 22, 'test': 20} and c['validation']['stability_blocks'] == 4 and c['validation']['shuffle'] is False
    assert c['options']['d0_max_verdict'] == 'INCONCLUSIVE' and c['options']['universe_derived_features_allowed'] is False


# ---------------------------------------------------------------- targets
@pytest.mark.parametrize('h', HS)
def test_targets_match_brute_force_definitions(h):
    O, H, L, C = _mats(); T = tg.targets_matrix(O, H, L, C, h); rng = np.random.default_rng(h)
    for d in range(O.shape[0]):
        for kd in list(rng.integers(0, N - h + 1, 25)) + [0, N - h]:
            lab = range(kd, kd + h)
            r = 1e4 * np.log(C[d, kd + h - 1] / O[d, kd])
            rv = 1e4 * np.sqrt(np.log(C[d, kd] / O[d, kd]) ** 2 + sum(np.log(C[d, k] / C[d, k - 1]) ** 2 for k in range(kd + 1, kd + h)))
            rg = 1e4 * (max(H[d, k] for k in lab) - min(L[d, k] for k in lab)) / O[d, kd]
            assert np.isclose(T['r_bp'][d, kd], r) and np.isclose(T['rv_bp'][d, kd], rv) and np.isclose(T['rg_bp'][d, kd], rg)
            if kd >= h:
                tr = range(kd - h, kd); rex = (max(H[d, k] for k in lab) - min(L[d, k] for k in lab)) / (max(H[d, k] for k in tr) - min(L[d, k] for k in tr))
                assert np.isclose(T['rex'][d, kd], rex)
            else: assert np.isnan(T['rex'][d, kd])

@pytest.mark.parametrize('h', HS)
def test_targets_start_at_the_entry_open_and_end_inside_the_window(h):
    O, H, L, C = _mats(1); T0 = tg.targets_matrix(O, H, L, C, h); kd = 140
    # (a) nothing before the decision bar matters: scale every bar before kd, including the last completed close C[kd-1]
    O1, H1, L1, C1 = (x.copy() for x in (O, H, L, C))
    for x in (O1, H1, L1, C1): x[:, :kd] *= 1.03
    T1 = tg.targets_matrix(O1, H1, L1, C1, h)
    for k in ('r_bp', 'rv_bp', 'rg_bp'): assert np.allclose(T0[k][:, kd], T1[k][:, kd])           # no price gap from C[kd-1] enters r, RV or RG
    # (b) nothing after the label window matters
    O2, H2, L2, C2 = (x.copy() for x in (O, H, L, C))
    for x in (O2, H2, L2, C2): x[:, kd + h:] *= 0.97
    T2 = tg.targets_matrix(O2, H2, L2, C2, h)
    for k in ('r_bp', 'rv_bp', 'rg_bp', 'rex'): assert np.allclose(T0[k][:, kd], T2[k][:, kd])
    # (c) the entry reference is the open of the decision bar: changing only O[kd] changes r by exactly the log ratio
    O3 = O.copy(); O3[:, kd] *= 1.001; T3 = tg.targets_matrix(O3, np.maximum(H, O3), np.minimum(L, O3), C, h)
    assert np.allclose(T3['r_bp'][:, kd] - T0['r_bp'][:, kd], -1e4 * np.log(1.001))
    # (d) the last label bar is kd+h-1: changing C[kd+h] alone changes nothing, changing C[kd+h-1] changes r
    C4 = C.copy(); C4[:, kd + h] *= 1.01; assert np.allclose(tg.targets_matrix(O, np.maximum(H, C4), L, C4, h)['r_bp'][:, kd], T0['r_bp'][:, kd])
    C5 = C.copy(); C5[:, kd + h - 1] *= 1.01; assert not np.allclose(tg.targets_matrix(O, np.maximum(H, C5), L, C5, h)['r_bp'][:, kd], T0['r_bp'][:, kd])

@pytest.mark.parametrize('h', HS)
def test_targets_never_cross_the_session_end_and_missing_bars_invalidate(h):
    O, H, L, C = _mats(2); T = tg.targets_matrix(O, H, L, C, h)
    assert np.isfinite(T['r_bp'][:, N - h]).all() and np.isnan(T['r_bp'][:, N - h + 1:]).all() and np.isnan(T['rv_bp'][:, N - h + 1:]).all()
    C2 = C.copy(); C2[0, 200] = np.nan; H2 = H.copy(); H2[0, 200] = np.nan; L2 = L.copy(); L2[0, 200] = np.nan; O2 = O.copy(); O2[0, 200] = np.nan
    T2 = tg.targets_matrix(O2, H2, L2, C2, h)
    for kd in range(200 - h + 1, 201):
        for k in ('r_bp', 'rv_bp', 'rg_bp'): assert np.isnan(T2[k][0, kd])                         # any missing bar in the window -> NaN
    assert np.isfinite(T2['r_bp'][0, 200 - h]) and np.isfinite(T2['r_bp'][1, 200])

def test_straddle_target_uses_entry_opens_and_exit_closes_of_the_fixed_strike():
    d = pd.Timestamp('2026-01-06'); e = d; rows = []
    for cp, base in (('CE', 100.0), ('PE', 80.0)):
        for k in range(N): rows.append(dict(und='NIFTY', expiry=e, strike=24000.0, cp=cp, ts=d + sc.OPEN + pd.Timedelta(minutes=k), open=base + k, high=base + k + 2, low=base + k - 1, close=base + k + 1, volume=65))
    Opt = pd.DataFrame(rows); Z = pd.DataFrame(dict(und='NIFTY', expiry=e, date=d, m=[d + sc.OPEN + pd.Timedelta(minutes=16)], atm_strike=24000.0))
    S = tg.straddle_targets(Opt, Z, [15], {15: [16]})
    pin = (100 + 16) + (80 + 16); pout = (100 + 30 + 1) + (80 + 30 + 1)
    assert np.isclose(S.p_in.iloc[0], pin) and np.isclose(S.p_out.iloc[0], pout) and np.isclose(S.straddle_chg_pct.iloc[0], 100 * (pout / pin - 1)) and S.day.iloc[0] == 'D0'
    S2 = tg.straddle_targets(Opt[~((Opt.cp == 'PE') & (Opt.ts == d + sc.OPEN + pd.Timedelta(minutes=30)))], Z, [15], {15: [16]}); assert np.isnan(S2.straddle_chg_pct.iloc[0])


# ---------------------------------------------------------------- baseline predictors
@pytest.mark.parametrize('h', HS)
def test_trailing_predictors_use_only_completed_bars(h):
    O, H, L, C = _mats(3); P = pr.trailing_matrix(O, H, L, C, h); kd = 170
    d2 = [np.log(C[0, k] / (C[0, k - 1] if k else O[0, 0])) ** 2 for k in range(kd - h, kd)]
    assert np.isclose(P['trv_bp'][0, kd], 1e4 * np.sqrt(sum(d2)))
    assert np.isclose(P['trg_bp'][0, kd], 1e4 * (H[0, kd - h:kd].max() - L[0, kd - h:kd].min()) / C[0, kd - 1])
    O1, H1, L1, C1 = (x.copy() for x in (O, H, L, C))
    for x in (O1, H1, L1, C1): x[:, kd:] *= 1.05                                                   # the forming bar and everything after it
    P1 = pr.trailing_matrix(O1, H1, L1, C1, h)
    assert np.allclose(P['trv_bp'][:, :kd + 1], P1['trv_bp'][:, :kd + 1], equal_nan=True) and np.allclose(P['trg_bp'][:, :kd + 1], P1['trg_bp'][:, :kd + 1], equal_nan=True)
    assert np.isnan(P['trv_bp'][:, :h]).all() and np.isfinite(P['trv_bp'][:, h]).all()

def test_momentum_predictor_is_the_library_trailing_return():
    F = sc.feature_library(); d = pd.Timestamp('2026-01-06'); O, H, L, C = _mats(4, D=1)
    I = pd.DataFrame(dict(und='NIFTY', ts=d + sc.OPEN + pd.to_timedelta(np.arange(N), unit='min'), open=O[0], high=H[0], low=L[0], close=C[0])); X = F.index_features(I).set_index('m')
    for h in (15, 30, 60):
        kd = 200; m = d + sc.OPEN + pd.Timedelta(minutes=kd)
        assert np.isclose(X.loc[m, f'ret_{h}m_bp'], 1e4 * np.log(C[0, kd - 1] / C[0, kd - 1 - h]))    # bars kd-1-h ... kd-1: all completed before m


# ---------------------------------------------------------------- validation design
def test_primary_folds_are_chronological_date_blocks():
    dates = pd.bdate_range('2026-01-01', periods=85); f = sp.primary_folds(list(dates[::-1]), sc.CFG['validation']['primary_folds'])
    assert f.value_counts().to_dict() == {'TRAIN': 43, 'VAL': 22, 'TEST': 20}
    assert f[f == 'TRAIN'].index.max() < f[f == 'VAL'].index.min() and f[f == 'VAL'].index.max() < f[f == 'TEST'].index.min()
    assert list(f.index) == sorted(f.index)                                                        # never shuffled

def test_stability_blocks_are_contiguous():
    dates = pd.bdate_range('2026-01-01', periods=85); b = sp.stability_blocks(dates, 4)
    assert b.value_counts().sort_index().tolist() == [22, 21, 21, 21] and (np.diff(b.values) >= 0).all() and set(b) == {1, 2, 3, 4}

@pytest.mark.parametrize('h,n', [(5, 73), (15, 23), (30, 11), (60, 5)])
def test_purged_grid_has_no_overlapping_label_windows(h, n):
    g = sp.grid(h); assert len(g) == n and g[0] == h + 1 and (np.diff(g) == h).all() and g[-1] + h <= N
    wins = [set(range(k, k + h)) for k in g]; assert all(not (a & b) for a, b in zip(wins[:-1], wins[1:]))
    for phase in range(h):
        gp = sp.grid(h, phase); assert gp[0] - h - 1 >= 0 and gp[-1] + h <= N and (np.diff(gp) == h).all()
    assert set(g) <= set(sp.valid_range(h)) and len(sp.valid_range(h)) == N - 2 * h


# ---------------------------------------------------------------- inference tools
def test_bootstrap_resamples_whole_dates_and_is_reproducible():
    dates = np.repeat(np.arange(30), 7); val = dates.astype(float)
    whole = lambda v: float(all(c % 7 == 0 for c in np.unique(v, return_counts=True)[1]))            # 1.0 only if every date enters as a whole cluster
    for bl in (1, 5):
        p, lo, hi, n = inf.cluster_bootstrap(whole, dates, [val], reps=200, seed=1, block_len=bl); assert (p, lo, hi, n) == (1.0, 1.0, 1.0, 30)
    a = inf.cluster_bootstrap(lambda v: float(v.mean()), dates, [val], reps=300, seed=7); b = inf.cluster_bootstrap(lambda v: float(v.mean()), dates, [val], reps=300, seed=7); assert a == b

def test_date_permutation_detects_a_planted_relation_and_not_a_null_one():
    rng = np.random.default_rng(0); X = {u: rng.normal(size=(60, 10)) for u in 'ab'}
    Yp = {u: 0.5 * X[u] + rng.normal(size=(60, 10)) for u in 'ab'}; Yn = {u: rng.normal(size=(60, 10)) for u in 'ab'}
    assert inf.date_permutation_p(inf.spearman, X, Yp, reps=400, seed=1)[1] < 0.01 and inf.date_permutation_p(inf.spearman, X, Yn, reps=400, seed=1)[1] > 0.05

def test_multiple_testing_adjustments():
    assert np.allclose(inf.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06]) and np.allclose(inf.bh([0.01, 0.04, 0.03]), [0.03, 0.04, 0.04])
    assert np.allclose(inf.holm([0.5, 0.5]), [1.0, 1.0])


# ---------------------------------------------------------------- costs and inputs
def test_cost_scenarios_are_the_registered_ones_unchanged():
    K = cs.registered()
    assert K == {'zero': (0.0, 0.0, 0.0), 'moderate': (0.0025, 20.0, 0.05), 'conservative': (0.005, 20.0, 0.10), 'adverse': (0.005, 40.0, 0.20)}
    assert {k: list(v) for k, v in K.items()} == sc.CFG['costs']['expected']
    rs, sh = cs.straddle_round_trip(100.0, 65, 'moderate'); assert np.isclose(rs, 0.0025 * 2 * 100 * 65 + 20 * 4 + 0.05 * 4 * 65) and np.isclose(sh, rs / 6500)

def test_no_excluded_or_universe_input_in_stage2_research_code():
    banned = ('exit_cm', 'exit_bm', 'exit_lots', 'exit_models', 'robustness_results', 'analysis/_cache', 'ohlcv_research/_cache', 'rr_common', 'load_tagged', 'Trades_GKOHNP140', 'pair_strikes', 'straddle_coverage')
    for f in glob.glob(os.path.join(S2, 'baselines', '*.py')) + glob.glob(os.path.join(S2, 'targets', '*.py')) + glob.glob(os.path.join(S2, 'validation', '*.py')):
        src = open(f).read()
        for b in banned: assert b not in src, (os.path.basename(f), b)


# ---------------------------------------------------------------- real data and saved results
@real
def test_real_panel_alignment_clusters_and_library_equality():
    from baselines import run_baselines as rb
    T, mats, Opt, Z = rb.build_panel([15, 60]); dates = sorted(T.date.unique()); f = sp.primary_folds(dates, sc.CFG['validation']['primary_folds']); T['fold'] = T.date.map(f)
    assert len(dates) == 85 and (T.groupby('date').fold.nunique() == 1).all() and (T.groupby('date').und.nunique() == 2).all()      # both indices of a date share one fold
    assert (T.kd + T.h <= N).all() and (T.m == T.date + sc.OPEN + pd.to_timedelta(T.kd, unit='min')).all()
    u, (ds, O, H, L, C) = 'NIFTY', mats['NIFTY']; x = T[(T.und == u) & (T.h == 15) & (T.kd == 100)].sort_values('date')
    assert np.allclose(x.r.values, 1e4 * np.log(C[:, 114] / O[:, 100]), equal_nan=True)                                         # entry = open of the decision bar, exit = close of bar kd+h-1
    assert np.allclose(x.tr.values, 1e4 * np.log(C[:, 99] / C[:, 84]), equal_nan=True)                                         # predictor = completed bars only

@real
def test_saved_baseline_results_reproduce_from_the_saved_configuration():
    import yaml
    from baselines import run_baselines as rb
    snap = yaml.safe_load(open(os.path.join(sc.RES, 'm2_config_snapshot.yaml'))); assert snap == sc.CFG
    saved = pd.read_csv(os.path.join(sc.RES, 'm2_baseline_metrics.csv')); keep = saved.copy()
    new = rb.main(bootstrap=False, save=False)
    key = ['horizon_min', 'role', 'target', 'baseline', 'metric', 'segment', 'scope']
    m = keep[key + ['value', 'n_obs']].merge(new[key + ['value', 'n_obs']], on=key, suffixes=('_saved', '_new'))
    assert len(m) == len(keep) and np.allclose(m.value_saved, m.value_new, equal_nan=True, rtol=1e-9, atol=1e-12) and (m.n_obs_saved == m.n_obs_new).all()

@real
def test_saved_outputs_respect_the_scope_rules():
    M = pd.read_csv(os.path.join(sc.RES, 'm2_baseline_metrics.csv')); C = pd.read_csv(os.path.join(sc.RES, 'm2_sample_counts.csv')); S = pd.read_csv(os.path.join(sc.RES, 'm2_straddle_baselines.csv'))
    assert set(M[M.role == 'primary'].horizon_min) == {15, 30, 60} and set(M[M.role != 'primary'].horizon_min) == {5}
    assert set(M.baseline) == {'BL1 no signal', 'BL2 time of day', 'BL3 momentum', 'BL4 mean reversion', 'BL5 volatility only'}
    assert (C.candidates_before_purging - C.kept_on_non_overlapping_grid == C.removed_by_purging).all() and (C.dates_TRAIN == 43).all() and (C.dates_VAL == 22).all() and (C.dates_TEST == 20).all()
    assert S[S.day == 'D0'].max_verdict.str.startswith('INCONCLUSIVE').all()
    F = pd.read_csv(os.path.join(sc.RES, 'm2_folds.csv')); assert F.fold.value_counts().to_dict() == {'TRAIN': 43, 'VAL': 22, 'TEST': 20} and F.date.is_monotonic_increasing


@real
def test_closing_zone_classification_and_primary_effect_is_small():
    """frozen closing bars (register DAT-15): 48 + 48 frozen sessions, none before bar 300; primary grid barely touched"""
    S = pd.read_csv(os.path.join(sc.RES, 'm2_closing_zone_sessions.csv')); R = pd.read_csv(os.path.join(sc.RES, 'm2_closing_zone_sensitivity.csv'))
    assert S.groupby(['und', 'status']).size().to_dict() == {('NIFTY', 'clean'): 29, ('NIFTY', 'frozen tail'): 48, ('NIFTY', 'missing bars'): 8,
                                                              ('SENSEX', 'clean'): 29, ('SENSEX', 'frozen tail'): 48, ('SENSEX', 'missing bars'): 8}
    assert (S.frozen_before_bar_300 == 0).all() and S[S.status == 'frozen tail'].first_frozen_bar.between(360, 362).all()
    P = R[(R.phase == 0) & R.horizon_min.isin([15, 30, 60])]
    a = P[P.rows == 'all grid rows'].set_index('horizon_min'); b = P[P.rows != 'all grid rows'].set_index('horizon_min')
    assert (a.touching_rows_in_all <= 11).all() and ((a.bl3_rank_ic - b.bl3_rank_ic).abs() < 0.01).all()
