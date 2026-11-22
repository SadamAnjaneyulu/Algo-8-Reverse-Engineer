"""Accuracy push, second round: (a) bookkeeping fix: releases of the opening-wing contracts are booked as body-stream long closes (real num close_long: 93% are on opening-wing contracts, 81% within 10 s of a buy-back);
(b) joint coordinate-descent tuning of the whole simulator against the overall D-1 lot F1 on training cycles (two passes): reactive pair size, extras scale, ladder step and gate, solo depth sizing, late rule, stop level, lump size scale and time offset, counter-sell.
Setups: out-of-fold halves; forward A (same version); forward B (version change). Real num close_long becomes a scored class (body_long_close) for every variant, so all variants are comparable.
Outputs bl_push2.csv, bl_push2_classes.csv, bl_summary_push2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
REAL.loc[(REAL.module == 'num') & (REAL.role == 'close_long'), 'cls'] = 'body_long_close'; NMOD.append('body_long_close'); TOL['body_long_close'] = 1
RL = {}
for i, r in enumerate(CY.itertuples()):
    z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry)]
    for (cls, cp), g in z.groupby(['cls', 'cp']): g = lots_of(g); RL[(i, cls, cp)] = (g.j.values.astype(int), g.strike.values.astype(float))
fw = open('bl_fwd.py').read(); exec(fw[fw.index("CYd = CY.reset_index()"):fw.index("rows = []; cls_rows = []")])
def sim(P, cids): return {i: S.sim_cycle(i, P, 'free', bool(P.get('late_on'))) for i in cids}
def overall(orders, cids):
    rr = score(orders, cids, step_of); tp = sum(x['tp'] for x in rr.values()); sm = sum(x['sim'] for x in rr.values()); rl = sum(x['real'] for x in rr.values()); return f1(tp, sm, rl)
GRID = dict(tp=[0.25, 0.4, 0.5, 0.75, 1.0], ex_scale=[0.0, 0.5, 1.0, 1.5], lad_X=[0.1, 0.15, 0.2, 0.3, 0.4], lad_gate=[15, 30, 60, 90], solo_b=[None, 1, 2], late_on=[False, True], late_n=[1, 2], theta=[1.5, 1.55, 1.6, 1.65, 1.7],
            lump_scale=[0.8, 0.9, 1.0, 1.1, 1.2], lump_dt=[-3, -2, -1, 0, 1, 2], ev_counter=[None, 'one'])
def tune(P0, train):
    P = dict(P0); best = overall(OO(sim(P, train)), train); path = []
    for ps in range(2):
        for k, vals in GRID.items():
            for v in vals:
                if P.get(k) == v: continue
                Q = dict(P, **{k: v}); f = overall(OO(sim(Q, train)), train)
                if f > best + 1e-6: best, P = f, Q; path.append((ps, k, v, round(f, 4)))
    return P, best, path
def tbl(orders, cids, label):
    global ids
    keep = ids; ids = cids; T, ov = table(orders, label); ids = keep; return T, ov
rows = []; crow = []; R = {}
SETUPS = [('out-of-fold halves', [([i for i in ids if i % 2 == h_], [i for i in ids if i % 2 != h_], None) for h_ in (0, 1)])] + [(nm, [(tr, te, nm)]) for nm, (tr, te) in SPL.items()]
for setup, folds in SETUPS:
    res = {v: {} for v in ('baseline', '+ opening-wing close relabel', '+ relabel + joint tuning')}; info = []
    for tr, te, nm in folds:
        if nm:
            vmap = {'V1': 'V1', 'V2': 'V2'} if nm.startswith('A') else {'V1': 'V1', 'V2': 'V1'}; S.W = timetable(tr, vmap); P = fit_train(tr); P['lump_t'] = lump_t_from(tr)[0]
        else:
            P = fit_params(tr); P.update(bb_price='high', bb_vel=None, bb_mkt=None, bb_lo=None, bb_cluster=None, theta=1.6, tp=0.4)
        Pr = dict(P, ow_close=True); Pt, fbest, path = tune(Pr, tr)
        info.append(dict(setup=setup, train_F1_relabel=round(overall(OO(sim(Pr, tr)), tr), 4), train_F1_tuned=round(fbest, 4), changes=str(path))); print(info[-1], flush=True)
        for v, PP in (('baseline', P), ('+ opening-wing close relabel', Pr), ('+ relabel + joint tuning', Pt)): res[v].update(OO(sim(PP, te)))
        S.W = W_full
    cids = sorted(res['baseline'])
    for v in res:
        T, ov = tbl(res[v], cids, f'{setup} | {v}'); crow.append(T.assign(setup=setup, model=v)); rows.append(dict(setup=setup, model=v, cycles=len(cids), F1=ov['F1'], precision=ov['precision'], recall=ov['recall'], F1_within1=ov['F1_within1'], F1_strict=ov['F1_strict'])); print(rows[-1], flush=True)
    R[setup] = info
pd.DataFrame(rows).round(4).to_csv(f'{OUT}/bl_push2.csv', index=False); pd.concat(crow).round(4).to_csv(f'{OUT}/bl_push2_classes.csv', index=False); rec('push2', dict(info=R, rows=pd.DataFrame(rows).round(4).to_dict('records')))
