"""Section 7 - machine-learning reconstruction of the exit controller.
Protocol: chronological whole-cycle split by expiry (DEV 18 cycles fit, VAL 8 cycles early-stopping + decision threshold, TEST 9 cycles scored once).
Cycles do not overlap in time and every feature is computed inside its own cycle, so no purge gap is needed (no cross-cycle features).
No-exit opportunities are kept (every open short contract-minute / side-minute / book-minute / candidate).
Algorithms: logistic regression (balanced), LightGBM, CatBoost, depth-3 tree (rules exported), discrete-time hazard (logit on duration bins + covariates).
Metrics on VAL and TEST: precision, recall (strict minute), event coverage (fires at the event minute or the next minute on the same unit:
a minute-bar controller can only see an intrabar trigger after the bar closes), macro-F1, average precision, Brier, ECE, quantity agreement.
Definitional coupling (stated, not hidden): taxonomy classes defined by a threshold on a feature (lot stop: quote/cheapest >= 1.45; salvage: quote <= 1 or
<= 5 % of entry) are partly predictable by construction; the label-free model 'any unscheduled buy-back' is reported next to them.
python3 analysis/exit_engine/models.py -> results/exit_model_metrics.csv, results/exit_model_trees.txt, _cache/exit_models.pkl"""
import sys, os, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, brier_score_loss
import lightgbm as lgb
THREADS = int(os.environ.get('ALGO8_THREADS', '4'))        # split jobs run side by side: each gets its own share of the 4 cores
from catboost import CatBoostClassifier
from common import orders, RES, SCHEDULED, C, split_of
import bookstate
from side_basket import episodes, side_panel, candidate_sets

ACTION_COLS = {'closed', 'closed_contracts', 'close_label', 'close_L', 'sold', 'quote', 'bb_lots', 'bb_labels', 'n_bb_contracts', 'bb_sides', 'sale_lots', 'sale_sides', 'y', 'chosen'}
ID_COLS = {'und', 'expiry', 'mi', 'm', 'cp', 'strike', 'split', 'ep', 'n_chosen', 'contracts', 'sides', 'labels', 'cls'}
BOOK_JOIN = ['mtm', 'mtm_dd', 'mtm_peak', 'net_delta', 'net_gamma', 'net_vega', 'net_theta', 'n_contracts', 'lots_tot', 'lots_ce', 'lots_pe', 'imbalance', 'max_share',
             'up_basket', 'since_sale', 'since_bb', 'mv1', 'mv5', 'mv15', 'mv30', 'atr', 'rv1', 'mv_d0open', 'mv_prevclose']

def ece(y, p, bins=10):
    y = np.asarray(y, float); p = np.asarray(p, float); e = 0.0
    q = np.clip((p * bins).astype(int), 0, bins - 1)
    for b in range(bins):
        m = q == b
        if m.any(): e += m.mean() * abs(y[m].mean() - p[m].mean())
    return e

def feats_of(df):
    num = lambda c: pd.api.types.is_bool_dtype(df[c]) or pd.api.types.is_numeric_dtype(df[c])      # excludes object AND pandas string dtypes
    return [c for c in df.columns if c not in ACTION_COLS | ID_COLS and num(c) and not c.startswith('y_')]

def prep(df):
    X = df.copy()
    if 'cp' in X: X['is_ce'] = (X.cp == 'CE').astype(float)
    X['is_nifty'] = (X.und == 'NIFTY').astype(float)
    for c in X.columns:
        if X[c].dtype == bool: X[c] = X[c].astype(float)
    return X

