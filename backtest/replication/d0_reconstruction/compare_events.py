"""Actual vs simulated D0 behaviour at event, execution and portfolio-state level. Usage: python compare_events.py <orders_csv> <split: DISCOVERY|HOLDOUT> <tag>.
Matching is hierarchical and count-based (lots): L1 same cycle/right/strike/2-min bucket; L2 same cycle/right/2-min bucket (=> strike mismatch); L3 same cycle/right/10-min bucket (=> timing mismatch); unmatched = missing rule (actual) / spurious (simulated).
HOLDOUT evaluation is only possible after freeze.py (guard in d0common.load_events)."""
import sys
from d0common import *
orders_csv, split, tag = sys.argv[1], sys.argv[2], sys.argv[3]
A = load_events(discovery_only=(split == 'DISCOVERY')); A = A[A.split == split]; O = pd.read_csv(orders_csv); S_ = pd.read_csv(f'{RES}/cycle_status.csv'); ok = S_[(S_.split == split) & S_.carry_in_known][['und', 'expiry']]
A = A.merge(ok, on=['und', 'expiry']); O = O.merge(ok, on=['und', 'expiry']); A0 = A[A.day == 'D0'].copy(); A0['j'] = A0.sec // 60 - 555
O['sec_in'] = O.j * 60
def match(sim, act, label):
    """returns summary row + detail rows"""
    sim = sim.copy(); act = act.copy(); res = dict(category=label, sim_lots=sim.lots.sum(), actual_lots=act.lots.sum()); remS = {}; remA = {}
    keysS = lambda lv: {1: ['und', 'expiry', 'cp', 'strike', 'b2'], 2: ['und', 'expiry', 'cp', 'b2'], 3: ['und', 'expiry', 'cp', 'b10']}[lv]
    for d in (sim, act): d['b2'] = d.j // 2; d['b10'] = d.j // 10
    sim['rem'] = sim.lots; act['rem'] = act.lots; out = {}
    for lv in (1, 2, 3):
        k = keysS(lv); s = sim.groupby(k).rem.sum().rename('s'); a = act.groupby(k).rem.sum().rename('a'); m = pd.concat([s, a], axis=1).fillna(0); mt = np.minimum(m.s, m.a); out[lv] = mt.sum()
        # consume matched lots proportionally
        for d, col in ((sim, 's'), (act, 'a')):
            f = (m[col] - mt) / m[col].replace(0, np.nan); f = f.fillna(1.0); idx = d.set_index(k).index; d['rem'] = d.rem.values * f.reindex(idx).fillna(1.0).values
    S, Aa = sim.lots.sum(), act.lots.sum(); res.update(L1_exact=out[1], L2_strike_mismatch=out[2], L3_timing_mismatch=out[3], unmatched_sim_spurious=sim.rem.sum(), unmatched_actual_missing=act.rem.sum(),
                                                     precision_L1=out[1] / S if S else np.nan, precision_L2=(out[1] + out[2]) / S if S else np.nan, precision_L3=(out[1] + out[2] + out[3]) / S if S else np.nan, recall_L1=out[1] / Aa if Aa else np.nan, recall_L2=(out[1] + out[2]) / Aa if Aa else np.nan, recall_L3=(out[1] + out[2] + out[3]) / Aa if Aa else np.nan); return res
body = A0[A0.module == 'num']; sim_b = O[O.role == 'body']
cats = [('body sales (all classes)', sim_b[sim_b.side == -1], body[(body.side == 'Sell') & (body.opened_lots > 0)]),
        ('scheduled sales', sim_b[sim_b.cls == 'SCHEDULED_SALE'], body[body.event_class == 'SCHEDULED_SALE']),
        ('replacement sales', sim_b[sim_b.cls == 'REPLACEMENT_SALE'], body[body.event_class == 'REPLACEMENT_SALE']),
        ('buybacks excl. final liquidation', sim_b[(sim_b.side == 1) & (~sim_b.cls.isin(['FINAL_LIQUIDATION', 'STOP_LIQUIDATION']))], body[body.event_class == 'BUYBACK']),
        ('Clock-B buybacks (tick minute)', sim_b[sim_b.cls == 'CLOCKB_BUYBACK'], body[(body.event_class == 'BUYBACK') & (body.mm % 15 == 14)]),
        ('price-stop-like buybacks (actual: ratio>=1.55)', sim_b[sim_b.cls == 'PRICE_STOP_BUYBACK'], body[(body.event_class == 'BUYBACK') & (body.ratio_cheapest >= 1.55)]),
        ('final liquidation (>=15:10)', sim_b[sim_b.cls == 'FINAL_LIQUIDATION'], body[body.event_class == 'FINAL_LIQUIDATION'])]
