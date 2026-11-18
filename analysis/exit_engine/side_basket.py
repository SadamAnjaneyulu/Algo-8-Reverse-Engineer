"""Section 5 - side-level and basket-level management.
A. Episode dataset: short buy-backs before the cycle stop grouped into decision episodes (gap <= 10 s); non-exclusive flags
   multi_strike_one_side, both_sides, partial_one_contract, rebalance_with_replacement (same-side sale within +-60 s),
   same_contract_buy_sell (same contract sold within +-60 s).  'scheduled' episodes (all orders salvage / final flatten / platform) are kept but flagged.
B. Trigger tests on the side-minute panel (one row per minute x side with open shorts): target = an unscheduled episode that closes
   >=2 contracts of that side (side-level) or closes both sides (basket, book-minute).  Univariate AUC (DEV, VAL), feature-family
   LightGBM fitted on DEV and scored on VAL, depth-3 tree rules fitted on DEV, precision/recall on VAL.  TEST is not touched here.
C. Candidate selection: at every unscheduled episode with >=2 open candidate contracts, which contracts are closed?
   Deterministic criteria (hit@1 = the criterion's top candidate is closed) vs the random baseline, and a conditional logit fitted on DEV.
D. Quantity: share of a contract's lots closed, share of side inventory closed, closed-lot counts.
python3 analysis/exit_engine/side_basket.py -> results/side_basket_exit_results.csv (+ side_basket_episodes.csv, side_basket_selection.csv)"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score
from sklearn.tree import DecisionTreeClassifier, export_text
import lightgbm as lgb
from common import orders, cycle_stop_minute, markets, minute_index, RES, SCHEDULED, split_of
import bookstate
GAP_S, WIN_S = 10, 60

def episodes():
    o = orders(); cs = cycle_stop_minute(); mk = markets()
    o = o.copy(); o['t_dec'] = pd.to_datetime(o.t_dec)
    sells = o[(o.side == 'Sell') & (o.label == 'open')]
    b = o[(o.closing_short == True) & ~o.label.isin(['5 cycle stop & liquidation'])].sort_values(['und', 'expiry', 't_dec']).copy()
    b['mi'] = [minute_index(mk[(u, e)]['grid'], t) for u, e, t in zip(b.und, b.expiry, b.t_dec_lo)]
    b = b[[mi < cs.get((u, e), 10 ** 9) for u, e, mi in zip(b.und, b.expiry, b.mi)]]
    gap = b.groupby(['und', 'expiry']).t_dec.diff().dt.total_seconds().fillna(1e9)
    b['ep'] = (gap > GAP_S).cumsum()
    rows = []
    S = {k: g.t_dec.values for k, g in sells.groupby(['und', 'expiry', 'cp'])}
    SK = {k: g.t_dec.values for k, g in sells.groupby(['und', 'expiry', 'cp', 'strike'])}
    for ep, g in b.groupby('ep'):
        u, e = g.und.iloc[0], g.expiry.iloc[0]; t0 = g.t_dec.min()
        ks = sorted(set(zip(g.cp, g.strike))); sides = ''.join(sorted(set(g.cp)))
        part = g.groupby(['cp', 'strike']).agg(closed=('lots', 'sum'), open_before=('oid', 'size'))
        def near(arr, t, lo=-WIN_S, hi=WIN_S):
            if arr is None or not len(arr): return False
            d = (pd.to_datetime(arr) - t).total_seconds(); return bool(np.any((d >= lo) & (d <= hi)))
        repl = any(near(S.get((u, e, cp)), t0) for cp in set(g.cp))
        same = any(near(SK.get((u, e, cp, k)), t0) for cp, k in ks)
        sched = g.label.isin(SCHEDULED).all()
        rows.append(dict(ep=ep, und=u, expiry=e, split=split_of(e), t=t0, mi=g.mi.min(), day=int(g.dte.iloc[0] == 0), n_contracts=len(ks), sides=sides, lots=int(g.lots.sum()),
                         labels='|'.join(sorted(set(g.label))), scheduled=bool(sched), clock=g.clock.iloc[0],
                         multi_strike_one_side=(len(ks) >= 2) and sides in ('CE', 'PE'), both_sides=sides == 'CEPE',
                         single_contract=len(ks) == 1, rebalance_with_replacement=repl, same_contract_buy_sell=same,
                         contracts=';'.join(f'{cp}{int(k)}' for cp, k in ks)))
    E = pd.DataFrame(rows)
    return E, b

def side_panel(CM, BM):
    """minute x side rows: side features + adverse spot moves signed for that side"""
    g = CM.groupby(['und', 'expiry', 'mi', 'cp']).agg(n_contracts_side=('strike', 'size'), lots_side=('n_lots', 'sum'), up_side=('upnl', 'sum'),
                                                      max_r_avg=('r_avg', 'max'), mean_r_avg=('r_avg', 'mean'), max_r_cheap=('r_cheap', 'max'),
                                                      dexp_side=('dexp', 'sum'), gexp_side=('gexp', 'sum'), vexp_side=('vexp', 'sum'),
                                                      min_otm_atr=('otm_atr', 'min'), adv_mv5=('adv_mv5', 'first'), adv_mv15=('adv_mv15', 'first'),
                                                      adv_mv30=('adv_mv30', 'first'), adv_d0open=('adv_d0open', 'first'), adv_prevclose=('adv_prevclose', 'first'),
                                                      min_since_sale_k=('since_sale_k', 'min'), min_since_bb_k=('since_bb_k', 'min'),
                                                      max_age_oldest=('age_oldest', 'max'), carried_lots=('n_carried', 'sum'), closed_contracts=('closed', lambda x: (x > 0).sum())).reset_index()
    P = g.merge(BM, on=['und', 'expiry', 'mi'], how='left', suffixes=('', '_book'))
    return P

FAMILIES = {
    'spot_atr': ['adv_mv5', 'adv_mv15', 'adv_mv30', 'adv_d0open', 'adv_prevclose', 'mv1', 'mv5', 'mv15', 'mv30', 'atr', 'rv1'],
    'side_pnl': ['up_side', 'max_r_avg', 'mean_r_avg', 'max_r_cheap'],
    'basket_pnl': ['up_basket', 'up_ce', 'up_pe'],
    'cycle_dd': ['mtm', 'mtm_dd', 'mtm_peak'],
    'greeks': ['net_delta', 'net_gamma', 'net_vega', 'net_theta', 'dexp_side', 'gexp_side', 'vexp_side'],
    'inventory': ['n_contracts_side', 'lots_side', 'n_contracts', 'lots_tot', 'max_share', 'imbalance', 'carried_lots', 'min_otm_atr'],
    'since_trades': ['since_sale', 'since_bb', 'min_since_sale_k', 'min_since_bb_k', 'max_age_oldest'],
    'clock': ['clockB', 'gridA', 'grid00', 'hhmm', 'day', 'tte_min']}

def auc_safe(y, s):
    s = np.asarray(s, float); ok = np.isfinite(s)
    if ok.sum() < 50 or len(set(np.asarray(y)[ok])) < 2: return np.nan
    a = roc_auc_score(np.asarray(y)[ok], s[ok]); return max(a, 1 - a)

def lgb_fit(X, y, seed=0):
    m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, random_state=seed)
    return m.fit(X, y)

def trigger_tests(P, target, label):
    out = []
    dev, val = P[P.split == 'DEV'], P[P.split == 'VAL']
    if dev[target].sum() < 20 or val[target].sum() < 5: return out, None
    for fam, cols in FAMILIES.items():
        for c in cols:
            if c not in P: continue
            out.append(dict(event=label, test='univariate AUC (max(a,1-a))', feature=c, family=fam, dev=auc_safe(dev[target], dev[c]), val=auc_safe(val[target], val[c]),
                            n_dev_events=int(dev[target].sum()), n_val_events=int(val[target].sum())))
    allc = [c for cols in FAMILIES.values() for c in cols if c in P]
    base = FAMILIES['clock'] + FAMILIES['inventory']
    base = [c for c in base if c in P]
    m0 = lgb_fit(dev[base].astype(float), dev[target]); a0 = roc_auc_score(val[target], m0.predict_proba(val[base].astype(float))[:, 1])
    out.append(dict(event=label, test='LightGBM base (clock+inventory) VAL AUC', feature='base', family='base', dev=np.nan, val=a0))
    for fam, cols in FAMILIES.items():
        if fam in ('clock', 'inventory'): continue
        cc = base + [c for c in cols if c in P]
        mm = lgb_fit(dev[cc].astype(float), dev[target]); pv = mm.predict_proba(val[cc].astype(float))[:, 1]
        out.append(dict(event=label, test='LightGBM base+family VAL AUC gain', feature=fam, family=fam, dev=np.nan, val=roc_auc_score(val[target], pv) - a0,
                        val_ap=average_precision_score(val[target], pv)))
    mm = lgb_fit(dev[allc].astype(float), dev[target]); pv = mm.predict_proba(val[allc].astype(float))[:, 1]
    out.append(dict(event=label, test='LightGBM all families VAL', feature='all', family='all', dev=np.nan, val=roc_auc_score(val[target], pv), val_ap=average_precision_score(val[target], pv),
                    base_rate_val=val[target].mean()))
    imp = pd.Series(mm.booster_.feature_importance('gain'), index=allc).sort_values(ascending=False)
    for c, v in imp.head(8).items(): out.append(dict(event=label, test='LightGBM all: top gain features', feature=c, family=[f for f, cs in FAMILIES.items() if c in cs][0], dev=v / imp.sum(), val=np.nan))
    # interpretable depth-3 tree, class-balanced, fitted on DEV only
    t = DecisionTreeClassifier(max_depth=3, min_samples_leaf=200, class_weight='balanced', random_state=0).fit(dev[allc].fillna(-999).astype(float), dev[target])
    pr = t.predict(val[allc].fillna(-999).astype(float))
    out.append(dict(event=label, test='depth-3 tree (DEV fit) VAL precision', feature='tree', family='tree', dev=precision_score(dev[target], t.predict(dev[allc].fillna(-999).astype(float)), zero_division=0),
                    val=precision_score(val[target], pr, zero_division=0)))
    out.append(dict(event=label, test='depth-3 tree (DEV fit) VAL recall', feature='tree', family='tree', dev=recall_score(dev[target], t.predict(dev[allc].fillna(-999).astype(float))),
                    val=recall_score(val[target], pr)))
    return out, export_text(t, feature_names=allc, decimals=2)

CRITERIA = {  # name: (column, 'max' or 'min')
    'most adverse ratio (max px/avg entry)': ('r_avg', 'max'), 'max px/cheapest entry': ('r_cheap', 'max'), 'largest Rs loss (min upnl)': ('upnl', 'min'),
    'largest Rs profit (max upnl)': ('upnl', 'max'), 'highest premium': ('px', 'max'), 'lowest premium': ('px', 'min'), 'largest |delta|': ('delta_abs', 'max'),
    'largest delta exposure (|delta| x lots)': ('dexp', 'max'), 'largest gamma exposure': ('gexp', 'max'), 'largest vega exposure': ('vexp', 'max'),
    'nearest ATM (min |K-S|)': ('abs_otm', 'min'), 'farthest OTM': ('otm_pts', 'max'), 'most lots': ('n_lots', 'max'), 'fewest lots': ('n_lots', 'min'),
    'oldest position': ('age_oldest', 'max'), 'newest lot': ('age_newest', 'min'), 'cheapest entry': ('e_cheap', 'min'), 'most expensive avg entry': ('e_avg', 'max'),
    'most recent sale on contract': ('since_sale_k', 'min'), 'timer-phase match (age of newest lot mod 15 min ~ 0)': ('phase_off', 'min')}
CL_FEATS = ['r_avg', 'upnl', 'px', 'delta_abs', 'dexp', 'gexp', 'vexp', 'abs_otm', 'n_lots', 'age_oldest', 'age_newest', 'e_avg', 'since_sale_k', 'phase_off', 'n_carried']

def candidate_sets(CM, E, filt):
    """filt(E) -> episodes; candidates = open shorts at the episode minute on the episode's side(s)"""
    ee = filt(E); key = CM.set_index(['und', 'expiry', 'mi']).sort_index()
    out = []
    for r in ee.itertuples():
        try: c = key.loc[(r.und, r.expiry, r.mi)].reset_index()
        except KeyError: continue
        c = c[c.cp.isin(['CE', 'PE'] if r.sides == 'CEPE' else [r.sides])]
        if len(c) < 2: continue
        chosen = set(r.contracts.split(';'))
        c = c.assign(chosen=[f'{cp}{int(k)}' in chosen for cp, k in zip(c.cp, c.strike)], ep=r.ep, split=r.split, n_chosen=len(chosen))
        if not c.chosen.any(): continue
        out.append(c)
    if not out: return pd.DataFrame()
    G = pd.concat(out, ignore_index=True)
    G['delta_abs'] = G.delta.abs(); G['abs_otm'] = G.otm_pts.abs()
    G['phase_off'] = np.minimum(G.age_newest % 15, 15 - G.age_newest % 15)
    return G