class HazardFeatures:
    """discrete-time hazard design: duration-bin dummies + covariates (a class, not a closure, so fitted models can be pickled)"""
    EDGES = [-1, 5, 15, 30, 60, 120, 240, 1e9]
    def __init__(self, dur, cov): self.dur, self.cov = dur, list(cov)
    def __call__(self, D):
        b = pd.cut(D[self.dur].astype(float), self.EDGES, labels=False)                      # integer bin id 0..6 (NaN stays NaN)
        H = pd.get_dummies(b, prefix='dur').astype(float).reindex(columns=[f'dur_{i}' for i in range(len(self.EDGES) - 1)], fill_value=0.0)   # same columns on every split
        return pd.concat([H.reset_index(drop=True), D[self.cov].astype(float).reset_index(drop=True)], axis=1)

def fit_all(dev, val, feats, y, hazard_cols=None, seed=0):
    Xd, Xv = dev[feats].astype(float), val[feats].astype(float); yd, yv = dev[y].astype(int).values, val[y].astype(int).values
    M = {}
    M['logistic'] = make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler(), LogisticRegression(C=0.5, class_weight='balanced', max_iter=3000)).fit(Xd, yd)
    M['lightgbm'] = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.03, num_leaves=31, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                       reg_lambda=1.0, verbose=-1, random_state=seed, n_jobs=THREADS).fit(Xd, yd, eval_set=[(Xv, yv)], eval_metric='average_precision',
                                                                                         callbacks=[lgb.early_stopping(100, verbose=False)])
    M['catboost'] = CatBoostClassifier(iterations=1500, depth=6, learning_rate=0.05, verbose=0, random_seed=seed, thread_count=THREADS, eval_metric='PRAUC',
                                       od_type='Iter', od_wait=100).fit(Xd, yd, eval_set=(Xv, yv), use_best_model=True)
    M['tree_depth3'] = DecisionTreeClassifier(max_depth=3, min_samples_leaf=50, random_state=seed).fit(Xd.fillna(-999), yd)
    if hazard_cols is not None:
        dur, cov = hazard_cols; hz = HazardFeatures(dur, cov)
        M['hazard_logit'] = (make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=0.5, max_iter=3000)).fit(hz(dev), yd), hz)
    return M

def proba(m, X, feats):
    if isinstance(m, tuple): mod, hz = m; return mod.predict_proba(hz(X))[:, 1]
    Xf = X[feats].astype(float)
    if isinstance(m, DecisionTreeClassifier): Xf = Xf.fillna(-999)
    return m.predict_proba(Xf)[:, 1]

def best_threshold(y, p):
    best, bt = -1, 0.5
    for t in np.unique(np.quantile(p, np.linspace(0.5, 0.9995, 200))):
        f = f1_score(y, p >= t, zero_division=0)
        if f > best: best, bt = f, t
    return bt

def coverage(df, y, pred, unit):
    """share of events where the model fires at the event minute or the next minute on the same unit"""
    D = df[unit + ['mi']].copy(); D['pred'] = pred; D['y'] = df[y].values
    pos = set(map(tuple, D.loc[D.pred, unit + ['mi']].values.tolist()))
    ev = D[D.y.astype(bool)]
    if not len(ev): return np.nan
    hit = [tuple(r[:-1]) + (r[-1],) in pos or tuple(r[:-1]) + (r[-1] + 1,) in pos for r in ev[unit + ['mi']].values.tolist()]
    return float(np.mean(hit))

def score(name, algo, split, df, y, p, thr, unit, qty=None):
    yy = df[y].astype(int).values; pr = p >= thr
    r = dict(model=name, algorithm=algo, split=split, n_rows=len(df), n_events=int(yy.sum()), base_rate=yy.mean(), threshold=thr,
             precision=precision_score(yy, pr, zero_division=0), recall=recall_score(yy, pr, zero_division=0), macro_f1=f1_score(yy, pr, average='macro', zero_division=0),
             f1=f1_score(yy, pr, zero_division=0), avg_precision=average_precision_score(yy, p) if yy.sum() else np.nan, brier=brier_score_loss(yy, np.clip(p, 0, 1)), ece=ece(yy, np.clip(p, 0, 1)),
             event_coverage_lag1=coverage(df, y, pr, unit) if unit else np.nan)
    if qty is not None:
        rule, col_closed, col_open = qty
        tp = pr & (yy == 1)
        if tp.any():
            pq = rule(df[tp]); r['quantity_agreement'] = float(np.mean(pq == df.loc[tp, col_closed].values))
    r['meets_80_80'] = bool(r['precision'] >= 0.8 and r['recall'] >= 0.8)
    r['coverage_adequate'] = bool(r['n_events'] >= 30)
    return r

