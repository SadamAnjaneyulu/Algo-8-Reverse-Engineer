"""Decision-level confirmation (post-hoc, added to the counted tests): the engine ladder (algo8_d1.ladder_fires) with its extreme gate G in {5,10,15,30,60} minutes, run on each
candidate underlying; reference = the underlying close before the latest REAL sale on that side (teacher-forced, causal). Score: precision/recall of predicted (minute, side)
vs real late sales in 15:15-15:40 (+-1 minute), cycles whole. G chosen leave-one-cycle-out by F1 per underlying vs fixed G=60 (the engine). Null: random minutes with the same count.
Output outputs/trig/ladder_scores.csv, ladder_loco.csv."""
import sys, os, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
import bl_bt3_sim as S, bl_d0x_diag as DG, algo8_d1 as A
OUT = S.OUT; TR = f'{OUT}/trig'; GS = [5, 10, 15, 30, 60]; CAS = '2026-08-03'; OUTLIER = ('NIFTY', '2026-10-16'); RNG = np.random.default_rng(5)
def match(pred, real):
    tp = sum(1 for x in pred if any((x[0] + d, x[1]) in real for d in (-1, 0, 1))); hit = sum(1 for x in real if any((x[0] + d, x[1]) in pred for d in (-1, 0, 1))); return tp, len(pred), hit, len(real)
if __name__ == '__main__':
    O = DG.real_orders(); O = O.assign(jj=(O.t_last // 60 - 555).astype(int)); T = pd.read_csv(f'{OUT}/bl_bt3_cycles.csv'); T = T[T.ok]; B = pd.read_csv(f'{OUT}/d0x/book_compare.csv'); keep = set(zip(B.und, B.expiry)); rows = []
    for r in T.itertuples():
        if (r.und, r.expiry) not in keep or (r.und, r.d1) == OUTLIER: continue
        post = r.d0 >= CAS; g = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 0) & (O.role == 'open_short')]; jmax = 384 if post else 374
        ev = {cp: sorted(set(g[g.cp == cp].jj.tolist())) for cp in ('CE', 'PE')}; real = {(int(j), cp) for j, cp in zip(g.jj, g.cp) if 360 <= j <= jmax}
        cx = pd.read_pickle(f'{OUT}/bt3x/{r.und}_{r.expiry}.pkl.gz'); U = {'FEED': cx['spot1']}
        if post: U['FUT'] = pd.read_pickle(f'{OUT}/bt3u/{r.und}_{r.expiry}.pkl.gz')['spot1']; U['OPT'] = pd.read_pickle(f'{OUT}/bt3s/{r.und}_{r.expiry}.pkl.gz')['spot1']
        for nm, s in U.items():
            h, l, c = (s[k].values.astype(float) for k in ('high', 'low', 'close'))
            for G in GS:
                cfg = A.Config(); cfg.ladder_gate_min = G; cfg.strike_step = 50.0 if r.und == 'NIFTY' else 100.0
                lad = A.ladder_fires(c, h, l, ev, cfg); pred = {(j, cp) for j, cps in lad.items() for cp in cps if 360 <= j <= jmax}; tp, npred, hit, nreal = match(pred, real)
                rnd = [];
                for _ in range(200):
                    rp = {(int(j), cp) for j, cp in zip(RNG.integers(360, jmax + 1, npred), RNG.choice(['CE', 'PE'], npred))} if npred else set(); a = match(rp, real); rnd.append((a[0], a[2]))
                rows.append(dict(und=r.und, expiry=r.expiry, era='after' if post else 'before', underlying=nm, G=G, tp=tp, npred=npred, hit=hit, nreal=nreal, rnd_tp=np.mean([x[0] for x in rnd]), rnd_hit=np.mean([x[1] for x in rnd])))
    D = pd.DataFrame(rows); D.to_csv(f'{TR}/ladder_scores.csv', index=False)
    def f1(g):
        p = g.tp.sum() / max(g.npred.sum(), 1); rc = g.hit.sum() / max(g.nreal.sum(), 1); return p, rc, (2 * p * rc / (p + rc) if p + rc else 0)
    out = []
    for (era, u), g in D.groupby(['era', 'underlying']):
        cyc = g[['und', 'expiry']].drop_duplicates().apply(tuple, axis=1).tolist(); picks = []; oof = []
        for held in cyc:
            tr = g[~((g.und == held[0]) & (g.expiry == held[1]))]; best = max(GS, key=lambda G: f1(tr[tr.G == G])[2]); picks.append(best); oof.append(g[(g.und == held[0]) & (g.expiry == held[1]) & (g.G == best)])
        o = pd.concat(oof); p, rc, F = f1(o); p60, rc60, F60 = f1(g[g.G == 60])
        rb = []; 
        for _ in range(1000):
            d = RNG.integers(0, len(cyc), len(cyc)); sel = [cyc[i] for i in d]; a = pd.concat([o[(o.und == c[0]) & (o.expiry == c[1])] for c in sel]); b = pd.concat([g[(g.und == c[0]) & (g.expiry == c[1]) & (g.G == 60)] for c in sel]); rb.append(f1(a)[2] - f1(b)[2])
        row = dict(era=era, underlying=u, cycles=len(cyc), real_events=int(g[g.G == 60].nreal.sum()), loco_G=str(sorted(pd.Series(picks).value_counts().to_dict().items())), loco_precision=p, loco_recall=rc, loco_F1=F, G60_precision=p60, G60_recall=rc60, G60_F1=F60,
                   dF1=F - F60, dF1_lo=float(np.quantile(rb, .025)), dF1_hi=float(np.quantile(rb, .975)), rnd_precision=g[g.G == 60].rnd_tp.sum() / max(g[g.G == 60].npred.sum(), 1), rnd_recall=g[g.G == 60].rnd_hit.sum() / max(g[g.G == 60].nreal.sum(), 1))
        for G in GS: _p, _r, _f = f1(g[g.G == G]); row[f'F1_G{G}'] = _f; row[f'prec_G{G}'] = _p; row[f'rec_G{G}'] = _r
        out.append(row)
    L = pd.DataFrame(out); L.to_csv(f'{TR}/ladder_loco.csv', index=False); pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40); print(L.round(3).T.to_string())
