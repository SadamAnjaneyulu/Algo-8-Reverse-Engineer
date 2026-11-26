"""Buy-back second pass, step 5 (post-hoc test of the 'sustained price' explanation): the plain own-premium stop on the REAL sells (tf_bb) with different price measures: previous close (causal), current open, current close (same minute), typical price (H+L+C)/3, current high (intrabar). Theta out-of-fold. If the trigger is a sustained live price, close/typical should beat the high.
Output bl_bs_price.csv, bl_summary_bs4.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
rows = []
for pf in ('close', 'open_now', 'close_now', 'typical', 'high'):
    full = {}; ch = []
    for h_ in (0, 1):
        tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P.update(tp=0.4, bb_price=pf, bb_vel=None, bb_cluster=None, bb_mkt=None); best = None
        for th in np.round(np.arange(1.35, 1.86, 0.05), 2):
            P['theta'] = th; rr = score(OO(run(tr, P, 'tf_bb')), tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
            if best is None or v > best[0]: best = (v, th)
        P['theta'] = best[1]; ch.append(best[1]); full.update(run(te, P, 'tf_bb'))
    T, ov = table({i: t[0] for i, t in full.items()}, pf); b = T.set_index('cls').loc['body_buyback']
    rows.append(dict(price=pf, theta_folds=str(ch), precision=b.precision, recall=b.recall, F1=b.F1, F1_strict=b.F1_strict)); print(rows[-1])
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_bs_price.csv', index=False); rec('bs4', dict(table=T.round(4).to_dict('records')))
