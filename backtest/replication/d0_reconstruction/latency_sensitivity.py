"""Alternative sequencing/latency: every simulated fill is executed at the OPEN of the NEXT minute (decision at j, fill at j+1). Implemented without touching d0_sim.py by shifting the D0 open arrays. Reports agreement and P&L for variant V1 (both splits)."""
import copy
from d0_sim import *
E = load_events(False); S_ = pd.read_csv(f'{RES}/cycle_status.csv'); S_ = S_[S_.carry_in_known]; LPn = pd.read_csv(f'{RRES}/live_cycle_pnl.csv')
for sp in ('DISCOVERY', 'HOLDOUT'):
    orders = []; rows = []
    for st in S_[S_.split == sp].itertuples():
        ev = E[(E.und == st.und) & (E.expiry == st.expiry)]; c = copy.deepcopy(load_cycle(st.und, st.expiry, st.d1, st.d0))
        for r in ('CE', 'PE'): o = c[(1, r, 'open')]; c[(1, r, 'open')] = np.concatenate([o[:, 1:], c[(1, r, 'close')][:, -1:]], axis=1)
        r = simulate_d0(c, st.und, ev[ev.day == 'D-1'], price_stop=True); o = r['orders']; o['und'] = st.und; o['expiry'] = st.expiry; orders.append(o); LP = LPn[(LPn.und == st.und) & (LPn.expiry.str[:10] == st.expiry)].iloc[0]; rows.append((r['gross'] - r['v0'], LP.gross - r['v0']))
    pd.concat(orders).to_csv(f'{RES}/replay_orders_{sp}_V1_LAT1.csv', index=False); a = np.array(rows); print(sp, 'V1 +1min latency: D0 increment sim', a[:, 0].sum().round(0), 'live', a[:, 1].sum().round(0), 'corr', np.corrcoef(a[:, 0], a[:, 1])[0, 1].round(2))
