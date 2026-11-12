"""Stage 2, Milestone 1: data-integrity and leakage audit.  No model is trained and no feature is related to a future return.
(Future prices are used in exactly one place, section E2, to measure how much the OPTION UNIVERSE itself reveals about the rest
of the day: that is a test of a data artefact, not of a signal.)

Inputs (authoritative): raw Breeze 1-minute files (env ALGO8_MARKET_DIR), raw broker fills, PR #6 feature library (code only).
PR #3 / PR #6 caches are compared against, never used as inputs.
python3 stage2_alpha_research/audit/data_leakage_audit.py [--force]   -> stage2_alpha_research/results/*.csv, audit_report.txt
"""
import os, sys, hashlib, time
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); S2 = os.path.dirname(HERE); sys.path.insert(0, S2)
import s2common as sc
from targets import alignment as al
RES = sc.RES; CFG = sc.CFG; N = sc.N; OPEN = sc.OPEN
REP = []; CHECKS = []


def say(*a):
    s = ' '.join(str(x) for x in a); REP.append(s); print(s, flush=True)


def check(cid, name, status, detail):
    """status: PASS / FAIL / RISK (a real limitation that must be handled in the research design)"""
    CHECKS.append(dict(check_id=cid, check=name, status=status, detail=detail)); say(f'[{status}] {cid} {name}: {detail}')


def same(a, b, keys):
    try:
        a = a.sort_values(keys).reset_index(drop=True); b = b.sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a[sorted(a.columns)], b[sorted(a.columns)], check_dtype=False, check_exact=False, rtol=1e-9); return True
    except Exception as e:
        return False


