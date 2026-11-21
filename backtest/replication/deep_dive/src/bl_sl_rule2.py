"""After-15:00 solo, step 7 (POST-HOC rule check, no fitted parameter): minute rules on the late panel scored with +-1 minute tolerance per (cycle, right):
R1 spot fresh 15-min extreme on the right (same minute, true OHLC); R2 sold-side ITM option premium fresh 15-min low (same minute); R3 = R1 OR R2; causal variants use minute j-1.
Lot-level coverage of late solo lots by E (spot extreme), premium low of the sold contract, cross-right buy-back within 10 s. Outputs bl_sl_rule2.csv, bl_summary_sl7.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc, bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); sol = D[(D.typ == 'solo') & ~D.deep]; R = {}
src = open('bl_sl_prem.py').read(); exec(src[src.index('def panel'):src.index('def auc')])
P = panel(345, 375).fillna(0)
def score(sub, col):
    tp = hit = nf = npos = 0
    for _, g in sub.groupby(['cid', 'cp']):
        f = set(g.j[g[col] == 1]); p = set(g.j[g.y == 1]); nf += len(f); npos += len(p); tp += sum(1 for j in f if {j - 1, j, j + 1} & p); hit += sum(1 for j in p if {j - 1, j, j + 1} & f)
    pr = tp / max(nf, 1); rc = hit / max(npos, 1); return dict(rule=col, fires=nf, positives=npos, precision=pr, recall=rc, F1=2 * pr * rc / max(pr + rc, 1e-9))
P['R3'] = ((P.bk15 == 1) | (P.pl15_itm == 1)).astype(int); P['R3_prev'] = ((P.bk15_prev == 1) | (P.pl15_itm_prev == 1)).astype(int)
T = pd.DataFrame([score(P, c) for c in ('bk15', 'pl15_itm', 'R3', 'bk15_prev', 'pl15_itm_prev', 'R3_prev')]); T.round(3).to_csv(f'{OUT}/bl_sl_rule2.csv', index=False); print(T.round(3).to_string(index=False)); R['rules'] = T.round(4).to_dict('records')
Z = pd.read_csv(f'{OUT}/bl_sl_class.csv'); pl = Z.prem_newlow15.fillna(False).astype(bool); E_ = Z.E.astype(bool); B_ = (Z.Bb | Z.Ba).astype(bool)
cov = {'spot extreme (E)': E_, 'E or premium low': E_ | pl, 'E or premium low or cross-right buy-back +-10 s': E_ | pl | B_}
R['lot_coverage'] = {k: float(Z.lots[v].sum() / Z.lots.sum()) for k, v in cov.items()}; R['lots'] = int(Z.lots.sum()); print(R['lot_coverage']); rec('sl7', R)
