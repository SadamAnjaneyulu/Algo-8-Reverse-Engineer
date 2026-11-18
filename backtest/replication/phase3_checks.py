"""Behavioural statistics from the live ledger for the entry / basket structure (ladder, strike rule, CE/PE symmetry, wing selection)."""
from common import *
E = pd.read_csv(f'{RES}/live_decision_events.csv'); E['slot'] = (E.minute // 15) * 15
slotname = lambda m: MINLABEL[m]
MINLABEL = {i: f'{9 + (i + 15) // 60:02d}:{(i + 15) % 60:02d}' for i in range(375)}
body = E[(E.tp == 'num') & (E.side == 'Sell')]
# 1. D-1 ladder: lots per slot per leg per cycle, versus the modal table in FINDINGS (09:16 3, 09:31 2, 09:46 3, 10:01 1, 10:16 3, 10:31 1, 10:46 2, 11:01 2, 11:16 1, 11:31 1, 11:46 3, 12:01 1, 12:16 0, 12:31 2, 12:46 0, 13:01 0, 13:16 1)
MODAL = dict(zip(['09:16', '09:31', '09:46', '10:01', '10:16', '10:31', '10:46', '11:01', '11:16', '11:31', '11:46', '12:01', '12:16', '12:31', '12:46', '13:01', '13:16'], [3, 2, 3, 1, 3, 1, 2, 2, 1, 1, 3, 1, 0, 2, 0, 0, 1]))
b1 = body[body.day == 'D-1'].copy(); b1['slot_hm'] = [MINLABEL[(m // 15) * 15 + 1] if True else '' for m in b1.minute]
# slot start minute index: 09:16 = idx 1; slot k covers idx 1+15k .. 15+15k
b1['k'] = (b1.minute - 1) // 15; b1['slot_hm'] = [MINLABEL[1 + 15 * k] for k in b1.k]
pl = b1.groupby(['und', 'expiry', 'slot_hm', 'cp']).lots.sum().unstack('cp').fillna(0).reset_index()
rows = []
for s, mv in MODAL.items():
    x = pl[pl.slot_hm == s]; n_cyc = pl[['und', 'expiry']].drop_duplicates().shape[0]
    ce = x.CE.reindex(range(len(x))).fillna(0) if len(x) else pd.Series(dtype=float); 
    full = pl[['und', 'expiry']].drop_duplicates().merge(x, how='left', on=['und', 'expiry']).fillna(0)
    rows.append(dict(slot=s, modal_lots=mv, cycles=n_cyc, share_CE_eq_modal=(full.CE == mv).mean(), share_PE_eq_modal=(full.PE == mv).mean(), share_CE_eq_PE=(full.CE == full.PE).mean(), mean_CE=full.CE.mean(), mean_PE=full.PE.mean(), median_CE=full.CE.median(), median_PE=full.PE.median()))
L = pd.DataFrame(rows); L.to_csv(f'{RES}/ladder_d1_agreement.csv', index=False)
pd.set_option('display.width', 250); print(L.round(2).to_string(index=False))
# off-ladder D-1 sells (outside the 15-min first minutes)
b1['in_first3'] = ((b1.minute - 1) % 15) < 4; print('D-1 body sells within first 4 min of slot:', b1.in_first3.mean().round(3), ' lots share:', (b1.lots * b1.in_first3).sum() / b1.lots.sum())
# 2. Strike rule: body sells strike vs previous-minute spot, nearest strike
body = body.assign(near=lambda x: (x.strike - x.spot_prev).abs() <= np.where(x.und == 'NIFTY', 25, 50) + 1e-9, off=lambda x: x.off_steps.round())
print(body.groupby(['day']).agg(n=('near', 'size'), nearest=('near', 'mean'), within1=('off', lambda v: (v.abs() <= 1).mean())).round(3))
bs = body.groupby(['und', 'day']).agg(n=('near', 'size'), nearest=('near', 'mean'), within1=('off', lambda v: (v.abs() <= 1).mean())).round(3); print(bs); bs.to_csv(f'{RES}/strike_rule_agreement.csv')
# 3. By slot: 09:16 slot vs later for D-1
b1['nearest'] = (b1.strike - b1.spot_prev).abs() <= np.where(b1.und == 'NIFTY', 25, 50) + 1e-9; print(b1.groupby('slot_hm').nearest.mean().round(2).to_dict())
# 4. wings: price relationship with same-minute body sell on same side
w = E[(E.tp == 'h_') & (E.side == 'Buy') & (E.day == 'D-1')]; w['dist_pts'] = (w.strike - w.spot_prev).abs(); print('D-1 wing buys:', len(w), 'median dist pts NIFTY', w[w.und == 'NIFTY'].dist_pts.median(), 'SENSEX', w[w.und == 'SENSEX'].dist_pts.median(), 'median px', w.px.median())
bsell = b1.groupby(['und', 'expiry', 'minute', 'cp']).agg(bpx=('px', 'mean'), lots=('lots', 'sum')).reset_index()
ww = w.merge(bsell, on=['und', 'expiry', 'minute', 'cp'], how='inner'); ww['ratio'] = ww.px / ww.bpx; print('wing/body price ratio quantiles', ww.ratio.quantile([.1, .25, .5, .75, .9]).round(4).to_dict(), len(ww))
ww['wing_lots_per_body_lot'] = ww.lots_x / ww.lots_y; print('wing lots / body lots same minute (median):', ww.wing_lots_per_body_lot.median())
# 5. CE vs PE symmetry across all D-1 body sells
sym = b1.groupby(['und', 'expiry', 'cp']).lots.sum().unstack().fillna(0); sym['diff'] = sym.CE - sym.PE; print('D-1 total CE-PE lots per cycle: share equal', (sym['diff'] == 0).mean().round(3), 'median abs diff', sym['diff'].abs().median())
L.to_csv(f'{RES}/ladder_d1_agreement.csv', index=False)
