"""P1: when a leg stop fires, which other short contracts are bought back with it?   python3 analysis/p1_grouping.py
Trigger = body (numeric) buy-back whose recovered quote >= 1.45x the cheapest open lot entry of that contract (stop-class), outside s_ events.
Clusters: triggers within 10 s. Candidates: every OTHER contract with an open body short at cluster start.
Label: candidate bought back (numeric buy) within [t0-2s, t0+30s]. Chronological split by date."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import precision_score, recall_score, f1_score
from load import load_tagged
C = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')
d = load_tagged().sort_values(['t', 'row']).reset_index(drop=True)
d['L'] = np.where(d.side == 'Buy', d.px_order / 1.15, d.px_order / 0.85)
op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
pc = op.assign(m=op.ts + pd.Timedelta(minutes=1)).set_index(['und', 'expiry', 'cp', 'strike', 'm']).c.sort_index()
stop_t = d[d.tp == 's_'].groupby(['und', 'expiry']).t.min()
# pass 1: per-lot book (entry px, entry time), cheapest-first closing, record stop-class triggers with a snapshot
book = {}; cur = None; trig = []
for r in d.itertuples():
    ck = (r.und, r.expiry)
    if ck != cur: book = {}; cur = ck
    st = stop_t.get(ck, pd.NaT)
    if pd.notna(st) and r.t >= st: continue
    k = (r.cp, r.strike); n = int(round(r.lots))
    if r.tp == 'num' and r.side == 'Sell':
        book.setdefault(k, []).extend([(r.px_fill, r.t)] * n)
    elif r.tp == 'num' and r.side == 'Buy' and book.get(k):
        lots = sorted(book[k]); ratio = r.L / lots[0][0]
        if ratio >= 1.45:
            trig.append(dict(und=r.und, expiry=r.expiry, date=r.date, dte=r.dte, t=r.t, cp=r.cp, strike=r.strike, ratio=ratio,
                             trig_entry_t=lots[0][1], snap={kk: list(v) for kk, v in book.items() if v}))
        book[k] = lots[n:]
T = pd.DataFrame(trig).sort_values('t')
T['cl'] = (T.groupby(['und', 'expiry']).t.diff().dt.total_seconds().fillna(999) > 10).cumsum()
buys = d[(d.tp == 'num') & (d.side == 'Buy')]
rows = []
for cl, g in T.groupby('cl'):
    r0 = g.iloc[0]; t0 = r0.t; step = 50 if r0.und == 'NIFTY' else 100
    trig_keys = set(zip(g.cp, g.strike)); snap = r0.snap
    w = buys[(buys.und == r0.und) & (buys.expiry == r0.expiry) & (buys.t >= t0 - pd.Timedelta(seconds=2)) & (buys.t <= t0 + pd.Timedelta(seconds=30))]
    closed = w.groupby(['cp', 'strike']).lots.sum()
    m = t0.floor('min')
    for (cp, K), lots in snap.items():
        if (cp, K) in trig_keys: continue
        p = pc.get((r0.und, r0.expiry, cp, K, m), np.nan)
        ents = np.array([x[0] for x in lots]); etimes = [x[1] for x in lots]
        same_batch = any(abs((et - r0.trig_entry_t).total_seconds()) <= 60 for et in etimes)
        rows.append(dict(cl=cl, date=r0.date, und=r0.und, d0=int(r0.dte == 0), same_side=int(cp == r0.cp), same_strike=int(K == r0.strike),
                         dK_steps=(K - r0.strike) / step * (1 if r0.cp == 'CE' else -1), adK=abs(K - r0.strike) / step,
                         ratio_now=p / ents.min() if np.isfinite(p) else np.nan, ratio_now_avg=p / ents.mean() if np.isfinite(p) else np.nan,
                         nlots=len(lots), same_batch=int(same_batch), n_trig=len(g),
                         pnl_per_lot=(ents.mean() - p) if np.isfinite(p) else np.nan, trig_ratio=r0.ratio,
                         label=int(closed.get((cp, K), 0) > 0)))
X = pd.DataFrame(rows)
print('stop-class trigger clusters:', T.cl.nunique(), '| candidate contracts:', len(X), '| positive rate', round(X.label.mean(), 3))
print('\nclosure rate by relation to trigger:')
print(X.groupby(['same_side', 'same_strike']).label.agg(['size', 'mean']).round(3))
print(X.groupby(['same_side', 'same_batch']).label.agg(['size', 'mean']).round(3))
feats = ['same_side', 'same_strike', 'dK_steps', 'adK', 'ratio_now', 'ratio_now_avg', 'nlots', 'same_batch', 'n_trig', 'pnl_per_lot', 'trig_ratio', 'd0']
dates = sorted(X.date.unique()); cut = dates[int(len(dates) * 0.6)]
tr, te = X[X.date < cut], X[X.date >= cut]
m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=20, verbose=-1).fit(tr[feats], tr.label)
p = m.predict_proba(te[feats])[:, 1]
best = max(np.arange(0.1, 0.9, 0.05), key=lambda th: f1_score(tr.label, m.predict_proba(tr[feats])[:, 1] >= th))
yh = p >= best
print(f'\nLightGBM test: precision {precision_score(te.label, yh):.3f} recall {recall_score(te.label, yh):.3f} F1 {f1_score(te.label, yh):.3f} (thr {best:.2f}, test n={len(te)})')
imp = pd.Series(m.booster_.feature_importance('gain'), index=feats); print('importance', (imp / imp.sum()).sort_values(ascending=False).round(3).to_dict())
for depth in [2, 3]:
    t = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=30).fit(tr[feats].fillna(-9), tr.label)
    yh = t.predict(te[feats].fillna(-9))
    print(f'\ntree depth {depth}: test precision {precision_score(te.label, yh):.3f} recall {recall_score(te.label, yh):.3f} F1 {f1_score(te.label, yh):.3f}')
    print(export_text(t, feature_names=feats, decimals=3))
X.to_pickle(os.path.join(C, 'p1_candidates.pkl')); T.drop(columns=['snap']).to_pickle(os.path.join(C, 'p1_triggers.pkl'))
