"""Market regimes. DECISION-TIME features use only information available at entry (09:16 of D-1): Yahoo daily bars up to the trading day BEFORE D-1, plus the 09:15 spot bar and the traded entry premium. 
No implied-vol surface is available: 'straddle premium % of spot' is an observed traded price, not an IV. OUTCOME features (D-1/D0 moves) are ex-post and are used only to describe what happened. Tercile cut-offs come from IS only, per index."""
import json, math
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy import stats
from common import *
Y = {u: pd.read_csv(f'{BT}/../data_validation/reference/yahoo_daily_{s}.csv').assign(date=lambda x: pd.to_datetime(x.date_ist)).set_index('date').sort_index() for u, s in (('NIFTY', 'NSEI'), ('SENSEX', 'BSESN'))}
L = pd.read_csv(f'{RES}/leg_attribution_cycles.csv'); L['expiry'] = pd.to_datetime(L.expiry); d = cycles('HOLD', 'HOLD_SETTLE'); d['expiry'] = pd.to_datetime(d.expiry); d['d1'] = pd.to_datetime(d.d1); d['d0'] = pd.to_datetime(d.d0)
d = d.merge(L[['und', 'expiry', 'SCE_entry_ref', 'SPE_entry_ref', 'W', 'move_pts']].assign(expiry=lambda x: pd.to_datetime(x.expiry)), on=['und', 'expiry'])
f = []
for r in d.itertuples():
    y = Y[r.und]; prev = y[y.index < r.d1]; p1 = prev.iloc[-1]; lr = np.log(prev.close).diff().dropna()
    y0 = y.loc[r.d0] if r.d0 in y.index else None; y1 = y.loc[r.d1] if r.d1 in y.index else None
    prem = r.SCE_entry_ref + r.SPE_entry_ref
    f.append(dict(und=r.und, expiry=r.expiry, split=r.split, subset=r.subset, net=r.net, gross=r.gross,
                  # decision-time
                  gap_open_d1_pct=100 * (r.spot_0915 / p1.close - 1), prev_range_pct=100 * (p1.high - p1.low) / p1.close, rv5_pct=100 * lr.iloc[-5:].std(ddof=1), rv20_pct=100 * lr.iloc[-20:].std(ddof=1), ret5_pct=100 * (p1.close / prev.close.iloc[-6] - 1), ret20_pct=100 * (p1.close / prev.close.iloc[-21] - 1),
                  prem_pct_spot=100 * prem / r.K, prem_pts=prem,
                  # outcome (ex-post)
                  abs_move_pct=100 * abs(r.official_close - r.K) / r.K, signed_move_pct=100 * (r.official_close - r.K) / r.K, d1_range_pct=100 * ((y1.high - y1.low) / y1.close) if y1 is not None else np.nan, d0_range_pct=100 * ((y0.high - y0.low) / y0.close) if y0 is not None else np.nan,
                  overnight_gap_pct=100 * (y0.open / y1.close - 1) if (y0 is not None and y1 is not None) else np.nan, d0_open_to_close_pct=100 * (y0.close / y0.open - 1) if y0 is not None else np.nan,
                  premium_over_absmove=prem / abs(r.official_close - r.K) if abs(r.official_close - r.K) > 0 else np.nan, move_pts=abs(r.official_close - r.K)))
F = pd.DataFrame(f); F.to_csv(f'{RES}/regime_features_cycles.csv', index=False)
dec = ['gap_open_d1_pct', 'prev_range_pct', 'rv5_pct', 'rv20_pct', 'ret5_pct', 'ret20_pct', 'prem_pct_spot']
F['abs_gap'] = F.gap_open_d1_pct.abs(); F['abs_ret5'] = F.ret5_pct.abs(); F['abs_ret20'] = F.ret20_pct.abs(); dec += ['abs_gap', 'abs_ret5', 'abs_ret20']
rows = []
for u in ('NIFTY', 'SENSEX'):
    fu = F[F.und == u]; fi = fu[fu.split == 'IS']
    for ft in dec:
        q = fi[ft].quantile([1 / 3, 2 / 3]).values
        lab = lambda v: 'LOW' if v <= q[0] else ('MID' if v <= q[1] else 'HIGH')
        g = fu.assign(t=fu[ft].map(lab))
        for p, m in (('IS', g.split == 'IS'), ('OOS', g.split == 'OOS'), ('OOS_clean', g.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])), ('OOS_exposed', g.subset == 'OOS_EXPOSED')):
            for t in ('LOW', 'MID', 'HIGH'):
                x = g[m & (g.t == t)]
                rows.append(dict(und=u, feature=ft, cut_lo=q[0], cut_hi=q[1], part=p, tercile=t, cycles=len(x), net=x.net.sum(), mean=x.net.mean() if len(x) else np.nan, win_rate=(x.net > 0).mean() if len(x) else np.nan))
