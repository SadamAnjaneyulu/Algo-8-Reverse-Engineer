"""Follow-up audit: sensitivity of the cumulative cycle MTM at each `s_` trigger to the quote / mark assumptions, and of the
expiry-day-only MTM to the D-1 closing mark.  Cumulative MTM = cash of all fills before the trigger + open lots x mark.
python3 risk_rule_validation/followup/stop_mtm_sensitivity.py"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE); sys.path.insert(0, RR)
import rr_common as rc
sys.path.insert(0, rc.AN)
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)

VARIANTS = {
    'V1 base: s_ quote (orders <= 60 s), else other-order quote <= 60 s, else previous-minute close': ('quote', 60),
    'V2 s_ quotes of the first decision instant only (<= 1 s), else previous-minute close': ('quote_first', 1),
    'V3 s_ quote window 300 s': ('quote', 300),
    'V4 s_ fill VWAP (execution) instead of recovered quote': ('vwap', 60),
    'V5 all at previous-minute close': ('prev_close', None),
    'V6 all at stop-minute close': ('stop_close', None),
    'V7 adverse bound: shorts at stop-minute high, longs at low': ('adverse', None),
    'V8 favourable bound: shorts at stop-minute low, longs at high': ('favourable', None),
}


def main():
    o = rc.orders(); mk = rc.markets(); d = rc.fills(); L = rc.ledger('cheap')
    from mtm import cycle_mtm, cycle_mtm_adverse
    opt = pd.read_pickle(os.path.join(rc.AN, '_cache', 'opt_candles.pkl'))
    rows, band, d0rows, ns = [], [], [], []
    for (u, e) in rc.cycle_keys():
        m = mk[(u, e)]; oc = o[(o.und == u) & (o.expiry == e)]; dc = d[(d.und == u) & (d.expiry == e)]; lot = rc.LOT[u]
        B = rc.CycleBook(u, e, 'cheap', L, m); cum = B.cum(); d1, d0 = rc.d_bounds(m)
        s = oc[oc.tp == 's_']
        if s.empty:
            fm = cycle_mtm(d, opt, u, e); fa = cycle_mtm_adverse(d, opt, u, e)
            ns.append(dict(und=u, expiry=e.date(), min_mtm_minute_close=float(cum.min()), min_mtm_fills_close=float(fm.min()), min_mtm_adverse_bound=float(fa.min())))
            continue
        for r in s.itertuples():
            band.append(dict(side=r.side, ratio=r.vwap / (r.L * (1.15 if r.side == 'Buy' else 0.85)) if r.L > 0 else np.nan, fill_over_quote=r.vwap / r.L if r.L > 0 else np.nan))
        ts = s.t_dec.min(); ms = rc.minute_of(m, ts)
        pre = dc[dc.t < ts]; pos = pre.groupby(['cp', 'strike']).sl.sum(); pos = pos[pos != 0]; cash = pre.cash.sum()
        r0 = dict(und=u, expiry=e.date(), stop_time=ts, stop_day='D0' if ts.normalize() == e else 'D-1', open_contracts=len(pos))
        for name, (kind, win) in VARIANTS.items():
            val = cash; src_q = 0.0; tot = 0.0
            for (cp, k), q in pos.items():
                kk = m['k2i'][(cp, k)]; px = None
                if kind in ('quote', 'quote_first', 'vwap'):
                    sw = s[(s.cp == cp) & (s.strike == k) & (s.t_dec <= ts + pd.Timedelta(seconds=win))].sort_values('t_dec')
                    if len(sw): px = sw.vwap.iloc[0] if kind == 'vwap' else sw.L.iloc[0]
                    elif kind == 'quote':
                        rq = oc[(oc.cp == cp) & (oc.strike == k) & (oc.t_dec <= ts) & (oc.t_dec >= ts - pd.Timedelta(seconds=win)) & (oc.tp != 's_')].sort_values('t_dec')
                        if len(rq): px = rq.L.iloc[-1]
                    if px is not None: src_q += abs(q) * lot * px
                if px is None:
                    if kind in ('quote', 'quote_first', 'vwap', 'prev_close'): px = m['Cf'][kk, max(ms - 1, 0)]
                    elif kind == 'stop_close': px = m['Cf'][kk, ms]
                    else:
                        hi, lo_ = m['H'][kk, ms], m['L'][kk, ms]; c = m['Cf'][kk, ms]
                        hi = hi if np.isfinite(hi) else c; lo_ = lo_ if np.isfinite(lo_) else c
                        px = (hi if q < 0 else lo_) if kind == 'adverse' else (lo_ if q < 0 else hi)
                px = px if np.isfinite(px) else 0.0
                val += q * lot * px; tot += abs(q) * lot * px
            r0[name] = float(val)
            if kind in ('quote', 'quote_first', 'vwap'): r0[name.split(':')[0].split(' ')[0] + ' share of value quote-marked'] = src_q / tot if tot else np.nan
        rows.append(r0)
        # expiry-day-only MTM at the stop under two D-1 closing marks
        if r0['stop_day'] == 'D0' and d1 is not None:
            fm = cycle_mtm(d, opt, u, e); d1date = m['grid'][d1].normalize()
            base_bar = cum[d1]; base_last = fm[fm.index.normalize() == d1date].iloc[-1]
            v1 = r0[list(VARIANTS)[0]]
            d0rows.append(dict(und=u, expiry=e.date(), cumulative_at_stop_V1=v1, D1_close_mtm_1529_bar=float(base_bar), D1_close_mtm_last_print=float(base_last),
                               D0_only_at_stop_1529_ref=float(v1 - base_bar), D0_only_at_stop_last_print_ref=float(v1 - base_last)))
    R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, 'stop_mtm_sensitivity_by_stop.csv'), index=False)
    gap = R[list(VARIANTS)[0]] < -1.8e5          # descriptive split only: the two stops whose trigger-time MTM is beyond -Rs 1.8 L (both at a session open)
    summ = []
    for name in VARIANTS:
        for sub, msk in (('all 12 stops', np.ones(len(R), bool)), ('10 stops excluding the two open-gap stops', ~gap.values)):
            x = R.loc[msk, name]
            summ.append(dict(variant=name, subset=sub, n=len(x), median=x.median(), mean=x.mean(), sd=x.std(), min=x.min(), max=x.max(),
                             nifty_median=R.loc[msk & (R.und == 'NIFTY').values, name].median(), sensex_median=R.loc[msk & (R.und == 'SENSEX').values, name].median()))
    S = pd.DataFrame(summ); S.to_csv(os.path.join(OUT, 'stop_mtm_sensitivity_summary.csv'), index=False)
    pd.DataFrame(d0rows).to_csv(os.path.join(OUT, 'stop_d0_only_mtm_d1_mark_sensitivity.csv'), index=False)
    N = pd.DataFrame(ns); N.to_csv(os.path.join(OUT, 'non_stop_cycles_deepest_mtm.csv'), index=False)
    Bd = pd.DataFrame(band); Bd.groupby('side')[['ratio', 'fill_over_quote']].describe().to_csv(os.path.join(OUT, 's_order_band_check.csv'))
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 90)
    print(S.round(0).to_string(index=False)); print(pd.DataFrame(d0rows).round(0).to_string(index=False))
    print(N.sort_values('min_mtm_adverse_bound').round(0).head(8).to_string(index=False))
    print(Bd.groupby('side')[['ratio', 'fill_over_quote']].median())


if __name__ == '__main__':
    main()
