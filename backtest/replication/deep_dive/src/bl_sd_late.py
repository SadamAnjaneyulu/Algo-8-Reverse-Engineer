"""Solo decode: after-15:00 regime vs intraday (side relative to the book's heavier side, favourable move since the open, buy-back replacement, minute profile). Output bl_summary_sd10.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
D = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); X = pd.read_pickle(f'{OUT}/bl_sd_tilt.pkl.gz'); R = {}
S = D[(D.typ == 'solo') & ~D.deep].copy(); S['late'] = S.te >= 54000; rows = []
for r in S.itertuples():
    x = X[(X.cid == r.cid) & (X.j == min(max(r.j, 2), 374))]
    if not len(x): continue
    x = x.iloc[0]; own = x.ce if r.cp == 'CE' else x.pe; oth = x.pe if r.cp == 'CE' else x.ce; cy = CY.iloc[r.cid]; z = O[(O.und == cy.und) & (O.expiry == cy.expiry) & (O.dayno == 0)]
    cov = z[(z.role == 'cover_short') & (z.cp == r.cp) & (z.te <= r.te) & (z.te >= r.te - 120)]
    rows.append(dict(late=r.late, heavier=int(own > oth), move_fav=(x.move if r.cp == 'CE' else -x.move), after_buyback=int(len(cov) > 0)))
Z = pd.DataFrame(rows)
for k, g in Z.groupby('late'): R['late' if k else 'intraday'] = dict(n=len(g), heavier_share=float(g.heavier.mean()), median_fav_move=float(g.move_fav.median()), after_buyback_share=float(g.after_buyback.mean()))
L = S[S.late]; R['late_minute_profile'] = np.bincount(((L.te - 54000) // 60).astype(int).clip(0, 35), minlength=36).tolist(); print(R); rec('sd10', R)
