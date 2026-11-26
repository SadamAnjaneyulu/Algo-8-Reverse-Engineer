"""Seasonality / regime investigation of the combined backtest (plan reports/BACKTEST3Y_REGIME_PLAN.md). Exploratory: every cycle (IS, OOS, rule-fitted live window) is used.
Unit = ISO week (mean net per cycle of the cycles expiring that week), at a constant lot size (NIFTY 65, SENSEX 20). Outputs outputs/bt3_results/regime_*.csv and regime_summary.json."""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '/home/user/Algo-8-Reverse-Engineer/backtest'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from scipy import stats
from bt.cycles import cycle_list
OUT = os.path.join(os.path.dirname(os.path.abspath('.')), 'outputs'); RES = f'{OUT}/bt3_results'; BT3 = f'{OUT}/bt3'; REFU = {'NIFTY': 65.0, 'SENSEX': 20.0}; NP = 5000; NB = 2000; rng = np.random.default_rng(20261124); J = {}
# ---------------- per-cycle table
def load(split, run, suffix=''):
    c = pd.read_csv(f'{RES}/{split}_{run}{suffix}_cycles.csv'); c['split'] = split; return c[c.ok]
full = pd.concat([load('IS', 'B-V2'), load('OOS', 'B-V2'), load('LIVE_FITTED', 'A-V1')], ignore_index=True)
hold = pd.concat([load('IS', 'B-V2', '_HOLD'), load('OOS', 'B-V2', '_HOLD'), load('LIVE_FITTED', 'A-V1', '_HOLD')], ignore_index=True)[['und', 'expiry', 'net', 'gross']].rename(columns={'net': 'd1only_net', 'gross': 'd1only_gross'})
alt = pd.concat([load('IS', 'A-V1'), load('OOS', 'A-V1'), load('LIVE_FITTED', 'A-V1')], ignore_index=True)[['und', 'expiry', 'net', 'gross']].rename(columns={'net': 'altA_net', 'gross': 'altA_gross'})
C = full.merge(hold, on=['und', 'expiry']).merge(alt, on=['und', 'expiry']); ref = C.und.map(REFU) / C.unit
for c in ('net', 'gross', 'd1only_net', 'd1only_gross', 'altA_net', 'altA_gross'): C[c + '_k'] = C[c] * ref
C['d0adds_net_k'] = C.net_k - C.d1only_net_k; C['d0'] = pd.to_datetime(C.d0); C['wk'] = C.d0.dt.strftime('%G-%V')
# ---------------- features from the minute data (no P&L involved)
def feats(r):
    d = pd.read_pickle(f'{BT3}/{r.und}_{r.expiry}.pkl.gz'); s1, s0 = d['spot1'], d['spot0']; K = d['opt1']['K']; sp = s1.close.iloc[0]; a = int(np.argmin(np.abs(K - sp)))
    strad = d['opt1'][('CE', 'close')][a, 1] + d['opt1'][('PE', 'close')][a, 1]; imp = 100 * strad / sp
    mr = 100 * (s1.high.iloc[:61].max() - s1.low.iloc[:61].min()) / sp; gap = 100 * abs(s0.open.iloc[0] - s1.close.iloc[374]) / s1.close.iloc[374]
    real = 100 * abs(s0.close.iloc[374] - s1.open.iloc[0]) / s1.open.iloc[0]; exc = 100 * (max(s1.high.max(), s0.high.max()) - min(s1.low.min(), s0.low.min())) / s1.open.iloc[0]
    return pd.Series(dict(implied_move=imp, morning_range=mr, open_gap=gap, realised_move=real, excursion=exc, ratio=real / imp if imp > 0 else np.nan))
