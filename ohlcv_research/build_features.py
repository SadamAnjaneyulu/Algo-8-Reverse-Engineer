"""Build the feature tables (git-ignored cache) and the coverage / redundancy reports.  No target, no model, no outcome variable is touched here.
python3 ohlcv_research/build_features.py -> _cache/feat_{index,option,straddle}.pkl, results/feature_coverage.csv, results/feature_redundancy.csv, results/opportunity_counts.csv"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from common import *
import features as F

GROUP = {**{c: 'momentum' for c in F.INDEX_FEATURES[:9]}, **{c: 'mean reversion' for c in F.INDEX_FEATURES[9:12]}, **{c: 'volatility' for c in F.INDEX_FEATURES[12:17]},
         **{c: 'market structure' for c in F.INDEX_FEATURES[17:]}, **{c: 'option OHLC' for c in F.OPTION_FEATURES[:6]}, **{c: 'option volume' for c in F.OPTION_FEATURES[6:]},
         **{c: 'option OHLC (straddle)' for c in F.STRADDLE_FEATURES}}

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
    I = load_index(); O = load_options(); o = load_orders()
    X = F.index_features(I); Y = F.option_features(O, I); Z = F.straddle_features(O, I, STEP)
    X.to_pickle(os.path.join(CACHE, 'feat_index.pkl')); Y.to_pickle(os.path.join(CACHE, 'feat_option.pkl')); Z.to_pickle(os.path.join(CACHE, 'feat_straddle.pkl'))
    o = o.copy(); o['m'] = F.decision_minute(o); o['date'] = pd.to_datetime(o.date)
    ox = o[['oid', 'und', 'm']].merge(X, on=['und', 'm'], how='left'); oy = o[['oid', 'und', 'expiry', 'strike', 'cp', 'm']].merge(Y, on=['und', 'expiry', 'strike', 'cp', 'm'], how='left')
    oz = o[['oid', 'und', 'expiry', 'm']].merge(Z, on=['und', 'expiry', 'm'], how='left')
    rows = []
    for tab, T, A, cols in (('index (und, m)', X, ox, F.INDEX_FEATURES), ('option contract (contract, m)', Y, oy, F.OPTION_FEATURES), ('ATM straddle (und, expiry, m)', Z, oz, F.STRADDLE_FEATURES)):
        for c in cols:
            v = T[c].astype(float); rows.append(dict(table=tab, group=GROUP[c], feature=c, rows=len(T), available_share=float(v.notna().mean()), available_at_algo8_decisions=float(A[c].notna().mean()),
                                                     p01=v.quantile(.01), p50=v.quantile(.5), p99=v.quantile(.99)))
    COV = pd.DataFrame(rows); COV.to_csv(os.path.join(RES, 'feature_coverage.csv'), index=False); print(COV.round(3).to_string(index=False))
    red = []
    for tab, T, cols in (('index', X, F.INDEX_FEATURES), ('option', Y.sample(200000, random_state=0), F.OPTION_FEATURES), ('straddle', Z, F.STRADDLE_FEATURES[1:])):
        cm = T[cols].astype(float).corr(method='spearman')
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                red.append(dict(table=tab, a=a, b=b, spearman=cm.at[a, b]))
    RED = pd.DataFrame(red).assign(abs=lambda x: x.spearman.abs()).sort_values('abs', ascending=False); RED.to_csv(os.path.join(RES, 'feature_redundancy.csv'), index=False)
    print('\nmost redundant pairs (|Spearman|):'); print(RED.head(14).round(3).to_string(index=False)); print('pairs with |rho| > 0.9:', int((RED['abs'] > 0.9).sum()), '| > 0.8:', int((RED['abs'] > 0.8).sum()))
    # opportunity / event counts for the panel design (counts only; no features joined to outcomes)
    o['split'] = o.expiry.map(split_of); o['day'] = np.where(o.dte >= 1, 'D-1', 'D0')
    cls = {'scheduled or extra short entry (body sell, label open)': (o.label == 'open') & (o.side == 'Sell') & (o.tp == 'num'),
           'individual buy-back (label 1 individual lot stop-loss)': o.label == '1 individual lot stop-loss', 'side-level reduction': o.label == '3 side-level reduction',
           'basket reduction': o.label == '4 basket-level reduction', 'Clock-B rebalance': o.label == '8 clock-B rebalance', 'Clock-B exit, no replacement': o.label == '6 clock-based exit (clock B, no replacement)',
           'hedge: wing bought (open)': (o.label == 'open') & (o.side == 'Buy') & (o.tp != 'v_'), 'hedge: wing released': o.label.str.startswith('L-hedge release'), 'hedge: overnight lump': (o.label == 'open') & (o.tp == 'v_')}
    oc = []
    for k, msk in cls.items():
        g = o[msk]
        oc.append(dict(action=k, orders=len(g), lots=int(g.lots.sum()), cycles=g.groupby(['und', 'expiry']).ngroups, sessions=g.groupby(['und', 'date']).ngroups, distinct_decision_minutes=g.groupby(['und', 'm']).ngroups,
                       **{f'orders_{s}': int((g.split == s).sum()) for s in ('DEV', 'VAL', 'TEST')}, orders_D1=int((g.day == 'D-1').sum()), orders_D0=int((g.day == 'D0').sum())))
    OC = pd.DataFrame(oc); OC.to_csv(os.path.join(RES, 'opportunity_counts.csv'), index=False); print('\n', OC.to_string(index=False))
    cyc = o.groupby(['und', 'expiry']).agg(split=('split', 'first'), sessions=('date', 'nunique')).reset_index(); print('\ncycles per split:', cyc.groupby('split').size().to_dict(), '| sessions per split:', cyc.groupby('split').sessions.sum().to_dict())
    d = I.assign(date=I.ts.dt.normalize()).groupby(['und', 'date']).agg(o=('open', 'first'), c=('close', 'last')).reset_index(); d['r'] = np.log(d.c / d.o)
    w = d.pivot(index='date', columns='und', values='r'); print('index sessions:', len(w), '| NIFTY-SENSEX correlation of open-to-close returns:', round(float(w.corr().iloc[0, 1]), 3))
