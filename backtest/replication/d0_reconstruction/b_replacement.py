"""PHASE B (DISCOVERY cycles only). What follows a D0 buyback, and which buybacks are replaced?"""
from d0common import *
E = load_events(True); D0 = E[E.day == 'D0'].copy(); rng = np.random.default_rng(5)
print('discovery cycles with D0:', D0.groupby(['und', 'expiry']).ngroups, ' D0 orders', len(D0))
body = D0[D0.module == 'num']; bb = body[(body.side == 'Buy') & (body.closed_lots > 0)]; sales = body[(body.side == 'Sell') & (body.opened_lots > 0)]
# B1: delay from previous same-right buyback to each sale (seconds), observed vs time-shifted null
def delays(sales, bbs):
    out = []
    for (u, e, cp), g in sales.groupby(['und', 'expiry', 'cp']):
        b = np.sort(bbs[(bbs.und == u) & (bbs.expiry == e) & (bbs.cp == cp)].sec.values)
        if not len(b): continue
        i = np.searchsorted(b, g.sec.values, side='right') - 1; ok = i >= 0; out.extend(zip((g.sec.values - np.where(ok, b[np.maximum(i, 0)], np.nan)), g.lots.values))
    return np.array(out)
obs = delays(sales, bb); 
def share(x, w): m = ~np.isnan(x); return (x[m] <= w).astype(float) @ obs[m, 1] / obs[m, 1].sum() if False else None
rows = []
nulls = {w: [] for w in (30, 60, 120, 180, 300)}
for rep in range(200):
    bb2 = bb.copy(); bb2['sec'] = bb2.sec + rng.choice([-1, 1], len(bb2)) * rng.uniform(1200, 7200, len(bb2)); nd = delays(sales, bb2)
    for w in nulls: m = ~np.isnan(nd[:, 0]); nulls[w].append((nd[m, 0] <= w) @ nd[m, 1] / sales.lots.sum())
for w in nulls:
    m = ~np.isnan(obs[:, 0]); o = (obs[m, 0] <= w) @ obs[m, 1] / sales.lots.sum(); n = np.array(nulls[w]); rows.append(dict(window_s=w, observed_share_of_sold_lots=o, null_mean=n.mean(), null_p95=np.percentile(n, 95), ratio=o / n.mean()))
R1 = pd.DataFrame(rows); R1.to_csv(f'{RES}/b1_replacement_delay_vs_null.csv', index=False); print(R1.round(3).to_string(index=False))
# B2: buyback subtypes + follow-up
bb = bb.copy(); bb['sub_clockB'] = bb.clockB_minute & (bb.ss <= 30); bb['sub_late'] = bb.sec >= 15 * 3600 + 10 * 60; bb['sub_salvage'] = (bb.px <= 1.0) | (bb.px <= 0.05 * bb.avg_entry_before)
bb['sub_stoplike'] = bb.ratio_cheapest >= 1.55; bb['sub_profit'] = bb.px < bb.avg_entry_before; bb['hrs'] = (15.5 * 3600 - bb.sec) / 3600
def subtype(r):
    if r.sub_late: return '1 late (>=15:10)'
    if r.sub_salvage: return '2 salvage (<=Rs1 or <=5% entry)'
    if r.sub_stoplike: return '3 price >= 1.55x cheapest entry'
    if r.sub_clockB: return '4 Clock-B tick minute'
    return '5 other'
bb['subtype'] = bb.apply(subtype, axis=1)
T = bb.groupby('subtype').agg(orders=('lots', 'size'), lots=('lots', 'sum'), repl_any=('follow_kind', lambda s: (~s.isin(['NONE_WITHIN_180S', ''])).mean()), same_contract=('follow_kind', lambda s: (s == 'SAME_CONTRACT').mean()), same_right_other=('follow_kind', lambda s: (s == 'SAME_RIGHT_OTHER_STRIKE').mean()), opp_only=('follow_kind', lambda s: (s == 'OPPOSITE_RIGHT_ONLY').mean()), none=('follow_kind', lambda s: (s == 'NONE_WITHIN_180S').mean()), median_delay_s=('follow_delay_s', 'median'), mean_pnl=('realized_pnl', 'mean'))
T.to_csv(f'{RES}/b2_buyback_followup_by_subtype.csv'); print(T.round(3).to_string())
tr = bb.groupby(['subtype', 'follow_kind']).size().unstack(fill_value=0); tr.to_csv(f'{RES}/b2_transition_table.csv'); print(tr)
# follow lot ratio & strike relation for replaced
f = bb[bb.follow_kind.isin(['SAME_CONTRACT', 'SAME_RIGHT_OTHER_STRIKE'])]; print('lots ratio follow/bought', (f.follow_lots / f.lots).describe().round(2).to_dict()); print('follow strike steps vs ATM (prev minute spot):', f.follow_strike_steps_vs_atm.describe().round(2).to_dict()); print('delay s quantiles', f.follow_delay_s.quantile([.1,.25,.5,.75,.9]).round(1).to_dict())
bb.to_csv(f'{RES}/b_buybacks_discovery.csv', index=False)
