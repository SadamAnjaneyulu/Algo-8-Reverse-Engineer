"""Sizing study step 3 (plan tests 3-7): classification of every D-1 body sold lot (scheduled-cell / reactive pair / solo), build-up through D-1, solo sells in between, replacement test, state-dependence and change-date checks.
Outputs bl_size_lot_classes.csv, bl_size_class_cycle.csv, bl_size_buildup.csv, bl_size_solo_hour.csv, bl_size_state.csv, bl_size_notional_dates.csv, bl_summary_size3.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy import stats
rng = np.random.default_rng(83); R = {}; O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); Cc = pd.read_csv(f'{OUT}/bl_size_cells.csv'); P = pd.read_csv(f'{OUT}/bl_size_pairs.csv'); B0 = pd.read_csv(f'{OUT}/bl_book_panel.csv.gz', usecols=['und', 'expiry', 'day', 'j', 'B_total'])
S = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)].copy(); S['k'] = ((S.tod - 33360 + 30) // 900).astype(int); S['off'] = (S.tod - 33360 + 30) % 900 - 30; S = S.merge(CY[['und', 'expiry', 'version']], on=['und', 'expiry'], how='inner')
pairset = set(); 
for r in P[P.day == 'D-1'].itertuples(): pairset.add((r.und, r.expiry, r.te))
def incell(r):
    c = Cc[(Cc.version == r.version) & (Cc.k == r.k) & (r.off >= Cc.lo - 3) & (r.off <= Cc.hi + 3)]; return len(c) > 0
S['sched'] = [incell(r) for r in S.itertuples()]; S['paired'] = [((r.und, r.expiry, r.te) in pairset) for r in S.itertuples()]
# pair membership: CE side te in pairset; mark PE partner by matching strike & +-3 s
pe_partner = set()
for r in P[P.day == 'D-1'].itertuples(): pe_partner.add((r.und, r.expiry, r.strike, round(r.te)))
S['cls3'] = np.where(S.sched, 'scheduled cell', np.where(S.paired | S.apply(lambda r: any((r.und, r.expiry, int(r.strike), round(r.te) + d) in pe_partner for d in range(-3, 4)) if r.cp == 'PE' else False, axis=1), 'reactive pair (outside timetable)', 'solo'))
S[['und', 'expiry', 'cp', 'strike', 'te', 'tod', 'lots', 'k', 'off', 'version', 'cls3']].to_csv(f'{OUT}/bl_size_lot_classes.csv', index=False)
cc = S.groupby(['und', 'expiry', 'version', 'cls3']).lots.sum().unstack(fill_value=0).reset_index(); cc['total'] = cc[['scheduled cell', 'reactive pair (outside timetable)', 'solo']].sum(axis=1); cc.to_csv(f'{OUT}/bl_size_class_cycle.csv', index=False)
print('D-1 sold lots per cycle by class (mean / median / min / max), n cycles', len(cc)); print(cc.groupby('version')[['scheduled cell', 'reactive pair (outside timetable)', 'solo', 'total']].agg(['mean', 'median', 'min', 'max']).round(1).T.to_string()); R['class_total'] = S.groupby('cls3').lots.sum().to_dict(); R['class_per_cycle_mean'] = {k: float(cc[k].mean()) for k in ('scheduled cell', 'reactive pair (outside timetable)', 'solo', 'total')}; R['class_per_cycle_median'] = {k: float(cc[k].median()) for k in ('scheduled cell', 'reactive pair (outside timetable)', 'solo', 'total')}; R['ncycles'] = len(cc)
sc = S[S.cls3 == 'solo']; R['solo_by_right'] = sc.groupby('cp').lots.sum().to_dict(); R['solo_1lot_orders'] = float((sc.lots == 1).mean()); R['solo_orders'] = len(sc)
# multi-lot bursts: >= 2 solo orders at the same strike/right within 3 s
sc = sc.sort_values(['und', 'expiry', 'cp', 'strike', 'te']); g = sc.groupby(['und', 'expiry', 'cp', 'strike']).te.diff(); sc['burst'] = ((g.isna()) | (g > 3)).cumsum(); bs = sc.groupby('burst').lots.sum(); R['solo_bursts'] = len(bs); R['solo_burst_size_q'] = bs.quantile([.5, .75, .9, 1]).tolist(); R['solo_single_lot_burst_share'] = float((bs == 1).mean())
print(f"\nsolo sells: {R['solo_orders']} orders / {R['class_total'].get('solo', 0)} lots; CE {R['solo_by_right'].get('CE', 0)} PE {R['solo_by_right'].get('PE', 0)}; bursts {R['solo_bursts']} (lots per burst q50/75/90/max {bs.quantile([.5, .75, .9, 1]).tolist()}; single-lot bursts {R['solo_single_lot_burst_share']:.2f})")
S['hour'] = (S.tod // 3600).astype(int); H = S.groupby(['hour', 'cls3']).lots.sum().unstack(fill_value=0) / len(cc); H.round(2).to_csv(f'{OUT}/bl_size_solo_hour.csv'); print('\nmean D-1 lots per cycle by clock hour and class:'); print(H.round(2).to_string())
# ---- build-up: cumulative body short lots (sold - covered, body only) at clock marks
cv = O[(O.module == 'num') & (O.role == 'cover_short') & (O.dayno == 0)]; rows = []
for (u, e), g in S.groupby(['und', 'expiry']):
    gc = cv[(cv.und == u) & (cv.expiry == e)]
    for hh in (10, 11, 12, 13, 14, 15, 15.5):
        t = hh * 3600; rows.append((u, e, g.version.iloc[0], hh, g[g.tod < t].lots.sum(), g[(g.tod < t) & (g.cls3 == 'scheduled cell')].lots.sum(), gc[gc.tod < t].lots.sum()))
BU = pd.DataFrame(rows, columns=['und', 'expiry', 'version', 'clock_hour', 'sold', 'sold_scheduled', 'bought_back']); BU['net_short_body'] = BU.sold - BU.bought_back; BU.to_csv(f'{OUT}/bl_size_buildup.csv', index=False)
bt = BU.groupby('clock_hour')[['sold', 'sold_scheduled', 'bought_back', 'net_short_body']].median().round(1); print('\nbuild-up, median across cycles (body lots, both rights): sold / of which scheduled / bought back / net short'); print(bt.to_string()); R['buildup_median'] = bt.reset_index().to_dict('list')
# ---- replacement test: do non-scheduled sells follow a body buy-back within 60 s? (same cycle, any strike/right)
obs = []; nul = []
for (u, e), g in S[S.cls3 != 'scheduled cell'].groupby(['und', 'expiry']):
    cb = cv[(cv.und == u) & (cv.expiry == e)].te.values
    if len(cb) == 0: continue
    te = g.te.values; allt = S[(S.und == u) & (S.expiry == e)].te.values; lo, hi = allt.min(), allt.max(); span = max(hi - lo, 1)
    f = lambda tt: np.mean([((tt_ - cb > 0) & (tt_ - cb <= 60)).any() for tt_ in tt]); obs.append((f(te), len(te))); nul.append((np.mean([f(lo + ((te - lo + rng.uniform(0, span)) % span)) for _ in range(20)]), len(te)))
w = np.array([x[1] for x in obs]); R['replace_within60'] = [float(np.average([x[0] for x in obs], weights=w)), float(np.average([x[0] for x in nul], weights=w)), int(w.sum())]; print(f"\nnon-scheduled sells within 60 s AFTER a body buy-back: observed {R['replace_within60'][0]:.3f} vs shifted-time null {R['replace_within60'][1]:.3f} (n={R['replace_within60'][2]})")
# lots-sold-after vs lots-bought-back in 60 s windows
x = []
for (u, e), g in S.groupby(['und', 'expiry']):
    gc = cv[(cv.und == u) & (cv.expiry == e)]; ns = g[g.cls3 != 'scheduled cell']
    for t0 in sorted(set((gc.te // 60).astype(int))):
        b = gc[(gc.te // 60).astype(int) == t0].lots.sum(); a = ns[(ns.te // 60).astype(int) == t0 + 1].lots.sum(); x.append((b, a))
X = np.array(x); R['replace_corr'] = [float(stats.spearmanr(X[:, 0], X[:, 1])[0]), len(X)]; print(f"buy-back minutes: Spearman(lots bought back in minute m, non-scheduled lots sold in minute m+1) = {R['replace_corr'][0]:.3f} (n={len(X)})")
# ---- state dependence of the scheduled total (cycle level) and notional / date checks
TOT = pd.read_csv(f'{OUT}/bl_size_scheduled_totals.csv'); ST = TOT.merge(cc[['und', 'expiry', 'solo', 'reactive pair (outside timetable)']], on=['und', 'expiry']); ST['sched_total'] = ST.ce + ST.pe; ST['d1'] = pd.to_datetime(ST.d1)
from bl_greeks import surface
ch = Chain(); iv0 = []; stm = []
for r in ST.itertuples():
    c = ch.cyc(r.und, r.expiry); K = np.array(c['strikes'], dtype=float); sp = float(c[(0, 'spot')][1]); k = np.argmin(np.abs(K - sp)); stm.append(float(c[(0, 'CE', 'close')][k, 1] + c[(0, 'PE', 'close')][k, 1]) / sp * 100)
ST['straddle_pct_open'] = stm; ST['spot_chg_d1_pct'] = [float((lambda c: c[(0, 'spot')][np.isfinite(c[(0, 'spot')])][-1] / c[(0, 'spot')][1] - 1)(ch.cyc(r.und, r.expiry)) * 100) for r in ST.itertuples()]
ST.to_csv(f'{OUT}/bl_size_state.csv', index=False); rows = []
for tgt in ('sched_total', 'solo', 'reactive pair (outside timetable)'):
    for f in ('notional_per_lot', 'spot_d1_open', 'straddle_pct_open', 'spot_chg_d1_pct'):
        for sub, Z in (('all', ST), ('NIFTY', ST[ST.und == 'NIFTY']), ('SENSEX', ST[ST.und == 'SENSEX'])):
            rho, p = stats.spearmanr(Z[f], Z[tgt]); null = [stats.spearmanr(Z[f], rng.permutation(Z[tgt].values))[0] for _ in range(300)]; rows.append((tgt, f, sub, len(Z), rho, p, np.mean(np.abs(null) >= abs(rho))))
SD = pd.DataFrame(rows, columns=['target', 'state_variable', 'subset', 'n', 'spearman', 'p', 'perm_p']); SD.round(3).to_csv(f'{OUT}/bl_size_state_tests.csv', index=False); print('\nstate dependence (Spearman across cycles); smallest p per target:'); print(SD.sort_values('perm_p').groupby('target').head(3).round(3).to_string(index=False)); R['state_tests'] = SD.round(4).to_dict('list')
ND = ST[['und', 'expiry', 'd1', 'version', 'notional_per_lot']].sort_values('d1'); ND['notional_lakh'] = (ND.notional_per_lot / 1e5).round(2); ND.to_csv(f'{OUT}/bl_size_notional_dates.csv', index=False); print('\nnotional per lot (lakh) around the version change (sorted by D-1 date):'); print(ND[(ND.d1 >= '2026-08-24') & (ND.d1 <= '2026-10-01')][['d1', 'und', 'version', 'notional_lakh']].to_string(index=False))
R['first_below_15L_d1'] = str(ND[ND.notional_per_lot < 1.5e6].d1.min().date()) if (ND.notional_per_lot < 1.5e6).any() else None; R['v1_notional_lakh_range'] = [float(ND[ND.version == 'V1'].notional_lakh.min()), float(ND[ND.version == 'V1'].notional_lakh.max())]; R['v2_notional_lakh_range'] = [float(ND[ND.version == 'V2'].notional_lakh.min()), float(ND[ND.version == 'V2'].notional_lakh.max())]
rec('size3', R)