wing_a = A0[A0.module == 'h_']; sim_w = O[O.role == 'wing']
cats += [('hedge additions', sim_w[sim_w.side == 1], wing_a[wing_a.side == 'Buy']), ('hedge reductions', sim_w[sim_w.side == -1], wing_a[wing_a.side == 'Sell'])]
rows = [match(s.assign(j=s.j), a.assign(j=a.j), lab) for lab, s, a in cats]; M = pd.DataFrame(rows); M.to_csv(f'{RES}/compare_events_{tag}.csv', index=False); pd.set_option('display.width', 250); pd.set_option('display.max_columns', 20); print(M[['category', 'sim_lots', 'actual_lots', 'precision_L1', 'precision_L2', 'precision_L3', 'recall_L1', 'recall_L2', 'recall_L3']].round(3).to_string(index=False))
# execution agreement on L1-matched sales: price diff and strike agreement
ms = sim_b[sim_b.side == -1].copy(); ms['b2'] = ms.j // 2; ab = body[(body.side == 'Sell') & (body.opened_lots > 0)].copy(); ab['b2'] = ab.j // 2
x = ms.merge(ab.groupby(['und', 'expiry', 'cp', 'strike', 'b2']).agg(a_px=('px', 'mean')).reset_index(), on=['und', 'expiry', 'cp', 'strike', 'b2'])
print('execution: L1-matched sale orders', len(x), ' median (sim ref - actual)/actual price', round(float(((x.ref_px - x.a_px) / x.a_px).median()), 4), ' abs median', round(float(((x.ref_px - x.a_px) / x.a_px).abs().median()), 4))
# timing: for L2-type matches use nearest actual same-cycle same-right sale: median |dt| minutes
def nearest_dt(sim, act):
    d = []
    for (u, e, cp), g in sim.groupby(['und', 'expiry', 'cp']):
        a = np.sort(act[(act.und == u) & (act.expiry == e) & (act.cp == cp)].j.values)
        if len(a): i = np.searchsorted(a, g.j.values); i = np.clip(i, 1, len(a) - 1) if len(a) > 1 else np.zeros(len(g), int); d.extend(np.abs(g.j.values - a[i]) if len(a) == 1 else np.minimum(np.abs(g.j.values - a[i]), np.abs(g.j.values - a[i - 1])))
    return np.array(d)
dt = nearest_dt(ms, ab); print('timing: median minutes from a simulated sale to the nearest actual same-right sale', np.median(dt) if len(dt) else None, ' share within 1 min', (dt <= 1).mean().round(3) if len(dt) else None)
# portfolio-state agreement at hourly marks (net short body lots, by right) from order logs
st = []
for (u, e), g in A0.groupby(['und', 'expiry']):
    a_ = g[g.module == 'num']; e1 = A[(A.und == u) & (A.expiry == e) & (A.day == 'D-1') & (A.module == 'num')]; o = O[(O.und == u) & (O.expiry == e) & (O.role == 'body')]
    for cp in ('CE', 'PE'):
        s0 = (e1[e1.cp == cp].assign(x=lambda z: np.where(z.side == 'Sell', z.lots, -z.lots))).x.sum()
        for hh in (10, 11, 12, 13, 14, 15):
            t = hh * 60 - 555; sa = s0 + a_[(a_.cp == cp) & (a_.sec // 60 - 555 < t)].assign(x=lambda z: np.where(z.side == 'Sell', z.lots, -z.lots)).x.sum(); ss = s0 + o[(o.cp == cp) & (o.j < t)].assign(x=lambda z: np.where(z.side == -1, z.lots, -z.lots)).x.sum(); st.append(dict(und=u, expiry=e, cp=cp, hh=hh, actual=sa, sim=ss))
P = pd.DataFrame(st); P.to_csv(f'{RES}/portfolio_state_{tag}.csv', index=False); print('portfolio state (net short body lots): corr', np.corrcoef(P.actual, P.sim)[0, 1].round(3), ' MAE', (P.actual - P.sim).abs().mean().round(1), ' mean actual', P.actual.mean().round(1), ' mean sim', P.sim.mean().round(1), '| by hour MAE', P.assign(e=(P.actual - P.sim).abs()).groupby('hh').e.mean().round(1).to_dict())
