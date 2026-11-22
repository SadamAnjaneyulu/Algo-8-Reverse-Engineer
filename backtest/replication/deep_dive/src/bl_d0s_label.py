"""D0 chunk 1 (plan reports/D0_SELLS_PLAN.md): label every D0 body sell order.
pair = CE and PE sell orders at the same strike within 3 s (one-to-one, closest first); grid pair = first order of the pair inside a grid-A window
(minute-of-hour 1-3, 16-18, 31-33, 46-48); off-grid pair; solo = unpaired.
Outputs outputs/bl_d0s_orders.pkl.gz (one row per sell order: cid, tod, j, cp, strike, lots, px, lab, pid), outputs/bl_d0s_bb.pkl.gz (D0 body buy-backs), bl_summary_d0s0.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); GRID = {1, 2, 3, 16, 17, 18, 31, 32, 33, 46, 47, 48}
def label():
    rows = []; bbs = []
    for i, r in enumerate(CY.itertuples()):
        z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.dayno == 1) & (O.module == 'num')]
        s = z[z.role == 'open_short'].sort_values(['tod', 'row']); ce = s[s.cp == 'CE']; pe = s[s.cp == 'PE']; cand = []
        for a in ce.itertuples():
            for b in pe[(pe.strike == a.strike) & ((pe.tod - a.tod).abs() <= 3)].itertuples(): cand.append((abs(b.tod - a.tod), a.Index, b.Index))
        used = set(); pid = {}; n = 0
        for _, a, b in sorted(cand):
            if a in used or b in used: continue
            used.add(a); used.add(b); pid[a] = pid[b] = n; n += 1
        for q in s.itertuples():
            rows.append(dict(cid=i, und=r.und, version=r.version, tod=float(q.tod), j=int((q.tod - 33300) // 60), cp=q.cp, strike=float(q.strike), lots=int(q.lots), px=float(q.px_avg), step=float(q.step), pid=pid.get(q.Index, -1)))
        b = z[z.role == 'cover_short']
        for q in b.itertuples(): bbs.append(dict(cid=i, tod=float(q.tod), j=int((q.tod - 33300) // 60), cp=q.cp, strike=float(q.strike), lots=int(q.lots), px=float(q.px_avg)))
    S = pd.DataFrame(rows); B = pd.DataFrame(bbs)
    first = S[S.pid >= 0].groupby(['cid', 'pid']).tod.min().rename('t0').reset_index(); S = S.merge(first, on=['cid', 'pid'], how='left')
    moh = ((S.t0 // 60) % 60); S['lab'] = np.where(S.pid < 0, 'solo', np.where(moh.isin(GRID), 'grid_pair', 'offgrid_pair'))
    return S, B
if __name__ == '__main__':
    S, B = label(); pd.to_pickle(S, f'{OUT}/bl_d0s_orders.pkl.gz'); pd.to_pickle(B, f'{OUT}/bl_d0s_bb.pkl.gz')
    t = S.groupby('lab').agg(orders=('lots', 'size'), lots=('lots', 'sum')); t['share_lots'] = t.lots / t.lots.sum(); print(t.round(3).to_string())
    R = dict(orders=int(len(S)), lots=int(S.lots.sum()), by_label=t.lots.astype(int).to_dict(), share=t.share_lots.round(4).to_dict(), bb_orders=int(len(B)), bb_lots=int(B.lots.sum())); rec('d0s0', R); print(R)
