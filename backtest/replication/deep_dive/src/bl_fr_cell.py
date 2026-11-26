"""Free-running D-1: cell-level agreement (cycle x minute x right): does the simulation have any order of a class / any order at all in the same minute (and within +-1 minute) as the real ledger?
Output bl_fr_cell.csv, bl_summary_fr2.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_fr_sim as S
CY, REAL = S.CY, S.REAL; OA = pd.read_pickle(f'{OUT}/bl_fr_orders.pkl.gz')['FR free-running (primary)']; R = {}
CLASS = {('num', 'open_short'): 'body_sell', ('num', 'cover_short'): 'body_buyback', ('h_', 'open_long'): 'wing_buy', ('h_', 'close_long'): 'wing_sell', ('num', 'open_long'): 'opening_wings', ('v_', 'open_long'): 'lump'}
REAL['cls'] = [CLASS.get((m, r_), 'not_modelled') for m, r_ in zip(REAL.module, REAL.role)]; REAL.loc[(REAL.cls == 'opening_wings') & (REAL.j > 2), 'cls'] = 'not_modelled'
def cells(df, cls=None):
    if cls: df = df[df.cls == cls]
    return set(zip(df.cid, df.cp, df.j))
rows = []
for cls in ['body_sell', 'body_buyback', 'wing_buy', 'wing_sell', 'opening_wings', 'lump', 'any']:
    tp0 = tp1 = nr = ns = 0; hit_s1 = 0
    for i, r in enumerate(CY.itertuples()):
        z = REAL[(REAL.und == r.und) & (REAL.expiry == r.expiry)].copy(); z['cid'] = i; o = OA[i]
        rc = cells(z, None if cls == 'any' else cls); sc = cells(o, None if cls == 'any' else cls) if len(o) else set()
        if cls == 'any': rc = cells(z[z.cls != 'not_modelled']) | cells(z[z.cls == 'not_modelled'])
        nr += len(rc); ns += len(sc); tp0 += len(rc & sc)
        near = lambda c, S_: any((c[0], c[1], c[2] + d) in S_ for d in (-1, 0, 1)); tp1 += sum(1 for c in rc if near(c, sc)); hit_s1 += sum(1 for c in sc if near(c, rc))
    rows.append(dict(cls=cls, real_cells=nr, sim_cells=ns, P_exact=tp0 / ns if ns else np.nan, R_exact=tp0 / nr, F1_exact=2 * tp0 / (ns + nr), P_pm1=hit_s1 / ns if ns else np.nan, R_pm1=tp1 / nr, F1_pm1=2 * (hit_s1 / ns) * (tp1 / nr) / max(hit_s1 / ns + tp1 / nr, 1e-9) if ns else np.nan))
T = pd.DataFrame(rows); T.round(4).to_csv(f'{OUT}/bl_fr_cell.csv', index=False); print(T.round(3).to_string(index=False)); rec('fr2', dict(table=T.round(4).to_dict('records')))
