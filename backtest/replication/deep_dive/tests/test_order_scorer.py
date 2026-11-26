"""Verification of the order-level scorer (reports/ORDER_LEVEL_SCORING_SPEC.md v1.1, section 11). Synthetic inputs with answers derived independently, plus the LEGACY BRIDGE GATE:
the ORIGINAL lot-matching code, re-run on the stored replays, must reproduce the published 0.688 (D-1) and 0.410 (D0) before any new metric is trusted.
No new-framework scoring is run on real data here (the freeze record keeps first_scoring_run = null)."""
import os, sys, json, numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, '..'); sys.path.insert(0, f'{BASE}/src'); sys.path.insert(0, f'{BASE}/../..'); sys.path.insert(0, f'{BASE}/../../..'); sys.path.insert(0, f'{BASE}/../../../d1_strategy')
_cwd = os.getcwd(); os.chdir(f'{BASE}/src')
import bl_oscore as Q
os.chdir(_cwd)
OUT = f'{BASE}/outputs'
ATTR = pd.DataFrame([dict(cyc='C1', step=50.0, und='NIFTY', version='V2', era='after', stop=False, outlier=False), dict(cyc='C2', step=100.0, und='SENSEX', version='V1', era='before', stop=False, outlier=False)])
def real_df(rows):
    return pd.DataFrame(rows, columns=['cyc', 'day', 'cp', 'side', 'strike', 'lots', 't', 'cls', 'validity', 'module']).assign(row=lambda d: np.arange(len(d)))
def sim_from(real, dt=0.0, **over):
    s = real.drop(columns=['row']).copy(); s['t'] = s.t.astype(float) + dt; s['seq'] = np.arange(len(s)); s['t_resolution'] = 'second'
    for k, v in over.items(): s[k] = v
    return s
def synth(n=60, seed=0, spaced=False):
    """spaced=True puts every order of a (cycle, day) at least 300 s from every other, so no order can be matched to a neighbour after a shift of up to 120 s"""
    rng = np.random.default_rng(seed); rows = []
    for c in ('C1', 'C2'):
        for d in (0, 1):
            for k in range(n):
                t = int(34000 + 300 * k + rng.integers(0, 50)) if spaced else int(34000 + rng.integers(0, 20000))
                rows.append((c, d, rng.choice(['CE', 'PE']), rng.choice(['buy', 'sell']), float(24000 + 50 * rng.integers(-6, 7)), int(rng.choice([1, 1, 1, 2, 4])), t, rng.choice(['body_sell', 'wing_buy']), 'DAY', 'num'))
    return real_df(rows)
# ----------------------------------------------------------------------------------------------------------- 0. spec frozen
def test_scorer_checks_the_frozen_spec():
    r = Q.spec_record(); assert r['spec_version'] == '1.1' and len(r['spec_sha256']) == 64
    f = json.load(open(f'{OUT}/scoring/spec_freeze.json')); assert f['sha256'] == r['spec_sha256']
