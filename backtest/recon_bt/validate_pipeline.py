"""Pipeline validation (PREREGISTRATION section 6): data builder vs the 2026 research caches, D-1 orders vs B1 on the 32 development cycles (stop off)."""
import sys, os, json, warnings
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')); DD = f'{R}/backtest/replication/deep_dive'
for p in (R, f'{R}/backtest', f'{DD}/src', f'{R}/d1_strategy', f'{R}/d0_strategy'): sys.path.insert(0, p)
warnings.filterwarnings('ignore'); os.chdir(f'{DD}/src')
import numpy as np, pandas as pd
import bl_common, bl_fr_sim as S, bl_p1_5a_port as A
from recon_bt.engine_run import load_session
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
OUT = bl_common.OUT; B1 = pd.read_pickle(f'{OUT}/scoring/d1_F_v2_onelot/engine_orders_one_lot_v2.pkl.gz'); rows = []
for i, r in enumerate(S.CY.itertuples()):
    sp1, o1 = load_session(r.und, r.expiry, r.d1); ref_o = S.OH[(r.und, r.expiry)]; ref_op = S.OP[(r.und, r.expiry)]
    d1_eq = all(np.allclose(sp1[c].values, ref_o[c].values, equal_nan=True) for c in ('open', 'high', 'low', 'close')) and np.array_equal(o1['K'], ref_op['K']) and all(np.allclose(o1[k], ref_op[k], equal_nan=True) for k in o1 if isinstance(k, tuple))
    d0_eq = None
    if (r.und, r.expiry) in A.OPT:
        sp0, o0 = load_session(r.und, r.expiry, r.expiry); ro = A.OPT[(r.und, r.expiry)]; rs = A.SPT[(r.und, r.expiry)]
        d0_eq = all(np.allclose(sp0[c].values, rs[c].values, equal_nan=True) for c in ('open', 'high', 'low', 'close')) and np.array_equal(o0['K'], ro['K']) and all(np.allclose(o0[k], ro[k], equal_nan=True) for k in o0 if isinstance(k, tuple))
    feed = ReplayFeed(sp1.open.values, sp1.high.values, sp1.low.values, sp1.close.values, o1['K'], {k: v for k, v in o1.items() if isinstance(k, tuple)}); cfg = config_for(r.und, r.d1, order_split='one_lot_v2'); e = D1Engine(cfg, feed, PaperBroker(feed)); run_replay(e, feed); df = e.orders_frame(); b = B1[i]
    cols = ['ts', 'right', 'strike', 'lots', 'side', 'role']; same = len(df) == len(b) and (len(df) == 0 or df.reset_index(drop=True)[cols].equals(b.reset_index(drop=True)[cols]))
    rows.append(dict(cyc=f'{r.und}|{r.expiry}', d1_arrays_equal=bool(d1_eq), d0_arrays_equal=d0_eq, d1_orders=len(df), b1_orders=len(b), d1_orders_identical_to_B1=bool(same)))
X = pd.DataFrame(rows); res = dict(cycles=len(X), d1_arrays_equal=int(X.d1_arrays_equal.sum()), d0_arrays_equal=int(X.d0_arrays_equal.fillna(False).sum()), d0_cycles_with_cache=int(X.d0_arrays_equal.notna().sum()), d1_orders_identical=int(X.d1_orders_identical_to_B1.sum()), total_orders=int(X.d1_orders.sum()), b1_total=int(X.b1_orders.sum()))
res['passed'] = res['d1_arrays_equal'] == res['cycles'] and res['d0_arrays_equal'] == res['d0_cycles_with_cache'] and res['d1_orders_identical'] == res['cycles']
os.makedirs(f'{R}/backtest/recon_bt/results', exist_ok=True); json.dump(res, open(f'{R}/backtest/recon_bt/results/pipeline_validation.json', 'w'), indent=1); X.to_csv(f'{R}/backtest/recon_bt/results/pipeline_validation_cycles.csv', index=False); print(res); print(X[~X.d1_orders_identical_to_B1.astype(bool) | ~X.d1_arrays_equal.astype(bool)].to_string(index=False))
