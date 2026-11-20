"""Reactive-pair study, step 2 (plan tests 1-4, 6): when, timer-likeness, event-anchored, strike, quantity. Outputs bl_react_*.csv, bl_summary_react1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(101); R = {}; O = load_orders()
Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); BB = pd.read_csv(f'{OUT}/bl_close_orders_clusters_D-1.csv')[['und', 'expiry', 'te', 'tod', 'r_low', 'lots']]; Pn = pd.read_csv(f'{OUT}/bl_react_panel.csv.gz'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv')
rp = Pr[Pr.reactive].copy(); sp = Pr[Pr.sched].copy(); rp['hour'] = (rp.tod // 3600).astype(int); n = len(CY)
# 1. when
h = rp.groupby('hour').size() / n; R['react_pairs'] = len(rp); R['react_per_cycle'] = len(rp) / n; R['react_hour_per_cycle'] = h.round(2).to_dict(); R['react_cycles_with_any'] = int(rp.groupby(['und', 'expiry']).ngroups)
print(f'reactive pairs {len(rp)} ({len(rp) / n:.1f} per cycle; cycles with any {R["react_cycles_with_any"]}/{n}); per cycle by clock hour:', h.round(2).to_dict())
sec = (rp.tod % 60).values; chi = stats.chisquare(np.histogram(sec, bins=6, range=(0, 60))[0]); R['seconds_uniform_p'] = float(chi.pvalue); mn = stats.chisquare(np.histogram((rp.tod // 60 % 15).values, bins=15, range=(0, 15))[0]); R['minute_in_15_uniform_p'] = float(mn.pvalue); print(f'seconds-of-minute uniform p={chi.pvalue:.3f}; minute-within-15 uniform p={mn.pvalue:.3f}; offset-in-block quantiles {rp.off.quantile([.1, .25, .5, .75, .9]).round(0).tolist()}')
# lots per reactive burst (pairs within 3 s same strike)
rp = rp.sort_values(['und', 'expiry', 'strike', 'te']); g = rp.groupby(['und', 'expiry', 'strike']).te.diff(); rp['burst'] = ((g.isna()) | (g > 3)).cumsum(); bs = rp.groupby('burst').size(); R['burst_pairs_q'] = bs.quantile([.5, .75, .9, 1]).tolist(); R['burst_single_share'] = float((bs == 1).mean()); R['bursts'] = len(bs); print(f'reactive bursts {len(bs)}; pairs per burst q50/75/90/max {bs.quantile([.5, .75, .9, 1]).tolist()}; single-pair bursts {(bs == 1).mean():.2f}')
# 2. timer-likeness: gap to the previous body sell / previous pair in the same cycle
O1 = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)]; gaps = []; gaps_p = []
for (u, e), g_ in rp.groupby(['und', 'expiry']):
    st = np.sort(O1[(O1.und == u) & (O1.expiry == e)].te.values); pt = np.sort(Pr[(Pr.und == u) & (Pr.expiry == e)].te.values)
    for t in g_.te.values:
        a = st[st < t - 3]; b = pt[pt < t - 3]
        if len(a): gaps.append((t - a.max()) / 60)
        if len(b): gaps_p.append((t - b.max()) / 60)
gaps = np.array(gaps); gaps_p = np.array(gaps_p); R['gap_sell_q'] = np.quantile(gaps, [.1, .25, .5, .75, .9]).tolist(); R['gap_pair_q'] = np.quantile(gaps_p, [.1, .25, .5, .75, .9]).tolist()
def share15(a): return float(((a >= 14) & (a <= 15.5)).mean())
nul = []
for _ in range(100):
    gg = []
    for (u, e), g_ in rp.groupby(['und', 'expiry']):
        st = np.sort(O1[(O1.und == u) & (O1.expiry == e)].te.values); lo, hi = st.min(), st.max(); sh = lo + ((g_.te.values - lo + rng.uniform(0, hi - lo)) % (hi - lo))
        for t in sh:
            a = st[st < t - 3]
            if len(a): gg.append((t - a.max()) / 60)
    nul.append(share15(np.array(gg)))
R['gap_sell_15min_share'] = share15(gaps); R['gap_sell_15min_null'] = [float(np.mean(nul)), float(np.quantile(nul, .975))]; print(f'gap since previous body sell (min) q10/25/50/75/90: {np.round(R["gap_sell_q"], 1)}; share in 14-15.5 min {share15(gaps):.3f} vs shifted null {np.mean(nul):.3f} (97.5% {np.quantile(nul, .975):.3f})')
# 3. event-anchored: after a body buy-back
def after(delta, which):
    obs = []; null = []
    for (u, e), g_ in rp.groupby(['und', 'expiry']):
        b = BB[(BB.und == u) & (BB.expiry == e)]; b = b[b.r_low >= 1.5] if which == 'stop' else b; bt = np.sort(b.te.values)
        if len(bt) == 0: continue
        te = g_.te.values; allt = O1[(O1.und == u) & (O1.expiry == e)].te.values; lo, hi = allt.min(), allt.max(); span = max(hi - lo, 1); f = lambda tt: np.mean([((t - bt > 0) & (t - bt <= delta)).any() for t in tt]); obs.append((f(te), len(te))); null.append((np.mean([f(lo + ((te - lo + rng.uniform(0, span)) % span)) for _ in range(30)]), len(te)))
    w = np.array([x[1] for x in obs]); return float(np.average([x[0] for x in obs], weights=w)), float(np.average([x[0] for x in null], weights=w)), int(w.sum())
for delta in (60, 300, 900):
    for which in ('any', 'stop'): R[f'after_{which}_{delta}'] = after(delta, which); print(f'reactive pairs within {delta:4d} s after a body buy-back ({which:4s}): observed {R[f"after_{which}_{delta}"][0]:.3f} vs shifted null {R[f"after_{which}_{delta}"][1]:.3f} (n={R[f"after_{which}_{delta}"][2]})')
# 4. strike: hit rate of the previous-minute ATM; reference classes
def atm_hit(df): x = (df.strike == df.atm_prev); return float(x.mean()), int(len(df))
R['atm_hit_react'] = atm_hit(rp.dropna(subset=['atm_prev'])); R['atm_hit_sched'] = atm_hit(sp.dropna(subset=['atm_prev'])); So = pd.read_csv(f'{OUT}/bl_size_solo.csv'); So = So[So.day == 'D-1'].merge(O1[['und', 'expiry', 'te', 'cp', 'strike', 'atm_prev']].drop_duplicates(['und', 'expiry', 'te', 'cp', 'strike']), on=['und', 'expiry', 'te', 'cp', 'strike'], how='left', suffixes=('', '_o')); R['atm_hit_solo'] = atm_hit(So.dropna(subset=['atm_prev'])); print('previous-minute ATM hit rate: reactive pairs %.3f (n=%d), timetable pairs %.3f (n=%d), solo sells %.3f (n=%d)' % (*R['atm_hit_react'], *R['atm_hit_sched'], *R['atm_hit_solo']))
rp['off_steps'] = (rp.strike - rp.atm_prev) / rp.und.map(ref.STEP); R['react_strike_off_steps'] = rp.off_steps.round(0).value_counts(normalize=True).sort_index().round(3).to_dict(); print('reactive pair strike minus previous-minute ATM (steps):', R['react_strike_off_steps'])
# 6. quantity: reactive lots in minute vs lots bought back in previous 5 min (panel)
Q = Pn.copy(); Q['rlots'] = 0.0; cnt = rp.groupby(['und', 'expiry', 'j']).size().rename('n_pairs').reset_index(); Q = Q.merge(cnt, on=['und', 'expiry', 'j'], how='left').fillna({'n_pairs': 0}); ev = Q[Q.yR == 1]
R['corr_pairs_bbl5'] = [float(stats.spearmanr(ev.n_pairs, ev.lots_bb5)[0]), len(ev)]; R['corr_pairs_absdrift'] = [float(stats.spearmanr(ev.n_pairs, ev.absdrift_pair.fillna(0))[0]), len(ev)]; R['corr_pairs_a5'] = [float(stats.spearmanr(ev.n_pairs, ev.a5)[0]), len(ev)]; print(f'among reactive minutes (n={len(ev)}): Spearman(pairs in minute, lots bought back in previous 5 min)={R["corr_pairs_bbl5"][0]:.2f}; vs ATM drift {R["corr_pairs_absdrift"][0]:.2f}; vs |5-min spot move| {R["corr_pairs_a5"][0]:.2f}')
# hazard by minutes since last sell
Pn['age_b'] = pd.cut(Pn.age_sell, [0, 1, 2, 5, 10, 14, 16, 20, 30, 60, 500]); t = Pn.groupby('age_b', observed=True).yR.agg(['size', 'sum']); t['per1000'] = (t['sum'] / t['size'] * 1000).round(1); print('\nreactive-pair hazard (per 1000 cycle-minutes) by minutes since the last body sell:'); print(t.to_string()); t.reset_index().assign(age_b=lambda d: d.age_b.astype(str)).to_csv(f'{OUT}/bl_react_hazard_age.csv', index=False)
for k in ('version', 'nifty'): print(Pn.groupby(k).yR.agg(['size', 'sum']).assign(per1000=lambda d: (d['sum'] / d['size'] * 1000).round(1)).to_string())
rec('react1', R)
