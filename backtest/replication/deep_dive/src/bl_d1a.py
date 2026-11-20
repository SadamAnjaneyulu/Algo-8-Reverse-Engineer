"""D-1 study, parts A (strike selection) and B (quantity). Outputs outputs/bl_d1_*.csv"""
import sys; sys.path.insert(0, '.')
from bl_common import *
from scipy import stats
O = load_orders(); S = O[(O.module == 'num') & (O.role == 'open_short') & (O.dayno == 0)].copy(); S['hit_prev'] = S.strike == S.atm_prev; S['hit_cur'] = S.strike == S.atm_cur; S['pm1'] = (S.strike - S.atm_prev).abs() <= S.step * 1.0001
S['slot'] = np.round((S.tod - (9 * 3600 + 16 * 60)) / 900).astype(int)
# A1 hit rates by class / und / right
t = S.groupby('cls').agg(orders=('tag', 'size'), lots=('lots', 'sum'), exact_prev=('hit_prev', 'mean'), exact_cur=('hit_cur', 'mean'), within1=('pm1', 'mean')).round(3); t['share_lots'] = (t.lots / t.lots.sum()).round(3); t.to_csv(f'{OUT}/bl_d1_A_class.csv'); print(t.to_string())
sm = S[S.cls == 'slot_minute']
print('slot_minute by und:', sm.groupby('und').hit_prev.mean().round(3).to_dict(), '| by right:', sm.groupby('cp').hit_prev.mean().round(3).to_dict())
# causal reference: orders where the previous-close ATM and current-close ATM differ
d = sm[sm.atm_prev != sm.atm_cur]; print('slot_minute with atm_prev != atm_cur: n', len(d), '| K==atm_prev %.3f  K==atm_cur %.3f  other %.3f' % ((d.strike == d.atm_prev).mean(), (d.strike == d.atm_cur).mean(), ((d.strike != d.atm_prev) & (d.strike != d.atm_cur)).mean()))
# boundary test: distance of spot_prev from its nearest strike (u) vs hit
sm = sm.assign(u=(sm.spot_prev - sm.atm_prev).abs() / sm.step); sm['ub'] = pd.cut(sm.u, [0, .1, .2, .3, .4, .5]); bt = sm.groupby('ub').agg(n=('hit_prev', 'size'), hit=('hit_prev', 'mean')).round(3); bt.to_csv(f'{OUT}/bl_d1_A_boundary.csv'); print(bt.to_string())
ms = sm[~sm.hit_prev].copy(); ms['toward_spot'] = np.sign(ms.strike - ms.atm_prev) == np.sign(ms.spot_prev - ms.atm_prev); one = ms[(ms.strike - ms.atm_prev).abs() <= ms.step * 1.0001]
print('misses by 1 step: n', len(one), ' on the side toward spot_prev: %.3f (binomial p=%.2g)' % (one.toward_spot.mean(), stats.binomtest(int(one.toward_spot.sum()), len(one), .5).pvalue))
# by slot
bs = sm.groupby('slot').agg(n=('hit_prev', 'size'), hit=('hit_prev', 'mean')).round(3); bs.to_csv(f'{OUT}/bl_d1_A_by_slot.csv'); print('hit by slot:', bs.hit.to_dict())
# first order of each slot-right vs subsequent
sm = sm.sort_values(['und', 'expiry', 'cp', 'slot', 'te']); sm['idx'] = sm.groupby(['und', 'expiry', 'cp', 'slot']).cumcount(); print('hit by order index in slot minute:', sm.groupby(sm.idx.clip(upper=4)).hit_prev.agg(['size', 'mean']).round(3).to_dict('index'))
# strike migration across slots: modal strike per slot-right vs ATM change
M = sm.groupby(['und', 'expiry', 'cp', 'slot']).agg(K=('strike', lambda x: x.mode().iloc[0]), atm=('atm_prev', 'first'), step=('step', 'first')).reset_index().sort_values(['und', 'expiry', 'cp', 'slot'])
M['dK'] = M.groupby(['und', 'expiry', 'cp']).K.diff() / M.step; M['dATM'] = M.groupby(['und', 'expiry', 'cp']).atm.diff() / M.step; M['gap'] = M.groupby(['und', 'expiry', 'cp']).slot.diff(); m1 = M[(M.gap == 1)].dropna(subset=['dK', 'dATM'])
print('consecutive-slot pairs', len(m1), '| corr(dK,dATM) %.3f' % np.corrcoef(m1.dK, m1.dATM)[0, 1], '| dK==dATM: %.3f' % (m1.dK == m1.dATM).mean(), '| ATM unchanged and K unchanged: %.3f of %d' % (((m1.dK == 0)[m1.dATM == 0]).mean(), int((m1.dATM == 0).sum())), '| ATM changed and K moved same amount: %.3f of %d' % (((m1.dK == m1.dATM)[m1.dATM != 0]).mean(), int((m1.dATM != 0).sum())))
m1.to_csv(f'{OUT}/bl_d1_A_migration.csv', index=False)
# B: quantity
print('B orders: lots per slot-minute order', sm.lots.value_counts(normalize=True).head(4).round(3).to_dict())
L = sm.groupby(['und', 'expiry', 'cp', 'slot']).lots.sum().reset_index(); P = L.pivot_table(index=['und', 'expiry', 'slot'], columns='cp', values='lots', fill_value=0).reset_index(); P['tot'] = P.CE + P.PE
lad = P.groupby(['und', 'slot']).agg(mean_ce=('CE', 'mean'), mean_pe=('PE', 'mean'), modal_ce=('CE', lambda x: x.mode().iloc[0]), modal_pe=('PE', lambda x: x.mode().iloc[0]), n=('CE', 'size')).round(2); lad.to_csv(f'{OUT}/bl_d1_B_ladder.csv'); print(lad.unstack(0).iloc[:, :8].to_string())
P = P.merge(lad.reset_index()[['und', 'slot', 'modal_ce', 'modal_pe']], on=['und', 'slot']); print('slot-right lots equal the modal ladder: CE %.3f PE %.3f | CE==PE %.3f' % ((P.CE == P.modal_ce).mean(), (P.PE == P.modal_pe).mean(), (P.CE == P.PE).mean()))
P.to_csv(f'{OUT}/bl_d1_B_slot_lots.csv', index=False)
# accumulate vs migrate: share of slot-minute sells at a strike already short, by slot index
sm['existing'] = (sm.net_after - sm.sl) < 0; print('slot-minute sells at an already-short strike: %.3f ; by slot (first 6):' % sm.existing.mean(), sm.groupby('slot').existing.mean().round(2).head(8).to_dict())

