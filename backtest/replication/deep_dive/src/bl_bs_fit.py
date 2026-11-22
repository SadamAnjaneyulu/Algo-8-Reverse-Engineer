"""Buy-back second pass, step 4: the combined stop (loss AND premium high/entry >= theta AND spot close at a fresh N-minute extreme against the right, optional override ratio >= theta_hi) in the simulator.
Grid: N {15, 30, 45, 60, 90} x theta {1.4, 1.45, 1.5, 1.55, 1.6} x theta_hi {none, 1.7, 1.8, 1.9}; price feed = current minute high. Chosen per fold by buy-back lot F1 on the other half; scored (a) on the real sells (tf_bb) and (b) free-running; whole D-1 re-scored.
Outputs bl_bs_fit.csv, bl_fr4_classes.csv, bl_fr4_overall.csv, bl_fr4_full.pkl.gz, bl_summary_bs3.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
GRID = list(itertools.product((15, 30, 45, 60, 90), (1.4, 1.45, 1.5, 1.55, 1.6), (99, 1.7, 1.8, 1.9))); R = {}; out = []
for mode in ('tf_bb', 'free'):
    full = {}; chosen = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P.update(tp=0.4, bb_price='high', bb_vel=None, bb_cluster=None); best = None
        for N, th, hi in GRID:
            P.update(bb_mkt=N, theta=th, bb_hi=hi); rr = score(OO(run(tr, P, mode)), tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
            if best is None or v > best[0]: best = (v, N, th, hi)
        P.update(bb_mkt=best[1], theta=best[2], bb_hi=best[3]); chosen.append(dict(mode=mode, fold=h_, N=best[1], theta=best[2], theta_hi=best[3], F1_train=round(best[0], 4))); print(chosen[-1]); full.update(run(te, P, mode))
    T, ov = table({i: t[0] for i, t in full.items()}, f'combined stop ({mode})'); out.append(T.assign(mode=mode)); R[mode] = dict(chosen=chosen, overall=ov)
    if mode == 'free': pd.to_pickle(full, f'{OUT}/bl_fr4_full.pkl.gz'); T.round(4).to_csv(f'{OUT}/bl_fr4_classes.csv', index=False); pd.DataFrame([ov]).round(4).to_csv(f'{OUT}/bl_fr4_overall.csv', index=False)
    print(T[['cls', 'real_lots', 'sim_lots', 'precision', 'recall', 'F1', 'F1_within1', 'F1_strict']].round(3).to_string(index=False)); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in ov.items()})
pd.concat(out).round(4).to_csv(f'{OUT}/bl_bs_fit.csv', index=False); rec('bs3', R)
