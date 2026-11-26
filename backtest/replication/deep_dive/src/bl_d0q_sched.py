"""D0 step 1b (plan reports/D0_SCHEDULED_PLAN.md): scheduled selling in depth.
T1 timetable per underlying x version (all cycles, descriptive) + half-to-half stability; T2 start / end per cycle and what ends it; T3 attendance of out-of-fold waves while active, skip rate
and single-variable AUCs (MTM, book lots, spot move since the previous wave, distance to the strike midpoint, ATM straddle premium, recent buy-backs); T4 strike candidates
(nearest previous close / minute open / minute close / any ATM within the minute / straddle |CE-PE| / synthetic forward / previous scheduled strike) and the disagreement test;
T5 lots per wave; T6 D0 waves vs D-1 waves of the same group.
Outputs bl_d0q_waves.csv, bl_d0q_startend.csv, bl_d0q_attend.csv, bl_d0q_auc.csv, bl_d0q_strike.csv, bl_d0q_disagree.csv, bl_d0q_d1match.csv, bl_summary_d0q1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from sklearn.metrics import roc_auc_score
src = open('bl_d0s_tt.py').read(); exec(src[:src.index('WALL = waves(D0C)')])
WF = pd.read_pickle(f'{OUT}/bl_d0s_waves_fold.pkl.gz'); ST = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); MTM = pd.read_pickle(f'{OUT}/bl_d0x_mtm.pkl.gz')['MT']; BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz'); Pr1 = pd.read_csv(f'{OUT}/bl_react_pairs.csv')
R = {}; rng = np.random.default_rng(31)
for i in D0C: M[i]['o'] = SP[(CY.iloc[i].und, CY.iloc[i].expiry)].open.values
hms = lambda t: f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}'; GRPS = sorted({GRP(i) for i in D0C})
# ---------------- T1 timetable (all cycles) + stability
WALL = waves(D0C); WALL['clock'] = [hms(t) for t in WALL.t]; WALL['slot_offset_s'] = [(t - 33360) % 900 for t in WALL.t]
att = []
for x in WALL.itertuples():
    act = [i for i in D0C if GRP(i) == (x.und, x.version) and STOP[i] > x.t]; hit = [i for i in act if ((PS[PS.cid == i].t0 - x.t).abs() <= 3).any()]; att.append(len(hit) / max(len(act), 1))
WALL['attendance_all'] = att; WALL.to_csv(f'{OUT}/bl_d0q_waves.csv', index=False)
stab = {}
for g in GRPS:
    a = WF[0][(WF[0].und == g[0]) & (WF[0].version == g[1])].t.values; b = WF[1][(WF[1].und == g[0]) & (WF[1].version == g[1])].t.values
    stab[f'{g[0]} {g[1]}'] = dict(waves_half_a=len(a), waves_half_b=len(b), a_in_b=float(np.mean([np.min(np.abs(b - t)) <= 3 for t in a])) if len(a) and len(b) else np.nan, b_in_a=float(np.mean([np.min(np.abs(a - t)) <= 3 for t in b])) if len(a) and len(b) else np.nan)
R['T1_stability'] = stab; R['T1_waves'] = {f'{g[0]} {g[1]}': int(((WALL.und == g[0]) & (WALL.version == g[1])).sum()) for g in GRPS}
R['T1_first_last'] = {f'{g[0]} {g[1]}': [hms(WALL[(WALL.und == g[0]) & (WALL.version == g[1])].t.min()), hms(WALL[(WALL.und == g[0]) & (WALL.version == g[1])].t.max())] for g in GRPS}
print(R['T1_first_last'], R['T1_stability'])
bkl = {}
for i in D0C:
    ev = [(0.0, sum(1 for L in BK[i]['at_open']))]; cur = ev[0][1]
    e2 = sorted([(t, l) for t, l in zip(S[S.cid == i].tod, S[S.cid == i].lots)] + [(t, -l) for t, l in zip(B[B.cid == i].tod, B[B.cid == i].lots)])
    ts = [0.0]; vs = [cur]
    for t, d in e2: cur += d; ts.append(t); vs.append(cur)
    bkl[i] = (np.array(ts), np.array(vs))
# ---------------- T2 start / end per cycle
# scheduled pairs for the descriptive parts (T2, T4): pair starts within +-3 s of a wave of the cycle's own group (all-cycle timetable); OOF labels are used in T3
wl = {g: WALL[(WALL.und == g[0]) & (WALL.version == g[1])].t.values for g in GRPS}; PS['sched_all'] = [len(wl[GRP(i)]) > 0 and np.min(np.abs(wl[GRP(i)] - t)) <= 3 for i, t in zip(PS.cid, PS.t0)]
key_ = set(zip(PS[PS.sched_all].cid, PS[PS.sched_all].pid)); sched = S[[(c_, p_) in key_ for c_, p_ in zip(S.cid, S.pid)]].copy(); sched['tod'] = sched.t0; R['sched_pairs_all_timetable'] = int(len(key_)); R['sched_lots_all_timetable'] = int(sched.lots.sum()); se = []
for i in D0C:
    g = sched[sched.cid == i]; w = WALL[(WALL.und == CY.iloc[i].und) & (WALL.version == CY.iloc[i].version)]; lastw = w.t.max()
    first = g.tod.min() if len(g) else np.nan; last = g.tod.max() if len(g) else np.nan
    if not len(g): why = 'no scheduled sale (stopped at the open)' if STOP[i] < 34000 else 'no scheduled sale'
    elif STOP[i] < 1e8 and STOP[i] - last < 1800 and STOP[i] < lastw: why = 'cycle stop'
    elif last >= lastw - 3: why = "group's last wave"
    else: why = 'early end: skipped waves ' + ', '.join(hms(t) for t in w.t.values if last < t - 3 and t < min(STOP[i], 1e9))[:60]
    se.append(dict(cid=i, und=CY.iloc[i].und, version=CY.iloc[i].version, expiry=CY.iloc[i].expiry, first_sched=hms(first) if first == first else '-', last_sched=hms(last) if last == last else '-', group_last_wave=hms(lastw), stop=hms(STOP[i]) if STOP[i] < 1e8 else '-', end_reason=why, sched_lots=int(g.lots.sum())))
SE = pd.DataFrame(se); SE.to_csv(f'{OUT}/bl_d0q_startend.csv', index=False); R['T2_end_reasons'] = SE.end_reason.str.split(':').str[0].value_counts().to_dict(); print(SE.to_string(index=False))
# ---------------- early-end diagnostics: state at the first skipped wave vs the same wave in cycles of the group that sold it
ee = []
for r_ in SE[SE.end_reason.str.startswith('early end')].itertuples():
    i = r_.cid; w = wl[GRP(i)]; g = sched[sched.cid == i]; last = g.tod.max(); tw = [t for t in w if t > last + 3 and t < STOP[i]]
    if not tw: continue
    t = tw[0]; j = int((t - 33300) // 60); others = [c_ for c_ in D0C if GRP(c_) == GRP(i) and c_ != i and STOP[c_] > t and ((PS[(PS.cid == c_) & PS.sched_all].t0 - t).abs() <= 3).any()]
    def st_(c_):
        ts, vs = bkl[c_]; return dict(mtm=MTM[c_]['prev_close'][j] / 1e5, book=vs[np.searchsorted(ts, t, 'left') - 1], sells_so_far=int(S[(S.cid == c_) & (S.tod < t)].lots.sum()), bb_so_far=int(B[(B.cid == c_) & (B.tod < t)].lots.sum()))
    a = st_(i); o = pd.DataFrame([st_(c_) for c_ in others]); ee.append(dict(cid=i, expiry=r_.expiry, first_skipped=hms(t), mtm_lakh=a['mtm'], book_lots=a['book'], sells_so_far=a['sells_so_far'], others_n=len(others), others_mtm_range=f"{o.mtm.min():.2f}..{o.mtm.max():.2f}" if len(o) else '-', others_book_range=f"{o.book.min():.0f}..{o.book.max():.0f}" if len(o) else '-', others_sells_range=f"{o.sells_so_far.min():.0f}..{o.sells_so_far.max():.0f}" if len(o) else '-'))
EE = pd.DataFrame(ee); EE.to_csv(f'{OUT}/bl_d0q_earlyend.csv', index=False); print(EE.to_string(index=False))
# ---------------- T3 attendance of OOF waves while active
rows = []
for i in D0C:
    w = WF[i % 2]; w = w[(w.und == CY.iloc[i].und) & (w.version == CY.iloc[i].version)].sort_values('t'); m = M[i]; prev_t = None
    for x in w.itertuples():
        if x.t >= STOP[i]: break
        j = int((x.t - 33300) // 60); c0 = m['c'][j - 1] if j > 0 else m['c'][0]; K = m['K']; a = float(K[np.argmin(np.abs(K - c0))]); ki = m['ki']
        ex = bool(((PS[PS.cid == i].t0 - x.t).abs() <= 3).any()); ts, vs = bkl[i]; book = vs[np.searchsorted(ts, x.t, 'left') - 1]
        jp = int((prev_t - 33300) // 60) if prev_t else 0; strad = (m['op'][('CE', 'close')][ki[int(a)], max(j - 1, 0)] + m['op'][('PE', 'close')][ki[int(a)], max(j - 1, 0)]) if int(a) in ki else np.nan
        bb5 = int(B[(B.cid == i) & (B.tod >= x.t - 300) & (B.tod < x.t)].lots.sum())
        rows.append(dict(cid=i, und=CY.iloc[i].und, version=CY.iloc[i].version, t=x.t, hour=int(x.t // 3600), executed=int(ex), mtm_lakh=MTM[i]['prev_close'][j] / 1e5, book_lots=book, spot_move_since_prev_wave=abs(c0 - m['c'][max(jp - 1, 0)]) / m['step'],
                         dist_to_strike=abs(c0 - a) / m['step'], straddle_over_step=strad / m['step'], bb_lots_prev5=bb5))
        prev_t = x.t
A = pd.DataFrame(rows); A.to_csv(f'{OUT}/bl_d0q_attend.csv', index=False); A['skipped'] = 1 - A.executed
R['T3_attendance'] = A.groupby(['und', 'version']).executed.mean().round(3).to_dict(); R['T3_attendance'] = {f'{a} {b}': v for (a, b), v in R['T3_attendance'].items()}; R['T3_attendance_all'] = float(A.executed.mean()); R['T3_by_hour'] = A.groupby('hour').executed.mean().round(3).to_dict()
au = []
for v in ('mtm_lakh', 'book_lots', 'spot_move_since_prev_wave', 'dist_to_strike', 'straddle_over_step', 'bb_lots_prev5'):
    y = A.skipped.values; p = A[v].values; ok = np.isfinite(p); u = A.cid.unique(); idx = {c_: np.where((A.cid.values == c_) & ok)[0] for c_ in u}; bs = []
    for _ in range(500):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))])
        if y[k].min() != y[k].max(): bs.append(roc_auc_score(y[k], p[k]))
    h0 = ok & (A.cid % 2 == 0).values; h1 = ok & (A.cid % 2 == 1).values
    au.append(dict(variable=v, AUC_skip=roc_auc_score(y[ok], p[ok]), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5), AUC_half_even=roc_auc_score(y[h0], p[h0]) if y[h0].min() != y[h0].max() else np.nan, AUC_half_odd=roc_auc_score(y[h1], p[h1]) if y[h1].min() != y[h1].max() else np.nan))
AU = pd.DataFrame(au); AU.to_csv(f'{OUT}/bl_d0q_auc.csv', index=False); print('attendance', R['T3_attendance'], R['T3_attendance_all']); print(AU.round(3).to_string(index=False))
# ---------------- T4 strike candidates (one row per scheduled pair)
pp = sched.sort_values('tod').groupby(['cid', 'pid', 'tod', 'strike'], as_index=False).lots.sum(); pp = pp.drop_duplicates(['cid', 'pid']); rows = []; prevk = {}
for q in pp.sort_values(['cid', 'tod']).itertuples():
    i = q.cid; m = M[i]; K = m['K']; ki = m['ki']; j = int((q.tod - 33300) // 60); c_prev = m['c'][j - 1] if j > 0 else m['c'][0]; near = lambda x: float(K[np.argmin(np.abs(K - x))])
    o_ = m['o'][j] if 'o' in m else np.nan
    cand = dict(prev_close=near(c_prev), minute_open=near(o_) if o_ == o_ else np.nan, minute_close=near(m['c'][j]))
    lo_, hi_ = m['l'][j], m['h'][j]; cand['any_atm_in_minute'] = q.strike if (near(lo_) <= q.strike <= near(hi_)) else np.nan
    ce = m['op'][('CE', 'close')][:, max(j - 1, 0)]; pe = m['op'][('PE', 'close')][:, max(j - 1, 0)]; ok = np.isfinite(ce) & np.isfinite(pe)
    cand['straddle_min_abs_ce_pe'] = float(K[ok][np.argmin(np.abs(ce[ok] - pe[ok]))]) if ok.any() else np.nan
    a = cand['prev_close']; fw = a + ce[ki[int(a)]] - pe[ki[int(a)]] if int(a) in ki and np.isfinite(ce[ki[int(a)]]) and np.isfinite(pe[ki[int(a)]]) else np.nan; cand['synthetic_forward'] = near(fw) if fw == fw else np.nan
    cand['previous_sched_strike'] = prevk.get(i, np.nan); prevk[i] = q.strike
    rows.append(dict(cid=i, tod=q.tod, strike=q.strike, lots=q.lots, mid_frac=abs(c_prev - a) / m['step'], fwd_minus_spot=(fw - c_prev) / m['step'] if fw == fw else np.nan, **{f'c_{k}': v for k, v in cand.items()}))
TK = pd.DataFrame(rows)
for k in [c_ for c_ in TK.columns if c_.startswith('c_')]: TK[f'hit_{k[2:]}'] = (TK[k] == TK.strike).astype(float).where(TK[k].notna())
sk = pd.DataFrame([dict(candidate=k[4:], exact_share=float(TK[k].mean()), n=int(TK[k].notna().sum())) for k in TK.columns if k.startswith('hit_')]); sk.to_csv(f'{OUT}/bl_d0q_strike.csv', index=False); print(sk.round(3).to_string(index=False))
dis = []
for alt in ('straddle_min_abs_ce_pe', 'synthetic_forward', 'minute_open'):
    d = TK[TK[f'c_{alt}'].notna() & (TK[f'c_{alt}'] != TK.c_prev_close)]; dis.append(dict(alternative=alt, pairs_where_they_disagree=len(d), real_equals_prev_close=float((d.strike == d.c_prev_close).mean()) if len(d) else np.nan, real_equals_alternative=float((d.strike == d[f'c_{alt}']).mean()) if len(d) else np.nan, neither=float(((d.strike != d.c_prev_close) & (d.strike != d[f'c_{alt}'])).mean()) if len(d) else np.nan))
DI = pd.DataFrame(dis); DI.to_csv(f'{OUT}/bl_d0q_disagree.csv', index=False); print(DI.round(3).to_string(index=False))
miss = TK[TK.hit_prev_close == 0]; R['T4_misses'] = dict(n=len(miss), share=float(len(miss) / len(TK)), mid_frac_q=miss.mid_frac.quantile([.25, .5, .75]).tolist(), all_mid_frac_q=TK.mid_frac.quantile([.25, .5, .75]).tolist(), miss_equals_minute_close=float((miss.strike == miss.c_minute_close).mean()) if len(miss) else np.nan,
                                    miss_any_atm_in_minute=float(miss.hit_any_atm_in_minute.mean()) if len(miss) else np.nan, miss_equals_previous_sched=float((miss.strike == miss.c_previous_sched_strike).mean()) if len(miss) else np.nan)
TK.to_csv(f'{OUT}/bl_d0q_pairs.csv', index=False); print(R['T4_misses'])
# ---------------- T5 lots per wave
R['T5_lots_per_wave'] = WALL.groupby(['und', 'version']).lots.apply(lambda s: s.value_counts().to_dict()).to_dict(); R['T5_lots_per_wave'] = {f'{a} {b} lots={c}': int(v) for (a, b, c), v in R['T5_lots_per_wave'].items()}
R['T5_waves_per_slot'] = WALL.assign(slot=((WALL.t - 33360) // 900).astype(int)).groupby(['und', 'version', 'slot']).size().groupby(['und', 'version']).median().to_dict(); R['T5_waves_per_slot'] = {f'{a} {b}': float(v) for (a, b), v in R['T5_waves_per_slot'].items()}
# ---------------- T6 D-1 waves per group vs D0 waves
CYi = {(r.und, r.expiry): i for i, r in enumerate(CY.itertuples())}; p1 = Pr1[Pr1.sched].copy(); p1['cid'] = [CYi.get((u, e)) for u, e in zip(p1.und, p1.expiry)]; p1 = p1.dropna(subset=['cid']); p1['cid'] = p1.cid.astype(int)
def waves_d1(cids):
    out = []
    for g in sorted({GRP(i) for i in cids}):
        tc = [i for i in cids if GRP(i) == g]; pool = {i: sorted(p1[p1.cid == i].te.tolist()) for i in tc}
        while True:
            best = None
            for t in sorted({round(t) for i in tc for t in pool[i]}):
                hits = {i: min(pool[i], key=lambda x: abs(x - t)) for i in tc if pool[i] and min(abs(x - t) for x in pool[i]) <= 3}
                if best is None or len(hits) > len(best[1]): best = (t, hits)
            if best is None or len(best[1]) / len(tc) < 0.5 or len(best[1]) < 2: break
            for i, x in best[1].items(): pool[i].remove(x)
            out.append(dict(und=g[0], version=g[1], t=float(np.median(list(best[1].values())))))
    return pd.DataFrame(out)
W1 = waves_d1(sorted(p1.cid.unique())); mt_ = []
for g in GRPS:
    a = WALL[(WALL.und == g[0]) & (WALL.version == g[1])].t.values; b = W1[(W1.und == g[0]) & (W1.version == g[1])].t.values
    mt_.append(dict(group=f'{g[0]} {g[1]}', D0_waves=len(a), D1_waves=len(b), D0_waves_matching_a_D1_wave=float(np.mean([len(b) and np.min(np.abs(b - t)) <= 3 for t in a])) if len(a) else np.nan, D1_waves_matching_a_D0_wave=float(np.mean([len(a) and np.min(np.abs(a - t)) <= 3 for t in b])) if len(b) else np.nan,
                    D1_first_last=f'{hms(b.min())}–{hms(b.max())}' if len(b) else '-', D0_first_last=f'{hms(a.min())}–{hms(a.max())}' if len(a) else '-'))
MT6 = pd.DataFrame(mt_); MT6.to_csv(f'{OUT}/bl_d0q_d1match.csv', index=False); W1.to_csv(f'{OUT}/bl_d0q_d1waves.csv', index=False); print(MT6.to_string(index=False))
R['T4_strike'] = sk.round(4).to_dict('records'); R['T3_auc'] = AU.round(4).to_dict('records'); R['T6'] = MT6.to_dict('records'); rec('d0q1', R)