def main(force=False):
    t0 = time.time(); rng = np.random.default_rng(CFG['seed'])
    # ------------------------------------------------------------------ A. sources and manifest
    I, O, man = sc.build_market(force=force)
    ri, _ = sc.raw_index()
    trades = os.path.join(sc.REPO, 'Trades_GKOHNP140.csv'); th = hashlib.sha256(open(trades, 'rb').read()).hexdigest()
    M = [dict(m, role='AUTHORITATIVE input', path=f"${CFG['market']['env_var']}/" + ('indices' if 'index' in m['dataset'] else 'options')) for m in man]
    M.append(dict(dataset='broker fills (Trades_GKOHNP140.csv)', files=1, raw_rows=len(sc.fills()), rows=len(sc.fills()), bytes=os.path.getsize(trades), sha256=th, role='AUTHORITATIVE (used here only to verify the bar-label convention)', path='Trades_GKOHNP140.csv'))
    M.append(dict(dataset='PR #6 feature library (code)', files=1, sha256=hashlib.sha256(open(os.path.join(sc.REPO, 'ohlcv_research', 'features.py'), 'rb').read()).hexdigest(), role='AUTHORITATIVE code, reused unchanged', path='ohlcv_research/features.py'))
    recon = []
    for nm, p, tab, keys in (('PR #6 cache index.pkl', 'ohlcv_research/_cache/index.pkl', I, ['und', 'ts']), ('PR #6 cache options.pkl', 'ohlcv_research/_cache/options.pkl', O, ['und', 'expiry', 'strike', 'cp', 'ts'])):
        fp = os.path.join(sc.REPO, p)
        if os.path.exists(fp):
            ok = same(pd.read_pickle(fp), tab, keys); recon.append((nm, ok))
            M.append(dict(dataset=nm, role='NOT USED (compared only): ' + ('identical to the Stage 2 rebuild' if ok else 'DIFFERS from the Stage 2 rebuild'), path=p))
    fp = os.path.join(sc.REPO, 'analysis', '_cache', 'idx_candles.pkl')
    if os.path.exists(fp):
        a = pd.read_pickle(fp)[['und', 'ts', 'open', 'high', 'low', 'close']]; ok = same(a, I, ['und', 'ts']); recon.append(('PR #3 cache idx_candles.pkl', ok))
        M.append(dict(dataset='PR #3 cache idx_candles.pkl', role='NOT USED (compared only): ' + ('identical' if ok else 'DIFFERS'), path='analysis/_cache/idx_candles.pkl'))
    for p in CFG['excluded_provisional_inputs']:
        M.append(dict(dataset=p, role='EXCLUDED (provisional per FINAL_DEPENDENCY_AUDIT); never read by Stage 2', path=p))
    pd.DataFrame(M).to_csv(os.path.join(RES, 'dataset_manifest.csv'), index=False)
    check('A1', 'earlier caches reproduce from the raw files', 'PASS' if all(ok for _, ok in recon) else 'RISK', '; '.join(f'{n}: {"identical" if ok else "DIFFERS"}' for n, ok in recon))

    # ------------------------------------------------------------------ B. index bars
    ri['k'] = sc.session_minute(ri.ts); ri['date'] = ri.ts.dt.normalize()
    check('B1', 'index timestamps: one timezone, whole minutes', 'PASS' if set(ri.tz) == {CFG['market']['timezone_suffix']} and (ri.ts.dt.second == 0).all() else 'FAIL',
          f"timezones {sorted(set(ri.tz))}; off-minute rows {int((ri.ts.dt.second != 0).sum())}")
    dup = int(ri.duplicated(['und', 'ts']).sum()); check('B2', 'index duplicate bars', 'PASS' if dup == 0 else 'RISK', f'{dup} duplicate (und, ts) rows in the raw files')
    I['date'] = I.ts.dt.normalize(); I['k'] = sc.session_minute(I.ts)
    out_sess = int(((I.k < 0) | (I.k >= N)).sum())
    bad = ((I.high < I[['open', 'close']].max(axis=1)) | (I.low > I[['open', 'close']].min(axis=1)) | (I[['open', 'high', 'low', 'close']] <= 0).any(axis=1))
    g = I[(I.k >= 0) & (I.k < N)].groupby(['und', 'date'])
    S = g.agg(bars=('k', 'size'), first_k=('k', 'min'), last_k=('k', 'max'), open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last')).reset_index()
    S['missing_bars'] = N - S.bars
    miss = I[(I.k >= 0) & (I.k < N)].groupby(['und', 'date']).k.apply(lambda s: sorted(set(range(N)) - set(s)))
    S['missing_minutes'] = [','.join((pd.Timestamp('2000-01-01') + OPEN + pd.Timedelta(minutes=int(k))).strftime('%H:%M') for k in miss[(u, d)]) for u, d in zip(S.und, S.date)]
    r1 = I.sort_values(['und', 'ts']).groupby(['und', 'date']).close.apply(lambda c: float(np.abs(np.log(c).diff()).max() * 1e4)); S['max_abs_1m_move_bp'] = [r1[(u, d)] for u, d in zip(S.und, S.date)]
    S.to_csv(os.path.join(RES, 'audit_index_sessions.csv'), index=False)
    dates = {u: sorted(S[S.und == u].date) for u in S.und.unique()}
    check('B3', 'index sessions', 'PASS' if len(set(map(tuple, dates.values()))) == 1 else 'RISK', f"{ {u: len(v) for u, v in dates.items()} } sessions, identical dates across indices: {len(set(map(tuple, dates.values()))) == 1}; {S.date.min().date()} to {S.date.max().date()}")
    check('B4', 'index OHLC sanity and session bounds', 'PASS' if not bad.any() and out_sess == 0 else 'RISK', f'{int(bad.sum())} inconsistent rows; {out_sess} bars outside 09:15-15:29')
    ms = S[S.missing_bars > 0]
    check('B5', 'index missing bars', 'RISK' if len(ms) else 'PASS', f"{int(S.missing_bars.sum())} missing minutes in {len(ms)} index-sessions ({ms.date.nunique()} dates, {ms.date.min().date() if len(ms) else ''} to {ms.date.max().date() if len(ms) else ''}); minutes: {sorted(set(','.join(ms.missing_minutes).split(',')))[:8]}; never interpolated")
    cal = dates['NIFTY']; allwd = pd.bdate_range(cal[0], cal[-1]); nosess = [d.date().isoformat() for d in allwd if d not in set(cal)]
    say('weekdays without a session:', nosess)

    # ------------------------------------------------------------------ C. option bars
    ro, _ = sc.raw_options()
    check('C1', 'option timestamps: one timezone, whole minutes', 'PASS' if set(ro.tz) == {CFG['market']['timezone_suffix']} and (ro.ts.dt.second == 0).all() else 'FAIL', f'timezones {sorted(set(ro.tz))}')
    dupo = int(ro.duplicated(['und', 'expiry', 'strike', 'cp', 'ts']).sum()); check('C2', 'option duplicate bars', 'PASS' if dupo == 0 else 'RISK', f'{dupo} duplicate rows in the raw files')
    del ro
    O['date'] = O.ts.dt.normalize(); O['k'] = sc.session_minute(O.ts)
    post = int((O.k >= N).sum()); pre = int((O.k < 0).sum())
    Os = O[(O.k >= 0) & (O.k < N)]
    bado = ((Os.high < Os[['open', 'close']].max(axis=1)) | (Os.low > Os[['open', 'close']].min(axis=1)) | (Os[['open', 'high', 'low', 'close']] <= 0).any(axis=1))
    check('C3', 'option OHLC sanity; post-close bars', 'PASS' if not bado.any() else 'RISK', f'{int(bado.sum())} inconsistent rows; {post} bars at or after 15:30 and {pre} before 09:15 exist in the files and are dropped by the feature library')
    cd = Os.groupby(['und', 'date', 'expiry', 'strike', 'cp']).agg(bars=('k', 'size'), zero_vol=('volume', lambda v: int((v == 0).sum()))).reset_index()
    pos = {u: {d: i for i, d in enumerate(dates[u])} for u in dates}
    def dte_sessions(u, d, e):
        if e not in pos[u] or d not in pos[u]: return np.nan
        return pos[u][e] - pos[u][d]
    sess = cd.groupby(['und', 'date', 'expiry']).agg(contracts=('bars', 'size'), full_contract_days=('bars', lambda b: int((b == N).sum())), bars=('bars', 'sum'), zero_volume_bars=('zero_vol', 'sum')).reset_index()
    sess['dte_sessions'] = [dte_sessions(u, d, e) for u, d, e in zip(sess.und, sess.date, sess.expiry)]
    sess['dte_calendar_days'] = (sess.expiry - sess.date).dt.days
    nexp = sess.groupby(['und', 'date']).expiry.nunique()
    check('C4', 'expiry alignment', 'PASS' if (nexp == 1).all() and sess.dte_sessions.isin([0, 1]).all() else 'RISK',
          f"one expiry per (underlying, session): {bool((nexp == 1).all())}; sessions to expiry {sess.dte_sessions.value_counts().to_dict()}; calendar days {sess.dte_calendar_days.value_counts().to_dict()}; every expiry date is an index session: {bool(sess.dte_sessions.notna().all())}")
    tick = float(np.isclose((Os.close * 20) % 1, 0, atol=1e-6).mean()); lotm = float(((Os.volume % Os.und.map(sc.LOT)) == 0).mean())
    check('C5', 'option tick grid and volume units', 'PASS' if tick > 0.999 and lotm > 0.999 else 'RISK', f'closes on the 0.05 tick {tick:.4f}; volume a multiple of the lot {lotm:.4f}')
    say(f"option contract-days {len(cd)}, with all 375 bars {float((cd.bars == N).mean()):.3f}; zero-volume bars {cd.zero_vol.sum() / cd.bars.sum():.4f} of in-session bars")
    check('C6', 'stale option prices', 'RISK', f"{cd.zero_vol.sum() / cd.bars.sum():.3%} of in-session option bars have zero volume (carried last price); option return / reversal features on thin strikes can be spurious")

    # ------------------------------------------------------------------ D. bar label convention against broker fills
    f = sc.fills(); f = f[['und', 'expiry', 'cp', 'strike', 't', 'px_fill']].copy(); f['minute'] = f.t.dt.floor('min'); f['strike'] = f.strike.astype(float)
    key = ['und', 'expiry', 'cp', 'strike']; Ob = O[key + ['ts', 'low', 'high']].copy(); Ob['strike'] = Ob.strike.astype(float); res = {}
    for nm, sh in (('own', 0), ('next', 1), ('previous', -1)):
        x = f.assign(ts=f.minute + pd.Timedelta(minutes=sh)).merge(Ob, on=key + ['ts'], how='left')
        res[nm] = float(((x.px_fill >= x.low - 1e-9) & (x.px_fill <= x.high + 1e-9)).mean())
    check('D1', 'bar timestamp = bar START', 'PASS' if res['own'] > 0.95 and res['own'] > max(res['next'], res['previous']) + 0.2 else 'FAIL',
          f"share of {len(f)} broker fills inside [low, high] of the bar labelled with the fill's own minute {res['own']:.3f}, next bar {res['next']:.3f}, previous bar {res['previous']:.3f}")

    # ------------------------------------------------------------------ E. option universe: coverage and selection
    F = sc.feature_library(); Ic = I[['und', 'ts', 'open', 'high', 'low', 'close']]; Oc = O[['und', 'expiry', 'strike', 'cp', 'ts', 'open', 'high', 'low', 'close', 'volume']]
    Z = F.straddle_features(Oc, Ic, sc.STEP)
    Z['kd'] = ((Z.m - Z.date - OPEN).dt.total_seconds() // 60).astype(int); Zs = Z[(Z.kd >= 1) & (Z.kd <= N - 1)]
    cov = Zs.groupby(['und', 'date', 'expiry']).straddle_bp.apply(lambda s: float(s.notna().mean())).rename('straddle_coverage').reset_index()
    sess = sess.merge(cov, on=['und', 'date', 'expiry'], how='left')
    # universe geometry: strikes that have BOTH rights that session
    pr = Os.groupby(['und', 'date', 'expiry', 'strike']).cp.nunique(); pr = pr[pr == 2].reset_index()
    geo = pr.groupby(['und', 'date', 'expiry']).strike.agg(pair_min='min', pair_max='max', pair_strikes='size').reset_index()
    sess = sess.merge(geo, on=['und', 'date', 'expiry'], how='left').merge(S[['und', 'date', 'open', 'high', 'low', 'close']], on=['und', 'date'], how='left')
    st = sess.und.map(sc.STEP)
    sess['room_up_steps_at_open'] = (sess.pair_max - sess.open) / st; sess['room_down_steps_at_open'] = (sess.open - sess.pair_min) / st
    sess['later_max_up_steps'] = (sess.high - sess.open) / st; sess['later_max_down_steps'] = (sess.open - sess.low) / st
    sess['universe_centre_minus_open_steps'] = ((sess.pair_max + sess.pair_min) / 2 - sess.open) / st; sess['open_to_close_steps'] = (sess.close - sess.open) / st
    sess['day'] = np.where(sess.dte_sessions == 0, 'D0', 'D-1')
    sess.to_csv(os.path.join(RES, 'audit_option_sessions.csv'), index=False)
    low = sess[sess.straddle_coverage < CFG['audit']['min_straddle_coverage_flag']]
    check('E1', 'ATM straddle coverage (both legs of the ATM strike have a completed bar)', 'RISK',
          f"option sessions {len(sess)} ({sess.groupby('und').size().to_dict()}; {sess.groupby('day').size().to_dict()}); mean coverage D-1 {sess[sess.day == 'D-1'].straddle_coverage.mean():.3f}, D0 {sess[sess.day == 'D0'].straddle_coverage.mean():.3f}; {len(low)} sessions below {CFG['audit']['min_straddle_coverage_flag']:.0%} (minimum {sess.straddle_coverage.min():.3f})")
    sel = []
    for d_, g in sess.groupby('day'):
        for a, b, nm in (('room_up_steps_at_open', 'later_max_up_steps', 'universe room above the open vs the later maximum rise'), ('room_down_steps_at_open', 'later_max_down_steps', 'universe room below the open vs the later maximum fall'),
                         ('universe_centre_minus_open_steps', 'open_to_close_steps', 'universe centre minus open vs the open-to-close move')):
            sel.append(dict(day=d_, relation=nm, sessions=len(g), spearman=float(g[[a, b]].corr(method='spearman').iloc[0, 1])))
    SEL = pd.DataFrame(sel); SEL.to_csv(os.path.join(RES, 'audit_universe_selection.csv'), index=False)
    # coverage as a function of the move since the open (decision-minute level)
    Zc = Zs.merge(I.assign(m=I.ts + pd.Timedelta(minutes=1))[['und', 'm', 'close']], on=['und', 'm'], how='left').merge(S[['und', 'date', 'open']], on=['und', 'date'], how='left')
    Zc['move_bp'] = (Zc.close / Zc.open - 1).abs() * 1e4; Zc['day'] = np.where(Zc.date == Zc.expiry, 'D0', 'D-1')
    Zc['move_bin'] = pd.cut(Zc.move_bp, [0, 25, 50, 100, 150, 1e9], labels=['0-25 bp', '25-50', '50-100', '100-150', '>150'], include_lowest=True)
    CM = Zc.groupby(['day', 'move_bin'], observed=True).straddle_bp.agg(decision_minutes='size', coverage=lambda s: float(s.notna().mean())).reset_index(); CM.to_csv(os.path.join(RES, 'audit_straddle_coverage_by_move.csv'), index=False)
    mx = SEL.spearman.abs().max()
    check('E2', 'option universe is selected by Algo 8 trading (look-ahead in data availability)', 'RISK',
          'the files contain a contract-day only if Algo 8 traded or held it that day or the neighbouring day, with bars for the whole day; Spearman across sessions: ' + '; '.join(f"{r.day} {r.relation} {r.spearman:+.2f} (n={r.sessions})" for r in SEL.itertuples()) +
          f". Coverage by |move since open|: " + '; '.join(f"{r.day} {r.move_bin} {r.coverage:.2f}" for r in CM.itertuples()))

    # ------------------------------------------------------------------ F. feature availability (PR #6 library, rebuilt from raw)
    X = F.index_features(Ic); Y = F.option_features(Oc, Ic)
    recf = []
    for nm, tab, keys in (('feat_index.pkl', X, ['und', 'm']), ('feat_straddle.pkl', Z.drop(columns='kd'), ['und', 'expiry', 'm']), ('feat_option.pkl', Y, ['und', 'expiry', 'strike', 'cp', 'm'])):
        fp = os.path.join(sc.REPO, 'ohlcv_research', '_cache', nm)
        if os.path.exists(fp): recf.append((nm, same(pd.read_pickle(fp), tab, keys)))
    check('F1', 'PR #6 feature caches reproduce from the raw files', 'PASS' if recf and all(ok for _, ok in recf) else 'RISK', '; '.join(f'{n}: {"identical" if ok else "DIFFERS"}' for n, ok in recf) or 'no PR #6 cache present to compare')
    X.to_pickle(os.path.join(sc.CACHE, 's2_feat_index.pkl')); Z.to_pickle(os.path.join(sc.CACHE, 's2_feat_straddle.pkl')); Y.to_pickle(os.path.join(sc.CACHE, 's2_feat_option.pkl'))
    rows = []
    def avail(tab, cols, name, fam):
        t = tab.copy(); t['kd'] = ((t.m - t.date - OPEN).dt.total_seconds() // 60).astype(int); t = t[(t.kd >= 1) & (t.kd <= N - 1)]
        t['tod'] = pd.cut(t.kd, [0, 30, 105, 285, 375], labels=['09:16-09:45', '09:46-11:00', '11:01-14:00', '14:01-15:29'])
        skey = [c for c in ('und', 'expiry', 'strike', 'cp', 'date') if c in t.columns]
        for c in cols:
            v = t[c].astype(float); ok = v.notna()
            first = t[ok].groupby(skey).kd.min()
            r = dict(table=name, family=fam.get(c, ''), feature=c, decision_rows=len(t), available_share=float(ok.mean()), first_available_minute_median=(pd.Timestamp('2000-01-01') + OPEN + pd.Timedelta(minutes=float(first.median()))).strftime('%H:%M') if len(first) else '',
                     sessions_never_available=int(t.groupby(skey).ngroups - len(first)))
            for u in sorted(t.und.unique()): r[f'share_{u}'] = float(ok[t.und == u].mean())
            for b, gg in ok.groupby(t.tod, observed=True): r[f'share_{b}'] = float(gg.mean())
            rows.append(r)
    fam = {**{c: 'B momentum' for c in F.INDEX_FEATURES[:9]}, **{c: 'C mean reversion' for c in F.INDEX_FEATURES[9:12]}, **{c: 'A volatility' for c in F.INDEX_FEATURES[12:17]}, **{c: 'D market structure' for c in F.INDEX_FEATURES[17:]},
           **{c: 'E options / premium' for c in F.OPTION_FEATURES + F.STRADDLE_FEATURES}}
    avail(X, F.INDEX_FEATURES, 'index (underlying, decision minute)', fam); avail(Z, [c for c in F.STRADDLE_FEATURES], 'ATM straddle (underlying, expiry, decision minute)', fam); avail(Y, F.OPTION_FEATURES, 'option contract (contract, decision minute)', fam)
    AV = pd.DataFrame(rows); AV.to_csv(os.path.join(RES, 'feature_availability.csv'), index=False)
    say(AV[['table', 'family', 'feature', 'available_share', 'first_available_minute_median']].round(3).to_string(index=False))
    check('F2', 'feature availability', 'PASS', f"{len(AV)} market features; index features available in {AV[AV.table.str.startswith('index')].available_share.min():.3f} to {AV[AV.table.str.startswith('index')].available_share.max():.3f} of decision minutes; latest median warm-up {AV.first_available_minute_median.max()}")

    # ------------------------------------------------------------------ G. prefix invariance on the real data (look-ahead test of every feature)
    opt_sessions = sess[['und', 'date', 'expiry']].drop_duplicates().values.tolist(); pick = rng.choice(len(opt_sessions), CFG['audit']['prefix_invariance_sessions'], replace=False)
    worst = 0.0; ncmp = 0; nfail = 0; details = []
    for j in pick:
        u, d, e = opt_sessions[j]; d = pd.Timestamp(d); i = pos[u][d]; days = [x for x in dates[u][max(i - 1, 0): i + 2]]
        Isub = Ic[(Ic.und == u) & Ic.ts.dt.normalize().isin(days)]; Osub = Oc[(Oc.und == u) & (Oc.expiry == e) & Oc.ts.dt.normalize().isin(days)]
        full = (F.index_features(Isub), F.straddle_features(Osub, Isub, sc.STEP), F.option_features(Osub, Isub))
        for kc in sorted(rng.choice(np.arange(20, N - 5), CFG['audit']['prefix_invariance_cuts_per_session'], replace=False)):
            cut = d + OPEN + pd.Timedelta(minutes=int(kc))                                  # decision minute: bars starting at or after `cut` are removed
            It = Isub[Isub.ts < cut]; Ot = Osub[Osub.ts < cut]
            tr = (F.index_features(It), F.straddle_features(Ot, It, sc.STEP), F.option_features(Ot, It))
            for a, b, cols, keys in zip(full, tr, (F.INDEX_FEATURES, F.STRADDLE_FEATURES, F.OPTION_FEATURES), (['und', 'm'], ['und', 'expiry', 'm'], ['und', 'expiry', 'strike', 'cp', 'm'])):
                a = a[(a.date == d) & (a.m <= cut)]; b = b[(b.date == d) & (b.m <= cut)]
                mm = a.merge(b, on=keys, suffixes=('', '_t'), how='outer', indicator=True)
                if (mm._merge != 'both').any(): nfail += int((mm._merge != 'both').sum())
                for c in cols:
                    x = mm[c].astype(float).values; y = mm[c + '_t'].astype(float).values
                    bad_ = ~(np.isclose(x, y, rtol=1e-9, atol=1e-9) | (np.isnan(x) & np.isnan(y))); ncmp += len(x); nfail += int(bad_.sum())
                    if bad_.any(): worst = max(worst, float(np.nanmax(np.abs(x - y)[bad_]))); details.append((u, str(d.date()), cut.strftime('%H:%M'), c, int(bad_.sum())))
    pd.DataFrame(details, columns=['und', 'date', 'cut', 'feature', 'cells_changed']).to_csv(os.path.join(RES, 'audit_prefix_invariance_failures.csv'), index=False)
    check('G1', 'prefix invariance: removing every bar from the decision minute onward changes no feature value at or before it', 'PASS' if nfail == 0 else 'FAIL',
          f"{len(pick)} sessions x {CFG['audit']['prefix_invariance_cuts_per_session']} random cut minutes, {ncmp:,} feature values compared, {nfail} differences")

    # ------------------------------------------------------------------ H. label alignment (definitions only)
    lab = []
    missing_k = {(u, d): set(miss[(u, d)]) for u, d in zip(S.und, S.date)}
    for h in CFG['targets']['candidate_horizons_min']:
        vd = al.valid_decisions(h); nov = al.non_overlapping_decisions(h); hit = 0; hit_no = 0
        for (u, d), mk_ in missing_k.items():
            if mk_:
                hit += sum(1 for kd in vd if mk_ & set(al.label_bars(kd, h))); hit_no += sum(1 for kd in nov if mk_ & set(al.label_bars(kd, h)))
        lab.append(dict(horizon_min=h, valid_decision_minutes_per_session=len(vd), first_decision=(pd.Timestamp('2000-01-01') + OPEN + pd.Timedelta(minutes=int(vd[0]))).strftime('%H:%M'),
                        last_decision=(pd.Timestamp('2000-01-01') + OPEN + pd.Timedelta(minutes=int(vd[-1]))).strftime('%H:%M'), non_overlapping_per_session=len(nov),
                        non_overlapping_index_total=len(nov) * len(S), non_overlapping_option_sessions_total=len(nov) * len(sess), decision_minutes_touching_a_missing_index_bar=hit, of_which_non_overlapping=hit_no, purge_radius_min=al.purge_radius(h)))
    LAB = pd.DataFrame(lab); LAB.to_csv(os.path.join(RES, 'label_alignment.csv'), index=False); say(LAB.to_string(index=False))
    ok_al = all(len(np.intersect1d(al.feature_bars(kd), al.label_bars(kd, h))) == 0 for h in CFG['targets']['candidate_horizons_min'] for kd in al.valid_decisions(h))
    check('H1', 'label windows start at the decision minute and are disjoint from the bars a feature may use; no label crosses the session end', 'PASS' if ok_al else 'FAIL',
          f"candidate horizons {CFG['targets']['candidate_horizons_min']} min; overlapping labels inside a session require purging within the horizon (purge radius = horizon)")

    # ------------------------------------------------------------------ I. independence
    d1 = S.assign(r=np.log(S.close / S.open)).pivot(index='date', columns='und', values='r'); rho = float(d1.corr().iloc[0, 1])
    d2 = S.sort_values('date').assign(cc=lambda x: np.log(x.close)).pivot(index='date', columns='und', values='cc').diff(); rho2 = float(d2.corr().iloc[0, 1])
    osd = sess[['und', 'date', 'day']].drop_duplicates(); both_dates = osd.groupby('date').und.nunique()
    def split(dt): return 'DEV' if dt <= pd.Timestamp(CFG['validation']['legacy_split_dates']['dev_end']) else ('VAL' if dt <= pd.Timestamp(CFG['validation']['legacy_split_dates']['val_end']) else 'TEST')
    ind = [dict(item='index session dates', value=len(cal)), dict(item='index underlying-sessions', value=len(S)),
           dict(item='NIFTY-SENSEX correlation, open-to-close log return', value=round(rho, 3)), dict(item='NIFTY-SENSEX correlation, close-to-close log return', value=round(rho2, 3)),
           dict(item='usable independent index sessions (cluster = date)', value=len(cal)),
           dict(item='option underlying-sessions', value=len(osd)), dict(item='option session dates', value=int(osd.date.nunique())), dict(item='dates with option data for both indices', value=int((both_dates > 1).sum())),
           dict(item='option sessions D-1 / D0', value=f"{int((osd.day == 'D-1').sum())} / {int((osd.day == 'D0').sum())}"),
           dict(item='weekly expiry cycles with option data', value=int(sess[['und', 'expiry']].drop_duplicates().shape[0])),
           dict(item='index dates by legacy split (DEV / VAL / TEST, by date)', value=' / '.join(str(sum(1 for x in cal if split(x) == s)) for s in ('DEV', 'VAL', 'TEST'))),
           dict(item='option session dates by legacy split', value=' / '.join(str(osd[osd.date.map(split) == s].date.nunique()) for s in ('DEV', 'VAL', 'TEST'))),
           dict(item='index dates by month', value=str(pd.Series(cal).dt.strftime('%Y-%m').value_counts().sort_index().to_dict())),
           dict(item='untouched (never inspected) dates', value=0)]
    pd.DataFrame(ind).to_csv(os.path.join(RES, 'independence.csv'), index=False); say(pd.DataFrame(ind).to_string(index=False))
    check('I1', 'cross-instrument dependence', 'RISK', f'NIFTY and SENSEX open-to-close returns correlate {rho:.2f}: one date is one independent observation ({len(cal)} dates, not {len(S)} underlying-sessions)')
    check('I2', 'no untouched data', 'RISK', 'every session in the sample was inspected by earlier work (see the prior-look ledger in DATA_AUDIT.md): all Stage 2 results are in-sample; external validation needs new data')

    C = pd.DataFrame(CHECKS); C.to_csv(os.path.join(RES, 'leakage_checks.csv'), index=False)
    say(f"\nchecks: {C.status.value_counts().to_dict()}  |  runtime {time.time() - t0:.0f}s")
    open(os.path.join(RES, 'audit_report.txt'), 'w').write('\n'.join(REP) + '\n')
    return C


if __name__ == '__main__':
    main(force='--force' in sys.argv)