def run_model(name, df, y, unit, hazard=None, qty=None, rows=None, store=None, trees=None):
    df = prep(df); feats = feats_of(df)
    dev, val, tst = df[df.split == 'DEV'], df[df.split == 'VAL'], df[df.split == 'TEST']
    if dev[y].sum() < 20 or val[y].sum() < 5:
        rows.append(dict(model=name, algorithm='-', split='-', n_events=int(dev[y].sum()), note='too few events to fit')); return
    M = fit_all(dev, val, feats, y, hazard); TH = {}
    for algo, m in M.items():
        pv = proba(m, val, feats); thr = best_threshold(val[y].astype(int).values, pv); TH[algo] = thr
        for sp, D in (('VAL', val), ('TEST', tst)):
            if not len(D): continue
            p = proba(m, D, feats); rows.append(score(name, algo, sp, D, y, p, thr, unit, qty))
        if algo == 'tree_depth3': trees[name] = export_text(m, feature_names=feats, decimals=2)
    store[name] = dict(models=M, feats=feats, thr=TH, y=y, unit=unit)

def build_cmb(CM, BM):
    CMb = CM.merge(BM[['und', 'expiry', 'mi'] + BOOK_JOIN], on=['und', 'expiry', 'mi'], how='left')
    CMb['y_lotstop'] = CMb.close_label == '1 individual lot stop-loss'
    CMb['y_unsched'] = (CMb.closed > 0) & ~CMb.close_label.isin(SCHEDULED)
    CMb['y_salvage'] = CMb.close_label == '7 expiry-day salvage'
    CMb['y_any'] = CMb.closed > 0
    return CMb

def qty_rule_from_dev(df_dev, closed='closed', open_='n_lots'):
    """DEV-learned quantity rule: if 'all lots' is the modal outcome -> close all, else close 1 lot"""
    frac_all = (df_dev[closed] >= df_dev[open_]).mean(); one = (df_dev[closed] == 1).mean()
    if frac_all >= one: return (lambda D: D[open_].values), 'all lots'
    return (lambda D: np.ones(len(D))), '1 lot'


# ----------------------------------------------------------------------------------------------------------------------------
# Split jobs.  Each job fits ONE model family on DEV, picks thresholds on VAL, scores VAL and TEST once, and writes
#   results/models/<key>/metrics.csv, tree.txt   and   _cache/exit_models/<key>.pkl
# `--merge` combines them into results/exit_model_metrics.csv, results/exit_model_trees.txt and _cache/exit_models.pkl.
# python3 analysis/exit_engine/models.py --only 1_lotstop        (one job)        |  --list  |  --merge
# ----------------------------------------------------------------------------------------------------------------------------
JOBS = ['1_lotstop', '1b_unsched', '2_side', '3_basket', '4_clockb', '5_carried', '6_salvage', '6b_profit', '7_reentry', '8_final', '0_multiclass']
MDIR = os.path.join(RES, 'models'); SDIR = os.path.join(C, 'exit_models')

def job_context():
    CM, BM = bookstate.load(); return dict(CM=CM, BM=BM, CMb=build_cmb(CM, BM))

