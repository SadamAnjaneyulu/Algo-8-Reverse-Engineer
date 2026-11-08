"""Exit taxonomy. Primary label by explicit precedence + independent boolean flags (overlaps stay visible). Unknown is preserved.
Thresholds are stated constants (not fitted here); trailing is assigned only by trailing.py if its tests support it.
python3 analysis/exit_engine/taxonomy.py -> analysis/_cache/exit_taxonomy.pkl"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from load import load_tagged
C = os.path.join(os.path.dirname(HERE), '_cache')
STOP_R = 1.45          # lower edge of the validated ~1.55x leg stop (quote lag tolerance)
SALVAGE_PX, SALVAGE_R = 1.0, 0.05
EPISODE_GAP_S = 10; ROLL_WIN_S = 60
PLATFORM_IDS = {'152432', '2.18811E+15'}

def clock_window(t):
    ph = ((t - t.normalize() - pd.Timedelta('09:15:00')).total_seconds()) % 900
    if ph >= 13 * 60 + 45 or ph < 15: return 'B'
    if 55 <= ph < 180: return 'A'
    if ph < 55: return 'A0'
    return None

def classify(X, sells):
    X = X.sort_values(['und', 'expiry', 't_dec']).copy()
    X['t_dec'] = pd.to_datetime(X.t_dec)
    gap = X.groupby(['und', 'expiry']).t_dec.diff().dt.total_seconds().fillna(1e9)
    X['episode'] = (gap > EPISODE_GAP_S).cumsum()
    ep = X[X.closing_short].groupby('episode').agg(n_contracts=('strike', lambda s: len(set(zip(X.loc[s.index, 'cp'], s)))),
                                                   sides=('cp', lambda s: ''.join(sorted(set(s)))))
    X = X.join(ep, on='episode')
    X['clock'] = [clock_window(t) for t in X.t_dec]
    X['hhmm'] = X.t_dec.dt.strftime('%H:%M')
    first_stop = X[X.tp == 's_'].groupby(['und', 'expiry']).t_dec.min()
    X['after_cycle_stop'] = [pd.notna(first_stop.get((u, e))) and t >= first_stop[(u, e)] for u, e, t in zip(X.und, X.expiry, X.t_dec)]
    # same-side body sale within +-ROLL_WIN_S
    S = sells.set_index(['und', 'expiry', 'cp']).sort_index()
    def roll(u, e, cp, t):
        try: ts = S.loc[(u, e, cp)].t
        except KeyError: return False
        ts = pd.to_datetime(np.atleast_1d(ts.values)); return bool(np.any(np.abs((ts - t).total_seconds()) <= ROLL_WIN_S))
    X['flag_roll'] = [roll(u, e, cp, t) for u, e, cp, t in zip(X.und, X.expiry, X.cp, X.t_dec)]
    X['flag_platform'] = X.algoid.isin(PLATFORM_IDS) | (X.tp == 'm_')
    X['flag_stopmodule'] = X.tp == 's_'
    X['flag_salvage'] = (X.dte == 0) & ((X.L <= SALVAGE_PX) | (X.r_avg <= SALVAGE_R))
    X['flag_final_flatten'] = (X.dte == 0) & (X.hhmm >= '15:10')
    X['flag_lot_stop'] = X.closing_short & (X.r_cheap >= STOP_R)
    X['flag_first_passage'] = X.flag_lot_stop & ~(X.run_max_since_cheap >= 1.02 * X.L)          # price had not traded above this quote earlier
    X['flag_partial'] = X.remaining_after > 0
    X['flag_side_multi'] = X.closing_short & (X.n_contracts >= 2) & (X.sides.str.len() == 2).eq(False)
    X['flag_basket'] = X.closing_short & (X.n_contracts >= 2) & (X.sides.str.len() == 2)
    shc = X[X.closing_short].groupby(['und', 'expiry', 'cp']).t_dec.apply(lambda z: pd.to_datetime(z.values))
    X['flag_short_close_near'] = [((u, e, cp) in shc.index) and bool(np.any(np.abs((shc[(u, e, cp)] - t).total_seconds()) <= ROLL_WIN_S)) for u, e, cp, t in zip(X.und, X.expiry, X.cp, X.t_dec)]
    X['flag_cross_module'] = (X.closing_short & (X.tp == 'h_')) | (~X.closing_short & (X.tp == 'num'))
    lab = []
    for r in X.itertuples():
        if r.flag_platform: l = '10 manual / platform risk engine'
        elif r.flag_stopmodule or r.after_cycle_stop: l = '5 cycle stop & liquidation'
        elif r.closing_short:
            if r.flag_salvage: l = '7 expiry-day salvage'
            elif r.flag_final_flatten: l = '6 clock-based exit (final flatten)'
            elif r.flag_lot_stop: l = '1 individual lot stop-loss'
            elif r.clock == 'B' and r.flag_roll: l = '8 clock-B rebalance'
            elif r.clock in ('A', 'B', 'A0') and r.flag_roll: l = '8b grid rebalance (A/:00 clock)'
            elif r.clock == 'B': l = '6 clock-based exit (clock B, no replacement)'
            elif r.flag_basket: l = '4 basket-level reduction'
            elif r.flag_side_multi: l = '3 side-level reduction'
            elif r.flag_partial: l = '2 same-contract partial buy-back'
            else: l = '11 unexplained'
        else:   # closing longs (wings / lump / seed wings)
            if r.flag_salvage: l = 'L-salvage'
            elif r.flag_final_flatten: l = 'L-final flatten'
            elif r.tp == 'v_': l = 'L-lump disposal'
            elif r.flag_short_close_near: l = 'L-hedge release (same-side short closed within 60s)'
            else: l = 'L-unexplained'
        lab.append(l)
    X['label'] = lab
    return X

if __name__ == '__main__':
    X = pd.read_pickle(os.path.join(C, 'exit_ledger.pkl')); X['lot'] = np.where(X.und == 'NIFTY', 65, 20)
    d = load_tagged(); sells = d[(d.tp == 'num') & (d.side == 'Sell') & (d.px_fill >= 5)].groupby('oid').agg(t=('t', 'min'), und=('und', 'first'), expiry=('expiry', 'first'), cp=('cp', 'first')).reset_index()
    X = classify(X, sells); X.to_pickle(os.path.join(C, 'exit_taxonomy.pkl'))
    pd.set_option('display.width', 220)
    sh = X[X.closing_short].copy(); sh['pnl_vs_avg'] = (sh.e_avg - sh.vwap) * sh.lots_closed * sh.lot
    t = sh.groupby('label').agg(orders=('oid', 'size'), lots=('lots_closed', 'sum'), D1_share=('dte', lambda x: (x >= 1).mean()),
                                median_r_avg=('r_avg', 'median'), realised_vs_avg_entry_Rs_lakh=('pnl_vs_avg', lambda x: x.sum() / 1e5))
    t['lot_share'] = t.lots / t.lots.sum()
    print('=== SHORT-side exits (buy-backs) ==='); print(t.round(3).to_string())
    print('\nflags overlap on lot-stop exits:', sh[sh.label == '1 individual lot stop-loss'][['flag_first_passage', 'flag_partial', 'flag_roll', 'flag_basket', 'flag_side_multi']].mean().round(3).to_dict())
    print('cross-module netting (shorts closed by h_):', int(sh.flag_cross_module.sum()))
    lg = X[~X.closing_short]
    print('\n=== LONG-side closes (wings / lump) ==='); print(lg.groupby('label').agg(orders=('oid', 'size'), lots=('lots_closed', 'sum')).to_string())
