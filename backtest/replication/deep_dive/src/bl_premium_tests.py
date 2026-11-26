"""Question A of reports/PREMIUM_AND_ARCHITECTURE_PLAN.md: why is near-expiry premium rich? A1 jump vs continuous variance, A2 calendar gap,
A3 demand (SEBI 20 Nov 2024 natural experiment; pre-determined D-1 first-hour ATM volume), A4 implied-vol terciles.
Inputs: outputs/bt3 caches, outputs/thesis/thesis_t1.csv, bt3_results/alpha_iv_cycles.csv, raw option CSVs (volume). Output outputs/premium/*.csv, premium_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from multiprocessing import Pool
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); BT3 = f'{OUT}/bt3'; PR = f'{OUT}/premium'; os.makedirs(PR, exist_ok=True); B = 2000; SEBI = '2024-11-20'
S_ = None
def init():
    global S_; import data as D; S_ = D.Src()
def bv(r): r = np.abs(r); return float(np.pi / 2 * np.sum(r[1:] * r[:-1]))
def one(a):
    und, expiry, d1, d0 = a; c = pd.read_pickle(f'{BT3}/{und}_{expiry}.pkl.gz'); s1, s0, o1 = c['spot1'], c['spot0'], c['opt1']
    O1, C1 = s1.open.values.astype(float), s1.close.values.astype(float); O0, C0 = s0.open.values.astype(float), s0.close.values.astype(float)
    r1 = np.concatenate([[np.log(C1[1] / O1[1])], np.diff(np.log(C1[1:375]))]); r0 = np.concatenate([[np.log(C0[1] / O0[1])], np.diff(np.log(C0[1:359])), [np.log(O0[359] / C0[358])]])
    row = dict(und=und, expiry=expiry, d1=d1, d0=d0, cal_gap=(pd.Timestamp(d0) - pd.Timestamp(d1)).days, rv_d1=float(np.sum(r1 ** 2)), bv_d1=bv(r1), rv_d0=float(np.sum(r0 ** 2)), bv_d0=bv(r0), gap2=float(np.log(O0[1] / C1[374]) ** 2))
    K = o1['K'][int(np.argmin(np.abs(o1['K'] - O1[0])))]
    try:
        f = S_.csv(f'normalized/{und.lower()}/options/exp{expiry}_{d1}.csv'); hh = f.datetime.str.slice(11, 16); first = (hh >= '09:15') & (hh < '10:15')
        row['vol_d1_first_hour_atm'] = float(f[first & (f.strike == K)].volume.sum()); row['vol_d1_first_hour_all'] = float(f[first].volume.sum())
    except Exception as e: row['vol_d1_first_hour_atm'] = np.nan; row['vol_d1_first_hour_all'] = np.nan
    return row
def wkboot(df, stat, seed=20261124):
    rng = np.random.default_rng(seed); w = df.wk.unique(); g = {k: v for k, v in df.groupby('wk')}; pt = stat(df)
    bs = np.array([stat(pd.concat([g[k] for k in rng.choice(w, len(w))])) for _ in range(B)]); bs = bs[np.isfinite(bs)]; return pt, np.quantile(bs, .025), np.quantile(bs, .975)
if __name__ == '__main__':
    T0 = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T0 = T0[T0.split3.isin(['IS', 'OOS', 'LIVE_FITTED']) & T0.ok]
    with Pool(4, initializer=init) as p: res = p.map(one, [(r.und, r.expiry, r.d1, r.d0) for r in T0.itertuples()], chunksize=4)
    C = pd.DataFrame(res).merge(T0[['und', 'expiry', 'split3']].rename(columns={'split3': 'split'}), on=['und', 'expiry'])
    T1 = pd.read_csv(f'{OUT}/thesis/thesis_t1.csv'); piv = T1.pivot_table(index=['und', 'expiry'], columns='segment', values=['iv_used', 'pnl_pct']); piv.columns = [f'{a}|{b}' for a, b in piv.columns]; C = C.merge(piv.reset_index(), on=['und', 'expiry'])
    C = C.merge(pd.read_csv(f'{OUT}/bt3_results/alpha_iv_cycles.csv')[['und', 'expiry', 'iv_D1_open']], on=['und', 'expiry'], how='left')
    C['wk'] = pd.to_datetime(C.expiry).dt.strftime('%G-%V'); C['post_sebi'] = C.d0 >= SEBI; C.to_csv(f'{PR}/premium_cycles.csv', index=False)
    seg = {'D-1 day': ('rv_d1', 'bv_d1'), 'overnight': ('gap2', None), 'D0 day': ('rv_d0', 'bv_d0')}; rows = []
    def add(**k): rows.append(k)
    # ---- A1 jumps vs continuous
    for s, (rv, bvc) in seg.items():
        d = C[C[f'iv_used|{s}'] > 0].copy(); iv = f'iv_used|{s}'; d['ratio'] = d[rv] / d[iv]
        pt, lo, hi = wkboot(d, lambda x: x[rv].sum() / x[iv].sum()); add(q='A1', segment=s, stat='realised / implied (all variance)', value=pt, lo=lo, hi=hi)
        if bvc:
            pt, lo, hi = wkboot(d, lambda x: x[bvc].clip(upper=x[rv]).sum() / x[iv].sum()); add(q='A1', segment=s, stat='continuous (bipower) / implied', value=pt, lo=lo, hi=hi)
            pt, lo, hi = wkboot(d, lambda x: (x[rv] - x[bvc]).clip(lower=0).sum() / x[rv].sum()); add(q='A1', segment=s, stat='jump share of realised variance', value=pt, lo=lo, hi=hi)
        add(q='A1', segment=s, stat='median per-cycle ratio', value=d.ratio.median(), lo=np.nan, hi=np.nan); add(q='A1', segment=s, stat='share of cycles with ratio > 1', value=(d.ratio > 1).mean(), lo=np.nan, hi=np.nan)
        top = d[rv].sort_values(ascending=False); add(q='A1', segment=s, stat='share of realised variance from the top 10% of cycles', value=top.head(int(np.ceil(.1 * len(top)))).sum() / top.sum(), lo=np.nan, hi=np.nan)
        p = C[f'pnl_pct|{s}'].dropna(); add(q='A1', segment=s, stat='skewness of short-straddle P&L (% of premium)', value=float(p.skew()), lo=np.nan, hi=np.nan)
        add(q='A1', segment=s, stat='short-straddle: worst 5% of cycles as multiple of the mean gain of the other 95%', value=float(-p[p <= p.quantile(.05)].sum() / p[p > p.quantile(.05)].mean()), lo=np.nan, hi=np.nan)
        for u in ('NIFTY', 'SENSEX'):
            du = d[d.und == u]; add(q='A1', segment=s, stat=f'realised / implied, {u}', value=du[rv].sum() / du[iv].sum(), lo=np.nan, hi=np.nan)
            if bvc: add(q='A1', segment=s, stat=f'continuous / implied, {u}', value=du[bvc].clip(upper=du[rv]).sum() / du[iv].sum(), lo=np.nan, hi=np.nan)
    # ---- A2 calendar gap (overnight)
    d = C[C['iv_used|overnight'] > 0].copy(); d['multi'] = d.cal_gap > 1
    for m, g in d.groupby('multi'):
        add(q='A2', segment='overnight', stat=f'{"2-4 calendar days" if m else "1 calendar day"}: cycles', value=len(g), lo=np.nan, hi=np.nan)
        add(q='A2', segment='overnight', stat=f'{"2-4 calendar days" if m else "1 calendar day"}: implied variance consumed (bp^2)', value=1e8 * g['iv_used|overnight'].mean(), lo=np.nan, hi=np.nan)
        add(q='A2', segment='overnight', stat=f'{"2-4 calendar days" if m else "1 calendar day"}: realised gap variance (bp^2)', value=1e8 * g.gap2.mean(), lo=np.nan, hi=np.nan)
        pt, lo, hi = wkboot(g, lambda x: x.gap2.sum() / x['iv_used|overnight'].sum()) if len(g) > 5 else (g.gap2.sum() / g['iv_used|overnight'].sum(), np.nan, np.nan)
        add(q='A2', segment='overnight', stat=f'{"2-4 calendar days" if m else "1 calendar day"}: realised / implied', value=pt, lo=lo, hi=hi)
    # ---- A3 (i) SEBI natural experiment
    for s, (rv, _) in seg.items():
        d = C[C[f'iv_used|{s}'] > 0].copy(); iv = f'iv_used|{s}'
        for post, g in d.groupby('post_sebi'): add(q='A3', segment=s, stat=f'realised / implied, {"after" if post else "before"} 20 Nov 2024 ({len(g)} cycles)', value=g[rv].sum() / g[iv].sum(), lo=np.nan, hi=np.nan)
        pt, lo, hi = wkboot(d, lambda x: x[x.post_sebi][rv].sum() / x[x.post_sebi][iv].sum() - x[~x.post_sebi][rv].sum() / x[~x.post_sebi][iv].sum()); add(q='A3', segment=s, stat='ratio after minus before (+ = premium shrank)', value=pt, lo=lo, hi=hi)
        for u in ('NIFTY', 'SENSEX'):
            du = d[d.und == u]; a_, b_ = du[du.post_sebi], du[~du.post_sebi]; add(q='A3', segment=s, stat=f'ratio after minus before, {u}', value=a_[rv].sum() / a_[iv].sum() - b_[rv].sum() / b_[iv].sum(), lo=np.nan, hi=np.nan)
    for u in ('NIFTY', 'SENSEX'):
        du = C[C.und == u]
        for nm in ('vol_d1_first_hour_atm', 'vol_d1_first_hour_all'):
            b_, a_ = du[~du.post_sebi][nm].median(), du[du.post_sebi][nm].median(); add(q='A3', segment='D-1 first hour', stat=f'{u} {nm.replace("vol_d1_first_hour_", "volume (units), ")}: after / before median', value=a_ / b_, lo=np.nan, hi=np.nan)
        add(q='A3', segment='level', stat=f'{u} ATM implied vol at D-1 open: after minus before (vol points)', value=100 * (du[du.post_sebi].iv_D1_open.mean() - du[~du.post_sebi].iv_D1_open.mean()), lo=np.nan, hi=np.nan)
    # ---- A3 (ii) pre-determined demand proxy: D-1 first-hour ATM volume vs the trailing 8-cycle median of its index
    C = C.sort_values(['und', 'd0']); C['rel_vol'] = C.groupby('und').vol_d1_first_hour_atm.transform(lambda x: x / x.shift(1).rolling(8, min_periods=4).median())
    rng = np.random.default_rng(20261124)
    for s, (rv, _) in (('overnight', seg['overnight']), ('D0 day', seg['D0 day'])):
        d = C[(C[f'iv_used|{s}'] > 0) & C.rel_vol.notna()].copy(); d['ratio'] = d[rv] / d[f'iv_used|{s}']; rho = d[['rel_vol', 'ratio']].corr('spearman').iloc[0, 1]
        null = [pd.Series(np.concatenate([rng.permutation(g.rel_vol.values) for _, g in d.groupby('und')])).corr(pd.Series(np.concatenate([g.ratio.values for _, g in d.groupby('und')])), method='spearman') for _ in range(B)]
        add(q='A3', segment=s, stat=f'Spearman(D-1 first-hour relative ATM volume, later realised/implied) n={len(d)}', value=rho, lo=np.quantile(null, .025), hi=np.quantile(null, .975), p=float(np.mean(np.abs(null) >= abs(rho))))
    # ---- A4 implied-vol terciles
    C['iv_t'] = C.groupby('und').iv_D1_open.transform(lambda x: pd.qcut(x, 3, labels=['low', 'mid', 'high']))
    for s, (rv, _) in seg.items():
        d = C[C[f'iv_used|{s}'] > 0]
        for t, g in d.groupby('iv_t'): add(q='A4', segment=s, stat=f'realised / implied, D-1 open IV tercile {t} ({len(g)})', value=g[rv].sum() / g[f'iv_used|{s}'].sum(), lo=np.nan, hi=np.nan)
    S = pd.DataFrame(rows); S.to_csv(f'{PR}/premium_stats.csv', index=False); C.to_csv(f'{PR}/premium_cycles.csv', index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 100); print(S.round(4).to_string())
