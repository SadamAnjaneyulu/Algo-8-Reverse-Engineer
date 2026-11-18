"""NOTE: passive_at_stop default close_all is an ASSUMPTION; *_passive_kept variants are the other bound.
Phase 1 evaluation of simulator v2 + window matching. ALL cycles were previously inspected: results are labelled CONTAMINATED-DEVELOPMENT, not evidence of validation."""
import json
from ledger import *
from opening_book import opening_book
import d0_sim_v2 as S2
from data import load_cycle
from matching import match, match_binned_legacy
F = load_fills(); C = pd.read_csv(f'{OUT}/cycles.csv'); C = C[C.carry_in_known]; EV = pd.read_csv(f'{REPL}/d0_reconstruction/results/d0_events.csv', parse_dates=['t']); LPn = pd.read_csv(f'{REPL}/results/live_cycle_pnl.csv'); LPn['expiry'] = LPn.expiry.str[:10]
VARS = {'V1_none': dict(price_stop=True), 'V1_none_passive_kept': dict(price_stop=True, passive_at_stop='keep'), 'V1_wings_one_per_lot': dict(price_stop=True, replacement_wings='one_per_lot'), 'V1_wings_passive_kept': dict(price_stop=True, replacement_wings='one_per_lot', passive_at_stop='keep'), 'V0_none': dict()}; res = []; orders = {v: [] for v in VARS}; passive_info = []
for r in C.itertuples():
    ev = EV[(EV.und == r.und) & (EV.expiry == r.expiry)]; c = load_cycle(r.und, r.expiry, r.d1, r.d0); start = opening_book(F, r.und, r.expiry, r.d1); split = 'HOLDOUT-LABEL' if r.expiry >= '2026-09-23' else 'DISCOVERY-LABEL'
    for v, kw in VARS.items():
        s = S2.simulate_d0(c, r.und, None, start=opening_book(F, r.und, r.expiry, r.d1), **kw); o = s['orders'].copy(); o['und'] = r.und; o['expiry'] = r.expiry; orders[v].append(o)
        res.append(dict(variant=v, und=r.und, expiry=r.expiry, split=split, v0=s['v0'], sim_gross=s['gross'], sim_d0=s['gross'] - s['v0'], stopped=s['stopped'], passive_open_at_end=len(s['passive_open_at_end']), live_gross=LPn[(LPn.und == r.und) & (LPn.expiry == r.expiry)].gross.iloc[0]))
R = pd.DataFrame(res); R['live_d0'] = R.live_gross - R.v0; R.to_csv(f'{OUT}/remediation_replay_cycles.csv', index=False)
print(R.groupby(['variant', 'split']).agg(cycles=('sim_d0', 'size'), sim_d0=('sim_d0', 'sum'), live_d0=('live_d0', 'sum'), stops=('stopped', 'sum'), passive_left=('passive_open_at_end', 'sum')).round(0))
# legacy v1.1 numbers for reference
for v in VARS: pd.concat(orders[v]).to_csv(f'{OUT}/remediation_orders_{v}.csv', index=False)
# scheduled-sale matching sensitivity (window one-to-one vs legacy bins); actual scheduled = window-defined sales (no replacement precedence, addressing A5) and class-defined
A = EV[(EV.day == 'D0') & (EV.module == 'num') & (EV.side == 'Sell') & (EV.opened_lots > 0)].merge(C[['und', 'expiry']], on=['und', 'expiry']); A['win'] = A.sched_gridA | A.sched_grid00
out = []
for v in ('V1_none', 'V0_none'):
    O = pd.concat(orders[v]); O = O[(O.cls == 'SCHEDULED_SALE')].assign(sec=lambda x: (555 + x.j) * 60, lots=lambda x: x.lots)
    for split, cond in (('DISCOVERY-LABEL', A.expiry < '2026-09-23'), ('HOLDOUT-LABEL', A.expiry >= '2026-09-23')):
        for defn, aa in (('class SCHEDULED_SALE (replacement precedence)', A[cond & (A.event_class == 'SCHEDULED_SALE')]), ('window-only scheduled (no precedence)', A[cond & A.win])):
            o = O[O.expiry.isin(aa.expiry.unique())]
            for tol in (0, 30, 60, 120, 180, 300):
                for sm in ('any', 'same'):
                    m = match(o[['und', 'expiry', 'cp', 'strike', 'sec', 'lots']], aa[['und', 'expiry', 'cp', 'strike', 'sec', 'lots']], tol, sm); out.append(dict(variant=v, split=split, actual_definition=defn, tolerance_s=tol, strike=sm, sim_lots=m['sim_lots'], act_lots=m['act_lots'], matched=m['matched'], precision=m['precision'], recall=m['recall']))
            for bs in (120, 600):
                m = match_binned_legacy(o[['und', 'expiry', 'cp', 'sec', 'lots']], aa[['und', 'expiry', 'cp', 'sec', 'lots']], bs); out.append(dict(variant=v, split=split, actual_definition=defn, tolerance_s=f'LEGACY_BIN_{bs}', strike='any', sim_lots=m['sim_lots'], act_lots=m['act_lots'], matched=m['matched'], precision=m['precision'], recall=m['recall']))
M = pd.DataFrame(out); M.to_csv(f'{OUT}/scheduled_matching_sensitivity.csv', index=False); pd.set_option('display.width', 250)
print(M[(M.variant == 'V1_none') & (M.strike == 'any') & (M.split == 'HOLDOUT-LABEL')][['actual_definition', 'tolerance_s', 'sim_lots', 'act_lots', 'precision', 'recall']].round(3).to_string(index=False))
