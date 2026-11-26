"""Gate 5a research-layer adapter: builds the D0 engine's inputs (market arrays, opening state, configuration) from the repository's existing D0 caches EXACTLY as the reference simulator does, runs the standalone engine on every split and test cycle,
and compares with the saved reference output. Real D-1 orders enter only as the explicit opening state (teacher-forced start, mode T); real D0 orders are never read here."""
import sys, os, json, hashlib, warnings; sys.path.insert(0, '.'); sys.path.insert(0, '../../../../d0_strategy'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from bl_common import OUT, ref, load_orders
from d0_algo import D0Config, D0Engine, D0Market, D0Opening
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OPT = pd.read_pickle(f'{OUT}/bl_d0_opt.pkl.gz'); SPT = pd.read_pickle(f'{OUT}/bl_d0_spot.pkl.gz'); BK = pd.read_pickle(f'{OUT}/bl_d0b_book.pkl.gz'); _O = None
def O():
    global _O
    if _O is None: _O = load_orders()
    return _O
def market_of(i):
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; sp = SPT[(r.und, r.expiry)]
    return D0Market(K=op['K'], step=ref.STEP[r.und], unit=float(r.unit), spot_open=sp.open.values, spot_high=sp.high.values, spot_low=sp.low.values, spot_close=sp.close.values, opt={k: v for k, v in op.items() if isinstance(k, tuple)})
def opening_of(i):
    """carried state at the D0 open: body short lots from the real D-1 book cache, other-module positions and cash from the REAL D-1 orders (teacher-forced start, mode T; as the reference)"""
    r = CY.iloc[i]; u = float(r.unit); lots = [[L['cp'], L['strike'], L['entry']] for L in BK[i]['at_open']]
    z1 = O()[(O().und == r.und) & (O().expiry == r.expiry) & (O().dayno == 0)]; sg = np.where(z1.side.str.lower() == 'buy', 1, -1); cash = float((-sg * z1.px_avg * z1.lots * u).sum()); oth = {}
    for q, s_ in zip(z1.itertuples(), sg):
        if q.module == 'num' and q.role in ('open_short', 'cover_short'): continue
        k = (q.module, q.cp, int(q.strike)); oth[k] = oth.get(k, 0) + s_ * q.lots
    return D0Opening(lots=lots, longs={k: v for k, v in oth.items() if v > 0}, oshort={k: -v for k, v in oth.items() if v < 0}, cash=cash)
def config_of(P, i):
    r = CY.iloc[i]; W = P['W']; W = W[(W.und == r.und) & (W.version == r.version)]; X_, G_, mult = P['m1']; k3 = P['k3']
    return D0Config(waves=[(float(x.t), int(x.lots)) for x in W.itertuples()], buyback_theta=float(k3['theta']), buyback_tp=(float(k3['tp']) if k3.get('tp') else None), ladder_step=float(X_), ladder_gate_min=int(G_), ladder_mult=bool(mult), counter_ratio=float(P['r']), opening_wing_lots=int(P['ow']))
def run_cycle(P, i):
    e = D0Engine(config_of(P, i), market_of(i), opening_of(i)); e.run(); return e
def config_mode(P, i, mode):
    c = config_of(P, i); c.risk_mode = mode; return c
if __name__ == '__main__':
    import bl_oscore as Q
    REF = pd.read_pickle(f'{OUT}/bl_d0_fr_orders.pkl.gz'); PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); res = dict(modes={}, note='monitor = reference behaviour with risk breaches recorded; enforce = guard refuses sells beyond the observed real D0 envelope (278 net short lots per right, 90 sell decisions per minute)'); sims = {}
    for mode in ('monitor', 'enforce'):
        r_ = dict(splits={}, cycles=0, identical=0, reconciled=0, deterministic=0, stopped=0, cleared=0, rejected_orders=0, violations=[], max_sell_decisions_per_minute=0); sims[mode] = {}
        for nm, P in PR.items():
            same = rec = det = 0; sims[mode][nm] = {}
            for i in P['test']:
                op = opening_of(i); e = D0Engine(config_mode(P, i, mode), market_of(i), op); e.run(); a = e.events_frame(); b = REF[nm][i].reset_index(drop=True); sims[mode][nm][i] = a; same += int(a.equals(b)); rec += int(e.reconcile(op))
                e2 = D0Engine(config_mode(P, i, mode), market_of(i), opening_of(i)); e2.run(); det += int(e2.events_frame().equals(a)); r_['stopped'] += int(e.stopped); r_['cleared'] += int(e.cleared); r_['rejected_orders'] += len(e.rejected); r_['max_sell_decisions_per_minute'] = max(r_['max_sell_decisions_per_minute'], max(e._decisions.values(), default=0))
                for (j, cp, why, n) in (e.rejected + e.violations): r_['violations'].append(dict(split=nm, cid=int(i), cyc=f"{CY.iloc[i].und}|{CY.iloc[i].expiry}", minute=int(j), cp=cp, reason=why, lots=n))
                if not a.equals(b): r_.setdefault('differs_from_reference', []).append(dict(split=nm, cid=int(i), events=len(a), reference_events=len(b)))
            r_['splits'][nm] = dict(cycles=len(P['test']), identical_to_reference=same, position_reconciles=rec, deterministic_on_rerun=det); r_['cycles'] += len(P['test']); r_['identical'] += same; r_['reconciled'] += rec; r_['deterministic'] += det
        ref_sims = {**REF['OOF half 0 test'], **REF['OOF half 1 test']}; eng_sims = {**sims[mode]['OOF half 0 test'], **sims[mode]['OOF half 1 test']}; D0C = sorted(ref_sims)
        r_['legacy_D0_OOF'] = dict(reference=Q.legacy_d0_scores(ref_sims, D0C, CY, O(), None), engine=Q.legacy_d0_scores(eng_sims, D0C, CY, O(), None)); res['modes'][mode] = r_; print(mode, {k: v for k, v in r_.items() if k in ('cycles', 'identical', 'reconciled', 'deterministic', 'rejected_orders')}, 'legacy F1 engine', round(r_['legacy_D0_OOF']['engine']['F1'], 6), 'reference', round(r_['legacy_D0_OOF']['reference']['F1'], 6), flush=True)
    pd.to_pickle(sims, f'{OUT}/phase1/5a/engine_events_mode_T.pkl.gz'); res['engine_events_sha256'] = hashlib.sha256(open(f'{OUT}/phase1/5a/engine_events_mode_T.pkl.gz', 'rb').read()).hexdigest()
    json.dump(res, open(f'{OUT}/phase1/5a/port_check.json', 'w'), indent=1, default=float); print(json.dumps(res['modes']['enforce'].get('differs_from_reference'), default=float)); print(pd.DataFrame(res['modes']['enforce']['violations']).to_string(index=False))