# ----------------------------------------------------------------------------------------------------------- 1. LEGACY BRIDGE (gate)
def test_legacy_bridge_d1_reproduces_published_0_688():
    import bl_fr_sim as S, bl_common
    ORD = pd.read_pickle(f'{OUT}/bl_d1eng_orders.pkl.gz'); got = Q.legacy_d1_scores(ORD, S.CY, S.REAL, bl_common.ref.STEP); pub = pd.read_csv(f'{OUT}/bl_d1eng_scores.csv').set_index('cls')
    a = got.set_index('cls').loc['ALL']; assert int(a.real_lots) == 13655 and int(a.sim_lots) == int(pub.loc['ALL', 'sim_lots']) and int(a.matched) == int(pub.loc['ALL', 'matched'])
    assert abs(a.F1 - 0.6878) < 5e-4 and abs(a.F1 - pub.loc['ALL', 'F1']) < 5e-4 and abs(a.precision - pub.loc['ALL', 'precision']) < 5e-4 and abs(a.recall - pub.loc['ALL', 'recall']) < 5e-4
    for c in ('body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'opening_wings', 'lump'): assert abs(got.set_index('cls').loc[c, 'F1'] - pub.loc[c, 'F1']) < 5e-4, c
def test_legacy_bridge_d0_reproduces_published_0_410():
    cwd = os.getcwd(); os.chdir(f'{BASE}/src')                                  # the D0 simulator module reads its helper scripts relative to the working directory
    try: import bl_d0_fr as F
    finally: os.chdir(cwd)
    RES = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz'); sims = {**RES['OOF half 0 test'], **RES['OOF half 1 test']}; got = Q.legacy_d0_scores(sims, F.D0C, F.CY, F.O, None); pub = pd.read_csv(f'{OUT}/bl_d0_fr_score.csv').set_index('split').loc['OOF (cycle halves)']
    assert got['real_lots'] == int(pub.real_lots) == 40874 and got['sim_lots'] == int(pub.sim_lots) and abs(got['F1'] - pub.F1) < 5e-4 and abs(got['F1'] - 0.410) < 1e-3 and abs(got['precision'] - pub.precision) < 5e-4
# ----------------------------------------------------------------------------------------------------------- 2. one-to-one, determinism, permutation invariance
def test_one_to_one_and_partition_identities():
    real = Q.prepare_real(synth()); sim = Q.prepare_sim(sim_from(real, dt=2.0).sample(frac=0.8, random_state=1)); P = Q.match_orders(real, sim, ATTR.set_index('cyc').step.to_dict())
    assert P.ri.is_unique and P.si.is_unique and len(P) <= min(len(real), len(sim)); T = Q.tier_tables(real, sim, P)
    assert int(T[T.tier.isin(['exact', 'near', 'broad'])].matched.sum()) == len(P) and int(T.iloc[3].missing_real) == len(real) - len(P) and int(T.iloc[3].extra_sim) == len(sim) - len(P)     # matched + missing = real; matched + extra = simulated
def test_determinism_and_permutation_invariance():
    real = Q.prepare_real(synth(seed=3)); sim = Q.prepare_sim(sim_from(real, dt=7.0, strike=real.strike.values + 50.0)); step = ATTR.set_index('cyc').step.to_dict(); P = Q.match_orders(real, sim, step)
    P2 = Q.match_orders(real, sim, step); assert P.equals(P2)
    rp = real.sample(frac=1.0, random_state=5); sp = sim.sample(frac=1.0, random_state=6); Pp = Q.match_orders(Q.prepare_real(rp.drop(columns=['sec'])), Q.prepare_sim(sp.drop(columns=['sec'])), step)
    a = set(zip(real.row[P.ri], sim.seq[P.si])); rp2 = Q.prepare_real(rp.drop(columns=['sec'])); sp2 = Q.prepare_sim(sp.drop(columns=['sec'])); b = set(zip(rp2.row[Pp.ri], sp2.seq[Pp.si]))
    assert a == b and set(P.tier) == set(Pp.tier)
# ----------------------------------------------------------------------------------------------------------- 3. exclusive tiers and cumulative shares
def test_exclusive_tiers_and_cumulative_shares():
    rows = [('C1', 0, 'CE', 'sell', 24000.0, 1, 1000 + 100 * k, 'body_sell', 'DAY', 'num') for k in range(4)]; real = Q.prepare_real(real_df(rows))
    sim = Q.prepare_sim(sim_from(real_df(rows), dt=0).assign(t=[1000.0, 1103.0, 1230.0, 1500.0 + 70], seq=range(4), t_resolution='second')); P = Q.match_orders(real, sim, {'C1': 50.0})
    assert sorted(zip(P.ri, P.tier)) == [(0, 0), (1, 1), (2, 2)]                                          # 0 s exact, 3 s near, 30 s broad, 70 s unmatched
    T = Q.tier_tables(real, sim, P); assert list(T.matched[:3]) == [1, 1, 1] and list(T.cumulative_matched[:3]) == [1, 2, 3] and int(T.iloc[3].missing_real) == 1 and int(T.iloc[3].extra_sim) == 1
# ----------------------------------------------------------------------------------------------------------- 4. perfect reproduction and k-second shifts
def test_perfect_reproduction_gives_every_metric_one():
    real = synth(seed=1); sim = sim_from(real); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', bootstrap=50)
    S = R['strictness']; assert (S.F1 == 1.0).all() and int(R['tiers'].iloc[0].matched) == len(real) and R['quantity']['lots_exact_share'] == 1.0 and R['strike']['exact_share'] == 1.0 and R['type']['available'] and R['type']['agreement'] == 1.0
    assert R['unmatched']['totals'] == dict(missing_orders=0, missing_lots=0, extra_orders=0, extra_lots=0) and R['per_cycle_F1']['min'] == 1.0 and R['per_cycle_F1']['below_0_5'] == 0
    assert (R['state_after_matched'].SL_equal).all() and R['state_after_matched'].l1.max() == 0
@pytest.mark.parametrize('k,tier,cum', [(0, 0, 0), (1, 1, 5), (3, 1, 5), (5, 1, 5), (6, 2, 60), (30, 2, 60), (60, 2, 60)])
def test_shift_by_k_seconds_lands_in_the_tier_that_contains_k(k, tier, cum):
    real = synth(seed=2, n=20, spaced=True); R = Q.score(real, sim_from(real, dt=float(k)), ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); T = R['tiers']
    assert int(T.matched[tier]) == len(real) and all(int(T.matched[i]) == 0 for i in range(3) if i != tier)
    S = R['strictness'].query('level=="keys"').set_index('cumulative_tolerance_s').F1; assert S[cum] == 1.0 and all(S[c] == 0.0 for c in (0, 5, 60) if c < cum)
def test_shift_beyond_sixty_seconds_is_unmatched():
    real = synth(seed=2, n=20, spaced=True); R = Q.score(real, sim_from(real, dt=61.0), ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); assert int(R['tiers'].iloc[0:3].matched.sum()) == 0 and R['unmatched']['totals']['missing_orders'] == len(real) and R['unmatched']['totals']['extra_orders'] == len(real)
# ----------------------------------------------------------------------------------------------------------- 5. cumulativeness and placebo
def test_cumulative_F1_never_decreases_with_tolerance():
    real = synth(seed=4); rng = np.random.default_rng(4); sim = sim_from(real).assign(t=lambda d: d.t + rng.integers(-40, 41, len(d)).astype(float)); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', bootstrap=0)
    for lvl in ('keys', 'strike_within_1', 'strike_exact', 'lots_exact', 'type'):
        f = R['strictness'].query('level==@lvl').sort_values('cumulative_tolerance_s').F1.values; assert (np.diff(f) >= -1e-12).all(), lvl
def test_time_shift_placebo_lowers_time_specific_agreement():
    real = synth(seed=5); sim = sim_from(real, dt=1.0); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', bootstrap=0)
    assert R['time_shift_placebo']['F1_keys_at_60s'] < 0.2 < R['strictness'].query('level=="keys" and cumulative_tolerance_s==60').F1.iloc[0] and 'not a universal random-chance baseline' in R['time_shift_placebo']['note']
# ----------------------------------------------------------------------------------------------------------- 6. ambiguity
def test_same_second_ambiguity_is_flagged_and_range_reported():
    rows = [('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num'), ('C1', 0, 'CE', 'sell', 24050.0, 1, 1000, 'body_sell', 'DAY', 'num')]; real = real_df(rows)
    sim = sim_from(real).assign(strike=[24050.0, 24000.0]); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
    assert R['ambiguity']['real_share'] == 1.0 and R['ambiguity']['sim_share'] == 1.0                      # two same-second orders with differing strikes on both sides
    rng_ = R['tie_break_range']['strike_exact@0s']; assert rng_[0] is not None and rng_[0] <= rng_[1]
    clean = real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num'), ('C1', 0, 'CE', 'sell', 24000.0, 1, 1060, 'body_sell', 'DAY', 'num')]); R2 = Q.score(clean, sim_from(clean), ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); assert R2['ambiguity']['real_share'] == 0.0
# ----------------------------------------------------------------------------------------------------------- 7. state, type availability, labels, per-cycle
def test_state_metrics_on_a_hand_built_day():
    rows = [('C1', 0, 'CE', 'sell', 24000.0, 2, 1000, 'body_sell', 'DAY', 'num'), ('C1', 0, 'PE', 'sell', 23900.0, 2, 1010, 'body_sell', 'DAY', 'num'), ('C1', 0, 'CE', 'buy', 24500.0, 2, 1020, 'wing_buy', 'IOC', 'h_')]; real = real_df(rows)
    sim = sim_from(real).assign(lots=[2, 1, 2]); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); X = R['state_after_matched'].sort_values('ri').reset_index(drop=True)
    assert list(X.SL_equal) == [True, False, False] and X.l1.tolist() == [0.0, 1.0, 1.0] and X.S_real_PE[1] == 2 and X.S_sim_PE[1] == 1 and X.L_real_CE[2] == 2
    assert not R['checkpoints'].empty and R['checkpoints'].end_of_day.sum() == 1
