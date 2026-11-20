"""H5 lifecycle (contract level, ownership-free).
(1) overnight state per (cycle, right): at the end of D-1 (all events with dayno 0) S, L, and net lots from v_ (lump) orders; test L - S == lump lots.
(2) what is released: for every h_ SELL that reduces a long, rank of the sold strike among currently-long strikes by (a) entry time (oldest=1), (b) price, (c) distance from the nearest short strike.
(3) end of cycle: residual S and L at the last event of D0 by cycle and right.
Outputs outputs/bh_h5_overnight.csv, bh_h5_release_rank.csv, bh_h5_endstate.csv"""
import sys; sys.path.insert(0, '.')
from bh_common import *
X = fills_x(); O = order_table(X); bk = Bd = None
O['te'] = np.where(O.module.isin(['h_', 's_', 'v_', 'm_']), O.tt_dec, O.tt_first); O['sl'] = np.where(O.side == 'Buy', O.lots, -O.lots)
ov = []; end = []
for (u, e, cp), o in O.groupby(['und', 'expiry', 'cp']):
    comp = bool(o.complete.iloc[0]); o = o.sort_values(['te', 'row']); d1 = o[o.dayno == 0]
    def SL(oo):
        n = oo.groupby('strike').sl.sum(); return -n[n < 0].sum(), n[n > 0].sum()
    S1, L1 = SL(d1); v = d1[d1.module == 'v_'].sl.sum(); ov.append((u, e, cp, comp, len(d1) > 0, S1, L1, L1 - S1, v))
    S2, L2 = SL(o); end.append((u, e, cp, comp, S2, L2, S2 - L2))
OV = pd.DataFrame(ov, columns=['und', 'expiry', 'cp', 'complete', 'has_d1', 'S_end_d1', 'L_end_d1', 'L_minus_S', 'lump_lots']); OV.to_csv(f'{OUT}/bh_h5_overnight.csv', index=False)
x = OV[OV.complete & OV.has_d1]; print('(1) cycles x rights', len(x), ': L-S == lump lots', (x.L_minus_S == x.lump_lots).mean().round(3), ' | L-S>0', (x.L_minus_S > 0).mean().round(3), ' | median L-S', x.L_minus_S.median(), ' median lump', x.lump_lots.median(), ' corr', np.corrcoef(x.L_minus_S, x.lump_lots)[0, 1].round(3))
EN = pd.DataFrame(end, columns=['und', 'expiry', 'cp', 'complete', 'S_end', 'L_end', 'gap_end']); EN.to_csv(f'{OUT}/bh_h5_endstate.csv', index=False)
x = EN[EN.complete]; print('(3) end of cycle (complete-carry): rights', len(x), ' flat (S=L=0)', ((x.S_end == 0) & (x.L_end == 0)).mean().round(3), ' S==L', (x.gap_end == 0).mean().round(3), ' residual shorts>0', (x.S_end > 0).mean().round(3), ' residual longs>0', (x.L_end > 0).mean().round(3))
# (2) release ranking
rr = []
for (u, e, cp), o in O.groupby(['und', 'expiry', 'cp']):
    o = o.sort_values(['te', 'row']); net = {}; t_in = {}; 
    for r in o.itertuples():
        if r.module == 'h_' and r.side == 'Sell' and net.get(r.strike, 0) > 0:
            longs = [k for k, v in net.items() if v > 0]
            if len(longs) >= 2:
                ks = sorted(longs); tin = np.array([t_in[k] for k in ks]); rk_old = (tin < t_in[r.strike]).sum() + 1; rk_out = (np.array(ks) > r.strike).sum() + 1 if cp == 'CE' else (np.array(ks) < r.strike).sum() + 1
                shorts = [k for k, v in net.items() if v < 0]; rr.append((u, e, cp, r.dayno, len(longs), rk_old, rk_out, r.strike))
        k = r.strike; n0 = net.get(k, 0); net[k] = n0 + r.sl
        if r.sl > 0 and n0 <= 0: t_in[k] = r.te
RR = pd.DataFrame(rr, columns=['und', 'expiry', 'cp', 'dayno', 'n_long_strikes', 'rank_oldest', 'rank_outermost', 'strike']); RR.to_csv(f'{OUT}/bh_h5_release_rank.csv', index=False)
print('(2) wing sells with >=2 long strikes held', len(RR), ': sold the OLDEST long', (RR.rank_oldest == 1).mean().round(3), ' sold the NEWEST', (RR.rank_oldest == RR.n_long_strikes).mean().round(3), ' sold the OUTERMOST', (RR.rank_outermost == 1).mean().round(3), ' sold the INNERMOST', (RR.rank_outermost == RR.n_long_strikes).mean().round(3), ' mean n longs', RR.n_long_strikes.mean().round(1))
exp_old = (1 / RR.n_long_strikes).mean(); print('   chance level for any one rank (mean of 1/n) = %.3f' % exp_old)

# (2b) release rank by current price and by lot-weighted holdings (chain price at j-1 close)
ch = Chain(); rp = []
for (u, e, cp), o in O.groupby(['und', 'expiry', 'cp']):
    o = o.sort_values(['te', 'row']); net = {}
    for r in o.itertuples():
        if r.module == 'h_' and r.side == 'Sell' and net.get(r.strike, 0) > 0:
            longs = [k for k, v in net.items() if v > 0]
            if len(longs) >= 2:
                j = int(np.floor((r.te % 100000 - ref.OPEN_SEC) / 60)); p = {k: ch.px(u, e, r.dayno, cp, k, j - 1, 'close') for k in longs}
                if not any(np.isnan(v) for v in p.values()):
                    rk = sorted(longs, key=lambda k: -p[k]).index(r.strike) + 1; rp.append((rk, len(longs), net[r.strike], max(net[k] for k in longs)))
        net[r.strike] = net.get(r.strike, 0) + r.sl
P = pd.DataFrame(rp, columns=['rank_price_desc', 'n', 'lots_held_at_strike', 'max_lots_held'])
P.to_csv(f'{OUT}/bh_h5_release_price_rank.csv', index=False); print('(2b) n', len(P), ': sold the HIGHEST-priced long', (P.rank_price_desc == 1).mean().round(3), ' the LOWEST-priced', (P.rank_price_desc == P.n).mean().round(3), ' chance', (1 / P.n).mean().round(3), '; sold the strike with the MOST lots held', (P.lots_held_at_strike == P.max_lots_held).mean().round(3))
