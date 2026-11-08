"""B2f: name the residual indicator signals that survive conditioning on raw price (D7 trend family, D3 options family).
Gain-importance inside the family model + within-DATE stratified AUC (removes between-day confounding).  python3 analysis/b2_residual_signals.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
import b2_indicator_tests as B
from b2_univariate import strat_auc
from b2_followup import fam_cols, add_price
C = B.C
D = B.datasets()
for name, fam in [('D7 leg stop executed vs survived', 'trend'), ('D3 strike offset != ATM (sale)', 'options'), ('D3b offset direction (OTM vs ITM)', 'levels')]:
    df, base, price, side = D[name]; df = df.dropna(subset=['label']).reset_index(drop=True)
    if not price: df, price = add_price(df)
    real = B.attach(df, side); cols = fam_cols(fam); y = df.label.astype(int).values
    X = pd.concat([df[base + price].astype(float), real[cols]], axis=1)
    m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, verbose=-1).fit(X, y)
    imp = pd.Series(m.booster_.feature_importance('gain'), index=X.columns).loc[cols].sort_values(ascending=False)
    strata_day = (pd.to_datetime(df.date).dt.strftime('%Y%m%d') + '_' + (df.m.dt.hour >= 12).astype(str)).values
    strata_tod = (df.m.dt.hour * 2 + (df.m.dt.minute >= 30)).astype(str).values
    print(f'\n=== {name} | family {fam}: top features by gain, with stratified AUC (time-of-day) and within-date AUC')
    for c in imp.index[:6]:
        x = real[c].values.astype(float)
        print(f'   {c:22s} gain {imp[c] / imp.sum():.2f}  AUC(tod) {strat_auc(x, y, strata_tod):.3f}  AUC(within date) {strat_auc(x, y, strata_day):.3f}  '
              f'corr with raw 5m move {np.corrcoef(np.nan_to_num(x), np.nan_to_num(df[price[1]].astype(float)))[0, 1]:+.2f}')