F = C.apply(feats, axis=1); C = pd.concat([C, F], axis=1)
cl = cycle_list(); cl['d0'] = pd.to_datetime(cl.d0); cl = cl.sort_values(['und', 'd0']); cl['monthly'] = cl.groupby(['und', cl.d0.dt.to_period('M')]).d0.transform('max') == cl.d0
C = C.merge(cl[['und', 'expiry', 'monthly']], on=['und', 'expiry'], how='left'); C['monthly'] = C.monthly.fillna(False)
C.to_csv(f'{RES}/regime_cycles.csv', index=False)
# ---------------- weekly series
g = C.groupby('wk'); W = pd.DataFrame({'date': g.d0.min(), 'n': g.size(), 'net': g.net_k.mean(), 'gross': g.gross_k.mean(), 'altA_net': g.altA_net_k.mean(), 'altA_gross': g.altA_gross_k.mean(), 'd1only': g.d1only_net_k.mean(), 'd0adds': g.d0adds_net_k.mean(),
                  'implied_move': g.implied_move.mean(), 'morning_range': g.morning_range.mean(), 'open_gap': g.open_gap.mean(), 'realised_move': g.realised_move.mean(), 'excursion': g.excursion.mean(), 'ratio': g.ratio.mean(),
                  'split': g.split.agg(lambda s: s.mode().iloc[0]), 'monthly': g.monthly.max()}).sort_values('date').reset_index()
W['month'] = W.date.dt.month; W['quarter'] = W.date.dt.quarter; W['year'] = W.date.dt.year; W['half'] = W.year.astype(str) + 'H' + np.where(W.month <= 6, '1', '2'); W['wom'] = (W.date.dt.day - 1) // 7 + 1
W['regime'] = np.where(W.date < '2026-06-22', 'before June 2026 (timetable assumed)', 'from June 2026 (observed)'); W['monthly_week'] = np.where(W.monthly, 'monthly-expiry week', 'other week')
for f in ('implied_move', 'morning_range', 'open_gap', 'realised_move', 'ratio'): W[f + '_t'] = pd.qcut(W[f], 3, labels=['low', 'mid', 'high']).astype(str)
W.to_csv(f'{RES}/regime_weeks.csv', index=False); n = len(W); J['weeks'] = n; J['cycles'] = len(C)
# ---------------- Part 1: stationarity
def roll_means(x, w=26): c = np.cumsum(np.insert(x, 0, 0.0)); return (c[w:] - c[:-w]) / w
def scan(x, m=30):
    n = len(x); cs = np.cumsum(x); cs2 = np.cumsum(x ** 2); best = 0.0; arg = None
    for k in range(m, n - m + 1):
        m1, m2 = cs[k - 1] / k, (cs[-1] - cs[k - 1]) / (n - k); v1 = (cs2[k - 1] - k * m1 ** 2) / (k - 1); v2 = ((cs2[-1] - cs2[k - 1]) - (n - k) * m2 ** 2) / (n - k - 1); t = (m2 - m1) / np.sqrt(v1 / k + v2 / (n - k))
        if abs(t) > abs(best): best, arg = t, k
    return best, arg
def stationarity(x, label):
    x = np.asarray(x, float); rm = roll_means(x); s0 = rm.std(); t0, k0 = scan(x); perm_s = []; perm_t = []
    for _ in range(NP): p = rng.permutation(x); perm_s.append(roll_means(p).std()); perm_t.append(abs(scan(p)[0]) if _ < 1000 else np.nan)
    half = len(x) // 2; d = x[half:].mean() - x[:half].mean(); bs = [rng.choice(x[half:], len(x) - half).mean() - rng.choice(x[:half], half).mean() for _ in range(NB)]
    ac = [float(pd.Series(x).autocorr(l)) for l in (1, 2, 3, 4)]
    return dict(series=label, weeks=len(x), mean=float(x.mean()), roll26_sd=float(s0), roll26_sd_p=float((np.array(perm_s) >= s0).mean()), changepoint_t=float(t0), changepoint_week=int(k0), changepoint_p=float((np.nanmean(np.array(perm_t[:1000]) >= abs(t0)))), first_half_mean=float(x[:half].mean()), second_half_mean=float(x[half:].mean()),
                diff=float(d), diff_lo=float(np.quantile(bs, .025)), diff_hi=float(np.quantile(bs, .975)), acf1=ac[0], acf2=ac[1], acf3=ac[2], acf4=ac[3], acf_band=float(2 / np.sqrt(len(x))))
