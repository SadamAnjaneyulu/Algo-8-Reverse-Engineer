"""Buy-back rebalancing events in the simulator (plan reports/BUYBACK_EVENTS_PLAN.md). Out-of-fold (cycle halves) choice of the event parts:
theta {1.6, 1.65} x cluster th2 {off, 1.2, 1.4} x partner {off, on} x counter-sell {off, one, match} (free only) x reactive continuation d {off, 1, 1.5} x solo reversal d2 {off, 1.5, 2}; price feed = minute high.
(a) real sells (tf_bb): objective = buy-back lot F1; (b) free-running: objective = overall D-1 lot F1. Reference = the plain stop (all parts off, theta out-of-fold).
Outputs bl_ev_fit.csv, bl_ev_classes.csv, bl_ev_overall.csv, bl_ev_full.pkl.gz, bl_summary_ev1.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
R = {}; out = []; ovs = []
def grid(mode): return list(itertools.product((1.6, 1.65), (None, 1.2, 1.4), (False, True), ((None, 'one', 'match') if mode == 'free' else (None,)), (None, 1.0, 1.5), (None, 1.5, 2.0)))
for mode, obj in (('tf_bb', 'buyback'), ('free', 'overall')):
    for variant in ('plain stop (reference)', 'rebalancing events'):
        full = {}; chosen = []
        for h_ in (0, 1):
            tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); P.update(tp=0.4, bb_price='high', bb_vel=None, bb_mkt=None, bb_lo=None); best = None
            G = grid(mode) if variant == 'rebalancing events' else [(th, None, False, None, None, None) for th in (1.5, 1.55, 1.6, 1.65, 1.7)]
            for th, th2, pa, co, dR, dS in G:
                P.update(theta=th, bb_cluster=th2, ev_partner=pa, ev_counter=co, ev_react=dR, ev_solo=dS); orders = OO(run(tr, P, mode))
                if obj == 'buyback': rr = score(orders, tr, step_of)['body_buyback']; v = f1(rr['tp'], rr['sim'], rr['real'])
                else: v = table(orders, 'x')[1]['F1'] if False else None
                if obj == 'overall':
                    rows_ = score(orders, tr, step_of); tp = sum(x['tp'] for x in rows_.values()); sm = sum(x['sim'] for x in rows_.values()); rl = sum(x['real'] for x in rows_.values()); v = f1(tp, sm, rl)
                if best is None or v > best[0]: best = (v, th, th2, pa, co, dR, dS)
            P.update(theta=best[1], bb_cluster=best[2], ev_partner=best[3], ev_counter=best[4], ev_react=best[5], ev_solo=best[6]); chosen.append(dict(mode=mode, variant=variant, fold=h_, theta=best[1], cluster=best[2], partner=best[3], counter=best[4], react_d=best[5], solo_d=best[6], obj_train=round(best[0], 4))); print(chosen[-1], flush=True)
            full.update(run(te, P, mode))
        T, ov = table({i: t[0] for i, t in full.items()}, f'{variant} ({mode})'); out.append(T.assign(mode=mode)); ovs.append(dict(ov, mode=mode)); R[f'{mode}|{variant}'] = dict(chosen=chosen, overall=ov)
        if mode == 'free' and variant == 'rebalancing events': pd.to_pickle(full, f'{OUT}/bl_ev_full.pkl.gz')
        b = T.set_index('cls').loc['body_buyback']; print(mode, variant, 'buy-back F1', round(b.F1, 4), 'P', round(b.precision, 3), 'R', round(b.recall, 3), '| overall F1', round(ov['F1'], 4), flush=True)
pd.concat(out).round(4).to_csv(f'{OUT}/bl_ev_classes.csv', index=False); pd.DataFrame(ovs).round(4).to_csv(f'{OUT}/bl_ev_overall.csv', index=False); pd.DataFrame([c for v in R.values() for c in v['chosen']]).to_csv(f'{OUT}/bl_ev_fit.csv', index=False); rec('ev1', R)