def run_job(key, rows, store, trees):
    ctx = job_context(); CM, BM, CMb = ctx['CM'], ctx['BM'], ctx['CMb']
    if key == '1_lotstop':
        q_rule, _ = qty_rule_from_dev(CMb[(CMb.split == 'DEV') & CMb.y_lotstop])
        run_model('1 individual lot stop', CMb, 'y_lotstop', ['und', 'expiry', 'cp', 'strike'], hazard=('age_cheap', ['r_cheap', 'rh_prev', 'r_avg', 'day', 'tte_min']),
                  qty=(q_rule, 'closed', 'n_lots'), rows=rows, store=store, trees=trees)
    elif key == '1b_unsched':
        run_model('1b any unscheduled buy-back (label-free)', CMb, 'y_unsched', ['und', 'expiry', 'cp', 'strike'],
                  hazard=('age_cheap', ['r_cheap', 'rh_prev', 'r_avg', 'day', 'tte_min', 'clockB', 'gridA']), rows=rows, store=store, trees=trees)
    elif key in ('2_side', '3_basket', '7_reentry'):
        E, _ = episodes(); U = E[~E.scheduled]
        if key == '2_side':
            P = side_panel(CM, BM)
            s1 = set((r.und, r.expiry, r.mi, r.sides) for r in U[U.multi_strike_one_side].itertuples())
            P['y_side'] = [(u, e, mi, cp) in s1 for u, e, mi, cp in zip(P.und, P.expiry, P.mi, P.cp)]
            run_model('2 side-level reduction', P[P.n_contracts_side >= 2], 'y_side', ['und', 'expiry', 'cp'], rows=rows, store=store, trees=trees)
        elif key == '3_basket':
            bas = set(zip(U[U.both_sides].und, U[U.both_sides].expiry, U[U.both_sides].mi))
            B2 = BM[BM.n_contracts >= 2].copy(); B2['y_basket'] = [(u, e, mi) in bas for u, e, mi in zip(B2.und, B2.expiry, B2.mi)]
            run_model('3 basket-level reduction', B2, 'y_basket', ['und', 'expiry'], rows=rows, store=store, trees=trees)
        else:
            RE = E[~E.scheduled].merge(BM, on=['und', 'expiry', 'mi', 'split'], how='left', suffixes=('', '_b'))
            RE['y_reentry'] = RE.rebalance_with_replacement; RE['clockB_ep'] = RE.clock == 'B'; RE['clockA_ep'] = RE.clock.isin(['A', 'A0'])
            RE['lotstop_ep'] = RE.labels.str.contains('1 individual'); RE['sideboth'] = RE.both_sides.astype(float); RE['n_contracts_ep'] = RE.n_contracts; RE['lots_ep'] = RE.lots
            RE = RE.drop(columns=['t', 'n_contracts'], errors='ignore')
            run_model('7 re-entry (same-side sale within 60 s of a buy-back episode)', RE.drop(columns=['rebalance_with_replacement', 'same_contract_buy_sell']), 'y_reentry', None,
                      rows=rows, store=store, trees=trees)
    elif key == '4_clockb':
        from clock_b import tick_of
        from common import markets, minute_index
        o = orders(); mk = markets(); ob = o[(o.closing_short == True) & (o.dte == 0) & ~o.label.isin(['5 cycle stop & liquidation', '10 manual / platform risk engine'])].copy()
        ob['tick'] = [tick_of(t) for t in pd.to_datetime(ob.t_dec)]; ob = ob[ob.tick.notna()]
        ob['tick_mi'] = [minute_index(mk[(u, e)]['grid'], t) for u, e, t in zip(ob.und, ob.expiry, ob.tick)]
        ob['mi'] = ob.groupby(['und', 'expiry', 'tick']).tick_mi.transform('min') - 1
        EB = ob.groupby(['und', 'expiry', 'mi', 'cp']).agg(contracts=('strike', lambda s: ';'.join(sorted(set(f'{cp}{int(k)}' for cp, k in zip(ob.loc[s.index, 'cp'], s)))))).reset_index()
        EB['sides'] = EB.cp; EB['split'] = EB.expiry.map(split_of); EB['ep'] = np.arange(len(EB))
        G = candidate_sets(CM, EB, lambda z: z)
        if len(G):
            G = G.merge(BM[['und', 'expiry', 'mi'] + BOOK_JOIN], on=['und', 'expiry', 'mi'], how='left'); G['y_chosen'] = G.chosen
            nm = '4 clock-B contract selection (candidate-level)'
            run_model(nm, G.drop(columns=['chosen']), 'y_chosen', ['ep', 'cp', 'strike'], rows=rows, store=store, trees=trees)
            st = store.get(nm)
            if st:
                Gp = prep(G.drop(columns=['chosen']))
                for algo in ('lightgbm', 'catboost', 'logistic'):
                    Gp['s'] = proba(st['models'][algo], Gp, st['feats'])
                    for sp in ('VAL', 'TEST'):
                        g = Gp[Gp.split == sp]
                        if not len(g): continue
                        top = g.loc[g.groupby('ep').s.idxmax()]
                        rows.append(dict(model='4 clock-B contract selection (top-1 per tick-side)', algorithm=algo, split=sp, n_rows=g.ep.nunique(), n_events=g.ep.nunique(),
                                         precision=top.y_chosen.mean(), recall=np.nan, note=f'random baseline {g.groupby("ep").y_chosen.mean().mean():.3f}'))
    elif key == '5_carried':
        CR = CMb[(CMb.day == 1) & (CMb.n_carried > 0)].copy()
        CR['y_carried_exit'] = (CR.closed > 0) & ~CR.close_label.isin(['7 expiry-day salvage', '6 clock-based exit (final flatten)'])
        run_model('5 expiry-day carried-position exit (non-salvage, non-final)', CR, 'y_carried_exit', ['und', 'expiry', 'cp', 'strike'],
                  hazard=('age_oldest', ['r_cheap', 'r_prevclose', 'rh_prev', 'tte_min', 'adv_mv15']), rows=rows, store=store, trees=trees)
    elif key == '6_salvage':
        D0 = CMb[CMb.day == 1].copy()
        run_model('6 expiry-day salvage', D0, 'y_salvage', ['und', 'expiry', 'cp', 'strike'], rows=rows, store=store, trees=trees)
    elif key == '6b_profit':
        D0 = CMb[CMb.day == 1].copy()
        D0['y_profit'] = (D0.closed > 0) & ~D0.close_label.isin(SCHEDULED + ('1 individual lot stop-loss',)) & (D0.r_avg < 1)
        run_model('6b D0 in-profit unscheduled exit (profit-taking)', D0, 'y_profit', ['und', 'expiry', 'cp', 'strike'], rows=rows, store=store, trees=trees)
    elif key == '8_final':
        FL = BM[(BM.day == 1) & (BM.hhmm >= 14 * 60 + 45) & (BM.n_contracts >= 1)].copy()
        FL['y_final'] = FL.bb_labels.str.contains('final flatten')
        run_model('8 final liquidation (D0 book-minute)', FL, 'y_final', ['und', 'expiry'], rows=rows, store=store, trees=trees)
    elif key == '0_multiclass':
        from sklearn.metrics import classification_report
        cm = prep(CMb); feats = [f for f in feats_of(cm) if not f.startswith('y_')]
        cls = sorted(cm.close_label.unique()); c2i = {c: i for i, c in enumerate(cls)}; cm['yc'] = cm.close_label.map(c2i)
        dv, vl, ts = cm[cm.split == 'DEV'], cm[cm.split == 'VAL'], cm[cm.split == 'TEST']
        # capacity cap (this is the job that exceeded the 2-hour limit: 12 classes x up to 2000 trees): lr 0.08, <= 600 rounds, early stop 40 on VAL
        mc = lgb.LGBMClassifier(objective='multiclass', n_estimators=600, learning_rate=0.08, num_leaves=31, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                class_weight='balanced', verbose=-1, random_state=0, n_jobs=THREADS).fit(
            dv[feats].astype(float), dv.yc, eval_set=[(vl[feats].astype(float), vl.yc)], callbacks=[lgb.early_stopping(40, verbose=False)])
        for sp, D in (('VAL', vl), ('TEST', ts)):
            pr = mc.predict(D[feats].astype(float)); rep = classification_report(D.yc, pr, labels=list(range(len(cls))), target_names=cls, output_dict=True, zero_division=0)
            for c in cls:
                rows.append(dict(model='0 multi-class exit controller (contract-minute)', algorithm='lightgbm multiclass', split=sp, n_rows=len(D), n_events=int(rep[c]['support']),
                                 precision=rep[c]['precision'], recall=rep[c]['recall'], f1=rep[c]['f1-score'], note=c, meets_80_80=bool(rep[c]['precision'] >= .8 and rep[c]['recall'] >= .8),
                                 coverage_adequate=bool(rep[c]['support'] >= 30)))
            rows.append(dict(model='0 multi-class exit controller (contract-minute)', algorithm='lightgbm multiclass', split=sp, n_rows=len(D), macro_f1=rep['macro avg']['f1-score'],
                             note='macro over all classes incl. none'))
        store['0 multiclass'] = dict(models={'lightgbm': mc}, feats=feats, classes=cls, best_iteration=int(mc.best_iteration_ or 0))
    else: raise SystemExit(f'unknown job {key}; known: {JOBS}')

