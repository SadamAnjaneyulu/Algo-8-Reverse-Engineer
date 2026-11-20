"""Buy-back study, step 6 (plan test D): what happens by the end of D-1 to body short lots that never reach ~1.2x? Lot level under three ownership conventions (FIFO / LOW / HIGH): highest minute-close premium ratio reached while open (price / own entry) vs closed on D-1 or carried overnight.
Strike-position level (ownership-free): highest cheapest-open-entry ratio reached at the strike during D-1 vs whether the strike still had body short lots at the end of D-1.
Outputs outputs/bl_close_D_lots.csv, bl_close_D_strikes.csv, bl_summary_close5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
L = pd.read_csv(f'{OUT}/bl_close_lots.csv'); P = pd.read_csv(f'{OUT}/bl_close_panel2.csv.gz'); R = {}
bins = [0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.0, 99]; rows = []
for cv in ('low', 'fifo', 'high'):
    l = L[L.conv == cv]; t = l.groupby(pd.cut(l.max_ratio, bins), observed=True).closed_d1.agg(['size', 'sum']); t['carried'] = t['size'] - t['sum']; t['carried_share'] = (t.carried / t['size']).round(3); t = t.reset_index(); t.insert(0, 'conv', cv); rows.append(t)
    R[f'{cv}_lots'] = len(l); R[f'{cv}_carried_share'] = float(1 - l.closed_d1.mean()); R[f'{cv}_never12_share'] = float((l.max_ratio < 1.2).mean()); R[f'{cv}_never12_carried_share'] = float(1 - l[l.max_ratio < 1.2].closed_d1.mean()); R[f'{cv}_ge12_carried_share'] = float(1 - l[l.max_ratio >= 1.2].closed_d1.mean())
    R[f'{cv}_never12_closed_n'] = int(l[(l.max_ratio < 1.2) & (l.closed_d1 == 1)].shape[0]); R[f'{cv}_never12_n'] = int((l.max_ratio < 1.2).sum()); R[f'{cv}_ge15_closed_share'] = float(l[l.max_ratio >= 1.5].closed_d1.mean()); R[f'{cv}_ge17_closed_share'] = float(l[l.max_ratio >= 1.7].closed_d1.mean())
    print(f'{cv}: lots {len(l)}, carried {R[cv + "_carried_share"]:.3f}; never reached 1.2x: {R[cv + "_never12_share"]:.3f} of lots, of which carried {R[cv + "_never12_carried_share"]:.3f}; reached >=1.2x: carried {R[cv + "_ge12_carried_share"]:.3f}; reached >=1.5x: closed {R[cv + "_ge15_closed_share"]:.3f}; >=1.7x: closed {R[cv + "_ge17_closed_share"]:.3f}')
T = pd.concat(rows); T.to_csv(f'{OUT}/bl_close_D_lots.csv', index=False); print(T.pivot(index='bin' if 'bin' in T else T.columns[1], columns='conv', values='carried_share').to_string())
# strike-position level
Pd = P[P.day == 'D-1']; S = Pd.groupby(['und', 'expiry', 'cp', 'strike']).agg(max_r_low=('r_low', 'max'), max_r_avg=('r_avg', 'max'), last_j=('j', 'max'), max_n=('n_open', 'max')).reset_index()
end = L[(L.conv == 'low')].groupby(['und', 'expiry', 'cp', 'strike']).agg(lots=('lot_id', 'size'), carried=('closed_d1', lambda s: int((1 - s).sum()))).reset_index(); S = S.merge(end, on=['und', 'expiry', 'cp', 'strike'], how='left'); S['status'] = np.where(S.carried.fillna(0) > 0, 'carried (some lots)', 'fully closed on D-1')
S.to_csv(f'{OUT}/bl_close_D_strikes.csv', index=False)
t = S.groupby(pd.cut(S.max_r_low, [0, 1.0, 1.2, 1.4, 1.5, 1.6, 1.7, 99]), observed=True).agg(n=('status', 'size'), carried=('status', lambda s: (s == 'carried (some lots)').sum())); t['carried_share'] = (t.carried / t.n).round(3); print('\nstrike positions on D-1 by highest cheapest-open-entry ratio reached'); print(t.to_string()); R['strike_table'] = t.reset_index().assign(max_r_low=lambda d: d.max_r_low.astype(str)).to_dict('list')
R['strike_n'] = len(S); R['strike_carried_share'] = float((S.status == 'carried (some lots)').mean()); R['strike_never12_n'] = int((S.max_r_low < 1.2).sum()); R['strike_never12_carried'] = float((S[S.max_r_low < 1.2].status == 'carried (some lots)').mean())
print(f'strike positions {len(S)}, carried {R["strike_carried_share"]:.3f}; never reaching 1.2x (cheapest-entry ref): {R["strike_never12_n"]}, of which carried {R["strike_never12_carried"]:.3f}')
# robustness: lots sold before 12:00 IST (>= 3.25 h of D-1 left) so that late sales do not mechanically carry
for cv in ('low', 'fifo', 'high'):
    l = L[(L.conv == cv) & (L.t_entry < 12 * 3600)]; R[f'{cv}_early_n'] = len(l); R[f'{cv}_early_never12_carried'] = float(1 - l[l.max_ratio < 1.2].closed_d1.mean()); R[f'{cv}_early_ge15_closed'] = float(l[l.max_ratio >= 1.5].closed_d1.mean()); R[f'{cv}_early_carried'] = float(1 - l.closed_d1.mean())
    print(f'{cv} early lots (sold before 12:00): {len(l)}, carried {R[cv + "_early_carried"]:.3f}; never reached 1.2x: carried {R[cv + "_early_never12_carried"]:.3f}; reached >=1.5x: closed {R[cv + "_early_ge15_closed"]:.3f}')
rec('close5', R)
