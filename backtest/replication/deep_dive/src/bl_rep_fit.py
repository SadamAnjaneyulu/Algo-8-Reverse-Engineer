"""Reconstruction improvement step: reactive repeat entries in the free-running simulator (new running-candle extreme beyond the channel after the first entry), rep_max in {0, 1, 2, 3} x rep_gap in {1, 2, 3, 5} chosen on the other cycle half by body-sell lot F1; buy-back design and the other parameters as in bl_bb_fit (out-of-fold). Re-scores the whole D-1.
Outputs bl_fr3_classes.csv, bl_fr3_overall.csv, bl_fr3_full.pkl.gz, bl_summary_rep1.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
ch = json.load(open(f'{OUT}/bl_summary_bb6.json'))['chosen']; FULL3 = {}; chosen = []; R = {}
for h_, c_ in zip((0, 1), ch):
    tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P.update(tp=c_['tp'], bb_price=c_['price'], theta=c_['theta'], bb_vel=eval(c_['vel']), bb_cluster=c_['cluster'] if c_['cluster'] == c_['cluster'] else None); best = None
    for rm, rg in itertools.product((0, 1, 2, 3), (1, 2, 3, 5)):
        if rm == 0 and rg != 2: continue
        P.update(rep_max=rm, rep_gap=rg); rr = score(OO(run(tr, P, 'free')), tr, step_of)['body_sell']; v = f1(rr['tp'], rr['sim'], rr['real'])
        if best is None or v > best[0]: best = (v, rm, rg)
    P.update(rep_max=best[1], rep_gap=best[2]); chosen.append(dict(fold=h_, rep_max=best[1], rep_gap=best[2], F1_train=round(best[0], 4))); print(chosen[-1]); FULL3.update(run(te, P, 'free'))
T, ov = table({i: t[0] for i, t in FULL3.items()}, 'FR + decoded buy-back + reactive repeats'); T.round(4).to_csv(f'{OUT}/bl_fr3_classes.csv', index=False); pd.DataFrame([ov]).round(4).to_csv(f'{OUT}/bl_fr3_overall.csv', index=False); pd.to_pickle(FULL3, f'{OUT}/bl_fr3_full.pkl.gz')
print(T[['cls', 'real_lots', 'sim_lots', 'precision', 'recall', 'F1', 'F1_within1', 'F1_strict']].round(3).to_string(index=False)); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in ov.items()}); R['chosen'] = chosen; R['overall'] = ov; rec('rep1', R)
