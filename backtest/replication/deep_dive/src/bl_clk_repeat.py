"""Clock-bar study: (1) the clock-phase table of the reactive fires (minute of hour, moduli, chi-square); (2) repeat entries inside a 30-min bar (same side / strike / gaps); (3) entry probability of a machine break by number of scheduled pairs in the bar. Outputs bl_clk_phase_minutes.csv, bl_clk_moduli.csv, bl_summary_clk9.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import chisquare
R = {}; F = pd.read_csv(f'{OUT}/bl_trk_fires.csv'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); ch = Chain(); w = (F.t.values >= 37800) & (F.t.values < 54900); Fw = F[w]
fm = ((Fw.t.values % 3600) // 60).astype(int); hf = np.bincount(fm, minlength=60); pd.DataFrame({'minute_of_hour': range(60), 'fires': hf}).to_csv(f'{OUT}/bl_clk_phase_minutes.csv', index=False)
R['fires_in_window'] = int(w.sum()); R['minute0_30'] = int(hf[0] + hf[30]); R['median_other_minute'] = float(np.median(np.delete(hf, [0, 30]))); R['share_minutes_0_2_of_half_hour'] = float(np.mean((fm % 30) < 3)); R['share_minutes_15_17_of_half_hour'] = float(np.mean(((fm - 15) % 30) < 3))
s = (Fw.t.values - 33300); rows = []
for L in (60, 120, 300, 420, 600, 900, 1800):
    k = 10 if L >= 300 else 6; h = np.histogram(s % L, bins=k, range=(0, L))[0]; rows.append(dict(modulus_seconds=L, bins=k, chi2_p_uniform=float(chisquare(h).pvalue), counts=' '.join(map(str, h))))
pd.DataFrame(rows).to_csv(f'{OUT}/bl_clk_moduli.csv', index=False); R['moduli'] = rows
# repeats inside a bar
r = Pr[Pr.reactive].copy(); r['bar'] = (r.te // 1800).astype(int); rows = []
for (u, e), g in r.groupby(['und', 'expiry']):
    c = ch.cyc(u, e); sp = np.array(c[(0, 'spot')], float); K = np.array(c['strikes'], float)
    for b, gb in g.groupby('bar'):
        gb = gb.sort_values('te'); t = gb.te.values; grp = np.r_[0, np.cumsum(np.diff(t) > 5)]; fires = []
        for gi in np.unique(grp):
            m = grp == gi; j = int((t[m][0] - 33300) // 60); live = sp[min(max(j - 1, 0), 374)]; atm = K[np.argmin(np.abs(K - live))]; fires.append(dict(t=t[m][0], strike=int(gb.strike.values[m][0]), side=int(np.sign(gb.strike.values[m][0] - atm)), pairs=int(m.sum())))
        rows.append(fires)
nf = pd.Series([len(f) for f in rows]).value_counts().sort_index(); R['fires_per_bar'] = {int(k): int(v) for k, v in nf.items()}; ss = ds = sd = od = 0; gaps = []
for f in rows:
    for a, b in zip(f[:-1], f[1:]): ss += a['strike'] == b['strike']; ds += a['strike'] != b['strike']; sd += a['side'] == b['side']; od += a['side'] != b['side']; gaps.append((b['t'] - a['t']) / 60)
R['repeat'] = dict(same_strike=int(ss), diff_strike=int(ds), same_side=int(sd), opposite_side=int(od), gap_q=[float(x) for x in np.quantile(gaps, [.1, .25, .5, .75, .9])])
# entry probability of a machine break by number of scheduled pairs in the bar (from bl_clk_refine machinery)
R_keep = R; sys.argv = ['x']; exec(open('bl_clk_refine.py').read().split("rows = []\nfor nm, fn")[0]); R = R_keep; rr = []
for d in CYC:
    e = CY.expiry.iloc[d['cid']]; g = Pr[(Pr.und == d['und']) & (Pr.expiry == e)]; sch = g[g.sched].te.values; ab = {int((33300 + 60 * a) // 1800) for a in d['A']}
    for f, s_ in run2(d, var='intra', per_side=True): b = int((33300 + 60 * f) // 1800); rr.append(dict(n_sched=int(((sch >= b * 1800) & (sch < (b + 1) * 1800)).sum()), entry=int(b in ab)))
RR = pd.DataFrame(rr); t = RR.groupby(RR.n_sched.clip(upper=3)).entry.agg(['size', 'mean']); R['entry_given_break_by_sched'] = {int(k): dict(n=int(v['size']), p=float(v['mean'])) for k, v in t.iterrows()}; print(R['fires_per_bar'], R['repeat'], R['entry_given_break_by_sched']); rec('clk9', R)