R = pd.DataFrame(rows); R.to_csv(f'{RES}/regime_terciles.csv', index=False)
# association tests (Spearman) between decision-time features and cycle net, IS vs OOS; and between features and |move|
sp = []
for u in ('NIFTY', 'SENSEX'):
    for p, m in (('IS', F.split == 'IS'), ('OOS', F.split == 'OOS')):
        x = F[(F.und == u) & m]
        for ft in dec: 
            r1, p1 = stats.spearmanr(x[ft], x.net, nan_policy='omit'); r2, p2 = stats.spearmanr(x[ft], x.abs_move_pct, nan_policy='omit'); sp.append(dict(und=u, part=p, feature=ft, n=len(x), rho_net=r1, p_net=p1, rho_absmove=r2, p_absmove=p2))
S = pd.DataFrame(sp); S.to_csv(f'{RES}/regime_spearman.csv', index=False)
# ex-post descriptive by part
ds = F.groupby(['und', F.subset.replace({'OOS_CLEAN_BEFORE': 'OOS_CLEAN', 'OOS_CLEAN_AFTER': 'OOS_CLEAN'})]).agg(n=('net', 'size'), prem_pct=('prem_pct_spot', 'mean'), abs_move_pct=('abs_move_pct', 'mean'), d0_range_pct=('d0_range_pct', 'mean'), overnight_abs_gap=('overnight_gap_pct', lambda v: v.abs().mean()), rv5=('rv5_pct', 'mean'), rv20=('rv20_pct', 'mean'), prem_over_move=('premium_over_absmove', 'median'), p_move_gt_prem=('premium_over_absmove', lambda v: (v < 1).mean()), net_mean=('net', 'mean')).reset_index(); ds.to_csv(f'{RES}/regime_descriptive.csv', index=False)
# volatility clustering: autocorrelation of |move| series per index and corr(prior rv5, |move|)
vc = []
for u in ('NIFTY', 'SENSEX'):
    x = F[F.und == u].sort_values('expiry'); a = x.abs_move_pct.values; vc.append(dict(und=u, ac1_absmove=float(np.corrcoef(a[:-1], a[1:])[0, 1]), corr_rv5_absmove=float(x[['rv5_pct', 'abs_move_pct']].corr().iloc[0, 1]), corr_prem_absmove=float(x[['prem_pct_spot', 'abs_move_pct']].corr().iloc[0, 1]), corr_prem_net=float(x[['prem_pct_spot', 'net']].corr().iloc[0, 1])))
pd.DataFrame(vc).to_csv(f'{RES}/regime_volclustering.csv', index=False)
# result-level split: P&L when |move| bigger vs premium (the structural identity)
F['edge_pts'] = F.prem_pts - F.move_pts; F['sign'] = np.sign(F.edge_pts)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(ds.round(3).to_string(index=False)); print(pd.DataFrame(vc).round(3)); 
print(R[(R.part.isin(['IS', 'OOS', 'OOS_clean'])) & (R.feature.isin(['rv5_pct', 'prem_pct_spot', 'abs_gap', 'abs_ret20']))].pivot_table(index=['und', 'feature', 'tercile'], columns='part', values=['mean', 'cycles']).round(0).to_string())
print(S[S.feature.isin(['rv5_pct', 'prem_pct_spot', 'abs_gap', 'abs_ret20', 'ret20_pct'])].round(3).to_string(index=False))
# chart: net by regime tercile of rv5 and prem, IS vs OOS
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for a, ft in zip(ax, ('rv5_pct', 'prem_pct_spot')):
    q = R[(R.feature == ft) & (R.part.isin(['IS', 'OOS']))].groupby(['part', 'tercile']).net.sum().unstack().reindex(columns=['LOW', 'MID', 'HIGH']) / 1e3; q.plot.bar(ax=a); a.set_title(f'Net P&L (₹k) by IS-tercile of {ft} (NIFTY+SENSEX)'); a.axhline(0, c='k', lw=.6); a.set_xlabel('')
plt.tight_layout(); plt.savefig(f'{FIG}/regime_terciles.png', dpi=130)
