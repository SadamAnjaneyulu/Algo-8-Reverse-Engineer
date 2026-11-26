"""Phase A G5 (plan: reports/PHASE_A_G1_G6_PLAN.md): cycle-stop constant with limit-implied prices. MTM (cash since the D-1 open + open positions x mark x lot size) at the second of the first s_ order of each stopped cycle under
(a) previous-minute close, (b) current-minute open, (c) previous close except the contracts the s_ orders trade in their first 10 s, which use decision prices (buy: limit / 1.15; sell: limit / 0.85). Output outputs/phaseA/g5.json, g5_stops.csv"""
import sys, os, json, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from bl_common import *
PA = f'{OUT}/phaseA'; os.makedirs(PA, exist_ok=True)
def run():
    CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); MT = pd.read_pickle(f'{OUT}/bl_d0x_mtm.pkl.gz'); D0C = [i for i, r in enumerate(CY.itertuples()) if ((O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1)).any()]; rows = []; nonstop = []
    for i in D0C:
        r = CY.iloc[i]; u = float(r.unit); z = O[(O.und == r.und) & (O.expiry == r.expiry)].sort_values(['dayno', 'tod', 'row']); sg = np.where(z.side.str.lower() == 'buy', 1, -1); z = z.assign(sg=sg, cash=-sg * z.px_avg * z.lots * u); op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}
        s_ = z[(z.dayno == 1) & (z.module == 's_')]
        if not len(s_): nonstop.append(dict(i=i, cyc=f'{r.und}|{r.expiry}', min_close_mtm=float(MT['MT'][i]['close'].min()))); continue
        t0 = float(s_.tod.min()); j = int(max(0, (t0 - 33300) // 60)); pre = z[(z.dayno == 0) | ((z.dayno == 1) & (z.tod < t0))]; cash = pre.cash.sum(); pos = pre.groupby(['cp', 'strike']).apply(lambda g: (g.sg * g.lots).sum()).to_dict()
        first = s_[s_.tod <= t0 + 10]; dec = {}
        for q in first.itertuples():
            px = q.lim_px / 1.15 if q.side.lower() == 'buy' else q.lim_px / 0.85; dec.setdefault((q.cp, q.strike), []).append(px)
        dec = {k: float(np.mean(v)) for k, v in dec.items()}; out = {}
        for m in ('a_prev_close', 'b_open', 'c_prev_close_plus_decision_prices'):
            v = cash; used = 0
            for (cp, k), n in pos.items():
                if n == 0: continue
                x = ki.get(int(k))
                if m.startswith('c') and (cp, k) in dec: v += n * dec[(cp, k)] * u; used += 1; continue
                if x is None: continue
                px = (op[(cp, 'close')][x, j - 1] if j > 0 else op[(cp, 'open')][x, 0]) if not m.startswith('b') else op[(cp, 'open')][x, j]
                if px == px: v += n * px * u
            out[m] = float(v); out['decision_contracts_used'] = used
        rows.append(dict(i=i, cyc=f'{r.und}|{r.expiry}', stop_time=f'{int(t0) // 3600:02d}:{int(t0) % 3600 // 60:02d}:{int(t0) % 60:02d}', before_0916=bool(t0 < 33360), s_orders=int(len(s_)), **out))
    S_ = pd.DataFrame(rows); N_ = pd.DataFrame(nonstop); S_.to_csv(f'{PA}/g5_stops.csv', index=False); res = dict(stops=int(len(S_)), gap_stops_before_0916=int(S_.before_0916.sum()), non_stop_cycles=int(len(N_)), non_stop_worst_minute_close_mtm=float(N_.min_close_mtm.min()), non_stop_median_worst=float(N_.min_close_mtm.median()))
    X = S_[~S_.before_0916]; res['non_gap_stops'] = int(len(X))
    for m in ('a_prev_close', 'b_open', 'c_prev_close_plus_decision_prices'):
        v = X[m]; med = v.median(); res[m] = dict(levels_rupees=[round(x) for x in v.sort_values().tolist()], median=float(med), min=float(v.min()), max=float(v.max()), spread_over_median=float((v.max() - v.min()) / abs(med)) if med else None, within_10pct_of_median=int(((v - med).abs() <= 0.10 * abs(med)).sum()), n=int(len(v)),
                                                  smallest_magnitude_stop=float(v.max()), non_stop_min_above_smallest_stop=bool(N_.min_close_mtm.min() > v.max()))
    c = res['c_prev_close_plus_decision_prices']; res['verdict'] = 'consistent with a single MTM constant' if (c['within_10pct_of_median'] == c['n'] and c['non_stop_min_above_smallest_stop']) else 'not a single MTM constant (under the pre-set rule)'
    res['gap_stops'] = S_[S_.before_0916][['cyc', 'stop_time', 'a_prev_close', 'c_prev_close_plus_decision_prices']].round(0).to_dict('records')
    json.dump(res, open(f'{PA}/g5.json', 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=lambda z: round(float(z), 3))); print(S_.round(0).to_string(index=False))
if __name__ == '__main__': run()
