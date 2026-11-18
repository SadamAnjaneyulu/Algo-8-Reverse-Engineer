"""Fit the small set of DISCOVERY-ONLY parameters of rule set D0-v1 -> rules_d0_v1.json. Uses only discovery cycles (holdout guard active)."""
import json
from d0common import *
E = load_events(True); D = E[(E.day == 'D0') & (E.module == 'num')]; cyc = D[['und', 'expiry']].drop_duplicates()
# (S1) scheduled-sale ladder: lots per right in the first 3 minutes of each grid-A slot, scheduled class only; median over discovery cycles where the book was active (>=1 short body lot)
sc = D[(D.side == 'Sell') & (D.opened_lots > 0) & (D.event_class == 'SCHEDULED_SALE') & D.sched_gridA].copy(); sc['slot'] = ((sc.sec - (9 * 3600 + 16 * 60) + 2) // 900).astype(int)
lad = []
for k in range(25):
    row = {}
    for cp in ('CE', 'PE'):
        x = sc[(sc.slot == k) & (sc.cp == cp)].groupby(['und', 'expiry']).lots.sum(); full = cyc.merge(x.rename('l').reset_index(), how='left', on=['und', 'expiry']).fillna(0).l
        row[cp] = int(round(full.median()))
    lad.append(row)
# (S2) Clock-B act threshold: maximise F1 of 'total short body lots >= theta' for 'tick acted' on discovery ticks
T = pd.read_csv(f'{RES}/c1_ticks_discovery.csv'); best = None
for th in sorted(T.lots.unique()):
    pred = T.lots >= th; tp = (pred & T.acted).sum(); p = tp / max(pred.sum(), 1); r = tp / T.acted.sum(); f1 = 2 * p * r / (p + r) if p + r else 0
    if best is None or f1 > best[0]: best = (f1, th, p, r)
# wing ratios from discovery (paired wings): median wing/body price ratio by class, wings per sold lot
w = D[(D.side == 'Sell') & (D.opened_lots > 0) & D.event_class.isin(['SCHEDULED_SALE', 'OFF_SCHEDULE_SALE', 'REPLACEMENT_SALE'])]; ws = w[w.event_class != 'REPLACEMENT_SALE']; wr = w[w.event_class == 'REPLACEMENT_SALE']
rules = dict(version='D0-v1', fitted_on='DISCOVERY cycles only (D0 < 2026-09-23)', n_discovery_cycles_with_d0=int(len(cyc)), S1_scheduled_ladder_slot0_is_0916=lad, S2_clockB_act_threshold_total_short_lots=int(best[1]), S2_fit_discovery=dict(F1=best[0], precision=best[2], recall=best[3], ticks=int(len(T)), acted_share=float(T.acted.mean())),
             S2_contract_choice='short body contract with the most lots (ties: nearest to ATM)', S2_buyback_lots=1, S2_replacement='1 lot, same right, nearest strike to previous-minute spot, minute after the buyback', S3_price_stop_mult=1.6, S3_status='HYPOTHESIS (weak on D0: EXT-05); replayed as an explicit variant',
             S4_final_flatten_minute_0915_eq_0=359, S5_wing_ratio_sched_off=float((ws.wing_px / ws.px).median()), S5_wing_lots_per_lot_sched_off=1.0, S5_wing_lots_per_lot_replacement=float(wr.wing_lots.sum() / wr.lots.sum()), S5_wing_ratio_replacement=float((wr.wing_px / wr.px).median()), cycle_stop_rs=144000)
json.dump(rules, open(f'{RES}/rules_d0_v1.json', 'w'), indent=1); print(json.dumps(rules, indent=1)[:2500])
