"""Time-ordered event tables (D-1 and D0) for ALL modules, with ATM references and contract/right state after every event.
Event time: body orders = first fill second (resolution 1 s); h_/s_/v_/m_ = microsecond decision stamp. Position columns are contract-level (all modules): net lots of the traded contract, and S / L (short / long lots) of the right after the event.
Sell classes (body open_short only): slot_minute (minute 09:16+15k, k=0..), minute_before_slot, roll_sell (body cover on the same right <= 60 s earlier), other. Outputs outputs/bl_events_d1.csv, bl_events_d0.csv, pickles for later studies."""
import sys; sys.path.insert(0, '.')
from bl_common import *
O = order_table(); R = pd.read_csv(f'{OUT}/bh_b1_order_roles.csv', dtype={'tag': str})[['tag', 'role']]; O = O.merge(R, on='tag', how='left'); ch = Chain()
O['te'] = np.where(O.module.isin(['h_', 's_', 'v_', 'm_']), O.tt_dec, O.tt_first); O['sl'] = np.where(O.side == 'Buy', O.lots, -O.lots); O['step'] = O.und.map(ref.STEP)
O['tod'] = O.te % 100000; O['jj'] = np.floor((O.tod - ref.OPEN_SEC) / 60).astype(int).clip(0, 374)
sp = []; sc = []; a1 = []; a2 = []
for r in O.itertuples():
    st = ch.strikes(r.und, r.expiry); a = ch.spot(r.und, r.expiry, r.dayno, r.jj - 1) if r.jj >= 1 else np.nan; b = ch.spot(r.und, r.expiry, r.dayno, r.jj)
    sp.append(a); sc.append(b); a1.append(st[np.argmin(np.abs(st - a))] if a == a else np.nan); a2.append(st[np.argmin(np.abs(st - b))] if b == b else np.nan)
O['spot_prev'] = sp; O['spot_cur'] = sc; O['atm_prev'] = a1; O['atm_cur'] = a2; O['off_prev'] = (O.strike - O.atm_prev) / O.step
O['ref_px'] = np.where(O.side == 'Sell', O.lim_px / .85, O.lim_px / 1.15)
# classes for body sells
O['cls'] = ''
mo = ((O.tod - (9 * 3600 + 16 * 60)) // 60) % 15
cov = O[(O.module == 'num') & (O.role == 'cover_short')]
roll = np.zeros(len(O), bool)
for (u, e, cp), g in O[(O.module == 'num') & (O.role == 'open_short')].groupby(['und', 'expiry', 'cp']):
    c = np.sort(cov[(cov.und == u) & (cov.expiry == e) & (cov.cp == cp)].tt_first.values)
    for i, t in zip(g.index, g.tt_first.values):
        k = np.searchsorted(c, t, side='right'); roll[i] = (k > 0) and (t - c[k - 1] <= 60)
m = (O.module == 'num') & (O.role == 'open_short')
O.loc[m, 'cls'] = np.where(roll[m], 'roll_sell', np.where(mo[m] == 0, 'slot_minute', np.where(mo[m] == 14, 'minute_before_slot', 'other')))
O.loc[(O.module == 'num') & (O.role != 'open_short'), 'cls'] = O.role
O.loc[O.module != 'num', 'cls'] = O.module.map({'h_': 'hedge', 's_': 'stop', 'v_': 'lump', 'm_': 'manual'}); O['cls'] = O.cls.where(O.module == 'num', O.cls) 
# running state per cycle
rows = []
for (u, e), o in O.sort_values(['und', 'expiry', 'te', 'row']).groupby(['und', 'expiry']):
    net = {}
    for r in o.itertuples():
        k = (r.cp, r.strike); net[k] = net.get(k, 0) + r.sl
        S = sum(-v for (c, s), v in net.items() if c == r.cp and v < 0); L = sum(v for (c, s), v in net.items() if c == r.cp and v > 0)
        rows.append((r.Index, net[k], S, L))
X = pd.DataFrame(rows, columns=['i', 'net_after', 'S_after', 'L_after']).set_index('i'); O = O.join(X)
def hms(t): return '%02d:%02d:%06.3f' % (t // 3600, (t % 3600) // 60, t % 60)
E_ = O.sort_values(['und', 'expiry', 'te', 'row']).copy(); E_['time_IST'] = E_.tod.map(hms); E_['day'] = E_.dayno.map({0: 'D-1', 1: 'D0'})
cols = ['und', 'expiry', 'day', 'time_IST', 'module', 'cls', 'cp', 'side', 'strike', 'lots', 'lim_px', 'ref_px', 'px_avg', 'spot_prev', 'atm_prev', 'atm_cur', 'off_prev', 'net_after', 'S_after', 'L_after', 'complete', 'tag']
E_ = E_[cols].rename(columns={'cp': 'right', 'lim_px': 'limit', 'px_avg': 'fill', 'off_prev': 'strike_minus_ATMprev_steps', 'net_after': 'contract_net_after', 'complete': 'carry_in_known'})
for d, nm in (('D-1', 'd1'), ('D0', 'd0')): E_[E_.day == d].to_csv(f'{OUT}/bl_events_{nm}.csv', index=False)
O.to_pickle(ORDERS_PKL); print(len(O), O.groupby(['dayno', 'cls']).lots.sum().unstack(0).fillna(0).astype(int))
