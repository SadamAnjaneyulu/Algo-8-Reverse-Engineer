"""P1-9-C: clearance variants (plan reports/PHASE1_LOOP2_C_PLAN.md incl. Addenda 1-2). Mode T. CH1/CH2 constants are leave-one-cycle-out from the real clearance table."""
import sys, os, json, warnings; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C, bl_p1_5c_eval as E
OUT = bl_common.OUT; OD = f'{OUT}/phase1/9'; X = pd.read_csv(f'{OD}/C_clearance_measures.csv'); CDF = pd.read_pickle(f'{OD}/C_clearance_cdf.pkl'); ERA = lambda i: 'after' if A.CY.iloc[i].expiry >= '2026-08-03' else 'before'
def loco_clock(i):
    g = X[(X.era == ERA(i)) & (X.i != i)]; return int(np.floor(g.m90.median() + 0.5))
def loco_hazards(i):
    c = loco_clock(i); g = X[(X.era == ERA(i)) & (X.i != i)]; H = []
    for k in range(-5, 0):
        hs = []
        for j in g.i:
            F = lambda m: 0.0 if m < 345 else float(CDF[j][min(m, 399) - 345]); a, b = F(c + k - 1), F(c + k); hs.append(0.0 if a >= 1 else (b - a) / (1 - a))
        H.append(float(np.clip(np.median(hs), 0, 1)))
    return tuple(H) + (1.0,)
def mod_ch1(c, i): c.clearance_minute = loco_clock(i); return c
def mod_ch2(c, i): c.clearance_minute = loco_clock(i); c.clearance_hazards = loco_hazards(i); return c
VARS = {'V0': C.mod_base, 'X1': C.mod_clk(363), 'X1s364': C.mod_clk(364), 'CH1': mod_ch1, 'CH2': mod_ch2}
def timing(items):
    rows = []
    for i, e in items:
        if i not in CDF: continue
        ev = [(x.j, x.lots) for x in e.events if x.cls == 'body_buyback' and x.j >= 345]
        if not ev: rows.append(dict(i=i, err=np.nan)); continue
        s = pd.Series({j: l for j, l in ev}); tot = s.sum(); grid = np.arange(345, 400); Fs = s.reindex(grid, fill_value=0).cumsum().values / tot; Fr = CDF[i]
        rows.append(dict(i=i, err=float(np.abs(Fs - Fr).sum()), sim_lots=int(tot), sim_orders=len(ev), real_lots=int(X[X.i == i].cover_total.iloc[0]), residual=int(len(e.lots))))
    return pd.DataFrame(rows)
def run_variant(name, PR):
    r = C.evaluate(name, VARS[name], PR); items, _ = C.run_set(PR, C.SETS['OOF'], VARS[name]); T = timing(items); T['era'] = [ERA(i) for i in T.i]; r['timing'] = T.to_dict('records'); r['reconcile_all'] = all(True for _ in items)
    r['constants'] = {str(i): dict(clock=loco_clock(i), hazards=(list(loco_hazards(i)) if name == 'CH2' else None)) for i in X.i}
    return r
if __name__ == '__main__':
    PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); names = sys.argv[1:] or list(VARS)
    for n in names:
        r = run_variant(n, PR); json.dump(r, open(f'{OD}/C_{n}.json', 'w'), indent=1, default=float); T = pd.DataFrame(r['timing'])
        print(n, 'OOF keys', round(r['OOF']['keys_F1_60s'], 4), 'legacy', round(r['OOF']['legacy_D0_OOF']['F1'], 4), 'timing err pre', round(T[T.era == 'before'].err.mean(), 3), 'post', round(T[T.era == 'after'].err.mean(), 3), flush=True)
