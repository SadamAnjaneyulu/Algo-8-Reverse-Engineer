"""DISCOVERY ONLY. Off-schedule vs scheduled vs replacement D0 sales: timing, strike, balance, wings, P&L per lot."""
from d0common import *
from data import load_cycle, NM
E = load_events(True); Lg = pd.read_csv(f'{RES}/lot_lineage.csv'); Lg = Lg[Lg.split == 'DISCOVERY']
D0 = E[(E.day == 'D0') & (E.module == 'num') & (E.side == 'Sell') & (E.opened_lots > 0)].copy(); rng = np.random.default_rng(1)
print('D0 sales discovery orders:', len(D0), D0.groupby('event_class').lots.sum().round(0).to_dict())
# (a) strike offset (steps vs previous-minute spot) by class
a = D0.groupby('event_class').off_steps.describe(percentiles=[.1, .25, .5, .75, .9]).round(2); a['exact_nearest'] = D0.groupby('event_class').apply(lambda x: (x.off_steps.abs() <= 0.5).mean()).round(3); a['within1'] = D0.groupby('event_class').apply(lambda x: (x.off_steps.abs() <= 1.0).mean()).round(3); a.to_csv(f'{RES}/c3_sale_strike_offset_by_class.csv'); print(a[['count', '25%', '50%', '75%', 'exact_nearest', 'within1']])
# (b) ATM migration: did the nearest strike change in the 1-3 minutes before the sale (previous-minute spot grid)?
rows = []
for (u, e), g in D0.groupby(['und', 'expiry']):
    st = E[(E.und == u) & (E.expiry == e)].iloc[0]; c = load_cycle(u, e, st.d1, st.d0); sp = c[(1, 'spot')]; step = 50 if u == 'NIFTY' else 100; atm = step * np.floor(sp / step + 0.5)
    for r in g.itertuples():
        j = r.minute - 1
        if j < 5 or j >= NM: continue
        ch = {w: float(atm[j] != atm[j - w]) for w in (1, 3, 5)}; mv = abs(sp[j] - sp[j - 3]) / step
        rows.append(dict(cls=r.event_class, lots=r.lots, **{f'atm_changed_{w}m': v for w, v in ch.items()}, abs_move3m_steps=mv, und=u))
M = pd.DataFrame(rows)
# null: all D0 minutes 09:20..15:00 for the same cycles
nul = []
for (u, e), g in D0.groupby(['und', 'expiry']):
    st = E[(E.und == u) & (E.expiry == e)].iloc[0]; c = load_cycle(u, e, st.d1, st.d0); sp = c[(1, 'spot')]; step = 50 if u == 'NIFTY' else 100; atm = step * np.floor(sp / step + 0.5)
    for j in range(6, 345): nul.append(dict(atm_changed_1m=float(atm[j] != atm[j - 1]), atm_changed_3m=float(atm[j] != atm[j - 3]), atm_changed_5m=float(atm[j] != atm[j - 5]), abs_move3m_steps=abs(sp[j] - sp[j - 3]) / step))
N = pd.DataFrame(nul); b = M.groupby('cls')[['atm_changed_1m', 'atm_changed_3m', 'atm_changed_5m', 'abs_move3m_steps']].mean().round(3); b.loc['ALL-MINUTES NULL'] = N.mean().round(3); b.to_csv(f'{RES}/c3_atm_migration_by_class.csv'); print(b)
# (c) balance: does the sale go to the lighter side of the short book? (CE vs PE short lots before)
D0['own'] = np.where(D0.cp == 'CE', D0.body_short_CE, D0.body_short_PE); D0['other'] = np.where(D0.cp == 'CE', D0.body_short_PE, D0.body_short_CE); D0['to_lighter'] = D0.own < D0.other
print('share of sales going to the lighter side (excluding ties):', D0[D0.own != D0.other].groupby('event_class').to_lighter.mean().round(3).to_dict(), ' lots ratio sale/own-side book:', (D0.lots / D0.own.replace(0, np.nan)).groupby(D0.event_class).median().round(3).to_dict())
# (d) wings coupling
w = D0.groupby('event_class').apply(lambda x: pd.Series(dict(wing_paired=(x.wing_lots > 0).mean(), wing_lots_per_lot=x.wing_lots.sum() / x.lots.sum(), wing_ratio_median=(x.wing_px / x.px).median(), wing_delay_median_s=x.wing_delay_s.median()))).round(3); w.to_csv(f'{RES}/c3_wing_coupling_by_class.csv'); print(w)
# (e) P&L per lot by opening class (D0-opened body lots, discovery)
p = Lg[(Lg.role == 'body') & (Lg.open_day == 'D0') & (Lg.open_class.isin(['SCHEDULED_SALE', 'OFF_SCHEDULE_SALE', 'REPLACEMENT_SALE']))].groupby('open_class').apply(lambda x: pd.Series(dict(lots=x.lots.sum(), pnl=x.pnl.sum(), pnl_per_lot=x.pnl.sum() / x.lots.sum(), win_rate_lotw=(x.lots * (x.pnl > 0)).sum() / x.lots.sum(), median_hold_min=x.hold_min.median(), settled_share=(x.lots * (x.close_class == 'SETTLEMENT')).sum() / x.lots.sum()))).round(2); p.to_csv(f'{RES}/c3_pnl_by_open_class_discovery.csv'); print(p)
# cycle-level bootstrap CI for pnl/lot by class (resample cycles)
cyc = Lg[(Lg.role == 'body') & (Lg.open_day == 'D0')].groupby(['und', 'expiry', 'open_class']).agg(l=('lots', 'sum'), p=('pnl', 'sum')).reset_index(); keys = cyc[['und', 'expiry']].drop_duplicates().values.tolist(); out = []
for oc in ['SCHEDULED_SALE', 'OFF_SCHEDULE_SALE', 'REPLACEMENT_SALE']:
    x = cyc[cyc.open_class == oc].set_index(['und', 'expiry']); bs = []
    for _ in range(2000):
        idx = rng.integers(0, len(keys), len(keys)); sel = [tuple(keys[i]) for i in idx]; ll = sum(x.l.get(k, 0) for k in sel); pp = sum(x.p.get(k, 0) for k in sel); bs.append(pp / ll if ll else np.nan)
    out.append(dict(open_class=oc, pnl_per_lot_ci95_lo=np.nanpercentile(bs, 2.5), ci95_hi=np.nanpercentile(bs, 97.5)))
print(pd.DataFrame(out).round(1))
