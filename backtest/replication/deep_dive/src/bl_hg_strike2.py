"""D-1 long side, L2b (POST-HOC): alternative reference prices for the wing strike (calibrated nearest rule, k out-of-fold): ATM same-right price, sold option price at the wing minute (close/open), half the ATM straddle; and the per-slot null. Outputs bl_hg_strike2.csv, bl_summary_hg2b.json"""

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
        atmk = np.argmin(np.abs(K - c[j - 1])); kso = np.where(np.abs(K - o.strike) < 1)[0]
        rows.append(dict(atm_px=op[(q.cp, 'close')][atmk, j - 1], body_now=(op[(q.cp, 'close')][kso[0], j] if len(kso) else np.nan), body_open=(op[(q.cp, 'open')][kso[0], j] if len(kso) else np.nan), straddle=op[('CE', 'close')][atmk, j - 1] + op[('PE', 'close')][atmk, j - 1], cid=i, und=r.und, cp=q.cp, j=j, slot=(33300 + 60 * j) // 1800, wing=float(q.strike), sold=float(o.strike), body_ref=o.ref_px, body_fill=o.px_avg, wing_ref=q.ref_px, wing_fill=q.px_avg, spot=c[j - 1], sig=sg, step=st, K=K[cand], **{f'p_{f}': v for f, v in pr.items()}))
S = pd.DataFrame(rows); S['half_straddle'] = S.straddle / 2
def pick(Kc, p, tgt):
    m = ~np.isnan(p); return Kc[m][np.argmin(np.abs(np.log(np.maximum(p[m], 1e-3) / tgt)))] if m.any() else np.nan
def score(df, k, refcol, shuffle=False):
    rf = df[refcol].values
    if shuffle: rf = df.groupby(['cid', 'slot', 'cp'])[refcol].transform(lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).values).values
    kk = np.array([pick(x.K, x.p_calibrated, k * rr) for x, rr in zip(df.itertuples(), rf)]); return float(np.mean(kk == df.wing)), float(np.mean(np.abs(kk - df.wing) <= df.step))
halves = [S.cid % 2 == 0, S.cid % 2 == 1]; res = []
for refcol, KS in (('body_fill', np.arange(0.015, 0.0401, 0.001)), ('body_ref', np.arange(0.015, 0.0401, 0.001)), ('body_now', np.arange(0.015, 0.0401, 0.001)), ('body_open', np.arange(0.015, 0.0401, 0.001)), ('atm_px', np.arange(0.005, 0.0601, 0.001)), ('half_straddle', np.arange(0.005, 0.0601, 0.001))):
    oof = []
    for h in (0, 1):
        tr, te = S[halves[h]].dropna(subset=[refcol]), S[halves[1 - h]].dropna(subset=[refcol]); kb = max(KS, key=lambda k: score(tr, k, refcol)[0]); ex, nr = score(te, kb, refcol); oof.append((kb, ex, nr, len(te)))
    n = sum(o[3] for o in oof); kb = oof[0][0]; nl = score(S.dropna(subset=[refcol]), kb, refcol, shuffle=True)[0]
    res.append(dict(reference=refcol, k_fold=f"{oof[0][0]:.3f}/{oof[1][0]:.3f}", exact=sum(o[1] * o[3] for o in oof) / n, within1=sum(o[2] * o[3] for o in oof) / n, null_same_slot_exact=nl)); print(res[-1])
T = pd.DataFrame(res).sort_values('exact', ascending=False); T.round(4).to_csv(f'{OUT}/bl_hg_strike2.csv', index=False); print(T.round(3).to_string(index=False)); rec('hg2b', dict(table=T.round(4).to_dict('records')))
