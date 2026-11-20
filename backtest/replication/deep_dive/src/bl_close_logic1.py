"""Buy-back study, step 2 (plan tests A, B, E, F): order-level pairing, below-1.2x classification, episodes. D-1 primary, D0 secondary.
pair  = other-right body buy-back at the SAME strike within +-3 s; partner = other-right body buy-back at ANY strike within +-3 s.
Outputs: outputs/bl_close_orders_flags.csv, outputs/bl_close_pair_*.csv, outputs/bl_summary_close1.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
W = 3.0; THR = 1.2; EOD = 15 * 3600 + 10 * 60
O = pd.read_csv(f'{OUT}/bl_close_orders.csv'); R = {}; rng = np.random.default_rng(0)


def flag(df, w=W):
    df = df.reset_index(drop=True); n = len(df); pa = np.zeros(n, bool); pt = np.zeros(n, bool); p_ratio = np.full(n, np.nan); pt_ratio = np.full(n, np.nan); p_dt = np.full(n, np.nan)
    ra = (df.dec_px / df.avg).values
    for _, g in df.groupby(['und', 'expiry', 'day']):
        idx = g.index.values; te = g.te.values; cp = g.cp.values; k = g.strike.values
        for a in range(len(g)):
            m = (np.abs(te - te[a]) <= w) & (cp != cp[a])
            if m.any():
                pt[idx[a]] = True; j = np.where(m)[0]; pt_ratio[idx[a]] = np.nanmax(ra[idx[j]])
                ms = m & (k == k[a])
                if ms.any(): pa[idx[a]] = True; jj = np.where(ms)[0]; p_ratio[idx[a]] = np.nanmax(ra[idx[jj]]); p_dt[idx[a]] = np.min(np.abs(te[jj] - te[a]))
    df['paired'] = pa; df['partnered'] = pt; df['pair_ratio'] = p_ratio; df['partner_ratio'] = pt_ratio; df['pair_dt'] = p_dt; return df


def null_pair(df, nrep=100):
    """expected pairing share if the other right's buy-back times were unrelated: circularly shift the other right's order times within the cycle-day (strike kept)"""
    out = []
    for _ in range(nrep):
        hit = 0; tot = 0
        for _, g in df.groupby(['und', 'expiry', 'day']):
            te = g.te.values; cp = g.cp.values; k = g.strike.values; lo, hi = te.min(), te.max(); span = max(hi - lo, 1)
            for c in ('CE', 'PE'):
                a = (cp == c); b = ~a
                if not a.any() or not b.any(): continue
                tb = lo + ((te[b] - lo + rng.uniform(0, span)) % span)
                kb = k[b]
                for ta, ka in zip(te[a], k[a]): hit += int(((np.abs(tb - ta) <= W) & (kb == ka)).any())
                tot += a.sum()
        out.append(hit / tot)
    return np.mean(out), np.quantile(out, [.025, .975])


for ref_name, col in (('avg', 'avg'), ('low', 'low'), ('fifo', 'fifo')): O['r_' + ref_name] = O.dec_px / O[col]
O['o_r_avg'] = O.o_px_chain / O.o_avg; O['straddle_r'] = (O.px_chain + O.o_px_chain) / (O.avg + O.o_avg); O['r_avg_chain'] = O.px_chain / O.avg
F = pd.concat([flag(O[O.day == d]) for d in ('D-1', 'D0')]); F.to_csv(f'{OUT}/bl_close_orders_flags.csv', index=False)
bins = [0, .8, 1.0, 1.2, 1.4, 1.55, 1.7, 2.0, 99]
for day in ('D-1', 'D0'):
    d = F[F.day == day].copy(); print(f'\n===== {day}: {len(d)} buy-back orders ({d.lots.sum()} lots), cycles {d.groupby(["und", "expiry"]).ngroups}')
    R[f'{day}_n'] = len(d); R[f'{day}_paired'] = float(d.paired.mean()); R[f'{day}_partnered'] = float(d.partnered.mean())
    nm, ci = null_pair(d, 60); R[f'{day}_pair_null'] = [float(nm), float(ci[0]), float(ci[1])]; print(f'paired share {d.paired.mean():.3f}; null (other-right times shifted) {nm:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]; partnered {d.partnered.mean():.3f}')
    # B: pairing by ratio class under each reference
    for rn in ('r_avg', 'r_low', 'r_fifo'):
        t = d.groupby(pd.cut(d[rn], bins), observed=True).agg(n=('paired', 'size'), paired=('paired', 'mean'), partnered=('partnered', 'mean')).round(3); t.index = t.index.astype(str); t.to_csv(f'{OUT}/bl_close_pair_{day}_{rn}.csv'); R[f'{day}_pair_by_{rn}'] = t.reset_index().to_dict('list')
        if rn == 'r_avg': print(t.to_string())
    # legs of paired events: ratios of both legs
    pp = d[d.paired & d.pair_ratio.notna()]
    if len(pp):
        hi = np.maximum(pp.r_avg, pp.pair_ratio); lo = np.minimum(pp.r_avg, pp.pair_ratio)
        R[f'{day}_pairs_n'] = len(pp); R[f'{day}_pair_both_ge12'] = float(((hi >= THR) & (lo >= THR)).mean()); R[f'{day}_pair_one_ge12_one_lt'] = float(((hi >= THR) & (lo < THR)).mean()); R[f'{day}_pair_both_lt12'] = float((hi < THR).mean())
        print(f'paired legs (n={len(pp)}): max-leg ratio median {hi.median():.2f}, min-leg median {lo.median():.2f}; both >=1.2: {R[day + "_pair_both_ge12"]:.2f}, one >=1.2 and other <1.2: {R[day + "_pair_one_ge12_one_lt"]:.2f}, both <1.2: {R[day + "_pair_both_lt12"]:.2f}')
    # share of buy-backs below 1.2 under each reference
    for rn in ('r_avg', 'r_low', 'r_fifo', 'r_avg_chain'): R[f'{day}_below12_{rn}'] = float((d[rn] < THR).mean()); print(f'  share below {THR}x ({rn}): {(d[rn] < THR).mean():.3f}')
    d['hi_ref'] = d[['r_avg', 'r_low', 'r_fifo']].max(axis=1); R[f'{day}_below12_all3'] = float((d.hi_ref < THR).mean()); print(f'  below 1.2 under ALL three references: {(d.hi_ref < THR).mean():.3f}')
    # E: mutually exclusive classes for buy-backs below 1.2x on the average reference, in a fixed priority order
    u = d[d.r_avg < THR].copy()
    cls = np.full(len(u), 'other', object); left = np.ones(len(u), bool)
    def take(mask, name):
        global cls, left
        m = left & mask; cls[m] = name; left = left & ~m
    take((u.pair_ratio >= THR).values, '1 same-strike partner leg >=1.2x (paired)')
    take((u.partner_ratio >= THR).values, '2 other-strike partner leg >=1.2x')
    take((u.hi_ref >= THR).values, '3 a lot-level reference (LOW/FIFO) >=1.2x')
    take((u.tod >= EOD).values, '4 end of day (>=15:10)')
    take(((u.o_px_chain / u.o_avg) >= THR).values, '5 other leg of the strike >=1.2x, not bought back')
    take((u.straddle_r >= THR).values, '6 straddle ratio >=1.2x')
    take((u.resell_any == 1).values, '7 re-sold within 60 s (same right)')
    take((u.empties == 1).values, '8 empties the strike')
    u['cls'] = cls; t = u.cls.value_counts().sort_index(); print(f'\nbuy-backs below 1.2x (avg ref): {len(u)} of {len(d)}'); print(t.to_string()); R[f'{day}_below_classes'] = t.to_dict(); R[f'{day}_below_n'] = len(u)
    oth = u[u.cls == 'other']
    if len(oth): print('residual "other":', len(oth), 'median ratio', round(oth.r_avg.median(), 2), 'median hold min', round(oth.hold_fifo_min.median(), 0), 'median tod h', round(oth.tod.median() / 3600, 2), 'ITM share', round((oth.itm_steps > 0).mean(), 2))
    u.to_csv(f'{OUT}/bl_close_below12_{day}.csv', index=False)
    # F: episodes (same cycle, day, cp, strike; gap <= 60 s) and bursts
    d = d.sort_values(['und', 'expiry', 'day', 'cp', 'strike', 'te']); gap = d.groupby(['und', 'expiry', 'day', 'cp', 'strike']).te.diff(); d['ep'] = ((gap.isna()) | (gap > 60)).cumsum()
    ep = d.groupby('ep').agg(orders=('lots', 'size'), lots=('lots', 'sum'), dur=('te', lambda s: s.max() - s.min())); R[f'{day}_ep_n'] = len(ep); R[f'{day}_ep_orders_q'] = ep.orders.quantile([.5, .75, .9, 1]).tolist(); R[f'{day}_ep_single_order_share'] = float((ep.orders == 1).mean())
    print(f'\nepisodes (same strike, gap<=60 s): {len(ep)}; orders per episode quantiles (50/75/90/100): {ep.orders.quantile([.5, .75, .9, 1]).tolist()}; single-order share {(ep.orders == 1).mean():.2f}')
    d['minute'] = (d.te // 60).astype(int); mb = d.groupby(['und', 'expiry', 'day', 'minute']).agg(orders=('lots', 'size'), strikes=('strike', 'nunique'), rights=('cp', 'nunique')); R[f'{day}_minute_orders_q'] = mb.orders.quantile([.5, .75, .9, 1]).tolist(); R[f'{day}_minute_multi_strike_share'] = float((mb.strikes > 1).mean()); print('buy-back minutes:', len(mb), 'orders per minute q50/75/90/max', mb.orders.quantile([.5, .75, .9, 1]).tolist(), 'multi-strike share', round((mb.strikes > 1).mean(), 2))
rec('close1', R)
