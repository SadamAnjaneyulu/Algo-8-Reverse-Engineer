"""Lot-construction step 5 (plan D1_LOTS_PLAN.md): quantity fixes in the free-running simulator, chosen on training cycles by the overall D-1 lot F1:
solo lots per ladder fire = clip(round(a + b x depth60), 1, 8) (off or a in {1.0, 1.2, 1.4} x b in {1, 2, 3, 4, 6}); late R3 rule (off or 1 / 2 / 3 lots per fire); one-lot opposite-right counter-sell on a stop (off / on).
Scored (1) out-of-fold on cycle halves and (2) forward on unseen cycles (splits A and B of bl_fwd: timetable and lump time from training cycles only). Baseline = all off.
Outputs bl_lots_fit.csv, bl_lots_classes.csv, bl_summary_lf1.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
fw = open('bl_fwd.py').read(); exec(fw[fw.index("CYd = CY.reset_index()"):fw.index("rows = []; cls_rows = []")])
G = [(None, None, None, None)] + [(sa, sb, lt, co) for sa, sb in [(None, None)] + [(a, b) for a in (1.0, 1.2, 1.4) for b in (1, 2, 3, 4, 6)] for lt in (None, 1, 2, 3) for co in (None, 'one')][1:]
def overall(orders, cids):
    rr = score(orders, cids, step_of); tp = sum(x['tp'] for x in rr.values()); sm = sum(x['sim'] for x in rr.values()); rl = sum(x['real'] for x in rr.values()); return f1(tp, sm, rl)
def fit(train, base_P):
    best = None
    for sa, sb, lt, co in G:
        P = dict(base_P, solo_a=sa if sa else 1.0, solo_b=sb, late_n=lt or 1, ev_counter=co); late = lt is not None
        v = overall(OO({i: S.sim_cycle(i, P, 'free', late) for i in train}), train)
        if best is None or v > best[0]: best = (v, sa, sb, lt, co)
    return best
def tbl(orders, cids, label):
    global ids
    keep = ids; ids = cids; T, ov = table(orders, label); ids = keep; return T, ov
R = {}; rows = []; crow = []
SETUPS = [('out-of-fold halves', [([i for i in ids if i % 2 == h_], [i for i in ids if i % 2 != h_], None) for h_ in (0, 1)])] + [(nm, [(tr, te, nm)]) for nm, (tr, te) in SPL.items()]
for setup, folds in SETUPS:
    res = {'baseline': {}, 'fixed': {}}; chosen = []
    for tr, te, nm in folds:
        if nm:
            vmap = {'V1': 'V1', 'V2': 'V2'} if nm.startswith('A') else {'V1': 'V1', 'V2': 'V1'}; S.W = timetable(tr, vmap)
        P = fit_train(tr) if nm else None
        if not nm:
            P = fit_params(tr); P.update(bb_price='high', bb_vel=None, bb_mkt=None, bb_lo=None, bb_cluster=None, theta=1.6); best_tp = max((0.25, 0.4, 0.5, 0.75, 1.0), key=lambda tp: f1(*[score(OO(run(tr, dict(P, tp=tp), 'free')), tr, step_of)['body_sell'][k] for k in ('tp', 'sim', 'real')])); P['tp'] = best_tp
        else:
            lt_, rg = lump_t_from(tr); P['lump_t'] = lt_
        b = fit(tr, P); chosen.append(dict(setup=setup, solo_a=b[1], solo_b=b[2], late_n=b[3], counter=b[4], F1_train=round(b[0], 4))); print(chosen[-1], flush=True)
        res['baseline'].update(OO({i: S.sim_cycle(i, P, 'free', False) for i in te}))
        Pf = dict(P, solo_a=b[1] if b[1] else 1.0, solo_b=b[2], late_n=b[3] or 1, ev_counter=b[4]); res['fixed'].update(OO({i: S.sim_cycle(i, Pf, 'free', b[3] is not None) for i in te}))
        S.W = W_full
    cids = sorted(res['fixed'])
    for var in ('baseline', 'fixed'):
        T, ov = tbl(res[var], cids, f'{setup} | {var}'); crow.append(T.assign(setup=setup, model=var)); rows.append(dict(setup=setup, model=var, cycles=len(cids), F1=ov['F1'], precision=ov['precision'], recall=ov['recall'], F1_within1=ov['F1_within1'], F1_strict=ov['F1_strict']))
        print(rows[-1], flush=True)
    R[setup] = chosen
pd.DataFrame(rows).round(4).to_csv(f'{OUT}/bl_lots_fit.csv', index=False); pd.concat(crow).round(4).to_csv(f'{OUT}/bl_lots_classes.csv', index=False); rec('lf1', dict(chosen=R, rows=pd.DataFrame(rows).round(4).to_dict('records')))
