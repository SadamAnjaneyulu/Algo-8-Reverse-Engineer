"""Buy-back third pass, step 7: buy-backs of lots in profit (ratio <= 1 at the decision). Lot type, holding time, minute-clock, same-strike partner (other right) bought back within 5 s, stop-like buy-back (>= 1.5x) on any right within 5 s, new sells within 5 s (by right), time of day, premium level. Compared with in-loss buy-backs.
Output bl_bt_profit.csv, bl_summary_bt7.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); EV = pd.read_csv(f'{OUT}/bl_bb_events.csv'); R = {}
L = X[X.y == 1].drop_duplicates('lid'); B = O[(O.dayno == 0) & (O.module == 'num') & (O.role == 'cover_short')]; rows = []
for x in L.itertuples():
    r = CY.iloc[x.cid]; Bc = B[(B.und == r.und) & (B.expiry == r.expiry)]; bb = Bc[(Bc.cp == x.cp) & (Bc.strike == x.strike) & (((Bc.te - 33300) // 60) == x.j)]
    if not len(bb): continue
    t = bb.te.iloc[0]; w = Bc[((Bc.te - t).abs() <= 5)]; ev = EV[(EV.cid == x.cid) & ((EV.te - t).abs() <= 5)]; s = SD[(SD.cid == x.cid) & ((SD.te - t).abs() <= 5)]
    oth = 'PE' if x.cp == 'CE' else 'CE'
    rows.append(dict(state='in profit' if x.ratio_h <= 1 else 'in loss', typ=x.typ, held=x.held, ratio=x.ratio_h, sec0=int(round(t % 60)) % 60 == 0, hour=int(t // 3600),
                     partner_same_strike_other_right=int(len(w[(w.cp == oth) & (w.strike == x.strike)]) > 0), stop_like_any_right=int((ev.r_ref_min >= 1.5).any()), stop_like_same_right=int(((ev.r_ref_min >= 1.5) & (ev.cp == x.cp)).any()), stop_like_other_right=int(((ev.r_ref_min >= 1.5) & (ev.cp == oth)).any()),
                     sell_same_right=int((s.cp == x.cp).any()), sell_other_right=int((s.cp == oth).any()), itm=None))
C = pd.DataFrame(rows).drop(columns='itm'); C.to_csv(f'{OUT}/bl_bt_profit.csv', index=False)
T = C.groupby('state').mean(numeric_only=True).round(3); T['n'] = C.groupby('state').size(); print(T.T.to_string())
p = C[C.state == 'in profit']; print('profit: lot type', p.typ.value_counts().to_dict(), '| hour', p.hour.value_counts().sort_index().to_dict())
p = p.assign(cls=np.select([p.stop_like_other_right == 1, p.stop_like_same_right == 1, p.sell_same_right == 1, p.sell_other_right == 1], ['stop on the other right (same moment)', 'stop on the same right (cluster)', 'roll: new sell on the same right', 'new sell on the other right'], 'none'))
print('profit buy-backs by coincident event:', p.cls.value_counts().to_dict()); R['profit_classes'] = p.cls.value_counts().to_dict(); R['table'] = T.reset_index().to_dict('records'); rec('bt7', R)
