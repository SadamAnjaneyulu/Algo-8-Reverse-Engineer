"""D-1 long side, L2: wing strike rule with option one-minute OHLC. Sample: simple D-1 wing buys (h_ open_long, 1 lot) with exactly one 1-lot body open_short on the same right in the previous [1.5, 10] s.
Reference = body decision price (limit / 0.85, 'ref_px') or body fill price. Candidate wing prices per OTM strike at the wing minute: previous close, minute open, minute low, minute high, and 'calibrated' (minute close of each strike x the chosen strike's decision price / its minute close: removes the common staleness of the minute bar).
Rules: nearest premium to k x ref; floor (most expensive strike with price <= k x ref, i.e. first strike moving OTM that is cheap enough); ceil (cheapest strike with price >= k x ref); sigma-distance (strike nearest S x (1 +/- z sigma sqrt T)); fixed offset from the sold strike.
k / z / offset chosen on one cycle half, scored on the other. Null: reference shuffled within the same 30-minute slot and right. Outputs bl_hg_strike.csv, bl_hg_strike_sample.csv, bl_summary_hg2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_sd_build, bl_ohlc
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OP = bl_sd_build.load_opt(); OH = bl_ohlc.load(); R = {}; rng = np.random.default_rng(0)
d1 = O[O.dayno == 0]; rows = []
for i, r in enumerate(CY.itertuples()):
    z = d1[(d1.und == r.und) & (d1.expiry == r.expiry)]; b = z[(z.module == 'num') & (z.role == 'open_short')]; w = z[(z.module == 'h_') & (z.role == 'open_long') & (z.lots == 1)]
    op = OP[(r.und, r.expiry)]; K = op['K']; st = ref.STEP[r.und]; c = OH[(r.und, r.expiry)].close.values
    for q in w.itertuples():
        bb = b[(b.cp == q.cp) & (b.te <= q.te - 1.5) & (b.te >= q.te - 10)]
        if len(bb) != 1 or bb.lots.iloc[0] != 1: continue
        j = min(max(int((q.te - 33300) // 60), 1), 374); o = bb.iloc[0]; sgn = 1 if q.cp == 'CE' else -1
        cand = np.where((sgn * (K - o.strike) > 0))[0]
        if not len(cand): continue
        kc = np.where(np.abs(K - q.strike) < 1)[0]
        if not len(kc): continue
        pr = {f: op[(q.cp, f)][cand, j] for f in ('open', 'high', 'low')}; pr['prevclose'] = op[(q.cp, 'close')][cand, j - 1]; pr['close'] = op[(q.cp, 'close')][cand, j]
        cc = op[(q.cp, 'close')][kc[0], j - 1]; pr['calibrated'] = pr['prevclose'] * (q.ref_px / cc) if cc > 0 else pr['prevclose'] * np.nan
        sg = (op[('CE', 'close')][np.argmin(np.abs(K - c[j - 1])), j - 1] + op[('PE', 'close')][np.argmin(np.abs(K - c[j - 1])), j - 1]) / (0.7979 * c[j - 1])
        rows.append(dict(cid=i, und=r.und, cp=q.cp, j=j, slot=(33300 + 60 * j) // 1800, wing=float(q.strike), sold=float(o.strike), body_ref=o.ref_px, body_fill=o.px_avg, wing_ref=q.ref_px, wing_fill=q.px_avg, spot=c[j - 1], sig=sg, step=st, K=K[cand], **{f'p_{f}': v for f, v in pr.items()}))
S = pd.DataFrame(rows); print('sample', len(S), 'cycles', S.cid.nunique()); S['ratio'] = S.wing_ref / S.body_ref
R['n'] = len(S); R['ratio_q'] = S.ratio.quantile([.1, .25, .5, .75, .9]).round(4).to_dict(); R['ratio_q_by_und'] = S.groupby('und').ratio.quantile([.25, .5, .75]).round(4).unstack().to_dict('index')
def pick(Kc, p, tgt, kind):
    m = ~np.isnan(p)
    if not m.any(): return np.nan
    Kc, p = Kc[m], p[m]
    if kind == 'nearest': return Kc[np.argmin(np.abs(p - tgt))]
    if kind == 'nearest_log': return Kc[np.argmin(np.abs(np.log(np.maximum(p, 1e-3) / tgt)))]
    if kind == 'floor':
        ok = p <= tgt; return Kc[ok][np.argmax(p[ok])] if ok.any() else np.nan
    if kind == 'ceil':
        ok = p >= tgt; return Kc[ok][np.argmin(p[ok])] if ok.any() else np.nan
def score(df, f, kind, k, refcol, shuffle=False):
    rf = df[refcol].values.copy()
    if shuffle: rf = df.groupby(['cid', 'slot', 'cp'])[refcol].transform(lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).values).values
    hits = []; near = []
    for x, rr in zip(df.itertuples(), rf):
        kk = pick(x.K, getattr(x, f'p_{f}'), k * rr, kind); hits.append(kk == x.wing); near.append(abs(kk - x.wing) <= x.step if kk == kk else False)
    return float(np.mean(hits)), float(np.mean(near))
KS = np.round(np.arange(0.015, 0.0401, 0.001), 4); res = []
halves = [S.cid % 2 == 0, S.cid % 2 == 1]
for refcol in ('body_ref', 'body_fill'):
    for f in ('prevclose', 'open', 'low', 'high', 'close', 'calibrated'):
        for kind in ('nearest', 'nearest_log', 'floor', 'ceil'):
            oof = []
            for h in (0, 1):
                tr, te = S[halves[h]], S[halves[1 - h]]
                kb = max(KS, key=lambda k: score(tr.sample(min(len(tr), 1500), random_state=1), f, kind, k, refcol)[0]); ex, nr = score(te, f, kind, kb, refcol); oof.append((kb, ex, nr, len(te)))
            n = sum(o[3] for o in oof); res.append(dict(reference=refcol, wing_price=f, rule=kind, k_fold=f'{oof[0][0]:.3f}/{oof[1][0]:.3f}', exact=sum(o[1] * o[3] for o in oof) / n, within1=sum(o[2] * o[3] for o in oof) / n))
            print(res[-1])
T = pd.DataFrame(res).sort_values('exact', ascending=False); best = T.iloc[0]
kb = float(best.k_fold.split('/')[0]); R['null_exact_best'] = score(S, best.wing_price, best.rule, kb, best.reference, shuffle=True)[0]
# sigma-distance and fixed-offset rules (out-of-fold)
def sig_score(df, zz):
    t = df.spot * (1 + np.where(df.cp == 'CE', 1, -1) * zz * df.sig); kk = [x.K[np.argmin(np.abs(x.K - tt))] for x, tt in zip(df.itertuples(), t)]; kk = np.array(kk); return float((kk == df.wing).mean()), float((np.abs(kk - df.wing) <= df.step).mean())
def off_score(df, n):
    kk = df.sold + np.where(df.cp == 'CE', 1, -1) * n * df.step; return float((kk == df.wing).mean()), float((np.abs(kk - df.wing) <= df.step).mean())
for nm, fn, grid in (('sigma distance z', sig_score, np.round(np.arange(0.5, 4.01, 0.05), 2)), ('fixed offset from sold strike (steps)', off_score, range(3, 30))):
    oof = []
    for u in ('NIFTY', 'SENSEX'):
        for h in (0, 1):
            tr, te = S[halves[h] & (S.und == u)], S[halves[1 - h] & (S.und == u)]; g = max(grid, key=lambda v: fn(tr, v)[0]); ex, nr = fn(te, g); oof.append((ex, nr, len(te)))
    n = sum(o[2] for o in oof); res.append(dict(reference='spot', wing_price='-', rule=nm, k_fold='per und, out-of-fold', exact=sum(o[0] * o[2] for o in oof) / n, within1=sum(o[1] * o[2] for o in oof) / n))
T = pd.DataFrame(res).sort_values('exact', ascending=False); T.round(4).to_csv(f'{OUT}/bl_hg_strike.csv', index=False); S.drop(columns=['K'] + [c for c in S.columns if c.startswith('p_')]).to_csv(f'{OUT}/bl_hg_strike_sample.csv', index=False)
print(T.head(12).round(3).to_string(index=False)); print(T.tail(4).round(3).to_string(index=False)); R['table'] = T.round(4).to_dict('records'); print('null', R['null_exact_best'], R['ratio_q']); rec('hg2', R)
