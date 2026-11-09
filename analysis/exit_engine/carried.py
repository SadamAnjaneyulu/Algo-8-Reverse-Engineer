"""Section 6 - expiry-day stop scope and carried-position rules.
A. D0 lot classes (closing convention 'cheap'; FIFO/LIFO sensitivity): fresh D0, re-entered D0 (contract bought back earlier in the cycle),
   carried (entered D-1, open at D0 start); contract-minutes with one vs several distinct entry prices.
B. Stop hazard above the D-1 stop level: P(unscheduled buy-back in the minute | px/cheapest entry >= 1.5) by class and by condition
   (lot age, entry premium, premium decay = running low / entry, TTE, adverse spot move, ATR, IV level, prev-session premium ratio).
   A conditional rule is accepted only if a depth-2/3 tree fitted on DEV separates stop vs no-stop on VAL (TEST untouched).
C. 4 % carry-forward SL interpretations, each tested independently (first D0 minute the condition holds, close-based = definite;
   evidence = share of carried lots bought back within 5 min of the trigger vs cycles/minutes without the trigger):
   a  carried premium >= 1.04 x its D-1 close value         b  whole short book value >= 1.04 x D-1 close value
   c  D0 loss on carried lots >= 4 % of capital (2 Cr; 1 Cr per index)
   d  D0 loss since open >= 4 % of the cycle P&L banked at D-1 close (|MTM at D-1 close|)
   e  spot move since D-1 close >= 4 % (and 0.4 %, 1 % as scale alternatives, labelled)     f  D0 MTM drawdown from D0 peak >= 4 % of premium collected
D. Cycle-stop level by day (is the D-1 stop the same as the D0 stop?).
python3 analysis/exit_engine/carried.py -> results/carried_position_results.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import precision_score, recall_score
from common import orders, markets, replay_book, cycle_stop_minute, minute_index, RES, SCHEDULED, LOT, split_of
import bookstate
STOPLIKE_EXCL = SCHEDULED + ('8 clock-B rebalance', '6 clock-based exit (clock B, no replacement)', '8b grid rebalance (A/:00 clock)')

def lot_classes():
    rows = []
    for conv in ('cheap', 'fifo', 'lifo'):
        Lt = replay_book(conv); sh = Lt[(Lt.sgn < 0)]
        d0 = sh[(sh.entry_day == 1) | sh.carried]
        cls = np.where(d0.carried, 'carried', np.where(d0.reentry, 're-entered D0', 'fresh D0'))
        for c, g in d0.groupby(cls):
            lab = g.exit_label.where(g.exit_mi >= g.d0_mi, 'closed D-1')
            r = dict(convention=conv, cls=c, lots=len(g))
            for L_, share in lab.value_counts(normalize=True).head(8).items(): r[f'exit: {L_}'] = share
            rows.append(r)
    return pd.DataFrame(rows)

def hazard_tables(CM, Lt):
    D = CM[(CM.day == 1)].copy()
    D['stop_exit'] = (D.closed > 0) & ~D.close_label.isin(STOPLIKE_EXCL)
    D['cls'] = np.where(D.n_carried == D.n_lots, 'carried only', np.where(D.n_carried > 0, 'mixed carried+fresh', np.where(D.n_reentry > 0, 're-entered only/partly', 'fresh only')))
    # premium decay: running low of the contract since the cheapest lot's entry / cheapest entry (from the minute lows)
    mk = markets(); lowr = []
    for (u, e), g in D.groupby(['und', 'expiry']):
        m = mk[(u, e)]
        for r in g.itertuples():
            kk = m['k2i'][(r.cp, r.strike)]; a = int(r.mi - r.age_cheap) + 1; lo = m['L'][kk, a:r.mi]
            lowr.append((r.Index, np.nanmin(lo) / r.e_cheap if len(lo) and np.isfinite(lo).any() else np.nan))
    lr = pd.Series(dict(lowr)); D['decay_low'] = lr.reindex(D.index)
    out = []
    A = D[D.r_cheap >= 1.5]
    for c, g in A.groupby('cls'):
        out.append(dict(part='B hazard (px/cheapest >= 1.5, D0)', condition='class', bin=c, n=len(g), hazard=g.stop_exit.mean()))
    D1 = CM[(CM.day == 0) & (CM.r_cheap >= 1.5)]
    D1s = (D1.closed > 0) & ~D1.close_label.isin(STOPLIKE_EXCL)
    out.append(dict(part='B hazard (px/cheapest >= 1.5)', condition='class', bin='D-1 (reference)', n=len(D1), hazard=D1s.mean()))
    conds = {'age_cheap': [0, 15, 30, 60, 120, 240, 2000], 'e_cheap': [0, 5, 10, 20, 40, 80, 1e9], 'decay_low': [0, 0.3, 0.5, 0.7, 0.9, 1.01, 10],
             'tte_min': [0, 60, 120, 180, 240, 300, 400], 'adv_mv15': [-1e9, -2, 0, 2, 4, 1e9], 'iv': [0, 0.1, 0.15, 0.2, 0.3, 10], 'r_prevclose': [0, 0.5, 1, 1.5, 2, 1e9]}
    for c, bins in conds.items():
        for cl in ('fresh only', 'carried only'):
            g = A[A.cls == cl]
            for b_, z in g.groupby(pd.cut(g[c], bins), observed=True):
                out.append(dict(part='B hazard (px/cheapest >= 1.5, D0)', condition=f'{c} [{cl}]', bin=str(b_), n=len(z), hazard=z.stop_exit.mean()))
    # D0 ratio curve by class
    for cl in ('fresh only', 'carried only', 'mixed carried+fresh'):
        g = D[D.cls == cl]
        for b_, z in g.groupby(pd.cut(g.r_cheap, [0, 1, 1.3, 1.45, 1.55, 1.7, 2, 3, 100]), observed=True):
            out.append(dict(part='B hazard by ratio (D0)', condition=f'r_cheap [{cl}]', bin=str(b_), n=len(z), hazard=z.stop_exit.mean()))
    # conditional rule search: depth-3 tree on DEV among D0 minutes with r_cheap >= 1.5, scored on VAL
    feats = ['age_cheap', 'age_oldest', 'e_cheap', 'decay_low', 'tte_min', 'adv_mv15', 'adv_mv5', 'iv', 'r_prevclose', 'r_cheap', 'r_avg', 'n_carried', 'n_reentry', 'n_lots', 'otm_atr']
    dev, val = A[A.split == 'DEV'], A[A.split == 'VAL']
    t = DecisionTreeClassifier(max_depth=3, min_samples_leaf=40, class_weight='balanced', random_state=0).fit(dev[feats].fillna(-999), dev.stop_exit)
    pv = t.predict(val[feats].fillna(-999)); pdv = t.predict(dev[feats].fillna(-999))
    out.append(dict(part='B conditional rule (tree, DEV fit)', condition='precision DEV / VAL', bin='', n=len(val), hazard=precision_score(dev.stop_exit, pdv, zero_division=0),
                    extra=precision_score(val.stop_exit, pv, zero_division=0)))
    out.append(dict(part='B conditional rule (tree, DEV fit)', condition='recall DEV / VAL', bin='', n=len(val), hazard=recall_score(dev.stop_exit, pdv), extra=recall_score(val.stop_exit, pv)))
    return pd.DataFrame(out), export_text(t, feature_names=feats, decimals=2), D

def carry_sl_tests():
    o = orders(); mk = markets(); Lt = replay_book('cheap'); cs = cycle_stop_minute(); rows = []
    for (u, e), m in mk.items():
        if not m['day'].any() or m['day'][0] == 1: continue
        d0 = int(m['day'].argmax()); n = len(m['grid']); cut = cs.get((u, e), n); lot = LOT[u]
        L_ = Lt[(Lt.und == u) & (Lt.expiry == e)]; car = L_[L_.carried & (L_.sgn < 0)]
        if not len(car): continue
        sh_open = L_[(L_.sgn < 0) & (L_.entry_mi < d0) & (L_.exit_mi >= d0)]
        Cf = m['Cf'].astype(float)
        def val_lots(lots_df, i):
            v = 0.0
            for r in lots_df.itertuples():
                p = Cf[m['k2i'][(r.cp, r.strike)], i]; v += (p if np.isfinite(p) else 0) * lot
            return v
        # carried lots still open at minute i (convention: cheap)
        car_v0 = val_lots(car, d0 - 1); book_v0 = val_lots(sh_open, d0 - 1)
        prem = (L_[L_.sgn < 0].entry_px * lot).sum()
        # MTM series from bookstate BM
        mt = BMx[(BMx.und == u) & (BMx.expiry == e)].set_index('mi').mtm
        mtm_d1close = mt.get(d0, np.nan)
        S = m['S']; s_close = S[d0 - 1]
        trig = {}
        peak = -1e18
        for i in range(d0, min(cut, n)):
            ca = car[(car.exit_mi >= i)]
            cv = val_lots(ca, i - 1) if len(ca) else np.nan
            cv0 = val_lots(ca, d0 - 1) if len(ca) else np.nan
            bv = val_lots(L_[(L_.sgn < 0) & (L_.entry_mi < i) & (L_.exit_mi >= i)], i - 1)
            loss_car = (cv - cv0) if len(ca) else np.nan
            mtm_i = mt.get(i, np.nan); peak = max(peak, mtm_i if np.isfinite(mtm_i) else peak)
            conds = {'a carried premium >= 1.04 x D-1 close': len(ca) and cv >= 1.04 * cv0,
                     'b short book value >= 1.04 x D-1 close value': bv >= 1.04 * book_v0,
                     'c carried loss >= 4% of 2 Cr': len(ca) and loss_car >= 0.04 * 2e7, 'c2 carried loss >= 4% of 1 Cr': len(ca) and loss_car >= 0.04 * 1e7,
                     'd D0 loss >= 4% of |MTM at D-1 close|': np.isfinite(mtm_i) and np.isfinite(mtm_d1close) and (mtm_d1close - mtm_i) >= 0.04 * abs(mtm_d1close),
                     'e spot move >= 4% since D-1 close': abs(S[i - 1] / s_close - 1) >= 0.04, 'e2 spot move >= 0.4% (scale alt.)': abs(S[i - 1] / s_close - 1) >= 0.004,
                     'e3 spot move >= 1% (scale alt.)': abs(S[i - 1] / s_close - 1) >= 0.01,
                     'f D0 drawdown from D0 peak >= 4% of premium collected': np.isfinite(mtm_i) and (peak - mtm_i) >= 0.04 * prem}
            for k, v in conds.items():
                if v and k not in trig: trig[k] = i
        car_exit = car.exit_mi.values; car_lab = car.exit_label.values
        for k in ['a carried premium >= 1.04 x D-1 close', 'b short book value >= 1.04 x D-1 close value', 'c carried loss >= 4% of 2 Cr', 'c2 carried loss >= 4% of 1 Cr',
                  'd D0 loss >= 4% of |MTM at D-1 close|', 'e spot move >= 4% since D-1 close', 'e2 spot move >= 0.4% (scale alt.)', 'e3 spot move >= 1% (scale alt.)',
                  'f D0 drawdown from D0 peak >= 4% of premium collected']:
            i = trig.get(k)
            if i is not None:
                open_at = (car_exit >= i).sum(); ex5 = ((car_exit >= i) & (car_exit <= i + 5) & ~np.isin(car_lab, ['expired/open'])).sum()
                # matched base rate: carried lots exited in any 5-min window on D0 before the trigger
                base = np.mean([((car_exit >= j) & (car_exit <= j + 5)).sum() / max((car_exit >= j).sum(), 1) for j in range(d0, i)]) if i > d0 else np.nan
            else:
                open_at = ex5 = 0; base = np.mean([((car_exit >= j) & (car_exit <= j + 5)).sum() / max((car_exit >= j).sum(), 1) for j in range(d0, min(cut, n) - 5)])
            rows.append(dict(und=u, expiry=e, split=split_of(e), interpretation=k, triggered=i is not None, trig_min_after_open=(i - d0) if i is not None else np.nan,
                             carried_open_at_trigger=open_at, carried_exited_within5=ex5, share_exited_within5=ex5 / open_at if open_at else np.nan, base_5min_exit_share=base,
                             cycle_stopped=(u, e) in cs))
    return pd.DataFrame(rows)

def stop_by_day():
    """close-based book MTM (marks = close of the minute before the first s_ order) at every cycle stop, by day; BM is cut at the stop minute"""
    o = orders(); s = o[o.tp == 's_'].groupby(['und', 'expiry']).agg(t=('t_dec', 'min'), dte=('dte', 'first'))
    mk = markets(); Lt = replay_book('cheap'); rows = []
    for (u, e), r in s.iterrows():
        m = mk[(u, e)]; i = minute_index(m['grid'], r.t); lot = LOT[u]; Lc = Lt[(Lt.und == u) & (Lt.expiry == e)]
        v = 0.0
        for x in Lc.itertuples():
            if x.entry_mi >= i: continue
            if x.exit_mi < i: v += x.sgn * (x.exit_px - x.entry_px) * lot
            else:
                p = float(m['Cf'][m['k2i'][(x.cp, x.strike)], i - 1]); v += x.sgn * ((p if np.isfinite(p) else x.entry_px) - x.entry_px) * lot
        rows.append(dict(und=u, expiry=e, dte=r.dte, mtm_prev_minute_close=v, t=r.t))
    return pd.DataFrame(rows)

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
    CM, BMx = bookstate.load(); Lt = replay_book('cheap')
    if '--only-d' in sys.argv:
        SD = stop_by_day(); print(SD.groupby('dte').mtm_prev_minute_close.describe().round(0).to_string())
        p = os.path.join(RES, 'carried_position_results.csv'); old = pd.read_csv(p); old = old[old.section != 'D stop by day']
        pd.concat([old, SD.assign(section='D stop by day')], ignore_index=True).to_csv(p, index=False); sys.exit(0)
    A = lot_classes(); print('=== A. D0 lot classes and their exits ==='); print(A.round(3).fillna('').to_string(index=False))
    H, tree, D = hazard_tables(CM, Lt); print('\n=== B. stop hazards ==='); print(H.round(3).to_string(index=False)); print(tree)
    # multiple entry prices
    D['multi_px'] = D.n_lots >= 2
    mp = D[D.r_cheap >= 1.5].groupby('multi_px').apply(lambda g: pd.Series(dict(n=len(g), hazard=g.stop_exit.mean())))
    print('\nmultiple entries (>=2 lots) vs single lot, D0, r>=1.5:\n', mp)
    T = carry_sl_tests()
    agg = T.groupby(['interpretation', 'split']).agg(cycles=('expiry', 'size'), triggered=('triggered', 'sum'), med_trig_min=('trig_min_after_open', 'median'),
                                                     share_exited_within5=('share_exited_within5', 'mean'), base_5min=('base_5min_exit_share', 'mean')).reset_index()
    print('\n=== C. 4% carry-forward SL interpretations ==='); print(agg.round(3).to_string(index=False))
    SD = stop_by_day(); print('\n=== D. cycle-stop MTM by day ==='); print(SD.groupby('dte').mtm_prev_minute_close.describe().round(0).to_string())
    out = pd.concat([A.assign(section='A lot classes'), H.assign(section='B hazards'), mp.reset_index().assign(section='B multi-entry'),
                     agg.assign(section='C carry SL'), SD.assign(section='D stop by day')], ignore_index=True)
    out.to_csv(os.path.join(RES, 'carried_position_results.csv'), index=False)
    T.to_csv(os.path.join(RES, 'carried_carry_sl_by_cycle.csv'), index=False)