ST = pd.DataFrame([stationarity(W[c].values, c) for c in ('net', 'gross', 'altA_net', 'd1only', 'd0adds')]); ST.round(4).to_csv(f'{RES}/regime_stationarity.csv', index=False)
W['roll26'] = pd.Series(W.net).rolling(26).mean(); bs = np.array([[rng.choice(W.net.values[i:i + 26], 26).mean() for _ in range(300)] for i in range(len(W) - 25)]); W.loc[25:, 'roll26_lo'] = np.quantile(bs, .025, axis=1); W.loc[25:, 'roll26_hi'] = np.quantile(bs, .975, axis=1); W.to_csv(f'{RES}/regime_weeks.csv', index=False)
# ---------------- Parts 2 and 3: families
def fam_week(col, label, order=None):
    lab = W[col].astype(str).values; groups = sorted(set(lab)) if order is None else [str(o) for o in order]; y = W.net.values; m = y.mean()
    def ss(l): return sum(((l == gname).sum()) * (y[l == gname].mean() - m) ** 2 for gname in groups if (l == gname).any())
    s0 = ss(lab); p = float(np.mean([ss(rng.permutation(lab)) >= s0 for _ in range(NP)])); cells = []
    for gname in groups:
        msk = lab == gname
        if msk.sum() < 3: continue
        yy = y[msk]; b = np.array([rng.choice(yy, len(yy)).mean() for _ in range(NB)]); pc = max(2 * min((b <= 0).mean(), (b >= 0).mean()), 1 / NB); other = {k: float(W[k].values[msk].mean()) for k in ('gross', 'altA_net')}
        cells.append(dict(family=label, cell=gname, weeks=int(msk.sum()), mean_net=float(yy.mean()), lo=float(np.quantile(b, .025)), hi=float(np.quantile(b, .975)), p_cell=float(pc), mean_gross=other['gross'], mean_altA_net=other['altA_net'], win_weeks=float((yy > 0).mean())))
    return dict(family=label, groups=len(cells), family_p=p, stat=float(s0)), cells
def fam_cycle(col, label):
    d = C[['wk', col, 'net_k']].copy(); d['res'] = d.net_k - d.groupby('wk').net_k.transform('mean'); d = d[d.groupby('wk').wk.transform('size') > 1]; lab = d[col].astype(str).values; y = d.res.values; groups = sorted(set(lab)); wk = d.wk.values; idx = {w_: np.where(wk == w_)[0] for w_ in np.unique(wk)}
    def ss(l): return sum(((l == gname).sum()) * (y[l == gname].mean()) ** 2 for gname in groups if (l == gname).any())
    s0 = ss(lab); perms = []
    for _ in range(NP):
        l2 = lab.copy()
        for w_, ii in idx.items(): l2[ii] = rng.permutation(lab[ii])
        perms.append(ss(l2))
    cells = []
    for gname in groups:
        msk = C[col].astype(str).values == gname; yy = C.net_k.values[msk]
        if msk.sum() < 3: continue
        wkc = C.wk.values[msk]; uw = np.unique(wkc); sums = {w_: yy[wkc == w_] for w_ in uw}; b = []
        for _ in range(NB): ch = rng.choice(uw, len(uw)); b.append(np.concatenate([sums[w_] for w_ in ch]).mean())
        b = np.array(b); pc = max(2 * min((b <= 0).mean(), (b >= 0).mean()), 1 / NB); cells.append(dict(family=label, cell=gname, weeks=int(len(uw)), mean_net=float(yy.mean()), lo=float(np.quantile(b, .025)), hi=float(np.quantile(b, .975)), p_cell=float(pc), mean_gross=float(C.gross_k.values[msk].mean()), mean_altA_net=float(C.altA_net_k.values[msk].mean()), win_weeks=float((yy > 0).mean())))
    return dict(family=label, groups=len(cells), family_p=float((np.array(perms) >= s0).mean()), stat=float(s0)), cells
