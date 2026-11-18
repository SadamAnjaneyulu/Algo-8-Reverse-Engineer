"""1DTE vs 0DTE contract comparison for Algo 7 and Algo 8 (descriptive; no strategy fitting).

Inputs
  Algo 8: Trades_GKOHNP140.csv (repo root, 167 cols, no header) via analysis/load.py.
  Algo 7: the user-supplied Algo_7_Dump.xlsx (header row); path in env ALGO7_DUMP (.xlsx or a pickle of the same sheet).
          Not committed to the repository.
  Index 1-minute bars: analysis/_cache/idx_candles.pkl (Breeze, 22 Jun - 22 Oct 2026), used for ATM distance and the session calendar.

Definitions (see DTE_COMPARISON_REPORT.md section 2)
  contract      = (underlying, expiry, right, strike)
  DTE bucket    = 0DTE if the trade date is the contract's expiry date; 1DTE if it is the last trading session before expiry
                  (session calendar = index-bar sessions U weekdays with fills); '2+DTE' if earlier; 'non-session' for weekend fills.
  order key     = Algo 8: column-163 UniqueOrderIdentifier; Algo 7: (NOWOrderNo, trade date) (NOWOrderNo alone is reused across days).
  position role = per contract, fills in time order against a running net position starting at 0 at the contract's first fill:
                  sell lots that increase the short -> short_open; sell lots that reduce a long -> long_close;
                  buy lots that reduce a short -> short_close; buy lots that increase the long -> long_open (an order crossing zero is split).
  re-entry      = short_open lots in a contract that already had short_close lots earlier in the same session (association label).
  replacement   = short_open lots within 60 s after a short_close on the same underlying, session and right (association label, as PR #5).
python3 dte_comparison/dte_compare.py
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE); AN = os.path.join(REPO, 'analysis'); C = os.path.join(AN, '_cache')
sys.path.insert(0, AN)
LOT = {'NIFTY': 65, 'SENSEX': 20}; STEP = {'NIFTY': 50, 'SENSEX': 100}
MAIN_IDS = {'99999', '9999999999999990', '1E+16'}          # main books (per underlying); others = platform risk actor / hedge app / unlabelled
REPL_S = 60

def load_a8():
    from load import load_tagged
    d = load_tagged()
    raw = pd.read_csv(os.path.join(REPO, 'Trades_GKOHNP140.csv'), header=None, dtype=str, keep_default_na=False, usecols=[144])
    return pd.DataFrame(dict(algo='Algo 8', und=d.und, expiry=d.expiry, cp=d.cp, strike=d.strike.astype(float), side=d.side, qty=d.qty_fill.astype(float),
                             px=d.px_fill.astype(float), t=d.t, order=d.tag.astype(str), tp=d.tp, algoid=raw[144].values, row=d.row))

def load_a7():
    p = os.environ.get('ALGO7_DUMP')
    if not p or not os.path.exists(p): raise SystemExit('set ALGO7_DUMP to Algo_7_Dump.xlsx (or a pickle of it)')
    a = pd.read_pickle(p) if p.endswith('.pkl') else pd.read_excel(p)
    t = pd.to_datetime(a['TradeTime'])
    tag = a['UniqueOrderIdentifier']
    tp = tag.astype(str).str.extract(r'^([a-z]+_)')[0].where(tag.notna(), 'untagged').fillna('num')
    return pd.DataFrame(dict(algo='Algo 7', und=a['Symbol'].astype(str), expiry=pd.to_datetime(a['ExpiryDate']).dt.normalize(), cp=a['OptionType'].astype(str),
                             strike=a['StrikePrice'].astype(float), side=a['BuySell'].astype(str), qty=a['TradedQty'].astype(float), px=a['TradePrice'].astype(float),
                             t=t, order=a['NOWOrderNo'].astype(str) + '|' + t.dt.strftime('%Y-%m-%d'), tp=tp, algoid=a['AlgoId'].astype(str), row=np.arange(len(a))))

def sessions_calendar(frames, idx):
    s = set(idx.ts.dt.normalize().unique())
    for f in frames:
        dd = f.t.dt.normalize(); s |= set(dd[dd.dt.dayofweek < 5].unique())
    return np.array(sorted(s), dtype='datetime64[ns]')

def bucket(df, cal):
    df['date'] = df.t.dt.normalize()
    df['dte_cal_days'] = (df.expiry - df.date).dt.days
    pos_e = np.searchsorted(cal, df.expiry.values.astype('datetime64[ns]'))       # index of expiry (or insertion point)
    pos_d = np.searchsorted(cal, df.date.values.astype('datetime64[ns]'))
    df['dte_sessions'] = pos_e - pos_d
    weekend = df.date.dt.dayofweek >= 5
    df['bucket'] = np.select([weekend, df.dte_cal_days == 0, df.dte_sessions == 1], ['non-session', '0DTE', '1DTE'], '2+DTE')
    return df

def roles(df):
    df = df.sort_values(['t', 'row']).reset_index(drop=True)
    df['lots'] = df.qty / df.und.map(LOT)
    out = {k: np.zeros(len(df)) for k in ('short_open', 'long_close', 'short_close', 'long_open')}
    net = {}
    for i, (k, s, q) in enumerate(zip(zip(df.und, df.expiry, df.cp, df.strike), df.side, df.lots.values)):
        n = net.get(k, 0.0)
        if s == 'Sell':
            a = min(max(n, 0.0), q); out['long_close'][i] = a; out['short_open'][i] = q - a; n -= q
        else:
            a = min(max(-n, 0.0), q); out['short_close'][i] = a; out['long_open'][i] = q - a; n += q
        net[k] = n
    for k, v in out.items(): df[k] = v
    # association labels on short opens
    df['reentry'] = 0.0; df['replacement'] = 0.0
    for (u, dt), g in df.groupby(['und', 'date'], sort=False):
        closed_before = set(); last_close_t = {}
        for i, r in zip(g.index, g.itertuples()):
            k = (r.expiry, r.cp, r.strike)
            if r.short_open > 0:
                if k in closed_before: df.at[i, 'reentry'] = r.short_open
                lc = last_close_t.get(r.cp)
                if lc is not None and 0 <= (r.t - lc).total_seconds() <= REPL_S: df.at[i, 'replacement'] = r.short_open
            if r.short_close > 0: closed_before.add(k); last_close_t[r.cp] = r.t
    return df

def add_atm(df, idx):
    s = idx.assign(m=idx.ts + pd.Timedelta(minutes=1)).set_index(['und', 'm']).close    # previous completed minute close, keyed by the fill minute
    S = s.reindex(list(zip(df.und, df.t.dt.floor('min')))).values
    df['spot_prev'] = S
    step = df.und.map(STEP).values
    atm = step * np.floor(S / step + 0.5)
    df['atm_steps'] = (df.strike.values - atm) / step                                     # signed strike - ATM, in strikes
    df['otm_steps'] = np.where(df.cp == 'CE', df.atm_steps, -df.atm_steps)               # + = OTM, - = ITM
    return df

POPS = {'all': None, 'short positions (open+close)': ['short_open', 'short_close'], 'long hedges (open+close)': ['long_open', 'long_close'],
        'new entries: short': ['short_open'], 'new entries: long hedge': ['long_open'], 'buybacks: short': ['short_close'],
        'exits: long hedge': ['long_close'], 're-entry (same contract)': ['reentry'], 'replacement (<=60 s, same side)': ['replacement']}

def metrics(g, n_sess):
    """g has column 'w' = lots in this population for each fill (fills with w == 0 removed)."""
    g = g[g.w > 1e-9]
    if g.empty: return dict(sessions_in_bucket=n_sess)
    con = list(zip(g.und, g.expiry, g.cp, g.strike))
    g = g.assign(contract=con, units=g.w * g.und.map(LOT), turnover=g.w * g.und.map(LOT) * g.px)
    per_c = g.groupby('contract').w.sum(); per_cd = g.groupby(['contract', 'date']).w.sum()
    cov = g.otm_steps.notna()
    ww = g.w[cov]; ab = g.otm_steps[cov].abs()
    def wq(x, w, q):
        o = np.argsort(x.values); cx = np.cumsum(w.values[o]); return float(x.values[o][np.searchsorted(cx, q * cx[-1])]) if len(x) else np.nan
    return dict(sessions_in_bucket=n_sess, distinct_contracts=len(per_c), contract_days=len(per_cd), lots=g.w.sum(), units=g.units.sum(),
                buy_orders=g[g.side == 'Buy'].order.nunique(), sell_orders=g[g.side == 'Sell'].order.nunique(), orders=g.order.nunique(), fills=len(g),
                ce_contracts=int(sum(1 for c in per_c.index if c[2] == 'CE')), pe_contracts=int(sum(1 for c in per_c.index if c[2] == 'PE')),
                distinct_strikes=g[['und', 'strike']].drop_duplicates().shape[0],
                atm_coverage_lots=ww.sum() / g.w.sum(), atm_dist_median_abs_steps=wq(ab, ww, 0.5), atm_dist_mean_abs_steps=float(np.average(ab, weights=ww)) if len(ww) else np.nan,
                atm_dist_p90_abs_steps=wq(ab, ww, 0.9), share_lots_at_atm=float(ww[ab == 0].sum() / ww.sum()) if len(ww) else np.nan,
                share_lots_within_1_step=float(ww[ab <= 1].sum() / ww.sum()) if len(ww) else np.nan, median_otm_steps_signed=wq(g.otm_steps[cov], ww, 0.5),
                lots_per_contract_mean=per_c.mean(), lots_per_contract_median=per_c.median(), lots_per_contract_day_mean=per_cd.mean(),
                orders_per_contract_day=g.groupby(['contract', 'date']).order.nunique().mean(), lots_per_order=g.w.sum() / g.order.nunique(),
                premium_avg_lot_weighted=float(np.average(g.px, weights=g.w)), premium_median_fill=float(g.px.median()), turnover_rs=g.turnover.sum())

def summarize(df):
    rows = []
    for scope, sub in (('all actors', df), ('main-book AlgoIds only', df[df.algoid.isin(MAIN_IDS)])):
        for b, gb in sub.groupby('bucket'):
            n_sess = gb[['und', 'date']].drop_duplicates().shape[0]
            for pname, cols in POPS.items():
                g = gb.assign(w=gb.lots if cols is None else gb[cols].sum(axis=1))
                m = metrics(g, n_sess); m.update(algo=df.algo.iloc[0], scope=scope, bucket=b, population=pname, dates=gb.date.nunique()); rows.append(m)
    return pd.DataFrame(rows)

if __name__ == '__main__':
    idx = pd.read_pickle(os.path.join(C, 'idx_candles.pkl'))
    a8 = load_a8(); a7 = load_a7()
    cal = sessions_calendar([a8, a7], idx)
    out, fills = [], []
    for df in (a7, a8):
        df = add_atm(roles(bucket(df, cal)), idx); fills.append(df); out.append(summarize(df))
    R = pd.concat(out, ignore_index=True)
    per = ['distinct_contracts', 'contract_days', 'lots', 'units', 'buy_orders', 'sell_orders', 'orders', 'fills', 'ce_contracts', 'pe_contracts', 'distinct_strikes', 'turnover_rs']
    for c in per: R[c + '_per_session'] = R[c] / R.sessions_in_bucket
    lead = ['algo', 'scope', 'bucket', 'population', 'sessions_in_bucket', 'dates']
    R = R[lead + [c for c in R.columns if c not in lead]]
    R.to_csv(os.path.join(HERE, 'DTE_COMPARISON.csv'), index=False, float_format='%.4f')
    F = pd.concat(fills, ignore_index=True)
    F.groupby(['algo', 'bucket', 'und']).agg(fills=('t', 'size'), sessions=('date', 'nunique'), lots=('lots', 'sum'),
                                              cal_days_min=('dte_cal_days', 'min'), cal_days_max=('dte_cal_days', 'max')).to_csv(os.path.join(HERE, 'dte_bucket_coverage.csv'))
    # role reconciliation: role lots must sum to traded lots
    chk = (F[['short_open', 'long_close', 'short_close', 'long_open']].sum(axis=1) - F.lots).abs().max()
    print('max role reconciliation error (lots):', chk)
    print(R[(R.scope == 'all actors') & (R.population == 'all')][lead + ['distinct_contracts', 'contract_days', 'lots', 'turnover_rs']].to_string(index=False))
    # decomposition of per-session lots: contracts/session x orders per contract-day x lots per order; contracts = strikes x rights per strike
    D = []
    for (al, b), g in F[F.bucket.isin(['0DTE', '1DTE'])].groupby(['algo', 'bucket']):
        g = g.assign(contract=list(zip(g.und, g.expiry, g.cp, g.strike)))
        ps = g.groupby(['und', 'date']).agg(contracts=('contract', 'nunique'), strikes=('strike', 'nunique'), orders=('order', 'nunique'), lots=('lots', 'sum'),
                                             turnover=('px', lambda x: float((x * g.loc[x.index, 'qty']).sum())))
        cd = g.groupby(['contract', 'date']).agg(orders=('order', 'nunique'), lots=('lots', 'sum'))
        D.append(dict(algo=al, bucket=b, sessions=len(ps), contracts_per_session=ps.contracts.mean(), strikes_per_session=ps.strikes.mean(),
                      rights_per_strike=(ps.contracts / ps.strikes).mean(), orders_per_contract_day=cd.orders.sum() / len(cd),
                      lots_per_order=cd.lots.sum() / cd.orders.sum(), lots_per_contract_day=cd.lots.mean(), lots_per_session=ps.lots.mean(),
                      turnover_per_session=ps.turnover.mean()))
    D = pd.DataFrame(D)
    for al, g in D.groupby('algo'):
        if set(g.bucket) >= {'0DTE', '1DTE'}:
            z, o = g.set_index('bucket').loc['0DTE'], g.set_index('bucket').loc['1DTE']
            tot = np.log(z.lots_per_session / o.lots_per_session)
            parts = {'contracts_per_session': np.log(z.contracts_per_session / o.contracts_per_session),
                     'orders_per_contract_day': np.log(z.orders_per_contract_day / o.orders_per_contract_day),
                     'lots_per_order': np.log(z.lots_per_order / o.lots_per_order)}
            D.loc[D.algo == al, 'ratio_lots_per_session_0DTE_over_1DTE'] = z.lots_per_session / o.lots_per_session
            for k, v in parts.items(): D.loc[D.algo == al, 'logshare_' + k] = v / tot
            D.loc[D.algo == al, 'ratio_strikes_per_session'] = z.strikes_per_session / o.strikes_per_session
            D.loc[D.algo == al, 'ratio_rights_per_strike'] = z.rights_per_strike / o.rights_per_strike
    D.to_csv(os.path.join(HERE, 'dte_decomposition.csv'), index=False, float_format='%.4f')
    print(D.T.to_string())
    # contracts traded in both buckets, and overnight carry (net position at the end of the 1DTE session)
    O = []
    for al, g in F.groupby('algo'):
        k = g.assign(contract=list(zip(g.und, g.expiry, g.cp, g.strike)))
        c1 = set(k[k.bucket == '1DTE'].contract); c0 = set(k[k.bucket == '0DTE'].contract)
        one = k[k.bucket == '1DTE']; net = (one.lots * np.where(one.side == 'Buy', 1, -1)).groupby(one.contract).sum()
        O.append(dict(algo=al, contracts_1DTE=len(c1), contracts_0DTE=len(c0), contracts_both=len(c1 & c0), contracts_union=len(c1 | c0),
                      carried_short_lots=float(-net[net < 0].sum()), carried_long_lots=float(net[net > 0].sum()),
                      carried_short_contracts=int((net < 0).sum()), carried_long_contracts=int((net > 0).sum())))
    O = pd.DataFrame(O); O.to_csv(os.path.join(HERE, 'dte_overlap_and_carry.csv'), index=False); print(O.to_string(index=False))
