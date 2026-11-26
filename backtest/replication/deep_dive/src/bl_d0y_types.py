"""D0 buy-back reasons (plan reports/D0_BB_TYPES_PLAN.md). Every D0 body buy-back lot gets one type by a fixed precedence:
1 cycle-stop window, 2 clearance (>= 15:10), 3 stop-loss (minute high >= 1.4 x entry), 4 take-profit (minute low <= 0.1 x entry), 5 partner (other-right stop-loss buy-back, same strike, +-60 s),
6 roll-out (same-right body sale within 60 s after), 7 burst member (>= 5 lots, same right, gaps <= 30 s), 8 other. Chance levels for 5 and 6: partner / sale times shifted +-10 min.
Q1 ratio shares, Q2 holding time of scheduled-straddle lots vs shifted-time null, Q3 clock association, Q4 'other'.
Outputs bl_d0y_lots.pkl.gz, bl_d0y_types.csv, bl_d0y_chance.csv, bl_d0y_overlap.csv, bl_d0y_hours.csv, bl_d0y_hold.csv, bl_d0y_sens.csv, bl_summary_d0y1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); X = pd.read_pickle(f'{OUT}/bl_d0b_removed.pkl.gz'); P = pd.read_pickle(f'{OUT}/bl_d0b_panel.pkl.gz'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); rng = np.random.default_rng(37); R = {}
STOP = {}
for i in sorted(X.cid.unique()):
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 's_')]; STOP[i] = float(z.tod.min()) if len(z) else 1e9
# minute high / low ratios of the lot's own contract at the buy-back minute (panel rows exist while the lot is open before 15:10 and the stop)
Pk = P.set_index(['lid', 'j'])[['rh', 'rl']]; key = list(zip(X.lid, X.j)); idx = Pk.index; ok = [k in idx for k in key]
X['rh'] = np.nan; X['rl'] = np.nan; sel = Pk.reindex(key); X['rh'] = sel.rh.values; X['rl'] = sel.rl.values
# lots outside the panel scope (>= 15:10 or after the stop) keep rh/rl missing: they are types 1-2 by precedence anyway
X['held_min'] = np.where(X.entry_day == 1, (X.tod - X.entry_tod) / 60, np.nan); X['stopped'] = [t >= STOP[c] for c, t in zip(X.cid, X.tod)]
def stop_flag(th): return (X.rh >= th)
def classify(th_sl=1.4, th_tp=0.1, shift=0):
    t = np.full(len(X), '', dtype=object); done = np.zeros(len(X), bool)
    def put(mask, nm):
        m = mask & ~done; t[m] = nm; done[m] = True
    put(X.stopped.values, '1 cycle-stop window'); put((X.tod >= 54600 + 0).values & (X.tod < 54840).values, '2a clearance 15:10-15:13'); put(((X.tod >= 54840) & (X.tod < 54900)).values, '2b clearance 15:14'); put((X.tod >= 54900).values, '2c clearance 15:15+')
    sl = (X.rh >= th_sl).values; put(sl, '3 stop-loss'); put((X.rl <= th_tp).values, '4 take-profit')
    # partner: other-right stop-loss lot, same strike, within +-60 s (partner times shifted by `shift` s for the chance level)
    SLl = X[sl & ~X.stopped.values]; pm = np.zeros(len(X), bool)
    for i, g in X.groupby('cid'):
        s = SLl[SLl.cid == i]
        if not len(s): continue
        for ix, q in zip(g.index, g.itertuples()):
            o = s[(s.cp != q.cp) & (s.strike == q.strike)]
            if len(o) and ((o.tod + shift - q.tod).abs() <= 60).any(): pm[X.index.get_loc(ix)] = True
    put(pm, '5 partner')
    rm = np.zeros(len(X), bool)
    for i, g in X.groupby('cid'):
        s = S[S.cid == i]; st = s.tod.values; sc = s.cp.values
        for ix, q in zip(g.index, g.itertuples()):
            m = (sc == q.cp) & (st > q.tod + shift) & (st <= q.tod + shift + 60)
            if m.any(): rm[X.index.get_loc(ix)] = True
    put(rm, '6 roll-out')
    return t, done, pm, rm, sl
X = X.reset_index(drop=True); t, done, pm, rm, sl = classify()
# burst membership (same cycle and right, gap <= 30 s, >= 5 lots) applied after types 1-6
bu = np.zeros(len(X), bool)
for (i, cp), g in X.groupby(['cid', 'cp']):
    g = g.sort_values('tod'); gid = (g.tod.diff().fillna(1e9) > 30).cumsum()
    for _, x in g.groupby(gid):
        if len(x) >= 5: bu[x.index.values] = True
m7 = bu & (t == ''); t[m7] = '7 burst member'; t[t == ''] = '8 other'; X['type'] = t
# chance levels for partner / roll-out among lots reaching the rule
ch = []
for nm, fn in (('5 partner', 'pm'), ('6 roll-out', 'rm')):
    reach = ~X.type.isin(['1 cycle-stop window', '2a clearance 15:10-15:13', '2b clearance 15:14', '2c clearance 15:15+', '3 stop-loss', '4 take-profit']) if fn == 'pm' else ~X.type.isin(['1 cycle-stop window', '2a clearance 15:10-15:13', '2b clearance 15:14', '2c clearance 15:15+', '3 stop-loss', '4 take-profit', '5 partner'])
    real = (X.type == nm).sum() / reach.sum(); nl = []; nl15 = []
    for sh in (600, -600):
        tt, dd, p2, r2, s2 = classify(shift=sh); nl.append(((p2 if fn == 'pm' else r2) & reach.values & (~(p2) if fn == 'rm' else True)).sum() / reach.sum())
    for sh in (900, -900):
        tt, dd, p2, r2, s2 = classify(shift=sh); nl15.append(((p2 if fn == 'pm' else r2) & reach.values & (~(p2) if fn == 'rm' else True)).sum() / reach.sum())
    ch.append(dict(type=nm, lots_reaching_rule=int(reach.sum()), share_flagged=real, chance_shift10min=float(np.mean(nl)), chance_shift15min_clock_kept=float(np.mean(nl15)), ratio_vs_10min=real / max(np.mean(nl), 1e-9), ratio_vs_15min=real / max(np.mean(nl15), 1e-9)))
CH = pd.DataFrame(ch); CH.to_csv(f'{OUT}/bl_d0y_chance.csv', index=False); print(CH.round(3).to_string(index=False))
# ---------------- per-type table
ORDER = sorted(X.type.unique()); rows = []
for nm in ORDER:
    g = X[X.type == nm]; q = g.ratio.quantile([.1, .25, .5, .75, .9]).tolist(); hq = g.held_min.quantile([.25, .5, .75]).tolist() if g.held_min.notna().any() else [np.nan] * 3
    rows.append(dict(type=nm, lots=len(g), share=len(g) / len(X), cycles=int(g.cid.nunique()), ratio_q10=q[0], ratio_q25=q[1], ratio_median=q[2], ratio_q75=q[3], ratio_q90=q[4], share_in_loss=float((g.ratio > 1).mean()), held_min_q25=hq[0], held_min_median=hq[1], held_min_q75=hq[2],
                     carried_from_D1=float((g.origin == 'D-1').mean()), CE_share=float((g.cp == 'CE').mean()), median_time=(lambda x: f'{int(x // 3600):02d}:{int(x % 3600 // 60):02d}')(g.tod.median())))
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/bl_d0y_types.csv', index=False); print(T.round(2).to_string(index=False))
H = X.assign(hour=(X.tod // 3600).astype(int)).pivot_table(index='hour', columns='type', values='lid', aggfunc='size').fillna(0).astype(int); H.to_csv(f'{OUT}/bl_d0y_hours.csv')
E = X.pivot_table(index='type', columns='typ', values='lid', aggfunc='size').fillna(0).astype(int); E.to_csv(f'{OUT}/bl_d0y_entrymix.csv'); print(E.to_string())
# overlap of flags (before precedence)
fl = pd.DataFrame(dict(stop_window=X.stopped, clearance=X.tod >= 54600, stop_loss=sl, take_profit=(X.rl <= 0.1), partner=pm, roll_out=rm, burst=bu)); ov = pd.DataFrame([[int((fl[a] & fl[b]).sum()) for b in fl] for a in fl], index=fl.columns, columns=fl.columns); ov.to_csv(f'{OUT}/bl_d0y_overlap.csv')
# sensitivity of the stop-loss threshold (lots in scope only)
sens = []
for th in (1.2, 1.4, 1.6):
    tt, *_ = classify(th_sl=th); s = pd.Series(tt).value_counts(); sens.append(dict(threshold=th, stop_loss=int(s.get('3 stop-loss', 0)), take_profit=int(s.get('4 take-profit', 0)), partner=int(s.get('5 partner', 0)), roll_out=int(s.get('6 roll-out', 0)), other=int(s.get('8 other', 0)) + int(s.get('7 burst member', 0))))
SE = pd.DataFrame(sens); SE.to_csv(f'{OUT}/bl_d0y_sens.csv', index=False); print(SE.to_string(index=False))
# ---------------- Q1 ratio shares by type (lots in panel scope: rh available)
q1 = []
for nm in ['ALL'] + ORDER:
    g = X if nm == 'ALL' else X[X.type == nm]; q1.append(dict(type=nm, lots=len(g), ratio_ge_1p2=float((g.ratio >= 1.2).mean()), ratio_ge_1p4=float((g.ratio >= 1.4).mean()), ratio_ge_1p6=float((g.ratio >= 1.6).mean()), ratio_lt_1=float((g.ratio < 1).mean()), ratio_lt_0p25=float((g.ratio < .25).mean())))
Q1 = pd.DataFrame(q1); Q1.to_csv(f'{OUT}/bl_d0y_q1.csv', index=False); print(Q1.round(3).to_string(index=False))
# ---------------- Q2 holding time of scheduled-straddle lots (entry typ scheduled on D-1, grid_pair / offgrid_pair on D0) vs shifted-time null
sch = X[(X.typ.isin(['grid_pair', 'offgrid_pair'])) & (X.entry_day == 1) & ~X.stopped & (X.tod < 54600)].copy(); sch['hold'] = (sch.tod - sch.entry_tod) / 60
bins = [0, 1, 2, 3, 5, 7, 10, 15, 20, 30, 45, 60, 90, 120, 180, 300, 500]; real = np.histogram(sch.hold, bins)[0]; null = []
for _ in range(500):
    sh = rng.uniform(1, 15, len(sch)) * 60 * rng.choice([-1, 1], len(sch)); null.append(np.histogram((sch.tod + sh - sch.entry_tod) / 60, bins)[0])
null = np.array(null); HD = pd.DataFrame(dict(hold_min=[f'{a}-{b}' for a, b in zip(bins[:-1], bins[1:])], lots=real, null_mean=null.mean(0), null_p95=np.percentile(null, 95, axis=0))); HD['ratio'] = HD.lots / HD.null_mean.clip(lower=1e-9); HD.to_csv(f'{OUT}/bl_d0y_hold.csv', index=False); print(HD.round(2).to_string(index=False))
R['q2_lots'] = int(len(sch)); R['q2_bins_above_2x_p95'] = HD[(HD.lots > 2 * HD.null_p95) & (HD.lots >= 20)].hold_min.tolist()
# exact holding durations in whole minutes (+-3 s): 5, 10, 15, 30 ...
dm = {k: float((np.abs(sch.hold * 60 - k * 60) <= 3).mean()) for k in (5, 10, 15, 20, 30, 45, 60)}; R['q2_exact_hold_share'] = dm
# ---------------- Q3 clock association
five = (X.tod - 33300) % 300; R['q3_in_133s_after_5min_mark'] = float(((five <= 133) | (five >= 297)).mean()); R['q3_uniform_expectation'] = (133 + 3) / 300; R['q3_second_00'] = float(((X.tod % 60).round() % 60 == 0).mean())
mk = ((X.tod - 33300) // 60) % 15; R['q3_block_minute_hist'] = {int(k): float(v) for k, v in mk.value_counts(normalize=True).sort_index().items()}
R['types'] = T.round(4).to_dict('records'); R['chance'] = CH.round(4).to_dict('records'); R['q1'] = Q1.round(4).to_dict('records'); R['sens'] = SE.to_dict('records'); X.to_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); # roll-out with non-scheduled sales only (sales whose pair label is not grid_pair / offgrid_pair)
Sns = S[S.lab == 'solo']; rm2 = np.zeros(len(X), bool)
for i, g in X.groupby('cid'):
    s_ = Sns[Sns.cid == i]; st = s_.tod.values; sc = s_.cp.values
    for ix, q in zip(g.index, g.itertuples()):
        if ((sc == q.cp) & (st > q.tod) & (st <= q.tod + 60)).any(): rm2[ix] = True
reach6 = ~X.type.isin(['1 cycle-stop window', '2a clearance 15:10-15:13', '2b clearance 15:14', '2c clearance 15:15+', '3 stop-loss', '4 take-profit', '5 partner']).values
ch15 = []
for sh in (900, -900):
    rm3 = np.zeros(len(X), bool)
    for i, g in X.groupby('cid'):
        s_ = Sns[Sns.cid == i]; st = s_.tod.values; sc = s_.cp.values
        for ix, q in zip(g.index, g.itertuples()):
            if ((sc == q.cp) & (st > q.tod + sh) & (st <= q.tod + sh + 60)).any(): rm3[ix] = True
    ch15.append(float((rm3 & reach6).sum() / reach6.sum()))
R['rollout_solo_sales_only'] = dict(share=float((rm2 & reach6).sum() / reach6.sum()), chance_15min=float(np.mean(ch15)), chance_15min_each=ch15)
rec('d0y1', R); print({k: v for k, v in R.items() if k.startswith('q') or k.startswith('roll')})
