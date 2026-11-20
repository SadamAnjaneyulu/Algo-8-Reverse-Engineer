"""H1 (independent re-implementation, order level): lag structure between body orders and opposite-side hedge orders on the same right; 1:1 lot matching; null by time shifts.
Outputs: outputs/bh_h1_lag_hist.csv, bh_h1_body_lots.csv (one row per body lot with matched wing), bh_h1_wing_lots.csv."""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); B = O[O.module == 'num'].copy(); W = O[O.module == 'h_'].copy()
BIN = 0.5; EDGES = np.arange(-5, 20.0001, BIN)
hist = np.zeros(len(EDGES) - 1); null = np.zeros(len(EDGES) - 1); SH = [137, -211, 389, -523]
bl = []; wl = []
for (u, e, cp), b in B.groupby(['und', 'expiry', 'cp']):
    w = W[(W.und == u) & (W.expiry == e) & (W.cp == cp)]
    for d in (0, 1):
        bb = b[b.dayno == d].sort_values(['tt_first', 'row']); ww = w[w.dayno == d].sort_values('tt_dec')
        if not len(bb) or not len(ww): continue
        for sb, sw in (('Sell', 'Buy'), ('Buy', 'Sell')):
            b2 = bb[bb.side == sb]; w2 = ww[ww.side == sw]
            if not len(b2) or not len(w2): continue
            tw = w2.tt_dec.values; tb = b2.tt_first.values
            for shift, acc in [(0, hist)] + [(s, null) for s in SH]:
                tws = tw + shift
                for t in tb:
                    lo = np.searchsorted(tws, t + EDGES[0]); hi = np.searchsorted(tws, t + EDGES[-1])
                    if hi > lo: acc += np.histogram(tws[lo:hi] - t, bins=EDGES)[0]
H = pd.DataFrame({'lag_lo': EDGES[:-1], 'lag_hi': EDGES[1:], 'real': hist, 'null_per_shift': null / len(SH)}); H.to_csv(f'{OUT}/bh_h1_lag_hist.csv', index=False)
print(H[(H.lag_lo >= -2) & (H.lag_lo < 10)].round(2).to_string(index=False))


def match(B, W, lo, hi):
    """greedy 1:1 lot matching per (und,expiry,cp,day,direction): each body lot (time order) takes the earliest unmatched opposite-side wing lot whose decision stamp lies in [t_body+lo, t_body+hi]; t_body = first fill second."""
    BL = []; WL = []
    for (u, e, cp, d), b in B.groupby(['und', 'expiry', 'cp', 'dayno']):
        w = W[(W.und == u) & (W.expiry == e) & (W.cp == cp) & (W.dayno == d)]
        for sb, sw in (('Sell', 'Buy'), ('Buy', 'Sell')):
            b2 = b[b.side == sb].sort_values(['tt_first', 'row']); w2 = w[w.side == sw].sort_values('tt_dec')
            wt = np.repeat(w2.tt_dec.values, w2.lots.values); wtag = np.repeat(w2.tag.values, w2.lots.values); used = np.zeros(len(wt), bool); bt = np.repeat(b2.tt_first.values, b2.lots.values); btag = np.repeat(b2.tag.values, b2.lots.values)
            for t, tg in zip(bt, btag):
                cand = np.where((~used) & (wt >= t + lo) & (wt <= t + hi))[0]
                if len(cand): k = cand[0]; used[k] = True; BL.append((tg, u, e, cp, d, sb, t, True, wt[k] - t, wtag[k]))
                else: BL.append((tg, u, e, cp, d, sb, t, False, np.nan, None))
            for k in range(len(wt)): WL.append((wtag[k], u, e, cp, d, sw, wt[k], bool(used[k])))
    BL = pd.DataFrame(BL, columns=['tag', 'und', 'expiry', 'cp', 'dayno', 'side', 'tt', 'matched', 'lag', 'wing_tag']); WL = pd.DataFrame(WL, columns=['tag', 'und', 'expiry', 'cp', 'dayno', 'side', 'tt', 'matched'])
    return BL, WL


if __name__ == '__main__':
    res = []
    for lo, hi in ((1.5, 10), (1.5, 20), (0, 30), (1.5, 60)):
        BL, WL = match(B, W, lo, hi)
        res.append(dict(window=f'[{lo},{hi}] s', body_lots=len(BL), matched_share=BL.matched.mean().round(4), wing_lots=len(WL), wing_matched_share=WL.matched.mean().round(4)))
        if (lo, hi) == (1.5, 20): BL.to_csv(f'{OUT}/bh_h1_body_lots.csv', index=False); WL.to_csv(f'{OUT}/bh_h1_wing_lots.csv', index=False); m = BL[BL.matched]
    W2 = W.copy(); W2['cp'] = W2.cp.map({'CE': 'PE', 'PE': 'CE'}); BLn, WLn = match(B, W2, 1.5, 20); res.append(dict(window='[1.5,20] s, WRONG-RIGHT null', body_lots=len(BLn), matched_share=BLn.matched.mean().round(4), wing_lots=len(WLn), wing_matched_share=WLn.matched.mean().round(4)))
    pd.DataFrame(res).to_csv(f'{OUT}/bh_h1_windows.csv', index=False); print(pd.DataFrame(res).to_string(index=False))
    print('lag of matched (window 1.5-20): quantiles', m.lag.quantile([.05, .25, .5, .75, .95]).round(2).tolist())
    BL = pd.read_csv(f'{OUT}/bh_h1_body_lots.csv'); WL = pd.read_csv(f'{OUT}/bh_h1_wing_lots.csv')
    print(BL.groupby(['dayno', 'side']).matched.agg(['size', 'mean']).round(3)); print(WL.groupby(['dayno', 'side']).matched.agg(['size', 'mean']).round(3))
