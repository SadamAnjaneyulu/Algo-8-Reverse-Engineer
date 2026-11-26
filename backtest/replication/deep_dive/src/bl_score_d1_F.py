"""FIRST order-level scoring run, D-1, mode F (free-running), spec v1.1. STRICTLY DIAGNOSTIC: its purpose is the mismatch profile, not a closure claim. Evidence label: historical reproduction (the engine's parameters were fitted on these cycles).
T is identical to F for D-1 (flat start) and is reported once. TF-E is not built. Order type uses the validity the engine emits explicitly. No P&L anywhere.
Outputs outputs/scoring/d1_F/ (report.json, tables as csv, run_record.json); also recomputes the legacy lot-level F1 on the SAME replay as a guard."""
import sys, os, json, time, hashlib, datetime, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../..'); sys.path.insert(0, '../../..'); sys.path.insert(0, '../../../../d1_strategy'); warnings.filterwarnings('ignore')
from multiprocessing import Pool
import numpy as np, pandas as pd
import validate_engine as V, bl_fr_sim as S, bl_common, bl_oscore as Q
CONV = os.environ.get('ORDER_SPLIT', 'freeze_v1')                                   # execution convention: 'freeze_v1' (baseline, outputs/scoring/d1_F, never overwritten) or 'one_lot_v2' (outputs/scoring/d1_F_v2_onelot)
assert CONV in ('freeze_v1', 'one_lot_v2'), CONV
OUT = bl_common.OUT; OD = f'{OUT}/scoring/' + ('d1_F' if CONV == 'freeze_v1' else 'd1_F_v2_onelot'); os.makedirs(OD, exist_ok=True)
SECOND_ROLES = {'scheduled_straddle', 'opening_wing_buy'}                      # rules that fix the second (timetable); everything else fires on a bar or derives from a bar-triggered order
def _run(i): return V.run_cycle(i, None if CONV == 'freeze_v1' else dict(order_split=CONV))
def build_sim(ORD, CY):
    rows = []
    for i, df in ORD.items():
        if not len(df): continue
        r = CY.iloc[i]; d = df.sort_values('ts', kind='stable').reset_index(drop=True)
        rows.append(pd.DataFrame(dict(cyc=f'{r.und}|{r.expiry}', day=0, cp=d.cp, side=d.side.str.lower(), strike=d.strike, lots=d.lots, t=d.ts, seq=np.arange(len(d)), cls=d.cls, validity=d.validity, module=d.module, role=d.role, t_resolution=np.where(d.role.isin(SECOND_ROLES), 'second', 'minute'))))
    return pd.concat(rows, ignore_index=True)
def build_real(CY):
    CLASS = Q._literal(os.path.join(Q.HERE, 'validate_engine.py'), 'CLASS'); R = S.REAL.copy(); R['cls'] = [CLASS.get((m, r_), 'not_modelled') for m, r_ in zip(R.module, R.role)]; R.loc[(R.cls == 'opening_wings') & (R.j > 2), 'cls'] = 'not_modelled'
    R['cyc'] = R.und + '|' + R.expiry; R['day'] = 0; R['t'] = R.t_first.astype(int); return R[['cyc', 'day', 'cp', 'side', 'strike', 'lots', 't', 'row', 'cls', 'validity', 'module', 'role']]
def build_attrs(CY):
    A = pd.DataFrame(dict(cyc=CY.und + '|' + CY.expiry, und=CY.und, step=CY.und.map(bl_common.ref.STEP), version=np.where(CY.d1 >= '2026-09-16', 'V2', 'V1'), era=np.where(CY.expiry >= '2026-08-03', 'after', 'before'), outlier=((CY.und == 'NIFTY') & (CY.d1 == '2026-10-16')).values))
    stop = set((S.REAL[S.REAL.module == 's_'].und + '|' + S.REAL[S.REAL.module == 's_'].expiry)); A['stop'] = A.cyc.isin(stop); return A
def tab(x):
    return x.to_dict('records') if isinstance(x, pd.DataFrame) else x
def jsonable(o):
    if isinstance(o, pd.DataFrame): return o.replace({np.nan: None}).to_dict('records')
    if isinstance(o, dict): return {str(k): jsonable(v) for k, v in o.items() if not str(k).startswith('_')}
    if isinstance(o, (list, tuple)): return [jsonable(v) for v in o]
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    return o
if __name__ == '__main__':
    t0 = time.time(); CY = S.CY
    with Pool(max(1, min(8, os.cpu_count() or 1))) as p: res = p.map(_run, range(len(CY)))
    ORD = {i: df for i, df, _ in res}; pd.to_pickle(ORD, f'{OD}/engine_orders_{CONV}.pkl.gz'); rejected = int(sum(n for _, _, n in res)); sim = build_sim(ORD, CY); real = build_real(CY); attrs = build_attrs(CY)
    # guard: the legacy lot-level F1 on THIS replay (adding validity/module must not change the replay)
    leg = Q.legacy_d1_scores(ORD, CY, S.REAL, bl_common.ref.STEP).set_index('cls').loc['ALL']; assert abs(leg.F1 - 0.6878) < 5e-4, f'replay changed: legacy F1 {leg.F1}'
    rec = dict(Q.spec_record(), order_split=CONV, mode='F', t_equals_f_for_d1=True, evidence_label='historical reproduction', simulator='d1_strategy/d1_algo (D1Engine replay of one-minute bars, config_for(und, d1))', engine_orders=int(len(sim)), real_orders=int(len(real)), rejected_orders=rejected, legacy_f1_on_this_replay=float(leg.F1),
               data_cache=hashlib.sha256(open(f'{OUT}/bl_d1eng_orders.pkl.gz', 'rb').read()).hexdigest(), run_at=datetime.datetime.utcnow().isoformat() + 'Z', diagnostic_only=True)
    V_ = Q.variants(real, sim, attrs, 'F', 'historical reproduction', bootstrap=2000); full = V_['all']
    for name, R in V_.items():
        d = f'{OD}/{name}'; os.makedirs(d, exist_ok=True)
        for k, v in R.items():
            if isinstance(v, pd.DataFrame) and not k.startswith('_'): v.to_csv(f'{d}/{k}.csv', index=False)
        for k, v in R['unmatched'].items():
            if isinstance(v, pd.DataFrame): v.to_csv(f'{d}/unmatched_{k}.csv', index=False)
        R['_pairs'].to_csv(f'{d}/pairs.csv', index=False)
        json.dump(jsonable({k: v for k, v in R.items() if k not in ('per_cycle', 'state_after_matched', 'checkpoints', 'unmatched')}), open(f'{d}/report.json', 'w'), indent=1)
    sim.to_csv(f'{OD}/sim_orders.csv', index=False); real.to_csv(f'{OD}/real_orders.csv', index=False); attrs.to_csv(f'{OD}/cycle_attributes.csv', index=False); rec['seconds'] = round(time.time() - t0); json.dump(rec, open(f'{OD}/run_record.json', 'w'), indent=1)
    print(json.dumps(rec, indent=1)); print(full['tiers'].round(4).to_string(index=False)); print(full['strictness'].round(4).to_string(index=False))
