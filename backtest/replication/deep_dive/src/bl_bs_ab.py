"""Buy-back second pass, step 6: rule A OR B on the real sells (tf_bb) and free-running.
A = own-premium intrabar stop (minute high / entry >= theta, theta out-of-fold from {1.55, 1.6, 1.65}).
B = lot in loss (previous close > entry) AND high / entry >= theta_lo AND market against: spot close at a fresh N-minute extreme (N in {15, 30, 60}) or premium speed high[j] / close[j-4] >= v (v in {1.15, 1.25}); quantity one lot (highest ratio) or all lots >= theta_lo.
Grid chosen on the other half by buy-back lot F1. Outputs bl_bs_ab.csv, bl_fr5_classes.csv, bl_fr5_overall.csv, bl_fr5_full.pkl.gz, bl_summary_bs5.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
G = [(th, None, None, None, None)] if False else []
for th in (1.55, 1.6, 1.65):
    G.append((th, None, None, None, None))
    for lo, mN, vv, q in itertools.product((1.0, 1.1, 1.2, 1.3, 1.4), (None, 15, 30, 60), (None, 1.15, 1.25), ('one', 'all')):
        if mN is None and vv is None: continue
        G.append((th, lo, mN, vv, q))
R = {}; out = []
for mode in ('tf_bb', 'free'):
    full = {}; chosen = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P.update(tp=0.4, bb_price='high', bb_vel=None, bb_cluster=None, bb_mkt=None); best = None
        for th, lo, mN, vv, q in G:
            P.update(theta=th, bb_lo=lo, bb_lo_mkt=mN, bb_lo_vel=vv, bb_lo_qty=q); rr = score(OO(run(tr, P, mode)), tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
            if best is None or v > best[0]: best = (v, th, lo, mN, vv, q)
        P.update(theta=best[1], bb_lo=best[2], bb_lo_mkt=best[3], bb_lo_vel=best[4], bb_lo_qty=best[5]); chosen.append(dict(mode=mode, fold=h_, theta=best[1], theta_lo=best[2], N=best[3], v=best[4], qty=best[5], F1_train=round(best[0], 4))); print(chosen[-1]); full.update(run(te, P, mode))
    T, ov = table({i: t[0] for i, t in full.items()}, f'A OR B ({mode})'); out.append(T.assign(mode=mode)); R[mode] = dict(chosen=chosen, overall=ov)
    if mode == 'free': pd.to_pickle(full, f'{OUT}/bl_fr5_full.pkl.gz'); T.round(4).to_csv(f'{OUT}/bl_fr5_classes.csv', index=False); pd.DataFrame([ov]).round(4).to_csv(f'{OUT}/bl_fr5_overall.csv', index=False)
    print(T[T.cls.isin(['body_buyback', 'wing_sell', 'wing_buy', 'lump'])][['cls', 'real_lots', 'sim_lots', 'precision', 'recall', 'F1', 'F1_within1']].round(3).to_string(index=False)); print('overall F1', round(ov['F1'], 4))
pd.concat(out).round(4).to_csv(f'{OUT}/bl_bs_ab.csv', index=False); rec('bs5', R)
