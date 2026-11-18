import os, sys, math
import numpy as np, pandas as pd, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bt import account as A, scen, cycles as Cy, config as C, metrics as M


def mini_cycle():
    """synthetic 4-leg cycle: short CE/PE 100, wings 120/80; 1 lot = 10; every leg has D-1 bars 09:15.. and D0 bars"""
    def fr(day, prices):
        return pd.DataFrame(dict(datetime=[f'{day} 09:{15 + i}:00' for i in range(len(prices))], hm=[f'09:{15 + i}' for i in range(len(prices))], open=prices, high=prices, low=prices, close=prices, volume=[100] * len(prices), open_interest=[1] * len(prices)))
    legs = {'SCE': dict(strike=100, nominal_strike=100, cp='CE', side=-1, hm='09:16', open=10.0, close=10.0, volume=1, substituted=False), 'SPE': dict(strike=100, nominal_strike=100, cp='PE', side=-1, hm='09:16', open=8.0, close=8.0, volume=1, substituted=False),
            'WCE': dict(strike=120, nominal_strike=120, cp='CE', side=1, hm='09:16', open=1.0, close=1.0, volume=1, substituted=False), 'WPE': dict(strike=80, nominal_strike=80, cp='PE', side=1, hm='09:16', open=1.0, close=1.0, volume=1, substituted=False)}
    d1, d0 = '2024-03-27', '2024-03-28'; frames = {l: (fr(d1, [legs[l]['open']] * 4), fr(d0, [legs[l]['open']] * 4)) for l in legs}
    return dict(und='NIFTY', expiry=d0, d1=d1, d0=d0, lot_d1=10, lot_d0=10, K=100, W=20, legs=legs, frames=frames, official_close=112.0, official_close_src='TEST', feasible=True)


FILLS = lambda c: [(f'S{i + 1}-{l}', scen.iid(c, l), scen.epoch(c['d1'], '09:16'), c['legs'][l]['side'], 30, int(round(c['legs'][l]['open'] * 100))) for i, l in enumerate(sorted(c['legs']))]


def test_settlement_gross_pnl_is_hand_calculable():
    c = mini_cycle(); a = A.account(c, FILLS(c), 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0, cost_mult=0))
    # close 112: short CE 100 loses (12-10)*30=60; short PE gains 8*30=240; long CE 120 expires 0 (-1*30); long PE 80 expires 0 (-30)
    assert a['gross'] == pytest.approx(-60 + 240 - 30 - 30) and a['net'] == pytest.approx(a['gross']) and a['slippage'] == 0 and a['costs'] == 0


def test_slippage_goes_against_every_order_and_costs_are_positive():
    c = mini_cycle(); a0 = A.account(c, FILLS(c), 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0, cost_mult=0)); a1 = A.account(c, FILLS(c), 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0.5, cost_mult=0)); a2 = A.account(c, FILLS(c), 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0, cost_mult=1))
    assert a1['net'] == pytest.approx(a0['net'] - 4 * 0.5 * 30) and a1['slippage'] == pytest.approx(60) and a2['costs'] > 0 and a2['net'] < a0['net']


def test_cost_schedule_by_date():
    assert A.stt_sell('2024-09-30') == 0.000625 and A.stt_sell('2024-10-01') == 0.001 and A.stt_sell('2026-04-01') == 0.0015 and A.stt_exercise('2026-03-31') == 0.00125 and A.stt_exercise('2026-04-01') == 0.0015
    c = A.order_costs('NIFTY', '2025-01-01', -1, 100000.0); assert c == pytest.approx(20 + 35 + 0.1 + 0.18 * (20 + 35 + 0.1) + 100)             # sell: brokerage + txn + SEBI + GST + 0.1 % STT, no stamp
    assert A.order_costs('NIFTY', '2025-01-01', 1, 100000.0) == pytest.approx(20 + 35 + 0.1 + 0.18 * (20 + 35 + 0.1) + 3)                           # buy: stamp duty instead of STT


def test_exercise_stt_only_on_long_itm_and_flatten_trades_the_open_positions():
    c = mini_cycle(); c['official_close'] = 130.0; a = A.account(c, FILLS(c), 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0, cost_mult=1)); long_itm = 10 * 30 * A.stt_exercise(c['d0'])
    base = A.account(dict(c, official_close=112.0), FILLS(c), 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0, cost_mult=1))
    assert a['costs'] - base['costs'] == pytest.approx(long_itm)                                                                                       # long 120 CE is 10 in the money
    f = A.account(mini_cycle(), FILLS(mini_cycle()), 'FLATTEN_1525', dict(slip_pct=0, slip_min=0, cost_mult=0))
    assert f['n_orders'] == 8 and not f['settle']


