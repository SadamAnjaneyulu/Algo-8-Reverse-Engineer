"""Cost reconstruction, slippage break-even and entry-timing (delay) analysis on the HOLD_SETTLE baseline."""
import json, math
from common import *
d = cycles('HOLD', 'HOLD_SETTLE'); comp = []
for r in d.itertuples():
    c = Cy.load(r.und, str(r.expiry)[:10]); day = c['d1']; b = t = s = g = st = stt = 0.0
    for tr in r.trades:
        v = tr[3] * tr[5]; bb = A.BROKERAGE; tt = A.TXN[r.und] * v; ss = A.SEBI * v; gg = A.GST * (bb + tt + ss); sm = A.STAMP_BUY * v if tr[2] > 0 else 0.0; sx = A.stt_sell(day) * v if tr[2] < 0 else 0.0
        b += bb; t += tt; s += ss; g += gg; st += sm; stt += sx
    ex = sum(A.stt_exercise(str(r.d0)[:10]) * v * q for _, q, v in r.settle if q > 0 and v > 0)
    prem_sold = sum(-tr[2] * tr[3] * tr[5] for tr in r.trades if tr[2] < 0); notional = sum(tr[3] * tr[5] for tr in r.trades)
    comp.append(dict(und=r.und, expiry=str(r.expiry)[:10], split=r.split, subset=r.subset, brokerage=b, exchange_txn=t, sebi=s, gst=g, stamp=st, stt_sell=stt, stt_exercise=ex, total_costs=b + t + s + g + st + stt + ex, reported_costs=r.costs, slippage=r.slippage, gross=r.gross, net=r.net, premium_sold=prem_sold, traded_value=notional, n_orders=r.n_orders))
C_ = pd.DataFrame(comp); print('max|recon-reported| costs:', (C_.total_costs - C_.reported_costs).abs().max()); C_.to_csv(f'{RES}/cost_components_cycles.csv', index=False)
agg = []
for p in ('IS', 'OOS', 'OOS_exposed', 'OOS_clean'):
    for u in ('COMBINED', 'NIFTY', 'SENSEX'):
        x = C_[C_.split.eq('IS') if p == 'IS' else (C_.split.eq('OOS') if p == 'OOS' else (C_.subset.eq('OOS_EXPOSED') if p == 'OOS_exposed' else C_.subset.isin(['OOS_CLEAN_BEFORE', 'OOS_CLEAN_AFTER'])))]
        if u != 'COMBINED': x = x[x.und == u]
        agg.append(dict(part=p, scope=u, cycles=len(x), gross=x.gross.sum(), slippage=x.slippage.sum(), brokerage=x.brokerage.sum(), exchange_txn=x.exchange_txn.sum(), sebi=x.sebi.sum(), gst=x.gst.sum(), stamp=x.stamp.sum(), stt_sell=x.stt_sell.sum(), stt_exercise=x.stt_exercise.sum(), total_costs=x.total_costs.sum(), net=x.net.sum(),
                        slip_plus_cost_per_cycle=(x.slippage.sum() + x.total_costs.sum()) / len(x), friction_share_of_gross=(x.slippage.sum() + x.total_costs.sum()) / x.gross.sum(), gross_per_cycle=x.gross.mean(), premium_sold_per_cycle=x.premium_sold.mean()))
A_ = pd.DataFrame(agg); A_.to_csv(f'{RES}/cost_components_summary.csv', index=False); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); print(A_[A_.scope == 'COMBINED'].round(0).to_string(index=False))
# break-even slippage: multiplier on (0.5% of price, floor 0.10) ; costs at 1x
sy = pd.read_csv(f'{RES}/settle_yahoo_cycles_HOLD.csv'); sy['expiry'] = sy.expiry.astype(str).str[:10]; Dm = {}
mults = [0, 0.5, 1, 2, 3, 4, 6, 8, 10]; rows = []
for m in mults:
    t = F.table('HOLD', 'HOLD_SETTLE', dict(slip_pct=0.005 * m, slip_min=0.10 * m, delay_min=0, cost_mult=1.0)); t['expiry'] = t.expiry.astype(str).str[:10]
    t = t.merge(sy[['und', 'expiry', 'net', 'net_y']].rename(columns={'net': 'net_base1x'}), on=['und', 'expiry']); t['settle_delta'] = t.net_y - t.net_base1x; t['net_yahoo'] = t.net + t.settle_delta
    for p in ('IS', 'OOS', 'OOS_clean', 'OOS_exposed'):
        x = part(t, p); rows.append(dict(slip_multiple=m, slip_pct=0.5 * m, part=p, net_original_settle=x.net.sum(), net_yahoo_settle=x.net_yahoo.sum(), sharpe_original=M.summarize(x)['sharpe']))
