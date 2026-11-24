"""D0 quantity, Part A: order execution (plan reports/D0_QTY_PLAN.md).
A1 size and splitting (lots per order / event, max order quantity by month vs freeze), A2 limit-price buffer, A3 order type and partial fills,
A4 where the first fill sits in the one-minute option bar, A5 dripping inside multi-order events.
Outputs bl_d0u_orders.pkl.gz, bl_d0u_a1_size.csv, bl_d0u_a1_maxqty.csv, bl_d0u_a2_buffer.csv, bl_d0u_a3_type.csv, bl_d0u_a4_bar.csv, bl_d0u_a5_drip.csv, bl_summary_d0u_a.json"""
import sys, json, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); R = {}
UNIT = {'NIFTY': 65, 'SENSEX': 20}; FREEZE_LOTS = {'NIFTY': 27, 'SENSEX': 50}
def klass(r):
    m, ro = r.module, r.role
    if m == 'num': return {'open_short': 'body sell', 'cover_short': 'body buy-back', 'open_long': 'body long buy', 'close_long': 'body long sell'}.get(ro, 'body other')
    if m == 'h_': return 'wing buy' if ro == 'open_long' else ('wing sell' if ro == 'close_long' else 'hedge other')
    if m == 'v_': return 'lump salvage'
    if m == 's_': return 'stop module'
    return 'other'
