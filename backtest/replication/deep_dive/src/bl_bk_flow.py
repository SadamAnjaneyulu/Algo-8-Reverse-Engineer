"""Book-state study step 4 (H5): order flow around the reactive pairs - share of reactive pairs vs random control seconds that have an order of each module/role/leg in a window before / after. Outputs bl_bk_flow.csv, bl_summary_bk3.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); B = pd.read_pickle(f'{OUT}/bl_bk_S.pkl.gz'); O1 = O[O.dayno == 0].copy(); O1['kind'] = O1.module + ' | ' + O1.role + ' | ' + O1.cp; EV = B[B.y == 1]; CT = B[B.y == 0]; rows = []
for lo, hi, nm in ((-120, -3, 'before: 2 min'), (-30, -3, 'before: 30 s'), (3, 30, 'after: 30 s'), (3, 120, 'after: 2 min')):
    for kind in sorted(O1.kind.unique()):
        ev_hit = []; ct_hit = []
        for (u, e), g in O1.groupby(['und', 'expiry']):
            t = np.sort(g[g.kind == kind].te.values)
            for df, lst in ((EV, ev_hit), (CT, ct_hit)):
                q = df[(df.und == u) & (df.expiry == e)].t.values; l = np.searchsorted(t, q + lo, 'left'); h = np.searchsorted(t, q + hi, 'right'); lst += list(h > l)
        rows.append(dict(window=nm, order_kind=kind, share_of_pairs=np.mean(ev_hit), share_of_control_seconds=np.mean(ct_hit), lift=np.mean(ev_hit) / max(np.mean(ct_hit), 1e-9)))
FL = pd.DataFrame(rows); FL.round(4).to_csv(f'{OUT}/bl_bk_flow.csv', index=False)
R = {nm: FL[FL.window == nm].sort_values('lift', ascending=False).head(6).round(3).to_dict('records') for nm in FL.window.unique()}; rec('bk3', R); print(FL[FL.share_of_pairs > .05].sort_values(['window', 'lift'], ascending=[True, False]).round(3).to_string(index=False))
