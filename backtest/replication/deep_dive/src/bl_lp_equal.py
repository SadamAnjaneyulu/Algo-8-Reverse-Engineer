"""Lump study step 5 (POST-HOC, margin-equalisation hypothesis): the whole book's scenario P&L (marks -> expiry intrinsic) over a spot grid in BOTH directions (0-R%), R = 3, 4, 6%.
H: the lump (heavy side) is sized so that worst loss in the heavy direction (after the lump) ~= worst loss in the light direction, i.e. the two tails are equalised (what a SPAN-style margin, = max of the two tails, rewards).
Predicted lots = smallest n (at the actual lump strike and price) with worst_heavy(n) >= worst_light; compared with the actual lots (exact, within 5 lots, median abs error %). Output bl_lp_equal.csv, bl_summary_lp5.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import spearmanr
import bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OP = bl_sd_build.load_opt(); D = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); B = pd.read_pickle(f'{OUT}/bl_lp_book.pkl.gz'); R = {}; rows = []
for x in D[D.main == 1].itertuples():
    r = CY.iloc[x.cid]; op = OP[(r.und, r.expiry)]; K = op['K']; j = min(int((x.t - 33300) // 60), 374); bk = B[(x.cid, x.dec)]; sg = 1 if x.cp == 'CE' else -1
    def px(cp, k):
        w = np.where(np.abs(K - k) < 1)[0]; return op[(cp, 'close')][w[0], j - 1] if len(w) else 0.0
    pos = [(cp, k, n, px(cp, k)) for cp in ('CE', 'PE') for k, n in bk[cp]]
    def pnl(ST, n=0):
        p = sum(m * ((max(0, ST - k) if cp == 'CE' else max(0, k - ST)) - mk) for cp, k, m, mk in pos)
        p += n * ((max(0, ST - x.strike) if x.cp == 'CE' else max(0, x.strike - ST)) - x.px); return p * r.unit
    d = dict(cid=x.cid, und=x.und, y=x.lots)
    for Rg in (3, 4, 6):
        gh = x.spot * (1 + sg * np.linspace(0, Rg / 100, 121)); gl = x.spot * (1 - sg * np.linspace(0, Rg / 100, 121))
        wl = min(pnl(s) for s in gl); wh = lambda n: min(pnl(s, n) for s in gh)
        n = 0
        while wh(n) < wl and n < 400: n += 1
        d[f'worst_light_{Rg}'] = wl; d[f'worst_heavy_pre_{Rg}'] = wh(0); d[f'worst_heavy_post_{Rg}'] = wh(x.lots); d[f'pred_{Rg}'] = n
    rows.append(d)
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_lp_equal.csv', index=False)
for Rg in (3, 4, 6):
    e = (X[f'pred_{Rg}'] - X.y).abs(); R[f'R{Rg}'] = dict(exact=float((e == 0).mean()), within5=float((e <= 5).mean()), within10=float((e <= 10).mean()), median_abs_err_pct=float((e / X.y.clip(lower=1)).median() * 100), spearman=float(spearmanr(X[f'pred_{Rg}'], X.y)[0]), post_over_light_median=float((X[f'worst_heavy_post_{Rg}'] / X[f'worst_light_{Rg}']).median()))
    print(Rg, {k: round(v, 3) for k, v in R[f'R{Rg}'].items()})
print(X[['cid', 'und', 'y', 'pred_3', 'pred_4', 'pred_6', 'worst_light_4', 'worst_heavy_pre_4', 'worst_heavy_post_4']].round(0).to_string(index=False)); rec('lp5', R)