B = pd.DataFrame(rows); B.to_csv(f'{RES}/slippage_scan.csv', index=False)
def be(p, col):
    x = B[B.part == p].sort_values('slip_multiple'); v = x[col].values; m = x.slip_multiple.values
    for i in range(len(v) - 1):
        if v[i] > 0 >= v[i + 1]: return m[i] + (m[i + 1] - m[i]) * v[i] / (v[i] - v[i + 1])
    return float('nan') if v[-1] > 0 else float('nan')
bes = [dict(part=p, basis=c, breakeven_slip_multiple=be(p, c)) for p in ('IS', 'OOS', 'OOS_clean', 'OOS_exposed') for c in ('net_original_settle', 'net_yahoo_settle')]; pd.DataFrame(bes).to_csv(f'{RES}/breakeven_slippage.csv', index=False)
print(B.pivot_table(index='slip_multiple', columns='part', values=['net_original_settle', 'net_yahoo_settle']).round(0).to_string()); print(pd.DataFrame(bes).round(2))
# per-trade entry slippage in index points as % of premium at base: avg slip per leg
sl = []; 
for r in d.itertuples():
    for tr in r.trades: sl.append(dict(und=r.und, split=r.split, leg=tr[1], side=tr[2], ref=tr[4], exe=tr[5], slip_pts=abs(tr[5] - tr[4]), slip_pct=abs(tr[5] - tr[4]) / tr[4]))
SL = pd.DataFrame(sl); print(SL.groupby(['und', 'leg']).agg(ref=('ref', 'mean'), slip_pts=('slip_pts', 'mean'), slip_pct=('slip_pct', 'mean')).round(3))
# ---- entry-timing drift: short-leg price drift after the 09:16 open (why a 1-minute delay raises P&L)
dr = []
for r in d.itertuples():
    c = Cy.load(r.und, str(r.expiry)[:10]); px = A.Px(c)
    for lid in ('SCE', 'SPE'):
        t0 = scen.epoch(c['d1'], '09:16'); p0 = px.bar_open(lid, t0)
        for k in (1, 2, 3, 5, 10, 15, 30):
            pk = px.bar_open(lid, t0 + 60 * k)
            if p0 and pk: dr.append(dict(und=r.und, split=r.split, subset=r.subset, leg=lid, delay_min=k, drift_pct=100 * (pk / p0 - 1), drift_pts=pk - p0, p0=p0))
DR = pd.DataFrame(dr); g = DR.groupby(['und', 'split', 'delay_min']).agg(n=('drift_pct', 'size'), mean_drift_pct=('drift_pct', 'mean'), median_drift_pct=('drift_pct', 'median'), mean_drift_pts=('drift_pts', 'mean')).reset_index(); g.to_csv(f'{RES}/entry_drift.csv', index=False); print(g[g.delay_min.isin([1, 3, 5])].round(3).to_string(index=False))
# is the 09:16 bar open stale? stale = open equals previous bar close or zero volume: share of entry bars with the same OHLC (flat)
fl = []
for r in d.itertuples():
    c = Cy.load(r.und, str(r.expiry)[:10])
    for lid in ('SCE', 'SPE'):
        f = c['frames'][lid][0]; b = f[f.hm == '09:16']
        if len(b): fl.append(dict(und=r.und, split=r.split, flat=float(b.iloc[0].open == b.iloc[0].close), vol=float(b.iloc[0].volume)))
print(pd.DataFrame(fl).groupby(['und', 'split']).agg(flat_share=('flat', 'mean'), n=('flat', 'size')).round(3))
