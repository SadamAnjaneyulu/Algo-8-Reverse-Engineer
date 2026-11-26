"""Look-back study (plan BODY_REACTIVE_LOOKBACK_PLAN.md): is 'ATM + 1 step toward the 15-minute move' correct, and is the look-back rolling every minute?
Outputs bl_lb_scan.csv, bl_lb_defs.csv, bl_lb_magnitude.csv, bl_lb_seconds.csv, bl_lb_sample.csv, bl_lb_hazard.csv, bl_summary_lb.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
rng = np.random.default_rng(401); R = {}; O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); Pr = Pr.sort_values(['und', 'expiry', 'te']); ch = Chain(); S1 = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)]
rows = []; cyc_id = {}; series = {}
for (u, e), g in Pr.groupby(['und', 'expiry']):
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values; series[(u, e)] = (K, sp)
    cyc_id[(u, e)] = len(cyc_id)
for (u, e), g in Pr.groupby(['und', 'expiry']):
    K, sp = series[(u, e)]; step = ref.STEP[u]; near = lambda s: K[np.argmin(np.abs(K - s))]; g = g.reset_index(drop=True); sells = np.sort(S1[(S1.und == u) & (S1.expiry == e)].te.values)
    for i, r in g.iterrows():
        j = int(r.j)
        if not r.reactive or j > 373 or j < 20: continue
        prevR = g[(g.index < i) & g.reactive & (g.te < r.te - 3)]; prevS = g[(g.index < i) & g.sched & (g.te < r.te - 3)]; sl = sells[sells < r.te - 3]
        b0 = 1 + 15 * int(r.k); m_in = int(((r.tod - 33360) % 900) // 60); sec = int(r.tod % 60); atm = near(sp[j - 1]); sgn = lambda a, b: float(np.sign(a - b))
        d = {'rolling 10': sgn(sp[j - 1], sp[j - 11]), 'rolling 15': sgn(sp[j - 1], sp[j - 16]), 'rolling 20': sgn(sp[j - 1], sp[j - 21]), 'rolling 30': sgn(sp[j - 1], sp[max(j - 31, 0)]), 'rolling 60': sgn(sp[j - 1], sp[max(j - 61, 0)]),
             'previous 15-min block (open to close)': sgn(sp[b0 - 1], sp[max(b0 - 16, 0)]) if b0 >= 16 else np.nan, 'current block so far': sgn(sp[j - 1], sp[b0 - 1]) if j - 1 > b0 - 1 else 0.0,
             'since previous reactive pair': sgn(sp[j - 1], sp[max(int((prevR.te.iloc[-1] - 33300) // 60) - 1, 0)]) if len(prevR) else np.nan, 'since previous timetable wave': sgn(sp[j - 1], sp[max(int((prevS.te.iloc[-1] - 33300) // 60) - 1, 0)]) if len(prevS) else np.nan,
             'since previous sell (any)': sgn(sp[j - 1], sp[max(int((sl.max() - 33300) // 60) - 1, 0)]) if len(sl) else np.nan, 'since the open': sgn(sp[j - 1], sp[1]), 'direction of latest day extreme': (1.0 if np.argmax(sp[1:j]) > np.argmin(sp[1:j]) else -1.0)}
        hit = {k: (float(atm + v * step == r.strike) if v == v else np.nan) for k, v in d.items()}
        row = dict(und=u, expiry=e, cid=cyc_id[(u, e)], j=j, m_in=m_in, sec=sec, strike=r.strike, atm=atm, step=step, tod=r.tod, sp_now=sp[j - 1], sp_15=sp[j - 16], m15=(sp[j - 1] - sp[j - 16]) / step, first_half=r.expiry < '2026-08-25'); row.update({f'hit|{k}': v for k, v in hit.items()}); row.update({f'dir|{k}': v for k, v in d.items()})
        # scan L
        for L in range(1, 91): row[f'L{L}'] = float(atm + np.sign(sp[j - 1] - sp[max(j - 1 - L, 0)]) * step == r.strike); row[f'S{L}'] = (np.sign(r.strike - atm) == np.sign(sp[j - 1] - sp[max(j - 1 - L, 0)])) if r.strike != atm else np.nan
        row['hit_close_j'] = float(near(sp[j]) + np.sign(sp[j] - sp[j - 15]) * step == r.strike); row['atm_same_jm1_j'] = float(near(sp[j]) == atm); row['atm_close_j_hit'] = float(near(sp[j]) == r.strike); row['atm_close_jm1_hit'] = float(atm == r.strike); rows.append(row)
D = pd.DataFrame(rows); D.to_pickle(f'{OUT}/bl_lb_events.pkl'); n = len(D); print('reactive pairs evaluated', n); R['n'] = n
# ---- 1. correctness
h15 = D['hit|rolling 15']; R['hit15'] = float(h15.mean()); R['hit15_und'] = D.groupby('und')['hit|rolling 15'].mean().to_dict(); R['hit15_half'] = D.groupby('first_half')['hit|rolling 15'].mean().to_dict(); off = (D.strike - D.atm) / D.step * np.sign(D['dir|rolling 15']).replace(0, np.nan); R['offset_dist'] = off.round(0).value_counts(normalize=True).sort_index().round(3).to_dict(); R['dir_zero'] = int((D['dir|rolling 15'] == 0).sum())
print(f"stated rule hit {R['hit15']:.3f}; by und {R['hit15_und']}; by half {R['hit15_half']}; offset in the move direction (steps): {R['offset_dist']}; exact-zero 15-min moves: {R['dir_zero']}")
# sample table: first reactive pair of the first 10 cycles by D-1 date
cyd = CY.set_index(['und', 'expiry']).d1; D['d1'] = [cyd[(u, e)] for u, e in zip(D.und, D.expiry)]; first = D.sort_values(['d1', 'und', 'tod']).groupby(['und', 'expiry'], sort=False).head(1).sort_values('d1').head(10)
clk = lambda t: f'{int(t // 3600)}:{int((t % 3600) // 60):02d}:{int(t % 60):02d}'; smp = pd.DataFrame({'D-1 date': first.d1, 'underlying': first.und, 'order time': first.tod.map(clk), 'previous-minute ATM': first.atm.astype(int), 'spot 15 min earlier': first.sp_15.round(1), 'spot now (prev-minute close)': first.sp_now.round(1), '15-min move (points)': (first.sp_now - first.sp_15).round(1), 'predicted strike': (first.atm + np.sign(first['dir|rolling 15']) * first.step).astype(int), 'actual strike': first.strike.astype(int)}); smp['match'] = smp['predicted strike'] == smp['actual strike']; smp.to_csv(f'{OUT}/bl_lb_sample.csv', index=False); print(smp.to_string(index=False)); R['sample_matches'] = int(smp.match.sum())
# ---- 2. scan L with paired cluster bootstrap vs L = 15
cid = D.cid.values; ucy = np.unique(cid); idx = {c: np.where(cid == c)[0] for c in ucy}; Ls = list(range(1, 91)); H = np.array([D[f'L{L}'].values for L in Ls]); Sg = np.array([D[f'S{L}'].values.astype(float) for L in Ls]); rows = []
bs_idx = [np.concatenate([idx[c] for c in rng.choice(ucy, len(ucy))]) for _ in range(400)]
for a, L in enumerate(Ls):
    diff = [H[a][ii].mean() - H[14][ii].mean() for ii in bs_idx]; rows.append((L, H[a].mean(), np.nanmean(Sg[a]), np.quantile(diff, .025), np.quantile(diff, .975)))
SC = pd.DataFrame(rows, columns=['L_min', 'hit_rate', 'side_agreement_nonATM', 'diff_vs_L15_lo', 'diff_vs_L15_hi']); SC.round(4).to_csv(f'{OUT}/bl_lb_scan.csv', index=False)
R['scan_best_L'] = int(SC.sort_values('hit_rate', ascending=False).L_min.iloc[0]); R['scan_hit_at'] = {str(L): float(SC.set_index('L_min').hit_rate.loc[L]) for L in (3, 5, 10, 12, 14, 15, 16, 18, 20, 25, 30, 45, 60, 90)}; R['scan_L_ge_hit_within_2pts_of_max'] = [int(x) for x in SC[SC.hit_rate >= SC.hit_rate.max() - 0.02].L_min.tolist()]; R['scan_L15_diff_ci_vs_10_20'] = {str(L): [float(SC.set_index('L_min').diff_vs_L15_lo.loc[L]), float(SC.set_index('L_min').diff_vs_L15_hi.loc[L])] for L in (10, 12, 14, 16, 18, 20, 30)}
print('rule(L) hit rate:', {k: round(v, 3) for k, v in R['scan_hit_at'].items()}, '| best L', R['scan_best_L'], '| L within 2 points of the max:', R['scan_L_ge_hit_within_2pts_of_max'])
# ---- 3. definitions overall and by minute-of-block
defs = [c[4:] for c in D.columns if c.startswith('hit|')]; rows = []
for k in defs:
    x = D[f'hit|{k}']; v = x.notna(); bs = [np.nanmean(x.values[ii]) for ii in bs_idx]; row = [k, int(v.sum()), x.mean()] + [x[D.m_in.between(a, b)].mean() for a, b in ((0, 4), (5, 9), (10, 14))] + [np.quantile(bs, .025), np.quantile(bs, .975)]; rows.append(row)
DF = pd.DataFrame(rows, columns=['direction definition', 'n', 'hit_rate', 'minute_0_4', 'minute_5_9', 'minute_10_14', 'ci_lo', 'ci_hi']).sort_values('hit_rate', ascending=False); DF.round(4).to_csv(f'{OUT}/bl_lb_defs.csv', index=False); print(DF.round(3).to_string(index=False)); R['defs'] = DF.round(4).to_dict('list')
dis = D[(D['dir|rolling 15'] != D['dir|previous 15-min block (open to close)']) & D['dir|previous 15-min block (open to close)'].notna()]; R['disagree_n'] = len(dis); R['disagree_rolling_hit'] = float(dis['hit|rolling 15'].mean()); R['disagree_block_hit'] = float(dis['hit|previous 15-min block (open to close)'].mean()); print(f"events where rolling-15 and previous-block directions disagree: n={len(dis)}; rolling hit {R['disagree_rolling_hit']:.3f}; previous-block hit {R['disagree_block_hit']:.3f}")
dis2 = D[(D['dir|rolling 15'] != D['dir|current block so far'])]; R['disagree2_n'] = len(dis2); R['disagree2_rolling_hit'] = float(dis2['hit|rolling 15'].mean()); R['disagree2_cur_hit'] = float(dis2['hit|current block so far'].mean())
# minute-of-block trend of rolling-15 hit rate
from scipy import stats
rho = stats.spearmanr(D.m_in, D['hit|rolling 15'])[0]; R['rolling15_vs_minute_in_block_rho'] = float(rho); print('Spearman(minute-of-block, rolling-15 hit) =', round(rho, 3))
# ---- 4. magnitude and ties
D['abs_m15'] = D.m15.abs(); D['mb'] = pd.cut(D.abs_m15, [-1e-9, 1e-9, .1, .25, .5, 1, 2, 10]); T = D.groupby('mb', observed=True).agg(n=('strike', 'size'), hit=('hit|rolling 15', 'mean')); T['mean_offset_in_direction'] = D.assign(o=off).groupby('mb', observed=True).o.mean(); T.round(3).reset_index().assign(mb=lambda d: d.mb.astype(str)).to_csv(f'{OUT}/bl_lb_magnitude.csv', index=False); print(T.round(3).to_string()); R['magnitude'] = T.round(4).reset_index().assign(mb=lambda d: d.mb.astype(str)).to_dict('list')
# ---- 5. bar vs tick: hit rate by second of the minute
D['sb'] = pd.cut(D.sec, [-1, 9, 19, 29, 39, 49, 59]); T2 = D.groupby('sb', observed=True).agg(n=('strike', 'size'), rule15_hit=('hit|rolling 15', 'mean'), atm_prev_hit=('atm_close_jm1_hit', 'mean'), atm_curr_close_hit=('atm_close_j_hit', 'mean'), atm_same=('atm_same_jm1_j', 'mean')); T2.round(3).reset_index().assign(sb=lambda d: d.sb.astype(str)).to_csv(f'{OUT}/bl_lb_seconds.csv', index=False); print(T2.round(3).to_string()); R['seconds_rho'] = float(stats.spearmanr(D.sec, D['hit|rolling 15'])[0]); R['seconds'] = T2.round(4).reset_index().assign(sb=lambda d: d.sb.astype(str)).to_dict('list'); R['hit_close_j'] = float(D.hit_close_j.mean())
# ---- 6. direction vs trigger: hazard inside the gate by signed 15-minute move
P = pd.read_csv(f'{OUT}/bl_mech_panel.csv.gz'); W = P[(P.j >= 75) & (P.j < 360)].copy(); W['dirb'] = pd.cut(W.ch15, [-10, -0.1, -0.02, 0.02, 0.1, 10], labels=['down > 0.1%', 'down 0.02-0.1%', 'flat (< 0.02%)', 'up 0.02-0.1%', 'up > 0.1%'])
Hz = W.groupby('dirb', observed=True).yR.agg(['size', 'sum']); Hz['per1000'] = (Hz['sum'] / Hz['size'] * 1000).round(1); W = W.sort_values(['und', 'expiry', 'j']); W['flip'] = (np.sign(W.ch15) != np.sign(W.groupby(['und', 'expiry']).ch15.shift(5))) & W.groupby(['und', 'expiry']).ch15.shift(5).notna()
Hf = W.groupby('flip').yR.agg(['size', 'sum']); Hf['per1000'] = (Hf['sum'] / Hf['size'] * 1000).round(1); print('\nhazard inside the 10:30-15:15 window by signed 15-min move'); print(Hz.to_string()); print('hazard by direction flip in the last 5 min'); print(Hf.to_string()); R['hazard_dir'] = Hz.reset_index().assign(dirb=lambda d: d.dirb.astype(str)).to_dict('list'); R['hazard_flip'] = Hf.reset_index().to_dict('list')
pd.concat([Hz.reset_index().rename(columns={'dirb': 'group'}).assign(kind='signed 15-min move'), Hf.reset_index().rename(columns={'flip': 'group'}).assign(kind='direction flipped in last 5 min')]).to_csv(f'{OUT}/bl_lb_hazard.csv', index=False)
rec('lb', R)
