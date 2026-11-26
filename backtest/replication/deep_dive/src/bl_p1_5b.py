"""Gate 5b: order-level D0 reconstruction (plan reports/PHASE1_GATE5B_PLAN.md). Converts the standalone engine's minute events to order records, builds the real D0 order frame, scores with the frozen spec v1.1 (mode T: the real carried book is the opening state),
adds D0 portfolio-state reconciliation with the carried book, and a mismatch ledger by class. Real D0 orders are used only for evaluation. Evidence label: historical reproduction (fitted constants out-of-fold by cycle halves; structure in-sample)."""
import sys, os, json, time, hashlib, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d0_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_p1_5a_port as A, bl_common, bl_oscore as Q
from d0_algo import D0Engine
OUT = bl_common.OUT; AGG_STOP_PARTS = True; OPEN_S = 33300; FREEZE = {'NIFTY': 27, 'SENSEX': 50}
VALIDITY = {'num': 'DAY', 'h_': 'IOC', 'v_': 'IOC', 'm_': 'IOC', 's_': ''}                  # observed in the real D0 log (s_ is mixed DAY/IOC: left unspecified, never assumed)
CLS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('v_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'body_long', ('num', 'close_long'): 'body_long'}
def real_frame(cids):
    CY = A.CY; rows = []
    for i in cids:
        r = CY.iloc[i]; z = A.O()[(A.O().und == r.und) & (A.O().expiry == r.expiry) & (A.O().dayno == 1)].copy(); z['cls'] = ['stop' if m == 's_' else CLS.get((m, ro), 'not_modelled') for m, ro in zip(z.module, z.role)]
        rows.append(pd.DataFrame(dict(cyc=f'{r.und}|{r.expiry}', day=1, cp=z.cp.values, side=z.side.values, strike=z.strike.astype(float).values, lots=z.lots.astype(int).values, t=z.t_first.astype(int).values, row=z.row.values, cls=z.cls.values, validity=z.validity.values, module=z.module.values, role=z.role.values)))
    return pd.concat(rows, ignore_index=True)
def sim_frame(items, one_lot=False):
    """items: [(cid, engine_after_run)] -> order records. One event = one order (split at the freeze quantity), or single-lot orders when one_lot (a labelled scoring-layer sensitivity)."""
    CY = A.CY; rows = []; 
    for i, e in items:
        r = CY.iloc[i]; cyc = f'{r.und}|{r.expiry}'; fz = FREEZE[r.und]; seq = 0
        def add(cls, cp, strike, n, side, module, role, t):
            nonlocal seq
            chunks = [1] * n if one_lot else [min(fz, n - x) for x in range(0, n, fz)]
            for c in chunks: rows.append(dict(cyc=cyc, day=1, cp=cp, side=side, strike=float(strike), lots=int(c), t=float(t), seq=seq, cls=cls, validity=VALIDITY.get(module, ''), module=module, role=role, t_resolution='minute')); seq += 1
        for ev in e.events:
            t = OPEN_S + 60 * ev.j
            if ev.cls == 'stop':
                if AGG_STOP_PARTS:                      # corrected convention (Addendum 1 of the 5b plan): one order per contract and component KIND, as the plan stated; engine parts are per-lot tuples
                    agg = {}
                    for kind, n in ev.parts: agg[kind] = agg.get(kind, 0) + n
                    parts = list(agg.items())
                else: parts = ev.parts                  # first-run convention (one order per part tuple), kept only to reproduce the archived first run
                for kind, n in parts: add('stop', ev.cp, ev.strike, n, 'sell' if kind == 'long' else 'buy', 's_', 'close_long' if kind == 'long' else 'cover_short', t)
            else: add(ev.cls, ev.cp, ev.strike, ev.lots, ev.side, ev.module, ev.role, t)
    return pd.DataFrame(rows)
def attrs_of(cids, real):
    CY = A.CY; stop = set(real[real.cls == 'stop'].cyc); return pd.DataFrame([dict(cyc=f'{CY.iloc[i].und}|{CY.iloc[i].expiry}', und=CY.iloc[i].und, step=float(bl_common.ref.STEP[CY.iloc[i].und]), version=CY.iloc[i].version, era='after' if CY.iloc[i].expiry >= '2026-08-03' else 'before', outlier=False, stop=(f'{CY.iloc[i].und}|{CY.iloc[i].expiry}' in stop)) for i in cids])
def run_split(P, cids, mode='enforce'):
    out = []
    for i in cids:
        c = A.config_of(P, i); c.risk_mode = mode; op = A.opening_of(i); e = D0Engine(c, A.market_of(i), op); e.run(); out.append((i, e, op))
    return out
def carry_state(real, sim, pairs, opens):
    """book agreement at matched events WITH the carried book: per matched pair, contract-level L1 distance between the real and the simulated position (opening net + cumulative orders), normalised by gross real lots; short/long lots per right"""
    rows = []; cyc_of = {f'{A.CY.iloc[i].und}|{A.CY.iloc[i].expiry}': i for i in opens}
    for cyc, rg in real.groupby('cyc'):
        sg = sim[sim.cyc == cyc]; pp = pairs[pairs.ri.isin(rg.index)]
        if not len(pp): continue
        op = opens[cyc_of[cyc]]; base = {}
        for cp, k, e in op.lots: base[(cp, float(k))] = base.get((cp, float(k)), 0) - 1
        for (md, cp, k), n in op.longs.items(): base[(cp, float(k))] = base.get((cp, float(k)), 0) + n
        for (md, cp, k), n in op.oshort.items(): base[(cp, float(k))] = base.get((cp, float(k)), 0) - n
        rd = rg.sort_values(['t', 'row']); sd = sg.sort_values(['t', 'seq']); cons = sorted(set(zip(rd.cp, rd.strike)) | set(zip(sd.cp, sd.strike)) | set(base)); ci = {c: n for n, c in enumerate(cons)}
        def cum(df): 
            M = np.zeros((len(df), len(cons))); sgn = np.where(df.side.str.lower().values == 'buy', 1, -1) * df.lots.values
            for n, (cp, k, q) in enumerate(zip(df.cp.values, df.strike.values, sgn)): M[n, ci[(cp, k)]] = q
            return np.cumsum(M, axis=0)
        b0 = np.zeros(len(cons))
        for c_, v in base.items(): b0[ci[c_]] = v
        rc = cum(rd) + b0; sc = cum(sd) + b0; rpos = {o: n for n, o in enumerate(rd.index)}; spos = {o: n for n, o in enumerate(sd.index)}
        for p in pp.itertuples():
            a = rc[rpos[p.ri]]; b = sc[spos[p.si]]; rows.append(dict(cyc=cyc, ri=p.ri, si=p.si, l1=float(np.abs(a - b).sum()), gross_real=float(np.abs(a).sum()), SL_equal=bool(all(((a[[ci[c] for c in cons if c[0] == cp]] < 0).sum() * 0 + (-a[[ci[c] for c in cons if c[0] == cp and a[ci[c]] < 0]]).sum() == (-b[[ci[c] for c in cons if c[0] == cp and b[ci[c]] < 0]]).sum() and a[[ci[c] for c in cons if c[0] == cp and a[ci[c]] > 0]].sum() == b[[ci[c] for c in cons if c[0] == cp and b[ci[c]] > 0]].sum()) for cp in ('CE', 'PE')))))
    X = pd.DataFrame(rows); X['l1_norm'] = X.l1 / X.gross_real.clip(lower=1); return X
if __name__ == '__main__':
    t0 = time.time(); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); OD = f'{OUT}/phase1/5b'; os.makedirs(OD, exist_ok=True); SETS = {'OOF': (['OOF half 0 test', 'OOF half 1 test']), 'forwardA': ['forward A (same version, later cycles)'], 'forwardB': ['forward B (train V1, test V2)']}; summary = {}
    for name, keys in SETS.items():
        items = []; opens = {}
        for k in keys:
            P = PR[k]
            for i, e, op in run_split(P, P['test']): items.append((i, e)); opens[i] = op
        cids = [i for i, _ in items]; real = real_frame(cids); attrs = attrs_of(cids, real)
        for conv in ('events', 'one_lot'):
            sim = sim_frame(items, one_lot=(conv == 'one_lot')); d = f'{OD}/{name}_{conv}'; os.makedirs(d, exist_ok=True)
            R = Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=True, bootstrap=1000)
            for k, v in R.items():
                if isinstance(v, pd.DataFrame) and not k.startswith('_'): v.to_csv(f'{d}/{k}.csv', index=False)
            for k, v in R['unmatched'].items():
                if isinstance(v, pd.DataFrame): v.to_csv(f'{d}/unmatched_{k}.csv', index=False)
            R['_pairs'].to_csv(f'{d}/pairs.csv', index=False); real.to_csv(f'{d}/real_orders.csv', index=False); sim.to_csv(f'{d}/sim_orders.csv', index=False); attrs.to_csv(f'{d}/attrs.csv', index=False)
            CS = carry_state(Q.prepare_real(real), Q.prepare_sim(sim), R['_pairs'], opens); CS.to_csv(f'{d}/carry_state.csv', index=False)
            st = R['strictness']; f = lambda tol, lvl: float(st[(st.cumulative_tolerance_s == tol) & (st.level == lvl)].F1.iloc[0])
            summary[f'{name}_{conv}'] = dict(cycles=len(cids), real_orders=int(len(real)), sim_orders=int(len(sim)), keys_F1_0s=f(0, 'keys'), keys_F1_5s=f(5, 'keys'), keys_F1_60s=f(60, 'keys'), strict_F1_60s=f(60, 'lots_exact'), strike_exact_F1_60s=f(60, 'strike_exact'), carry_state_L1_median=float(CS.l1_norm.median()), carry_state_SL_equal=float(CS.SL_equal.mean()), placebo_keys_F1_60s=R['time_shift_placebo']['F1_keys_at_60s'], per_cycle_F1=R['per_cycle_F1'], ci=R['pooled_F1_ci95'])
            json.dump({k: v for k, v in R.items() if k in ('run', 'ambiguity', 'timing', 'strike', 'quantity', 'type', 'by_class', 'by_block', 'per_cycle_F1', 'pooled_F1_ci95', 'tie_break_range', 'time_shift_placebo', 'by_attribute')}, open(f'{d}/report.json', 'w'), indent=1, default=lambda o: o.to_dict('records') if hasattr(o, 'to_dict') else float(o))
            print(name, conv, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in summary[f'{name}_{conv}'].items() if k not in ('per_cycle_F1', 'ci')}, flush=True)
    json.dump(summary, open(f'{OD}/summary.json', 'w'), indent=1, default=float); print('seconds', round(time.time() - t0))