def test_type_not_available_without_validity_is_reported_not_assumed():
    real = synth(seed=6, n=10); sim = sim_from(real).drop(columns=['validity', 'module']); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
    assert not R['type']['available'] and R['strictness'].query('level=="type"').F1.isna().all()
def test_mode_and_label_are_mandatory_and_validated():
    real = synth(seed=7, n=5)
    with pytest.raises(AssertionError): Q.score(real, sim_from(real), ATTR, 'free', 'historical reproduction')
    with pytest.raises(AssertionError): Q.score(real, sim_from(real), ATTR, 'F', 'good')
    R = Q.score(real, sim_from(real), ATTR, 'TF-E', 'independent', shift_placebo=False, bootstrap=0); assert R['run']['mode'] == 'TF-E' and R['run']['evidence_label'] == 'independent'
def test_per_cycle_distribution_names_worst_cycles():
    real = synth(seed=8, n=40); sim = sim_from(real); bad = sim.cyc == 'C2'; sim = sim[~bad | (np.arange(len(sim)) % 4 == 0)]; R = Q.score(real, sim.reset_index(drop=True), ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); d = R['per_cycle_F1']
    assert d['n'] == 2 and d['worst_five'][0][0] == 'C2' and d['min'] < d['max'] == 1.0 and d['below_0_5'] == 1 and R['per_cycle'].set_index('cyc').loc['C1', 'F1'] == 1.0

