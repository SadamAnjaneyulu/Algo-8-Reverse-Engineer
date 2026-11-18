"""P3: when do extra (off-grid) body sells fire?  Minute x side classification.   python3 analysis/p3_extra_entries.py
Rows: every (session minute 09:17-15:08 outside grid windows [slot+0..+2], side). Label: body sell of that side in the minute.
All features causal (bars up to m-1, fills before m). Chronological split 60/40 by date. Stop-module periods excluded."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import precision_recall_curve, average_precision_score
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged().sort_values(['t', 'row'])
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
bb = pd.read_pickle(os.path.join(C, 'buyback_events.pkl')); bb = bb[bb.tp == 'num'].assign(r=lambda z: z.L / z.min_e)
stop_t = d[d.tp == 's_'].groupby('date').t.min()
d['m'] = d.t.dt.floor('min')
rows = []
for date, g in d.groupby('date'):
    und = g.und.iloc[0]; exp = g.expiry.iloc[0]; step = 50 if und == 'NIFTY' else 100; lot = g.lot.iloc[0]
    cyc = d[(d.und == und) & (d.expiry == exp)]
    s = ix[(ix.und == und) & (ix.ts.dt.normalize() == date)].set_index('ts').close
    if len(s) < 100: continue
    grid = pd.date_range(date + pd.Timedelta('09:17:00'), date + pd.Timedelta('15:08:00'), freq='min')
    if date in stop_t.index: grid = grid[grid < stop_t[date].floor('min')]
    S1 = s.shift(1).reindex(grid)                      # close of bar m-1, known at m
    mv = {L: (s.shift(1) - s.shift(1 + L)).reindex(grid) / S1 * 1e4 for L in [1, 3, 5, 10, 15]}
    rng15 = (s.rolling(15).max() - s.rolling(15).min()).shift(1).reindex(grid) / S1 * 1e4
    # positions at start of minute (all fills before m, incl. carried)
    cyc = cyc.assign(key=cyc.cp + '|' + cyc.strike.astype(int).astype(str))
    P = cyc.pivot_table(index='m', columns='key', values='sl', aggfunc='sum').sort_index().cumsum()
    P = P.reindex(P.index.union(grid)).ffill().fillna(0).shift(1).reindex(grid).fillna(0)
    sellsb = g[(g.tp == 'num') & (g.side == 'Sell') & (g.px_fill >= 10)]
    mins = (grid.hour * 60 + grid.minute) - (9 * 60 + 16)
    ongrid = (mins % 15) <= 2
    for cp in ['CE', 'PE']:
        sg = 1 if cp == 'CE' else -1
        cols = [c for c in P.columns if c.startswith(cp)]; ocols = [c for c in P.columns if not c.startswith(cp)]
        Ks = np.array([float(c.split('|')[1]) for c in cols])
        shortlots = (-P[cols].clip(upper=0)).sum(axis=1); oshort = (-P[ocols].clip(upper=0)).sum(axis=1)
        w = -P[cols].clip(upper=0).values
        avgK = np.where(w.sum(1) > 0, (w * Ks).sum(1) / np.maximum(w.sum(1), 1e-9), np.nan)
        ss = sellsb[sellsb.cp == cp].groupby('m').agg(K=('strike', 'last'), px=('px_fill', 'mean'))
        lastK = ss.K.reindex(ss.index.union(grid)).ffill().shift(1).reindex(grid)
        lastpx = ss.px.reindex(ss.index.union(grid)).ffill().shift(1).reindex(grid)
        lastT = pd.Series(ss.index, index=ss.index).reindex(ss.index.union(grid)).ffill().shift(1).reindex(grid)
        anyss = sellsb.groupby('m').size()
        lastAny = pd.Series(anyss.index, index=anyss.index).reindex(anyss.index.union(grid)).ffill().shift(1).reindex(grid)
        stp = bb[(bb.date == date) & (bb.r >= 1.45)]
        def last_stop(side):
            x = stp[stp.cp == side].t.dt.floor('min')
            ser = pd.Series(x.values, index=x.values)
            return ser[~ser.index.duplicated()].reindex(ser.index.union(grid).drop_duplicates()).ffill().shift(1).reindex(grid)
        lsS = last_stop(cp); lsO = last_stop('PE' if cp == 'CE' else 'CE')
        # ATM premium (prev-minute close) at nearest strike, vs premium at last same-side sale
        K0 = (S1 / step).round() * step
        oc = op[(op.und == und) & (op.expiry == exp) & (op.cp == cp)].assign(m=lambda z: z.ts + pd.Timedelta(minutes=1)).set_index(['m', 'strike']).c
        patm = np.array([oc.get((m, k), np.nan) for m, k in zip(grid, K0)])
        label = sellsb[sellsb.cp == cp].groupby('m').size().reindex(grid).fillna(0).values > 0
        df = pd.DataFrame(dict(date=date, und=und, cp=cp, m=grid, label=label.astype(int), ongrid=ongrid,
                               mins=mins, d0=int((exp - date).days == 0), ux=int(und == 'SENSEX'), ce=int(cp == 'CE'),
                               mv1=mv[1].values * sg, mv3=mv[3].values * sg, mv5=mv[5].values * sg, mv10=mv[10].values * sg, mv15=mv[15].values * sg,
                               rng15=rng15.values,
                               dist_lastK=((S1 - lastK) / step).values * sg, dist_avgK=((S1.values - avgK) / step) * sg,
                               since_sale_same=((pd.Series(grid, index=grid) - lastT).dt.total_seconds() / 60).values, since_sale_any=((pd.Series(grid, index=grid) - lastAny).dt.total_seconds() / 60).values,
                               since_stop_same=((pd.Series(grid, index=grid) - lsS).dt.total_seconds() / 60).values, since_stop_other=((pd.Series(grid, index=grid) - lsO).dt.total_seconds() / 60).values,
                               shortlots=shortlots.values, imb=(shortlots - oshort).values,
                               prem_chg=(patm / lastpx.values - 1)))
        rows.append(df)
X = pd.concat(rows, ignore_index=True)
X = X[~X.ongrid].copy()
for c in ['since_sale_same', 'since_sale_any', 'since_stop_same', 'since_stop_other']: X[c] = X[c].fillna(999)
feats = ['mins', 'd0', 'ux', 'ce', 'mv1', 'mv3', 'mv5', 'mv10', 'mv15', 'rng15', 'dist_lastK', 'dist_avgK', 'since_sale_same', 'since_sale_any',
         'since_stop_same', 'since_stop_other', 'shortlots', 'imb', 'prem_chg']
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
tr, te = X[X.date < cut], X[X.date >= cut]
print('rows', len(X), 'positives', int(X.label.sum()), 'base rate', round(X.label.mean(), 4))
m = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1).fit(tr[feats], tr.label)
p = m.predict_proba(te[feats])[:, 1]
pr, rc, th = precision_recall_curve(te.label, p); f1 = 2 * pr * rc / np.maximum(pr + rc, 1e-9); i = np.nanargmax(f1)
print(f'LightGBM test: AP {average_precision_score(te.label, p):.3f} | best F1 {f1[i]:.3f} (precision {pr[i]:.3f}, recall {rc[i]:.3f}) | base rate {te.label.mean():.4f}')
for dd in [0, 1]:
    q = te.d0 == dd; print(f'   {"D0" if dd else "D-1"}: AP {average_precision_score(te.label[q], p[q]):.3f}')
imp = pd.Series(m.booster_.feature_importance('gain'), index=feats); print('importance', (imp / imp.sum()).sort_values(ascending=False).round(3).to_dict())
t = DecisionTreeClassifier(max_depth=4, min_samples_leaf=200, class_weight='balanced').fit(tr[feats], tr.label)
pt = t.predict_proba(te[feats])[:, 1]; print('tree depth4 test AP', round(average_precision_score(te.label, pt), 3))
print(export_text(t, feature_names=feats, decimals=2))
X.to_pickle(os.path.join(C, 'p3_minutes.pkl'))
