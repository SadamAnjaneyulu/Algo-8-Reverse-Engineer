"""Buy-back decode step 7 (diagnostic): the stop rule run on the REAL body sells (mode tf_bb: real sells with their decision prices as entries, buy-backs simulated, hedge simulated). Separates the stop rule's own accuracy from the sell errors it inherits in free-running mode.
Same out-of-fold grid as bl_bb_fit. Outputs bl_bb_tf.csv, bl_summary_bb7.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
GRID = list(itertools.product(('close', 'high'), (1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8), (None, (5, 1.3), (5, 1.4), (5, 1.5), (3, 1.3), (3, 1.4)), (None, 1.3, 1.4)))
allo = {}; chosen = []; R = {}
for h_ in (0, 1):
    tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P['tp'] = 0.4; best = None
    for pf, th, vel, cl in GRID:
        P.update(bb_price=pf, theta=th, bb_vel=vel, bb_cluster=cl); rr = score(OO(run(tr, P, 'tf_bb')), tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
        if best is None or v > best[0]: best = (v, (pf, th, vel, cl))
    P.update(bb_price=best[1][0], theta=best[1][1], bb_vel=best[1][2], bb_cluster=best[1][3]); chosen.append(dict(fold=h_, design=str(best[1]), F1_train=round(best[0], 3))); print(chosen[-1]); allo.update(OO(run(te, P, 'tf_bb')))
    if h_ == 0:   # also the plain rule (close, 1.5) for reference
        P0 = dict(P, bb_price='close', theta=1.5, bb_vel=None, bb_cluster=None)
allo0 = {}
for h_ in (0, 1):
    te = [i for i in ids if i % 2 != h_]; P0 = fit_params([i for i in ids if i % 2 == h_]); P0.update(tp=0.4, bb_price='close', theta=1.5, bb_vel=None, bb_cluster=None); allo0.update(OO(run(te, P0, 'tf_bb')))
T, ov = table(allo, 'TF-buyback: decoded stop on real sells'); T0, ov0 = table(allo0, 'TF-buyback: plain stop close>=1.5x on real sells')
out = pd.concat([T, T0]); out = out[out.cls.isin(['body_buyback', 'wing_sell', 'wing_buy'])]; out.round(4).to_csv(f'{OUT}/bl_bb_tf.csv', index=False); print(out[['variant', 'cls', 'real_lots', 'sim_lots', 'precision', 'recall', 'F1', 'F1_within1', 'F1_strict']].round(3).to_string(index=False))
R['chosen'] = chosen; R['table'] = out.round(4).to_dict('records'); rec('bb7', R)