def prep(day):
    d = O[O.dayno == day].copy(); d['klass'] = [klass(r) for r in d.itertuples()]; d['unit'] = d.und.map(UNIT); d['qty'] = d.lots * d.unit
    d['month'] = d.expiry.str.slice(0, 7); d['buy'] = d.side == 'Buy'
    d['buf'] = np.where(d.buy, d.lim_px / d.px_first - 1, 1 - d.lim_px / d.px_first); d['buf'] = d.buf.where(d.px_first > 0)
    d['jm'] = ((d.tod - 33300) // 60).astype(int)
    return d
D0 = prep(1); D1 = prep(0)
# --- event grouping: same cycle, module, role, right, gap <= 2 s
def events(d):
    d = d.sort_values(['und', 'expiry', 'module', 'role', 'cp', 'tod', 'row']).copy()
    g = (d.und + d.expiry + d.module + d.role + d.cp).values; new = np.r_[True, (g[1:] != g[:-1]) | (np.diff(d.tod.values) > 2)]
    d['eid'] = np.cumsum(new); return d
D0 = events(D0); D1 = events(D1)
# --- A1 size
def a1(d, tag):
    e = d.groupby(['klass', 'eid']).agg(lots=('lots', 'sum'), n_orders=('lots', 'size'), und=('und', 'first')).reset_index()
    out = []
    for k, z in d.groupby('klass'):
        ev = e[e.klass == k]
        out.append(dict(day=tag, klass=k, orders=len(z), lots=int(z.lots.sum()), lots_per_order_med=z.lots.median(), lots_per_order_p90=z.lots.quantile(.9), lots_per_order_max=z.lots.max(),
                        events=len(ev), lots_per_event_med=ev.lots.median(), lots_per_event_p90=ev.lots.quantile(.9), lots_per_event_max=ev.lots.max(), single_lot_orders=float((z.lots == 1).mean()),
                        single_lot_events=float((ev.lots == 1).mean()), orders_per_event_med=ev.n_orders.median()))
    return pd.DataFrame(out)
A1 = pd.concat([a1(D0, 'D0'), a1(D1, 'D-1')]); A1.to_csv(f'{OUT}/bl_d0u_a1_size.csv', index=False)
mx = []
for day, d in (('D0', D0), ('D-1', D1)):
    for (u, m), z in d.groupby(['und', 'month']):
        mx.append(dict(day=day, und=u, month=m, orders=len(z), gcd_qty=int(np.gcd.reduce(z.qty.values)), max_order_lots=int(z.lots.max()), max_order_qty=int(z.qty.max()), n_orders_at_max=int((z.lots == z.lots.max()).sum()),
                       freeze_lots_assumed=FREEZE_LOTS[u], orders_above_freeze=int((z.lots > FREEZE_LOTS[u]).sum()),
                       orders_in_27_to_54=int(((z.lots > 27) & (z.lots <= 54)).sum()) if u == 'NIFTY' else np.nan))
MX = pd.DataFrame(mx); MX.to_csv(f'{OUT}/bl_d0u_a1_maxqty.csv', index=False)
# large events: size of orders inside events above 27 lots (NIFTY) / 50 (SENSEX)
big = D0.groupby('eid').agg(lots=('lots', 'sum'), n=('lots', 'size'), mx=('lots', 'max'), und=('und', 'first'), month=('month', 'first')).reset_index()
big = big[big.lots > big.und.map(FREEZE_LOTS)]
R['a1_events_above_freeze'] = int(len(big)); R['a1_events_above_freeze_split_in_several_orders'] = int((big.n > 1).sum()); R['a1_max_order_lots_D0'] = {u: int(D0[D0.und == u].lots.max()) for u in UNIT}
R['a1_lots_by_class_D0'] = {k: int(v) for k, v in D0.groupby('klass').lots.sum().items()}
# --- A2 limit buffer
def a2(d, tag):
    out = []
    for keys, z in d[d.buf.notna()].groupby(['klass', 'side']):
        b = z.buf; tick = 0.05; px = z.px_first.values; lim = z.lim_px.values; sgn = np.where(z.buy.values, 1, -1)
        pred = np.round(px * (1 + sgn * 0.15) / tick) * tick; fit = (np.abs(lim - pred) <= tick + 1e-9).mean()
        out.append(dict(day=tag, klass=keys[0], side=keys[1], n=len(z), buf_med=b.median(), buf_p05=b.quantile(.05), buf_p95=b.quantile(.95), buf_cv=b.std() / b.mean() if b.mean() else np.nan,
                        share_within_1tick_of_15pct=float(fit), share_buf_0=float((b.abs() < 1e-9).mean())))
    return pd.DataFrame(out)
A2 = pd.concat([a2(D0, 'D0'), a2(D1, 'D-1')]); A2.to_csv(f'{OUT}/bl_d0u_a2_buffer.csv', index=False)
z = D0[D0.buf.notna()]
R['a2_buf_overall_med'] = float(z.buf.median()); R['a2_share_within_1tick_of_15pct'] = float(A2[A2.day == 'D0'].eval('share_within_1tick_of_15pct * n').sum() / A2[A2.day == 'D0'].n.sum())
# by price level (is the buffer a constant percentage or a constant rupee amount?)
z = z.assign(pxb=pd.cut(z.px_first, [0, 1, 3, 10, 30, 100, 300, 1e4]))
pl = z.groupby('pxb').agg(n=('buf', 'size'), buf_med=('buf', 'median'), abs_gap_med=('px_first', lambda s: np.nan)).reset_index()
pl['abs_gap_med'] = [float(np.median(np.abs(zz.lim_px - zz.px_first))) for _, zz in z.groupby('pxb')]; pl.to_csv(f'{OUT}/bl_d0u_a2_bylevel.csv', index=False)
# --- A3 order type
t3 = D0.groupby(['module', 'klass', 'validity']).agg(orders=('lots', 'size'), lots=('lots', 'sum'), partial=('n_partial', lambda s: float((s > 0).mean())), multi_fill=('n_fills', lambda s: float((s > 1).mean())),
                                                    fill_secs_med=('fill_secs', 'median'), fill_secs_p90=('fill_secs', lambda s: s.quantile(.9)), lots_eq_ordered=('lim_lots', 'size')).reset_index()
t3['lots_eq_ordered'] = [float((zz.lots == zz.lim_lots).mean()) for _, zz in D0.groupby(['module', 'klass', 'validity'])]; t3.to_csv(f'{OUT}/bl_d0u_a3_type.csv', index=False)
R['a3_validity_by_module_D0'] = {f'{k[0]}|{k[1]}': int(v) for k, v in D0.groupby(['module', 'validity']).size().items()}
R['a3_partial_share_D0'] = float((D0.n_partial > 0).mean()); R['a3_status_last_D0'] = D0.status_last.value_counts().to_dict()
# --- A4 fill vs bar
pos = []; rel_o = []; rel_c1 = []; rel_c = []; out_of = []; hi_lo_w = []
for r in D0.itertuples():
    o = OPT.get((r.und, r.expiry));
    if o is None or r.jm < 0 or r.jm > 374: pos.append(np.nan); rel_o.append(np.nan); rel_c1.append(np.nan); rel_c.append(np.nan); out_of.append(np.nan); hi_lo_w.append(np.nan); continue
    ki = np.searchsorted(o['K'], r.strike)
    if ki >= len(o['K']) or o['K'][ki] != r.strike: pos.append(np.nan); rel_o.append(np.nan); rel_c1.append(np.nan); rel_c.append(np.nan); out_of.append(np.nan); hi_lo_w.append(np.nan); continue
    hi = o[(r.cp, 'high')][ki, r.jm]; lo = o[(r.cp, 'low')][ki, r.jm]; op = o[(r.cp, 'open')][ki, r.jm]; cl = o[(r.cp, 'close')][ki, r.jm]; c1 = o[(r.cp, 'close')][ki, r.jm - 1] if r.jm > 0 else np.nan; p = r.px_first
    pos.append((p - lo) / (hi - lo) if hi > lo else np.nan); rel_o.append(p / op - 1 if op > 0 else np.nan); rel_c.append(p / cl - 1 if cl > 0 else np.nan); rel_c1.append(p / c1 - 1 if c1 and c1 > 0 else np.nan)
    out_of.append(float(p < lo - 1e-9 or p > hi + 1e-9)); hi_lo_w.append((hi - lo) / cl if cl > 0 else np.nan)
D0['bar_pos'] = pos; D0['rel_open'] = rel_o; D0['rel_close'] = rel_c; D0['rel_prevclose'] = rel_c1; D0['outside_bar'] = out_of; D0['bar_width'] = hi_lo_w
D0['ref_vs_prevclose'] = (D0.lim_px / np.where(D0.buy, 1.15, 0.85)) / (D0.px_first / (1 + D0.rel_prevclose)) - 1
def a4(z):
    return pd.Series(dict(n=len(z), n_bar=int(z.bar_pos.notna().sum()), outside_bar=z.outside_bar.mean(), pos_med=z.bar_pos.median(), pos_p25=z.bar_pos.quantile(.25), pos_p75=z.bar_pos.quantile(.75),
                          abs_gap_to_open_med=z.rel_open.abs().median(), abs_gap_to_close_med=z.rel_close.abs().median(), abs_gap_to_prevclose_med=z.rel_prevclose.abs().median(),
                          signed_vs_close_med=z.rel_close.median(), bar_width_med=z.bar_width.median(), fill_secs_med=z.fill_secs.median()))
A4 = D0.groupby(['klass', 'side']).apply(a4).reset_index(); A4.to_csv(f'{OUT}/bl_d0u_a4_bar.csv', index=False)
R['a4_outside_bar_overall'] = float(D0.outside_bar.mean()); R['a4_pos_by_side'] = {s: float(D0[D0.side == s].bar_pos.median()) for s in ('Buy', 'Sell')}
# does the decision-time reference (limit / 1.15) track the previous close or the current open better?
ref = D0.lim_px / np.where(D0.buy, 1.15, 0.85); R['a4_ref_vs_open_abs_med'] = float((ref / (D0.px_first / (1 + D0.rel_open)) - 1).abs().median()); R['a4_ref_vs_prevclose_abs_med'] = float((ref / (D0.px_first / (1 + D0.rel_prevclose)) - 1).abs().median())
R['a4_ref_vs_fill_abs_med'] = float((ref / D0.px_first - 1).abs().median())
# --- A5 dripping
ev = D0.groupby('eid').agg(klass=('klass', 'first'), lots=('lots', 'sum'), n=('lots', 'size'), span=('tod', lambda s: s.max() - s.min()), und=('und', 'first'))
gaps = D0.sort_values(['eid', 'tod', 'row']).groupby('eid').tod.diff().dropna()
gk = D0.sort_values(['eid', 'tod', 'row']).assign(g=lambda x: x.groupby('eid').tod.diff()).dropna(subset=['g'])
out = []
for k, z in ev.groupby('klass'):
    m = z[z.n > 1]; g = gk[gk.klass == k].g
    out.append(dict(klass=k, events=len(z), multi_order_events=len(m), share_multi=len(m) / len(z), orders_per_multi_med=m.n.median() if len(m) else np.nan, orders_per_multi_p90=m.n.quantile(.9) if len(m) else np.nan,
                    span_s_med=m.span.median() if len(m) else np.nan, same_second_gap_share=float((g == 0).mean()) if len(g) else np.nan, gap_s_med=g.median() if len(g) else np.nan, lots_per_order_in_multi=(m.lots / m.n).median() if len(m) else np.nan))
A5 = pd.DataFrame(out); A5.to_csv(f'{OUT}/bl_d0u_a5_drip.csv', index=False)
D0.to_pickle(f'{OUT}/bl_d0u_orders.pkl.gz'); rec('d0u_a', R); print(json.dumps({k: v for k, v in R.items()}, default=str, indent=1)[:3000])
print(A1[A1.day == 'D0'].round(2).to_string()); print(MX[MX.day == 'D0'].to_string()); print(A2[A2.day == 'D0'].round(3).to_string()); print(A5.round(2).to_string()); print(A4.round(3).to_string())
