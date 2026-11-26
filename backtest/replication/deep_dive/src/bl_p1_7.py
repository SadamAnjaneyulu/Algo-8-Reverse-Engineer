"""Gate 7 robustness and independence review (plan reports/PHASE1_GATE7_PLAN.md, fixed before scoring). Writes outputs/phase1/7/{summary.json, tests.json}."""
import sys, os, json, copy, time, warnings; os.environ.setdefault('ORDER_SPLIT', 'one_lot_v2')
for p in ('.', '../../../../d0_strategy', '../../../../d1_strategy', '../../../..'): sys.path.insert(0, p)
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_common, bl_p1_5a_port as A, bl_p1_5b as B, bl_p1_5c as C, bl_oscore as Q
from d0_algo import D0Engine
OUT = bl_common.OUT; OD = f'{OUT}/phase1/7'; os.makedirs(OD, exist_ok=True); res = {}
def keys_f1(R, tol=60): st = R['strictness']; return float(st[(st.cumulative_tolerance_s == tol) & (st.level == 'keys')].F1.iloc[0])
# ---------------- R1 true LOCO
LO = pd.read_pickle(f'{OD}/loco_params.pkl'); items = []; 
for i, P in LO.items():
    c = C.mod_clk(363)(A.config_of(P, i), i); c.risk_mode = 'enforce'; e = D0Engine(c, A.market_of(i), A.opening_of(i)); e.run(); items.append((i, e))
