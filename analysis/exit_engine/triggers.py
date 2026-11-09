"""EX3 trigger tests on the contract-minute exit panel.   python3 analysis/exit_engine/triggers.py
T1 static stop level (hazard vs minute-high/cheapest-entry; by entry-premium band, % vs points)
T2 dynamic stop level (threshold by TTE / IV-change / ATR move / day; bootstrap over cycles)
T3 trailing (hazard vs bounce off running low and vs drawdown from contract peak P&L, holding premium level fixed)
T4 feature-family ablation per exit category (LightGBM, 3 chronological folds, AUC gain over timing+inventory baseline)"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
from load import load_tagged
if len(sys.argv) > 1 and sys.argv[1] == 'merge':
    import glob
    OUTD = os.path.join(HERE, 'results'); ncat = 9
    parts = sorted(glob.glob(os.path.join(OUTD, 't4_parts', '*.csv')), key=lambda f: int(os.path.basename(f).split('.')[0]))
    G = pd.concat([pd.read_csv(f) for f in parts], ignore_index=True); G.to_csv(os.path.join(OUTD, 't4_family_gains.csv'), index=False)
    miss = [i for i in range(ncat) if not os.path.exists(os.path.join(OUTD, 't4_parts', f'{i}.csv'))]
    txt = open(os.path.join(OUTD, 'triggers_t123_report.txt')).read() + '\n\n=== T4 feature families: OOS AUC gain over timing+inventory baseline (3 chronological folds) ===\n' + G.to_string(index=False)
    txt += '\n\nT4 categories with no part file: ' + (', '.join(map(str, miss)) or 'none') + ' (categories with < 40 positives are skipped by design)\n'
    open(os.path.join(OUTD, 'triggers_report.txt'), 'w').write(txt); print(txt); sys.exit(0)
C = os.path.join(os.path.dirname(HERE), '_cache'); OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)
P = pd.read_pickle(os.path.join(C, 'exit_panel.pkl'))
P['mins'] = (P.m.dt.hour * 60 + P.m.dt.minute) - 555
ph = ((P.m - P.m.dt.normalize() - pd.Timedelta('09:15:00')).dt.total_seconds()) % 900
P['clockB'] = ((ph >= 13 * 60) | (ph < 60)).astype(int); P['clockA'] = ((ph >= 60) & (ph < 180)).astype(int)
P['is_d1'] = P.is_d1.astype(int); P['ux'] = (P.und == 'SENSEX').astype(int); P['ce'] = (P.cp == 'CE').astype(int)
P['pts_above'] = P.hi - P.e_cheap
# time since previous sale / buy-back (contract and side), from fills, causal
d = load_tagged(); d['m'] = d.t.dt.floor('min')
sales = d[(d.tp == 'num') & (d.side == 'Sell')][['und', 'expiry', 'cp', 'strike', 'm']].drop_duplicates()
buys = d[(d.side == 'Buy') & d.tp.isin(['num', 's_'])][['und', 'expiry', 'cp', 'strike', 'm']].drop_duplicates()
def since(ev, by):
    ev = ev.sort_values('m').rename(columns={'m': 'm_ev'}); x = P[['und', 'expiry', 'cp', 'strike', 'm']].reset_index().sort_values('m')
    x['m_q'] = x.m - pd.Timedelta(minutes=1)
    j = pd.merge_asof(x, ev[by + ['m_ev']].drop_duplicates(), left_on='m_q', right_on='m_ev', by=by, direction='backward')
    return ((j.m - j.m_ev).dt.total_seconds() / 60).set_axis(j['index']).sort_index().values
P['since_sale_contract'] = since(sales, ['und', 'expiry', 'cp', 'strike']); P['since_sale_side'] = since(sales, ['und', 'expiry', 'cp'])
P['since_bb_contract'] = since(buys, ['und', 'expiry', 'cp', 'strike']); P['since_bb_side'] = since(buys, ['und', 'expiry', 'cp'])
STOP = '1 individual lot stop-loss'
pd.set_option('display.width', 230); lines = []
PART = sys.argv[1] if len(sys.argv) > 1 else 'all'; PART_ARG = sys.argv[2] if len(sys.argv) > 2 else None   # all | t123 | t4 <category index> | merge
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); lines.append(s)

if PART in ('all', 't123'):
    # ---------- T1 static threshold
    say('=== T1 static stop level: P(lot-stop exit this minute | minute-high / cheapest entry in bin) ===')
    y = (P.label == STOP).astype(int)
    bins = [0, 1.0, 1.2, 1.3, 1.4, 1.45, 1.5, 1.55, 1.6, 1.7, 1.8, 2.0, 2.5, 100]
    say(P.assign(y=y).groupby(pd.cut(P.rh_cheap, bins), observed=True).y.agg(['size', 'mean']).round(4).T.to_string())
    say('\nby entry-premium band (hazard at rh_cheap bins):')
    for lo, hi in [(0, 10), (10, 25), (25, 50), (50, 100), (100, 10000)]:
        g = P[(P.e_cheap > lo) & (P.e_cheap <= hi)].assign(y=y)
        h = g.groupby(pd.cut(g.rh_cheap, [0, 1.3, 1.45, 1.55, 1.7, 2.0, 3.0, 100]), observed=True).y.mean().round(3).to_dict()
        say(f'  entry Rs {lo}-{hi}: {h}')
    say('\npoints test for cheap entries (<= Rs 25): hazard by points above entry (minute high - entry):')
    g = P[P.e_cheap <= 25].assign(y=y)
    say(g.groupby(pd.cut(g.pts_above, [-100, 0, 2, 4, 6, 8, 10, 15, 20, 30, 1000]), observed=True).y.agg(['size', 'mean']).round(3).T.to_string())

    # ---------- T2 dynamic threshold
    def thr(g):
        """smallest rh level (grid) where minute hazard >= 0.25 (robust midpoint proxy)."""
        for lv in np.arange(1.2, 2.6, 0.05):
            x = g[(g.rh_cheap >= lv) & (g.rh_cheap < lv + 0.05)]
            if len(x) >= 15 and (x.label == STOP).mean() >= 0.25: return round(lv, 2)
        return np.nan
    say('\n=== T2 dynamic stop level: hazard-implied threshold by condition (entries > Rs 25), with cycle bootstrap 90% band ===')
    Q = P[P.e_cheap > 25]
    cyc = Q[['und', 'expiry']].drop_duplicates().values.tolist(); rng = np.random.default_rng(0)
    for name, col, cuts in [('TTE (min)', 'tte_min', [0, 120, 375, 1000, 5000]), ('day', 'is_d1', [-1, 0.5, 2]), ('IV change since entry', 'iv_chg', [-5, -0.03, 0, 0.03, 5]),
                            ('spot move since entry (ATR, adverse+)', 'spot_move_atr', [-100, 0, 2, 5, 100]), ('minutes since entry', 'min_since_cheap', [0, 30, 120, 400, 5000])]:
        res = {}
        for b, g in Q.groupby(pd.cut(Q[col], cuts), observed=True):
            t0 = thr(g); bs = []
            for _ in range(100):
                pick = [tuple(cyc[i]) for i in rng.integers(len(cyc), size=len(cyc))]
                gg = pd.concat([g[(g.und == u) & (g.expiry == e)] for u, e in pick]); bs.append(thr(gg))
            bs = np.array([x for x in bs if np.isfinite(x)])
            res[str(b)] = (t0, (round(np.percentile(bs, 5), 2), round(np.percentile(bs, 95), 2)) if len(bs) else None, len(g))
        say(f'  {name}: ' + '; '.join(f'{k}: {v[0]} [{v[1]}] n={v[2]}' for k, v in res.items()))

    # ---------- T3 trailing
    say('\n=== T3 trailing: exits while IN PROFIT (r_cheap < 1); non-stop, non-salvage, non-flatten, non-cycle categories ===')
    TR = ['2 same-contract partial buy-back', '3 side-level reduction', '4 basket-level reduction', '6 clock-based exit (clock B, no replacement)',
          '8 clock-B rebalance', '8b grid rebalance (A/:00 clock)', '11 unexplained']
    W = P[(P.r_cheap < 1) & (P.label.isin(TR + ['none']))].copy(); W['y'] = W.label.isin(TR).astype(int)
    for rb in [(0, 0.3), (0.3, 0.6), (0.6, 0.9)]:
        g = W[(W.r_cheap >= rb[0]) & (W.r_cheap < rb[1])]
        h = g.groupby(pd.cut(g.bounce, [0, 1.05, 1.15, 1.3, 1.5, 2.0, 3.0, 100]), observed=True).y.agg(['size', 'mean']).round(4)
        say(f'  premium {rb} of entry: hazard by bounce off running low  ' + str(h['mean'].to_dict()) + '  n=' + str(h['size'].to_dict()))
    say('  hazard by drawdown from contract peak unrealised P&L (Rs):')
    say('   ' + str(W.groupby(pd.cut(W.dd_contract, [-1e7, -20000, -10000, -5000, -2000, -500, 0.1]), observed=True).y.agg(['size', 'mean']).round(4).to_dict('index')))

    open(os.path.join(OUT, 'triggers_t123_report.txt'), 'w').write('\n'.join(lines))

# ---------- T4 family ablation
say('\n=== T4 feature families: OOS AUC gain over timing+inventory baseline (3 chronological folds) ===')
FAM = {'premium_ratio': ['r_cheap', 'r_avg', 'rh_cheap', 'rmax_cheap'], 'pnl': ['upnl_contract', 'upnl_side', 'upnl_strike', 'cycle_mtm'],
       'drawdown/trailing': ['dd_contract', 'cycle_dd', 'bounce'], 'spot_atr': ['spot_move_atr', 'mv5_atr'], 'iv': ['iv_chg'], 'greeks': ['absdelta_chg'],
       'since_trades': ['since_sale_contract', 'since_sale_side', 'since_bb_contract', 'since_bb_side']}
BASE = ['mins', 'tte_min', 'is_d1', 'min_since_cheap', 'n_lots', 'clockA', 'clockB', 'ux', 'ce']
days = sorted(P.m.dt.normalize().unique()); cuts = [days[int(len(days) * f)] for f in (0.5, 0.67, 0.84)] + [days[-1] + pd.Timedelta(days=1)]
def oos(cols, y, R):
    ps, ys = [], []
    dd = R.m.dt.normalize()
    for i in range(3):
        tr = dd < cuts[i]; te = (dd >= cuts[i]) & (dd < cuts[i + 1])
        if y[tr].sum() < 20 or y[te].sum() < 5: continue
        m = lgb.LGBMClassifier(n_estimators=250, learning_rate=0.05, num_leaves=15, min_child_samples=50, subsample=0.8, subsample_freq=1, verbose=-1)
        m.fit(R.loc[tr, cols], y[tr]); ps.append(m.predict_proba(R.loc[te, cols])[:, 1]); ys.append(y[te].values)
    return roc_auc_score(np.concatenate(ys), np.concatenate(ps)) if ps else np.nan
rows = []
CATS = [STOP, '2 same-contract partial buy-back', '3 side-level reduction', '4 basket-level reduction', '8 clock-B rebalance',
        '8b grid rebalance (A/:00 clock)', '6 clock-based exit (clock B, no replacement)', '7 expiry-day salvage', '11 unexplained']
SEL = [int(PART_ARG)] if PART == 't4' else (list(range(len(CATS))) if PART == 'all' else [])
for ci in SEL:
    cat = CATS[ci]
    if True:
        R = P[P.label.isin([cat, 'none'])]
        R = pd.concat([R[R.label == cat], R[R.label == 'none'].sample(min(150000, (R.label == 'none').sum()), random_state=0)]).sort_values('m')
        y = (R.label == cat).astype(int)
        if y.sum() < 40: continue
        b = oos(BASE, y, R); row = dict(category=cat, positives=int(y.sum()), base_auc=round(b, 3))
        for f, cols in FAM.items(): row[f] = round(oos(BASE + cols, y, R) - b, 3)
        row['all'] = round(oos(BASE + sum(FAM.values(), []), y, R) - b, 3)
        rows.append(row); say(row)
if PART == 't4':
    os.makedirs(os.path.join(OUT, 't4_parts'), exist_ok=True)
    if rows: pd.DataFrame(rows).to_csv(os.path.join(OUT, 't4_parts', f'{PART_ARG}.csv'), index=False)
if PART == 'all':
    pd.DataFrame(rows).to_csv(os.path.join(OUT, 't4_family_gains.csv'), index=False)
    open(os.path.join(OUT, 'triggers_report.txt'), 'w').write('\n'.join(lines))