sm0 = S[S.cls == 'slot_minute']; d_ = sm0[sm0.atm_prev != sm0.atm_cur]; sm1 = sm0.assign(u=(sm0.spot_prev - sm0.atm_prev).abs() / sm0.step)
rec('d1a', dict(n_sells=len(S), lots_sells=S.lots.sum(), n_slot=len(sm0), hit_und=sm0.groupby('und').hit_prev.mean(), hit_right=sm0.groupby('cp').hit_prev.mean(), causal_n=len(d_), causal_prev=(d_.strike == d_.atm_prev).mean(), causal_cur=(d_.strike == d_.atm_cur).mean(), causal_other=((d_.strike != d_.atm_prev) & (d_.strike != d_.atm_cur)).mean(),
  miss1_n=len(one), miss1_toward=one.toward_spot.mean(), miss1_p=stats.binomtest(int(one.toward_spot.sum()), len(one), .5).pvalue, mig_pairs=len(m1), mig_corr=np.corrcoef(m1.dK, m1.dATM)[0, 1], mig_dK_eq_dATM=(m1.dK == m1.dATM).mean(), mig_unch_n=int((m1.dATM == 0).sum()), mig_unch=((m1.dK == 0)[m1.dATM == 0]).mean(), mig_chg_n=int((m1.dATM != 0).sum()), mig_chg=((m1.dK == m1.dATM)[m1.dATM != 0]).mean(),
  lots_1=(sm0.lots == 1).mean(), ladder_eq_ce=(P.CE == P.modal_ce).mean(), ladder_eq_pe=(P.PE == P.modal_pe).mean(), ce_eq_pe=(P.CE == P.PE).mean(), existing_share=sm.existing.mean(), existing_by_slot=sm.groupby('slot').existing.mean(), idx_hit=sm.groupby(sm.idx.clip(upper=4)).hit_prev.mean()))