def merge():
    rows, trees, store = [], [], {}
    missing = [k for k in JOBS if not os.path.exists(os.path.join(MDIR, k, 'metrics.csv'))]
    for k in JOBS:
        p = os.path.join(MDIR, k)
        if os.path.exists(os.path.join(p, 'metrics.csv')):
            rows.append(pd.read_csv(os.path.join(p, 'metrics.csv')).assign(job=k))
            if os.path.exists(os.path.join(p, 'tree.txt')): trees.append(open(os.path.join(p, 'tree.txt')).read())
        sp = os.path.join(SDIR, k + '.pkl')
        if os.path.exists(sp): store.update(pd.read_pickle(sp))
    R = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    R.to_csv(os.path.join(RES, 'exit_model_metrics.csv'), index=False)
    open(os.path.join(RES, 'exit_model_trees.txt'), 'w').write(''.join(trees))
    pd.to_pickle(store, os.path.join(C, 'exit_models.pkl'))
    open(os.path.join(RES, 'exit_model_merge_status.txt'), 'w').write('missing jobs: ' + (', '.join(missing) or 'none') + '\n')
    print('merged', len(rows), 'jobs; missing:', missing or 'none')
    return R

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--only'); ap.add_argument('--merge', action='store_true'); ap.add_argument('--list', action='store_true'); a = ap.parse_args()
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    if a.list: print('\n'.join(JOBS)); raise SystemExit(0)
    if a.merge:
        R = merge(); cols = ['model', 'algorithm', 'split', 'n_events', 'precision', 'recall', 'event_coverage_lag1', 'macro_f1', 'avg_precision', 'brier', 'ece', 'quantity_agreement', 'meets_80_80', 'coverage_adequate', 'note']
        print(R[[c for c in cols if c in R]].round(3).to_string(index=False)); raise SystemExit(0)
    keys = [a.only] if a.only else JOBS
    for key in keys:
        import time; t0 = time.time(); rows, store, trees = [], {}, {}
        run_job(key, rows, store, trees)
        os.makedirs(os.path.join(MDIR, key), exist_ok=True); os.makedirs(SDIR, exist_ok=True)
        pd.DataFrame(rows).to_csv(os.path.join(MDIR, key, 'metrics.csv'), index=False)
        open(os.path.join(MDIR, key, 'tree.txt'), 'w').write(''.join(f'===== {k} (depth-3 tree, DEV fit) =====\n{t}\n' for k, t in trees.items()))
        pd.to_pickle(store, os.path.join(SDIR, key + '.pkl'))
        print(f'job {key} finished in {time.time() - t0:.0f}s: {len(rows)} metric rows', flush=True)
