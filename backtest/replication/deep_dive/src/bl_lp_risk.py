"""Lump study step 2 (POST-HOC risk-budget test): at each main lump decision, P&L of the whole book (both rights, all strikes, all modules) from the current marks to expiry intrinsic, over a spot grid in the heavy direction (0 to 6% move), before and after adding the lump (main decision lots at its strike, at its price).
If the lump is sized to cap the worst-case loss, the after-lump worst loss (or the loss at a fixed gap) should be nearly constant across cycles while the before-lump one is not.
Outputs bl_lp_risk.csv, bl_summary_lp2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OP = bl_sd_build.load_opt(); D = pd.read_csv(f'{OUT}/bl_lp_dec.csv'); B = pd.read_pickle(f'{OUT}/bl_lp_book.pkl.gz'); R = {}; rows = []
for x in D[D.main == 1].itertuples():
    r = CY.iloc[x.cid]; op = OP[(r.und, r.expiry)]; K = op['K']; j = min(int((x.t - 33300) // 60), 374); bk = B[(x.cid, x.dec)]; sg = 1 if x.cp == 'CE' else -1
    def px(cp, k):
        w = np.where(np.abs(K - k) < 1)[0]; return op[(cp, 'close')][w[0], j - 1] if len(w) else 0.0
    pos = [(cp, k, n, px(cp, k)) for cp in ('CE', 'PE') for k, n in bk[cp]]
    grid = x.spot * (1 + sg * np.linspace(0, 0.06, 241))
    def pnl(ST, extra=None):
        p = sum(n * ((max(0, ST - k) if cp == 'CE' else max(0, k - ST)) - m) for cp, k, n, m in pos)
        if extra: cp, k, n, m = extra; p += n * ((max(0, ST - k) if cp == 'CE' else max(0, k - ST)) - m)
        return p * r.unit
    pre = np.array([pnl(s) for s in grid]); post = np.array([pnl(s, (x.cp, x.strike, x.lots, x.px)) for s in grid])
    g = lambda arr, pc: float(np.interp(pc, np.linspace(0, 6, 241), arr))
    rows.append(dict(cid=x.cid, und=x.und, lots=x.lots, S_h=x.S_h, worst_pre=float(pre.min()), worst_post=float(post.min()), argworst_pre_pct=float(np.linspace(0, 6, 241)[pre.argmin()]), argworst_post_pct=float(np.linspace(0, 6, 241)[post.argmin()]),
                     **{f'pre_{p}': g(pre, p) for p in (1, 1.5, 2, 2.5, 3, 4)}, **{f'post_{p}': g(post, p) for p in (1, 1.5, 2, 2.5, 3, 4)}, lump_otm_pct=x.otm_pct, pnl_now=0.0))
X = pd.DataFrame(rows); X.to_csv(f'{OUT}/bl_lp_risk.csv', index=False)
cv = lambda s: float(s.std() / abs(s.mean()))
R['cv'] = {c: cv(X[c]) for c in X.columns if c.startswith(('worst', 'pre_', 'post_'))}; R['median'] = {c: float(X[c].median()) for c in R['cv']}
print(pd.DataFrame({'median_rs': R['median'], 'cv': R['cv']}).round(2).to_string())
print(X[['cid', 'und', 'lots', 'S_h', 'worst_pre', 'worst_post', 'argworst_pre_pct', 'argworst_post_pct', 'pre_2', 'post_2']].round(0).to_string(index=False)); rec('lp2', R)
