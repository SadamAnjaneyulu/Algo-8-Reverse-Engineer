"""Reactive-pair mechanism study, step 1 (plan BODY_REACTIVE_MECHANISM_PLAN.md): add volume, realised-volatility and range-from-open features to the D-1 cycle-minute panel; per-cycle onset/stop table; block-level volume/volatility table.
Outputs bl_mech_panel.csv.gz, bl_mech_cycle.csv, bl_mech_block.csv"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
P = pd.read_csv(f'{OUT}/bl_react_panel.csv.gz'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); ch = Chain(); STEP = ref.STEP; rows = []; cyc_rows = []; blk_rows = []
for r0 in CY.itertuples():
    u, e = r0.und, r0.expiry; c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); step = STEP[u]; spot = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values
    vol = {cp: np.nan_to_num(np.array(c[(0, cp, 'volume')], dtype=float)) for cp in ('CE', 'PE')}; atm0 = K[np.argmin(np.abs(K - spot[1]))]
    ret = np.abs(np.diff(spot, prepend=spot[0])) / spot * 100; rv15 = pd.Series(ret).rolling(15, min_periods=1).sum().values; rv5 = pd.Series(ret).rolling(5, min_periods=1).sum().values
    hi = np.maximum.accumulate(spot); lo = np.minimum.accumulate(spot); atmv = np.zeros(375); totv = np.zeros(375)
    for j in range(375):
        i = int(np.argmin(np.abs(K - spot[j]))); sl = slice(max(i - 3, 0), i + 4); atmv[j] = vol['CE'][sl, j].sum() + vol['PE'][sl, j].sum(); totv[j] = vol['CE'][:, j].sum() + vol['PE'][:, j].sum()
    atmv15 = pd.Series(atmv).rolling(15, min_periods=1).sum().values; totv15 = pd.Series(totv).rolling(15, min_periods=1).sum().values
    dev = np.abs(spot - atm0) / step; maxdev = np.maximum.accumulate(dev)
    for j in range(375):
        rows.append((u, e, j, atmv[max(j - 1, 0)], atmv15[max(j - 1, 0)], totv15[max(j - 1, 0)], rv5[max(j - 1, 0)], rv15[max(j - 1, 0)], dev[max(j - 1, 0)], maxdev[max(j - 1, 0)], (hi[max(j - 1, 0)] / lo[max(j - 1, 0)] - 1) * 100))
    # onset table
    re = Pr[(Pr.und == u) & (Pr.expiry == e) & Pr.reactive].tod.values; first_re = re.min() if len(re) else np.nan; last_re = re.max() if len(re) else np.nan; so = O_sells = None
    def first_cross(th): w = np.where(dev >= th)[0]; return 33300 + w[0] * 60 if len(w) else np.nan
    cyc_rows.append((u, e, first_re, last_re, len(re), first_cross(1), first_cross(1.5), first_cross(2), first_cross(3), (33300 + np.where((hi / lo - 1) * 100 >= 0.2)[0][0] * 60) if ((hi / lo - 1) * 100 >= 0.2).any() else np.nan, (33300 + np.where((hi / lo - 1) * 100 >= 0.3)[0][0] * 60) if ((hi / lo - 1) * 100 >= 0.3).any() else np.nan))
    for b in range(25):
        js = np.arange(1 + 15 * b, min(1 + 15 * b + 15, 375)); blk_rows.append((u, e, b, totv[js].sum(), atmv[js].sum(), ret[js].sum(), dev[js].mean()))
F = pd.DataFrame(rows, columns=['und', 'expiry', 'j', 'atm_vol1', 'atm_vol15', 'tot_vol15', 'rv5', 'rv15', 'dev_open', 'maxdev_open', 'range_pct2']); P = P.merge(F, on=['und', 'expiry', 'j'], how='left'); P.to_csv(f'{OUT}/bl_mech_panel.csv.gz', index=False)
C = pd.DataFrame(cyc_rows, columns=['und', 'expiry', 'first_react', 'last_react', 'n_react', 't_dev1', 't_dev15', 't_dev2', 't_dev3', 't_range02', 't_range03']); C.to_csv(f'{OUT}/bl_mech_cycle.csv', index=False)
B = pd.DataFrame(blk_rows, columns=['und', 'expiry', 'block', 'tot_vol', 'atm_vol', 'rv', 'dev_open']); B.to_csv(f'{OUT}/bl_mech_block.csv', index=False)
hm = lambda s: f'{int(s // 3600)}:{int((s % 3600) // 60):02d}'
print('per-cycle first / last reactive pair (clock) quantiles 10/25/50/75/90:', [hm(x) for x in C.first_react.quantile([.1, .25, .5, .75, .9])], [hm(x) for x in C.last_react.quantile([.1, .25, .5, .75, .9])])
print('first time |spot - open ATM| >= 1 / 1.5 / 2 / 3 steps (median):', [hm(C[c].median()) for c in ('t_dev1', 't_dev15', 't_dev2', 't_dev3')])
print(P.shape)