C['index'] = C.und; C['weekday'] = C.d0.dt.day_name()
famlist = [fam_week('month', 'month of year', list(range(1, 13))), fam_week('quarter', 'quarter', [1, 2, 3, 4]), fam_week('year', 'calendar year'), fam_week('half', 'half-year'), fam_week('wom', 'week of month (D0)', [1, 2, 3, 4, 5]), fam_week('monthly_week', 'monthly-expiry week'), fam_week('regime', 'timetable regime'),
           fam_cycle('weekday', 'weekday of D0 (within week)'), fam_cycle('index', 'index (within week)')]
for f in ('implied_move', 'morning_range', 'open_gap', 'realised_move', 'ratio'): famlist.append(fam_week(f + '_t', {'implied_move': 'implied move at D-1 open (ex ante)', 'morning_range': 'D-1 morning range (ex ante)', 'open_gap': 'opening gap on D0 (known at the D0 open)', 'realised_move': 'realised move (ex post)', 'ratio': 'realised / implied ratio (ex post)'}[f], ['low', 'mid', 'high']))
FAM = pd.DataFrame([f for f, _ in famlist]); CELLS = pd.DataFrame([c for _, cs in famlist for c in cs])
# multiple testing: BH over all cells, Holm over families
p = CELLS.p_cell.values; o = np.argsort(p); m_ = len(p); q = np.empty(m_); prev = 1.0
for r_, i in zip(range(m_, 0, -1), o[::-1]): prev = min(prev, p[i] * m_ / r_); q[i] = prev
CELLS['q_bh'] = q; po = FAM.family_p.values; oo = np.argsort(po); h = np.empty(len(po)); run = 0.0
for k, i in enumerate(oo): run = max(run, min(1.0, (len(po) - k) * po[i])); h[i] = run
FAM['p_holm'] = h; FAM['best_cell_q'] = [float(CELLS[CELLS.family == f].q_bh.min()) for f in FAM.family]; sg = lambda a, b: np.sign(a) == np.sign(b)
CELLS['sign_ok_gross_and_A'] = sg(CELLS.mean_net, CELLS.mean_gross) & sg(CELLS.mean_net, CELLS.mean_altA_net)
FAM['sign_ok'] = [bool(CELLS[(CELLS.family == f) & (CELLS.q_bh < 0.10)].sign_ok_gross_and_A.any()) if (CELLS[CELLS.family == f].q_bh < 0.10).any() else False for f in FAM.family]; FAM['supported'] = (FAM.p_holm < 0.05) & (FAM.best_cell_q < 0.10) & FAM.sign_ok
FAM.round(4).to_csv(f'{RES}/regime_families.csv', index=False); CELLS.round(4).to_csv(f'{RES}/regime_cells.csv', index=False)
# mechanism: net vs realised / implied ratio (weekly)
rho = stats.spearmanr(W.ratio, W.net).correlation; pr = float(np.mean([abs(stats.spearmanr(W.ratio, rng.permutation(W.net.values)).correlation) >= abs(rho) for _ in range(2000)])); J['mechanism_spearman_ratio_net'] = float(rho); J['mechanism_p'] = pr
J['spearman_implied_net'] = float(stats.spearmanr(W.implied_move, W.net).correlation); J['spearman_realised_net'] = float(stats.spearmanr(W.realised_move, W.net).correlation)
J['share_weeks_positive'] = float((W.net > 0).mean()); J['cells'] = int(len(CELLS)); J['families'] = int(len(FAM)); json.dump(J, open(f'{RES}/regime_summary.json', 'w'), indent=1)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); print(json.dumps(J, indent=1)); print(ST.round(3).to_string()); print(FAM.round(3).to_string()); print(CELLS[CELLS.q_bh < 0.25].round(3).to_string())
