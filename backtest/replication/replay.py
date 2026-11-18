"""Historical replay on the 35 cycles for which the REAL Algo 8 ledger exists: simulate the reconstructed rules on the same market data and compare decisions and P&L with the live fills."""
import json, math
from sim import *
from bt import cycles as Cy
LP = pd.read_csv(f'{RES}/live_cycle_pnl.csv', parse_dates=['expiry']); EV = pd.read_csv(f'{RES}/live_decision_events.csv')
cl = Cy.cycle_list(); LOT = {'NIFTY': 65, 'SENSEX': 20}; d0l = d0_median_ladder(); rows = []; sim_events = []
for r in LP.itertuples():
    e = r.expiry.strftime('%Y-%m-%d'); m = cl[(cl.und == r.und) & (cl.expiry == e)].iloc[0]; c = load_cycle(r.und, e, m.d1, m.d0)
    for v in ('R1', 'R2'):
        s = simulate(c, LOT[r.und], v, d0l)
        rows.append(dict(variant=v, und=r.und, expiry=e, d1=m.d1, d0=m.d0, live_gross=r.gross, live_net=r.net_cost_model, live_orders=r.orders, live_stop=r.stop_cycle, sim_gross=s['gross'], sim_net=s['net'], sim_orders=s['n_orders'], sim_stop=s['stopped'] is not None, sim_stop_at=(s['stopped'][0] * 375 + s['stopped'][1]) if s['stopped'] else np.nan, sim_costs=s['costs'], sim_slip=s['slippage']))
        for ev in s['events']: sim_events.append(dict(variant=v, und=r.und, expiry=e, **ev))
R_ = pd.DataFrame(rows); R_.to_csv(f'{RES}/replay_cycle_pnl.csv', index=False); pd.DataFrame(sim_events).to_csv(f'{RES}/replay_sim_events.csv', index=False)
pd.set_option('display.width', 250)
for v in ('R1', 'R2'):
    x = R_[R_.variant == v]; cg = np.corrcoef(x.live_gross, x.sim_gross)[0, 1]; cn = np.corrcoef(x.live_net, x.sim_net)[0, 1]
    tp = ((x.live_stop) & (x.sim_stop)).sum(); fp = ((~x.live_stop) & (x.sim_stop)).sum(); fn = ((x.live_stop) & (~x.sim_stop)).sum()
    print(v, f'cycles={len(x)} live_gross={x.live_gross.sum():,.0f} sim_gross={x.sim_gross.sum():,.0f} live_net={x.live_net.sum():,.0f} sim_net={x.sim_net.sum():,.0f} corr(gross)={cg:.2f} corr(net)={cn:.2f} orders live/sim median={x.live_orders.median():.0f}/{x.sim_orders.median():.0f} stops TP={tp} FP={fp} FN={fn}')