def test_margin_proxy_is_worst_case_expiry_loss_of_the_defined_risk_basket():
    c = mini_cycle(); assert A.max_loss(c, {'SCE': -30, 'SPE': -30, 'WCE': 30, 'WPE': 30}) == pytest.approx(30 * 20)                                       # wings 20 away, premiums ignored


def test_scenario_never_exposes_a_bar_before_it_completes_and_enters_at_the_bar_open():
    cyc = Cy.cycle_list(); r = cyc[(cyc.und == 'NIFTY') & (cyc.status == 'Complete')].iloc[3]; c = Cy.load(r.und, r.expiry)
    text = scen.make_text(c, dict(cut=None, reentry=None, stop=None), 'HOLD_SETTLE'); marks = [l.split('\t') for l in text.split('\n') if l.startswith('MARK')]; seeds = [l.split('\t') for l in text.split('\n') if l.startswith('LEG')]
    ticks = [int(l.split('\t')[1]) for l in text.split('\n') if l.startswith('TICK')]
    for _, ts, ins, pr in marks:
        lid = [k for k in c['legs'] if scen.iid(c, k) == ins][0]; day = c['d1'] if int(ts) < scen.epoch(c['d0'], '09:00') else c['d0']; fr = c['frames'][lid][0 if day == c['d1'] else 1]
        hm = '%02d:%02d' % divmod((int(ts) - scen.epoch(day, '00:00')) // 60 - 1, 60); row = fr[fr.hm == hm]; assert len(row) == 1 and scen.paise(row.close.iloc[0]) == int(pr)        # mark at t = close of the bar that started at t-60
    for s in seeds:
        lid = s[3]; e = c['legs'][lid]; assert int(s[8]) == scen.epoch(c['d1'], e['hm']) and int(s[7]) == scen.paise(e['open']) and e['hm'] >= '09:16' and min(ticks) > min(int(x[8]) for x in seeds)          # entry at the bar open; legs can enter at different minutes (non-atomic), ticks start after the first entry
    assert c['spot_0915'] is not None and c['K'] == C.STEP['NIFTY'] * math.floor(c['spot_0915'] / 50 + 0.5)                                                   # strike from the 09:15 close only


def test_split_has_an_embargo_and_no_cycle_straddles_the_boundary():
    cyc = Cy.cycle_list()
    assert not ((cyc.split == 'IS') & (cyc.d0 > '2025-11-17')).any() and not ((cyc.split == 'OOS') & (cyc.d1 <= '2025-11-17')).any()
    e = cyc[cyc.split == 'EMBARGO']; assert (e.d1 <= '2025-11-17').all() and (e.d0 > '2025-11-17').all()


def test_metrics_basics():
    df = pd.DataFrame(dict(d0=['2024-01-04', '2024-01-11', '2024-01-18'], d1=['2024-01-03', '2024-01-10', '2024-01-17'], net=[100.0, -50.0, 80.0], gross=[110.0, -40.0, 90.0], costs=[10.0] * 3, slippage=[0.0] * 3, n_orders=[4] * 3, peak_margin=[1000.0] * 3,
                         path=[[(1704331200, 100.0)], [(1704936000, -50.0)], [(1705540800, 80.0)]]))
    s = M.summarize(df, cap=10000.0); assert s['net_pnl'] == 130 and s['win_rate_pct'] == pytest.approx(200 / 3) and s['profit_factor'] == pytest.approx(180 / 50) and s['max_dd_rs'] == pytest.approx(-50)


def test_accounting_matches_the_engine_ledger_when_the_engine_closes_everything():
    """independent cross-check: where the capital stop closed every leg, the engine's own FIFO realised P&L must equal the accounting layer's gross P&L"""
    from bt import experiment as X
    f = os.path.join(X.ENG, 'HOLD_SETTLE', 'STOP_ONLY.pkl')
    if not os.path.exists(f): pytest.skip('engine results not generated')
    eng = X.load_engine('STOP_ONLY', 'HOLD_SETTLE'); n = 0
    for (und, exp), e in eng.items():
        s = dict(l.split('\t') for l in e['summary'].split('\n')[2:] if '\t' in l)
        if int(s['final_gross_units']) == 0:
            a = A.account(X._cyc(und, exp), e['fills'], 'HOLD_SETTLE', dict(slip_pct=0, slip_min=0, cost_mult=0)); assert abs(float(s['final_realized_pnl_paise']) / 100 - a['gross']) < 0.5; n += 1
    assert n > 10


def test_every_stored_engine_run_has_python_cpp_parity():
    from bt import experiment as X
    bad = 0; total = 0
    for root, _, fs in os.walk(X.ENG):
        for f in fs:
            import pickle
            for k, v in pickle.load(open(os.path.join(root, f), 'rb')).items():
                total += 1; bad += v['parity'] is not True
    if total == 0: pytest.skip('engine results not generated')
    assert bad == 0