def test_fractional_simulated_seconds_use_floor():
    """spec 11.8: the simulated second is floor(t): 1000.9 is the same second as 1000 (Exact); 1001.0 is one second later (Near); 1005.9 is 5 s (Near); 1006.0 is 6 s (Broad); 1060.99 is 60 s (Broad); 1061.0 is unmatched"""
    real = Q.prepare_real(real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000 + 1000 * k, 'body_sell', 'DAY', 'num') for k in range(6)]))
    ts = [1000.9, 2001.0, 3005.9, 4006.0, 5060.99, 6061.0]; sim = Q.prepare_sim(sim_from(real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000 + 1000 * k, 'body_sell', 'DAY', 'num') for k in range(6)])).assign(t=ts)); P = Q.match_orders(real, sim, {'C1': 50.0})
    assert dict(zip(P.ri, P.tier)) == {0: 0, 1: 1, 2: 1, 3: 2, 4: 2}
def test_one_to_one_guard_fires_if_the_assignment_ever_returns_a_duplicate(monkeypatch):
    real = Q.prepare_real(real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num'), ('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num')])); sim = Q.prepare_sim(sim_from(real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num')] * 2)))
    monkeypatch.setattr(Q, 'linear_sum_assignment', lambda C: (np.array([0, 1]), np.array([0, 0])))          # a buggy solver pairing two real orders with the same simulated order
    with pytest.raises(AssertionError): Q.match_orders(real, sim, {'C1': 50.0})
