"""Buy-back third pass, step 6: context of each lot buy-back by lot type: second of minute (0 = minute-clocked), orders within +-5 s (new body sells by type, on same/other right; other buy-backs same right / other right; how many lots of the same type bought together), and the lot's own ratio and holding time.
Outputs bl_bt_ctx.csv, bl_summary_bt6.json"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); X = pd.read_pickle(f'{OUT}/bl_bt_lot.pkl.gz'); R = {}
L = X[X.y == 1][['lid', 'cid', 'j', 'cp', 'strike', 'typ', 'held', 'ratio_h', 'adv']].drop_duplicates('lid')
B = O[(O.dayno == 0) & (O.module == 'num') & (O.role == 'cover_short')].copy(); rows = []
for x in L.itertuples():
    r = CY.iloc[x.cid]; bb = B[(B.und == r.und) & (B.expiry == r.expiry) & (B.cp == x.cp) & (B.strike == x.strike) & (((B.te - 33300) // 60) == x.j)]
    if not len(bb): continue
    t = bb.te.iloc[0]; s = SD[(SD.cid == x.cid) & ((SD.te - t).abs() <= 5)]; ob = B[(B.und == r.und) & (B.expiry == r.expiry) & ((B.te - t).abs() <= 5)]
    rows.append(dict(typ=x.typ, held=x.held, ratio=x.ratio_h, adv=x.adv, sec0=int(round(t % 60)) % 60 == 0, new_sell_any=int(len(s) > 0), new_sell_reactive=int((s.typ == 'reactive').any()), new_sell_sched=int((s.typ == 'scheduled').any()), new_sell_same_right=int((s.cp == x.cp).any()),
                     other_bb_same_right=int(len(ob[(ob.cp == x.cp) & (ob.strike != x.strike)]) > 0), other_bb_other_right=int(len(ob[ob.cp != x.cp]) > 0), lots_same_contract=int(ob[(ob.cp == x.cp) & (ob.strike == x.strike)].lots.sum())))
C = pd.DataFrame(rows); C.to_csv(f'{OUT}/bl_bt_ctx.csv', index=False)
C['fresh'] = C.held <= 10; T = C.groupby(['typ', 'fresh']).mean(numeric_only=True).round(3); T['n'] = C.groupby(['typ', 'fresh']).size(); print(T.drop(columns=['adv']).to_string())
# reference: how often does any reactive/scheduled sell happen within +-5 s of a random second (base rate)
rng = np.random.default_rng(0); base = []
for i, r in enumerate(CY.itertuples()):
    s = SD[SD.cid == i]
    for t in rng.uniform(34200, 55800, 200): base.append(dict(any=int((np.abs(s.te - t) <= 5).any()), reactive=int(((np.abs(s.te - t) <= 5) & (s.typ == 'reactive')).any())))
print('base rate within +-5 s of a random second:', pd.DataFrame(base).mean().round(3).to_dict()); rec('bt6', dict(table=T.reset_index().astype({'fresh': str}).to_dict('records')))
