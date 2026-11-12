"""Milestone 2: the five registered baselines on the locked targets, with the locked chronological validation.
No alpha family is tested here and no model beyond means, signs and persistence is used.
python3 stage2_alpha_research/baselines/run_baselines.py [--no-bootstrap]   -> stage2_alpha_research/results/m2_*.csv"""
import os, sys, time, shutil
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); S2 = os.path.dirname(HERE); sys.path.insert(0, S2)
import s2common as sc
from targets import targets as tg
from baselines import predictors as pr
from validation import splits as sp, inference as inf, costs as cs
CFG = sc.CFG; RES = sc.RES; N = sc.N
PRIMARY = list(CFG['targets']['horizons_min']); SENS = list(CFG['targets']['sensitivity_horizons_min'])
BW = int(CFG['baselines']['time_of_day_bucket_min'])

# (target, baseline, metric, function, columns, fitted on TRAIN?, headline (bootstrap CI)?)
Z0 = 'zero'
METRICS = [
    ('r', 'BL1 no signal', 'mean_bp', lambda y: float(np.nanmean(y)), ['r'], False, True),
    ('r', 'BL1 no signal', 'sd_bp', lambda y: float(np.nanstd(y)), ['r'], False, False),
    ('r', 'BL1 no signal', 'skill_trainmean_vs_zero', inf.skill, ['f_mean_r', Z0, 'r'], True, False),
    ('r', 'BL2 time of day', 'skill_vs_zero', inf.skill, ['f_tod_r', Z0, 'r'], True, True),
    ('r', 'BL2 time of day', 'ic', inf.pearson, ['f_tod_r', 'r'], True, False),
    ('r', 'BL3 momentum', 'ic', inf.pearson, ['tr', 'r'], False, True),
    ('r', 'BL3 momentum', 'rank_ic', inf.spearman, ['tr', 'r'], False, True),
    ('r', 'BL3 momentum', 'hit_rate', inf.hit_rate, ['tr', 'r'], False, True),
    ('r', 'BL3 momentum', 'mean_signed_bp', inf.mean_signed, ['tr', 'r'], False, True),
    ('r', 'BL4 mean reversion', 'ic', lambda x, y: -inf.pearson(x, y), ['tr', 'r'], False, False),
    ('r', 'BL4 mean reversion', 'rank_ic', lambda x, y: -inf.spearman(x, y), ['tr', 'r'], False, False),
    ('r', 'BL4 mean reversion', 'hit_rate', lambda x, y: 1 - inf.hit_rate(x, y), ['tr', 'r'], False, False),
    ('r', 'BL4 mean reversion', 'mean_signed_bp', lambda x, y: -inf.mean_signed(x, y), ['tr', 'r'], False, False),
    ('reversal', 'BL1 no signal', 'base_rate', lambda y: float(np.nanmean(y)), ['rev'], False, True),
    ('reversal', 'BL1 no signal', 'brier_trainrate', inf.mse, ['f_mean_rev', 'rev'], True, False),
    ('reversal', 'BL2 time of day', 'brier_skill_vs_BL1', inf.skill, ['f_tod_rev', 'f_mean_rev', 'rev'], True, False),
    ('rex', 'BL1 no signal', 'mean', lambda y: float(np.nanmean(y)), ['rex'], False, False),
    ('rex', 'BL2 time of day', 'skill_vs_BL1', inf.skill, ['f_tod_rex', 'f_mean_rex', 'rex'], True, False),
]
for t, trail in (('rv', 'trv'), ('rg', 'trg')):
    METRICS += [
        (t, 'BL1 no signal', 'mean_bp', lambda y: float(np.nanmean(y)), [t], False, False),
        (t, 'BL1 no signal', 'mse_trainmean', inf.mse, [f'f_mean_{t}', t], True, False),
        (t, 'BL1 no signal', 'mae_trainmean', inf.mae, [f'f_mean_{t}', t], True, False),
        (t, 'BL2 time of day', 'skill_vs_BL1', inf.skill, [f'f_tod_{t}', f'f_mean_{t}', t], True, True),
        (t, 'BL2 time of day', 'rank_ic', inf.spearman, [f'f_tod_{t}', t], True, False),
        (t, 'BL5 volatility only', 'rank_ic', inf.spearman, [trail, t], False, True),
        (t, 'BL5 volatility only', 'ic', inf.pearson, [trail, t], False, False),
        (t, 'BL5 volatility only', 'skill_vs_BL1', inf.skill, [trail, f'f_mean_{t}', t], True, True),
        (t, 'BL5 volatility only', 'skill_vs_BL2', inf.skill, [trail, f'f_tod_{t}', t], True, True),
        (t, 'BL5 volatility only', 'mae', inf.mae, [trail, t], False, False)]
