"""B2: does Algo 8 use technical / option indicators?   python3 analysis/b2_indicator_tests.py
For each decision dataset: out-of-sample AUC of nested LightGBM models (expanding chronological folds):
  base (clock+book)  ->  +price (raw spot moves)  ->  +indicators (89 causal indicators)
Null: indicators re-assigned from a different random date, same time of day (date derangement per underlying), 5 reps.
Indicator use is supported only if real gain over +price exceeds the null gains."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
II = pd.read_pickle(os.path.join(C, 'indicators_index.pkl')); IO = pd.read_pickle(os.path.join(C, 'indicators_options.pkl'))
IND = II.merge(IO, on=['und', 'm'], how='left')
IND_COLS = [c for c in IND.columns if c not in ('und', 'm')]
DIRECTIONAL = [c for c in IND_COLS if any(k in c for k in ['ema', 'sma', 'macd', 'rsi', 'stoch', 'cci', 'roc', 'bb_pctb', 'di_diff', 'supertrend', 'dist_', 'gap_', 'orb_', 'iv_ce_minus_pe', 'skew'])]
CENTER = {c: (50 if ('rsi' in c or 'stoch' in c) else (0.5 if 'bb_pctb' in c else 0)) for c in DIRECTIONAL}

def datasets():
    D = {}
    X = pd.read_pickle(os.path.join(C, 'p3_minutes.pkl'))
    base3 = ['mins', 'd0', 'ux', 'ce', 'since_sale_same', 'since_sale_any', 'since_stop_same', 'since_stop_other', 'shortlots', 'imb', 'dist_lastK', 'dist_avgK', 'prem_chg']
    D['D2 off-grid extra sale (minute x side)'] = (X, base3, ['mv1', 'mv3', 'mv5', 'mv10', 'mv15', 'rng15'], True)
    D['D1 timer-due fire (D-1)'] = (X[(X.d0 == 0) & X.since_sale_same.between(13.5, 15.5)], base3, ['mv1', 'mv3', 'mv5', 'mv10', 'mv15', 'rng15'], True)
    f = pd.read_pickle(os.path.join(C, 'p4_orders_feat.pkl')).dropna(subset=['off_prev_close', 'mv15'])
    f['label'] = (f.off_prev_close.round() != 0).astype(int); f['ce'] = (f.cp == 'CE').astype(int); f['ux'] = (f.und == 'SENSEX').astype(int)
    f['mins'] = (f.m.dt.hour * 60 + f.m.dt.minute) - 555; f['d0'] = (f.day == 'D0').astype(int); f['grid'] = f.grid.astype(int)
    sgn = np.where(f.cp == 'CE', 1, -1)
    for c in ['mv3', 'mv5', 'mv10', 'mv15']: f[c + 's'] = f[c] / f.prev_close * 1e4 * sgn
    D['D3 strike offset != ATM (sale)'] = (f, ['frac', 'grid', 'd0', 'mins', 'ce', 'ux'], ['mv3s', 'mv5s', 'mv10s', 'mv15s'], True)
    g = f[f.label == 1].copy(); g['label'] = (g.off_prev_close * np.where(g.cp == 'CE', 1, -1) > 0).astype(int)   # offset toward OTM
    D['D3b offset direction (OTM vs ITM)'] = (g, ['frac', 'grid', 'd0', 'mins', 'ce', 'ux'], ['mv3s', 'mv5s', 'mv10s', 'mv15s'], True)
    Y = pd.read_pickle(os.path.join(C, 'p2_contract_minutes.pkl')); Y['und'] = np.where(Y.ux == 1, 'SENSEX', 'NIFTY')
    D['D4 D0 buy-back hazard (contract-minute)'] = (Y, ['nlots', 'emin', 'emean', 'carried', 'px', 'r_min', 'r_mean', 'rh_min', 'mny', 'mins', 'ux', 'ce'], ['mv1', 'mv5', 'mv15'], True)
    A = pd.read_pickle(os.path.join(C, 'a2_clock_rows.pkl')); A['m'] = A.date + pd.Timedelta('09:15:00') + pd.to_timedelta(A.tmin, unit='min')
    D['D6 clock-event rebalance choice'] = (A, ['tmin', 'nl', 'carried', 'itm', 'absdist', 'px', 'r_min', 'r_mean', 'has_sells', 'dist_to_sold', 'ux', 'ce', 'isB'], [], True)
    L = pd.read_pickle(os.path.join(C, 'p1_crossed_lots.pkl')); L['m'] = pd.to_datetime(L.date) + pd.Timedelta('09:15:00') + pd.to_timedelta(L.trig_min, unit='min')
    L['label'] = L.stopped
    D['D7 leg stop executed vs survived'] = (L, ['entry_px', 'entry_px_rel', 'entry_min', 'entry_slot', 'entry_off', 'grid', 'opening', 'trig_min', 'hold_min', 'ux', 'ce', 'd0'], [], True)
    s = pd.read_pickle(os.path.join(C, 'sale_orders.pkl')); s = s[(s.dte >= 1)].copy()
    s['und'] = s.date.map(X.drop_duplicates('date').set_index('date').und)
    mins = (s.t.dt.hour * 60 + s.t.dt.minute) - 556; s = s[(mins % 15 <= 2) & (mins >= 0)].copy(); s['k'] = ((s.t.dt.hour * 60 + s.t.dt.minute) - 556) // 15
    q = s.groupby(['date', 'und', 'k', 'cp']).lots.sum().reset_index()
    q['mode'] = q.groupby(['k', 'cp']).lots.transform(lambda x: x.mode().iloc[0]); q['label'] = (q.lots > q['mode']).astype(int)
    q['m'] = q.date + pd.Timedelta('09:16:00') + pd.to_timedelta(q.k * 15, unit='min'); q['ce'] = (q.cp == 'CE').astype(int); q['ux'] = (q.und == 'SENSEX').astype(int)
    D['D5 scheduled slot sized above ladder (D-1)'] = (q, ['k', 'ce', 'ux'], [], True)
    return D

def attach(df, side_sign, mapping=None):
    x = df[['und', 'm']].copy()
    if mapping is not None:
        x['m'] = [mapping[(u, m.normalize())] + (m - m.normalize()) for u, m in zip(x.und, x.m)]
    J = x.merge(IND, on=['und', 'm'], how='left')[IND_COLS].reset_index(drop=True)
    if side_sign:
        sg = np.where(df.ce.values == 1, 1, -1)
        for c in DIRECTIONAL: J[c] = (J[c] - CENTER[c]) * sg
    J.index = df.index
    return J

def folds(dates, k=3):
    u = sorted(dates.unique()); n = len(u); cuts = [u[int(n * f)] for f in (0.5, 0.67, 0.84)] + [u[-1] + pd.Timedelta(days=1)]
    return [(dates < cuts[i], (dates >= cuts[i]) & (dates < cuts[i + 1])) for i in range(k)]

def oos_auc(X, y, dates):
    ps, ys = [], []
    for tr, te in folds(dates):
        if y[tr].nunique() < 2 or y[te].nunique() < 2: continue
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, verbose=-1)
        m.fit(X[tr], y[tr]); ps.append(m.predict_proba(X[te])[:, 1]); ys.append(y[te].values)
    return roc_auc_score(np.concatenate(ys), np.concatenate(ps))

def derangement_map(rng):
    mp = {}
    for u, g in IND.groupby('und'):
        days = sorted(g.m.dt.normalize().unique())
        while True:
            p = rng.permutation(len(days))
            if not np.any(p == np.arange(len(days))): break
        for i, dd in enumerate(days): mp[(u, dd)] = days[p[i]]
    return mp

if __name__ == '__main__':
    rng = np.random.default_rng(7); maps = [derangement_map(rng) for _ in range(5)]
    out = []
    for name, (df, base, price, side) in datasets().items():
        df = df.dropna(subset=['label']).reset_index(drop=True)
        if len(df) > 80000: df = df.sample(80000, random_state=0).reset_index(drop=True)
        dates = pd.to_datetime(df.date); y = df.label.astype(int)
        Xb = df[base].astype(float); a_b = oos_auc(Xb, y, dates)
        Xp = pd.concat([Xb, df[price].astype(float)], axis=1) if price else Xb; a_p = oos_auc(Xp, y, dates)
        Xi = pd.concat([Xp, attach(df, side)], axis=1); a_i = oos_auc(Xi, y, dates)
        nul = [oos_auc(pd.concat([Xp, attach(df, side, mp)], axis=1), y, dates) for mp in maps]
        out.append(dict(decision=name, n=len(df), pos_rate=round(y.mean(), 3), auc_base=round(a_b, 3), auc_plus_price=round(a_p, 3), auc_plus_ind=round(a_i, 3),
                        gain_ind=round(a_i - a_p, 3), null_gain_mean=round(np.mean(nul) - a_p, 3), null_gain_max=round(np.max(nul) - a_p, 3),
                        beats_all_nulls=bool(a_i > max(nul))))
        print(out[-1], flush=True)
    R = pd.DataFrame(out); R.to_csv(os.path.join(C, 'b2_model_level.csv'), index=False)
    pd.set_option('display.width', 250); print(R.to_string(index=False))
