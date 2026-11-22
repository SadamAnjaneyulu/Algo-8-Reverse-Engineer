"""D0 counter-sells (plan reports/D0_COUNTER_PLAN.md). Events = stop-loss buy-back lots (reason 3, bl_d0y_lots.pkl.gz) on one right in one cycle and minute; counter-sells = solo sales (bl_d0s_orders lab == 'solo') on the other right.
C1 rate by buy-back reason vs shifted nulls (+-10 min, +-15 min); C2 lag histogram; C3 minute panel within adverse-move bins (common-cause test); C4 quantity; C5 strike / price; C6 which events trigger sales (AUC).
Outputs bl_d0k_c1.csv, bl_d0k_c2.csv, bl_d0k_c3.csv, bl_d0k_c4.csv, bl_d0k_c5.csv, bl_d0k_c6.csv, bl_summary_d0k1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); O = load_orders()
rng = np.random.default_rng(53); R = {}; SO = S[S.lab == 'solo'].copy(); other = lambda c: 'PE' if c == 'CE' else 'CE'
STOP = {}
for i in sorted(X.cid.unique()):
    r = CY.iloc[i]; z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 's_')]; STOP[i] = float(z.tod.min()) if len(z) else 1e9
ev = X.groupby(['cid', 'cp', 'tod']).agg(lots=('lid', 'size'), type=('type', lambda s: s.value_counts().idxmax()), ratio=('ratio', 'median'), strike=('strike', 'median'), px=('px', 'median'), j=('j', 'min')).reset_index()
def rate(evs, lo, hi, shift=0):
    n = 0; k = 0
    for r in evs.itertuples():
        s = SO[(SO.cid == r.cid) & (SO.cp == other(r.cp))]; d = s.tod.values - (r.tod + shift); m = (d >= lo) & (d <= hi); n += int(m.sum()); k += int(m.any())
    return n / max(len(evs), 1), k / max(len(evs), 1)
# ---------------- C1
c1 = []
for ty in sorted(ev.type.unique()):
    g = ev[ev.type == ty]; a, p = rate(g, -90, 90); n10 = np.mean([rate(g, -90, 90, s)[0] for s in (600, -600)]); n15 = np.mean([rate(g, -90, 90, s)[0] for s in (900, -900)]); a2, p2 = rate(g, 0, 60); p2n = np.mean([rate(g, 0, 60, s)[1] for s in (900, -900)])
    c1.append(dict(reason=ty, events=len(g), sales_per_event=a, null_10min=n10, null_15min_clock_kept=n15, ratio_vs_10=a / max(n10, 1e-9), ratio_vs_15=a / max(n15, 1e-9), share_events_with_sale_0_60s=p2, null_share_15min=p2n))
C1 = pd.DataFrame(c1); C1.to_csv(f'{OUT}/bl_d0k_c1.csv', index=False); print(C1.round(2).to_string(index=False))
SL = ev[ev.type == '3 stop-loss'].copy()
# ---------------- C2 lag histogram
d = np.concatenate([SO[(SO.cid == r.cid) & (SO.cp == other(r.cp))].tod.values - r.tod for r in SL.itertuples()]); bins = np.arange(-60, 95, 5); h = np.histogram(d, bins)[0]; dn = np.concatenate([SO[(SO.cid == r.cid) & (SO.cp == other(r.cp))].tod.values - (r.tod + 900) for r in SL.itertuples()]); hn = np.histogram(dn, bins)[0]
C2 = pd.DataFrame(dict(lag_from_s=bins[:-1], lag_to_s=bins[1:], orders=h, null_15min=hn)); C2.to_csv(f'{OUT}/bl_d0k_c2.csv', index=False)
before = ((d >= -30) & (d < 0)).sum(); after = ((d >= 0) & (d <= 30)).sum(); R['c2'] = dict(before_30s=int(before), after_30s=int(after), null_before=int(((dn >= -30) & (dn < 0)).sum()), null_after=int(((dn >= 0) & (dn <= 30)).sum()), orders_total=int(len(d)))
# ---------------- C3 minute panel within adverse-move bins
rows = []
for i in sorted(X.cid.unique()):
    r = CY.iloc[i]; sp = SP[(r.und, r.expiry)]; c = sp.close.values; hh = sp.high.values; ll = sp.low.values; st = ref.STEP[r.und]; je = int(min(354, (STOP[i] - 33300) // 60 - 1)); si = SO[SO.cid == i]; sli = SL[SL.cid == i]
    for j in range(20, je + 1):
        for cp in ('CE', 'PE'):
            o = other(cp); adv = (c[j] - c[j - 5]) / st * (1 if cp == 'CE' else -1)
            y = float(si[(si.cp == o) & (si.j >= j) & (si.j <= j + 1)].lots.sum()); xs = int(sli[(sli.cp == cp) & (sli.j == j)].lots.sum())
            fav_ext = float((ll[j] < ll[max(j - 60, 0):j].min()) if o == 'CE' else (hh[j] > hh[max(j - 60, 0):j].max()))     # fresh 60-min favourable extreme for the other right's short
            rows.append((i, j, cp, adv, y, xs, fav_ext))
M = pd.DataFrame(rows, columns=['cid', 'j', 'cp', 'adv5', 'y', 'nsl', 'fav_ext']); M['bin'] = pd.qcut(M.adv5.rank(method='first'), 10, labels=False); M['sl'] = M.nsl > 0
c3 = []
for b, g in M.groupby('bin'):
    a = g[g.sl]; z = g[~g.sl]
    if len(a) < 10: continue
    bs = []
    cids = g.cid.unique()
    for _ in range(300):
        k = rng.choice(cids, len(cids)); gg = pd.concat([g[g.cid == c] for c in k]); aa = gg[gg.sl]; zz = gg[~gg.sl]
        if len(aa) and len(zz): bs.append(aa.y.mean() - zz.y.mean())
    c3.append(dict(adverse_move_bin=int(b), adv_lo=g.adv5.min(), adv_hi=g.adv5.max(), cells_with_stop=len(a), cells_without=len(z), sold_with_stop=a.y.mean(), sold_without=z.y.mean(), difference=a.y.mean() - z.y.mean(), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5), fav_ext_share_with=a.fav_ext.mean(), fav_ext_share_without=z.fav_ext.mean()))
C3 = pd.DataFrame(c3); C3.to_csv(f'{OUT}/bl_d0k_c3.csv', index=False); print(C3.round(3).to_string(index=False)); R['c3'] = dict(bins=len(C3), bins_positive_ci=int((C3.ci_lo > 0).sum()))
# fresh extreme alone vs stop alone vs both
M['fe'] = M.fav_ext > 0; c3b = M.groupby(['sl', 'fe']).agg(cells=('y', 'size'), sold=('y', 'mean')).reset_index(); c3b.to_csv(f'{OUT}/bl_d0k_c3b.csv', index=False); print(c3b.round(3).to_string(index=False))
# ---------------- C4 quantity
q = []
for r in SL.itertuples():
    s = SO[(SO.cid == r.cid) & (SO.cp == other(r.cp)) & (SO.tod >= r.tod) & (SO.tod <= r.tod + 60)]; q.append((r.lots, int(s.lots.sum()), len(s)))
Q = pd.DataFrame(q, columns=['bought', 'sold', 'orders']); Q['bin'] = pd.cut(Q.bought, [0, 1, 2, 3, 5, 8, 15, 1000], labels=['1', '2', '3', '4-5', '6-8', '9-15', '16+'])
C4 = Q.groupby('bin', observed=True).agg(events=('sold', 'size'), bought_mean=('bought', 'mean'), sold_mean=('sold', 'mean'), sold_median=('sold', 'median'), share_with_sale=('sold', lambda s: float((s > 0).mean()))).reset_index(); C4['sold_over_bought'] = C4.sold_mean / C4.bought_mean; C4.to_csv(f'{OUT}/bl_d0k_c4.csv', index=False); print(C4.round(2).to_string(index=False))
rho = spearmanr(Q.bought, Q.sold); slope = float(np.polyfit(Q.bought, Q.sold, 1)[0]); R['c4'] = dict(spearman=float(rho[0]), slope=slope, events=len(Q), share_with_sale=float((Q.sold > 0).mean()), sold_total=int(Q.sold.sum()), bought_total=int(Q.bought.sum()))
# ---------------- C5 strike and price (counter-sells = solo sales on the other right within 0..+60 s of a stop-loss event, first one per event)
c5 = []
for r in SL.itertuples():
    s = SO[(SO.cid == r.cid) & (SO.cp == other(r.cp)) & (SO.tod >= r.tod) & (SO.tod <= r.tod + 60)].sort_values('tod')
    for q_ in s.itertuples():
        j = q_.j; K = OPT[(CY.iloc[r.cid].und, CY.iloc[r.cid].expiry)]['K']; c0 = SP[(CY.iloc[r.cid].und, CY.iloc[r.cid].expiry)].close.values[max(j - 1, 0)]; atm = float(K[np.argmin(np.abs(K - c0))]); st = q_.step
        c5.append(dict(off_atm=(q_.strike - atm) / st * (1 if q_.cp == 'CE' else -1), same_strike_as_stopped=float(q_.strike == r.strike), px_ratio=q_.px / r.px if r.px > 0 else np.nan, lots=q_.lots))
C5 = pd.DataFrame(c5); R['c5'] = dict(orders=len(C5), exact_atm=float((C5.off_atm == 0).mean()), within1=float((C5.off_atm.abs() <= 1).mean()), same_strike_as_stopped=float(C5.same_strike_as_stopped.mean()), px_ratio_q=C5.px_ratio.quantile([.1, .25, .5, .75, .9]).tolist(), off_atm_q=C5.off_atm.quantile([.1, .5, .9]).tolist())
C5.describe().to_csv(f'{OUT}/bl_d0k_c5.csv'); print(R['c5'])
# ---------------- C6 which events trigger a sale within +60 s
SL['sale'] = (Q.sold > 0).astype(int).values; SL['hour'] = (SL.tod // 3600).astype(int); SL['ratio_ev'] = SL.ratio
c6 = []
for v in ('lots', 'ratio', 'hour', 'j'):
    y = SL.sale.values; p = SL[v].values; u = SL.cid.unique(); idx = {c_: np.where(SL.cid.values == c_)[0] for c_ in u}; bs = []
    for _ in range(300):
        k = np.concatenate([idx[c_] for c_ in rng.choice(u, len(u))])
        if y[k].min() != y[k].max(): bs.append(roc_auc_score(y[k], p[k]))
    c6.append(dict(variable=v, AUC=roc_auc_score(y, p), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5)))
C6 = pd.DataFrame(c6); C6.to_csv(f'{OUT}/bl_d0k_c6.csv', index=False); print(C6.round(3).to_string(index=False)); R['c6_by_hour'] = SL.groupby('hour').sale.agg(['mean', 'size']).round(3).to_dict('index'); R['c6_by_hour'] = {int(k): v for k, v in R['c6_by_hour'].items()}
R['c1'] = C1.round(4).to_dict('records'); R['events_stop_loss'] = len(SL); rec('d0k1', R); print({k: v for k, v in R.items() if k in ('c2', 'c3', 'c4')})