def selection(G, label):
    rows = []
    if not len(G): return rows
    for sp in ('DEV', 'VAL', 'ALL-not-TEST'):
        g = G[G.split == sp] if sp != 'ALL-not-TEST' else G[G.split != 'TEST']
        if not len(g): continue
        eps = g.groupby('ep'); base = eps.apply(lambda z: z.chosen.sum() / len(z)).mean()
        rows.append(dict(event=label, split=sp, criterion='random baseline (E[chosen/candidates])', n_episodes=eps.ngroups, hit_at_1=base, exact_set=np.nan,
                         mean_candidates=eps.size().mean(), mean_chosen=eps.chosen.sum().mean()))
        for name, (col, how) in CRITERIA.items():
            hits, exact = [], []
            for _, z in eps:
                z = z[np.isfinite(z[col].astype(float))]
                if not len(z): continue
                zs = z.sort_values(col, ascending=(how == 'min'))
                hits.append(bool(zs.chosen.iloc[0])); k_ = int(z.chosen.sum()); exact.append(set(zs.index[:k_]) == set(z.index[z.chosen]))
            rows.append(dict(event=label, split=sp, criterion=name, n_episodes=len(hits), hit_at_1=np.mean(hits) if hits else np.nan, exact_set=np.mean(exact) if exact else np.nan))
    # conditional logit fitted on DEV, top-1 on VAL
    dev, val = G[G.split == 'DEV'], G[G.split == 'VAL']
    if dev.ep.nunique() >= 30 and val.ep.nunique() >= 10:
        mu = dev[CL_FEATS].astype(float).mean(); sd = dev[CL_FEATS].astype(float).std().replace(0, 1)
        def prep(D): return ((D[CL_FEATS].astype(float) - mu) / sd).fillna(0).values, D.chosen.values.astype(float), D.ep.values
        Xd, yd, gd = prep(dev); Xv, yv, gv = prep(val)
        ud, gi = np.unique(gd, return_inverse=True)
        def nll(b):
            s = Xd @ b; s = s - s.max(); ex = np.exp(s); den = np.bincount(gi, ex); ll = (yd * (s - np.log(den[gi]))).sum()
            p = ex / den[gi]; ch = np.bincount(gi, yd)
            grad = Xd.T @ yd - Xd.T @ (p * ch[gi])
            return -ll + 0.5 * 0.1 * b @ b, -grad + 0.1 * b
        res = minimize(nll, np.zeros(len(CL_FEATS)), jac=True, method='L-BFGS-B')
        b = res.x
        def top1(X, y, g):
            s = X @ b; h = []
            for gg in np.unique(g):
                ix = np.where(g == gg)[0]; h.append(y[ix[np.argmax(s[ix])]])
            return float(np.mean(h))
        rows.append(dict(event=label, split='DEV', criterion='conditional logit (DEV fit)', n_episodes=len(ud), hit_at_1=top1(Xd, yd, gd)))
        rows.append(dict(event=label, split='VAL', criterion='conditional logit (DEV fit)', n_episodes=len(np.unique(gv)), hit_at_1=top1(Xv, yv, gv)))
        for f, c in sorted(zip(CL_FEATS, b), key=lambda x: -abs(x[1])):
            rows.append(dict(event=label, split='DEV', criterion=f'clogit coef (std units): {f}', n_episodes=len(ud), hit_at_1=c))
    return rows

