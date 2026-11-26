"""Buy-back decode step 6: choose the stop design in the free-running simulator (out-of-fold, objective = buy-back lot F1, timing +-1 min), then re-score the whole D-1 reconstruction with it.
Grid: price feed {previous close, current high} x theta {1.45..1.80} x velocity trigger {none, (5, 1.3/1.4/1.5), (3, 1.3/1.4)} x cluster {none, 1.3, 1.4}. Everything else as in bl_fr_score (reactive size fitted first, as before).
Outputs bl_bb_grid.csv, bl_fr2_classes.csv, bl_fr2_overall.csv, bl_fr2_orders.pkl.gz, bl_summary_bb6.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
R = {}; GRID = list(itertools.product(('close', 'high'), (1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8), (None, (5, 1.3), (5, 1.4), (5, 1.5), (3, 1.3), (3, 1.4)), (None, 1.3, 1.4)))
rows = []; allo = {}; FULL2 = {}; chosen = []
for h_ in (0, 1):
    tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P['theta'] = 1.5; best = None
    for tp in (0.25, 0.4, 0.5, 0.75, 1.0, 1.5):
        P['tp'] = tp; rr = score(OO(run(tr, P, 'free')), tr, step_of)['body_sell']; v = f1(rr['tp'], rr['sim'], rr['real'])
        if best is None or v > best[0]: best = (v, tp)
    P['tp'] = best[1]; best = None
    for pf, th, vel, cl in GRID:
        P.update(bb_price=pf, theta=th, bb_vel=vel, bb_cluster=cl); rr = score(OO(run(tr, P, 'free')), tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
        rows.append(dict(fold=h_, price=pf, theta=th, vel=str(vel), cluster=cl, F1_train=v, precision_train=rr['tp'] / max(rr['sim'], 1), recall_train=rr['tp'] / max(rr['real'], 1)))
        if best is None or v > best[0]: best = (v, (pf, th, vel, cl))
    P.update(bb_price=best[1][0], theta=best[1][1], bb_vel=best[1][2], bb_cluster=best[1][3]); chosen.append(dict(fold=h_, tp=P['tp'], price=best[1][0], theta=best[1][1], vel=str(best[1][2]), cluster=best[1][3], F1_train=best[0])); print(chosen[-1])
    full = run(te, P, 'free'); FULL2.update(full); allo.update(OO(full))
G = pd.DataFrame(rows); G.round(4).to_csv(f'{OUT}/bl_bb_grid.csv', index=False)
T, ov = table(allo, 'FR with decoded buy-back (stop design out-of-fold)'); T.round(4).to_csv(f'{OUT}/bl_fr2_classes.csv', index=False); pd.DataFrame([ov]).round(4).to_csv(f'{OUT}/bl_fr2_overall.csv', index=False); pd.to_pickle({'FR2': allo}, f'{OUT}/bl_fr2_orders.pkl.gz'); pd.to_pickle(FULL2, f'{OUT}/bl_fr2_full.pkl.gz')
print(T.round(3).to_string(index=False)); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in ov.items()})
# best of each design family on the training folds (diagnostic)
fam = G.assign(family=G.price + ' | vel ' + G.vel.astype(str) + ' | cluster ' + G.cluster.astype(str)).groupby(['fold', 'price', 'vel', 'cluster']).F1_train.max().reset_index().sort_values('F1_train', ascending=False); print(fam.head(10).round(3).to_string(index=False))
R['chosen'] = chosen; R['overall'] = ov; R['classes'] = T.round(4).to_dict('records'); rec('bb6', R)
