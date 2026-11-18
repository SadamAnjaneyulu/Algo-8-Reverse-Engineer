"""Clock-B (D0 :14/:29/:44/:59 from 09:29, decision window -15 s..+15 s) - contract selection and replacement.
1. Tick-level: at which clock-B ticks does the controller buy back anything?  (book state at the tick; DEV fit, VAL eval)
2. Which contract (candidate selection among open shorts of the side acted on; criteria hit@1 vs random; conditional logit)
3. How many lots (fraction of the contract / of the side)
4. Replacement sale: strike / delta of the contract sold within +-60 s vs the one bought back
python3 analysis/exit_engine/clock_b.py -> results/clock_b_selection_results.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from common import orders, markets, minute_index, cycle_stop_minute, RES, split_of
import bookstate
from side_basket import candidate_sets, selection, auc_safe, lgb_fit, FAMILIES
STEP = {'NIFTY': 50, 'SENSEX': 100}

def tick_of(t):
    """clock-B tick (the :14/:29/:44/:59 minute) for a decision time inside the taxonomy window [boundary-75 s, boundary+15 s], else NaT"""
    t = pd.Timestamp(t); base = t.normalize() + pd.Timedelta('09:15:00'); s = (t - base).total_seconds()
    q = np.floor((s + 75) / 900); tick = base + pd.Timedelta(seconds=q * 900 - 60)       # :14/:29/:44/:59 minute start
    off = s - q * 900                                                                  # seconds relative to the quarter boundary
    return tick if (-75 <= off <= 15 and tick >= t.normalize() + pd.Timedelta('09:29:00')) else pd.NaT

if __name__ == '__main__':
    pd.set_option('display.width', 250)
    CM, BM = bookstate.load(); o = orders(); mk = markets(); cs = cycle_stop_minute()
    o = o.copy(); o['t_dec'] = pd.to_datetime(o.t_dec)
    b = o[(o.closing_short == True) & (o.dte == 0) & ~o.label.isin(['5 cycle stop & liquidation', '10 manual / platform risk engine'])].copy()
    b['tick'] = [tick_of(t) for t in b.t_dec]; b = b[b.tick.notna()]
    b['tick_mi'] = [minute_index(mk[(u, e)]['grid'], t) for u, e, t in zip(b.und, b.expiry, b.tick)]
    b['mi'] = b.groupby(['und', 'expiry', 'tick']).tick_mi.transform('min') - 1       # state at the start of the :28 minute (before the earliest window order)
    sells = o[(o.side == 'Sell') & (o.label == 'open') & (o.dte == 0)]
    rows = []
    # 1. tick-level action model
    T = BM[BM.clockB & (BM.day == 1)][['und', 'expiry', 'mi']].copy(); T['mi'] = T.mi - 1   # causal state one minute before the tick minute
    T = T.merge(BM, on=['und', 'expiry', 'mi'], how='inner'); T = T[T.n_contracts >= 1]
    acted = set(zip(b.und, b.expiry, b.mi))
    T['y'] = [(u, e, mi) in acted for u, e, mi in zip(T.und, T.expiry, T.mi)]
    feats = [c for f in FAMILIES.values() for c in f if c in T.columns and c not in ('clockB',)]
    dev, val = T[T.split == 'DEV'], T[T.split == 'VAL']
    rows.append(dict(part='tick action', metric='ticks DEV/VAL/TEST', value=f'{len(dev)}/{len(val)}/{(T.split == "TEST").sum()}', note=f'action rate DEV {dev.y.mean():.3f} VAL {val.y.mean():.3f}'))
    for c in feats:
        rows.append(dict(part='tick action', metric=f'univariate AUC {c}', value=auc_safe(dev.y, dev[c]), note=f'VAL {auc_safe(val.y, val[c]):.3f}'))
    m = lgb_fit(dev[feats].astype(float), dev.y); pv = m.predict_proba(val[feats].astype(float))[:, 1]
    rows.append(dict(part='tick action', metric='LightGBM VAL AUC', value=roc_auc_score(val.y, pv) if val.y.nunique() > 1 else np.nan, note=''))
    tr = DecisionTreeClassifier(max_depth=3, min_samples_leaf=30, class_weight='balanced', random_state=0).fit(dev[feats].fillna(-999), dev.y)
    pr = tr.predict(val[feats].fillna(-999))
    rows.append(dict(part='tick action', metric='depth-3 tree VAL precision / recall', value=precision_score(val.y, pr, zero_division=0), note=f'recall {recall_score(val.y, pr):.3f}'))
    tree_txt = export_text(tr, feature_names=feats, decimals=2)
    # 2. selection
    E = b.groupby(['und', 'expiry', 'mi', 'cp']).agg(contracts=('strike', lambda s: ';'.join(f'{cp}{int(k)}' for cp, k in zip(b.loc[s.index, 'cp'], s))),
                                                     lots=('lots', 'sum'), labels=('label', lambda s: '|'.join(sorted(set(s))))).reset_index()
    E['sides'] = E.cp; E['split'] = E.expiry.map(split_of); E['ep'] = np.arange(len(E))
    E['contracts'] = E.contracts.apply(lambda s: ';'.join(sorted(set(s.split(';')))))
    G = candidate_sets(CM, E, lambda z: z)
    sel = pd.DataFrame(selection(G, 'clock-B buy-back: which contract of the side'))
    # 3. quantity
    q = []
    key = CM.set_index(['und', 'expiry', 'mi', 'cp', 'strike']).sort_index()
    for r in b.itertuples():
        try: z = key.loc[(r.und, r.expiry, r.mi, r.cp, r.strike)]
        except KeyError: continue
        z = z.iloc[0] if isinstance(z, pd.DataFrame) else z
        q.append(dict(split=split_of(r.expiry), closed=r.lots, open=z.n_lots, frac=min(r.lots / z.n_lots, 1), label=r.label, r_avg=z.r_avg, delta=z.delta))
    Q = pd.DataFrame(q); Qn = Q[Q.split != 'TEST']
    for lab, g in Qn.groupby('label'):
        rows.append(dict(part='quantity', metric=f'{lab}: full-contract share / 1-lot share / median frac', value=(g.frac >= 1).mean(), note=f'{(g.closed == 1).mean():.3f} / {g.frac.median():.3f} (n={len(g)})'))
    # 4. replacement sales: delta & strike of the contract sold within +-60 s on the same side
    rep = []
    for r in b[b.label == '8 clock-B rebalance'].itertuples():
        s = sells[(sells.und == r.und) & (sells.expiry == r.expiry) & (sells.cp == r.cp) & ((pd.to_datetime(sells.t_dec) - r.t_dec).dt.total_seconds().abs() <= 60)]
        if not len(s): continue
        mm = mk[(r.und, r.expiry)]
        if 'greeks' not in mm: mm['greeks'] = bookstate.greeks(mm)
        DEL = mm['greeks'][1]; pm = max(r.mi - 1, 0); S = mm['S'][pm]; atm = round(S / STEP[r.und]) * STEP[r.und]
        for z in s.itertuples():
            if (z.cp, z.strike) not in mm['k2i']: continue
            rep.append(dict(split=split_of(r.expiry), und=r.und, bb_strike=r.strike, sold_strike=z.strike, steps=(z.strike - r.strike) / STEP[r.und] * (1 if r.cp == 'CE' else -1),
                            bb_delta=abs(DEL[mm['k2i'][(r.cp, r.strike)], pm]) if (r.cp, r.strike) in mm['k2i'] else np.nan, sold_delta=abs(DEL[mm['k2i'][(z.cp, z.strike)], pm]),
                            sold_atm_steps=(z.strike - atm) / STEP[r.und] * (1 if r.cp == 'CE' else -1), bb_lots=r.lots, sold_lots=z.lots, sold_after_s=(pd.Timestamp(z.t_dec) - r.t_dec).total_seconds()))
    RP = pd.DataFrame(rep); RPn = RP[RP.split != 'TEST']
    if len(RPn):
        rows += [dict(part='replacement', metric='pairs (non-TEST)', value=len(RPn), note=''),
                 dict(part='replacement', metric='sold strike further OTM than bought-back (share)', value=(RPn.steps > 0).mean(), note=f'same strike {(RPn.steps == 0).mean():.3f}; closer {(RPn.steps < 0).mean():.3f}'),
                 dict(part='replacement', metric='median |delta| bought back / sold', value=RPn.bb_delta.median(), note=f'{RPn.sold_delta.median():.3f}'),
                 dict(part='replacement', metric='sold |delta| IQR', value=RPn.sold_delta.quantile(.25), note=f'{RPn.sold_delta.quantile(.75):.3f}'),
                 dict(part='replacement', metric='sold strike vs ATM (steps OTM) median / IQR', value=RPn.sold_atm_steps.median(), note=f'{RPn.sold_atm_steps.quantile(.25)}..{RPn.sold_atm_steps.quantile(.75)}'),
                 dict(part='replacement', metric='sold lots == bought-back lots (share)', value=(RPn.sold_lots == RPn.bb_lots).mean(), note=f'median sold {RPn.sold_lots.median()} vs bb {RPn.bb_lots.median()}'),
                 dict(part='replacement', metric='sale after buy-back (s) median', value=RPn.sold_after_s.median(), note=f'IQR {RPn.sold_after_s.quantile(.25)}..{RPn.sold_after_s.quantile(.75)}')]
    R = pd.DataFrame(rows)
    out = pd.concat([R, sel.rename(columns={'criterion': 'metric', 'hit_at_1': 'value'}).assign(part='selection')], ignore_index=True)
    out.to_csv(os.path.join(RES, 'clock_b_selection_results.csv'), index=False)
    print(R.to_string(index=False)); print('\n--- tick-action tree (DEV) ---\n' + tree_txt)
    print(sel.round(3).to_string(index=False))
