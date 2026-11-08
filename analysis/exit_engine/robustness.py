"""Section 9 - validation and robustness of the exit models (thresholds fixed on VAL, never re-tuned here).
1 Segment validation on VAL and TEST: per index, D-1 vs D0, fresh vs carried contracts, high vs low volatility cycles (threshold = DEV median of
  the cycle mean 1-min ATR in bp), trend vs sideways sessions (|close-open| / (high-low) of the session >= 0.5).
2 Cycle-level bootstrap 90 % confidence intervals (resample TEST cycles, 2000 reps) for precision / recall / AP.
3 Feature ablation: LightGBM re-fitted on DEV without one family at a time, early stopping on VAL; AP on VAL and TEST.
4 Missing-data / incomplete-chain stress: option bars removed at random (10 %, 25 %) or in 15-minute blocks (10 % of blocks); the contract-minute
  features are rebuilt from the damaged bars and the stored models are scored on TEST at their VAL thresholds.
Execution and transaction-cost stress of the replay are in replay.py (--fill open|adverse|delay1; zero/moderate/conservative/adverse costs).
python3 analysis/exit_engine/robustness.py -> results/robustness_results.csv"""
import sys, os, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import lightgbm as lgb
from sklearn.metrics import precision_score, recall_score, average_precision_score
from common import markets, RES, C
import bookstate
from models import prep, feats_of, proba, build_cmb

FAM = {'premium ratio': lambda f: f.startswith('r_') or f in ('rh_prev', 'px', 'e_cheap', 'e_avg'),
       'P&L / drawdown': lambda f: f.startswith('upnl') or f.startswith('mtm') or f in ('up_basket',),
       'spot move / ATR / RV': lambda f: f.startswith('adv_') or f.startswith('mv') or f in ('atr', 'rv1', 'otm_atr', 'otm_pts'),
       'Greeks / IV': lambda f: f in ('delta', 'gamma', 'vega', 'theta', 'iv', 'dexp', 'gexp', 'vexp') or f.startswith('net_'),
       'inventory / concentration': lambda f: f.startswith('n_') or f.startswith('lots') or f in ('share_side', 'imbalance', 'max_share'),
       'timing since trades / age': lambda f: f.startswith('age_') or f.startswith('since_'),
       'clock / calendar': lambda f: f in ('clockB', 'gridA', 'grid00', 'hhmm', 'day', 'tte_min')}
MAIN = ['1 individual lot stop', '1b any unscheduled buy-back (label-free)', '5 expiry-day carried-position exit (non-salvage, non-final)', '6 expiry-day salvage']

def regimes(BM):
    mk = markets(); r = {}
    for (u, e), m in mk.items():
        S = m['S']; a = np.nanmean(m['atr1'] / S * 1e4)
        d0 = m['day'] == 1
        x = S[d0] if d0.any() else S
        trend = abs(x[-1] - x[0]) / max(x.max() - x.min(), 1e-9)
        r[(u, e)] = dict(atr_bp=a, trend=trend)
    R = pd.DataFrame(r).T; R.index.names = ['und', 'expiry']; return R.reset_index()

def seg_metrics(D, y, p, thr, name, algo):
    out = []
    segs = {'all': np.ones(len(D), bool), 'NIFTY': (D.und == 'NIFTY').values, 'SENSEX': (D.und == 'SENSEX').values, 'D-1': (D.day == 0).values, 'D0': (D.day == 1).values,
            'fresh contracts': (D.n_carried == 0).values if 'n_carried' in D else None, 'carried contracts': (D.n_carried > 0).values if 'n_carried' in D else None,
            'high-vol cycles': (D.vol == 'high').values, 'low-vol cycles': (D.vol == 'low').values, 'trend sessions': (D.trend >= 0.5).values, 'sideways sessions': (D.trend < 0.5).values}
    yy = D[y].astype(int).values; pr = p >= thr
    for s, msk in segs.items():
        if msk is None or msk.sum() == 0: continue
        out.append(dict(test='segment', model=name, algorithm=algo, split=D.split.iloc[0], segment=s, n_events=int(yy[msk].sum()), precision=precision_score(yy[msk], pr[msk], zero_division=0),
                        recall=recall_score(yy[msk], pr[msk], zero_division=0), avg_precision=average_precision_score(yy[msk], p[msk]) if yy[msk].sum() else np.nan))
    return out

def bootstrap(D, y, p, thr, name, algo, reps=2000, seed=0):
    rng = np.random.default_rng(seed); cyc = D[['und', 'expiry']].drop_duplicates().values.tolist(); idx = {tuple(c): np.where((D.und == c[0]) & (D.expiry == c[1]))[0] for c in cyc}
    yy = D[y].astype(int).values; pr = p >= thr; P, R, A = [], [], []
    for _ in range(reps):
        pick = rng.integers(0, len(cyc), len(cyc)); ix = np.concatenate([idx[tuple(cyc[j])] for j in pick])
        if yy[ix].sum() == 0: continue
        P.append(precision_score(yy[ix], pr[ix], zero_division=0)); R.append(recall_score(yy[ix], pr[ix], zero_division=0)); A.append(average_precision_score(yy[ix], p[ix]))
    q = lambda v: (np.percentile(v, 5), np.percentile(v, 95))
    return dict(test='bootstrap 90% CI (TEST cycles)', model=name, algorithm=algo, split='TEST', precision_lo=q(P)[0], precision_hi=q(P)[1], recall_lo=q(R)[0], recall_hi=q(R)[1],
                ap_lo=q(A)[0], ap_hi=q(A)[1], n_cycles=len(cyc))

