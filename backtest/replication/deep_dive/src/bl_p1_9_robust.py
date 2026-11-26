"""P1-9 final robustness (mirrors Gate 7 R1/R4/R5/R6 for the final configurations; writes outputs/phase1/9/final_robust.json; nothing from Gate 7 is overwritten)."""
import sys, os, json, warnings; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C, bl_oscore as Q, bl_fr_sim as S
from d0_algo import D0Engine
OUT = bl_common.OUT; OD = f'{OUT}/phase1/9'; res = {}; LO = pd.read_pickle(f'{OUT}/phase1/7/loco_params.pkl')
kf = lambda R, tol=60: float(R['strictness'][(R['strictness'].cumulative_tolerance_s == tol) & (R['strictness'].level == 'keys')].F1.iloc[0])
for cfg in ('hr', 'fwd'):
    items = []
    for i, P in LO.items():
        c = C.MODS[cfg](A.config_of(P, i), i); c.risk_mode = 'enforce'; e = D0Engine(c, A.market_of(i), A.opening_of(i)); e.run(); items.append((i, e))
    cids = [i for i, _ in items]; real = B.real_frame(cids); attrs = B.attrs_of(cids, real); sim = B.sim_frame(items); R = Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=True, bootstrap=1000)
    ex = {i: e.events_frame() for i, e in items}; leg = Q.legacy_d0_scores(ex, sorted(ex), A.CY, A.O(), None)
    res[f'LOCO_{cfg}'] = dict(keys_F1_60s=kf(R), ci=R['pooled_F1_ci95'], legacy_F1=float(leg['F1']), strict_F1=float(R['strictness'][(R['strictness'].cumulative_tolerance_s == 60) & (R['strictness'].level == 'lots_exact')].F1.iloc[0]), placebo=R['time_shift_placebo']['F1_keys_at_60s'], per_cycle=R['per_cycle_F1'], by_class={r['cls']: r['F1'] for r in R['by_class'].to_dict('records')}, cycles=len(cids), real=int(len(real)), sim=int(len(sim)))
    print('LOCO', cfg, round(res[f'LOCO_{cfg}']['keys_F1_60s'], 4), flush=True)
# R4 shifts on the final hr outputs
rl = pd.read_csv(f'{OD}/final_hr/OOF_events/real_orders.csv'); sm = pd.read_csv(f'{OD}/final_hr/OOF_events/sim_orders.csv'); at = pd.read_csv(f'{OD}/final_hr/OOF_events/attrs.csv'); sh = {}
for d in (-120, -60, 0, 60, 120): s2 = sm.copy(); s2['t'] = s2.t + d; sh[str(d)] = kf(Q.score(rl, s2, at, 'T', 'historical reproduction', shift_placebo=False, bootstrap=0))
res['R4_shift_hr'] = sh
# R5 causality: D0 (hr config) and D-1 with the stop switch ON
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
P0 = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl')['OOF half 0 test']; rng = np.random.default_rng(1); diffs = []
for i in P0['test'][:4]:
    for m_ in (100, 200, 300):
        c = C.MODS['hr'](A.config_of(P0, i), i); c.risk_mode = 'monitor'; e = D0Engine(c, A.market_of(i), A.opening_of(i)); e.run(); base = e.events_frame(); mk2 = A.market_of(i)
        for nm in ('spot_open', 'spot_high', 'spot_low', 'spot_close'): arr = getattr(mk2, nm).copy(); arr[m_ + 1:] = arr[m_ + 1:] * rng.uniform(0.5, 1.5, size=arr[m_ + 1:].shape); setattr(mk2, nm, arr)
        for key in list(mk2.opt): a = mk2.opt[key].copy(); a[:, m_ + 1:] = a[:, m_ + 1:] * rng.uniform(0.2, 3.0, size=a[:, m_ + 1:].shape); mk2.opt[key] = a
        e2 = D0Engine(c, mk2, A.opening_of(i)); e2.run(); o = e2.events_frame(); diffs.append(dict(engine='D0', cid=int(i), m=m_, identical=bool(base[base.j <= m_].reset_index(drop=True).equals(o[o.j <= m_].reset_index(drop=True))), events=int((base.j <= m_).sum())))
cyc_stop = [S.CY.index[(S.CY.und == 'NIFTY') & (S.CY.expiry == '2026-09-01')][0], 8 if False else S.CY.index[(S.CY.und == 'SENSEX') & (S.CY.expiry == '2026-10-08')][0]]
for i in cyc_stop:
    r = S.CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']
    def run_d1(m_):
        oo, hh, ll, cc = (x.values.copy() for x in (o.open, o.high, o.low, o.close)); bars = {k: v.copy() for k, v in op.items() if isinstance(k, tuple)}
        if m_ is not None:
            for arr in (oo, hh, ll, cc): arr[m_ + 1:] = arr[m_ + 1:] * rng.uniform(0.5, 1.5, size=arr[m_ + 1:].shape)
            for k in bars: bars[k][:, m_ + 1:] = bars[k][:, m_ + 1:] * rng.uniform(0.2, 3.0, size=bars[k][:, m_ + 1:].shape)
        feed = ReplayFeed(oo, hh, ll, cc, d['K'], bars); cfg = config_for(r.und, r.d1, order_split='one_lot_v2', cycle_stop_rupees=1.25e5); eng = D1Engine(cfg, feed, PaperBroker(feed)); run_replay(eng, feed); return eng.orders_frame()
    base = run_d1(None)
    for m_ in (100, 200, 300):
        oth = run_d1(m_); cut = 33300 + 60 * (m_ + 1); k = ['ts', 'right', 'strike', 'lots', 'side', 'role']; diffs.append(dict(engine='D1+stop', cid=int(i), m=m_, identical=bool(base[base.ts < cut][k].reset_index(drop=True).equals(oth[oth.ts < cut][k].reset_index(drop=True))), events=int((base.ts < cut).sum())))
res['R5'] = dict(tests=diffs, passed=all(x['identical'] for x in diffs), n=len(diffs))
PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); res['R6_disjoint'] = {k: bool(set(P['train']).isdisjoint(P['test'])) for k, P in PR.items()}; res['R6_disjoint']['LOCO'] = all(set(P['train']).isdisjoint(P['test']) for P in LO.values())
json.dump(res, open(f'{OD}/final_robust.json', 'w'), indent=1, default=float); print('R5', res['R5']['passed'], res['R5']['n'], 'R4', sh)
