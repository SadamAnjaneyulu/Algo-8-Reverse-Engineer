"""Phase 3 analysis. Hypotheses and thresholds were fixed BEFORE evaluation (listed below); thresholds come from earlier project literature (1.55x stop band, Clock-B minute, <=Rs1 salvage), not tuned here. Chronological blocks: development = D0 < 2026-09-23 (22 cycles), later block = D0 >= 2026-09-23 (8 cycles).
EVIDENCE LABEL: all 30 cycles were previously inspected; the later block is NOT an independent holdout."""
from ledger import *
LT = pd.read_csv(f'{OUT}/carried_lots.csv.gz'); PN = pd.read_csv(f'{OUT}/contract_minute_panel.csv.gz'); L = pd.read_csv(f'{OUT}/lots.csv.gz'); F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv')
rng = np.random.default_rng(4); CONV = ('FIFO', 'LIFO', 'LOW_ENTRY_FIRST', 'HIGH_ENTRY_FIRST'); rowmod = F.set_index('row').module.to_dict(); rowsec = F.set_index('row').sec.to_dict(); rowday = F.set_index('row').day.to_dict()
# ---------- A. lot-level descriptive (carried = opened D-1, not closed on D-1)
cl = LT.merge(C[['und', 'expiry', 'd0']].assign(index=lambda x: x.und, cycle_id=lambda x: x.und + '_' + x.expiry)[['cycle_id', 'd0']], on='cycle_id')
def closed_day(r, conv):
    row = r[f'close_row_{conv}']
    return rowday.get(row, 'SETTLE') if row >= 0 else 'SETTLE'
