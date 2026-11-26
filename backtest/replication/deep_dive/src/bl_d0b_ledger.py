"""D0 chunk 2 data step: body short-lot ledger through D-1 and D0 (real orders). Lots enter at their decision price (ref_px); on a body buy-back the lot removed is the
highest-ratio open lot on the contract (lowest entry, the D-1 convention); FIFO kept as a check. D-1 lots carry the D-1 sell type (SDL t2), D0 lots the chunk-1 label.
Outputs outputs/bl_d0b_removed.pkl.gz (one row per D0 body buy-back lot: cid, tod, j, cp, strike, px, ref_px, entry, origin, typ, entry_tod, entry_day, ratio, ratio_fifo, origin_fifo),
outputs/bl_d0b_book.pkl.gz (per cycle: list of open lots at the D0 open and every D0 lot with entry/exit, for the hazard panel), bl_summary_d0b0.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); S = pd.read_pickle(f'{OUT}/bl_d0s_orders.pkl.gz'); SDL = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz')
SDL['t2'] = np.where(SDL.deep, 'deep', np.where((SDL.typ == 'solo') & (SDL.te >= 54000), 'late', SDL.typ))
rem = []; books = {}; lid = 0
for i, r in enumerate(CY.itertuples()):
    z = O[(O.und == r.und) & (O.expiry == r.expiry) & (O.module == 'num') & O.role.isin(['open_short', 'cover_short'])].sort_values(['dayno', 'tod', 'row'])
    if not (z.dayno == 1).any(): continue
    l1 = {(round(x.te, 3), x.cp, int(x.strike)): x.t2 for x in SDL[SDL.cid == i].itertuples()}; l0 = {(round(x.tod, 3), x.cp, int(x.strike)): x.lab for x in S[S.cid == i].itertuples()}
    book = {}; fifo = {}; allots = {}; at_open = None
    for q in z.itertuples():
        if q.dayno == 1 and at_open is None: at_open = [dict(l) for k in book for l in book[k]]
        k = (q.cp, int(q.strike)); t = float(q.tod)
        if q.role == 'open_short':
            typ = l1.get((round(q.te, 3), q.cp, int(q.strike)), 'solo') if q.dayno == 0 else l0.get((round(q.tod, 3), q.cp, int(q.strike)), 'solo')
            for _ in range(int(q.lots)):
                L = dict(lid=lid, cid=i, cp=q.cp, strike=int(q.strike), entry=float(q.ref_px), entry_px=float(q.px_avg), entry_tod=t, entry_day=int(q.dayno), typ=typ, exit_tod=np.nan, exit_ref=np.nan)
                book.setdefault(k, []).append(L); fifo.setdefault(k, []).append(L); allots[lid] = L; lid += 1
        elif book.get(k):
            for _ in range(int(q.lots)):
                if not book.get(k): break
                a = int(np.argmin([l_['entry'] for l_ in book[k]])); L = book[k].pop(a); ff = fifo[k][0]; fifo[k] = fifo[k][1:]
                L['exit_tod'] = t; L['exit_day'] = int(q.dayno); L['exit_ref'] = float(q.ref_px)
                if q.dayno == 1:
                    rem.append(dict(cid=i, tod=t, j=int((t - 33300) // 60), cp=q.cp, strike=int(q.strike), px=float(q.px_avg), ref_px=float(q.ref_px), entry=L['entry'], origin='D-1' if L['entry_day'] == 0 else 'D0', typ=L['typ'],
                                    entry_tod=L['entry_tod'], entry_day=L['entry_day'], ratio=float(q.ref_px) / L['entry'], ratio_fifo=float(q.ref_px) / ff['entry'], origin_fifo='D-1' if ff['entry_day'] == 0 else 'D0', lid=L['lid']))
    if at_open is None: at_open = [dict(l) for k in book for l in book[k]]
    books[i] = dict(at_open=at_open, lots=[allots[x] for x in allots])
X = pd.DataFrame(rem); pd.to_pickle(X, f'{OUT}/bl_d0b_removed.pkl.gz'); pd.to_pickle(books, f'{OUT}/bl_d0b_book.pkl.gz')
R = dict(cycles=len(books), bb_lots=int(len(X)), by_origin=X.origin.value_counts().to_dict(), in_loss=float((X.ratio > 1).mean()), in_loss_fifo=float((X.ratio_fifo > 1).mean()), ratio_q=X.ratio.quantile([.1, .25, .5, .75, .9]).tolist(),
         carried_open_lots=int(sum(len(b['at_open']) for b in books.values())), origin_agree_fifo=float((X.origin == X.origin_fifo).mean()))
rec('d0b0', R); print(R)
