"""What drives the counter-sell AUC (post-hoc follow-up to reports/D0_CAUC_PLAN.md; labelled post-hoc): family ablation, single families, permutation importance, and a family for the stop pressure of the OTHER right.
Outputs bl_d0c_fam.csv, bl_d0c_imp.csv, bl_summary_d0c2.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
exec(open('bl_d0c_auc.py').read().split("rows = []; PP = {}")[0])      # same panel, groups, loco(), score()
LP = pd.read_pickle(f'{OUT}/bl_d0p_lotpanel.pkl.gz')
OS = ['max_ratio_hi_prev', 'max_ratio_close_prev', 'n_cross_prev_1.4', 'ref_side_prev', 'ref_strike_prev', 'side_loss_rs', 'side_loss_share', 'adv_fresh60_prev', 'prem_high60_prev', 'prem_chg_1_cp', 'prem_chg_5_cp', 'n_open']
Lo = LP[['cid', 'j', 'cp'] + OS].copy(); Lo['cp'] = np.where(Lo.cp == 'CE', 'PE', 'CE'); Lo = Lo.rename(columns={c: 'oth_' + c for c in OS})          # the OTHER right's state, joined to the cell of R'
PN = PN.merge(Lo, on=['cid', 'j', 'cp'], how='left'); G['other_stop'] = ['oth_' + c for c in OS]
V1 = ['base', 'spot', 'prem', 'book', 'bb']; rows = []
def run(nm, gs, y):
    cols = sum([G[g] for g in gs], []); p = loco(PN, cols, y); sc = score(PN, p, y); rows.append(dict(outcome='counter-sell cell' if y == 'y_counter' else 'any solo-sale cell', model=nm, features=len(cols), **sc)); print(rows[-1]['outcome'], nm, round(sc['auc'], 3), round(sc['within_cycle_auc'], 3)); return cols
for y in ('y_counter', 'y'):
    run('V1 causal (reference)', V1, y); run('V1 + stop pressure of the other right', V1 + ['other_stop'], y)
    for g in V1: run(f'V1 minus {g}', [x for x in V1 if x != g], y)
    for g in V1: run(f'only {g} (+ base)', ['base', g] if g != 'base' else ['base'], y)
    run('only other-right stop pressure (+ base)', ['base', 'other_stop'], y)
F = pd.DataFrame(rows); F.round(4).to_csv(f'{OUT}/bl_d0c_fam.csv', index=False)
# permutation importance, counter cells, V1 + other_stop
cols = sum([G[g] for g in V1 + ['other_stop']], []); imp = {c_: [] for c_ in cols}
for c_cid in PN.cid.unique():
    te = (PN.cid == c_cid).values; yt = PN[te].y_counter.values
    if yt.min() == yt.max(): continue
    m = mk().fit(PN[~te][cols].values, PN[~te].y_counter.values); Xt = PN[te][cols].values.copy(); b0 = roc_auc_score(yt, m.predict_proba(Xt)[:, 1])
    for k, f_ in enumerate(cols): Xs = Xt.copy(); Xs[:, k] = rng.permutation(Xs[:, k]); imp[f_].append(b0 - roc_auc_score(yt, m.predict_proba(Xs)[:, 1]))
IM = pd.DataFrame([dict(feature=f_, drop_in_auc=np.mean(v), family=[g for g in G if f_ in G[g]][0]) for f_, v in imp.items()]).sort_values('drop_in_auc', ascending=False); IM.round(5).to_csv(f'{OUT}/bl_d0c_imp.csv', index=False); print(IM.head(14).round(4).to_string(index=False))
rec('d0c2', dict(fam=F.round(4).to_dict('records'), top=IM.head(14).round(5).to_dict('records')))