cids = [i for i, _ in items]; real = B.real_frame(cids); attrs = B.attrs_of(cids, real); sim = B.sim_frame(items); R = Q.score(real, sim, attrs, 'T', 'historical reproduction', shift_placebo=True, bootstrap=1000)
ex = {i: e.events_frame() for i, e in items}; leg = Q.legacy_d0_scores(ex, sorted(ex), A.CY, A.O(), None)['F1']; oof = json.load(open(f'{OUT}/phase1/5d/summary.json'))['OOF_events']
res['R1'] = dict(loco_keys_F1_60s=keys_f1(R), loco_legacy_F1=float(leg), ci=R['pooled_F1_ci95'], placebo=R['time_shift_placebo']['F1_keys_at_60s'], half_split_OOF=oof['keys_F1_60s'], half_split_legacy=oof['legacy_lot_level']['F1'], cycles=len(cids), per_cycle=R['per_cycle_F1'], passed=keys_f1(R) >= oof['keys_F1_60s'] - 0.03)
real.to_csv(f'{OD}/loco_real.csv', index=False); sim.to_csv(f'{OD}/loco_sim.csv', index=False); R['per_cycle'].to_csv(f'{OD}/loco_per_cycle.csv', index=False)
# ---------------- R2 parameter stability
import collections
cnt = lambda f: collections.Counter(f(P) for P in LO.values()); n = len(LO)
par = dict(theta=cnt(lambda P: P['k3']['theta']), take_profit=cnt(lambda P: P['k3'].get('tp')), ladder=cnt(lambda P: tuple(P['m1'])), counter_ratio=cnt(lambda P: P['r']), opening_wings=cnt(lambda P: P['ow']))
modal = {k: max(v.values()) / n for k, v in par.items()}; ow = np.array([P['ow'] for P in LO.values()]); modal['opening_wings'] = float((np.abs(ow - np.median(ow)) <= 2).mean())
res['R2'] = dict(counts={k: {str(a): b for a, b in v.items()} for k, v in par.items()}, modal_share=modal, half_splits={k: dict(theta=P['k3']['theta'], tp=P['k3'].get('tp'), ladder=P['m1'], r=P['r'], ow=P['ow']) for k, P in pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl').items()}, passed=all(v >= 0.75 for v in modal.values()))
# ---------------- R3 regimes (D0-C mode T OOF per cycle, from 5d; and D-1 B1 per cycle)
pc = pd.read_csv(f'{OUT}/phase1/5d/OOF_events/per_cycle.csv'); at = pd.read_csv(f'{OUT}/phase1/5d/OOF_events/attrs.csv'); z = pc.merge(at, on='cyc'); macro = float(z.F1.mean()); sub = []
for col in ('era', 'und', 'version', 'stop'):
    for v, g in z.groupby(col): sub.append(dict(split=col, value=str(v), cycles=int(len(g)), macro_F1=float(g.F1.mean()), median_F1=float(g.F1.median()), ratio_to_all=float(g.F1.mean() / macro)))
d1pc = pd.read_csv(f'{OUT}/scoring/d1_F_v2_onelot/all/per_cycle.csv'); fcol = [c for c in d1pc.columns if c == 'F1'][0]; a1 = pd.read_csv(f'{OUT}/scoring/d1_F_v2_onelot/all/per_cycle.csv'); sub1 = []
try:
    at1 = pd.read_csv(f'{OUT}/scoring/d1_F_v2_onelot/all/attrs.csv') if os.path.exists(f'{OUT}/scoring/d1_F_v2_onelot/all/attrs.csv') else None
except Exception: at1 = None
import bl_score_d1_F as F1M, bl_fr_sim as S
at1 = F1M.build_attrs(S.CY); z1 = d1pc.merge(at1, on='cyc'); macro1 = float(z1.F1.mean())
for col in ('era', 'und', 'version', 'stop'):
    for v, g in z1.groupby(col): sub1.append(dict(split=col, value=str(v), cycles=int(len(g)), macro_F1=float(g.F1.mean()), ratio_to_all=float(g.F1.mean() / macro1)))
bad = [s for s in sub if s['cycles'] >= 5 and s['ratio_to_all'] < 0.7]; bad1 = [s for s in sub1 if s['cycles'] >= 5 and s['ratio_to_all'] < 0.7]
res['R3'] = dict(d0_macro_F1=macro, d0_subgroups=sub, d1_macro_F1=macro1, d1_subgroups=sub1, flagged_d0=bad, flagged_d1=bad1, passed=not bad and not bad1)
# ---------------- R4 timing sensitivity (5d OOF events)
rl = pd.read_csv(f'{OUT}/phase1/5d/OOF_events/real_orders.csv'); sm = pd.read_csv(f'{OUT}/phase1/5d/OOF_events/sim_orders.csv'); at5 = pd.read_csv(f'{OUT}/phase1/5d/OOF_events/attrs.csv'); sh = {}
for d in (-120, -60, 0, 60, 120):
    s2 = sm.copy(); s2['t'] = s2.t + d; sh[d] = keys_f1(Q.score(rl, s2, at5, 'T', 'historical reproduction', shift_placebo=False, bootstrap=0))
res['R4'] = dict(f1_by_shift_s=sh, ratio_plus60=sh[60] / sh[0], passed=sh[60] >= 0.8 * sh[0] and sh[-120] < sh[0] and sh[120] < sh[0])
# ---------------- R5 causality perturbation: D0 engine and D-1 engine
P0 = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl')['OOF half 0 test']; diffs = []; rng = np.random.default_rng(0)
for i in P0['test'][:4]:
    for m_ in (100, 200, 300):
        c = A.config_of(P0, i); c.risk_mode = 'monitor'; mk = A.market_of(i); e = D0Engine(c, mk, A.opening_of(i)); e.run(); base = e.events_frame()
        mk2 = A.market_of(i); n = len(mk2.spot_close)
        for nm in ('spot_open', 'spot_high', 'spot_low', 'spot_close'): arr = getattr(mk2, nm).copy(); arr[m_ + 1:] = arr[m_ + 1:] * rng.uniform(0.5, 1.5, size=arr[m_ + 1:].shape); setattr(mk2, nm, arr)
        for key in list(mk2.opt): a = mk2.opt[key].copy(); a[:, m_ + 1:] = a[:, m_ + 1:] * rng.uniform(0.2, 3.0, size=a[:, m_ + 1:].shape); mk2.opt[key] = a
        e2 = D0Engine(c, mk2, A.opening_of(i)); e2.run(); other = e2.events_frame(); a_ = base[base.j <= m_].reset_index(drop=True); b_ = other[other.j <= m_].reset_index(drop=True); diffs.append(dict(engine='D0', cid=int(i), m=m_, identical=bool(a_.equals(b_)), events=int(len(a_))))
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
for i in (3, 10):
    r = S.CY.iloc[i]; d = S.prep(i); o = S.OH[(r.und, r.expiry)]; op = d['op']
    def run_d1(garbage_after):
        oo, hh, ll, cc = (x.values.copy() for x in (o.open, o.high, o.low, o.close)); bars = {k: v.copy() for k, v in op.items() if isinstance(k, tuple)}
        if garbage_after is not None:
            m_ = garbage_after
            for arr in (oo, hh, ll, cc): arr[m_ + 1:] = arr[m_ + 1:] * rng.uniform(0.5, 1.5, size=arr[m_ + 1:].shape)
            for k in bars: bars[k][:, m_ + 1:] = bars[k][:, m_ + 1:] * rng.uniform(0.2, 3.0, size=bars[k][:, m_ + 1:].shape)
        feed = ReplayFeed(oo, hh, ll, cc, d['K'], bars); cfg = config_for(r.und, r.d1, order_split='one_lot_v2'); eng = D1Engine(cfg, feed, PaperBroker(feed)); run_replay(eng, feed); return eng.orders_frame()
    base = run_d1(None)
    for m_ in (100, 200, 300):
        oth = run_d1(m_); cut = 33300 + 60 * (m_ + 1); a_ = base[base.ts < cut][['ts', 'right', 'strike', 'lots', 'side', 'role']].reset_index(drop=True); b_ = oth[oth.ts < cut][['ts', 'right', 'strike', 'lots', 'side', 'role']].reset_index(drop=True); diffs.append(dict(engine='D1', cid=int(i), m=m_, identical=bool(a_.equals(b_)), events=int(len(a_))))
res['R5'] = dict(tests=diffs, passed=all(x['identical'] for x in diffs) and len(diffs) == 18)
# ---------------- R6 hygiene
PR = pd.read_pickle(f'{OUT}/phase1/5a/ref_params.pkl'); hy = {k: bool(set(P['train']).isdisjoint(P['test'])) for k, P in PR.items()}; hy['LOCO'] = all(set(P['train']).isdisjoint(P['test']) for P in LO.values())
res['R6'] = dict(disjoint=hy, d1_note='D-1 B1 constants were fitted on all 32 cycles (in-sample by construction)', passed=all(hy.values()))
res['R7'] = dict(variants_tested_phase1={'2A solo trigger': 10, '2B strike rule': 10, '2C 15:00+ block': 2, '2D delayed breakout sizing': 4, '3A buy-back stop (K1-K6)': 6, '3B/3C wings and lump': 10, '5C D0 (X1, X3; +1 labelled sensitivity)': 3}, total=45, note='Counted, not deflated. Earlier D-1/D0 research chunks tested many more rules on the same cycles and are not countable.')
res['R8'] = dict(independent_validation='none exists', datasets=[dict(name='32 D-1 development cycles (Jun-Oct 2026)', independent=False, use='all D-1 rules and constants'), dict(name='30 D0 cycles (same expiries)', independent=False, use='D0 structure chosen on all; constants out-of-fold (halves, forward A/B, LOCO)'), dict(name='forward A / B splits', independent=False, use='pseudo-forward: same cycles, later or other-version subsets; structure visible'), dict(name='post-22-Oct exports, tick/second data, decision logs', independent=None, use='not available')])
json.dump(res, open(f'{OD}/tests.json', 'w'), indent=1, default=float)
for k in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6'): print(k, 'PASS' if res[k]['passed'] else 'FAIL')
print('R1', {a: (round(b, 4) if isinstance(b, float) else b) for a, b in res['R1'].items() if a not in ('per_cycle', 'ci')}); print('R2', res['R2']['modal_share']); print('R3 flagged', [(s['split'], s['value'], round(s['ratio_to_all'], 2)) for s in bad + bad1]); print('R4', {k: round(v, 4) for k, v in sh.items()}); print('R5', sum(x['identical'] for x in diffs), '/', len(diffs)); print('R6', hy)