def quantity(CM, E, b, label, filt):
    ee = filt(E); rows = []
    key = CM.set_index(['und', 'expiry', 'mi']).sort_index()
    for r in ee.itertuples():
        try: c = key.loc[(r.und, r.expiry, r.mi)].reset_index()
        except KeyError: continue
        ch = c[c.closed > 0]
        side_lots = c[c.cp.isin(['CE', 'PE'] if r.sides == 'CEPE' else [r.sides])].n_lots.sum()
        for z in ch.itertuples():
            rows.append(dict(event=label, split=r.split, closed=z.closed, open_lots=z.n_lots, frac=min(z.closed / z.n_lots, 1.0), side_frac=r.lots / side_lots if side_lots else np.nan))
    Q = pd.DataFrame(rows)
    if not len(Q): return []
    return [dict(event=label, split='ALL-not-TEST', criterion='quantity', n_episodes=len(Q), full_contract=(Q.frac >= 1).mean(), one_lot=(Q.closed == 1).mean(),
                 half=((Q.frac > 0.4) & (Q.frac < 0.6)).mean(), median_frac=Q.frac.median(), median_closed=Q.closed.median(), median_side_frac=Q.side_frac.median())] if len(Q[Q.split != 'TEST']) else []

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    CM, BM = bookstate.load()
    E, b = episodes(); E.to_csv(os.path.join(RES, 'side_basket_episodes.csv'), index=False)
    U = E[~E.scheduled]
    print('episodes', len(E), '| unscheduled', len(U))
    print(U[['multi_strike_one_side', 'both_sides', 'single_contract', 'rebalance_with_replacement', 'same_contract_buy_sell']].mean().round(3).to_dict())
    # targets
    P = side_panel(CM, BM)
    side_ev = U[U.multi_strike_one_side | U.both_sides]
    tgt = set()
    for r in side_ev.itertuples():
        for cp in (['CE', 'PE'] if r.sides == 'CEPE' else [r.sides]): tgt.add((r.und, r.expiry, r.mi, cp))
    P['y_side'] = [(u, e, mi, cp) in tgt for u, e, mi, cp in zip(P.und, P.expiry, P.mi, P.cp)]
    bas = set(zip(U[U.both_sides].und, U[U.both_sides].expiry, U[U.both_sides].mi))
    BMx = BM.copy(); BMx['y_basket'] = [(u, e, mi) in bas for u, e, mi in zip(BMx.und, BMx.expiry, BMx.mi)]
    BMx = BMx[BMx.n_contracts >= 2]
    part = set(zip(U[U.single_contract].und, U[U.single_contract].expiry, U[U.single_contract].mi))
    rows, trees = [], {}
    r1, t1 = trigger_tests(P[P.n_contracts_side >= 2], 'y_side', 'side-level reduction (>=2 contracts of a side, unscheduled)'); rows += r1; trees['side'] = t1
    for fam in FAMILIES.values():
        for c in fam:
            if c not in BMx: BMx[c] = np.nan
    r2, t2 = trigger_tests(BMx, 'y_basket', 'basket-level reduction (both sides, unscheduled)'); rows += r2; trees['basket'] = t2
    R = pd.DataFrame(rows)
    # selection + quantity
    sel = []
    for lab, f in [('side-level reduction', lambda E_: E_[~E_.scheduled & E_.multi_strike_one_side]), ('basket-level reduction', lambda E_: E_[~E_.scheduled & E_.both_sides]),
                   ('single-contract unscheduled exit (which contract of the side)', lambda E_: E_[~E_.scheduled & E_.single_contract]),
                   ('rebalance with replacement', lambda E_: E_[~E_.scheduled & E_.rebalance_with_replacement])]:
        G = candidate_sets(CM, E, f); sel += selection(G, lab); sel += quantity(CM, E, b, lab, f)
    SEL = pd.DataFrame(sel)
    SEL.to_csv(os.path.join(RES, 'side_basket_selection.csv'), index=False)
    out = pd.concat([R.assign(section='trigger'), SEL.assign(section='selection')], ignore_index=True)
    out.to_csv(os.path.join(RES, 'side_basket_exit_results.csv'), index=False)
    print(R[R.test.str.startswith('LightGBM') | R.test.str.startswith('depth')].round(3).to_string(index=False))
    print('\nTop univariate (VAL) per event:'); print(R[R.test.str.startswith('univariate')].sort_values('val', ascending=False).groupby('event').head(8).round(3).to_string(index=False))
    for k, t in trees.items(): print(f'\n--- {k} tree (DEV) ---\n{t}')
    print('\nSelection:'); print(SEL.round(3).to_string(index=False))
    # same-contract interactions
    print('\nsame-contract buy/sell within 60s among unscheduled single-contract exits:', U[U.single_contract].same_contract_buy_sell.mean().round(3))
