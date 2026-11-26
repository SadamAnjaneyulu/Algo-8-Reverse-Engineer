#!/usr/bin/env python3
"""Python reference dump of one cycle in the same text format as dump_cycle.cpp (for the parity check)."""
import sys, os
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (R, f'{R}/d1_strategy', f'{R}/d0_strategy', f'{R}/backtest'): sys.path.insert(0, p)
from backtest.recon_bt import engine_run as E
from d1_algo import config_for, D1Engine, ReplayFeed, PaperBroker, run_replay
from d1_algo.models import Lot
from d0_algo import D0Engine, D0Market
from algo8_integrated.handoff import d1_state_to_d0_opening
ROLE = {'scheduled_straddle': 0, 'breakout_straddle': 1, 'breakout_extra': 2, 'ladder_solo': 3, 'stop_buyback': 4, 'protective_wing_buy': 5, 'protective_wing_sell': 6, 'opening_wing_buy': 7, 'overnight_lump': 8, 'cycle_stop_buyback': 9, 'cycle_stop_sell': 10}
CLS = {'body_sell': 0, 'body_buyback': 1, 'body_long': 2, 'wing_buy': 3, 'wing_sell': 4, 'stop': 5}
def main(und, ex, d1, d0, lot, stop, data=None):
    sp1, o1 = E.load_session(und, ex, d1); sp0, o0 = E.load_session(und, ex, d0)
    feed = ReplayFeed(sp1.open.values, sp1.high.values, sp1.low.values, sp1.close.values, o1['K'], {k: v for k, v in o1.items() if isinstance(k, tuple)})
    cfg = config_for(und, d1, order_split='one_lot_v2', lot_units=lot, cycle_stop_rupees=(stop or None)); br = PaperBroker(feed); e1 = D1Engine(cfg, feed, br); run_replay(e1, feed)
    for f in br.all_fills: print('D1 %.0f %d %.0f %d %d %.2f %d' % (f.ts, 0 if f.right == 'CE' else 1, f.strike, 1 if f.side == 'BUY' else -1, f.lots, f.price, ROLE[f.role]))
    if e1.stopped: print('D1STOP %.0f' % e1.stop_time); return
    mk = D0Market(K=o0['K'], step=E.STEP[und], unit=float(lot), spot_open=sp0.open.values, spot_high=sp0.high.values, spot_low=sp0.low.values, spot_close=sp0.close.values, opt={k: v for k, v in o0.items() if isinstance(k, tuple)})
    b = E._Book(); b.shorts = {}
    for (cp, k), lots in e1.book.shorts.items():
        for l in lots: b.shorts.setdefault((cp, k), []).append(l)
    b.wings = {k: v for k, v in e1.book.wings.items() if v > 0}; b.lump = {k: v for k, v in e1.book.lump.items() if v > 0}
    op = d1_state_to_d0_opening(b, [E._Fill('SELL' if f.side == 'SELL' else 'BUY', f.price, f.lots) for f in br.all_fills], float(lot), chain=mk.K)
    print('OPEN lots %d longs %d cash %.6f' % (len(op.lots), len(op.longs), op.cash))
    e0 = D0Engine(E.d0_config(und, d1, stop or None), mk, op); e0.run()
    for e in e0.events: print('D0 %d %d %d %d %d %.4f' % (CLS[e.cls], 0 if e.cp == 'CE' else 1, int(e.strike), e.j, e.lots, e.px))
if __name__ == '__main__':
    a = sys.argv[1:]; main(a[0], a[1], a[2], a[3], int(a[4]), float(a[5]) if len(a) > 5 else 0.0)
