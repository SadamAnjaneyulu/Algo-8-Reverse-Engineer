"""PHASE H: actual vs simulated (V1, NULL) P&L attribution by stream (gross, lot entry -> exit, rupees), discovery and holdout separately. Only lots that CLOSE on D0 or at settlement are attributed (lots closed on D-1 are common history for actual and simulation); carried lots include their D-1 P&L (entry to exit). Lump / stop-module / manual lots are passive in the simulator: the remainder is reported as 'passive/not simulated'.
Holdout numbers are read only because FREEZE.json exists."""
from collections import deque
from d0sim_import import *
Lg = pd.read_csv(f'{RES}/lot_lineage.csv'); S_ = pd.read_csv(f'{RES}/cycle_status.csv'); E = load_events(False); rows = []
def stream_actual(g):
    out = {}; g = g[g.close_day == 'D0']                       # lots that close on D0 or at settlement (lots closed on D-1 are common history and excluded from both sides)
    b = g[g.role == 'body']
    for oc in ('SCHEDULED_SALE', 'OFF_SCHEDULE_SALE', 'REPLACEMENT_SALE'): out[f'body D0-opened: {oc}'] = b[(b.open_day == 'D0') & (b.open_class == oc)].pnl.sum()
    out['body D0-opened: other classes'] = b[(b.open_day == 'D0') & (~b.open_class.isin(['SCHEDULED_SALE', 'OFF_SCHEDULE_SALE', 'REPLACEMENT_SALE']))].pnl.sum()
    c = b[b.open_day == 'D-1']
    for cc, lab in (('BUYBACK', 'buyback (stop-like/Clock-B/other)'), ('FINAL_LIQUIDATION', 'final liquidation'), ('SETTLEMENT', 'held to settlement')): out[f'body carried from D-1: {lab}'] = c[c.close_class == cc].pnl.sum()
    out['body carried from D-1: other closes'] = c[~c.close_class.isin(['BUYBACK', 'FINAL_LIQUIDATION', 'SETTLEMENT'])].pnl.sum()
    out['wings'] = g[g.role == 'wing'].pnl.sum(); out['passive/not simulated (lump, stop-module, manual)'] = g[g.role.isin(['lump', 'stop'])].pnl.sum(); return out
def stream_sim(c, und, ev_d1, orders, total_gross):
    lot = LOT[und]; body, wing, _, _ = start_book(ev_d1); S0 = YAHOO[und].close.get(pd.Timestamp(c['d0']), np.nan); out = defaultdict(float); lots = {'body': {k: deque([[x[0], x[1], 'CARRIED'] for x in L]) for k, L in body.items()}, 'wing': {k: deque([[x[0], x[1], 'CARRIED'] for x in L]) for k, L in wing.items()}}
    for o in orders.sort_values('j', kind='stable').itertuples():
        role = o.role; k = (o.cp, o.strike); Lq = lots[role].setdefault(k, deque()); q = o.lots; closing = (role == 'body' and o.side == 1) or (role == 'wing' and o.side == -1)
        if not closing: Lq.append([q, o.ref_px, 'D0:' + o.cls]); continue
        while q > 1e-9 and Lq:
            x = Lq[0]; t = min(q, x[0]); pnl = ((x[1] - o.ref_px) if role == 'body' else (o.ref_px - x[1])) * t * lot
            key = ('wings' if role == 'wing' else (f'body D0-opened: {x[2][3:]}' if x[2].startswith('D0:') else ('body carried from D-1: ' + {'FINAL_LIQUIDATION': 'final liquidation', 'STOP_LIQUIDATION': 'other closes'}.get(o.cls, 'buyback (stop-like/Clock-B/other)')))); out[key] += pnl; x[0] -= t; q -= t
            if x[0] <= 1e-9: Lq.popleft()
    for role in lots:
        for (cp, k), Lq in lots[role].items():
            for x in Lq:
                v = max(S0 - k, 0) if cp == 'CE' else max(k - S0, 0); pnl = ((x[1] - v) if role == 'body' else (v - x[1])) * x[0] * lot
                key = 'wings' if role == 'wing' else (f'body D0-opened: {x[2][3:]}' if x[2].startswith('D0:') else 'body carried from D-1: held to settlement'); out[key] += pnl
    return out
rr = []
for split in ('DISCOVERY', 'HOLDOUT'):
    st = S_[(S_.split == split) & S_.carry_in_known]; act = defaultdict(float); simv = {v: defaultdict(float) for v in ('V1', 'NULL')}
    for r in st.itertuples():
        g = Lg[(Lg.und == r.und) & (Lg.expiry == r.expiry)]
        for k, v in stream_actual(g).items(): act[k] += v
        ev = E[(E.und == r.und) & (E.expiry == r.expiry)]; c = load_cycle(r.und, r.expiry, r.d1, r.d0)
        for v in simv:
            f = f'{RES}/replay_orders_{split}_{v}.csv' if (split == 'HOLDOUT' or os.path.exists(f'{RES}/replay_orders_{split}_{v}.csv')) else f'{RES}/dev_replay_orders_{v}.csv'
            O = pd.read_csv(f); O = O[(O.und == r.und) & (O.expiry == r.expiry)]
            for k, x in stream_sim(c, r.und, ev[ev.day == 'D-1'], O, None).items(): simv[v][k] += x
    keys = sorted(set(act) | set(simv['V1']) | set(simv['NULL']))
    for k in keys: rr.append(dict(split=split, cycles=len(st), stream=k, actual=act.get(k, 0), sim_V1=simv['V1'].get(k, 0), sim_NULL=simv['NULL'].get(k, 0)))
R = pd.DataFrame(rr); R.to_csv(f'{RES}/pnl_attribution.csv', index=False); pd.set_option('display.width', 250); print((R.set_index(['split', 'stream'])[['actual', 'sim_V1', 'sim_NULL']] / 1e5).round(2).to_string())