for cv in CONV: cl[f'closeday_{cv}'] = [closed_day(r, cv) for _, r in cl.iterrows()]
car = cl[cl['closeday_FIFO'].isin([d for d in cl.d0.unique()]) | (cl['closeday_FIFO'] == 'SETTLE')].copy()          # FIFO-carried; set per convention below
rows = []
for cv in CONV:
    x = cl[(cl[f'closeday_{cv}'] != cl.cycle_id.map(C.assign(cid=C.und + '_' + C.expiry).set_index('cid').d1)) ]                # not closed on D-1
    mod = x[f'close_row_{cv}'].map(lambda r: rowmod.get(r, 'SETTLEMENT') if r >= 0 else 'SETTLEMENT'); rows.append(dict(convention=cv, carried_lots=len(x), body_buyback=(mod == 'num').mean(), stop_module=mod.isin(['s_', 'm_']).mean(), settlement=(mod == 'SETTLEMENT').mean(), other=(~mod.isin(['num', 's_', 'm_', 'SETTLEMENT'])).mean(),
                                                           median_close_minute=np.nanmedian([(rowsec[r] // 60 - 555) for r in x[f'close_row_{cv}'] if r >= 0 and rowday.get(r) != 'x']),))
A = pd.DataFrame(rows); A.to_csv(f'{OUT}/carried_disposition_by_convention.csv', index=False); pd.set_option('display.width', 250); print(A.round(3).to_string(index=False))
car = cl[cl.closed_on_d0 | cl.settled].copy(); car['quarter'] = pd.cut(car.close_minute_FIFO, [-1, 30, 90, 180, 300, 375], labels=['09:15-09:45', '09:45-10:45', '10:45-12:15', '12:15-14:15', '14:15-15:30'])
print('carried lots (FIFO: closed on D0 or settled):', len(car), ' closed D0', int(car.closed_on_d0.sum()), ' settled', int(car.settled.sum())); print('closing time distribution (FIFO):', car.quarter.value_counts(normalize=True).sort_index().round(3).to_dict())
print('premium: close/entry ratio median', (car.close_price_FIFO / car.entry_price).median().round(3), ' D0-open ratio quantiles', car.d0_open_ratio.quantile([.1, .25, .5, .75, .9]).round(2).to_dict()); print('MFE pts median', car.mfe_pts.median().round(1), 'MAE pts median', car.mae_pts.median().round(1), ' CE/PE hold(min) median', car.groupby('cp').hold_minutes_from_d0_open.median().to_dict())
car['dist_bin'] = pd.cut(car.off_steps_at_d0_open.abs(), [-1, 0.5, 1.5, 3, 6, 100]); print('share settled by |strike offset| at D0 open:', car.groupby('dist_bin', observed=True).settled.mean().round(3).to_dict(), ' n', car.groupby('dist_bin', observed=True).size().to_dict())
car.to_csv(f'{OUT}/carried_lots_analysed.csv.gz', index=False)
# ---------- B. hypotheses on the contract-minute panel
PN['block'] = np.where(PN.expiry >= '2026-09-23', 'LATER', 'DEV'); PN = PN[(PN.j >= 0) & (PN.j <= 358)]
H = {'H1 price stop: price >= 1.55 x cheapest open entry': PN.ratio_cheapest >= 1.55, 'H2 decay take-profit: price <= 0.5 x average entry': PN.ratio_avg <= 0.5, 'H3 Clock-B minute (mm%15=14, >=09:29)': PN.clockB, 'H4 ITM by >= 1 step': PN.itm & (PN.off_steps.abs() >= 1), 'H5 last hour (<= 1.0 h to expiry)': PN.hours_left <= 1.0,
     'H6 salvage: price <= Rs 1': PN.price <= 1.0, 'H7 clustered: <= 2 min since a cycle buy-back': PN.mins_since_cycle_buyback <= 2}
res = []
def lift_stats(d, pred):
    p = pred.loc[d.index]; ev = d.event; base = ev.mean(); n = p.sum()
    if n == 0 or ev.sum() == 0: return dict(n_pred=int(n), precision=np.nan, recall=np.nan, lift=np.nan)
    return dict(n_pred=int(n), precision=ev[p].mean(), recall=(ev & p).sum() / ev.sum(), lift=ev[p].mean() / base)
for blk in ('DEV', 'LATER', 'ALL'):
    d = PN if blk == 'ALL' else PN[PN.block == blk]; keys = d[['und', 'expiry']].drop_duplicates().values.tolist()
    for name, pred in H.items():
        s = lift_stats(d, pred); lifts = []; cyc_lift = []
        for (u, e), g in d.groupby(['und', 'expiry']):
            ls = lift_stats(g, pred); cyc_lift.append(ls['lift'])
        for _ in range(300):
            idx = rng.integers(0, len(keys), len(keys)); sel = pd.concat([d[(d.und == keys[i][0]) & (d.expiry == keys[i][1])] for i in idx[:60]]) if False else None
        cyc = np.array(cyc_lift, float); s.update(block=blk, hypothesis=name, base_rate=d.event.mean(), cycles=len(keys), cycles_lift_gt1=np.nanmean(cyc > 1), median_cycle_lift=np.nanmedian(cyc)); res.append(s)
R = pd.DataFrame(res); R.to_csv(f'{OUT}/carried_hypothesis_tests.csv', index=False); print(R[R.block != 'ALL'][['block', 'hypothesis', 'n_pred', 'precision', 'recall', 'lift', 'cycles_lift_gt1', 'base_rate']].round(3).to_string(index=False))
# coverage: share of buy-back contract-minutes explained by at least one hypothesis, and by none
anyp = np.zeros(len(PN), bool)
for p in H.values(): anyp |= p.values
ev = PN.event.values; print('buy-back events:', int(ev.sum()), ' explained by >=1 hypothesis:', round((ev & anyp).sum() / ev.sum(), 3), ' by none:', round((ev & ~anyp).sum() / ev.sum(), 3), ' predicate-union precision:', round(ev[anyp].mean(), 4), ' base', round(ev.mean(), 4))
for blk in ('DEV', 'LATER'): m = (PN.block == blk).values; print(blk, 'union recall', round((ev[m] & anyp[m]).sum() / ev[m].sum(), 3), 'precision', round(ev[m & anyp].mean(), 4), 'base', round(ev[m].mean(), 4))