TARGETS = ['r', 'rv', 'rg', 'rex', 'rev']


def build_panel(horizons):
    """every decision with a complete label window, with targets and baseline predictors (all phases; the grid is selected later)"""
    I, O, _ = sc.build_market(); X, Z = sc.feature_tables()
    mats = tg.session_matrices(I)
    T = tg.index_targets(I, horizons).rename(columns={'r_bp': 'r', 'rv_bp': 'rv', 'rg_bp': 'rg'})
    P = pr.trailing_table(mats, horizons).rename(columns={'trv_bp': 'trv', 'trg_bp': 'trg'})
    T = T.merge(P, on=['und', 'date', 'kd', 'h'], how='left')
    Xl = X[['und', 'm'] + [f'ret_{h}m_bp' for h in horizons]].melt(['und', 'm'], var_name='f', value_name='tr'); Xl['h'] = Xl.f.str.extract(r'ret_(\d+)m_bp').astype(int)
    T = T.merge(Xl[['und', 'm', 'h', 'tr']], on=['und', 'm', 'h'], how='left')
    T['rev'] = np.where((T.r != 0) & (T.tr != 0) & T.r.notna() & T.tr.notna(), (np.sign(T.r) != np.sign(T.tr)).astype(float), np.nan)
    T['bucket'] = pr.tod_bucket(T.kd, BW); T[Z0] = 0.0
    return T, mats, O, Z


def add_forecasts(G, fit_mask):
    """train-mean and time-of-day forecasts from the rows in fit_mask only (both indices pooled)"""
    G = G.copy(); F = G[fit_mask]
    for t in TARGETS:
        mu = F[t].mean(); bm = F.groupby('bucket')[t].mean()
        G[f'f_mean_{t}'] = mu; G[f'f_tod_{t}'] = G.bucket.map(bm).fillna(mu)       # a bucket never seen in the fit rows falls back to the fit mean
    return G


def metric_rows(E, fitted_ok=True):
    out = []
    for t, b, m, fn, cols, fitted, head in METRICS:
        if fitted and not fitted_ok: continue
        try: v = fn(*[E[c].values.astype(float) for c in cols])
        except Exception: v = np.nan
        n = int(np.isfinite(E[cols].values.astype(float)).all(axis=1).sum())
        out.append(dict(target=t, baseline=b, metric=m, value=v, n_obs=n, n_dates=int(E.date.nunique()), fitted_on_train=fitted, headline=head))
    return out


