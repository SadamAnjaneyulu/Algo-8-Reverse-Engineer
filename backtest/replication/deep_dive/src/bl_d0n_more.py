"""N4 (tight coupling, timing), H7 (clock), N5 (loss recovery, burst size), N6 (mechanics) of reports/D0_CTRIG_PLAN.md.
Outputs bl_d0n_n4.csv, bl_d0n_n4b.csv, bl_d0n_hour.csv, bl_d0n_h7.csv, bl_d0n_n5.csv, bl_d0n_n5b.csv, bl_d0n_n6.csv, bl_summary_d0n2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); SO = pd.read_pickle(f'{OUT}/bl_d0n_orders.pkl.gz'); PN = pd.read_pickle(f'{OUT}/bl_d0n_panel.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_d0y_lots.pkl.gz'); T = pd.read_pickle(f'{OUT}/bl_d0t_orders.pkl.gz'); SP = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz')
rng = np.random.default_rng(83); R = {}; other = lambda c: 'PE' if c == 'CE' else 'CE'
SO['counter'] = SO.type == 'counter-sell solo'; SO['unit'] = SO.cid.map(CY.unit)
SLB = X[X.type == '3 stop-loss'].copy(); ALLB = X.copy()
# ---------------- N4 tight coupling: signed lag (sale - buy-back) at 1 s; sales on R' vs stop-loss buy-backs on R
def lags(sales, bbs, shift=0, lim=60):
    out = []
    for (cid, cp), g in bbs.groupby(['cid', 'cp']):
        s = sales[(sales.cid == cid) & (sales.cp == other(cp))].tod.values
        if len(s) == 0: continue
        for t in np.unique(g.tod.values):
            d = s - (t + shift); out.append(d[np.abs(d) <= lim])
    return np.concatenate(out) if out else np.array([])
bins = np.arange(-10, 12, 1); rows = []
for nm, bb in (('stop-loss buy-backs', SLB), ('all buy-backs', ALLB)):
    d = lags(SO, bb); dn = np.concatenate([lags(SO, bb, s) for s in (900, -900)]) / 2 if False else (np.histogram(lags(SO, bb, 900), bins)[0] + np.histogram(lags(SO, bb, -900), bins)[0]) / 2
    h = np.histogram(d, bins)[0]
    for k in range(len(bins) - 1): rows.append(dict(bb=nm, lag_s=int(bins[k]), orders=int(h[k]), null=float(dn[k]), ratio=h[k] / max(dn[k], 1e-9)))
N4 = pd.DataFrame(rows); N4.to_csv(f'{OUT}/bl_d0n_n4.csv', index=False)
# tight bin 0..2 s, cycle-bootstrap CI of ratio, and share of counter-labelled lots inside
def tight_ratio(cids, bb, lo=0, hi=2):
    s = SO[SO.cid.isin(cids)]; b = bb[bb.cid.isin(cids)]; d = lags(s, b); a = ((d >= lo) & (d <= hi)).sum(); n = np.mean([((lags(s, b, sh) >= lo) & (lags(s, b, sh) <= hi)).sum() for sh in (900, -900)]); return a, n
cids = sorted(SLB.cid.unique()); a, n = tight_ratio(cids, SLB); bs = []
for _ in range(200):
    k = list(rng.choice(cids, len(cids)));  # bootstrap with replacement: replicate by concatenating renamed cycles
    ss = pd.concat([SO[SO.cid == c_].assign(cid=1000 * (m + 1) + c_) for m, c_ in enumerate(k)]); bb_ = pd.concat([SLB[SLB.cid == c_].assign(cid=1000 * (m + 1) + c_) for m, c_ in enumerate(k)])
    d = lags(ss, bb_); a_ = ((d >= 0) & (d <= 2)).sum(); n_ = np.mean([((lags(ss, bb_, sh) >= 0) & (lags(ss, bb_, sh) <= 2)).sum() for sh in (900, -900)]); bs.append(a_ / max(n_, 1e-9))
R['n4'] = dict(tight_orders=int(a), tight_null=float(n), ratio=float(a / max(n, 1e-9)), ratio_ci=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))])
# share of counter-labelled / all solo lots with a stop-loss buy-back on the other right within 2 s, 5 s, 60 s
def near(s, bb, w):
    k = np.zeros(len(s), bool)
    for n_, q in enumerate(s.itertuples()):
        b = bb[(bb.cid == q.cid) & (bb.cp == other(q.cp))].tod.values; k[n_] = bool(len(b) and (np.abs(b - q.tod) <= w).any())
    return k
rows = []
for w in (2, 5, 60):
    k = near(SO, ALLB, w); rows.append(dict(window_s=w, share_all_solo_lots=float(SO.lots[k].sum() / SO.lots.sum()), share_counter_lots=float(SO.lots[k & SO.counter.values].sum() / SO.lots[SO.counter].sum()), share_noncounter_lots=float(SO.lots[k & ~SO.counter.values].sum() / SO.lots[~SO.counter].sum())))
    kn = np.mean([near(SO.assign(tod=SO.tod + sh), ALLB, w) for sh in (900, -900)], axis=0); rows[-1]['null_share_all_lots'] = float((SO.lots * kn).sum() / SO.lots.sum())
pd.DataFrame(rows).to_csv(f'{OUT}/bl_d0n_n4b.csv', index=False); R['n4b'] = rows
# hour profile: counter lots vs panel rate
SO['hour'] = (SO.tod // 3600).astype(int); H = SO.groupby('hour').agg(counter_lots=('lots', lambda s: s[SO.loc[s.index, 'counter']].sum()), solo_lots=('lots', 'sum')).reset_index(); H['counter_share_of_solo'] = H.counter_lots / H.solo_lots; PN['hour'] = PN.hour.astype(int); H = H.merge(PN.groupby('hour').agg(cells=('y', 'size'), solo_rate=('y', 'mean')).reset_index(), on='hour'); H.to_csv(f'{OUT}/bl_d0n_hour.csv', index=False)
# ---------------- H7 clock: leave-one-cycle-out, same underlying/version
def clock_cov(sub, shift=0, w=2):
    hit = 0; n = 0
    for (und, ver), g in sub.groupby(['und', 'version']):
        for c_ in g.cid.unique():
            t = g[g.cid == c_].tod.values + shift; o = g[g.cid != c_].tod.values
            if len(o) == 0: continue
            o = np.sort(o); k = np.searchsorted(o, t); dd = np.minimum(np.abs(o[np.clip(k, 0, len(o) - 1)] - t), np.abs(o[np.clip(k - 1, 0, len(o) - 1)] - t)); hit += int((dd <= w).sum()); n += len(t)
    return hit / max(n, 1)
h7 = []
for nm, sub in (('counter-labelled solo', SO[SO.counter]), ('other solo (not counter)', SO[~SO.counter]), ('all solo', SO)):
    real = clock_cov(sub); nulls = [clock_cov(sub, s) for s in (150, -150, 120, -120, 180, -180)]; h7.append(dict(set=nm, orders=len(sub), loco_share_on_other_cycles_times=real, null_mean=float(np.mean(nulls)), ratio=real / max(np.mean(nulls), 1e-9)))
pd.DataFrame(h7).to_csv(f'{OUT}/bl_d0n_h7.csv', index=False); R['h7'] = h7
# position within 5-minute block (counter vs all solo): share in seconds 0-133 of the block
for nm, sub in (('counter', SO[SO.counter]), ('other solo', SO[~SO.counter])): R[f'in_first_133s_of_5min_{nm}'] = float((((sub.tod - 33300) % 300) < 133).mean())
# ---------------- N5 size / loss recovery
rows = []
for q in SLB.itertuples():
    s = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp)) & (SO.tod >= q.tod) & (SO.tod <= q.tod + 60)]; u = CY.unit.iloc[q.cid]; rows.append((q.cid, q.tod, q.cp, (q.px - q.entry) * u, float((s.lots * s.px).sum() * u), int(s.lots.sum())))
E = pd.DataFrame(rows, columns=['cid', 'tod', 'cp', 'loss_rs', 'sold_premium_rs', 'sold_lots'])
E = E.groupby(['cid', 'cp', 'tod']).agg(loss_rs=('loss_rs', 'sum'), sold_premium_rs=('sold_premium_rs', 'first'), sold_lots=('sold_lots', 'first')).reset_index()
def sp_(E_): return spearmanr(E_.loss_rs, E_.sold_premium_rs)[0]
rho = sp_(E); u = E.cid.unique(); b = [sp_(pd.concat([E[E.cid == c_] for c_ in rng.choice(u, len(u))])) for _ in range(300)]
# shifted null: sold premium in a window +/-900 s away (clock-kept)
nl = []
for sh in (900, -900):
    z = []
    for q in E.itertuples():
        s = SO[(SO.cid == q.cid) & (SO.cp == other(q.cp)) & (SO.tod >= q.tod + sh) & (SO.tod <= q.tod + sh + 60)]; z.append(float((s.lots * s.px).sum() * CY.unit.iloc[q.cid]))
    nl.append(spearmanr(E.loss_rs, z)[0])
R['n5'] = dict(events=len(E), spearman_loss_vs_sold_premium=float(rho), ci=[float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))], null_spearman=[float(x) for x in nl], median_loss_rs=float(E.loss_rs.median()), median_sold_premium_rs=float(E.sold_premium_rs.median()), share_events_with_sale=float((E.sold_lots > 0).mean()), sold_to_loss_ratio_median_where_sale=float((E.sold_premium_rs / E.loss_rs.where(E.loss_rs > 0))[E.sold_lots > 0].median()))
E.to_csv(f'{OUT}/bl_d0n_n5.csv', index=False)
# bursts on solo orders: same cycle & right, gap <= 30 s
B = []
for (cid, cp), g in SO.sort_values('tod').groupby(['cid', 'cp']):
    t = g.tod.values; L = g.lots.values; st = np.r_[0, np.where(np.diff(t) > 30)[0] + 1, len(t)]
    for a, z in zip(st[:-1], st[1:]):
        j0 = int(g.j.values[a]); j1 = int(g.j.values[z - 1]); c = SP[(CY.und.iloc[cid], CY.expiry.iloc[cid])].close.values; stp = float(ref.STEP[CY.und.iloc[cid]]); sg = -1.0 if cp == 'CE' else 1.0
        B.append(dict(cid=cid, cp=cp, orders=z - a, lots=int(L[a:z].sum()), start=t[a], span_s=t[z - 1] - t[a], fav_move_steps=sg * (c[j1] - c[max(j0 - 1, 0)]) / stp, counter_share=float(g.counter.values[a:z].mean())))
B = pd.DataFrame(B); B.to_csv(f'{OUT}/bl_d0n_n5b.csv', index=False)
R['bursts'] = dict(n=len(B), orders_median=float(B.orders.median()), lots_q=B.lots.quantile([.1, .5, .9]).tolist(), span_s_q=B.span_s.quantile([.5, .9]).tolist(), lots_vs_move_spearman=float(spearmanr(B.lots, B.fav_move_steps)[0]), share_lots_in_5plus=float(B.lots[B.lots >= 5].sum() / B.lots.sum()), share_bursts_with_counter_label=float((B.counter_share > 0).mean()))
# ---------------- N6 mechanics by type
M = SO.merge(T[['off_steps', 'exact_atm', 'status', 'px_over_atm']].reset_index(drop=True).set_index(T.index), left_index=True, right_index=True, how='left')
N6 = M.groupby(M.counter.map({True: 'counter-labelled', False: 'other solo'})).agg(orders=('lots', 'size'), lots_per_order=('lots', 'mean'), exact_atm=('exact_atm', 'mean'), median_off_steps=('off_steps', 'median'), carried_strike=('status', lambda s: (s == 'carried strike').mean()), d0_strike=('status', lambda s: (s == 'D0 strike').mean()), new_strike=('status', lambda s: (s == 'new strike').mean()), median_px_over_atm=('px_over_atm', 'median')).reset_index(); N6.to_csv(f'{OUT}/bl_d0n_n6.csv', index=False)
R['status_values'] = T.status.value_counts().to_dict(); rec('d0n2', R); print(N4[N4.bb == 'stop-loss buy-backs'].round(2).to_string(index=False)); print(pd.DataFrame(R['n4b']).round(3)); print(H.round(3)); print(pd.DataFrame(h7).round(3)); print({k: v for k, v in R.items() if k in ('n4', 'n5', 'bursts')}); print(N6.round(3).to_string(index=False))