# ----------------------------------------------------------------------------------------------------------- review additions (self-review of the scorer against spec v1.1)
def test_partial_validity_is_excluded_not_assumed():
    real = synth(seed=9, n=10); sim = sim_from(real); sim.loc[sim.index[: len(sim) // 2], 'validity'] = np.nan; R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
    assert R['type']['available'] and 0.4 < R['type']['coverage_of_matched'] < 0.6 and R['type']['agreement'] == 1.0                  # agreement computed on supplied validity only
    S = R['strictness'].query('level=="type" and cumulative_tolerance_s==60').iloc[0]; assert S.matched < len(real) and S.matched >= len(real) // 2 - 1      # unsupplied pairs cannot be full matches
def test_validity_mismatch_is_scored_and_module_is_compared():
    real = synth(seed=10, n=10); sim = sim_from(real).assign(validity='IOC'); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); assert R['type']['agreement'] == 0.0 and R['strictness'].query('level=="type" and cumulative_tolerance_s==60').F1.iloc[0] == 0.0
    sim2 = sim_from(real).assign(module='h_'); assert Q.score(real, sim2, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)['type']['agreement'] == 0.0
def test_report_has_every_table_the_spec_requires():
    real = synth(seed=11, n=30); rng = np.random.default_rng(1); sim = sim_from(real).assign(t=lambda d: d.t + rng.integers(-30, 31, len(d)).astype(float)); R = Q.score(real, sim, ATTR, 'F', 'out-of-fold', bootstrap=200)
    for k in ('tiers', 'strictness', 'timing', 'key_level', 'strike', 'quantity', 'burst_lots', 'type', 'unmatched', 'per_cycle', 'per_cycle_F1', 'per_cycle_lot_abs_error', 'per_cycle_state_error', 'state_summary', 'state_after_matched', 'checkpoints', 'time_shift_placebo', 'by_attribute', 'by_class', 'by_block', 'timing_by_class', 'ambiguity', 'tie_break_range', 'pooled_F1_ci95', 'pooled_F1_strike_lots_exact_ci95', 'run'): assert k in R, k
    assert (R['by_block'].real.sum() == len(real)) and R['by_block'].matched_by_real_block.sum() == len(R['_pairs']) and 'ambiguous' in R['state_after_matched']
    assert set(R['by_attribute']) == {'und', 'version', 'era'} and R['pooled_F1_ci95'][0] <= R['pooled_F1_ci95'][1]
def test_variants_split_outlier_and_stop_cycles():
    real = synth(seed=12, n=20); at = ATTR.assign(outlier=[False, True], stop=[True, False]); V = Q.variants(real, sim_from(real), at, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
    assert set(V) == {'all', 'without_outlier', 'non_stop', 'stop_only'} and V['all']['run']['real_orders'] == len(real) and V['without_outlier']['run']['cycles'] == 1 and V['stop_only']['run']['cycles'] == 1 and V['non_stop']['run']['cycles'] == 1
def test_matching_maximises_the_number_of_matches_then_minimises_cost():
    """documented reading of 'minimum-cost assignment': among tier-eligible pairs the assignment first maximises the number of matches (a cheap pairing must not block a second match)"""
    real = Q.prepare_real(real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num'), ('C1', 0, 'CE', 'sell', 24000.0, 1, 1004, 'body_sell', 'DAY', 'num')]))
    sim = Q.prepare_sim(sim_from(real_df([('C1', 0, 'CE', 'sell', 24000.0, 1, 1000, 'body_sell', 'DAY', 'num')] * 2)).assign(t=[1002.0, 1008.0]))
    P = Q.match_orders(real, sim, {'C1': 50.0}); assert len(P) == 2 and set(P.ri) == {0, 1} and set(P.si) == {0, 1}         # both real orders are matched; no match is sacrificed for a cheaper one
def test_class_table_is_two_sided_and_never_exceeds_one():
    """review finding from the first D-1 run: with class-blind keys a real class can match a simulated order of ANOTHER class; the first version of the class table divided real-side matches by simulated counts and gave F1 = 1.008"""
    real = real_df([('C1', 0, 'CE', 'buy', 24000.0, 1, 1000 + 500 * k, 'body_buyback', 'DAY', 'num') for k in range(4)]); sim = sim_from(real).assign(cls='wing_buy', validity='IOC', module='h_')              # same keys, different class and type
    R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0); T = R['by_class'].set_index('cls')
    assert T.loc['body_buyback', 'recall'] == 1.0 and T.loc['body_buyback', 'sim'] == 0 and np.isnan(T.loc['body_buyback', 'precision'])                                   # real orders found partners, but no simulated order claims the class
    assert T.loc['wing_buy', 'precision'] == 1.0 and T.loc['wing_buy', 'matched_same_class'] == 0 and (T.F1.dropna() <= 1.0).all()
    C = R['class_confusion'].set_index('cls'); assert int(C.loc['body_buyback', 'wing_buy']) == 4 and R['type']['agreement'] == 0.0                                  # the cross-class pairs are visible, and the type level refuses to count them
def test_by_class_never_exceeds_one_on_random_data():
    real = synth(seed=13, n=40); rng = np.random.default_rng(13); sim = sim_from(real).assign(cls=lambda d: rng.choice(['body_sell', 'wing_buy', 'lump'], len(d))); R = Q.score(real, sim, ATTR, 'F', 'historical reproduction', shift_placebo=False, bootstrap=0)
    assert (R['by_class'].F1.dropna() <= 1.0 + 1e-12).all() and int(R['class_confusion'].drop(columns='cls').values.sum()) == len(R['_pairs'])