def main(bootstrap=True, save=True):
    """save=False (used by the tests) writes every output to a temporary directory, never to results/"""
    import tempfile
    RES = sc.RES if save else tempfile.mkdtemp(prefix='s2_m2_')
    t0 = time.time(); log = []
    def say(*a):
        s = ' '.join(str(x) for x in a); log.append(s); print(s, flush=True)
    H = PRIMARY + SENS
    T, mats, Opt, Z = build_panel(H)
    dates = sorted(T.date.unique()); folds = sp.primary_folds(dates, CFG['validation']['primary_folds']); blocks = sp.stability_blocks(dates, CFG['validation']['stability_blocks'])
    T['fold'] = T.date.map(folds); T['block'] = T.date.map(blocks)
    FD = pd.DataFrame({'date': folds.index, 'fold': folds.values, 'block': blocks.values}); FD.to_csv(os.path.join(RES, 'm2_folds.csv'), index=False)
    say('folds:', FD.groupby('fold').date.agg(['min', 'max', 'size']).to_dict('index')); say('blocks:', FD.groupby('block').date.agg(['min', 'max', 'size']).to_dict('index'))
    n_sess = T[['und', 'date']].drop_duplicates().shape[0]
    counts, MET, STAB, PHASE, PERM = [], [], [], [], []
    reps = int(CFG['validation']['bootstrap']['reps']); seed = int(CFG['seed'])
    for h in H:
        role = 'primary' if h in PRIMARY else 'sensitivity only'
        Th = T[T.h == h]; cand = Th[Th.kd.isin(sp.valid_range(h))]; G = Th[Th.kd.isin(sp.grid(h))].copy()
        ok = G[['r', 'rv', 'rg']].notna().all(axis=1)
        c = dict(horizon_min=h, role=role, underlying_sessions=n_sess, session_dates=len(dates), decisions_per_session_before_purging=len(sp.valid_range(h)), decisions_per_session_on_grid=len(sp.grid(h)),
                 candidates_before_purging=len(cand), kept_on_non_overlapping_grid=len(G), removed_by_purging=len(cand) - len(G), kept_with_complete_label=int(ok.sum()), label_missing_bar=int((~ok).sum()),
                 momentum_predictor_missing=int(G.tr.isna().sum()), volatility_predictor_missing=int(G.trv.isna().sum()))
        for f in ('TRAIN', 'VAL', 'TEST'): c[f'obs_{f}'] = int(ok[G.fold == f].sum()); c[f'dates_{f}'] = int(G[G.fold == f].date.nunique())
        counts.append(c)
        G = add_forecasts(G, (G.fold == 'TRAIN').values)
        segs = {'ALL': np.ones(len(G), bool), 'TRAIN': (G.fold == 'TRAIN').values, 'VAL': (G.fold == 'VAL').values, 'TEST': (G.fold == 'TEST').values, 'VAL+TEST': G.fold.isin(['VAL', 'TEST']).values}
        for sname, sm in segs.items():
            for scope, um in (('combined', np.ones(len(G), bool)), ('NIFTY', (G.und == 'NIFTY').values), ('SENSEX', (G.und == 'SENSEX').values)):
                E = G[sm & um]
                for r in metric_rows(E):
                    r.update(horizon_min=h, role=role, segment=sname, scope=scope, in_sample_fit=bool(r['fitted_on_train'] and sname in ('ALL', 'TRAIN')))
                    if bootstrap and r['headline'] and scope == 'combined' and sname != 'TRAIN' and not r['in_sample_fit']:
                        t_, b_, m_, fn, cols, _, _ = next(x for x in METRICS if x[:3] == (r['target'], r['baseline'], r['metric']))
                        arrs = [E[cc].values.astype(float) for cc in cols]
                        _, lo, hi, nd = inf.cluster_bootstrap(fn, E.date.values, arrs, reps=reps, seed=seed); r.update(ci_lo=lo, ci_hi=hi)
                        if sname == 'ALL' and role == 'primary':
                            _, lo5, hi5, _ = inf.cluster_bootstrap(fn, E.date.values, arrs, reps=reps, seed=seed, block_len=int(CFG['validation']['bootstrap']['sensitivity_block_len_dates'])); r.update(ci_lo_block5=lo5, ci_hi_block5=hi5)
                    MET.append(r)
        # four-block expanding stability: parameter-free metrics per block; fitted baselines refit on blocks 1..k and scored on block k+1
        for k in range(1, int(CFG['validation']['stability_blocks']) + 1):
            if k == 1: Gk = G; fitted_ok = False; train_blocks = ''
            else: Gk = add_forecasts(G.drop(columns=[c_ for c_ in G.columns if c_.startswith('f_')]), (G.block < k).values); fitted_ok = True; train_blocks = '1' if k == 2 else f'1-{k - 1}'
            E = Gk[Gk.block == k]
            for r in metric_rows(E, fitted_ok=fitted_ok):
                r.update(horizon_min=h, role=role, test_block=k, train_blocks=train_blocks, first_date=str(E.date.min().date()), last_date=str(E.date.max().date())); STAB.append(r)
        # grid-phase sensitivity of the parameter-free headline statistics (each phase is itself a purged, non-overlapping grid)
        ph = []
        for phase in range(h):
            Gp = Th[Th.kd.isin(sp.grid(h, phase))]
            ph.append(dict(phase=phase, **{f'{t}|{b}|{m}': fn(*[Gp[c_].values.astype(float) for c_ in cols]) for t, b, m, fn, cols, fitted, head in METRICS if head and not fitted}))
        ph = pd.DataFrame(ph)
        for col in [c_ for c_ in ph.columns if c_ != 'phase']:
            t_, b_, m_ = col.split('|'); PHASE.append(dict(horizon_min=h, role=role, target=t_, baseline=b_, metric=m_, primary_phase0=ph[col].iloc[0], min=ph[col].min(), median=ph[col].median(), max=ph[col].max(), phases=h))
        # date-permutation tests of the three parameter-free relations (primary horizons only)
        if role == 'primary' and bootstrap:
            Gs = G.sort_values(['und', 'date', 'kd'])
            def mat(col): return {u: g.pivot(index='date', columns='kd', values=col).reindex(index=pd.DatetimeIndex(dates)).values for u, g in Gs.groupby('und')}
            for name, xc, yc in (('BL3 momentum: rank IC(trailing return, r)', 'tr', 'r'), ('BL5 volatility only: rank IC(trailing RV, RV)', 'trv', 'rv'), ('BL5 volatility only: rank IC(trailing range, RG)', 'trg', 'rg')):
                s_, p_, sd_ = inf.date_permutation_p(inf.spearman, mat(xc), mat(yc), reps=int(CFG['validation']['permutation']['reps']), seed=seed)
                PERM.append(dict(horizon_min=h, test=name, statistic=s_, null_sd=sd_, p_two_sided=p_))
        say(f'h={h} ({role}): grid obs {len(G)}, complete labels {int(ok.sum())}, {time.time() - t0:.0f}s')
    C = pd.DataFrame(counts); C.to_csv(os.path.join(RES, 'm2_sample_counts.csv'), index=False)
    M = pd.DataFrame(MET); lead = ['horizon_min', 'role', 'target', 'baseline', 'metric', 'segment', 'scope']
    M = M[lead + [c_ for c_ in M.columns if c_ not in lead]]; M.to_csv(os.path.join(RES, 'm2_baseline_metrics.csv'), index=False)
    pd.DataFrame(STAB).to_csv(os.path.join(RES, 'm2_stability_blocks.csv'), index=False); pd.DataFrame(PHASE).to_csv(os.path.join(RES, 'm2_phase_sensitivity.csv'), index=False)
    if PERM:
        Pm = pd.DataFrame(PERM); Pm['p_holm'] = inf.holm(Pm.p_two_sided); Pm['p_bh'] = inf.bh(Pm.p_two_sided); Pm.to_csv(os.path.join(RES, 'm2_permutation_tests.csv'), index=False); say(Pm.round(4).to_string(index=False))
    say(C.T.to_string())

    # ------------------------------------------------------------------ options, isolated: ATM straddle premium change (D-1 and D0 reported separately)
    S = tg.straddle_targets(Opt, Z, H, {h: sp.grid(h) for h in H}); S['fold'] = S.date.map(folds); S['bucket'] = pr.tod_bucket(S.kd, BW); S['zero'] = 0.0
    srows = []
    zs = Z.assign(day=np.where(Z.date == Z.expiry, 'D0', 'D-1'))[['und', 'date', 'day']].drop_duplicates(); nsess = zs.groupby('day').size()      # every option session, including those with no ATM pair
    for (h, day), g in S.groupby(['h', 'day']):
        role = 'primary' if h in PRIMARY else 'sensitivity only'; y = g.straddle_chg_pct; fit = g[g.fold == 'TRAIN']; ev = g[g.fold.isin(['VAL', 'TEST'])]
        mu = fit.straddle_chg_pct.mean(); bm = fit.groupby('bucket').straddle_chg_pct.mean()
        possible = int(nsess[day]) * len(sp.grid(h))
        r = dict(horizon_min=h, role=role, day=day, option_sessions=int(nsess[day]), session_dates_with_target=int(g[y.notna()].date.nunique()), grid_decisions_possible=possible, target_available=int(y.notna().sum()),
                 available_share=float(y.notna().sum() / possible),
                 BL1_mean_pct=float(y.mean()), sd_pct=float(y.std()), dates_TRAIN=int(fit.date.nunique()), dates_VAL_TEST=int(ev.date.nunique()),
                 BL1_skill_trainmean_vs_zero_VAL_TEST=inf.skill(np.full(len(ev), mu), np.zeros(len(ev)), ev.straddle_chg_pct.values.astype(float)),
                 BL2_tod_skill_vs_BL1_VAL_TEST=inf.skill(ev.bucket.map(bm).fillna(mu).values.astype(float), np.full(len(ev), mu), ev.straddle_chg_pct.values.astype(float)),
                 max_verdict=('INCONCLUSIVE (D0: selection-biased sample, decision D4)' if day == 'D0' else 'as evidence allows; in-sample'))
        if bootstrap:
            gg = g[y.notna()]; _, lo, hi, nd = inf.cluster_bootstrap(lambda v: float(np.mean(v)), gg.date.values, [gg.straddle_chg_pct.values.astype(float)], reps=reps, seed=seed); r.update(BL1_mean_ci_lo=lo, BL1_mean_ci_hi=hi)
        srows.append(r)
    SB = pd.DataFrame(srows); SB.to_csv(os.path.join(RES, 'm2_straddle_baselines.csv'), index=False); say(SB.round(3).to_string(index=False))

    # ------------------------------------------------------------------ cost scenarios: reproduced exactly, with applicability
    K = cs.registered(); med = S[(S.day == 'D-1') & (S.h == PRIMARY[0])].groupby('und').p_in.median()
    crow = []
    for name, (a, b, c_) in K.items():
        r = dict(scenario=name, share_of_premium_turnover=a, rupees_per_parent_order=b, rupees_per_unit=c_,
                 applies_to_index_only_prediction=('trivially (all components are zero)' if name == 'zero' else 'NO: an index level has no premium turnover, parent order or traded unit'),
                 applies_to_option_trades='yes (premium turnover, orders and units are defined for option trades)')
        for u in med.index:
            rs, sh = cs.straddle_round_trip(float(med[u]), sc.LOT[u], name); r[f'{u}_median_D-1_ATM_straddle_points'] = float(med[u]); r[f'{u}_one_lot_round_trip_rupees'] = rs; r[f'{u}_round_trip_pct_of_premium'] = 100 * sh
        crow.append(r)
    pd.DataFrame(crow).to_csv(os.path.join(RES, 'm2_costs.csv'), index=False); say(pd.DataFrame(crow).round(3).T.to_string())
    shutil.copy(os.path.join(S2, 'configs', 'stage2.yaml'), os.path.join(RES, 'm2_config_snapshot.yaml'))
    say(f'done in {time.time() - t0:.0f}s (bootstrap={bootstrap})'); open(os.path.join(RES, 'm2_run_log.txt'), 'w').write('\n'.join(log) + '\n')
    return M


if __name__ == '__main__':
    main(bootstrap='--no-bootstrap' not in sys.argv)
