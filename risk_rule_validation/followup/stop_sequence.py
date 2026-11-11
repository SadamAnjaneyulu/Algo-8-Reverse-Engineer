"""Follow-up audit: order-level reconstruction of the 12 `s_` cycle-stop events.

Submission order. The export stamps order entry only to the minute, so an order filled after the stop is not necessarily
submitted after it. Column 4 (broker order number) is used as the submission sequence WITHIN a dashboard app key (col 166):
it is unique per date; inside one app key it forms concurrent number BLOCKS (jumps > 500), and inside a block it is monotone\nin fill time (0.74 % inversions; validated in stream_validation()). Numbers are compared only inside one block.
Tag times of h_/s_/v_/m_ orders are decision/creation times; numbers give submission order.

Classification of every non-`s_` order filled after the stop decision (first `s_` tag time) that opens short lots:
  in-flight              submitted before the first `s_` order of its stream (number lower), filled after the stop
  wing double-liquidation submitted after the stop, in a contract held LONG at the stop that the `s_` module also sold:
                          the short is the excess of two liquidating sells (body hedge-release + `s_`)
  new short (flat/short)  submitted after the stop in a contract that was flat or short at the stop: a possible new decision
  unresolved stream       no `s_` order in the same number block and entered in the stop's own minute
python3 risk_rule_validation/followup/stop_sequence.py
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RR = os.path.dirname(HERE); sys.path.insert(0, RR)
import rr_common as rc
OUT = os.path.join(HERE, 'results'); os.makedirs(OUT, exist_ok=True)


BLOCK_GAP = 500   # a jump larger than this in the order number starts a new number block (a separate, concurrent sequence)


def load():
    raw = pd.read_csv(os.path.join(rc.REPO, 'Trades_GKOHNP140.csv'), header=None, dtype=str, keep_default_na=False, usecols=[4, 163, 166])
    g = raw.groupby(163).agg(no=(4, 'first'), app=(166, 'first'))
    o = rc.orders().merge(g, left_on='oid', right_index=True); o['no'] = o.no.astype(np.int64)
    o['app'] = o.app.str[-6:]
    o = o.sort_values(['date', 'app', 'no'])
    o['block'] = o.groupby(['date', 'app']).no.transform(lambda s: np.r_[0, np.cumsum(np.diff(s.values) > BLOCK_GAP)])
    return o.sort_index(), rc.fills()


def stream_validation(o):
    rows = []
    for (d, a, bl), x in o.groupby(['date', 'app', 'block']):
        b = x.sort_values('no'); inv = (np.diff(b.om.values.astype('int64')) < 0); invf = (np.diff(b.t_fill.values.astype('int64')) < 0)
        rows.append(dict(date=d, app=a, block=bl, orders=len(x), no_min=b.no.min(), no_max=b.no.max(), modules=','.join(f'{k}:{v}' for k, v in b.tp.value_counts().items()),
                         adjacent_pairs=len(inv), minute_inversions=int(inv.sum()), fill_time_inversions=int(invf.sum())))
    R = pd.DataFrame(rows)
    return R, R.fill_time_inversions.sum() / R.adjacent_pairs.sum()


def net_before(dc, t):
    x = dc[dc.t < t]; return x.groupby(['cp', 'strike']).sl.sum()


def main():
    o, d = load()
    V, inv_rate = stream_validation(o); V.to_csv(os.path.join(OUT, 'order_number_stream_validation.csv'), index=False)
    seq_rows, post_rows, summ = [], [], []
    for (u, e), oc in o.groupby(['und', 'expiry']):
        s = oc[oc.tp == 's_']
        if s.empty: continue
        ts = s.t_dec.min(); day = ts.normalize()
        dc = d[(d.und == u) & (d.expiry == e)].sort_values(['t', 'row'])
        lot = rc.LOT[u]
        pos0 = net_before(dc, ts); pos0 = pos0[pos0 != 0]
        s_same = s[s.date == day]; app_s = s_same.app.mode().iloc[0]
        first_no = {(a, b): g.no.min() for (a, b), g in s_same.groupby(['app', 'block'])}   # comparisons only inside one number block
        # s_ waves: cluster s_ orders by submission number gaps > 0 with any non-s_ order in between (same stream)
        stream = oc[(oc.date == day) & (oc.app == app_s)].sort_values('no')
        stream = stream[stream.no >= s_same[s_same.app == app_s].no.min()]
        wave, w = [], 0; prev_s = None
        for r in stream.itertuples():
            if r.tp == 's_':
                if prev_s is False: w += 1
                wave.append((r.oid, w)); prev_s = True
            else:
                prev_s = False if prev_s is not None else None
        wv = dict(wave)
        # per-order position effect at its first fill (convention-free, from fills before that order's first fill)
        win = oc[(oc.t_fill >= ts - pd.Timedelta(minutes=2)) & (oc.date == day)].sort_values(['t_fill', 'no'])
        for r in win.itertuples():
            pb = net_before(dc, r.t_fill).get((r.cp, r.strike), 0.0)
            n = r.lots; sg = 1 if r.side == 'Buy' else -1
            if sg < 0: lc = min(max(pb, 0), n); so = n - lc; sc = lo = 0
            else: sc = min(max(-pb, 0), n); lo = n - sc; lc = so = 0
            kb = (r.app, r.block)
            submitted_before = (r.no < first_no[kb]) if kb in first_no else (r.om < ts.floor('min'))
            ambiguous = (kb not in first_no) and (r.om == ts.floor('min'))
            seq_rows.append(dict(und=u, expiry=e.date(), stop_time=ts, order_no=r.no, app=r.app, block=r.block, module=r.tp, s_wave=wv.get(r.oid, ''), side=r.side, cp=r.cp,
                                 strike=r.strike, lots=n, order_minute=r.om, decision_time=r.t_dec, first_fill=r.t_fill, short_open_lots=so, short_close_lots=sc,
                                 long_open_lots=lo, long_close_lots=lc, net_before_fill=pb, submitted_before_stop=bool(submitted_before) and not ambiguous,
                                 submission_ambiguous=bool(ambiguous), after_stop_fill=r.t_fill >= ts))
            if r.t_fill >= ts and r.tp != 's_' and so > 0:
                held_long_at_stop = pos0.get((r.cp, r.strike), 0.0) > 0
                s_sold = ((s_same.cp == r.cp) & (s_same.strike == r.strike) & (s_same.side == 'Sell')).any()
                if ambiguous: cls = 'unresolved (no s_ in its number block; entered in the stop minute)'
                elif submitted_before: cls = 'in-flight (submitted before the stop)'
                elif held_long_at_stop and s_sold: cls = 'wing double-liquidation (long at stop; s_ also sold it)'
                elif held_long_at_stop: cls = 'over-sale of a long held at the stop (no s_ sale of it)'
                else: cls = 'new short in a contract flat/short at the stop'
                later = dc[(dc.t > r.t_fill) & (dc.cp == r.cp) & (dc.strike == r.strike) & (dc.side == 'Buy')]
                closer = oc[oc.oid.isin(later.oid.unique())].sort_values('t_fill')
                post_rows.append(dict(und=u, expiry=e.date(), stop_time=ts, order_no=r.no, app=r.app, module=r.tp, cp=r.cp, strike=r.strike, lots=n,
                                      short_open_lots=so, order_minute=r.om, first_fill=r.t_fill, seconds_after_stop=(r.t_fill - ts).total_seconds(),
                                      position_at_stop=pos0.get((r.cp, r.strike), 0.0), s_sold_same_contract=bool(s_sold), classification=cls,
                                      next_buy_module=closer.tp.iloc[0] if len(closer) else '', next_buy_seconds_after_fill=(closer.t_fill.iloc[0] - r.t_fill).total_seconds() if len(closer) else np.nan))
        # s_ orders that themselves open shorts (over-selling wings)
        S = pd.DataFrame([x for x in seq_rows if x['und'] == u and x['expiry'] == e.date()])
        sS = S[S.module == 's_']
        end_flat = None
        net = dc.groupby(['cp', 'strike']).sl.sum()
        after = dc[dc.t >= ts]
        # first time after the stop the short book is flat (net short lots == 0)
        run = net_before(dc, ts).to_dict(); t_flat = None
        for r in after.itertuples():
            k = (r.cp, r.strike); run[k] = run.get(k, 0.0) + r.sl
            if sum(-v for v in run.values() if v < 0) < 1e-9: t_flat = r.t; break
        P = pd.DataFrame([x for x in post_rows if x['und'] == u and x['expiry'] == e.date()])
        cls_counts = P.groupby('classification').short_open_lots.agg(['size', 'sum']) if len(P) else pd.DataFrame()
        summ.append(dict(und=u, expiry=e.date(), stop_time=ts, stop_day='D0' if day == e else 'D-1', s_orders=len(s_same), s_lots=float(s_same.lots.sum()),
                         s_waves=int(sS.s_wave.replace('', np.nan).dropna().nunique()) if len(sS) else 0,
                         s_buy_lots=float(s_same[s_same.side == 'Buy'].lots.sum()), s_sell_lots=float(s_same[s_same.side == 'Sell'].lots.sum()),
                         s_short_open_lots=float(sS.short_open_lots.sum()), s_span_seconds=(s_same.t_fill.max() - ts).total_seconds(),
                         open_short_lots_at_stop=float(-pos0[pos0 < 0].sum()), open_long_lots_at_stop=float(pos0[pos0 > 0].sum()),
                         post_stop_short_open_orders=len(P), post_stop_short_open_lots=float(P.short_open_lots.sum()) if len(P) else 0.0,
                         **{f'{k} orders': int(v['size']) for k, v in cls_counts.iterrows()}, **{f'{k} lots': float(v['sum']) for k, v in cls_counts.iterrows()},
                         short_book_flat_seconds_after_stop=(t_flat - ts).total_seconds() if t_flat is not None else np.nan,
                         open_short_lots_end_of_session=float(-net[net < 0].sum()), open_long_lots_end_of_session=float(net[net > 0].sum())))
    pd.DataFrame(seq_rows).to_csv(os.path.join(OUT, 'stop_event_order_sequence.csv'), index=False)
    pd.DataFrame(post_rows).to_csv(os.path.join(OUT, 'post_stop_short_fills_classified.csv'), index=False)
    S = pd.DataFrame(summ).fillna(0); S.to_csv(os.path.join(OUT, 'stop_event_summary.csv'), index=False)
    print(f'fill-time inversion rate within number blocks: {inv_rate:.4f}')
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
    print(S.T.to_string())
    P = pd.DataFrame(post_rows); print(P.groupby('classification').agg(orders=('lots', 'size'), short_lots=('short_open_lots', 'sum'), cycles=('expiry', 'nunique')))
    print(P.groupby(['classification', 'next_buy_module']).size())


if __name__ == '__main__':
    main()