def damage(mk, kind, frac, seed=0):
    rng = np.random.default_rng(seed); out = {}
    for key, m in mk.items():
        m2 = dict(m); M = {c: m[c].copy() for c in 'OHLC'}
        nk, n = M['C'].shape
        if kind == 'random':
            drop = rng.random((nk, n)) < frac
        else:
            drop = np.zeros((nk, n), bool)
            for kk in range(nk):
                for b in range(0, n, 15):
                    if rng.random() < frac: drop[kk, b:b + 15] = True
        for c in 'OHLC': M[c][drop] = np.nan
        m2.update(O=M['O'], H=M['H'], L=M['L'], C=M['C'], Cf=pd.DataFrame(M['C'].T).ffill().values.T.astype(np.float32)); m2.pop('prep', None)
        out[key] = m2
    return out

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    CM, BM = bookstate.load(); store = pd.read_pickle(os.path.join(C, 'exit_models.pkl'))
    CMb = build_cmb(CM, BM); rg = regimes(BM)
    dev_cyc = CMb[CMb.split == 'DEV'][['und', 'expiry']].drop_duplicates().merge(rg, on=['und', 'expiry'])
    vt = dev_cyc.atr_bp.median(); rg['vol'] = np.where(rg.atr_bp >= vt, 'high', 'low')
    X = prep(CMb.merge(rg[['und', 'expiry', 'vol', 'trend']], on=['und', 'expiry'], how='left'))
    rows = []
    for name in MAIN:
        st = store.get(name)
        if st is None: continue
        y = st['y']
        sub = X if not name.startswith('5') else X[(X.day == 1) & (X.n_carried > 0)].copy()
        if name.startswith('5'): sub['y_carried_exit'] = (sub.closed > 0) & ~sub.close_label.isin(['7 expiry-day salvage', '6 clock-based exit (final flatten)'])
        if name.startswith('6'): sub = X[X.day == 1]
        for algo in ('lightgbm', 'catboost', 'logistic'):
            m = st['models'][algo]; thr = st['thr'][algo]
            for sp in ('VAL', 'TEST'):
                D = sub[sub.split == sp]
                if not len(D): continue
                p = proba(m, D, st['feats']); rows += seg_metrics(D, y, p, thr, name, algo)
                if sp == 'TEST': rows.append(bootstrap(D, y, p, thr, name, algo))
    # feature ablation (LightGBM) on the two contract-level models
    for name, y in (('1 individual lot stop', 'y_lotstop'), ('1b any unscheduled buy-back (label-free)', 'y_unsched')):
        feats = store[name]['feats']; dev, val, tst = X[X.split == 'DEV'], X[X.split == 'VAL'], X[X.split == 'TEST']
        for fam, sel in [('none (full model)', lambda f: False)] + list(FAM.items()):
            ff = [f for f in feats if not sel(f)]
            mm = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.03, num_leaves=31, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1,
                                    random_state=0).fit(dev[ff].astype(float), dev[y], eval_set=[(val[ff].astype(float), val[y])], eval_metric='average_precision',
                                                        callbacks=[lgb.early_stopping(100, verbose=False)])
            rows.append(dict(test='feature ablation (LightGBM, DEV fit)', model=name, algorithm='lightgbm', segment=f'without {fam}', n_features=len(ff),
                             val_ap=average_precision_score(val[y], mm.predict_proba(val[ff].astype(float))[:, 1]), test_ap=average_precision_score(tst[y], mm.predict_proba(tst[ff].astype(float))[:, 1])))
        print('ablation done', name, flush=True)
    # missing-data / incomplete-chain stress
    mk = markets()
    for kind, frac in (('random', 0.10), ('random', 0.25), ('block15', 0.10)):
        mkd = damage(mk, kind, frac)
        CMd, BMd = bookstate.build(mk=mkd, save=False)
        Xd = prep(build_cmb(CMd, BMd)); Xd = Xd[Xd.split == 'TEST']
        for name in ('1 individual lot stop', '1b any unscheduled buy-back (label-free)'):
            st = store[name]; y = st['y']
            for algo in ('lightgbm', 'logistic'):
                p = proba(st['models'][algo], Xd, st['feats']); pr = p >= st['thr'][algo]
                rows.append(dict(test=f'missing-data stress: {kind} {int(frac * 100)}%', model=name, algorithm=algo, split='TEST', n_events=int(Xd[y].sum()), n_rows=len(Xd),
                                 precision=precision_score(Xd[y], pr, zero_division=0), recall=recall_score(Xd[y], pr, zero_division=0), avg_precision=average_precision_score(Xd[y], p)))
        print('stress done', kind, frac, flush=True)
    R = pd.DataFrame(rows); R.to_csv(os.path.join(RES, 'robustness_results.csv'), index=False)
    print(R.round(3).to_string(index=False))
