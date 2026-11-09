"""Exit ledger: one row per CLOSING order with the full state known BEFORE the decision.
Inventory is tag-agnostic per contract (a Buy closes open shorts first, else opens a long; a Sell closes open longs first, else opens a short).
Marks = Breeze closes of the minute BEFORE the decision (ffill); the traded contract additionally carries its recovered quote L.
python3 analysis/exit_engine/ledger.py  -> analysis/_cache/exit_ledger.pkl"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from load import load_tagged, RAW
from a7_lean import bs_vec, iv_vec
C = os.path.join(os.path.dirname(HERE), '_cache')

def decision_times(d):
    """microsecond decision time from h_/s_/v_/m_ tags (DDHHMMSSffffff, UTC); else first fill time."""
    t = d.groupby('oid').t.min()
    tag = d.groupby('oid').tag.first()
    out = t.copy()
    m = tag.str.match(r'^[a-z]+_\d{14}$')
    for oid in tag[m].index:
        s = tag[oid].split('_')[1]; dd, hh, mi, ss, us = int(s[:2]), int(s[2:4]), int(s[4:6]), int(s[6:8]), int(s[8:])
        ft = t[oid]
        if ft.day != dd: continue
        cand = ft.normalize() + pd.Timedelta(hours=hh + 5, minutes=mi + 30, seconds=ss, microseconds=us)
        if abs((cand - ft).total_seconds()) < 120: out[oid] = min(cand, ft)
    return out

def build():
    raw = pd.read_csv(RAW, header=None, dtype=str, keep_default_na=False)
    d = load_tagged(); d['algoid'] = raw[144].values; d['appkey'] = raw[166].str[-6:].values
    d['oid'] = d['tag']      # col 4 order ids are reused across days; col 163 (UniqueOrderIdentifier) is unique per order (== oid + date)
    d['L'] = np.where(d.side == 'Buy', d.px_order / 1.15, d.px_order / 0.85)
    v = d.tp == 'v_'; d.loc[v, 'L'] = np.where(d.side == 'Buy', d.px_order / 1.03, d.px_order / 0.85)[v]
    dt = decision_times(d)
    o = d.sort_values(['t', 'row']).groupby('oid').agg(t_first=('t', 'min'), t_last=('t', 'max'), und=('und', 'first'), expiry=('expiry', 'first'),
        date=('date', 'first'), dte=('dte', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), side=('side', 'first'), tp=('tp', 'first'),
        algoid=('algoid', 'first'), appkey=('appkey', 'first'), lots=('lots', 'sum'), L=('L', 'first'), validity=('validity', 'first'),
        vwap=('px_fill', lambda x: np.average(x, weights=d.loc[x.index, 'qty_fill'])), lot=('lot', 'first'))
    o['t_dec'] = dt.reindex(o.index).values
    o = o.reset_index().sort_values(['t_dec', 'oid'])
    ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')); op = pd.read_pickle(os.path.join(C, 'opt_candles.pkl'))
    I = pd.read_pickle(os.path.join(C, 'indicators_index.pkl')); IO = pd.read_pickle(os.path.join(C, 'indicators_options.pkl'))
    I = I.merge(IO, on=['und', 'm'], how='left').set_index(['und', 'm'])
    rows = []
    for (u, e), g in o.groupby(['und', 'expiry']):
        days = sorted(g.date.unique()); lot = int(g.lot.iloc[0]); step = 50 if u == 'NIFTY' else 100
        s = ix[(ix.und == u) & ix.ts.dt.normalize().isin(days)].set_index('ts').close.sort_index()
        if len(s) < 50: continue
        grid = s.index; gpos = {t: i for i, t in enumerate(grid)}
        oc = op[(op.und == u) & (op.expiry == e) & op.ts.isin(grid)]
        keys = sorted(set(zip(oc.cp, oc.strike)) | set(zip(g.cp, g.strike))); k2i = {k: i for i, k in enumerate(keys)}
        Cm = np.full((len(keys), len(grid)), np.nan); Hm = Cm.copy(); Lm = Cm.copy()
        ki = np.array([k2i[(a, b)] for a, b in zip(oc.cp, oc.strike)]); ti = np.array([gpos[t] for t in oc.ts])
        Cm[ki, ti] = oc.c.values; Hm[ki, ti] = oc.h.values; Lm[ki, ti] = oc.l.values
        Cf = pd.DataFrame(Cm.T).ffill().values.T
        K = np.array([k for _, k in keys], float); isc = np.array([c == 'CE' for c, _ in keys])
        T = ((e + pd.Timedelta('15:30:00') - grid).total_seconds().values / (365 * 86400)).clip(min=1 / 525600)
        S = s.values
        P = np.where(np.isfinite(Cf), Cf, np.nan)
        intr = np.where(isc[:, None], np.maximum(S[None] - K[:, None], 0), np.maximum(K[:, None] - S[None], 0))
        Pc = np.maximum(np.nan_to_num(P, nan=0.05), intr + 0.05)
        shp = Pc.shape; bS = np.broadcast_to(S[None], shp); bK = np.broadcast_to(K[:, None], shp); bT = np.broadcast_to(T[None], shp); bc = np.broadcast_to(isc[:, None], shp)
        IV = iv_vec(bc, bS, bK, bT, Pc); _, DEL = bs_vec(bc, bS, bK, bT, IV)
        sq = IV * np.sqrt(bT); d1 = (np.log(bS / bK) + 0.5 * IV * IV * bT) / sq
        GAM = np.exp(-d1 * d1 / 2) / np.sqrt(2 * np.pi) / (bS * sq); VEG = bS * np.exp(-d1 * d1 / 2) / np.sqrt(2 * np.pi) * np.sqrt(bT) / 100
        THE = -(bS * np.exp(-d1 * d1 / 2) / np.sqrt(2 * np.pi) * IV / (2 * np.sqrt(bT))) / 365
        # running inventory state
        lots = {k: [] for k in keys}        # list of [sgn, entry_px, entry_t, entry_spot, entry_idx] per unit lot
        cash = 0.0; realized = {k: 0.0 for k in keys}
        last_sale = {}; last_buyback = {}
        mtm_hist = []                        # (minute index, cycle mtm) for peak tracking
        def book_mtm(mi):
            return cash + sum(sum(x[0] for x in lots[k]) * lot * Cf[k2i[k], mi] for k in keys if lots[k] and np.isfinite(Cf[k2i[k], mi]))
        last_mi = -1
        for r in g.itertuples():
            mi = gpos.get(pd.Timestamp(r.t_dec).floor('min'), None)
            if mi is None:
                cand = grid.searchsorted(pd.Timestamp(r.t_dec).floor('min')); mi = min(cand, len(grid) - 1)
            pm = max(mi - 1, 0)
            # update mtm history for minutes up to pm
            for j in range(last_mi + 1, pm + 1): mtm_hist.append(book_mtm(j))
            last_mi = max(last_mi, pm)
            k = (r.cp, r.strike); kk = k2i[k]; n = int(round(r.lots)); sgn_order = 1 if r.side == 'Buy' else -1
            open_units = lots[k]; pos = sum(x[0] for x in open_units)
            closing = (sgn_order > 0 and pos < 0) or (sgn_order < 0 and pos > 0)
            if closing:
                ents = np.array([x[1] for x in open_units]); ets = [x[2] for x in open_units]; esp = np.array([x[3] for x in open_units]); eix = [x[4] for x in open_units]
                q = r.L if np.isfinite(r.L) else Cf[kk, pm]
                side_keys = [x for x in keys if x[0] == r.cp and lots[x]]; same_strike = [x for x in keys if x[1] == r.strike and lots[x]]
                def upnl(ks): return sum((sum(x[0] for x in lots[x_]) * lot * (Cf[k2i[x_], pm] if np.isfinite(Cf[k2i[x_], pm]) else 0)) - sum(x[0] * x[1] for x in lots[x_]) * lot for x_ in ks)
                mt = mtm_hist[-1] if mtm_hist else 0.0; peak = max([0.0] + mtm_hist)
                tot_short = sum(-sum(x[0] for x in lots[x_]) for x_ in keys if lots[x_] and sum(x[0] for x in lots[x_]) < 0)
                side_short = sum(-sum(x[0] for x in lots[x_]) for x_ in side_keys if sum(x[0] for x in lots[x_]) < 0)
                cheap = int(np.argmin(ents)) if pos < 0 else int(np.argmax(ents))
                key_m = pd.Timestamp(r.t_dec).floor('min')
                ind = I.loc[(u, key_m)] if (u, key_m) in I.index else None
                atr1 = (ind['1m_atr14_bp'] * S[pm] / 1e4) if ind is not None else np.nan
                atr5 = (ind['5m_atr14_bp'] * S[pm] / 1e4) if ind is not None else np.nan
                ci = eix[cheap]
                rows.append(dict(oid=r.oid, und=u, expiry=e, date=r.date, dte=r.dte, t_dec=r.t_dec, cp=r.cp, strike=r.strike, side=r.side, tp=r.tp,
                    algoid=r.algoid, appkey=r.appkey, validity=r.validity, lots_closed=n, closing_short=pos < 0, open_lots_before=abs(pos),
                    remaining_after=max(abs(pos) - n, 0), L=q, vwap=r.vwap, mark_prev=Cf[kk, pm], hi_min=Hm[kk, mi], lo_min=Lm[kk, mi],
                    e_cheap=ents.min() if pos < 0 else ents.max(), e_avg=ents.mean(), e_fifo=ents[0], e_lifo=ents[-1],
                    r_cheap=q / (ents.min() if pos < 0 else ents.max()), r_avg=q / ents.mean(), r_fifo=q / ents[0], r_lifo=q / ents[-1],
                    run_min_since_cheap=np.nanmin(Lm[kk, ci:mi]) if mi > ci else np.nan, run_max_since_cheap=np.nanmax(Hm[kk, ci:mi]) if mi > ci else np.nan,
                    upnl_contract=upnl([k]), upnl_side=upnl(side_keys), upnl_basket=upnl(same_strike), realized_contract=realized[k],
                    cycle_mtm=mt, cycle_peak=peak, cycle_dd=mt - peak,
                    spot=S[pm], spot_entry_cheap=esp[cheap], atr1=atr1, atr5=atr5,
                    mv5=S[pm] - S[max(pm - 5, 0)], mv15=S[pm] - S[max(pm - 15, 0)],
                    iv_now=IV[kk, pm], iv_entry=IV[kk, ci], delta_now=DEL[kk, pm], delta_entry=DEL[kk, ci], gamma_now=GAM[kk, pm], gamma_entry=GAM[kk, ci],
                    theta_now=THE[kk, pm], vega_now=VEG[kk, pm], vega_entry=VEG[kk, ci],
                    rv1_now=ind['1m_rv20_bp'] if ind is not None else np.nan, atm_iv=ind['atm_iv'] if ind is not None else np.nan,
                    atm_iv_chg15=ind['atm_iv_chg15'] if ind is not None else np.nan, ema20_slope5=ind['5m_ema20_slope'] if ind is not None else np.nan,
                    day_range_bp=ind['day_range_bp'] if ind is not None else np.nan,
                    min_since_cheap_entry=(pd.Timestamp(r.t_dec) - ets[cheap]).total_seconds() / 60, min_since_oldest=(pd.Timestamp(r.t_dec) - min(ets)).total_seconds() / 60,
                    min_since_newest=(pd.Timestamp(r.t_dec) - max(ets)).total_seconds() / 60, tte_min=(e + pd.Timedelta('15:30:00') - pd.Timestamp(r.t_dec)).total_seconds() / 60,
                    since_sale_contract=(pd.Timestamp(r.t_dec) - last_sale[k]).total_seconds() / 60 if k in last_sale else np.nan,
                    since_sale_side=min([(pd.Timestamp(r.t_dec) - v_).total_seconds() / 60 for k_, v_ in last_sale.items() if k_[0] == r.cp] or [np.nan]),
                    since_sale_any=min([(pd.Timestamp(r.t_dec) - v_).total_seconds() / 60 for v_ in last_sale.values()] or [np.nan]),
                    since_bb_contract=(pd.Timestamp(r.t_dec) - last_buyback[k]).total_seconds() / 60 if k in last_buyback else np.nan,
                    since_bb_any=min([(pd.Timestamp(r.t_dec) - v_).total_seconds() / 60 for v_ in last_buyback.values()] or [np.nan]),
                    n_short_contracts=sum(1 for x_ in keys if lots[x_] and sum(y[0] for y in lots[x_]) < 0), total_short_lots=tot_short,
                    share_contract_in_side=abs(pos) / side_short if side_short else np.nan, share_side_in_book=side_short / tot_short if tot_short else np.nan))
            # apply the order to inventory
            rem = n
            if closing:
                # close fungible units: keep identity-agnostic, remove cheapest-first for shorts (stop-consistent), FIFO for longs
                open_units.sort(key=lambda x: x[1] if pos < 0 else x[2])
                take = min(rem, len(open_units)); closed = open_units[:take]; del open_units[:take]; rem -= take
                realized[k] += sum((-x[0]) * (r.vwap - x[1]) * lot * -1 for x in closed) * 1
                if pos < 0: last_buyback[k] = pd.Timestamp(r.t_dec)
            for _ in range(rem):
                open_units.append([sgn_order, r.vwap, pd.Timestamp(r.t_dec), S[pm], mi])
                if sgn_order < 0: last_sale[k] = pd.Timestamp(r.t_dec)
            cash += -sgn_order * r.vwap * lot * n
    X = pd.DataFrame(rows)
    X.to_pickle(os.path.join(C, 'exit_ledger.pkl'))
    return X

if __name__ == '__main__':
    X = build()
    print('closing orders:', len(X), '| closing shorts:', int(X.closing_short.sum()), '| closing longs:', int((~X.closing_short).sum()))
    print(X.groupby(['closing_short', 'tp']).agg(orders=('oid', 'size'), lots=('lots_closed', 'sum')).to_string())
