"""Body module reconstruction (B1-B4) from the numeric-tag order stream, contract-level roles (bh_b1_order_roles.csv).
B1 structure: per D-1 slot (09:16 + 15k min, first 3 minutes): CE vs PE short strikes (equal?), equal lots, which right first; the long wings that the body stream itself buys (role open_long): when / how far OTM.
B2 strike selection of body open_short orders: nearest strike to previous-minute spot close (exact / +-1), synthetic-ATM argmin|C-P| at j-1 close, null = nearest to the spot of a random other minute of the same day.
B3 quantity: lots per order, fills per order, ladder lots per slot (CE vs PE).
B4 entry execution: limit cushion (see bh_h4), fill price vs prior minute close, order spacing in a ladder."""
import sys; sys.path.insert(0, '.')
from bh_common import *
R = pd.read_csv(f'{OUT}/bh_b1_order_roles.csv', dtype={'tag': str}); O = order_table(); ch = Chain(); rng = np.random.default_rng(3)
Bd = O[O.module == 'num'].merge(R[['tag', 'role', 'net_before']], on='tag', how='left'); Bd['slot_off'] = Bd.t_first - (9 * 3600 + 16 * 60); Bd['slot'] = np.round(Bd.slot_off / 900).astype(int); Bd['in_win'] = (Bd.slot_off - Bd.slot * 900 >= -30) & (Bd.slot_off - Bd.slot * 900 < 210)
SH = Bd[(Bd.role == 'open_short') & (Bd.dayno == 0) & Bd.in_win & (Bd.slot >= 0) & (Bd.slot <= 16)]
rows = []
for (u, e, k), g in SH.groupby(['und', 'expiry', 'slot']):
    ce = g[g.cp == 'CE']; pe = g[g.cp == 'PE']
    if len(ce) and len(pe):
        kc = ce.strike.mode().iloc[0]; kp = pe.strike.mode().iloc[0]; rows.append((u, e, k, kc, kp, (kc - kp) / ref.STEP[u], ce.lots.sum(), pe.lots.sum(), ce.t_first.min() - pe.t_first.min(), g.dayno.iloc[0]))
SL = pd.DataFrame(rows, columns=['und', 'expiry', 'slot', 'k_ce', 'k_pe', 'ce_minus_pe_steps', 'lots_ce', 'lots_pe', 'ce_first_minus_pe_first_s', 'day']); SL.to_csv(f'{OUT}/bh_b1_slot_structure.csv', index=False)
print('B1 D-1 slots with both rights sold:', len(SL), 'cycles', SL.groupby(['und', 'expiry']).ngroups)
print('  modal CE strike == modal PE strike (same-strike straddle):', (SL.ce_minus_pe_steps == 0).mean().round(3), '| CE strike above PE strike:', (SL.ce_minus_pe_steps > 0).mean().round(3), '| below:', (SL.ce_minus_pe_steps < 0).mean().round(3), '| steps CE-PE quantiles', SL.ce_minus_pe_steps.quantile([.1, .25, .5, .75, .9]).tolist())
print('  equal lots CE=PE:', (SL.lots_ce == SL.lots_pe).mean().round(3), '| CE sold first (strict):', (SL.ce_first_minus_pe_first_s < 0).mean().round(3), 'PE first:', (SL.ce_first_minus_pe_first_s > 0).mean().round(3), 'same second:', (SL.ce_first_minus_pe_first_s == 0).mean().round(3))
LG = Bd[(Bd.role == 'open_long')]; LG = LG.assign(hh=(LG.t_first // 3600).astype(int) * 100 + ((LG.t_first % 3600) // 60).astype(int))
print('B1 long buys in the numeric stream:', int(LG.lots.sum()), 'lots in', len(LG), 'orders; by day', LG.groupby('dayno').lots.sum().to_dict(), '; hour-minute (top)', LG.groupby('hh').lots.sum().sort_values(ascending=False).head(5).to_dict())
# B2 strike selection
rows = []
for r in Bd[(Bd.role == 'open_short')].itertuples():
    j = int(r.j)
    if j < 1: continue
    sp = ch.spot(r.und, r.expiry, r.dayno, j - 1); st = ch.strikes(r.und, r.expiry)
    if sp != sp: continue
    near = st[np.argmin(np.abs(st - sp))]; sp_rand = ch.spot(r.und, r.expiry, r.dayno, int(rng.integers(0, 375))); near_null = st[np.argmin(np.abs(st - sp_rand))] if sp_rand == sp_rand else np.nan
    cp_ = np.array([ch.px(r.und, r.expiry, r.dayno, 'CE', k, j - 1, 'close') for k in st]); pp_ = np.array([ch.px(r.und, r.expiry, r.dayno, 'PE', k, j - 1, 'close') for k in st]); ok = ~np.isnan(cp_) & ~np.isnan(pp_) & (cp_ > 0.5) & (pp_ > 0.5)
    atm = st[ok][np.argmin(np.abs(cp_[ok] - pp_[ok]))] if ok.any() else np.nan
    rows.append((r.und, r.expiry, r.dayno, r.cp, r.strike, near, near_null, atm, ref.STEP[r.und], sp - r.strike if r.cp == 'CE' else r.strike - sp))
Z = pd.DataFrame(rows, columns=['und', 'expiry', 'dayno', 'cp', 'strike', 'near', 'near_null', 'atm', 'step', 'itm_pts']); Z.to_csv(f'{OUT}/bh_b2_strike.csv', index=False)
for d in (0, 1):
    z = Z[Z.dayno == d]; print('B2 day', ['D-1', 'D0'][d], 'n', len(z), '| nearest(prev spot close) exact %.3f +-1 %.3f | null exact %.3f | synthetic ATM exact %.3f +-1 %.3f' % ((z.strike == z.near).mean(), ((z.strike - z.near).abs() <= z.step * 1.0001).mean(), (z.strike == z.near_null).mean(), (z.strike == z.atm).mean(), ((z.strike - z.atm).abs() <= z.step * 1.0001).mean()), '| median distance of sold strike from spot (steps) CE/PE:', (z[z.cp == 'CE'].itm_pts / z[z.cp == 'CE'].step).median().round(2), (z[z.cp == 'PE'].itm_pts / z[z.cp == 'PE'].step).median().round(2))
# B3/B4
print('B3 body order sizes (lots):', Bd.lots.value_counts().head(5).to_dict(), '| fills per order:', Bd.n_fills.value_counts().head(4).to_dict(), '| orders with a PartiallyFilled row:', (Bd.n_partial > 0).mean().round(3))
gp = []
for (u, e, cp, d), g in Bd[Bd.role == 'open_short'].groupby(['und', 'expiry', 'cp', 'dayno']):
    t = np.sort(g.tt_first.values); dt = np.diff(t); gp.extend(dt[dt < 60])
print('B4 spacing between consecutive body short-sale orders on one right (<60 s): quantiles 25/50/75/90:', np.quantile(gp, [.25, .5, .75, .9]).round(1).tolist(), ' share same second', (np.array(gp) == 0).mean().round(3))
